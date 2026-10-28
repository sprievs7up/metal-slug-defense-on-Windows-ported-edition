"""沙包（未来）（修筑者 s1xlv.sandbag_future_builder，建筑 s1xlv.sandbag_future）资源与单位文件生成（2026-10-27）。

原版沙包工兵（SANDBAG，UnitID 5，BattleAction_Kouhei）出击后修筑沙包（UnitID 4，BattleAction_Donou）；两者共用描述符
0x1097512c 与图集 donou.obm（OI 04 08：512×256，RGB5_A1 调色板 + 8 位索引）。本单位为叛军（阵营 1）的换色版，动作脚本、
受击框、音效与修筑流程全部沿用原版（行为 build_structure，修筑时间倍率 [1, 1]）。

图集 sandbag_future.obm 以 donou.obm 为底本，保持格式与像素位置，只改调色板并为木桩另分索引：
- 建筑的矩形 0–18（待机 / 受击 0–2、倒塌 3、损毁烟尘 4–18）与工兵的矩形 19–50 在原图中不共用任何调色板索引，工兵像素与
  索引原样保留。
- 沙袋色阶（索引 5 / 12 / 21 / 30 / 39 / 47，由暗到亮 6 级）逐级换为未来兵（F.REBEL INFANTRY，UnitID 206，f-normal_out.obm）
  护甲的 6 级青色（轮廓 (24,24,0) 至高光 (248,248,232)，见 FUTURE_SUIT）。
- 木桩：原图以另一组棕色色阶（索引 8 / 11 / 17 / 23 / 27）绘制木桩，同一组颜色也散见于沙袋表面与损毁烟尘。矩形 0–3 中该
  色阶像素按 8 邻接分块，不少于 POLE_MIN 像素的块为木桩，改用新索引并换为灰色（POLE_GREY，用户要求加深后的冷灰）；其余像素（矩形 0–3 的零星点、
  矩形 4–18 的烟尘）连同烟尘专用色按亮度在青色色阶上插值（cyan_for）。木桩外侧的深色轮廓与沙袋共用索引 5，取青色轮廓色。
- 调色板为 RGB5_A1：目标颜色按各通道 5 位四舍五入写入，游戏内显示值与表中颜色每通道相差不超过 4。
头像：原版沙包工兵的头像（unit_icon_02 的 (307,471,47,39)，锚点 (1,-6)，工兵在前、沙袋与木桩在后）按颜色换色：沙袋 6 级与
木桩 5 级为头像专用色（只出现在沙袋区域），工兵、十字镐与共用轮廓不变；写入社区合并图集 unit_icon_02.obm 的空位，两单位共用。

运行：E:/anaconda3/python.exe -I artwork/sandbag_future_20261027/build_sandbag_future.py [--preview]
（--preview 只写 out/；否则另写 community_content/ 的图集、unit_icon_02.obm、两个单位文件与 content.json）。
"""
from collections import Counter
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

KEY, BUILDER_KEY = 's1xlv.sandbag_future', 's1xlv.sandbag_future_builder'
BASE_ATLAS, ATLAS, ICON_ATLAS = 'donou.obm', 'sandbag_future.obm', 'unit_icon_02.obm'
# 原生描述符 0x1097512c 的矩形（x、y、宽、高；verification/sandbag_future_20261027/runs/dump_*/units.json）：0–18 为建筑，19–50 为工兵。
STRUCTURE_RECTS = [(290, 46, 48, 35), (241, 48, 48, 36), (276, 85, 48, 35), (183, 120, 48, 40), (97, 117, 48, 47),
                   (0, 182, 48, 50), (48, 124, 47, 52), (0, 126, 47, 55), (146, 0, 47, 59), (49, 0, 47, 63), (0, 63, 47, 62),
                   (0, 0, 48, 62), (97, 60, 48, 56), (194, 0, 46, 58), (48, 64, 48, 59), (97, 0, 48, 59), (146, 60, 44, 59),
                   (191, 60, 44, 59), (446, 0, 28, 49)]
