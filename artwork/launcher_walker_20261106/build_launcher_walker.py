"""MS7 任务 7 带炮管的雷贝尔沃克 s1xlv.launcher_walker（2026-11-06，雷贝尔沃克会话；设计、原作核对与示意动画见
docs/MS7_LAUNCHER_WALKER_2026-11-06.md 第 2–9 节，用户确认示意动画 R4 后开工）。

来源：
- 原生 228 REBEL WALKER（BattleAction_LevelWalker）的描述符（verification/ms7_m7_20261103/runs/rw_213913_740/units.json）与图集
  levelwalker_out.obm（第 0 页原样引用，不改像素）。
- Gussprint 拆的 MS7 DS 素材表 F:\\egg\\MS7\\DS _ DSi - Metal Slug 7 - Enemies - Rebel Walker.png：侧视发射器（WRECKED 两行第 0 帧之差，
  23 × 14）、导弹 4 帧、发射效果两行（第 1 行前烟、第 2 行后焰）、带发射器的损毁 12 帧，放第 1 页 launcher_walker.obm（8 位）。
做法：
- 原生矩形 / 帧表原样在前，新矩形与新帧追加在后（未改写的原生脚本仍指向原生帧）。
- 发射器挂点按身体矩形（source/pad_table.json，verification/ms7_rwalker_20261106/pad_table.py 以肩甲匹配求得）：身体帧 + 旋转后的发射器
  组成新帧，改写画身体的子脚本 14（待机）、15（行走）、20 / 52（跳跃、击退）。
- 损毁脚本 13 的 12 帧换为带发射器的 12 帧（锚点同原生矩形 122–133），其余（碎块、时刻）不变。
- 新脚本：76 普通攻击（站立，69 tick，第 FIRE_TICK tick 发射；腿同原生 6）、77 特殊攻击（72 tick，三次发射）、78–93 导弹 16 个方向
  （每 22.5° 一档，4 帧尾焰交替，攻击框 4）、94 前烟、95 后焰、96 烟团。发射、效果与导弹运动由核心（行为 launcher_walker）处理。
- 头像：拼合待机（朝右）放进 unit_icon_02.obm 的空格（用户可另行替换）。
- 音效：发射音暂用 MSXX SE B4_MISSL.wav（待用户听辨）。
运行：E:\\anaconda3\\python.exe -I artwork/launcher_walker_20261106/build_launcher_walker.py [--preview]
"""
from pathlib import Path
import hashlib
import json
import math
import struct
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

_PVZ = REPO / 'artwork' / 'pvz_zombies_20261012' / 'build_pvz_zombies.py'
_src = _PVZ.read_text(encoding='utf-8')
_src = _src.replace("sys.path.insert(0, str(RT / 'packages'))", "").replace("os.add_dll_directory(str(RT / 'native'))", "")
pvz = type(sys)('pvzb')
pvz.__dict__['__file__'] = str(_PVZ)
exec(compile(_src, str(_PVZ), 'exec'), pvz.__dict__)
indexed_obm, save_json, shelf_pack = pvz.indexed_obm, pvz.save_json, pvz.shelf_pack

