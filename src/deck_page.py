"""编队页（原生场景 54–56，SC_DeckInit / SC_DeckLoop / SC_DeckEnd）的选单位条、排序与 DECK 标签（2026-11-11）。

参照 Metal Slug Attack 的 CUSTOMIZE DECK：
- 选单位条每页 10 格，两侧箭头翻页（首末页循环），右下为页码；图标下方一行显示所选单位的阵营标志、名称、等级与 AP。
  按下图标即选中，按住移动即拖起（不需长按，原生为按住约 10 帧）；图标底板在按下与鼠标划过时为浅绿
  （原生的按下图块），松开或移开后渐变回墨绿（核心按宿主每帧写入的亮度表，在底板与头像之间以该透明度加画浅绿底板）。
  面板仍为原生任务（GT_DeckPanel：绘制、SELECTED 标记、按住拖放编队均为原生）：宿主把当前页的单位写入原生列表
  （app+0xb9d4，社区内容启用时为其重定位缓冲）后调用原生换页函数 InitDeckPanels(int)（0x1f1a24）重建，再改写各面板的
  位置；原生的左右滑动（TouchSlideManager）范围置 0、触摸区域移出画面，两侧渐暗层（任务槽 app+0x3368）与原生的
  名称 / 等级文字（只画“当前”面板，面板序号改为 1000 起即无当前面板）不显示。
- 底栏 SORT 由宿主受理，打开单位强化界面的排序与筛选面板（unit_browser.compose_panel，设定独立保存为 deck）。
- DECK 标签由 3 个增为 5 个（核心 r161 起：msd_deck_groups；第 4、5 组在存档 app+0x8880、app+0x88a8）。标签由宿主以
  原生图块绘制（数字 4、5 按同一字形补画），原生的 3 个标签与 AP 数字任务移出画面；切换与原生相同
  （写当前组号 app+0x88d0 后调用 DeckChangeInit）。
- 面板的 EVENT 标记（InitDeckPanel 为活动加成单位另建的任务，槽 app+0x34e8 起）随面板移动。编队栏空位的红色数字
  （任务槽 app+0x3370 起，空位图块 15+格）对到背景图上的灰色数字：原生两者错开 12 个单位（第 10 格 18）。
- SELECTED 标记：原生画在各面板自己的绘制中（右侧相邻面板之下），间距缩小后右端被下一格盖住。重建面板时为每格另建
  一个与 EVENT 标记同层的原生任务（图块 0x19，后于 EVENT 标记建立，画在全部面板与 EVENT 标记之上），每帧按是否
  已编入显示或隐藏；核心据亮度表第 15 字节停掉面板自己的那一份。
- 宿主图层画在原生画面之上：编队页的原生闸门（ChangeNT 17 / 18）改由本模块在图层之后推进并绘制（与
  SC_ShutterClose / SC_ShutterOpen 相同的步骤），原生弹窗显示期间不画信息行与选择框。
"""
import ctypes
import struct
from contextlib import contextmanager

from lab_ui import W, H, SE_DECIDE, SE_CLOSE, play_se

SCENE_DECK = 55
POPUP_SCENES = range(119, 123)
GT_SELECTED_DECK_NUM = 0x101f0d1d              # 原生 DECK 标签任务函数（判断编队页对象是否存在）
SLOT_FADE = 0x3368                             # 选单位条两侧渐暗层
SLOT_TABS = (0x34d0, 0x34d4, 0x34d8, 0x34dc, 0x34e0, 0x34e4)   # 原生 DECK 标签 ×3 与 AP 数字 ×3
SLOT_PANELS, PANEL_LIMIT = 0x33d0, 50
SLOT_MARKS = 0x34e8                            # 面板的 EVENT 标记任务（与面板同序号，建立时取面板的位置）
SLOT_STAMPS = SLOT_MARKS + 4 * 10              # SELECTED 标记任务：借用标记槽的第 10–19 项（ClearDeckPanel 一并删除）
GOT_MARK_FUNC = 0x109387b8                     # EVENT 标记的任务函数指针（0x208f4c：随所属面板的滑动偏移，按 +0x50 的图块绘制）
MARK_IMAGE, MARK_TABLE, STAMP_PICT = 0x18, 0x13, 0x19    # 标记的图像与转换表；SELECTED 的图块（GT_DeckPanelDraw）
PANEL_Y = 368.0                                # 面板的原生纵坐标（InitDeckPanel 0x170）
SLOT_NUMBERS = 0x3370                          # 编队栏 10 格的数字任务（x = 56 + 96·格；图块 5+格 为已编入，15+格 为空位）
NUMBER_X, NUMBER_PITCH = 56.0, 96.0
# 空位的数字对到背景图（unit.obm，图内 x = 66 + 48·格，第 10 格的“10”自 495 起；画面 x = 2·图内 x - 88）的灰色数字上
EMPTY_NUMBER_SHIFT = (-12.0,) * 9 + (-18.0,)
SLOT_SORT = 0x36f8                             # 底栏 SORT
SELECTED_DECK = 0x88d0
HIDDEN_Y = 3000.0
PAGE_SIZE = 10
NATIVE_SCALE = 1.125                           # 原生逻辑坐标（960×640，横向边距 app+0x3c）到 1280×720
PANEL_X0, PANEL_PITCH = -28.0, 102.0           # 面板的原生横坐标：10 格居中（原生间距 136）
ICON_Y, ICON_SIZE = 416, 108                   # 图标格在画布上的范围
INFO_Y = 548
RAIL_LEFT, RAIL_PITCH, RAIL_TOP, RAIL_BOTTOM = 153, 108, 100, 372   # 编队栏 10 格（原生 x=48+96·格，y=294）在画布上的范围
FADE_FRAMES = 15                               # 浅绿底板渐变回墨绿的帧数（30 帧 / 秒，约 0.5 秒）
DRAG_START = 6                                 # 按住后移动达到该距离（画布像素）即拖起
GT_DECK_PANEL = 0x101f1c9d                     # 面板任务函数（未在拖动中）
GOT_DECK_PANEL_HOLD = 0x109387bc               # GT_DeckPanelHold 的函数指针（GT_DeckPanel 开始拖动时 Change 的参数）
IN_DECK_COLOR = (128, 200, 0, 255)             # 已编入的单位：信息行颜色（原生 GT_DeckPanelDraw 的名称颜色 0xff80c800）
# DECK 标签（menuparts_02.obm；位置为相对标签左上角的画布像素，按原生画面校准）
TAB_ATLAS = 'menuparts_02.obm'
TAB_BG = {True: (81, 210, 80, 28), False: (0, 210, 80, 28)}
TAB_WORD = {True: (30, 239, 29, 10), False: (0, 239, 29, 10)}
TAB_DIGITS = {True: {1: (131, 239, 6, 10), 2: (122, 239, 8, 10), 3: (113, 239, 8, 10)},
              False: {1: (183, 161, 6, 10), 2: (104, 239, 8, 10), 3: (95, 239, 8, 10)}}
