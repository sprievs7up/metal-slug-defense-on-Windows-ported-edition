"""钢铁死亡蠕虫（IRON DEATH WORM）按 MSA 7.13.0 原始动作记录移植（2026-10-25；行为 iron_death_worm v2，核心 r92；R3 核心 r94；R4 行为 v3、核心 r95；R5 行为 v4、核心 r96）。

来源：F:\\egg\\research\\metal_slug_attack\\decoded\\units\\1843（匿名命名空间 BattleAction_IronDeathWarm，虚表 0x4a742f0；图集
70003IronDeathWarm01_out.obm 1024×1024、70003IronDeathWarm_EF_out.obm 1024×512，矩形 266、脚本 107）。反汇编与核查见
docs/ms7/MS7_AA_TURRETS_IRON_DEATH_WORM_CHECK_2026-10-24.md 与 verification/iron_death_worm_20261025/。图像取 MSA 图集原样
（MS7 素材表为同一像素画，未采用）。
- 原生动作类：MSD 原版侵略者 192（BattleAction_Alien）。其 update 对本单位整体由行为 iron_death_worm 按 MSA update 中各状态实际播放的
  动作执行，动作号即 MSA 脚本号（不重排）：待机 6、移动钻入 7、钻出 12、近距掘削 17、绝招 / 损毁钻入 25、地下钻击 33、
  损毁后横穿 44、爆炸 49；MSA 状态 80（技能硬直）的 43 在 MSD 中无对应状态，保留在描述符中。R2 起按 MSA 底层代码逐条核对
  （verification/iron_death_worm_20261025/msa_r2/FINDINGS_R2.md）。
- 脚本转换：
  * MSA 专有指令 24–35、47–58 为 BattleSprite::EventCallback 回调（MSD runScript 不识别，自脚本中删除），其作用由核心按动作实现：
    全部动作的 op26 EnableNockBack(false)（MSA 状态 70 = 击退不可进入）→ 本单位不击退；17 的 op35 / op34 EveryTimeAtk（攻击框
    存在期间每 tick 重置攻击 ID）→ 掘削中每 tick 以 BattleUnit::refreshAttackStatus 换新攻击 ID；op54 / op56（攻击结算组 30 / 50）→ 掘削 30、绝招钻入与
    钻击 50；op24 / op28（技能眩晕 / 技能回避）与 op30（禁止进入 MSA 状态 80 技能硬直）在 MSD 中无对应。
  * op36（只在第一遍挂子层，AnimationStatus +0x50 为 0 时）改为 op11。MSA 与 MSD 的 getAnimationStatus 取得已有子层时都把子层
    重置到脚本开头，MSD op11 每遍执行；父层在挂载之后只有等待与循环时（待机 6、43、横穿 44、编队 0 / 1），把循环前的等待改为
    HOLD tick，父层不回到挂载处，部件连续播放（同 MSA）。
  * op45（MSA onEventMoveSpeedAnimation：下一位置 = 当前 + v，速度 = v + a）：MSD op7（= MSA op7，速度 = v，第二 tick 重复 v）
    不能单独表示；加速度不为 0 时改为每 tick 一条 op7（第 k tick 取 v + k·a），位移序列 v, v + a, v + 2a, … 与 MSA 相同。
  * op42（子层偏移累加）改为 op14（设定偏移）：值为挂载该子层的 op11 偏移加此前 op42 增量的累计（各脚本只有一种挂载偏移，逐一断言；
    含 op42 的脚本均无循环）。
  * 编队页：原生 CreateDeckObject 以动作 0 原尺寸绘制且不按地面裁切；动作 0 改为空根层挂各部件的缩放副本（MENU_SCALE %，追加脚本
    108 起，挂载偏移同比缩放；同侵略者之王）；编队页不按地面裁切，几乎全在地下的末节 69 不挂。单位菜单的动作演示的待机用战斗
    待机 6（按地面裁切）。
  * 损毁碎块 50 / 52 / 54（MSA createObject 0x32 / 0x34 / 0x36 建立 EffectAction_DeadBody，下落中 y ≥ 地形高度 − 当前帧第一个
    矩形高 / 2 时改播 51 / 53 / 55 并清除移动，播完移除）：由核心在运行时按地形判定（字 113–114），脚本保持 MSA。
  * EffectAction_DeadBody::createObject 0x5c：55 中建立的火焰 92 以默认效果播放，播完接 93（MSA 0x10e1edc，setAnimationID 清除移动）；
    MSD 中把 93 接在 92 之后（op16 清除移动）。
  * op23 的 MSA 音效 2715 / 2716 改为本体音效键（MSA 原文件 irondw_atk / irondw_move 复制为 .msdf，音量取 m_sound_data）；
    200、203、225、425、808 为 MSD 同号同文件的原版音效，保持数字。
- 受击框（用户 2026-10-25：按地面以上的可见部分分段设框；地下钻击给钻头设框，不采用 MSA 钻击中的不可接触 / 不可选为目标 / 穿过
  标记；R3 用户：身体在地下时不应被打到，同蜈蚣长老的地下前行）：按 MSD 语义逐 tick 模拟转换后的脚本（子层偏移、op7 速度、op14、op19 缩放、op2 旋转、矩形翻转），取优先级
  低于 6 的层（MSA draw 只对这些层做地面裁切；6 以上为地面的土环与空中碎屑）中不透明像素在地面以上的部分（各帧矩形内不透明像素的
  外接框按旋转后的多边形裁到 y ≤ 0）的外接矩形；钻入 7、钻出 12、绝招钻入 25、地下钻击 33 每 WINDOW tick 设一次受击框（取该段及
  前后各 1 tick 的并集）；身体全在地下的段落设受击框 0（R3；r91 / R2 取钻孔矩形：地面土环层在地面以上部分的范围，高 HOLE_H，
  现只记在报告中）；43 开头补 op3 1（同待机）。待机、掘削与受击保持 MSA 受击框 1（单位宽度由脚本 6 的受击框求得，原生
  setObjectSize）。
- 绝招攻击框（R3 用户 2026-10-25：钻离与钻击分段输出，每 4 tick 一段、每段 400，范围跟随可见钻身）：25 与 33 在 MSA 的攻击时段
  （第一条 op4 至 op4 0：25 第 0–60 tick、33 第 0–59 tick）内每 WINDOW tick 写一条 op4，攻击框为同一段受击框的矩形（标志
  ATTACK_FLAGS），无可见部分时为 0；核心 r94 在这两个动作中置身体状态 0x20，每条 op4 新建攻击 ID，框内各目标每段各受 1 次。
- 数值（用户 2026-10-25 选“同蜈蚣长老量级”；R2 用户选照 MSA：掘削每 tick 可命中、不击退；R3 用户：掘削每次 400，绝招每段 400）：
  生命 Lv40 50000（192 的 6000 × 25/3）、AP 850、掘削每次命中 400（近距组，192 的 1500 × 4/15，碎块同；R2 为 188）、绝招每段 400
  （192 的 2400 × 1/6；25 与 33 各 15 段，R2 为每个动作一次 6000）；R4 用户：生命 60000（192 × 10）、绝招 16 段 × 500（192 × 5/24，
  25 / 33 的攻击时段由 MSA 的 60 / 59 tick 延长到 64）、冷却 250 / 首次 200、出击时间同蜈蚣长老（192 × 26/7）、价格 150；击退门槛
  300 保留但本单位不击退。其余为 MSA 1843 的值（暂定）：近攻击距离 20（无远距攻击，词 7 写 0）、近距等待 60、绝招等待 40、绝招
  搜索距离（词 33，MSA 攻击 3 投射距离）500、近距第二参数 5（同 192）、绝招第二参数 200、目标数 999、属性普通。
- 部件判定（R4 用户 2026-10-25：判定框贴合贴图，只比贴图大一点点）：受击框 / 绝招攻击框每段另算部件（该段 4 tick 中身体层地面以上
  的不透明像素按 CELL 像素栅格化，按行或按列分成至多 PART_K 个条带、各取外接矩形，取总面积较小的分法），接在描述符框表中该框
  之后（第 5 值 PART_MARK）；核心 r95 在命中判定入口按部件判定，外框仍供原生的其他用途。待机 6 沿用 MSA 受击框 1（单位宽度由其求得），部件为待机循环中的并集；
  掘削 17 每 4 tick 一段，外框仍为受击框 1 的值。
- 掘削碎块（R4 用户 2026-10-25：同 MS7 / MSXX，落地后随惯性弹跳、滚动，过 0.5 秒爆炸，碰到敌军立即爆炸，无索敌）：落地后改播滚动
  动作（ROLL_FIRST 起，根层开攻击框 2、挂旋转子层），由核心按地形实时运动；落地 DEBRIS_FUSE tick 后或碰到敌方单位时改播爆炸
  BURST（MSA 小爆炸 103，攻击框按其图像范围开 BURST_ATTACK tick，伤害同碎块，碰到的目标不重复结算）。
- 音效：钻入与钻出同 MSA 都用原版 425（bull_drill_1，“钻出”声）与 2716（s1xlv.irondw_move，石块声）。R4 曾把 2716 换为 MSXX 的
  DRILL_STOP / DRILL_STAR（换错了音效，用户要求回退）；R6（用户 2026-10-25：钻出为“钻出、石块声”，缩回为“钻入、石块声”）把缩回地面的
  钻入 7（2 倍速副本 120 随之）与钻击 33 中的 425 换为 MSXX 的 DRILL_STOP，石块声保持，钻出不变。
- 钻入 / 钻出速度（R5 用户 2026-10-25：速度为 200%，动画一并加快；不影响大招的速度）：钻入 7 与钻出 12（连同其子层）按 FAST_FACTOR
  倍速重采样为 FAST 中的副本（新第 k tick 显示原第 2k tick 的帧、旋转、偏移与缩放，挂载与音效在原 tick 的一半处），用于移动的钻入与
  出场、移动结束、为近距攻击的钻出；绝招中的钻出（绝招开始时在地下先钻出、钻击后回原处钻出）仍用原速的 12（参数
  special_emerge_animation，核心 r96）。
- 地下行进（用户 2026-10-25 要求；MSA 为钻入后瞬移）：动作 UNDER 为根层挂与待机相同的土环 100 × 5 与每 TRAIL_EVERY tick 放一团
  尘土 21 的发射层 EMITTER，不设受击框（R3；R2 为钻孔矩形）；移速同蜈蚣长老（192 的 3 × 5/3）。
运行：E:\\anaconda3\\python.exe -I artwork/iron_death_worm_20261025/build_iron_death_worm.py [--report]
"""
from pathlib import Path
import hashlib
import json
import math
import shutil
import struct
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MSA_UNIT = Path(r'F:\egg\research\metal_slug_attack\decoded\units\1843')
MSA_DATA = Path(r'F:\egg\research\metal_slug_attack\data\files')
MSA_ICONS = Path(r'F:\egg\research\metal_slug_attack\decoded\unit_icons\unit_icon_02.obme.png')
MSA_TEXTS = REPO / 'verification' / 'iron_death_worm_20261025' / 'msa_texts.json'

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
KEY = 's1xlv.iron_death_worm'
FILE = 'iron_death_worm.json'
TEXTURES = ('iron_death_worm_0.obm', 'iron_death_worm_1.obm')
DESCRIPTOR = 'iron_death_worm_descriptor.json'
BASE = 192
MSA_SCRIPTS = 107
MSA_NOOP = set(range(24, 36)) | set(range(47, 59))
USED = (0, 6, 7, 12, 17, 25, 33, 44, 49)
MENU_SLOT, MENU_SCALE, MENU_SHIFT = 0, 40, 0      # 编队页缩小（追加脚本 107 起为动作 0 各部件的缩放副本）
MENU_DROP = {69}                                  # 编队页不挂的部件：待机末节（y 34 处，几乎全在地面以下）
UNDER, EMITTER = 111, 112                         # 地下行进（根层，土环随行）与其尘土发射层（每 TRAIL_EVERY tick 放一团尘土 21）
TRAIL, TRAIL_EVERY = 21, 4
DEAD_BODY = (50, 52, 54)                          # MSA EffectAction_DeadBody：落地后改播 +1（核心）
FALL_CHAIN = {92: 93}                             # EffectAction_DeadBody::createObject 0x5c：92 播完接 93
HOLD = 32767                                      # 挂载子层的父层循环前的等待（同 MSA op36：父层循环不重置子层）
HOLD_SLOTS = (0, 1, 6, 43, 44)                    # MSA 中含 op36 且循环的脚本
SOUNDS = {   # MSA SoundID → (本体音效键, MSA 文件, 音量 m_sound_data)
    2715: ('s1xlv.irondw_atk', 'irondw_atk.msa', 115),
    2716: ('s1xlv.irondw_move', 'irondw_move.msa', 100),
}
NATIVE_SOUNDS = {200, 203, 225, 425, 808}         # MSD 同号同文件
MSXX_SE = Path(r'F:\egg\MS7\MSXX-audio-wav\SE')    # 《合金弹头 XX》（PSP）音频提取包转出的 WAV（AGENTS 第 268 节）
DRILL_STOP = ('s1xlv.irondw_drill_stop', 'DRILL_STOP.wav', 100)   # R6：缩回地面的“钻入”声（本体音效键, WAV, 音量）
SOUND_425 = {7: DRILL_STOP[0], 33: DRILL_STOP[0]}  # R6：钻入 7 与钻击 33 的 425（“钻出”声）换为 DRILL_STOP；石块声 2716 保持
ROLL_FIRST, BURST = 113, 116                      # R4：碎块滚动根层 113–115（旋转子层 117–119）、碎块爆炸 116
ROLL_SPIN = BURST + 1
BURST_FX, BURST_DY = 103, 12                      # 爆炸图像为 MSA 小爆炸 103（用户 2026-10-25）；下移 12 使爆炸中心在碎块处
BURST_SOUND = 203                                 # B4_EXP3（MSA 损毁碎块落地的爆炸音效，同号同文件）
BURST_ATTACK = 4                                  # 爆炸攻击框开启 tick（同猎人炸药）
DEBRIS_FUSE = 15                                  # 落地后 0.5 秒爆炸（用户 2026-10-25）
FAST, FAST_FACTOR = {7: 120, 12: 121}, 2          # R5：钻入 / 钻出的 2 倍速副本（子层副本自 FAST_CHILD 起）；绝招中的钻出仍用 12
FAST_CHILD = 122
WORM = {   # 行为 iron_death_worm 的参数（MSA 动作号）
    'neutral_animation': 6, 'burrow_animation': FAST[7], 'emerge_animation': FAST[12], 'near_attack_animation': 17,
    'dive_animation': 25, 'drill_animation': 33, 'death_move_animation': 44, 'death_burst_animation': 49,
    'underground_animation': UNDER, 'debris_first_animation': 22, 'debris_count': 3,
    'dead_body_first_animation': DEAD_BODY[0], 'dead_body_count': len(DEAD_BODY),
    'debris_roll_first_animation': ROLL_FIRST, 'debris_burst_animation': BURST, 'debris_fuse': DEBRIS_FUSE,
    'special_emerge_animation': 12,
}
ICON_MSA = (441, 1464, 40, 40)                    # m_unit_misc.pict 1363
ICON_ANCHOR = [-5, -5]
ICON_START = (1748, 768)
VALUES = {
    # 生命 Lv40：R1–R3 50000（192 的 6000 × 25/3），R4 用户 2026-10-25 改为 60000（× 10）；击退门槛 300 为用户指定（本单位不击退）
    'ap': 850, 'shop_price': 150, 'hp_multiplier': [10, 1], 'knockback_threshold_multiplier': [15, 1],
    # 掘削每次命中（R2 照 MSA 的 EveryTimeAtk 每 tick 可命中，188；R3 用户 2026-10-25 提高到 400）：192 近距 Lv40 1500 × 4/15 = 400
    # 绝招（R3 用户 2026-10-25：钻离 25 与钻击 33 每 4 tick 一段、每段 400）：192 绝招 Lv40 2400 × 1/6 = 400；
    # R4 用户 2026-10-25：每个动作合计 8000，16 段 × 500（2400 × 5/24）
    'damage_multiplier': [1, 1], 'near_damage_multiplier': [4, 15], 'special_damage_multiplier': [5, 24],
    'production_interval_multiplier': [26, 7],
    # 用户 2026-10-25：移动改为像蜈蚣长老那样在地下行进；地下行进的移速同蜈蚣长老（192 的 3 × 5/3 = 5）
    'move_speed_multiplier': [5, 3],
    'status_word_values': {'6': 20, '7': 0, '17': 999, '20': 60, '31': 999, '33': 500, '34': 40, '35': 250, '36': 200},
    'status_float_values': {'16': 5.0, '30': 200.0},
    'attack_attributes': {'melee': 0, 'special': 0},
}
ONES = ('attack_wait_multiplier', 'attack_range_multiplier', 'knockback_distance_multiplier',
        'ballistic_range_multiplier')
