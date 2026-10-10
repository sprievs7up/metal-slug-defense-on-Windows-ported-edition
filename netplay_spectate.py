"""观战（N5.5b，docs/netcode/N5_5_REPLAY_SPECTATE_2026-10-10.md）。

房主向观战者转发已确认的双方输入（R6：每个房间最多 MAX_SPECTATORS 名，画面延迟约 TARGET_LAG 帧，只用于缓冲网络抖动）。
观战者与双方玩家使用同一个对战端口：连接请求带 role='spectator'，房主的端点按连接令牌把包分派给各观战连接（netplay_net）。
局域网发现、直接连接与会合服务器（房间码）三种方式均可加入；会合服务器只交换地址，不转发数据（R3）。

可靠消息（PeerLink.send_message）：
- 观战者 → 房主：spectate_hello {protocol, digest, name, version}
- 房主 → 观战者：spectate_reject {reason, manifest?}（内容不同时附房主清单，观战者在本机列出差异）；
  spectate_welcome {names, state}；spectate_round {round, match, setup, names, frame0, first, inputs, checksums}（开战时；中途加入时附已确认的全部输入）；
  spectate_inputs {round, first, inputs, checksums}（新确认的帧，约每 10 帧一批）；spectate_end {round, frames, result}；spectate_close {reason}
观战者按与回放相同的方式重算（SpectateBattle），并以房主的周期校验值核对；中途加入时先快速追赶（不显示）到缓冲位置。
"""
import time

import content_manifest
import netplay_net as nn
import netplay_replay as nr

MAX_SPECTATORS = 4
TARGET_LAG = 60                      # 帧（约 2 秒）
BATCH_FRAMES = 10
BATCH_SECONDS = 0.3


def pack_pairs(pairs):
    return nr.encode_inputs(pairs)


