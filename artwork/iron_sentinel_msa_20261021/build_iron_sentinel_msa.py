"""IRON SENTINEL（钢铁哨兵）按 MSA 7.13.0 原始动作记录重做（2026-10-21，AGENTS 第 182 节；方案
docs/ms6/IRON_SENTINEL_MSA_PORT_PLAN_2026-10-21.md，数值 docs/ms6/IRON_SENTINEL_MSA_STATS_2026-10-21.md 与用户设定）。

来源：F:\\egg\\research\\metal_slug_attack\\decoded\\units\\0287（msa_unit.py export 287；288 第二形态共用同一记录）。
- 图集：iron_slider_out.obm（2048×1024）、ironiso_1_out.obm（256×256）原样转为 MSD OI 01 08（各不超过 256 色）。
- 脚本：142 条，编号不变（原生较早版本的槽号由核心钩子换成 MSA 编号）。删除 MSA 专有指令 24–29；部件 op19 75% 改为 100%
  （用户 2026-10-21：不按 MSA 缩小一号），op11 / op12 / op22 偏移、op14 位移与部件、弹体、效果脚本中的 op7 按 4/3 缩放；
  单位本体槽（受击后退 12、20）的 op7 不缩放（击退距离不变）。受击框与攻击框按 4/3 缩放。未写 op19 的效果层保持 100%。
- 音效：SoundID 204/208/212/229/249/260/261/279/332/457 与 MSD 原生同号同名，原样保留；491（MSA cata2，行走）与 688
  （MSA knock_back_heavy，受击）登记为本体音效 s1xlv.isentinel_walk / s1xlv.isentinel_knockback（MSA .msa 即 Ogg）。
- 单位：第一形态 s1xlv.iron_sentinel（UnitID 1062，基准 394 原生 IRON SLIDER，行为 iron_slider）；第二形态
  s1xlv.iron_sentinel_form2（内部单位，基准 395，行为 iron_slider_second_form）。数值按用户 2026-10-21 设定（Lv40）：
  总生命 60000（第一形态 40000，第二形态 20000）、AP 900、再出击 180 秒（5400 tick）、普通攻击 600、绝招 3000（每发）、
  第二形态巨型导弹 8000（每次命中）、抗击退 160、远程攻击距离 300、投射距离 600、绝招冷却 500、勋章 500、
  强化基数 1800（BIG SHIEE 312 的 1500 × 120%）；未指定项按 MSA 1:1。
  R2（用户 2026-10-21）：第一形态生命 60000（总计 80000）、AP 950、移速 ×4/5（4.0 → 3.2）、第一形态受击后退距离 ×1/2；
  第二形态保留免击退；绝招可发动时的蓝光按本体大小（special_effect_size，原生 394 / 395 为 0，按空帧绘制成小光点）。
  R3：本体槽下移 DROP（8）。R4（AGENTS 第 188 节）：菜单槽 0–2 挂 40% 的部件副本（编队页等菜单显示）；头像改为 MSA 原格 46×46、
  锚点 −5,1（msa_icons.py 写入图集）。R5（用户 2026-10-22）：第一形态生命 40000、第二形态 50000（合计 90000）、AP 999，其余不变。
  R6（用户 2026-10-22）：第二形态巨型导弹每次命中 8000 → 16000（damage_multiplier [32, 3]），其余不变。
  R7（用户 2026-10-22）：第二形态顶盖切图带着的徽记圆环一段清除（clean_lid），消除 X 徽记上方多出的一截。
  R8（用户 2026-10-22）：R7 清除后顶盖下的阴影带成 U 形缺口；改为圆环色补成阴影带、延续下缘线，只清除下缘以下（4 个顶盖切图）。
  R9（用户 2026-10-22：R8 的阴影盖掉徽记上部、下缘折一下，要求徽记完整、阴影成一条线、阴影下的徽记为阴影色）：撤回 R7 / R8 的
  顶盖修图，图集恢复 MSA 原样；含 op14 的本体部件（顶盖等）的 op14 y 补上 R3 漏加的 DROP；正面板（部件 30 / 94）各槽的 op11 y
  加 PLATE_FIX（3）。顶盖、正面板与车身的相对位置因此同《合金弹头6》合成图，顶盖原画中阴影里的徽记上部与正面板的徽记对齐。
  R11（用户 2026-10-22：16000 毁灭性太强）：第二形态巨型导弹每次命中 16000 → 8000（damage_multiplier [16, 3]），其余不变。
  R12（社区意见，用户 2026-10-25：伤害不削，第二形态在总生命中的占比降低，快速击杀成为对手的奖励；画在其他单位之后）：第一形态
  生命 60000、第二形态 30000（合计 90000 不变），绘制优先级 −90（同 BIG SHIEE），其余不变。
运行：E:\\anaconda3\\python.exe -I artwork/iron_sentinel_msa_20261021/build_iron_sentinel_msa.py [--preview]
（--preview 只写 out/；否则写入 community_content/：两张图集、描述符、两个单位文件、音效与 content.json）。
"""
from pathlib import Path
import copy
import hashlib
import json
import shutil
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MSA_UNIT = Path(r'F:\egg\research\metal_slug_attack\decoded\units\0287')
MSA_DATA = Path(r'F:\egg\research\metal_slug_attack\data\files')
sys.path.insert(0, r'F:\egg\research\metal_slug_attack\scripts')

