"""本地双人对战的确定性会话与回放录制（N5.5c，docs/netcode/N5_5_REPLAY_SPECTATE_2026-10-10.md）。

本地双人对战（VERSUS → 本地）开战时改经联机会话（NetplayBattle，无网络、不回滚）运行：
- 确定性设定（比赛种子由随机数决定、虚拟时钟、确定性数学、分配清零）与联机相同，因此整场可由“初始设定 + 双方逐帧输入”完整重现；
- 输入层 InputLayer：双方键盘 / 手柄的离散指令（左右选格、出兵、AP、绝招、弹头车）在下一帧开始时以输入字节应用（N6 联机的本机输入复用）；
  选格属于本地界面，不进入输入；同一方同一帧的多个出兵顺延到后续各帧。鼠标只移动镜头（宿主直接移动，不送入原生触点）。
- 暂停菜单打开期间以“只渲染帧”保持画面（渲染后恢复状态），战斗时间与状态不前进，回放中也不出现暂停；
- 回放录制（2026-10-11 用户决定停用）：默认不保存。环境变量 MSD_VERSUS_RECORD=1 时（开发与验证）在结束（战斗结束后 30 帧，
  或菜单的重新开始 / 退出且已进行 MIN_SAVE_FRAMES 帧以上）时按准备界面的完整设定保存回放（netplay_replay，保留最近 100 场）。
环境变量 MSD_VERSUS_SESSION=0 时不使用本会话（回到原来的本地对战流程）。
"""
import os
import time
from collections import deque
from pathlib import Path

import netplay_replay
from netplay_session import AP, DEPLOY_MASK, NetplayBattle, SLUG, SPECIAL

BITS = {'ap': AP, 'special': SPECIAL, 'slug': SLUG}
MIN_SAVE_FRAMES = 900                 # 中途退出时至少 30 秒才保存回放
CONFIG_KEYS = ('stage_id', 'player_deck', 'enemy_deck', 'player_base_level', 'enemy_base_level', 'player_hp_boost',
               'player_atk_boost', 'enemy_hp_boost', 'enemy_atk_boost', 'player_support', 'enemy_support', 'full_control',
               'player_ai', 'enemy_ai', 'player_auto_special', 'enemy_auto_special', 'player_ai_tier', 'enemy_ai_tier')


def enabled():
    return os.environ.get('MSD_VERSUS_SESSION', '1') != '0'


def recording():
    return os.environ.get('MSD_VERSUS_RECORD') == '1'


class InputLayer:
    """双方的离散指令 → 逐帧输入字节。take(一方) 在模拟每一帧时各调用一次。"""

    def __init__(self, lab):
        self.lab = lab
        self.pending = [0, 0]
        self.overflow = (deque(), deque())
        self.stats = {'commands': 0, 'deferred': 0}

    def command(self, side, action):
        lab = self.lab
        self.stats['commands'] += 1
        if action in ('left', 'right'):                     # 选格：本地界面（光标与分栏滚动）
            mine, enemy, _ = lab.controllers()
            controller = (mine, enemy)[side]
            if controller:
                lab.versus_action(side, controller, action)
            return
        if action == 'deploy':
            value = (lab.vs_cursor[side] + 1) & DEPLOY_MASK
            if self.pending[side] & DEPLOY_MASK:
                self.overflow[side].append(value)
                self.stats['deferred'] += 1
            else:
                self.pending[side] |= value
        elif action in BITS:
            self.pending[side] |= BITS[action]

    def take(self, side):
        value, self.pending[side] = self.pending[side], 0
        if self.overflow[side]:
            self.pending[side] = self.overflow[side].popleft()
        return value


class LocalVersusBattle(NetplayBattle):
    """本地对战会话：逐帧处理时另绘制战斗菜单与提示（联机会话省略界面部分）。"""

    def lab_update(self):
        lab = self.lab
        lab.vs_view.prepare()
        if not lab.menu.open and lab.finishing is None:
            lab.vs_camera.update()
        lab.menu.draw()
        self.logic_tick()


