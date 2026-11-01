"""Fall Climber（MS7 任务 4 首领）制作为本体单位（2026-11-01 起；行为 fall_climber v1，核心 r115 起）。

方案：docs/MS7_M4_UNITS_2026-10-31.md 第 19 节（用户 2026-11-01 确认离线示意第 14 版，决定两形态 20000 + 20000、玩家可购买 350 勋章、
普攻数值同 HOZUMI、绝招 16 × 500、AP 999、再出击 100 秒、绝招冷却 16 秒；R9 用户平衡调整：第二形态生命 40000、普攻每颗 800、
远距 700、弹飞行距离 900、绝招 12 段 × 800；R10：普攻每颗 400、1.2 秒一发、每 20 发强制待机 6 秒、远距 600、弹飞行距离 750；R11 弹飞行距离 700；R12 绝招 4 段 × 2000）。
- 两个单位共用一套图集与描述符：第一形态 s1xlv.fall_climber（可购买、无绝招）、第二形态 s1xlv.fall_climber_form2（内部单位）。
- 图像：原作精灵表部件与效果帧（fc_rig.py；Gussprint 拆图、esreveR 大激光），HOZUMI（原生 317）普攻光球 8 帧取自原生图集
  VG27_29F_3_out.obm（脚本 44 的帧 348–362）。原画朝左（image_direction 270），左手 = 前方的手。
- 结构：每个根动作（待机、移动、攻击、转换、绝招、损毁）只隐藏根层并以 op11 挂七个子层：两块上臂（优先级 0 / 1，画在机体之后）、
  机体组（2；其下再挂髋、爪、机体、引擎、引擎蒸汽、背枪、头部 / 玻璃罩、炮口火花、蓄力光球、激光，合计 3–9）、左手与左前臂（11、12）、
  右手与右前臂（21、22）。
  子层偏移为游戏中的静止姿势（fc_rig.py）；核心每 tick 改写机体组的偏移（起伏）与六块手臂的偏移、转角（两手随步伐与地形，反向运动学），
  整机按原生绘制，不按地形裁切（R4，用户选定方案 A：位置不变，行走线以下的部分大多在底栏之后）。根层与子层的脚本以长等待
  （HOLD）保持，不以短循环重建子层。根动作第一 tick 不放音效（核心以嵌套调用切换动作，遇到音效导入会中止）。
- 音效（R4 按名称与时长选定；R5 用户嫌 MSXX 版音质差，改用用户提供的 NDS 版提取包 F:\\egg\\MS7\\mslug7_sdat_extract 中同名的序列，
  以 ds_sseq.py 按同目录的 SoundFont 渲染为 16 kHz 立体声）：
  手落地 St4_Boss3_Walk1 / Walk2（核心在左 / 右手落地时播放，行为参数 step_sounds），绝招蓄力 ST4_KydaiLASER_Tm（巨大激光蓄力，
  PSG 方波扫频），激光 St4_Beam_Shot（采样 + PSG，约 2.2 秒，对应激光全程）；未与原作画面逐一对照。普攻仍为 HOZUMI 470。
  核心播放的音效须出现在单位脚本中才会随单位预载，手落地音效写在不播放的脚本 sound_bank（同 PvZ 僵尸的槽 8）。
运行：E:\\anaconda3\\python.exe -I artwork/fall_climber_20261101/build_fall_climber.py [--preview]
（--preview 只写 out/；否则另写 community_content/ 的图集、描述符、两个单位文件与 content.json，头像与文本见 M3）。"""
from pathlib import Path
import gzip
import hashlib
import json
import math
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import fc_rig as R   # noqa: E402

CONTENT = REPO / 'community_content'
OUT = HERE / 'out'
NATIVE = REPO / 'game_data' / 'assets' / 'com.snkplaymore.android003'
_PVZ = REPO / 'artwork' / 'pvz_zombies_20261012' / 'build_pvz_zombies.py'
_src = _PVZ.read_text(encoding='utf-8')
_src = _src.replace("sys.path.insert(0, str(RT / 'packages'))", "").replace("os.add_dll_directory(str(RT / 'native'))", "")
pvz = type(sys)('pvzb')
pvz.__dict__['__file__'] = str(_PVZ)
exec(compile(_src, str(_PVZ), 'exec'), pvz.__dict__)
indexed_obm, save_json, shelf_pack = pvz.indexed_obm, pvz.save_json, pvz.shelf_pack

KEY1, KEY2 = 's1xlv.fall_climber', 's1xlv.fall_climber_form2'
FILE1, FILE2 = 'fall_climber.json', 'fall_climber_form2.json'
DESCRIPTOR = 'fall_climber_descriptor.json'
TEX = 'fall_climber_{}.obm'
BASE = 192
FACTION, IDENTITY = 1, 'Rebel Army'
HOLD = 32767                          # 根层与静态子层的长等待（父层循环会重建子层）

SLOT = {
    'deck': 0, 'deck2': 1,
    # 第一形态根动作
    'neutral': 6, 'move': 7, 'attack_l': 8, 'attack_r': 9, 'transform': 10,
    # 第二形态根动作
    'neutral2': 12, 'move2': 13, 'attack2_l': 14, 'attack2_r': 15, 'intro2': 16, 'charge': 17, 'laser': 18, 'death2': 19,
    # 机体组
    'g1': 20, 'g1_fire_l': 21, 'g1_fire_r': 22, 'g2': 24, 'g2_fire_l': 25, 'g2_fire_r': 26, 'g2_charge': 27, 'g2_laser': 28,
    # 机体组内的部件
    'hip_l1': 30, 'hip_r1': 31, 'claw_l1': 32, 'claw_r1': 33, 'body1': 34, 'engine': 35, 'steam_l': 36, 'steam_r': 37,
    'gun_l': 38, 'gun_r': 39, 'gun_l_fire': 40, 'gun_r_fire': 41, 'head1': 42, 'spark_l': 43, 'spark_r': 44,
    'hip_l2': 45, 'hip_r2': 46, 'claw_l2': 47, 'claw_r2': 48, 'body2': 49, 'core': 50, 'charge_orb': 51, 'beam': 52,
    # 手臂（根层的直接子层，核心逐 tick 改写）
    'upper_l1': 53, 'hand_l1': 54, 'fore_l1': 55, 'upper_r1': 56, 'hand_r1': 57, 'fore_r1': 58,
    'upper_l2': 59, 'hand_l2': 60, 'fore_l2': 61, 'upper_r2': 62, 'hand_r2': 63, 'fore_r2': 64,
    # 肘护盖（R7 起单独成层）
    'cap_l1': 72, 'cap_r1': 73, 'cap_l2': 74, 'cap_r2': 75,
    # 效果（op12）与弹体
    'orb': 65, 'release_l': 66, 'release_r': 67, 'shell': 68, 'hand_steam': 69, 'death_burst': 70,
    # 不播放：核心播放的手落地音效随单位预载（R4）
    'sound_bank': 71,
    # 损毁时抛出的碎块（R7）
    **{f'debris{k}': 76 + k for k in range(10)},
}
SCRIPT_COUNT = 86
# 优先级（沿父层累加）：上臂在机体之后（整机图），与机体组同属第一遍（< 10，按身体处地形裁切）；手与前臂各为第二、三遍
# R7：手臂各块按整机图的前后（手 < 前臂 < 肘护盖 < 上臂 < 机体）；机体组移到 10，全部为正数（核心按这些值找层，FC_P_*）
GROUP_PRIO = 10
ARM_PRIO = {'hand_l': 1, 'fore_l': 2, 'cap_l': 3, 'upper_l': 4, 'hand_r': 5, 'fore_r': 6, 'cap_r': 7, 'upper_r': 8}
# 机体组内的次序按整机图（Fallmecha.webp）逐像素核对：机体 < 背枪 < 头部 < 引擎 < 蒸汽。背枪（素材表 SPARK GUN，32×32 方块，含所在处
# 机体的镀板与凹槽边缘）在引擎之下（R5）；头部在引擎之下（R6，用户指出升起的气缸顶被头部下沿截平；整机图中头部与引擎重叠的 45 个像素
# 全为引擎）。炮口火花、蓄力光球与激光在最上。
BODY_PRIO = {'hip': 1, 'claw': 1, 'body': 2, 'gun': 3, 'head': 4, 'engine': 5, 'steam': 6, 'spark': 7, 'beam': 7}

