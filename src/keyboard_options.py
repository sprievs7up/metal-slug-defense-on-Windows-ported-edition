"""主菜单 OPTION 页的语言 / 键盘两个半宽按钮与键盘操作模式页（2026-11-10 用户要求）。

- OPTION 页（场景 28 状态 2）第一行（语言面板，任务槽 11）分为左右两段：左为语言设定（打开原生语言窗口），右为键盘设定。
  按钮框沿用历史活动浏览页“上一個 / 下一個”的分段做法（event_browser.row3_image）：drawConv 替换表（LAB 头部 +0xb40）按
  纵坐标 180.0 把褐色框图块换为左右两段等宽、中间透明的合成框（取原生框图块的左右端）；按下的亮框图块换为只含被按半段的
  合成图，透明度沿用面板的原生按压值（任务 +0xd8，每帧 ±64），所以按压白光与原生面板一样渐显、渐隐，且只出现在被按的半段。
- 防误触：语言面板置原生“不受理点击”标记（任务 +0x7c 的 0x20），原生不再为这一行产生按压与选择；两段的点击全部由宿主判定：
  按下时落在哪一段即锁定哪一段，移出该段即取消，只有在同一段内抬起才受理；两段之间的空隙与外缘不属于任何一段。
  语言窗口以原生流程打开（置面板选择标记后调用原生 SelectPanelMainMenu：确定音、OpenLanguageWindow、显像管雪花）。
- 键盘操作模式页：点击键盘设定后，三行按原生离场动作滑出（SetPanelOut），语言、音乐两行改为“经典”“S1XLV”两个选项后按原生
  入场动作滑入（SetPanelIn，逐行延迟 2 帧），音效行隐藏；原生状态仍为 2。当前模式的一行为原生红色框（面板 +0x1b4 = 7，
  GT_MenuPanelDraw 据此取红色图块，与主菜单第一行相同）。点击选项即切换并保存（keyboard_modes.py），留在本页；底栏 BACK
  与 Esc 回到 OPTION 页（两行滑出、恢复原文字与图标后三行滑入）。经其他底栏按钮离开时由原生切换，下次进入 OPTION 为第一层。
  本页期间 audio_options 不改写音乐、音效两行（owns_rows）。以后增加“自定义”时使用第三行（音效行）。
"""
import struct

TABLE, TABLE_MAGIC, TABLE_LIMIT = 0x1ffeb000 + 0xb40, 0x47505356, 16
TILE_NORMAL_CONV, TILE_PRESSED_CONV = 0x1031cfe0, 0x1031cff0    # menuparts.obm 褐色按钮框（常态 y154、按下 y120）
TILE_W, TILE_H, HALF, GAP, CAP = 190, 33, 90, 10, 12               # 图块像素；绘制 2 倍，1280×720 逻辑坐标再 ×1.125
SCALE = 2 * 1.125
ROW_X = (540 + 88.9) * 1.125
ROW_Y = (180.0, 272.0, 364.0)
ROW_RECTS = tuple((ROW_X, y * 1.125, TILE_W * SCALE, TILE_H * SCALE) for y in ROW_Y)
HALF_RECTS = ((ROW_X, ROW_Y[0] * 1.125, HALF * SCALE, TILE_H * SCALE),
              (ROW_X + (HALF + GAP) * SCALE, ROW_Y[0] * 1.125, HALF * SCALE, TILE_H * SCALE))
