"""本地双人对战的出兵栏选中格光标（原生绘制顺序，钩子版本 15）。

原生“按下格”图像（drawUI 0x1d88b0 起）只在格子处于可出兵状态时绘制，不能作为光标。光标由 src/lab_hooks.cpp 的
draw_conv 钩子插入原生出兵格绘制：原生画完本侧光标所在格的底板（operator+200 转换表项 53/54/55）后，以相同位置与
缩放画光标框；画完费用牌（项 77/98/107）后画光标费用牌。单位头像与费用数字随后由原生绘制，较高的头像可遮挡光标。

光标图块在开战后由宿主建立一次（整个进程复用）：
- 光标框：用户绘制的 50×50 灰度框 custom_content/versus_cursor_P{1,2}.png（与格子底板同尺寸）。
- 光标费用牌：createGrahics 在开战时把每个槽位的费用牌连同价格数字画成独立图块（operator+200 项 78–97 绿/红，
  77 OK!、98 MAX、107）。自其贴图（operator+188）以 GL 帧缓冲读回费用牌项 87（第 10 格的绿色费用牌，编队满 10 格时
  带有价格数字）的原生像素，转灰度，中央数字窗口（不接触边缘的最大近黑区域的外接矩形，含其中的数字）置透明；
  钩子在原生费用牌之后画该图块，原生价格数字从窗口透出。
- 配色：灰度按亮度映射到绝招光环 aura.obm 16 色调色板的亮度阶（黑 → 青 → 浅白），P1 为原色（我方光环），
  P2 为 LAB 敌方光环的同一换色（R←max，G、B←min），最亮三阶改为饱和亮红（RED_HIGHLIGHTS）。近黑轮廓保持黑色。
头部 +0xa00 的布局见 src/lab_hooks.cpp（功能位 512）。
"""
from pathlib import Path
import ctypes
import struct

VS_CUR = 0xa00
CURSOR_FILES = ('versus_cursor_P1.png', 'versus_cursor_P2.png')
TILE_ENTRY, PLATE_ENTRY = 53, 87          # 格子底板、空费用牌（镂空形状来源）
DARK = 30
RED_HIGHLIGHTS = [(220, 48, 40), (240, 88, 72), (255, 128, 112)]   # P2 光标最亮三阶
# 框左上角 P1/P2 字样：用户原稿中字样像素灰度恰为 194（每框 22 个，其他像素无此值），单独着近白色以保证可读（用户 2026-10-08 要求）。
LABEL_GRAY, LABEL_COLORS = 194, ((232, 252, 255), (255, 236, 226))


def aura_ramp(root, red):
    """aura.obm 调色板（去除洋红透明键）按原色亮度排序的颜色阶；red 为 LAB 敌方光环换色（顺序与原色一致）。"""
    raw = (Path(root) / 'game_data/assets/com.snkplaymore.android003/aura.obm').read_bytes()
    colors = []
    for index in range(16):
        value = struct.unpack_from('<H', raw, 8 + index * 2)[0]
        rgb = tuple(((value >> s) & 31) * 255 // 31 for s in (11, 6, 1))
        if rgb != (255, 0, 255):
            colors.append(rgb)
    colors.sort(key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2])
    if red:
        colors = [(max(c), min(c), min(c)) for c in colors]
        # 原色最亮三阶为青白光环芯；按同一规则换色后为粉白，与红色主体不协调（用户 2026-10-08 指出），改为饱和亮红。
        colors[-3:] = RED_HIGHLIGHTS
    return colors


def tint(image, ramp, label=None):
    """灰度 → 光环颜色阶：亮度 0–255 线性映射到颜色阶序号；近黑像素保持黑色，透明度保持。
    label 给定时，灰度等于 LABEL_GRAY 的字样像素改用该颜色。"""
    out = image.copy()
    px = out.load()
    top = len(ramp) - 1
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if not a:
                continue
            v = round(0.299 * r + 0.587 * g + 0.114 * b)
            if label is not None and v == LABEL_GRAY:
                px[x, y] = label + (a,)
                continue
            px[x, y] = (0, 0, 0, a) if v < 24 else ramp[min(top, round(v / 255 * top))] + (a,)
    return out