# 受击框分段
HIT_SLOTS = (7, 12, 25, 33) + tuple(FAST.values())
ATTACK_SLOTS = (25, 33)   # R3：绝招钻离与钻击，在 MSA 的攻击时段内每 WINDOW tick 一段，攻击框取该段可见钻身（核心置攻击 ID 重置，每段各自结算）
ATTACK_FLAGS = 7          # MSA 攻击框 3 的第 5 个值
SPECIAL_SEGMENTS = 16     # R4：绝招每个动作 16 段（攻击时段 0–64 tick）
PART_SLOTS = (17,)        # R4：外框沿用受击框 1、只按段换部件的动作（掘削）
PART_MARK = 0x57445054    # R4：框表中部件条目的第 5 值（'WDPT'，核心 r95 按部件判定）
PART_K = 8                # 每个框的部件数上限
CELL = 2                  # 部件栅格（精灵像素）
STANDBY_TICKS = 288       # 待机 6 各部件循环（32 / 24 / 24 / 18 tick）的公倍数
WINDOW = 4
HOLE_H = 16          # 钻孔矩形高（精灵单位，世界 32）；土环在地面以上部分的高度见报告
BODY_PRIO = 6        # MSA draw：优先级 < 6 的层按地面裁切
DEBRIS_PRIO = 20     # 优先级 20 以上为空中的碎屑与尘土（op11 21）


