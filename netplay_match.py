"""联机对局协议（N4，docs/netcode/N4_NETWORK_LAYER_2026-10-10.md 第 4 节），在 PeerLink 的可靠消息之上运行。

非阻塞：外层每帧调用 poll()，按 state 推进界面或对战流程。
1. hello：双方交换协议版本、内容清单摘要（M7）、地图池、输入延迟偏好与随机数 nonce。摘要相同即兼容；不同时双方交换完整清单，
   以 content_manifest.diff 列出差异并拒绝（state 'rejected'，differences）。
2. decks（编队，R4：与官方相同，只在开战前一刻得知对方编队）：本方锁定编队时只发送承诺值
   BLAKE2b(规范化编队 + 轮次 + 随机盐)；双方都已承诺后才揭示编队与盐，收到后核对承诺值与编队结构。
   修改过的客户端既不能在锁定前得知对方编队，也不能在得知后更换本方编队。
3. locked：本轮设定 match 可用——比赛种子与地图由双方的 nonce 共同决定（任何一方都不能单独选择），
   地图从地图池中按种子抽取；输入延迟取双方（自动或指定）值中较大者；房主为 P1（左），加入方为 P2（右），画面不镜像（R4）。
4. ready / go：双方到达联机第 0 帧后（到达前后都不再推进原生帧）交换校验值、原生战斗帧号与双方编队各单位的实际数值摘要（N5），
   一致后互发 go，收到对方 go 即开始（state 'battle'，对战数据走 PeerLink 的不可靠通道，轮次号为本轮）。
   不一致时拒绝（frame0_mismatch，differences 指出不同的项与单位）。
5. desync（N5）：对战中任一方检测到分歧（周期校验不同或对方校验值长期缺失）即结束对战并发送 desync 通知与 desync_data
   （分歧帧附近的状态快照、已确认输入、单位数据表逐行摘要）；收到通知的一方同样结束并回送本方数据（peer_desync、peer_desync_data），
   双方各自以 netplay_desync.build_report 生成相同内容的分歧报告。第 0 帧不一致时同样交换第 0 帧的数据。
6. result：对战结束后交换已确认帧的周期校验值，比较共同帧（state 'result'，outcome）。
7. rematch（再战，R4）：任一方 request_rematch()，对方也 request_rematch() 后进入下一轮（新的 nonce → 新种子与地图，重新锁定编队）；
   leave() 离开（对方 state 'left'）。
"""
import hashlib
import json
import math
import os
import time

import content_manifest
import netplay_desync
from netplay_net import PROTOCOL, b64, unb64

DECK_SLOTS = 10
MAX_LEVEL = 40


def canonical(value):
    return content_manifest.canonical(value)


def deck_commitment(deck, number, salt, status=None):
    """承诺值：规范化编队 + 轮次（+ 常规联机的据点基础状态，N6a）+ 随机盐的 BLAKE2b。"""
    content = {'deck': deck, 'round': number}
    if status is not None:
        content['status'] = status
    raw = canonical(content).encode('utf-8') + salt
    return hashlib.blake2b(raw, digest_size=32).hexdigest()


def clean_profile(profile):
    """对方名片（N6a）：名称、头像号、留言号、本地战绩；只保留结构正确的字段。"""
    import netplay_profile
    out = {}
    if not isinstance(profile, dict):
        return out
    name = profile.get('name')
    if isinstance(name, str):
        out['name'] = netplay_profile.clean_name(name)
    for key, limit in (('avatar', 255), ('message', 255)):
        value = profile.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= limit:
            out[key] = value
    record = profile.get('record')
    if isinstance(record, dict):
        out['record'] = {k: v for k, v in record.items() if k in ('wins', 'losses', 'draws')
                         and isinstance(v, int) and not isinstance(v, bool) and 0 <= v < 10**7}
    return out


def validate_deck(deck, known_keys=None):
    """编队结构：10 格，每格为 null 或 [单位, 等级]；单位为 1–399 的原版 UnitID 或已知社区单位稳定键；等级 1–40；至少一格。
    返回错误说明（None 表示有效）。"""
    if not isinstance(deck, list) or len(deck) != DECK_SLOTS:
        return 'deck_size'
    filled = 0
    for entry in deck:
        if entry is None:
            continue
        if not isinstance(entry, list) or len(entry) != 2:
            return 'deck_entry'
        unit, level = entry
        if isinstance(unit, bool) or not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= MAX_LEVEL:
            return 'deck_level'
        if isinstance(unit, int):
            if not 1 <= unit <= 399:
                return 'deck_unit'
        elif isinstance(unit, str):
            if known_keys is not None and unit not in known_keys:
                return 'deck_unit'
        else:
            return 'deck_unit'
        filled += 1
    return None if filled else 'deck_empty'