CONTENT = REPO / 'community_content'
OUT = HERE / 'out'
NATIVE = REPO / 'verification' / 'ms7_m7_20261103' / 'runs' / 'rw_213913_740' / 'units.json'
SHEET = Path(r'F:\egg\MS7\DS _ DSi - Metal Slug 7 - Enemies - Rebel Walker.png')
MSXX_SE = Path(r'F:\egg\MS7\MSXX-audio-wav\SE')
KEY, FILE = 's1xlv.launcher_walker', 'launcher_walker.json'
TEXTURES = ['levelwalker_out.obm', 'launcher_walker.obm']
DESCRIPTOR = 'launcher_walker_descriptor.json'
# R7（用户：发射音效严重失真）：B4_MISSL 混音过满（RMS −5.9 dB，109 处削顶）；改用同目录无削顶的 ROCKETS.wav（换来源前先删去旧的 msdf）
SOUND_KEY, SOUND_SRC, SOUND_VOLUME = 's1xlv.lwalker_launch', 'ROCKETS.wav', 100
VORBIS_QUALITY = 0.8
# 数值（用户 2026-11-06：只有导弹攻击；HP、再出击时间等同原版（原生 228），攻击间隔按原版；AP 160；伤害与射程同原生）
AP, PRICE = 220, 120                 # R7（用户）：AP 220（R6 为 160）；价格同原生 228（代理所定，待用户定）
DAMAGE = [9, 10]                     # R7（用户）：导弹伤害 −10%（普通 1750 → 1575、特殊 800 → 720，Lv40）
# R7（用户）：导弹飞行速度 +25%（初速 4.8 → 6、加速度 0.26 → 0.33、上限 14 → 17.5，逻辑单位 / 帧）、存在 640 帧、追踪视野 750
MISSILE = {'speed': 60, 'acceleration': 33, 'max_speed': 175, 'life': 640, 'target_range': 750, 'puff_interval': 2}
# 脚本号
ATTACK, SALVO, MISSILE_FIRST, FX_FRONT, FX_REAR, PUFF = 76, 77, 78, 94, 95, 96
SCRIPT_COUNT = 97
# R7（用户：发射间隔 −20%）：普通攻击 69 → 52 tick，一轮（攻击 + 状态 10 的 15 帧）84 → 67 帧；特殊攻击保持 72 tick
ATTACK_TICKS, SALVO_TICKS = 52, 72   # R6 为 69（同原生远距脚本 9）
FIRE_TICK = 20                       # 普通攻击的发射 tick（代理暂定）
SALVO_FIRE = (24, 34, 44)            # 3 连射的发射 tick（间隔 10，代理暂定）
MISSILE_BOX = 4                      # 攻击框序号（追加在原生 0–3 之后）
POD_SCRIPTS = (14, 15, 20, 52)       # 画身体的子脚本（待机、行走、跳跃 / 击退）
WRECK_RECTS = range(122, 134)        # 原生损毁 12 帧的矩形（脚本 13）
WRECK_BOXES = [[3, 708, 38, 39], [44, 709, 38, 38], [85, 710, 38, 37], [126, 709, 38, 38], [167, 713, 38, 34], [208, 720, 38, 27],
               [249, 721, 38, 26], [290, 721, 39, 26], [332, 722, 39, 25], [374, 723, 39, 24], [416, 724, 39, 24], [458, 724, 40, 24]]
MISSILE_BOXES = ([3, 830, 32, 13], [38, 830, 32, 13], [73, 830, 31, 13], [107, 830, 28, 13])
MISSILE_PIVOT = (13, 6)              # 弹体中心（不含尾焰），素材朝左
HEADINGS = 16
ICON_ANCHOR = [-5, -5]


def cmd(op, *v):
    return {'opcode': op, 'values': list(v)}


def sheet_rgba(sh, box):
    x, y, w, h = box
    a = np.asarray(sh.crop((x, y, x + w, y + h))).astype(np.uint8)
    bg = (a[..., :3] == 255).all(-1) | ((a[..., 0] == 255) & (a[..., 1] == 204) & (a[..., 2] == 204))
    return Image.fromarray(np.dstack([a[..., :3], np.where(bg, 0, 255).astype(np.uint8)]), 'RGBA')


def pod_image(sh):
    """侧视发射器：WRECKED 第 0 帧与带发射器版第 0 帧之差（同 verification/ms7_rwalker_20261106/rw_pod.py）。"""
    a = np.asarray(sheet_rgba(sh, (3, 660, 38, 39))).astype(int)
    b = np.asarray(sheet_rgba(sh, (3, 708, 38, 39))).astype(int)
    diff = (np.abs(a[..., :3] - b[..., :3]).sum(-1) > 30) | (a[..., 3] != b[..., 3])
    ys, xs = np.nonzero(diff)
    pod = np.zeros_like(b)
    pod[diff] = b[diff]
    return Image.fromarray(pod[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.uint8), 'RGBA')


