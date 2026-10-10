"""联机网络层（N4，docs/netcode/N4_NETWORK_LAYER_2026-10-10.md）。

一名对手的全部通信使用一个 UDP 套接字（端点 Endpoint）：
- 连接：加入方向房主地址重复发送 CONNECT，房主以 ACCEPT 应答（Listener / Connector）。连接令牌为 64 位随机数，
  之后每个包都带令牌；令牌正确但来源地址改变时（路由器重新映射端口等）改用新地址（地址迁移）。
- 可靠消息（握手、编队、结果、再战）：JSON 消息按 1000 字节分片，逐片序号、累计确认加选择确认、超时重传、按序交付。
- 对战数据（不可靠）：输入（每包冗余携带对方未确认的全部本方输入）、周期校验值、心跳；字段与 N3 的 UdpTransport 相同，
  另带轮次号（再战时丢弃上一轮迟到的包）。PeerLink 提供与 UdpTransport 相同的接口，NetplayBattle 直接使用。
- 断线：1 秒收不到任何包为“连接不稳定”（interrupted），超过 disconnect_after（默认 10 秒）为“已断线”（disconnected，
  向对方发 BYE 后不再恢复）；期间恢复收包即回到 connected，对战由冗余输入自动补齐。
- 局域网发现：房主在发现端口（47630）应答 QUERY（LanResponder）；加入方向广播地址发送 QUERY 并列出房间（LanScanner）。
- 远程会合（Rendezvous，配合社区自建的 rendezvous_server.py）：房主以对战用的同一套接字登记，得到房间码；加入方以房间码
  取得房主的公网与内网地址，服务器同时把加入方地址告知房主。双方互发打洞包（房主 PUNCH、加入方 CONNECT）；
  收到对方打洞包时把其来源地址加入候选（对称型 NAT 一侧的新端口）。打不通时报告无法连接（不提供中继）。
- 测试：端点可模拟单向延迟、抖动、丢包、重复与断网时段；SimNat 以本机回环套接字模拟路由器的映射与过滤
  （full_cone、port_restricted、symmetric），用于验证打洞成功与失败两种结果。
- 观战（N5.5b，netplay_spectate）：连接请求带 role='spectator' 时，房主端点交给 on_extra_connect（SpectatorHub.accept）处理，
  观战连接登记在 extra_links（按连接令牌分派），与对手的连接共用同一套接字。
- N6b（docs/netcode/N6B_REMOTE_DIRECT_2026-10-10.md）：IPv4 与 IPv6 双栈——端点在同一端口另开一个 IPv6 套接字（只收发 IPv6），
  按目的地址的地址族选择套接字；地址一律以 (主机, 端口) 二元组表示。房主可设定房间码，连接请求中的房间码不符时以 wrong_code 拒绝。
"""
import base64
import hashlib
import heapq
import ipaddress
import json
import os
import random
import socket
import struct
import time
import zlib
from collections import deque

PROTOCOL = 5                              # 与 content_manifest.PROTOCOL 相同（握手前即比较，不同时拒绝连接）；3：N5 校验 tag 包、分歧消息；4：N6a 每帧输入 32 位；5：N6b 连接请求带房间码
DISCOVERY_PORT, GAME_PORT, RENDEZVOUS_PORT = 47630, 47631, 47632
MAGIC, LAN_MAGIC, RDV_MAGIC = b'MSDN', b'MSDL', b'MSDR'
RDV_VERSION = 1
HEADER = struct.Struct('<4sBBQI')         # 魔数、协议版本、类型、连接令牌、包序号
INPUT = struct.Struct('<HiiiiH')          # 轮次、确认帧、发送方当前帧、帧优势、首帧、个数（随后逐帧输入，每帧 uint32，协议 4）
INPUT_VALUE = struct.Struct('<I')
CHECKSUM = struct.Struct('<HiII')         # 轮次、帧、语义校验 h、深度校验 d（N3/N4 格式，保留供测试）
TAGS = struct.Struct('<HB')               # N5：轮次、个数（随后每项为帧 int32 与 tag uint64）
TAG_ENTRY = struct.Struct('<iQ')
PING = struct.Struct('<dI')               # 发送时刻、心跳序号（PONG 原样带回）
CHUNK = struct.Struct('<IB')              # 可靠分片序号、标志（1 首片、2 末片、4 zlib 压缩）
ACK = struct.Struct('<II')                # 累计确认（已按序收到的最后一片）、其后 32 片的选择确认位图
(KIND_INPUT, KIND_CHECKSUM, KIND_PING, KIND_PONG, KIND_BYE, KIND_CONNECT, KIND_ACCEPT, KIND_REJECT,
 KIND_DATA, KIND_ACK, KIND_PUNCH, KIND_TAGS) = range(1, 13)
BATTLE_KINDS = (KIND_INPUT, KIND_CHECKSUM, KIND_TAGS)
CHUNK_BYTES = 1000
WINDOW = 32                               # 可靠分片的在途上限
MAX_MESSAGE = 4 << 20                     # 单条可靠消息解压后的上限
INTERRUPT_AFTER = 1.0
DISCONNECT_AFTER = 10.0
PING_EVERY = 0.5
CONNECT_EVERY = 0.1
PUNCH_EVERY = 0.1
SIO_UDP_CONNRESET = 0x9800000C


def now():
    return time.perf_counter()


def new_token():
    while True:
        token = int.from_bytes(os.urandom(8), 'little')
        if token:
            return token


def disable_connreset(sock):
    """Windows：发往无人监听端口的 UDP 包引起的 ICMP 端口不可达不再以 WSAECONNRESET 报告给后续 recvfrom。"""
    if os.name != 'nt':
        return
    try:
        import ctypes
        from ctypes import wintypes
        ws2 = ctypes.WinDLL('ws2_32')
        ws2.WSAIoctl.argtypes = [ctypes.c_size_t, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p,
                                 wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p, ctypes.c_void_p]
        value, returned = wintypes.DWORD(0), wintypes.DWORD(0)
        ws2.WSAIoctl(sock.fileno(), SIO_UDP_CONNRESET, ctypes.byref(value), 4, None, 0, ctypes.byref(returned), None, None)
    except Exception:
        pass


