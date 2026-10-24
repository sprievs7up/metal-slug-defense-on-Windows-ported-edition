"""Walter（385）与 Tyra（381）补帧接入游戏：把已完成的补帧图写成原版单位外观替换（content.json 的 stock_sprites）。
来源（核查文档 docs/msadv/MS_ADVANCE_UNITS_CHECK_2026-10-23.md 第 13–22 节；补帧图在 verification/ 下，只读）：
- Walter 前进（脚本 7 与 1）：Ralf 前进 12 帧换头（第 15 节，walter_walk.npz），Ralf 节奏每帧 2 tick；
- Walter 死亡（脚本 13–20）：MS5“向后炸飞”10 帧，用户修改定稿（第 17 节，walter_death_final.npz；第 9 帧同第 8 帧）；
- Walter 近战（脚本 8）：原帧 + 补帧 A、D（第 18 节，walter_melee.npz）；
- Walter 射击（脚本 9、10）：原帧 + 补帧 a1、a3、b2、b4、b5、c1，用户修改定稿（第 19 节，walter_shoot_final.npz）；
- Tyra 前进（脚本 7）：Nadia 前进 11 帧换头（第 13 节，headswap.npz），Nadia 节奏 13 tick；
- Tyra 死亡（脚本 13–20）：Nadia 脚本 13 / 14 的 18 帧（第 14 节，death.npz）；
- Tyra 普通攻击（脚本 9）：原帧 + 补帧 a1、a3、c1；近战（脚本 8）：原帧 + 补帧 k1、k3（第 22 节，tyra_shoot.npz / tyra_melee.npz）。
写出（community_content/）：
- <name>_frames.obm：补帧图逐张裁到不透明外接框后按行排入 512 宽画布（高取 2 的幂），OBM kind 1（8 位索引、RGBA 调色板，索引 0 透明）；
- <name>_descriptor.json：原生矩形与帧原样在前（偏移不变，未改写的原生脚本照常引用），补帧的矩形与帧追加在后；受击框与攻击框取原生；
- <name>_sprite.json：textures = 原生图集 + 补帧图集；animations = 改写的脚本（其余沿用原生）。
改写脚本时，原脚本中帧与等待以外的指令（op3 受击框、op4 攻击框、op7 弹起、op11 子层、op22 发射、op23 音效）放在与原脚本相同的 tick，
结尾的 op5 / op15 / op16 / op21 原样在后；新节奏中没有该 tick 的帧边界时报错。最后在 content.json 登记图集摘要与 stock_sprites。
用法：E:\\anaconda3\\python.exe -I build_stock_sprites.py"""
import re, sys, json, struct
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
VER = REPO / 'verification'
sys.path.insert(0, str(VER / 'msadv_tyra_walk_20261023'))
sys.path.insert(0, str(REPO))
from frames import Unit  # noqa: E402
from elfmem import read  # noqa: E402
import content_digest  # noqa: E402

OUT = REPO / 'community_content'
W_OUT = VER / 'msadv_walter_20261023' / 'out'
T_OUT = VER / 'msadv_tyra_walk_20261023' / 'out'
WALK_W_BOX, WALK_T_BOX = (-64, -80, 128, 96), (-48, -64, 96, 72)
DBOX = (-80, -96, 160, 112)
MBOX = SBOX = (-64, -80, 160, 112)
TERMINAL = (5, 15, 16, 21)
BLANK = None


def images_walter():
    imgs = {}
    d = np.load(W_OUT / 'walter_walk.npz')
    imgs.update({f'walk{j}': (d[f'f{j}'], WALK_W_BOX) for j in range(12)})
    d = np.load(W_OUT / 'walter_death_final.npz')
    imgs.update({f'death{k}': (d[f'f{k}'], DBOX) for k in range(9)})     # 第 9 帧与第 8 帧同图
    d = np.load(W_OUT / 'walter_melee.npz')
    imgs.update({f'melee{k}': (d[f'f{k}'], MBOX) for k in ('A', 'D')})
    d = np.load(W_OUT / 'walter_shoot_final.npz')
    imgs.update({f'shoot_{k}': (d[f'f{k}'], SBOX) for k in ('a1', 'a3', 'b2', 'b4', 'b5', 'c1')})
    return imgs