def crop_bbox(im):
    bb = im.getbbox()
    return im.crop(bb), bb


def build():
    native = json.loads(NATIVE.read_text(encoding='utf-8'))['228']['descriptor']
    assert native['names'] == ['levelwalker_out.obm'] and native['script_count'] == 76
    sh = Image.open(SHEET).convert('RGB')
    rects = [list(r) for r in native['rects']]
    frames = list(native['frames'])
    pad = {int(k): v for k, v in json.loads((HERE / 'source' / 'pad_table.json').read_text(encoding='utf-8')).items() if v}
    for r in WRECK_RECTS:          # 122 / 123 为损毁帧（pad_table 误作身体），不挂发射器
        pad.pop(r, None)
    tiles, tile_anchor, rect_of_tile = [], [], []   # 第 1 页的图块与锚点

    def add_tile(im, ax, ay):
        tiles.append(im)
        tile_anchor.append((ax, ay))
        return len(tiles) - 1
    # 发射器：每种角度一张图块，每个（角度、锚点）组合一个矩形
    pod = pod_image(sh)
    pod_tile = {}
    for ri, (cx, cy, ang, _) in sorted(pad.items()):
        if ang not in pod_tile:
            pod_tile[ang] = add_tile(pod.rotate(ang, resample=Image.NEAREST, expand=True), 0, 0)
    # 导弹 16 方向 × 4 帧（素材朝左；方向 k 为前方向下 k × 22.5°，PIL 逆时针旋转 = 屏幕上朝左的箭头转向下方）
    missile_tiles = {}
    for k in range(HEADINGS):
        for f, box in enumerate(MISSILE_BOXES):
            im = sheet_rgba(sh, box)
            big = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            big.alpha_composite(im, (32 - MISSILE_PIVOT[0], 32 - MISSILE_PIVOT[1]))
            big = big.rotate(k * 360.0 / HEADINGS, resample=Image.NEAREST, center=(32, 32))
            c, bb = crop_bbox(big)
            missile_tiles[(k, f)] = add_tile(c, 32 - bb[0], 32 - bb[1])
    # 前烟（右缘中点贴发射器前端）、后焰（左缘中点贴发射器后端）：各 8 格 32 × 16
    fx_tiles = {}
    for row, y, key in ((1, 794, 'front'), (2, 811, 'rear')):
        for i in range(8):
            im = sheet_rgba(sh, (3 + 33 * i, y, 32, 16))
            if not im.getbbox():
                fx_tiles[(key, i)] = None
                continue
            c, bb = crop_bbox(im)
            ax = (32 if key == 'front' else 0) - bb[0]
            fx_tiles[(key, i)] = add_tile(c, ax, 8 - bb[1])
    # 烟团（素材表无单独帧：取前烟第 3–7 帧左半的烟球，中心为锚点；R7 由 4 帧改为 5 帧）
    puff_tiles = []
    for i in (2, 3, 4, 5, 6):
        a = np.asarray(sheet_rgba(sh, (3 + 33 * i, 794, 32, 16))).copy()
        a[:, 16:, 3] = 0
        c, bb = crop_bbox(Image.fromarray(a, 'RGBA'))
        puff_tiles.append(add_tile(c, 8 - bb[0], 8 - bb[1]))
    # 带发射器的损毁 12 帧（锚点同原生矩形 122–133；第 10 帧素材表比原生高 1 行，左缘与底边对齐）
    wreck_tiles = []
    for k, box in enumerate(WRECK_BOXES):
        r = native['rects'][122 + k]
        assert r[2] == box[2] and box[3] - r[3] in (0, 1), (k, r, box)
        wreck_tiles.append(add_tile(sheet_rgba(sh, box), r[4], r[5] + box[3] - r[3]))
    page, pos = shelf_pack(tiles)
    for i, im in enumerate(tiles):
        x, y = pos[i]
        ax, ay = tile_anchor[i]
        rect_of_tile.append(len(rects))
        rects.append([x, y, im.width, im.height, ax, ay, 0, 1])

    def new_frame(rect_ids):
        at = len(frames)
        frames.extend([len(rect_ids)] + list(rect_ids))
        return at
    # 身体帧 + 发射器
    pod_rect = {}
    for ri, (cx, cy, ang, _) in pad.items():
        t = pod_tile[ang]
        w, h = tiles[t].width, tiles[t].height
        ax, ay = -int(round(cx - w / 2)), -int(round(cy - h / 2))   # 同 rw_pod.paste_pod：左上 = 原点 + round(c − 尺寸 / 2)
        x, y = pos[t]
        rects.append([x, y, w, h, ax, ay, 0, 1])
        pod_rect[ri] = len(rects) - 1
    starts, at = [], 0
    while at < len(native['frames']):
        starts.append(at)
        at += native['frames'][at] + 1
    body_frame = {}
    for f in starts:
        ids = native['frames'][f + 1:f + 1 + native['frames'][f]]
        bodies = [r for r in ids if r in pod_rect]
        if bodies:
            body_frame[f] = new_frame(list(ids) + [pod_rect[bodies[-1]]])
    wreck_frame = {}
    for f in starts:
        ids = native['frames'][f + 1:f + 1 + native['frames'][f]]
        if len(ids) == 1 and ids[0] in WRECK_RECTS:
            wreck_frame[f] = new_frame([rect_of_tile[wreck_tiles[ids[0] - 122]]])
    missile_frame = {kf: new_frame([rect_of_tile[t]]) for kf, t in missile_tiles.items()}
    fx_frame = {kf: (new_frame([rect_of_tile[t]]) if t is not None else None) for kf, t in fx_tiles.items()}
    puff_frame = [new_frame([rect_of_tile[t]]) for t in puff_tiles]
    # 脚本
    def native_script(i):
        return [cmd(c[0], *c[1:]) for c in native['scripts'][i]]
    animations = {}
    for s in POD_SCRIPTS:
        seq = native_script(s)
        for c in seq:
            if c['opcode'] == 0 and c['values'][0] in body_frame:
                c['values'][0] = body_frame[c['values'][0]]
        animations[str(s)] = seq
    death = native_script(13)
    for c in death:
        if c['opcode'] == 0 and c['values'][0] in wreck_frame:
            c['values'][0] = wreck_frame[c['values'][0]]
    animations['13'] = death
    # 攻击：腿与身体同原生中立脚本 6（根层腿 8 帧各 3 tick 循环，子脚本 14 画身体），按 tick 展开到攻击长度后结束
    s6 = native['scripts'][6]
    legs = [(s6[i][1], s6[i + 1][1]) for i in range(len(s6) - 1) if s6[i][0] == 0 and s6[i + 1][0] == 1]
    assert legs and all(w == 3 for _, w in legs), legs

    def attack_script(total, fires):
        seq = [cmd(11, 14, 0, 0, 0), cmd(3, 1)]
        t, i = 0, 0
        while t < total:
            frame, wait = legs[i % len(legs)]
            i += 1
            seq.append(cmd(0, frame))
            for k in range(min(wait, total - t)):
                if t + k in fires:
                    seq.append(cmd(23, SOUND_KEY))
                seq.append(cmd(1, 1))
            t += min(wait, total - t)
        seq.append(cmd(21))
        return seq
    animations[str(ATTACK)] = attack_script(ATTACK_TICKS, {FIRE_TICK})
    animations[str(SALVO)] = attack_script(SALVO_TICKS, set(SALVO_FIRE))
    for k in range(HEADINGS):
        seq = [cmd(4, MISSILE_BOX)]
        for f in range(4):
            seq += [cmd(0, missile_frame[(k, f)]), cmd(1, 1)]   # R7：尾焰每 tick 换帧（R6 为 2 tick）
        animations[str(MISSILE_FIRST + k)] = seq + [cmd(5)]
    for script, key in ((FX_FRONT, 'front'), (FX_REAR, 'rear')):
        seq = []
        for i in range(8):
            seq += [cmd(0, fx_frame[(key, i)] if fx_frame[(key, i)] is not None else -1), cmd(1, 2)]
        animations[str(script)] = seq + [cmd(0, -1), cmd(1, 1), cmd(21)]
    seq = []
    for f in puff_frame:
        seq += [cmd(0, f), cmd(1, 2)]   # R7：每帧 2 tick（R6 为 3 tick × 4 帧、每 3 帧放一个，尾迹断续）
    animations[str(PUFF)] = seq + [cmd(0, -1), cmd(1, 1), cmd(21)]
    attack_bounds = [list(b) for b in native['attack_bounds']] + [[-7, -6, 14, 12, 7]]
    assert len(attack_bounds) == MISSILE_BOX + 1
    desc = {'rects': rects, 'frames': frames, 'script_count': SCRIPT_COUNT,
            'hit_bounds': [list(b) for b in native['hit_bounds']], 'attack_bounds': attack_bounds}
    stats = {'tiles': len(tiles), 'rects': len(rects), 'native_rects': len(native['rects']), 'frames_words': len(frames),
             'pod_angles': sorted(pod_tile), 'body_frames': len(body_frame), 'wreck_frames': len(wreck_frame),
             'page': list(page.size), 'colors': len(set(page.getdata()))}
    return page, desc, animations, stats