def hollow_gray(image):
    """费用牌：转灰度，数字窗口置透明。返回（图像、窗口像素数）。
    窗口为不接触图像边缘的最大近黑连通区域的外接矩形，矩形内的价格数字一并置透明：读回的项 87 是第 10 格的绿色费用牌，
    编队满 10 格时其中画有该格价格（2026-11-05 用户报告双方光标费用牌固定显示 P1 第 10 格的 270）。
    空费用牌的窗口为整块近黑矩形，结果与原先“自中心连通”的做法逐像素相同（verification/versus_esc_20261105）。"""
    w, h = image.size
    px = image.load()

    def dark(q):
        return px[q][3] > 0 and max(px[q][:3]) < DARK

    seen, best = set(), None
    for y0 in range(h):
        for x0 in range(w):
            if (x0, y0) in seen or not dark((x0, y0)):
                continue
            seen.add((x0, y0))
            stack, region, edge = [(x0, y0)], [], False
            while stack:
                cx, cy = stack.pop()
                region.append((cx, cy))
                edge = edge or cx in (0, w - 1) or cy in (0, h - 1)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    q = (cx + dx, cy + dy)
                    if 0 <= q[0] < w and 0 <= q[1] < h and q not in seen and dark(q):
                        seen.add(q)
                        stack.append(q)
            if not edge and (best is None or len(region) > len(best)):
                best = region
    if not best:
        raise ValueError('费用牌中未找到数字窗口')
    left, top = min(q[0] for q in best), min(q[1] for q in best)
    right, bottom = max(q[0] for q in best), max(q[1] for q in best)
    out = image.copy()
    o = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if left <= x <= right and top <= y <= bottom:
                o[x, y] = (0, 0, 0, 0)
            else:
                v = round(0.299 * r + 0.587 * g + 0.114 * b)
                o[x, y] = (v, v, v, a)
    return out, (right - left + 1) * (bottom - top + 1)


def create_native_image(p, image):
    """以 RGBA PIL 图像建立原生 Image（OI 32 位格式，Image::createImageBuf），纹理采用最近邻采样与边缘截取。"""
    raw = b'OI ' + struct.pack('<HH', *image.size) + image.tobytes()
    buffer = p.alloc(len(raw))
    p.write(buffer, raw)
    try:
        native = p.call('_ZN5Image14createImageBufEPhiiS0_i', buffer, len(raw), 0, 0, 0)
    finally:
        p.free(buffer)
    if not native or p.word(native + 4) != image.width or p.word(native + 8) != image.height:
        raise RuntimeError('原生图像创建失败')
    g = p.graphics
    saved = ctypes.c_int()
    g.function('glGetIntegerv', 'up')(0x8069, ctypes.byref(saved))
    g.function('glBindTexture', 'uu')(0x0DE1, p.word(native + 12))
    try:
        for parameter, value in ((0x2801, 0x2600), (0x2800, 0x2600), (0x2802, 0x812F), (0x2803, 0x812F)):
            g.function('glTexParameteri', 'uui')(0x0DE1, parameter, value)
    finally:
        g.function('glBindTexture', 'uu')(0x0DE1, saved.value)
    return native


