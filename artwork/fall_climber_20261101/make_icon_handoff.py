"""Fall Climber（s1xlv.fall_climber）头像构图素材导出（2026-11-01，用户要求提供缩略图素材以自行制作；做法同
artwork/rebel_bomb_bike_20261031/make_icon_handoff.py）。只读 community_content/unit_icon_02.obm、原生 unit.obm 与生成脚本的图块，
写入本目录 handoff/。
运行：E:\\anaconda3\\python.exe -I artwork/fall_climber_20261101/make_icon_handoff.py"""
from pathlib import Path
import json
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / 'handoff'
sys.path.insert(0, str(HERE))
import build_fall_climber as B   # noqa: E402
R = B.R

ICONS = REPO / 'community_content' / 'unit_icon_02.obm'
UNIT_OBM = REPO / 'game_data' / 'assets' / 'com.snkplaymore.android003' / 'unit.obm'
CELLS = {'player_green': (362, 151), 'enemy_red': (428, 125), 'empty': (439, 188)}   # 原生选单位格 50×50（unit.obm）
# 原生头像（页 1 = unit_icon_02；同机动兵素材）与大型社区单位的头像（单位文件）
REFS = {'native_133': ([134, 284, 46, 41], [-5, -4]), 'native_162': ([691, 424, 39, 37], [-5, -8]),
        'native_2': ([804, 85, 42, 39], [-2, -6])}
REF_UNITS = ('iron_sentinel', 'iron_death_worm')


def rgba(path):
    raw = path.read_bytes()
    assert raw[:4] == b'OI\x01\x20'
    w, h = struct.unpack_from('<HH', raw, 4)
    return np.frombuffer(raw[8:8 + w * h * 4], np.uint8).reshape(h, w, 4)


def crop(a, rect):
    x, y, w, h = rect
    return Image.fromarray(np.ascontiguousarray(a[y:y + h, x:x + w]), 'RGBA')


def in_cell(cell, icon, anchor):
    """头像按锚点叠在格上（锚点取负值为格内左上角）；画布向四边各留 8 像素，越出格子的部分照样画出。"""
    pad = 8
    canvas = Image.new('RGBA', (50 + 2 * pad, 50 + 2 * pad), (0, 0, 0, 0))
    canvas.alpha_composite(cell, (pad, pad))
    canvas.alpha_composite(icon, (pad - anchor[0], pad - anchor[1]))
    return canvas, pad


def zoom(img, k, pad=None, bg=(40, 40, 48, 255)):
    big = Image.new('RGBA', img.size, bg)
    big.alpha_composite(img)
    big = big.resize((img.width * k, img.height * k), Image.NEAREST)
    if pad is not None:   # 黄框为内框（格内 5–44），白框为格子外沿
        d = ImageDraw.Draw(big)
        d.rectangle([pad * k, pad * k, (pad + 50) * k - 1, (pad + 50) * k - 1], outline=(255, 255, 255, 255))
        d.rectangle([(pad + 5) * k, (pad + 5) * k, (pad + 45) * k - 1, (pad + 45) * k - 1], outline=(255, 220, 0, 255))
    return big


def rest_layers(t, form):
    """游戏中静止姿势的各层，按绘制次序（由后到前，同 build_fall_climber 的子层优先级）：[(名称, 图, 左上角相对单位原点)]。
    单位原点为身体中心、行走线上；原画朝左（左手 = 前方的手）。蒸汽为间歇动画，不含。"""
    f = str(form)
    peek = R.PEEK + (R.RISE if form == 2 else 0)

    def at(name, x=0, y=0):
        img, (ax, ay) = t.items[name]
        return img, (int(round(x)) - ax, int(round(y)) - ay)

    out = []
    for s in 'LR':
        a = R.arm_rest(form, s)
        s_ = s.lower()
        for piece, pivot in (('hand', 'H'), ('fore', 'E'), ('cap', 'E'), ('upper', 'S')):
            out.append((f'{piece}_{s_}', *at(f'{piece}_{s_}{f}', *a[pivot])))
    for s in 'LR':
        out.append((f'hip_{s.lower()}', *at(f'hip_{s}{f}')))
    for s in 'LR':
        out.append((f'claw_{s.lower()}', *at(f'claw_{s}{f}')))
    out.append(('body', *at(f'body{f}')))
    for s in 'LR':
        gx, gy = R.REF['gun_' + s][3]
        out.append((f'gun_{s.lower()}', *at(f'gun_{s.lower()}1', gx, gy - peek)))
    if form == 1:
        out.append(('head', *at('head1')))
    else:
        cx, cy = R.CORE_AT
        out.append(('core', *at('core0', cx, cy - peek)))
    ex, ey = R.REF['engine'][3]
    out.append(('engine', *at('engine0', ex, ey - peek)))
    return out


