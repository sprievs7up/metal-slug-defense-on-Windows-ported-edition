"""MS7 任务 5 新单位 Energy Pod（中文名「能量弹」）制作为本体单位（2026-11-02；行为 energy_pod v1，行为库 40，核心 r131；R13 起行为 v2，行为库 41，核心 r133）。

设计与用户决定：docs/MS7_ENERGY_POD_2026-11-02.md（第 5.1–5.3 节为 R7 示意动画与被击毁后的调整，第 7 节为做进游戏的方案，第 7.9 节为音效）。
- 两个单位共用一个描述符与图集：组单位 s1xlv.energy_pod（可购买，role 0：出场即生成三颗球并隐去，作为全组的控制者）与
  球单位 s1xlv.energy_pod_ball（内部单位，role 1；三颗为同一种类，颜色在变色时由核心决定）。
- 图像：MS7（DS）素材表 F:\\egg\\MS7\\DS _ DSi - Metal Slug 7 - Enemies - Energy Pod.png（Gussprint 拆图）。帧位置与调色板同
  verification/ms7_epod_20261102/epod_frames.py（连通区域、格线与色块核实，文档第 3 节），此处只保留生成所需的部分。
  球体帧以球心为锚点、单位原点在球的底边中点（球心在原点上方 BALL_CY 素材像素，世界 = × 2），原生瞄准弹瞄准原点上方高度一半处即球心。
- 动作（SLOT）：编队页与单位菜单（0、1：三颗 IDLE 球的三角排列）、隐去（2）、球的待机（3–5：IDLE 往返播放，三颗相位错开 10 tick）、
  ABOUT TO ATTACK（6，原色）、充能循环（7–9：黄、蓝、红调色）、俯冲（10–12：同充能循环，另开攻击框）、收尾（13–15：ELECTRIC ATTACK 收尾 7 帧）、
  WRECKED（16–19：原色、黄、蓝、红球体；第 1 tick 播放警備機器人被击破的音效 202（R14），播完放原生中爆炸 0xff03 与音效 203）；效果：尾迹（20–22）、BUMP（23–25）、电环（26 黄 / 27 蓝）、
  火柱（28，锚点为底边中点）；29 为不播放的音效预载脚本（变色、发射 / 落地、火柱、203）。
- 音效（文档第 7.9 节 R10c，用户确认）：变色 St5_Boss5_Las_Tam、每颗发射与落地 St5_OgUFO_Warp1（NDS 版，F:\\egg\\MS7\\mslug7_sdat_extract
  sequence/00fc-011e，以 artwork/fall_climber_20261101/ds_sseq.py 渲染为 16 kHz 立体声），红球落地另叠 MSXX B4_FLAME。
- 数值（Lv40，基准 192：生命 6000、近距 1500、生产 550 帧、移速 3.0）：每颗球生命 3000（用户），组单位生命 9000（三颗之和，只用于 STATUS 显示，
  战斗中组单位不受伤）；撞击 800（R13 用户：1200 偏高；近距组词 15；目标数词 17 为 999 即穿透）；进入攻击的距离 180（词 6，STATUS 的近距射程）；
  AP 300、价格 200、再出击 20 秒（600 帧）为暂定（文档第 7.8 节建议值）。击退门槛按 AGENTS 第 6.1 节随生命倍率联动（本单位不击退）。
运行：E:\\anaconda3\\python.exe -I artwork/energy_pod_20261102/build_energy_pod.py [--preview]
（--preview 只写 out/；否则另写 community_content/ 的图集、描述符、两个单位文件、音效、unit_icon_02.obm 与 content.json）。
"""
from pathlib import Path
import hashlib
import json
import math
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CONTENT = REPO / 'community_content'
OUT = HERE / 'out'
SHEET = Path(r'F:\egg\MS7\DS _ DSi - Metal Slug 7 - Enemies - Energy Pod.png')
DS_SEQ = Path(r'F:\egg\MS7\mslug7_sdat_extract\sequence\00fc-011e')   # NDS 版音效序列（任务 5 区段，BANK_006.sf2）
MSXX_SE = Path(r'F:\egg\MS7\MSXX-audio-wav\SE')
sys.path.insert(0, str(REPO / 'artwork' / 'fall_climber_20261101'))   # ds_sseq（-I 运行时加入）

