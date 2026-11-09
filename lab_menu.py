"""LAB / VS CPU / 本地双人对战的战斗中菜单：原生暂停页风格的宿主面板，打开期间暂停战斗（2026-11-07 重新设计）。

GameMode 1 中原生暂停页不可用；打开菜单时置 BattleGameMaster+0x1c（暂停标记，战斗模拟随之停止，原生不显示暂停界面），
关闭时还原。
- 大界面：用户以原版 pause_window.obm 制作（PANEL，1920×1440，为 1280×720 的 2 倍画布、原版图集像素的 4.5 倍），
  绘制于 PANEL_RECT（960×720，水平居中、贴齐画面顶边），与原生暂停页同为 2.25 倍；标题 PAUSE MENU 在图中。
- 按钮：原版 menuparts.obm 按钮，高度 23 不变、横向三段拉伸（两端各 5 图集像素）。开 = 深绿、关 = 深红、一般 = 棕；键盘选中用
  同色系浅色版（浅绿、粉红、米色），文字与图标改深色；按下时下移 2 像素并压暗。表头与功能名为 pause_window.obm 深色条加绿字。
- 文字：与原生文字渲染相同的字体（简体 msyh、繁体 msjh、日语 msgothic、英语 arial），超出格宽时缩小字号。
  音乐 / 音效按钮为“名称：开 / 关”加原生暂停页的喇叭图标（SPEAKER，取自 2560×1440 下的原生画面）。
- LAB：左块 AI 设定、右块战斗设定（行 = 功能，列 = 我方 / 敌方，LAB_BLOCKS），其下音乐 / 音效与重新开始、返回准备界面、继续。
  新功能在 LAB_BLOCKS 中追加一行（每块最多 4 行，2026-11-09 起两块均已满）。VS CPU 与本地对战：原生暂停页的 5 行单列。
- 操作：鼠标点击（按下显示按下状态，同一项上抬起执行）；↑/↓/←/→ 移动选择、Enter 执行、Esc 打开 / 关闭（手柄同）。
  打开时选中“继续”。打开时自上方滑入（OPEN_FRAMES，略有回弹），关闭时上移滑出（CLOSE_FRAMES）；打开 / 选择播放原生确定音，
  关闭播放原生关闭音。背景不压暗（同原生暂停页）。
- 绘制：按面板在窗口表面上的实际像素尺寸生成图像（静态层与各按钮图分别缓存），由 SurfaceOverlay 1:1 绘制。
布局坐标为 2 倍画布像素（PANEL 的像素），说明见 docs/lab/HANDOFF_LAB_UI.md 第 2.30 节。
"""
from pathlib import Path

from lab_ui import SE_CLOSE, SE_DECIDE, Skin, T, lang, play_se

PANEL_DIR = 'artwork/pause_menu_20261107'
PANEL_RECT = (160, 0, 960, 720)            # 逻辑坐标（1280×720）
CANVAS = (1920, 1440)                      # PANEL 像素 = 逻辑 × 2
K = 4.5                                    # 画布像素 / 原版图集像素
AUDIO_ROWS = (('menu_music', 0x3d5c), ('menu_effects', 0x3d60))   # app 偏移（audio_options.MUSIC / EFFECTS）
OPEN_FRAMES, CLOSE_FRAMES = 12, 8
GREEN_TEXT, WHITE, DARK = (12, 140, 50, 255), (240, 240, 240, 255), (45, 38, 26, 255)
# 原版按钮（menuparts.obm，图集像素）：普通与键盘选中（同色系浅色版）
BUTTONS = {'brown': (191, 144, 190, 23), 'brown_sel': (191, 120, 190, 23),
           'on': (191, 192, 90, 23), 'on_sel': (191, 168, 90, 23),
           'off': (282, 168, 90, 23), 'off_sel': (191, 216, 90, 23)}
BAR = (0, 278, 227, 22)                    # pause_window.obm 深色条（OPTION），取两端与无字段作表头底板
FONT_FILES = {'ZS': (('msyh.ttc', 'msjh.ttc', 'arial.ttf'), ('msyhbd.ttc', 'msyh.ttc', 'arialbd.ttf')),
              'ZT': (('msjh.ttc', 'msyh.ttc', 'arial.ttf'), ('msjhbd.ttc', 'msjh.ttc', 'arialbd.ttf')),
              'JP': (('msgothic.ttc', 'msjh.ttc', 'arial.ttf'), ('msgothic.ttc', 'msjh.ttc', 'arialbd.ttf')),
              'EN': (('arial.ttf',), ('arialbd.ttf', 'arial.ttf'))}
