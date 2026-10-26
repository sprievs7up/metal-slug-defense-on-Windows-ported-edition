"""MS7 / MSXX 任务 2 首领 Crablops 绝招放出的鼹鼠弹（Mole Missile）制作为本体单位（2026-10-26；行为 mole_missile v1，核心 r97；
R1 行为 v2，核心 r98）。

核查与方案：docs/ms7/MS7_MOLE_MISSILE_CHECK_2026-10-26.md（用户 2026-10-26 按第 6 节 D1–D11 的建议值实施）。
R1（用户 2026-10-26 逻辑图 F:\\MSD宣传\\1.png：检测到前方敌人后钻出、以很小的前倾角高高跃起、悬停索敌、冲向敌方自爆，冲刺中索敌，
未被击落则必中；目标在途中死亡时沿原路径飞行至触地爆炸；高处难以被击中、生命低不一定是弱点，同原作）：检测距离（状态词 7）300；
升起 15 tick，机体重心升到离地 HOVER_Y、前移 RISE_DRIFT（约 6°）；冲刺动作以弹体为原点，核心在冲刺开始时把单位移到悬停点
（launch_forward / launch_height）并锁定目标、追踪俯冲（dash_speed 120）；爆炸框以弹头为中心。下列 R0 说明中的“普攻距离 120”
“竖直升起 12 tick”“水平飞行、开头下降”已由 R1 取代。
- 图像：MS7（DS）素材表 F:\\egg\\MS7\\DS _ DSi - Metal Slug 7 - Enemies - Mole Missle.png（Gussprint 拆图）原色（MSD 原生
  CRABLOPS 的鼹鼠弹图集 moggle Missile_1_out.obm 与素材表同色）。素材朝左（钻头向左），image_direction 270。
  切帧同 verification/mole_missile_20261025/sheet_frames.py：每帧在 (128,128,255) 底色框内，框外为白色，共 66 块（3 块为调色板样条）。
- 动作（录像核对 verification/mole_missile_20261025/ref/：MSXX 13:43–13:52、MS7 DS 任务 2 262–265 秒；30 tick = 1 秒）：
  出击后钻入（7）→ 地下潜行（8，地面只见小土堆，无受击框）→ 敌方前线进入普攻距离（状态词 7 = 120）时钻出（9：土堆隆起 3 tick、
  竖直升起 12 tick、倾转 12 tick、悬停调整位置并与蓝色版交替闪烁 18 tick，合计 45 tick）→ 冲刺（10，水平飞行，核心按 dash_speed
  移动，开头 dash_drop_ticks 内下降 dash_drop，攻击框接触敌方单位或据点即爆炸）→ 爆炸（11 / 绝招 12，核心预约状态 140；伤害取进入
  动作时的攻击组，普攻词 22、绝招词 29；一个攻击 ID，每个目标只结算一次）。钻出后生命耗尽为 13（不造成伤害）。绝招（状态 50）在地下
  时原处钻出，之后同普攻，爆炸范围长宽各 1.5 倍。
- 效果：土堆与爆炸为独立效果（op12 [效果号, 绘制优先级, x, y]；0xff00 + n 为原生共用效果 402 的动画 n）。
- 悬停喷焰（R2，用户 2026-10-26：素材表的心形与月牙形火焰是悬停时的火焰，原作冲刺没有分开的尾迹）：悬停帧 6 + k 与第 k 对喷焰
  （心形 22 + 2k、月牙形 23 + 2k）组成同一帧（喷焰在下），喷焰宽端接在机体尾端喷口，逐 tick 心形 / 月牙形交替；冲刺不再放尾焰粒子。
- 位置：精灵坐标（世界 = × 2），原点为地面上的单位位置，y 向下为正。机体（去掉尾焰颜色的像素）重心在悬停时位于 (0, −HOVER_Y)；
  同一姿态的帧逐像素配准（同色像素数最多），不同姿态之间按机体重心衔接；蓝色版按轮廓与常色版配准。
- 受击框贴合机体（尾焰与蓝色描边不计）；地下与升起中在地面以下的部分不设受击框（升起时核心按地面裁切绘制）。
运行：E:\\anaconda3\\python.exe -I artwork/mole_missile_20261026/build_mole_missile.py [--preview]
（--preview 只写 out/；否则另写 community_content/ 的图集、描述符、单位文件、音效、unit_icon_02.obm 与 content.json）。
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CONTENT = REPO / 'community_content'
OUT = HERE / 'out'
SHEET = Path(r'F:\egg\MS7\DS _ DSi - Metal Slug 7 - Enemies - Mole Missle.png')
MSXX_SE = Path(r'F:\egg\MS7\MSXX-audio-wav\SE')

_PVZ = REPO / 'artwork' / 'pvz_zombies_20261012' / 'build_pvz_zombies.py'
_src = _PVZ.read_text(encoding='utf-8')
_src = _src.replace("sys.path.insert(0, str(RT / 'packages'))", "").replace("os.add_dll_directory(str(RT / 'native'))", "")
pvz = type(sys)('pvzb')
pvz.__dict__['__file__'] = str(_PVZ)
exec(compile(_src, str(_PVZ), 'exec'), pvz.__dict__)
indexed_obm, save_json, shelf_pack = pvz.indexed_obm, pvz.save_json, pvz.shelf_pack

KEY = 's1xlv.mole_missile'
FILE = 'mole_missile.json'
TEXTURE = 'mole_missile.obm'
DESCRIPTOR = 'mole_missile_descriptor.json'
BASE = 133                     # SPECIAL FORCE (RIDER)（BattleAction_Bike_P）：冲撞自爆的原生流程
FACTION, IDENTITY = 1, 'Rebel Army'   # 同 CRABLOPS 239（验证时读取数据行 +0x378 核对）
FLAME = {(96, 192, 240), (160, 232, 240), (240, 240, 240)}    # 常色帧中的尾焰与白色光晕（不计入机体）
EMERGE_SOUND = ('s1xlv.mole_emerge', 'EXPF1.wav', 100)   # 钻出音效：用户 2026-10-26 指定 MSXX EXPF1（sound test 134）；R2 以前为 ST2_MOGURA

# 素材表各组（切帧次序：按行，行内按 x）
RISE = (0, 1)
TILT = (2, 3, 4, 5)
HOVER = tuple(range(6, 14))
HOVER_BLUE = tuple(range(14, 22))
PUFF_BIG = (22, 24, 26, 28, 30, 32, 34, 36)      # 悬停喷焰（心形），与悬停帧 HOVER 逐一对应
PUFF_RING = (23, 25, 27, 29, 31, 33, 35, 37)     # 悬停喷焰（月牙形）
DASH = (38, 39, 40, 42)
DASH_BLUE = (41, 43, 44, 45)            # 与 DASH 同形（同尺寸）的蓝色版
# 冲刺 4 帧的相对位置取 MSA 图集 moggle_Missile_1_out.obm 的锚点（CRABLOPS 239 矩形 258–261：(24,19)、(24,22)、(24,24)、(24,13)，
# 同一像素画，逐像素一致 ≥ 99%）；逐像素配准对 39、42 各差 1 像素（报告 reg_*_to_38）
DASH_MSA = {39: (0, -3), 40: (0, -5), 42: (0, 6)}
MOUND = (55, 56, 57, 58, 49, 50, 51, 52, 53, 54, 59, 60)   # 土堆：由小变大再变小（共 12 帧）
TRACE = (61, 62, 63, 64)                 # 扁平的土痕
HOLE = 65             # 地面的坑：用户 2026-10-26 要求去掉（多余），不使用

# 尺寸与时长（精灵坐标 / tick）
HOVER_Y = 80          # R1：悬停时机体重心离地高度（用户 2026-10-26 逻辑图：高高跃起后悬停，难被地面单位打中，同原作）
NEUTRAL_Y = 34        # 单位菜单待机与编队页的悬停高度（只用于显示）
RISE_DRIFT = 11       # R1：升起中前移的距离（很小的前倾角，约 6°）
RISE_FROM = 26        # 升起开始时机体重心在地面以下的深度（整体在地下，按地面裁切）
BULGE_T, RISE_T, TILT_STEP, ADJUST_STEP = 3, 15, 3, 2
ADJUST = (6, 7, 8, 9, 10, 11, 12, 13, 11)   # 悬停调整位置，奇数步为蓝色版（录像：钻出后约 0.5–1 秒原地闪烁再冲刺）
# 单位菜单待机：悬停帧往返播放（1 2 3 4 5 4 3 2 1 …，同猎人待机的往返；用户 2026-10-27），此前为 6–10 单向循环，第 10 帧跳回第 6 帧
NEUTRAL_ORDER = (6, 7, 8, 9, 10, 9, 8, 7)
DASH_STEP = 2
DASH_SPEED = 120      # 世界单位 × 10 / tick（R1：追踪俯冲路程变长，取每 tick 12，约 1 秒命中；首版按录像取 9）
BLAST = (80, 80)      # 普攻爆炸攻击框（同原生鼹鼠弹爆炸攻击框 8：宽 80、高 80 脚本单位；R1 起以弹头为中心）
BLAST_SP = (120, 120) # 绝招：长宽各 1.5 倍
BLAST_T = 4           # 爆炸攻击框开启 tick
ATTACK_FLAGS = 7
EFFECT_BLAST = 0xff17    # 原生共用效果：MSD CRABLOPS 鼹鼠弹（BulletAction_CrabMecha_Mogura 状态 140）的爆炸
EFFECT_DEATH = 0xff04    # 原生共用效果：SPECIAL FORCE (RIDER) 被击毁时的爆炸
SOUND_BLAST = 202        # 原生鼹鼠弹爆炸音效（Mogura 状态 140）
SOUND_DEATH = 203        # 原生 B4_EXP3

SLOT = {'deck': 0, 'deck2': 1, 'neutral': 6, 'burrow': 7, 'under': 8, 'emerge': 9, 'dash': 10,
        'blast': 11, 'blast_sp': 12, 'death': 13, 'mound_fx': 14}
SCRIPT_COUNT = SLOT['mound_fx'] + 1
FLAME_OVERLAP = 2     # 喷焰宽端伸入喷口的深度（精灵像素，喷焰画在机体之下）

VALUES = {   # 用户 2026-10-26 采用的建议值（文档第 6 节 D2、D10）；R4（用户 2026-10-26 指定）：AP 120、再出击 12 秒；
             # R5（用户 2026-10-26：容易被集火）：生命 2000、普攻 2400、绝招 3600（R4 为 1200 / 2200 / 3300）；R6（用户 2026-10-26）：生命 3000
    'ap': 120, 'shop_price': 150,
    'hp_multiplier': [10, 9],                     # 133 Lv40 2700 → 3000（R6；R5 20/27 → 2000，R4 4/9 → 1200，初版 2/3 → 1800）
    'knockback_threshold_multiplier': [10, 9],    # 第 6.1 节联动（原生 −1 不缩放；本单位不击退）
    'damage_multiplier': [4, 3],                  # 普攻 1800 → 2400（R5；R4 11/9 → 2200，初版 10/3 → 6000）
    'special_damage_multiplier': [45, 43],        # 绝招 2580 → 2700，再 × 4/3 = 3600（普攻的 1.5 倍；初版 × 10/3 = 9000）
    'move_speed_multiplier': [10, 11],            # 3.3 → 3.0
    'production_interval_multiplier': [3, 4],    # 480 → 360 tick = 12 秒（R4；初版 15/16 → 450）
    'status_word_values': {'6': 0, '7': 300, '24': 999, '31': 999, '35': 300, '36': 150},   # R1：检测距离 120 → 300（暂定）
    'attack_attributes': {'normal': 2, 'special': 2},   # 爆炸
}
ONES = ('attack_wait_multiplier', 'attack_range_multiplier', 'knockback_distance_multiplier', 'ballistic_range_multiplier')

LOCALIZATION = {   # 名称为 MSA 官方译名（鼹鼠弹 / 鼴鼠彈 / モグラ弾 / 모구라탄 / Mole Missiles）；简体 / 繁体说明为用户文本（2026-10-26）。
    # 其余 9 种语言（2026-10-26 按用户要求随中文说明重写）：第 1 行取 MSA 同一对攻击（自爆 / 自爆・大）的官方文本（m_string_unit_info 第 43 行，
    # 俄语取第 39 行），“未来叛军”取 MSA 各语言的译法，第 2、3 行为代理按中文说明翻译，待校对
    'EN': ('MOLE MISSILE', 'STAND. ATK : Self-Destruct     SPEC. ATK : Massive Self-Destruct\nA drilling missile developed by the future Rebel Army.\nIt silently advances to the front line, then explodes.'),
    'JP': ('モグラ弾', '通常攻撃：自爆     特殊攻撃：自爆・大\n未来のモーデン軍が開発した掘削ミサイル。\n音もなく前線まで進み、爆発する。'),
    'KR': ('모구라탄', '일반 공격: 자폭     특수 공격: 대규모 자폭\n미래의 모덴군이 개발한 굴착 미사일.\n소리 없이 전선까지 나아가 폭발한다.'),
    'ES': ('MISIL TOPO', 'ATQ ESTÁND. : Autodestruc.     ATQ ESPEC. : Autodestruc. masiva\nMisil perforador desarrollado por el Ejército Rebelde del futuro.\nAvanza sigilosamente hasta el frente y explota.'),
    'PT': ('MÍSSIL TOUPEIRA', 'ATQ. PADR. : Autodestruição   ATQ. ESPEC. : Autodestruição Massiva\nMíssil perfurador desenvolvido pelo Exército Rebelde do futuro.\nAvança silenciosamente até a linha de frente e explode.'),
    'RU': ('РАКЕТА-КРОТ', 'СТАНД. АТАК: Самоликв. СПЕЦ. АТАК: Массивн. Самоликв.\nБуровая ракета, созданная армией повстанцев будущего.\nБесшумно продвигается к линии фронта и взрывается.'),
    'FR': ('MISSILE TAUPE', 'ATT. STAND : Autodestruction   ATT. SPÉ : Autodestruction massive\nMissile foreur développé par l\'armée rebelle du futur.\nIl avance en silence jusqu\'à la ligne de front, puis explose.'),
    'DE': ('MAULWURFSRAKETE', 'NORM. ANGR.: Explosion SPEZ. ANGR.: Große Explosion\nBohrrakete, entwickelt von der Rebellenarmee der Zukunft.\nRückt lautlos bis zur Front vor und explodiert.'),
    'IT': ('MISSILE TALPA', 'ATC STAND.: Autodistruzione   ATC SPEC.: Potente Autodistruzione\nMissile perforante sviluppato dall\'esercito ribelle del futuro.\nAvanza silenziosamente fino al fronte, poi esplode.'),
    'ZT': ('鼴鼠彈', '普通攻擊：自爆     特殊攻擊：自爆（大）\n未來叛軍研製的鑽地飛彈。\n悄無聲息地前進至前線然後爆炸。'),   # 用户 2026-10-26 文本（简体）的逐字转写
    'ZS': ('鼹鼠弹', '普通攻击：自爆     特殊攻击：自爆（大）\n未来叛军研制的钻地飞弹。\n悄无声息地前进至前线然后爆炸。'),   # 用户 2026-10-26 文本
}
ICON_SIZE = (46, 43)
ICON_ANCHOR = [-5, -2]


def cmd(op, *v):
    return {'opcode': op, 'values': [int(x) for x in v]}


def show(key):
    """op0（值为矩形号，写出时换为帧表偏移）。"""
    return {'opcode': 0, 'values': [key], 'key': True}


END = [cmd(0, -1), cmd(1, 1), cmd(21)]


# ---------- 切帧 ----------
def load_frames():
    a = np.array(Image.open(SHEET).convert('RGB')).astype(int)
    white = (a == 255).all(-1)
    bg = white | (a == [128, 128, 255]).all(-1)
    lab, _ = ndimage.label(~white)
    out = []
    for sl in ndimage.find_objects(lab):
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        if y0 >= 385:      # 拆图者署名与截图
            continue
        ys, xs = np.nonzero(~bg[y0:y1, x0:x1])
        if len(ys) == 0:
            continue
        bx0, by0, bx1, by1 = x0 + xs.min(), y0 + ys.min(), x0 + xs.max() + 1, y0 + ys.max() + 1
        alpha = ~bg[by0:by1, bx0:bx1]
        img = np.zeros(alpha.shape + (4,), np.uint8)
        img[..., :3] = a[by0:by1, bx0:bx1]
        img[..., 3] = alpha * 255
        img[~alpha] = 0
        out.append({'box': (int(x0), int(y0)), 'sheet': (int(bx0), int(by0)), 'img': img})
    out.sort(key=lambda f: (f['box'][1] // 8, f['box'][0]))
    assert len(out) == 66, len(out)
    return out


def body_mask(img):
    m = img[..., 3] > 0
    for c in FLAME:
        m &= ~(img[..., :3] == c).all(-1)
    return m


def centroid(mask):
    ys, xs = np.nonzero(mask)
    return float(xs.mean()), float(ys.mean())


def bbox(mask):
    ys, xs = np.nonzero(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def register(a, b, mode, R=10):
    """b 相对 a 的平移 (dx, dy)：b 的像素 (x, y) 与 a 的 (x + dx, y + dy) 重合。
    'color'：两帧机体像素同色的数目最多（同一姿态、只差尾焰或脚）；'shape'：a 为蓝色帧（多一圈描边），b 为常色帧，
    b 的不透明像素落在 a 轮廓内的数目减去落在轮廓外（含超出 a 的范围）的两倍。"""
    best = None
    ha, wa = a.shape[:2]
    hb, wb = b.shape[:2]
    nb_all = int((b[..., 3] > 0).sum())
    for dy in range(-R, ha - hb + R + 1):
        for dx in range(-R, wa - wb + R + 1):
            ox0, oy0, ox1, oy1 = max(0, dx), max(0, dy), min(wa, dx + wb), min(ha, dy + hb)
            if ox1 <= ox0 or oy1 <= oy0:
                continue
            pa = a[oy0:oy1, ox0:ox1]
            pb = b[oy0 - dy:oy1 - dy, ox0 - dx:ox1 - dx]
            if mode == 'color':
                both = body_mask(pa) & body_mask(pb)
                sc = int((both & (pa[..., :3] == pb[..., :3]).all(-1)).sum())
            else:
                nb = pb[..., 3] > 0
                inside = int((nb & (pa[..., 3] > 0)).sum())
                sc = inside - 2 * (nb_all - inside)
            if best is None or sc > best[0]:
                best = (sc, dx, dy)
    return best[1], best[2], best[0]


# ---------- 位置 ----------
def layout(img):
    """各帧相对位置。rel：帧号 → 以本组参照帧的机体重心为原点时帧左上角的精灵坐标（悬停、倾转、冲刺三组；蓝色版按轮廓配准到常色版）；
    rise：升起各 tick 的 (帧号, (X, Y))，机体重心自地下 (0, RISE_FROM) 沿很小的前倾角升到悬停点 (−RISE_DRIFT, −HOVER_Y)（素材朝左，
    前方为 −x）。"""
    rep = {}
    cen = {i: centroid(body_mask(img[i])) for i in RISE + TILT + HOVER + DASH}
    rel = {}

    def group(ref, members, blue, fixed=None):
        off = {ref: (0, 0)}
        for i in members:
            if i != ref:
                dx, dy, sc = register(img[ref], img[i], 'color')
                off[i] = fixed[i] if fixed else (dx, dy)
                rep[f'reg_{i}_to_{ref}'] = [dx, dy, sc]
        cx, cy = cen[ref]
        for i in members:
            rel[i] = (int(round(-cx)) + off[i][0], int(round(-cy)) + off[i][1])
        for n, b in zip(members, blue):
            dx, dy, sc = register(img[b], img[n], 'shape')
            rel[b] = (rel[n][0] - dx, rel[n][1] - dy)
            rep[f'reg_{n}_in_{b}'] = [dx, dy, sc]
    group(6, HOVER, HOVER_BLUE)
    group(38, DASH, DASH_BLUE, DASH_MSA)
    for i in TILT:                       # 倾转：各帧机体重心在悬停点
        rel[i] = (int(round(-cen[i][0])), int(round(-cen[i][1])))
    dx1, dy1, sc = register(img[0], img[1], 'color')
    rep['reg_1_to_0'] = [dx1, dy1, sc]
    rise = []
    for k in range(RISE_T):             # 先快后慢；横向与纵向同比例（直线，前倾角 atan(RISE_DRIFT / 升起高度)）
        u = (k + 1) / RISE_T
        e = 1 - (1 - u) ** 2
        x = -RISE_DRIFT * e
        y = RISE_FROM + (-HOVER_Y - RISE_FROM) * e
        f = RISE[(k // 2) % 2]
        X, Y = x - cen[0][0], y - cen[0][1]
        if f == 1:
            X, Y = X + dx1, Y + dy1
        rise.append((f, (int(round(X)), int(round(Y)))))
    rep.update({'centroids': {str(k): v for k, v in cen.items()},
                'rise_angle_deg': round(float(np.degrees(np.arctan2(RISE_DRIFT, HOVER_Y + RISE_FROM))), 2)})
    return rel, rise, rep


class Table:
    def __init__(self):
        self.rows = [[0, 0, 0, 0, 0]]

    def add(self, r):
        r = [int(v) for v in r]
        if r not in self.rows:
            self.rows.append(r)
        return self.rows.index(r)


def body_box(im, X, Y, clip=True):
    x0, y0, x1, y1 = bbox(body_mask(im))
    x0, y0, x1, y1 = X + x0, Y + y0, X + x1, Y + y1
    if clip:
        y1 = min(y1, 0)
    return [x0, y0, x1 - x0, y1 - y0] if y1 > y0 else None


def flame_offset(body, flame, plume):
    """悬停喷焰 flame 相对悬停帧左上角的位置 (dx, dy)：沿同一对心形喷焰 plume 的主轴（自宽端指向尖端，素材中朝右下），机体在
    主轴方向最远的像素（尾端喷口）与喷焰在反方向最远的像素（宽端）对齐，宽端伸入喷口 FLAME_OVERLAP。"""
    ys, xs = np.nonzero(plume[..., 3] > 0)
    pts = np.stack([xs, ys], 1).astype(float)
    w, v = np.linalg.eigh(np.cov((pts - pts.mean(0)).T))
    d = v[:, np.argmax(w)]
    d = d if d[1] > 0 else -d
    ys, xs = np.nonzero(flame[..., 3] > 0)
    pts = np.stack([xs, ys], 1).astype(float)
    pf = pts[pts @ d <= (pts @ d).min() + 1.5].mean(0)
    ys, xs = np.nonzero(body_mask(body))
    pb = np.stack([xs, ys], 1).astype(float)
    pn = pb[pb @ d >= (pb @ d).max() - 1.5].mean(0)
    o = pn - FLAME_OVERLAP * d - pf
    return int(round(o[0])), int(round(o[1]))


# ---------- 动作 ----------
def build(fr):
    img = {i: f['img'] for i, f in enumerate(fr)}
    rel, rise, rep = layout(img)
    tiles, tile_of, rect_keys, frame_keys = [], {}, [], []

    def rect(i, X, Y):
        if i not in tile_of:
            tile_of[i] = len(tiles)
            tiles.append(i)
        k = (tile_of[i], -int(X), -int(Y))
        if k not in rect_keys:
            rect_keys.append(k)
        return rect_keys.index(k)

    def frame(i, X, Y, *under):
        """帧 i 以左上角 (X, Y) 放置（矩形锚点 = (−X, −Y)），返回帧键；under 为画在其下的部件 (帧号, X, Y)。"""
        k = tuple(rect(*p) for p in under) + (rect(i, X, Y),)
        if k not in frame_keys:
            frame_keys.append(k)
        return frame_keys.index(k)

    def at(i, px, py):                  # 帧 i 的本组参照重心放在 (px, py)
        return rel[i][0] + px, rel[i][1] + py

    def ground(i):                      # 底边中点落在地面
        h, w = img[i].shape[:2]
        return frame(i, -(w // 2), -h)
    hits, atks = Table(), Table()

    def hbox(i, X, Y, clip=True):
        b = body_box(img[i], X, Y, clip)
        return hits.add(b + [0]) if b else 0
    blue_of = dict(zip(HOVER, HOVER_BLUE)) | dict(zip(DASH, DASH_BLUE))
    s = {k: list(END) for k in range(SCRIPT_COUNT)}
    HX, HY = -RISE_DRIFT, -HOVER_Y      # 战斗中的悬停点
    puff = {i: (PUFF_BIG[k], PUFF_RING[k]) for k, i in enumerate(HOVER)}
    flame_at = {i: tuple(flame_offset(img[i], img[p], img[puff[i][0]]) for p in puff[i]) for i in HOVER}
    rep['flame_offsets'] = {str(i): flame_at[i] for i in HOVER}

    def hover(i, f, px, py, ticks):
        """悬停帧 i（显示 f：常色或蓝色版）的参照重心放在 (px, py)，喷焰（画在机体下）逐 tick 心形 / 月牙形交替。"""
        X, Y = at(i, px, py)
        out = []
        for t in range(ticks):
            dx, dy = flame_at[i][t % 2]
            out += [show(frame(f, *at(f, px, py), (puff[i][t % 2], X + dx, Y + dy))), cmd(1, 1)]
        return out

    # 单位菜单动作演示的待机与编队页：悬停姿态放在较低处（NEUTRAL_Y），单位宽度取此动作的受击框
    s[SLOT['neutral']] = sum(([cmd(3, hbox(i, *at(i, 0, -NEUTRAL_Y)))] + hover(i, i, 0, -NEUTRAL_Y, 3)
                              for i in NEUTRAL_ORDER), []) + [cmd(5)]
    s[SLOT['deck']] = [cmd(3, hbox(6, *at(6, 0, -NEUTRAL_Y))), show(frame(6, *at(6, 0, -NEUTRAL_Y))), cmd(1, 60), cmd(5)]
    s[SLOT['deck2']] = list(s[SLOT['deck']])

    # 钻出的土堆效果：隆起、迸开、塌下、土痕（效果对象在第一次绘制前已更新两次，第一帧多留 2 tick）。不放坑（用户 2026-10-26）
    seq = [(55, 3), (56, 1), (57, 1), (58, 1), (49, 1), (50, 2), (51, 2), (52, 3), (53, 3), (54, 2), (59, 2), (60, 2),
           (61, 3), (62, 3), (63, 3), (64, 3)]
    s[SLOT['mound_fx']] = sum(([show(ground(i)), cmd(1, t)] for i, t in seq), []) + END
    # 地下潜行：小土堆循环，无受击框
    s[SLOT['under']] = [cmd(3, 0), cmd(4, 0)] + sum(([show(ground(i)), cmd(1, 3)] for i in (55, 56, 57, 58, 57, 56)), []) + [cmd(5)]
    # 钻入：土块塌下，播完由核心转入地下潜行
    s[SLOT['burrow']] = [cmd(3, 0), cmd(4, 0)] + sum(
        ([show(ground(i)), cmd(1, 2)] for i in (52, 53, 54, 59, 60)), []) + [cmd(21)]

    # 钻出：隆起（导弹在地下）→ 以很小的前倾角升起 → 倾转 → 悬停调整位置并锁定（与蓝色版交替）；播完由核心转入冲刺
    em = [cmd(3, 0), cmd(4, 0), cmd(12, SLOT['mound_fx'], 0, 0, 0), cmd(0, -1), cmd(1, BULGE_T), {'opcode': 23, 'values': ['emerge']}]
    rise_boxes = []
    for f, (X, Y) in rise:
        b = hbox(f, X, Y)
        rise_boxes.append(b)
        em += [cmd(3, b), show(frame(f, X, Y)), cmd(1, 1)]
    for i in TILT:
        em += [cmd(3, hbox(i, *at(i, HX, HY))), show(frame(i, *at(i, HX, HY))), cmd(1, TILT_STEP)]
    for k, i in enumerate(ADJUST):
        f = blue_of[i] if k % 2 else i
        em += [cmd(3, hbox(i, *at(i, HX, HY)))] + hover(i, f, HX, HY, ADJUST_STEP)
    s[SLOT['emerge']] = em + [cmd(21)]

    # 冲刺：机体重心为原点（核心在冲刺开始时把单位移到悬停点，此后按追踪方向移动）；常色 / 蓝色 × 4 种尾焰交替
    # （8 步 × DASH_STEP tick）；尾焰只有帧内自带的部分（R2 去掉独立的尾焰粒子：原作没有分开的尾迹）
    boxes = [body_box(img[i], *at(i, 0, 0), clip=False) for i in DASH]
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes)
    y1 = max(b[1] + b[3] for b in boxes)
    dash_hit = [x0, y0, x1 - x0, y1 - y0]
    nose = x0                                                # 机体前端（素材朝左，x 最小处）
    mid_y = (y0 + y1) // 2
    contact = atks.add([nose - 2, y0, x1 - x0 + 2, y1 - y0, ATTACK_FLAGS])
    order = [(0, 0), (1, 1), (2, 0), (3, 1), (0, 1), (1, 0), (2, 1), (3, 0)]
    dash = [cmd(3, hits.add(dash_hit + [0])), cmd(4, contact)]
    for shape, blue in order:
        f = (DASH_BLUE if blue else DASH)[shape]
        dash += [show(frame(f, *at(f, 0, 0))), cmd(1, DASH_STEP)]
    s[SLOT['dash']] = dash + [cmd(5)]

    # 爆炸：隐藏导弹，攻击框以弹头为中心，开 BLAST_T tick（一个攻击 ID，每个目标只结算一次）；原生共用爆炸效果与音效；播完由核心移除
    def blast(size, effects):
        w, h = size
        box = atks.add([nose - w // 2, mid_y - h // 2, w, h, ATTACK_FLAGS])
        out, t_now = [cmd(3, 0), cmd(0, -1), cmd(4, box), cmd(23, SOUND_BLAST)], 0
        for t, x, y in effects:
            if t > t_now:
                out.append(cmd(1, t - t_now))
                t_now = t
            out.append(cmd(12, EFFECT_BLAST, 0, x, y))
        if t_now < BLAST_T:
            out.append(cmd(1, BLAST_T - t_now))
        out.append(cmd(4, 0))
        return out + [cmd(1, 20), cmd(21)], box
    s[SLOT['blast']], box_n = blast(BLAST, [(0, nose, mid_y)])
    s[SLOT['blast_sp']], box_s = blast(BLAST_SP, [(0, nose, mid_y), (2, nose - 26, mid_y - 18), (4, nose + 24, mid_y - 10)])
    s[SLOT['death']] = [cmd(3, 0), cmd(4, 0), cmd(0, -1), cmd(12, EFFECT_DEATH, 0, (x0 + x1) // 2, mid_y),
                        cmd(23, SOUND_DEATH), cmd(1, 12), cmd(21)]
    launch = (RISE_DRIFT * 2, HOVER_Y * 2)                  # 世界单位：悬停点相对出土点的前方距离与离地高度
    rep.update({'nose': nose, 'mid_y': mid_y, 'dash_hit': dash_hit, 'rise_boxes': rise_boxes,
                'hover_hit': hits.rows[hbox(6, *at(6, HX, HY))], 'blast_box': atks.rows[box_n], 'blast_sp_box': atks.rows[box_s],
                'contact_box': atks.rows[contact], 'launch_world': launch})
    return s, tiles, (rect_keys, frame_keys), hits.rows, atks.rows, rel, rise, launch, rep


def assemble(fr, s, tiles, keys, sound_key):
    """装箱；帧表每条为 [部件数, 矩形号…]（先画前面的部件），脚本中的帧键换为帧表偏移，音效占位换为本体音效键。"""
    rect_keys, frame_keys = keys
    page, xy = shelf_pack([Image.fromarray(fr[i]['img'], 'RGBA') for i in tiles])
    rects, words, start = [], [], []
    for t, ax, ay in rect_keys:
        h, w = fr[tiles[t]]['img'].shape[:2]
        x, y = xy[t]
        rects.append([x, y, w, h, ax, ay, 0, 0])
    for k in frame_keys:
        start.append(len(words))
        words += [len(k)] + list(k)
    anims = {}
    for slot, cmds in s.items():
        out = []
        for c in cmds:
            if c.get('key'):
                out.append(cmd(0, start[c['values'][0]]))
            elif c['opcode'] == 23 and c['values'] == ['emerge']:
                out.append({'opcode': 23, 'values': [sound_key]})
            else:
                out.append(c)
        anims[slot] = out
    return page, rects, words, anims


# ---------- 头像 ----------
def icon_cell(im):
    """悬停帧左右镜像（朝右，同 MSA 头像取景）置于 46×43 格的中心。"""
    src = im[:, ::-1]
    iw, ih = ICON_SIZE
    cell = np.zeros((ih, iw, 4), np.uint8)
    h, w = src.shape[:2]
    x0, y0 = (iw - w) // 2, (ih - h) // 2 + 2
    cell[max(0, y0):y0 + h, max(0, x0):x0 + w] = src[max(0, -y0):ih - y0, max(0, -x0):iw - x0]
    return cell


def find_icon_slot(raw, start=(1748, 768)):
    w, h = struct.unpack_from('<HH', raw, 4)
    alpha = np.frombuffer(bytes(raw[8:8 + w * h * 4]), np.uint8).reshape(h, w, 4)[..., 3]
    used = []
    for f in CONTENT.glob('units/*.json'):
        unit = json.loads(f.read_text(encoding='utf-8'))
        icon = unit['icon']
        if unit['key'] != KEY and icon.get('page') == 1 and 'atlas' not in icon:
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


def encode_ogg(wav, target):
    """WAV 编码为 Ogg Vorbis（同钢铁死亡蠕虫生成脚本的 encode_ogg：libsndfile 分块写入）。"""
    import soundfile as sf
    data, rate = sf.read(str(wav), always_2d=True)
    with sf.SoundFile(str(target), 'w', samplerate=rate, channels=data.shape[1], format='OGG', subtype='VORBIS') as f:
        for i in range(0, len(data), 4096):
            f.write(data[i:i + 4096])


# ---------- 审阅图（只按根层近似：不执行子层、效果对象与核心的移动、下降） ----------
def strip(page, rects, words, hits, atks, anims, slot, ticks, step=1, scale=3, clip=False):
    W, H, oy = 160, 220, 180
    cells = []
    for t in range(0, ticks, step):
        canvas = Image.new('RGBA', (W, H), (70, 70, 90, 255))
        d = ImageDraw.Draw(canvas)
        d.line([(0, oy), (W, oy)], fill=(150, 110, 60, 255))
        frame, hit, atk, clock = -1, 0, 0, 0
        for c in anims[slot]:
            op, v = c['opcode'], c['values']
            if op == 0:
                frame = v[0]
            elif op == 3:
                hit = v[0]
            elif op == 4:
                atk = v[0]
            elif op == 1:
                if clock + v[0] > t:
                    break
                clock += v[0]
            elif op in (5, 21):
                break
        for n in (words[frame + 1:frame + 1 + words[frame]] if frame >= 0 else ()):
            r = rects[n]
            tile = page.crop((r[0], r[1], r[0] + r[2], r[1] + r[3]))
            if clip:
                keep = max(0, min(r[3], r[5]))
                tile = tile.crop((0, 0, r[2], keep)) if keep > 0 else None
            if tile is not None:
                canvas.alpha_composite(tile, (W // 2 - r[4], oy - r[5]))
        for table, idx, col in ((hits, hit, (0, 255, 0, 255)), (atks, atk, (255, 220, 0, 255))):
            if idx:
                x, y, w, h = table[idx][:4]
                d.rectangle([W // 2 + x, oy + y, W // 2 + x + w - 1, oy + y + h - 1], outline=col)
        d.text((2, 2), f'{slot}:{t}', fill=(255, 255, 0, 255))
        cells.append(canvas.resize((W * scale, H * scale), Image.NEAREST))
    cols = 8
    rows = (len(cells) + cols - 1) // cols
    out = Image.new('RGBA', (cols * W * scale, rows * H * scale), (0, 0, 0, 255))
    for k, c in enumerate(cells):
        out.paste(c, ((k % cols) * W * scale, (k // cols) * H * scale))
    return out


def main():
    OUT.mkdir(exist_ok=True)
    fr = load_frames()
    sizes = [f['img'].shape[:2] for f in fr]
    assert all(sizes[n] == sizes[b] for n, b in zip(DASH, DASH_BLUE)), [(sizes[n], sizes[b]) for n, b in zip(DASH, DASH_BLUE)]
    s, tiles, keys, hits, atks, rel, rise, launch, rep = build(fr)
    page, rects, words, anims = assemble(fr, s, tiles, keys, EMERGE_SOUND[0])
    desc = {'rects': rects, 'frames': words, 'script_count': SCRIPT_COUNT, 'hit_bounds': hits, 'attack_bounds': atks}
    cell = icon_cell(fr[6]['img'])
    Image.fromarray(cell, 'RGBA').save(OUT / 'icon.png')
    page.save(OUT / 'atlas.png')
    for name, ticks, step, clip in (('emerge', 48, 1, True), ('dash', 16, 1, False), ('neutral', 24, 1, False),
                                    ('under', 18, 1, False), ('burrow', 10, 1, False), ('blast', 8, 1, False),
                                    ('blast_sp', 8, 1, False), ('mound_fx', 56, 2, False), ('death', 4, 1, False)):
        strip(page, rects, words, hits, atks, anims, SLOT[name], ticks, step, clip=clip).save(OUT / f'strip_{SLOT[name]:02d}_{name}.png')
    report = {'frames': len(fr), 'tiles': len(tiles), 'rects': len(rects), 'hit_bounds': len(hits), 'attack_bounds': len(atks),
              'atlas': list(page.size), 'colors': len(set(page.getdata())), 'rel': {str(k): v for k, v in rel.items()},
              'rise': rise, **rep}
    if '--preview' in sys.argv:
        (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k: v for k, v in report.items() if k not in ('rel', 'rise', 'centroids')}, ensure_ascii=False))
        return
    index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
    if KEY not in index['unit_ids']:
        index['unit_ids'][KEY] = max(index['unit_ids'].values()) + 1
    obm = indexed_obm(page)
    (CONTENT / TEXTURE).write_bytes(obm)
    index['assets'][TEXTURE] = hashlib.blake2b(obm, digest_size=32).hexdigest()
    key, wav, volume = EMERGE_SOUND                   # libsndfile 每次取随机流序列号，已有文件时不重编（换源文件时先删除旧的 .msdf）
    target = key.split('.', 1)[1] + '.msdf'
    if not (CONTENT / target).exists():
        encode_ogg(MSXX_SE / wav, CONTENT / target)
    sounds = list(index.get('sounds', []))
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
    v = VALUES
    unit = {'key': KEY, 'base_id': BASE, 'faction': FACTION, 'identity': IDENTITY,
            'shop_price': v['shop_price'], 'available_from_start': True, 'ap': v['ap'],
            'hp_multiplier': v['hp_multiplier'], 'knockback_threshold_multiplier': v['knockback_threshold_multiplier'],
            'damage_multiplier': v['damage_multiplier'], 'special_damage_multiplier': v['special_damage_multiplier'],
            **{k: [1, 1] for k in ONES},
            'move_speed_multiplier': v['move_speed_multiplier'],
            'production_reference_id': BASE, 'production_interval_multiplier': v['production_interval_multiplier'],
            'status_word_values': v['status_word_values'], 'attack_attributes': v['attack_attributes'],
            'image_direction': 270,
            'icon': {'page': 1, 'rect': list(rect), 'anchor': ICON_ANCHOR},
            'textures': [TEXTURE], 'sprite_descriptor': DESCRIPTOR,
            'animations': {str(k): anims[k] for k in sorted(anims)},
            'localization': {lang: {'name': n, 'description': t} for lang, (n, t) in LOCALIZATION.items()},
            'tags': ['ms7'],
            'behaviors': [{'name': 'mole_missile', 'version': 2, 'params': {
                'neutral_animation': SLOT['neutral'], 'burrow_animation': SLOT['burrow'],
                'underground_animation': SLOT['under'], 'emerge_animation': SLOT['emerge'],
                'dash_animation': SLOT['dash'], 'explode_animation': SLOT['blast'],
                'special_explode_animation': SLOT['blast_sp'], 'death_animation': SLOT['death'],
                'dash_speed': DASH_SPEED, 'launch_forward': launch[0], 'launch_height': launch[1]}}]}
    save_json(CONTENT / DESCRIPTOR, desc)
    save_json(unit_path, unit)
    save_json(CONTENT / 'content.json', index)
    report.update(unit_id=index['unit_ids'][KEY], icon_rect=rect, obm_bytes=len(obm))
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('rel', 'rise', 'centroids')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
