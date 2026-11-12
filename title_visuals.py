"""标题图集适配：保留用户 PNG 的原始尺寸、RGBA 及透明背景；可选的月夜背景（title_night.json）。"""
from pathlib import Path
import json
import struct

LOGO_FILE = 'LOGO_IN_GAME.png'
LOGO_SIZE = (282, 247)
ATLAS_SIZE = (512, 1024)
LOGO_XY = (0, 512)
NATIVE_IMAGE_ID = 34
NATIVE_CONV_ADDRESS = 0x10308460
NATIVE_PAT_ADDRESS = 0x10308970
NATIVE_OFF_ADDRESS = 0x10308ac8
NATIVE_RECT_COUNT = 81
NATIVE_PATTERN_WORDS = 172
NATIVE_OFFSET_COUNT = 42
NATIVE_LOGO_PATTERN = 8
NATIVE_LOGO_OFFSET = 104
NATIVE_LOGO_RECT = (0, 204, 282, 227, -143, -21, 0, 0)
NATIVE_TAP_RECT = (116, 483, 111, 23, -229, -262, 0, 0)
# 月夜背景（2026-11-12）：背景任务 0 改播 9 帧星空闪烁（图块在 title02 的替换图集中），版权横条由任务 19 单独绘制，
# 原生的随机飞行物（任务 21）、通关残骸（任务 20）与左下两个角色（任务 4、5）不显示。
NIGHT_FILE = 'title_night.json'
NIGHT_BAR_PATTERN = 15                 # 原为表世界 2 通关残骸的帧，改为版权横条（任务 19 的帧号）
TASK_SLOTS = 0x3360                    # app + 0x3360 + 4 × 任务号
TASK_SCALE = 0xa8                      # 任务缩放 x、y（float）
GT_COMMON = '_ZN7AppMain9GT_CommonEP17GENERAL_TASK_BASE'
GT_BLANK = '_ZN7AppMain8GT_BlankEP17GENERAL_TASK_BASE'
GT_TITLE_OPTION = '_ZN7AppMain14GT_TitleOptionEP17GENERAL_TASK_BASE'
TASK_CHANGE = '_ZN13CTaskSystem2D6ChangeEPFiP17GENERAL_TASK_BASEES1_'
NIGHT_TASKS = ((19, GT_COMMON), (20, GT_BLANK), (21, GT_BLANK), (4, GT_BLANK), (5, GT_BLANK))


