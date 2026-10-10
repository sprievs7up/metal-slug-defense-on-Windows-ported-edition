#!/usr/bin/env python3
"""MSD WINDOWS S1XLV 联机会合服务（社区自建，docs/netcode/RENDEZVOUS_SERVER.md）。

只帮助两名玩家交换地址以便 UDP 打洞直连；不转发任何对战数据，不保存任何玩家数据（房间只存在于内存中）。
只依赖 Python 3.8 及以上的标准库，可在任何系统上独立运行：

    python3 rendezvous_server.py --host 0.0.0.0 --port 47632

协议（UDP，每包为魔数 b'MSDR' + 版本字节 1 + UTF-8 JSON，单包不超过 1400 字节）：
- register {private, info}          → registered {code, secret, public, ttl}  房主登记，code 为 6 位房间码
- keepalive {code, secret}          → （无应答）房主每 15 秒一次；超过 ttl 秒未保活的房间删除
- unregister {code, secret}         → （无应答）
- join {code, private, info}        → joined {host:{public, private, info}, public, punch}；同时向房主发送
                                       peer {peer:{public, private, info}, punch}（加入方打洞期间每秒重复 join，房主收到重复的 peer）
- whoami {}                         → you {public}
- 出错时                             → error {reason}：no_room、rate_limited、server_full（格式不符的包直接忽略）
public 为服务器看到的来源地址（玩家路由器的公网地址与端口）；private 为玩家自报的内网地址（同一局域网内可直接互通）。
"""
import argparse
import ipaddress
import json
import logging
import secrets
import socket
import time
from collections import defaultdict, deque

MAGIC, VERSION = b'MSDR', 1
ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'      # 不含易混淆的 I、O、0、1
CODE_LENGTH = 6
MAX_PACKET = 1400
MAX_PRIVATE = 8
MAX_INFO = 512                                       # info 字段 JSON 长度上限


def clean_endpoints(values):
    result = []
    if not isinstance(values, list):
        return result
    for value in values[:MAX_PRIVATE]:
        try:
            ip, port = value
            ipaddress.IPv4Address(ip)
            if isinstance(port, int) and 0 < port < 65536:
                result.append([str(ip), port])
        except (TypeError, ValueError):
            continue
    return result


def clean_info(value):
    if not isinstance(value, dict):
        return {}
    text = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    return value if len(text) <= MAX_INFO else {}


class RateLimit:
    """每个来源 IP 在 window 秒内最多 limit 次。"""

    def __init__(self, limit, window=60.0):
        self.limit, self.window = limit, window
        self.events = defaultdict(deque)

    def allow(self, ip, now):
        events = self.events[ip]
        while events and now - events[0] > self.window:
            events.popleft()
        if len(events) >= self.limit:
            return False
        events.append(now)
        return True

    def prune(self, now):
        for ip in [ip for ip, events in self.events.items() if not events or now - events[-1] > self.window]:
            del self.events[ip]


