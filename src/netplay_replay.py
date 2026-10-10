"""对战回放（N5.5a，docs/netcode/N5_5_REPLAY_SPECTATE_2026-10-10.md）。

回放文件（.msdreplay）：魔数行 `MSDREPLAY` 之后为 zlib 压缩的 JSON，内容为
- 版本与环境：schema、游戏显示版本、联机协议版本、核心库名、录制时间、种类（netplay / local / reference）；
- 内容清单（M7）的完整内容与摘要：播放前与本机清单比较，不同时拒绝播放并列出差异；
- 初始条件：轮次、比赛种子、地图、双方编队、输入延迟、校验间隔、测试用的据点生命设定；第 0 帧校验值与编队单位摘要；
- 输入流：已确认的每帧双方输入（P1、P2 各一字节，zlib + base64）；
- 周期校验值：已确认帧每 30 帧的 (h, d)，重算时逐点比较；
- 结果：结束原因、结束帧、双方据点生命与胜方、双方名称。
每场自动保存到用户目录（%LOCALAPPDATA%\\MSD_WINDOWS_S1XLV\\netplay\\replays，可由 MSD_REPLAY_DIR 改变），保留最近 KEEP 场；
子目录 kept\\ 中的回放（玩家标记保留）不计入上限、不被清理。

回放会话 ReplayBattle（NetplayBattle 的子类）按记录的输入逐帧重算：
- 校验：每个周期校验帧与录制值比较，第一个不一致时记录 mismatch（netplay_desync.replay_report）。
- 跳转：向后跳转为快速重算（不显示）；向前跳转恢复到最近的关键帧再重算。关键帧每 keyframe_every 帧一个，保存该段中首次被改动的各页在段首的内容
  （由回滚记录的撤销内容取得，不另复制整个内存）与段首的宿主状态；恢复时自后向前写回各段的页内容。
- 暂停与慢速：只渲染帧——置原生暂停标记渲染一帧，再恢复到渲染前的状态（回滚记录），画面保持而状态不变；期间静音。
- 倍速：每个显示帧重算多帧，只显示最后一帧，期间静音。
"""
import base64
import ctypes
import json
import os
import struct
import time
import zlib
from pathlib import Path

import netplay_desync
from netplay_session import NetplayBattle
from netplay_state import PAGE

MAGIC = b'MSDREPLAY\n'
SCHEMA = 2                           # 2：每帧输入 32 位（N6a 单体绝招）、双方据点基础状态；1：每帧输入 1 字节（N5.5）
SUFFIX = '.msdreplay'
KEEP = 100
KEYFRAME_EVERY = 900                 # 30 秒
SPEEDS = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)


class ReplayError(Exception):
    pass


# ---------- 文件 ----------
def default_dir():
    configured = os.environ.get('MSD_REPLAY_DIR')
    if configured:
        return Path(configured)
    local = os.environ.get('LOCALAPPDATA')
    return Path(local) / 'MSD_WINDOWS_S1XLV' / 'netplay' / 'replays' if local else Path(__file__).resolve().parent / 'replays'


def encode_inputs(pairs):
    values = [v & 0xffffffff for pair in pairs for v in pair]
    raw = struct.pack('<%dI' % len(values), *values)
    return base64.b64encode(zlib.compress(raw, 9)).decode('ascii')


