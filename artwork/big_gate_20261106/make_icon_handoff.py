"""大门（s1xlv.big_gate_builder 1099 / s1xlv.big_gate 1100，两者共用头像）头像构图素材导出（2026-11-06 R6，用户：预留头像，
等待用户修改；做法同 artwork/fall_climber_20261101/make_icon_handoff.py）。只读 community_content/unit_icon_02.obm、原生 unit.obm、
本单位的描述符与图集，写入本目录 handoff/。
运行：E:\\anaconda3\\python.exe -I artwork/big_gate_20261106/make_icon_handoff.py"""
from pathlib import Path
import json
import struct

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / 'handoff'
VER = REPO / 'verification' / 'ms7_bigate_20261106'
ICONS = REPO / 'community_content' / 'unit_icon_02.obm'
UNIT_OBM = REPO / 'game_data' / 'assets' / 'com.snkplaymore.android003' / 'unit.obm'
CELLS = {'player_green': (362, 151), 'enemy_red': (428, 125), 'empty': (439, 188)}   # 原生选单位格 50×50（unit.obm）
REFS = {'native_133': ([134, 284, 46, 41], [-5, -4]), 'native_162': ([691, 424, 39, 37], [-5, -8]),
        'native_2': ([804, 85, 42, 39], [-2, -6])}
REF_UNITS = ('iron_sentinel', 'iron_death_worm', 'fall_climber')


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


def gate_rest():
    """建成后的大门静止画面（素材像素 1:1，透明底）：两爪、漩涡（转角 0）、环体，按 MSA 槽 12–15 的偏移与次序（gate_anim.PARTS）。
    返回 (图, 单位原点在图中的位置)；单位原点为地面上的中心。"""
    ns = {'__name__': 'gate_anim', '__file__': str(VER / 'gate_anim.py')}
    exec(compile((VER / 'gate_anim.py').read_text(encoding='utf-8'), 'gate_anim', 'exec'), ns)
    ox, oy = 200, 260
    canvas = Image.new('RGBA', (400, 300), (0, 0, 0, 0))
    for name, (frame, dx, dy, _) in sorted(ns['PARTS'].items(), key=lambda kv: kv[1][3]):
        ns['draw_frame'](canvas, ns['GATE'], ns['GATE_PAGES'], frame, ox + dx, oy + dy)
    bb = canvas.getbbox()
    return canvas.crop(bb), (ox - bb[0], oy - bb[1])


def main():
    OUT.mkdir(exist_ok=True)
    unit = json.loads((REPO / 'community_content' / 'units' / 'big_gate.json').read_text(encoding='utf-8'))
    rect, anchor = unit['icon']['rect'], unit['icon']['anchor']
    icons, cells = rgba(ICONS), rgba(UNIT_OBM)
    cell = {k: crop(cells, (x, y, 50, 50)) for k, (x, y) in CELLS.items()}
    for k, img in cell.items():
        img.save(OUT / f'unit_cell_{k}_50x50.png')
    icon = crop(icons, rect)
    icon.save(OUT / f'big_gate_icon_current_{rect[2]}x{rect[3]}.png')
    zoom(icon, 8).save(OUT / 'big_gate_icon_current_8x.png')
    for side in ('player_green', 'enemy_red'):
        img, pad = in_cell(cell[side], icon, anchor)
        img.crop((pad, pad, pad + 50, pad + 50)).save(OUT / f'big_gate_icon_current_in_{side}_cell_50x50.png')
        zoom(img, 8, pad).save(OUT / f'big_gate_icon_current_in_{side}_cell_8x.png')
    refs = dict(REFS)
    for key in REF_UNITS:
        u = json.loads((REPO / 'community_content' / 'units' / f'{key}.json').read_text(encoding='utf-8'))
        refs[key] = (u['icon']['rect'], u['icon']['anchor'])
    for name, (r, a) in refs.items():
        img, pad = in_cell(cell['player_green'], crop(icons, r), a)
        zoom(img, 4, pad).save(OUT / f'ref_icon_{name}_in_cell_4x.png')
    whole, (ux, uy) = gate_rest()
    whole.save(OUT / f'big_gate_rest_{whole.width}x{whole.height}.png')
    prev = zoom(whole, 2)
    gy = min(uy * 2, prev.height - 1)   # 地面（单位原点所在行；两爪底边即地面，画在图像最下一行）
    ImageDraw.Draw(prev).line([(0, gy), (prev.width - 1, gy)], fill=(255, 64, 64, 255))
    prev.save(OUT / 'big_gate_rest_2x_ground.png')
    print(json.dumps({'icon': {'rect': rect, 'anchor': anchor}, 'rest': {'size': list(whole.size), 'origin': [ux, uy]}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