_PVZ = REPO / 'artwork' / 'pvz_zombies_20261012' / 'build_pvz_zombies.py'
_src = _PVZ.read_text(encoding='utf-8')
_src = _src.replace("sys.path.insert(0, str(RT / 'packages'))", "").replace("os.add_dll_directory(str(RT / 'native'))", "")
pvz = type(sys)('pvzb')
pvz.__dict__['__file__'] = str(_PVZ)
exec(compile(_src, str(_PVZ), 'exec'), pvz.__dict__)
indexed_obm, save_json, shelf_pack = pvz.indexed_obm, pvz.save_json, pvz.shelf_pack

KEY, BALL_KEY = 's1xlv.energy_pod', 's1xlv.energy_pod_ball'
FILE, BALL_FILE = 'energy_pod.json', 'energy_pod_ball.json'
TEXTURE = 'energy_pod.obm'
DESCRIPTOR = 'energy_pod_descriptor.json'
BASE = 192                     # 侵略者类（BattleAction_Alien）：行动由核心 energy_pod 段接管（同 UNION、Fall Climber）
FACTION, IDENTITY = 1, 'Rebel Army'

# ---------- 素材表（epod_frames.py 的外接框与调色板，含端点） ----------
WHITE, GREEN, GRAY = (255, 255, 255), (0, 248, 0), (192, 192, 192)
IDLE = [(3 + 23 * k, 3, 22 + 23 * k, 22) for k in range(16)]
ABOUT = [(3, 141, 24, 162), (28, 140, 51, 163), (55, 139, 80, 164), (84, 139, 109, 164), (113, 139, 138, 164),
         (142, 139, 167, 164), (171, 139, 196, 164), (200, 140, 223, 163), (227, 141, 248, 162), (252, 140, 275, 163),
         (279, 139, 304, 164), (308, 139, 333, 164), (337, 139, 362, 164), (366, 139, 391, 164), (395, 139, 420, 164),
         (3, 168, 26, 191)]
ELEC = [(3, 220, 28, 245), (32, 219, 59, 246), (63, 209, 110, 256), (114, 201, 177, 264), (181, 198, 250, 267),
        (254, 197, 325, 268), (329, 196, 402, 269), (3, 270, 78, 344), (82, 271, 155, 344),
        (159, 296, 182, 319), (186, 297, 207, 318), (211, 296, 234, 319), (238, 295, 263, 320), (267, 294, 294, 321),
        (298, 293, 327, 322), (331, 298, 350, 317)]
TRAIL = [(3 + 49 * k, 349, 50 + 49 * k, 396) for k in range(8)] + [(3, 398, 50, 445)]
BUMP = [(3 + 49 * k, 447, 50 + 49 * k, 494) for k in range(6)]
FIRE = [(3 + 66 * c, 498 + 66 * r, 66 + 66 * c, 561 + 66 * r) for r in range(4) for c in range(6)] + \
       [(3 + 50 * c, 762, 50 + 50 * c, 809) for c in range(3)]
WRECK_CENTERS = [(24.5, 66.0), (64.5, 64.0), (112.5, 64.0), (163.5, 62.5), (217.0, 61.5), (269.5, 61.5),
                 (323.5, 62.5), (371.5, 62.0), (403.5, 63.5), (19.5, 122.0), (49.5, 123.0), (79.5, 124.0)]
WRECK_BANDS = [((0, 27, 415, 76), range(0, 9)), ((0, 79, 95, 134), range(9, 12))]
POD_NORMAL = ['f0f0f0', 'c8c0b8', 'a8a098', '807870', '605850', '403838', '100000', '68d070',
              '289030', '086818', '003800', 'f0f088', 'f0d810', 'f0b800', 'f09000']
POD_VARIANT = {
    'red': ['f0f0f0', 'd0c8c0', 'b0a098', '987870', '785848', '603818', '501000', 'e89030',
            'd05020', 'b02810', '900000', 'f0d880', 'e8a840', 'e88008', 'e85800'],
    'blue': ['f0f0f0', 'c8c8c8', 'a8a0a8', '807880', '605860', '403840', '101038', '5098e8',
             '3078d0', '1858b8', '0030a0', 'b8e0e8', '90c0e8', '70a8e8', '5098e8'],
    'yellow': ['f0f0f0', 'd0c8c0', 'b0a898', '908870', '786848', '585018', '583000', 'e8d000',
               'd09000', 'b06800', '803800', 'f0f090', 'e8d018', 'e8b000', 'e88800'],
}
FX_NORMAL = ['f0f0f0', 'f0f088', 'f0d810', 'f0b800', 'f09000']
FX_VARIANT = {'red': ['f0f0f0', 'f0d078', 'f0a038', 'f08000', 'f06008'],
              'blue': ['f0f0f0', 'b0d8f0', '88c8f0', '68b0f0', '48a0f0'], 'yellow': FX_NORMAL}