POLE_RECTS = 4            # 矩形 0–3（待机、受击两帧、倒塌）画有木桩
POLE_MIN = 4              # 木桩块的最少像素（8 邻接）
SAND = [5, 12, 21, 30, 39, 47]          # 沙袋色阶索引（由暗到亮）
STICK = [8, 11, 17, 23, 27]             # 木桩色阶索引（由暗到亮）
# 未来兵 206（f-normal_out.obm）护甲由暗到亮 6 级：索引 7、26、45、76、101、135。
FUTURE_SUIT = [(24, 24, 0), (48, 80, 64), (72, 120, 104), (128, 168, 160), (176, 200, 192), (248, 248, 232)]
# 灰色木桩：木桩色阶 5 级依次对应（暗面为主体）。用户 2026-10-27 评估初版灰白 (112,120,120)–(248,248,248) 过浅、与浅色沙袋
# 区分不足，要求加深：现行各级亮度约 57 / 89 / 121 / 153 / 185（原版木桩 44 / 64 / 92 / 117 / 151，初版 119 / 168 / 192 / 224 / 248），
# 低于沙袋亮部（156 / 191），蓝通道略高（冷灰）。
POLE_GREY = [(56, 56, 64), (88, 88, 96), (120, 120, 128), (152, 152, 160), (184, 184, 192)]
# 头像（unit_icon_02 的 32 位像素）中沙袋与木桩的专用色：与图集的两组色阶逐级对应（头像为另一幅画，颜色按 8 位记录）。
ICON_SAND = [(32, 31, 0), (79, 64, 47), (112, 111, 80), (175, 160, 128), (223, 208, 160), (255, 255, 223)]
ICON_STICK = [(63, 47, 15), (79, 64, 32), (111, 95, 63), (128, 112, 80), (160, 144, 112)]
SOURCE_ICON, ICON_ANCHOR = (307, 471, 47, 39), [1, -6]

# 名称：简体 / 繁体按用户指定。说明第 1 行取原版沙包工兵 5 的文本（简体按繁体转写；德语原版无文字，取未来重装 B 型的格式），
# 第 2、3 行为用户文本（在逗号处分行，繁体逐字转写）；其余 9 种语言的名称与第 2、3 行由代理撰写（待校对）。
LOCALIZATION = {
    'ZS': ('沙包（未来）', '普通攻击：‐     特殊攻击：‐\n完全没有任何理由被制造的兵器，\n唯一能知晓的是来自创作者的恶趣味。'),
    'ZT': ('沙包（未來）', '普通攻擊：‐     特殊攻擊：‐\n完全沒有任何理由被製造的兵器，\n唯一能知曉的是來自創作者的惡趣味。'),
    'JP': ('土嚢（未来）', '通常攻撃：‐     特殊攻撃：‐\n何の理由もなく造られた兵器。\n唯一わかるのは、作者の悪趣味によるものだということだ。'),
    'KR': ('샌드백 (미래)', '일반 공격: -     특수 공격: -\n아무런 이유 없이 만들어진 병기.\n알 수 있는 것은 제작자의 짓궂은 취향뿐이다.'),
    'EN': ('SANDBAG (Future)', 'STAND. ATK : -     SPEC. ATK : -\nA weapon built for no reason whatsoever.\n'
                               "The only clue is its creator's twisted sense of humor."),
    'ES': ('BOLSA DE ARENA (Futuro)', 'ATQ. ESTÁND. : -    ATQ. ESPEC. : -\nUn arma fabricada sin razón alguna.\n'
                                      'Solo se sabe que nace del mal gusto de su creador.'),
    'PT': ('SACO DE AREIA (Futuro)', 'ATQ. PADR. : -   ATQ. ESPEC. : -\nUma arma criada sem motivo algum.\n'
                                     'Só se sabe que vem do gosto duvidoso de seu criador.'),
    'FR': ('SAC DE SABLE (Futur)', "ATT. STAND : -   ATT. SPÉ : -\nUne arme fabriquée sans la moindre raison.\n"
                                   "Seul indice : l'humour douteux de son créateur."),
    'DE': ('SANDSACK (Zukunft)', 'STANDARDANGR. : -     SPEZIALANGR. : -\nEine Waffe, gebaut ohne jeden Grund.\n'
                                 'Bekannt ist nur der schräge Humor ihres Schöpfers.'),
    'IT': ('SACCO DI SABBIA (Futuro)', "ATC STAND.: -   ATC SPEC.: -\nUn'arma costruita senza alcun motivo.\n"
                                       'Si sa solo che nasce dal gusto perverso del suo creatore.'),
    'RU': ('САНДБАГ (будущее)', 'СТАНД. АТАК: -   СПЕЦ. АТАК: -\nОружие, созданное без всякой причины.\n'
                                'Известно лишь, что это причуда его создателя.'),
}

