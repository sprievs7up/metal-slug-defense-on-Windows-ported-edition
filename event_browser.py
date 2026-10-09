"""历史活动浏览页（docs/events/historical_event_redesign_2026-10-08.md R01–R12）。

借用原生主菜单（场景 27/28，MENU 页 state 1）：
- 左侧显像管：drawConv 替换表（LAB 头部 +0xb40，与 VERSUS 页共用、互斥）把新闻画面转换项 0x108fddfe 换为所选活动的
  360×240 原图；翻页时以 GT_ActionSet 重启 app+0x3370 子任务的完整原生雪花脚本（含 SoundID 10），图像在雪花开始时更换。
- 右侧按钮：主菜单文字批次的前三个字符串在光栅化时临时替换为“開始 / 細則 / 上一個……下一個”。第三行按钮框按纵坐标
  （364.0）匹配，换为左右两段等宽、中间透明的合成框（取原生褐色框图块左右端），按下时对应半段换为原生按下图块。
- 開始、細則与底栏 BACK 保留原生按压白光（按下、移动送入原生，释放在框外结束原生触点后由宿主执行）。
- 浏览期间不绑定活动数据；只有“開始”调用 EventTrial.select 进入女教官基地。浏览偏好单独保存在
  historical_event_browse.json，与活动进度分离。
"""
from pathlib import Path
import json
import struct

import probe as probe_module

MONITOR_CONV = 0x108fddfe
TILE_NORMAL_CONV, TILE_PRESSED_CONV = 0x1031cfe0, 0x1031cff0    # menuparts.obm 褐色按钮框（常态 y154、按下 y120）
ROW3_Y_BITS = struct.unpack('<I', struct.pack('<f', 364.0))[0]
TILE_W, TILE_H, HALF, GAP, CAP = 190, 33, 90, 10, 12               # 图块像素；绘制 2 倍，1280×720 逻辑坐标再 ×1.125
SCALE = 2 * 1.125
ROW_X = (540 + 88.9) * 1.125
ROW_RECTS = tuple((ROW_X, y * 1.125, TILE_W * SCALE, TILE_H * SCALE) for y in (180, 272, 364))
HALF_RECTS = ((ROW_X, 364 * 1.125, HALF * SCALE, TILE_H * SCALE),
              (ROW_X + (HALF + GAP) * SCALE, 364 * 1.125, HALF * SCALE, TILE_H * SCALE))
# 右侧三行按钮区及外缘：按下于此而未命中宿主按钮时，整次触点（含移动与抬起）不送入原生，
# 避免原生第三行“對戰”面板于抬起时受理（两段间隙、按钮外缘、闸门期间）。
GUARD_RECT = (ROW_X - 40, ROW_RECTS[0][1] - 30, TILE_W * SCALE + 80, ROW_RECTS[2][1] + ROW_RECTS[2][3] - ROW_RECTS[0][1] + 70)
ROW_TASKS = (0x337c, 0x3380, 0x3384)                               # 主菜单右侧三个按钮任务
BACK_TASK, BACK_RECT = 0x36d8, (45, 598, 132, 110)
SAND_TASK = 0x3370
LANGUAGE_KEYS = {9: 'ZT', 10: 'ZS', 1: 'JP', 2: 'KR'}
LABELS = {'ZT': ('開始', '細則', '上一個', '下一個'), 'ZS': ('开始', '细则', '上一个', '下一个'),
          'JP': ('開始', '詳細', '前へ', '次へ'), 'KR': ('시작', '상세', '이전', '다음'),
          'EN': ('START', 'DETAILS', 'PREV', 'NEXT')}
DETAIL = {'ZT': ('發行商', '發行日期', '擴充', '合作'), 'ZS': ('发行商', '发行日期', '扩展', '合作'),
          'JP': ('発行', '配信日', '追加配信', 'コラボ'), 'KR': ('발행사', '배포일', '추가 배포', '콜라보'),
          'EN': ('Publisher', 'Release', 'Expansion', 'Partner')}
VS_LABELS = {'對戰', '対戦', '대전', 'VERSUS', 'ВЕРСУС', 'Wi-Fi對戰', 'Wi-Fi対戦', 'Wi-Fi 대전', 'Wi-Fi VS', 'Wi-Fi V/S', 'Wi-Fi ВЕР'}