COLORS = ('yellow', 'blue', 'red')      # 颜色号 0–2（核心按此取各色动作与效果；攻击属性 黄 0、蓝 2、红 1）

# ---------- 动作号与尺寸（素材像素；世界 = × 2） ----------
SLOT = {'deck': 0, 'deck2': 1, 'hidden': 2, 'idle': 3, 'about': 6, 'charged': 7, 'dive': 10, 'recover': 13, 'wreck': 16,
        'trail': 20, 'bump': 23, 'ring': 26, 'fire': 28, 'sounds': 29}
SCRIPT_COUNT = 30
BALL_CY = -10            # 球心在单位原点（球的底边中点）上方 10
DECK_CY = -38            # 编队页三角排列的中心高度
DECK_R = 26              # 编队页的排列半径（同战斗中的编队半径 52 世界单位）
IDLE_PHASE = 10          # 三颗球待机的相位差（tick，同示意 pod_frame 的 k × 10）
BOOM_DY = 29             # 原生 0xff03 以底部为原点：放在球心下方 29，火球中心落在残骸处（文档第 5.3 节）
FIRE_DY = 3              # 火柱的底边在地面下方 3（示意 GROUND + 3）
HIT = [-10, -20, 20, 20]     # 球体的受击框与撞击攻击框（原点在底边中点）
ATTACK_FLAGS = 7
SOUND_DEATH = 203            # 原生 B4_EXP3（与 0xff03 一同，同鼹鼠弹被击毁）
SOUND_BREAK = 202            # R14（用户 2026-11-02）：被击破时先播放警備機器人（PATROL ROBOT 127）被击破的音效，再爆炸（203 不变）；
                             # 127 的死亡动作（脚本 10）第一 tick 播放 202（LAB 实测 verification/ms7_epod_20261102/impl/runs/pr2_*）
EFFECT_DEATH = 0xff03
SOUNDS = {   # 键 → (来源, 序列名或文件, 音量)
    's1xlv.epod_charge': ('ds', 'St5_Boss5_Las_Tam', 100),
    's1xlv.epod_warp': ('ds', 'St5_OgUFO_Warp1', 100),
    's1xlv.epod_flame': ('msxx', 'B4_FLAME.wav', 100),
}
VORBIS_QUALITY = 0.8         # 同 Fall Climber 生成脚本

# 数值（Lv40；基准 192 生命 6000、近距 1500、生产 550 帧）。暂定：AP、价格、再出击（文档第 7.8 节建议值，待用户定）
VALUES = {'ap': 300, 'ball_ap': 100, 'shop_price': 200, 'production_interval_multiplier': [12, 11],   # 550 → 600 帧 = 20 秒
          'hp': [3, 2], 'ball_hp': [1, 2], 'near_damage_multiplier': [8, 15],                         # 9000 / 3000；撞击 1500 → 800（R13 用户；R11–R12 为 [4, 5] → 1200）
          'detect_range': 180}
ONES = ('damage_multiplier', 'special_damage_multiplier', 'attack_wait_multiplier', 'attack_range_multiplier', 'knockback_distance_multiplier',
        'ballistic_range_multiplier', 'move_speed_multiplier')
# 行为参数（世界单位 / tick；文档第 7.8 节：示意素材像素 × 2）
PARAMS = {'radius': 52, 'height': 220, 'dive_speed': 140, 'period': 36, 'neutral_period': 216, 'spin_up': 30, 'spin_down': 30,
          'about_ticks': 32, 'charged_hold': 24, 'single_hold': 12, 'launch_gap': 15, 'join_wait': 10, 'regroup_ticks': 20,
          'recover_ticks': 14, 'reattack_wait': 54, 'attack_damage_taken': 20,
          'target_range': 650}   # R13（用户 2026-11-02）：出发时只取离编队中心水平 650 以内的敌人（暂定）

