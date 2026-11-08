"""未来爆竹红（s1xlv.sarubia_future，基准 UnitID 6）开火烟气替换（2026-11-08）。
素材：F:/egg/MSFIX/Custom _ Edited - Metal Slug Customs - Rebel Army - Future Rebel Vehicles II.png 的 SARUBIA 段 SFX，共 13 帧（用户指定）。
写出（community_content/）：
- sarubia_future_sfx.obm：13 帧逐张水平翻转后按行排入 512 宽画布（高取 2 的幂），OBM kind 1（8 位索引、RGBA 调色板，索引 0 透明）；
- sarubia_future_descriptor.json：原生矩形（97）与帧（194 项）原样在前，新矩形（页 1，flags 1，与原烟气相同）与帧追加在后；受击框、攻击框取原生。
改写：
- units/sarubia_future.json：texture 换为 textures（原图集 + 新图集）、加 sprite_descriptor、animations 加脚本 "17"；
- content.json：assets 登记新图集的摘要。
脚本 17 只有换帧与等待，第 0–9 帧 1 tick、第 10–12 帧 2 tick，总长 16 tick（原 16 帧每帧 1 tick）；放出它的 op12 与其他脚本不变。
定位（用户逐次确认，verification/sarubia_future_smoke_20261108/preview.py）：圆环中心相对 op12 原点 (−34, −70) 的偏移 (−5, −2)，即单位局部 (−39, −72)（朝向坐标，负值为炮口前方）。
绘制层级（R1，用户要求炮弹画在气体之后）：脚本 8、9 中放出脚本 17 的 op12 第二个值由 0 改为 1（只影响绘制次序）。
原图集 sarubia_future.obm 不改动，原烟气矩形 81–96 保留在描述符中、不再被引用。
用法：E:/anaconda3/python.exe -I build_smoke.py"""
import re, sys, json, struct
from pathlib import Path
import numpy as np
from PIL import Image
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'verification' / 'msadv_tyra_walk_20261023'))
sys.path.insert(0, str(REPO))
from frames import Unit  # noqa: E402
from elfmem import read  # noqa: E402
import content_digest  # noqa: E402

SHEET = r'F:\egg\MSFIX\Custom _ Edited - Metal Slug Customs - Rebel Army - Future Rebel Vehicles II.png'
OUT = REPO / 'community_content'
UNIT = OUT / 'units' / 'sarubia_future.json'
ATLAS, DESC = 'sarubia_future_sfx.obm', 'sarubia_future_descriptor.json'
# 13 帧在素材表上的列范围（含端点）与纵向范围；上方标签 "SFX" 在 y<900，下方标签 "ENERGY PODS" 在 y≥985
COLS = [(8, 42), (45, 73), (76, 107), (110, 145), (148, 180), (183, 221), (224, 265), (268, 312), (315, 361), (364, 413), (416, 468), (471, 525), (528, 576)]
Y0, Y1 = 899, 984
# 圆环中心（素材表列号）；第 0 帧为光球中心，第 12 帧无圆环，按前几帧“环心 − 左缘”的趋势外推
RING = [25, 66, 101, 137, 172, 212, 255, 301, 349, 400, 454, 510, 569]
CY_EDGE = 940       # 素材表上圆环纵向中心的行边界
# 圆环中心相对 op12 原点的偏移（负 DY 向上）。RX 为朝向坐标（负值 = 炮口前方）；用户所说的左右以样张动画（单位朝左）为准，RX 增大即样张向右、靠近炮口。
RX, DY = -5, -2
# R1：气体画在炮弹之上。原生 addEffectImpl 令效果 +0xf0 = 单位 +0xf0 + op12 第二个值（钳制 ±100），弹体 +0xf0 = 单位 +0xf0（实测 0x5300010），
# 相同时按建立次序绘制，效果比弹体早 1 tick 建立、原来在下层；第二个值写 1 后效果排在弹体之后。
SMOKE_PRIORITY = 1
HOLD = [1] * 10 + [2] * 3
ORIGINAL_TICKS = 16


def cut():
    a = np.array(Image.open(SHEET).convert('RGBA'))
    out = []
    for (x0, x1), rc in zip(COLS, RING):
        c = a[Y0:Y1, x0:x1 + 1]
        assert set(np.unique(c[..., 3]).tolist()) <= {0, 255}, 'partial alpha in SFX frame'
        m = c[..., 3] > 0
        ys, xs = np.where(m.any(1))[0], np.where(m.any(0))[0]
        bx0, by0 = x0 + int(xs[0]), Y0 + int(ys[0])
        img = c[int(ys[0]):int(ys[-1]) + 1, int(xs[0]):int(xs[-1]) + 1]
        # flags=1 的矩形绘制时以锚点为中心水平翻转：画面朝左的素材存成镜像，局部范围 (ax − w, ax]
        out.append(dict(img=img[:, ::-1].copy(), ax=RX + (bx0 - rc) + img.shape[1], ay=CY_EDGE - by0 - DY))
    return out


def pack(sizes, width=512):
    """逐张紧排（按高度降序分行），行间与列间各留 1 像素。"""
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i][0])
    pos, x, y, row_h = [None] * len(sizes), 0, 0, 0
    for i in order:
        h, w = sizes[i]
        if x + w > width:
            x, y, row_h = 0, y + row_h + 1, 0
        pos[i] = (x, y)
        x += w + 1
        row_h = max(row_h, h)
    height = 1
    while height < y + row_h:
        height *= 2
    return pos, height


