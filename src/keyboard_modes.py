"""键盘操作模式（2026-11-10 用户要求）：经典（原 Windows 版的默认键位与出兵选择框）与 S1XLV（本移植版键位）。

设定
- %LOCALAPPDATA%\\MSD_WINDOWS_S1XLV\\keyboard.json：{"schema": 1, "mode": "classic" | "s1xlv"}，环境变量 MSD_KEYBOARD_CONFIG
  可改路径；缺省 S1XLV。各存档入口共用；在主菜单 OPTION 的 KEYBOARD 页切换（keyboard_options.py），立即生效。

经典模式：原 Windows 版 msdf-steam.exe 的默认键位与战斗中的处理（0x50b230、0x50aaf0、0x50b570 与出兵格循环；研究记录
research/metal_slug_defense/content_work/steam_msd_compare_20261014 第 7 节，本次核对见 verification/keyboard_mode_20261110/summary.md）
- Z / C：出兵格选择框左 / 右移。按下即移动一格，按住时每 5 帧再移动一格；选择框不在出兵栏可见范围时先回到可见范围的近端；
  移出可见范围时出兵栏滚动一格；两端不循环。
- V：出动所选单位（可出动而单位已满时播放原生提示音 28）。W：AP 升级。鼠标右键：弹头车。
- A / D：镜头向左 / 向右卷动，按住时每帧 12；先按下的方向保持到松开。
- E：暂停（同 Esc）。R：倍速（同屏幕按钮：速度 1 ↔ 2，原生音效 23 / 24）。Backspace：返回（同 Esc）。
- 战斗未进行、暂停或 AUTO 开启时，选择、出动、AP 升级、弹头车与卷动不受理（原版 0x50b230 开头的检查）。
- 没有按编号直接出兵与全体绝招的键；单位绝招以鼠标点击单位发动。
- 选择框：原版图像 unit_icon_select.obm（64×64，其中左上 56×56 为绿色框），与格子底板、头像画在同一点、2 倍缩放，画在头像之后，
  透明度按原版的 14 级表循环（每级 2 帧）。由核心钩子第 31 版在原生出兵格循环中绘制（头部 +0xa00 写 'CLAS'，src/lab_hooks.cpp）。
  原版选择框转换项的锚点在运行时表中，未取得；本实现取与 50×50 格子底板同心（四周各伸出 3 像素）。

S1XLV 模式：1–0（含小键盘）出兵、空格 全体绝招、` AP 升级、- 弹头车、= 依次尝试全部槽位（player.py 原有处理）。
F7、F9、F11、F12、Alt+Enter、Esc 与模式无关。本地双人对战使用自己的双方键位（lab_versus_input），不受模式影响。
常规联机中，经典模式的出动、AP 升级与弹头车同样转为联机输入；选择框与镜头为本地界面；倍速不受理。
"""
import json
import os
import struct
from pathlib import Path

MODES = ('classic', 's1xlv')
DEFAULT_MODE = 's1xlv'
VS_CUR = 0x1ffeb000 + 0xa00            # lab_hooks.cpp 的光标头部
CLASSIC_MAGIC = 0x53414c43             # 'CLAS'
FRAME_FILE = 'custom_content/unit_icon_select.obm'
FRAME_SIZE = 56                        # 图像 64×64 中选择框所占的左上 56×56
TILE_ENTRY = 53                        # 出兵格底板（operator+200 转换表，50×50）
ALPHA_STEPS = (0xff, 0xf9, 0xf2, 0xe5, 0xd8, 0xcc, 0xbf, 0xb2, 0x99, 0x7f, 0x66, 0x4c, 0x33, 0x19)   # msdf-steam.exe 0x78706c
REPEAT_FRAMES = 5                      # 选择键按住时的连发间隔（0x50aaf0 的第二个参数）
SCROLL_STEP = 12                       # 卷动键按住时每帧的镜头移动量
SE_UNIT_LIMIT, SE_SPEED_ON, SE_SPEED_OFF = 0x1c, 0x17, 0x18
# 动作名 → GLFW 键名（KEY_ 之后部分）；弹头车（slug）为鼠标右键。
CLASSIC_KEYS = {'select_left': 'Z', 'select_right': 'C', 'sortie': 'V', 'ap': 'W', 'pause': 'E', 'speed': 'R',
                'scroll_left': 'A', 'scroll_right': 'D', 'back': 'BACKSPACE'}