LOCALIZATION = {   # 中文名称为用户所定（2026-11-02）；说明第 2、3 行为用户所定（2026-11-03，“警戒机器人”取原生 127 各语言名称），其余 10 种语言为代理翻译，待校对
    'ZS': ('能量弹', '普通攻击：能量冲撞\n未来莫丁军研发的元素武器。\n其实是拿「警备机器人」图纸改造而来。'),
    'ZT': ('能量彈', '普通攻擊：能量衝撞\n未來莫丁軍研發的元素武器。\n其實是拿「警備機器人」圖紙改造而來。'),
    'EN': ('ENERGY POD', 'STAND. ATK : Energy Ram\nAn elemental weapon developed by the future Morden Army.\nIt was actually rebuilt from the blueprints of the "PATROL ROBOT".'),
    'JP': ('エネルギーポッド', '通常攻撃：エネルギー体当たり\n未来のモーデン軍が開発したエレメント兵器。\n実は「パトロールロボット」の設計図を改造して作られた。'),
    'KR': ('에너지 포드', '일반 공격: 에너지 돌진\n미래의 모덴군이 개발한 원소 병기.\n사실은 "패트롤 로봇"의 설계도를 개조해 만들었다.'),
    'ES': ('CÁPSULA DE ENERGÍA', 'ATQ ESTÁND. : Embestida de energía\nArma elemental desarrollada por el futuro Ejército de Morden.\nEn realidad se hizo modificando los planos del "ROBOT DE PATRULLA".'),
    'PT': ('CÁPSULA DE ENERGIA', 'ATQ. PADR. : Investida de energia\nArma elemental desenvolvida pelo futuro Exército de Morden.\nNa verdade, foi feita a partir dos projetos do "ROBÔ PATRULHEIRO".'),
    'FR': ("CAPSULE D'ÉNERGIE", 'ATT. STAND : Charge d\'énergie\nArme élémentaire développée par la future Armée de Morden.\nElle a en fait été conçue à partir des plans du "PATROUILLE ROBOT".'),
    'DE': ('ENERGIEKAPSEL', 'NORM. ANGR.: Energierammstoß\nElementarwaffe, entwickelt von der Morden-Armee der Zukunft.\nEigentlich aus den Bauplänen des "PATROL ROBOT" umgebaut.'),
    'IT': ('CAPSULA ENERGETICA', 'ATC STAND.: Carica di energia\nArma elementale sviluppata dal futuro Esercito di Morden.\nIn realtà è stata ricavata dai progetti del "PATTUGLIA ROBOT".'),
    'RU': ('ЭНЕРГОКАПСУЛА', 'СТАНД. АТАК: Энергетический таран\nСтихийное оружие, созданное армией Мордена будущего.\nНа самом деле переделано из чертежей "ПАТРУЛЬНЫЙ РОБОТ".'),
}
ICON_SIZE = (46, 43)
ICON_ANCHOR = [-5, -2]


def cmd(op, *v):
    return {'opcode': op, 'values': [int(x) if not isinstance(x, str) else x for x in v]}


def show(key):
    return {'opcode': 0, 'values': [key], 'key': True}


# ---------- 切帧（同 epod_frames.py） ----------
def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


POD_MAP = {k: {_rgb(a): _rgb(b) for a, b in zip(POD_NORMAL, v)} for k, v in POD_VARIANT.items()}
FX_MAP = {k: {_rgb(a): _rgb(b) for a, b in zip(FX_NORMAL, v)} for k, v in FX_VARIANT.items()}
_sheet = Image.open(SHEET).convert('RGB')


def cut(box, bgs):
    x0, y0, x1, y1 = box
    im = _sheet.crop((x0, y0, x1 + 1, y1 + 1)).convert('RGBA')
    a = np.array(im)
    mask = np.zeros(a.shape[:2], bool)
    for c in bgs:
        mask |= (a[..., :3] == c).all(-1)
    a[mask] = 0
    return Image.fromarray(a, 'RGBA')


def recolor(im, table):
    if not table:
        return im
    a = np.array(im)
    out = a.copy()
    for src, dst in table.items():
        m = (a[..., 3] > 0) & (a[..., :3] == src).all(-1)
        out[m, :3] = dst
    return Image.fromarray(out, 'RGBA')


def centered(frames):
    return [(im, im.width / 2, im.height / 2) for im in frames]


def idle():
    return centered([cut(b, {WHITE}) for b in IDLE])


def about(color=None):
    return centered([recolor(cut(b, {WHITE}), POD_MAP.get(color)) for b in ABOUT])


def elec(color=None, erase_pod=False):
    out = []
    for i, b in enumerate(ELEC):
        im = recolor(cut(b, {GREEN, WHITE}), POD_MAP.get(color))
        if erase_pod and 2 <= i <= 8:
            im = _erase_center(im, 13 if i < 5 else 16)
        out.append(im)
    return centered(out)


def _erase_center(im, r):
    a = np.array(im)
    h, w = a.shape[:2]
    cy, cx = (h - 1) / 2, (w - 1) / 2
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.hypot(xx - cx, yy - cy)
    ring = (d >= r + 1) & (d <= r + 3)
    white = np.array(_rgb('f0f0f0'))
    whites = int(((a[..., 3] > 0) & (a[..., :3] == white).all(-1) & ring).sum())
    fill = list(white) + [255] if ring.any() and whites > ring.sum() * 0.6 else [0, 0, 0, 0]
    a[d <= r] = fill
    return Image.fromarray(a, 'RGBA')