TAB_AP = (60, 246, 15, 7)
AP_DIGITS = ((168, 218, 5, 7), (150, 239, 3, 7), (138, 247, 5, 7), (174, 210, 5, 7), (144, 239, 5, 7),
             (162, 218, 5, 7), (168, 210, 5, 7), (138, 239, 5, 7), (162, 210, 5, 7), (183, 172, 5, 7))
AP_ZERO_DIM = (76, 246, 5, 7)
TAB_SCALE = 2.25
TAB_Y, TAB_W, TAB_H = 18, 180, 63
TAB_RIGHT = 1055                               # 最右标签的左端（原生第 3 个标签的位置）
TAB_PITCH = {3: 198, 5: 190}                   # 原生间距 198；5 个标签时为让出标题缩为 190
TAB_WORD_AT, TAB_DIGIT_AT, TAB_AP_AT = (48, 7), (115, 7), (45, 36)
# 数字 4、5（原版只有 1–3）：6×8 字形，X 为笔画、g 为圆角灰；外框与配色规则取自原版 2、3。
GLYPHS = {4: ('...XX.', '..XXX.', '.gXXX.', 'gX.XX.', 'XX.XX.', 'XXXXXX', '...XX.', '...XX.'),
          5: ('XXXXXX', 'XXXXXX', 'XX....', 'XXXXXg', 'gXXXXX', '....XX', 'XXXXXX', 'gXXXXg')}
DIM_ROWS = (151, 140, 124, 110, 94, 80, 74, 131)
ARROW_SCALE = 2.25


def deck_address(app, deck, slot):
    """原生 Get/SetDeckUnitSaveData：第 0 组在 app+0x4ed0，其后各组在 app+0x8830 起每组 10 格。"""
    return app + (0x13b4 + slot if deck == 0 else 0x220c + 10 * (deck - 1) + slot) * 4


def glyph_image(digit, bright):
    """数字 4、5：8×10，亮版为白框黑字，暗版为黑框灰字（逐行明度同原版）。"""
    from PIL import Image
    img = Image.new('RGBA', (8, 10))
    box = (255, 255, 255) if bright else (0, 0, 0)
    for y in range(10):
        for x in range(8):
            edge = (x in (0, 7)) + (y in (0, 9))
            near = (x in (1, 6) and y in (0, 9)) or (x in (0, 7) and y in (1, 8))
            img.putpixel((x, y), box + ((23 if edge == 2 else 150 if near else 255),))
    for r, row in enumerate(GLYPHS[digit]):
        for c, mark in enumerate(row):
            if mark == '.':
                continue
            if bright:
                v = 0 if mark == 'X' else 127
            else:
                v = DIM_ROWS[r] if mark == 'X' else 76
            img.putpixel((c + 1, r + 1), (v, v, v, 255))
    return img