# ---------- 房主 ----------
class SpectatorHub:
    """房主侧：接受观战连接、比较内容摘要、在开战时下发本轮设定，并转发新确认的输入与周期校验值。"""

    def __init__(self, endpoint, manifest, name='', version='', limit=MAX_SPECTATORS, disconnect_after=nn.DISCONNECT_AFTER):
        self.endpoint = endpoint
        self.manifest = manifest
        self.digest = content_manifest.digest(manifest)
        self.name, self.version = name, version
        self.limit = limit
        self.disconnect_after = disconnect_after
        self.links = {}                  # 令牌 → PeerLink
        self.state = {}                  # 令牌 → 'hello' | 'watching' | 'rejected'
        self.names = {}
        self.round = None                # 当前轮的设定消息（中途加入时补发）
        self.session = None
        self.sent = {}                   # 令牌 → 已发送的最后一帧
        self.last_batch = 0.0
        self.ended = False
        self.stats = {'accepted': 0, 'rejected_full': 0, 'rejected_content': 0, 'left': 0, 'messages': 0}
        endpoint.on_extra_connect = self.accept

    # 端点回调：未知令牌的 role='spectator' 连接请求
    def accept(self, token, request, address):
        if token in self.links:
            link = self.links[token]
            if link.state in ('connected', 'interrupted'):
                self.endpoint.send(nn.packet(nn.KIND_ACCEPT, token, 0, nn.json_bytes(link.local_info)), address)
            return
        if len([t for t, s in self.state.items() if s != 'rejected']) >= self.limit:
            self.endpoint.send(nn.packet(nn.KIND_REJECT, token, 0, nn.json_bytes({'reason': 'spectators_full'})), address)
            self.stats['rejected_full'] += 1
            return
        link = nn.PeerLink(self.endpoint, address, token, 'host', info=request, disconnect_after=self.disconnect_after,
                           register=False)
        link.local_info = {'name': self.name, 'version': self.version, 'protocol': nn.PROTOCOL, 'spectate': True}
        self.endpoint.extra_links[token] = link
        self.links[token] = link
        self.state[token] = 'hello'
        self.names[token] = str(request.get('name', ''))[:40]
        self.stats['accepted'] += 1
        self.endpoint.send(nn.packet(nn.KIND_ACCEPT, token, 0, nn.json_bytes(link.local_info)), address)

    def watchers(self):
        return [t for t, s in self.state.items() if s == 'watching' and self.links[t].state in ('connected', 'interrupted')]

    def service(self):
        for token, link in list(self.links.items()):
            link.service()
            while True:
                message = link.receive_message()
                if message is None:
                    break
                self.on_message(token, link, message)
            if link.state in ('disconnected', 'closed'):
                self.endpoint.extra_links.pop(token, None)
                del self.links[token]
                self.stats['left'] += 1 if self.state.pop(token, None) == 'watching' else 0
                self.sent.pop(token, None)
        if self.session is not None:
            self.feed()

    def on_message(self, token, link, message):
        if message.get('type') != 'spectate_hello' or self.state.get(token) != 'hello':
            return
        if message.get('protocol') != nn.PROTOCOL:
            self.reject(token, link, 'protocol')
        elif message.get('digest') != self.digest:
            self.reject(token, link, 'content', manifest=nn.b64(content_manifest.encode(self.manifest)))
        else:
            self.state[token] = 'watching'
            link.send_message({'type': 'spectate_welcome', 'name': self.name, 'version': self.version,
                               'state': 'battle' if self.round else 'waiting'})
            if self.round is not None:
                self.send_round(token, link)

    def reject(self, token, link, reason, **extra):
        self.state[token] = 'rejected'
        self.stats['rejected_content'] += 1 if reason == 'content' else 0
        link.send_message(dict(extra, type='spectate_reject', reason=reason))

    def send_round(self, token, link):
        """本轮设定与迄今已确认的全部输入（中途加入）。"""
        session = self.session
        frames = len(session.input_log) if session is not None else 0
        message = dict(self.round, type='spectate_round', first=1, inputs=pack_pairs(session.input_log[:frames]) if frames else '',
                       checksums={str(f): list(v) for f, v in session.checksum_log.items() if f <= frames} if session else {})
        link.send_message(message)
        self.sent[token] = frames
        self.stats['messages'] += 1

    def begin_round(self, session, number, match, names, setup=None):
        """开战（第 0 帧之后）：记录本轮设定并下发给全部观战者。match：seed、stage、p1_deck、p2_deck、delay。"""
        self.session = session
        self.ended = False
        self.round = {'round': number, 'names': list(names), 'setup': dict(setup or {}),
                      'match': {'round': number, 'seed': match['seed'], 'stage': match['stage'], 'p1_deck': match['p1_deck'],
                                'p2_deck': match['p2_deck'], 'p1_status': match.get('p1_status'),
                                'p2_status': match.get('p2_status'), 'delay': match.get('delay', 2), 'interval': session.interval},
                      'frame0': {'checksum': list(session.checksum_log.get(0, ())), 'units': session.deck_digests}}
        for token in self.watchers():
            self.send_round(token, self.links[token])

    def feed(self, force=False):
        """新确认的帧：约每 BATCH_FRAMES 帧或 BATCH_SECONDS 秒一批。"""
        session = self.session
        frames = len(session.input_log)
        if not force and time.perf_counter() - self.last_batch < BATCH_SECONDS:
            pending = [t for t in self.watchers() if frames - self.sent.get(t, 0) >= BATCH_FRAMES]
            if not pending:
                return
        self.last_batch = time.perf_counter()
        for token in self.watchers():
            first = self.sent.get(token, 0)
            if frames <= first:
                continue
            pairs = session.input_log[first:frames]
            checksums = {str(f): list(v) for f, v in session.checksum_log.items() if first < f <= frames}
            self.links[token].send_message({'type': 'spectate_inputs', 'round': self.round['round'], 'first': first + 1,
                                            'inputs': pack_pairs(pairs), 'checksums': checksums})
            self.sent[token] = frames
            self.stats['messages'] += 1

    def end_round(self, result):
        if self.session is None:
            return
        self.feed(force=True)
        frames = len(self.session.input_log)
        for token in self.watchers():
            self.links[token].send_message({'type': 'spectate_end', 'round': self.round['round'], 'frames': frames,
                                            'result': result})
        self.session = None
        self.round = None
        self.ended = True

    def close(self, reason='room_closed'):
        for token, link in list(self.links.items()):
            if link.state in ('connected', 'interrupted'):
                link.send_message({'type': 'spectate_close', 'reason': reason})
        deadline = time.perf_counter() + 1.0
        while time.perf_counter() < deadline and any(not l.reliable_idle() for l in self.links.values()
                                                     if l.state in ('connected', 'interrupted')):
            for link in self.links.values():
                link.service()
            time.sleep(0.005)
        for link in self.links.values():
            link.leave(reason)
        self.endpoint.on_extra_connect = None

    def status(self):
        return {'spectators': {self.names.get(t, ''): self.state.get(t) for t in self.links}, 'stats': dict(self.stats),
                'links': [link.status() for link in self.links.values()]}