def trail(color):
    return centered([recolor(cut(b, {GREEN}), FX_MAP.get(color)) for b in TRAIL])


def bump(color):
    return centered([recolor(cut(b, {GREEN}), FX_MAP.get(color)) for b in BUMP])


def fire():
    return [(im, im.width / 2, im.height) for im in (cut(b, {GRAY, WHITE}) for b in FIRE)]


def wrecked(color=None):
    """WRECKED 12 帧（epod_frames.wrecked）：两行内的 8 连通块各归入质心最近、且不在其左方的球心所在帧，锚点为球心；color 只给球体换色。"""
    px = _sheet.load()
    out = []
    for (x0, y0, x1, y1), ks in WRECK_BANDS:
        seen = set()
        owned = {k: [] for k in ks}
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if (x, y) in seen or px[x, y] == GREEN:
                    continue
                comp, stack = [], [(x, y)]
                seen.add((x, y))
                while stack:
                    a, b = stack.pop()
                    comp.append((a, b))
                    for da in (-1, 0, 1):
                        for db in (-1, 0, 1):
                            q = (a + da, b + db)
                            if x0 <= q[0] <= x1 and y0 <= q[1] <= y1 and q not in seen and px[q] != GREEN:
                                seen.add(q)
                                stack.append(q)
                mx = sum(p[0] for p in comp) / len(comp)
                my = sum(p[1] for p in comp) / len(comp)
                right = [k for k in ks if WRECK_CENTERS[k][0] >= mx - 12] or list(ks)
                k = min(right, key=lambda k: (WRECK_CENTERS[k][0] - mx) ** 2 + (WRECK_CENTERS[k][1] - my) ** 2)
                owned[k] += comp
        table = POD_MAP.get(color)
        for k in ks:
            cx, cy = WRECK_CENTERS[k]
            pts = owned[k]
            ax, ay = min(p[0] for p in pts), min(p[1] for p in pts)
            im = Image.new('RGBA', (max(p[0] for p in pts) - ax + 1, max(p[1] for p in pts) - ay + 1))
            ip = im.load()
            for a, b in pts:
                c = px[a, b]
                if table and c in table and (a - cx) ** 2 + (b - cy) ** 2 <= 10.5 ** 2:
                    c = table[c]
                ip[a - ax, b - ay] = c + (255,)
            out.append((im, cx - ax + 0.5, cy - ay + 0.5))
    return out


def trim(frames):
    """去掉透明的外边（效果帧多在 48 / 64 见方的格中），锚点随之平移。"""
    out = []
    for im, ax, ay in frames:
        bb = im.getbbox()
        if bb is None:
            out.append((im.crop((0, 0, 1, 1)), ax, ay))
        else:
            out.append((im.crop(bb), ax - bb[0], ay - bb[1]))
    return out


# ---------- 动作 ----------
class Table:
    def __init__(self):
        self.rows = [[0, 0, 0, 0, 0]]

    def add(self, r):
        r = [int(v) for v in r]
        if r not in self.rows:
            self.rows.append(r)
        return self.rows.index(r)