def obm_kind1(rgba):
    h, w = rgba.shape[:2]
    a = rgba[..., 3] > 0
    colors = sorted({tuple(int(v) for v in p[:3]) for p in rgba[a]})
    if len(colors) > 255:
        raise ValueError('palette exceeds 255 colours')
    index = {c: i + 1 for i, c in enumerate(colors)}
    idx = np.zeros((h, w), np.uint8)
    for y, x in zip(*np.where(a)):
        idx[y, x] = index[tuple(int(v) for v in rgba[y, x, :3])]
    pal = bytearray(1024)
    for c, i in index.items():
        pal[i * 4:i * 4 + 4] = bytes((*c, 255))
    return b'OI' + bytes((1, 8)) + struct.pack('<HH', w, h) + bytes(pal) + idx.tobytes(), len(colors)


def native_bounds(u):
    """受击框按指针差取整表；攻击框数取原生脚本实际引用的最大下标 + 1。"""
    d = u.d
    hits = [list(struct.unpack('<5i', read(d[4] + i * 20, 20))) for i in range((d[5] - d[4]) // 20)]
    used = [c['values'][0] for sid in range(d[7]) for c in u.script(sid) if c.get('opcode') == 4]
    attacks = [list(struct.unpack('<5i', read(d[5] + i * 20, 20))) for i in range(max(used) + 1)]
    return hits, attacks


def write_unit(animation):
    """按文本改写单位文件（保持原有格式与换行，可重复运行）：texture 换 textures、animations 写脚本 17、
    脚本 8 / 9 中放出脚本 17 的 op12 第二个值写 SMOKE_PRIORITY；其余内容不变。"""
    raw = UNIT.read_bytes().decode('utf-8')
    nl = '\r\n' if '\r\n' in raw else '\n'
    text = raw.replace('\r\n', '\n')
    data = json.loads(text)
    if 'texture' in data:
        old = '  "texture": "sarubia_future.obm",\n'
        assert text.count(old) == 1 and '17' not in data['animations']
        text = text.replace(old, f'  "textures": [\n    "sarubia_future.obm",\n    "{ATLAS}"\n  ],\n  "sprite_descriptor": "{DESC}",\n')
    start = text.index('  "animations": {\n')
    end = text.index('\n  }', start)
    body = text[start:end]
    if ',\n    "17": ' in body:
        body = body[:body.index(',\n    "17": ')]
    expected = sum(1 for sid in ('8', '9') for c in data['animations'][sid] if c['opcode'] == 12 and c['values'][0] == 17)
    body, count = re.subn(r'(\n +17,\n +)-?\d+(,\n +-34,\n +-70\n)', lambda m: m.group(1) + str(SMOKE_PRIORITY) + m.group(2), body)
    assert count == expected and count > 0, (count, expected)
    block = ',\n    "17": ' + json.dumps(animation, indent=2).replace('\n', '\n    ')
    text = text[:start] + body + block + text[end:]
    got = json.loads(text)
    assert got['animations']['17'] == animation
    for sid in ('8', '9'):
        assert len(got['animations'][sid]) == len(data['animations'][sid])
        for new, old in zip(got['animations'][sid], data['animations'][sid]):
            if old['opcode'] == 12 and old['values'][0] == 17:
                assert new['values'] == [17, SMOKE_PRIORITY, -34, -70]
            else:
                assert new == old
    UNIT.write_bytes(text.replace('\n', nl).encode('utf-8'))


def register():
    index = OUT / 'content.json'
    raw = index.read_bytes().decode('utf-8')
    assert '\r\n' in raw
    text = raw.replace('\r\n', '\n')
    data = json.loads(text)
    digest = content_digest.blake2((OUT / ATLAS).read_bytes())
    line = f'    "{ATLAS}": "{digest}"'
    if ATLAS in data['assets']:
        text = re.sub(rf'    "{re.escape(ATLAS)}": "[0-9a-f]{{64}}"', line, text)
    else:
        end = text.index('\n  },\n', text.index('  "assets": {'))
        text = text[:end] + ',\n' + line + text[end:]
    json.loads(text)
    index.write_bytes(text.replace('\n', '\r\n').encode('utf-8'))
    return digest


def main():
    u = Unit(6)
    assert len(u.rects) == 97 and len(u.frames) == 194 and u.d[7] == 18 and sum(HOLD) == ORIGINAL_TICKS
    tiles = cut()
    pos, height = pack([t['img'].shape[:2] for t in tiles])
    atlas = np.zeros((height, 512, 4), np.uint8)
    rects, frames, script = [list(r) for r in u.rects], list(u.frames), []
    for t, (px, py), hold in zip(tiles, pos, HOLD):
        h, w = t['img'].shape[:2]
        atlas[py:py + h, px:px + w] = t['img']
        script += [{'opcode': 0, 'values': [len(frames)]}, {'opcode': 1, 'values': [hold]}]
        frames += [1, len(rects)]
        rects.append([int(px), int(py), int(w), int(h), int(t['ax']), int(t['ay']), 1, 1])
    script.append({'opcode': 21, 'values': []})
    raw, ncolors = obm_kind1(atlas)
    (OUT / ATLAS).write_bytes(raw)
    hits, attacks = native_bounds(u)
    desc = {'rects': rects, 'frames': frames, 'script_count': u.d[7], 'hit_bounds': hits, 'attack_bounds': attacks}
    (OUT / DESC).write_text(json.dumps(desc, separators=(',', ':')) + '\n', encoding='utf-8', newline='\n')
    write_unit(script)
    digest = register()
    print('atlas', ATLAS, f'512x{height}', 'colors', ncolors, 'rects', len(rects), 'frames', len(frames), 'hits', len(hits), 'attacks', len(attacks), 'digest', digest)


if __name__ == '__main__':
    main()