def split_address(text, default_port):
    """'1.2.3.4:47631'、'1.2.3.4'、'[2001:db8::1]:47631'、'2001:db8::1'（无括号时整段为地址、端口取默认）、'name.example:47631'
    → (主机, 端口)。只做格式拆分，不解析域名。"""
    text = text.strip()
    host, port = text, default_port
    if text.startswith('['):
        end = text.find(']')
        if end < 0:
            raise ValueError('地址格式无效: ' + text)
        host, rest = text[1:end], text[end + 1:]
        if rest:
            if not rest.startswith(':'):
                raise ValueError('地址格式无效: ' + text)
            port = int(rest[1:])
    elif text.count(':') == 1:
        host, port = text.rsplit(':', 1)
        port = int(port)
    port = int(port)
    if not host or not 0 < port < 65536:
        raise ValueError('地址或端口无效: ' + text)
    return host, port


def resolve_addresses(text, default_port):
    """地址文字 → 候选地址列表 [(IP, 端口)]（IPv4 在前）。IP 字面量不查询域名服务；域名可能需要等待（调用方在后台线程中进行）。"""
    host, port = split_address(text, default_port)
    try:
        return [(str(ipaddress.ip_address(host)), port)]
    except ValueError:
        pass
    found = []
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            for info in socket.getaddrinfo(host, port, family, socket.SOCK_DGRAM):
                found.append((info[4][0], port))
        except OSError:
            pass
    return list(dict.fromkeys(found))


def parse_address(text, default_port):
    """地址文字 → 第一个候选 (IP, 端口)（IPv4 优先）；解析不到时 ValueError。"""
    found = resolve_addresses(text, default_port)
    if not found:
        raise ValueError('无法解析地址: ' + text)
    return found[0]


def format_address(address):
    """(IP, 端口) → 显示用文字：IPv4 为 'a.b.c.d:端口'，IPv6 为 '[地址]:端口'。"""
    host, port = address[0], address[1]
    return f'[{host}]:{port}' if ':' in str(host) else f'{host}:{port}'


def local_ipv4():
    """本机 IPv4 地址（不含回环）：主机名解析结果，加上默认路由所在网卡的地址（以未发送的 UDP connect 求得）。"""
    found = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(info[4][0])
    except OSError:
        pass
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(('192.0.2.1', 9))          # 文档保留地址，不实际发送
            found.append(probe.getsockname()[0])
        finally:
            probe.close()
    except OSError:
        pass
    return [ip for ip in dict.fromkeys(found) if not ip.startswith('127.') and ip != '0.0.0.0']


IPV6_EXCLUDED = tuple(ipaddress.ip_network(n) for n in ('2001::/32', '2001:db8::/32', '2002::/16'))  # Teredo、文档、6to4


def ipv6_kind(text):
    """'global'（全局单播，不含 Teredo / 6to4 / 文档地址）、'ula'（fc00::/7，局域网或虚拟局域网）或 None（其他）。"""
    try:
        address = ipaddress.IPv6Address(str(text).split('%')[0])
    except ValueError:
        return None
    if address in ipaddress.ip_network('2000::/3') and not any(address in n for n in IPV6_EXCLUDED):
        return 'global'
    if address in ipaddress.ip_network('fc00::/7'):
        return 'ula'
    return None


def local_ipv6():
    """本机可用于连接的 IPv6 地址（全局单播在前，其次 ULA；不含回环、链路本地、Teredo）：默认路由的源地址（未发送的 UDP connect）
    与主机名解析结果。"""
    found = []
    try:
        probe = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        try:
            probe.connect(('2001:4860:4860::8888', 9))   # 不实际发送，只取路由所选的源地址
            found.append(probe.getsockname()[0])
        finally:
            probe.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET6):
            found.append(info[4][0].split('%')[0])
    except OSError:
        pass
    found = [ip for ip in dict.fromkeys(found) if ipv6_kind(ip)]
    return sorted(found, key=lambda ip: ipv6_kind(ip) != 'global')


def hex64(text):
    try:
        value = int(str(text), 16)
    except (TypeError, ValueError):
        return None
    return value if 0 < value < 1 << 64 else None


def valid_endpoint(value):
    try:
        ip, port = value
        ipaddress.ip_address(ip)
        return isinstance(port, int) and 0 < port < 65536
    except (TypeError, ValueError):
        return False


def open_udp(family, bind):
    sock = socket.socket(family, socket.SOCK_DGRAM)
    try:
        if family == socket.AF_INET6:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
        except OSError:
            pass
        sock.bind(bind)
        disable_connreset(sock)
        sock.setblocking(False)
        return sock
    except OSError:
        sock.close()
        raise