# 用户设定（2026-10-27）：AP 100；生命 16000（Lv40）；再出击 20.8 秒；修筑时间与原版沙包相同；其余与原版沙包相同。
# 原版：沙包工兵 5 AP 40、再出击 500 tick（各等级相同）；沙包 4 生命 Lv1 / 10 / 20 / 30 / 40 = 1200 / 2400 / 3600 / 4800 / 6000，
# 击退门槛 −1（Donou 不经过击退计量）。
COMMON = {
    'faction': 1,
    'identity': 'Rebel Army',
    'shop_price': 100,                  # 暂定（用户未指定；同防空炮台）
    'available_from_start': True,
    'ap': 100,                          # 击毁返还 10（加载器按 AP 的 10% 写入）
    'special_damage_multiplier': [1, 1],
    'damage_multiplier': [1, 1],
    'move_speed_multiplier': [1, 1],
    'attack_wait_multiplier': [1, 1],
    'attack_range_multiplier': [1, 1],
    'knockback_distance_multiplier': [1, 1],
    'ballistic_range_multiplier': [1, 1],
    'production_reference_id': 5,
    'production_interval_multiplier': [156, 125],   # 500 → 624 tick（20.8 秒）
}
STRUCTURE_VALUES = {'base_id': 4, **COMMON,
                    'hp_multiplier': [8, 3],                    # Lv40 6000 → 16000
                    'knockback_threshold_multiplier': [8, 3]}   # 随生命（第 6.1 节）；原版 −1 不缩放
BUILDER_VALUES = {'base_id': 5, **COMMON,
                  'hp_multiplier': [1, 1],                      # 修筑者生命按 content.json 的 engineer_hp 缺省规则
                  'knockback_threshold_multiplier': [1, 1]}


def read_atlas(raw):
    assert raw[:4] == b'OI\x04\x08', 'expected an 8-bit indexed OI atlas with an RGB5_A1 palette'
    w, h = struct.unpack_from('<HH', raw, 4)
    assert len(raw) == 8 + 512 + w * h
    return w, h, list(struct.unpack_from('<256H', raw, 8)), bytearray(raw[8 + 512:])


def write_atlas(w, h, palette, body):
    return b'OI\x04\x08' + struct.pack('<HH', w, h) + struct.pack('<256H', *palette) + bytes(body)


def unpack5551(v):
    """显示值（5 位按 v<<3 | v>>2 扩展到 8 位）。"""
    r, g, b = (v >> 11) & 31, (v >> 6) & 31, (v >> 1) & 31
    return (r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2, 255 if v & 1 else 0)


def pack5551(rgb):
    r, g, b = (min(31, round(c * 31 / 255)) for c in rgb)
    return r << 11 | g << 6 | b << 1 | 1


def luma(rgb):
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def cyan_for(rgb, anchors):
    """按亮度在青色色阶上分段线性插值；anchors 为 [(源亮度, 目标颜色)]（由暗到亮），两端取端点色。"""
    y = luma(rgb)
    if y <= anchors[0][0]:
        return anchors[0][1]
    for (y0, c0), (y1, c1) in zip(anchors, anchors[1:]):
        if y <= y1:
            t = (y - y0) / (y1 - y0)
            return tuple(round(a + (b - a) * t) for a, b in zip(c0, c1))
    return anchors[-1][1]