from PIL import Image  # noqa: E402
import msa_unit  # noqa: E402

_PVZ = REPO / 'artwork' / 'pvz_zombies_20261012' / 'build_pvz_zombies.py'
_src = _PVZ.read_text(encoding='utf-8')
_src = _src.replace("sys.path.insert(0, str(RT / 'packages'))", "").replace("os.add_dll_directory(str(RT / 'native'))", "")
pvz = type(sys)('pvzb')
pvz.__dict__['__file__'] = str(_PVZ)
exec(compile(_src, str(_PVZ), 'exec'), pvz.__dict__)
indexed_obm, save_json = pvz.indexed_obm, pvz.save_json

CONTENT = REPO / 'community_content'
OUT = HERE / 'out'
KEY, KEY2 = 's1xlv.iron_sentinel', 's1xlv.iron_sentinel_form2'
TEXTURES = ['iron_sentinel_0.obm', 'iron_sentinel_1.obm']
DESCRIPTOR = 'iron_sentinel_descriptor.json'
SCALE = (4, 3)                      # 部件 75% → 100%
BODY_SLOTS = {0, 1, 2, 6, 7, 9, 10, 11, 12, 13, 17, 18, 19, 20, 21}   # 单位本体槽：其 op7 移动单位本身
# R3（用户 2026-10-21：悬空较多，向下 8 像素）：本体槽中 op11（部件）、op12 / op22（生成点）的 y 加 DROP，部件与其生成的弹体
# 一同下移；本体受击框上沿下移 DROP（下沿仍在地面）。弹体与效果脚本不变。
DROP = 8
# R9（verification/iron_sentinel_msa_20261021/plate_fix/）：
# - 部件脚本的 op14 设定该部件相对父层的位置，取代 op11 的偏移（实测第二形态顶盖 75、部件 76 画在 op14 位置）。R3 只改了 op11，
#   本体槽的直接部件中含 op14 的（67 / 68 形态转换，75 / 76 第二形态，97 / 98 第二形态损毁）比车身高 DROP；其 op14 y 同样加 DROP。
#   这些部件也被未使用的非本体槽 22 / 65 / 78 / 79 以偏移 0 挂载，那几个槽中它们比其余部件低 DROP（原生动作类不播放这些槽）。
# - 正面板（部件 30，第二形态损毁中为 94）在 MSA 中比《合金弹头6》合成图（MS6 素材表 REFERENCES）偏上：以车身 29 为准，第二形态
#   顶盖 75 与第一形态顶部 37 和 MS6 相差不到 1 像素，正面板差 (1.4, −2.4)。顶盖切图下沿画有 MS6 原画中落在阴影里的徽记圆环上部，
#   正面板偏上时与其自身的徽记错开（R7 所见多出的一截）。各槽放置正面板的 op11 y 加 PLATE_FIX 后，正面板与车身、两种顶部的偏差
#   均在 1 精灵像素以内。菜单槽的 40% 副本（脚本 143）未改。
PLATE_FIX = 3
PLATE_SCRIPTS = (30, 94)
MSA_ONLY = range(24, 73)
SOUND_KEYS = {491: 's1xlv.isentinel_walk', 688: 's1xlv.isentinel_knockback'}
SOUND_FILES = {'s1xlv.isentinel_walk': ('cata2.msa', 'isentinel_walk.msdf', 35),
               's1xlv.isentinel_knockback': ('knock_back_heavy.msa', 'isentinel_knockback.msdf', 110)}