def localization():
    """名称为代理暂定（待用户定）；说明第 1 行为攻击名，第 2 行沿用原生 228 原文的意思，第 3 行为本单位特征。"""
    t = {
        'ZS': ('雷贝尔沃克（火箭）', '普通攻击：追踪导弹     特殊攻击：导弹三连射\n从未来而来的莫丁军新兵器。\n肩部装有火箭发射器的型号。'),
        'ZT': ('雷貝爾沃克（火箭）', '普通攻擊：追蹤導彈     特殊攻擊：導彈三連射\n從未來而來的莫迪軍新兵器。\n肩部裝有火箭發射器的型號。'),
        'EN': ('REBEL WALKER (ROCKET)', "STAND. ATK : Homing missile     SPEC. ATK : Triple missile\nMorden’s new weapon from the future.\nThis model carries a rocket launcher on its shoulder."),
        'JP': ('レベルウォーカー（ロケット）', '通常攻撃：誘導ミサイル    特殊攻撃：ミサイル3連射\n未来からやってきたモーデンの新兵器。\n肩にロケットランチャーを装備した型。'),
        'KR': ('레벨 워커(로켓)', '일반 공격: 유도 미사일     특수 공격: 미사일 3연사\n미래로부터 온 모덴의 새로운 병기.\n어깨에 로켓 발사기를 장착한 형식.'),
        'ES': ('CAMINANTE REBELDE (COHETES)', 'ATQ. ESTÁN.: Misil teledirigido ATQ. ESPEC.: Misil triple\nLa nueva arma del futuro de Morden.\nEste modelo lleva un lanzacohetes en el hombro.'),
        'PT': ('CAMINHANTE REBELDE (FOGUETES)', 'ATQ. PADR.: Míssil teleguiado ATQ. ESPEC.: Míssil triplo\nNova arma de Morden do futuro.\nEste modelo leva um lança-foguetes no ombro.'),
        'FR': ('MARCHEUR REBELLE (ROQUETTES)', 'ATT. STAND : Missile guidé   SPEC. ATK : Triple missile\nNouvelle arme de Morden provenant du Futur.\nCe modèle porte un lance-roquettes sur l’épaule.'),
        'DE': ('REBEL WALKER (RAKETEN)', 'STANDARD-ANGR.: Lenkrakete   SPEZ.-ANGR.: Dreifachrakete\nMordens neue Waffe aus der Zukunft.\nDieses Modell trägt einen Raketenwerfer auf der Schulter.'),
        'IT': ('WALKER RIBELLE (RAZZI)', 'ATC STAND.: Missile guidato ATC SPEC.: Missile triplo\nNuova arma di Morden dal futuro.\nQuesto modello porta un lanciarazzi sulla spalla.'),
        'RU': ('РЭБЭЛ УОКЕР (РАКЕТЫ)', 'СТОЙКА. АТК: Самонаводящаяся ракета СПЕЦ. АТК: Тройная ракета\nНовое оружие Мордена из будущего.\nЭта модель несёт ракетную установку на плече.'),
    }
    return {k: {'name': n, 'description': d} for k, (n, d) in t.items()}


