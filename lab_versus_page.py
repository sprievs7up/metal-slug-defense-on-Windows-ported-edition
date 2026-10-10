"""主菜单“對戰”入口与 VERSUS 子页面（钩子版本 16；第四张卡 VS CPU 需第 23 版）。

- 主菜单第三个按钮的文字由宿主光栅化（probe.draw_text）。各语言的 Wi-Fi 对战按钮文字（libAppMain.so 字符串表中的
  独立字符串）整串替换为“对战”，Wi-Fi 模式因 Google Play 登录判断不可用。
- 点击该按钮时保留原生按压白光，由宿主调用原生布局切换函数进入 SHOP 子页面（scene28/state4），底栏 SHOP 不接收按压触点。
  页面打开期间，src/lab_hooks.cpp 的 drawConv 替换表（头部 +0xb40，'VSPG'）把 SHOP 标题字换为原生 VERSUS 整词，
  三张卡的插画与标签图块换为本地对战 / 局域网对战 / 远程对战，并跳过底栏 SHOP 的 LOCK 叠层；位置、缩放与入场动画
  沿用原生调用。原生 BACK 返回 MENU 时页面关闭；在页面中点击底栏 SHOP 时解除原生“当前页”标记，由原生切换动画进入商店（场景离开 28 时页面关闭）。
- 卡片点击由宿主拦截：本地对战以双人模式打开 LAB 准备界面；局域网（N6a）与远程（N6b：按地址与房间码直连）经原生闸门进入
  同一联机大厅（netplay_lobby，原版 Wi-Fi VERSUS 菜单改造）。离开大厅回到主菜单时重新显示本页（follow_lobby_return）。
卡片图块为 98×123（与原生卡片插画加标签的转换项相同）：上 98×102 为插画，下方为 12 行原生标题字体的标签
（artwork/title_font_20261008/titles/*_12.png）。存在 custom_content/versus_card_{local,lan,online}.png（98×102）时采用用户插画，
否则使用占位插画（原生叛军普通兵头像相对）。三张卡的 VS 字样均由程序以原始像素尺寸固定叠加，用户插画仅包含人物图标。
用户人物插画以原尺寸统一向下绘制 16 px，避让固定 VS，PNG 文件内的像素与坐标保持。
触点（2026-10-11 误入修正，docs/lab/vs_cpu_plan_2026-10-11.md 第 10 节）：原生卡片任务的点击区域为卡框四周各外扩 10 个原生单位
（任务 +0xf4..+0x100：偏移 -10、244×308），卡片命中范围与之相同。本页显示期间，内容区（y 112–572）的按下全部由宿主处理：
命中已就绪的卡片时照常转送原生（按下白光），卡片未就绪或空白处整次吞掉、不送入原生；顶栏与底栏照常交给原生。
此前宿主只拦截卡框范围，卡框外沿的点击交给原生后按商店卡片处理，进入原生商店分页。
四张卡（C1，docs/lab/vs_cpu_plan_2026-10-11.md 第 2、10 节）：显示顺序 VS CPU、LOCAL、LAN、ONLINE，尺寸与间距沿用原生（卡距 284），
整组居中，原生横坐标 -58 / 226 / 510 / 794。三张原生卡片任务的横坐标（+0x84）在页面打开的同一调用中写入、每帧核对，
页面关闭时在仍属场景 28 的任务上恢复 86 / 370 / 654（原生商店页共用这三个任务）。第四张卡按主菜单初始化表中槽 17 的表项
以 createMenuTask 建立原生任务（入场淡入、按下白光、离场淡出均为原生），复制 LOCAL 卡的点击区域字段；函数每帧对齐 LOCAL 卡，
透明度由核心第 23 版钩子在绘制时取 LOCAL 卡当前值；每帧按任务槽位核对仍有效（主菜单在场景 28 内重建任务时槽位被清空）。
第四张卡与 LOCAL 共用转换项，替换表按绘制 x 区分（钩子第 21 版）。
"""
from pathlib import Path
import struct