class Endpoint:
    """UDP 套接字：按包头魔数分派收到的包（MSDN 对战、MSDR 会合），并可模拟网络条件（测试用）：
    单向延迟、抖动（会造成乱序）、丢包、重复，以及断网时段（blackout：期间收发全部丢弃）。"""

    def __init__(self, bind=('0.0.0.0', 0), sock=None, latency_ms=0.0, jitter_ms=0.0, loss=0.0, duplicate=0.0, seed=0, ipv6=None):
        """ipv6（N6b）：None 为自动——IPv4 绑定到 0.0.0.0 时在同一端口另开 IPv6 套接字（绑定 ::）；字符串为 IPv6 绑定地址
        （测试用 '::1'）；False 不开。IPv6 不可用或端口被占用时只用 IPv4。传入 sock（测试用的模拟路由器）时不开 IPv6。"""
        self.sock6 = None
        if sock is None:
            sock = open_udp(socket.AF_INET, bind)
            host6 = ('::' if bind[0] in ('0.0.0.0', '') else None) if ipv6 is None else (ipv6 or None)
            if host6:
                try:
                    self.sock6 = open_udp(socket.AF_INET6, (host6, sock.getsockname()[1]))
                except OSError:
                    self.sock6 = None
        sock.setblocking(False)
        self.sock = sock
        self.latency = latency_ms / 1000.0
        self.jitter = jitter_ms / 1000.0
        self.loss = loss
        self.duplicate = duplicate
        self.rng = random.Random(seed)
        self.outgoing = []                  # 堆：(到期时刻, 序号, 数据, 地址)
        self.counter = 0
        self.blackout_until = 0.0
        self.handlers = {}                  # 魔数 → handle(data, address)
        self.extra_links = {}               # 连接令牌 → 观战连接（PeerLink，N5.5b）；由已登记的 MSDN 处理者转交
        self.on_extra_connect = None        # 回调 (令牌, 请求, 地址)：role='spectator' 的连接请求
        self.stats = {'sent': 0, 'received': 0, 'bytes_sent': 0, 'bytes_received': 0, 'dropped': 0,
                      'duplicated': 0, 'blackout_dropped': 0, 'send_errors': 0, 'unhandled': 0}

    @property
    def address(self):
        return self.sock.getsockname()

    def candidates(self):
        """本方可被直接访问的地址（内网候选）：绑定到具体地址时为该地址，绑定 0.0.0.0 时为各网卡地址加端口。"""
        own = getattr(self.sock, 'candidates', None)
        if own is not None:
            return own()
        ip, port = self.address[:2]
        found = [(ip, port)] if ip not in ('0.0.0.0', '') else [(address, port) for address in local_ipv4()]
        if self.sock6 is not None:
            ip6, port6 = self.sock6.getsockname()[:2]
            found += [(ip6, port6)] if ip6 != '::' else [(address, port6) for address in local_ipv6()]
        return found

    def blackout(self, seconds):
        self.blackout_until = now() + seconds

    def in_blackout(self):
        return now() < self.blackout_until

    def send(self, data, address):
        if self.in_blackout():
            self.stats['blackout_dropped'] += 1
            return
        if self.loss and self.rng.random() < self.loss:
            self.stats['dropped'] += 1
            return
        copies = 2 if self.duplicate and self.rng.random() < self.duplicate else 1
        self.stats['duplicated'] += copies - 1
        for _ in range(copies):
            delay = self.latency + (self.rng.random() * self.jitter if self.jitter else 0.0)
            if delay <= 0:
                self.transmit(data, address)
            else:
                self.counter += 1
                heapq.heappush(self.outgoing, (now() + delay, self.counter, data, address))

    def transmit(self, data, address):
        sock = self.sock6 if ':' in str(address[0]) else self.sock
        if sock is None:
            self.stats['send_errors'] += 1
            return
        try:
            sock.sendto(data, address)
            self.stats['sent'] += 1
            self.stats['bytes_sent'] += len(data)
        except OSError:
            self.stats['send_errors'] += 1

    def flush(self):
        t = now()
        while self.outgoing and self.outgoing[0][0] <= t:
            _, _, data, address = heapq.heappop(self.outgoing)
            self.transmit(data, address)

    def poll(self, limit=1024):
        """发送到期的模拟延迟包，收取全部到达的包并分派。"""
        self.flush()
        for sock in (self.sock, self.sock6):
            if sock is None:
                continue
            for _ in range(limit):
                try:
                    data, address = sock.recvfrom(65535)
                except (BlockingIOError, InterruptedError):
                    break
                except ConnectionResetError:
                    continue
                except OSError:
                    break
                if self.in_blackout():
                    self.stats['blackout_dropped'] += 1
                    continue
                self.stats['received'] += 1
                self.stats['bytes_received'] += len(data)
                handler = self.handlers.get(data[:4])
                if handler is None:
                    self.stats['unhandled'] += 1
                    continue
                handler(data, (str(address[0]).split('%')[0], address[1]))

    def close(self):
        for sock in (self.sock, self.sock6):
            if sock is None:
                continue
            try:
                sock.close()
            except OSError:
                pass


def packet(kind, token, seq, payload=b''):
    return HEADER.pack(MAGIC, PROTOCOL, kind, token, seq & 0xffffffff) + payload


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def parse_json(raw):
    try:
        value = json.loads(raw.decode('utf-8'))
        return value if isinstance(value, dict) else None
    except (UnicodeDecodeError, ValueError):
        return None