def decode_inputs(text, schema=SCHEMA):
    raw = zlib.decompress(base64.b64decode(text))
    if schema < 2:                                       # N5.5：每帧每方 1 字节
        return [(raw[i], raw[i + 1]) for i in range(0, len(raw) - 1, 2)]
    values = struct.unpack('<%dI' % (len(raw) // 4), raw[:len(raw) // 4 * 4])
    return [(values[i], values[i + 1]) for i in range(0, len(values) - 1, 2)]


def build(session, kind, manifest, match, names=None, end=None, setup=None, version='', frame0=None, config=None):
    """由一场已结束（或已停止）的会话生成回放：只含已确认的帧。match：本轮设定（seed、stage、p1_deck、p2_deck、delay、round）。"""
    import content_manifest
    stopped = session.events_end.get(session.finished_frame) if session.finished_frame is not None else None
    hp = stopped if isinstance(stopped, list) else session.base_hp()
    winner = None
    if hp[0] is not None and hp[1] is not None and session.finished_frame is not None:
        winner = 0 if hp[1] <= 0 < hp[0] else 1 if hp[0] <= 0 < hp[1] else None
    frames = len(session.input_log)
    return {
        'schema': SCHEMA, 'kind': kind, 'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'game_version': version,
        'protocol': content_manifest.PROTOCOL, 'core': Path(session.p.uc.library_path).name,
        'manifest_digest': content_manifest.digest(manifest), 'manifest': manifest,
        'match': {'round': match.get('round', 1), 'seed': match['seed'], 'stage': match['stage'], 'p1_deck': match['p1_deck'],
                  'p2_deck': match['p2_deck'], 'p1_status': match.get('p1_status'), 'p2_status': match.get('p2_status'),
                  'delay': match.get('delay', session.delay), 'interval': session.interval,
                  'config': dict(config) if config else None},
        'setup': dict(setup or {}), 'local_side': session.local_side, 'names': list(names or ['P1', 'P2']),
        'frame0': frame0 or {'checksum': list(session.checksum_log.get(0, ())), 'units': session.deck_digests},
        'frames': frames, 'inputs': encode_inputs(session.input_log),
        'checksums': {str(f): list(v) for f, v in sorted(session.checksum_log.items()) if f <= frames},
        'result': {'end': end, 'finished_frame': session.finished_frame, 'base_hp': hp, 'winner': winner},
    }


def file_name(replay):
    stamp = replay.get('created', '').replace('-', '').replace(':', '').replace(' ', '_') or time.strftime('%Y%m%d_%H%M%S')
    return f"replay_{stamp}_r{replay['match'].get('round', 1)}_{replay['match']['stage']}{SUFFIX}"


def save(replay, directory=None, keep=KEEP):
    """写入回放（临时文件后替换），并清理超出保留数的旧回放。返回路径。"""
    directory = Path(directory) if directory is not None else default_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / file_name(replay)
    index = 1
    while path.exists():
        path = directory / file_name(replay).replace(SUFFIX, f'_{index}{SUFFIX}')
        index += 1
    data = MAGIC + zlib.compress(json.dumps(replay, ensure_ascii=False, separators=(',', ':')).encode('utf-8'), 6)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(data)
    os.replace(temporary, path)
    if keep:
        prune(directory, keep)
    return path


def load(path):
    raw = Path(path).read_bytes()
    if not raw.startswith(MAGIC):
        raise ReplayError('not_a_replay')
    try:
        replay = json.loads(zlib.decompress(raw[len(MAGIC):]).decode('utf-8'))
    except (zlib.error, ValueError) as error:
        raise ReplayError('corrupt: ' + type(error).__name__)
    if replay.get('schema') not in (1, SCHEMA):
        raise ReplayError(f"schema {replay.get('schema')}")
    for key in ('match', 'inputs', 'checksums', 'manifest', 'frames'):
        if key not in replay:
            raise ReplayError('missing ' + key)
    return replay


def prune(directory, keep=KEEP):
    """只保留最近 keep 个回放（按修改时间）；子目录（如 kept\\）不受影响。返回删除的文件名。"""
    files = sorted((p for p in Path(directory).glob('*' + SUFFIX) if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = []
    for path in files[keep:]:
        try:
            path.unlink()
            removed.append(path.name)
        except OSError:
            pass
    return removed


def summary(replay):
    """回放列表（N6 历史记录）所需的摘要。"""
    result = replay.get('result') or {}
    return {'created': replay.get('created'), 'kind': replay.get('kind'), 'round': replay['match'].get('round'),
            'stage': replay['match']['stage'], 'names': replay.get('names'), 'frames': replay['frames'],
            'seconds': round(replay['frames'] / 30, 1), 'winner': result.get('winner'), 'end': result.get('end'),
            'game_version': replay.get('game_version')}


def check_content(replay, manifest):
    """本机内容清单与回放录制时的清单比较；返回差异（content_manifest.diff 的格式），空表示可以播放。"""
    import content_manifest
    if content_manifest.digest(manifest) == replay.get('manifest_digest'):
        return []
    return content_manifest.diff(manifest, replay['manifest'])


# ---------- 关键帧 ----------
class KeyframeLog:
    """每 every 帧一个关键帧：段首宿主状态，与该段中首次被改动的各页在段首的内容。"""

    def __init__(self, every=KEYFRAME_EVERY):
        self.every = every
        self.frames = []                 # 关键帧帧号（升序）
        self.hosts = {}
        self.pages = {}                  # 关键帧 → {页地址: 段首内容}
        self.stats = {'keyframes': 0, 'pages': 0, 'restores': 0}

    def start(self, frame, host):
        self.frames.append(frame)
        self.hosts[frame] = host
        self.pages[frame] = {}
        self.stats['keyframes'] += 1

    def record(self, record):
        """一帧的回滚记录（撤销内容为该帧之前的页内容）：本段中首次出现的页保存其撤销内容。"""
        current = self.pages[self.frames[-1]]
        if record.pages is not None:                       # 核心复制（msd_snap_*）
            addresses = struct.unpack('<%dQ' % record.count, record.pages)
            view = memoryview(record.undo)
            for index, address in enumerate(addresses):
                if address not in current:
                    current[address] = view[index * PAGE:(index + 1) * PAGE].tobytes()
                    self.stats['pages'] += 1
        elif record.runs:                                  # 宿主逐段复制
            raise ReplayError('关键帧需要核心快照接口（r44 及以上）')

    def memory_bytes(self):
        return sum(len(pages) for pages in self.pages.values()) * PAGE

    def restore(self, frame):
        """写回各段的页内容，使客体内存回到关键帧 frame（调用前须已撤销上次提交后的写入）。返回该关键帧的宿主状态。"""
        later = [f for f in self.frames if f >= frame]
        for key in reversed(later):
            for address, content in self.pages[key].items():
                ctypes.memmove(address, content, PAGE)
        for key in later[1:]:
            del self.pages[key]
            del self.hosts[key]
        self.frames = [f for f in self.frames if f <= frame]
        self.pages[frame] = {}
        self.stats['restores'] += 1
        return self.hosts[frame]


# ---------- 回放会话 ----------
class ReplayBattle(NetplayBattle):
    """按回放记录的输入重算一场对战。journal=False 时只做校验（不建回滚记录，不能暂停渲染与跳回）。"""

    def __init__(self, p, replay, journal=True, keyframe_every=KEYFRAME_EVERY):
        m = replay['match']
        super().__init__(p, replay.get('local_side', 0) or 0, m['seed'], delay=m.get('delay', 2), interval=m.get('interval', 30),
                         journal=journal)
        self.replay = replay
        self.inputs = decode_inputs(replay['inputs'], replay.get('schema', SCHEMA))
        self.total = int(replay['frames'])
        self.recorded = {int(f): tuple(v) for f, v in replay['checksums'].items()}
        self.verified = 0
        self.verified_frames = set()
        self.mismatch = None
        self.keyframes = KeyframeLog(keyframe_every) if journal and keyframe_every else None
        if self.keyframes is not None:
            self.ledger_confirm = False
            self.on_commit = self.keyframe_commit
        self.paused = False
        self.speed = 1.0
        self.carry = 0.0
        self.muted_by_replay = False
        self.local_input = lambda frame, side: 0

    def replay_config(self):
        """本场设定：本地对战的回放保存了准备界面的完整设定（据点初始等级、优势、支援等）；联机为 match_config。"""
        m = self.replay['match']
        if m.get('config'):
            return dict(m['config'])
        return self.match_config(m['stage'], m['p1_deck'], m['p2_deck'], m.get('p1_status'), m.get('p2_status'))

    def begin(self):
        values = super().begin()
        self.check(0)
        if self.keyframes is not None:
            self.keyframes.start(0, self.journal.base_host)
        return values

    def inputs_for(self, frame):
        values = self.inputs[frame - 1] if 1 <= frame <= len(self.inputs) else (0, 0)
        self.frame_inputs[frame] = values
        return values

    def check(self, frame):
        recorded = self.recorded.get(frame)
        local = self.checksums.get(frame)
        if recorded is None or local is None:
            return
        self.verified += 1
        self.verified_frames.add(frame)
        if tuple(local) != recorded and self.mismatch is None:
            self.mismatch = netplay_desync.replay_report(frame, local, recorded, self.replay['match'].get('round', 0))

    def keyframe_commit(self, frame, record):
        self.keyframes.record(record)
        if frame % self.keyframes.every == 0:
            self.keyframes.start(frame, record.host)

    def finished(self):
        return self.frame >= self.total

    def advance(self, present=True):
        """重算下一帧（present 为真时显示）。回放结束后不再推进。"""
        if self.finished():
            return False
        self.simulate(self.frame + 1, present)
        self.update_confirmed()
        self.check(self.frame)
        return True

    def verify(self, present=False, until=None):
        """无窗口校验：重算至结束（或 until 帧），返回 (校验点数, 第一个不一致)。"""
        limit = self.total if until is None else min(self.total, until)
        while self.frame < limit:
            self.advance(present)
        return self.verified, self.mismatch

    # ---------- 播放控制（只渲染帧 render_paused 与镜头保留见 NetplayBattle） ----------
    def set_muted(self, muted):
        bridge = getattr(self.p, 'audio_bridge', None)
        if bridge is None:
            return
        if muted and not bridge.muted:
            bridge.set_muted(True)
            self.muted_by_replay = True
        elif not muted and self.muted_by_replay:
            bridge.set_muted(False)
            self.muted_by_replay = False

    def tick(self):
        """窗口播放每显示帧调用一次：按暂停与倍速推进。返回本显示帧是否渲染了画面。"""
        if self.paused or self.finished():
            self.set_muted(True)
            return self.render_paused()
        self.set_muted(self.speed != 1.0)
        self.carry += self.speed
        steps = int(self.carry)
        self.carry -= steps
        if steps <= 0:
            return self.render_paused()
        for index in range(steps):
            if not self.advance(present=index == steps - 1):
                return self.render_paused()
        return True

    def seek(self, target):
        """跳到第 target 帧末（并显示该帧）。向前为快速重算；向后恢复到最近的关键帧再重算。"""
        target = max(0, min(self.total, int(target)))
        if target < self.frame:
            if self.keyframes is None:
                raise ReplayError('向后跳转需要关键帧（journal=True）')
            self.restore_keyframe(max(f for f in self.keyframes.frames if f <= target))
        while self.frame < target - 1:
            self.advance(present=False)
        if self.frame < target:
            self.advance(present=True)
        else:
            self.render_paused()
        return self.frame

    def restore_keyframe(self, frame):
        p = self.p
        started = time.perf_counter()
        camera = self.camera()
        self.journal.restore(self.frame)                     # 撤销上次提交后的写入（只渲染帧等）
        host = self.keyframes.restore(frame)
        self.host.apply(host)
        if self.ledger is not None:
            self.ledger.rollback(frame)
            self.ledger.frame = frame
        self.journal.begin(frame, host)
        self.set_camera(camera)
        self.frame = self.confirmed = frame
        self.mode.frame = frame
        for table in (self.checksums, self.snapshots, self.events_end, self.audio_frames, self.frame_inputs):
            for f in [f for f in table if f > frame]:
                del table[f]
        for f in [f for f in self.checksum_log if f > frame]:
            del self.checksum_log[f]
        del self.input_log[frame:]
        if self.finished_frame is not None and self.finished_frame > frame:
            self.finished_frame = None
        if self.mismatch is not None and self.mismatch['frame'] > frame:
            self.mismatch = None
        self.stats['restore_seconds'] += time.perf_counter() - started
        p.log('REPLAY_KEYFRAME_RESTORE', frame, round((time.perf_counter() - started) * 1000, 1))

    def status(self):
        s = super().status()
        s.update(total=self.total, verified=self.verified, mismatch=self.mismatch, paused=self.paused, speed=self.speed,
                 keyframes=dict(self.keyframes.stats, bytes=self.keyframes.memory_bytes()) if self.keyframes else None)
        return s


# ---------- 窗口播放 ----------
class ReplayViewer:
    """窗口回放的会话驱动（lab_runtime.DRIVER_FACTORY）：自动由标题进入 LAB 双人对战准备界面，比较内容清单后开始回放，
    处理播放指令（暂停、跳转、倍速、回到开头、镜头）并在画面底部绘制状态条。指令由窗口线程放入 commands。
    N6 的游戏内回放入口复用本类的播放部分（phase 'playing' 之后）。"""

    BAR_H = 44

    def __init__(self, probe, replay, log=None):
        from collections import deque
        self.p = probe
        self.replay = replay
        self.log = log or (lambda *a: None)
        self.commands = deque()
        self.phase = 'boot'
        self.battle = None
        self.finished = False
        self.taps = []                    # [(到期帧, 动作, x, y)]
        self.menu_frames = 0
        self.prep_requested = False
        self.differences = None
        self.error = None
        self.overlay = None
        self.font = None

    # 窗口线程
    def command(self, *command):
        self.commands.append(command)

    def context(self):
        p = self.p
        app = p.app_instance()
        return p.word(app + 0x22bc), p.word(app + 0x22dc)

    def tap(self, x, y):
        self.taps.append((self.p.frame, 1, x, y))
        self.taps.append((self.p.frame + 3, 3, x, y))

    def drive(self):
        p = self.p
        try:
            for item in [t for t in self.taps if t[0] <= p.frame]:
                self.taps.remove(item)
                p.touch_event(item[1], item[2], item[3])
            if self.phase == 'playing':
                return self.play()
            if self.phase == 'boot':
                self.boot()
            elif self.phase == 'starting' and self.starting():
                return self.play()                           # 第 0 帧起由回放会话推进（不再执行会话之外的原生帧）
            p.step_frame()
            if self.phase in ('rejected', 'error'):
                self.draw_bar(self.status_text())
            return True
        except Exception as error:
            import traceback
            from probe import ProbeCancelled
            if isinstance(error, ProbeCancelled):            # 关闭窗口：交由游戏循环结束
                raise
            self.error = f'{type(error).__name__}: {error}'
            self.phase = 'error'
            self.log('REPLAY_VIEWER_ERROR', traceback.format_exc())
            return False

    def boot(self):
        p = self.p
        lab = p.lab
        scene, state = self.context()
        if scene == 20 and p.frame > 150 and p.frame % 60 == 0 and not self.taps:
            self.tap(640, 500)                                   # 标题画面：进入主菜单
        if scene == 120 and p.frame % 30 == 0:
            self.tap(640, 435)                                   # 原生弹窗（登入奖励等）
        if scene == 82 and p.frame % 30 == 0:
            self.tap(1165, 680)
        self.menu_frames = self.menu_frames + 1 if (scene, state) == (28, 1) else 0
        if self.menu_frames >= 30 and not self.prep_requested:
            import content_manifest
            self.differences = check_content(self.replay, content_manifest.build(p))
            if self.differences:
                self.phase = 'rejected'
                self.log('REPLAY_REJECTED', json.dumps([d.get('zh') for d in self.differences], ensure_ascii=False))
                return
            self.prep_requested = True
            lab.commands.append(('prep', 'versus'))
        if self.prep_requested and lab.prep.open and lab.versus and not lab.prep.busy() and not lab.active:
            self.battle = ReplayBattle(p, self.replay, journal=True)
            self.battle.prepare(self.battle.replay_config())
            self.phase = 'starting'

    def starting(self):
        battle = self.battle
        if not battle.ready():
            return False
        setup = self.replay.get('setup') or {}
        if setup.get('base_hp'):
            p = self.p
            manager = p.call('_ZN19BattleObjectManager11getInstanceEv')
            for team in (0, 1):
                base = p.call('_ZN19BattleObjectManager13getKyotenUnitE12BattleTeamID18BattleTeamMemberID', manager, team, 0)
                p.write(base + 776, struct.pack('<f', setup['base_hp']))     # 与验收工具 set_base_hp 相同
        battle.begin()
        self.phase = 'playing'
        self.log('REPLAY_VIEWER_START', self.replay['match']['stage'], battle.total)
        return True

    def play(self):
        battle = self.battle
        while self.commands:
            command = self.commands.popleft()
            kind = command[0]
            if kind == 'pause':
                battle.paused = not battle.paused
            elif kind == 'seek':
                battle.seek(battle.frame + int(command[1]))
            elif kind == 'start':
                battle.seek(0)
            elif kind == 'speed':
                index = SPEEDS.index(battle.speed) if battle.speed in SPEEDS else 2
                battle.speed = SPEEDS[max(0, min(len(SPEEDS) - 1, index + int(command[1])))]
            elif kind == 'camera' and battle.screen:
                self.p.call('_ZN12BattleScreen12movePositionEi', battle.screen, (-int(command[1])) & 0xffffffff)
        drawn = battle.tick()
        if drawn:
            self.draw_bar(self.status_text())
        return drawn

    def status_text(self):
        if self.phase == 'rejected':
            items = '；'.join(d.get('zh', '') for d in (self.differences or [])[:3])
            return f'回放与本机内容不同，无法播放 Replay rejected：{items}    Esc 退出'
        if self.phase == 'error':
            return f'回放出错 Replay error：{self.error}    Esc 退出'
        b = self.battle
        clock = lambda frame: f'{frame // 1800:02d}:{frame // 30 % 60:02d}'
        state = '暂停 Paused' if b.paused else ('结束 End' if b.finished() else f'×{b.speed:g}')
        check = (f"不一致 Diverged @{b.mismatch['frame']}" if b.mismatch else f'校验 {len(b.verified_frames)}/{len(b.recorded)}')
        return (f'回放 {clock(b.frame)} / {clock(b.total)}  {state}  {check}    '
                f'空格 暂停  ←/→ ±10秒  Shift ±60秒  ↑/↓ 速度  Home 开头  拖动 镜头  Esc 退出')

    def draw_bar(self, text):
        from PIL import Image, ImageDraw
        from lab_ui import W, fonts
        from trial_overlay import SurfaceOverlay
        if self.overlay is None:
            self.overlay = SurfaceOverlay(self.p.graphics)
            self.font = fonts()
        key = ('replay_bar', text)
        image = None
        if self.overlay.cached != key:
            image = Image.new('RGBA', (W, self.BAR_H), (0, 0, 0, 170))
            ImageDraw.Draw(image).text((16, self.BAR_H // 2), text, font=self.font(18), fill=(255, 255, 255, 255), anchor='lm')
        self.overlay.draw_image(image, key, (0, 720 - self.BAR_H, W, self.BAR_H))