# 原生面板的点击区（任务位置起 (−10, −9)、400×84）：按下于此而未命中宿主按钮时，整次触点不送入原生。
GUARD_RECTS = tuple(((540 - 10 + 88) * 1.125, (y - 9) * 1.125, 400 * 1.125, 84 * 1.125) for y in ROW_Y)
ROW1_Y_BITS = struct.unpack('<I', struct.pack('<f', ROW_Y[0]))[0]
SLOTS = (11, 12, 13)                                               # 语言、音乐、音效面板的任务槽（app+0x3360 起）
BACK_TASK, BACK_RECT = 0x36d8, (45, 598, 132, 110)
FONT_SIZE = 24                                                     # 面板文字字号（原生文字批次记录）
RIGHT_LABEL_X = (HALF + GAP) * 2                                   # 右半段文字相对左半段文字的起点（原生单位）
SE_DECIDE, SE_CLOSE = 13, 8
SWITCH_LIMIT = 40                                                  # 滑出动作的等待上限（帧）
# 语言代码 → （语言设定、键盘设定、经典）；语言设定取各语言原生面板文字的写法，其余为本项目撰写。
LABELS = {'EN': ('LANGUAGE', 'KEYBOARD', 'CLASSIC'), 'JP': ('言語設定', 'キー設定', 'クラシック'),
          'KR': ('언어 설정', '키 설정', '클래식'), 'ES': ('IDIOMA', 'TECLADO', 'CLÁSICO'), 'PT': ('IDIOMA', 'TECLADO', 'CLÁSSICO'),
          'FR': ('LANGUE', 'CLAVIER', 'CLASSIQUE'), 'DE': ('SPRACHE', 'TASTATUR', 'KLASSISCH'),
          'IT': ('LINGUA', 'TASTIERA', 'CLASSICO'), 'ZS': ('语言设置', '键盘设置', '经典'),
          'ZT': ('語言設定', '鍵盤設定', '經典'), 'RU': ('ЯЗЫК', 'КЛАВИШИ', 'КЛАССИКА')}
S1XLV_LABEL = 'S1XLV'
MODE_ROWS = ('classic', 's1xlv')


def inside(rect, x, y):
    return rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]