def scripts_walter():
    walk = [(f'walk{j}', 2) for j in range(12)]
    pre = [(167, 1), ('shoot_a1', 1), (170, 1), ('shoot_a3', 1), (173, 2)]
    mid = [(176, 1), ('shoot_b2', 1), (179, 1), ('shoot_b4', 1), ('shoot_b5', 1), (182, 1), ('shoot_c1', 1)]
    air = [('death0', 3), ('death1', 3), ('death2', 4), ('death3', 4), ('death4', 60)]
    ground = [('death5', 3), ('death6', 3), ('death7', 3), ('death8', 4), ('death8', 10)] + [(BLANK, 1), ('death8', 1)] * 6
    s = {1: walk, 7: walk,
         8: [(104, 2), (106, 2), (108, 1), ('meleeA', 1), (110, 1), (112, 1), ('meleeD', 1), (114, 3), ('meleeD', 1), (112, 1),
             (110, 1), ('meleeA', 1), (108, 1), (106, 2), (104, 2)],
         9: pre + mid + [(185, 1)],
         10: pre + mid + [(173, 1)] + mid + [(173, 1)] + mid + [(185, 1)]}
    for sid in (13, 17, 19):
        s[sid] = air
    s[15] = air + [(BLANK, 1)]
    for sid in (14, 16, 18, 20):
        s[sid] = ground
    return s


def images_tyra():
    imgs = {}
    d = np.load(T_OUT / 'headswap.npz')
    imgs.update({f'walk{j}': (d[f'f{j}'], WALK_T_BOX) for j in range(11)})
    d = np.load(T_OUT / 'death.npz')
    imgs.update({f'death{o}': (d[f'f{o}'], DBOX) for o in range(142, 177, 2)})
    d = np.load(W_OUT / 'tyra_shoot.npz')
    imgs.update({f'shoot_{k}': (d[f'f{k}'], SBOX) for k in ('a1', 'a3', 'c1')})
    d = np.load(W_OUT / 'tyra_melee.npz')
    imgs.update({f'melee_{k}': (d[f'f{k}'], MBOX) for k in ('k1', 'k3')})
    return imgs


def scripts_tyra():
    walk = [(f'walk{j}', h) for j, h in enumerate([1, 2, 1, 1, 1, 1, 2, 1, 1, 1, 1])]   # Nadia 前进节奏
    air = [(f'death{o}', h) for o, h in zip(range(142, 157, 2), [2, 2, 2, 2, 6, 6, 6, 45])] + [(BLANK, 1)]   # 末帧保持到原版的 72 tick
    ground = [(f'death{o}', h) for o, h in zip(range(158, 177, 2), [2, 2, 4, 8, 6, 4, 2, 2, 2, 10])] \
        + [(BLANK, 1), ('death176', 1)] * 5 + [(BLANK, 1)]
    s = {7: walk,
         8: [(191, 1), ('melee_k1', 1), (193, 1), ('melee_k3', 1), (195, 4), (197, 2)],
         9: [(199, 2), ('shoot_a1', 1), (202, 2), ('shoot_a3', 2), (205, 2), (208, 3), (211, 3), (214, 3), (217, 2), ('shoot_c1', 2), (220, 2)]}
    for sid in (13, 15, 17, 19):
        s[sid] = air
    for sid in (14, 16, 18, 20):
        s[sid] = ground
    return s


UNITS = {385: ('walter_rian', images_walter, scripts_walter), 381: ('tyra_elson', images_tyra, scripts_tyra)}