def unit_file(animations, icon):
    return {'key': KEY, 'base_id': 228, 'faction': 1, 'identity': 'Rebel Army', 'shop_price': PRICE, 'available_from_start': True,
            'ap': AP,
            # 生命、击退门槛、移速、生产间隔、攻击等待与射程同原生 228（倍率 1:1）；伤害 × 9/10（R7）
            'hp_multiplier': [1, 1], 'knockback_threshold_multiplier': [1, 1], 'damage_multiplier': DAMAGE,
            'special_damage_multiplier': [1, 1], 'move_speed_multiplier': [1, 1], 'attack_wait_multiplier': [1, 1],
            'attack_range_multiplier': [1, 1], 'knockback_distance_multiplier': [1, 1], 'ballistic_range_multiplier': [1, 1],
            'production_reference_id': 228, 'production_interval_multiplier': [1, 1],
            # 近距射程 0：贴身时也以远距（导弹）攻击；近距组仍保留数据（核心把状态 30 也当作导弹攻击，攻击组按远距 40）
            'status_word_values': {'6': 0},
            'image_direction': 270,
            'icon': icon, 'textures': TEXTURES, 'sprite_descriptor': DESCRIPTOR, 'animations': animations,
            'localization': localization(), 'tags': ['ms7'],
            'behaviors': [{'name': 'launcher_walker', 'version': 1, 'params': {
                'attack_animation': ATTACK, 'special_animation': SALVO, 'fire_tick': FIRE_TICK, 'special_fire_ticks': list(SALVO_FIRE),
                'missile_first_animation': MISSILE_FIRST, 'front_effect': FX_FRONT, 'rear_effect': FX_REAR, 'puff_effect': PUFF,
                **MISSILE}}]}


