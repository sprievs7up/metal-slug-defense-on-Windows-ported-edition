"""《合金弹头 Advance》出处原版单位改色接入（2026-11-08，核查文档 docs/msadv/MS_ADVANCE_UNITS_CHECK_2026-10-23.md 第 25 节）。
1. 按 palette_maps.json 把各单位的原版图集（game_data/assets，只读）换色，写成 community_content/ 中的改色副本（只换调色板条目）；
2. DARARIN 248、BALOR 340 / 341：写只换图集的原版单位外观替换 <name>_sprite.json（无描述符、animations 为空，
   沿用原生矩形、帧、脚本与判定框；textures 按原生图集顺序，效果图集保持原版）；
3. WALTER 385、TYRA 381、NATIVE(BIRD) 221：调用 artwork/msadv_frames_20261024/build_stock_sprites.py 重建补帧替换（补帧图集按同一换色表换色，
   textures 中的原生图集换成改色副本）；
4. 在 content.json 登记改色副本的摘要与 stock_sprites；
5. NATIVE_ICONS 所列单位的头像按同一换色表写入 community_content/unit_icon_02.obm（只改该矩形）。
用法：E:\\anaconda3\\python.exe -I build_recolor.py"""
import re, sys, json, struct
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))
import recolor  # noqa: E402
import content_digest  # noqa: E402

ASSETS = REPO / 'game_data' / 'assets' / 'com.snkplaymore.android003'
OUT = REPO / 'community_content'
# 原生描述符的图集顺序（安装时宿主核对数量；与 verification/msadv_units_20261023/unit_pages.txt 一致）
NATIVE_TEXTURES = {
    248: ['DARIRIN_DARADARA_out.obm'],
    340: ['Submarine_out.obm'],
    341: ['Submarine_out.obm'],
}
# 原版单位头像（community_content/unit_icon_02.obm 为原版 unit_icon_02 的扩展副本，32 位 RGBA）：单位键 → ConvUnitIcon 矩形 (x, y, w, h)。
# ConvUnitIcon 第 194（221）、215（248）、310（341）、327（385）、328（381）项，各只由该单位使用，与其他原生及社区头像矩形不重叠。取色以原版图集同一矩形为准，重跑结果不变。
NATIVE_ICONS = {'221': (773, 329, 32, 46), '248': (42, 417, 47, 40), '341': (734, 0, 44, 40),
                '381': (892, 298, 38, 36), '385': (844, 335, 37, 38)}
# Walter / Tyra 的原版头像由 GBA 色经明暗拉伸得到（约 24 + (v−48)×1.14），不在换色表内：头像色 → 该单位 sprite 的 GBA 基色，再经换色表。
ICON_COLOURS = {
    '385': {(24, 24, 24): (48, 48, 48), (51, 51, 24): (72, 72, 48), (51, 51, 133): (72, 72, 144), (51, 69, 69): (72, 88, 88),
            (51, 133, 197): (72, 144, 200), (69, 24, 24): (88, 48, 48), (124, 106, 51): (136, 120, 72),
            (133, 133, 160): (144, 144, 168), (151, 87, 24): (160, 104, 48), (206, 188, 124): (208, 192, 136),
            (224, 169, 87): (224, 176, 104), (252, 252, 151): (248, 248, 160), (252, 252, 252): (248, 248, 248)},
    '381': {(24, 24, 24): (48, 48, 48), (33, 24, 24): (56, 48, 48), (51, 42, 24): (72, 64, 48), (60, 33, 24): (80, 56, 48),
            (124, 89, 43): (136, 104, 64), (151, 24, 24): (160, 48, 48), (160, 89, 24): (168, 104, 48),
            (178, 163, 100): (184, 168, 112), (206, 145, 148): (208, 152, 152), (243, 173, 71): (240, 176, 88),
            (252, 42, 43): (248, 64, 64), (252, 238, 148): (248, 232, 152), (252, 248, 244): (248, 240, 232),
            (252, 252, 252): (248, 248, 248)},
}


