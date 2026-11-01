"""机动兵（s1xlv.rebel_bomb_bike）头像构图素材导出（2026-10-31，用户要求提供单位缩略图以便修改；做法同
artwork/ms7_bug_hive_20261029/handoff/）。只读 community_content/unit_icon_02.obm 与原生 unit.obm，写入本目录 handoff/。
运行：E:\\anaconda3\\python.exe -I artwork/rebel_bomb_bike_20261031/make_icon_handoff.py"""
from pathlib import Path
import json
import struct

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / 'handoff'
ICONS = REPO / 'community_content' / 'unit_icon_02.obm'
UNIT_OBM = REPO / 'game_data' / 'assets' / 'com.snkplaymore.android003' / 'unit.obm'
CELLS = {'player_green': (362, 151), 'enemy_red': (428, 125), 'empty': (439, 188)}   # 原生选单位格 50×50（unit.obm）
# 原生头像（ConvUnitIcon，页 1 = unit_icon_02；icon_info.py 导出，verification/ms7_m4_units_20261031/runs/ic162_*）
NATIVE = {133: ([134, 284, 46, 41], [-5, -4]), 162: ([691, 424, 39, 37], [-5, -8]), 2: ([804, 85, 42, 39], [-2, -6])}


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


def main():
    OUT.mkdir(exist_ok=True)
    unit = json.loads((REPO / 'community_content' / 'units' / 'rebel_bomb_bike.json').read_text(encoding='utf-8'))
    rect, anchor = unit['icon']['rect'], unit['icon']['anchor']
    icons, cells = rgba(ICONS), rgba(UNIT_OBM)
    cell = {k: crop(cells, (x, y, 50, 50)) for k, (x, y) in CELLS.items()}
    for k, img in cell.items():
        img.save(OUT / f'unit_cell_{k}_50x50.png')
    icon = crop(icons, rect)
    icon.save(OUT / f'rebel_bomb_bike_icon_current_{rect[2]}x{rect[3]}.png')
    zoom(icon, 8).save(OUT / 'rebel_bomb_bike_icon_current_8x.png')
    for side in ('player_green', 'enemy_red'):
        img, pad = in_cell(cell[side], icon, anchor)
        img.crop((pad, pad, pad + 50, pad + 50)).save(OUT / f'rebel_bomb_bike_icon_current_in_{side}_cell_50x50.png')
        zoom(img, 8, pad).save(OUT / f'rebel_bomb_bike_icon_current_in_{side}_cell_8x.png')
    for uid, (r, a) in NATIVE.items():
        img, pad = in_cell(cell['player_green'], crop(icons, r), a)
        zoom(img, 4, pad).save(OUT / f'ref_icon_native_{uid}_in_cell_4x.png')
    alpha = np.asarray(icon)[..., 3] > 0
    ys, xs = np.nonzero(alpha)
    print(json.dumps({'rect': rect, 'anchor': anchor, 'opaque_box_in_icon': [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                      'opaque_box_in_cell': [int(xs.min() - anchor[0]), int(ys.min() - anchor[1]), int(xs.max() - anchor[0]), int(ys.max() - anchor[1])]}))


if __name__ == '__main__':
    main()