def encode_ogg(data, rate, target):
    import soundfile as sf
    with sf.SoundFile(str(target), 'w', samplerate=rate, channels=data.shape[1], format='OGG', subtype='VORBIS') as f:
        q = sf._ffi.new('double*', VORBIS_QUALITY)
        assert sf._snd.sf_command(f._file, 0x1300, q, sf._ffi.sizeof('double')) == 1
        for i in range(0, len(data), 4096):
            f.write(data[i:i + 4096])


def decode_obm(path):
    """OI 图集（8 位调色板 kind 0 / 1）→ RGBA（同 verification/ms7_rwalker_20261106/rw_common.decode 的 8 位分支）。"""
    raw = Path(path).read_bytes()
    assert raw[:2] == b'OI' and raw[3] == 8 and (raw[2] & 0x7f) in (0, 1), path
    kind = raw[2] & 0x7f
    w, h = struct.unpack_from('<HH', raw, 4)
    size = 3 if kind == 0 else 4
    pal = np.array([tuple(raw[8 + i * size:8 + (i + 1) * size]) + ((255,) if size == 3 else ()) for i in range(256)], dtype=np.uint8)
    start = 8 + 256 * size
    idx = np.frombuffer(raw[start:start + w * h], dtype=np.uint8).reshape(h, w)
    return Image.fromarray(pal[idx], 'RGBA')