class PeerLink:
    """与一名对手的连接（连接建立后）。可靠消息：send_message / messages；对战：与 N3 UdpTransport 相同的接口。
    每帧调用 service()（或对战中由 NetplayBattle 调用 poll()）。"""

    def __init__(self, endpoint, remote, token, role, info=None, disconnect_after=DISCONNECT_AFTER, register=True):
        self.endpoint, self.remote, self.token, self.role = endpoint, tuple(remote), token, role
        self.peer_info = info or {}           # 对方在 CONNECT/ACCEPT 中报告的名称与版本
        self.local_info = {}                  # 房主：重发 ACCEPT 时的本方信息
        self.disconnect_after = disconnect_after
        self.seq = 0
        t = now()
        self.created = self.last_receive = self.last_send = t
        self.last_ping = 0.0
        self.ping_id = 0
        self.state = 'connected'              # connected、interrupted、disconnected、closed
        self.state_since = t
        self.interruptions = []               # [(开始, 时长)]
        self.closed_reason = None
        # 可靠消息
        self.rel_next = 1
        self.rel_unacked = {}                 # 序号 → [包, 最近发送时刻, 发送次数]
        self.rel_queue = deque()
        self.rel_expected = 1
        self.rel_buffer = {}
        self.rel_parts = []
        self.rel_size = 0
        self.ack_due = False
        self.messages = deque()
        # 对战（UdpTransport 兼容字段）
        self.round = 0
        self.peer_ack = 0
        self.ack = 0
        self.peer_frame = 0
        self.peer_advantage = 0
        self.rtt = None
        self.srtt = None
        self.closed_by_peer = False
        self.battle_events = []
        self.stats = {'sent': 0, 'received': 0, 'bad': 0, 'stale_round': 0, 'retransmits': 0, 'migrations': 0,
                      'messages_sent': 0, 'messages_received': 0, 'duplicate_chunks': 0}
        if register:                          # 观战连接不登记（由对手连接或 Listener 按令牌转交）
            endpoint.handlers[MAGIC] = self.handle

    # ---------- 收发 ----------
    def send(self, data):
        self.endpoint.send(data, self.remote)
        self.last_send = now()
        self.stats['sent'] += 1

    def packet(self, kind, payload=b''):
        self.seq += 1
        return packet(kind, self.token, self.seq, payload)

    def handle(self, data, address):
        if len(data) < HEADER.size:
            self.stats['bad'] += 1
            return
        magic, version, kind, token, _ = HEADER.unpack_from(data)
        if token != self.token and kind != KIND_CONNECT:
            other = self.endpoint.extra_links.get(token)
            if other is not None and other is not self:
                other.handle(data, address)           # 观战连接的包
                return
        body = data[HEADER.size:]
        if kind == KIND_CONNECT:
            self.answer_connect(version, token, body, address)
            return
        if version != PROTOCOL or token != self.token:
            self.stats['bad'] += 1
            return
        if self.state in ('disconnected', 'closed'):
            return
        if address != self.remote:
            # 令牌正确而来源改变：对方的路由器重新映射了端口或对方换了网络。改用新地址。
            self.remote = tuple(address)
            self.stats['migrations'] += 1
        self.last_receive = now()
        self.stats['received'] += 1
        if kind == KIND_INPUT:
            if len(body) < INPUT.size:
                self.stats['bad'] += 1
                return
            rnd, ack, frame, advantage, first, count = INPUT.unpack_from(body)
            if rnd != self.round:
                self.stats['stale_round'] += 1
                return
            self.peer_ack = max(self.peer_ack, ack)
            if frame >= self.peer_frame:
                self.peer_frame, self.peer_advantage = frame, advantage
            raw = body[INPUT.size:INPUT.size + count * INPUT_VALUE.size]
            values = list(struct.unpack('<%dI' % count, raw)) if len(raw) == count * INPUT_VALUE.size else []
            if len(values) == count and len(self.battle_events) < 4096:
                self.battle_events.append(('input', (first, values)))
        elif kind == KIND_CHECKSUM:
            if len(body) < CHECKSUM.size:
                self.stats['bad'] += 1
                return
            rnd, frame, h, d = CHECKSUM.unpack_from(body)
            if rnd != self.round:
                self.stats['stale_round'] += 1
                return
            if len(self.battle_events) < 4096:
                self.battle_events.append(('checksum', (frame, (h, d))))
        elif kind == KIND_TAGS:
            if len(body) < TAGS.size:
                self.stats['bad'] += 1
                return
            rnd, count = TAGS.unpack_from(body)
            if rnd != self.round:
                self.stats['stale_round'] += 1
                return
            if len(body) < TAGS.size + count * TAG_ENTRY.size or count > 16:
                self.stats['bad'] += 1
                return
            for index in range(count):
                frame, value = TAG_ENTRY.unpack_from(body, TAGS.size + index * TAG_ENTRY.size)
                if len(self.battle_events) < 4096:
                    self.battle_events.append(('checksum_tag', (frame, value)))
        elif kind == KIND_PING:
            self.send(self.packet(KIND_PONG, body[:PING.size]))
        elif kind == KIND_PONG:
            if len(body) >= PING.size:
                sample = now() - PING.unpack_from(body)[0]
                if 0 <= sample < 30:
                    self.rtt = sample
                    self.srtt = sample if self.srtt is None else self.srtt * 0.875 + sample * 0.125
        elif kind == KIND_DATA:
            self.receive_chunk(body)
        elif kind == KIND_ACK:
            self.receive_ack(body)
        elif kind == KIND_BYE:
            self.closed_by_peer = True
            self.set_state('closed', 'peer_left')
        elif kind in (KIND_ACCEPT, KIND_PUNCH):
            pass                                   # 连接已建立后迟到的应答与打洞包

    def answer_connect(self, version, token, body, address):
        """房主：重复的 CONNECT（ACCEPT 丢失）重发 ACCEPT；其他加入方的 CONNECT 回复“房间已满”。"""
        if self.role != 'host':
            return
        if token == self.token and version == PROTOCOL:
            if self.state in ('connected', 'interrupted'):
                self.endpoint.send(packet(KIND_ACCEPT, token, 0, json_bytes(self.local_info)), address)
            return
        request = parse_json(body) or {}
        if request.get('role') == 'spectator' and version == PROTOCOL and request.get('protocol') == PROTOCOL:
            if self.endpoint.on_extra_connect is not None:
                self.endpoint.on_extra_connect(token, request, address)
            else:
                self.endpoint.send(packet(KIND_REJECT, token, 0, json_bytes({'reason': 'no_spectate', 'protocol': PROTOCOL})), address)
            return
        self.endpoint.send(packet(KIND_REJECT, token, 0, json_bytes({'reason': 'busy', 'protocol': PROTOCOL})), address)

    # ---------- 可靠消息 ----------
    def send_message(self, message):
        raw = json_bytes(message)
        flags = 0
        if len(raw) > 512:
            packed = zlib.compress(raw, 6)
            if len(packed) < len(raw):
                raw, flags = packed, 4
        parts = [raw[i:i + CHUNK_BYTES] for i in range(0, len(raw), CHUNK_BYTES)] or [b'']
        for index, part in enumerate(parts):
            self.rel_queue.append((flags | (1 if index == 0 else 0) | (2 if index == len(parts) - 1 else 0), part))
        self.stats['messages_sent'] += 1
        self.pump_reliable(now())

    def rto(self):
        base = self.srtt if self.srtt is not None else 0.3
        return min(2.0, max(0.1, base * 1.5 + 0.05))

    def pump_reliable(self, t):
        while self.rel_queue and len(self.rel_unacked) < WINDOW:
            flags, part = self.rel_queue.popleft()
            seq = self.rel_next
            self.rel_next += 1
            data = self.packet(KIND_DATA, CHUNK.pack(seq, flags) + part)
            self.rel_unacked[seq] = [data, t, 1]
            self.send(data)
        rto = self.rto()
        for item in self.rel_unacked.values():
            data, sent, attempts = item
            if t - sent > rto * min(2 ** (attempts - 1), 8):
                item[1], item[2] = t, attempts + 1
                self.send(data)
                self.stats['retransmits'] += 1

    def receive_chunk(self, body):
        if len(body) < CHUNK.size:
            self.stats['bad'] += 1
            return
        seq, flags = CHUNK.unpack_from(body)
        self.ack_due = True
        if seq < self.rel_expected or seq in self.rel_buffer:
            self.stats['duplicate_chunks'] += 1
            return
        if seq - self.rel_expected >= 4 * WINDOW:
            return
        self.rel_buffer[seq] = (flags, body[CHUNK.size:])
        while self.rel_expected in self.rel_buffer:
            flags, part = self.rel_buffer.pop(self.rel_expected)
            self.rel_expected += 1
            if flags & 1:
                self.rel_parts, self.rel_size = [], 0
            self.rel_parts.append(part)
            self.rel_size += len(part)
            if self.rel_size > MAX_MESSAGE:
                self.rel_parts, self.rel_size = [], 0
                self.stats['bad'] += 1
                continue
            if flags & 2:
                raw, self.rel_parts, self.rel_size = b''.join(self.rel_parts), [], 0
                if flags & 4:
                    inflater = zlib.decompressobj()
                    try:
                        raw = inflater.decompress(raw, MAX_MESSAGE)
                    except zlib.error:
                        self.stats['bad'] += 1
                        continue
                    if inflater.unconsumed_tail:
                        self.stats['bad'] += 1
                        continue
                message = parse_json(raw)
                if message is None:
                    self.stats['bad'] += 1
                    continue
                self.messages.append(message)
                self.stats['messages_received'] += 1

    def send_ack(self):
        cumulative = self.rel_expected - 1
        bits = 0
        for i in range(32):
            if cumulative + 2 + i in self.rel_buffer:
                bits |= 1 << i
        self.send(self.packet(KIND_ACK, ACK.pack(cumulative, bits)))
        self.ack_due = False

    def receive_ack(self, body):
        if len(body) < ACK.size:
            self.stats['bad'] += 1
            return
        cumulative, bits = ACK.unpack_from(body)
        for seq in [s for s in self.rel_unacked if s <= cumulative]:
            del self.rel_unacked[seq]
        for i in range(32):
            if bits >> i & 1:
                self.rel_unacked.pop(cumulative + 2 + i, None)

    def receive_message(self, kind=None):
        """取出下一条（指定类型的）可靠消息；没有时返回 None。"""
        for index, message in enumerate(self.messages):
            if kind is None or message.get('type') == kind:
                del self.messages[index]
                return message
        return None

    def reliable_idle(self):
        return not self.rel_unacked and not self.rel_queue

    # ---------- 定时 ----------
    def set_state(self, state, reason=None):
        if state == self.state:
            return
        t = now()
        if self.state == 'interrupted':
            self.interruptions.append((round(self.state_since - self.created, 3), round(t - self.state_since, 3)))
        self.state, self.state_since = state, t
        if state in ('disconnected', 'closed'):
            self.closed_reason = reason

    def service(self):
        """收包、重传、确认、心跳与断线判定。不取走对战事件（由 poll() 取走）。"""
        self.endpoint.poll()
        if self.state in ('disconnected', 'closed'):
            self.endpoint.flush()
            return
        t = now()
        quiet = t - self.last_receive
        if quiet >= self.disconnect_after:
            self.set_state('disconnected', 'timeout')
            self.bye()
            return
        self.set_state('interrupted' if quiet >= INTERRUPT_AFTER else 'connected')
        if self.ack_due:
            self.send_ack()
        self.pump_reliable(t)
        if t - self.last_ping >= PING_EVERY:
            self.ping()
        self.endpoint.flush()

    # ---------- 对战（与 netplay_transport.UdpTransport 相同的接口） ----------
    def begin_round(self, number):
        """新一轮对战：对战字段归零，之后收到的其他轮次输入与校验值一律丢弃。"""
        self.round = number & 0xffff
        self.peer_ack = self.ack = self.peer_frame = self.peer_advantage = 0
        self.battle_events = []

    def send_inputs(self, first, values, ack=None, frame=0, advantage=0):
        if ack is not None:
            self.ack = ack
        self.send(self.packet(KIND_INPUT, INPUT.pack(self.round, self.ack, frame, advantage, first, len(values))
                              + struct.pack('<%dI' % len(values), *[v & 0xffffffff for v in values])))

    def send_checksum(self, frame, value):
        self.send(self.packet(KIND_CHECKSUM, CHECKSUM.pack(self.round, frame, *value)))

    def send_checksum_tags(self, entries):
        """N5：最近若干已确认校验帧的 tag（与发送方一侧绑定，见 netplay_desync.tag）。"""
        entries = list(entries)[-16:]
        self.send(self.packet(KIND_TAGS, TAGS.pack(self.round, len(entries))
                              + b''.join(TAG_ENTRY.pack(f, v & 0xffffffffffffffff) for f, v in entries)))

    def ping(self):
        self.ping_id += 1
        self.last_ping = now()
        self.send(self.packet(KIND_PING, PING.pack(self.last_ping, self.ping_id)))

    def bye(self):
        """离开或判定断线时通知对方（直接发送三次，不经模拟延迟与丢包；模拟断网期间不发送）。"""
        if self.endpoint.in_blackout():
            return
        data = self.packet(KIND_BYE)
        for _ in range(3):
            self.endpoint.transmit(data, self.remote)

    def poll(self):
        """收包并取走对战事件 [('input', (首帧, [输入])), ('checksum_tag', (帧, tag)), ('checksum', (帧, (h, d)))]。"""
        self.service()
        events, self.battle_events = self.battle_events, []
        return events

    def flush(self):
        self.endpoint.flush()

    def leave(self, reason='leave'):
        if self.state not in ('disconnected', 'closed'):
            self.bye()
            self.set_state('closed', reason)

    def close(self):
        self.leave()
        self.endpoint.close()

    def status(self):
        return {'state': self.state, 'remote': list(self.remote), 'role': self.role, 'round': self.round,
                'rtt_ms': round(self.rtt * 1000, 1) if self.rtt is not None else None,
                'srtt_ms': round(self.srtt * 1000, 1) if self.srtt is not None else None,
                'quiet_seconds': round(now() - self.last_receive, 3), 'interruptions': list(self.interruptions),
                'closed_reason': self.closed_reason, 'stats': dict(self.stats), 'endpoint': dict(self.endpoint.stats)}


