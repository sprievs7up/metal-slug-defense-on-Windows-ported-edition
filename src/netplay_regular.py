"""常规联机对战（N6a，docs/netcode/N6A_REGULAR_NETPLAY_2026-10-10.md）。

在 N1–N5 的回滚会话（NetplayBattle）之上，按原版 Wi-Fi 对战的操作方式运行：
- 双方以存档的当前编队、单位等级与据点基础状态开战（netplay_profile.development；承诺—揭示后写入本场设定 player_status / enemy_status）。
- 操作（R7、R8）：本方使用原生底栏（10 格、滚动、AP 升级与弹头车按钮）与点击单位发动单体绝招；原生触点照常处理命中与按压，
  核心第 22 版捕获钩子（功能位 1024）把出兵、据点升级、弹头车与单体绝招记入核心缓冲区，本类在下一次排程时取走并转为本方输入，
  双方在同一帧执行。暂停、倍速与 AUTO 屏幕按钮在联机中不响应；键盘 1–0、空格、` 与 - 同样转为输入。
- 画面不镜像（R4）：P2 一方把底栏绑定到 P2 控制器（与房主相同分配的 P2 出兵格图集，开战时由 LAB 为双方建立）、原生界面事件的本方队伍
  （BattleScene +0x2c / +0x64）改为 P2，镜头移到 P2 据点；P2 的底栏左右栏位与 P1 相同（R7 补充，原生界面即如此）。
  这些均为本地界面状态，不在周期校验范围内，由校验值确认不影响模拟。
- 触点只在实际显示的帧中送入原生（回滚恢复会撤销显示帧之前送入的触点）；回滚时底栏、TouchEvent 与 BattleScreenTouch 的触点记录、
  音乐 / 音效开关与镜头一样保持当前值（本地界面；BattleScreenTouch 的触点记录另不计入周期校验，netplay_session.SCREEN_TOUCH）。
- 投降（Esc 菜单）为输入位 SURRENDER：双方在同一已确认帧判定本轮结束；同一帧双方都投降时为平手（netplay_lobby.RegularDriver）。
"""
import ctypes
import struct
from collections import deque

from netplay_session import AP, DEPLOY_MASK, SCREEN_TOUCH, SLUG, SPECIAL, SURRENDER, UNIT_SHIFT, NetplayBattle

OPERATOR_UI = (0x10, 0x78)          # BattlePlayerOperator：触点坐标、按压槽位 +0x20、屏幕按钮 +0x24、拖动 +0x34/+0x38、滚动 +0x60..+0x74
OPERATOR_GFX = (188, 9)             # 出兵格图集等 9 字（与 lab_hooks swap_gfx 相同）
TOUCH_EVENT_BYTES = 0x1e0           # TouchEvent 对象（当前与上一次触点数据、触点计数）
AUDIO_WORDS = 0x3d5c                # app 偏移：音乐、音效开关（audio_options），回滚时保持当前值
SCENE_TEAM, SCENE_MEMBER = 0x2c, 0x64
ACTION_KINDS = {1: 'deploy', 2: 'ap', 3: 'slug', 4: 'unit'}


class LocalActions:
    """本方操作 → 逐帧输入：每帧至多一次出兵与一次单体绝招，据点升级、全体绝招、弹头车可与之合并；其余顺延到后续帧。"""

    def __init__(self):
        self.queue = deque()
        self.stats = {'actions': 0, 'deferred': 0}

    def add(self, kind, value=0):
        self.queue.append((kind, int(value)))
        self.stats['actions'] += 1

    def take(self):
        value, deploy, unit, rest = 0, False, False, deque()
        while self.queue:
            kind, v = self.queue.popleft()
            if kind == 'deploy' and not deploy:
                value |= (v + 1) & DEPLOY_MASK
                deploy = True
            elif kind == 'unit' and not unit:
                value |= ((v + 1) & 0xffffff) << UNIT_SHIFT
                unit = True
            elif kind == 'ap':
                value |= AP
            elif kind == 'special':
                value |= SPECIAL
            elif kind == 'slug':
                value |= SLUG
            elif kind == 'surrender':
                value |= SURRENDER
            else:
                rest.append((kind, v))
                self.stats['deferred'] += 1
        self.queue = rest
        return value


