"""标题画面改版用的原生素材拆分（2026-11-12）：版权横条、去掉版权条的前景、两处通关残骸、尺寸标注图。
来源为原生图集 title01.obm / title02.obm 与图像表 34（表数据取自 verification/title_screen_20261112/out/tables.json）。
用法（工作区根目录）：E:/anaconda3/python.exe -I artwork/title_screen_20261112/export_title_parts.py"""
import json, struct, sys
from pathlib import Path
from PIL import Image, ImageDraw
HERE = Path(__file__).resolve().parent
sys.path.insert(0, r'F:\egg\research\metal_slug_defense\windows_native\modding_feasibility_20261002')
sys.path.insert(0, 'artwork/title_font_20261008')
from obm_tool import parse
from obm_extra import parse_extra
SRC = Path('game_data/assets/com.snkplaymore.android003')
T = json.loads(Path('verification/title_screen_20261112/out/tables.json').read_text(encoding='utf-8'))
RECT, FRAME = T['title_rects'], T['title_frames']
VIEW_W, CANVAS_H, BAR_Y = 568, 320, 305          # 可见宽度（1136 / 2）、背景画布高、版权条首行


def atlas(name):
    raw = (SRC / (name + '.obm')).read_bytes()
    kind, bits = raw[2:4]
    return (parse_extra(raw) if bits == 4 or (kind == 4 and bits == 24) else parse(raw)).convert('RGBA')


PAGES = [atlas('title01'), atlas('title02')]


def compose(rect_ids):
    c = Image.new('RGBA', (640, CANVAS_H))
    for rid in rect_ids:
        x, y, w, h, ax, ay, flag, page = RECT[rid]
        c.alpha_composite(PAGES[page].crop((x, y, x + w, y + h)), (-ax, -ay))
    return c.crop((0, 0, VIEW_W, CANVAS_H))


def save(im, name):
    im.save(HERE / name)
    print(name, im.size)


full = compose(FRAME[0])
front = compose([2, 8])                                   # 前景废墟 + 版权条（两个图块）
bar = front.crop((0, BAR_Y, VIEW_W, CANVAS_H))
rows = [y for y in range(CANVAS_H) if all(max(full.getpixel((x, y))[:3]) < 16 for x in range(0, VIEW_W, 7))]
assert {305, 306, 307, 308, 316, 317, 318, 319} <= set(rows) and BAR_Y - 1 not in rows, rows[-20:]
save(bar, 'copyright_bar_568x15.png')
no_bar = front.copy()
no_bar.paste((0, 0, 0, 0), (0, BAR_Y, VIEW_W, CANVAS_H))
save(no_bar.crop(no_bar.getbbox()), 'native_foreground_without_bar.png')
print('foreground bbox on canvas', no_bar.getbbox())
save(full.crop((0, 0, VIEW_W, BAR_Y)), 'native_upper_area_frame0_568x305.png')
save(Image.new('RGBA', (VIEW_W, BAR_Y)), 'template_upper_area_568x305.png')

wrecks = {'wreck_world2_tank': 15, 'wreck_world3_slug': 16}
layer = Image.new('RGBA', (VIEW_W, CANVAS_H))
info = {}
for name, frame in wrecks.items():
    x, y, w, h, ax, ay, flag, page = RECT[FRAME[frame][0]]
    im = PAGES[page].crop((x, y, x + w, y + h))
    save(im, '%s_%dx%d.png' % (name, w, h))
    layer.alpha_composite(im, (-ax, -ay))
    info[name] = {'frame': frame, 'size': [w, h], 'canvas_xy': [-ax, -ay], 'atlas_xy_title01': [x, y]}
save(layer, 'wrecks_in_place_568x320.png')

guide = full.copy()
guide.alpha_composite(layer)
guide = guide.resize((VIEW_W * 2, CANVAS_H * 2), Image.NEAREST)
d = ImageDraw.Draw(guide)
d.rectangle((0, 0, VIEW_W * 2 - 1, BAR_Y * 2 - 1), outline=(0, 255, 255, 255), width=2)
d.text((8, 6), 'upper area 568 x 305 (art px) = 1136 x 610 (logical) = 1278 x 686 @1280x720', fill=(0, 255, 255, 255))
d.rectangle((0, BAR_Y * 2, VIEW_W * 2 - 1, CANVAS_H * 2 - 1), outline=(255, 255, 0, 255), width=2)
d.text((8, BAR_Y * 2 - 14), 'copyright bar 568 x 15, rows 305-319', fill=(255, 255, 0, 255))
for name, v in info.items():
    x, y = v['canvas_xy']; w, h = v['size']
    d.rectangle((x * 2, y * 2, (x + w) * 2 - 1, (y + h) * 2 - 1), outline=(255, 0, 255, 255), width=1)
    d.text((x * 2, y * 2 - 12), '%s %dx%d @(%d,%d)' % (name.split('_', 1)[1], w, h, x, y), fill=(255, 0, 255, 255))
save(guide, 'layout_guide_2x.png')
(HERE / 'layout.json').write_text(json.dumps({
    'view_art_px': [VIEW_W, CANVAS_H], 'upper_area_art_px': [VIEW_W, BAR_Y], 'copyright_bar_rows': [BAR_Y, CANVAS_H - 1],
    'draw_scale_logical': 2, 'logical_canvas': [1136, 640], 'pixel_factor_at_1280x720': 2.25,
    'bar_source': {'rect2_title01': [0, 188, 512, 15], 'rect8_title01': [412, 330, 56, 15]}, 'wrecks': info}, indent=1), encoding='utf-8')