class RendezvousServer:
    def __init__(self, sock, ttl=60.0, max_rooms=5000, register_limit=20, join_limit=120, other_limit=240):
        self.sock = sock
        self.ttl = ttl
        self.max_rooms = max_rooms
        self.rooms = {}                    # 房间码 → {public, private, info, secret, created, seen, joins}
        self.limits = {'register': RateLimit(register_limit), 'join': RateLimit(join_limit), 'other': RateLimit(other_limit)}
        self.stats = defaultdict(int)
        self.last_prune = 0.0

    def send(self, message, address):
        try:
            self.sock.sendto(MAGIC + bytes((VERSION,)) + json.dumps(message, ensure_ascii=False, separators=(',', ':')).encode('utf-8'), address)
            self.stats['sent'] += 1
        except OSError:
            self.stats['send_errors'] += 1

    def new_code(self):
        while True:
            code = ''.join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
            if code not in self.rooms:
                return code

    def handle(self, data, address, now):
        self.stats['received'] += 1
        if len(data) > MAX_PACKET or len(data) < 5 or data[:4] != MAGIC or data[4] != VERSION:
            self.stats['ignored'] += 1
            return
        try:
            message = json.loads(data[5:].decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            self.stats['ignored'] += 1
            return
        if not isinstance(message, dict):
            self.stats['ignored'] += 1
            return
        op = message.get('op')
        ip = address[0]
        public = [address[0], address[1]]
        limit = self.limits['register' if op == 'register' else 'join' if op == 'join' else 'other']
        if not limit.allow(ip, now):
            self.stats['rate_limited'] += 1
            if op in ('register', 'join', 'whoami'):
                self.send({'op': 'error', 'reason': 'rate_limited'}, address)
            return
        if op == 'register':
            if len(self.rooms) >= self.max_rooms:
                self.send({'op': 'error', 'reason': 'server_full'}, address)
                return
            # 同一来源地址重复 register（应答丢失）时返回原房间
            for code, room in self.rooms.items():
                if room['public'] == public and now - room['created'] < 30:
                    self.send({'op': 'registered', 'code': code, 'secret': room['secret'], 'public': public, 'ttl': self.ttl}, address)
                    return
            code = self.new_code()
            room = {'public': public, 'private': clean_endpoints(message.get('private')), 'info': clean_info(message.get('info')),
                    'secret': secrets.token_hex(8), 'created': now, 'seen': now, 'joins': 0}
            self.rooms[code] = room
            self.stats['registered'] += 1
            logging.info('register %s from %s:%d', code, *address)
            self.send({'op': 'registered', 'code': code, 'secret': room['secret'], 'public': public, 'ttl': self.ttl}, address)
        elif op in ('keepalive', 'unregister'):
            room = self.rooms.get(str(message.get('code', '')).upper())
            if room is None or not secrets.compare_digest(str(message.get('secret', '')), room['secret']):
                return
            if op == 'unregister':
                del self.rooms[str(message['code']).upper()]
                self.stats['unregistered'] += 1
            else:
                room['seen'] = now
                room['public'] = public         # 房主路由器的映射可能改变
        elif op == 'join':
            code = str(message.get('code', '')).strip().upper()
            room = self.rooms.get(code)
            if room is None:
                self.stats['join_missing'] += 1
                self.send({'op': 'error', 'reason': 'no_room'}, address)
                return
            peer = {'public': public, 'private': clean_endpoints(message.get('private')), 'info': clean_info(message.get('info'))}
            key = tuple(public)
            punch = room.setdefault('punches', {}).get(key)
            if punch is None:
                punch = secrets.token_hex(8)
                room['punches'][key] = punch
                room['joins'] += 1
                self.stats['joined'] += 1
                logging.info('join %s from %s:%d', code, *address)
            self.send({'op': 'joined', 'host': {'public': room['public'], 'private': room['private'], 'info': room['info']},
                       'public': public, 'punch': punch}, address)
            self.send({'op': 'peer', 'peer': peer, 'punch': punch}, tuple(room['public']))
        elif op == 'whoami':
            self.send({'op': 'you', 'public': public}, address)
        else:
            self.stats['ignored'] += 1

    def prune(self, now):
        if now - self.last_prune < 1.0:
            return
        self.last_prune = now
        for code in [c for c, r in self.rooms.items() if now - r['seen'] > self.ttl]:
            del self.rooms[code]
            self.stats['expired'] += 1
        for limit in self.limits.values():
            limit.prune(now)

    def service(self, now=None):
        """收取并处理全部到达的包（非阻塞套接字）。"""
        now = time.monotonic() if now is None else now
        for _ in range(4096):
            try:
                data, address = self.sock.recvfrom(65535)
            except (BlockingIOError, InterruptedError):
                break
            except ConnectionResetError:
                continue
            except OSError:
                break
            self.handle(data, address[:2], now)
        self.prune(now)


def disable_connreset(sock):
    try:
        import ctypes
        import os
        if os.name != 'nt':
            return
        from ctypes import wintypes
        ws2 = ctypes.WinDLL('ws2_32')
        ws2.WSAIoctl.argtypes = [ctypes.c_size_t, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p,
                                 wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p, ctypes.c_void_p]
        value, returned = wintypes.DWORD(0), wintypes.DWORD(0)
        ws2.WSAIoctl(sock.fileno(), 0x9800000C, ctypes.byref(value), 4, None, 0, ctypes.byref(returned), None, None)
    except Exception:
        pass


def open_socket(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    disable_connreset(sock)
    return sock


def main():
    parser = argparse.ArgumentParser(description='MSD WINDOWS S1XLV rendezvous (hole punching) server; relays no game data.')
    parser.add_argument('--host', default='0.0.0.0', help='listen address (default 0.0.0.0)')
    parser.add_argument('--port', type=int, default=47632, help='UDP port (default 47632)')
    parser.add_argument('--ttl', type=float, default=60.0, help='seconds before an idle room expires (default 60)')
    parser.add_argument('--max-rooms', type=int, default=5000)
    parser.add_argument('--stats-every', type=float, default=300.0, help='log statistics every N seconds (0 = never)')
    parser.add_argument('--log', default=None, help='log file (default: stderr)')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', filename=args.log)
    sock = open_socket(args.host, args.port)
    sock.settimeout(1.0)
    server = RendezvousServer(sock, ttl=args.ttl, max_rooms=args.max_rooms)
    logging.info('MSD rendezvous server listening on %s:%d (UDP)', args.host, args.port)
    last_stats = time.monotonic()
    try:
        while True:
            try:
                data, address = sock.recvfrom(65535)
                server.handle(data, address[:2], time.monotonic())
            except (socket.timeout, ConnectionResetError):
                pass
            except OSError as error:                   # 其他接收错误（如超大包）只记录，服务继续
                logging.warning('receive error: %s', error)
            now = time.monotonic()
            server.prune(now)
            if args.stats_every and now - last_stats >= args.stats_every:
                last_stats = now
                logging.info('rooms=%d stats=%s', len(server.rooms), dict(server.stats))
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()


if __name__ == '__main__':
    main()