# 普攻：炮口伸出（1→10）、蓄能、射出、缩回，再回 1。示意第 13–14 版为蓄能 16、缩回 11、12、13、5、4、3、2（一发约 2.7 秒，同 HOZUMI）；
# R6（用户：0.8 秒一发）蓄能 7、缩回 11、12、13、5、3，动作 22 tick 加攻击后等待 1 tick（词 27），两门轮流
GUN_EXTEND = list(range(1, 11))
GUN_CHARGE = 7
GUN_RETRACT = [11, 12, 13, 5, 3]
FIRE_TICK = len(GUN_EXTEND) - 1 + GUN_CHARGE           # 第 16 tick 出膛
ATTACK_T = FIRE_TICK + 1 + len(GUN_RETRACT)             # 攻击动作长度 22（加攻击后等待（词 27）与回到状态 10 的 1 tick：R6–R9 等待 1、24 tick 一发，R10 等待 14、36 tick 一发）
SHOT_SOUND, SOUND_LEAD = 470, 6                          # HOZUMI 普攻音效（hoz_lazer_1），出膛前 6 tick
CHARGE_SEQ = [0, 2, 4, 6, 9, 12, 13]                    # 炮口蓄能火花（表内 SHOOTING SFX 第一行 14 帧取 7 帧），7 tick（R6）
# 绝招：蓄力 8 帧 × 4 tick；激光起始 6、持续 8 帧循环 9 次、变暗 8、收窄 12（每 tick 一帧）；R12（用户 4 段）4 段每 22 tick，
# 第 6、28、50、72 tick 分布在激光持续段（R9–R11 为 12 段每 6 tick，R3–R8 为 16 段每 4 tick）
CHARGE_T = 32
LASER_SEGMENTS, LASER_EVERY, LASER_FIRST = 4, 22, 6
EXT = 64                                                 # 激光帧顶以上按顶行补的高度（素材像素）
DS_SEQ = Path(r'F:\egg\MS7\mslug7_sdat_extract\sequence\00de-00fa')   # NDS 版音效序列（任务 4 区段，BANK_005.sf2；R5）
SOUNDS = {   # 本体音效键 → 序列名（R5）；音量 100
    's1xlv.fall_climber_step1': 'St4_Boss3_Walk1',
    's1xlv.fall_climber_step2': 'St4_Boss3_Walk2',
    's1xlv.fall_climber_charge': 'ST4_KydaiLASER_Tm',
    's1xlv.fall_climber_laser': 'St4_Beam_Shot',
}
VORBIS_QUALITY = 0.8                                     # libsndfile VBR 质量（缺省 0.4）；原版 16 kHz 立体声音效中位约 76 kbps
STEP_SOUNDS = ['s1xlv.fall_climber_step1', 's1xlv.fall_climber_step2']   # 左手、右手
SOUND_CHARGE, SOUND_LASER = 's1xlv.fall_climber_charge', 's1xlv.fall_climber_laser'   # 绝招蓄力与激光（各在第 1 tick）
ENGINE_STEP, STEAM_STEP = 1, 1                           # 每 tick 一帧（30 fps，示意第 11 版起）
# 引擎 10 帧各自的偏移（示意第 11 版 fc_anim_r11.py 的 ENG_OFF：对齐后为无缝单向周期；R4 以前缺此偏移，逐帧抖动 1–2 像素）
ENG_OFF = [(0, 0), (-1, -1), (0, 0), (-1, 2), (0, 2), (-1, 0), (0, -1), (-1, 0), (0, 2), (-1, 2)]
TRANSFORM_T, INTRO_T, DEATH2_T = 36, 60, 46

# HOZUMI 普攻光球（原生 317 脚本 44：帧 348–362 各 2 tick；图集页 3 = VG27_29F_3_out.obm）：(x, y, w, h, 锚点 x, y)
HZ_PAGE = 'VG27_29F_3_out.obm'
ORB_BOX = 2                                              # 光球攻击框在描述符 attack_bounds 中的序号（R6）
HZ_ORB = [(651, 145, 21, 23, 12, 13), (673, 145, 21, 23, 12, 13), (695, 145, 26, 25, 15, 14), (448, 392, 26, 25, 15, 14),
          (206, 171, 21, 18, 11, 9), (293, 233, 21, 17, 11, 9), (478, 373, 21, 23, 12, 13), (687, 171, 25, 26, 11, 13)]


def cmd(op, *v):
    return {'opcode': op, 'values': [int(round(x)) for x in v]}


def sound(key):
    return {'opcode': 23, 'values': [key]}


def show(key):
    return {'opcode': 0, 'values': [key], 'key': True}


HIDE = cmd(0, -1)


# ---------- 素材 ----------
def oi_decode(raw):
    if raw[:2] == b'\x1f\x8b':
        raw = gzip.decompress(raw)
    kind, depth = raw[2] & 0x7f, raw[3]
    w, h = struct.unpack_from('<HH', raw, 4)
    assert depth == 8 and kind in (0, 1), (kind, depth)
    size = 3 if kind == 0 else 4
    pal = [tuple(raw[8 + i * size:8 + (i + 1) * size]) + ((255,) if size == 3 else ()) for i in range(256)]
    data = raw[8 + 256 * size:8 + 256 * size + w * h]
    im = Image.new('RGBA', (w, h))
    im.putdata([pal[i] for i in data])
    return im


def core_center(img):
    """白色内芯（240,240,240）的外接框中心；没有时取最上方连通块的中心（示意第 14 版的炮口火花对位）。"""
    a = np.asarray(img)
    white = np.all(a[..., :3] == 240, axis=2) & (a[..., 3] > 0)
    if white.sum() >= 3:
        ys, xs = np.nonzero(white)
    else:
        lab, n = ndimage.label(a[..., 3] > 0, structure=np.ones((3, 3)))
        objs = ndimage.find_objects(lab)
        top = min(range(n), key=lambda k: objs[k][0].start)
        ys, xs = np.nonzero(lab == top + 1)
    return (xs.min() + xs.max() + 1) / 2, (ys.min() + ys.max() + 1) / 2