def build():
    tiles, tile_of, rect_keys, frame_keys = [], {}, [], []

    def rect(im, ax, ay, cx, cy):
        key = im.tobytes() + bytes(str(im.size), 'ascii')
        if key not in tile_of:
            tile_of[key] = len(tiles)
            tiles.append(im)
        X, Y = math.floor(cx - ax + 0.5), math.floor(cy - ay + 0.5)   # 左上角
        k = (tile_of[key], -X, -Y)
        if k not in rect_keys:
            rect_keys.append(k)
        return rect_keys.index(k)

    def frame(*parts):
        """parts 为 (帧, 放置点 x, y)：帧的锚点放在该点，先列者画在下面。"""
        k = tuple(rect(im, ax, ay, cx, cy) for (im, ax, ay), cx, cy in parts)
        if k not in frame_keys:
            frame_keys.append(k)
        return frame_keys.index(k)

    hits, atks = Table(), Table()
    hb = hits.add(HIT + [0])
    ab = atks.add(HIT + [ATTACK_FLAGS])
    s = {k: [cmd(0, -1), cmd(1, 1), cmd(21)] for k in range(SCRIPT_COUNT)}
    I, A = idle(), about()
    seq = list(range(16)) + list(range(14, 0, -1))   # 往返播放 1-2-…-16-…-2（项目规则）

    def ball(fr):
        return show(frame((fr, 0, BALL_CY)))
    # 编队页与单位菜单（组单位未生成三颗球时）：三颗 IDLE 球的三角排列（顶角朝上，同战斗中的起始排列）；受击框为一颗球
    # （原生 setObjectSize 取第一个带 op3 的脚本，两个单位共用此宽度与高度）
    pts = [(DECK_R * math.cos(math.pi / 2 + 2 * math.pi * k / 3), DECK_CY - DECK_R * math.sin(math.pi / 2 + 2 * math.pi * k / 3))
           for k in range(3)]
    deck = []
    for j in range(len(seq)):
        deck += [show(frame(*[(I[seq[(j + k * IDLE_PHASE // 2) % len(seq)]], x, y) for k, (x, y) in enumerate(pts)])), cmd(1, 2)]
    s[SLOT['deck']] = [cmd(3, hb), cmd(4, 0)] + deck + [cmd(5)]
    s[SLOT['deck2']] = list(s[SLOT['deck']])
    s[SLOT['hidden']] = [cmd(3, 0), cmd(4, 0), cmd(0, -1), cmd(1, 30000), cmd(5)]
    for k in range(3):
        rot = seq[k * IDLE_PHASE // 2:] + seq[:k * IDLE_PHASE // 2]
        s[SLOT['idle'] + k] = [cmd(3, hb), cmd(4, 0)] + sum(([ball(I[i]), cmd(1, 2)] for i in rot), []) + [cmd(5)]
    s[SLOT['about']] = [cmd(3, hb), cmd(4, 0)] + sum(([ball(f), cmd(1, 2)] for f in A), []) + [cmd(21)]
    EN = elec()
    for c, color in enumerate(COLORS):
        C = about(color)
        loop = sum(([ball(f), cmd(1, 2)] for f in C), [])
        s[SLOT['charged'] + c] = [cmd(3, hb), cmd(4, 0)] + loop + [cmd(5)]
        s[SLOT['dive'] + c] = [cmd(3, hb), cmd(4, ab)] + loop + [cmd(5)]   # 攻击框在整段俯冲与反弹中保持（一个攻击 ID）
        rec = elec(color)[9:13] + EN[13:16]
        s[SLOT['recover'] + c] = [cmd(3, hb), cmd(4, 0)] + sum(([ball(f), cmd(1, 2)] for f in rec), []) + [cmd(21)]
        s[SLOT['trail'] + c] = sum(([show(frame((f, 0, BALL_CY))), cmd(1, 1)] for f in trim(trail(color))), []) + [cmd(0, -1), cmd(1, 1), cmd(21)]
        s[SLOT['bump'] + c] = sum(([show(frame((f, 0, BALL_CY))), cmd(1, 2)] for f in trim(bump(color))), []) + [cmd(0, -1), cmd(1, 1), cmd(21)]
    for c, color in enumerate((None,) + COLORS):
        W = wrecked(color)
        # 被击破音效放在第 1 tick（动作由核心以嵌套调用切换，脚本第一 tick 的 op23 会使嵌套调用中止）
        s[SLOT['wreck'] + c] = ([cmd(3, 0), cmd(4, 0), ball(W[0]), cmd(1, 1), cmd(23, SOUND_BREAK), cmd(1, 1)]
                                + sum(([ball(f), cmd(1, 2)] for f in W[1:]), [])
                                + [cmd(12, EFFECT_DEATH, -1, 0, BALL_CY + BOOM_DY), cmd(23, SOUND_DEATH), cmd(0, -1), cmd(1, 2), cmd(21)])
    for k, color in enumerate((None, 'blue')):
        ring = trim(elec(color, erase_pod=True)[2:9])
        s[SLOT['ring'] + k] = sum(([show(frame((f, 0, BALL_CY))), cmd(1, 2)] for f in ring), []) + [cmd(0, -1), cmd(1, 1), cmd(21)]
    s[SLOT['fire']] = sum(([show(frame((f, 0, FIRE_DY))), cmd(1, 1)] for f in trim(fire())), []) + [cmd(0, -1), cmd(1, 1), cmd(21)]
    # 不播放的脚本：登记全部音效，随单位开战预载（同 UNION 脚本 179 的 253）
    s[SLOT['sounds']] = [cmd(0, -1)] + [{'opcode': 23, 'values': [k]} for k in SOUNDS] + [cmd(23, SOUND_DEATH), cmd(1, 1), cmd(21)]
    return s, tiles, (rect_keys, frame_keys), hits.rows, atks.rows


def assemble(s, tiles, keys):
    rect_keys, frame_keys = keys
    page, xy = shelf_pack(tiles)
    rects, words, start = [], [], []
    for t, ax, ay in rect_keys:
        w, h = tiles[t].size
        x, y = xy[t]
        rects.append([x, y, w, h, ax, ay, 0, 0])
    for k in frame_keys:
        start.append(len(words))
        words += [len(k)] + list(k)
    anims = {}
    for slot, cmds in s.items():
        anims[slot] = [cmd(0, start[c['values'][0]]) if c.get('key') else c for c in cmds]
    return page, rects, words, anims


# ---------- 头像 ----------
def icon_cell():
    """三颗 IDLE 球的三角排列（顶角朝上）置于 46×43 格中。"""
    iw, ih = ICON_SIZE
    cell = Image.new('RGBA', (iw, ih))
    I = idle()
    for k, (cx, cy) in enumerate(((23, 11), (12, 31), (34, 31))):
        im, ax, ay = I[(k * 5) % 16]
        cell.alpha_composite(im, (int(cx - ax), int(cy - ay)))
    return np.array(cell)


def find_icon_slot(raw, start=(1748, 768)):
    w, h = struct.unpack_from('<HH', raw, 4)
    alpha = np.frombuffer(bytes(raw[8:8 + w * h * 4]), np.uint8).reshape(h, w, 4)[..., 3]
    used = []
    for f in CONTENT.glob('units/*.json'):
        unit = json.loads(f.read_text(encoding='utf-8'))
        icon = unit['icon']
        if unit['key'] not in (KEY, BALL_KEY) and icon.get('page') == 1 and 'atlas' not in icon:
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


def encode_ogg(data, rate, target):
    """PCM 编码为 Ogg Vorbis（同 Fall Climber 生成脚本：libsndfile 分块写入，写入前设 VBR 质量）。"""
    import soundfile as sf
    with sf.SoundFile(str(target), 'w', samplerate=rate, channels=data.shape[1], format='OGG', subtype='VORBIS') as f:
        q = sf._ffi.new('double*', VORBIS_QUALITY)
        assert sf._snd.sf_command(f._file, 0x1300, q, sf._ffi.sizeof('double')) == 1
        for i in range(0, len(data), 4096):
            f.write(data[i:i + 4096])


# ---------- 审阅图（只按根层近似） ----------
def strip(page, rects, words, anims, slot, ticks, scale=3):
    W, H, oy = 120, 150, 110
    cells = []
    for t in range(ticks):
        canvas = Image.new('RGBA', (W, H), (70, 70, 90, 255))
        d = ImageDraw.Draw(canvas)
        d.line([(0, oy), (W, oy)], fill=(150, 110, 60, 255))
        frame, clock = -1, 0
        for c in anims[slot]:
            op, v = c['opcode'], c['values']
            if op == 0:
                frame = v[0]
            elif op == 1:
                if clock + v[0] > t:
                    break
                clock += v[0]
            elif op in (5, 21):
                break
        for n in (words[frame + 1:frame + 1 + words[frame]] if frame >= 0 else ()):
            r = rects[n]
            canvas.alpha_composite(page.crop((r[0], r[1], r[0] + r[2], r[1] + r[3])), (W // 2 - r[4], oy - r[5]))
        d.text((2, 2), f'{slot}:{t}', fill=(255, 255, 0, 255))
        cells.append(canvas.resize((W * scale, H * scale), Image.NEAREST))
    cols = 10
    rows = (len(cells) + cols - 1) // cols
    out = Image.new('RGBA', (cols * W * scale, rows * H * scale), (0, 0, 0, 255))
    for k, c in enumerate(cells):
        out.paste(c, ((k % cols) * W * scale, (k // cols) * H * scale))
    return out


def unit_file(role, anims, rect):
    v = VALUES
    ball = role == 1
    hp = v['ball_hp'] if ball else v['hp']
    unit = {'key': BALL_KEY if ball else KEY, 'base_id': BASE, 'faction': FACTION, 'identity': IDENTITY,
            'shop_price': v['shop_price'], 'available_from_start': True, 'ap': v['ball_ap'] if ball else v['ap'],
            'hp_multiplier': hp, 'knockback_threshold_multiplier': hp,                  # 第 6.1 节联动
            'near_damage_multiplier': v['near_damage_multiplier'],
            **{k: [1, 1] for k in ONES},
            'production_reference_id': BASE, 'production_interval_multiplier': v['production_interval_multiplier'],
            # 词 6：组单位为进入攻击的距离（STATUS 的近距射程）；球为 0（原生不为球预约近距攻击状态，撞击由核心以攻击组 30 结算）
            'status_word_values': {'6': 0 if ball else v['detect_range'], '7': 0, '17': 999, '36': 0},
            'image_direction': 90,
            'icon': {'page': 1, 'rect': list(rect), 'anchor': ICON_ANCHOR},
            'textures': [TEXTURE], 'sprite_descriptor': DESCRIPTOR,
            'animations': {str(k): anims[k] for k in sorted(anims)},
            'localization': {lang: {'name': n, 'description': t} for lang, (n, t) in LOCALIZATION.items()},
            'tags': ['ms7'],
            'behaviors': [{'name': 'energy_pod', 'version': 2, 'params': dict(
                {'role': role, 'ball_unit': BALL_KEY, 'deck_animation': SLOT['deck'], 'hidden_animation': SLOT['hidden'],
                 'idle_animation': SLOT['idle'], 'about_animation': SLOT['about'], 'charged_animation': SLOT['charged'],
                 'dive_animation': SLOT['dive'], 'recover_animation': SLOT['recover'], 'wreck_animation': SLOT['wreck'],
                 'trail_effect': SLOT['trail'], 'bump_effect': SLOT['bump'], 'ring_effect': SLOT['ring'], 'fire_effect': SLOT['fire'],
                 'charge_sound': 's1xlv.epod_charge', 'launch_sound': 's1xlv.epod_warp', 'flame_sound': 's1xlv.epod_flame'},
                **PARAMS)},
                {'name': 'no_knockback', 'version': 1, 'params': {}}]}
    if ball:
        unit['internal_only'] = True
    return unit


def main():
    OUT.mkdir(exist_ok=True)
    s, tiles, keys, hits, atks = build()
    page, rects, words, anims = assemble(s, tiles, keys)
    desc = {'rects': rects, 'frames': words, 'script_count': SCRIPT_COUNT, 'hit_bounds': hits, 'attack_bounds': atks}
    cell = icon_cell()
    Image.fromarray(cell, 'RGBA').resize((ICON_SIZE[0] * 4, ICON_SIZE[1] * 4), Image.NEAREST).save(OUT / 'icon_x4.png')
    page.save(OUT / 'atlas.png')
    for name, slot, ticks in (('deck', 0, 30), ('idle', 3, 30), ('about', 6, 34), ('charged_red', 9, 32), ('recover_blue', 14, 16),
                              ('wreck_yellow', 17, 28), ('trail_red', 22, 10), ('bump_blue', 24, 13), ('ring_y', 26, 15),
                              ('fire', 28, 28)):
        strip(page, rects, words, anims, slot, ticks).save(OUT / f'strip_{slot:02d}_{name}.png')
    report = {'tiles': len(tiles), 'rects': len(rects), 'frames': len(keys[1]), 'hit_bounds': hits, 'attack_bounds': atks,
              'atlas': list(page.size), 'colors': len(set(page.getdata()))}
    if '--preview' in sys.argv:
        (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
        return
    index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
    for k in (KEY, BALL_KEY):
        if k not in index['unit_ids']:
            index['unit_ids'][k] = max(index['unit_ids'].values()) + 1
    obm = indexed_obm(page)
    (CONTENT / TEXTURE).write_bytes(obm)
    index['assets'][TEXTURE] = hashlib.blake2b(obm, digest_size=32).hexdigest()
    sounds = list(index.get('sounds', []))
    import ds_sseq
    sf2 = next(DS_SEQ.glob('BANK_*.sf2'))
    for key, (src, name, volume) in SOUNDS.items():     # libsndfile 每次取随机流序列号，已有文件时不重编（换来源时先删去旧文件）
        target = key.split('.', 1)[1] + '.msdf'
        if not (CONTENT / target).exists():
            if src == 'ds':
                data, _ = ds_sseq.render_native(DS_SEQ / (name + '.mid'), sf2)
                encode_ogg(data, 16000, CONTENT / target)
            else:
                import soundfile as sf
                data, rate = sf.read(str(MSXX_SE / name), always_2d=True)
                encode_ogg(data.astype(np.float32), rate, CONTENT / target)
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
    save_json(unit_path, unit_file(0, anims, rect))
    save_json(CONTENT / 'units' / BALL_FILE, unit_file(1, anims, rect))
    save_json(CONTENT / 'content.json', index)
    report.update(unit_ids={k: index['unit_ids'][k] for k in (KEY, BALL_KEY)}, icon_rect=rect, obm_bytes=len(obm))
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('hit_bounds', 'attack_bounds')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