# ---------- 连接建立 ----------
class Listener:
    """房主：在端点上接受第一名加入方。远程会合时另向加入方的候选地址打洞（punch）。
    code（N6b）：房间码；设定时对手的连接请求须带相同的房间码（不区分大小写），否则以 wrong_code 拒绝。观战连接不在此检查。"""

    def __init__(self, endpoint, info=None, disconnect_after=DISCONNECT_AFTER, code=None):
        self.endpoint = endpoint
        self.code = str(code).strip().upper() if code else None
        self.info = dict(info or {}, protocol=PROTOCOL)
        self.disconnect_after = disconnect_after
        self.link = None
        self.punches = {}                      # 地址 → [打洞令牌, 截止时刻, 上次发送]
        self.rejected = []
        endpoint.handlers[MAGIC] = self.handle

    def handle(self, data, address):
        if len(data) < HEADER.size:
            return
        _, version, kind, token, _ = HEADER.unpack_from(data)
        if kind != KIND_CONNECT:
            other = self.endpoint.extra_links.get(token)
            if other is not None:
                other.handle(data, address)           # 对手加入之前已连接的观战者
            return
        request = parse_json(data[HEADER.size:]) or {}
        if request.get('role') == 'spectator' and version == PROTOCOL and request.get('protocol') == PROTOCOL:
            if self.endpoint.on_extra_connect is not None:
                self.endpoint.on_extra_connect(token, request, address)
            else:
                self.endpoint.send(packet(KIND_REJECT, token, 0, json_bytes({'reason': 'no_spectate', 'protocol': PROTOCOL})), address)
            return
        if version != PROTOCOL or request.get('protocol') != PROTOCOL:
            self.endpoint.send(packet(KIND_REJECT, token, 0, json_bytes({'reason': 'protocol', 'protocol': PROTOCOL})), address)
            self.rejected.append({'address': list(address), 'reason': 'protocol', 'protocol': request.get('protocol', version)})
            return
        if not token:
            return
        if self.code and str(request.get('code') or '').strip().upper() != self.code:
            self.endpoint.send(packet(KIND_REJECT, token, 0, json_bytes({'reason': 'wrong_code', 'protocol': PROTOCOL})), address)
            if len(self.rejected) < 50:
                self.rejected.append({'address': list(address), 'reason': 'wrong_code'})
            return
        link = PeerLink(self.endpoint, address, token, 'host', info=request, disconnect_after=self.disconnect_after)
        link.local_info = self.info
        self.link = link                       # PeerLink 构造时已接管端点的 MSDN 分派
        self.punches.clear()
        self.endpoint.send(packet(KIND_ACCEPT, token, 0, json_bytes(self.info)), address)

    def punch(self, candidates, token, seconds=12.0):
        """向加入方的候选地址发打洞包，使本方路由器为对方地址建立映射（直到连接建立或超时）。"""
        until = now() + seconds
        for address in candidates:
            if valid_endpoint(address):
                self.punches[tuple(address)] = [token, until, 0.0]

    def service(self):
        self.endpoint.poll()
        t = now()                                      # 对手加入后仍为观战者打洞（会合服务器通知的新加入者）
        for address, item in list(self.punches.items()):
            token, until, last = item
            if t > until:
                del self.punches[address]
            elif t - last >= PUNCH_EVERY:
                item[2] = t
                self.endpoint.send(packet(KIND_PUNCH, token, 0), address)
        self.endpoint.flush()
        return self.link