VS_PAGE = 0xb40
VS_PAGE_MAGIC = 0x47505356
# 原生只读数据中的转换项（verification/lab_versus_20261008/driver_menu_log.py 记录，shop 页）
TITLE_CONV = 0x108fdd58                     # menu.obm 的 SHOP 标题字（64×18，锚点 0,9）
CARD_CONVS = (0x10304fe2, 0x10304ff2, 0x10305002)   # ITEM、MSP、UNIT 的插画加标签（98×123，锚点 -7,-7）
LOCK_CONV = 0x1031cf70                      # 底栏 SHOP 的 LOCK 叠层
CARDS = ('local', 'lan', 'online')          # 三张原生卡片任务（CARD_TASKS）对应的模式
CARD_NATIVE_X = (86, 370, 654)              # 卡框的原生参考坐标 x（y 160），尺寸 112×144，绘制 2 倍（原生商店页）
ORDER = ('cpu', 'local', 'lan', 'online')    # VERSUS 页显示顺序
ORDER_X = (-58, 226, 510, 794)              # VERSUS 页的原生横坐标：卡距 284 不变，四张整组居中
CARD_Y = 160
CARD_HIT = (-10, -10, 244, 308)             # 原生点击区域（任务 +0xf4/+0xf8 偏移、+0xfc/+0x100 尺寸，原生单位）
CONTENT_TOP, CONTENT_BOTTOM = 112, 572      # 顶栏与底栏之间的内容区（1280×720 逻辑坐标）
WIFI_BUTTON = (708, 410, 424, 74)           # 1280×720 逻辑坐标：主菜单第三个按钮
SHOP_BUTTON = (532, 650)                    # 底栏 SHOP
SHOP_TASK = 0x36e0                          # app 偏移：底栏 SHOP 按钮任务
WIFI_TASK = 0x3384                          # 主菜单第三项（原生 panel index 9）
CARD_TASKS = (0x33a4, 0x33a8, 0x33ac)       # 三张原生卡片任务（菜单任务槽 17–19）
MENU_TASKS = 0x3360                         # app 偏移：菜单任务槽数组
CARD_SLOT = 17                              # 第四张卡复制其表项的槽（LOCAL 所用卡片）
MENU_TABLE = (0x1020453c, 0x102041f0, 336, 26)   # SC_MainMenuInit 传给 createMenuTask 的表：[字面量] + 基址 + 偏移，26 项、每项 0x38 字节
EXTRA_SLOTS = range(20, 200)                # 第四张卡可用的空槽（表中未用、当前为空）
CHANGE = '_ZN13CTaskSystem2D6ChangeEPFiP17GENERAL_TASK_BASEES1_'
PANEL_FUNCS = ('GT_MenuGenrePanel', 'GT_MenuGenrePanelIn', 'GT_MenuGenrePanelOut')
WIFI_LABELS = {'Wi-Fi對戰': '對戰', 'Wi-Fi対戦': '対戦', 'Wi-Fi 대전': '대전', 'Wi-Fi VS': 'VERSUS',
               'Wi-Fi V/S': 'VERSUS', 'Wi-Fi ВЕР': 'ВЕРСУС'}


def card_rect(index):
    """VERSUS 页第 index 张卡（ORDER）在 1280×720 逻辑画布上的命中矩形，与原生点击区域相同（原生坐标 → L=(D+88.9)×1.125）。"""
    x = (ORDER_X[index] + CARD_HIT[0] + 88.9) * 1.125
    return (x, (CARD_Y + CARD_HIT[1]) * 1.125, CARD_HIT[2] * 1.125, CARD_HIT[3] * 1.125)


def as_float(value):
    return struct.unpack('<I', struct.pack('<f', float(value)))[0]


def inside(rect, x, y):
    return rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]