OLD_SOUNDS = ('s1xlv.isentinel_launch', 's1xlv.isentinel_blast')
# 头像（R4）：MSA 头像图集原格 (295,644) 46×46（透明底剪影），由 msa_icons.py 写入 unit_icon_02；内框在格的左下，锚点 −5,1
ICON = {'page': 1, 'rect': [1650, 768, 46, 46], 'anchor': [-5, 1]}
# 菜单显示（R4，用户：卡组浏览界面类比大杰缩小）：原生大杰 312 的菜单槽 0–2 挂专用部件（脚本 73–85，op19 50），
# 原生 IRON SLIDER 394 的菜单部件（脚本 100–108）为 op19 40。本单位取 40（原画的 40%）：编队页中宽约为大杰的 1.1 倍
# （50% 时约 1.4 倍）。菜单槽 0–2 改挂追加在脚本表末尾的部件副本：op19 75 → 40，偏移为 MSA 原值 × 8/15（战斗为 × 4/3），
# 下移量取 DROP × 0.4。父层 op19 不作用于子层，部件须各自缩放。
MENU_SLOTS = (0, 1, 2)
MENU_SCALE = (8, 15)
SPECIAL_EFFECT_SIZE = [380, 120]    # 本体宽约 800、高约 476（动作演示图像范围单位）；蓝光宽 2×380+31，高 (2×120+49)×0.64
# 绘制优先级（R12，社区意见、用户 2026-10-25：画在其他单位之后）：原生按对象 +0xf0 升序绘制，值取数据行 +0x340；基准 394 / 395 为 0，
# 原版大型单位为负值（BIG SHIEE −90、REBEL GIGANT −78、JUPITER KING −80），本单位取大杰的 −90。
DRAW_PRIORITY = -90

FIRST = {
    'base_id': 394, 'ap': 999, 'shop_price': 500, 'upgrade_cost_base': 1800,
    'hp_multiplier': [6, 5],                      # 394：10000…50000 → 12000…60000（Lv1…Lv40，R12；R5 为 [4, 5]，R2 为 [6, 5]）
    'knockback_threshold_multiplier': [32, 5],    # 25 → 160（用户指定，R2、R5、R12 生命修改后保持）
    'knockback_distance_multiplier': [1, 2],      # 受击后退距离减半（R2）
    'production_reference_id': 394, 'production_interval_multiplier': [6, 7],   # 6300 → 5400 tick（180 秒）
    'damage_multiplier': [2, 5],                  # 远程 500…1500 → 200…600
    'special_damage_multiplier': [5, 2],          # 绝招 1000…3000 → ×5/2×2/5 = 1000…3000
    'near_damage_multiplier': [3, 10],            # 近距 1000…5000 → ×3/10×2/5 = 120…600
    'move_speed_multiplier': [16, 17],            # 3.4 → 3.2（MSA 4.0 减慢 20%，R2）
    'status_word_values': {'6': 0, '7': 300, '20': 20, '26': 600, '27': 20, '33': 600, '34': 30, '35': 500, '36': 500},
    'status_float_values': {'16': 1, '18': 0, '23': 1, '25': 20, '30': 20, '32': 10},
}
SECOND = {
    'base_id': 395, 'ap': 999, 'shop_price': 500, 'upgrade_cost_base': 1800,
    'hp_multiplier': [3, 5],                      # 395：10000…50000 → 6000…30000（Lv1…Lv40，R12；R5 为 [1, 1]，此前为 [2, 5]）
    'knockback_threshold_multiplier': [32, 5],
    'knockback_distance_multiplier': [1, 1],      # 出场后免击退（原生与 MSA 动作类），保持原值
    'production_reference_id': 395, 'production_interval_multiplier': [6, 7],
    'damage_multiplier': [16, 3],                 # 远程 500…1500 → 2666…8000（巨型导弹；R11 由 R6 的 [32, 3] 即 16000 改回）
    'special_damage_multiplier': [1, 2],          # 绝招 1000…3000 → ×1/2×16/3 = 2666…8000（只影响 STATUS 显示）
    'near_damage_multiplier': [3, 10],            # 近距 1000…5000 → ×3/10×16/3 = 1600…8000（只影响 STATUS 显示）
    'move_speed_multiplier': [16, 17],
    'status_word_values': {'6': 0, '7': 300, '20': 70, '26': 600, '27': 70, '33': 600, '34': 70, '35': 500, '36': 500},
    'status_float_values': {'16': 10, '18': 10, '23': 10, '25': 10, '30': 10, '32': 10},
}