def native_bounds(u):
    d = u.d
    hits = [list(struct.unpack('<5i', read(d[4] + i * 20, 20))) for i in range((d[5] - d[4]) // 20)]
    attacks = []
    for i in range(256):
        r = list(struct.unpack('<5i', read(d[5] + i * 20, 20)))
        if i and r[4] != 7:
            break
        attacks.append(r)
    return hits, attacks


def pack(sizes, width=512):
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


def rewrite(orig, timeline, offset_of):
    """按新节奏 timeline（[(帧, 等待)]，帧为原生帧偏移、补帧名或 BLANK）重写原脚本 orig，事件指令保持原 tick。"""
    events, tail, t = [], [], 0
    for c in orig:
        op = c['opcode']
        if op == 0:
            continue
        if op == 1:
            t += c['values'][0]
        elif op in TERMINAL:
            tail.append(c)
        else:
            events.append((t, c))
    out, t, placed = [], 0, 0
    for frame, hold in timeline:
        while placed < len(events) and events[placed][0] == t:
            out.append(dict(events[placed][1])); placed += 1
        v = -1 if frame is BLANK else (offset_of[frame] if isinstance(frame, str) else frame)
        out += [{'opcode': 0, 'values': [v]}, {'opcode': 1, 'values': [hold]}]
        t += hold
    while placed < len(events) and events[placed][0] <= t:
        out.append(dict(events[placed][1])); placed += 1
    if placed != len(events):
        raise ValueError(f'event at tick {events[placed][0]} has no frame boundary in the new timeline')
    return out + [dict(c) for c in tail]


def build(uid):
    name, img_fn, script_fn = UNITS[uid]
    u = Unit(uid)
    imgs = img_fn()
    keys = list(imgs)
    crops = []
    for k in keys:
        img, box = imgs[k]
        ys, xs = np.where(img[..., 3] > 0)
        cy0, cy1, cx0, cx1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        crops.append((img[cy0:cy1, cx0:cx1], -(int(cx0) + box[0]), -(int(cy0) + box[1])))
    pos, height = pack([c[0].shape[:2] for c in crops])
    atlas = np.zeros((height, 512, 4), np.uint8)
    page = len(u.pages)
    rects = [list(r) for r in u.rects]
    frames = list(u.frames)
    offset_of = {}
    for k, (img, ax, ay), (px, py) in zip(keys, crops, pos):
        h, w = img.shape[:2]
        atlas[py:py + h, px:px + w] = img
        offset_of[k] = len(frames)
        frames += [1, len(rects)]
        rects.append([int(px), int(py), int(w), int(h), int(ax), int(ay), 0, page])
    raw, ncolors = obm_kind1(atlas)
    atlas_name = f'{name}_frames.obm'
    (OUT / atlas_name).write_bytes(raw)
    hits, attacks = native_bounds(u)
    desc = {'rects': rects, 'frames': frames, 'script_count': u.d[7], 'hit_bounds': hits, 'attack_bounds': attacks}
    (OUT / f'{name}_descriptor.json').write_text(json.dumps(desc, separators=(',', ':')) + '\n', encoding='utf-8', newline='\n')
    animations = {}
    for sid, tl in sorted(script_fn().items()):
        orig = [c for c in u.script(sid) if 'values' in c]
        animations[str(sid)] = rewrite(orig, tl, offset_of)
    spec = {'textures': list(u.pages) + [atlas_name], 'sprite_descriptor': f'{name}_descriptor.json', 'animations': animations}
    (OUT / f'{name}_sprite.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    ticks = {s: sum(c['values'][0] for c in cmds if c['opcode'] == 1) for s, cmds in animations.items()}
    print(uid, atlas_name, f'512x{height}', 'colors', ncolors, 'new images', len(crops), 'rects', len(rects), 'frames', len(frames),
          'scripts', ticks)
    return name


def register(names):
    index = OUT / 'content.json'
    raw = index.read_bytes().decode('utf-8')
    assert '\r\n' in raw
    text = raw.replace('\r\n', '\n')
    data = json.loads(text)
    for uid, name in names.items():
        atlas = f'{name}_frames.obm'
        digest = content_digest.blake2((OUT / atlas).read_bytes())
        line = f'    "{atlas}": "{digest}"'
        if atlas in data['assets']:
            text = re.sub(rf'    "{re.escape(atlas)}": "[0-9a-f]{{64}}"', line, text)
        else:
            end = text.index('\n  },\n', text.index('  "assets": {'))
            text = text[:end] + ',\n' + line + text[end:]
    if 'stock_sprites' not in data:
        block = '  "stock_sprites": {\n' + ',\n'.join(f'    "{uid}": "{name}_sprite.json"' for uid, name in sorted(names.items())) + '\n  },\n'
        anchor = text.index('  "unit_pack": {')
        text = text[:anchor] + block + text[anchor:]
    json.loads(text)
    index.write_bytes(text.replace('\n', '\r\n').encode('utf-8'))


if __name__ == '__main__':
    names = {uid: build(uid) for uid in UNITS}
    register(names)
    print('registered', names)