def pole_mask(w, body, used_stick):
    """矩形 0–3 中木桩色阶像素的 8 邻接分块；返回木桩像素位置集合与各块大小。"""
    poles, sizes = set(), []
    for rx, ry, rw, rh in STRUCTURE_RECTS[:POLE_RECTS]:
        cells = {(x, y) for y in range(ry, ry + rh) for x in range(rx, rx + rw) if body[y * w + x] in used_stick}
        seen = set()
        for start in sorted(cells, key=lambda c: (c[1], c[0])):
            if start in seen:
                continue
            block, stack = [], [start]
            seen.add(start)
            while stack:
                x, y = stack.pop()
                block.append((x, y))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        n = (x + dx, y + dy)
                        if n in cells and n not in seen:
                            seen.add(n)
                            stack.append(n)
            sizes.append([rx, ry, len(block)])
            if len(block) >= POLE_MIN:
                poles.update(y * w + x for x, y in block)
    return poles, sizes


def atlas(report):
    w, h, palette, body = read_atlas((ASSETS / BASE_ATLAS).read_bytes())
    inside = set()
    for rx, ry, rw, rh in STRUCTURE_RECTS:
        inside.update(y * w + x for y in range(ry, ry + rh) for x in range(rx, rx + rw))
    structure = Counter(body[p] for p in inside if palette[body[p]] & 1)
    builder = Counter(body[p] for p in range(w * h) if p not in inside and palette[body[p]] & 1)
    assert not set(structure) & set(builder), set(structure) & set(builder)   # 建筑与工兵不共用索引
    assert set(SAND + STICK) <= set(structure)
    shown = {i: unpack5551(palette[i])[:3] for i in range(256)}
    anchors = [(luma(shown[i]), c) for i, c in zip(SAND, FUTURE_SUIT)]
    new = list(palette)
    changes = {}

    def put(index, rgb, tag, count):
        new[index] = pack5551(rgb)
        changes[str(index)] = [tag, list(shown[index]), list(rgb), list(unpack5551(new[index])[:3]), count]

    for i, rgb in zip(SAND, FUTURE_SUIT):
        put(i, rgb, 'sand', structure[i])
    for i in sorted(structure):
        if i not in SAND:
            put(i, cyan_for(shown[i], anchors), 'stick_dust' if i in STICK else 'dust', structure[i])
    poles, sizes = pole_mask(w, body, set(STICK))
    used = set(body)
    free = [i for i in range(255, 0, -1) if i not in used]   # 图集中未被任何像素使用的索引
    pole_index = {}
    for i, grey in zip(STICK, POLE_GREY):
        moved = [p for p in poles if body[p] == i]
        if moved:
            pole_index[i] = free.pop(0)
            for p in moved:
                body[p] = pole_index[i]
            put(pole_index[i], grey, 'pole', len(moved))
    report['atlas'] = {'size': [w, h], 'structure_indices': len(structure), 'builder_indices': len(builder),
                       'pole_pixels': len(poles), 'stick_blocks': sizes, 'pole_index': pole_index, 'changed': changes}
    return write_atlas(w, h, new, body), (w, h, [unpack5551(v) for v in new], body)


def read_rgba32(raw):
    assert raw[:4] == b'OI\x01\x20', 'expected a 32-bit OI atlas'
    w, h = struct.unpack_from('<HH', raw, 4)
    assert len(raw) == 8 + w * h * 4
    return w, h, bytearray(raw[8:])


def find_icon_slot(pixels, w, h, size, start=(1748, 768)):
    """unit_icon_02 中的空位（同未来 5 连发马克斯奈尔生成脚本：避开已登记的单位头像，区域须全透明）。"""
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