class DeckPage:
    def __init__(self, p, lab, root):
        self.p, self.lab, self.root = p, lab, root
        self.overlay = None
        self.items = []                    # 当前排序与筛选下的全部条目（unit_catalog）
        self.page = 0
        self.current = None                # 所选单位（信息行）；进入页面与翻页后为无，按下图标或编队栏单位时设定
        self.press_icon = None             # 按下的图标：{'index', 'uid', 'x', 'y', 'started'}（started：已拖起）
        self.pointer = None                # 鼠标位置（画布坐标；窗口线程写入，鼠标在画面之外为 None）
        self.levels = [0] * PAGE_SIZE      # 各格浅绿底色的剩余帧数（FADE_FRAMES 为全亮）
        self.lit_table = None              # 核心读取的亮度表（客体地址，每格 1 字节；第 15 字节为 1 时面板不自己画 SELECTED）；核心无此接口时为 0
        self.stamps_ready = False          # 当前页的 SELECTED 标记任务已建立
        self.lit_written = None
        self.panel = False                 # SORT 面板
        self.panel_boxes = []
        self.pressed = None
        self.sort_press = None             # 底栏 SORT 的按压（cockpit_hold）
        self.shut = None                   # 由本模块推进的原生闸门：'closing' / 'opening'；'closed' 为合拢后交还原生
        self.panel_tasks = ()              # 最近一次重建后的面板任务（原生自行重建时不同）
        self.rebuilt = False               # 在本帧原生画面之后重建了面板：新面板下一帧才画出，图层本帧保持上一帧的内容
        self.down = False                  # 触点按下中（期间不以键盘、滚轮翻页：原生拖放正持有面板任务）
        self.keys_ok = False               # 每帧更新：键盘由本模块受理（窗口线程只读此标记）
        self.in_draw = False               # draw() 中（原生画面之后）；触点在原生步进之前送达，其间的重建当帧即画出
        self.jump = None                   # 按下的编队栏单位：选单位条跳到该单位所在页并选中（原生为滚动到该单位）
        self.dirty = True                  # 列表需重新查询
        self.commands = []                 # 窗口线程写入（键、字符、滚轮）
        self.revision = 0
        self.was_alive = False
        self.cache = {}
        self.groups = None
        self.boxes = []
        self.by_uid = {}

    # ---------- 状态 ----------
    @property
    def browser(self):
        return self.p.unit_browser

    def app(self):
        return self.p.app_instance()

    def scene(self):
        app = self.app()
        return self.p.word(app + 0x22bc) if app else None

    def deck_groups(self):
        if self.groups is None:
            export = getattr(self.p.uc.lib, 'msd_deck_groups', None)
            self.groups = 5 if export is not None and export() >= 5 else 3
        return self.groups

    def alive(self):
        """编队页对象存在：场景 55（或其上的原生弹窗），原生 DECK 标签任务仍在。"""
        app = self.app()
        if not app or self.scene() not in (SCENE_DECK, *POPUP_SCENES):
            return False
        task = self.p.word(app + SLOT_TABS[0])
        return bool(task) and self.p.word(task) == GT_SELECTED_DECK_NUM

    def shutter_tasks(self):
        app = self.app()
        return any(self.p.word(app + 0x3820 + 4 * i) for i in range(4))

    def ready(self):
        """可操作：编队页已开闸、无弹窗、闸门不在动作中。"""
        return (self.alive() and self.scene() == SCENE_DECK and self.shut is None and not self.shutter_tasks()
                and self.p.read(self.app() + 0xc21d, 1)[0] == 0 and not self.browser.busy())

    @contextmanager
    def deck_mode(self):
        """以 deck 设定使用单位浏览组件的排序面板与查询（其自身的模式在退出时恢复）。"""
        b = self.browser
        if b.state is None:
            b.load_state()
        if b.art is None:
            from unit_browser import Art
            b.art = Art(self.p, self.lab)
        saved = b.mode
        b.mode = 'deck'
        try:
            yield b
        finally:
            b.mode = saved

    # ---------- 列表与面板 ----------
    def query(self):
        from unit_browser import SOURCES
        with self.deck_mode() as b:
            catalog = b.catalog()
            catalog.refresh_state(shop=False)
            s = b.settings
            filters = b.filters()
            sources = filters.pop('_sources', None)
            if sources is not None:
                filters['source'] = {name for name in {e['source'] for e in catalog.index()}
                                     if ('original' if name == 'original' else 'body' if name == 'body' else 'mod') in sources}
            items, _ = catalog.list(filters, sort=s['sort'], descending=s['descending'], page=0, page_size=10 ** 9,
                                    level='owned')
        self.items = items
        self.by_uid = {e['uid']: e for e in catalog.index()}
        self.dirty = False

    @property
    def pages(self):
        return max(1, (len(self.items) + PAGE_SIZE - 1) // PAGE_SIZE)

    def page_items(self):
        return self.items[self.page * PAGE_SIZE:(self.page + 1) * PAGE_SIZE]

    def native_list(self):
        """原生编队列表（地址, 容量）：app+0xb9d4 的 400 项，社区内容启用时为其重定位缓冲。"""
        community = getattr(self.p, 'community', None)
        address = getattr(community, 'deck_list', None)
        if address:
            return address, community.owned_list_capacity
        return self.app() + 0xb9d4, 400

    def hide(self, slot):
        task = self.p.word(self.app() + slot)
        if task:
            self.p.write(task + 0x88, struct.pack('<f', HIDDEN_Y))

    def panel_slots(self):
        p, app = self.p, self.app()
        return struct.unpack('<%dI' % PANEL_LIMIT, p.read(app + SLOT_PANELS, 4 * PANEL_LIMIT))

    def native_fresh(self):
        """面板为原生所建：进入场景后的首帧（渐暗层尚在原位），或原生自行重建之后（面板任务与上次重建不同，
        或面板序号小于 1000；核心 r161 起宿主模式下 GT_DeckUnit 不再重建，此项留作旧核心的补救）。"""
        p, app = self.p, self.app()
        fade = p.word(app + SLOT_FADE)
        if fade and struct.unpack('<f', p.read(fade + 0x88, 4))[0] < HIDDEN_Y - 1:
            return True
        slots = self.panel_slots()
        return slots != self.panel_tasks or any(task and p.word(task + 0x220) < 1000 for task in slots)

    def rebuild(self):
        """把当前页写入原生列表并重建面板（原生换页：ClearDeckPanel → InitDeckPanels(偏移)），再改写位置与滑动范围。"""
        p, app = self.p, self.app()
        if self.dirty:
            self.query()
        self.page = min(max(self.page, 0), self.pages - 1)
        units = [e['uid'] for e in self.page_items()]
        # 列表只留当前页，其后全部清零（原生按列表查找单位时不得遇到旧条目）
        address, capacity = self.native_list()
        p.write(address, struct.pack('<%dI' % capacity, *(units + [0] * (capacity - len(units)))))
        p.put(app + 0xc014, len(units))
        p.call('_ZN7AppMain14ClearDeckPanelEv', app)
        p.call('_ZN7AppMain14RequestClear2DEv', app)
        p.put(app + 0xb884, 0)
        p.call('_ZN7AppMain14InitDeckPanelsEi', app, 0)
        stamps = self.create_stamps(len(units))           # 后于 InitDeckPanels：SELECTED 画在面板与 EVENT 标记之上
        for i, stamp in enumerate(stamps):
            p.put(stamp + 0x1b8, p.word(app + SLOT_PANELS + 4 * i))    # 所属面板（任务函数每帧读取）
        self.stamps_ready = bool(stamps) and all(p.word(app + SLOT_PANELS + 4 * i) for i in range(len(stamps)))
        if stamps and not self.stamps_ready:              # 面板未建成：撤掉标记任务，由面板自己画
            for i, stamp in enumerate(stamps):
                p.call('_ZN13CTaskSystem2D6DeleteEP17GENERAL_TASK_BASE', app + 0x3830, stamp)
                p.put(app + SLOT_STAMPS + 4 * i, 0)
        self.lit_written = None
        if self.lit_table:
            self.write_levels()                # 亮度表第 15 字节（上层标记已建立）
        self.update_stamps()                   # 建立后立即按是否已编入显示：与新面板同帧画出
        for i in range(PANEL_LIMIT):
            task = p.word(app + SLOT_PANELS + 4 * i)
            if not task:
                break
            p.write(task + 0x84, struct.pack('<f', PANEL_X0 + PANEL_PITCH * i))
            p.put(task + 0x220, 1000 + i)
            mark = p.word(app + SLOT_MARKS + 4 * i)
            if mark:                                  # EVENT 标记与面板同位置
                p.write(mark + 0x84, struct.pack('<f', PANEL_X0 + PANEL_PITCH * i))
        slide = p.word(app + 0x98)
        p.put(slide + 4, 0)
        p.put(slide + 8, 0)
        p.write(slide + 0x38, struct.pack('<f', 5000.0))      # 滑动的触摸区域移出画面
        self.hold_scroll()
        self.hide(SLOT_FADE)
        for slot in SLOT_TABS:
            self.hide(slot)
        if self.current not in units:
            self.current = None                # 不默认选中：信息行只在玩家选择单位后显示
        self.levels = [0] * PAGE_SIZE
        self.press_icon = None
        self.panel_tasks = self.panel_slots()
        self.rebuilt = self.in_draw
        self.revision += 1

    def hold_scroll(self):
        """滑动位置与目标保持为 0（按下编队栏单位时原生 GT_DeckUnit 会写滚动目标）。"""
        p = self.p
        slide = p.word(self.app() + 0x98)
        p.write(slide + 0xc, struct.pack('<f', 0.0))
        p.put(slide + 0x10, 0)
        p.put(slide + 0x24, 0)

    def create_stamps(self, count):
        """为当前页各格建立 SELECTED 标记任务（做法同 InitDeckPanel 建立 EVENT 标记：CTaskSystem2D::Entry(函数, 2, 3)、
        setTaskParamater(x, y, 图像 0x18, 表 0x13, -1, 图块, 1, 0)、setTaskRender(3, 255)、setTaskAffine(2, 2, 0)）。
        初始图块为 -1（不画），由 update_stamps 按是否已编入切换（重建与切换标签时立即调用，其后每帧核对；
        单位刚被拖入的那一帧上层任务尚未显示，核心仍让面板自己画）。返回任务列表；核心无亮度表接口时不建立。"""
        p, app = self.p, self.app()
        if self.lit_table is None:
            self.write_levels()
        if not self.lit_table:
            return []
        bits = lambda value: struct.unpack('<I', struct.pack('<f', value))[0]
        tasks = []
        for i in range(count):
            task = p.call('_ZN13CTaskSystem2D5EntryEPFiP17GENERAL_TASK_BASEEiiS1_', app + 0x3830, p.word(GOT_MARK_FUNC), 2, 3, 0)
            if not task:
                break
            p.call('_ZN7AppMain16setTaskParamaterEP17GENERAL_TASK_BASEffiiiiii', app, task, bits(PANEL_X0 + PANEL_PITCH * i),
                   bits(PANEL_Y), MARK_IMAGE, MARK_TABLE, 0xffffffff, 0xffffffff, 1, 0)
            p.call('_ZN7AppMain13setTaskRenderEP17GENERAL_TASK_BASEii', app, task, 3, 0xff)
            p.call('_ZN7AppMain13setTaskAffineEP17GENERAL_TASK_BASEfff', app, task, bits(2.0), bits(2.0), bits(0.0))
            p.put(app + SLOT_STAMPS + 4 * i, task)
            tasks.append(task)
        return tasks

    def update_stamps(self):
        """SELECTED 标记任务：单位已编入当前编队时显示（图块 0x19），否则不画。"""
        if not self.stamps_ready:
            return
        p, app = self.p, self.app()
        deck = set(self.deck_units(self.selected_deck()))
        for i, entry in enumerate(self.page_items()):
            task = p.word(app + SLOT_STAMPS + 4 * i)
            if not task:
                continue
            want = STAMP_PICT if entry['uid'] in deck else 0xffffffff
            if p.word(task + 0x50) != want:
                p.put(task + 0x50, want)

    def align_numbers(self):
        """编队栏空位的红色数字移到背景图的灰色数字上；已编入的格保持原生位置（阵营标志盖住灰色数字，数字在其右）。"""
        p, app = self.p, self.app()
        for i in range(10):
            task = p.word(app + SLOT_NUMBERS + 4 * i)
            if not task:
                continue
            x = NUMBER_X + NUMBER_PITCH * i + (EMPTY_NUMBER_SHIFT[i] if p.word(task + 0x50) == 15 + i else 0.0)
            raw = struct.pack('<f', x)
            if p.read(task + 0x84, 4) != raw:
                p.write(task + 0x84, raw)

    def apply_jump(self):
        uid, self.jump = self.jump, None
        index = next((i for i, e in enumerate(self.items) if e['uid'] == uid), None)
        if index is None:
            return
        self.current = uid
        if index // PAGE_SIZE != self.page:
            self.page = index // PAGE_SIZE
            self.rebuild()
        self.revision += 1

    def flip(self, delta):
        if self.pages <= 1:
            return False
        self.page = (self.page + delta) % self.pages
        self.current = None
        self.rebuild()
        return True

    # ---------- 编队数据 ----------
    def selected_deck(self):
        value = self.p.word(self.app() + SELECTED_DECK)
        return value if value < self.deck_groups() else 0

    def deck_units(self, deck):
        raw = self.p.read(deck_address(self.app(), deck, 0), 40)
        return struct.unpack('<10i', raw)

    def deck_ap(self, deck):
        return sum(self.by_uid[u]['ap'] for u in self.deck_units(deck) if u in self.by_uid)

    def select_deck(self, deck):
        p, app = self.p, self.app()
        if deck == self.selected_deck():
            return
        p.put(app + SELECTED_DECK, deck)
        p.call('_ZN7AppMain14DeckChangeInitEv', app)
        p.put(app + SELECTED_DECK, deck)
        self.update_stamps()                   # 与面板的已编入底板同帧更换
        p.log('DECK_PAGE_SELECT', deck)

    # ---------- 画面 ----------
    def art(self):
        return self.browser.art

    def sprite(self, rect, scale=TAB_SCALE, atlas=TAB_ATLAS):
        from unit_browser import scaled
        key = ('sprite', atlas, rect, scale)
        if key not in self.cache:
            self.cache[key] = scaled(self.art().part((atlas, rect)), scale)
        return self.cache[key]

    def digit_sprite(self, number, bright):
        from unit_browser import scaled
        key = ('digit', number, bright)
        if key not in self.cache:
            if number in TAB_DIGITS[bright]:
                self.cache[key] = self.sprite(TAB_DIGITS[bright][number])
            else:
                self.cache[key] = scaled(glyph_image(number, bright), TAB_SCALE)
        return self.cache[key]

    def tab_rects(self):
        count = self.deck_groups()
        pitch = TAB_PITCH[count]
        return [(TAB_RIGHT - pitch * (count - 1 - i), TAB_Y, TAB_W, TAB_H) for i in range(count)]

    def tab_image(self, number, selected, ap):
        from PIL import Image
        key = ('tab', number, selected, ap)
        if key in self.cache:
            return self.cache[key]
        img = Image.new('RGBA', (TAB_W, TAB_H))
        img.alpha_composite(self.sprite(TAB_BG[selected]))
        img.alpha_composite(self.sprite(TAB_WORD[selected]), TAB_WORD_AT)
        digit = self.digit_sprite(number, selected)
        lead = round(2 * TAB_SCALE) if number == 1 else 0          # 原版 1 的锚点为 -2
        img.alpha_composite(digit, (TAB_DIGIT_AT[0] + lead, TAB_DIGIT_AT[1]))
        line = Image.new('RGBA', (TAB_W, TAB_H))
        line.alpha_composite(self.sprite(TAB_AP), TAB_AP_AT)
        value = max(0, min(9999, int(ap)))
        text = '%04d' % value
        for i, ch in enumerate(text):
            leading = value < 10 ** (3 - i) and i < 3
            rect = AP_ZERO_DIM if leading else AP_DIGITS[int(ch)]
            x = TAB_AP_AT[0] + round((16 + 6 * i + (1 if rect[2] == 3 else 0)) * TAB_SCALE)
            line.alpha_composite(self.sprite(rect), (x, TAB_AP_AT[1]))
        if not selected:          # 原生 GT_SelectedDeckAPNum：未选中标签的 AP 数字透明度 0x7a
            line.putalpha(line.getchannel('A').point(lambda v: v * 0x7a // 255))
        img.alpha_composite(line)
        self.cache[key] = img
        return img

    def icon_at(self, x, y):
        for i in range(len(self.page_items())):
            left, top, w, h = self.icon_rect(i)
            if left <= x < left + w and top <= y < top + h:
                return i
        return None

    def update_levels(self, popup):
        """浅绿底色：按下的图标（拖动中保持）与鼠标所在的图标为全亮，其余逐帧减退；已编入的单位不显示。"""
        units = [e['uid'] for e in self.page_items()]
        lit = None
        if not popup and not self.panel and self.shut is None:
            if self.down:
                lit = self.press_icon['index'] if self.press_icon is not None else None
            elif self.pointer is not None and self.ready():
                lit = self.icon_at(*self.pointer)
        deck = set(self.deck_units(self.selected_deck())) if any(self.levels) or lit is not None else ()
        for i in range(PAGE_SIZE):
            if i >= len(units) or units[i] in deck:
                self.levels[i] = 0
            elif i == lit:
                self.levels[i] = FADE_FRAMES
            elif self.levels[i] > 0:
                self.levels[i] -= 1

    def write_levels(self):
        """把各格亮度写入核心的亮度表（msd_deck_lit_table；内容变化时才写）。"""
        p = self.p
        if self.lit_table is None:
            register = getattr(p.uc.lib, 'msd_deck_lit_table', None)
            self.lit_table = p.alloc(16) if register is not None else 0
            if self.lit_table:
                p.write(self.lit_table, bytes(16))
                register.argtypes, register.restype = [ctypes.c_uint32], None
                register(self.lit_table)
        if not self.lit_table:
            return
        data = bytes(level * 255 // FADE_FRAMES for level in self.levels) + bytes(5) + bytes((1 if self.stamps_ready else 0,))
        if data != self.lit_written:
            p.write(self.lit_table, data)
            self.lit_written = data

    def start_drag(self, press):
        """拖起按下的图标（原生 GT_DeckPanel 在按住约 10 帧后所做的步骤：SetDeckDrag、任务换为 GT_DeckPanelHold、
        停用滑动）。拖动物按触点相对按下点的位移移动（GT_DeckDrag），放下与退回均为原生。"""
        p, app = self.p, self.app()
        task = p.word(app + SLOT_PANELS + 4 * press['index'])
        slide = p.word(app + 0x98)
        if (not task or p.word(task) != GT_DECK_PANEL or p.word(task + 0x224) != press['uid'] or not self.ready()
                or not p.read(slide + 0x46, 1)[0] or press['uid'] in self.deck_units(self.selected_deck())):
            return False
        f = lambda offset: struct.unpack('<f', p.read(task + offset, 4))[0]
        p.put(task + 0x80, p.word(task + 0x80) | 0x800000)
        p.call('_ZN7AppMain11SetDeckDragEiii', app, press['uid'], int(f(0x84) + f(0x9c) + 50.0), int(f(0x88)))
        p.call('_ZN13CTaskSystem2D6ChangeEPFiP17GENERAL_TASK_BASEES1_', p.word(GOT_DECK_PANEL_HOLD), task)
        p.call('_ZN17TouchSlideManager9setEnableEb', slide, 0)
        return True

    def icon_rect(self, index):
        x = (PANEL_X0 + PANEL_PITCH * index + 88) * NATIVE_SCALE + 2
        return (round(x), ICON_Y, ICON_SIZE, ICON_SIZE)

    def arrow_boxes(self):
        left = self.icon_rect(0)[0]
        right = self.icon_rect(PAGE_SIZE - 1)[0] + ICON_SIZE
        return ((0, ICON_Y, left - 2, ICON_SIZE), -1), ((right + 2, ICON_Y, W - right - 2, ICON_SIZE), 1)

    def state_key(self, popup):
        app = self.app()
        decks = tuple(self.deck_units(d) for d in range(self.deck_groups()))
        b = self.browser
        caret = (self.p.frame // 15) % 2 if self.panel and b.search_focus else 0
        return ('deck_page', self.revision, self.page, self.current, self.selected_deck(), decks, popup, self.panel,
                b.language(), caret, self.pressed if self.panel else None)

    def compose(self, popup):
        from PIL import Image
        from unit_browser import ARROW, scaled
        img = Image.new('RGBA', (W, H))
        boxes = []
        with self.deck_mode() as b:
            art = b.art
            # DECK 标签
            selected = self.selected_deck()
            for i, rect in enumerate(self.tab_rects()):
                img.alpha_composite(self.tab_image(i + 1, i == selected, self.deck_ap(i)), rect[:2])
                boxes.append((rect, ('deck', i)))
            # 翻页箭头与页码
            if self.pages > 1:
                arrow = scaled(art.part(ARROW), ARROW_SCALE)
                for box, delta in self.arrow_boxes():
                    sprite = arrow if delta > 0 else arrow.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                    img.alpha_composite(sprite, (box[0] + (box[2] - sprite.width) // 2,
                                                 box[1] + (box[3] - sprite.height) // 2))
                    boxes.append((box, ('page', delta)))
                k, pitch = 2, 18
                page, pages = self.page + 1, self.pages
                width = (len(str(page)) + len(str(pages))) * pitch + 12 * k
                x = W - 22 - width
                x = b.number(img, x, INFO_Y - 11, page, 0, k, pitch, lead=False)
                b.conv_paste(img, 85, x + 1, INFO_Y - 11, k)
                b.number(img, x + 12 * k, INFO_Y - 11, pages, 0, k, pitch, lead=False)
            units = [e['uid'] for e in self.page_items()]
            if not units:
                b.text(img, (W // 2, ICON_Y + ICON_SIZE // 2), b.tr('empty'), 28, anchor='mm')
            if not popup and self.current in units:
                # 信息行（阵营标志、名称、等级、AP）
                entry = self.by_uid[self.current]
                name = entry['name']
                rest = '  LV : %d / AP : %d' % (entry['level'] or 1, entry['ap'])
                font = b.font(26)
                logo = art.logo(entry['faction'])
                name_w, rest_w = font.getlength(name), font.getlength(rest)
                total = (logo.width + 10 if logo is not None else 0) + name_w + rest_w
                left = W / 2 - total / 2
                if logo is not None:
                    img.alpha_composite(logo, (round(left), INFO_Y - logo.height // 2))
                    left += logo.width + 10
                in_deck = self.current in self.deck_units(self.selected_deck())
                color = IN_DECK_COLOR if in_deck else (240, 240, 240, 255)      # 已编入：整行（名称、LV、AP）为绿色
                b.text(img, (left, INFO_Y), name, 26, color, 'lm')
                b.text(img, (left + name_w, INFO_Y), rest, 26, color, 'lm')
            if self.panel:
                img.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, 140)))
                b.icon_lights = {}
                self.panel_boxes = b.compose_panel(img)
        self.boxes = boxes
        return img

    # ---------- 每帧 ----------
    def draw(self):
        """游戏线程，每帧在原生画面之后、单位浏览组件（其闸门）之前调用。"""
        if not self.alive():
            if self.was_alive:
                self.leave()
            return
        p, app = self.p, self.app()
        if not self.was_alive:
            self.was_alive, self.dirty, self.page, self.current, self.panel = True, True, 0, None, False
        self.in_draw = True
        try:
            self.process_commands()
            if self.native_fresh():
                self.rebuild()
            if self.jump is not None:
                self.apply_jump()
        finally:
            self.in_draw = False
        self.hold_scroll()
        self.align_numbers()
        self.update_stamps()
        self.keys_ok = self.panel or self.ready()
        state = p.word(app + 0x22c8)
        first = False
        if self.shut is None and state in (17, 18):
            # 原生闸门（SetShutterClose / SetShutterOpen 的 ChangeNT）：改由本模块在图层之后推进，使闸门画在图层之上。
            self.shut = 'closing' if state == 17 else 'opening'
            p.put(app + 0x22c8, 0)
            first = True
            if self.panel:
                self.close_panel()
        if self.shut == 'closed':
            if state == 18:                              # 未离开场景而再次开闸
                self.shut = None
            return                                       # 合拢后闸门由原生绘制，不叠加图层
        if not (first and self.shut == 'opening'):       # 开闸首帧闸门已由原生画成合拢，不叠加图层
            popup = self.scene() != SCENE_DECK
            self.update_levels(popup)
            self.write_levels()
            if self.overlay is None:
                from trial_overlay import SurfaceOverlay
                self.overlay = SurfaceOverlay(p.graphics)
            key = self.state_key(popup)
            if self.rebuilt and self.overlay.cached is not None and self.shut is None:
                key = self.overlay.cached            # 与本帧原生画出的旧面板一致
            self.rebuilt = False
            image = self.compose(popup) if self.overlay.cached != key else None
            self.overlay.draw_image(image, key, (0, 0, W, H))
        if self.shut in ('closing', 'opening') and not first:
            p.call('_ZN13CTaskSystem2D6CallerEi', app + 0x3830, 5)
            p.call('_ZN11GraphicsOpt9drawStackEv', p.word(app + 124))
            released = not self.shutter_tasks()
            if released or p.call('_ZN7AppMain18IsShutterActionEndEv', app):
                if self.shut == 'closing':               # SC_ShutterClose 的结束步骤；其后交还原生（保持合拢的闸门）
                    p.write(app + 0xc21c, bytes((1, 1)))
                    p.put(app + 0x22c8, 17)
                    self.shut = 'closed'
                else:                                    # SC_ShutterOpen 的结束步骤
                    if not released:
                        p.call('_ZN7AppMain12ClearShutterEv', app)
                    p.write(app + 0xc21d, bytes((0,)))
                    self.shut = None

    def leave(self):
        self.was_alive = False
        self.keys_ok = False
        self.press_icon = None
        self.levels = [0] * PAGE_SIZE
        if self.lit_table:
            self.write_levels()
        self.shut = None
        self.panel = False
        self.pressed = None
        self.sort_press = None
        with self.deck_mode() as b:
            b.search_focus = False
            b.save_state()

    # ---------- SORT 面板 ----------
    def open_panel(self):
        self.panel = True
        self.pressed = None
        with self.deck_mode() as b:
            b.search_focus = False
        self.revision += 1

    def close_panel(self):
        self.panel = False
        self.pressed = None
        with self.deck_mode() as b:
            b.search_focus = False
            b.save_state()
        if self.dirty and self.alive():
            self.page = 0
            self.current = None
            self.rebuild()
        self.revision += 1

    def panel_command(self, command):
        if command == ('panel',):
            return
        if command == ('ok',):
            self.close_panel()
            return
        with self.deck_mode() as b:
            b.command(*command)
            b.panel = None
        self.dirty = True
        self.revision += 1

    def text_input(self, character):
        with self.deck_mode() as b:
            if not (self.panel and b.search_focus):
                return
            s = b.settings
            if character == '\b':
                s['text'] = s['text'][:-1]
            elif character.isprintable() and len(s['text']) < 40:
                s['text'] += character
        self.dirty = True
        self.revision += 1

    def wants_text(self):
        return self.panel and self.browser.search_focus

    def wants_keys(self):
        return self.was_alive and self.keys_ok

    def process_commands(self):
        while self.commands:
            item = self.commands.pop(0)
            if item[0] == 'text':
                self.text_input(item[1])
            elif item[0] == 'key':
                self.key(item[1])
            elif item[0] == 'wheel' and not self.panel and not self.down and self.ready():
                if self.flip(-1 if item[1] > 0 else 1):
                    play_se(self.p, SE_DECIDE)

    def key(self, name):
        if self.panel:
            if name == 'enter':
                play_se(self.p, SE_DECIDE)
                self.close_panel()
            elif name == 'backspace':
                self.text_input('\b')
        elif name in ('left', 'right') and not self.down and self.ready():
            if self.flip(-1 if name == 'left' else 1):
                play_se(self.p, SE_DECIDE)

    def back(self):
        """Esc：面板打开时关闭面板；其余交给原有流程。"""
        if self.was_alive and self.panel:
            play_se(self.p, SE_CLOSE)
            self.close_panel()
            return True
        return False

    # ---------- 输入 ----------
    @staticmethod
    def hit(boxes, x, y):
        for box, command in reversed(boxes):
            left, top, w, h = box
            if left <= x < left + w and top <= y < top + h:
                return command
        return None

    def sort_rect(self):
        from unit_browser import BAR_RIGHT, BAR_Y, BUTTON_SCALE
        return (BAR_RIGHT, BAR_Y, round(60 * BUTTON_SCALE), round(48 * BUTTON_SCALE))

    def touch(self, action, x, y):
        """返回 True 表示触点由本模块受理（不送入原生）。"""
        if action == 1:
            self.down = True
        elif action == 3:
            self.down = False
        if not self.was_alive or not self.alive() or self.browser.busy():
            return False
        if self.panel:
            hit = self.hit(self.panel_boxes, x, y)
            if action == 1:
                self.pressed = hit if hit is not None else ('ok',)
            elif action == 3:
                pressed, self.pressed = self.pressed, None
                if pressed is not None and (hit == pressed or (hit is None and pressed == ('ok',))):
                    if pressed != ('panel',):
                        play_se(self.p, SE_DECIDE)
                    self.panel_command(pressed)
            return True
        if self.shut is not None:
            return True
        from cockpit_hold import instance
        p, app = self.p, self.app()
        inside_sort = self.hit([(self.sort_rect(), True)], x, y)
        if self.sort_press is not None:
            press = self.sort_press
            if action == 5 and not inside_sort and not press['cancelled']:
                press['cancelled'] = True
                self.release_sort(keep=True)
            elif action == 3:
                activate = inside_sort and not press['cancelled'] and self.ready()
                self.release_sort()
                if activate:
                    play_se(p, SE_DECIDE)
                    self.open_panel()
            return True
        if self.pressed is not None:
            if action == 3:
                pressed, self.pressed = self.pressed, None
                if self.ready() and self.hit(self.boxes, x, y) == pressed:
                    if pressed[0] == 'page':
                        if self.flip(pressed[1]):
                            play_se(p, SE_DECIDE)
                    elif pressed[0] == 'deck' and pressed[1] != self.selected_deck():
                        play_se(p, SE_CLOSE)
                        self.select_deck(pressed[1])
            return True
        if action == 3:
            self.press_icon = None
            return False
        if action == 5:
            press = self.press_icon
            if press is not None and not press['started'] and abs(x - press['x']) + abs(y - press['y']) >= DRAG_START:
                press['started'] = self.start_drag(press) or press['uid'] in self.deck_units(self.selected_deck())
            return False
        if action != 1 or not self.ready():
            return False
        if inside_sort:
            task = p.word(app + SLOT_SORT)
            if task:
                self.sort_press = {'task': task, 'cancelled': False}
                instance(p).hold(task)
                return True
        hit = self.hit(self.boxes, x, y)
        if hit is not None:
            self.pressed = hit
            return True
        if RAIL_TOP <= y < RAIL_BOTTOM:
            slot = int((x - RAIL_LEFT) // RAIL_PITCH)
            if 0 <= slot < 10:
                uid = self.deck_units(self.selected_deck())[slot]
                self.jump = uid if uid in self.by_uid else None
            return False
        index = self.icon_at(x, y)
        if index is not None:
            # 按下图标：选中（无音效，2026-11-11 用户试用后决定）；触点照常送入原生（拖动物按原生的触点起点定位），按住移动即拖起
            uid = self.page_items()[index]['uid']
            self.current = uid
            self.press_icon = {'index': index, 'uid': uid, 'x': x, 'y': y, 'started': False}
        return False

    def release_sort(self, keep=False):
        press = self.sort_press
        if press is None:
            return
        from cockpit_hold import instance
        if self.p.word(self.app() + SLOT_SORT) == press['task']:
            instance(self.p).release(press['task'])
        if not keep:
            self.sort_press = None

    def close(self):
        self.overlay = None