# 布局（画布像素）：米色内区 x 140–1777、y 339–1274，夹扣下沿约 y 355；内容区左右各留约 50。
X0, X1 = 190, 1730
USABLE_Y0, USABLE_Y1 = 375, 1255
ROW_H = 104                                # 原版按钮高 23 × 4.5
BLOCK_GAP, CELL_W, CELL_GAP, ROW_GAP = 40, 148, 12, 8
BLOCK_W = (X1 - X0 - BLOCK_GAP) // 2       # 750
LABEL_W = BLOCK_W - 2 * (CELL_W + CELL_GAP)   # 430
LOWER_GAP, LOWER_PITCH, LOWER_SPACING = 44, 128, 30
VS_W, VS_PITCH = round(190 * K), round(34 * K)   # 原生暂停页按钮宽 190、行距 34
SIDES = ('player', 'enemy')
# LAB 表格：(块标题, ((功能名, 开关属性后缀), ...))；属性为 player/enemy + 后缀。
LAB_BLOCKS = (('menu_ai_group', (('menu_ai_deploy', '_ai'), ('menu_ai_special', '_auto_special'),
                                 ('menu_ai_support', '_ai_slug'), ('stop_activity', '_stop'))),
              ('menu_rule_group', (('unlimited_ap', '_unlimited_ap'), ('no_cooldown', '_no_cooldown'),
                                   ('unlimited_support', '_unlimited_support'), ('unlimited_special', '_unlimited_special'))))


class Item:
    """一个可选项：rect 为画布坐标；nav 为 (导航行, 中心 x)；state 为开关状态（None 为指令按钮）。"""

    def __init__(self, command, rect, nav, state=None, label=None, icon=None, kind='brown'):
        self.command, self.rect, self.nav, self.state = command, rect, nav, state
        self.label, self.icon, self.kind = label, icon, kind


