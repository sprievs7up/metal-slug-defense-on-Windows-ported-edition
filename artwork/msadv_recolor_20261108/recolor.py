"""《合金弹头 Advance》出处原版单位的改色（2026-11-08，核查文档 docs/msadv/MS_ADVANCE_UNITS_CHECK_2026-10-23.md 第 25 节）。
palette_maps.json：逐单位的换色表（GBA 色 → 街机色，每项注明来源）与原版图集 → 改色副本的文件名。
recolor_obm 只改写 8 位索引 OBM（kind 1）调色板中被像素使用的条目；像素索引、透明度与图集尺寸不变，原生矩形与帧因此可直接沿用。"""
import json
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAPS = HERE / 'palette_maps.json'


def load_maps():
    """返回 {UnitID 字符串: 单位项}；单位项另加 color_map：{(r, g, b): (r, g, b)}。"""
    units = json.loads(MAPS.read_text(encoding='utf-8'))['units']
    for m in units.values():
        m['color_map'] = {tuple(s): tuple(d) for s, d, _ in m['map']}
    return units


def recolor_obm(raw, color_map):
    if raw[:2] != b'OI' or raw[2] != 1 or raw[3] != 8:
        raise ValueError('expected an 8-bit kind-1 OBM')
    w, h = struct.unpack_from('<HH', raw, 4)
    if len(raw) != 8 + 1024 + w * h:
        raise ValueError('unexpected OBM length')
    pal = bytearray(raw[8:8 + 1024])
    for i in sorted(set(raw[8 + 1024:])):
        r, g, b, a = pal[i * 4:i * 4 + 4]
        if a == 0:
            continue
        if (r, g, b) not in color_map:
            raise KeyError(f'colour {(r, g, b)} has no mapping')
        pal[i * 4:i * 4 + 3] = bytes(color_map[(r, g, b)])
    return raw[:8] + bytes(pal) + raw[8 + 1024:]