class VersusPage:
    def __init__(self, probe, lab, root, native_touch):
        self.p, self.lab, self.root = probe, lab, Path(root)
        self.native_touch = native_touch        # 未经 LAB 拦截的原生触点入口
        self.state = 'closed'                   # closed / opening / open
        self.left_menu = False
        self.unlocked = False                   # 已清除底栏 SHOP 的当前页标记
        self.leaving = 0                        # 离开 VERSUS 页后的帧数
        self.pressed = None
        self.press_cancelled = False
        self.images = {}                        # 语言 → 已建立的原生图像
        self.error = None
        self.lobby = None                       # 联机大厅（netplay_lobby.NetplayLobby，lab_runtime 建立）
        self.lobby_return = None                # 离开联机大厅回到主菜单时重开本页：None / 'lobby' / 'armed'
        self.swallow = False                    # 本次触点由宿主吞掉（不送入原生）
        self.extra_task = 0                     # 第四张卡（VS CPU）的原生任务
        self.extra_slot = None
        self.extra_entry = 0

    # ---------- 文字 ----------
    def rename_strings(self, a):
        """在 probe.draw_text 光栅化前替换 Wi-Fi 对战按钮文字（整串相等时）。"""
        try:
            p = self.p
            cursor = a[3]
            cursor = (cursor + 4 + 7) & ~7
            cursor += 8
            refs = [p.word(cursor + 4 * i) for i in range(6)]
            for item in p.objects[refs[5]]['items']:
                text = p.objects.get(item)
                if isinstance(text, str) and text in WIFI_LABELS:
                    p.objects[item] = WIFI_LABELS[text]
        except Exception as error:
            p.log('VERSUS_RENAME_ERROR', type(error).__name__, str(error))

    # ---------- 图块 ----------
    def card_image(self, name, lang):
        from PIL import Image
        art_path = self.root / 'custom_content' / f'versus_card_{name}.png'
        art_y = 0
        if art_path.is_file():
            art = Image.open(art_path).convert('RGBA')
            if art.size != (98, 102):
                raise ValueError(f'{art_path.name} 须为 98×102')
            art_y = 16                         # 用户人物图统一下移，原图像素与尺寸保持。
        else:
            art = self.placeholder_art()
        card = Image.new('RGBA', (98, 123), (0, 0, 0, 0))
        card.alpha_composite(art, (0, art_y))
        vs = self.versus_mark()
        # 内容距卡框上沿 7 px，VS 顶端透明 2 px；可见像素与底部标签均距相应卡框外沿 14 px。
        card.alpha_composite(vs, ((98 - vs.width) // 2, 5))
        label = Image.open(self.root / f'artwork/title_font_20261008/titles/{name.upper()}_12.png').convert('RGBA')
        bbox = label.getchannel('A').getbbox()
        label = label.crop(bbox)
        card.alpha_composite(label, ((98 - label.width) // 2, 123 - label.height))
        return card

    def placeholder_art(self):
        from PIL import Image
        soldier = self.lab.prep.skin.icon(2, 1)                       # UnitID 2 原生头像（ConvUnitIcon，原尺寸）
        art = Image.new('RGBA', (98, 102), (0, 0, 0, 0))
        art.alpha_composite(soldier, (2, 40))
        art.alpha_composite(soldier.transpose(Image.FLIP_LEFT_RIGHT), (54, 40))
        return art

    def versus_mark(self):
        """以原生像素拼接 34×20 的 VS 字样，在各卡片插画上独立叠加。"""
        from PIL import Image
        versus = Image.open(self.root / 'artwork/title_font_20261008/titles/VERSUS_16_native.png').convert('RGBA')
        vs = Image.new('RGBA', (34, versus.height), (0, 0, 0, 0))
        vs.alpha_composite(versus.crop((0, 0, 17, versus.height)), (0, 0))          # V
        vs.alpha_composite(versus.crop((versus.width - 17, 0, versus.width, versus.height)), (17, 0))  # S
        return vs

    def native_images(self, lang):
        """替换表条目：(转换项, 匹配图像, 新图像, 匹配值, 新转换项)。匹配图像 1 表示按绘制 x（匹配值为浮点位）区分。"""
        if lang not in self.images:
            from PIL import Image
            from lab_versus import create_native_image
            title = Image.open(self.root / 'artwork/title_font_20261008/titles/VERSUS_16_native.png').convert('RGBA')
            rect = (0, 0, 98, 123, -7, -7, 0, 0)
            entries = [(TITLE_CONV, 0, create_native_image(self.p, title), 0,
                        (0, 0, title.width, title.height, 0, title.height // 2, 0, 0))]
            cpu = create_native_image(self.p, self.card_image('cpu', lang))
            for index, conv in enumerate(CARD_CONVS):
                image = create_native_image(self.p, self.card_image(CARDS[index], lang))
                if index == 0:                   # LOCAL 与第四张卡共用转换项：按绘制 x 区分
                    entries.append((conv, 1, image, as_float(ORDER_X[1]), rect))
                    entries.append((conv, 1, cpu, as_float(ORDER_X[0]), rect))
                else:
                    entries.append((conv, 0, image, 0, rect))
            entries.append((LOCK_CONV, 0, 0, 0, (0,) * 8))
            self.images[lang] = entries
        return self.images[lang]

    def write_header(self, enable):
        import lab as labmod
        from lab_ui import lang
        p = self.p
        header = labmod.LAB_HEADER + VS_PAGE
        if not enable:
            p.put(header, 0)
            p.put(header + 8, 0)
            p.put(header + 12, 0)
            return
        entries = self.native_images(lang(p))
        for i, (conv, want, image, match, rect) in enumerate(entries):
            e = header + 0x10 + i * 32
            p.put(e, conv)
            p.put(e + 4, want)
            p.put(e + 8, image)
            p.put(e + 12, match)
            p.write(e + 16, struct.pack('<8h', *rect))
        p.put(header + 4, len(entries))
        self.write_slot()
        p.put(header, VS_PAGE_MAGIC)

    def write_slot(self):
        """头部 +8 第四张卡的菜单任务槽号、+12 AppMain 指针：钩子第 23 版据此在绘制时同步其透明度。"""
        import lab as labmod
        p = self.p
        header = labmod.LAB_HEADER + VS_PAGE
        ok = self.lab.native_hooks >= 23 and self.extra_valid()
        p.put(header + 8, self.extra_slot if ok else 0)
        p.put(header + 12, p.app_instance() if ok else 0)

    # ---------- 四张卡 ----------
    def task(self, index):
        """VERSUS 页第 index 张卡（ORDER）的原生任务。"""
        if index == 0:
            return self.extra_task if self.extra_valid() else 0
        return self.p.word(self.p.app_instance() + CARD_TASKS[index - 1])

    def panel_funcs(self):
        p = self.p
        return {p.symbols[f'_ZN7AppMain{len(n)}{n}EP17GENERAL_TASK_BASE'] & ~1 for n in PANEL_FUNCS}

    def extra_valid(self):
        """第四张卡仍占据其菜单任务槽（主菜单在场景 28 内重建任务时由 deleteMenuTask 释放并清空槽位）。"""
        if not self.extra_task or self.extra_slot is None:
            return False
        return self.p.word(self.p.app_instance() + MENU_TASKS + self.extra_slot * 4) == self.extra_task

    def live(self, task):
        """场景 28 中仍有效的卡片任务（函数指针位于原生代码段）。"""
        return bool(task) and self.menu_state()[0] == 28 and 0x10000000 <= (self.p.word(task) & ~1) < 0x10a00000

    def write_x(self, values):
        """三张原生卡片任务的横坐标（+0x84，浮点）。"""
        p = self.p
        for offset, x in zip(CARD_TASKS, values):
            task = p.word(p.app_instance() + offset)
            if self.live(task) and struct.unpack('<f', p.read(task + 0x84, 4))[0] != x:
                p.write(task + 0x84, struct.pack('<f', float(x)))

    def apply_layout(self):
        self.write_x(ORDER_X[1:])
        if self.lab.native_hooks >= 23:
            self.ensure_extra()
            self.write_slot()
            self.mirror()

    def restore_layout(self):
        """恢复原生商店页的横坐标；第四张卡透明度归零并转入离场函数（随后为原生的空闲函数）。"""
        self.write_x(CARD_NATIVE_X)
        task = self.task(0)
        if self.live(task):
            p = self.p
            p.put(task + 212, 0)
            p.put(task + 216, 0)
            out = p.symbols['_ZN7AppMain20GT_MenuGenrePanelOutEP17GENERAL_TASK_BASE']
            if (p.word(task) & ~1) in self.panel_funcs() and (p.word(task) & ~1) != (out & ~1):
                p.call(CHANGE, out, task)

    def ensure_extra(self):
        p = self.p
        app = p.app_instance()
        if self.extra_valid():
            return self.extra_task
        self.extra_task = 0
        literal, base, add, count = MENU_TABLE
        table = (p.word(literal) + base + add) & 0xffffffff
        entries = [p.read(table + i * 0x38, 0x38) for i in range(count)]
        slots = [struct.unpack_from('<I', e, 0)[0] for e in entries]
        if CARD_SLOT not in slots:
            p.log('VERSUS_CPU_TABLE_UNEXPECTED', slots)
            return 0
        if self.extra_slot is None:
            self.extra_slot = next((s for s in EXTRA_SLOTS if s not in slots and not p.word(app + MENU_TASKS + s * 4)), None)
        if self.extra_slot is None or p.word(app + MENU_TASKS + self.extra_slot * 4):
            p.log('VERSUS_CPU_SLOT_BUSY', self.extra_slot)
            return 0
        entry = bytearray(entries[slots.index(CARD_SLOT)])
        struct.pack_into('<I', entry, 0, self.extra_slot)
        struct.pack_into('<ii', entry, 0x10, ORDER_X[0], CARD_Y)
        if not self.extra_entry:
            self.extra_entry = p.alloc(0x38)
        p.write(self.extra_entry, bytes(entry))
        p.call('_ZN7AppMain14createMenuTaskEPP17GENERAL_TASK_BASEPNS_10_MENU_TASKEi', app, app + MENU_TASKS, self.extra_entry, 1)
        task = p.word(app + MENU_TASKS + self.extra_slot * 4)
        if not task:
            p.log('VERSUS_CPU_CREATE_FAILED', self.extra_slot)
            return 0
        src = self.task(1)
        p.put(task + 0x1b8, p.word(src + 0x1b8))
        p.write(task + 0xf4, p.read(src + 0xf4, 16))              # 点击区域（偏移、尺寸）：新建任务为 0
        p.write(task + 0x84, struct.pack('<ff', ORDER_X[0], CARD_Y))
        p.put(task + 212, 0)
        self.extra_task = task
        p.log('VERSUS_CPU_CARD_TASK', hex(task), self.extra_slot)
        return task

    def mirror(self):
        """第四张卡的函数对齐 LOCAL 卡（透明度另由第 23 版钩子在绘制时同步）。"""
        p = self.p
        src, task = self.task(1), self.task(0)
        if not (self.live(src) and self.live(task)):
            return
        f_src = p.word(src) & ~1
        if f_src in self.panel_funcs() and f_src != (p.word(task) & ~1):
            p.call(CHANGE, p.word(src), task)
        p.put(task + 212, p.word(src + 212))

    # ---------- 状态 ----------
    def menu_state(self):
        app = self.p.app_instance()
        return self.p.word(app + 0x22bc), self.p.word(app + 0x22dc)

    def panel_ready(self, offset, symbol):
        """按压仅在原生入场任务切换至稳态控件后受理，白光与业务点击使用相同就绪时机。"""
        p = self.p
        task = p.word(p.app_instance() + offset)
        return bool(task and (p.word(task) & ~1) == (p.symbols[symbol] & ~1))

    def can_open(self):
        scene, state = self.menu_state()
        lab = self.lab
        return (scene == 28 and state == 1 and not lab.active and not lab.prep.open and not lab.prep.busy()
                and self.state == 'closed' and self.lab.native_hooks >= 16
                and self.panel_ready(WIFI_TASK, '_ZN7AppMain12GT_MenuPanelEP17GENERAL_TASK_BASE'))

    def open(self):
        p = self.p
        try:
            self.write_header(True)
            app = p.app_instance()
            task = p.word(app + SHOP_TASK)
            if not task:
                raise RuntimeError('原生 SHOP 布局任务未就绪')
            # 仅登记布局选择；原生切换函数保留入场、单次确定音与标记清理，SHOP 不进入按压状态。
            try:
                p.put(task + 0x194, 1)
                p.call('_ZN7AppMain21SelectCockpitMainMenuEv', app)
            finally:
                p.call('_ZN7AppMain16ClearSelectPanelEP17GENERAL_TASK_BASEi', app, task, 0)
            if p.word(app + 0xb168) != 4:
                raise RuntimeError('原生对战卡片布局切换未完成')
        except Exception as error:
            self.write_header(False)
            self.error = f'{type(error).__name__}: {error}'
            p.log('VERSUS_PAGE_ERROR', self.error)
            return
        self.state, self.left_menu, self.unlocked, self.leaving = 'opening', False, False, 0
        self.error = None
        self.apply_layout()
        p.log('VERSUS_PAGE_OPEN', p.frame)

    def close(self, reason):
        self.end_press()
        if self.state != 'closed':
            if self.menu_state()[0] == 28:
                self.restore_layout()
            else:
                self.extra_task = 0                 # 场景结束时 deleteMenuTask 已释放
            self.write_header(False)
            self.p.log('VERSUS_PAGE_CLOSE', reason, self.p.frame)
        self.state, self.pressed = 'closed', None

    def follow_lobby_return(self):
        """离开联机大厅（大厅 BACK，或经编队页进入的勋章商店、单位改造等页面返回）回到主菜单时显示本页。
        原生按 app+0xb168 选择回到主菜单后的子页；大厅打开后该值置 0（原版从 MENU 进入 Wi-Fi 菜单时的状态），
        途中在原生底栏另选 OPTION / SHOP 时由原生改写，按原生前往。主菜单初始化（场景 27）时仍为 0 则改为 4（SHOP 子页），
        场景 28 起以 VERSUS 替换表打开本页，入场动画沿用原生。"""
        p = self.p
        app = p.app_instance()
        scene, _ = self.menu_state()
        if scene == 27 and self.lobby_return == 'lobby':
            if p.word(app + 0xb168) == 0:
                p.put(app + 0xb168, 4)
                self.lobby_return = 'armed'
            else:
                self.lobby_return = None
        elif scene == 28:
            if self.lobby_return == 'armed' and self.state == 'closed':
                self.extra_task = 0                 # 场景 27 重建了全部菜单任务
                self.write_header(True)
                self.state, self.left_menu, self.unlocked, self.leaving = 'opening', False, False, 0
                self.apply_layout()
                p.log('VERSUS_PAGE_RETURN', p.frame)
            self.lobby_return = None

    def prepare_frame(self):
        if self.lobby_return is not None:
            self.follow_lobby_return()
        if self.extra_task and not self.extra_valid():
            self.extra_task = 0                     # 任务已随场景结束或菜单重建释放
            if self.state != 'closed':
                self.write_slot()
        if self.state == 'closed':
            return
        scene, state = self.menu_state()
        if scene == 28 and self.state in ('opening', 'open', 'local_transition', 'lan_transition'):
            self.write_x(ORDER_X[1:])
            if self.extra_task:
                self.mirror()
        if self.state == 'local_transition':
            # 准备界面 reveal() 在闸门完全闭合后置 open；此前继续显示 VERSUS 的标题与卡片。
            if self.lab.prep.open or self.lab.active or scene != 28:
                self.close('local')
            return
        if self.state == 'lan_transition':
            # 原生闸门合拢、进入联机大厅（场景 66）之前继续显示 VERSUS 的标题与卡片。
            if scene != 28 or self.lobby is None or not self.lobby.active():
                if scene != 28 and self.lobby is not None and self.lobby.active():
                    self.lobby_return = 'lobby'
                    self.p.put(self.p.app_instance() + 0xb168, 0)
                self.close('lan')
            return
        if scene != 28 or self.lab.active or self.lab.prep.open:
            self.close('left_menu')
            return
        if self.state == 'open' and state != 4:
            # 离开 VERSUS 页（BACK、OPTION、MEDAL 等原生切换）：卡片淡出期间保留替换，三张卡透明度归零
            # （或任务结束、至多 30 帧）后关闭，使其后原生再次进入的商店为原生内容。
            self.leaving = (self.leaving or 0) + 1
            app = self.p.app_instance()
            alphas = [self.p.word(self.p.word(app + o) + 212) & 0xff if self.p.word(app + o) else 0
                      for o in (0x33a4, 0x33a8, 0x33ac)]
            if not any(alphas) or self.leaving > 30:
                self.close('left_page')
            return
        if state == 4:
            self.state = 'open'
            # 原生 SHOP 子页面把底栏 SHOP 按钮任务 +0x80 第 0 位置 1（当前页，按下不受理）。VERSUS 页清除该位，
            # 点击 SHOP 时原生 SelectCockpitMainMenu 受理并重新进入商店（再次置位）；此时宿主关闭替换，
            # 并以原生进入商店时的卡片动作（CTaskSystem2D::Change，见 shop_card_entry）重放三张卡的入场。
            task = self.p.word(self.p.app_instance() + SHOP_TASK)
            if task and self.p.word(task + 0x80) & 1:
                if self.unlocked:
                    self.shop_card_entry()
                    self.close('shop')                  # 同一帧恢复原生横坐标，原生商店卡片在原位置淡入
                    return
                self.p.put(task + 0x80, self.p.word(task + 0x80) & ~1)
                self.unlocked = True

    def shop_card_entry(self):
        """原生 SelectCockpitMainMenu 进入商店的共同段（0x10205516 起）对三张卡任务（app+0x33a4/0x33a8/0x33ac）
        把透明度归零并调用 CTaskSystem2D::Change(GT_MenuGenrePanelIn, 任务)；入场动作取自该函数的 GOT 偏移（字面量 0x102058e8，基址
        字面量 0x102058d0 + 0x1020529a）。"""
        p = self.p
        app = p.app_instance()
        got = (p.word(0x102058d0) + 0x1020529a) & 0xffffffff
        action = p.word((got + p.word(0x102058e8)) & 0xffffffff)
        for offset in (0x33a4, 0x33a8, 0x33ac):
            task = p.word(app + offset)
            if task and action:
                p.put(task + 212, 0)                # GT_MenuGenrePanelIn：+212 透明度每帧 +32 至 255（淡入）
                p.call('_ZN13CTaskSystem2D6ChangeEPFiP17GENERAL_TASK_BASEES1_', action, task)
        p.log('VERSUS_PAGE_TO_SHOP', hex(action), p.frame)

    # ---------- 输入 ----------
    def clear_press(self):
        """清除当前原生控件的按压与点击完成字，白光由其原生任务继续淡出。"""
        p, app = self.p, self.p.app_instance()
        task = p.word(app + WIFI_TASK) if self.pressed == 'wifi' else self.task(self.pressed)
        if task:
            p.call('_ZN7AppMain16ClearSelectPanelEP17GENERAL_TASK_BASEi', app, task, 0)

    def end_press(self):
        if self.pressed is None:
            return
        # 框外释放结束原生触点；业务点击由宿主处理，原 Wi-Fi 与商店卡片的选择动作保持未触发。
        try:
            self.native_touch(self.p, 3, -1000, -1000)
        finally:
            try:
                self.clear_press()
            finally:
                self.pressed, self.press_cancelled = None, False

    def move_press(self, rect, x, y):
        if self.press_cancelled:
            self.native_touch(self.p, 5, -1000, -1000)
            self.clear_press()
            return
        self.native_touch(self.p, 5, x, y)
        if not inside(rect, x, y):
            self.press_cancelled = True
            self.clear_press()

    def touch(self, action, x, y):
        """返回 True 表示已处理（不送入原生）。"""
        trial = getattr(self.p, 'event_trial', None)
        if trial is not None and trial.browser.active:
            return False                                    # 历史活动浏览页借用主菜单，第三行由浏览页处理
        if self.state == 'closed':
            if action == 1 and self.can_open() and inside(WIFI_BUTTON, x, y):
                self.end_press()
                self.pressed = 'wifi'
                self.press_cancelled = False
                self.native_touch(self.p, action, x, y)
                return True
            if self.pressed == 'wifi':
                if action == 5:
                    self.move_press(WIFI_BUTTON, x, y)
                if action == 3:
                    activate = not self.press_cancelled and inside(WIFI_BUTTON, x, y) and self.can_open()
                    self.end_press()
                    if activate:
                        self.open()
                return True
            return False
        if self.state != 'open':
            return True                                     # 入场过程中不接受输入
        if self.menu_state()[1] != 4:
            # 离场淡出中（BACK、OPTION 等原生切换）：原生 MENU 等页面正在入场，触点交给原生。
            self.end_press()
            self.swallow = False
            return False
        if action == 1:
            self.end_press()
            self.swallow = False
            hit = next((i for i in range(len(ORDER)) if inside(card_rect(i), x, y) and self.task(i)), None)
            if hit is not None and self.task_ready(self.task(hit)):
                self.pressed, self.press_cancelled = hit, False
                self.native_touch(self.p, action, x, y)
                return True
            if hit is not None or CONTENT_TOP <= y < CONTENT_BOTTOM:
                self.swallow = True                         # 卡片未就绪或空白处：整次触点不送入原生
                return True
            return False                                    # 顶栏与底栏（含 SHOP）由原生处理
        if self.pressed is None:
            swallow = self.swallow
            if action == 3:
                self.swallow = False
            return swallow
        if action == 5:
            self.move_press(card_rect(self.pressed), x, y)
        if action == 3:
            index = self.pressed
            activate = not self.press_cancelled and inside(card_rect(index), x, y)
            self.end_press()
            if activate:
                self.activate(index)
        return True

    def task_ready(self, task):
        return (self.p.word(task) & ~1) == (self.p.symbols['_ZN7AppMain17GT_MenuGenrePanelEP17GENERAL_TASK_BASE'] & ~1)

    def activate(self, index):
        from lab_ui import play_se, SE_DECIDE, SE_CLOSE, T
        name = ORDER[index]
        if name in ('cpu', 'local'):
            play_se(self.p, SE_DECIDE)
            self.state = 'local_transition'               # 闸门合拢后打开准备界面（VS CPU / 本地双人对战）
            self.lab.commands.append(('prep', 'cpu' if name == 'cpu' else 'versus'))
            return
        if name in ('lan', 'online') and self.lobby is not None:
            play_se(self.p, SE_DECIDE)
            self.state = 'lan_transition'                 # 局域网与远程（N6b）进入同一大厅
            self.lobby.open('lan' if name == 'lan' else 'remote')
            return
        play_se(self.p, SE_CLOSE)
        self.lab.feedback(T(self.p, 'vs_soon'), False)

    def shutdown(self):
        self.write_header(False)
