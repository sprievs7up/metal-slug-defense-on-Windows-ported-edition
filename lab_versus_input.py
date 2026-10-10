"""本地双人对战的输入：键位校验、手柄（Xbox 360 布局，GLFW gamepad 映射）与镜头仲裁。

- 键位（docs/lab/local_versus_design_2026-10-06.md 5.4）：每名玩家 6 项，同一玩家内不得重复（指定已占用的键时两项互换），
  两名玩家之间允许重复；Esc、F1–F25、修饰键（Shift/Ctrl/Alt/Win）与系统锁定键不可指定。
- 手柄（5.8）：GLFW 规定手柄函数只在主线程调用，PadPoller.poll 由窗口线程每轮事件循环调用（player.Player.poll_input），
  只把指令放入 lab.commands，由游戏线程执行。十字键与左摇杆只负责左右选择（按住连发），功能键 A/X/Y/B 可自定义，
  START 为战斗中菜单。两只手柄按连接顺序分给 P1、P2；只有一只时按设定分给 P2（默认）或 P1。
- 镜头（5.8）：双方右摇杆与 P1 的鼠标拖动参与仲裁。先开始输入的一方控制，直至其输入结束；同一帧同时开始时 P1 优先。
  移动经原生 BattleScreen::movePosition（0x1d65c4，位置按场地范围截取），BattleScreen 位于操作者（scene+0x3c）+28，
  与原生拖动（BattlePlayerOperator::update 以 −op[+52] 调用同一函数）相同。
"""
import time

ACTIONS = ('left', 'right', 'ap', 'deploy', 'special', 'slug')
PAD_ACTIONS = ('ap', 'deploy', 'special', 'slug')        # 手柄可自定义的功能键；左右固定为十字键 / 左摇杆
PAD_DEFAULTS = {'deploy': 'A', 'ap': 'X', 'special': 'Y', 'slug': 'B'}
# GLFW gamepad 按键序号（glfw.GAMEPAD_BUTTON_*）；LT、RT 为轴 4、5，按下超过 0.5 视为按键。
PAD_BUTTONS = {'A': 0, 'B': 1, 'X': 2, 'Y': 3, 'LB': 4, 'RB': 5, 'BACK': 6, 'START': 7, 'GUIDE': 8, 'LS': 9, 'RS': 10,
               'DPAD_UP': 11, 'DPAD_RIGHT': 12, 'DPAD_DOWN': 13, 'DPAD_LEFT': 14}
PAD_BINDABLE = ('A', 'B', 'X', 'Y', 'LB', 'RB', 'LT', 'RT', 'BACK', 'LS', 'RS')
STICK_SELECT = 0.5            # 左摇杆选择阈值
STICK_DEAD = 0.25             # 右摇杆镜头死区
CAMERA_SPEED = 20             # 右摇杆推满时每帧镜头移动量（原生场地坐标）
REPEAT_DELAY, REPEAT_RATE = 0.35, 0.12   # 左右选择按住连发（秒）
MAX_PADS = 16
BANNED_KEYS = ('ESCAPE', 'LEFT_SHIFT', 'RIGHT_SHIFT', 'LEFT_CONTROL', 'RIGHT_CONTROL', 'LEFT_ALT', 'RIGHT_ALT',
               'LEFT_SUPER', 'RIGHT_SUPER', 'MENU', 'PRINT_SCREEN', 'CAPS_LOCK', 'SCROLL_LOCK', 'NUM_LOCK', 'PAUSE')


def glfw_key_names():
    """GLFW 键码 → 键名（KEY_ 之后部分）；KEY_LAST 与 KEY_MENU 同值时取 MENU。"""
    import glfw
    names = {}
    for attr in dir(glfw):
        if attr.startswith('KEY_') and attr not in ('KEY_LAST', 'KEY_UNKNOWN'):
            value = getattr(glfw, attr)
            if isinstance(value, int) and value >= 0:
                names.setdefault(value, attr[4:])
    return names


def key_banned(name):
    name = str(name).upper()
    return name in BANNED_KEYS or (name.startswith('F') and name[1:].isdigit())


def bind(table, action, value):
    """在一名玩家的 {动作: 键} 中指定 action = value；value 已属于其他动作时两项互换。返回被互换的动作或 None。"""
    swapped = next((other for other, current in table.items() if other != action and current == value), None)
    if swapped is not None:
        table[swapped] = table[action]
    table[action] = value
    return swapped