def draw_frame(cv, desc, pages, f, ox, oy):
    for k in range(desc['frames'][f]):
        x, y, w, h, ax, ay, fl, pg = desc['rects'][desc['frames'][f + 1 + k]]
        tile = pages[pg].crop((x, y, x + w, y + h))
        if fl & 1:
            tile = tile.transpose(Image.FLIP_LEFT_RIGHT)
        cv.alpha_composite(tile, (int(ox) - ax, int(oy) - ay))


def idle_pose(desc, animations, pages):
    """待机第 0 tick：腿帧（攻击脚本第一帧，同脚本 6）+ 身体帧（改写后的脚本 14 第一帧，偏移取其 op14）。返回 80 × 80 画布（朝左，原点 (40, 70)）。"""
    cv = Image.new('RGBA', (80, 80), (0, 0, 0, 0))
    legs = next(c['values'][0] for c in animations[str(ATTACK)] if c['opcode'] == 0)
    s14 = animations['14']
    off = next(c['values'] for c in s14 if c['opcode'] == 14)
    body = next(c['values'][0] for c in s14 if c['opcode'] == 0)
    draw_frame(cv, desc, pages, legs, 40, 70)
    draw_frame(cv, desc, pages, body, 40 + off[0], 70 + off[1])
    return cv


def free_icon_slot(raw, w, iw, ih):
    used = []
    for p in CONTENT.glob('units/*.json'):
        u = json.loads(p.read_text(encoding='utf-8'))
        icon = u.get('icon') or {}
        if u['key'] == KEY or 'atlas' in icon or icon.get('page') != 1:
            continue
        used.append(icon['rect'])
    for y in (770,):
        for x in range(0, 2048 - iw, 2):
            if any(not (x + iw + 4 <= a or x >= a + c + 4 or y + ih <= b or y >= b + d) for a, b, c, d in used):
                continue
            if all(raw[8 + ((y + j) * w + x + i) * 4 + 3] == 0 for j in range(ih) for i in range(iw)):
                return [x, y, iw, ih]
    raise RuntimeError('no free icon slot')


