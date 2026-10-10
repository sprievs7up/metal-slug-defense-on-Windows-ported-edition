"""正式版各启动入口共用的 LAB 输入、原生核心与存档隔离适配器。"""
from pathlib import Path
import io
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
try:
    # 先登记便携运行时 DLL 目录，再导入 ctypes 与窗口宿主。
    import portable_launcher
    import player
    import glfw
    import ctypes
except BaseException:
    # pythonw 无控制台：导入阶段的异常也写入错误记录，避免“双击无反应”。
    import traceback
    (ROOT / 'lab_launcher_error.log').write_text(traceback.format_exc(), encoding='utf-8')
    raise

PROFILE = 'lab_test_save'
# 含 LAB 钩子的核心由正式版配置统一加载；独立入口和验证保留显式指定核心接口。
LAB_CORE = ROOT / 'src' / 'build' / 'MSD_Core_LAB_r45_20261010.dll'
KEYS = {glfw.KEY_F7: ('prep',), glfw.KEY_F5: ('exit',), glfw.KEY_F8: ('toggle_full',),
        glfw.KEY_F4: ('toggle_enemy_ai',), glfw.KEY_F3: ('toggle_player_ai',),
        glfw.KEY_LEFT_BRACKET: ('enemy_ap',), glfw.KEY_RIGHT_BRACKET: ('enemy_slug',),
        glfw.KEY_BACKSLASH: ('enemy_special',)}
KEYS.update({key: ('enemy_unit', slot) for slot, key in enumerate(
    (glfw.KEY_Q, glfw.KEY_W, glfw.KEY_E, glfw.KEY_R, glfw.KEY_T,
     glfw.KEY_Y, glfw.KEY_U, glfw.KEY_I, glfw.KEY_O, glfw.KEY_P))})
BLOCKED_MODS = glfw.MOD_SHIFT | glfw.MOD_CONTROL | glfw.MOD_ALT | glfw.MOD_SUPER
# 常规联机（N6a）：普通关卡的战斗快捷键（AGENTS 第 5 节）→ 联机输入。
NETPLAY_KEYS = {glfw.KEY_SPACE: ('special',), glfw.KEY_GRAVE_ACCENT: ('ap',), glfw.KEY_MINUS: ('slug',)}
NETPLAY_KEYS.update({key: ('deploy', slot) for slot, key in enumerate(
    (glfw.KEY_1, glfw.KEY_2, glfw.KEY_3, glfw.KEY_4, glfw.KEY_5, glfw.KEY_6, glfw.KEY_7, glfw.KEY_8, glfw.KEY_9, glfw.KEY_0))})
NETPLAY_KEYS.update({key: ('deploy', slot) for slot, key in enumerate(
    (glfw.KEY_KP_1, glfw.KEY_KP_2, glfw.KEY_KP_3, glfw.KEY_KP_4, glfw.KEY_KP_5, glfw.KEY_KP_6, glfw.KEY_KP_7,
     glfw.KEY_KP_8, glfw.KEY_KP_9, glfw.KEY_KP_0))})
# 双人对战：始终交给原有流程的按键（菜单、全屏、截图、静音），其余按键只按双方键位处理。
VS_PASS_KEYS = (glfw.KEY_ESCAPE, glfw.KEY_F7, glfw.KEY_F9, glfw.KEY_F11, glfw.KEY_F12)
VS_BAR_TOP = 573          # 底栏上沿（1280×720 逻辑坐标，HANDOFF 设计文档 4.1b）
VS_DRAG_START = 8         # 鼠标移动超过该距离（逻辑像素）才视为镜头拖动


def safe_profile(path):
    profile = (ROOT / path).resolve()
    if not profile.is_relative_to(ROOT):
        raise ValueError('存档目录必须位于仓库内')
    if any(part.lower().startswith('play_save') for part in profile.relative_to(ROOT).parts):
        raise ValueError('拒绝使用 play_save* 目录，请使用独立存档副本')
    return profile


