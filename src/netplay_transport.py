"""联机传输（N3/N4 原型，docs/netcode/N1_N2_ROLLBACK_2026-10-10.md 第 5 节）。

- 握手（Lobby，TCP，可靠）：交换内容清单（content_manifest，M7），任一差异即拒绝匹配并返回差异说明；主机下发本场设定
  （比赛种子、地图、双方编队、输入延迟）；双方到达联机第 0 帧后交换该帧校验值与原生战斗帧号，不一致时不开始。
- 对战（UdpTransport，UDP）：每包带本方自对方确认帧之后的全部输入（冗余重发，丢包后由后续包补齐）与本方已连续收到的
  对方输入帧（确认）；另有周期状态校验值。可模拟单向延迟、抖动与丢包（测试用）。
目前用于本机回环（127.0.0.1）原型测试；局域网发现、远程会合与打洞属于 N4 后续工作。
"""
import base64
import json
import random
import socket
import struct
import time

MAGIC = b'MSDN'
VERSION = 1
HEADER = struct.Struct('<4sBBII')          # 魔数、版本、类型、会话号、序号
INPUT = struct.Struct('<iiiiH')            # 确认帧、发送方当前帧、发送方帧优势、首帧、个数（随后为逐帧输入字节）
CHECKSUM = struct.Struct('<iII')
PING = struct.Struct('<d')
KIND_INPUT, KIND_CHECKSUM, KIND_PING, KIND_PONG, KIND_BYE = 1, 2, 3, 4, 5


class UdpTransport:
    def __init__(self, local, remote, session, latency_ms=0.0, jitter_ms=0.0, loss=0.0, seed=0):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(local)
        self.sock.setblocking(False)
        self.remote = remote
        self.session = session & 0xffffffff
        self.latency = latency_ms / 1000.0
        self.jitter = jitter_ms / 1000.0
        self.loss = loss
        self.rng = random.Random(seed)
        self.seq = 0
        self.peer_ack = 0                  # 对方已连续收到的本方输入的最后一帧
        self.ack = 0                       # 本方已连续收到的对方输入的最后一帧（随输入包发送）
        self.peer_frame = 0                # 对方最近报告的当前帧与帧优势（时间同步）
        self.peer_advantage = 0
        self.outgoing = []                 # [(发送时刻, 数据)]：模拟延迟
        self.rtt = None
        self.closed_by_peer = False
        self.stats = {'sent': 0, 'dropped': 0, 'received': 0, 'bytes_sent': 0, 'bad': 0}

    def packet(self, kind, payload):
        self.seq += 1
        return HEADER.pack(MAGIC, VERSION, kind, self.session, self.seq) + payload

    def queue(self, data):
        if self.loss and self.rng.random() < self.loss:
            self.stats['dropped'] += 1
            return
        delay = self.latency + (self.rng.random() * self.jitter if self.jitter else 0.0)
        self.outgoing.append((time.perf_counter() + delay, data))

    def flush(self):
        now = time.perf_counter()
        due = [item for item in self.outgoing if item[0] <= now]
        if not due:
            return
        self.outgoing = [item for item in self.outgoing if item[0] > now]
        for _, data in sorted(due, key=lambda item: item[0]):
            try:
                self.sock.sendto(data, self.remote)
                self.stats['sent'] += 1
                self.stats['bytes_sent'] += len(data)
            except OSError:
                self.stats['dropped'] += 1

    def send_inputs(self, first, values, ack=None, frame=0, advantage=0):
        if ack is not None:
            self.ack = ack
        self.queue(self.packet(KIND_INPUT, INPUT.pack(self.ack, frame, advantage, first, len(values)) + bytes(values)))

    def send_checksum(self, frame, value):
        self.queue(self.packet(KIND_CHECKSUM, CHECKSUM.pack(frame, *value)))

    def ping(self):
        self.queue(self.packet(KIND_PING, PING.pack(time.perf_counter())))

    def bye(self):
        for _ in range(3):
            self.sock.sendto(self.packet(KIND_BYE, b''), self.remote)

    def poll(self):
        """收取全部到达的数据包，返回 [('input', (首帧, [输入])), ('checksum', (帧, (h, d)))]。"""
        self.flush()
        events = []
        while True:
            try:
                data, _ = self.sock.recvfrom(4096)
            except (BlockingIOError, ConnectionResetError, OSError):
                break
            if len(data) < HEADER.size:
                self.stats['bad'] += 1
                continue
            magic, version, kind, session, _ = HEADER.unpack_from(data)
            if magic != MAGIC or version != VERSION or session != self.session:
                self.stats['bad'] += 1
                continue
            self.stats['received'] += 1
            body = data[HEADER.size:]
            if kind == KIND_INPUT:
                ack, frame, advantage, first, count = INPUT.unpack_from(body)
                self.peer_ack = max(self.peer_ack, ack)
                if frame >= self.peer_frame:
                    self.peer_frame, self.peer_advantage = frame, advantage
                events.append(('input', (first, list(body[INPUT.size:INPUT.size + count]))))
            elif kind == KIND_CHECKSUM:
                frame, h, d = CHECKSUM.unpack_from(body)
                events.append(('checksum', (frame, (h, d))))
            elif kind == KIND_PING:
                self.queue(self.packet(KIND_PONG, body[:PING.size]))
            elif kind == KIND_PONG:
                self.rtt = time.perf_counter() - PING.unpack_from(body)[0]
            elif kind == KIND_BYE:
                self.closed_by_peer = True
        return events

    def close(self):
        self.sock.close()


