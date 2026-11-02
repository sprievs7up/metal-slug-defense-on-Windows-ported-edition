"""UNION（MS7 任务 5 首领）按 MSA 7.13.0 原始动作记录移植（2026-11-01；行为 union v1，行为库 32，核心 r118；R5 起行为 v2，行为库 33，核心 r119；R6 起行为 v3，行为库 34，核心 r120；R7 起行为 v4，行为库 35，核心 r121；R8 起行为 v5，行为库 36，核心 r122；R9 起行为 v6，行为库 37，核心 r125；R11 核心 r126；R12 起行为 v7，行为库 38，核心 r127；R13 核心 r128；R14 起行为 v8，行为库 39，核心 r129）。

来源：F:\\egg\\research\\metal_slug_attack\\decoded\\units\\0377（254–257、377–384 共用的动作记录：图集 7boss_A_out.obm（1024×512）、
7boss_B_1_out.obm（512×256）、7boss_C_2_out.obm（512×512），矩形 301、帧 602、脚本 150）。反汇编与解读见
docs/MS7_M5_UNITS_2026-11-01.md 与 verification/ms7_m5_units_20261101/。

- 四个单位共用一个描述符与图集，动作号即 MSA 脚本号（不重排）：合体单位 s1xlv.union（MSA 377，role 0：待机 6、前进 7、分离 10、
  击退 12、损毁 13）、1 号机 s1xlv.union_01（378：53 / 54 / 55 / 57 / 59 / 60→114）、2 号机 s1xlv.union_02（379：69 / 70 / 71 / 72 / 73 /
  113 / 75→117）、3 号机 s1xlv.union_03（380：61 / 62 / 63 / 64 / 65 / 67 / 68→116）。三机为内部单位。
- 脚本转换：MSA 专有指令 24 / 26 / 28（SkillStun、EnableNockBack、SkillAvoid 的 false；只出现在合体单位各动作与三机的硬直、击退、
  损毁动作开头）删除：MSD 的击退（80）期间原生不再击退，合体单位常置 Guard 不受伤。op22 第 2 个值（MSA 为绘制优先级）改为 0
  （MSD 为攻击状态覆盖）。op23 的 MSA 音效号 211–375 与 MSD 原生同号同名（B4_STGUN 等），保留；491（cata2）改为已有的本体音效
  s1xlv.isentinel_walk（同一 MSA 文件、同一音量 35），492（charge3）改为新登记的 s1xlv.union_charge（MSA charge3.msa，音量 90）。
- 战斗槽没有 op19 缩小（原尺寸），不做 × 4/3 换算；菜单槽 1–2 与部件 129–132 保留 MSA 的 op19 70%；编队槽 0 与部件 121–128 改为 40%（见 DECK_SCALE）。
- 数值（Lv40，基准 192：生命 6000、近距 1500、远距 1060、绝招 2400、移速 3.0、生产 550 帧）为 MSA 377–380 首次进化等级 3 的值（暂定，
  用户 2026-11-01：伤害与移速先按 MSA，AP 2000、再出击约 94 秒，价格暂定）。见 PROVISIONAL 与文档第 13 节。
- 头像：MSA unit_icon_02.obme 原格（m_unit_misc.pict 264 → (816,365) 45×40，锚点 [−5, −5]），写在 (594,770)；名称与说明取 MSA 主数据表。
运行：E:\\anaconda3\\python.exe -I artwork/union_20261101/build_union.py [--report]
"""
from pathlib import Path
from fractions import Fraction
from math import gcd
import hashlib
import json
import shutil
import struct
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MSA_UNIT = Path(r'F:\egg\research\metal_slug_attack\decoded\units\0377')
MSA_ASSETS = Path(r'F:\egg\research\metal_slug_attack\apk\assets')
MSA_ICONS = Path(r'F:\egg\research\metal_slug_attack\decoded\unit_icons\unit_icon_02.obme.png')
MSA_TEXTS = REPO / 'verification' / 'ms7_m5_units_20261101' / 'msa_union_texts.json'

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
TEXTURES = tuple(f'union_{i}.obm' for i in range(3))
DESCRIPTOR = 'union_descriptor.json'
BASE = 192
MSA_NOOP = {24, 26, 28}
SOUNDS_MAP = {491: 's1xlv.isentinel_walk', 492: 's1xlv.union_charge'}
NEW_SOUNDS = [('s1xlv.union_charge', 'charge3.msa', 90)]   # (键, MSA 文件, 音量 m_sound_data)
KEYS = ('s1xlv.union', 's1xlv.union_01', 's1xlv.union_02', 's1xlv.union_03')
FILES = ('union.json', 'union_01.json', 'union_02.json', 'union_03.json')
ICON_CELL = (816, 365, 45, 40)
ICON = {'page': 1, 'rect': [594, 770, 45, 40], 'anchor': [-5, -5]}
# 弹体表 [首个脚本, 个数, 种类, 命中]（行为库说明）：142 分离弹体；29 1 号机水平导弹；23 1 号机弹道导弹；103 2 号机能量弹（命中动作 104）；
# 85–91 2 号机绝招扫射；106 3 号机光弹（触地不消失，命中动作 107）；118 3 号机炸弹。命中效果为 MSA 的共用效果编号（0xff00 + n）。
# R8（用户 2026-11-02）：1 号机绝招的平射导弹 29 改为种类 5（水平射出后追踪，MSA 为水平直飞）。
# R11（用户：1 号机导弹爆炸无音效、只有一团灰烟）：29 / 23 的命中效果由 0xff1a（MSD 共用效果 26 为灰色烟雾，无音效）改为 0xff03
# （中爆炸，带原生音效 203；原生 BulletAction_B4Missile、HeavyB 的导弹命中同用 0xff03）。
BULLETS = [142, 1, 4, 0, 29, 1, 5, 0xff03, 23, 1, 3, 0xff03, 103, 1, 2, 104, 85, 7, 3, 0xff0f, 106, 1, 17, 107, 118, 1, 3, 0xff13]
ROLES = {   # 行为 union 的角色与动作号（MSA 各类 update 播放的槽）
    0: dict(neutral_animation=6, move_animation=7, near_animation=10, far_animation=10, special_animation=10, divide_animation=10,
            knockback_animation=12, death_animation=13, death_loop_animation=13),
    1: dict(neutral_animation=53, move_animation=54, near_animation=55, far_animation=55, special_animation=57, divide_animation=55,
            knockback_animation=59, death_animation=60, death_loop_animation=114),
    2: dict(neutral_animation=69, move_animation=70, near_animation=71, far_animation=72, special_animation=73, divide_animation=71,
            knockback_animation=113, death_animation=75, death_loop_animation=117),
    3: dict(neutral_animation=61, move_animation=62, near_animation=63, far_animation=64, special_animation=65, divide_animation=63,
            knockback_animation=67, death_animation=68, death_loop_animation=116),
}
COMMON = dict(first_unit=KEYS[1], second_unit=KEYS[2], third_unit=KEYS[3], bullets=BULLETS)
# 数值：生命与击退门槛见 R2，AP 与出击时间见 R3（用户确认）；伤害 R4 为用户指定（2026-11-01，每发 / 每次命中，Lv40），合体单位的分离弹体未指定、保持 MSA 1089；
# 移速、射程、冷却等为 MSA 377–380 首次进化等级 3 的值（R3 用户确认）。损毁冲撞 = 绝招伤害 × crash（1 号机 1000 × 3、3 号机 600 × 5 = 3000）。
# R6（用户 2026-11-02）：1 号机 40000、2 号机 30000、3 号机 30000，合计 100000；合体单位的生命为三机之和 100000，未分离时受伤 −90%
# （COMBINED_DAMAGE_TAKEN 10，行为参数 combined_damage_taken），分离时三机按合体单位当时的生命比例继承；四者均不击退（no_knockback）。
# 击退门槛倍率按第 6.1 节仍取生命倍率（不击退后不起作用）。R2–R5 为 80000 / 40000 / 10000 / 30000、合体 Guard 不受伤；R1 为 MSA 每台 90750。
# R13（用户 2026-11-02：能达到 2 号机的单位不多，予以削弱）：2 号机 20000，合体单位 = 三机之和 90000，1、3 号机不变。
HP = {0: [15, 1], 1: [20, 3], 2: [10, 3], 3: [5, 1]}   # 6000 × → 90000 / 40000 / 20000 / 30000（R6–R12 为 100000 / 40000 / 30000 / 30000）
COMBINED_DAMAGE_TAKEN = 10
# R13（用户 2026-11-02）：四个单位的移速均减半（合体与 1、3 号机 5.0 → 2.5，2 号机 6.0 → 3.0），前进动作的履带倍率随之；其余不变。
# R7（用户 2026-11-02）：合体单位以与 1、3 号机相同的移速前进（PROVISIONAL[0] 的 move 由 MSA 1.2 改为 5.0，前进动作的履带倍率随之为 5/4）；
# 出场后最多前进 2.6 秒（78 帧，MAX_COMBINED_TICKS）仍未遇敌时自行开始分离；1、3 号机爆炸时核心另放大型爆炸并播放原生音效 253，
# 该音效写在不播放的脚本（SOUND_PRELOAD_SCRIPT）中以随单位预载。
MAX_COMBINED_TICKS = 78
CRASH_BLAST_SOUND = 253
PRODUCTION = [36, 7]      # 550 × 36/7 = 2829 帧（94.3 秒；MSA 生产时间 3600 × 550/700，蜈蚣长老、钢铁死亡蠕虫的换算；R3 用户确认，R1–R2 为 × 0.78 的 2808 帧）
PROVISIONAL = {
    0: dict(move=[5, 6], near=[363, 500], normal=[1089, 1060], special=[363, 800],   # 移速 2.5（R13 减半；R7–R12 为 5.0，同 1、3 号机；MSA 1.2）；三组 1089（分离弹体）
            words={'6': 250, '7': 250, '17': 999, '24': 999, '26': 600, '31': 999, '33': 600, '35': 400, '36': 400},
            floats={'16': 10.0, '23': 3.0, '25': 8.0, '30': 40.0, '32': 12.0}, effect=[320, 144], marker=[9, 7]),
    # R10（用户 2026-11-02）：1 号机冲撞 1200、导弹每发 1600；2 号机近距 / 远距能量弹每发 1200（扫射保持 800）；3 号机光弹每发 1200、
    # 降落伞炸弹每枚 1000（接触保持 900）；损毁冲撞与触地爆炸仍为 3000（绝招组 × crash：1600 × 15/8、800 × 15/4、1000 × 3）。
    1: dict(move=[5, 6], near=[4, 5], normal=[1089, 1060], special=[2, 3], crash=[15, 8],   # 移速 2.5（R13 减半）；R10 冲撞 1200、导弹每发 1600、损毁冲撞 3000（远距不使用）
            words={'6': 10, '7': 0, '17': 999, '24': 999, '31': 999, '33': 600, '35': 200, '36': 200},
            floats={'16': 1.0, '30': 40.0, '32': 12.0}, effect=[160, 90], marker=[5, 5]),
    2: dict(move=[1, 1], near=[4, 5], normal=[60, 53], special=[1, 3], crash=[15, 4],   # 移速 3.0（R13 减半）；R10 近距 / 远距能量弹每发 1200，扫射每发 800；R9 触地爆炸 3000
            words={'6': 40, '7': 500, '17': 999, '19': 600, '24': 999, '26': 600, '27': 90, '31': 999, '33': 600, '34': 30,
                   '35': 300, '36': 300},
            floats={'16': 10.0, '18': 8.0, '23': 3.0, '25': 8.0, '30': 15.0, '32': 6.0}, effect=[0, 0], marker=[6, 6]),
    3: dict(move=[5, 6], near=[3, 5], normal=[60, 53], special=[5, 12], crash=[3, 1],   # 移速 2.5（R13 减半）；接触 900，R10 光弹每发 1200、炸弹每枚 1000、损毁冲撞 3000
            words={'6': 30, '7': 500, '17': 999, '24': 999, '26': 600, '27': 60, '31': 999, '33': 600, '34': 20,
                   '35': 400, '36': 400},
            floats={'16': 1.0, '23': 3.0, '25': 8.0, '30': 30.0}, effect=[210, 94], marker=[6, 5]),
}
AP, PRICE = 999, 350   # R3 用户确认：AP 999（首领先例，MSA 377 为 2000）、价格 350 勋章（同 Fall Climber）
# R5（用户 2026-11-01：分离动作“极为鬼畜”，认为播放过快）：分离动作 10 及其挂载的子层、效果与分离弹体（脚本 31–33、142–149）按
# DIVIDE_SLOW 倍时长重采样为副本（1 为 MSA 原速，不生成副本）；分离帧 split_tick 随之为 DIVIDE_SLOW × (SPLIT + 1) − 1。
# R6（用户 2026-11-02：sprite 像在原地打滑）：前进动作的履带（合体与 3 号机子层 35 / 36、1 号机帧 0–6）每帧 1 tick、4 帧一周，履带齿每帧
# 后移 2 精灵像素，即原速时履带表面相对机体每 tick 4 世界单位（TREAD_SPEED）；合体单位移速 1.2 时履带快 3.3 倍，1、3 号机 5.0 时慢 0.8 倍。
# 前进动作（及其子层）按 移速 / TREAD_SPEED 的倍率重新定时为副本（retime_script），履带与位移一致；移速改动后重新生成即随之。
# 2 号机为飞行（无履带）不改。MOVE_ANIM_RATE 可为某角色指定倍率（Fraction）代替自动值。
# R9（用户 2026-11-02）：
# - 2 号机为空中单位：untargetable 1（MSA 非 BOSS 版 255 / 379 与原生空中单位 SLUG FLYER、R-SHOBU、直升机同置 NoTarget、DontToche；
#   原生 getNearEnemyDistance 不以其为攻击目标，只有攻击框碰到其受击框的攻击使其受伤）。
# - 2 号机的能量弹（103、104）与发射时的聚能粒子（107–114）改为 3 号机同形状的红橙色版：描述符帧中的矩形 106–129 换为 82–105
#   （ORB_RECOLOR；125 与 101 高差 1 像素，其余逐像素同形；图集不变）。
# - 2 号机损毁：机体下缘（死亡动作各层帧的下缘 × 精灵缩放 2，TOUCHDOWN）触地即爆炸，播放触地爆炸动作（攻击框 CRASH_BLAST_BOX），
#   伤害按损毁冲撞：绝招 800 × 15/4 = 3000（用户指定）。
# - 3 号机空投炸弹改用原生派斯戰車（UnitID 263 PARACHUTE TRUCK，BattleAction_M3_RocketVan）的降落伞炸弹：原生图集 PARA_TEXTURE 的矩形 28–32、
#   脚本 16（下落：op7 [0, 200]、攻击框 1、每 3 tick 换帧的摆动循环）与 17（爆炸：攻击框 2、音效 202、10 tick 不绘制），命中或落地时同原生
#   在下方 40 放共用效果 0xff16（BulletAction_M3_RocketVan 状态 60）。数值取自 libAppMain.so 1.46.0 的 263 精灵描述符。
ORB_RECOLOR = {r: r - 24 for r in range(106, 130)}
PARA_TEXTURE = 'M-3_Rocket_Van_out.obm'
PARA_RECTS = [[389, 506, 40, 58, 20, 29], [896, 0, 41, 58, 22, 29], [429, 506, 40, 58, 22, 29], [937, 0, 40, 58, 19, 29], [389, 564, 40, 58, 19, 29]]
PARA_FALL_ORDER = [0, 1, 2, 2, 1, 0, 3, 4, 4, 3]   # 原生脚本 16：F56 F58 F60 F60 F58 F56 F62 F64 F64 F62，各 3 tick
PARA_BOXES = [[-17, -3, 35, 25, 7], [-23, -25, 47, 35, 7]]   # 原生攻击框 1（下落）、2（爆炸）
PARA_BLAST_SOUND, PARA_HIT_EFFECT = 202, 0x16
CRASH_BLAST_BOX = [-80, -32, 160, 100, 7]   # 2 号机触地爆炸（精灵像素，原点在触地点上方 TOUCHDOWN 处）：横向 ±160、触地点上方 180 至下方 20（世界单位）
CRASH_BLAST_TICKS = 6
DIVIDE_SLOW, SPLIT = 2, 39
BASE_SPEED, TREAD_SPEED = Fraction(3), Fraction(4)   # 基准 192 的移速 3.0；履带原速
TRACKED = {0, 1, 3}
MOVE_ANIM_RATE = {}
# R11（用户：MSA 素材抖动太严重，待机与前进的播放速度减慢 33%，攻击、绝招等不变）：四个单位的待机动作及其子层按 IDLE_MOVE_RATE 重新定时为
# 副本（脚本号接在最后）；前进动作在履带倍率之上再乘此倍率（移速不变，履带因此慢于地面，用户选定）。
IDLE_MOVE_RATE = Fraction(2, 3)
# R14（用户 2026-11-02：分离动作不在平地时 1 号机卡进地面、生成时瞬移；2 号机闪现）：
# - 分离动作中 1 号机由分离弹体（MSA 142 → split_bullet）与效果 143–145（GROUND_FOLLOW，op12，各带水平 op7）移出；核心 r129 让它们随地形升降
#   （行为参数 ground_follow_first / ground_follow_count），1 号机在该高度生成。
# - 2 号机近距攻击后升到 rise_top 再移到本方据点上空：MSA 为机体高度一半（−84），MSD 中 2 号机的原点在机体上部，下缘仍在画面内（世界 y 78），
#   改为待机动作各帧下缘的最大值（精灵像素 × 2）之上 RISE_MARGIN，使整机移出画面（世界 y < 0）后再移动。
GROUND_FOLLOW = (143, 3)
RISE_MARGIN = 8