def icon_cell(pose):
    """拼合待机镜像为朝右，居中、底边对齐放进 40 × 40。"""
    im = pose.transpose(Image.FLIP_LEFT_RIGHT)
    c, bb = crop_bbox(im)
    cell = Image.new('RGBA', (40, 40), (0, 0, 0, 0))
    cell.alpha_composite(c, ((40 - c.width) // 2, 40 - c.height - 1))
    return cell


def write_icon(cell, rect):
    raw = bytearray((CONTENT / 'unit_icon_02.obm').read_bytes())
    assert raw[:4] == b'OI\x01\x20'
    w = struct.unpack_from('<H', raw, 4)[0]
    x0, y0, iw, ih = rect
    for j in range(ih):
        for i in range(iw):
            at = 8 + ((y0 + j) * w + x0 + i) * 4
            raw[at:at + 4] = bytes(cell.getpixel((i, j)))
    return bytes(raw)


def review(desc, animations, pages):
    """审阅图：待机 / 行走 / 跳跃的身体帧、导弹 16 方向、前烟与后焰、损毁 12 帧（各放大 3 倍，朝左原样）。"""
    rows = []

    def strip(frames_offsets):
        cells = []
        for f, ox, oy in frames_offsets:
            cv = Image.new('RGBA', (64, 64), (255, 255, 255, 255))
            draw_frame(cv, desc, pages, f, ox, oy)
            cells.append(cv)
        s = Image.new('RGBA', (64 * max(1, len(cells)), 64), (255, 255, 255, 255))
        for i, cv in enumerate(cells):
            s.alpha_composite(cv, (64 * i, 0))
        rows.append(s.resize((s.width * 3, s.height * 3), Image.NEAREST))
    for sc in ('14', '15', '20', '52'):
        frames, off = [], (0, 0)
        for c in animations[sc]:
            if c['opcode'] == 14:
                off = c['values']
            if c['opcode'] == 0 and c['values'][0] >= 0:
                frames.append((c['values'][0], 32 + off[0], 56 + off[1]))
        strip(frames[:12])
    strip([(animations[str(MISSILE_FIRST + k)][1]['values'][0], 32, 32) for k in range(HEADINGS)])
    strip([(c['values'][0], 40, 32) for c in animations[str(FX_FRONT)] if c['opcode'] == 0 and c['values'][0] >= 0])
    strip([(c['values'][0], 16, 32) for c in animations[str(FX_REAR)] if c['opcode'] == 0 and c['values'][0] >= 0])
    strip([(c['values'][0], 32, 56) for c in animations['13'] if c['opcode'] == 0 and c['values'][0] >= 0][:12])
    W = max(r.width for r in rows)
    sheet = Image.new('RGBA', (W, sum(r.height for r in rows)), (255, 255, 255, 255))
    y = 0
    for r in rows:
        sheet.alpha_composite(r, (0, y))
        y += r.height
    return sheet


def main():
    OUT.mkdir(exist_ok=True)
    page, desc, animations, stats = build()
    pages = [decode_obm(REPO / 'game_data' / 'assets' / 'com.snkplaymore.android003' / TEXTURES[0]), page]
    page.save(OUT / 'launcher_walker_page1.png')
    review(desc, animations, pages).save(OUT / 'review.png')
    pose = idle_pose(desc, animations, pages)
    pose.save(OUT / 'idle_pose.png')
    cell = icon_cell(pose)
    cell.save(OUT / 'icon_cell.png')
    obm = indexed_obm(page)
    report = {'stats': stats, 'obm_bytes': len(obm)}
    save_json(OUT / DESCRIPTOR, desc)
    if '--preview' in sys.argv:
        save_json(OUT / FILE, unit_file(animations, {'page': 1, 'rect': [0, 0, 40, 40], 'anchor': ICON_ANCHOR}))
        print(json.dumps(report, ensure_ascii=False))
        return
    index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
    if KEY not in index['unit_ids']:
        index['unit_ids'][KEY] = max(index['unit_ids'].values()) + 1
    (CONTENT / TEXTURES[1]).write_bytes(obm)
    index['assets'][TEXTURES[1]] = hashlib.blake2b(obm, digest_size=32).hexdigest()
    sounds = list(index.get('sounds', []))
    target = SOUND_KEY.split('.', 1)[1] + '.msdf'
    if not (CONTENT / target).exists():      # libsndfile 每次取随机流序列号，已有文件时不重编（换来源时先删去旧文件）
        import soundfile as sf
        data, rate = sf.read(str(MSXX_SE / SOUND_SRC), always_2d=True)
        encode_ogg(data.astype(np.float32), rate, CONTENT / target)
    entry = {'key': SOUND_KEY, 'file': target, 'type': 'se', 'volume': SOUND_VOLUME}
    at = next((i for i, e in enumerate(sounds) if e['key'] == SOUND_KEY), None)
    if at is None:
        sounds.append(entry)
    else:
        sounds[at] = entry
    index['sounds'] = sounds
    unit_path = CONTENT / 'units' / FILE
    icon_raw = (CONTENT / 'unit_icon_02.obm').read_bytes()
    if unit_path.exists():
        rect = json.loads(unit_path.read_text(encoding='utf-8'))['icon']['rect']
    else:
        rect = free_icon_slot(icon_raw, struct.unpack_from('<H', icon_raw, 4)[0], 40, 40)
        (CONTENT / 'unit_icon_02.obm').write_bytes(write_icon(cell, rect))   # 头像只在首次生成时写入（之后可由用户替换）；该资源的摘要在 content.json 中为 null
    icon = {'page': 1, 'rect': rect, 'anchor': ICON_ANCHOR}
    save_json(CONTENT / DESCRIPTOR, desc)
    save_json(unit_path, unit_file(animations, icon))
    save_json(CONTENT / 'content.json', index)
    report.update(unit_id=index['unit_ids'][KEY], icon=icon)
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