# ---------- 观战者 ----------
class SpectatorClient:
    """观战者侧：发送 hello，接收本轮设定与输入。rounds 为按轮次保存的 {设定, 输入, 校验值, 结束}。"""

    def __init__(self, link, manifest, name='', version=''):
        self.link = link
        self.manifest = manifest
        self.state = 'hello'             # hello、watching、rejected、closed、disconnected
        self.reason = None
        self.differences = None
        self.host = None
        self.rounds = {}                 # 轮次 → {'info', 'inputs', 'checksums', 'end'}
        self.current = None
        link.send_message({'type': 'spectate_hello', 'protocol': nn.PROTOCOL, 'digest': content_manifest.digest(manifest),
                           'name': name, 'version': version})

    def poll(self):
        link = self.link
        link.service()
        while True:
            message = link.receive_message()
            if message is None:
                break
            self.on_message(message)
        if self.state not in ('rejected', 'closed') and link.state == 'disconnected':
            self.state, self.reason = 'disconnected', link.closed_reason or 'timeout'
        elif self.state not in ('rejected', 'closed', 'disconnected') and link.state == 'closed':
            self.state, self.reason = 'closed', link.closed_reason or 'host_left'
        return self.state

    def on_message(self, message):
        kind = message.get('type')
        if kind == 'spectate_reject':
            self.state, self.reason = 'rejected', message.get('reason')
            if message.get('manifest'):
                remote = content_manifest.decode(nn.unb64(message['manifest']))
                self.differences = content_manifest.diff(self.manifest, remote)
        elif kind == 'spectate_welcome':
            self.state, self.host = 'watching', message
        elif kind == 'spectate_round':
            number = message['round']
            pairs = nr.decode_inputs(message['inputs']) if message.get('inputs') else []
            self.rounds[number] = {'info': message, 'inputs': pairs, 'checksums': dict(message.get('checksums') or {}),
                                   'end': None, 'received_at': time.perf_counter()}
            self.current = number
        elif kind == 'spectate_inputs':
            entry = self.rounds.get(message.get('round'))
            if entry is not None and int(message['first']) == len(entry['inputs']) + 1:
                entry['inputs'].extend(nr.decode_inputs(message['inputs']))
                entry['checksums'].update(message.get('checksums') or {})
        elif kind == 'spectate_end':
            entry = self.rounds.get(message.get('round'))
            if entry is not None:
                entry['end'] = message
        elif kind == 'spectate_close':
            self.state, self.reason = 'closed', message.get('reason')

    def leave(self):
        self.link.leave('spectator_left')


class SpectateBattle(nr.ReplayBattle):
    """观战会话：输入随房主转发逐步增加；保持约 TARGET_LAG 帧的缓冲，落后过多时加速追赶（不显示中间帧）。"""

    def __init__(self, p, entry, target_lag=TARGET_LAG):
        info = entry['info']
        replay = {'match': info['match'], 'inputs': nr.encode_inputs([]), 'checksums': {}, 'frames': 0,
                  'local_side': 0, 'setup': info.get('setup') or {}, 'manifest': None}
        super().__init__(p, replay, journal=False)
        self.entry = entry
        self.target_lag = target_lag
        self.started = False
        self.stats.update(spectate_stalls=0, catchup_frames=0, max_lag=0)
        self.sync()

    def sync(self):
        """取得房主已转发的输入与校验值。"""
        self.inputs = self.entry['inputs']
        self.total = len(self.inputs)
        for frame, value in self.entry['checksums'].items():
            self.recorded[int(frame)] = tuple(value)
        for frame in [f for f in self.recorded if f <= self.frame and f not in self.verified_frames]:
            self.check(frame)

    def ended(self):
        end = self.entry.get('end')
        return end is not None and self.frame >= int(end['frames'])

    def tick(self):
        """每显示帧调用一次。返回是否显示了画面。"""
        self.sync()
        lag = self.total - self.frame
        self.stats['max_lag'] = max(self.stats['max_lag'], lag)
        final = self.entry.get('end') is not None
        if not self.started:
            if lag < self.target_lag and not final:
                return False
            self.started = True
        if lag <= 0:
            self.stats['spectate_stalls'] += 0 if final else 1
            return False
        if lag > self.target_lag + 60:
            steps = min(30, lag - self.target_lag)       # 中途加入或长时间中断后：追赶
            self.stats['catchup_frames'] += steps - 1
        elif lag > self.target_lag + 15 and not final:
            steps = 2
        else:
            steps = 1
        for index in range(steps):
            self.advance(present=index == steps - 1)
        return True