# 编队页（原生 CreateDeckObject 以动作 0 原尺寸绘制）：MSA 编队槽 0 与其部件 121–128 为 70%（op19 [70, 70]，子层偏移已按 70% 换算）；
# 按本项目大型单位的惯例（大杰 50%、IRON SLIDER 与侵略者之王 40%）改为 DECK_SCALE，op19 与 op11 / op14 偏移按 DECK_SCALE / 70 换算。
DECK_SCALE, DECK_SLOTS = 40, {0} | set(range(121, 129))


def transform(record):
    stats = {'removed_msa_noop': {}, 'op22_priority_zeroed': 0, 'sounds': {}, 'deck_rescaled': 0}
    animations = {}
    for slot in range(record['script_count']):
        out = []
        for c in record['scripts'][slot]:
            op, v = c[0], list(c[1:])
            if slot in DECK_SLOTS:
                if op == 19:
                    assert v == [70, 70], (slot, v)
                    v = [DECK_SCALE, DECK_SCALE]
                    stats['deck_rescaled'] += 1
                elif op == 11:
                    v = [v[0], v[1], round(v[2] * DECK_SCALE / 70), round(v[3] * DECK_SCALE / 70)]
                elif op == 14:
                    v = [round(v[0] * DECK_SCALE / 70), round(v[1] * DECK_SCALE / 70)]
            if op in MSA_NOOP:
                stats['removed_msa_noop'][str(op)] = stats['removed_msa_noop'].get(str(op), 0) + 1
                continue
            if op == 22 and v[1] != 0:
                v[1] = 0
                stats['op22_priority_zeroed'] += 1
            if op == 23:
                stats['sounds'][str(v[0])] = stats['sounds'].get(str(v[0]), 0) + 1
                v = [SOUNDS_MAP.get(v[0], v[0])]
            assert op <= 23, (slot, c)
            out.append({'opcode': op, 'values': v})
        animations[str(slot)] = out
    return animations, stats