class VirtualFile(io.BytesIO):
    """LAB 隔离期间的存档写入目标：关闭时把内容记入 lab.virtual_files，不落盘。"""

    def __init__(self, lab, key, initial, append=False):
        super().__init__(initial)
        self.lab, self.key = lab, key
        if append:
            self.seek(0, io.SEEK_END)

    def close(self):
        if not self.closed:
            self.lab.virtual_files[self.key] = self.getvalue()
        super().close()


def install_core(path):
    """以指定 DLL 替代根目录配置的核心，ABI 检查与原 static_cpu.Uc 相同。"""
    import ctypes
    import probe
    import static_cpu

    class LabUc(static_cpu.Uc):
        def __init__(self, *args):
            self.ctx = static_cpu.Context()
            self.callbacks = {}
            self.library_path = path
            self.lib = ctypes.CDLL(str(path))
            self.lib.msd_context_size.restype = ctypes.c_uint32
            if self.lib.msd_context_size() != ctypes.sizeof(static_cpu.Context):
                raise RuntimeError('AOT context ABI mismatch')
            self.lib.msd_runtime_kind.restype = ctypes.c_uint32
            if self.lib.msd_runtime_kind() != 0x414f5431:
                raise RuntimeError('Unexpected AOT backend')
            self.lib.msd_run.argtypes = [ctypes.POINTER(static_cpu.Context), ctypes.c_uint32]
            self.lib.msd_run.restype = ctypes.c_uint32

    probe.Uc = LabUc


DRIVER_FACTORY = None           # 可选：probe → 会话驱动（drive() 推进并返回本帧是否有画面；finished 为真时撤除）