def parent_offsets(record):
    seen, out = set(), {}

    def walk(s):
        if s in seen:
            return
        seen.add(s)
        for c in record['scripts'][s] or []:
            if c[0] in (11, 12, 36):
                out.setdefault(c[1], set()).add((c[3], c[4]))
                walk(c[1])
    for u in range(MSA_SCRIPTS):      # 未使用的槽（如 39 及其部件）一并换算，使描述符内全部脚本可用
        walk(u)
    return out


def frame_box(record, fid):
    rects, frames = record['rects'], record['frames']
    xs, ys = [], []
    for k in range(frames[fid]):
        x, y, w, h, ax, ay, flags, page = rects[frames[fid + 1 + k]]
        x0, x1 = (ax - w, ax) if flags & 1 else (-ax, w - ax)
        y0, y1 = (ay - h, ay) if flags & 2 else (-ay, h - ay)
        xs += [x0, x1]
        ys += [y0, y1]
    return min(xs), min(ys), max(xs), max(ys)


def expand_op45(cmds):
    """MSA op45（onEventMoveSpeedAnimation：下一位置 = 当前 + v，速度 = v + a；对象 update 先提交位置再加速度）的位移序列为
    v, v + a, v + 2a, …；MSD op7（同 MSA op7 onEventMoveAnimation，速度 = v）单独使用时为 v, v, v + a, …。加速度不为 0 时在其后
    每 tick 补一条 op7，第 k tick 取 v + k·a（下一位置 = 当前 + v + k·a，速度 = v + k·a），与 MSA 相同。"""
    out, t, move = [], 0, None
    for c in cmds:
        op = c['opcode']
        if op == 1 and move:
            for _ in range(c['values'][0]):
                out.append({'opcode': 1, 'values': [1]})
                t += 1
                k = t - move[4]
                out.append({'opcode': 7, 'values': [move[0] + k * move[2], move[1] + k * move[3], move[2], move[3]]})
            continue
        if op == 1:
            t += c['values'][0]
        if op == 7 and c.get('op45'):
            v = c['values']
            move = (v[0], v[1], v[2], v[3], t) if (v[2] or v[3]) else None
            out.append({'opcode': 7, 'values': list(v)})
            continue
        if op in (7, 16, 21):
            move = None
        out.append(c)
    return out


def hold_mounts(cmds):
    """MSA op36 只在第一遍执行，父层循环时子层不被重置；MSD op11 每遍执行，getAnimationStatus 把已有子层重置到开头。挂载之后只有
    受击框、等待与循环的父层把循环前的等待改为 HOLD tick（父层不再回到挂载处）。"""
    ops = [c['opcode'] for c in cmds]
    assert ops[-3:] == [0, 1, 5] and cmds[-3]['values'] == [-1] and ops.count(1) == 1, ops
    assert set(ops) <= {0, 1, 3, 5, 7, 11}, ops
    out = [dict(c, values=list(c['values'])) for c in cmds]
    out[-2]['values'] = [HOLD]
    return out