def dome_anchor(img):
    a = np.asarray(img.getchannel('A')) > 0
    rows = np.nonzero(a.any(axis=1))[0]
    b = rows.max() + 1
    xs = np.nonzero(a[b - 4:b].any(axis=0))[0]
    return ((xs.min() + xs.max() + 1) / 2, b)


class Tiles:
    """图块：名称 → (RGBA 图, 锚点)，按页分组（页内颜色不超过 256）。"""

    def __init__(self):
        self.items, self.page = {}, {}

    def add(self, name, img, anchor, page):
        if img.getbbox() is None:
            img = Image.new('RGBA', (1, 1))
            anchor = (0, 0)
        self.items[name] = (img, (int(round(anchor[0])), int(round(anchor[1]))))
        self.page[name] = page


def load():
    t = Tiles()
    # 页 0：机体与手臂（两形态）；页 1：背枪、引擎、蒸汽、玻璃罩、火花、光球；页 2–3：蓄力光球与激光
    for form in (1, 2):
        peek = R.PEEK + (R.RISE if form == 2 else 0)
        for name, img, tl in R.body_parts(form):
            t.add(f'{name}{form}', img, (-tl[0], -tl[1]), 0)
        for side in 'LR':
            a = R.arm_rest(form, side)
            for piece, pivot in (('upper', 'S'), ('cap', 'E'), ('fore', 'E'), ('hand', 'H')):
                img, tl = a[piece]
                t.add(f'{piece}_{side.lower()}{form}', img, (a[pivot][0] - tl[0], a[pivot][1] - tl[1]), 0)
        if form == 1:
            head = R.part(3)
            t.add('head1', head, (51, peek), 0)
    for k in range(10):
        t.add(f'engine{k}', R.part(56 + k), (-ENG_OFF[k][0], -ENG_OFF[k][1]), 1)
    for side, (seq, y, h) in (('l', (R._ST1, 462, 50)), ('r', (R._ST2, 514, 64))):
        prev = None
        for k, (x0, x1) in enumerate(seq):
            img = R.cell(x0, y, x1 - x0, h)
            ox = 0
            if img.width < 48 and prev is not None:
                pa = np.asarray(prev)[..., 3] > 0
                best = -1
                for cand in (0, 8, 16):
                    m = np.zeros_like(pa)
                    m[:, cand:cand + img.width] = np.asarray(img)[..., 3] > 0
                    if (m & pa).sum() > best:
                        best, ox = (m & pa).sum(), cand
            t.add(f'steam_{side}{k}', img, (-ox, 0), 1)
            if img.width == 48:
                prev = img
            else:
                prev = Image.new('RGBA', (48, img.height))
                prev.alpha_composite(img, (ox, 0))
    gl = [R.part(k) for k in list(range(4, 16)) + [17, 18]]
    gr = [R.part(k) for k in range(19, 33)]
    for k in range(14):
        t.add(f'gun_l{k}', gl[k], (0, 0), 1)
        t.add(f'gun_r{k}', gr[k], (0, 0), 1)
    for k, x in enumerate((3, 69, 137, 203, 269, 335)):
        t.add(f'core{k}', R.cell(x, 756, 64, 32), (0, 0), 1)
    rows1 = [(3, 16, 16), (21, 16, 32), (39, 32, 32), (73, 32, 32), (107, 48, 32), (157, 32, 32), (191, 48, 32), (241, 32, 32),
             (275, 48, 32), (325, 32, 32), (359, 48, 32), (409, 32, 32), (443, 48, 32), (493, 32, 32)]
    for k, (x, w, h) in enumerate(rows1):
        img = R.cell(x, 200, w, h)
        t.add(f'spark_l{k}', img, core_center(img), 1)
        m = R.mirror(img)
        cx, cy = core_center(img)
        t.add(f'spark_r{k}', m, (img.width - cx, cy), 1)
    rel0 = [R.cell(3 + 34 * i, 234, 32, 32) for i in range(10)]
    c0 = core_center(rel0[0])
    for k, img in enumerate(rel0):
        t.add(f'release_l{k}', img, c0, 1)
        t.add(f'release_r{k}', R.mirror(img), (img.width - c0[0], c0[1]), 1)
    page = oi_decode((NATIVE / HZ_PAGE).read_bytes())
    for k, (x, y, w, h, ax, ay) in enumerate(HZ_ORB):
        t.add(f'orb{k}', page.crop((x, y, x + w, y + h)), (ax, ay), 1)
    charge = [R.part(k, rect=True) for k in (348, 345, 346, 347, 344, 350, 351, 349)]
    for k, img in enumerate(charge):
        t.add(f'charge{k}', img, dome_anchor(img), 2)
    seqs = {'ls': (352, 353, 355, 356, 364, 365), 'll': range(366, 374), 'lf': (379, 381, 382, 383, 386, 387, 388, 389),
            'le': list(range(390, 398)) + [398, 399, 400, 401]}
    for tag, ks in seqs.items():
        for k, n in enumerate(ks):
            img = R.part(n, rect=True)
            a = dome_anchor(img)
            t.add(f'{tag}{k}', img, a, 2 if tag in ('ls', 'll') else 3)
            row = np.asarray(img.getchannel('A'))[0]
            if (row > 0).mean() > 0.5:                     # 帧顶以上按顶行补 EXT 行（与激光帧同一帧的第二个矩形）
                strip = img.crop((0, 0, img.width, 2))
                ext = Image.new('RGBA', (img.width, EXT))
                for y in range(0, EXT, 2):
                    ext.alpha_composite(strip, (0, y))
                t.add(f'{tag}{k}x', ext, (a[0], a[1] + EXT), 2 if tag in ('ls', 'll') else 3)
    t.add('shell', R.part(3), (51, 19), 0)
    # 损毁碎块（R7）：第二形态的手、前臂、肘护盖、上臂（两侧）与玻璃罩、引擎，锚点在图案中心
    for side in 'LR':
        a = R.arm_rest(2, side)
        for piece in ('hand', 'fore', 'cap', 'upper'):
            img = a[piece][0]
            t.add(f'deb_{piece}_{side.lower()}', img, (img.width / 2, img.height / 2), 0)
    core = R.cell(69, 756, 64, 32)   # R12（用户）：抛出的玻璃罩为已碎状态（表内 BRAIN CORE 第 1 帧；R7–R11 为完好的第 0 帧）
    t.add('deb_core', core, (32, 16), 1)
    t.add('deb_engine', R.part(56), (30, 40), 1)
    return t


# ---------- 脚本 ----------
# 损毁（R7，用户：先停下，再像钢铁哨兵 R13 那样炸成碎屑）：核心在损毁 / 转换开始时冻结骨架（不再起伏、迈步）；槽 19 第 1–29 tick 每 2 tick
# 在机体可见各处放 1 个爆炸（0xff04，每 3 个中 1 个 0xff03），第 30–37 tick 两侧错开的爆炸铺满整机并有 2 个大型爆炸 0xff17，第 34 tick
# 抛出 10 个碎块（op7 抛出：向上 5–8、横向 1–3.5 素材像素每 tick，重力 0.4，每 tick 转 spin 度，落回约出发高度时消失），第 46 tick 结束、
# 单位移除（爆炸遮住）。坐标为素材像素、相对单位原点（原画朝左，x 负为前方）。
DEATH_SPOTS = [(0, -30), (-122, -32), (122, -30), (-24, -16), (26, -18), (-100, 6), (98, 4), (-132, -8), (130, -10),
               (-60, 14), (62, 12), (0, -6), (-40, 30), (42, 28), (-118, -48), (120, -46)]