def install():
    probe_class = player.Probe
    player_class = player.Player
    if getattr(probe_class, 'lab_runtime_installed', False) and getattr(player_class, 'lab_runtime_installed', False):
        return

    class LabProbe(probe_class):
        lab_runtime_installed = True

        def initialize(self):
            super().initialize()
            from lab import Lab
            self.lab = Lab(self, ROOT)
            # 未经 LAB 拦截的原生触点入口（常规联机在实际显示的帧中送入，netplay_regular.RegularBattle.simulate）。
            self.native_touch = lambda action, x, y: probe_class.touch_event(self, action, x, y)
            enable = getattr(self.uc.lib, 'msd_enable_lab_hooks', None)
            if enable is None:
                self.lab.native_hooks = 0
                self.log('LAB_NATIVE_HOOKS_UNAVAILABLE', str(self.uc.library_path))
            else:
                enable()
                version = self.uc.lib.msd_lab_hooks_version
                version.restype = ctypes.c_uint32
                self.lab.native_hooks = version()
                self.log('LAB_NATIVE_HOOKS', self.lab.native_hooks, str(self.uc.library_path))
            from lab_menu_entry import LabMenuEntry
            self.menu_entry = LabMenuEntry(self, self.lab, ROOT)
            from lab_versus_page import VersusPage
            self.versus_page = VersusPage(self, self.lab, ROOT, probe_class.touch_event)
            from mod_page import ModPage
            self.mod_page = ModPage(self, self.lab, ROOT)
            from netplay_lobby import NetplayLobby
            self.netplay_lobby = NetplayLobby(self, self.lab, ROOT)
            self.versus_page.lobby = self.netplay_lobby

        def draw_text(self, a, idx):
            page = getattr(self, 'versus_page', None)
            if page is not None:
                page.rename_strings(a)              # 主菜单 Wi-Fi 对战按钮 → 对战
            lobby = getattr(self, 'netplay_lobby', None)
            if lobby is not None:
                lobby.rename_strings(a)             # 联机大厅（原生 Wi-Fi VERSUS 菜单）的按钮与战绩文字
            return super().draw_text(a, idx)

        def filecall(self, name, a):
            # 敌方红色绝招光圈：LAB 以替换文件名 aurR.obm 构造第二个 BattleEffectRenderer，
            # 此处返回由 aura.obm 调色板换色得到的内存数据（贴图结构与原图一致）。
            if name == 'fopen':
                requested = self.string(a[0])
                if requested.replace('\\', '/').rsplit('/', 1)[-1] == 'aurR.obm':
                    handle = self.alloc(16)
                    self.handles[handle] = io.BytesIO(self.lab.red_aura_bytes())
                    self.log('LAB_RED_AURA_OPEN', requested)
                    return handle
                lab = getattr(self, 'lab', None)
                if lab is not None and lab.sandbox:
                    handle = self.sandbox_open(lab, requested, self.string(a[1]))
                    if handle is not None:
                        return handle
            return super().filecall(name, a)

        def sandbox_open(self, lab, requested, mode):
            """LAB 存档隔离（T9）：存档目录内的写入改写到 lab.virtual_files；已写过的文件读回虚拟内容。"""
            # 只读且尚无虚拟文件，或读取 .obm/.msdf 素材时，结果必为 None；跳过路径解析
            # （原生每次资源读取都会先尝试本地数据目录，逐个解析约 0.6 ms，进入战斗时累计约 110 ms）。
            if not any(k in mode for k in 'wa+') and (not lab.virtual_files or requested.endswith(('.obm', '.msdf'))):
                return None
            path = self.path(requested)
            if not path.is_relative_to(self.guest_root):
                return None
            key = str(path)
            writing = any(k in mode for k in 'wa+')
            if writing:
                initial = b''
                if not mode.startswith('w'):
                    initial = lab.virtual_files.get(key, path.read_bytes() if path.is_file() else b'')
                stream = VirtualFile(lab, key, initial, append=mode.startswith('a'))
                lab.virtual_write_count += 1
                self.log('LAB_SANDBOX_WRITE', key, mode)
            elif key in lab.virtual_files:
                stream = io.BytesIO(lab.virtual_files[key])
            else:
                return None
            handle = self.alloc(16)
            self.handles[handle] = stream
            return handle

        def touch_event(self, action, x, y):
            mods = getattr(self, 'mod_page', None)
            if mods is not None and mods.touch(action, x, y):
                return
            lobby = getattr(self, 'netplay_lobby', None)
            if lobby is not None and lobby.touch(action, x, y):
                return
            lab = getattr(self, 'lab', None)
            if lab is not None and (lab.menu.touch(action, x, y) or lab.prep.touch(action, x, y)):
                return
            netplay = getattr(lab, 'netplay', None) if lab is not None else None
            if netplay is not None and lab.active and hasattr(netplay, 'queue_touch'):
                # 常规联机（N6a）：触点在下一个实际显示的帧中送入原生（底栏与点击单位的操作由核心捕获后转为联机输入）。
                netplay.queue_touch(action, x, y)
                return
            if lab is not None and lab.vs_battle() and not lab.menu.open and getattr(lab, 'netplay', None) is not None:
                # 会话模式（本地对战录制、联机）：鼠标拖动由宿主直接移动镜头，不送入原生触点（触点会进入模拟、也不会出现在回放中）。
                if action == 1:
                    self.vs_press = (x, y) if y < VS_BAR_TOP else None
                    self.vs_dragging = False
                    return
                press = getattr(self, 'vs_press', None)
                if press is None:
                    return
                if action == 5:
                    if not self.vs_dragging:
                        if abs(x - press[0]) + abs(y - press[1]) < VS_DRAG_START or not lab.vs_camera.mouse_allowed():
                            return
                        self.vs_dragging, self.vs_last = True, press[0]
                        lab.vs_camera.mouse = True
                    lab.vs_camera.drag(x - self.vs_last)
                    self.vs_last = x
                elif action == 3:
                    self.vs_press = None
                    if self.vs_dragging:
                        self.vs_dragging = False
                        lab.vs_camera.mouse = False
                return
            if lab is not None and lab.vs_battle() and not lab.menu.open:
                # 双人对战：鼠标只拖动镜头。按下先缓存，移动超过阈值后才把按下送入原生（成为战场拖动）；
                # 未移动的点击不送入原生（不点出兵栏、按钮与单位绝招）；底栏区域的按下一律忽略。
                if action == 1:
                    self.vs_press = (x, y) if y < VS_BAR_TOP else None
                    self.vs_dragging = False
                    return
                press = getattr(self, 'vs_press', None)
                if press is None:
                    return
                if action == 5 and not self.vs_dragging:            # 5 为拖动（player.py 逐帧送出最近位置）
                    if abs(x - press[0]) + abs(y - press[1]) < VS_DRAG_START:
                        return
                    if not lab.vs_camera.mouse_allowed():
                        return                                      # P2 右摇杆正在控制镜头
                    self.vs_dragging = True
                    lab.vs_camera.mouse = True
                    super().touch_event(1, *press)
                if action == 3:
                    self.vs_press = None
                    if not self.vs_dragging:
                        return
                    self.vs_dragging = False
                    lab.vs_camera.mouse = False
                super().touch_event(action, x, y)
                return
            page = getattr(self, 'versus_page', None)
            if page is not None and lab is not None and not lab.active and page.touch(action, x, y):
                return
            entry = getattr(self, 'menu_entry', None)
            if entry is not None and entry.touch(action, x, y):
                return
            super().touch_event(action, x, y)

        def back(self):
            mods = getattr(self, 'mod_page', None)
            if mods is not None and mods.back():
                return True
            lobby = getattr(self, 'netplay_lobby', None)
            if lobby is not None and lobby.back():
                return True
            lab = getattr(self, 'lab', None)
            if lab is not None and lab.back():
                return True
            return super().back()

        def close(self):
            lab = getattr(self, 'lab', None)
            if lab is not None and lab.sandbox:
                # 关闭窗口时停止事件已设置，原生调用会被取消；LAB 对战不保存，只还原内存存档映像。
                stopping = self.stop_event is not None and self.stop_event.is_set()
                lab.abort(native=not stopping)
            entry = getattr(self, 'menu_entry', None)
            if entry is not None:
                entry.close()
            page = getattr(self, 'versus_page', None)
            if page is not None:
                page.shutdown()
            mods = getattr(self, 'mod_page', None)
            if mods is not None:
                mods.close()
            lobby = getattr(self, 'netplay_lobby', None)
            if lobby is not None:
                lobby.shutdown()
            return super().close()

        def activate_unit_slot(self, slot):
            result = super().activate_unit_slot(slot)
            lab = getattr(self, 'lab', None)
            if lab is not None:
                lab.reveal_slot(False, slot)
            return result

        def step_frame(self):
            # 会话驱动（N5.5：回放播放器；N6：联机与本地对战会话）：窗口游戏循环的每一帧交给驱动推进，驱动内部再调用本函数
            # 执行实际的一帧（可能为零帧、一帧或多帧）。frame_drawn 为假时游戏循环不交换缓冲区，窗口保持上一帧画面。
            driver = getattr(self, 'session_driver', None)
            if driver is None and DRIVER_FACTORY is not None:
                driver = self.session_driver = DRIVER_FACTORY(self)
            if driver is not None and not getattr(self, 'driving', False):
                self.driving = True
                try:
                    self.frame_drawn = bool(driver.drive())
                finally:
                    self.driving = False
                if getattr(driver, 'finished', False):
                    self.session_driver = None
                return
            self.frame_drawn = True
            entry = getattr(self, 'menu_entry', None)
            if entry is not None:
                entry.prepare_frame()
            page = getattr(self, 'versus_page', None)
            if page is not None:
                page.prepare_frame()
            mods = getattr(self, 'mod_page', None)
            if mods is not None:
                mods.prepare_frame()
            lobby = getattr(self, 'netplay_lobby', None)
            if lobby is not None:
                lobby.prepare_frame()
            super().step_frame()
            lab = getattr(self, 'lab', None)
            if lab is None:
                return
            try:
                lab.update()
                if entry is not None:
                    entry.draw()
                if mods is not None:
                    mods.draw()
                if lobby is not None:
                    lobby.draw()
            except Exception as error:
                import traceback
                self.log('LAB_UPDATE_ERROR', type(error).__name__, str(error), traceback.format_exc())
                try:
                    lab.abort()
                except Exception:
                    pass
                lab.feedback(f'内部错误：{type(error).__name__}，详见 {Path(self.logfile.name).name}', False)

    class LabPlayer(player_class):
        lab_runtime_installed = True

        def poll_input(self):
            """窗口线程：准备界面打开或双人对战进行中时轮询手柄（GLFW 手柄函数只在主线程调用）。"""
            if not getattr(self, 'char_installed', False) and getattr(self, 'window', None):
                # 文字输入（联机大厅的名称与 IP，N6a）：GLFW 字符回调在窗口线程送出已确认的字符（含输入法的结果）。
                glfw.set_char_callback(self.window, self.text_input)
                self.char_installed = True
            lab = getattr(self.probe, 'lab', None) if self.probe else None
            if lab is None or not self.ready:
                return
            if not (lab.prep.open or lab.vs_battle()):
                lab.vs_camera.stick = [0.0, 0.0]
                return
            if getattr(self, 'pad_poller', None) is None:
                from lab_versus_input import PadPoller
                self.pad_poller = PadPoller()
            try:
                self.pad_poller.poll(lab)
            except Exception as error:
                if not getattr(self, 'pad_error', None):
                    self.pad_error = f'{type(error).__name__}: {error}'
                    self.probe.log('VS_PAD_ERROR', self.pad_error)

        def text_input(self, window, codepoint):
            lobby = getattr(self.probe, 'netplay_lobby', None) if self.probe else None
            if lobby is not None and self.ready and lobby.wants_text():
                lobby.commands.append(('text', chr(codepoint)))

        def key(self, window, key, scan, action, mods):
            lobby = getattr(self.probe, 'netplay_lobby', None) if self.probe else None
            if lobby is not None and self.ready and lobby.wants_keys() and action in (glfw.PRESS, glfw.REPEAT):
                # 联机大厅窗口（名称、IP、房间等）：Enter 确定、Esc 取消、Backspace 删除；其他按键不送入原生菜单（F 键除外）。
                name = {glfw.KEY_ENTER: 'enter', glfw.KEY_KP_ENTER: 'enter', glfw.KEY_ESCAPE: 'escape',
                        glfw.KEY_BACKSPACE: 'backspace', glfw.KEY_TAB: 'tab'}.get(key)
                if name and (action == glfw.PRESS or name == 'backspace'):
                    lobby.commands.append(('key', name))
                if key not in (glfw.KEY_F11, glfw.KEY_F12, glfw.KEY_F9):
                    return
            lab = getattr(self.probe, 'lab', None) if self.probe else None
            if (lab is not None and self.ready and action == glfw.PRESS and lab.prep.open and key != glfw.KEY_ESCAPE
                    and lab.prep.capture is not None and lab.prep.capture[1] == 'key'):
                # 按键设定：等待指定时下一次按键（含修饰键与保留键，由游戏线程校验）交给准备界面。
                lab.commands.append(('prep_key', 'bind', key))
                return
            netplay = getattr(lab, 'netplay', None) if lab is not None else None
            if (lab is not None and self.ready and lab.active and hasattr(netplay, 'queue_touch') and key == glfw.KEY_ESCAPE
                    and action == glfw.PRESS and lobby is not None):
                lobby.commands.append(('battle_menu',))     # 常规联机：Esc 打开不暂停的菜单（netplay_lobby.NetMenu）
                return
            if lab is not None and self.ready and lab.active and hasattr(netplay, 'queue_touch') and key not in VS_PASS_KEYS:
                # 常规联机（N6a）：与普通关卡相同的战斗快捷键转为联机输入（1–0 出兵、空格全体绝招、` 据点升级、- 弹头车）。
                if action == glfw.PRESS and not mods & BLOCKED_MODS:
                    command = NETPLAY_KEYS.get(key)
                    if command:
                        lab.commands.append(('np',) + command)
                return
            if lab is not None and self.ready and lab.vs_battle() and not lab.menu.open and key not in VS_PASS_KEYS:
                # 双人对战：只接受双方键位（修饰键状态为全局，不据此拒绝）；左右选择允许按住连发。其余游戏按键不送入战斗。
                if action == glfw.PRESS or (action == glfw.REPEAT and key in self.vs_repeat_keys(lab)):
                    for command in self.vs_commands(lab).get(key, ()):
                        if action == glfw.PRESS or command[2] in ('left', 'right'):
                            lab.commands.append(command)
                return
            if lab is not None and self.ready and action == glfw.PRESS and not mods & BLOCKED_MODS:
                # 战斗中菜单（T6）：Esc 打开/关闭；打开期间 ↑/↓/Enter 操作菜单，其余游戏按键不送入战斗。
                if key == glfw.KEY_ESCAPE and lab.active:
                    lab.commands.append(('menu',))
                    return
                if lab.prep.open:
                    # 准备界面（T8）：Esc 返回/关闭，F7 关闭；其余游戏按键不送入菜单场景。
                    if key == glfw.KEY_ESCAPE:
                        # 按键回调在窗口线程：只入队，由游戏线程执行（原生调用不得跨线程）。
                        lab.commands.append(('prep_key', 'escape'))
                    elif key == glfw.KEY_F7:
                        lab.commands.append(('prep',))
                    if key not in (glfw.KEY_F11, glfw.KEY_F12, glfw.KEY_F9):
                        return
                if lab.menu.open:
                    menu_keys = {glfw.KEY_UP: ('menu_move', -1), glfw.KEY_DOWN: ('menu_move', 1),
                                 glfw.KEY_ENTER: ('menu_select',), glfw.KEY_KP_ENTER: ('menu_select',)}
                    if key in menu_keys:
                        lab.commands.append(menu_keys[key])
                    if key not in (glfw.KEY_F11, glfw.KEY_F12, glfw.KEY_F9):
                        return
            command = KEYS.get(key)
            if command and action == glfw.PRESS and not mods & BLOCKED_MODS:
                lab = getattr(self.probe, 'lab', None) if self.probe else None
                if lab is not None and self.ready:
                    lab.commands.append(command)
                return
            super().key(window, key, scan, action, mods)

        def vs_commands(self, lab):
            """GLFW 键码 → 指令列表；同一键可同时属于两名玩家（用户确认允许），各自触发。"""
            keys = lab.versus_keys()
            cache = getattr(self, 'vs_cache', None)
            if cache is None or cache[0] != keys:
                table = {}
                for side, name in ((0, 'p1'), (1, 'p2')):
                    for action, key_name in keys[name].items():
                        code = getattr(glfw, 'KEY_' + str(key_name).upper(), None)
                        if code is not None:
                            table.setdefault(code, []).append(('vs', side, action))
                cache = self.vs_cache = (keys, table)
            return cache[1]

        def vs_repeat_keys(self, lab):
            return {code for code, commands in self.vs_commands(lab).items()
                    if any(command[2] in ('left', 'right') for command in commands)}

    if not getattr(probe_class, 'lab_runtime_installed', False):
        player.Probe = LabProbe
    if not getattr(player_class, 'lab_runtime_installed', False):
        player.Player = LabPlayer


def install_platform():
    import local_platform
    original = local_platform.handle_java_call
    if getattr(original, 'lab_runtime_installed', False):
        return

    def handle_java_call(p, method, arg):
        lab = getattr(p, 'lab', None)
        if lab is not None and lab.active and method[1] in (
                'sendDataTCP', 'sendDataUDP', 'startQuickGame', 'cancelRoom', 'setRoomVariant'):
            if not hasattr(p, 'lab_network_counts'):
                p.lab_network_counts = {}
            p.lab_network_counts[method[1]] = p.lab_network_counts.get(method[1], 0) + 1
            if p.lab_network_counts[method[1]] == 1:
                p.log('LAB_NETWORK_CALL_OMITTED', method[1])
            return True, 0
        return original(p, method, arg)

    handle_java_call.lab_runtime_installed = True
    local_platform.handle_java_call = handle_java_call


