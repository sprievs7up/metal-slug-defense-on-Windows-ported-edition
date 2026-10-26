"""未来 5 连发马克斯奈尔（s1xlv.mcsnl_five_future，僚机 s1xlv.mcsnl_five_future_wing）资源与单位文件生成（2026-10-27）。

原版 5 连发马克斯奈尔（REGIMENTAL MH-6s，UnitID 187）出击后，领队（原生 BattleAction_McsnlFive）以写死的 UnitID 187 另行生成
4 架僚机单位（僚机 +0x24 为 2–5）。本单位以 187 的精灵描述符、动作脚本与音效为基础，领队与僚机分为两个单位：
- 领队 s1xlv.mcsnl_five_future：行为 formation_wingmen（核心 r99）使其生成的僚机改为内部单位 s1xlv.mcsnl_five_future_wing。
- 两者数值相同（用户设定，见 UNIT_VALUES），每架各有生命（原版每架即为 187 的生命）。

图集 mcsnl_five_out.obm 只改调色板与少量像素索引，生成两张：
- 领队 mcsnl_five_future.obm：红色领队（帧 0–14、200–212 的 15 个矩形）专用的 5 级红色与旋翼罩等部件的 5 级橄榄色 → 紫色
  （用户 2026-10-27：顶部不用未来机体的蓝色而用紫色；R-SHOBU VER.F 的浅紫过淡、易与普通马克斯奈尔混淆，加深）。紫色取
  未来 R 菖蒲的色相，按原版红色领队各级的亮度加深（R.R-SHOBU 186 → R-SHOBU VER.F 277 的原版换色同样逐级对应，见
  verification/future_mcsnl_five_20261027/match_frames.py）。单位菜单动作演示中由领队画出的僚机（帧 184–198、214–226 的
  15 个矩形）另分调色板索引，保持未来马克斯奈尔的蓝色。
- 僚机 mcsnl_five_future_wing.obm：机体色 → 原版未来马克斯奈尔（MH-6s VER.F，UnitID 378）的配色（187 与 378 的 147 对同形矩形
  逐像素配对，10 种机体色各取唯一的主对应）；只换色，性能不取 378。领队专用红色同样换紫色（僚机不绘制领队帧）。
- 两张图集中，领队与僚机共用的深色机体色（引擎舱等）取未来马克斯奈尔的灰色；尾翼的红色条纹、黄色细节与火光保持原版。
- 子弹（帧 160 / 162 的 8×8 矩形 87 / 88）：用户 2026-10-27 要求与未来 MV-280C（MV-280C VER.F，UnitID 377）一样的蓝色。两者像素
  结构相同（逐格同形），按位置取 VER.F 子弹图集 bullet_mv-280c_out.obm 矩形 55 / 56 的颜色，另分 10 个调色板索引（两张图集相同）。
- 两个单位都带行为 piercing_shots（核心 r100）：子弹命中后继续下落，依次结算之后接触的目标，同一目标只结算一次。
- 头像：187 头像（unit_icon_02 的 (178,454,40,46)，锚点 (-5,1)）按领队的换色表换色，写入社区合并图集 unit_icon_02.obm 的空位；
  僚机共用该头像。
配对与分析脚本在 verification/future_mcsnl_five_20261027/（match_rects.py、match_frames.py、analyze_five.py）。

运行：E:/anaconda3/python.exe -I artwork/future_mcsnl_five_20261027/build_future_mcsnl_five.py [--preview]
（--preview 只写 out/；否则另写 community_content/ 的两张图集、unit_icon_02.obm、两个单位文件与 content.json）。
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

KEY, WING_KEY = 's1xlv.mcsnl_five_future', 's1xlv.mcsnl_five_future_wing'
BASE_ATLAS, ATLAS, WING_ATLAS, ICON_ATLAS = 'mcsnl_five_out.obm', 'mcsnl_five_future.obm', 'mcsnl_five_future_wing.obm', 'unit_icon_02.obm'
# 187 的领队与僚机矩形（原生描述符 0x1097652c 中帧 0–14、200–212 与帧 184–198、214–226 引用的各 15 个矩形，x、y、宽、高）；
# 两组与其余矩形（旋翼部件、火光、子弹、碎块）在图集中互不重叠。
LEADER_RECTS = [(0, 0, 78, 60), (0, 61, 77, 65), (0, 127, 68, 75), (69, 144, 43, 73), (78, 70, 49, 73), (79, 0, 73, 69),
                (113, 148, 77, 65), (128, 74, 44, 73), (153, 0, 69, 73), (173, 74, 78, 60), (191, 135, 49, 73),
                (223, 0, 73, 69), (252, 74, 68, 75), (297, 0, 69, 73), (367, 0, 43, 73)]
WING_RECTS = [(0, 254, 78, 60), (0, 315, 77, 65), (0, 381, 73, 69), (74, 389, 43, 73), (78, 315, 69, 73), (118, 403, 77, 65),
              (148, 256, 57, 73), (148, 330, 44, 72), (193, 330, 78, 60), (196, 391, 57, 73), (206, 252, 49, 73),
              (256, 256, 73, 69), (272, 326, 49, 73), (322, 326, 43, 73), (330, 250, 69, 73)]
# 色阶（由暗到亮 5 级）：领队红色、僚机与部件的橄榄色逐级对应（187 领队与僚机同形矩形逐像素配对）。
RED = [(96, 0, 0), (152, 24, 0), (192, 80, 24), (232, 160, 40), (248, 224, 176)]
OLIVE = [(79, 63, 16), (96, 80, 47), (128, 112, 79), (175, 159, 112), (255, 240, 192)]
# 未来马克斯奈尔（378）的配色：187 → 378 同形矩形逐像素配对的主对应（verification/.../match_rects.py 187 378）。
FUTURE_OLIVE = [(16, 57, 107), (57, 90, 140), (107, 132, 189), (165, 189, 222), (222, 247, 255)]
FUTURE_SHARED = {(48, 32, 0): (33, 33, 57), (56, 32, 0): (49, 57, 57), (88, 56, 0): (74, 82, 82),
                 (120, 96, 48): (123, 123, 123), (152, 128, 80): (156, 165, 165)}
# 紫色：未来 R 菖蒲（R-SHOBU VER.F）的色相，亮度按原版红色领队各级（Y ≈ 29 / 60 / 107 / 168 / 226）加深，
# 得 Y ≈ 30 / 54 / 90 / 145 / 212（R-SHOBU VER.F 原色 (49,49,82)、(90,90,123)、(140,123,156)、(214,189,206)、(248,240,240)
# 为 53 / 94 / 132 / 198 / 243，2026-10-27 第一版采用，用户评估过淡）。
PURPLE = [(40, 16, 72), (72, 32, 120), (112, 64, 168), (168, 120, 216), (224, 200, 240)]
SOURCE_ICON, ICON_ANCHOR = (178, 454, 40, 46), [-5, 1]
# 子弹：187 矩形 87（帧 160）/ 88（帧 162）的左上角 ↔ VER.F 子弹图集中矩形 55 / 56 的左上角（同 mv280c 生成脚本的 BULLETS）。
BULLET_ATLAS, BULLET_SIZE = 'bullet_mv-280c_out.obm', 8
BULLETS = [((48, 245), (0, 51)), ((173, 135), (8, 51))]

# 名称：简体 / 繁体按用户指定（原版繁体“未來馬庫斯那爾”有误，以“未来马克斯奈尔”为准）；英文名用半角字符（原版 187 的全角空格与
# 全角 ｓ 在宿主 STATUS 字体中显示为方框）。说明第 1 行与原版 187 相同
# （简体与德语原版无文字：简体按繁体转写，德语取 MSA 同一单位的格式并按 MSD 写“-”）；第 2、3 行为用户文本，
# 其余 9 种语言由代理翻译（待校对）。
LOCALIZATION = {
    'ZS': ('未来5连发马克斯奈尔', '普通攻击：机关炮   特殊攻击：-\n从未来而来的马克斯奈尔5连队。\n由最前方的紫色马克斯奈尔指挥攻击。'),
    'ZT': ('未來5連發馬克斯奈爾', '普通攻擊：機關砲   特殊攻擊：-\n從未來而來的馬克斯奈爾5連隊。\n由最前方的紫色馬克斯奈爾指揮攻擊。'),
    'JP': ('未来5連マクスネル', '通常攻撃：バルカン   特殊攻撃：-\n未来からやってきたマクスネルの5連隊。\n先頭の紫のマクスネルが攻撃を指揮している。'),
    'KR': ('미래 마크스넬 5개 편대', '일반 공격: 발칸     특수 공격: -\n미래에서 온 마크스넬의 5개 편대.\n선두의 보라색 마크스넬이 공격을 지휘하고 있다.'),
    'EN': ('REGIMENTAL MH-6s VER.F', 'STAND. ATK : Vulcan     SPEC. ATK : -\nFormation of 5 Max Nail soldiers from the future.\n'
                                         'The Purple leader in front directs the attack.'),
    'ES': ('MH-6s REGIMIENTO VER.F', 'ATQ ESTÁND. : Vulcano    ATQ ESPEC. :  -\nFormación de 5 soldados Max Nail del futuro.\n'
                                    'El líder morado al frente dirige el ataque.'),
    'PT': ('BATALHÃO DE MH-6 VER.F', 'ATQ. PADR. : Vulcan ATQ. ESPEC. : -\nBatalhão de 5 Masknells vindos do futuro.\n'
                                    'O líder roxo à frente lidera o ataque.'),
    'FR': ('RÉGIMENT DE MH-6S DU FUTUR', "ATT. STAND : Vulcain   ATT. SPÉ : -\nFormation de 5 soldats Max Nail venus du futur.\n"
                                        "Le chef en violet, en tête, dirige l'attaque."),
    'DE': ('MH-6S-GESCHWADER (Zukunft)', 'NORM. ANGR.: Vulkan     SPEZ. ANGR.: -\nEine Formation aus 5 Masknells aus der Zukunft.\n'
                                        'Der violette Masknell an der Spitze ist der Anführer.'),
    'IT': ('SQUADRA MH-6 VER.F', "ATC STAND.: Vulcan   ATC SPEC.: -\nFormazione di 5 soldati dal futuro.\n"
                                "Il leader in viola in testa dirige l'attacco."),
    'RU': ('Полковый вертолет MH-6 ВЕР. Эф', 'СТАНД. АТАК: Вулкан   СПЕЦ. АТАК: -\nФормирование 5-ого полка из будущего.\n'
                                            'Атакой командует фиолетовый лидер впереди.'),
}

# 用户设定（2026-10-27）：AP 450（R2 改为 550）；再出击 40 秒（1200 tick）；移速 3.7；Lv40 生命 4000；远 / 近距离攻击与原版 187 相同，
# 两组子弹均可穿透（每发命中目标数 999，同未来 MV-280C（377）绝招）；用户随后要求子弹贯穿后继续下落、依次打到其后的目标，
# 每个目标仍只结算一次（行为 piercing_shots，见 unit_files）。
# 原版 187：AP 200、再出击 800 tick、移速 3.5、Lv40 生命 3000（每架）、击退门槛 −1（每次受击均击退）、近 / 远距每发 Lv40 270、
# 命中目标数 1（状态词 17 / 24）、无特殊攻击。僚机与领队相同（原版僚机即为 187 的数据行）。
UNIT_VALUES = {
    'base_id': 187,
    'faction': 1,
    'identity': 'X Army',
    'shop_price': 300,                  # 暂定（用户未指定；同其他未来换色单位）
    'available_from_start': True,
    'ap': 550,                          # R2（2026-10-27 用户）：450 → 550；击毁返还随之为 55
    'hp_multiplier': [4, 3],            # Lv40 3000 → 4000
    'knockback_threshold_multiplier': [4, 3],   # 随生命（第 6.1 节）；原版 −1 不缩放，仍为每次受击均击退
    'special_damage_multiplier': [1, 1],
    'damage_multiplier': [1, 1],
    'move_speed_multiplier': [37, 35],  # 3.5 → 3.7
    'production_reference_id': 187,
    'production_interval_multiplier': [3, 2],   # 800 → 1200 tick
    'attack_range_multiplier': [1, 1],
    'knockback_distance_multiplier': [1, 1],
    'ballistic_range_multiplier': [1, 1],
    'status_word_values': {'17': 999, '24': 999},
}


def read_indexed(raw):
    assert raw[:4] == b'OI\x01\x08', 'expected an 8-bit indexed OI atlas with an RGBA8888 palette'
    w, h = struct.unpack_from('<HH', raw, 4)
    assert len(raw) == 8 + 1024 + w * h
    return w, h, [tuple(raw[8 + i * 4:12 + i * 4]) for i in range(256)], bytearray(raw[8 + 1024:])


def write_indexed(w, h, palette, body):
    return b'OI\x01\x08' + struct.pack('<HH', w, h) + b''.join(bytes(c) for c in palette) + bytes(body)


def read_rgba32(raw):
    assert raw[:4] == b'OI\x01\x20', 'expected a 32-bit OI atlas'
    w, h = struct.unpack_from('<HH', raw, 4)
    assert len(raw) == 8 + w * h * 4
    return w, h, bytearray(raw[8:])


def inside(rects, x, y):
    return any(rx <= x < rx + rw and ry <= y < ry + rh for rx, ry, rw, rh in rects)


def index_of(palette, where, rgb):
    hits = [i for i in where if palette[i][:3] == rgb]
    assert len(hits) == 1, (rgb, hits)
    return hits[0]


def atlas(kind, report):
    """kind：'leader'（领队图集）或 'wing'（僚机图集）。返回 (OBM 字节, 页)。"""
    w, h, palette, body = read_indexed((ASSETS / BASE_ATLAS).read_bytes())
    where = {}
    for pos, index in enumerate(body):
        if palette[index][3]:
            where.setdefault(index, []).append(pos)
    new = list(palette)
    changes = {}

    def put(index, rgb, tag):
        new[index] = (*rgb, 255)
        changes[str(index)] = [tag, list(palette[index][:3]), list(rgb), len(where.get(index, ()))]

    for src, dst in FUTURE_SHARED.items():
        put(index_of(palette, where, src), dst, 'shared')
    for src, dst in zip(RED, PURPLE):
        index = index_of(palette, where, src)
        assert all(inside(LEADER_RECTS, p % w, p // w) for p in where[index]), src   # 领队专用色
        put(index, dst, 'leader')
    used = set(body)
    free = [i for i in range(255, 0, -1) if i not in used]   # 图集中未被任何像素使用的索引
    # 子弹：逐像素换为 VER.F 子弹的颜色（同色共用一个新索引）。
    bw, _, bpal, bbody = read_indexed((ASSETS / BULLET_ATLAS).read_bytes())
    slots = {}
    for (x0, y0), (vx, vy) in BULLETS:
        for j in range(BULLET_SIZE):
            for i in range(BULLET_SIZE):
                pos = (y0 + j) * w + x0 + i
                colour = bpal[bbody[(vy + j) * bw + vx + i]]
                assert (palette[body[pos]][3] != 0) == (colour[3] != 0), ((x0, y0), i, j)
                assert not inside(LEADER_RECTS + WING_RECTS, x0 + i, y0 + j)
                if colour[3]:
                    if colour[:3] not in slots:
                        slots[colour[:3]] = free.pop(0)
                        put(slots[colour[:3]], colour[:3], 'bullet')
                        changes[str(slots[colour[:3]])][3] = 0
                    body[pos] = slots[colour[:3]]
                    changes[str(slots[colour[:3]])][3] += 1
    for src, purple, blue in zip(OLIVE, PURPLE, FUTURE_OLIVE):
        index = index_of(palette, where, src)
        if kind == 'wing':
            put(index, blue, 'wing')
            continue
        # 领队图集：部件为紫色；僚机矩形中的像素改用新索引并保持未来马克斯奈尔的蓝色（菜单动作演示中由领队画出的僚机）。
        put(index, purple, 'parts')
        assert not any(inside(LEADER_RECTS, p % w, p // w) for p in where[index]), src
        moved = [p for p in where[index] if inside(WING_RECTS, p % w, p // w)]
        if moved:
            extra = free.pop(0)
            for p in moved:
                body[p] = extra
            put(extra, blue, 'demo_wing')
            changes[str(extra)][3] = len(moved)
    report[kind] = {'size': [w, h], 'indices_used': len(where), 'changed': changes}
    return write_indexed(w, h, new, body), (w, h, new, body)


def find_icon_slot(pixels, w, h, size, start=(1748, 768)):
    """unit_icon_02 中的空位（同鼹鼠弹生成脚本：避开已登记的单位头像，区域须全透明）。"""
    used = []
    for f in (CONTENT / 'units').glob('*.json'):
        unit = json.loads(f.read_text(encoding='utf-8'))
        icon = unit['icon']
        if unit['key'] not in (KEY, WING_KEY) and icon.get('page') == 1 and 'atlas' not in icon:
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
    unit_path = CONTENT / 'units' / 'mcsnl_five_future.json'
    x0, y0, iw, ih = SOURCE_ICON
    rect = json.loads(unit_path.read_text(encoding='utf-8'))['icon']['rect'] if unit_path.exists() else find_icon_slot(pixels, w, h, (iw, ih))
    tx, ty = rect[:2]
    _, _, palette, _ = read_indexed((ASSETS / BASE_ATLAS).read_bytes())
    known = {c[:3] for c in palette if c[3]}
    mapping = {**FUTURE_SHARED, **dict(zip(RED, PURPLE)), **dict(zip(OLIVE, PURPLE))}   # 头像为领队（含顶部旋翼罩）
    unknown, changed = Counter(), 0
    for j in range(ih):
        for i in range(iw):
            src = ((y0 + j) * w + x0 + i) * 4
            dst = ((ty + j) * w + tx + i) * 4
            r, g, b, a = pixels[src:src + 4]
            if a and (r, g, b) not in known:
                unknown[(r, g, b)] += 1
            rgb = mapping.get((r, g, b), (r, g, b)) if a else (0, 0, 0)
            changed += bool(a and rgb != (r, g, b))
            pixels[dst:dst + 4] = bytes((*rgb, a))
    assert not unknown, unknown
    report['icon'] = {'source_rect': list(SOURCE_ICON), 'rect': rect, 'recoloured_pixels': changed}
    return raw[:8] + bytes(pixels), rect


def unit_files(rect):
    icon = {'page': 1, 'rect': list(rect), 'anchor': ICON_ANCHOR}
    localization = {lang: {'name': name, 'description': text} for lang, (name, text) in LOCALIZATION.items()}
    pierce = {'name': 'piercing_shots', 'version': 1, 'params': {}}
    leader = {'key': KEY, **UNIT_VALUES, 'textures': [ATLAS], 'icon': icon, 'animations': {},
              'behaviors': [{'name': 'formation_wingmen', 'version': 1, 'params': {'unit': WING_KEY}}, pierce],
              'localization': localization}
    wing = {'key': WING_KEY, **UNIT_VALUES, 'textures': [WING_ATLAS], 'icon': icon, 'animations': {},
            'behaviors': [pierce], 'localization': localization, 'internal_only': True}
    return leader, wing


def save_json(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').replace('\n', '\r\n').encode('utf-8'))


def preview(page, path, scale):
    w, h, palette, body = page
    image = Image.new('RGBA', (w, h))
    image.putdata([palette[i] for i in body])
    canvas = Image.new('RGBA', (w, h), (60, 60, 60, 255))
    canvas.alpha_composite(image)
    canvas.resize((w * scale, h * scale), Image.NEAREST).save(path)


def main():
    OUT.mkdir(exist_ok=True)
    report = {}
    leader_raw, leader_page = atlas('leader', report)
    wing_raw, wing_page = atlas('wing', report)
    icon_raw, rect = icon_atlas(report)
    preview(leader_page, OUT / 'mcsnl_five_future_out.png', 1)
    preview(wing_page, OUT / 'mcsnl_five_future_wing_out.png', 1)
    w, h, pixels = read_rgba32(icon_raw)
    icon = Image.frombytes('RGBA', (w, h), bytes(pixels)).crop((rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]))
    icon.resize((icon.width * 8, icon.height * 8), Image.NEAREST).save(OUT / 'icon_8x.png')
    if '--preview' not in sys.argv:
        index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
        for key in (KEY, WING_KEY):
            if key not in index['unit_ids']:
                index['unit_ids'][key] = max(index['unit_ids'].values()) + 1
        for name, raw in ((ATLAS, leader_raw), (WING_ATLAS, wing_raw)):
            (CONTENT / name).write_bytes(raw)
            index['assets'][name] = hashlib.blake2b(raw, digest_size=32).hexdigest()
        (CONTENT / ICON_ATLAS).write_bytes(icon_raw)   # 该资源的摘要在 content.json 中为 null，保持不变
        leader, wing = unit_files(rect)
        save_json(CONTENT / 'units' / 'mcsnl_five_future.json', leader)
        save_json(CONTENT / 'units' / 'mcsnl_five_future_wing.json', wing)
        save_json(CONTENT / 'content.json', index)
        report['unit_ids'] = {key: index['unit_ids'][key] for key in (KEY, WING_KEY)}
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'unit_ids': report.get('unit_ids'), 'icon_rect': rect,
                      'changed': {k: len(report[k]['changed']) for k in ('leader', 'wing')}}))


if __name__ == '__main__':
    main()