def touch_event_address(p):
    """原生 TouchEvent 对象：Java_…_onTouchEvent（0x164118）取 [[全局]+0x80]。"""
    import probe
    base = probe.BASE
    literal = p.word(base + 0x1641a8)
    holder = p.word((base + literal + 0x16412a) & 0xffffffff)
    return p.word(holder + 0x80) if holder else 0


class RegularBattle(NetplayBattle):
    def __init__(self, p, local_side, seed, delay=2, transport=None, interval=30, journal=True):
        super().__init__(p, local_side, seed, delay=delay, interval=interval, transport=transport, journal=journal)
        self.se_sides = (local_side,)
        self.actions = LocalActions()
        self.touches = deque()
        self.bound = None                    # (operator, 原 P1 控制器, 原队伍, 原成员)
        self.operator = self.touch_event = 0
        self.on_present = None               # 回调：实际显示帧的界面绘制（连接状态、Esc 菜单，netplay_lobby）
        self.local_input = self.collect
        self.stats.update(touches=0, native_actions=0, native_dropped=0, ui_preserved=0)

    # ---------- 开战 ----------
    def prepare(self, config):
        self.lab.netplay_mode = 'regular'
        super().prepare(config)

    def battle_controllers(self):
        """P1（队伍 0）与 P2（队伍 1）的控制器，须在绑定视角之前取得：LAB 的 controllers() 以底栏绑定的控制器为“我方”，
        原生 BattleMain::getPlayerController / getEnemyController 以 BattleScene +0x2c 选择（只在开战设定等非逐帧代码中调用）。"""
        p = self.p
        main = p.word(p.app_instance() + 0xc220)
        return (p.call('_ZN10BattleMain19getPlayerControllerEv', main), p.call('_ZN10BattleMain18getEnemyControllerEv', main))

    def begin(self):
        p1, p2 = self.battle_controllers()
        self.bind_view(p1, p2)               # 在第 0 帧的回滚基准之前：恢复到第 0 帧仍保持本方视角
        self.lab.controllers = lambda: (p1, p2, None)
        try:
            values = super().begin()
        finally:
            del self.lab.controllers
        if self.local_side == 1:
            screen = self.screen
            if screen:
                self.p.call('_ZN12BattleScreen12movePositionEi', screen, 100000)   # 镜头移到 P2 据点（原生按场地宽度限定）
        self.take_native()                   # 第 0 帧之前的触点操作不计
        self.actions.queue.clear()
        return values

    def bind_view(self, mine, enemy):
        p, lab = self.p, self.lab
        _, scene = lab.battle()
        operator = p.word(scene + 0x3c) if scene else 0
        self.operator = operator
        self.touch_event = touch_event_address(p)
        if self.local_side != 1 or not operator:
            return
        import lab as labmod
        if not p.word(labmod.LAB_HEADER + labmod.LAB_ENEMY_GFX_READY):
            lab.build_enemy_graphics(enemy)
        self.swap_gfx(operator)
        self.bound = (operator, p.word(operator + 24), p.word(scene + SCENE_TEAM), p.word(scene + SCENE_MEMBER), scene)
        p.put(operator + 24, enemy)
        pitch = struct.unpack('<f', p.read(operator + 108, 4))[0]
        visible = 6 if p.read(operator + 12, 1)[0] else 5
        p.put(operator + 104, int((p.word(enemy + 912) - visible) * pitch) & 0xffffffff)   # 最大滚动（BattlePlayerOperator::initialize）
        p.put(operator + 100, 0)
        p.write(operator + 112, struct.pack('<f', 0.0))
        p.put(scene + SCENE_TEAM, p.word(enemy + 0x38c))
        p.put(scene + SCENE_MEMBER, p.word(enemy + 0x39c))

    def swap_gfx(self, operator):
        import lab as labmod
        p = self.p
        base = labmod.LAB_HEADER + labmod.LAB_ENEMY_GFX
        for i in range(OPERATOR_GFX[1]):
            a, b = operator + OPERATOR_GFX[0] + 4 * i, base + 4 * i
            va, vb = p.word(a), p.word(b)
            p.put(a, vb)
            p.put(b, va)

    def unbind_view(self):
        if not self.bound:
            return
        p = self.p
        operator, controller, team, member, scene = self.bound
        self.bound = None
        p.put(operator + 24, controller)
        self.swap_gfx(operator)
        p.put(scene + SCENE_TEAM, team)
        p.put(scene + SCENE_MEMBER, member)

    def end(self):
        self.unbind_view()                   # 交还原生底栏对象后由 LAB 按原生方式释放 P2 图集
        self.lab.netplay_mode = None
        super().end()

    # ---------- 本方输入 ----------
    def take_native(self):
        fn = getattr(self.p.uc.lib, 'msd_netplay_take_actions', None)
        if fn is None:
            return
        buffer = (ctypes.c_uint32 * 64)()
        dropped = ctypes.c_uint32(0)
        fn.restype = ctypes.c_uint32
        count = fn(buffer, ctypes.c_uint32(32), ctypes.byref(dropped))
        self.stats['native_dropped'] += dropped.value
        for i in range(count):
            kind = ACTION_KINDS.get(buffer[2 * i])
            if kind is not None:
                self.actions.add(kind, buffer[2 * i + 1])
                self.stats['native_actions'] += 1

    def collect(self, frame, side):
        if side != self.local_side:
            return 0
        self.take_native()
        return self.actions.take()

    def command(self, action, value=0):
        """键盘（窗口线程入队，游戏线程执行）：'deploy' 槽位、'ap'、'special'、'slug'。投降由对战驱动直接加入本方操作。"""
        if action in ('deploy', 'ap', 'special', 'slug'):
            self.actions.add(action, value)

    def queue_touch(self, action, x, y):
        self.touches.append((action, x, y))

    # ---------- 帧 ----------
    def simulate(self, frame, present):
        if present and self.touches:
            native = getattr(self.p, 'native_touch', None)
            while self.touches and native is not None:
                native(*self.touches.popleft())
                self.stats['touches'] += 1
        super().simulate(frame, present)

    def ui_capture(self):
        p = self.p
        saved = []
        if self.operator:
            saved.append((self.operator + OPERATOR_UI[0], p.read(self.operator + OPERATOR_UI[0], OPERATOR_UI[1] - OPERATOR_UI[0])))
        if self.touch_event:
            saved.append((self.touch_event, p.read(self.touch_event, TOUCH_EVENT_BYTES)))
        app = p.app_instance()
        main = p.word(app + 0xc220)
        screen_touch = p.word(main + 4) if main else 0
        if screen_touch:                                                     # BattleScreenTouch 的触点记录（本地点击）
            saved.append((screen_touch + SCREEN_TOUCH[0], p.read(screen_touch + SCREEN_TOUCH[0], SCREEN_TOUCH[1] - SCREEN_TOUCH[0])))
        saved.append((app + AUDIO_WORDS, p.read(app + AUDIO_WORDS, 8)))       # Esc 菜单的音乐 / 音效开关（玩家设定）
        return saved

    def rollback(self, first):
        saved = self.ui_capture()
        super().rollback(first)
        for address, raw in saved:
            self.p.write(address, raw)
        self.stats['ui_preserved'] += 1

    def lab_update(self):
        """实际显示帧：键盘指令转为输入，再做逻辑部分（不暂停，无菜单）。"""
        lab = self.lab
        others = []
        while lab.commands:
            command = lab.commands.popleft()
            if command[0] == 'np':
                self.command(*command[1:])
            else:
                others.append(command)
        lab.commands.extend(others)
        self.logic_tick()
        if self.on_present is not None:
            self.on_present()

    def logic_tick(self):
        """战斗逻辑部分（模拟的一部分，双方相同）：头部、联机修正；绝招光圈本方为原生、对方为红色（视角不同只改变指针，不在校验范围内）。"""
        lab = self.lab
        mine, enemy = self.controllers
        lab.publish_enemy(enemy)
        lab.apply_advantage(mine, enemy)
        if self.playing():
            lab.fix_units(mine, enemy, red_team=self.p.word((mine, enemy)[1 - self.local_side] + 0x38c))

    def status(self):
        s = super().status()
        s.update(local_actions=dict(self.actions.stats), bound=bool(self.bound))
        return s