def closure(animations, root):
    """root 及其经 op11（子层）、op12（效果）、op22（弹体）递归引用的脚本。"""
    seen, todo = [], [root]
    while todo:
        k = todo.pop()
        if k in seen:
            continue
        seen.append(k)
        todo += [c['values'][0] for c in animations[str(k)] if c['opcode'] in (11, 12, 22)]
    return sorted(seen)


def slow_script(ops, n, remap):
    """按 n 倍时长重采样一个脚本：op1 等待 × n；op11 / op12 / op22 的脚本号换为 remap 中的副本。
    含 op7（运动：[vx, vy, ax, ay]，1/100 精灵像素；每 tick 先按速度提交位置再加加速度；op16 按停止运动）的脚本逐 tick 展开：先按原脚本模拟各整数 tick 的位置，
    新第 k tick 重新下达 op7 [v, 0, 0]，v 为原轨迹在 (k + 1) / n 与 k / n 处（线性插值、取整）的位置差，使对象沿原路径以 1/n 的速度移动。"""
    def mapped(c):
        v = list(c['values'])
        if c['opcode'] in (11, 12, 22):
            v[0] = remap.get(v[0], v[0])
        return {'opcode': c['opcode'], 'values': v}
    if not any(c['opcode'] == 7 for c in ops):
        return [mapped(c) if c['opcode'] != 1 else {'opcode': 1, 'values': [c['values'][0] * n]} for c in ops]
    # 分 tick：ticks[j] = 第 j tick 开头执行的指令（op1 之外），lengths[j] = 该组的 tick 数；tail 为结尾的 op21 / op5
    groups, cur, tail = [], [], []
    for c in ops:
        if c['opcode'] == 1:
            groups.append((cur, c['values'][0]))
            cur = []
        elif c['opcode'] in (5, 21):
            tail = [c]
        else:
            cur.append(c)
    assert not tail or tail[0]['opcode'] == 21, 'looping script with motion'
    ticks = []
    for g, w in groups:
        ticks.append(g)
        ticks += [[] for _ in range(w - 1)]
    ticks.append(cur)   # 结尾 op21 之前的指令（如有）
    # 原轨迹（整数 tick 的位置，op7 单位）
    pos, v, a = [(0.0, 0.0)], [0.0, 0.0], [0.0, 0.0]
    for g in ticks[:-1]:
        for c in g:
            if c['opcode'] == 7:
                v, a = [float(c['values'][0]), float(c['values'][1])], [float(c['values'][2]), float(c['values'][3])]
            elif c['opcode'] == 16:   # 按停止运动处理（效果 146–148 结束前的最后 1 tick）
                v, a = [0.0, 0.0], [0.0, 0.0]
        x, y = pos[-1]
        pos.append((x + v[0], y + v[1]))
        v = [v[0] + a[0], v[1] + a[1]]

    def at(t):
        j = min(int(t), len(pos) - 2)
        f = t - j
        return tuple(round(pos[j][i] + (pos[j + 1][i] - pos[j][i]) * f) for i in range(2))
    started = next(j for j, g in enumerate(ticks) if any(c['opcode'] == 7 for c in g))
    out, last_v = [], None
    for k in range(n * (len(ticks) - 1)):
        if k % n == 0:
            out += [mapped(c) for c in ticks[k // n] if c['opcode'] != 7]
        if k >= n * started:
            p0, p1 = at(k / n), at((k + 1) / n)
            vel = [p1[0] - p0[0], p1[1] - p0[1]]
            if vel != last_v:
                out.append({'opcode': 7, 'values': vel + [0, 0]})
                last_v = vel
        out.append({'opcode': 1, 'values': [1]})
    out += [mapped(c) for c in ticks[-1]] + tail
    # 合并相邻且之间无其他指令的 op1
    merged = []
    for c in out:
        if c['opcode'] == 1 and merged and merged[-1]['opcode'] == 1:
            merged[-1] = {'opcode': 1, 'values': [merged[-1]['values'][0] + c['values'][0]]}
        else:
            merged.append(c)
    return merged


def slowed_copies(animations, roots, n, next_id):
    """roots 各自的引用闭包按 n 倍时长生成副本（脚本号自 next_id 起），返回 {原脚本号: 副本号} 与下一个可用脚本号。"""
    if n == 1:
        return {}, next_id
    keys = sorted({k for r in roots for k in closure(animations, r)})
    remap = {k: next_id + i for i, k in enumerate(keys)}
    for k in keys:
        animations[str(remap[k])] = slow_script(animations[str(k)], n, remap)
    return remap, next_id + len(keys)


def retime_script(ops, r, remap):
    """按倍率 r（Fraction，原 tick / 新 tick；小于 1 放慢、大于 1 加快）重新定时一个循环脚本（以 op5 结尾、不含 op7）。
    新第 k tick 显示原第 floor(k × r) tick（跨周期时展开 n 周，使新周期 L = n × P / r 为整数），其间被越过的原 tick 的指令依次执行；
    展开后的第 2 周起不再执行挂载指令 op11 / op12 / op22（子层同倍率循环，原脚本每周重新挂载时子层恰在周期起点，两者等价）。"""
    assert ops[-1]['opcode'] == 5 and not any(c['opcode'] in (5, 7, 21) for c in ops[:-1]), 'retime_script: loop without op7 expected'
    ticks, cur = [], []
    for c in ops[:-1]:
        if c['opcode'] == 1:
            ticks.append(cur)
            ticks += [[] for _ in range(c['values'][0] - 1)]
            cur = []
        else:
            cur.append(c)
    assert not cur, 'retime_script: ops after the last op1'
    period = len(ticks)
    n = r.numerator // gcd(period * r.denominator, r.numerator)
    length = n * period * r.denominator // r.numerator
    out, done = [], -1
    for k in range(length):
        upto = (k * r.numerator) // r.denominator
        for u in range(done + 1, upto + 1):
            for c in ticks[u % period]:
                if c['opcode'] in (11, 12, 22):
                    if u >= period:
                        continue
                    c = {'opcode': c['opcode'], 'values': [remap.get(c['values'][0], c['values'][0])] + list(c['values'][1:])}
                out.append(c)
        done = max(done, upto)
        if out and out[-1]['opcode'] == 1:
            out[-1] = {'opcode': 1, 'values': [out[-1]['values'][0] + 1]}
        else:
            out.append({'opcode': 1, 'values': [1]})
    return out + [ops[-1]]


def retimed_copies(animations, roots, r, next_id):
    """roots 各自的引用闭包按倍率 r 重新定时为副本（脚本号自 next_id 起），返回 {原脚本号: 副本号} 与下一个可用脚本号。"""
    if r == 1:
        return {}, next_id
    keys = sorted({k for root in roots for k in closure(animations, root)})
    remap = {k: next_id + i for i, k in enumerate(keys)}
    for k in keys:
        animations[str(remap[k])] = retime_script(animations[str(k)], r, remap)
    return remap, next_id + len(keys)


def front_width(animations, desc, slot):
    """原生 setObjectSize 的单位宽度（精灵像素）：脚本中首个 op3 的受击框 x + 宽（朝向 90 的前缘；朝向 270 镜像后同为前缘）。"""
    idx = next(c['values'][0] for c in animations[str(slot)] if c['opcode'] == 3)
    x, _, w, _, _ = desc['hit_bounds'][idx]
    return x + w


def frame_blocks(frames):
    """描述符帧表的各帧起点（[个数, 矩形…] 首尾相接）。"""
    pos, starts = 0, []
    while pos < len(frames):
        starts.append(pos)
        pos += frames[pos] + 1
    assert pos == len(frames)
    return starts


def script_frames(animations, roots):
    """roots 的引用闭包中 op0 显示的帧起点。"""
    keys = {k for r in roots for k in closure(animations, r)}
    return {c['values'][0] for k in keys for c in animations[str(k)] if c['opcode'] == 0 and c['values'][0] >= 0}


def recolor_orbs(animations, desc, other_roots):
    """R9：帧中的矩形按 ORB_RECOLOR 换为 3 号机的红橙色版；含这些矩形的帧不得被其他单位的动作引用（other_roots 的闭包）。"""
    frames, changed = desc['frames'], []
    other = script_frames(animations, other_roots)
    for pos in frame_blocks(frames):
        rs = frames[pos + 1:pos + 1 + frames[pos]]
        if any(r in ORB_RECOLOR for r in rs):
            assert pos not in other, pos
            frames[pos + 1:pos + 1 + frames[pos]] = [ORB_RECOLOR.get(r, r) for r in rs]
            changed.append(pos)
    return changed


def sprite_bottom(animations, desc, slot):
    """脚本首帧及其 op11 子层（含偏移）各矩形下缘的最大值（精灵像素，相对原点）。"""
    def bottom(s, oy, depth):
        ops = animations[str(s)]
        first = next((c['values'][0] for c in ops if c['opcode'] == 0), -1)
        out = [oy - desc['rects'][r][5] + desc['rects'][r][3] for r in desc['frames'][first + 1:first + 1 + desc['frames'][first]]] if first >= 0 else []
        for c in ops:
            if c['opcode'] == 11 and depth < 3:
                out += bottom(c['values'][0], oy + c['values'][3], depth + 1)
        return out
    return max(bottom(slot, 0, 0))


def sprite_bottom_all(animations, desc, slot):
    """R14：脚本及其 op11 子层（含偏移；子层的 op14 位置另计）全部帧各矩形下缘的最大值（精灵像素，相对原点）。"""
    def frame_bottom(pos):
        n = desc['frames'][pos] if pos >= 0 else 0
        return max(desc['rects'][r][3] - desc['rects'][r][5] for r in desc['frames'][pos + 1:pos + 1 + n]) if n else None
    def bottom(s, oy, depth):
        ops = animations[str(s)]
        ys = {oy} | {c['values'][1] for c in ops if c['opcode'] == 14}
        out = []
        for c in ops:
            b = frame_bottom(c['values'][0]) if c['opcode'] == 0 else None
            if b is not None:
                out += [y + b for y in ys]
            if c['opcode'] == 11 and depth < 4:
                out += bottom(c['values'][0], oy + c['values'][3], depth + 1)
        return out
    return max(bottom(slot, 0, 0))


def add_parachute_bomb(animations, desc, next_id):
    """R9：原生派斯戰車的降落伞炸弹（矩形、帧、攻击框、下落与爆炸脚本）接在描述符之后，图集页为 PARA_TEXTURE（第 len(TEXTURES) 页）。"""
    page = len(TEXTURES)
    first_rect = len(desc['rects'])
    desc['rects'] += [r + [0, page] for r in PARA_RECTS]
    starts = []
    for i in range(len(PARA_RECTS)):
        starts.append(len(desc['frames']))
        desc['frames'] += [1, first_rect + i]
    fall_box, blast_box = len(desc['attack_bounds']), len(desc['attack_bounds']) + 1
    desc['attack_bounds'] += [list(b) for b in PARA_BOXES]
    fall = [{'opcode': 7, 'values': [0, 200, 0, 0]}, {'opcode': 4, 'values': [fall_box]}]
    for i in PARA_FALL_ORDER:
        fall += [{'opcode': 0, 'values': [starts[i]]}, {'opcode': 1, 'values': [3]}]
    fall.append({'opcode': 5, 'values': []})
    blast = [{'opcode': 4, 'values': [blast_box]}, {'opcode': 23, 'values': [PARA_BLAST_SOUND]}, {'opcode': 0, 'values': [-1]},
             {'opcode': 1, 'values': [10]}, {'opcode': 21, 'values': []}]
    animations[str(next_id)], animations[str(next_id + 1)] = fall, blast
    return next_id, next_id + 1, next_id + 2


def descriptor(record):
    assert 0xffffffff not in record['frames']
    return {'rects': [list(r) for r in record['rects']], 'frames': list(record['frames']),
            'script_count': record['script_count'], 'hit_bounds': record['hit_bounds'],
            'attack_bounds': record['attack_bounds']}


# 说明第 2、3 行（用户 2026-11-03：“由埋伏在废品岛的莫丁军研发的武器。显然这项技术并非来自现代。”）；第 1 行（攻击名）照 MSA 377。
# 中文为用户原文；其余语言第 2 行沿用 MSA 译文、第 3 行为代理翻译（德语 MSA 原文缺第 3 行，第 2 行一并改写），待校对。
DESCRIPTION = {
    'ZS': '由埋伏在废品岛的莫丁军研发的武器。\n显然这项技术并非来自现代。',
    'ZT': '由埋伏在廢鐵島的莫丁軍研發的武器。\n顯然這項技術並非來自現代。',
    'EN': 'A weapon built in secret on Scrap Island by the Morden Army. \nClearly, this technology is not of this era.',
    'JP': 'スクラップ島に潜伏したモーデン軍により作られた兵器。\nこの技術は明らかに現代のものではない。',
    'KR': '고철섬에 잠복한 모덴군이 만든 병기.\n이 기술은 분명 현대의 것이 아니다.',
    'ES': 'Arma construida en secreto por el ejército de Morden en la Isla Chatarra. \nEs evidente que esta tecnología no es de esta época.',
    'PT': 'Uma arma construída em segredo na Ilha Scrap pelo Exército de Morden. \nClaramente, esta tecnologia não é da era atual.',
    'FR': "Une arme développée en secret sur l'île de la Casse par l'armée de Morden. \nDe toute évidence, cette technologie n'est pas de notre époque.",
    'DE': 'Eine Waffe der Morden-Armee, im Geheimen auf der Schrottinsel gebaut.\nDiese Technologie stammt offensichtlich nicht aus der Gegenwart.',
    'IT': "Arma costruita in segreto sull'Isola dei Rottami dall'Armata di Morden. \nChiaramente questa tecnologia non appartiene al presente.",
    'RU': 'Оружие, созданное морденовской армией на Мусорном острове. \nОчевидно, эта технология не из нашего времени.',
}


def localization():
    texts = json.loads(MSA_TEXTS.read_text(encoding='utf-8'))['377']
    return {lang: {'name': t['name'].strip(), 'description': t['description'].split('\n')[0] + '\n' + DESCRIPTION[lang]}
            for lang, t in texts.items()}


def unit_file(role, animations, params):
    p = PROVISIONAL[role]
    unit = {'key': KEYS[role], 'base_id': BASE, 'faction': 1, 'identity': 'Rebel Army',
            'shop_price': PRICE, 'available_from_start': True, 'ap': AP,
            'hp_multiplier': HP[role], 'knockback_threshold_multiplier': HP[role],
            'damage_multiplier': [1, 1], 'near_damage_multiplier': p['near'], 'normal_damage_multiplier': p['normal'],
            'special_damage_multiplier': p['special'], 'attack_wait_multiplier': [1, 1], 'attack_range_multiplier': [1, 1],
            'knockback_distance_multiplier': [1, 1], 'ballistic_range_multiplier': [1, 1], 'move_speed_multiplier': p['move'],
            'production_reference_id': BASE, 'production_interval_multiplier': PRODUCTION,
            'status_word_values': p['words'], 'status_float_values': p['floats'],
            # 绘制优先级：R11 起 −90（用户：巨型单位画在最下层，同钢铁哨兵；R1–R10 为 −80）
            'image_direction': 90, 'draw_priority': -90, 'minimap_marker': p['marker'], 'special_effect_size': p['effect'],
            'icon': ICON, 'textures': list(TEXTURES) + [PARA_TEXTURE], 'sprite_descriptor': DESCRIPTOR, 'animations': animations,
            'localization': localization(), 'tags': ['ms7', 'msa'],
            'behaviors': [{'name': 'union', 'version': 8, 'params': dict(role=role, **params,
                                                                          **({'crash_damage': p['crash']} if 'crash' in p else {}))},
                          {'name': 'no_knockback', 'version': 1, 'params': {}}]}
    if role:
        unit['internal_only'] = True
    return unit


def write_icon(cell):
    raw = bytearray((CONTENT / 'unit_icon_02.obm').read_bytes())
    assert raw[:4] == b'OI\x01\x20'
    w, h = struct.unpack_from('<HH', raw, 4)
    ax, ay, iw, ih = ICON['rect']
    assert ax + iw <= w and ay + ih <= h
    for other in CONTENT.glob('units/*.json'):
        unit = json.loads(other.read_text(encoding='utf-8'))
        icon = unit['icon']
        if unit['key'] in KEYS or 'atlas' in icon or icon['page'] != 1:
            continue
        x, y, ow, oh = icon['rect']
        assert x + ow <= ax or x >= ax + iw or y + oh <= ay or y >= ay + ih, unit['key']
    for j in range(ih):
        for i in range(iw):
            at = 8 + ((ay + j) * w + ax + i) * 4
            raw[at:at + 4] = bytes(cell.getpixel((i, j)))
    return bytes(raw)


def main():
    OUT.mkdir(exist_ok=True)
    (HERE / 'source').mkdir(exist_ok=True)
    record = json.loads((MSA_UNIT / 'record.json').read_text(encoding='utf-8'))
    assert record['names'] == ['7boss_A_out.obm', '7boss_B_1_out.obm', '7boss_C_2_out.obm'] and record['script_count'] == 150
    atlases = [Image.open(MSA_UNIT / (n + '.png')).convert('RGBA') for n in record['names']]
    animations, stats = transform(record)
    desc = descriptor(record)
    # R5：分离动作与前进动作的重采样副本（新脚本号接在 MSA 的 150 个之后）；三机的单位宽度取各自待机脚本的受击框前缘
    div, next_id = slowed_copies(animations, [10], DIVIDE_SLOW, record['script_count'])
    moves, rates = {}, {}
    for role in range(4):
        speed = BASE_SPEED * Fraction(*PROVISIONAL[role]['move'])
        rates[role] = MOVE_ANIM_RATE.get(role, speed / TREAD_SPEED if role in TRACKED else Fraction(1)) * IDLE_MOVE_RATE
        moves[role] = {}
        if role in TRACKED:   # 2 号机（飞行、无履带）R11 起才放慢，其副本接在最后，既有脚本号不变
            moves[role], next_id = retimed_copies(animations, [ROLES[role]['move_animation']], rates[role], next_id)
    animations[str(next_id)] = [{'opcode': 23, 'values': [CRASH_BLAST_SOUND]}, {'opcode': 1, 'values': [1]}, {'opcode': 21, 'values': []}]
    stats['sound_preload_script'] = next_id   # 不播放，只供原生开战预载登记音效
    next_id += 1
    # R9：2 号机红橙色能量弹（2 号机各动作与其弹体 103 / 104、85–91 之外的脚本不得引用改色的帧）
    machine2 = {k for r in [ROLES[2][k] for k in ROLES[2]] + [103, 104] + list(range(85, 92)) for k in closure(animations, r)}
    stats['orb_recolored_frames'] = recolor_orbs(animations, desc, [int(k) for k in animations if int(k) not in machine2])
    para_fall, para_blast, next_id = add_parachute_bomb(animations, desc, next_id)
    touchdown = 2 * sprite_bottom(animations, desc, ROLES[2]['death_animation'])   # 精灵缩放 2
    crash_box = len(desc['attack_bounds'])
    desc['attack_bounds'].append(list(CRASH_BLAST_BOX))
    crash_blast = next_id
    animations[str(crash_blast)] = [{'opcode': 4, 'values': [crash_box]}, {'opcode': 0, 'values': [-1]}, {'opcode': 1, 'values': [CRASH_BLAST_TICKS]},
                                    {'opcode': 4, 'values': [0]}, {'opcode': 0, 'values': [-1]}, {'opcode': 1, 'values': [1]}, {'opcode': 21, 'values': []}]
    next_id += 1
    stats['r9'] = {'parachute_fall': para_fall, 'parachute_blast': para_blast, 'touchdown_offset': touchdown, 'crash_animation': crash_blast,
                   'crash_box': crash_box}
    for role in range(4):
        if role not in TRACKED:
            moves[role], next_id = retimed_copies(animations, [ROLES[role]['move_animation']], rates[role], next_id)
    idles = {}
    for role in range(4):   # R11：待机放慢（副本接在最后，既有脚本号不变）
        idles[role], next_id = retimed_copies(animations, [ROLES[role]['neutral_animation']], IDLE_MOVE_RATE, next_id)
    stats['r11_idle'] = idles
    # R12：隐去的合体单位改播的空白动作（原生绘制不看 Invisible，原先停在分离动作最后一帧，显示 3 号机车身）
    hidden = next_id
    animations[str(hidden)] = [{'opcode': 0, 'values': [-1]}, {'opcode': 1, 'values': [1]}, {'opcode': 5, 'values': []}]
    next_id += 1
    stats['r12_hidden'] = hidden
    desc['script_count'] = next_id
    params = {}
    for role in range(4):
        q = dict(ROLES[role], **COMMON)
        q['move_animation'] = moves[role].get(q['move_animation'], q['move_animation'])
        q['neutral_animation'] = idles[role].get(q['neutral_animation'], q['neutral_animation'])
        q['bullets'] = [div.get(v, v) if i % 4 == 0 else v for i, v in enumerate(BULLETS)]
        at = next(i for i in range(0, len(BULLETS), 4) if BULLETS[i] == 118)   # R9：3 号机炸弹改为派斯戰車的降落伞炸弹
        q['bullets'][at:at + 4] = [para_fall, 1, 3, para_blast | PARA_HIT_EFFECT << 16]
        if role == 2:
            q.update(untargetable=1, touchdown_offset=touchdown, crash_animation=crash_blast)
            q['rise_top'] = -(2 * sprite_bottom_all(animations, desc, q['neutral_animation']) + RISE_MARGIN)   # R14：81 × 2 + 8
        if role == 3:
            q['bomb_bullet'] = para_fall
        if role == 0:
            for k in ('near_animation', 'far_animation', 'special_animation', 'divide_animation'):
                q[k] = div.get(q[k], q[k])
            q['hidden_animation'] = hidden
            q.update(ground_follow_first=div.get(GROUND_FOLLOW[0], GROUND_FOLLOW[0]), ground_follow_count=GROUND_FOLLOW[1])   # R14
            assert [div.get(GROUND_FOLLOW[0] + i) for i in range(GROUND_FOLLOW[1])] == list(range(q['ground_follow_first'], q['ground_follow_first'] + GROUND_FOLLOW[1]))
            q.update(split_tick=DIVIDE_SLOW * (SPLIT + 1) - 1, split_bullet=div.get(142, 142), combined_damage_taken=COMBINED_DAMAGE_TAKEN,
                     max_combined_ticks=MAX_COMBINED_TICKS)
        else:
            q['object_width'] = front_width(animations, desc, q['neutral_animation'])
        params[role] = q
    stats['slowed'] = {'divide': div, 'move': moves, 'move_rate': {r: str(v) for r, v in rates.items()}, 'script_count': next_id}
    stats['object_width'] = {r: params[r].get('object_width', 0) for r in range(4)}
    units = [unit_file(role, animations, params[role]) for role in range(4)]
    x, y, iw, ih = ICON_CELL
    cell = Image.open(MSA_ICONS).convert('RGBA').crop((x, y, x + iw, y + ih))
    cell.save(HERE / 'source' / f'msa_icon_union_{x}_{y}.png')
    report = {'stats': stats, 'colors': [len(set(a.getdata())) for a in atlases], 'provisional': {str(k): v for k, v in PROVISIONAL.items()}}
    if '--report' in sys.argv:
        print(json.dumps(report, ensure_ascii=False))
        return
    obms = [indexed_obm(a) for a in atlases]
    report['obm_bytes'] = [len(o) for o in obms]
    index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
    for key in KEYS:   # 稳定键只追加
        if key not in index['unit_ids']:
            index['unit_ids'][key] = max(index['unit_ids'].values()) + 1
    for name, raw in zip(TEXTURES, obms):
        (CONTENT / name).write_bytes(raw)
        index['assets'][name] = hashlib.blake2b(raw, digest_size=32).hexdigest()
    sounds = list(index.get('sounds', []))
    for key, source, volume in NEW_SOUNDS:
        target = key.split('.', 1)[1] + '.msdf'
        if not (CONTENT / target).exists():
            shutil.copyfile(MSA_ASSETS / source, CONTENT / target)
        entry = {'key': key, 'file': target, 'type': 'se', 'volume': volume}
        at = next((i for i, e in enumerate(sounds) if e['key'] == key), None)
        if at is None:
            sounds.append(entry)
        else:
            sounds[at] = entry
    assert any(e['key'] == 's1xlv.isentinel_walk' and e.get('volume') == 35 for e in sounds)
    index['sounds'] = sounds
    (CONTENT / 'unit_icon_02.obm').write_bytes(write_icon(cell))   # 该资源的摘要在 content.json 中为 null，保持不变
    save_json(CONTENT / DESCRIPTOR, desc)
    for name, unit in zip(FILES, units):
        save_json(CONTENT / 'units' / name, unit)
    save_json(CONTENT / 'content.json', index)
    report['unit_ids'] = {k: index['unit_ids'][k] for k in KEYS}
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