class LocalVersusDriver:
    """会话驱动（lab_runtime 的 session_driver）：开战前进入确定性设定，第 0 帧起每显示帧推进一帧，结束时保存回放并交还 LAB。"""

    def __init__(self, lab, seed=None, replay_dir=None):
        self.lab = lab
        self.p = lab.p
        self.seed = seed if seed is not None else int.from_bytes(os.urandom(4), 'little') & 0x7fffffff
        self.replay_dir = replay_dir
        self.session = LocalVersusBattle(self.p, 0, self.seed, delay=0, transport=None, journal=True)
        self.inputs = InputLayer(lab)
        self.session.local_input = lambda frame, side: self.inputs.take(side)
        self.session.on_applied = self.feedback
        self.phase = 'starting'
        self.finished = False
        self.started_at = self.p.frame
        self.saved = None
        self.error = None
        self.config = None
        self.session.mode.enter(reseed=False)
        lab.start_hook = self.session.mode.reseed          # Lab.start 开头、原生战斗初始化之前设定各随机源

    # ---------- 驱动 ----------
    def drive(self):
        lab, session = self.lab, self.session
        try:
            if self.phase == 'starting':
                if lab.active and session.ready():
                    self.begin()
                else:
                    if (not lab.active and self.p.frame - self.started_at > 300) or lab.prep.open and not lab.active:
                        return self.abort('not_started')
                    for _ in range(len(lab.commands)):                         # 第 0 帧之前不接受出兵等指令
                        command = lab.commands.popleft()
                        if command[0] != 'vs':
                            lab.commands.append(command)
                    self.p.step_frame()
                    return True
            self.drain()
            if lab.finishing is not None or not lab.active:
                return self.close(lab.finishing[0] if lab.finishing else 'left')
            if lab.menu.open:
                return session.render_paused()
            session.tick()
            if session.finished_frame is not None and session.frame >= session.finished_frame + 30:
                self.close('finished')
            return True
        except Exception as error:
            import traceback
            from probe import ProbeCancelled
            if isinstance(error, ProbeCancelled):
                raise
            self.error = f'{type(error).__name__}: {error}'
            self.p.log('VERSUS_SESSION_ERROR', traceback.format_exc())
            return self.abort('error')

    def begin(self):
        lab, session = self.lab, self.session
        self.config = {key: lab.config.get(key) for key in CONFIG_KEYS}
        mine, enemy, _ = lab.controllers()
        for key, controller in (('player_deck', mine), ('enemy_deck', enemy)):
            if self.config[key] is None:                      # 存档编队 / 原生 NPC 编队：回放中写成明确的单位与等级
                self.config[key] = self.actual_deck(controller)
        session.config = dict(self.config)
        session.begin()
        self.phase = 'playing'
        self.p.log('VERSUS_SESSION_BEGIN', self.seed, self.config.get('stage_id'))

    def actual_deck(self, controller):
        """控制器 10 个出兵格的实际单位与等级（出兵格信息 +0x10 UnitID、+0x14 内部等级）；社区单位写稳定键。"""
        p = self.p
        community = getattr(p, 'community', None)
        keys = {u['id']: u['key'] for u in community.units} if community is not None else {}
        deck = []
        for slot in range(10):
            info = p.call('_ZNK16BattleController11getUnitInfoEi', controller, slot)
            uid = p.word(info + 0x10) if info else 0
            deck.append([keys.get(uid, uid), p.word(info + 0x14) + 1] if uid else None)
        return deck

    def drain(self):
        """把窗口线程放入的双方指令交给输入层；其他指令照常执行。"""
        lab = self.lab
        others = []
        while lab.commands:
            command = lab.commands.popleft()
            if command[0] == 'vs':
                if lab.vs_battle() and not lab.menu.open:
                    self.inputs.command(command[1], command[2])
            else:
                others.append(command)
        for command in others:
            try:
                lab.execute(command)
            except Exception as error:
                self.p.log('LAB_COMMAND_ERROR', command, type(error).__name__, str(error))

    def feedback(self, side, kind, ok, detail):
        """与原双人对战相同的提示（只在显示帧中）。"""
        from lab_ui import T
        lab, p = self.lab, self.p
        label = ('P1', 'P2')[side]
        if kind == 'deploy':
            reason = detail.get('reason')
            if reason == 'empty':
                lab.feedback(T(p, 'fb_empty_slot', label), False)
            elif reason == 'unit_limit':
                lab.feedback(T(p, 'fb_unit_limit', label), False)
            elif reason == 'cannot':
                mine, enemy = self.session.controllers
                controller = (mine, enemy)[side]
                from lab import PB
                lab.feedback(T(p, 'fb_cannot', label, p.call(PB + '5getAPEv', controller), p.word(detail['info'])), False)
            else:
                lab.feedback(T(p, 'fb_vs_deployed' if ok else 'fb_rejected', label), ok)
        elif kind == 'ap':
            lab.feedback(T(p, 'fb_vs_ap' if ok else 'fb_vs_ap_no', label), ok)
        elif kind == 'slug':
            lab.feedback(T(p, 'fb_vs_slug' if ok else 'fb_vs_slug_no', label), ok)
        elif kind == 'special':
            count = detail.get('count', 0)
            lab.feedback(T(p, 'fb_vs_special', label, count) if count else T(p, 'fb_vs_special_none', label), bool(count))

    # ---------- 结束 ----------
    def close(self, reason):
        """结束会话并交还 LAB 的正常流程；录制开启时先保存回放（战斗结束，或中途退出且已进行 MIN_SAVE_FRAMES 帧以上）。"""
        session = self.session
        if recording() and (session.finished_frame is not None or len(session.input_log) >= MIN_SAVE_FRAMES):
            self.save(reason)
        self.end()
        self.p.step_frame()                                   # 本显示帧交给 LAB 的正常流程（结果演出、闸门等）
        return True

    def save(self, reason):
        import content_manifest
        session = self.session
        try:
            manifest = content_manifest.build(self.p)
            match = {'round': 1, 'seed': self.seed, 'stage': self.config.get('stage_id'), 'p1_deck': self.config.get('player_deck'),
                     'p2_deck': self.config.get('enemy_deck'), 'delay': 0}
            import branding
            version = branding.load(Path(__file__).resolve().parent)['display_version']
            replay = netplay_replay.build(session, 'local', manifest, match, names=['P1', 'P2'], end=reason, version=version,
                                          config=self.config)
            started = time.perf_counter()
            path = netplay_replay.save(replay, self.replay_dir)
            self.saved = {'path': str(path), 'frames': replay['frames'], 'seconds': round(time.perf_counter() - started, 3)}
            self.p.log('VERSUS_REPLAY_SAVED', path, replay['frames'])
        except Exception as error:
            self.error = f'{type(error).__name__}: {error}'
            self.p.log('VERSUS_REPLAY_ERROR', self.error)

    def end(self):
        if self.phase in ('playing', 'starting'):
            self.session.end()
        self.phase = 'ended'
        self.finished = True
        if getattr(self.lab, 'local_driver', None) is self:
            self.lab.local_driver = None

    def abort(self, reason):
        self.p.log('VERSUS_SESSION_ABORT', reason, self.error)
        if self.lab.start_hook == self.session.mode.reseed:
            self.lab.start_hook = None
        self.session.mode.exit()
        if self.phase == 'playing':
            self.session.end()
        self.phase = 'ended'
        self.finished = True
        self.p.step_frame()
        return True

    def status(self):
        return {'phase': self.phase, 'seed': self.seed, 'frame': self.session.frame, 'inputs': dict(self.inputs.stats),
                'saved': self.saved, 'error': self.error}