def write_icons(maps):
    stock = (ASSETS / 'unit_icon_02.obm').read_bytes()
    atlas = bytearray((OUT / 'unit_icon_02.obm').read_bytes())
    assert stock[:4] == atlas[:4] == b'OI\x01\x20'
    stock_w = struct.unpack_from('<H', stock, 4)[0]
    atlas_w = struct.unpack_from('<H', atlas, 4)[0]
    for key, (x, y, w, h) in NATIVE_ICONS.items():
        color_map = maps[key]['color_map']
        source = ICON_COLOURS.get(key, {})
        for j in range(y, y + h):
            for i in range(x, x + w):
                r, g, b, a = stock[8 + (j * stock_w + i) * 4:8 + (j * stock_w + i) * 4 + 4]
                out = color_map[source.get((r, g, b), (r, g, b))] if a else (r, g, b)
                atlas[8 + (j * atlas_w + i) * 4:8 + (j * atlas_w + i) * 4 + 4] = bytes((*out, a))
        print('icon', key, (x, y, w, h))
    (OUT / 'unit_icon_02.obm').write_bytes(atlas)   # 该资源的摘要在 content.json 中为 null，保持不变


def write_pages(maps):
    written = []
    for key, m in maps.items():
        for src, dst in m['pages'].items():
            raw = (ASSETS / src).read_bytes()
            out = recolor.recolor_obm(raw, m['color_map'])
            assert len(out) == len(raw) and out[:8] == raw[:8] and out[8 + 1024:] == raw[8 + 1024:]
            (OUT / dst).write_bytes(out)
            written.append(dst)
            print(key, src, '->', dst)
    return written


def write_texture_only_specs(maps):
    entries = {}
    for key, m in maps.items():
        if key in ('385', '381', '221'):
            continue
        name = f"{m['name']}_sprite.json"
        textures = [m['pages'].get(n, n) for n in NATIVE_TEXTURES[m['unit_ids'][0]]]
        assert all(NATIVE_TEXTURES[u] == NATIVE_TEXTURES[m['unit_ids'][0]] for u in m['unit_ids'])
        spec = {'textures': textures, 'animations': {}}
        (OUT / name).write_text(json.dumps(spec, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
        for uid in m['unit_ids']:
            entries[uid] = name
    return entries


def register(pages, entries):
    index = OUT / 'content.json'
    raw = index.read_bytes().decode('utf-8')
    assert '\r\n' in raw
    text = raw.replace('\r\n', '\n')
    data = json.loads(text)
    for atlas in pages:
        digest = content_digest.blake2((OUT / atlas).read_bytes())
        line = f'    "{atlas}": "{digest}"'
        if atlas in data['assets']:
            text = re.sub(rf'    "{re.escape(atlas)}": "[0-9a-f]{{64}}"', line, text)
        else:
            end = text.index('\n  },\n', text.index('  "assets": {'))
            text = text[:end] + ',\n' + line + text[end:]
    start = text.index('  "stock_sprites": {\n')
    end = text.index('\n  },\n', start)
    table = dict(data['stock_sprites'])
    table.update({str(uid): name for uid, name in entries.items()})
    block = '  "stock_sprites": {\n' + ',\n'.join(f'    "{uid}": "{name}"' for uid, name in sorted(table.items(), key=lambda kv: int(kv[0])))
    text = text[:start] + block + text[end:]
    json.loads(text)
    index.write_bytes(text.replace('\n', '\r\n').encode('utf-8'))


def main():
    maps = recolor.load_maps()
    pages = write_pages(maps)
    write_icons(maps)
    entries = write_texture_only_specs(maps)
    register(pages, entries)
    sys.path.insert(0, str(REPO / 'artwork' / 'msadv_frames_20261024'))
    import build_stock_sprites as bss
    names = {uid: bss.build(uid) for uid in bss.UNITS}
    bss.register(names)
    print('stock sprites', entries, names)


if __name__ == '__main__':
    main()