class Connector:
    """加入方：向候选地址重复发送 CONNECT，收到 ACCEPT 即建立连接。打洞时收到的 PUNCH 来源地址加入候选。"""

    def __init__(self, endpoint, candidates, info=None, timeout=10.0, punch_token=None, disconnect_after=DISCONNECT_AFTER):
        self.endpoint = endpoint
        self.token = new_token()
        self.candidates = [tuple(c) for c in dict.fromkeys(tuple(c) for c in candidates) if valid_endpoint(c)]
        self.info = dict(info or {}, protocol=PROTOCOL)
        self.punch_token = punch_token
        self.deadline = now() + timeout
        self.disconnect_after = disconnect_after
        self.last_send = 0.0
        self.state = 'connecting'              # connecting、connected、rejected、failed
        self.reason = None
        self.link = None
        self.learned = []                      # 打洞中由对方 PUNCH 得到的新候选
        endpoint.handlers[MAGIC] = self.handle

    def add_candidates(self, candidates):
        for c in candidates:
            if valid_endpoint(c) and tuple(c) not in self.candidates:
                self.candidates.append(tuple(c))

    def handle(self, data, address):
        if len(data) < HEADER.size or self.state != 'connecting':
            return
        _, version, kind, token, _ = HEADER.unpack_from(data)
        body = data[HEADER.size:]
        if kind == KIND_PUNCH and self.punch_token is not None and token == self.punch_token:
            if tuple(address) not in self.candidates:
                self.candidates.append(tuple(address))
                self.learned.append(list(address))
            return
        if token != self.token:
            return
        if kind == KIND_ACCEPT and version == PROTOCOL:
            info = parse_json(body) or {}
            self.link = PeerLink(self.endpoint, address, self.token, 'client', info=info, disconnect_after=self.disconnect_after)
            self.state = 'connected'
        elif kind == KIND_REJECT:
            answer = parse_json(body) or {}
            self.state = 'rejected'
            self.reason = answer.get('reason', 'rejected')
            self.peer_protocol = answer.get('protocol')

    def service(self):
        self.endpoint.poll()
        if self.state == 'connecting':
            t = now()
            if t > self.deadline:
                self.state, self.reason = 'failed', 'timeout'
            elif t - self.last_send >= CONNECT_EVERY:
                self.last_send = t
                request = json_bytes(dict(self.info, punch=None if self.punch_token is None else '%016x' % self.punch_token))
                for address in self.candidates:
                    self.endpoint.send(packet(KIND_CONNECT, self.token, 0, request), address)
        self.endpoint.flush()
        return self.link