PB = '_ZN26BattleControllerPlayerBase'


def config_path():
    value = os.environ.get('MSD_KEYBOARD_CONFIG')
    if value:
        return Path(value)
    base = os.environ.get('LOCALAPPDATA')
    return Path(base) / 'MSD_WINDOWS_S1XLV' / 'keyboard.json' if base else None


def load_mode(path=None):
    path = config_path() if path is None else path
    try:
        mode = json.loads(path.read_text(encoding='utf-8')).get('mode')
    except (AttributeError, OSError, ValueError):
        return DEFAULT_MODE
    return mode if mode in MODES else DEFAULT_MODE


def save_mode(mode, path=None):
    """先写临时文件再替换（同 mod_loader.write_enabled）。"""
    if mode not in MODES:
        raise ValueError(mode)
    path = config_path() if path is None else path
    if path is None:
        raise RuntimeError('LOCALAPPDATA is not set')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps({'schema': 1, 'mode': mode}, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def classic_key_codes(glfw):
    """GLFW 键码 → 经典模式的动作名。"""
    return {getattr(glfw, 'KEY_' + name): action for action, name in CLASSIC_KEYS.items()}


def i32(value):
    return value - (1 << 32) if value & 0x80000000 else value


class KeyboardModes:
    def __init__(self, p, root):
        self.p, self.root = p, Path(root)
        self.mode = load_mode()
        self.cursor = 0
        self.counter = 0                        # 选择框闪烁计数（原版 0x9371f0）
        self.repeat_action, self.repeat_left = None, 0      # 连发：上一次受理的选择动作与剩余帧数（原版 +0x98c / +0x988）
        self.scroll_latch = None                # 卷动：保持中的方向（原版 0x92509c）
        self.frame_image = self.frame_conv = None
        self.frame_error = None
        self.header_on = False
        self.battle_main = 0
        self.stats = {'select': 0, 'sortie': 0, 'scroll': 0}
        p.log('KEYBOARD_MODE', self.mode)

    def set_mode(self, mode):
        if mode not in MODES or mode == self.mode:
            return
        self.mode = mode
        self.repeat_action = self.scroll_latch = None
        try:
            save_mode(mode)
        except (OSError, RuntimeError) as error:
            self.p.log('KEYBOARD_MODE_WRITE_ERROR', type(error).__name__, str(error))
        self.p.log('KEYBOARD_MODE', mode)

    # ---------- 上下文 ----------
    def lab(self):
        return getattr(self.p, 'lab', None)

    def versus(self):
        lab = self.lab()
        return bool(lab is not None and lab.vs_battle())

    def netplay(self):
        """常规联机战斗中（操作须转为联机输入）。"""
        lab = self.lab()
        return bool(lab is not None and lab.active and hasattr(getattr(lab, 'netplay', None), 'queue_touch'))

    def battle(self):
        """战斗场景中的 (BattleMain, BattlePlayerOperator)；不在战斗场景或对象未建立时为 None。"""
        p = self.p
        app = p.app_instance()
        if not app or p.word(app + 0x22bc) != 100:
            return None
        main = p.word(app + 0xc220)
        if not main or not p.word(main + 8):
            return None
        scene = p.call('_ZN10BattleMain12getMainSceneEv', main)
        operator = p.word(scene + 0x3c) if scene else 0
        if not 0x10000000 <= operator < 0x1ffff000 or p.word(operator) != p.symbols['_ZTV20BattlePlayerOperator'] + 8:
            return None
        return main, operator

    def playing(self):
        """经典模式的战斗操作可受理时返回 (控制器, operator)：战斗进行中、未暂停、AUTO 未开启；LAB 战斗中菜单未打开。"""
        if self.versus():
            return None
        from battle_controls import context
        p = self.p
        controller, blocked, scene = context(p)
        if controller is None:
            return None
        lab = self.lab()
        if lab is not None and lab.active and lab.menu.open:
            return None
        if p.call(p.word(p.word(controller) + 0xf8), controller):        # AUTO（原生 getUnitIndex 同以此停用底栏）
            return None
        found = self.battle()
        return (controller, found[1]) if found else None

    # ---------- 游戏线程：每个显示帧的输入 ----------
    def frame(self, held, pressed):
        """held：当前按住的动作名集合；pressed：自上一帧以来新按下的动作名（按顺序）。"""
        if self.mode != 'classic':
            self.repeat_action = self.scroll_latch = None
            return
        for action in pressed:
            if action == 'pause':
                self.pause()
            elif action == 'back':
                self.back()
            elif action == 'speed':
                self.speed()
            elif action == 'sortie':
                self.sortie()
            elif action == 'ap':
                self.simple('upgrade_ap', 'ap', 'W')
            elif action == 'slug':
                self.simple('slug_attack', 'slug', 'MOUSE R')
        self.poll_select(held, pressed)
        self.poll_scroll(held)

    def poll_select(self, held, pressed):
        """原版 0x50aaf0：新按下立即受理并把间隔计数设为 5；同一动作按住时每帧减 1，减到 0 再受理。左优先于右。"""
        for action, step in (('select_left', -1), ('select_right', 1)):
            fresh = action in pressed
            if not fresh and action not in held:
                continue
            if not fresh and self.repeat_action == action:
                self.repeat_left -= 1
                if self.repeat_left > 0:
                    continue
            self.repeat_action, self.repeat_left = action, REPEAT_FRAMES
            self.select(step)
            return
        if self.repeat_action is not None and self.repeat_action not in held:
            self.repeat_action = None

    def poll_scroll(self, held):
        """原版：未保持方向时依次检查左、右卷动键；保持中的方向在其按键松开后解除（下一帧起可换向）。"""
        if self.scroll_latch is not None and self.scroll_latch not in held:
            self.scroll_latch = None
            return
        if self.scroll_latch is None:
            self.scroll_latch = next((a for a in ('scroll_left', 'scroll_right') if a in held), None)
        if self.scroll_latch is None:
            return
        ctx = self.playing()
        if not ctx:
            return
        p = self.p
        screen = p.word(ctx[1] + 28)
        if screen:
            step = -SCROLL_STEP if self.scroll_latch == 'scroll_left' else SCROLL_STEP
            p.call('_ZN12BattleScreen12movePositionEi', screen, step & 0xffffffff)
            self.stats['scroll'] += 1

    # ---------- 动作 ----------
    def slots(self, controller):
        return max(1, min(10, self.p.word(controller + 0x390)))

    def bar(self, operator, controller):
        """出兵栏：(滚动地址, 格距, 最大滚动, 可见格数)；滚动动画或拖动进行中、格距无效时为 None。分栏底栏每侧 3 格（lab_hooks）。"""
        p = self.p
        pitch = round(struct.unpack('<f', p.read(operator + 108, 4))[0])
        if pitch <= 0 or p.word(operator + 0x60):
            return None
        slots = self.slots(controller)
        lab = self.lab()
        if lab is not None and lab.active and lab.native_hooks >= 3 and lab.netplay_mode != 'regular' and not lab.cpu_battle():
            return operator + 100, pitch, max(0, slots - 3) * pitch, min(3, slots)
        limit = max(0, i32(p.word(operator + 0x68)))
        return operator + 100, pitch, limit, max(1, slots - round(limit / pitch))

    def select(self, step):
        ctx = self.playing()
        if not ctx:
            return
        controller, operator = ctx
        p = self.p
        last_slot = self.slots(controller) - 1
        bar = self.bar(operator, controller)
        if bar is None:
            self.cursor = max(0, min(last_slot, self.cursor + step))
            return
        address, pitch, limit, visible = bar
        scroll = i32(p.word(address))
        first = scroll // pitch
        last = first + visible - 1
        if self.cursor < first:
            self.cursor = first
        elif self.cursor > last:
            self.cursor = last
        else:
            self.cursor = max(0, min(last_slot, self.cursor + step))
            if self.cursor < first:
                scroll -= pitch
            elif self.cursor > last:
                scroll += pitch
        self.cursor = max(0, min(last_slot, self.cursor))
        p.put(address, max(0, min(limit, scroll)))
        self.stats['select'] += 1

    def sortie(self):
        ctx = self.playing()
        if not ctx:
            return
        controller, operator = ctx
        p = self.p
        slot = self.cursor
        self.stats['sortie'] += 1
        if self.netplay():
            self.lab().commands.append(('np', 'deploy', slot))
            return
        if (p.call(PB + '12isUnitCreateEi', controller, slot)
                and p.call('_ZNK16BattleController15isUnitCountOverEv', controller)):
            p.call('_ZN17FrameworkInstance6playSEENS_9SoundTypeE7SoundIDi', 0, SE_UNIT_LIMIT, 0)
        p.activate_unit_slot(slot, 'V')

    def simple(self, action, net_action, key):
        if not self.playing():
            return
        if self.netplay():
            self.lab().commands.append(('np', net_action))
            return
        self.p.battle_key_action(action, key)

    def pause(self):
        """暂停键只在战斗与暂停画面受理（原版动作 PAUSE）；其余同 Esc。"""
        p = self.p
        app = p.app_instance()
        if app and p.word(app + 0x22bc) in (100, 113):
            self.back()

    def back(self):
        p = self.p
        if self.netplay():
            lobby = getattr(p, 'netplay_lobby', None)
            if lobby is not None:
                lobby.commands.append(('battle_menu',))      # 常规联机：与 Esc 相同，打开不暂停的菜单
            return
        p.log('WINDOW_BACK_REQUEST', p.frame)
        p.back()

    def speed(self):
        """倍速：与屏幕按钮相同（onGameScreenTouchEnded 项 0x67）。按钮只在 operator+8 为 1 的战斗中存在；联机中不受理。"""
        ctx = self.playing()
        if not ctx or self.netplay():
            return
        p = self.p
        if p.word(ctx[1] + 8) != 1:
            return
        master = p.call('_ZN16BattleGameMaster11getInstanceEv')
        fast = struct.unpack('<f', p.read(master + 0x18, 4))[0] != 1.0
        p.call('_ZN17FrameworkInstance6playSEENS_9SoundTypeE7SoundIDi', 0, SE_SPEED_OFF if fast else SE_SPEED_ON, 0)
        p.write(master + 0x18, struct.pack('<f', 1.0 if fast else 2.0))
        p.log('KEY_CLASSIC_SPEED', 1 if fast else 2)

    # ---------- 选择框 ----------
    def build_frame(self, operator):
        from PIL import Image
        from lab_versus import create_native_image
        p = self.p
        raw = (self.root / FRAME_FILE).read_bytes()
        width, height = struct.unpack_from('<HH', raw, 4)
        if raw[:2] != b'OI' or len(raw) != 8 + width * height * 4 or min(width, height) < FRAME_SIZE:
            raise ValueError('unit_icon_select.obm 格式与预期不符')
        image = Image.frombytes('RGBA', (width, height), raw[8:])
        tile = struct.unpack('<8h', p.read(p.word(operator + 200) + TILE_ENTRY * 16, 16))
        margin = (FRAME_SIZE - tile[2]) // 2, (FRAME_SIZE - tile[3]) // 2
        self.frame_image = create_native_image(p, image)
        # 转换项：图像矩形、锚点（与底板同心：锚点各加伸出量）、其余沿用底板。
        self.frame_conv = (0, 0, FRAME_SIZE, FRAME_SIZE, tile[4] + margin[0], tile[5] + margin[1], tile[6], 0)
        p.log('KEYBOARD_FRAME_BUILT', tile, self.frame_conv)

    def update(self):
        """每帧（原生步进之后）：经典模式的战斗中写入选择框头部，其余情形清除本模块写入的头部。"""
        p = self.p
        found = self.battle() if self.mode == 'classic' and not self.versus() else None
        operator = found[1] if found else 0
        if not operator or not p.word(operator + 200) or not p.word(operator + 188) or self.frame_error:
            if self.header_on:
                if p.word(VS_CUR) == CLASSIC_MAGIC:
                    p.put(VS_CUR, 0)
                self.header_on = False
            return
        if found[0] != self.battle_main:
            self.battle_main, self.cursor, self.counter = found[0], 0, 0       # 新的一场：选择框回到第 1 格
        if self.frame_image is None:
            try:
                self.build_frame(operator)
            except Exception as error:
                self.frame_error = f'{type(error).__name__}: {error}'
                p.log('KEYBOARD_FRAME_ERROR', self.frame_error)
                return
        # 闪烁：计数每帧加 1，序号为计数的一半；表末后回到开头（原版 0x50b230 开头）。
        self.counter += 1
        if self.counter // 2 >= len(ALPHA_STEPS):
            self.counter = 0
        p.put(VS_CUR + 4, self.cursor)
        p.put(VS_CUR + 8, ALPHA_STEPS[self.counter // 2])
        p.put(VS_CUR + 0x10, self.frame_image)
        p.write(VS_CUR + 0x30, struct.pack('<8h', *self.frame_conv))
        p.put(VS_CUR + 0xc0, operator)
        p.put(VS_CUR, CLASSIC_MAGIC)
        self.header_on = True