def inside(rect, x, y):
    return rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]


def entry_key(event):
    """浏览入口独立标识；旧目录继续使用活动家族键。"""
    return event.get('entry_key', event['event_key'])


class EventBrowser:
    def __init__(self, trial):
        self.t, self.p = trial, trial.p
        root = trial.root
        meta = json.loads((root / 'historical_events/browse.json').read_text(encoding='utf-8'))
        known = {e['event_key'] for e in trial.catalog}
        self.meta = meta
        self.events = [e for e in meta['events'] if e['event_key'] in known]
        self.image_dir = root / 'historical_events/assets/browse'
        self.pref_path = self.p.saves / 'historical_event_browse.json'
        self.active = False
        self.index = len(self.events) - 1
        self.pressed = None
        self.cancelled = False
        self.native_images = {}
        self.row3_images = {}
        self.header_written = False
        self.renamed = 0

    # ---------- 偏好 ----------
    def load_last(self):
        try:
            key = json.loads(self.pref_path.read_text(encoding='utf-8')).get('last')
        except (OSError, ValueError):
            key = None
        keys = [entry_key(e) for e in self.events]
        if key in keys:
            return keys.index(key)
        # 旧偏好保存活动家族键；分期后的对应入口默认选该家族最新一期。
        matches = [i for i, event in enumerate(self.events) if event['event_key'] == key]
        return matches[-1] if matches else len(self.events) - 1   # 首次或失效时为最新活动

    def save_last(self):
        from event_trial import atomic_bytes
        data = {'schema': 1, 'last': entry_key(self.events[self.index])}
        atomic_bytes(self.pref_path, json.dumps(data, ensure_ascii=False).encode('utf-8'))

    # ---------- 语言与文字 ----------
    def lang(self):
        app = self.p.app_instance()
        return LANGUAGE_KEYS.get(self.p.word(app + 0x3d64) if app else 0, 'EN')

    def name(self, event):
        names = event['names']
        return names.get(self.lang(), names['EN'])

    def rename(self, a):
        """主菜单文字批次光栅化前调用；返回需要在光栅化后恢复的 (对象, 原字符串)。"""
        if not self.active:
            return []
        p = self.p
        try:
            cursor = (a[3] + 4 + 7) & ~7
            cursor += 8
            refs = [p.word(cursor + 4 * i) for i in range(6)]
            items = p.objects[refs[5]]['items']
            if len(items) < 3 or p.objects.get(items[2]) not in VS_LABELS:
                return []
            obj = p.objects[refs[0]]
            sizes = struct.unpack('<' + 'i' * obj['length'], p.read(obj['data'], obj['length'] * 4))
            start, detail = LABELS[self.lang()][:2]
            restore = [(items[i], p.objects[items[i]]) for i in range(3)]
            p.objects[items[0]] = start
            p.objects[items[1]] = detail
            p.objects[items[2]] = self.row3_label(sizes[2])
            self.renamed += 1
            return restore
        except Exception as error:
            p.log('EVENT_BROWSER_RENAME_ERROR', type(error).__name__, str(error))
            return []

    def row3_label(self, size):
        """第三行文字：“上一個”保持原生位置，“下一個”以空格推至右半段同一相对位置（图块 2 倍为原生单位）。"""
        prev, nxt = LABELS[self.lang()][2:]
        font = self.p.font(max(1, size))
        target = (HALF + GAP) * 2
        space = max(1.0, font.getlength(' '))
        count = max(1, round((target - font.getlength(prev)) / space))
        return prev + ' ' * count + nxt

    def measure(self, text, size):
        """getFontWidthJava：浏览页中第三行文字按替换后的字符串测量，避免原生按原文宽度裁切。"""
        if self.active and text in VS_LABELS:
            return self.row3_label(size)
        return None

    # ---------- 图像 ----------
    def event_image(self, event):
        from PIL import Image, ImageDraw
        lang = self.lang()
        key = (entry_key(event), lang)
        if key in self.native_images:
            return self.native_images[key]
        name = event.get('localized_images', {}).get(lang) or event.get('image')
        if name:
            image = Image.open(self.image_dir / name).convert('RGBA')
        else:
            # 无存档原图的活动：黑底标题卡（文字以游戏当前语言字体绘制）。
            image = Image.new('RGBA', (360, 240), (8, 12, 10, 255))
            draw = ImageDraw.Draw(image)
            title = self.p.font(28)
            sub = self.p.font(16)
            text = self.name(event)
            w = title.getlength(text)
            title.draw(draw, ((360 - w) / 2, 100), text, fill=(240, 220, 150, 255))
            label = 'METAL SLUG DEFENSE  EVENT'
            sub.draw(draw, ((360 - sub.getlength(label)) / 2, 150), label, fill=(150, 200, 190, 255))
        if image.size != (360, 240):
            raise ValueError(f'活动显像管图像须为 360×240：{name}')
        from lab_versus import create_native_image
        native = create_native_image(self.p, image)
        self.native_images[key] = native
        return native

    def tile(self, y):
        from PIL import Image
        if not hasattr(self, '_atlas'):
            raw = (Path(probe_module.RESOURCE_ROOT) / 'com.snkplaymore.android003' / 'menuparts.obm').read_bytes()
            w, h = struct.unpack_from('<HH', raw, 4)
            self._atlas = Image.frombytes('RGBA', (w, h), raw[8:8 + w * h * 4])
        return self._atlas.crop((0, y, TILE_W, y + TILE_H))

    def row3_image(self, pressed):
        """第三行合成框：左右两段（各 HALF 像素，取原生框左右端），中间 GAP 像素透明；pressed 为按下的半段。"""
        if pressed in self.row3_images:
            return self.row3_images[pressed]
        from PIL import Image
        normal, down = self.tile(154), self.tile(120)
        out = Image.new('RGBA', (TILE_W, TILE_H), (0, 0, 0, 0))
        for side in (0, 1):
            src = down if pressed == side else normal
            half = Image.new('RGBA', (HALF, TILE_H), (0, 0, 0, 0))
            half.paste(src.crop((0, 0, HALF - CAP, TILE_H)), (0, 0))
            half.paste(src.crop((TILE_W - CAP, 0, TILE_W, TILE_H)), (HALF - CAP, 0))
            out.paste(half, (side * (HALF + GAP), 0))
        from lab_versus import create_native_image
        native = create_native_image(self.p, out)
        self.row3_images[pressed] = native
        return native

    def write_header(self, enable):
        import lab as labmod
        p = self.p
        header = labmod.LAB_HEADER + 0xb40
        if not enable:
            if self.header_written:
                p.put(header, 0)
            self.header_written = False
            return
        entries = [(MONITOR_CONV, 0, self.event_image(self.events[self.index]), 0, (0, 0, 360, 240, 0, 0, 0, 0))]
        if self.main_page():
            # 第三行分段框仅用于主菜单主页；OPTION 等子页面的同高度按钮保持原生整框。
            entries += [(TILE_NORMAL_CONV, 0, self.row3_image(self.pressed if self.pressed in (0, 1) and not self.cancelled else None),
                         ROW3_Y_BITS, (0, 0, TILE_W, TILE_H, 0, 0, 0, 0)),
                        (TILE_PRESSED_CONV, 0, 0, ROW3_Y_BITS, (0,) * 8)]
        for i, (conv, want, image, ybits, rect) in enumerate(entries):
            e = header + 0x10 + i * 32
            p.put(e, conv)
            p.put(e + 4, want)
            p.put(e + 8, image)
            p.put(e + 12, ybits)
            p.write(e + 16, struct.pack('<8h', *rect))
        p.put(header + 4, len(entries))
        p.put(header, 0x47505356)
        self.header_written = True

    def main_page(self):
        """主菜单主页（入场 27 或稳态 28/1）。"""
        p = self.p
        app = p.app_instance()
        scene, state = p.word(app + 0x22bc), p.word(app + 0x22dc)
        if scene == 27:
            return True
        if scene != 28 or state != 1:
            return False
        return True

    # ---------- 流程 ----------
    def open(self, immediate=False):
        t = self.t
        if not immediate:
            return t.transition(lambda: self.open(True))
        p = self.p
        app = p.app_instance()
        t.native_map.disable()
        t.native_selector.disable()
        t.overlay = None
        self.index = self.load_last()
        self.active, self.pressed, self.renamed = True, None, 0
        p.call('_ZN7AppMain12SceneEndFuncEi', app, p.word(app + 0x22bc))
        p.call('_ZN7AppMain11ChangeExeSTEi', app, 27)
        p.log('EVENT_BROWSER_OPEN', entry_key(self.events[self.index]))

    def close(self, reason):
        self.end_native_press()
        self.active, self.pressed = False, None
        self.write_header(False)
        self.p.log('EVENT_BROWSER_CLOSE', reason)

    def menu_ready(self):
        p = self.p
        app = p.app_instance()
        if p.word(app + 0x22bc) != 28 or p.word(app + 0x22dc) != 1:
            return False
        task = p.word(app + ROW_TASKS[0])
        return bool(task and (p.word(task) & ~1) == (p.symbols['_ZN7AppMain12GT_MenuPanelEP17GENERAL_TASK_BASE'] & ~1))

    def update(self):
        if not self.active:
            return
        p = self.p
        app = p.app_instance()
        scene = p.word(app + 0x22bc)
        if self.t.transition_action is not None:
            return
        if scene not in (27, 28, 119, 120):           # 119/120 为原生弹窗（細則）
            self.close(f'scene_{scene}')            # MEDAL、MISSION、全局商店等离开主菜单的原生功能结束浏览
            return
        if scene in (27, 28):
            self.write_header(True)

    def flip(self, step):
        from lab_ui import play_se, SE_DECIDE
        self.index = (self.index + step) % len(self.events)
        self.save_last()
        p = self.p
        app = p.app_instance()
        task = p.word(app + SAND_TASK)
        if task:
            for off, value in ((0, p.symbols['_ZN7AppMain18GT_MenuMonitorSandEP17GENERAL_TASK_BASE']),
                               (4, p.symbols['_ZN7AppMain19GT_MenuMonitorChildEP17GENERAL_TASK_BASE'])):
                p.put(task + off, value)
            # 原生 pActMenuTbl[2]（0x8fe4c8）以 (-10, 10) 请求雪花音效，再运行显像管过渡。
            # GT_ActionSet 的 restart=True 将 +0x44 设为 -2；下一帧 ActionSub2D 从脚本起点执行。
            p.call('_ZN7AppMain12GT_ActionSetEP17GENERAL_TASK_BASEib', app, task, 2, 1)
        self.write_header(True)
        play_se(p, SE_DECIDE)
        p.log('EVENT_BROWSER_FLIP', step, entry_key(self.events[self.index]))

    def details(self):
        from lab_ui import play_se, SE_DECIDE
        event = self.events[self.index]
        lang = self.lang()
        publisher, release, expansion, partner = DETAIL[lang]
        when = f"{event['date']} ({event['platform']})" if event.get('platform') else event['date']
        lines = [f"{publisher}: {self.meta['publisher']}", f"{release}: {when}"]
        if event.get('extension_date'):
            lines.append(f"{expansion}: {event['extension_date']}")
        if event.get('partner'):
            lines.append(f"{partner}: {event['partner']}")
        p = self.p
        play_se(p, SE_DECIDE)
        # 原生调用约定（UpdateScrollPrisoner 0x2128ac）：正文、标题、回调、290、30、-256、0。
        p.call('_ZN7AppMain10SetPopupOKEPcS0_PFvvEiiii', p.app_instance(), p.cstr('\n'.join(lines)),
               p.cstr(self.name(event)), 0, 290, 30, -256, 0)

    def start(self):
        from lab_ui import play_se, SE_DECIDE
        event = self.events[self.index]
        key = event['event_key']
        play_se(self.p, SE_DECIDE)
        self.save_last()

        def enter_event():
            # transition 在原生 IsShutterEnd 成立后调用；原图替换表覆盖完整关闸过程。
            self.close('start')
            options = {'enter': True, 'immediate': True}
            if event.get('phase_id') is not None:
                options['phase_id'] = event['phase_id']
            self.t.select(key, **options)
        self.t.transition(enter_event)

    def back(self):
        """浏览页 BACK / Esc：经原生闸门返回世界地图。"""
        if not self.active:
            return False
        if self.t.transition_action is not None:
            return True
        app = self.p.app_instance()
        if self.p.word(app + 0x22bc) != 28 or self.p.word(app + 0x22dc) != 1:
            return False                                   # 子页面与弹窗：原生返回
        from lab_ui import play_se, SE_CLOSE
        play_se(self.p, SE_CLOSE)

        def to_world():
            self.close('back')
            p = self.p
            app = p.app_instance()
            p.call('_ZN7AppMain12SceneEndFuncEi', app, p.word(app + 0x22bc))
            p.call('_ZN7AppMain11ChangeExeSTEi', app, 31)
        self.t.transition(to_world)
        return True

    # ---------- 输入 ----------
    def native_touch(self, action, x, y):
        probe_module.Probe.touch_event(self.p, action, x, y)

    def set_back_pressed(self, down):
        from cockpit_hold import instance
        p = self.p
        task = p.word(p.app_instance() + BACK_TASK)
        if task:
            (instance(p).hold if down else instance(p).release)(task)

    def end_native_press(self):
        if self.pressed == 'back':
            self.set_back_pressed(False)
            return
        if self.pressed not in ('start', 'detail'):
            return
        p = self.p
        app = p.app_instance()
        self.native_touch(3, -1000, -1000)
        offset = {'start': ROW_TASKS[0], 'detail': ROW_TASKS[1]}[self.pressed]
        task = p.word(app + offset)
        if task:
            p.call('_ZN7AppMain16ClearSelectPanelEP17GENERAL_TASK_BASEi', app, task, 0)

    def touch(self, action, x, y):
        """返回 True 表示已处理。"""
        if not self.active:
            return False
        app = self.p.app_instance()
        scene, state = self.p.word(app + 0x22bc), self.p.word(app + 0x22dc)
        if scene in (119, 120) or (scene == 28 and state != 1 and self.pressed is None):
            return False                                   # 弹窗与 OPTION、SHOP 等子页面由原生处理
        if self.t.transition_action is not None or scene != 28:
            return True
        rects = {'start': ROW_RECTS[0], 'detail': ROW_RECTS[1], 'back': BACK_RECT, 0: HALF_RECTS[0], 1: HALF_RECTS[1]}
        if action == 1:
            self.end_native_press()
            self.pressed, self.cancelled, self.swallow = None, False, False
            if not self.menu_ready():
                self.swallow = inside(GUARD_RECT, x, y)
                return self.swallow
            for key in ('start', 'detail', 'back', 0, 1):
                if inside(rects[key], x, y):
                    self.pressed = key
                    break
            if self.pressed is None:
                self.swallow = inside(GUARD_RECT, x, y)    # 间隙与外缘：整次触点不受理，也不送入原生
                return self.swallow
            if self.pressed in ('start', 'detail'):
                self.native_touch(action, x, y)            # 原生按压白光（主菜单大按钮于释放时受理，释放在框外即不触发）
            elif self.pressed == 'back':
                self.set_back_pressed(True)                # 底栏按钮按下即受理，仅写入原生按压字段
            else:
                self.write_header(True)                    # 第三行对应半段换为按下图块
            return True
        if self.pressed is None:
            if getattr(self, 'swallow', False):
                if action == 3:
                    self.swallow = False
                return True
            return False
        key = self.pressed
        if action == 5:
            if self.cancelled:
                return True
            if key in ('start', 'detail'):
                self.native_touch(5, x, y)
            if not inside(rects[key], x, y):
                self.cancelled = True                      # 拖出框外：取消，原生白光淡出，第三行恢复常态图块
                if key in ('start', 'detail'):
                    self.end_native_press()
                elif key == 'back':
                    self.set_back_pressed(False)
                else:
                    self.write_header(True)
            return True
        if action == 3:
            activate = not self.cancelled and inside(rects[key], x, y)
            if not (activate and key == 'back'):
                self.end_native_press()            # BACK 确认后保持原生青色框至闸门合拢（场景切换时解除）
            self.pressed, self.cancelled = None, False
            self.write_header(True)
            if activate:
                if key == 'start':
                    self.start()
                elif key == 'detail':
                    self.details()
                elif key == 'back':
                    self.back()
                else:
                    self.flip(-1 if key == 0 else 1)
            return True
        return True
