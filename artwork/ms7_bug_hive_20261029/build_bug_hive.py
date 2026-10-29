"""虫穴（MS7 任务 3 的骷髅状虫巢，召唤原版二輪戰車 CHARIOT 167）资源与单位文件生成（2026-10-29）。

结构：可出击的工兵 s1xlv.bug_hive_builder（基准 77 木乃伊召唤箱工兵，BattleAction_Kouhei，图集 donou.obm）以 build_structure
修筑内部单位 s1xlv.bug_hive（基准 64 木乃伊召唤箱，动作类沿用）；召唤对象以行为库 v26 的 summon_native_unit 指定为原版 167。

外观：素材表 “DS / DSi - Metal Slug 7 - Miscellaneous - Mission 3 Environmental Objects”（Gussprint 拆图，DS 像素，白底、特效区绿底）
的骷髅状虫巢 (3,980,65,93)、10 帧碎块 (y 981) 与 8 帧爆散粒子 (y 1015–1065)；R8 起虫巢本体改用用户修图
（R9 为 handoff/bug_hive_horizontal_93x65 NEW2.png）。描述符沿用原生 64 的帧偏移结构
（F0/F5/F10/F15 两块、F3/F8/F13/F18 一块、F20–F106 各一块），帧内容换为：
  F0 / F10 虫巢；F5 / F15 虫巢提亮 1.25 倍（原生召唤时与 F0 / F10 交替）；门板 F3/F8/F13/F18 为 1×1 透明块；
  F20 虫巢提亮、F22–F36 爆散粒子 8 帧、F38 粒子末帧、F40 / F42 透明（损毁）；F44–F106 四组碎块（原生按 op7 速度飞散）。
  虫巢各帧一律用带镜像标记的矩形：引擎把左侧玩家（朝向 90）的单位整体镜像，镜像标记与之抵消，左侧按用户图原样显示，
  右侧（朝向 270，引擎不镜像）显示为水平镜像（R8，用户 2026-10-29）。
脚本：原生 64 的 32 个脚本逐条转写，op19 缩放 80% → 100%（虫巢按 DS 像素原大，1 像素 = 2 逻辑单位）；
损毁脚本 13 / 14 保留 tick 0 的事件（op13、op12 碎块、op23 音效 290），帧序改为单向播放爆散（共 38 tick，同原生）。
受击框沿用原生第 0 项，第 1 项改为虫巢大小 [-30, -88, 60, 88, 0]；攻击框只有空项。
头像：用户构图（2026-10-29，handoff/unit_cell_player_green_50x50_LOGO.png）中与原生绿格不同的像素（格内 x 5–49、y 5–44），
写入社区合并图集 unit_icon_02.obm 的空位，锚点 [-5, -5]（初版至 R4 为虫巢缩小 0.45 倍）。

运行：E:/anaconda3/python.exe -I artwork/ms7_bug_hive_20261029/build_bug_hive.py [--preview]
（--preview 只写 out/；否则另写 community_content/ 的图集、描述符、单位文件、unit_icon_02.obm 与 content.json）。
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CONTENT = REPO / 'community_content'
OUT = HERE / 'out'
ENV = Path(r'F:\egg\MS7\DS _ DSi - Metal Slug 7 - Miscellaneous - Mission 3 Environmental Objects.png')
TOOLS = Path(r'F:\egg\research\metal_slug_defense\content_work\kt21_feasibility_20261005\design_verification_r1\tools')

KEY, BUILDER_KEY, CHARIOT_KEY = 's1xlv.bug_hive', 's1xlv.bug_hive_builder', 's1xlv.bug_hive_chariot'
TEXTURE, DESCRIPTOR = 'bug_hive.obm', 'bug_hive_descriptor.json'
HIVE = (3, 980, 65, 93)
BLOBS = [(71, 981, 32, 32), (105, 981, 32, 32), (139, 981, 32, 32), (173, 981, 32, 32), (207, 981, 32, 32), (241, 981, 32, 32),
         (275, 981, 32, 32), (309, 981, 32, 32), (343, 981, 48, 32), (393, 981, 48, 32)]
SPRAY = [(71, 1031, 64, 32), (137, 1015, 64, 48), (203, 1015, 64, 48), (269, 1015, 64, 48), (335, 1031, 64, 32), (401, 1031, 64, 32),
         (71, 1065, 64, 32), (137, 1065, 64, 32)]
# R3（用户 2026-10-29 附图 verification/ms7_m3_units_20261029/user_marks/hive_ground_user.png）：按图摆放。用户图与 8 种翻转 / 旋转
# 比对，TRANSVERSE（沿副对角线翻转 = 旋转 90° 加镜像）相关 0.822、其余 ≤ 0.65。该朝向 93×65：棕色团块在左上、骨架孔洞在右、
# 长刺朝下与朝右；用户的地面线在第 43 行，脚点取第 43 行，第 44–64 行的刺画在行走线前方。
# （R1 为旋转 180°，R2 为顺时针 90° 右侧贴地，均已由用户否定。）
# R8（用户 2026-10-29）：虫巢本体改用用户在该朝向的 93×65 图上去掉两侧多余枝刺后的图样（颜色均取自原图），不再由素材表旋转得到；
# 该图为左侧玩家的朝向，右侧玩家水平镜像。
# R9（用户 2026-10-29）：换为 NEW2——左侧棕色团块中残留的刺痕重新绘制（263 像素改色、1 像素新增，另有新颜色）；
# 本体 182 色、提亮 68 色、爆散与碎块 7 色，合计 250 色（含透明），仍在 8 位图集 256 色内，不做减色。
USER_HIVE = HERE / 'handoff' / 'bug_hive_horizontal_93x65 NEW2.png'
# R4（用户 2026-10-29：太贴近地面，再上移 6 像素）：脚点改在第 49 行（素材像素 6 = 逻辑 12），受击框与爆散中心随之上移。
HIVE_ANCHOR = (43, 49)                     # 球体中心列（第 12–73 列）；脚点在第 49 行（R3 为第 43 行）
BODY_CENTER_Y = 21                         # 球体第 5–51 行的中心在脚点上方 21：爆散粒子以此为中心
BRIGHT = 1.25
HIT_BOX = [-31, -44, 62, 44, 0]   # R4：行走线以上的球体（R3 [-31, -38, 62, 38]，R2 [-31, -51, 62, 51]，R1 [-30, -78, 60, 60]，初版 [-30, -88, 60, 88]）
# R1（用户 2026-10-29）：约 9 秒召唤一次。LAB 实测（runs/hive1_*、hive2_*）召唤间隔约为（间隔计量 + 1）× 1.167 帧：倍率 3 时计量 362 → 423 帧，
# 倍率 19/11 时计量 208 → 244 帧。原生 64 Lv40 间隔计量 120，倍率 21/11 → 计量 230 → 约 270 帧（9.0 秒）；首次计量 160 → 306。
SUMMON_INTERVAL = [14, 11]   # R6（用户 2026-10-29）：约 6 秒——计量 120 → 153，约 180 帧（R1 的 21/11 为 9 秒）
HIT_SUMMON_COOLDOWN = 120     # R6：受击召唤后 4 秒内的攻击不再召唤（summon_on_hit，与定时召唤并存）
SPLASH_SPEED = 2              # R6：爆开时的浆液（爆散粒子与碎块）按 2 倍速播放
# 每批小虫：原生 167 的发射者在脚本 9 / 20 连发 12 / 11 条 op22（每条一只）；保留其中 5 条（第 1、4、6、9、12 条 / 第 1、3、5、8、11 条，
# 飞行脚本 21、23、25、28、31），其余指令不变。
CHARIOT_KEEP = {9: [0, 3, 5, 8, 11], 20: [0, 2, 4, 7, 10]}
CHARIOT_ICON = {'page': 1, 'rect': [138, 619, 20, 14], 'anchor': [-15, -18]}   # 原生 167 的头像
USER_ICON = HERE / 'handoff' / 'unit_cell_player_green_50x50_LOGO.png'   # 用户在原生绿格上画好的头像
USER_CELL = HERE / 'handoff' / 'unit_cell_player_green_50x50.png'        # 原生绿格（unit.obm (362,151)）
ICON_BOX = (5, 5, 50, 45)                  # 取用范围：内框 5–44，右侧 45–49 为用户压在边框上的部分

LOCALIZATION = {   # 代理撰写（待用户确认 / 校对）；第 3 行的二輪戰車按各语言原生译名加引号引用（2026-10-29 用户要求）
    'ZS': ('虫穴', '普通攻击：‐     特殊攻击：‐\n骷髅状的虫巢，\n不时会放出「二轮战车」。'),
    'ZT': ('蟲穴', '普通攻擊：‐     特殊攻擊：‐\n骷髏狀的蟲巢，\n不時會放出「二輪戰車」。'),
    'JP': ('バグネスト', '通常攻撃：‐     特殊攻撃：‐\nドクロのような形をした虫の巣。\n時おり「チャリオット」を放つ。'),
    'KR': ('벌레 둥지', '일반 공격: -     특수 공격: -\n해골 모양의 벌레 둥지.\n이따금 "채리엇"을 내보낸다.'),
    'EN': ('BUG NEST', 'STAND. ATK : -     SPEC. ATK : -\nA skull-shaped insect nest.\nNow and then "CHARIOT" swarm out of it.'),
    'ES': ('NIDO DE INSECTOS', 'ATQ. ESTÁND. : -    ATQ. ESPEC. : -\nUn nido de insectos con forma de calavera.\nDe vez en cuando salen enjambres de "CARRO".'),
    'PT': ('NINHO DE INSETOS', 'ATQ. PADR. : -   ATQ. ESPEC. : -\nUm ninho de insetos em forma de caveira.\nDe vez em quando saem enxames de "CARRUAGEM".'),
    'FR': ('NID D\'INSECTES', 'ATT. STAND : -   ATT. SPÉ : -\nUn nid d\'insectes en forme de crâne.\nDe temps à autre, des essaims de "CHARIOT" en sortent.'),
    'DE': ('INSEKTENNEST', 'STANDARDANGR. : -     SPEZIALANGR. : -\nEin schädelförmiges Insektennest.\nAb und zu schwärmen "CHARIOT" aus.'),
    'IT': ('NIDO DI INSETTI', 'ATC STAND.: -   ATC SPEC.: -\nUn nido di insetti a forma di teschio.\nDi tanto in tanto ne escono sciami di "CARRO".'),
    'RU': ('ГНЕЗДО ЖУКОВ', 'СТАНД. АТАК: -   СПЕЦ. АТАК: -\nГнездо насекомых в форме черепа.\nВремя от времени из него вылетают рои "КОЛЕСНИЦА".'),
}

COMMON = {
    'faction': 4,                       # 原生 64 / 167 数据行阵营字 4（同木乃伊召唤箱 MKII）
    'identity': 'Independent Army',
    'shop_price': 130,                  # 用户 2026-10-29 指定
    'available_from_start': True,
    'ap': 120,                          # 用户 2026-10-29 R6 指定（R1 为 110，原生 77 为 100；击毁返还 12）
    'special_damage_multiplier': [1, 1],
    'damage_multiplier': [1, 1],
    'move_speed_multiplier': [1, 1],
    'attack_wait_multiplier': [1, 1],
    'attack_range_multiplier': [1, 1],
    'knockback_distance_multiplier': [1, 1],
    'ballistic_range_multiplier': [1, 1],
    'production_reference_id': 77,
    'production_interval_multiplier': [1, 1],
    'hp_multiplier': [1, 1],            # 原生 64：Lv40 生命 4500
    'knockback_threshold_multiplier': [1, 1],
}


def env_piece(env, box):
    x, y, w, h = box
    a = np.asarray(env.crop((x, y, x + w, y + h)).convert('RGBA')).copy()
    rgb = a[..., :3].astype(int)
    bg = np.all(rgb >= 250, axis=2) | ((rgb[..., 1] >= 240) & (rgb[..., 0] <= 16) & (rgb[..., 2] <= 16))
    a[bg] = 0
    return Image.fromarray(a)


def bright(im, k):
    a = np.asarray(im).astype(float)
    a[..., :3] = np.minimum(248, np.round(a[..., :3] * k / 8) * 8)
    return Image.fromarray(a.astype(np.uint8))


def indexed_obm(image):
    """OI 01 08（RGBA8 调色板 + 8 位索引，同 pvz_zombies 生成脚本）；索引 0 为透明。"""
    rgba = image.convert('RGBA')
    data = [p if p[3] else (0, 0, 0, 0) for p in rgba.getdata()]
    colors = list(dict.fromkeys([(0, 0, 0, 0)] + data))
    assert len(colors) <= 256, len(colors)
    lut = {c: i for i, c in enumerate(colors)}
    raw = b'OI\x01\x08' + struct.pack('<HH', *image.size)
    return raw + b''.join(bytes(c) for c in colors).ljust(1024, b'\0') + bytes(lut[c] for c in data), len(colors)


def shelf_pack(tiles, W=256, pad=1):
    order = sorted(range(len(tiles)), key=lambda i: (-tiles[i].height, -tiles[i].width))
    x = y = shelf = 0
    pos = {}
    for i in order:
        w, h = tiles[i].width + pad, tiles[i].height + pad
        if x + w > W:
            x, y, shelf = 0, y + shelf, 0
        pos[i] = (x, y)
        x += w
        shelf = max(shelf, h)
    H = 1
    while H < y + shelf:
        H *= 2
    return pos, H


def native_scripts(uid=64):
    """原生单位（缺省 64）的描述符结构与全部脚本（静态读取）。"""
    sys.path.insert(0, str(TOOLS))
    import os
    cwd = os.getcwd()
    os.chdir(TOOLS)
    import elfmem
    os.chdir(cwd)
    a = elfmem.word(0x922f28 + uid * 8)
    m = elfmem.ctor_mem()
    d = [m.get(a + i * 4) for i in range(8)]
    frames = list(struct.unpack('<' + 'I' * ((d[4] - d[3]) // 4), elfmem.read(d[3], d[4] - d[3])))
    hits = list(struct.unpack('<10i', elfmem.read(d[4], 40)))
    scripts = [elfmem.script(d, frames, s)[0] for s in range(d[7])]
    return frames, [hits[:5], hits[5:]], scripts


def build_frames(native_frames):
    """与原生帧偏移一一对应的帧表；返回 (帧表, 帧偏移 → 名称)。"""
    names, i, layout = {}, 0, []
    while i < len(native_frames):
        n = native_frames[i]
        layout.append((i, n))
        i += 1 + n
    # R8：原生左侧玩家用 F10 / F15、右侧用 F0 / F5（LAB 实测），四帧与损毁首帧都用镜像标记矩形（见模块说明）
    body = {0: 'hive_flip', 5: 'hive_bright_flip', 10: 'hive_flip', 15: 'hive_bright_flip'}
    collapse = ['hive_bright_flip'] + [f'spray{k}' for k in range(8)] + ['spray7', 'blank', 'blank']
    debris = {44: [0, 1, 2, 3, 4, 5, 6, 7], 60: [1, 2, 3, 4, 5, 6, 7, 8], 76: [2, 3, 4, 5, 6, 7, 8, 9], 92: [0, 2, 4, 6, 8, 9, 9, 9]}
    out = []
    for off, n in layout:
        if off in body:
            parts = [body[off], 'blank']
        elif off in (3, 8, 13, 18):
            parts = ['blank']
        elif 20 <= off <= 42:
            parts = [collapse[(off - 20) // 2]]
        else:
            g = max(k for k in debris if k <= off)
            parts = [f'blob{debris[g][(off - g) // 2]}']
        assert len(parts) == n, (off, n, parts)
        names[off] = parts
        out.append(parts)
    return layout, names


def convert_scripts(scripts):
    anims = {}
    for slot, cmds in enumerate(scripts):
        out = []
        for c in cmds:
            op, v = c['opcode'], list(c['values'])
            if op == 19 and v == [80, 80]:
                v = [100, 100]
            out.append({'opcode': op, 'values': v})
        anims[slot] = out
    # 损毁（13 / 14）：tick 0 的事件照旧，爆散帧单向播放，共 38 tick
    # R6：浆液 2 倍速（初版 2,3,3,4,4,4,4,4,4,3,2,1 共 38 tick）
    seq = [(20, 1), (22, 2), (24, 2), (26, 2), (28, 2), (30, 2), (32, 2), (34, 2), (36, 2), (38, 1), (40, 1), (42, 1)]
    assert sum(w for _, w in seq) == 20
    for slot in (13, 14):
        events = [c for c in anims[slot] if c['opcode'] not in (0, 1, 21)]
        anims[slot] = events + [x for f, w in seq for x in ({'opcode': 0, 'values': [f]}, {'opcode': 1, 'values': [w]})] + \
            [{'opcode': 21, 'values': []}]
    # R6：碎块（浆液块）飞散脚本 21–30 按 SPLASH_SPEED 压缩时间：每 SPLASH_SPEED 帧取一帧，op7 速度 ×k、加速度 ×k²
    k = SPLASH_SPEED
    for slot in range(21, 31):
        out, frame_i, skip_wait = [], 0, False
        for c in anims[slot]:
            if c['opcode'] == 7:
                vx, vy, ax, ay = c['values']
                out.append({'opcode': 7, 'values': [vx * k, vy * k, ax * k * k, ay * k * k]})
            elif c['opcode'] == 0:
                skip_wait = frame_i % k != 0
                frame_i += 1
                if not skip_wait:
                    out.append(c)
            elif c['opcode'] == 1:
                if not skip_wait:
                    out.append(c)
            else:
                out.append(c)
        anims[slot] = out
    return anims


def main(preview):
    OUT.mkdir(parents=True, exist_ok=True)
    env = Image.open(ENV).convert('RGB')
    hive = Image.open(USER_HIVE).convert('RGBA')
    assert hive.size == (93, 65), hive.size
    a = np.asarray(hive).copy()
    a[a[..., 3] == 0] = 0
    hive = Image.fromarray(a)
    tiles = {'hive': hive, 'hive_bright': bright(hive, BRIGHT), 'blank': Image.new('RGBA', (1, 1), (0, 0, 0, 0))}
    for k, b in enumerate(SPRAY):
        tiles[f'spray{k}'] = env_piece(env, b)
    for k, b in enumerate(BLOBS):
        tiles[f'blob{k}'] = env_piece(env, b)
    keys = list(tiles)
    pos, H = shelf_pack([tiles[k] for k in keys])
    page = Image.new('RGBA', (256, H), (0, 0, 0, 0))
    for i, k in enumerate(keys):
        page.alpha_composite(tiles[k], pos[i])
    obm, ncolors = indexed_obm(page)
    # 矩形 [x, y, w, h, ax, ay, flags, page]（正值锚点 = 矩形边缘到原点的距离）
    rects, rect_of = [], {}
    for i, k in enumerate(keys):
        im = tiles[k]
        x, y = pos[i]
        if k.startswith('hive'):
            ax, ay = HIVE_ANCHOR
        elif k.startswith('spray'):
            ax, ay = im.width // 2, im.height // 2 + BODY_CENTER_Y
        elif k.startswith('blob'):
            ax, ay = im.width // 2, im.height // 2
        else:
            ax, ay = 0, 0
        if k in ('hive', 'hive_bright'):   # R8：只留镜像标记矩形
            rect_of[k + '_flip'] = len(rects)
            rects.append([x, y, im.width, im.height, im.width - ax - 1, ay, 1, 0])
            continue
        rect_of[k] = len(rects)
        rects.append([x, y, im.width, im.height, ax, ay, 0, 0])
    native_frames, native_hits, scripts = native_scripts()
    layout, names = build_frames(native_frames)
    words = []
    for off, n in layout:
        assert len(words) == off
        words += [n] + [rect_of[p] for p in names[off]]
    hits = [native_hits[0], HIT_BOX]
    desc = {'rects': rects, 'frames': words, 'script_count': len(scripts), 'hit_bounds': hits, 'attack_bounds': [[0, 0, 0, 0, 0]]}
    anims = convert_scripts(scripts)
    page.save(OUT / 'bug_hive_page.png')
    # 示意：待机、提亮、损毁序列与碎块
    strip = Image.new('RGBA', (16 + 80 * 14, 140), (40, 60, 60, 255))
    d = ImageDraw.Draw(strip)
    for j, f in enumerate([0, 5, 10] + list(range(20, 43, 2))):
        for r in names[f]:
            x, y, w, h, ax, ay, fl, _ = rects[rect_of[r] if not isinstance(r, int) else r]
            im = page.crop((x, y, x + w, y + h))
            if fl & 1:
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
            strip.alpha_composite(im, (40 + 80 * j - ax, 120 - ay))
        d.text((10 + 80 * j, 124), 'F%d' % f, fill=(255, 255, 0, 255))
    strip.resize((strip.width * 2, strip.height * 2), Image.NEAREST).save(OUT / 'bug_hive_frames_2x.png')
    report = {'colors': ncolors, 'page': [256, H], 'rects': len(rects), 'frame_words': len(words), 'scripts': len(anims)}
    # 头像
    icon = user_icon()
    report['icon_size'] = list(icon.size)
    if not preview:
        index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
        for key in (BUILDER_KEY, KEY, CHARIOT_KEY):
            if key not in index['unit_ids']:
                index['unit_ids'][key] = max(index['unit_ids'].values()) + 1
        raw = (CONTENT / 'unit_icon_02.obm').read_bytes()
        assert raw[:4] == bytes((79, 73, 1, 32))
        w, h = struct.unpack_from('<HH', raw, 4)
        px = bytearray(raw[8:])
        unit_path = CONTENT / 'units' / 'bug_hive_builder.json'
        rect = json.loads(unit_path.read_text(encoding='utf-8'))['icon']['rect'] if unit_path.exists() else None
        if rect is not None and tuple(rect[2:]) != icon.size:   # R2：头像尺寸改变时清除旧位置后重新找空位
            for j in range(rect[3]):
                o = ((rect[1] + j) * w + rect[0]) * 4
                px[o:o + rect[2] * 4] = bytes(rect[2] * 4)
            rect = None
        if rect is None:
            rect = find_icon_slot(px, w, h, icon.size)
        ia = np.asarray(icon)
        for j in range(icon.height):
            for i in range(icon.width):
                o = ((rect[1] + j) * w + rect[0] + i) * 4
                px[o:o + 4] = bytes(int(v) for v in ia[j, i]) if ia[j, i, 3] else bytes(4)
        (CONTENT / 'unit_icon_02.obm').write_bytes(raw[:8] + bytes(px))   # 摘要在 content.json 中为 null，保持不变
        (CONTENT / TEXTURE).write_bytes(obm)
        index['assets'][TEXTURE] = hashlib.blake2b(obm, digest_size=32).hexdigest()
        (CONTENT / DESCRIPTOR).write_bytes((json.dumps(desc, ensure_ascii=False) + chr(10)).encode('utf-8'))
        icon_entry = {'page': 1, 'rect': list(rect), 'anchor': [-ICON_BOX[0], -ICON_BOX[1]]}
        loc = {lang: {'name': n, 'description': t} for lang, (n, t) in LOCALIZATION.items()}
        builder = {'key': BUILDER_KEY, 'base_id': 77, **COMMON, 'textures': ['donou.obm'], 'icon': icon_entry, 'animations': {},
                   'behaviors': [{'name': 'build_structure', 'version': 1,
                                  'params': {'structure': KEY, 'construction_time_multiplier': [1, 1]}}],
                   'localization': loc}
        structure = {'key': KEY, 'base_id': 64, **COMMON, 'menu_reference_id': 77, 'internal_only': True,
                     'textures': [TEXTURE], 'sprite_descriptor': DESCRIPTOR, 'icon': icon_entry,
                     'animations': {str(k): v for k, v in sorted(anims.items())},
                     'behaviors': [{'name': 'summon_internal_unit', 'version': 1,
                                    'params': {'unit': CHARIOT_KEY, 'interval_multiplier': SUMMON_INTERVAL}},
                                   {'name': 'summon_on_hit', 'version': 1, 'params': {'cooldown': HIT_SUMMON_COOLDOWN}}],
                     'localization': loc}
        chariot = chariot_unit()
        for path, data in ((CONTENT / 'units' / 'bug_hive_builder.json', builder), (CONTENT / 'units' / 'bug_hive.json', structure),
                           (CONTENT / 'units' / 'bug_hive_chariot.json', chariot), (CONTENT / 'content.json', index)):
            path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + chr(10)).encode('utf-8'))
        report['unit_ids'] = {key: index['unit_ids'][key] for key in (BUILDER_KEY, KEY, CHARIOT_KEY)}
        report['icon_rect'] = rect
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


CHARIOT_LOC = {   # 原生 167 的各语言名称与说明（strMenuUnitName / strMenuUnitInfo）；DE 原版为空，用英语；ZS 原版为空，为繁体转写
    'ZS': ('二轮战车', '普通攻击： 突击   特殊攻击：-\n群体行动的大型虫子。\n拥有会爆炸的体液，只要接触到敌人就会自爆。'),
    'ZT': ('二輪戰車', '普通攻擊： 突擊   特殊攻擊：-\n群體行動的大型蟲子。\n擁有會爆炸的體液，只要接觸到敵人就會自爆。'),
    'JP': ('チャリオット', '通常攻撃： 突撃   特殊攻撃：-\n群れで行動する大型の虫。\n爆発性の体液を持っており、敵に接触すると自爆する。'),
    'KR': ('채리엇', '일반 공격: 돌진    특수 공격: -\n무리지어 행동하는 대형 벌레\n폭발성 체액을 지니고 있으며, 적에게 접촉하면 자폭한다.'),
    'EN': ('CHARIOT', 'STAND. ATK : Stampede    SPEC. ATK : -\nGiant insects which only moves in groups.They can make explode \ntheir enemies in pieces with their dangerous saliva. '),
    'ES': ('CARRO', 'ATQ ESTÁND.: Estampida\u3000ATQ ESPEC.: - \nInsectos gigantes que solo se mueven en grupos. Pueden hacer\nexplotar a sus enemigos en pedazos con su peligrosa saliva.'),
    'PT': ('CARRUAGEM', 'ATQ. PADR. : Debandada   ATQ. ESPEC. : -\nInsetos gigantes que se movem em nuvem. Possuem um líquido\nexplosivo que detona ao entrar em contato com o inimigo.'),
    'FR': ('CHARIOT', 'ATT. STAND : Charge   SPEC. ATK : -\nInsectes géants ne se déplaçant qu\'en groupe. \nLeur salive venimeuse peut réduire n\'importe quel ennemi en pièces.'),
    'DE': ('CHARIOT', 'STAND. ATK : Stampede    SPEC. ATK : -\nGiant insects which only moves in groups.They can make explode \ntheir enemies in pieces with their dangerous saliva. '),
    'IT': ('CARRO', 'ATC STAND.: Stampede    ATC SPEC.: -\nInsetti giganti che agiscono in gruppo.\nPossono far esplodere i nemici con la loro saliva.'),
    'RU': ('КОЛЕСНИЦА', 'СТАНД. АТАК: Табун   СПЕЦ. АТАК: -\nОгромные насекомые, передвигающиеся только группами.\nМогут разрывать своих врагов на куски при помощи опасной слюны.'),
}


def chariot_unit():
    """虫穴召唤的二輪戰車：基准 167 的内部单位，图集与数值沿用原生，只把脚本 9 / 20 的 op22 减为 5 条。"""
    _, _, scripts = native_scripts(167)
    anims = {}
    for slot, keep in CHARIOT_KEEP.items():
        shots = [i for i, c in enumerate(scripts[slot]) if c['opcode'] == 22]
        assert len(shots) == (12 if slot == 9 else 11), (slot, len(shots))
        kept = {shots[k] for k in keep}
        anims[str(slot)] = [{'opcode': c['opcode'], 'values': list(c['values'])} for i, c in enumerate(scripts[slot])
                            if c['opcode'] != 22 or i in kept]
    values = {k: v for k, v in COMMON.items() if k not in ('shop_price', 'ap', 'production_reference_id')}
    return {'key': CHARIOT_KEY, 'base_id': 167, **values, 'shop_price': 50, 'ap': 40, 'production_reference_id': 167,
            'menu_reference_id': 167, 'internal_only': True, 'textures': ['chariot_out.obm'], 'icon': CHARIOT_ICON,
            'animations': anims, 'localization': {lang: {'name': n, 'description': d} for lang, (n, d) in CHARIOT_LOC.items()}}


def user_icon():
    """用户构图中与原生绿格不同的像素（ICON_BOX 内），其余透明。"""
    a = np.asarray(Image.open(USER_ICON).convert('RGBA'))
    c = np.asarray(Image.open(USER_CELL).convert('RGBA'))
    assert a.shape == c.shape == (50, 50, 4)
    x0, y0, x1, y1 = ICON_BOX
    sa, sc = a[y0:y1, x0:x1], c[y0:y1, x0:x1]
    changed = np.any(sa != sc, axis=2)
    out = np.zeros_like(sa)
    out[changed] = sa[changed]
    out[changed, 3] = 255
    return Image.fromarray(out)


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


if __name__ == '__main__':
    main('--preview' in sys.argv)
