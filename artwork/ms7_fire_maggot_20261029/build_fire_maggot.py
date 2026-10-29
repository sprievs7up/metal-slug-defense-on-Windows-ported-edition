"""橘红色蛆群（MS7 任务 3 的火焰虫群）资源与单位文件生成（2026-10-29）。

原生 MAGGOT（蛆蟲）：可出击的工兵 UnitID 95（BattleAction_Kouhei，图集 donou.obm）修筑内部单位 90（BattleAction_Maggot，
图集 maggot_out.obm：OI 01 08，512×256，RGBA8 调色板 + 8 位索引）。本单位只换 90 的调色板：白色蛆体的米白色阶（索引 4/5/7/8/10/13/18/22/25/26，
由暗到亮）逐级换为橘红色阶（ORANGE，按 MS7 DS 录像 A 276 秒的橘红虫团取色、按 DS 15 位色取 8 的倍数）；暗红轮廓（1、2）、
原图的火焰与爆裂效果色（3/6/12/15/17/20/23/24）与橄榄色干尸 / 尘土色（9/11/14/16/21）不变。动作脚本、受击框、音效与修筑流程沿用原版
（`animations` 为空）。攻击属性三组均为 1（火焰；原生 90 为 4）。
头像：原生 95 的头像（unit_icon_02 的 (98,754,38,26)，锚点 (-6,-18)）按同一色阶对应换色，写入社区合并图集 unit_icon_02.obm 的空位。

运行：E:/anaconda3/python.exe -I artwork/ms7_fire_maggot_20261029/build_fire_maggot.py [--preview]
（--preview 只写 out/；否则另写 community_content/ 的图集、unit_icon_02.obm、两个单位文件与 content.json）。
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSETS = REPO / 'game_data/assets/com.snkplaymore.android003'
CONTENT = REPO / 'community_content'
OUT = HERE / 'out'

KEY, BUILDER_KEY = 's1xlv.fire_maggot', 's1xlv.fire_maggot_builder'
BASE_ATLAS, ATLAS, ICON_ATLAS = 'maggot_out.obm', 'fire_maggot.obm', 'unit_icon_02.obm'
CREAM = [4, 5, 7, 8, 10, 13, 18, 22, 25, 26]          # 米白蛆体色阶（由暗到亮）
ORANGE = [(56, 16, 0), (80, 24, 0), (112, 40, 8), (144, 56, 16), (176, 72, 24), (216, 104, 32), (240, 136, 48),
          (248, 176, 80), (248, 208, 120), (248, 240, 184)]
SOURCE_ICON, ICON_ANCHOR = (98, 754, 38, 26), [-6, -18]

# 名称与说明为代理撰写（待用户确认 / 校对）。说明第 1 行按原生 MAGGOT 的攻击名（MSA：通常攻撃：とびつき　特殊攻撃：突撃）。
LOCALIZATION = {
    'ZS': ('火焰蛆虫', '普通攻击：扑咬     特殊攻击：突击\n全身带火的橘红色蛆虫成群而来，\n碰到的东西都会烧起来。'),
    'ZT': ('火焰蛆蟲', '普通攻擊：撲咬     特殊攻擊：突擊\n全身帶火的橘紅色蛆蟲成群而來，\n碰到的東西都會燒起來。'),
    'JP': ('ファイアマゴット', '通常攻撃：とびつき     特殊攻撃：突撃\n炎をまとった橙色のマゴットの群れ。\n触れたものは燃え上がる。'),
    'KR': ('파이어 매곳', '일반 공격: 덤벼들기     특수 공격: 돌격\n불길을 두른 주황색 구더기 떼.\n닿는 것은 모두 불타오른다.'),
    'EN': ('FIRE MAGGOT', 'STAND. ATK : Pounce     SPEC. ATK : Charge\nA swarm of orange maggots wreathed in flame.\n'
                          'Whatever they touch bursts into fire.'),
    'ES': ('LARVA DE FUEGO', 'ATQ. ESTÁND. : Abalanzarse    ATQ. ESPEC. : Embestida\nUn enjambre de larvas naranjas envueltas en llamas.\n'
                             'Todo lo que tocan arde.'),
    'PT': ('LARVA DE FOGO', 'ATQ. PADR. : Bote   ATQ. ESPEC. : Investida\nUm enxame de larvas laranja envoltas em chamas.\n'
                            'Tudo o que tocam pega fogo.'),
    'FR': ('ASTICOT DE FEU', 'ATT. STAND : Bond   ATT. SPÉ : Charge\nUn essaim d\'asticots orange enveloppés de flammes.\n'
                             'Tout ce qu\'ils touchent s\'embrase.'),
    'DE': ('FEUERMADE', 'STANDARDANGR. : Sprung     SPEZIALANGR. : Ansturm\nEin Schwarm orangefarbener Maden in Flammen.\n'
                        'Alles, was sie berühren, fängt Feuer.'),
    'IT': ('LARVA DI FUOCO', 'ATC STAND.: Balzo   ATC SPEC.: Carica\nUno sciame di larve arancioni avvolte dalle fiamme.\n'
                             'Tutto ciò che toccano prende fuoco.'),
    'RU': ('ОГНЕННАЯ ЛИЧИНКА', 'СТАНД. АТАК: Прыжок   СПЕЦ. АТАК: Натиск\nРой оранжевых личинок, охваченных пламенем.\n'
                               'Всё, чего они касаются, вспыхивает.'),
}

# 数值（R1，用户 2026-10-29 指定）：蛆群 Lv40 生命 2000（原生 1500，[4, 3]）、普攻与绝招伤害 330（原生 270，[11, 9]，近距 240 不变）、
# AP 110（原生 90 + 20）、勋章价格 90；其余沿用原生 MAGGOT（95 / 90）。攻击属性改为火焰。
COMMON = {
    'faction': 4,                      # 原生 90 / 95 数据行阵营字 4（同木乃伊召唤箱 MKII）
    'identity': 'Independent Army',
    'shop_price': 90,                  # 用户 2026-10-29 指定
    'available_from_start': True,
    'ap': 110,                         # 原生 95 的 AP 90 + 20（用户 2026-10-29；击毁返还 11）
    'special_damage_multiplier': [1, 1],
    'damage_multiplier': [1, 1],
    'move_speed_multiplier': [1, 1],
    'attack_wait_multiplier': [1, 1],
    'attack_range_multiplier': [1, 1],
    'knockback_distance_multiplier': [1, 1],
    'ballistic_range_multiplier': [1, 1],
    'production_reference_id': 95,
    'production_interval_multiplier': [1, 1],
    'hp_multiplier': [1, 1],
    'knockback_threshold_multiplier': [1, 1],
}
STRUCTURE_VALUES = {'base_id': 90, **COMMON, 'menu_reference_id': 95, 'internal_only': True,
                    'hp_multiplier': [4, 3], 'knockback_threshold_multiplier': [4, 3],   # 第 6.1 节联动；原生 -1 不缩放
                    'normal_damage_multiplier': [11, 9], 'special_damage_multiplier': [11, 9],
                    'attack_attributes': {'melee': 1, 'normal': 1, 'special': 1}}
BUILDER_VALUES = {'base_id': 95, **COMMON}


def read_atlas(raw):
    assert raw[:4] == b'OI\x01\x08', 'expected an 8-bit indexed OI atlas with an RGBA8 palette'
    w, h = struct.unpack_from('<HH', raw, 4)
    assert len(raw) == 8 + 1024 + w * h
    return w, h, [list(raw[8 + 4 * i:12 + 4 * i]) for i in range(256)], raw[8 + 1024:]


def write_atlas(w, h, palette, body):
    return b'OI\x01\x08' + struct.pack('<HH', w, h) + bytes(v for c in palette for v in c) + bytes(body)


def recolor_palette(palette):
    out = [list(c) for c in palette]
    for i, rgb in zip(CREAM, ORANGE):
        out[i] = [*rgb, palette[i][3]]
    return out


def image(w, h, palette, body):
    im = Image.new('RGBA', (w, h))
    im.putdata([tuple(palette[i]) for i in body])
    return im


def icon_map(base_palette):
    """头像为 32 位像素：把头像中与图集米白色阶相同的颜色换为对应橘红色，其余不变。"""
    return {tuple(base_palette[i][:3]): rgb for i, rgb in zip(CREAM, ORANGE)}


def read_rgba32(raw):
    assert raw[:4] == bytes((79, 73, 1, 32)), 'expected a 32-bit OI atlas'
    w, h = struct.unpack_from('<HH', raw, 4)
    assert len(raw) == 8 + w * h * 4
    return w, h, bytearray(raw[8:])


def find_icon_slot(pixels, w, h, size, start=(1748, 768)):
    """unit_icon_02 中的空位（同沙包（未来）生成脚本：避开已登记的单位头像，区域须全透明）。"""
    used = []
    for f in (CONTENT / 'units').glob('*.json'):
        unit = json.loads(f.read_text(encoding='utf-8'))
        icon = unit['icon']
        if unit['key'] not in (KEY, BUILDER_KEY) and icon.get('page') == 1 and 'atlas' not in icon:
            used.append(icon['rect'])
    iw, ih = size
    for y in range(start[1], h - ih, 2):
        for x in range(start[0] if y == start[1] else 0, w - iw, 2):
            if any(not (x + iw + 2 <= u[0] or x >= u[0] + u[2] + 2 or y + ih + 2 <= u[1] or y >= u[1] + u[3] + 2) for u in used):
                continue
            if any(pixels[((y + j) * w + x + i) * 4 + 3] for j in range(ih) for i in range(iw)):
                continue
            return [x, y, iw, ih]
    raise RuntimeError('no free icon slot')


def icon_atlas(base_palette, report):
    raw = (CONTENT / ICON_ATLAS).read_bytes()
    w, h, pixels = read_rgba32(raw)
    unit_path = CONTENT / 'units' / 'fire_maggot_builder.json'
    x0, y0, iw, ih = SOURCE_ICON
    rect = json.loads(unit_path.read_text(encoding='utf-8'))['icon']['rect'] if unit_path.exists() else find_icon_slot(pixels, w, h, (iw, ih))
    tx, ty = rect[:2]
    mapping = icon_map(base_palette)
    counts, kept = 0, 0
    for j in range(ih):
        for i in range(iw):
            src = ((y0 + j) * w + x0 + i) * 4
            dst = ((ty + j) * w + tx + i) * 4
            r, g, b, a = pixels[src:src + 4]
            if a and (r, g, b) in mapping:
                counts += 1
            elif a:
                kept += 1
            rgb = mapping.get((r, g, b), (r, g, b)) if a else (0, 0, 0)
            pixels[dst:dst + 4] = bytes((*rgb, a))
    report['icon'] = {'source_rect': list(SOURCE_ICON), 'rect': rect, 'recoloured_pixels': counts, 'kept_pixels': kept}
    return raw[:8] + bytes(pixels), rect


def unit_files(rect):
    icon = {'page': 1, 'rect': list(rect), 'anchor': ICON_ANCHOR}
    localization = {lang: {'name': name, 'description': text} for lang, (name, text) in LOCALIZATION.items()}
    builder = {'key': BUILDER_KEY, **BUILDER_VALUES, 'textures': ['donou.obm'], 'icon': icon, 'animations': {},   # 工兵沿用原版图集
               'behaviors': [{'name': 'build_structure', 'version': 1,
                              'params': {'structure': KEY, 'construction_time_multiplier': [1, 1]}}],
               'localization': localization}
    structure = {'key': KEY, **STRUCTURE_VALUES, 'textures': [ATLAS], 'icon': icon, 'animations': {}, 'localization': localization}
    return builder, structure


def save_json(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + chr(10)).encode('utf-8'))


def main(preview):
    OUT.mkdir(parents=True, exist_ok=True)
    w, h, pal, body = read_atlas((ASSETS / BASE_ATLAS).read_bytes())
    new_pal = recolor_palette(pal)
    atlas = write_atlas(w, h, new_pal, body)
    before, after = image(w, h, pal, body), image(w, h, new_pal, body)
    sheet = Image.new('RGBA', (w * 2, h * 2 * 2 + 8), (40, 60, 60, 255))
    for k, im in enumerate((before, after)):
        bg = Image.new('RGBA', (w, h), (40, 60, 60, 255))
        bg.alpha_composite(im)
        sheet.paste(bg.resize((w * 2, h * 2), Image.NEAREST), (0, k * (h * 2 + 8)))
    sheet.save(OUT / 'fire_maggot_atlas_before_after.png')
    (OUT / ATLAS).write_bytes(atlas)
    report = {'atlas': ATLAS, 'bytes': len(atlas), 'recolored_indices': CREAM, 'orange': ORANGE}
    icon_raw, rect = icon_atlas(pal, report)
    iw, ih, ipx = read_rgba32(icon_raw)
    icon = Image.frombytes('RGBA', (iw, ih), bytes(ipx)).crop((rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]))
    canvas = Image.new('RGBA', icon.size, (60, 60, 60, 255))
    canvas.alpha_composite(icon)
    canvas.resize((icon.width * 8, icon.height * 8), Image.NEAREST).save(OUT / 'icon_8x.png')
    if not preview:
        index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
        for key in (BUILDER_KEY, KEY):
            if key not in index['unit_ids']:
                index['unit_ids'][key] = max(index['unit_ids'].values()) + 1
        (CONTENT / ATLAS).write_bytes(atlas)
        index['assets'][ATLAS] = hashlib.blake2b(atlas, digest_size=32).hexdigest()
        (CONTENT / ICON_ATLAS).write_bytes(icon_raw)   # 该资源的摘要在 content.json 中为 null，保持不变
        builder, structure = unit_files(rect)
        save_json(CONTENT / 'units' / 'fire_maggot_builder.json', builder)
        save_json(CONTENT / 'units' / 'fire_maggot.json', structure)
        save_json(CONTENT / 'content.json', index)
        report['unit_ids'] = {key: index['unit_ids'][key] for key in (BUILDER_KEY, KEY)}
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'unit_ids': report.get('unit_ids'), 'icon': report['icon']}, ensure_ascii=False))


if __name__ == '__main__':
    main('--preview' in sys.argv)