class Lobby:
    """TCP 握手：一行一个 JSON 消息。主机 listen，客户端 connect。"""

    def __init__(self, sock):
        self.sock = sock
        self.buffer = b''

    @classmethod
    def host(cls, address, timeout=60.0):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(address)
        server.listen(1)
        server.settimeout(timeout)
        try:
            conn, _ = server.accept()
        finally:
            server.close()
        conn.settimeout(timeout)
        return cls(conn)

    @classmethod
    def connect(cls, address, timeout=60.0):
        deadline = time.monotonic() + timeout
        while True:
            try:
                conn = socket.create_connection(address, timeout=5.0)
                conn.settimeout(timeout)
                return cls(conn)
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.2)

    def send(self, message):
        self.sock.sendall(json.dumps(message, ensure_ascii=False).encode('utf-8') + b'\n')

    def receive(self):
        while b'\n' not in self.buffer:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError('对方已断开')
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b'\n', 1)
        return json.loads(line.decode('utf-8'))

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def pack_manifest(manifest):
    import content_manifest
    return base64.b64encode(content_manifest.encode(manifest)).decode('ascii')


def unpack_manifest(text):
    import content_manifest
    return content_manifest.decode(base64.b64decode(text))


def host_handshake(lobby, manifest, match):
    """主机：收客户端清单并比较，回复是否接受（附本方清单与本场设定）。返回 (接受, 差异)。"""
    import content_manifest
    hello = lobby.receive()
    if hello.get('type') != 'hello':
        raise ConnectionError('意外的握手消息')
    remote = unpack_manifest(hello['manifest'])
    differences = content_manifest.diff(manifest, remote)
    accepted = not differences
    lobby.send({'type': 'welcome', 'accepted': accepted, 'differences': differences,
                'manifest': pack_manifest(manifest), 'match': match if accepted else None})
    return accepted, differences


def client_handshake(lobby, manifest):
    """客户端：发送清单，收主机答复；本方也比较主机清单。返回 (接受, 差异, 本场设定)。"""
    import content_manifest
    lobby.send({'type': 'hello', 'manifest': pack_manifest(manifest)})
    welcome = lobby.receive()
    if welcome.get('type') != 'welcome':
        raise ConnectionError('意外的握手消息')
    differences = content_manifest.diff(manifest, unpack_manifest(welcome['manifest']))
    return bool(welcome['accepted']) and not differences, differences or welcome['differences'], welcome.get('match')


def exchange_ready(lobby, checksum, battle_frame):
    """双方到达联机第 0 帧：交换校验值与原生战斗帧号；一致返回 True。"""
    lobby.send({'type': 'ready', 'checksum': list(checksum), 'battle_frame': battle_frame})
    ready = lobby.receive()
    return ready.get('type') == 'ready' and ready['checksum'] == list(checksum) and ready['battle_frame'] == battle_frame, ready
