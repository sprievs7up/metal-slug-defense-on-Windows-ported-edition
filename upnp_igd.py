"""UPnP 互联网网关（IGD）端口映射（N4，直接连接的可选辅助，R4）。

房主选择“直接连接”时，可请求路由器把对战用的 UDP 端口转发到本机（路由器支持并开启 UPnP 时有效），并取得路由器的公网 IP，
以便告诉对方“公网IP:端口”。结束时删除映射；映射另设租期（默认 2 小时），游戏异常退出时由路由器到期删除。
流程：SSDP 多播搜索（239.255.255.250:1900）→ 读取设备描述 XML → 找到 WANIPConnection 或 WANPPPConnection 服务 →
SOAP AddPortMapping（路由器只支持永久映射时以租期 0 重试）→ GetExternalIPAddress。
安全：只访问位于私有网段或本机的设备描述地址（局域网中的设备不能把游戏引向互联网地址）。
"""
import http.client
import ipaddress
import socket
import time
import urllib.parse
import xml.etree.ElementTree as ET

SSDP = ('239.255.255.250', 1900)
SEARCH_TARGETS = ('urn:schemas-upnp-org:device:InternetGatewayDevice:1',
                  'urn:schemas-upnp-org:device:InternetGatewayDevice:2',
                  'urn:schemas-upnp-org:service:WANIPConnection:1',
                  'urn:schemas-upnp-org:service:WANIPConnection:2',
                  'urn:schemas-upnp-org:service:WANPPPConnection:1')
SERVICES = ('urn:schemas-upnp-org:service:WANIPConnection:2', 'urn:schemas-upnp-org:service:WANIPConnection:1',
            'urn:schemas-upnp-org:service:WANPPPConnection:1')
LEASE = 7200


def local_location(url):
    try:
        host = urllib.parse.urlsplit(url).hostname
        address = ipaddress.ip_address(socket.gethostbyname(host))
        return address.is_private or address.is_loopback or address.is_link_local
    except (ValueError, OSError, TypeError):
        return False


def discover(timeout=2.5, target=SSDP, bind=None):
    """SSDP 搜索，返回设备描述地址列表（LOCATION）。bind：本地地址（测试时为回环）。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if bind is not None:
        sock.bind(bind)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.settimeout(0.2)
    locations = []
    try:
        for st in SEARCH_TARGETS:
            message = ('M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 2\r\n'
                       f'ST: {st}\r\n\r\n').encode('ascii')
            sock.sendto(message, target)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, _ = sock.recvfrom(4096)
            except (socket.timeout, ConnectionResetError):
                continue
            for line in data.decode('latin-1').split('\r\n'):
                if line.lower().startswith('location:'):
                    url = line.split(':', 1)[1].strip()
                    if url not in locations and local_location(url):
                        locations.append(url)
            if locations and time.monotonic() > deadline - timeout + 1.0:
                break
    finally:
        sock.close()
    return locations


def http_request(url, method='GET', body=None, headers=None, timeout=3.0):
    parts = urllib.parse.urlsplit(url)
    connection = http.client.HTTPConnection(parts.hostname, parts.port or 80, timeout=timeout)
    try:
        path = parts.path or '/'
        if parts.query:
            path += '?' + parts.query
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, response.read(1 << 20)
    finally:
        connection.close()


def find_service(location):
    """读取设备描述，返回 (服务类型, 控制地址)。"""
    status, raw = http_request(location)
    if status != 200:
        raise OSError(f'device description HTTP {status}')
    root = ET.fromstring(raw)
    base = location
    for element in root.iter():
        if element.tag.endswith('URLBase') and element.text:
            base = element.text.strip()
    for service in root.iter():
        if not service.tag.endswith('service'):
            continue
        fields = {child.tag.split('}')[-1]: (child.text or '').strip() for child in service}
        if fields.get('serviceType') in SERVICES and fields.get('controlURL'):
            control = urllib.parse.urljoin(base, fields['controlURL'])
            if local_location(control):
                return fields['serviceType'], control
    raise OSError('no WANIPConnection / WANPPPConnection service')


def soap(control, service, action, arguments):
    body = ('<?xml version="1.0"?>\r\n<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
            f'<u:{action} xmlns:u="{service}">'
            + ''.join(f'<{k}>{v}</{k}>' for k, v in arguments) +
            f'</u:{action}></s:Body></s:Envelope>').encode('utf-8')
    status, raw = http_request(control, 'POST', body, {'Content-Type': 'text/xml; charset="utf-8"',
                                                       'SOAPAction': f'"{service}#{action}"'})
    values = {}
    try:
        for element in ET.fromstring(raw).iter():
            values[element.tag.split('}')[-1]] = (element.text or '').strip()
    except ET.ParseError:
        pass
    return status, values


def local_ip_toward(url):
    host = urllib.parse.urlsplit(url).hostname
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect((host, 9))
        return probe.getsockname()[0]
    finally:
        probe.close()


def open_port(port, description='MSD S1XLV', lease=LEASE, target=SSDP, timeout=2.5, bind=None):
    """请求路由器把外部 UDP 端口 port 转发到本机同一端口。返回映射信息（ok、external_ip、external_port 等）或 {ok: False, error}。"""
    try:
        locations = discover(timeout, target, bind)
        if not locations:
            return {'ok': False, 'error': 'no_gateway'}
        errors = []
        for location in locations:
            try:
                service, control = find_service(location)
                internal = local_ip_toward(control)
                for duration in (lease, 0):
                    status, values = soap(control, service, 'AddPortMapping', (
                        ('NewRemoteHost', ''), ('NewExternalPort', port), ('NewProtocol', 'UDP'), ('NewInternalPort', port),
                        ('NewInternalClient', internal), ('NewEnabled', 1), ('NewPortMappingDescription', description),
                        ('NewLeaseDuration', duration)))
                    if status == 200:
                        break
                    errors.append(f"AddPortMapping {status} {values.get('errorCode')} {values.get('errorDescription')}")
                    if values.get('errorCode') != '725':          # 725：只支持永久映射
                        break
                if status != 200:
                    continue
                _, values = soap(control, service, 'GetExternalIPAddress', ())
                return {'ok': True, 'external_ip': values.get('NewExternalIPAddress'), 'external_port': port,
                        'internal': [internal, port], 'control': control, 'service': service, 'lease': duration}
            except (OSError, ET.ParseError, http.client.HTTPException) as error:
                errors.append(f'{location}: {type(error).__name__}: {error}')
        return {'ok': False, 'error': '; '.join(errors) or 'failed'}
    except OSError as error:
        return {'ok': False, 'error': f'{type(error).__name__}: {error}'}


def close_port(mapping):
    """删除 open_port 建立的映射。"""
    if not mapping or not mapping.get('ok'):
        return False
    try:
        status, _ = soap(mapping['control'], mapping['service'], 'DeletePortMapping', (
            ('NewRemoteHost', ''), ('NewExternalPort', mapping['external_port']), ('NewProtocol', 'UDP')))
        return status == 200
    except (OSError, http.client.HTTPException):
        return False