class VersusCursor:
    def __init__(self, lab):
        self.lab = lab
        self.root = Path(__file__).resolve().parent
        self.native = None          # 每侧 [框, 费用牌] 的原生 Image*
        self.convs = None           # 与 native 对应的转换项（8 个 short）
        self.built_images = None    # 生成的 RGBA 图块（检查用）
        self.source_images = None   # 读回的原生图块（检查用）
        self.error = None

    # ---------- 原生像素读回与图块建立 ----------
    def read_texture(self, image, rect):
        """以 GL 帧缓冲读回 Image（+12 纹理）的矩形区域，返回 RGBA PIL 图像。"""
        from PIL import Image
        f = self.lab.p.graphics.function
        x, y, w, h = rect
        fbo, prev = ctypes.c_uint(), ctypes.c_int()
        f('glGetIntegerv', 'up')(0x8CA6, ctypes.byref(prev))
        f('glGenFramebuffers', 'up')(1, ctypes.byref(fbo))
        try:
            f('glBindFramebuffer', 'uu')(0x8D40, fbo.value)
            f('glFramebufferTexture2D', 'uuuui')(0x8D40, 0x8CE0, 0x0DE1, self.lab.p.word(image + 12), 0)
            status = f('glCheckFramebufferStatus', 'u', ctypes.c_uint)(0x8D40)
            if status != 0x8CD5:
                raise RuntimeError(f'出兵格贴图帧缓冲不完整：0x{status:x}')
            buffer = ctypes.create_string_buffer(w * h * 4)
            f('glPixelStorei', 'ui')(0x0D05, 4)
            f('glReadPixels', 'iiiiuup')(x, y, w, h, 0x1908, 0x1401, buffer)
        finally:
            f('glBindFramebuffer', 'uu')(0x8D40, prev.value)
            f('glDeleteFramebuffers', 'up')(1, ctypes.byref(fbo))
        return Image.frombytes('RGBA', (w, h), buffer.raw)

    def create_native(self, image):
        return create_native_image(self.lab.p, image)

    def build(self, operator):
        from PIL import Image
        p = self.lab.p
        base, atlas = p.word(operator + 200), p.word(operator + 188)
        entry = lambda i: struct.unpack('<8h', p.read(base + i * 16, 16))
        tile, plate = entry(TILE_ENTRY), entry(PLATE_ENTRY)
        sources = [self.read_texture(atlas, plate[:4])]
        plate_images = [hollow_gray(sources[0])[0]]
        plates = [plate]
        native, convs, built = [], [], []
        for side in (0, 1):
            ramp = aura_ramp(self.root, red=bool(side))
            frame = Image.open(self.root / 'custom_content' / CURSOR_FILES[side]).convert('RGBA')
            if frame.size != (tile[2], tile[3]):
                raise ValueError(f'光标框须为 {tile[2]}×{tile[3]}（与格子底板相同）')
            parts = [tint(frame, ramp, LABEL_COLORS[side])] + [tint(img, ramp) for img in plate_images]
            built.append(parts)
            native.append([self.create_native(img) for img in parts])
            convs.append([(0, 0, img.width, img.height, e[4], e[5], e[6], 0) for img, e in zip(parts, [tile] + plates)])
        self.native, self.convs, self.built_images, self.source_images = native, convs, built, sources
        self.lab.record('vs_cursor_built', tile=tile, plates=plates)

    # ---------- 每帧 ----------
    def prepare(self):
        """双人对战战斗中每帧写入头部：两侧光标槽、图块与转换项、转换表基址、启用。"""
        import lab as labmod
        lab, p = self.lab, self.lab.p
        if not lab.vs_battle() or lab.native_hooks < 15 or self.error:
            return
        _, scene = lab.battle()
        operator = p.word(scene + 0x3c) if scene else 0
        if not operator or not p.word(operator + 200) or not p.word(operator + 188):
            return
        if self.native is None:
            try:
                self.build(operator)
            except Exception as error:
                self.error = f'{type(error).__name__}: {error}'
                lab.record('vs_cursor_error', error=self.error)
                return
        header = labmod.LAB_HEADER + VS_CUR
        p.put(header + 4, lab.vs_cursor[0])
        p.put(header + 8, lab.vs_cursor[1])
        for side in (0, 1):
            for part in range(2):
                p.put(header + 0x10 + side * 0x10 + part * 4, self.native[side][part])
                p.write(header + 0x30 + side * 0x40 + part * 16, struct.pack('<8h', *self.convs[side][part]))
        p.put(header + 0xc0, operator)
        p.put(header, 1)

    def visible_index(self, side, slot):
        """选中格在本侧 3 个可见格中的序号；不可见时为 None（滚动值与 lab.reveal_slot 相同）。"""
        import lab as labmod
        lab, p = self.lab, self.lab.p
        _, scene = lab.battle()
        operator = p.word(scene + 0x3c) if scene else 0
        if not operator:
            return None
        pitch = struct.unpack('<f', p.read(operator + 108, 4))[0]
        if pitch <= 0:
            return None
        address = labmod.LAB_HEADER + labmod.LAB_ENEMY_PANEL + 12 if side else operator + 100
        scroll = p.word(address)
        scroll = scroll - (1 << 32) if scroll & 0x80000000 else scroll
        index = slot - max(0, round(scroll / pitch))
        return index if 0 <= index <= 2 else None

    def draw(self):
        """光标由原生钩子在出兵格绘制顺序中绘制，宿主不另行叠加。"""
        return

    def close(self):
        return