DEATH_WAVE = [(-140, -40), (-110, -10), (-80, 10), (-50, -20), (-20, -36), (10, -10), (40, -30), (70, 8), (100, -14),
              (130, -36), (-125, 20), (125, 18), (-30, 40), (30, 44)]
DEBRIS_G = 40                                             # 碎块重力（1/100 素材像素每 tick²）
# (图块, 横向速度, 竖直速度（负为向上）, 每 tick 转角（度）, 存在 tick)；横向正值为向后（原画朝左）
DEBRIS = [('deb_hand_l', -300, -720, 14, 40), ('deb_fore_l', -200, -800, -12, 44), ('deb_cap_l', -350, -560, 20, 34),
          ('deb_upper_l', -120, -640, -9, 38), ('deb_hand_r', 300, -700, -14, 40), ('deb_fore_r', 220, -780, 12, 44),
          ('deb_cap_r', 340, -580, -20, 34), ('deb_upper_r', 140, -660, 9, 38), ('deb_core', -60, -820, 8, 46),
          ('deb_engine', 80, -600, -10, 36)]


def death_events():
    a = {s: R.arm_rest(2, s) for s in 'LR'}
    ev = [(1 + 2 * k, [cmd(12, 0xff03 if k % 3 == 2 else 0xff04, 1, *DEATH_SPOTS[k % len(DEATH_SPOTS)])]) for k in range(15)]
    ev += [(30 + k // 2, [cmd(12, 0xff04, 1, *DEATH_WAVE[k])]) for k in range(len(DEATH_WAVE))]
    ev += [(32, [cmd(12, 0xff17, 1, 0, -10)]), (36, [cmd(12, 0xff17, 1, 0, 30)])]
    out = []
    for k, (key, *_rest) in enumerate(DEBRIS):
        piece, side = (key[4:].rsplit('_', 1) + [''])[:2] if key.count('_') == 2 else (key[4:], '')
        if side:
            img, tl = a[side.upper()][piece]
            pos = (tl[0] + img.width / 2, tl[1] + img.height / 2)
        else:
            pos = (0, R.CORE_AT[1] - R.PEEK - R.RISE + 16) if piece == 'core' else (R.REF['engine'][3][0] + 30, R.REF['engine'][3][1] - R.PEEK - R.RISE + 40)
        out.append(cmd(12, SLOT[f'debris{k}'], 1, *pos))
    ev += [(34, out)]
    return ev


def frames(keys, step, total=None):
    out, tt, k = [], 0, 0
    total = total if total is not None else len(keys) * step
    while tt < total:
        n = min(step, total - tt)
        out += [show(keys[k % len(keys)]), cmd(1, n)]
        tt += n
        k += 1
    return out


def hold(key):
    return [show(key), cmd(1, HOLD), cmd(5)]


def sub(slot, prio, x=0, y=0):
    return cmd(11, SLOT[slot], prio, x, y)


def body_group(form, variant):
    """机体组（根层的子层，优先级 0）：子层偏移为 0，图块锚点已含相对原点的位置。"""
    f = str(form)
    out = [HIDE]
    for s in ('l', 'r'):
        out.append(sub(f'hip_{s}{f}', BODY_PRIO['hip']))
    for s in ('l', 'r'):
        out.append(sub(f'claw_{s}{f}', BODY_PRIO['claw']))
    peek = R.PEEK + (R.RISE if form == 2 else 0)
    ex, ey = R.REF['engine'][3]
    out += [sub(f'body{f}', BODY_PRIO['body']), sub('engine', BODY_PRIO['engine'], ex, ey - peek),
            sub('steam_l', BODY_PRIO['steam'], R.STEAM_AT['L'][0], R.STEAM_AT['L'][1] - peek),
            sub('steam_r', BODY_PRIO['steam'], R.STEAM_AT['R'][0], R.STEAM_AT['R'][1] - peek)]
    for s in ('l', 'r'):
        gx, gy = R.REF['gun_' + s.upper()][3]
        fire = variant == f'fire_{s}'
        out.append(sub(f'gun_{s}_fire' if fire else f'gun_{s}', BODY_PRIO['gun'], gx, gy - peek))
        if fire:
            mx, my = R.MUZZLE[s.upper()]
            out.append(sub(f'spark_{s}', BODY_PRIO['spark'], mx, my - peek))
    if form == 1:
        out.append(sub('head1', BODY_PRIO['head']))
    else:
        cx, cy = R.CORE_AT
        if variant == 'charge':
            out.append(sub('charge_orb', BODY_PRIO['spark'], R.CORE_ANCHOR[0], R.CORE_ANCHOR[1] - peek))
        if variant != 'laser':
            out.append(sub('core', BODY_PRIO['head'], cx, cy - peek))
        else:
            out.append(sub('beam', BODY_PRIO['beam'], R.CORE_ANCHOR[0], R.CORE_ANCHOR[1] - peek))
    out += [cmd(1, HOLD), cmd(5)]
    return out


def rig(form, group, extra=(), hit=1, end=None):
    """根动作：隐藏根层，挂机体组与六块手臂；extra 为其后的指令（不以 op23 开头）；end 为长度（None 为长等待循环）。"""
    f = str(form)
    out = [HIDE, cmd(3, hit), sub(group, GROUP_PRIO)]
    for side in 'LR':
        a = R.arm_rest(form, side)
        s = side.lower()
        out += [sub(f'upper_{s}{f}', ARM_PRIO['upper_' + s], *a['S']), sub(f'hand_{s}{f}', ARM_PRIO['hand_' + s], *a['H']),
                sub(f'fore_{s}{f}', ARM_PRIO['fore_' + s], *a['E']), sub(f'cap_{s}{f}', ARM_PRIO['cap_' + s], *a['E'])]
    out += list(extra)
    out += [cmd(1, HOLD), cmd(5)] if end is None else []
    return out


def at_ticks(events, total):
    """[(tick, [指令])] → 指令序列（op1 等待补齐到 total 后结束）。tick 0 的事件应不含 op23。"""
    out, t = [], 0
    for tick, cmds in sorted(events, key=lambda e: e[0]):
        if tick > t:
            out.append(cmd(1, tick - t))
            t = tick
        out += cmds
    if total > t:
        out.append(cmd(1, total - t))
    return out + [cmd(21)]


def scripts(t):
    s = {}
    peek1, peek2 = R.PEEK, R.PEEK + R.RISE
    # 机体组内的部件
    for f in (1, 2):
        for s_ in ('l', 'r'):
            s[SLOT[f'hip_{s_}{f}']] = hold(f'hip_{s_.upper()}{f}')
            s[SLOT[f'claw_{s_}{f}']] = hold(f'claw_{s_.upper()}{f}')
        s[SLOT[f'body{f}']] = hold(f'body{f}')
        for piece in ('upper', 'hand', 'fore', 'cap'):
            for s_ in ('l', 'r'):
                s[SLOT[f'{piece}_{s_}{f}']] = hold(f'{piece}_{s_}{f}')
    s[SLOT['engine']] = frames([f'engine{k}' for k in range(10)], ENGINE_STEP) + [cmd(5)]
    s[SLOT['steam_l']] = frames([f'steam_l{k}' for k in range(10)], STEAM_STEP) + [cmd(5)]
    s[SLOT['steam_r']] = frames([f'steam_r{k}' for k in range(10)], STEAM_STEP) + [cmd(5)]
    s[SLOT['head1']] = hold('head1')
    for s_ in ('l', 'r'):
        s[SLOT[f'gun_{s_}']] = hold(f'gun_{s_}1')
        seq = GUN_EXTEND + [10] * GUN_CHARGE + GUN_RETRACT + [1]
        s[SLOT[f'gun_{s_}_fire']] = [c for k in seq for c in (show(f'gun_{s_}{k}'), cmd(1, 1))][:-1] + [cmd(1, HOLD), cmd(5)]
        spark = [HIDE, cmd(1, len(GUN_EXTEND) - 1)] + [c for k in CHARGE_SEQ for c in (show(f'spark_{s_}{k}'), cmd(1, 1))]
        s[SLOT[f'spark_{s_}']] = spark + [HIDE, cmd(1, HOLD), cmd(5)]
        s[SLOT[f'release_{s_}']] = frames([f'release_{s_}{k}' for k in range(10)], 1) + [HIDE, cmd(1, 1), cmd(21)]
    # 玻璃罩（表内 BRAIN CORE 一行）：0 完好、1 已碎（不用）、2–5 放电；R11（用户：第二阶段绝招前后出现已损坏的玻璃罩）去掉循环中的第 1 帧
    s[SLOT['core']] = [show('core0'), cmd(1, 35)] + frames([f'core{k}' for k in (2, 3, 4, 5, 4, 5, 3, 2)], 1) + [cmd(5)]
    s[SLOT['charge_orb']] = frames([f'charge{k}' for k in range(8)], 4)[:-1] + [cmd(1, HOLD), cmd(5)]   # 蓄力 32 tick：8 帧 × 4，末帧保持
    beam = []
    for tag, n, rep in (('ls', 6, 1), ('ll', 8, 9), ('lf', 8, 1), ('le', 12, 1)):
        for _ in range(rep):
            for k in range(n):
                beam += [show(f'{tag}{k}'), cmd(1, 1)]
    s[SLOT['beam']] = beam + [HIDE, cmd(1, HOLD), cmd(5)]
    # 光球的攻击框（R6 补）：同 HOZUMI 弹体脚本 44 的 op4 3（攻击框 [-13, -16, 26, 27]）；R3–R5 缺此指令，光球没有攻击框、不造成伤害
    s[SLOT['orb']] = [cmd(4, ORB_BOX)] + frames([f'orb{k}' for k in range(8)], 2) + [cmd(5)]
    # 头壳：向后上方飞出并旋转（op7 [vx, vy, ax, ay]，1/100 素材像素；原画朝左，正 vx 为向后）
    shell = [cmd(7, 150, -750, 0, 35)]
    for k in range(40):
        shell += [cmd(2, (k * 11 * 4096 // 360) % 4096), show('shell'), cmd(1, 1)]
    s[SLOT['shell']] = shell + [HIDE, cmd(1, 1), cmd(21)]
    s[SLOT['hand_steam']] = frames([f'steam_l{k}' for k in range(10)], 2) + [HIDE, cmd(1, 1), cmd(21)]
    s[SLOT['death_burst']] = [HIDE, cmd(1, 1), cmd(21)]
    # 机体组
    s[SLOT['g1']] = body_group(1, 'rest')
    s[SLOT['g1_fire_l']] = body_group(1, 'fire_l')
    s[SLOT['g1_fire_r']] = body_group(1, 'fire_r')
    s[SLOT['g2']] = body_group(2, 'rest')
    s[SLOT['g2_fire_l']] = body_group(2, 'fire_l')
    s[SLOT['g2_fire_r']] = body_group(2, 'fire_r')
    s[SLOT['g2_charge']] = body_group(2, 'charge')
    s[SLOT['g2_laser']] = body_group(2, 'laser')
    # 根动作
    for f, pre in ((1, ''), (2, '2')):
        g = f'g{f}'
        s[SLOT['neutral' + pre]] = rig(f, g)
        s[SLOT['move' + pre]] = rig(f, g)
        peek = peek1 if f == 1 else peek2
        for side in ('l', 'r'):
            mx, my = R.MUZZLE[side.upper()]
            ev = [(FIRE_TICK - SOUND_LEAD, [cmd(23, SHOT_SOUND)]),
                  (FIRE_TICK, [cmd(22, SLOT['orb'], 40, mx, my - peek), cmd(12, SLOT[f'release_{side}'], 1, mx, my - peek)])]
            s[SLOT[f'attack{pre}_{side}']] = rig(f, f'{g}_fire_{side}', at_ticks(ev, ATTACK_T), end=True)
    s[SLOT['deck']] = rig(1, 'g1')
    s[SLOT['deck2']] = rig(1, 'g1')
    # 第一形态的转换（生命耗尽）：小爆炸 → 大爆炸；之后核心生成第二形态并移除本单位
    spots = [(-122, -30), (-40, -8), (122, -40), (40, -6), (-90, -20), (90, -24)]
    ev = [(4 + 5 * k, [cmd(12, 0xff02, 1, *spots[k % len(spots)])]) for k in range(6)] + [(TRANSFORM_T - 4, [cmd(12, 0xff04, 1, 0, 6)])]
    s[SLOT['transform']] = rig(1, 'g1', at_ticks(ev, TRANSFORM_T), hit=0, end=True)
    # 第二形态出场：头壳炸飞、两手冒蒸汽（机体抬高由核心按 tick 写入）
    ev = [(1, [cmd(12, SLOT['shell'], 1, 0, -(peek2 - 19))])]
    ev += [(2 + 12 * k, [cmd(12, SLOT['hand_steam'], 1, (-1) ** k * 125, -50)]) for k in range(5)]
    s[SLOT['intro2']] = rig(2, 'g2', at_ticks(ev, INTRO_T), end=True)
    ev = [(1, [sound(SOUND_CHARGE)])]
    s[SLOT['charge']] = rig(2, 'g2_charge', at_ticks(ev, CHARGE_T), end=True)
    laser_t = 6 + 8 * 9 + 8 + 12
    ev = [(1, [sound(SOUND_LASER)])]
    ev += [(LASER_FIRST + LASER_EVERY * k, [cmd(4, 1)]) for k in range(LASER_SEGMENTS)]
    ev += [(LASER_FIRST + LASER_EVERY * LASER_SEGMENTS, [cmd(4, 0)])]
    s[SLOT['laser']] = rig(2, 'g2_laser', at_ticks(ev, laser_t), end=True)
    s[SLOT['death2']] = rig(2, 'g2', at_ticks(death_events(), DEATH2_T), hit=0, end=True)
    for k, (key, vx, vy, spin, n) in enumerate(DEBRIS):
        sc = [cmd(7, vx, vy, 0, DEBRIS_G)]
        for i in range(n):
            sc += [cmd(2, (i * spin * 4096 // 360) % 4096), show(key), cmd(1, 1)]
        s[SLOT[f'debris{k}']] = sc + [HIDE, cmd(1, 1), cmd(21)]
    s[SLOT['sound_bank']] = [sound(k) for k in STEP_SOUNDS] + [cmd(21)]
    for k in range(SCRIPT_COUNT):
        s.setdefault(k, [cmd(21)])
    return s


def bounds():
    """受击框 1：外框（原生用于宽度、前缘与选目标；实际判定由核心按整台机体的部件计算，R4）；攻击框 1：激光竖列（身体 ±60、地面以上 400）。"""
    hits = [[0, 0, 0, 0, 0], [-160, -56, 320, 56, 0]]
    atks = [[0, 0, 0, 0, 7], [-60, -400, 120, 400, 7], [-13, -16, 26, 27, 7]]   # 2：光球（同 HOZUMI 攻击框 3）
    return hits, atks


def assemble(t, s):
    pages = sorted(set(t.page.values()))
    rects, words, start, page_imgs = [], [], {}, []
    for pi in pages:
        names = [n for n in t.items if t.page[n] == pi]
        img, xy = shelf_pack([t.items[n][0] for n in names])
        page_imgs.append(img)
        for i, n in enumerate(names):
            im, (ax, ay) = t.items[n]
            rects.append([xy[i][0], xy[i][1], im.width, im.height, ax, ay, 0, pages.index(pi)])
            start.setdefault(n, None)
            t.items[n] = (im, (ax, ay), len(rects) - 1)
    for n, item in t.items.items():
        start[n] = len(words)
        r = item[2]
        if n + 'x' in t.items:                               # 激光帧：帧本身与其上的补长矩形
            words += [2, r, t.items[n + 'x'][2]]
        else:
            words += [1, r]
    anims = {}
    for slot, cmds in s.items():
        anims[slot] = [cmd(0, start[c['values'][0]]) if c.get('key') else c for c in cmds]
    return page_imgs, rects, words, anims


def preview(page_imgs, rects, words, anims):
    """静态展示：根动作 0 的各层按脚本偏移合成（不经核心），对照 fc_rig 的静止姿势。"""
    W, H, ox, oy = 420, 260, 210, 120
    c = Image.new('RGBA', (W, H), (60, 60, 70, 255))

    def frame_of(slot):
        for cm in anims[slot]:
            if cm['opcode'] == 0:
                return cm['values'][0]
        return -1

    def draw(slot, x, y, depth=0):
        layers = [(cm['values'][1], cm['values'][0], cm['values'][2], cm['values'][3]) for cm in anims[slot] if cm['opcode'] == 11]
        f = frame_of(slot)
        items = [(0, None, 0, 0)] + layers
        for prio, child, dx, dy in sorted(items, key=lambda e: e[0]):
            if child is None:
                if f >= 0:
                    for r in words[f + 1:f + 1 + words[f]]:
                        rx, ry, rw, rh, ax, ay, _, pg = rects[r]
                        c.alpha_composite(page_imgs[pg].crop((rx, ry, rx + rw, ry + rh)), (int(x - ax), int(y - ay)))
            else:
                draw(child, x + dx, y + dy, depth + 1)
    draw(SLOT['deck'], ox, oy)
    d = ImageDraw.Draw(c)
    d.line([(0, oy), (W, oy)], fill=(255, 60, 60, 255))
    return c.resize((W * 3, H * 3), Image.NEAREST)


# ---------- 单位文件 ----------
# 基准 192（INVADER）Lv40：生命 6000、近距 1500、普攻 1060、绝招 2400、移速 3、再出击 550 tick（钢铁死亡蠕虫文档与 LAB 读数）。
VALUES = {
    # 用户 2026-11-01：第一形态 20000（6000 × 10/3）；R9 第二形态 40000（20/3，见 FORM2_VALUES）；击退门槛倍率随生命（第 6.1 节；本单位不击退）
    'ap': 999, 'shop_price': 350, 'hp_multiplier': [10, 3], 'knockback_threshold_multiplier': [10, 3],
    # R13（用户）：普攻 Lv40 600（1060 × 30/53；R10–R12 为 400，1060 × 20/53；R9 为 800，R3–R8 同 HOZUMI 3000）；远距 600、弹飞行距离 700（R11；R10 750，R9 为 700 / 900，
    # R6 为 400 / 600）；1.2 秒一发（攻击后等待 14，LAB fc17 实测一发周期 = 22 + 等待 tick；R6–R9 等待 1）；每射出 20 发强制待机 6 秒
    # （行为参数 burst_shots / burst_cooldown）；贯穿（每发命中目标数 999，同一颗对同一目标只结算一次）；绝招 4 段 × 2000（2400 × 5/6，R12；R9–R11 为 12 段 × 800，R3–R8 为 16 段 × 500）
    'damage_multiplier': [1, 1], 'normal_damage_multiplier': [30, 53], 'special_damage_multiplier': [5, 6],
    # 再出击 100 秒 = 3000 tick（550 × 60/11）；移速同 HOZUMI 1.5（3 × 1/2）
    'production_interval_multiplier': [60, 11], 'move_speed_multiplier': [1, 2],
    # 词 6 / 7 近距 / 远距触发距离，24 普攻每发命中目标数，26 / 27 普攻弹飞行距离 / 攻击后等待，33 绝招投射距离，34 间隔，35 / 36 绝招等待 / 首次冷却（16 秒 = 480 tick；
    # 第二形态的首次冷却为 1 tick，进入第二阶段即可发动一次，用户 2026-11-01 R4，见 FORM2_STATUS；词 36 为 0 时 BattleUnit::isSpAttack
    # 恒为否（无绝招），计量 +0x320 自词 36 起每 tick 递减、小于 0 时可发动，发动后自词 35 重新计）
    'status_word_values': {'6': 0, '7': 600, '24': 999, '26': 700, '27': 14, '33': 800, '34': 40, '35': 480, '36': 480},
    'attack_attributes': {'normal': 2, 'special': 0},
}
FORM2_STATUS = {'36': 1}
FORM2_VALUES = {'hp_multiplier': [20, 3], 'knockback_threshold_multiplier': [20, 3]}   # R9 第二形态 40000（6000 × 20/3）
ONES = ('attack_wait_multiplier', 'attack_range_multiplier', 'knockback_distance_multiplier', 'ballistic_range_multiplier')
LOCALIZATION = {   # 名称与说明由代理撰写，待校对
    'EN': ('FALL CLIMBER', 'STAND. ATK : Energy Ball     SPEC. ATK : Big Laser\nA Rebel Army giant machine that crawls with its head\nand two hands above ground, its body buried below.'),
    'JP': ('フォールクライマー', '通常攻撃：エネルギー弾     特殊攻撃：大型レーザー\n地中に胴体を沈め、頭と両手だけを地上に出して\n這い進むモーデン軍の巨大兵器。'),
    'KR': ('폴 클라이머', '일반 공격: 에너지탄     특수 공격: 대형 레이저\n몸통을 땅속에 묻고 머리와 두 손만 내민 채\n기어 나아가는 모덴군의 거대 병기.'),
    'ES': ('FALL CLIMBER', 'ATQ ESTÁND. : Bola de energía     ATQ ESPEC. : Gran láser\nMáquina gigante rebelde que repta con la cabeza\ny las manos sobre el suelo y el cuerpo enterrado.'),
    'PT': ('FALL CLIMBER', 'ATQ. PADR. : Bola de energia   ATQ. ESPEC. : Grande laser\nMáquina gigante rebelde que rasteja com a cabeça\ne as mãos acima do solo e o corpo enterrado.'),
    'RU': ('ФОЛЛ КЛАЙМЕР', 'СТАНД. АТАК: Энергошар  СПЕЦ. АТАК: Большой лазер\nГигантская машина повстанцев ползёт, выставив\nнад землёй голову и руки, а корпус — под землёй.'),
    'FR': ('FALL CLIMBER', "ATT. STAND : Boule d'énergie   ATT. SPÉ : Grand laser\nMachine géante rebelle qui rampe, tête et mains\nhors du sol et le corps enfoui dessous."),
    'DE': ('FALL CLIMBER', 'NORM. ANGR.: Energiekugel  SPEZ. ANGR.: Großer Laser\nRiesenmaschine der Rebellen, die mit Kopf und Händen\nüber dem Boden kriecht, den Rumpf im Boden.'),
    'IT': ('FALL CLIMBER', "ATC STAND.: Sfera d'energia   ATC SPEC.: Grande laser\nMacchina gigante ribelle che striscia con testa e\nmani sopra il suolo e il corpo sepolto."),
    'ZT': ('瀑布攀登者', '普通攻擊：能量彈     特殊攻擊：大型雷射\n將身軀埋入地下、只露出頭部與雙手\n向前爬行的叛軍巨大兵器。'),
    'ZS': ('瀑布攀登者', '普通攻击：能量弹     特殊攻击：大型激光\n将身躯埋入地下、只露出头部与双手\n向前爬行的叛军巨大兵器。'),
}
# R9（用户 2026-11-01）：头像改用用户在原生绿格上画好的构图（handoff/，导出素材见 make_icon_handoff.py）；R3–R8 为代理制作
# （地面以上的头部与两手缩小，45×41、锚点 [−5, −4]）。取格内 x 5–44、y 9–44（构图占满内框下部，上方 4 行为格底色）
USER_ICON = HERE / 'handoff' / 'unit_cell_player_green_50x50 fig.png'
USER_CELL = HERE / 'handoff' / 'unit_cell_player_green_50x50.png'
ICON_BOX = (5, 9, 45, 45)
ICON_SIZE = (ICON_BOX[2] - ICON_BOX[0], ICON_BOX[3] - ICON_BOX[1])
ICON_ANCHOR = [-ICON_BOX[0], -ICON_BOX[1]]


def outer(box, dx=0.0, dy=0.0):
    """不透明范围（左, 上, 右, 下）减去原点后向外取整。"""
    l, t, r, b = box
    return [math.floor(l - dx), math.floor(t - dy), math.ceil(r - dx), math.ceil(b - dy)]


def part_boxes(form):
    """整机部件判定（R4，素材像素）：左上臂 / 左前臂相对肩 / 肘的不透明范围（静止姿势，核心按当前转角转动、右侧镜像），机体组各部件
    （髋、爪、机体、引擎）不透明范围的并集。"""
    a = R.arm_rest(form, 'L')
    out = {}
    for key, pieces, pivot in (('upper_box', ('upper', 'cap'), a['S']), ('lower_box', ('fore',), a['E'])):   # R7：上臂含肘护盖
        bs = []
        for piece in pieces:
            img, tl = a[piece]
            bb = img.getbbox()
            bs.append((tl[0] + bb[0], tl[1] + bb[1], tl[0] + bb[2], tl[1] + bb[3]))
        out[key] = outer((min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)), *pivot)
    boxes = []
    for _, img, tl in R.body_parts(form):
        bb = img.getbbox()
        boxes.append((tl[0] + bb[0], tl[1] + bb[1], tl[0] + bb[2], tl[1] + bb[3]))
    out['body_box'] = outer((min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)))
    return out


def encode_ogg(data, rate, target):
    """PCM 编码为 Ogg Vorbis（libsndfile 分块写入，同钢铁死亡蠕虫生成脚本；写入前以 SFC_SET_VBR_ENCODING_QUALITY 设质量，
    soundfile 0.9 无此参数，经其 cffi 句柄调用 sf_command）。"""
    import soundfile as sf
    with sf.SoundFile(str(target), 'w', samplerate=rate, channels=data.shape[1], format='OGG', subtype='VORBIS') as f:
        q = sf._ffi.new('double*', VORBIS_QUALITY)
        assert sf._snd.sf_command(f._file, 0x1300, q, sf._ffi.sizeof('double')) == 1
        for i in range(0, len(data), 4096):
            f.write(data[i:i + 4096])


def behavior_params(form):
    a = R.arm_rest(form, 'L')
    peek = R.PEEK + (R.RISE if form == 2 else 0)
    mx, my = R.MUZZLE['L']
    t = lambda v: int(round(v * 10))   # noqa: E731
    pre = '' if form == 1 else '2'
    head = (-51, -peek, 102, 39) if form == 1 else (R.CORE_AT[0], R.CORE_AT[1] - peek, 64, 32)
    hand = R.part(104 if form == 1 else 105)
    p = {'form': form, 'neutral_animation': SLOT['neutral' + pre], 'move_animation': SLOT['move' + pre],
         'attack_left_animation': SLOT[f'attack{pre}_l'], 'attack_right_animation': SLOT[f'attack{pre}_r'],
         'change_animation': SLOT['transform'] if form == 1 else SLOT['intro2'], 'charge_animation': SLOT['charge'],
         'laser_animation': SLOT['laser'], 'death_animation': SLOT['death2'], 'orb_animation': SLOT['orb'],
         'hand_x': t(R.HAND_X), 'gait': 120, 'lift': 36, 'bob': 8, 'bob_up': 12, 'bob_high': 16, 'bob_down': 12, 'bob_low': 16,
         'rise': R.RISE, 'dash_speed': 80, 'dash_ahead': 100, 'shot_rise': 30, 'shot_speed': 80, 'shot_distance': 700, 'burst_shots': 20, 'burst_cooldown': 180,
         'special_move_damage_taken': 15,   # R14（用户）：第二形态绝招移动段受到的伤害 −85%（核心 r116）
         'special_laser_damage_taken': 10,   # R15（用户）：第二形态绝招蓄力与激光段受到的伤害 −90%（核心 r117）
         'upper_length': t(a['L1']), 'lower_length': t(a['L2']), 'shoulder_x': t(a['S'][0]), 'shoulder_y': t(a['S'][1]),
         'elbow_x': t(a['E'][0]), 'elbow_y': t(a['E'][1]), 'elbow_sign': a['sign'], 'muzzle_x': t(mx), 'muzzle_y': t(my - peek),
         'hand_width': hand.width, 'hand_height': hand.height, 'head_x': head[0], 'head_y': head[1], 'head_width': head[2],
         'head_height': head[3], **part_boxes(form), 'step_sounds': STEP_SOUNDS,
         'wrist_x': t(a['WH'][0]), 'wrist_y': t(a['WH'][1])}
    if form == 1:
        p['second_form'] = KEY2
    return p


def unit_file(form, anims, textures, icon_rect):
    v = VALUES
    unit = {'key': KEY1 if form == 1 else KEY2, 'base_id': BASE, 'faction': FACTION, 'identity': IDENTITY,
            'shop_price': v['shop_price'], 'available_from_start': True, 'ap': v['ap'],
            'hp_multiplier': v['hp_multiplier'], 'knockback_threshold_multiplier': v['knockback_threshold_multiplier'],
            'damage_multiplier': v['damage_multiplier'], 'normal_damage_multiplier': v['normal_damage_multiplier'],
            'special_damage_multiplier': v['special_damage_multiplier'], **{k: [1, 1] for k in ONES},
            'move_speed_multiplier': v['move_speed_multiplier'], 'production_reference_id': BASE,
            'production_interval_multiplier': v['production_interval_multiplier'], 'status_word_values': v['status_word_values'],
            'attack_attributes': v['attack_attributes'], 'image_direction': 270, 'draw_priority': -90,
            'minimap_marker': [13, 9], 'special_effect_size': [320, 60],
            'icon': {'page': 1, 'rect': list(icon_rect), 'anchor': ICON_ANCHOR},
            'textures': textures, 'sprite_descriptor': DESCRIPTOR,
            'animations': {str(k): anims[k] for k in sorted(anims)},
            'localization': {lang: {'name': n, 'description': d} for lang, (n, d) in LOCALIZATION.items()},
            'tags': ['ms7'], 'behaviors': [{'name': 'fall_climber', 'version': 1, 'params': behavior_params(form)}]}
    if form == 2:
        unit['internal_only'] = True
        unit['status_word_values'] = {**v['status_word_values'], **FORM2_STATUS}
        unit.update(FORM2_VALUES)
    return unit


def make_icon():
    """用户构图中与原生绿格不同的像素（ICON_BOX 内），其余透明（同机动兵、虫穴头像的做法；四角透明度的差异为导出所致，在 ICON_BOX 外）。"""
    a = np.asarray(Image.open(USER_ICON).convert('RGBA'))
    c = np.asarray(Image.open(USER_CELL).convert('RGBA'))
    assert a.shape == c.shape == (50, 50, 4)
    x0, y0, x1, y1 = ICON_BOX
    sa, sc = a[y0:y1, x0:x1], c[y0:y1, x0:x1]
    changed = np.any(sa != sc, axis=2)
    out = np.zeros_like(sa)
    out[changed] = sa[changed]
    out[changed, 3] = 255
    return out


def find_icon_slot(raw, start=(1748, 768)):
    w, h = struct.unpack_from('<HH', raw, 4)
    alpha = np.frombuffer(bytes(raw[8:8 + w * h * 4]), np.uint8).reshape(h, w, 4)[..., 3]
    used = []
    for f in CONTENT.glob('units/*.json'):
        unit = json.loads(f.read_text(encoding='utf-8'))
        icon = unit['icon']
        if unit['key'] not in (KEY1, KEY2) and icon.get('page') == 1 and 'atlas' not in icon:
            used.append(icon['rect'])
    iw, ih = ICON_SIZE
    for y in range(start[1], h - ih, 2):
        for x in range(start[0] if y == start[1] else 0, w - iw, 2):
            if any(not (x + iw + 2 <= u[0] or x >= u[0] + u[2] + 2 or y + ih + 2 <= u[1] or y >= u[1] + u[3] + 2) for u in used):
                continue
            if alpha[y:y + ih, x:x + iw].any():
                continue
            return [x, y, iw, ih]
    raise RuntimeError('no free icon slot')


def write_icon(raw, cell, rect):
    raw = bytearray(raw)
    assert raw[:4] == b'OI\x01\x20'
    w, _ = struct.unpack_from('<HH', raw, 4)
    ax, ay, iw, ih = rect
    for j in range(ih):
        for i in range(iw):
            at = 8 + ((ay + j) * w + ax + i) * 4
            raw[at:at + 4] = bytes(int(v) for v in cell[j, i])
    return bytes(raw)


def main():
    OUT.mkdir(exist_ok=True)
    t = load()
    s = scripts(t)
    page_imgs, rects, words, anims = assemble(t, s)
    hits, atks = bounds()
    report = {'tiles': len(t.items), 'rects': len(rects), 'pages': [list(p.size) for p in page_imgs],
              'colors': [len(set(p.getdata())) for p in page_imgs], 'frames_words': len(words),
              'params1': behavior_params(1), 'params2': behavior_params(2)}
    for i, p in enumerate(page_imgs):
        p.save(OUT / f'page_{i}.png')
    preview(page_imgs, rects, words, anims).save(OUT / 'preview_deck.png')
    icon = make_icon()
    Image.fromarray(icon, 'RGBA').resize((ICON_SIZE[0] * 4, ICON_SIZE[1] * 4), Image.NEAREST).save(OUT / 'icon_x4.png')
    print(json.dumps({k: v for k, v in report.items() if not k.startswith('params')}, ensure_ascii=False))
    if '--preview' in sys.argv:
        (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return
    index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
    for k in (KEY1, KEY2):
        if k not in index['unit_ids']:
            index['unit_ids'][k] = max(index['unit_ids'].values()) + 1
    textures = []
    for i, img in enumerate(page_imgs):
        name = TEX.format(i)
        obm = indexed_obm(img)
        (CONTENT / name).write_bytes(obm)
        index['assets'][name] = hashlib.blake2b(obm, digest_size=32).hexdigest()
        textures.append(name)
    icon_raw = (CONTENT / 'unit_icon_02.obm').read_bytes()
    unit_path = CONTENT / 'units' / FILE1
    if unit_path.exists():
        old = json.loads(unit_path.read_text(encoding='utf-8'))['icon']['rect']
        icon_raw = write_icon(icon_raw, np.zeros((old[3], old[2], 4), np.uint8), old)
        rect = [old[0], old[1], *ICON_SIZE]   # 沿用已登记的位置（R9 由 45×41 改为 40×36）
    else:
        rect = find_icon_slot(icon_raw)
    (CONTENT / 'unit_icon_02.obm').write_bytes(write_icon(icon_raw, icon, rect))   # 该资源的摘要在 content.json 中为 null，保持不变
    desc = {'rects': rects, 'frames': words, 'script_count': SCRIPT_COUNT, 'hit_bounds': hits, 'attack_bounds': atks}
    save_json(CONTENT / DESCRIPTOR, desc)
    save_json(unit_path, unit_file(1, anims, textures, rect))
    save_json(CONTENT / 'units' / FILE2, unit_file(2, anims, textures, rect))
    sounds = list(index.get('sounds', []))
    import ds_sseq
    sf2 = next(DS_SEQ.glob('BANK_*.sf2'))
    for key, seq in SOUNDS.items():                     # libsndfile 每次取随机流序列号，已有文件时不重编（换来源时先删去旧文件）
        target = key.split('.', 1)[1] + '.msdf'
        if not (CONTENT / target).exists():
            data, _ = ds_sseq.render_native(DS_SEQ / (seq + '.mid'), sf2)
            encode_ogg(data, 16000, CONTENT / target)
        entry = {'key': key, 'file': target, 'type': 'se', 'volume': 100}
        at = next((i for i, e in enumerate(sounds) if e['key'] == key), None)
        if at is None:
            sounds.append(entry)
        else:
            sounds[at] = entry
    index['sounds'] = sounds
    save_json(CONTENT / 'content.json', index)
    report.update(unit_ids={k: index['unit_ids'][k] for k in (KEY1, KEY2)}, icon_rect=rect, textures=textures)
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report['unit_ids']), rect, textures)


if __name__ == '__main__':
    main()