class KeyboardOptions:
    def __init__(self, p, keyboard):
        self.p, self.keyboard = p, keyboard
        self.page = 'option'            # 'option'：OPTION 第一层；'keyboard'：键盘操作模式页
        self.switch = None              # 换页中：(目标页, 开始帧)，三行正在滑出
        self.pressed = None             # 'lang'、'keys'、('row', 序号)、'back'
        self.cancelled = False
        self.swallow = False
        self.glow_half = 0              # 最近一次按下的半段（按压白光渐隐期间保持其图块）
        self.strings, self.labels, self.images = {}, {}, {}
        self.codes, self.split_labels = None, {}
        self.native_labels = None       # 已改写的原生面板文字表项：[(地址, 原指针)]
        self.table_base = self.table_total = None
        self.symbols = None
        self.disabled = None            # 出错后停用：恢复原生整行语言按钮，记录错误

    # ---------- 原生对象 ----------
    def functions(self):
        if self.symbols is None:
            s = self.p.symbols
            self.symbols = {name: s[f'_ZN7AppMain{len(name)}{name}EP17GENERAL_TASK_BASE'] & ~1
                            for name in ('GT_MenuPanel', 'GT_MenuPanelIn', 'GT_MenuPanelOut', 'GT_Blank')}
        return self.symbols

    def scene(self):
        p = self.p
        app = p.app_instance()
        if not app:
            return 0, 0, 0
        return app, p.word(app + 0x22bc), p.word(app + 0x22dc)

    def context(self):
        """'menu'：OPTION 页；'popup'：OPTION 页之上的原生弹窗（语言窗口等，面板仍在其后绘制）；其余为 None。"""
        app, scene, state = self.scene()
        if scene == 28 and state == 2:
            return 'menu'
        if scene in (119, 120) and state == 2:
            return 'popup'
        return None

    def tasks(self):
        app, scene, state = self.scene()
        if scene not in (28, 119, 120):
            return (0, 0, 0)                                   # 其他场景复用同一任务槽
        return tuple(self.p.word(app + 0x3360 + slot * 4) for slot in SLOTS)

    def function(self, task):
        if not 0x10000000 <= task < 0x1ffff000:
            return None
        value = self.p.word(task) & ~1
        return next((name for name, address in self.functions().items() if address == value), None)

    def drawn(self, task):
        """下一帧原生是否绘制该面板：常态、离场动作中，或入场动作的延迟已结束；隐藏标记（0x80）置位时不绘制。"""
        name = self.function(task)
        if name is None or name == 'GT_Blank' or self.p.word(task + 0x7c) & 0x80:
            return False
        return name != 'GT_MenuPanelIn' or self.p.word(task + 104) == 0

    def settled(self, task):
        return self.function(task) == 'GT_MenuPanel' and not self.p.word(task + 0x7c) & 0x80

    def owns_rows(self):
        """键盘操作模式页借用音乐、音效两行期间为真（audio_options 据此不改写这两行）。"""
        return self.page == 'keyboard'

    # ---------- 文字与图块 ----------
    def language_codes(self):
        """原生语言编号 → 语言代码。"""
        if self.codes is None:
            import content_locale
            self.codes = content_locale.language_codes(self.p)
        return self.codes

    def code(self):
        p = self.p
        return self.language_codes().get(p.word(p.app_instance() + 0x3d64), 'EN')

    def split_label(self, code=None):
        """第一行文字：语言设定保持原生位置，键盘设定以空格推到右半段的同一相对位置（按该语言的面板字体测量）。"""
        code = code or self.code()
        if code not in self.split_labels:
            from text_render import font_for
            left, right, _ = LABELS.get(code, LABELS['EN'])
            index = next((i for i, c in self.language_codes().items() if c == code), 0)
            font = font_for(self.p, FONT_SIZE, index)
            space = max(1.0, font.getlength(' '))
            self.split_labels[code] = left + ' ' * max(1, round((RIGHT_LABEL_X - font.getlength(left)) / space)) + right
        return self.split_labels[code]

    def cstring(self, text):
        if text not in self.strings:
            self.strings[text] = self.p.cstr(text)
        return self.strings[text]

    def patch_native_labels(self):
        """原生面板文字表 strMenuPanelTbl[语言][4]（语言面板，GetStringMenuPanel 读取）改指各语言的两段文字：原生重建面板文字
        （切换语言后的 SetPanelStringAll，在原生一帧之内执行并绘制）时直接得到两段文字，不出现只有原文的一帧。"""
        if self.native_labels is not None:
            return
        p = self.p
        table = p.symbols['strMenuPanelTbl']
        self.native_labels = []
        for index, code in sorted(self.language_codes().items()):
            row = p.word(table + index * 4)
            if 0x10000000 <= row < 0x1ffff000:
                address = row + (SLOTS[0] - 7) * 4
                self.native_labels.append((address, p.word(address)))
                p.put(address, self.cstring(self.split_label(code)))

    def restore_native_labels(self):
        for address, original in self.native_labels or ():
            self.p.put(address, original)
        self.native_labels = None

    def set_label(self, slot, task, text):
        p = self.p
        if self.labels.get(slot) == (task, text, p.word(task + 0x1f8)):
            return
        app = p.app_instance()
        p.call('_ZN9TexString13setStringCharEPKcPiP4Fontb', p.word(app + 0x3238), self.cstring(text), task + 0x1f8,
               p.word(app + 0x60), 0)
        self.labels[slot] = (task, text, p.word(task + 0x1f8))

    def tile(self, y):
        from pathlib import Path
        from PIL import Image
        import probe as probe_module
        if 'atlas' not in self.images:
            raw = (Path(probe_module.RESOURCE_ROOT) / 'com.snkplaymore.android003' / 'menuparts.obm').read_bytes()
            w, h = struct.unpack_from('<HH', raw, 4)
            self.images['atlas'] = Image.frombytes('RGBA', (w, h), raw[8:8 + w * h * 4])
        return self.images['atlas'].crop((0, y, TILE_W, y + TILE_H))

    def split_image(self, pressed):
        """pressed 为 None：左右两段常态框；为 0 / 1：只含该半段的按下亮框（另一半透明）。各段取原生框图块的左右端。"""
        if pressed not in self.images:
            from PIL import Image
            from lab_versus import create_native_image
            source = self.tile(154 if pressed is None else 120)
            out = Image.new('RGBA', (TILE_W, TILE_H), (0, 0, 0, 0))
            for side in ((0, 1) if pressed is None else (pressed,)):
                half = Image.new('RGBA', (HALF, TILE_H), (0, 0, 0, 0))
                half.paste(source.crop((0, 0, HALF - CAP, TILE_H)), (0, 0))
                half.paste(source.crop((TILE_W - CAP, 0, TILE_W, TILE_H)), (HALF - CAP, 0))
                out.paste(half, (side * (HALF + GAP), 0))
            self.images[pressed] = create_native_image(self.p, out)
        return self.images[pressed]

    # ---------- drawConv 替换表（与历史活动浏览页等共用：在其表项之后追加，离开时只撤回本模块的部分） ----------
    def write_table(self, entries):
        p = self.p
        active = p.word(TABLE) == TABLE_MAGIC
        count = min(p.word(TABLE + 4), TABLE_LIMIT) if active else 0
        base = self.table_base if active and self.table_base is not None and count == self.table_total else count
        if base + len(entries) > TABLE_LIMIT:
            return
        for i, (conv, image) in enumerate(entries, base):
            e = TABLE + 0x10 + i * 32
            p.put(e, conv)
            p.put(e + 4, 0)
            p.put(e + 8, image)
            p.put(e + 12, ROW1_Y_BITS)
            p.write(e + 16, struct.pack('<8h', 0, 0, TILE_W, TILE_H, 0, 0, 0, 0))
        p.put(TABLE + 4, base + len(entries))
        p.put(TABLE, TABLE_MAGIC)
        self.table_base, self.table_total = base, base + len(entries)

    def clear_table(self):
        if self.table_base is None:
            return
        p = self.p
        if p.word(TABLE) == TABLE_MAGIC and p.word(TABLE + 4) == self.table_total:
            if self.table_base:
                p.put(TABLE + 4, self.table_base)
            else:
                p.put(TABLE, 0)
        self.table_base = self.table_total = None

    # ---------- 每帧 ----------
    def apply(self):
        """按当前页维持面板的点击标记、红色框、文字与分段框（原生步进前后各调用一次，写入相同内容）。"""
        p = self.p
        context = self.context()
        language, music, effects = self.tasks()
        if context is None or not language:
            if language and self.page == 'option' and self.drawn(language):
                self.write_split()                           # 离开 OPTION：语言行滑出期间保持分段框
            else:
                self.clear_table()
                if not (language and self.drawn(language)):
                    self.reset()
            return
        p.put(language + 0x7c, p.word(language + 0x7c) | 0x20)
        self.patch_native_labels()
        if self.page == 'keyboard':
            mode = self.keyboard.mode
            labels = LABELS.get(self.code(), LABELS['EN'])
            for slot, task, text, name in ((SLOTS[0], language, labels[2], 'classic'), (SLOTS[1], music, S1XLV_LABEL, 's1xlv')):
                if not task:
                    continue
                # +0x1b4：7 为原生红色框；12 / 13 会在文字后画喇叭图标，未选中的一行统一取语言面板的值（褐色框、无图标）。
                p.put(task + 0x1b4, 7 if mode == name else SLOTS[0])
                self.set_label(slot, task, text)
            if music:
                p.put(music + 0x7c, (p.word(music + 0x7c) & ~0x80) | 0x20)
            if effects:
                p.put(effects + 0x7c, p.word(effects + 0x7c) | 0xa0)
            self.clear_table()
            return
        p.put(language + 0x1b4, SLOTS[0])
        self.set_label(SLOTS[0], language, self.split_label())
        if self.drawn(language):
            self.write_split()
        else:
            self.clear_table()

    def write_split(self):
        self.write_table([(TILE_NORMAL_CONV, self.split_image(None)), (TILE_PRESSED_CONV, self.split_image(self.glow_half))])

    def reset(self):
        """离开 OPTION 且面板不再绘制：回到第一层，文字记录作废（下次进入时重新设置）。"""
        if self.page != 'option' or self.switch is not None or self.pressed is not None or self.labels:
            self.release_back()
            self.page, self.switch, self.pressed, self.cancelled, self.swallow = 'option', None, None, False, False
            self.labels = {}

    def prepare_frame(self):
        """原生步进之前：维持面板状态，并为按住的按钮写入按压白光（原生每帧在未按压时减 64，预先加回并递增）。"""
        if self.disabled:
            return
        try:
            self.apply()
            task = self.pressed_task()
            if task:
                p = self.p
                p.put(task + 0xd8, min(255, p.word(task + 0xd8) + 64) + 64)
        except Exception as error:
            self.fail(error)

    def update(self):
        """原生步进之后（audio_options.update 之后）：推进换页，再维持面板状态。"""
        if self.disabled:
            return
        try:
            if self.switch is not None:
                self.advance_switch()
            self.apply()
        except Exception as error:
            self.fail(error)

    def fail(self, error):
        """出错：记录并停用本模块，语言面板恢复为原生整行按钮（原生受理点击、不分段）。"""
        import traceback
        self.disabled = f'{type(error).__name__}: {error}'
        self.p.log('KEYBOARD_OPTIONS_ERROR', self.disabled, traceback.format_exc())
        try:
            self.page, self.switch, self.pressed = 'option', None, None
            self.clear_table()
            self.restore_native_labels()
            language = self.tasks()[0]
            if language:
                p = self.p
                p.put(language + 0x7c, p.word(language + 0x7c) & ~0x20)
                p.put(language + 0x1b4, SLOTS[0])
        except Exception:
            pass

    # ---------- 换页 ----------
    def panel_out(self, slots):
        p = self.p
        app = p.app_instance()
        for slot in slots:
            p.call('_ZN7AppMain11SetPanelOutEi', app, slot)

    def open_page(self):
        self.play(SE_DECIDE)
        self.panel_out(SLOTS)
        self.switch = ('keyboard', self.p.frame)
        self.p.log('KEYBOARD_PAGE_OPEN', self.p.frame)

    def close_page(self):
        self.play(SE_CLOSE)
        self.panel_out(SLOTS[:2])
        self.switch = ('option', self.p.frame)
        self.p.log('KEYBOARD_PAGE_CLOSE', self.p.frame)

    def advance_switch(self):
        p = self.p
        if self.context() != 'menu':
            return                                           # 已离开 OPTION：由 apply / reset 处理
        target, started = self.switch
        tasks = self.tasks()
        if any(self.drawn(task) for task in tasks if task) and p.frame - started < SWITCH_LIMIT:
            return
        app = p.app_instance()
        self.page, self.switch = target, None
        self.apply()                                         # 文字、红色框与显示标记先于入场动作
        for index, slot in enumerate(SLOTS if target == 'option' else SLOTS[:2]):
            p.call('_ZN7AppMain10SetPanelInEii', app, slot, index * 2)
        p.log('KEYBOARD_PAGE', target, p.frame)

    def select_mode(self, index):
        self.play(SE_DECIDE)
        self.keyboard.set_mode(MODE_ROWS[index])
        self.apply()

    def open_language(self):
        """原生流程：语言面板置选择标记，由 SelectPanelMainMenu 受理（确定音 8、OpenLanguageWindow、清除标记）。"""
        p = self.p
        app = p.app_instance()
        language = self.tasks()[0]
        p.put(language + 0x194, 1)
        try:
            p.call('_ZN7AppMain19SelectPanelMainMenuEv', app)
        finally:
            p.call('_ZN7AppMain16ClearSelectPanelEP17GENERAL_TASK_BASEi', app, language, 0)
        p.log('KEYBOARD_OPTIONS_LANGUAGE', p.frame)

    def play(self, sound):
        p = self.p
        p.call('_ZN7AppMain23Sound_RequestPlayMenuSEE7SoundID', p.app_instance(), sound)

    # ---------- 输入 ----------
    def rect(self, key):
        if key == 'lang':
            return HALF_RECTS[0]
        if key == 'keys':
            return HALF_RECTS[1]
        if key == 'back':
            return BACK_RECT
        return ROW_RECTS[key[1]]

    def pressed_task(self):
        """按住且未取消的面板按钮所属的任务（按压白光）；底栏 BACK 另以 cockpit_hold 处理。"""
        key = self.pressed
        if key is None or key == 'back' or self.cancelled:
            return 0
        tasks = self.tasks()
        return tasks[0] if key in ('lang', 'keys') else tasks[key[1]]

    def set_back_pressed(self, down):
        from cockpit_hold import instance
        p = self.p
        task = p.word(p.app_instance() + BACK_TASK)
        if task:
            (instance(p).hold if down else instance(p).release)(task)

    def release_back(self):
        if self.pressed == 'back':
            self.set_back_pressed(False)

    def hit(self, x, y):
        """按下位置对应的宿主按钮；None 为未命中。面板须已就位（入场、离场动作中不受理）。"""
        language, music, effects = self.tasks()
        if self.switch is not None:
            return None
        if self.page == 'option':
            if self.settled(language):
                for key in ('lang', 'keys'):
                    if inside(self.rect(key), x, y):
                        return key
            return None
        for index, task in enumerate((language, music)):
            if self.settled(task) and inside(ROW_RECTS[index], x, y):
                return ('row', index)
        return 'back' if inside(BACK_RECT, x, y) else None

    def guarded(self, x, y):
        """未命中宿主按钮的按下是否仍由本模块吞掉：第一行的原生点击区；键盘页与换页中另含其余两行与底栏 BACK。"""
        if inside(GUARD_RECTS[0], x, y):
            return True
        if self.page == 'keyboard' or self.switch is not None:
            return any(inside(rect, x, y) for rect in GUARD_RECTS[1:]) or inside(BACK_RECT, x, y)
        return False

    def touch(self, action, x, y):
        """返回 True 表示触点已由本模块处理（不送入原生）。"""
        if self.disabled:
            return False
        try:
            return self.handle_touch(action, x, y)
        except Exception as error:
            self.fail(error)
            return False

    def handle_touch(self, action, x, y):
        if self.context() != 'menu':
            if action == 3:
                self.release_back()
                self.pressed, self.cancelled, self.swallow = None, False, False
            return False
        if action == 1:
            self.release_back()
            self.pressed, self.cancelled, self.swallow = self.hit(x, y), False, False
            if self.pressed is None:
                self.swallow = self.guarded(x, y)
                return self.swallow
            if self.pressed == 'back':
                self.set_back_pressed(True)
            elif self.pressed in ('lang', 'keys'):
                self.glow_half = 0 if self.pressed == 'lang' else 1
            return True
        if self.pressed is None:
            if self.swallow:
                if action == 3:
                    self.swallow = False
                return True
            return False
        key = self.pressed
        if action == 5:
            if not self.cancelled and not inside(self.rect(key), x, y):
                self.cancelled = True                        # 移出按钮：取消（白光由原生逐帧渐隐）
                self.release_back()
            return True
        if action == 3:
            activate = not self.cancelled and inside(self.rect(key), x, y)
            self.release_back()
            self.pressed, self.cancelled = None, False
            if activate and self.switch is None:
                if key == 'lang':
                    self.open_language()
                elif key == 'keys':
                    self.open_page()
                elif key == 'back':
                    self.close_page()
                else:
                    self.select_mode(key[1])
            return True
        return True

    def back(self):
        """Esc：键盘操作模式页回到 OPTION 页；换页中消费输入。其余情形交给原生。"""
        if self.disabled or self.context() != 'menu':
            return False
        if self.switch is not None:
            return True
        if self.page == 'keyboard':
            self.close_page()
            return True
        return False