def scaled(v):
    a, b = SCALE
    return round(v * a / b)


def transform(record):
    """MSA 脚本 → 本体动画（编号不变）。返回 (动画字典, 统计)。"""
    stats = {'removed_msa_only': 0, 'op19': 0, 'offsets': 0, 'dropped': 0, 'op14_dropped': 0, 'plate_fixed': 0,
             'op7_scaled': 0, 'op7_body_kept': 0, 'sounds': {}}
    scripts = record['scripts']
    placed = {c[1] for slot in BODY_SLOTS for c in scripts[slot] or [] if c[0] == 11}
    op14_parts = {s for s in placed if any(c[0] == 14 for c in scripts[s] or [])}
    animations = {}
    for slot, cmds in enumerate(record['scripts']):
        out = []
        for c in cmds or [[0, -1], [1, 1], [21]]:
            op, v = c[0], list(c[1:])
            if op in MSA_ONLY:
                stats['removed_msa_only'] += 1
                continue
            if op == 19 and v == [75, 75]:
                v = [100, 100]
                stats['op19'] += 1
            elif op in (11, 12, 22):
                v[2], v[3] = scaled(v[2]), scaled(v[3])
                if slot in BODY_SLOTS:
                    v[3] += DROP
                    stats['dropped'] += 1
                if op == 11 and v[0] in PLATE_SCRIPTS:
                    v[3] += PLATE_FIX
                    stats['plate_fixed'] += 1
                stats['offsets'] += 1
            elif op == 14:
                v = [scaled(v[0]), scaled(v[1])]
                if slot in op14_parts:
                    v[1] += DROP
                    stats['op14_dropped'] += 1
                stats['offsets'] += 1
            elif op == 7:
                if slot in BODY_SLOTS:
                    stats['op7_body_kept'] += 1
                else:
                    v = [scaled(x) for x in v]
                    stats['op7_scaled'] += 1
            elif op == 23:
                stats['sounds'][v[0]] = stats['sounds'].get(v[0], 0) + 1
                if v[0] in SOUND_KEYS:
                    v = [SOUND_KEYS[v[0]]]
            out.append({'opcode': op, 'values': v})
        animations[str(slot)] = out
    return animations, stats


def menu_animations(record, animations):
    """菜单槽 0–2 改挂缩小的部件副本（追加为脚本 script_count 起）；返回副本数。"""
    def menu(v):
        a, b = MENU_SCALE
        return round(v * a / b)
    parts = []

    def walk(slot):
        for c in record['scripts'][slot] or []:
            if c[0] in (10, 11) and c[1] not in parts and c[1] not in MENU_SLOTS:
                parts.append(c[1])
                walk(c[1])
    for slot in MENU_SLOTS:
        walk(slot)
    remap = {s: record['script_count'] + i for i, s in enumerate(sorted(parts))}

    def convert(slot):
        out = []
        for c in record['scripts'][slot]:
            op, v = c[0], list(c[1:])
            if op in MSA_ONLY:
                continue
            if op == 19:
                assert v == [75, 75], (slot, v)
                v = [menu(75), menu(75)]
            elif op in (10, 11):
                v[0] = remap.get(v[0], v[0])
                if op == 11:
                    v[2], v[3] = menu(v[2]), menu(v[3]) + (round(DROP * 0.4) if slot in MENU_SLOTS else 0)
            elif op in (12, 22, 14, 7):
                raise AssertionError(('menu part moves or spawns', slot, op))
            elif op == 23 and v[0] in SOUND_KEYS:
                v = [SOUND_KEYS[v[0]]]
            out.append({'opcode': op, 'values': v})
        return out
    for part in parts:
        assert any(c[0] == 19 for c in record['scripts'][part]), part
    for slot in MENU_SLOTS:
        animations[str(slot)] = convert(slot)
    for part, index in remap.items():
        animations[str(index)] = convert(part)
    return len(parts)