def auto_delay(rtt_seconds):
    """自动输入延迟：单向延迟（往返的一半）折算帧数后减 4，限制在 2–6 帧，使常见网络下回滚深度不超过约 4 帧。"""
    if rtt_seconds is None:
        return 2
    one_way_frames = rtt_seconds * 15.0               # 往返秒数 / 2 × 30 帧每秒
    return max(2, min(6, math.ceil(one_way_frames - 1e-9) - 4))


def round_values(host_nonce, client_nonce, number, pool):
    material = b'msd-netplay-round' + host_nonce + client_nonce + number.to_bytes(4, 'little')
    seed = int.from_bytes(hashlib.blake2b(material + b'seed', digest_size=4).digest(), 'little') & 0x7fffffff
    pick = int.from_bytes(hashlib.blake2b(material + b'stage', digest_size=4).digest(), 'little')
    return seed, pool[pick % len(pool)]


class Match:
    def __init__(self, link, role, manifest, name='', delay=2, pool=(1011,), version='', known_keys=None, digest=None,
                 profile=None, mode=None):
        self.link, self.role = link, role
        self.manifest = manifest
        self.digest = digest or content_manifest.digest(manifest)
        self.name, self.delay_pref, self.pool, self.version = name, int(delay), [int(s) for s in pool], version
        self.profile = dict(profile or {})       # 本方名片（N6a），hello 时发送
        self.mode = mode                          # 对局种类（N6a 'regular'；双方不同即拒绝）
        self.known_keys = known_keys
        self.state = 'hello'          # hello、comparing、decks、locked、battle、result、leaving、rejected、left、disconnected
        self.reason = None
        self.differences = None
        self.round = 1
        self.nonce = os.urandom(16)
        self.peer = None
        self.manifest_sent = False
        self.nonces = None            # (房主 nonce, 加入方 nonce)
        self.match = None
        self.outcome = None
        self.rematch_nonce = None
        self.peer_rematch = None
        self.history = []             # 各轮的 match 与 outcome
        self.reset_round()

    def reset_round(self):
        self.local_deck = self.salt = self.commit = None
        self.local_status = self.peer_status = None
        self.peer_commit = self.peer_deck = None
        self.revealed = False
        self.ready_sent = self.peer_ready = None
        self.go_sent = self.peer_go = False
        self.result_sent = self.peer_result = None
        self.desync_sent = self.peer_desync = self.peer_desync_data = None

    # ---------- 发送 ----------
    def send(self, message):
        self.link.send_message(dict(message, round=self.round))

    def start(self):
        self.send({'type': 'hello', 'protocol': PROTOCOL, 'version': self.version, 'digest': self.digest,
                   'name': self.name, 'delay': self.delay_pref, 'pool': self.pool, 'nonce': self.nonce.hex(),
                   'profile': self.profile, 'mode': self.mode})

    def reject(self, reason, differences=None):
        self.state, self.reason = 'rejected', reason
        if differences is not None:
            self.differences = differences
        self.send({'type': 'reject', 'reason': reason, 'differences': differences or []})

    def lock_deck(self, deck, status=None):
        """锁定本方编队（只发送承诺值）。status：常规联机的据点基础状态（17 字，N6a），与编队一起承诺与揭示。"""
        if self.state != 'decks' or self.commit is not None:
            raise RuntimeError('当前不能锁定编队: ' + self.state)
        error = validate_deck(deck, self.known_keys)
        if error:
            raise ValueError(error)
        if status is not None:
            import netplay_profile
            error = netplay_profile.status_error(status)
            if error:
                raise ValueError(error)
        self.local_deck = json.loads(canonical(deck))
        self.local_status = None if status is None else [int(v) for v in status]
        self.salt = os.urandom(16)
        self.commit = deck_commitment(self.local_deck, self.round, self.salt, self.local_status)
        self.send({'type': 'deck_commit', 'hash': self.commit})
        self.check_decks()

    def send_ready(self, checksum, battle_frame, units=None):
        """本方已到达联机第 0 帧（之后在收到 go 之前不推进原生帧）。units：双方编队各单位的实际数值摘要（N5）。"""
        self.ready_sent = {'checksum': [int(v) for v in checksum], 'battle_frame': int(battle_frame),
                           'units': [list(u) for u in units or []]}
        self.send(dict(self.ready_sent, type='ready'))
        self.check_ready()

    def send_result(self, summary):
        """本方对战结束：summary 含 confirmed、finished_frame、reason、checksums（{帧: [h, d]}）。"""
        self.result_sent = dict(summary)
        self.send(dict(self.result_sent, type='result'))
        self.check_result()

    def send_desync(self, notice, payload):
        """本方结束对战的分歧通知（kind、frame、by）与分歧数据（NetplayBattle.desync_payload）。每轮只发送一次。"""
        if self.desync_sent is not None:
            return
        self.desync_sent = dict(notice)
        self.send(dict(notice, type='desync'))
        self.send({'type': 'desync_data', 'data': payload})

    def request_rematch(self):
        if self.rematch_nonce is None:
            self.rematch_nonce = os.urandom(16)
            self.link.send_message({'type': 'rematch', 'round': self.round + 1, 'nonce': self.rematch_nonce.hex()})
        self.check_rematch()

    def leave(self, reason='leave', wait=3.0):
        """离开：先发离开消息，待已发出的可靠消息（如本方结果）全部被对方确认（最多 wait 秒）后再断开，
        对方因此一定先收到结果再收到离开。之后 poll() 把状态推进到 'left'。"""
        if self.state in ('left', 'disconnected', 'leaving'):
            return
        self.link.send_message({'type': 'leave', 'round': self.round, 'reason': reason})
        self.state, self.reason = 'leaving', reason
        self.leave_deadline = time.perf_counter() + wait
        self.finish_leave()

    def finish_leave(self):
        if self.state == 'leaving' and (self.link.reliable_idle() or time.perf_counter() > self.leave_deadline
                                        or self.link.state in ('disconnected', 'closed')):
            self.link.leave(self.reason)
            self.state = 'left'

    # ---------- 接收 ----------
    def poll(self):
        link = self.link
        link.service()
        while True:
            message = link.receive_message()
            if message is None:
                break
            try:
                self.on_message(message)
            except (KeyError, TypeError, ValueError) as error:
                if self.state not in ('rejected', 'left', 'disconnected'):
                    self.reject('bad_message:' + type(error).__name__)
        self.finish_leave()
        if self.state not in ('rejected', 'left', 'disconnected', 'leaving'):
            if link.state == 'disconnected':
                self.state, self.reason = 'disconnected', link.closed_reason or 'timeout'
            elif link.state == 'closed':
                self.state, self.reason = 'left', link.closed_reason or 'peer_left'
        return self.state

    def on_message(self, message):
        kind = message.get('type')
        number = message.get('round')
        if self.state == 'leaving':
            return
        if kind == 'leave':
            self.state, self.reason = 'left', 'peer_left'
            return
        if kind == 'reject':
            if self.state not in ('rejected', 'left', 'disconnected'):
                self.state, self.reason = 'rejected', 'peer:' + str(message.get('reason'))
                if self.differences is None and message.get('differences'):
                    self.differences = message['differences']
            return
        if kind == 'rematch':
            if number == self.round + 1 and self.peer_rematch is None:
                self.peer_rematch = bytes.fromhex(message['nonce'])
                self.check_rematch()
            return
        if number != self.round:
            return                                  # 上一轮迟到的消息
        if kind == 'desync':
            if self.peer_desync is None:
                self.peer_desync = {'kind': str(message.get('kind')), 'frame': message.get('frame'), 'by': message.get('by')}
            return
        if kind == 'desync_data':
            if self.peer_desync_data is None and isinstance(message.get('data'), dict):
                self.peer_desync_data = message['data']
            return
        if kind == 'hello' and self.state == 'hello':
            self.peer = dict(message, profile=clean_profile(message.get('profile')))
            if message.get('protocol') != PROTOCOL:
                return self.reject('protocol')
            if message.get('mode') != self.mode:
                return self.reject('mode')
            if [int(s) for s in message.get('pool', [])] != self.pool:
                return self.reject('pool')
            if message.get('digest') == self.digest:
                return self.enter_decks()
            self.state = 'comparing'
            self.send_manifest()
        elif kind == 'manifest' and self.state in ('hello', 'comparing'):
            self.send_manifest()
            remote = content_manifest.decode(unb64(message['data']))
            differences = content_manifest.diff(self.manifest, remote)
            if differences:
                self.state, self.reason, self.differences = 'rejected', 'content', differences
            elif self.peer is not None:
                self.enter_decks()                  # 摘要不同而比较项一致（如仅来源标签不同）：视为兼容
        elif kind == 'deck_commit' and self.state == 'decks':
            self.peer_commit = str(message['hash'])
            self.check_decks()
        elif kind == 'deck_reveal' and self.state == 'decks' and self.peer_commit is not None:
            deck, salt, status = message['deck'], bytes.fromhex(message['salt']), message.get('status')
            if deck_commitment(deck, self.round, salt, status) != self.peer_commit:
                return self.reject('deck_commitment')
            error = validate_deck(deck, self.known_keys)
            if error:
                return self.reject(error)
            if (status is None) != (self.local_status is None):
                return self.reject('status_missing')       # 一方常规联机（存档发展进度）而另一方不是
            if status is not None:
                import netplay_profile
                error = netplay_profile.status_error(status)
                if error:
                    return self.reject(error)
            self.peer_deck = deck
            self.peer_status = status
            self.peer_delay = int(message.get('delay', 2))
            self.check_decks()
        elif kind == 'ready' and self.state == 'locked':
            self.peer_ready = {'checksum': [int(v) for v in message['checksum']], 'battle_frame': int(message['battle_frame']),
                               'units': [list(u) for u in message.get('units') or []]}
            self.check_ready()
        elif kind == 'go' and self.state == 'locked':
            self.peer_go = True
            self.check_ready()
        elif kind == 'result' and self.state in ('battle', 'locked'):
            self.peer_result = message
            self.check_result()

    def send_manifest(self):
        if not self.manifest_sent:
            self.manifest_sent = True
            self.send({'type': 'manifest', 'data': b64(content_manifest.encode(self.manifest))})

    # ---------- 状态推进 ----------
    def enter_decks(self):
        if self.round == 1:
            peer_nonce = bytes.fromhex(self.peer['nonce'])
            self.nonces = (self.nonce, peer_nonce) if self.role == 'host' else (peer_nonce, self.nonce)
        self.state = 'decks'
        self.reset_round()

    def resolved_delay(self):
        return self.delay_pref if self.delay_pref > 0 else auto_delay(self.link.srtt)

    def check_decks(self):
        if self.commit is not None and self.peer_commit is not None and not self.revealed:
            self.revealed = True
            self.local_delay = self.resolved_delay()
            reveal = {'type': 'deck_reveal', 'deck': self.local_deck, 'salt': self.salt.hex(), 'delay': self.local_delay}
            if self.local_status is not None:
                reveal['status'] = self.local_status
            self.send(reveal)
        if self.revealed and self.peer_deck is not None and self.state == 'decks':
            seed, stage = round_values(self.nonces[0], self.nonces[1], self.round, self.pool)
            host_deck, client_deck = ((self.local_deck, self.peer_deck) if self.role == 'host'
                                      else (self.peer_deck, self.local_deck))
            host_status, client_status = ((self.local_status, self.peer_status) if self.role == 'host'
                                          else (self.peer_status, self.local_status))
            self.match = {'round': self.round, 'seed': seed, 'stage': stage, 'p1_deck': host_deck, 'p2_deck': client_deck,
                          'delay': max(self.local_delay, self.peer_delay), 'side': 0 if self.role == 'host' else 1}
            if host_status is not None:
                self.match.update(p1_status=host_status, p2_status=client_status)
            self.link.begin_round(self.round)
            self.state = 'locked'

    def check_ready(self):
        if self.state != 'locked':
            return
        if self.ready_sent is not None and self.peer_ready is not None and not self.go_sent:
            if self.peer_ready != self.ready_sent:
                self.differences = netplay_desync.frame0_differences(self.ready_sent, self.peer_ready)
                return self.reject('frame0_mismatch', self.differences)
            self.go_sent = True
            self.send({'type': 'go'})
        if self.go_sent and self.peer_go:
            self.state = 'battle'

    def check_result(self):
        if self.result_sent is None or self.peer_result is None:
            return
        mine = self.result_sent.get('checksums') or {}
        theirs = self.peer_result.get('checksums') or {}
        common = sorted(set(mine) & set(theirs), key=int)
        mismatched = [f for f in common if list(mine[f]) != list(theirs[f])]
        self.outcome = {'round': self.round, 'common_checksums': len(common), 'mismatched': mismatched,
                        'local_confirmed': self.result_sent.get('confirmed'), 'peer_confirmed': self.peer_result.get('confirmed'),
                        'local_finished': self.result_sent.get('finished_frame'),
                        'peer_finished': self.peer_result.get('finished_frame'),
                        'local_reason': self.result_sent.get('reason'), 'peer_reason': self.peer_result.get('reason')}
        self.history.append({'match': self.match, 'outcome': self.outcome})
        self.state = 'result'
        self.check_rematch()                         # 对方可能已先请求再战

    def check_rematch(self):
        if self.state != 'result' or self.rematch_nonce is None or self.peer_rematch is None:
            return
        self.round += 1
        self.nonces = ((self.rematch_nonce, self.peer_rematch) if self.role == 'host'
                       else (self.peer_rematch, self.rematch_nonce))
        self.rematch_nonce = self.peer_rematch = None
        self.match = self.outcome = None
        self.state = 'decks'
        self.reset_round()

    def status(self):
        return {'state': self.state, 'reason': self.reason, 'round': self.round, 'match': self.match,
                'outcome': self.outcome, 'differences': self.differences, 'desync_sent': self.desync_sent,
                'peer_desync': self.peer_desync, 'peer': {k: v for k, v in (self.peer or {}).items()
                                                                                    if k in ('name', 'version', 'delay', 'profile', 'mode')}}
