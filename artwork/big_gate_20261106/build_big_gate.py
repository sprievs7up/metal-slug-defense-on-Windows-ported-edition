"""MS7 任务 7 大门（BIG GATE）：修筑者 s1xlv.big_gate_builder 与大门本体 s1xlv.big_gate（2026-11-06，大门会话；设计与数值见
docs/MS7_BIG_GATE_2026-11-06.md）。

来源：F:\\egg\\research\\metal_slug_attack\\decoded\\units\\0564（MSA 7.13.0 大门门本体，BattleAction_BigGate；修筑者 563 为工兵）。
- 图集：MSA BigGate1 / 2 / 3（1024×512、64×32、64×64）原样转为 OI 01 08（big_gate_1.obm 等），页序同 MSA。MSA 脚本中没有 op19 75
  的缩小，按 1:1 移植（偏移与判定框不缩放）。
- 动作：MSA 槽 0–31 编号沿用，删除 MSA 专有指令 24 / 26 / 28；槽 17 / 18（常规召唤的两个光球）末尾延长到 300 tick 以等待触地；
  槽 23（光球触地后放大，MSA 为 F.反坦克兵小图）改用图集中的青绿色光焰（MSA 矩形 24）。槽 29 / 31 换为基．寇卡版莫丁元帥（原生 253）
  的光环飞行与命中爆炸（原生 BulletAction_MordenXX_Attack_SP 命中时固定播放槽 31），矩形按图像匹配到 MSA 图集的同一图像
  （verification/ms7_bigate_20261106/overview/ring_rect_match.json），攻击框 4 / 5 取 253；槽 30 留空；槽 32 为第一颗光环（槽 29 加音效 320）。
- 头像：MSA unit_icon_02.obme 原格（m_unit_misc.pict 468 → (604,758) 40×40，锚点 [−5, −5]），用户将另行替换。
- 名称与说明：MSA 563 主数据表原文（verification/ms7_bigate_20261106/msa_gate_texts.json）。
运行：E:\\anaconda3\\python.exe -I artwork/big_gate_20261106/build_big_gate.py [--preview]
（--preview 只写 out/；否则写入 community_content/：三张图集、描述符、两个单位文件、unit_icon_02.obm 与 content.json）。
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MSA_UNIT = Path(r'F:\egg\research\metal_slug_attack\decoded\units\0564')
MSA_ICONS = Path(r'F:\egg\research\metal_slug_attack\decoded\unit_icons\unit_icon_02.obme.png')
VER = REPO / 'verification' / 'ms7_bigate_20261106'
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

_PVZ = REPO / 'artwork' / 'pvz_zombies_20261012' / 'build_pvz_zombies.py'
_src = _PVZ.read_text(encoding='utf-8')
_src = _src.replace("sys.path.insert(0, str(RT / 'packages'))", "").replace("os.add_dll_directory(str(RT / 'native'))", "")
pvz = type(sys)('pvzb')
pvz.__dict__['__file__'] = str(_PVZ)
exec(compile(_src, str(_PVZ), 'exec'), pvz.__dict__)
indexed_obm, save_json = pvz.indexed_obm, pvz.save_json

CONTENT = REPO / 'community_content'
OUT = HERE / 'out'
KEY_BUILDER, KEY = 's1xlv.big_gate_builder', 's1xlv.big_gate'
FILE_BUILDER, FILE = 'big_gate_builder.json', 'big_gate.json'
TEXTURES = ['big_gate_1.obm', 'big_gate_2.obm', 'big_gate_3.obm', 'big_gate_4.obm']
DESCRIPTOR = 'big_gate_descriptor.json'
MSA_ONLY = (24, 26, 28)              # SkillStun / EnableNockBack / SkillAvoid（MSA 专有，MSD 无对应）
BALL_SLOTS = (17, 18)                # 常规召唤的两个光球（槽 7 第 32、64 tick 以 op12 放出）
BALL_HOLD = 300                      # 光球脚本延长到 300 tick（原生巴士小兵弹体为 301）；触地由核心判定
GROW_SLOT, GROW_RECT = 23, 24        # 触地放大：MSA 矩形 24 = 青绿色光焰 (123,382) 77×77，锚点底边
RING_FLY, RING_BLANK, RING_HIT, RING_FIRST = 29, 30, 31, 32
# R2（用户 2026-11-06 确认示意动画 R1d）：待机循环、每次召唤一个单位、落地伸展为所召唤单位的图像（MSA 槽 23 的做法）
# R3（用户 2026-11-06）：去掉 R2 放光环时的漩涡闪黄（槽 39 与第 4 页的黄色漩涡）；光环出现处为行为库 ring_offsets 的缺省值（环体右上缘外侧）
IDLE_SLOT, SUMMON_SLOT = 6, 7
GROW_FIRST = 33                      # 33–38：summon_units 第 i 个单位的落地伸展（MSA 槽 23：op19 纵向 10%→100%，10 tick，每 3 tick 黑色剪影）
GROW_TICKS = 10
RING_SOUND = 320                     # F322BEAM.ogg：253 绝招第 80 tick 射出光环前播放
ICON_CELL = (604, 758, 40, 40)       # MSA 头像（pict 468，563 / 564 共用）
ICON_ANCHOR = [-5, -5]
# R6（用户 2026-11-06：预留头像，等待用户修改）：用户在原生我方绿格 handoff/unit_cell_player_green_50x50.png 上画好后另存为 USER_ICON，
# 取格内 ICON_BOX（x 5–44、y 5–44，即内框 40×40）中与绿格不同的像素写入 unit_icon_02.obm 的预留格（现为 (692,770) 40×40，锚点 [−5, −5]），
# 其余透明（同机动兵、虫穴、Fall Climber 头像的做法）；该文件不存在时保留现用的 MSA 占位。构图素材由 make_icon_handoff.py 导出到 handoff/。
USER_ICON = HERE / 'handoff' / 'unit_cell_player_green_50x50 拷贝.png'   # R7：用户 2026-11-06 交回的构图（RGB，无 alpha）
USER_CELL = HERE / 'handoff' / 'unit_cell_player_green_50x50.png'
ICON_BOX = (5, 5, 45, 45)
# 数值（用户 2026-11-06：BOSS 型建筑，AP 800，再出击 213.3 秒，完全不吃击退，Lv40 生命 60000，修筑时间为德拉诺 392 的 1.1 倍，
# 光环伤害为 253 绝招的 25%）。价格为代理暂定。
# R6（用户 2026-11-06：大门较强）：AP 850、Lv40 生命 40000、光环伤害再减 50%（253 的 1/8，向下取整）、光环冷却 3.8 秒、召唤间隔 +33%。
# R11（用户 2026-11-06）：AP 800、再出击 4800 帧、召唤 310 帧一轮、修筑完成后立即召唤一个单位（first_summon_wait 0，行为 v2）。
AP, PRICE = 800, 350                 # R6–R10 为 850
PRODUCTION = [32, 5]                 # 工兵 77 的生产间隔 750 帧 × 32/5 = 4800 帧 = 160 秒；R1–R10 为 [128, 15]（6400 帧 = 213.3 秒）
CONSTRUCTION = [737, 200]            # 状态词 38：工兵 77 为 20；R1–R7 为 [11, 2]（德拉诺 392 的 100 × 1.1 = 110）；R8（用户：修筑时间 −33%）× 0.67：20 × 737/200 = 73.7 → 74 帧（加载器向上取整）
HP = [60, 7]                         # 基准 245 Lv40 7000 × 60/7 = 60000（Lv1 3000 → 25714）；R6–R8 为 [40, 7]（40000），R9（用户）改回 60000
RING_DAMAGE = [174, 213, 252, 291, 330, 368]   # R10（用户：单颗 330）：253 绝招伤害（字 29）900/1100/1300/1500/1700/1900 × 330/1700 向下取整（Lv40 330）；R6–R9 为 × 1/8（112–237），R1–R5 为 × 1/4（225–475）
RING_COOLDOWN = 114                  # 光环冷却 3.8 秒 × 30 帧（行为缺省 72 = 2.4 秒）
SUMMON_WAIT = 182                    # 召唤周期（待机计数 + 召唤动作 128 帧）310 帧，待机计数 310 − 128（行为缺省 256）；R6–R10 为 383（511 帧）
FIRST_SUMMON_WAIT = 0                # R11：修筑完成当帧即开始第一次召唤（行为缺省 −1 = 同 summon_wait）
SUMMONS = [214, 215, 's1xlv.sarubia_future', 's1xlv.heavy_b_future', 's1xlv.m15a_future', 377]   # 未来吉利塔、未来基寇卡、未来爆竹红、未来重装B、未来 M-15A、未来 MV-280C
ONES = ('special_damage_multiplier', 'damage_multiplier', 'move_speed_multiplier', 'attack_wait_multiplier',
        'attack_range_multiplier', 'knockback_distance_multiplier', 'ballistic_range_multiplier')


def cmd(op, *v):
    return {'opcode': op, 'values': list(v)}


def ring_parts():
    """253 槽 29 / 31 的脚本与所用矩形（按 ring_rect_match.json 映射到 MSA 第 0 页）。返回 (矩形列表, 帧映射函数用的 {253 帧值: 253 矩形号}, 脚本)。"""
    units = json.loads((VER / 'runs' / 'du_021530_20832' / 'units.json').read_text(encoding='utf-8'))
    d = units['253']['descriptor']
    match = json.loads((VER / 'overview' / 'ring_rect_match.json').read_text(encoding='utf-8'))
    return d, match


def summon_page():
    """第 4 页（512×512）：summon_units 六种单位的待机首帧（原生描述符 + 未来版图集，含子层，原画朝左者镜像为朝右）与黑色剪影。
    渲染借 verification/ms7_bigate_20261106/gate_anim.py（msa_unit.Sim）。返回 (页图, {名称: 矩形})。"""
    ns = {'__name__': 'gate_anim', '__file__': str(VER / 'gate_anim.py')}
    exec(compile((VER / 'gate_anim.py').read_text(encoding='utf-8'), 'gate_anim', 'exec'), ns)
    keys = {'s1xlv.sarubia_future': 1024, 's1xlv.heavy_b_future': 1026, 's1xlv.m15a_future': 1025}
    page = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
    rects, x = {}, 0
    for i, key in enumerate(SUMMONS):
        rec, pages, direction = ns['SUMMON'][keys.get(key, key)][1]
        a = ns['Actor'](rec, pages, 6, 200, 300, mirror=direction == 270)
        c = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
        a.draw(c)
        bb = c.getbbox()
        im = c.crop(bb)
        black = Image.new('RGBA', im.size, (0, 0, 0, 0))
        black.paste(Image.new('RGBA', im.size, (0, 0, 0, 255)), (0, 0), im)
        page.paste(im, (x, 0))
        page.paste(black, (x, 100))
        ax, ay = 200 - bb[0], 300 - bb[1]
        rects[f'unit{i}'] = [x, 0, im.width, im.height, ax, ay, 0, 3]
        rects[f'black{i}'] = [x, 100, im.width, im.height, ax, ay, 0, 3]
        x += im.width + 2
    assert x <= 512
    return page, rects


def build(record, extra):
    rects = [list(r) for r in record['rects']]
    frames = list(record['frames'])
    d253, match = ring_parts()
    frame_map = {}
    for f in sorted(set(c[1] for k in (29, 31) for c in d253['scripts'][k] if c[0] == 0 and c[1] >= 0)):
        r = d253['frames'][f + 1]
        x, y, w, h, ax, ay, flip, page = d253['rects'][r]
        mx, my, err = match['match'][str(r)]
        assert page == 1 and err < 6, (r, err)
        rects.append([mx, my, w, h, ax, ay, flip, 0])
        frame_map[f] = len(frames)
        frames += [1, len(rects) - 1]
    grow_frame = len(frames)
    frames += [1, GROW_RECT]
    extra_frame = {}
    for name, r in extra.items():
        rects.append(r)
        extra_frame[name] = len(frames)
        frames += [1, len(rects) - 1]
    animations, stats = {}, {'removed_msa_only': 0}
    for slot in range(record['script_count']):
        out = []
        for c in record['scripts'][slot]:
            op, v = c[0], list(c[1:])
            if op in MSA_ONLY:
                stats['removed_msa_only'] += 1
                continue
            if slot == GROW_SLOT and op == 0 and v[0] >= 0:
                v = [grow_frame]
            out.append(cmd(op, *v))
        if slot == IDLE_SLOT:   # R2：待机 128 tick 循环（原为 op21 结束，核心以同一动作号重播无效，漩涡静止 127 tick）
            assert out[-1]['opcode'] == 21
            out[-1] = cmd(5)
        if slot == SUMMON_SLOT:   # R2：每次只召唤一个单位，删去第 64 tick 的第二个光球与其音效
            t, kept = 0, []
            for c in out:
                if t == 64 and (c['opcode'] == 12 or (c['opcode'] == 23 and c['values'] == [390])):
                    stats['summon_removed'] = stats.get('summon_removed', 0) + 1
                    continue
                kept.append(c)
                if c['opcode'] == 1:
                    t += c['values'][0]
            out = kept
        if slot in BALL_SLOTS:
            assert out[-1]['opcode'] == 21
            t = sum(c['values'][0] for c in out if c['opcode'] == 1)
            body = [c for c in out[1:-1]]          # 首条 op7 之后的闪烁帧（两帧一周期）
            out = out[:-1]
            while t < BALL_HOLD:
                for c in body:
                    out.append(c)
                    if c['opcode'] == 1:
                        t += c['values'][0]
            out.append(cmd(21))
        animations[str(slot)] = out

    def ring(k):
        return [cmd(c[0], *([frame_map[c[1]]] if c[0] == 0 and c[1] >= 0 else c[1:])) for c in d253['scripts'][k]]
    animations[str(RING_FLY)] = ring(29)
    animations[str(RING_BLANK)] = [cmd(0, -1), cmd(1, 1), cmd(21)]
    animations[str(RING_HIT)] = ring(31)
    # 第一颗：槽 29 的循环体（3 tick 一周期，op5 回到开头）展开到 BALL_HOLD tick，音效只在第 1 tick 播放一次
    # （第 0 tick 的音效会使嵌套建立中止；留在循环中则每周期重播）
    loop = ring(29)
    assert loop[-1]['opcode'] == 5
    first, t = [], 0
    while t < BALL_HOLD:
        for c in loop[:-1]:
            if c['opcode'] == 4 and first:
                continue
            first.append(c)
            if c['opcode'] == 1:
                t += c['values'][0]
                if t == c['values'][0]:
                    first.append(cmd(23, RING_SOUND))
    first.append(cmd(5))
    animations[str(RING_FIRST)] = first
    for i in range(len(SUMMONS)):
        seq = []
        for t in range(GROW_TICKS):
            seq += [cmd(19, 100, 10 * (t + 1)), cmd(0, extra_frame[('black' if t % 3 == 0 else 'unit') + str(i)]), cmd(1, 1)]
        seq += [cmd(19, 100, 100), cmd(0, extra_frame[f'unit{i}']), cmd(1, 600), cmd(21)]
        animations[str(GROW_FIRST + i)] = seq
    attack = [[0, 0, 0, 0, 0]] * 4 + [list(d253['attack_bounds'][4]), list(d253['attack_bounds'][5])]
    desc = {'rects': rects, 'frames': frames, 'script_count': GROW_FIRST + len(SUMMONS),
            'hit_bounds': record['hit_bounds'], 'attack_bounds': attack}
    stats.update(ring_frames=len(frame_map), rects=len(rects), frames=len(frames) // 2)
    return animations, desc, stats


def localization():
    texts = json.loads((VER / 'msa_gate_texts.json').read_text(encoding='utf-8'))['563']
    return {lang: {'name': t['name'].strip(), 'description': t['description']} for lang, t in texts.items()}


def unit_files(animations, icon):
    common = {'faction': 1, 'identity': 'Rebel Army', 'shop_price': PRICE, 'available_from_start': True, 'ap': AP}
    ones = {k: [1, 1] for k in ONES}
    builder = {'key': KEY_BUILDER, 'base_id': 77, **common, 'hp_multiplier': [1, 1], 'knockback_threshold_multiplier': [1, 1], **ones,
               'production_reference_id': 77, 'production_interval_multiplier': PRODUCTION,
               'icon': icon, 'animations': {}, 'localization': localization(), 'textures': ['donou.obm'], 'tags': ['ms7', 'msa'],
               'behaviors': [{'name': 'build_structure', 'version': 1,
                              'params': {'structure': KEY, 'construction_time_multiplier': CONSTRUCTION}}]}
    gate = {'key': KEY, 'base_id': 245, **common, 'hp_multiplier': HP, 'knockback_threshold_multiplier': HP, **ones,
            'production_reference_id': 77, 'production_interval_multiplier': PRODUCTION,
            'image_direction': 90, 'menu_reference_id': 77, 'internal_only': True,
            'icon': icon, 'textures': TEXTURES, 'sprite_descriptor': DESCRIPTOR, 'animations': animations,
            'localization': localization(), 'tags': ['ms7', 'msa'],
            # 光环：绝招攻击组（字 29 伤害、30 击退计量扣除、31 目标数、32 弹速、33 飞行上限，属性字 37 爆炸），除伤害外取 253 原值
            'status_word_values': {'29': RING_DAMAGE, '31': 999, '33': 500},
            'status_float_values': {'30': 10.0, '32': 8.0},
            'attack_attributes': {'special': 2},
            'draw_priority': -78,          # MSA 564 render −78
            'minimap_marker': [8, 8],      # 受击框 194 × 172 按 1/25、1/21.5 换算
            'behaviors': [{'name': 'big_gate', 'version': 2, 'params': {'summon_units': SUMMONS, 'grow_first_animation': GROW_FIRST,
                                                                    'grow_ticks': GROW_TICKS, 'summon_wait': SUMMON_WAIT,
                                                                    'first_summon_wait': FIRST_SUMMON_WAIT,
                                                                    'ring_cooldown': RING_COOLDOWN}}]}
    return builder, gate


def free_icon_slot(raw, w):
    used = []
    for p in CONTENT.glob('units/*.json'):
        u = json.loads(p.read_text(encoding='utf-8'))
        icon = u.get('icon') or {}
        if u['key'] in (KEY, KEY_BUILDER) or 'atlas' in icon or icon.get('page') != 1:
            continue
        used.append(icon['rect'])
    iw, ih = ICON_CELL[2:]
    for y in (770,):
        for x in range(0, 2048 - iw, 2):
            if any(not (x + iw + 4 <= a or x >= a + c + 4 or y + ih <= b or y >= b + d) for a, b, c, d in used):
                continue
            if all(raw[8 + ((y + j) * w + x + i) * 4 + 3] == 0 for j in range(ih) for i in range(iw)):
                return [x, y, iw, ih]
    raise RuntimeError('no free icon slot')


def user_icon():
    """用户构图中与原生绿格不同的像素（ICON_BOX 内），其余透明（同 Fall Climber 的 make_icon）。"""
    a = np.asarray(Image.open(USER_ICON).convert('RGBA'))
    c = np.asarray(Image.open(USER_CELL).convert('RGBA'))
    assert a.shape == c.shape == (50, 50, 4)
    x0, y0, x1, y1 = ICON_BOX
    sa, sc = a[y0:y1, x0:x1], c[y0:y1, x0:x1]
    changed = np.any(sa != sc, axis=2)
    out = np.zeros_like(sa)
    out[changed] = sa[changed]
    out[changed, 3] = 255
    return Image.fromarray(out, 'RGBA')


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


def main():
    OUT.mkdir(exist_ok=True)
    (HERE / 'source').mkdir(exist_ok=True)
    record = json.loads((MSA_UNIT / 'record.json').read_text(encoding='utf-8'))
    assert record['names'] == ['BigGate1_out.obm', 'BigGate2_out.obm', 'BigGate3_out.obm'] and record['script_count'] == 32
    assert not any(c[0] == 19 and c[1:] == [75, 75] for s in record['scripts'] for c in s)   # 没有 op19 75 的缩小
    atlases = [Image.open(MSA_UNIT / (n + '.png')).convert('RGBA') for n in record['names']]
    page4, extra = summon_page()
    atlases.append(page4)
    page4.save(HERE / 'source' / 'big_gate_4.png')
    animations, desc, stats = build(record, extra)
    obms = [indexed_obm(a) for a in atlases]
    raw_icons = (CONTENT / 'unit_icon_02.obm').read_bytes()
    existing = json.loads((CONTENT / 'units' / FILE).read_text(encoding='utf-8'))['icon']['rect'] if (CONTENT / 'units' / FILE).exists() else None
    rect = existing or free_icon_slot(raw_icons, struct.unpack_from('<H', raw_icons, 4)[0])
    icon = {'page': 1, 'rect': rect, 'anchor': ICON_ANCHOR}
    builder, gate = unit_files(animations, icon)
    x, y, iw, ih = ICON_CELL
    cell = Image.open(MSA_ICONS).convert('RGBA').crop((x, y, x + iw, y + ih))
    cell.save(HERE / 'source' / f'msa_icon_big_gate_{x}_{y}.png')
    report = {'stats': stats, 'colors': [len(set(a.getdata())) for a in atlases], 'obm_bytes': [len(o) for o in obms],
              'icon': icon, 'hit_bounds': desc['hit_bounds'], 'attack_bounds': desc['attack_bounds']}
    save_json(OUT / DESCRIPTOR, desc)
    save_json(OUT / FILE, gate)
    if '--preview' in sys.argv:
        print(json.dumps(report, ensure_ascii=False))
        return
    index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
    for key in (KEY_BUILDER, KEY):
        if key not in index['unit_ids']:
            index['unit_ids'][key] = max(index['unit_ids'].values()) + 1
    for name, data in zip(TEXTURES, obms):
        (CONTENT / name).write_bytes(data)
        index['assets'][name] = hashlib.blake2b(data, digest_size=32).hexdigest()
    if USER_ICON.exists():   # R6：用户构图写入预留格
        cell = user_icon()
        assert list(cell.size) == rect[2:] and ICON_ANCHOR == [-ICON_BOX[0], -ICON_BOX[1]], (cell.size, rect)
        (CONTENT / 'unit_icon_02.obm').write_bytes(write_icon(cell, rect))
        report['icon_source'] = USER_ICON.name
    elif not existing:
        (CONTENT / 'unit_icon_02.obm').write_bytes(write_icon(cell, rect))   # 该资源的摘要在 content.json 中为 null，保持不变
    save_json(CONTENT / DESCRIPTOR, desc)
    save_json(CONTENT / 'units' / FILE_BUILDER, builder)
    save_json(CONTENT / 'units' / FILE, gate)
    save_json(CONTENT / 'content.json', index)
    report['unit_ids'] = {KEY_BUILDER: index['unit_ids'][KEY_BUILDER], KEY: index['unit_ids'][KEY]}
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