class LabMenu:
    def __init__(self, lab):
        self.lab = lab
        self.open = False
        self.closing = False
        self.frame = 0
        self.selected = 0
        self.paused_by_menu = False
        self.overlay = None
        self.skin = Skin(lab)
        self.rect = None
        self.revision = 0
        self.pressed = None
        self.hitboxes = []
        self.cache = {}
        self.fonts = {}
        self.static_key = self.static = None

    # ---------- 项目与布局 ----------
    def lab_layout(self):
        lab = self.lab
        return not (lab.vs_battle() or lab.cpu_battle())

    def items(self):
        lab, p = self.lab, self.lab.p
        app = p.app_instance()
        audio = [(name, offset, bool(p.word(app + offset))) for name, offset in AUDIO_ROWS]
        commands = (('restart', ('restart',)), ('exit_lab', ('exit',)), ('resume', ('close',)))
        items = []
        if self.lab_layout():
            y0, rows = self.lab_top()
            for b, (_, block) in enumerate(LAB_BLOCKS):
                bx = X0 + b * (BLOCK_W + BLOCK_GAP)
                for r, (_, suffix) in enumerate(block):
                    y = y0 + (r + 1) * (ROW_H + ROW_GAP)
                    for c, side in enumerate(SIDES):
                        x = bx + LABEL_W + CELL_GAP + c * (CELL_W + CELL_GAP)
                        attr = side + suffix
                        items.append(Item(('toggle', attr), (x, y, CELL_W, ROW_H), (r, x + CELL_W / 2),
                                          bool(getattr(lab, attr))))
            ly = y0 + rows * ROW_H + (rows - 1) * ROW_GAP + LOWER_GAP
            half = (X1 - X0 - LOWER_SPACING) // 2
            for i, (name, offset, on) in enumerate(audio):
                x = X0 + i * (half + LOWER_SPACING)
                items.append(Item(('audio', offset), (x, ly, half, ROW_H), (rows, x + half / 2), on, name, True))
            third = (X1 - X0 - 2 * LOWER_SPACING) // 3
            for i, (name, command) in enumerate(commands):
                x = X0 + i * (third + LOWER_SPACING)
                items.append(Item(command, (x, ly + LOWER_PITCH, third, ROW_H), (rows + 1, x + third / 2), None, name))
        else:
            x = (CANVAS[0] - VS_W) // 2
            y0 = USABLE_Y0 + (USABLE_Y1 - USABLE_Y0 - (4 * VS_PITCH + ROW_H)) // 2
            rows = [(('audio', offset), on, name, True) for name, offset, on in audio]
            rows += [(command, None, name, False) for name, command in commands]
            for i, (command, state, name, icon) in enumerate(rows):
                items.append(Item(command, (x, y0 + i * VS_PITCH, VS_W, ROW_H), (i, CANVAS[0] / 2), state, name, icon))
        return items

    def lab_top(self):
        """LAB 表格首行 y 与表格行数（含表头）：表格、音频行与指令行整体在内区纵向居中。"""
        rows = 1 + max(len(block) for _, block in LAB_BLOCKS)
        height = rows * ROW_H + (rows - 1) * ROW_GAP + LOWER_GAP + ROW_H + LOWER_PITCH
        return USABLE_Y0 + (USABLE_Y1 - USABLE_Y0 - height) // 2, rows

    # ---------- 打开与关闭 ----------
    def prewarm(self):
        """开战时预先生成当前模式、语言与窗口尺寸的面板图与按钮图（约 0.1 秒，由开战载入掩盖），首次按 Esc 时不再生成。
        失败时只记录，打开菜单时照常生成。"""
        try:
            size = self.lab.p.graphics.surface_rect(PANEL_RECT)[2:]
            if size[0] and size[1]:
                items = self.items()
                self.selected = next((i for i, item in enumerate(items) if item.command == ('close',)), 0)
                self.render(items, size)
        except Exception as error:
            self.lab.record('menu_prewarm_error', error=repr(error))

    def set_open(self, value, animate=True):
        p = self.lab.p
        master = p.call('_ZN16BattleGameMaster11getInstanceEv')
        if value and not self.open:
            self.open, self.closing, self.frame, self.pressed = True, False, 0, None
            items = self.items()
            self.selected = next((i for i, item in enumerate(items) if item.command == ('close',)), 0)
            play_se(p, SE_DECIDE)
            if master and not p.read(master + 0x1c, 1)[0]:
                p.write(master + 0x1c, b'\x01')
                self.paused_by_menu = True
        elif not value and self.open:
            if animate and not self.closing:
                self.closing, self.frame = True, 0
                play_se(p, SE_CLOSE)
                return
            self.open = self.closing = False
            if self.paused_by_menu and master:
                p.write(master + 0x1c, b'\x00')
            self.paused_by_menu = False
        self.revision += 1

    # ---------- 输入 ----------
    def move(self, step):
        """上下：移到上一 / 下一导航行中与当前项中心最近的项（首尾循环）。"""
        items = self.items()
        current = items[self.selected % len(items)]
        rows = sorted({item.nav[0] for item in items})
        row = rows[(rows.index(current.nav[0]) + step) % len(rows)]
        candidates = [i for i, item in enumerate(items) if item.nav[0] == row]
        self.selected = min(candidates, key=lambda i: abs(items[i].nav[1] - current.nav[1]))
        self.revision += 1

    def move_h(self, step):
        """左右：同一导航行内移到左 / 右一项（首尾循环）。"""
        items = self.items()
        current = items[self.selected % len(items)]
        row = sorted((i for i, item in enumerate(items) if item.nav[0] == current.nav[0]), key=lambda i: items[i].nav[1])
        self.selected = row[(row.index(self.selected % len(items)) + step) % len(row)]
        self.revision += 1

    def activate(self, index=None):
        index = self.selected if index is None else index
        command = self.items()[index].command
        if command[0] == 'close':
            self.set_open(False)
        else:
            play_se(self.lab.p, SE_DECIDE)
            self.lab.menu_command(command)
        self.revision += 1

    def touch(self, action, x, y):
        """返回 True 表示触点已由菜单处理（菜单打开期间一律拦截）。按下显示按下状态，同一项上抬起执行。"""
        if not self.open:
            return False
        if self.closing or not self.rect:
            return True
        hit = None
        for (left, top, w, h), index in self.hitboxes:
            if left <= x < left + w and top <= y < top + h:
                hit = index
        if action == 1:
            self.pressed = hit
            self.revision += 1
        elif action == 3:
            pressed, self.pressed = self.pressed, None
            self.revision += 1
            if hit is not None and hit == pressed:
                self.selected = hit
                self.activate(hit)
        return True

    # ---------- 绘制 ----------
    def draw(self):
        if not self.open:
            return
        g = self.lab.p.graphics
        size = g.surface_rect(PANEL_RECT)[2:]
        if not size[0] or not size[1]:
            return
        if self.overlay is None:
            from trial_overlay import SurfaceOverlay
            self.overlay = SurfaceOverlay(g)
        self.frame += 1
        left, top, w, h = PANEL_RECT
        if self.closing:
            t = min(1.0, self.frame / CLOSE_FRAMES)
            offset = -(h + 8) * t * t
        else:
            u = min(1.0, self.frame / OPEN_FRAMES) - 1   # easeOutBack（c1 = 0.5，回弹约 6 像素）
            offset = -(h + 8) * (1 - (1 + 1.5 * u ** 3 + 0.5 * u ** 2))
        self.rect = (left, top, w, h)
        items = self.items()
        key = ('lab_menu', size, self.lab_layout(), lang(self.lab.p), tuple(i.state for i in items), self.selected,
               self.pressed)
        image = None
        if self.overlay.cached != key:
            image = self.render(items, size)
        self.hitboxes = [((left + item.rect[0] / 2, top + item.rect[1] / 2, item.rect[2] / 2, item.rect[3] / 2), index)
                         for index, item in enumerate(items)]
        self.overlay.draw_image(image, key, (left, round(top + offset), w, h))
        if self.closing and self.frame >= CLOSE_FRAMES:
            self.set_open(False, animate=False)

    def render(self, items, size):
        from PIL import ImageEnhance
        s = size[0] / CANVAS[0]
        image = self.static_layer(size).copy()
        for index, item in enumerate(items):
            selected = index == self.selected % len(items)
            element = self.element(item, selected, s)
            x, y = round(item.rect[0] * s), round(item.rect[1] * s)
            if self.pressed == index:
                dark = ImageEnhance.Brightness(element).enhance(0.7)
                dark.putalpha(element.split()[3])
                element, y = dark, y + max(1, round(4 * s))
            image.alpha_composite(element, (x, y))
        return image

    def static_layer(self, size):
        """面板与表格的表头、功能名（不随状态变化），按目标尺寸缓存。"""
        from PIL import Image
        key = (size, self.lab_layout(), lang(self.lab.p))
        if self.static_key == key:
            return self.static
        canvas = Image.open(Path(self.lab.root) / PANEL_DIR / 'pause_panel.png').convert('RGBA')
        p = self.lab.p
        if self.lab_layout():
            y0, _ = self.lab_top()
            for b, (title, block) in enumerate(LAB_BLOCKS):
                bx = X0 + b * (BLOCK_W + BLOCK_GAP)
                self.plate(canvas, (bx, y0, LABEL_W, ROW_H), T(p, title), 46, 36)
                for c, side in enumerate(SIDES):
                    x = bx + LABEL_W + CELL_GAP + c * (CELL_W + CELL_GAP)
                    self.plate(canvas, (x, y0, CELL_W, ROW_H), T(p, 'adv_' + side), 40, 16)
                for r, (name, _) in enumerate(block):
                    self.plate(canvas, (bx, y0 + (r + 1) * (ROW_H + ROW_GAP), LABEL_W, ROW_H), T(p, name), 40, 36)
        self.static_key, self.static = key, canvas.resize(size, Image.LANCZOS)
        return self.static

    def plate(self, canvas, rect, text, size, pad):
        x, y, w, h = rect
        canvas.alpha_composite(self.header_bar(w), (x, y))
        self.text_center(canvas, rect, text, self.fit(text, w - pad, size, True), GREEN_TEXT)

    def element(self, item, selected, s):
        """按钮图（画布分辨率生成后缩到目标尺寸），按外观缓存。"""
        from PIL import Image
        p = self.lab.p
        if item.label is None:                                    # 表格开关格
            kind, text = ('on' if item.state else 'off'), T(p, 'on' if item.state else 'off')
        elif item.state is None:
            kind, text = 'brown', T(p, item.label)
        else:
            colon = ': ' if lang(p) == 'EN' else '：'
            kind, text = 'brown', T(p, item.label) + colon + T(p, 'on' if item.state else 'off')
        kind += '_sel' if selected else ''
        key = ('element', kind, item.rect[2], text, item.icon and item.state, round(s, 4), lang(p))
        if key in self.cache:
            return self.cache[key]
        w = item.rect[2]
        image = self.button(kind, w)
        color = DARK if selected else WHITE
        if item.icon:
            icon = self.speaker(bool(item.state), color)
            font = self.fit(text, w - 60 - icon.width, 52, False)
            self.text_with_icon(image, text, font, icon, color)
        else:
            self.text_center(image, (0, 0, w, ROW_H), text, self.fit(text, w - 28, 48 if item.label is None else 52, False),
                             color)
        image = image.resize((max(1, round(w * s)), max(1, round(ROW_H * s))), Image.LANCZOS)
        self.cache[key] = image
        return image

    # ---------- 素材与文字 ----------
    def three_slice(self, src, w, cap):
        from PIL import Image
        sw, sh = src.size
        cw = round(cap * K)
        left = src.crop((0, 0, cap, sh)).resize((cw, ROW_H), Image.NEAREST)
        right = src.crop((sw - cap, 0, sw, sh)).resize((cw, ROW_H), Image.NEAREST)
        mid = src.crop((cap, 0, sw - cap, sh)).resize((max(1, w - 2 * cw), ROW_H), Image.NEAREST)
        out = Image.new('RGBA', (w, ROW_H))
        out.paste(left, (0, 0))
        out.paste(mid, (cw, 0))
        out.paste(right, (w - cw, 0))
        return out

    def button(self, kind, w):
        x, y, bw, bh = BUTTONS[kind]
        return self.three_slice(self.skin.atlas('menuparts.obm').crop((x, y, x + bw, y + bh)), w, 5)

    def header_bar(self, w):
        from PIL import Image
        x, y, bw, bh = BAR
        src = self.skin.atlas('pause_window.obm').crop((x, y, x + bw, y + bh))
        blank = Image.new('RGBA', (60, bh))             # 两端 30 像素无字，拼成无字的条
        blank.paste(src.crop((0, 0, 30, bh)), (0, 0))
        blank.paste(src.crop((bw - 30, 0, bw, bh)), (30, 0))
        return self.three_slice(blank, w, 4)

    def speaker(self, on, color):
        from PIL import Image
        key = ('speaker', on, color)
        if key not in self.cache:
            icon = Image.open(Path(self.lab.root) / PANEL_DIR / ('speaker_on.png' if on else 'speaker_off.png')).convert('RGBA')
            tinted = Image.new('RGBA', icon.size, color[:3] + (255,))
            tinted.putalpha(icon.split()[3])
            self.cache[key] = tinted
        return self.cache[key]

    def font(self, size, bold):
        from PIL import ImageFont
        from text_render import FONT_DIR
        key = (lang(self.lab.p), size, bold)
        if key not in self.fonts:
            names = FONT_FILES.get(key[0], FONT_FILES['EN'])[1 if bold else 0]
            path = next((FONT_DIR / n for n in names if (FONT_DIR / n).is_file()), None)
            self.fonts[key] = ImageFont.truetype(str(path), size) if path else ImageFont.load_default()
        return self.fonts[key]

    def fit(self, text, width, size, bold):
        """width 内放得下 text 的最大字号（不超过 size，最小 20）。"""
        from PIL import Image, ImageDraw
        draw = ImageDraw.Draw(Image.new('L', (1, 1)))
        for value in range(size, 20, -1):
            font = self.font(value, bold)
            box = draw.textbbox((0, 0), text, font=font)
            if box[2] - box[0] <= width:
                return font
        return self.font(20, bold)

    @staticmethod
    def text_center(image, rect, text, font, fill):
        from PIL import ImageDraw
        x, y, w, h = rect
        draw = ImageDraw.Draw(image)
        box = draw.textbbox((0, 0), text, font=font)
        draw.text((x + (w - (box[2] - box[0])) / 2 - box[0], y + (h - (box[3] - box[1])) / 2 - box[1]), text, font=font,
                  fill=fill)

    @staticmethod
    def text_with_icon(image, text, font, icon, fill):
        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)
        box = draw.textbbox((0, 0), text, font=font)
        gap = 18
        total = box[2] - box[0] + gap + icon.width
        x = (image.width - total) / 2
        draw.text((x - box[0], (image.height - (box[3] - box[1])) / 2 - box[1]), text, font=font, fill=fill)
        image.alpha_composite(icon, (round(x + box[2] - box[0] + gap), round((image.height - icon.height) / 2)))

    def close_resources(self):
        if self.overlay is not None:
            self.overlay.close()
        self.overlay = None