def descriptor(record):
    def box(b):
        return [scaled(b[0]), scaled(b[1]), scaled(b[2]), scaled(b[3]), b[4]]
    # MSA 帧表第 24 项为“1 个部件、矩形 −1”（空帧，无脚本使用）；加载器要求矩形序号在表内，改为追加的 1×1 透明矩形
    # （第 0 页右下角像素，alpha 为 0），帧表长度与各帧起点不变。
    rects = [list(r) for r in record['rects']]
    frames = list(record['frames'])
    if 0xffffffff in frames:
        rects.append([2047, 1023, 1, 1, 0, 0, 0, 0])
        frames = [len(rects) - 1 if v == 0xffffffff else v for v in frames]
    def lowered(b):     # R3：上沿下移 DROP，下沿不变
        return [b[0], b[1] + DROP, b[2], b[3] - DROP, b[4]] if b[3] > DROP else b
    return {'rects': rects, 'frames': frames, 'script_count': record['script_count'],
            'hit_bounds': [lowered(box(b)) for b in record['hit_bounds']],
            'attack_bounds': [box(b) for b in record['attack_bounds']]}


def preview_record(record, animations, desc):
    """预览用：把变换后的动画换回 msa_unit 的记录格式（音效键不参与绘制）。"""
    r = copy.deepcopy(record)
    r['scripts'] = [[[c['opcode'], *(x if isinstance(x, int) else 0 for x in c['values'])] for c in animations[str(i)]]
                    for i in range(record['script_count'])]
    r['hit_bounds'], r['attack_bounds'] = desc['hit_bounds'], desc['attack_bounds']
    return r


def body_extent(r, atlases):
    """待机槽 6 第 0 帧各部件四边形（旋转、缩放后）的外接范围（精灵像素，相对单位原点）。"""
    import math
    sim = msa_unit.Sim(r, atlases)
    sim.start(6)
    xs, ys = [], []
    for lay in sim.layers:
        if lay.frame < 0:
            continue
        ox, oy = sim.origin(lay)
        c, s = math.cos(math.radians(lay.angle)), math.sin(math.radians(lay.angle))
        for k in range(r['frames'][lay.frame]):
            x, y, w, h, ax, ay, flags, page = r['rects'][r['frames'][lay.frame + 1 + k]]
            for u, v in ((0, 0), (w, 0), (0, h), (w, h)):
                px, py = (u - ax) * lay.sx, (v - ay) * lay.sy
                xs.append(ox + c * px - s * py)
                ys.append(oy + s * px + c * py)
    return round(min(xs)), round(min(ys)), round(max(xs)), round(max(ys))


def unit_files(animations, current):
    text = current['localization']
    # 394 / 395 未发布，原生菜单表无对应行：菜单行取同类大型载具 BIG SHIEE（312），加载器改写其中的 UnitID、阵营与头像。
    common = {'faction': 1, 'identity': 'Rebel Army', 'available_from_start': True,
              'menu_reference_id': 312,
              # 绝招可发动时的蓝光（BattleUnit::draw，宽、高为两倍值）：主槽不画帧（部件均为 op11 子层），原生按空帧画成小光点。
              # 按原版大型载具（286 等为 [160, 90]：蓝光与本体等宽，高约为本体的 0.4–0.5）由本体图像范围换算。
              'special_effect_size': SPECIAL_EFFECT_SIZE, 'draw_priority': DRAW_PRIORITY,
              # 原画朝向：MSA 287 的图像表为 90（朝右）；基准 394 / 395 在 MSD 中为 270，沿用会使单位镜像。
              'image_direction': 90,
              'icon': ICON, 'textures': TEXTURES, 'sprite_descriptor': DESCRIPTOR, 'animations': animations,
              'localization': text, 'tags': ['ms6', 'msa']}
    first = {'key': KEY, **{k: v for k, v in FIRST.items()}, **common,
             'behaviors': [{'name': 'iron_slider', 'version': 1, 'params': {'second_form': KEY2}}]}
    second = {'key': KEY2, **{k: v for k, v in SECOND.items()}, **common, 'internal_only': True,
              'behaviors': [{'name': 'iron_slider_second_form', 'version': 1, 'params': {}}]}
    return first, second