# ---------- 局域网发现 ----------
def broadcast_targets(port=DISCOVERY_PORT):
    """有限广播与各网卡按 /24 推算的定向广播地址（Windows 的有限广播只从一块网卡发出）。"""
    targets = [('255.255.255.255', port)]
    for ip in local_ipv4():
        parts = ip.split('.')
        targets.append(('.'.join(parts[:3] + ['255']), port))
    return list(dict.fromkeys(targets))


class LanResponder:
    """房主：在发现端口应答局域网查询（QUERY → ROOM）。room() 返回当前房间信息（含对战端口与状态）。"""

    def __init__(self, room, bind=('0.0.0.0', DISCOVERY_PORT)):
        self.room = room
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(bind)
        self.sock.setblocking(False)
        disable_connreset(self.sock)
        self.answered = 0

    def service(self):
        for _ in range(64):
            try:
                data, address = self.sock.recvfrom(65535)
            except (BlockingIOError, InterruptedError):
                break
            except ConnectionResetError:
                continue
            except OSError:
                break
            if not data.startswith(LAN_MAGIC):
                continue
            query = parse_json(data[4:])
            if not query or query.get('op') != 'query':
                continue
            answer = dict(self.room(), op='room', nonce=query.get('nonce'), protocol=PROTOCOL)
            try:
                self.sock.sendto(LAN_MAGIC + json_bytes(answer), address)
                self.answered += 1
            except OSError:
                pass

    def close(self):
        self.sock.close()


class LanScanner:
    """加入方：周期性发送 QUERY 并收集房间。rooms：{(ip, 对战端口): 房间信息}。"""

    def __init__(self, targets=None, bind=('0.0.0.0', 0), every=0.25):
        self.targets = targets or broadcast_targets()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind(bind)
        self.sock.setblocking(False)
        disable_connreset(self.sock)
        self.nonce = os.urandom(8).hex()
        self.every = every
        self.last = 0.0
        self.rooms = {}

    def service(self):
        t = now()
        if t - self.last >= self.every:
            self.last = t
            query = LAN_MAGIC + json_bytes({'op': 'query', 'protocol': PROTOCOL, 'nonce': self.nonce})
            for target in self.targets:
                try:
                    self.sock.sendto(query, target)
                except OSError:
                    pass
        for _ in range(64):
            try:
                data, address = self.sock.recvfrom(65535)
            except (BlockingIOError, InterruptedError):
                break
            except ConnectionResetError:
                continue
            except OSError:
                break
            if not data.startswith(LAN_MAGIC):
                continue
            room = parse_json(data[4:])
            if not room or room.get('op') != 'room' or room.get('nonce') != self.nonce:
                continue
            port = room.get('port')
            if not isinstance(port, int) or not 0 < port < 65536:
                continue
            room['address'] = [address[0], port]
            room['seen'] = t
            self.rooms[(address[0], port)] = room

    def close(self):
        self.sock.close()


def lan_scan(seconds=1.0, targets=None):
    scanner = LanScanner(targets)
    try:
        deadline = now() + seconds
        while now() < deadline:
            scanner.service()
            time.sleep(0.01)
        return sorted(scanner.rooms.values(), key=lambda r: (r.get('name', ''), r['address']))
    finally:
        scanner.close()


# ---------- 远程会合 ----------
class Rendezvous:
    """会合服务客户端，与对战共用端点（服务器看到的来源地址即本方公网地址）。
    房主：register() → state 'registered'，code 为房间码；之后服务器转来加入方地址时调用 on_peer(候选, 打洞令牌)。
    加入方：join(code) → state 'joined'，host_candidates 与 punch 可用于 Connector；失败时 state 'failed'、reason。"""

    RETRY, TIMEOUT, KEEPALIVE = 1.0, 10.0, 15.0

    def __init__(self, endpoint, server, info=None):
        self.endpoint = endpoint
        self.server = tuple(server)
        self.info = dict(info or {})
        self.state = 'idle'
        self.reason = None
        self.code = self.secret = self.public = None
        self.host_candidates, self.host_info, self.punch = [], {}, None
        self.request = None                   # (消息, 首次发送时刻, 上次发送时刻)
        self.last_keepalive = 0.0
        self.on_peer = None
        self.peers = []
        endpoint.handlers[RDV_MAGIC] = self.handle

    def send(self, message):
        self.endpoint.send(RDV_MAGIC + bytes((RDV_VERSION,)) + json_bytes(message), self.server)

    def start(self, message, state):
        t = now()
        self.state, self.reason = state, None
        self.request = (message, t, t)
        self.send(message)

    def register(self):
        self.start({'op': 'register', 'private': [list(c) for c in self.endpoint.candidates()], 'info': self.info}, 'registering')

    def join(self, code):
        self.code = code.strip().upper()
        self.start({'op': 'join', 'code': self.code, 'private': [list(c) for c in self.endpoint.candidates()],
                    'info': self.info}, 'joining')

    def whoami(self):
        self.start({'op': 'whoami'}, 'asking')

    def unregister(self):
        if self.code and self.secret:
            self.send({'op': 'unregister', 'code': self.code, 'secret': self.secret})
        self.state = 'idle'

    def handle(self, data, address):
        if tuple(address) != self.server or len(data) < 5 or data[4] != RDV_VERSION:
            return
        message = parse_json(data[5:])
        if not message:
            return
        op = message.get('op')
        if op == 'registered' and self.state == 'registering':
            self.code, self.secret = message.get('code'), message.get('secret')
            self.public = message.get('public')
            self.state, self.request, self.last_keepalive = 'registered', None, now()
        elif op == 'joined' and self.state == 'joining':
            host = message.get('host') or {}
            candidates = [host.get('public')] + list(host.get('private') or [])
            self.host_candidates = [tuple(c) for c in candidates if valid_endpoint(c)]
            self.host_info = host.get('info') or {}
            self.public = message.get('public')
            self.punch = hex64(message.get('punch'))
            self.state = 'joined'
            # 加入方在打洞期间继续以相同请求通知服务器（房主收不到 peer 消息时由重复的 join 补发），见 service()
        elif op == 'peer' and self.state == 'registered':
            peer = message.get('peer') or {}
            candidates = [tuple(c) for c in [peer.get('public')] + list(peer.get('private') or []) if valid_endpoint(c)]
            punch = hex64(message.get('punch'))
            key = (tuple(candidates), punch)
            if key not in self.peers:
                self.peers.append(key)
                if self.on_peer is not None:
                    self.on_peer(candidates, punch, peer.get('info') or {})
        elif op == 'you' and self.state == 'asking':
            self.public, self.state, self.request = message.get('public'), 'answered', None
        elif op == 'error' and self.state in ('registering', 'joining', 'asking'):
            self.state, self.reason, self.request = 'failed', message.get('reason', 'error'), None

    def service(self, keep_joining=False):
        """重发未应答的请求；房主每 15 秒保活；加入方打洞期间（keep_joining）每秒重复 join。"""
        t = now()
        if self.request is not None:
            message, first, last = self.request
            if t - first > self.TIMEOUT:
                self.state, self.reason, self.request = 'failed', 'server_timeout', None
            elif t - last >= self.RETRY:
                self.request = (message, first, t)
                self.send(message)
        if self.state == 'registered' and t - self.last_keepalive >= self.KEEPALIVE:
            self.last_keepalive = t
            self.send({'op': 'keepalive', 'code': self.code, 'secret': self.secret})
        if self.state == 'joined' and keep_joining and t - self.last_keepalive >= self.RETRY:
            self.last_keepalive = t
            self.send({'op': 'join', 'code': self.code, 'private': [list(c) for c in self.endpoint.candidates()],
                       'info': self.info})