def convert(record):
    offsets = parent_offsets(record)
    stats = {'removed_msa': {}, 'op36_to_op11': 0, 'op45_to_op7': 0, 'op45_expanded': {}, 'op42_to_op14': {}, 'sounds': {}}
    animations = {}
    for slot in range(MSA_SCRIPTS):
        out, cum = [], None
        for c in record['scripts'][slot] or []:
            op, v = c[0], list(c[1:])
            if op in MSA_NOOP:
                stats['removed_msa'][str(op)] = stats['removed_msa'].get(str(op), 0) + 1
                continue
            entry = {}
            if op == 36:
                op = 11
                stats['op36_to_op11'] += 1
            elif op == 45:
                op = 7
                entry['op45'] = True
                stats['op45_to_op7'] += 1
            elif op == 42:
                if cum is None:
                    parents = offsets.get(slot)
                    assert parents is not None and len(parents) == 1, (slot, parents)
                    cum = next(iter(parents))
                cum = (cum[0] + v[0], cum[1] + v[1])
                op, v = 14, list(cum)
                stats['op42_to_op14'][str(slot)] = stats['op42_to_op14'].get(str(slot), 0) + 1
            elif op == 23:
                stats['sounds'][str(v[0])] = stats['sounds'].get(str(v[0]), 0) + 1
                if v[0] == 425 and slot in SOUND_425:
                    v = [SOUND_425[slot]]
                elif v[0] in SOUNDS:
                    v = [SOUNDS[v[0]][0]]
                else:
                    assert v[0] in NATIVE_SOUNDS, (slot, v)
            elif op == 19:
                assert v == [100, 40], (slot, v)          # 只有土环的纵向压扁，无 MSA 的“缩小一号”
            assert op <= 23, (slot, c)
            out.append({'opcode': op, 'values': v, **entry})
        if any(c['opcode'] == 14 for c in out):
            assert not any(c['opcode'] == 5 for c in out), slot
        n = sum(1 for c in out if c.get('op45'))
        out = expand_op45(out)
        added = sum(1 for c in out if c['opcode'] == 7) - n
        if added:
            stats['op45_expanded'][str(slot)] = added
        animations[slot] = out
    # EffectAction_DeadBody::createObject 0x5c：92 播完接 93（setAnimationID 清除移动 → op16）
    for first, then in FALL_CHAIN.items():
        body = animations[first]
        assert body[-1]['opcode'] == 21, first
        animations[first] = body[:-1] + [{'opcode': 16, 'values': []}] + [dict(c, values=list(c['values'])) for c in animations[then]]
    stats['fall_chain'] = {str(k): v for k, v in FALL_CHAIN.items()}
    # 编队页（原生 CreateDeckObject 以动作 0 原尺寸绘制、不按地面裁切）：动作 0 改为空根层挂各部件的缩放副本（追加脚本 107 起；
    # 父层 op19 不作用于子层，各副本自带 op19，已有的 op19 按比例相乘），挂载偏移同比缩放（同侵略者之王的做法）
    menu, copies, extra = animations[MENU_SLOT], {}, MSA_SCRIPTS
    for c in menu:
        if c['opcode'] == 11 and c['values'][0] not in copies:
            script = c['values'][0]
            body = [dict(x, values=list(x['values'])) for x in animations[script]]
            own = [x for x in body if x['opcode'] == 19]
            assert all(not any(y['opcode'] in (7, 11, 12, 14, 22) for y in body) for _ in [0]), script
            if own:
                for x in own:
                    x['values'] = [v * MENU_SCALE // 100 for v in x['values']]
            else:
                body = [{'opcode': 19, 'values': [MENU_SCALE, MENU_SCALE]}] + body
            copies[script] = extra
            animations[extra] = body
            extra += 1
    # 编队页不按地面裁切（MSA 的菜单绘制 ViewDrawIronDeathWarm 按地面裁切）：几乎全在地下的末节 69 不挂（其副本保留在描述符中）
    animations[MENU_SLOT] = [dict(c, values=[copies[c['values'][0]], c['values'][1], c['values'][2] * MENU_SCALE // 100 + MENU_SHIFT,
                                             c['values'][3] * MENU_SCALE // 100]) if c['opcode'] == 11 else c
                             for c in menu if not (c['opcode'] == 11 and c['values'][0] in MENU_DROP)]
    stats['menu_scaled'] = {'slot': MENU_SLOT, 'copies': copies, 'scale': MENU_SCALE, 'shift': MENU_SHIFT}
    # 地下行进（用户要求）：根层挂与待机 6 相同的土环 100 × 5（随单位移动）与尘土发射层；受击框为钻孔矩形（hit_rects 中填入）
    assert extra == UNDER, extra
    ring = [dict(c, values=list(c['values'])) for c in animations[6] if c['opcode'] == 11 and c['values'][0] == 100]
    assert len(ring) == 5
    animations[UNDER] = [{'opcode': 3, 'values': ['HOLE']}] + ring + [{'opcode': 11, 'values': [EMITTER, 0, 0, 0]},
                         {'opcode': 0, 'values': [-1]}, {'opcode': 1, 'values': [HOLD]}, {'opcode': 5, 'values': []}]
    animations[EMITTER] = [{'opcode': 12, 'values': [TRAIL, 0, 0, 0]}, {'opcode': 0, 'values': [-1]},
                           {'opcode': 1, 'values': [TRAIL_EVERY]}, {'opcode': 5, 'values': []}]
    # R4 碎块滚动：碎块脚本的帧与旋转（去掉 op7）转满一周为一个循环，作为子层；根层开攻击框 2（同碎块）后挂子层并保持（op4 只执行一次）
    first = WORM['debris_first_animation']
    for i in range(WORM['debris_count']):
        cycle = [{'opcode': 2, 'values': [0]}]
        for c in animations[first + i]:
            if c['opcode'] == 2 and abs(c['values'][0]) == 4096:
                break
            if c['opcode'] == 1 and cycle[-1]['opcode'] == 1:
                cycle[-1] = {'opcode': 1, 'values': [cycle[-1]['values'][0] + c['values'][0]]}
            elif c['opcode'] in (0, 1, 2):
                cycle.append({'opcode': c['opcode'], 'values': list(c['values'])})
        assert [c['values'] for c in animations[first + i] if c['opcode'] == 4] == [[2]], first + i
        animations[ROLL_SPIN + i] = cycle + [{'opcode': 5, 'values': []}]
        animations[ROLL_FIRST + i] = [{'opcode': 2, 'values': [0]}, {'opcode': 4, 'values': [2]},
                                      {'opcode': 11, 'values': [ROLL_SPIN + i, 0, 0, 0]}, {'opcode': 0, 'values': [-1]},
                                      {'opcode': 1, 'values': [HOLD]}, {'opcode': 5, 'values': []}]
    # R4 碎块爆炸：MSA 小爆炸 103 作子层（下移 BURST_DY），攻击框 BLAST（hit_rects 中按其图像范围填入）开 BURST_ATTACK tick，播完移除
    fx = duration(animations, BURST_FX)
    animations[BURST] = [{'opcode': 2, 'values': [0]}, {'opcode': 4, 'values': ['BLAST']}, {'opcode': 23, 'values': [BURST_SOUND]},
                         {'opcode': 11, 'values': [BURST_FX, 0, 0, BURST_DY]}, {'opcode': 0, 'values': [-1]},
                         {'opcode': 1, 'values': [BURST_ATTACK]}, {'opcode': 4, 'values': [0]},
                         {'opcode': 1, 'values': [fx - BURST_ATTACK]}, {'opcode': 21, 'values': []}]
    stats['debris_roll'] = {'roll': [ROLL_FIRST + i for i in range(WORM['debris_count'])], 'burst': BURST, 'fuse': DEBRIS_FUSE}
    # R5：钻入 7 / 钻出 12 的 FAST_FACTOR 倍速副本（子层一并复制，原脚本保留：12 仍用于绝招中的钻出）
    remap, nxt = {}, FAST_CHILD
    for root, copy in FAST.items():
        for c in animations[root]:
            if c['opcode'] == 11 and c['values'][0] not in remap:
                remap[c['values'][0]] = nxt
                nxt += 1
    for child, copy in remap.items():
        animations[copy] = resample(animations[child], FAST_FACTOR, remap)
    for root, copy in FAST.items():
        animations[copy] = resample(animations[root], FAST_FACTOR, remap)
    stats['fast'] = {'factor': FAST_FACTOR, 'roots': {str(k): v for k, v in FAST.items()}, 'children': {str(k): v for k, v in remap.items()},
                     'ticks': {str(k): [duration(animations, k), duration(animations, v)] for k, v in FAST.items()}}
    for cmds in animations.values():
        for c in cmds:
            c.pop('op45', None)
    return animations, stats


# ---------- 受击框：按 MSD 语义模拟（单位原点为地面，原画朝右，精灵单位） ----------
class Layer:
    def __init__(self, script, prio, ox, oy, parent):
        self.script, self.prio, self.ox, self.oy, self.parent = script, prio, float(ox), float(oy), parent
        self.eprio = prio + (parent.eprio if parent else 0)
        self.frame, self.angle, self.sx, self.sy = -1, 0.0, 1.0, 1.0
        self.vx = self.vy = self.ax = self.ay = 0.0
        self.pc, self.wait, self.done, self.kids = 0, 0, False, {}


class Sim:
    def __init__(self, anims, record, opaque):
        self.anims, self.record, self.opaque = anims, record, opaque

    def start(self, slot):
        self.root = Layer(slot, 0, 0, 0, None)
        self.layers = [self.root]
        self.hit = None
        self.run(self.root)

    def run(self, lay):
        if lay.done:
            return
        if lay.wait > 0:
            lay.wait -= 1
            if lay.wait > 0:
                return
        cmds = self.anims[lay.script]
        for _ in range(10000):
            if lay.pc >= len(cmds):
                lay.done = True
                return
            c = cmds[lay.pc]
            lay.pc += 1
            op, a = c['opcode'], c['values']
            if op == 0:
                lay.frame = a[0]
            elif op == 1:
                lay.wait = a[0]
                if lay.wait > 0:
                    return
            elif op == 2:
                lay.angle = a[0] * 360.0 / 4096.0
            elif op == 3 and lay is self.root:
                self.hit = a[0]
            elif op == 5:
                lay.pc = 0
            elif op == 7 and lay is not self.root:
                lay.vx, lay.vy, lay.ax, lay.ay = (v * 0.01 for v in a)
            elif op == 11:
                key = (a[0], a[1])
                if key not in lay.kids:
                    kid = Layer(a[0], a[1], a[2], a[3], lay)
                    lay.kids[key] = kid
                    self.layers.append(kid)
                    self.run(kid)
            elif op == 14 and lay is not self.root:
                lay.ox, lay.oy = float(a[0]), float(a[1])
            elif op == 16:
                lay.vx = lay.vy = lay.ax = lay.ay = 0.0
            elif op == 19:
                lay.sx, lay.sy = a[0] / 100.0, a[1] / 100.0
            elif op == 21:
                lay.done = True
                return

    def step(self):
        for lay in list(self.layers):
            if lay is not self.root:
                lay.ox += lay.vx
                lay.oy += lay.vy
                lay.vx += lay.ax
                lay.vy += lay.ay
            self.run(lay)

    def origin(self, lay):
        x, y = 0.0, 0.0
        while lay is not None:
            x, y = x + lay.ox, y + lay.oy
            lay = lay.parent
        return x, y

    def points(self, pts):
        """R4：身体层（优先级 < 6）不透明像素中心（pts：各矩形相对锚点的坐标）经缩放、旋转后在地面以上（y ≤ 0）的位置，N × 2。"""
        import numpy as np
        frames, out = self.record['frames'], []
        for lay in self.layers:
            if lay.frame < 0 or lay.eprio >= BODY_PRIO:
                continue
            ox, oy = self.origin(lay)
            th = math.radians(lay.angle)
            co, si = math.cos(th), math.sin(th)
            for k in range(frames[lay.frame]):
                p = pts[frames[lay.frame + 1 + k]]
                if p is None:
                    continue
                x, y = p[:, 0] * lay.sx, p[:, 1] * lay.sy
                out.append(np.stack([ox + x * co - y * si, oy + x * si + y * co], 1))
        a = np.concatenate(out) if out else np.zeros((0, 2))
        return a[a[:, 1] <= 0]

    def boxes(self, body):
        """可见层各帧矩形中不透明像素的外接框（旋转缩放后）裁到地面以上（y ≤ 0）的外接矩形；body 为 True 时取优先级 < 6 的层（身体），
        否则取地面土环层（优先级 6–19；20 以上为空中碎屑）。"""
        rects, frames = self.record['rects'], self.record['frames']
        xs, ys = [], []
        for lay in self.layers:
            if lay.frame < 0 or (lay.eprio < BODY_PRIO) != body or (not body and lay.eprio >= DEBRIS_PRIO):
                continue
            ox, oy = self.origin(lay)
            th = math.radians(lay.angle)
            co, si = math.cos(th), math.sin(th)
            for k in range(frames[lay.frame]):
                r = frames[lay.frame + 1 + k]
                x, y, w, h, ax, ay, flags, page = rects[r]
                if self.opaque[r] is None:
                    continue
                p0, q0, p1, q1 = self.opaque[r]           # 矩形内不透明像素 [p0, p1) × [q0, q1)
                x0, x1 = (ax - p1, ax - p0) if flags & 1 else (p0 - ax, p1 - ax)
                y0, y1 = (ay - q1, ay - q0) if flags & 2 else (q0 - ay, q1 - ay)
                poly = [(px * lay.sx, py * lay.sy) for px, py in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
                poly = [(ox + px * co - py * si, oy + px * si + py * co) for px, py in poly]
                for px, py in clip_above(poly):
                    xs.append(px)
                    ys.append(py)
        return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def clip_above(poly):
    """多边形裁到 y ≤ 0（Sutherland–Hodgman，单边）。"""
    out = []
    for i, (x1, y1) in enumerate(poly):
        x0, y0 = poly[i - 1]
        in0, in1 = y0 <= 0, y1 <= 0
        if in0 != in1:
            t = y0 / (y0 - y1)
            out.append((x0 + (x1 - x0) * t, 0.0))
        if in1:
            out.append((x1, y1))
    return out


def union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def duration(anims, slot):
    t = 0
    for c in anims[slot]:
        if c['opcode'] == 1:
            t += c['values'][0]
        if c['opcode'] in (5, 21):
            break
    return t


def opaque_boxes(record, atlases):
    out = []
    for x, y, w, h, ax, ay, flags, page in record['rects']:
        out.append(atlases[page].crop((x, y, x + w, y + h)).getbbox() if w > 0 and h > 0 else None)
    return out


def timeline(anims, record, slot, opaque):
    sim = Sim(anims, record, opaque)
    sim.start(slot)
    total = duration(anims, slot)
    body, dirt = [], []
    for t in range(total):
        body.append(sim.boxes(True))
        dirt.append(sim.boxes(False))
        sim.step()
    return total, body, dirt


def opaque_points(record, atlases):
    """R4：各矩形不透明像素中心相对锚点的坐标（按翻转标志换算，同绘制），无不透明像素时为 None。"""
    import numpy as np
    out = []
    for x, y, w, h, ax, ay, flags, page in record['rects']:
        if w <= 0 or h <= 0:
            out.append(None)
            continue
        alpha = np.asarray(atlases[page].crop((x, y, x + w, y + h)))[:, :, 3]
        qy, px = np.nonzero(alpha)
        if not len(px):
            out.append(None)
            continue
        cx = (ax - px - 0.5) if flags & 1 else (px + 0.5 - ax)
        cy = (ay - qy - 0.5) if flags & 2 else (qy + 0.5 - ay)
        out.append(np.stack([cx, cy], 1).astype(float))
    return out


def timeline_points(anims, record, opaque, pts, slot, total=None):
    """R4：各 tick 的身体不透明像素位置（Sim.points）。"""
    sim = Sim(anims, record, opaque)
    sim.start(slot)
    total = duration(anims, slot) if total is None else total
    out = []
    for t in range(total):
        out.append(sim.points(pts))
        sim.step()
    return out


def bands(points, k):
    """R4：点集按 CELL 栅格化，按行（或按列）分成至多 k 个相邻条带，各取外接矩形，使总面积最小（动态规划），两种方向取较小者；
    返回 [x, y, w, h]（精灵像素）。"""
    import numpy as np
    if not len(points):
        return []
    cells = np.unique(np.floor(points / CELL).astype(int), axis=0)
    best = None
    for axis in (1, 0):                         # 1：按行分条带；0：按列
        lines = {}
        for c in cells:
            lo, hi = lines.get(int(c[axis]), (None, None))
            v = int(c[1 - axis])
            lines[int(c[axis])] = (v if lo is None else min(lo, v), v if hi is None else max(hi, v))
        keys = sorted(lines)
        n = len(keys)
        span = [[None] * n for _ in range(n)]   # span[i][j]：第 i 至 j 条线合成一个条带的 (面积, 低, 高)
        for i in range(n):
            lo, hi = lines[keys[i]]
            for j in range(i, n):
                lo, hi = min(lo, lines[keys[j]][0]), max(hi, lines[keys[j]][1])
                span[i][j] = ((keys[j] - keys[i] + 1) * (hi - lo + 1), lo, hi)
        inf = float('inf')
        dp = [[inf] * (n + 1) for _ in range(k + 1)]
        cut = [[0] * (n + 1) for _ in range(k + 1)]
        dp[0][0] = 0
        for g in range(1, k + 1):
            for j in range(1, n + 1):
                for i in range(g - 1, j):
                    v = dp[g - 1][i] + span[i][j - 1][0]
                    if v < dp[g][j]:
                        dp[g][j], cut[g][j] = v, i
        g = min(range(1, k + 1), key=lambda q: dp[q][n])
        total, rects, j = dp[g][n], [], n
        while g:
            i = cut[g][j]
            _, lo, hi = span[i][j - 1]
            a0, a1 = keys[i], keys[j - 1]
            x0, x1, y0, y1 = (lo, hi, a0, a1) if axis == 1 else (a0, a1, lo, hi)
            rects.append([x0 * CELL, y0 * CELL, (x1 - x0 + 1) * CELL, (y1 - y0 + 1) * CELL])
            g, j = g - 1, i
        if best is None or total < best[0]:
            best = (total, sorted(rects))
    return best[1]


class BoxTable:
    """R4：描述符的受击 / 攻击框表；每个框之后接其部件（第 5 值 PART_MARK），同一外框与部件只登记一次。"""
    def __init__(self, rows):
        self.rows, self.keys = [list(r) for r in rows], {}

    def add(self, box, parts):
        key = (tuple(box), tuple(tuple(p) for p in parts))
        if key not in self.keys:
            self.keys[key] = len(self.rows)
            self.rows.append(list(box))
            self.rows += [list(p) + [PART_MARK] for p in parts]
        return self.keys[key]


def resample(cmds, factor, remap):
    """R5：逐帧脚本按 factor 倍速重采样。新第 k tick 显示原第 factor·k tick 的状态（op0 帧、op2 旋转、op14 偏移、op19 缩放，按原 tick 执行
    后的值）；其余指令（op11 挂载改挂 remap 中的副本、op3、op4、op12、op16、op23）在原 tick ÷ factor（向下取整）处执行。原脚本须无循环与
    速度指令。"""
    state_ops = (0, 2, 14, 19)
    t, timed = 0, []
    for c in cmds:
        if c['opcode'] == 1:
            t += c['values'][0]
            continue
        assert c['opcode'] not in (5, 7, 10, 22), c
        if c['opcode'] == 21:
            break
        timed.append((t, c))
    total = t
    n = (total + factor - 1) // factor
    snaps, state, i = [], {}, 0
    for tick in range(total):
        while i < len(timed) and timed[i][0] <= tick:
            if timed[i][1]['opcode'] in state_ops:
                state[timed[i][1]['opcode']] = list(timed[i][1]['values'])
            i += 1
        snaps.append(dict(state))
    out, prev = [], {}
    for k in range(n):
        for tick, c in timed:
            if c['opcode'] not in state_ops and min(tick // factor, n - 1) == k:
                v = list(c['values'])
                if c['opcode'] == 11:
                    v[0] = remap[v[0]]
                out.append({'opcode': c['opcode'], 'values': v})
        cur = snaps[k * factor]
        for op in state_ops:
            if op in cur and cur[op] != prev.get(op):
                out.append({'opcode': op, 'values': list(cur[op])})
        prev = cur
        if out and out[-1]['opcode'] == 1:
            out[-1] = {'opcode': 1, 'values': [out[-1]['values'][0] + 1]}
        else:
            out.append({'opcode': 1, 'values': [1]})
    return out + [{'opcode': 21, 'values': []}]


def insert_rects(cmds, ticks):
    """在根层脚本的指定 tick（首个 op1 之前为 0）插入 op3 / op4；必要时拆分 op1 等待。ticks：[(tick, 指令, 框号)]，按 tick 升序；
    脚本中原有的同号指令（12 第 84 tick 的 op3、25 / 33 的 op4 3 与 op4 0）由分段取代。"""
    out, t, todo = [], 0, sorted(ticks, key=lambda e: (e[0], e[1]))
    ops = {e[1] for e in todo}
    for c in cmds:
        if c['opcode'] == 1:
            wait = c['values'][0]
            while todo and todo[0][0] < t + wait:
                at, op, idx = todo.pop(0)
                if at > t:
                    out.append({'opcode': 1, 'values': [at - t]})
                    wait -= at - t
                    t = at
                out.append({'opcode': op, 'values': [idx]})
            out.append({'opcode': 1, 'values': [wait]})
            t += wait
            continue
        if c['opcode'] in (5, 21):
            while todo and todo[0][0] <= t:
                at, op, idx = todo.pop(0)
                out.append({'opcode': op, 'values': [idx]})
        if c['opcode'] in ops:
            continue
        out.append(c)
    assert not todo, (todo, t)
    return out


def op_ticks(cmds, opcode):
    """脚本中各条 opcode 指令所在的 tick 与参数。"""
    t, out = 0, []
    for c in cmds:
        if c['opcode'] == 1:
            t += c['values'][0]
        elif c['opcode'] == opcode:
            out.append((t, c['values'][0]))
    return out


def rect_of(u, flags):
    return [math.floor(u[0]), math.floor(u[1]), math.ceil(u[2]) - math.floor(u[0]), math.ceil(u[3]) - math.floor(u[1]), flags]


def hit_rects(anims, record, opaque, pts):
    record_hits = [list(r) for r in record['hit_bounds']]
    assert record_hits == [[0, 0, 0, 0, 0], [12, -163, 92, 164, 0]]
    record_attacks = [list(r) for r in record['attack_bounds']]
    assert record_attacks[0] == [0, 0, 0, 0, 0] and record_attacks[3][4] == ATTACK_FLAGS
    report = {}
    # 待机 6（R4）：外框沿用 MSA 受击框 1（原生按其求单位宽度），部件为待机循环 STANDBY_TICKS tick 中各矩形外接框的并集
    import numpy as np
    standby_parts = bands(np.concatenate(timeline_points(anims, record, opaque, pts, 6, STANDBY_TICKS)), PART_K)
    hits = BoxTable(record_hits[:1])
    assert hits.add(record_hits[1], standby_parts) == 1
    attacks = BoxTable(record_attacks)
    for slot in HIT_SLOTS + PART_SLOTS:
        total, body, dirt = timeline(anims, record, slot, opaque)
        points = timeline_points(anims, record, opaque, pts, slot)
        hole_x = None
        for b in dirt:
            hole_x = union(hole_x, b)
        hole = (math.floor(hole_x[0]), -HOLE_H, math.ceil(hole_x[2]), 0) if hole_x else None
        # R3（用户 2026-10-25：身体在地下时不应被打到）：每段取该段及前后各 1 tick 中地面以上可见身体的外接矩形；全在地下时不设受击框
        # （受击框 0；r91 / R2 为钻孔矩形）。R4：外框之后接该段的部件；掘削 17 的外框沿用受击框 1
        segs, boxes, parts = [], {}, {}
        for k in range(0, total, WINDOW):
            u = None
            for t in range(max(0, k - 1), min(total, k + WINDOW + 1)):
                u = union(u, body[t])
            boxes[k] = u
            pp = np.concatenate(points[k:k + WINDOW])
            if u is None or not len(pp):      # R5：该段 4 tick 中身体全在地下时不设受击框（R3 / R4 按前后各加 1 tick 判断）
                segs.append((k, 3, 0))
                continue
            parts[k] = bands(pp, PART_K)
            box = record_hits[1] if slot in PART_SLOTS else rect_of(u, 0)
            segs.append((k, 3, hits.add(box, parts[k])))
        atk = []
        if slot in ATTACK_SLOTS:
            # R3：MSA 的攻击时段内每 WINDOW tick 一段，攻击框取该段可见钻身，没有可见部分时关框；R4：16 段（0–64 tick），框后接部件
            start = next(t for t, v in op_ticks(anims[slot], 4) if v)
            end = start + SPECIAL_SEGMENTS * WINDOW
            assert start % WINDOW == 0 and end <= total, (slot, start, end, total)
            for k in range(start, end, WINDOW):
                if k not in parts:
                    atk.append((k, 4, 0))
                    continue
                atk.append((k, 4, attacks.add(rect_of(boxes[k], ATTACK_FLAGS), parts[k])))
            atk.append((end, 4, 0))
        anims[slot] = insert_rects(anims[slot], segs + atk)
        dirt_top = min((b[1] for b in dirt if b), default=None)
        report[str(slot)] = {'ticks': total, 'hole': hole, 'dirt_top': dirt_top,
                             'segments': [[k, hits.rows[i], parts.get(k)] for k, _, i in segs],
                             'attack_segments': [[k, attacks.rows[i]] for k, _, i in atk],
                             'body_per_tick': [[round(v) for v in b] if b else None for b in body]}
    # 43（MSA 状态 80 技能硬直，MSD 中无对应状态）：开头补 op3 1（同待机）
    anims[43] = [{'opcode': 3, 'values': [1]}] + anims[43]
    # 地下行进：不设受击框（R3 用户 2026-10-25：同蜈蚣长老的地下前行，MSA 地下移动脚本以 op3 0 设空；R2 为钻孔矩形）
    anims[UNDER][0] = {'opcode': 3, 'values': [0]}
    # R4 碎块爆炸的攻击框：小爆炸 103 开框期间（BURST_ATTACK tick）各帧不透明外接框的并集（下移 BURST_DY），无部件
    fx = None
    t = 0
    for c in anims[BURST_FX]:
        if c['opcode'] == 1:
            t += c['values'][0]
        elif c['opcode'] == 0 and c['values'][0] >= 0 and t < BURST_ATTACK:
            fid = c['values'][0]
            for n in range(record['frames'][fid]):
                r = record['frames'][fid + 1 + n]
                x, y, w, h, ax, ay, flags, page = record['rects'][r]
                if opaque[r] is None:
                    continue
                p0, q0, p1, q1 = opaque[r]
                x0, x1 = (ax - p1, ax - p0) if flags & 1 else (p0 - ax, p1 - ax)
                y0, y1 = (ay - q1, ay - q0) if flags & 2 else (q0 - ay, q1 - ay)
                fx = union(fx, (x0, y0 + BURST_DY, x1, y1 + BURST_DY))
    blast = rect_of(fx, ATTACK_FLAGS)
    blast_index = attacks.add(blast, [])
    anims[BURST] = [dict(c, values=[blast_index]) if c['values'] == ['BLAST'] else c for c in anims[BURST]]
    report['burst_blast'] = blast
    # 待机 6 的核对：模拟的可见外接矩形与 MSA 受击框 1 对照
    total, body, _ = timeline(anims, record, 6, opaque)
    u = None
    for b in body:
        u = union(u, b)
    report['6_visible_union'] = [round(v) for v in u]
    report['6_parts'] = standby_parts
    attacks.rows.append([0, 0, 0, 0, 0])          # 末尾一条空框：核心读部件时到此为止
    assert len(hits.rows) <= 2048 and len(attacks.rows) <= 2048
    return hits.rows, attacks.rows, report


def descriptor(record, hit_bounds, attack_bounds, animations):
    assert 0xffffffff not in record['frames']
    return {'rects': [list(r) for r in record['rects']], 'frames': list(record['frames']),
            'script_count': max(animations) + 1, 'hit_bounds': hit_bounds, 'attack_bounds': attack_bounds}


def localization():
    texts = json.loads(MSA_TEXTS.read_text(encoding='utf-8'))['1843']
    return {lang: {'name': t['name'], 'description': t['description']} for lang, t in texts.items()}


def unit_file(animations, icon_rect):
    v = VALUES
    return {'key': KEY, 'base_id': BASE, 'faction': 1, 'identity': 'Rebel Army',
            'shop_price': v['shop_price'], 'available_from_start': True, 'ap': v['ap'],
            'hp_multiplier': v['hp_multiplier'],
            # 击退门槛 300：同蜈蚣长老（用户 2026-10-25；第 6.1 节的例外）。R2 起照 MSA 不击退（全部动作 EnableNockBack(false)），门槛不起作用
            'knockback_threshold_multiplier': v['knockback_threshold_multiplier'],
            'damage_multiplier': v['damage_multiplier'], 'near_damage_multiplier': v['near_damage_multiplier'],
            'special_damage_multiplier': v['special_damage_multiplier'],
            **{k: [1, 1] for k in ONES},
            'move_speed_multiplier': v['move_speed_multiplier'],
            'production_reference_id': BASE, 'production_interval_multiplier': v['production_interval_multiplier'],
            'status_word_values': v['status_word_values'], 'status_float_values': v['status_float_values'],
            'attack_attributes': v['attack_attributes'],
            'image_direction': 90, 'special_effect_size': [90, 120], 'minimap_marker': [10, 20],
            'icon': {'page': 1, 'rect': list(icon_rect), 'anchor': ICON_ANCHOR},
            'textures': list(TEXTURES), 'sprite_descriptor': DESCRIPTOR,
            'animations': {str(k): animations[k] for k in sorted(animations)},
            'localization': localization(), 'tags': ['ms7', 'msa'],
            'behaviors': [{'name': 'iron_death_worm', 'version': 4, 'params': WORM}]}


def find_icon_slot(raw):
    w, h = struct.unpack_from('<HH', raw, 4)
    used = []
    for f in CONTENT.glob('units/*.json'):
        unit = json.loads(f.read_text(encoding='utf-8'))
        icon = unit['icon']
        if unit['key'] != KEY and icon.get('page') == 1 and 'atlas' not in icon:
            used.append(icon['rect'])
    iw, ih = ICON_MSA[2], ICON_MSA[3]
    for y in range(ICON_START[1], h - ih, 2):
        for x in range(ICON_START[0] if y == ICON_START[1] else 0, w - iw, 2):
            if any(not (x + iw + 2 <= u[0] or x >= u[0] + u[2] + 2 or y + ih + 2 <= u[1] or y >= u[1] + u[3] + 2) for u in used):
                continue
            if any(raw[8 + ((y + j) * w + x + i) * 4 + 3] for j in range(ih) for i in range(iw)):
                continue
            return [x, y, iw, ih]
    raise RuntimeError('no free icon slot')


def write_icon(raw, cell, rect):
    raw = bytearray(raw)
    assert raw[:4] == b'OI\x01\x20'
    w, h = struct.unpack_from('<HH', raw, 4)
    ax, ay, iw, ih = rect
    for j in range(ih):
        for i in range(iw):
            at = 8 + ((ay + j) * w + ax + i) * 4
            raw[at:at + 4] = bytes(cell.getpixel((i, j)))
    return bytes(raw)


def encode_ogg(wav, target):
    """WAV 编码为 Ogg Vorbis（同 artwork/iron_sentinel_20261020/build_iron_sentinel.py 的 encode_ogg：libsndfile 分块写入）。"""
    import soundfile as sf
    data, rate = sf.read(str(wav), always_2d=True)
    with sf.SoundFile(str(target), 'w', samplerate=rate, channels=data.shape[1], format='OGG', subtype='VORBIS') as f:
        for i in range(0, len(data), 4096):
            f.write(data[i:i + 4096])


def main():
    OUT.mkdir(exist_ok=True)
    (HERE / 'source').mkdir(exist_ok=True)
    record = json.loads((MSA_UNIT / 'record.json').read_text(encoding='utf-8'))
    assert record['names'] == ['70003IronDeathWarm01_out.obm', '70003IronDeathWarm_EF_out.obm']
    assert record['script_count'] == MSA_SCRIPTS and record['image_value'] == 90
    atlases = [Image.open(MSA_UNIT / (n + '.png')).convert('RGBA') for n in record['names']]
    animations, stats = convert(record)
    hit_bounds, attack_bounds, hits = hit_rects(animations, record, opaque_boxes(record, atlases), opaque_points(record, atlases))
    for slot in HOLD_SLOTS:                     # 受击框模拟之后（模拟按 MSA 的首遍挂载语义，循环长度不影响）
        assert any(c[0] == 36 for c in record['scripts'][slot]) and any(c[0] == 5 for c in record['scripts'][slot]), slot
        animations[slot] = hold_mounts(animations[slot])
    stats['held'] = list(HOLD_SLOTS)
    # 音效清单（R3，供替换音效）：各动作中 op23 所在的 tick 与音效（数字为 MSD 原版 SoundID，键为本体音效）
    stats['sound_events'] = {str(k): op_ticks(v, 23) for k, v in sorted(animations.items()) if op_ticks(v, 23)}
    desc = descriptor(record, hit_bounds, attack_bounds, animations)
    obms = [indexed_obm(a) for a in atlases]
    x, y, iw, ih = ICON_MSA
    cell = Image.open(MSA_ICONS).convert('RGBA').crop((x, y, x + iw, y + ih))
    cell.save(HERE / 'source' / f'msa_icon_iron_death_worm_{x}_{y}.png')
    report = {'stats': stats, 'colors': [len(set(a.getdata())) for a in atlases], 'obm_bytes': [len(o) for o in obms],
              'hit_bounds': len(hit_bounds), 'attack_bounds': len(attack_bounds), 'hits': hits, 'values': VALUES}
    (OUT / 'hit_report.json').write_text(json.dumps(hits, ensure_ascii=False), encoding='utf-8')
    if '--report' in sys.argv:
        brief = {k: v for k, v in report.items() if k != 'hits'}
        brief['hits'] = {s: {k: v for k, v in h.items() if k != 'body_per_tick'} if isinstance(h, dict) else h for s, h in hits.items()}
        print(json.dumps(brief, ensure_ascii=False))
        return
    index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
    if KEY not in index['unit_ids']:
        index['unit_ids'][KEY] = max(index['unit_ids'].values()) + 1
    for name, raw in zip(TEXTURES, obms):
        (CONTENT / name).write_bytes(raw)
        index['assets'][name] = hashlib.blake2b(raw, digest_size=32).hexdigest()
    sounds = list(index.get('sounds', []))
    for key, source, volume in SOUNDS.values():
        target = key.split('.', 1)[1] + '.msdf'
        shutil.copyfile(MSA_DATA / source, CONTENT / target)
        entry = {'key': key, 'file': target, 'type': 'se', 'volume': volume}
        at = next((i for i, e in enumerate(sounds) if e['key'] == key), None)
        if at is None:
            sounds.append(entry)
        else:
            sounds[at] = entry
    key, wav, volume = DRILL_STOP                      # R6：WAV 编码为 Ogg Vorbis（.msdf）；libsndfile 每次取随机流序列号，已有文件时不重编
    target = key.split('.', 1)[1] + '.msdf'
    if not (CONTENT / target).exists():
        encode_ogg(MSXX_SE / wav, CONTENT / target)
    entry = {'key': key, 'file': target, 'type': 'se', 'volume': volume}
    at = next((i for i, e in enumerate(sounds) if e['key'] == key), None)
    if at is None:
        sounds.append(entry)
    else:
        sounds[at] = entry
    index['sounds'] = sounds
    icon_raw = (CONTENT / 'unit_icon_02.obm').read_bytes()
    unit_path = CONTENT / 'units' / FILE
    rect = json.loads(unit_path.read_text(encoding='utf-8'))['icon']['rect'] if unit_path.exists() else find_icon_slot(icon_raw)
    (CONTENT / 'unit_icon_02.obm').write_bytes(write_icon(icon_raw, cell, rect))   # 该资源的摘要在 content.json 中为 null，保持不变
    save_json(CONTENT / DESCRIPTOR, desc)
    save_json(unit_path, unit_file(animations, rect))
    save_json(CONTENT / 'content.json', index)
    report['unit_id'] = index['unit_ids'][KEY]
    report['icon_rect'] = rect
    brief = {k: v for k, v in report.items() if k != 'hits'}
    (OUT / 'build_report.json').write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(brief, ensure_ascii=False))


if __name__ == '__main__':
    main()