def main():
    OUT.mkdir(exist_ok=True)
    record = json.loads((MSA_UNIT / 'record.json').read_text(encoding='utf-8'))
    assert record['names'] == ['iron_slider_out.obm', 'ironiso_1_out.obm'] and record['script_count'] == 142
    atlases = [Image.open(MSA_UNIT / (n + '.png')).convert('RGBA') for n in record['names']]
    animations, stats = transform(record)
    desc = descriptor(record)
    stats['menu_parts'] = menu_animations(record, animations)
    desc['script_count'] += stats['menu_parts']
    pr = preview_record(record, animations, desc)
    x0, y0, x1, y1 = body_extent(pr, atlases)
    # 小地图标记：按原版大型单位标记与图像尺寸（世界单位 = 2 精灵像素）的比例（宽约 1/25、高约 1/21.5）
    marker = [round((x1 - x0) * 2 / 25), round((y1 - y0) * 2 / 21.5)]
    current = json.loads((CONTENT / 'units' / 'iron_sentinel.json').read_text(encoding='utf-8'))
    first, second = unit_files(animations, current)
    first['minimap_marker'] = second['minimap_marker'] = marker
    obms = [indexed_obm(im) for im in atlases]
    report = {'stats': stats, 'extent_sprite_px': [x0, y0, x1, y1], 'minimap_marker': marker,
              'hit_bounds': desc['hit_bounds'][1], 'attack_bounds': len(desc['attack_bounds']),
              'colors': [len(set(im.getdata())) for im in atlases], 'obm_bytes': [len(b) for b in obms]}
    for slot, ticks, step in ((6, 12, 2), (9, 184, 8), (10, 140, 6), (13, 40, 3), (19, 112, 6), (12, 16, 2)):
        sim = msa_unit.Sim(pr, atlases)
        sim.start(slot)
        frames = []
        for t in range(ticks):
            if t % step == 0:
                frames.append(sim.draw((1600, 760), (420, 640), 2))
            sim.step()
        tw, th = 800, 380
        cols = 4
        rows = (len(frames) + cols - 1) // cols
        sheet = Image.new('RGB', (tw * cols, th * rows), (20, 20, 20))
        for i, im in enumerate(frames):
            sheet.paste(im.convert('RGB').resize((tw, th), Image.BOX), ((i % cols) * tw, (i // cols) * th))
        sheet.save(OUT / f'preview_slot{slot:02d}.png')
    if '--preview' in sys.argv:
        print(json.dumps(report, ensure_ascii=False))
        return
    index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
    if KEY2 not in index['unit_ids']:
        index['unit_ids'][KEY2] = max(index['unit_ids'].values()) + 1
    for name, raw in zip(TEXTURES, obms):
        (CONTENT / name).write_bytes(raw)
        index['assets'][name] = hashlib.blake2b(raw, digest_size=32).hexdigest()
    # 已登记的条目原位更新、未登记的追加（R3：保持其他内容追加的音效条目的次序）
    sounds = [e for e in index.get('sounds', []) if e['key'] not in OLD_SOUNDS]
    for key, (source, target, volume) in SOUND_FILES.items():
        src = next(d / source for d in (MSA_DATA, MSA_DATA.parents[1] / 'apk' / 'assets') if (d / source).is_file())
        shutil.copyfile(src, CONTENT / target)
        entry = {'key': key, 'file': target, 'type': 'se', 'volume': volume}
        at = next((i for i, e in enumerate(sounds) if e['key'] == key), None)
        if at is None:
            sounds.append(entry)
        else:
            sounds[at] = entry
    index['sounds'] = sounds
    for old in ('isentinel_launch.msdf', 'isentinel_blast.msdf'):
        (CONTENT / old).unlink(missing_ok=True)
    disabled = [k for k in index.get('disabled_units', []) if k != KEY]
    if disabled:
        index['disabled_units'] = disabled
    else:
        index.pop('disabled_units', None)
    save_json(CONTENT / DESCRIPTOR, desc)
    save_json(CONTENT / 'units' / 'iron_sentinel.json', first)
    save_json(CONTENT / 'units' / 'iron_sentinel_form2.json', second)
    save_json(CONTENT / 'content.json', index)
    report['unit_ids'] = {KEY: index['unit_ids'][KEY], KEY2: index['unit_ids'][KEY2]}
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