def connect_failure_text(reason, language='zh'):
    """无法连接时的说明（不提供中继，R3）。"""
    texts = {
        'timeout': ('无法连接：对方没有回应。请确认对方已建立房间、地址与端口正确，并允许本游戏通过 Windows 防火墙。',
                    'Could not connect: no answer. Check that the host is waiting, the address and port are correct, '
                    'and the game is allowed through Windows Firewall.'),
        'punch_failed': ('无法连接：双方网络无法直接互通（打洞失败，可能双方都处于对称型 NAT 或运营商级 NAT 之后）。'
                         '可尝试：由一方在路由器上为本游戏开放端口后使用“直接连接”，或换用其他网络。本游戏不提供中继服务器。',
                         'Could not connect: the two networks cannot reach each other directly (hole punching failed; '
                         'both sides may be behind symmetric or carrier-grade NAT). Try forwarding the game port on one '
                         'router and use Direct connect, or another network. No relay server is provided.'),
        'busy': ('无法连接：该房间已有对手。', 'Could not connect: the room already has an opponent.'),
        'wrong_code': ('无法连接：房间码不正确。', 'Could not connect: wrong room code.'),
        'resolve': ('无法连接：无法解析该地址。', 'Could not connect: the address could not be resolved.'),
        'protocol': ('无法连接：对方的游戏版本使用不同的联机协议。', 'Could not connect: the peer uses a different netplay protocol.'),
        'no_room': ('无法连接：房间码不存在或已过期。', 'Could not connect: the room code does not exist or has expired.'),
        'server_timeout': ('无法连接：会合服务器没有回应。请确认服务器地址与端口。',
                           'Could not connect: the rendezvous server did not answer. Check its address and port.'),
        'rate_limited': ('无法连接：请求过于频繁，请稍后再试。', 'Could not connect: too many requests, try again later.'),
        'server_full': ('无法连接：会合服务器房间已满。', 'Could not connect: the rendezvous server is full.'),
        'spectators_full': ('无法观战：该房间的观战席位已满（最多 4 人）。', 'Cannot spectate: the room has no free spectator seats (4 at most).'),
        'no_spectate': ('无法观战：该房间不接受观战。', 'Cannot spectate: the room does not accept spectators.'),
    }
    zh, en = texts.get(reason, ('无法连接：' + str(reason), 'Could not connect: ' + str(reason)))
    return zh if language == 'zh' else en


# ---------- 测试：模拟路由器（NAT） ----------
class SimNat:
    """以本机回环套接字模拟一台 NAT 路由器之后的 UDP 套接字（只用于测试打洞流程）：
    - full_cone：所有目的地址共用一个外部端口，任何来源都可送达；
    - port_restricted：共用一个外部端口，只接收本方发过包的 (地址, 端口)；
    - symmetric：每个目的地址各用一个外部端口，且只接收该目的地址的回包。
    内网地址（10.x，getsockname 返回）不可从外部到达，发往 10.x 的包丢弃。"""

    def __init__(self, kind, inside_ip='10.77.1.2'):
        assert kind in ('full_cone', 'port_restricted', 'symmetric')
        self.kind = kind
        self.mappings = {}                 # 目的地址或 None → 外部套接字
        self.permits = {}                  # 外部套接字 → 已发往的地址
        self.inside = (inside_ip, 40000 + random.randrange(20000))
        self.filtered = 0

    def mapping(self, destination):
        key = destination if self.kind == 'symmetric' else None
        sock = self.mappings.get(key)
        if sock is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('127.0.0.1', 0))
            sock.setblocking(False)
            disable_connreset(sock)
            self.mappings[key] = sock
            self.permits[sock] = set()
        return sock

    def external(self):
        return [s.getsockname() for s in self.mappings.values()]

    def candidates(self):
        return [self.inside]

    def sendto(self, data, destination):
        destination = tuple(destination)
        if destination[0].startswith('10.'):
            return len(data)
        sock = self.mapping(destination)
        self.permits[sock].add(destination)
        return sock.sendto(data, destination)

    def recvfrom(self, size):
        for sock in list(self.mappings.values()):
            while True:
                try:
                    data, source = sock.recvfrom(size)
                except (BlockingIOError, InterruptedError):
                    break
                except ConnectionResetError:
                    continue
                if self.kind == 'full_cone' or source[:2] in self.permits[sock]:
                    return data, source
                self.filtered += 1
        raise BlockingIOError

    def getsockname(self):
        return self.inside

    def setblocking(self, flag):
        pass

    def fileno(self):
        return -1

    def close(self):
        for sock in self.mappings.values():
            sock.close()


def b64(raw):
    return base64.b64encode(raw).decode('ascii')


def unb64(text):
    return base64.b64decode(text.encode('ascii'))


def blake(raw, size=32):
    return hashlib.blake2b(raw, digest_size=size).digest()