def compose(layers):
    x0 = min(tl[0] for _, _, tl in layers)
    y0 = min(tl[1] for _, _, tl in layers)
    x1 = max(tl[0] + img.width for _, img, tl in layers)
    y1 = max(tl[1] + img.height for _, img, tl in layers)
    canvas = Image.new('RGBA', (x1 - x0, y1 - y0))
    for _, img, tl in layers:
        canvas.alpha_composite(img, (tl[0] - x0, tl[1] - y0))
    return canvas, (x0, y0)


def main():
    OUT.mkdir(exist_ok=True)
    unit = json.loads((REPO / 'community_content' / 'units' / 'fall_climber.json').read_text(encoding='utf-8'))
    rect, anchor = unit['icon']['rect'], unit['icon']['anchor']
    icons, cells = rgba(ICONS), rgba(UNIT_OBM)
    cell = {k: crop(cells, (x, y, 50, 50)) for k, (x, y) in CELLS.items()}
    for k, img in cell.items():
        img.save(OUT / f'unit_cell_{k}_50x50.png')
    icon = crop(icons, rect)
    icon.save(OUT / f'fall_climber_icon_current_{rect[2]}x{rect[3]}.png')
    zoom(icon, 8).save(OUT / 'fall_climber_icon_current_8x.png')
    for side in ('player_green', 'enemy_red'):
        img, pad = in_cell(cell[side], icon, anchor)
        img.crop((pad, pad, pad + 50, pad + 50)).save(OUT / f'fall_climber_icon_current_in_{side}_cell_50x50.png')
        zoom(img, 8, pad).save(OUT / f'fall_climber_icon_current_in_{side}_cell_8x.png')
    refs = dict(REFS)
    for key in REF_UNITS:
        u = json.loads((REPO / 'community_content' / 'units' / f'{key}.json').read_text(encoding='utf-8'))
        refs[key] = (u['icon']['rect'], u['icon']['anchor'])
    for name, (r, a) in refs.items():
        img, pad = in_cell(cell['player_green'], crop(icons, r), a)
        zoom(img, 4, pad).save(OUT / f'ref_icon_{name}_in_cell_4x.png')

    t = B.load()
    info = {'icon': {'rect': rect, 'anchor': anchor}, 'forms': {}}
    for form in (1, 2):
        layers = rest_layers(t, form)
        whole, (x0, y0) = compose(layers)
        whole.save(OUT / f'fall_climber_form{form}_rest_{whole.width}x{whole.height}.png')
        prev = zoom(whole, 2)
        d = ImageDraw.Draw(prev)
        d.line([(0, -y0 * 2), (prev.width - 1, -y0 * 2)], fill=(255, 64, 64, 255))   # 行走线（单位原点所在行）
        prev.save(OUT / f'fall_climber_form{form}_rest_2x_walkline.png')
        ldir = OUT / f'layers_form{form}'
        ldir.mkdir(exist_ok=True)
        order = []
        for k, (name, img, tl) in enumerate(layers):
            fn = f'{k:02d}_{name}.png'
            img.save(ldir / fn)
            order.append({'file': fn, 'x': tl[0] - x0, 'y': tl[1] - y0, 'w': img.width, 'h': img.height})
        (ldir / 'layers.json').write_text(json.dumps(order, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        info['forms'][form] = {'size': list(whole.size), 'walk_line_row': -y0, 'origin_x': -x0, 'layers': len(layers)}
    print(json.dumps(info, ensure_ascii=False))


if __name__ == '__main__':
    main()