def icon_atlas(report):
    raw = (CONTENT / ICON_ATLAS).read_bytes()
    w, h, pixels = read_rgba32(raw)
    unit_path = CONTENT / 'units' / 'sandbag_future_builder.json'
    x0, y0, iw, ih = SOURCE_ICON
    rect = json.loads(unit_path.read_text(encoding='utf-8'))['icon']['rect'] if unit_path.exists() else find_icon_slot(pixels, w, h, (iw, ih))
    tx, ty = rect[:2]
    mapping = {**dict(zip(ICON_SAND, FUTURE_SUIT)), **dict(zip(ICON_STICK, POLE_GREY))}
    counts = Counter()
    for j in range(ih):
        for i in range(iw):
            src = ((y0 + j) * w + x0 + i) * 4
            dst = ((ty + j) * w + tx + i) * 4
            r, g, b, a = pixels[src:src + 4]
            if a and (r, g, b) in mapping:
                counts[(r, g, b)] += 1
                if i < 16:   # 头像左侧 16 列为工兵，换色只应落在沙袋区域（两腿之间露出的沙袋除外，见下）
                    counts['left'] += 1
            rgb = mapping.get((r, g, b), (r, g, b)) if a else (0, 0, 0)
            pixels[dst:dst + 4] = bytes((*rgb, a))
    assert set(mapping) <= set(counts), set(mapping) - set(counts)
    report['icon'] = {'source_rect': list(SOURCE_ICON), 'rect': rect,
                      'recoloured': {str(k): v for k, v in counts.items()}}
    return raw[:8] + bytes(pixels), rect


def unit_files(rect):
    icon = {'page': 1, 'rect': list(rect), 'anchor': ICON_ANCHOR}
    localization = {lang: {'name': name, 'description': text} for lang, (name, text) in LOCALIZATION.items()}
    builder = {'key': BUILDER_KEY, **BUILDER_VALUES, 'textures': [ATLAS], 'icon': icon, 'animations': {},
               'behaviors': [{'name': 'build_structure', 'version': 1,
                              'params': {'structure': KEY, 'construction_time_multiplier': [1, 1]}}],
               'localization': localization}
    structure = {'key': KEY, **STRUCTURE_VALUES, 'menu_reference_id': 5, 'internal_only': True, 'textures': [ATLAS],
                 'icon': icon, 'animations': {}, 'localization': localization}
    return builder, structure


def save_json(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').replace('\n', '\r\n').encode('utf-8'))


def preview(page, path, scale, background=(60, 60, 60, 255)):
    w, h, palette, body = page
    image = Image.new('RGBA', (w, h))
    image.putdata([palette[i] for i in body])
    canvas = Image.new('RGBA', (w, h), background)
    canvas.alpha_composite(image)
    canvas.resize((w * scale, h * scale), Image.NEAREST).save(path)


def main():
    OUT.mkdir(exist_ok=True)
    report = {}
    atlas_raw, page = atlas(report)
    icon_raw, rect = icon_atlas(report)
    preview(page, OUT / 'sandbag_future_out.png', 2)
    w, h, pixels = read_rgba32(icon_raw)
    icon = Image.frombytes('RGBA', (w, h), bytes(pixels)).crop((rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]))
    canvas = Image.new('RGBA', icon.size, (60, 60, 60, 255))
    canvas.alpha_composite(icon)
    canvas.resize((icon.width * 8, icon.height * 8), Image.NEAREST).save(OUT / 'icon_8x.png')
    if '--preview' not in sys.argv:
        index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
        for key in (BUILDER_KEY, KEY):
            if key not in index['unit_ids']:
                index['unit_ids'][key] = max(index['unit_ids'].values()) + 1
        (CONTENT / ATLAS).write_bytes(atlas_raw)
        index['assets'][ATLAS] = hashlib.blake2b(atlas_raw, digest_size=32).hexdigest()
        (CONTENT / ICON_ATLAS).write_bytes(icon_raw)   # 该资源的摘要在 content.json 中为 null，保持不变
        builder, structure = unit_files(rect)
        save_json(CONTENT / 'units' / 'sandbag_future_builder.json', builder)
        save_json(CONTENT / 'units' / 'sandbag_future.json', structure)
        save_json(CONTENT / 'content.json', index)
        report['unit_ids'] = {key: index['unit_ids'][key] for key in (BUILDER_KEY, KEY)}
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'unit_ids': report.get('unit_ids'), 'icon_rect': rect, 'pole_pixels': report['atlas']['pole_pixels'],
                      'pole_index': report['atlas']['pole_index'], 'changed': len(report['atlas']['changed'])}))


if __name__ == '__main__':
    main()