class PadPoller:
    """窗口线程：读取已连接手柄，产生 lab 指令，并把右摇杆横向值交给 lab.vs_camera。"""

    def __init__(self):
        self.previous = {}          # jid → 上一轮按下的按键名集合
        self.repeat = {}            # (jid, 'left'/'right') → 下次连发时刻
        self.status = None

    def gamepads(self, glfw):
        pads = []
        for jid in range(MAX_PADS):
            try:
                if glfw.joystick_is_gamepad(jid):
                    pads.append(jid)
            except Exception:
                continue
        return pads

    @staticmethod
    def pressed(state):
        buttons, axes = state.buttons, state.axes
        names = {name for name, index in PAD_BUTTONS.items() if buttons[index]}
        if axes[4] > 0.5:
            names.add('LT')
        if axes[5] > 0.5:
            names.add('RT')
        if 'DPAD_LEFT' in names or axes[0] < -STICK_SELECT:
            names.add('LEFT')
        if 'DPAD_RIGHT' in names or axes[0] > STICK_SELECT:
            names.add('RIGHT')
        if 'DPAD_UP' in names or axes[1] < -STICK_SELECT:
            names.add('UP')
        if 'DPAD_DOWN' in names or axes[1] > STICK_SELECT:
            names.add('DOWN')
        return names

    def assignment(self, lab, pads):
        """jid → 玩家（0 为 P1，1 为 P2）。"""
        if len(pads) >= 2:
            return {pads[0]: 0, pads[1]: 1}
        if pads:
            return {pads[0]: 0 if lab.config.get('versus_pad_single', 'p2') == 'p1' else 1}
        return {}

    def poll(self, lab):
        import glfw
        pads = self.gamepads(glfw)
        sides = self.assignment(lab, pads)
        status = tuple((jid, sides.get(jid), glfw.get_gamepad_name(jid) or '') for jid in pads)
        if status != self.status:
            self.status = status
            lab.pad_status = status
            lab.commands.append(('prep_key', 'pads'))
        now = time.perf_counter()
        sticks = [0.0, 0.0]
        prep, battle = lab.prep, lab.vs_battle()
        capture = prep.capture if prep.open else None
        for jid in pads:
            state = glfw.get_gamepad_state(jid)
            if state is None:
                continue
            names = self.pressed(state)
            edges = names - self.previous.get(jid, set())
            self.previous[jid] = names
            side = sides.get(jid)
            if capture is not None and capture[1] == 'pad':
                for name in edges:
                    if name == 'START':
                        lab.commands.append(('prep_key', 'escape'))
                    elif name in PAD_BINDABLE:
                        lab.commands.append(('prep_key', 'pad_bind', name))
                continue
            if not battle or side is None:
                continue
            if lab.menu.open:
                for name, command in (('UP', ('menu_move', -1)), ('DOWN', ('menu_move', 1)), ('A', ('menu_select',)),
                                      ('B', ('menu',)), ('START', ('menu',))):
                    if name in edges:
                        lab.commands.append(command)
                continue
            if 'START' in edges:
                lab.commands.append(('menu',))
                continue
            for direction, name in (('left', 'LEFT'), ('right', 'RIGHT')):
                key = (jid, direction)
                if name in edges:
                    lab.commands.append(('vs', side, direction))
                    self.repeat[key] = now + REPEAT_DELAY
                elif name in names and now >= self.repeat.get(key, float('inf')):
                    lab.commands.append(('vs', side, direction))
                    self.repeat[key] = now + REPEAT_RATE
                elif name not in names:
                    self.repeat.pop(key, None)
            buttons = lab.versus_pad()['p1' if side == 0 else 'p2']
            for action, button in buttons.items():
                if button in edges:
                    lab.commands.append(('vs', side, action))
            x = state.axes[2]
            if abs(x) > STICK_DEAD:
                sticks[side] = (abs(x) - STICK_DEAD) / (1 - STICK_DEAD) * (1 if x > 0 else -1)
        for jid in list(self.previous):
            if jid not in pads:
                self.previous.pop(jid)
        lab.vs_camera.stick = sticks


class VersusCamera:
    """游戏线程：镜头仲裁与右摇杆移动（每帧 update 一次）。"""

    def __init__(self, lab):
        self.lab = lab
        self.stick = [0.0, 0.0]     # 窗口线程写入（整体替换）
        self.mouse = False          # P1 鼠标拖动进行中（lab_runtime touch_event 设定）
        self.owner = None
        self.moves = [0, 0]         # 检查用：各方右摇杆累计移动量

    def reset(self):
        self.owner, self.mouse = None, False

    def update(self):
        stick = self.stick
        active = (bool(stick[0]) or self.mouse, bool(stick[1]))
        if self.owner is not None and not active[self.owner]:
            self.owner = None
        if self.owner is None:
            self.owner = 0 if active[0] else 1 if active[1] else None
        if self.owner is None or not stick[self.owner]:
            return
        lab, p = self.lab, self.lab.p
        _, scene = lab.battle()
        operator = p.word(scene + 0x3c) if scene else 0
        screen = p.word(operator + 28) if operator else 0
        if not screen:
            return
        dx = round(stick[self.owner] * CAMERA_SPEED)
        if dx:
            p.call('_ZN12BattleScreen12movePositionEi', screen, dx & 0xffffffff)
            self.moves[self.owner] += dx

    def drag(self, dx):
        """宿主直接移动镜头（会话模式的鼠标拖动；方向与原生拖动相同：向右拖动看向左侧）。"""
        lab, p = self.lab, self.lab.p
        _, scene = lab.battle()
        operator = p.word(scene + 0x3c) if scene else 0
        screen = p.word(operator + 28) if operator else 0
        if screen and int(dx):
            p.call('_ZN12BattleScreen12movePositionEi', screen, (-int(dx)) & 0xffffffff)

    def mouse_allowed(self):
        return self.owner != 1