class TitleVisuals:
    """在首次 title01 读取时创建图集及原生转换表，沿用既有任务与动作。"""

    def __init__(self, probe, folder):
        self.p = probe
        self.folder = Path(folder)
        self.atlas = None
        self.metadata = None
        self.tables = None
        self.loaded = False
        self.night = None
        self.night_atlas = None

    def read_asset(self, path, mode, asset_folder):
        path = Path(path)
        if path.parent != Path(asset_folder) or path.name not in ('title01.obm', 'title02.obm'):
            return None
        if not mode.startswith('r') or any(flag in mode for flag in 'wa+'):
            return None
        if path.name == 'title02.obm':
            return self.night_atlas if self.atlas is not None else None
        if not self.loaded:
            self.loaded = True
            if not (self.folder / LOGO_FILE).is_file():
                self.p.log('TITLE_VISUALS_DEFAULT', str(self.folder / LOGO_FILE))
                return None
            self._load(path)
            self._load_night()
        if self.atlas is not None:
            self._install_tables()
        return self.atlas

    def _load(self, path):
        from PIL import Image
        source = self.folder / LOGO_FILE
        with Image.open(source) as original:
            if original.format != 'PNG' or original.mode != 'RGBA' or original.size != LOGO_SIZE:
                raise ValueError('标题 PNG 必须保持用户提供的 282×247 RGBA 尺寸和格式')
            logo = original.tobytes()
        raw = path.read_bytes()
        if raw[:8] != b'OI\x01\x20' + struct.pack('<HH', 512, 512) or len(raw) != 8 + 512 * 512 * 4:
            raise ValueError('标题原生图集格式或尺寸发生变化')
        pixels = bytearray(ATLAS_SIZE[0] * ATLAS_SIZE[1] * 4)
        pixels[:len(raw) - 8] = raw[8:]
        tap_x, tap_y, tap_w, tap_h = NATIVE_TAP_RECT[:4]
        for y in range(tap_y, tap_y + tap_h):
            start = (y * ATLAS_SIZE[0] + tap_x) * 4 + 3
            for x in range(tap_w):
                pixels[start + x * 4] = 0
        width, height = LOGO_SIZE
        for y in range(height):
            start = ((LOGO_XY[1] + y) * ATLAS_SIZE[0] + LOGO_XY[0]) * 4
            pixels[start:start + width * 4] = logo[y * width * 4:(y + 1) * width * 4]
        self.atlas = b'OI\x01\x20' + struct.pack('<HH', *ATLAS_SIZE) + bytes(pixels)
        self.metadata = dict(source=str(source), source_size=list(LOGO_SIZE),
            atlas_size=list(ATLAS_SIZE), foreground_xy=list(LOGO_XY),
            source_png_preserved=True, source_resampling=False,
            source_rgba_pixels_preserved=True, source_rgb_pixels_preserved=True,
            source_alpha_preserved=True,
            logo_rectangle_layers=1,
            native_anchor=[-143, -21], native_title_actions_preserved=True,
            tap_screen_alpha_hidden=True, tap_screen_geometry_preserved=True)
        self.p.log('TITLE_VISUALS_LOADED', json.dumps(self.metadata, ensure_ascii=False))

    def _load_night(self):
        """读取月夜背景的布局与图集；文件缺少或有误时保持原生背景。"""
        source = self.folder / NIGHT_FILE
        if not source.is_file():
            return
        try:
            from PIL import Image
            layout = json.loads(source.read_text(encoding='utf-8'))
            with Image.open(self.folder / layout['atlas']) as image:
                if image.mode != 'RGBA' or max(image.size) > 2048:
                    raise ValueError('月夜标题图集须为不超过 2048 的 RGBA 图像')
                size, pixels = image.size, image.tobytes()
            for x, y, w, h, _ax, _ay, _flag, page in layout['rects']:
                if page != 1 or x < 0 or y < 0 or x + w > size[0] or y + h > size[1]:
                    raise ValueError('月夜标题图块超出图集')
            count = len(layout['rects'])
            if not layout['patterns'] or any(not 0 <= r < count for frame in layout['patterns'] for r in frame):
                raise ValueError('月夜标题帧表引用了不存在的图块')
            self.night_atlas = b'OI\x01\x20' + struct.pack('<HH', *size) + pixels
            self.night = layout
            self.p.log('TITLE_NIGHT_LOADED', str(source), size, count, len(layout['patterns']))
        except Exception as error:
            self.night = self.night_atlas = None
            self.p.log('TITLE_NIGHT_ERROR', repr(error))

    def _install_tables(self):
        p = self.p
        names = ('m_pMenuTblConv', 'm_pMenuTblPat', 'm_pMenuTblOff')
        slots = tuple(p.symbols[name] + NATIVE_IMAGE_ID * 4 for name in names)
        if self.tables is not None and tuple(p.word(slot) for slot in slots) == self.tables[:3]:
            return
        if self.tables is None:
            if tuple(p.word(slot) for slot in slots) != (
                    NATIVE_CONV_ADDRESS, NATIVE_PAT_ADDRESS, NATIVE_OFF_ADDRESS):
                raise RuntimeError('标题原生转换表映射与核验版本不符')
            conv = bytearray(p.read(NATIVE_CONV_ADDRESS, NATIVE_RECT_COUNT * 16))
            if struct.unpack_from('<8h', conv) != NATIVE_LOGO_RECT or struct.unpack_from('<8h', conv, 16) != NATIVE_TAP_RECT:
                raise RuntimeError('标题原生 LOGO 与 TAP SCREEN 矩形发生变化')
            anchor = NATIVE_LOGO_RECT[4:]
            struct.pack_into('<8h', conv, 0, *LOGO_XY, *LOGO_SIZE, *anchor)
            pat, off, action = NATIVE_PAT_ADDRESS, NATIVE_OFF_ADDRESS, 0
            if self.night is not None:
                conv, pat, off, action = self._night_tables(conv)
            address = p.alloc(len(conv))
            p.write(address, bytes(conv))
            self.tables = (address, pat, off, action)
        for slot, value in zip(slots, self.tables):
            p.put(slot, value)
        if self.tables[3]:
            p.put(p.symbols['pActTitleTbl'], self.tables[3])
        p.log('TITLE_VISUALS_TABLES', *map(hex, self.tables))

    def _night_tables(self, conv):
        """图块表追加版权横条与月夜图块；帧表重建（帧 15 = 版权横条，末尾追加星空各帧）；背景动作改为这些帧的循环。"""
        p, night = self.p, self.night
        words = struct.unpack('<%dh' % NATIVE_PATTERN_WORDS, p.read(NATIVE_PAT_ADDRESS, NATIVE_PATTERN_WORDS * 2))
        starts = struct.unpack('<%dH' % NATIVE_OFFSET_COUNT, p.read(NATIVE_OFF_ADDRESS, NATIVE_OFFSET_COUNT * 2))
        frames = []
        for index, start in enumerate(starts):
            end = starts[index + 1] if index + 1 < len(starts) else len(words)
            frames.append([value for value in words[start:end] if value != -1])
        base = NATIVE_RECT_COUNT
        conv = bytearray(conv)
        for rect in night['bar_rects']:
            conv += struct.pack('<8h', *rect)
        frames[NIGHT_BAR_PATTERN] = list(range(base, base + len(night['bar_rects'])))
        base += len(night['bar_rects'])
        for rect in night['rects']:
            conv += struct.pack('<8h', *rect)
        first = len(frames)
        frames.extend([base + rect for rect in frame] for frame in night['patterns'])
        pat_words, offsets = [], []
        for frame in frames:
            offsets.append(len(pat_words))
            pat_words.extend(frame + [-1])
        pat = p.alloc(len(pat_words) * 2)
        p.write(pat, struct.pack('<%dh' % len(pat_words), *pat_words))
        off = p.alloc(len(offsets) * 2)
        p.write(off, struct.pack('<%dH' % len(offsets), *offsets))
        script = b''.join(struct.pack('<4i', int(night['frame_ticks']), 0, 0, first + index)
                          for index in range(len(night['patterns']))) + struct.pack('<i', -3)
        action = p.alloc(len(script))
        p.write(action, script)
        return conv, pat, off, action

    def update(self):
        """每帧：标题场景中维持月夜背景的任务状态（背景缩放、版权横条任务、不显示的原生元素）。"""
        if self.night is None or self.tables is None:
            return
        try:
            p = self.p
            app = p.app_instance()
            if not app or p.word(app + 0x22bc) != 20:
                return
            icon = p.word(app + TASK_SLOTS + 4 * 3)
            if not icon or p.word(icon) | 1 != p.symbols[GT_TITLE_OPTION] | 1:
                return
            background = p.word(app + TASK_SLOTS)
            if not background:
                return
            scale = struct.pack('<2f', self.night['background_scale'], self.night['background_scale'])
            if p.read(background + TASK_SCALE, 8) != scale:
                p.write(background + TASK_SCALE, scale)
            for task_id, name in NIGHT_TASKS:
                task = p.word(app + TASK_SLOTS + 4 * task_id)
                if task and p.word(task) | 1 != p.symbols[name] | 1:
                    p.call(TASK_CHANGE, p.symbols[name], task)
        except Exception as error:
            self.night = None
            self.p.log('TITLE_NIGHT_UPDATE_ERROR', repr(error))
