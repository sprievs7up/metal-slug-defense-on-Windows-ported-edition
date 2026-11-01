"""叛军自爆摩托（MS7 任务 4 单位，原作 Fanatic Biker）制作为本体单位（2026-10-31；行为 bomb_bike v1）。

方案：docs/MS7_M4_UNITS_2026-10-31.md 第 7、8 节（用户 2026-10-31 选定离线预览 verification/ms7_m4_units_20261031/proto/bike_r3_apex260.mp4）。
- 图像：素材表 F:\\egg\\MS7\\Neo Geo _ NGCD - Metal Slug - Enemies & Bosses - Rebel Biker.png（Metal Slug 1–4，The Mad Soldier 拆图，
  前一版 The Huntress；要求注明来源）原色，原画朝左，image_direction 270。帧位置取 verification/ms7_m4_units_20261031/biker_frames.py 的切帧
  （外接框，素材表坐标）；尾气（SFX 12 格）与后轮扬尘（X 代沙色 8 格）的格子底色 (112,146,190) 转透明。不背火箭的 1 代棕衣骑手版。
- 本单位（基准 133 BattleAction_Bike_P）：槽 0–22 与原生 133 的用途一一对应（状态 10 / 20 与 ≥ 100 交原生：平骑、行驶中被击毁、
  槽 18 的爆炸攻击框），23 起为 bomb_bike 行为的蓄力、翘头冲刺、弃车、飞行与效果。锚点：骑行各帧取后轮着地点（平骑帧为最后一行最右一段的
  中点，翘头与弃车帧为最左一段的中点），翻滚与效果帧取中心，扬尘取靠后轮一端的底边。
- 骑手（基准 160 BattleAction_ParaTrooper，内部单位）：槽结构照 PvZ 小鬼（s1xlv.pvz_imp_flight），槽 8 为双手上举帧与后跳
  op7[150,-500,0,50]（op7 的 x 按原画坐标：本单位原画朝左，正值为后退；LAB bb2 中 −150 使骑手向前跳 72），落地为原生 162 冲天火箭弹兵
  （R9，用户 2026-10-31；R4–R8 为原生 2）。骑手生命为基准 160 × 4/3（各等级等于 162 的生命），行为 landing_keeps_hp 把落地前的剩余生命
  交给 162：与车分离的瞬间起单独记录生命（用户 R9）。
- 名称「机动兵」（R9，用户：机动指机动车；原版 133 的繁体名「特種兵（機動）」，各语言按原版 133 对「機動」的译法），AP 110（R9），
  再出击 480 tick 与原生 133 相同；价格（150）待定。
运行：E:\\anaconda3\\python.exe -I artwork/rebel_bomb_bike_20261031/build_rebel_bomb_bike.py [--preview]
（--preview 只写 out/；否则另写 community_content/ 的图集、描述符、单位文件、unit_icon_02.obm 与 content.json）。
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
SHEET = Path(r'F:\egg\MS7\Neo Geo _ NGCD - Metal Slug - Enemies & Bosses - Rebel Biker.png')

_PVZ = REPO / 'artwork' / 'pvz_zombies_20261012' / 'build_pvz_zombies.py'
_src = _PVZ.read_text(encoding='utf-8')
_src = _src.replace("sys.path.insert(0, str(RT / 'packages'))", "").replace("os.add_dll_directory(str(RT / 'native'))", "")
pvz = type(sys)('pvzb')
pvz.__dict__['__file__'] = str(_PVZ)
exec(compile(_src, str(_PVZ), 'exec'), pvz.__dict__)
indexed_obm, save_json, shelf_pack = pvz.indexed_obm, pvz.save_json, pvz.shelf_pack

KEY, FILE = 's1xlv.rebel_bomb_bike', 'rebel_bomb_bike.json'
TEXTURE, DESCRIPTOR = 'rebel_bomb_bike.obm', 'rebel_bomb_bike_descriptor.json'
RIDER_KEY, RIDER_FILE = 's1xlv.rebel_bomb_bike_rider', 'rebel_bomb_bike_rider.json'
RIDER_TEXTURE, RIDER_DESCRIPTOR = 'rebel_bomb_bike_rider.obm', 'rebel_bomb_bike_rider_descriptor.json'
BASE, RIDER_BASE = 133, 160
# R11（用户 2026-10-31：落地小兵受到火焰 / 爆炸 / 子弹伤害的死亡音效应与普通兵相同）：落地单位改为原版 162 的内部副本（R9–R10 为原生 162，
# R4–R8 为原生 2）。原生 162（BattleAction_MissileZako）死亡状态 100 / 110 播放槽 13、120 播放槽 15，三者都是同一死亡语音 864（120 另有 283）；
# 普通兵 2 为 100 → 809、110 → 807、120 → 808 + 283（LAB ds2 / ds162）。副本沿用原生 162 的图集、描述符与数值，只改槽 13 / 14 / 15 的语音，
# 以 death_by_attribute（核心 r114 起适用基准 162）把 110 换到槽 14。
ROCKETEER_KEY, ROCKETEER_FILE = 's1xlv.rebel_bomb_bike_rocketeer', 'rebel_bomb_bike_rocketeer.json'
LANDING_UNIT = ROCKETEER_KEY
ROCKETEER_BASE = 162
ROCKETEER_TEXTURE = 'missile_zako_out.obm'                                  # 原生 162 的图集
ROCKETEER_ICON = {'page': 1, 'rect': [691, 424, 39, 37], 'anchor': [-5, -8]}   # 原生 162 的头像（icon_info.py）
ROCKETEER_VOICES = {13: [809], 14: [807], 15: [808, 283]}                    # 槽 → 开头的 op23：子弹 / 爆炸 / 火焰死亡
ROCKETEER_DEATH = {'explosion_animation': 14, 'fire_animation': 15}
TOOLS = Path(r'F:\egg\research\metal_slug_defense\content_work\kt21_feasibility_20261005\design_verification_r1\tools')
ROCKETEER_LOC = {   # 原生 162 的各语言名称与说明（strMenuUnitName / strMenuUnitInfo，runs/ni162_*/names.txt）；DE 原版为空，用英语；ZS 原版为空，为繁体转写
    'EN': ('ROCKET BOMB SOLDIER', 'STAND. ATK : Rocket Bomb     SPEC. ATK : Rocket Bomb\nInfantry from Morden’s Army who throw pencil-type missile bombshells.'),
    'JP': ('ロケット爆弾兵', '通常攻撃：ロケット爆弾    特殊攻撃：ロケット爆弾\nペンシルロケット型の爆弾を投げるモーデン軍の歩兵。'),
    'KR': ('로켓 폭탄병', '일반 공격: 로켓 폭탄          특수 공격: 로켓 폭탄\n펜슬 미사일형 폭탄을 투척하는 모덴군 보병.'),
    'ES': ('SOLDADO CON MISIL', 'ATQ ESTÁND. : Misil   ATQ ESPEC. : Misil\nLa infantería de la Armada de Morden que\nlanza misiles explosivos con forma de lápiz. '),
    'PT': ('SOLDADO C/ FOGUETE', 'ATQ. PADR. : Bomba-Foguete   ATQ. ESPEC. : Bomba Foguete\n Infantaria do Exército de Morden que atira mísseis em forma de lápis.'),
    'FR': ('SOLDAT ROQUETTE', "ATT. STAND : Fusée roquette ATK SPEC. : Fusée roquette\nInfanterie de l'Armée de Morden qui lance des missiles.\n"),
    'DE': ('ROCKET BOMB SOLDIER', 'STAND. ATK : Rocket Bomb     SPEC. ATK : Rocket Bomb\nInfantry from Morden’s Army who throw pencil-type missile bombshells.'),
    'IT': ('SOLDATO BOMBA MISSILE', "ATC STAND.: Bomba Missile   ATC SPEC.: Bomba Missile\nFanteria dell'Esercito di Morden, lanciano missili a forma di matita."),
    'ZT': ('沖天火箭彈兵', '普通攻擊：火箭炸彈    特殊攻擊：火箭炸彈\n會擲出沖天炮型的炸彈的莫丁軍步兵。'),
    'ZS': ('冲天火箭弹兵', '普通攻击：火箭炸弹    特殊攻击：火箭炸弹\n会掷出冲天炮型的炸弹的莫丁军步兵。'),
    'RU': ('СОЛДАТ РАКЕТНАЯ БОМБА', 'СТАНД. АТАК: Ракетная бомба   СПЕЦ. АТАК: Ракетная бомба\nПехота Морденовскй армии, \nкоторая запускает ракетные бомбы карандашного типа.'),
}
FACTION, IDENTITY = 1, 'Rebel Army'
SHEET_BG = (153, 217, 234)
CELL_BG = (112, 146, 190)

# 素材表外接框（x, y, w, h）：biker_frames.py 的 thunder_drive、wheelie_drive、wheelie_eject、bike_tumble、debris
RIDE = [(5, 29, 56, 41), (66, 29, 56, 41), (127, 29, 56, 41)]
WHEELIE = [(5, 2054, 57, 48), (67, 2055, 58, 47), (130, 2056, 58, 46)]
EJECT = [(5, 2125, 52, 45), (62, 2127, 54, 43), (121, 2123, 53, 47), (179, 2120, 56, 50)]
RIDER = (240, 2120, 28, 43)
TUMBLE = [(5, 2192, 37, 54), (47, 2190, 30, 56), (82, 2192, 40, 54), (127, 2197, 48, 49),
          (180, 2209, 54, 37), (239, 2216, 56, 30), (300, 2206, 54, 40), (359, 2198, 49, 48)]
WHEELS = [(48, 2479, 18, 15), (71, 2481, 20, 13)]
EXHAUST = [(5 + 18 * k, 1046, 16, 16) for k in range(12)]      # SFX 尾气烟团（格子底色）
SPRAY = [(5 + 34 * k, 2443, 32, 16) for k in range(8)]         # 后轮扬尘，X 代沙色（格子底色）

# 时长与运动（tick；op7 为脚本单位 1/100 精灵像素，世界 = × 2；x 按原画坐标，原画朝左时正值为后退）
POP_DEG = (16, 32)               # 翘起：平骑帧绕后轮着地点旋转（op2，4096 = 360°）
POP_SIGN = 1                     # 原画朝左时车头抬起的旋转方向（LAB 核对：−1 时车头下压）
CHARGE_T = 40                    # 原地翘头蓄力
RIDE_STEP, WHEELIE_STEP, EJECT_STEP, TUMBLE_STEP, EXHAUST_STEP, SPRAY_STEP = 2, 2, 3, 3, 2, 2
EXHAUST_EVERY = (3, 2)           # 蓄力 / 冲刺中每几 tick 放一团尾气
# R7（用户 2026-10-31 截图：绝招冷却条没对齐）：冷却条按单位位置绘制，骑行各帧的锚点由后轮着地点前移 ANCHOR_SHIFT 到车身中部
# （平骑帧前后轮着地点 x 8、44 的中点）；尾气、扬尘与骑手出发点随之按后轮位置换算
ANCHOR_SHIFT = 18                # 精灵像素（原画朝左，前方为 −x）
EXHAUST_AT = (10 + ANCHOR_SHIFT, -5)   # 尾气出生点（原画坐标，后轮着地点后方 10、离地 5）
SPRAY_AT = (ANCHOR_SHIFT, 0)     # 扬尘子层在后轮着地点
# R7（用户：翘头骑行中没有尾气、车身像固定的平移图片）：op21 为停在末帧、不循环（LAB dump1：冲刺根层帧号 6、8、10 后停在 10），
# 冲刺、飞行与扬尘按最长持续时间逐帧写满
DASH_T, FLIGHT_T, SPRAY_T = 96, 96, 128
EXHAUST_DRIFT = [40, -15, 0, 0]  # 尾气向后上方漂移（每 tick 0.8 / 0.3 世界单位）
RIDER_HOP = [150, -500, 0, 50]   # 骑手后跳：约 60 世界单位、空中约 20 tick
WHEEL_HOPS = ([-250, -650, 0, 60], [300, -550, 0, 60])
WHEEL_T = 22
SOUND_ENGINE, SOUND_REV = 318, 319   # 原生 133 的行驶与翘头音效

# 行为参数（ZSpec；世界单位）
DASH_V0, DASH_ACCEL, DASH_CAP = 60, 40, 120   # 冲刺初速 6、每 tick +0.4、上限 12（× 10 / × 100 / × 10）
# R10（用户 2026-10-31：抛射距离太远，必须削弱）：放出的车头距离 200 → 130，另限水平抛射距离（车身中心到落点）≤ 120
# （R9 前正常抛出 120–160，绝招后冲刺满 dash_limit 时不设上限，LAB far0 为 751；没有目标时 300）
THROW_RANGE = 130                # 车头距目标前缘的投掷距离
MAX_THROW = 120                  # 最大水平抛射距离（世界单位）
EJECT_SPEED = 80                 # 弃车中每 tick 8（× 10）
APEX, GRAVITY, LAND_OFFSET = 260, 120, 12   # 顶点（车身中心离地）、重力每 tick² 1.2（× 100）、落点在目标前缘之后
DASH_LIMIT = 90                  # 冲刺上限 tick
FLIGHT_HEIGHT0 = 54              # 放出时车身中心离地（翻滚帧半高 27 精灵像素）

SLOT = {'deck': 0, 'deck2': 1, 'menu_wheelie': 2, 'neutral': 6, 'move': 7, 'attack': 9, 'special': 10, 'wheelie_loop': 11,
        'death': (13, 14, 15, 16), 'wheelie_short': 17, 'blast': 18, 'dust': 19, 'move_loop': 20, 'dash_native': 21,
        'dash_native_sp': 22, 'charge': 23, 'dash': 24, 'eject': 25, 'flight': 26, 'exhaust': 27, 'spray': 28,
        'wheel_a': 29, 'wheel_b': 30, 'pop': 31}
SCRIPT_COUNT = 32

VALUES = {   # 用户 2026-10-31：Lv40 生命 4000、AP 110（R9；R6–R8 为 120）、普攻 1600、绝招 2700（原生 133 为 2700 / 90 / 1800 / 2580）；
             # 再出击 480 tick（R9 用户要求与原生 133 相同：production_reference_id 133、倍率 1）、移速 3.3
             # 保持原值；击退门槛倍率随生命（第 6.1 节；133 为 −1 每次受击均击退，加载器不缩放）；普攻距离（词 7）为触发距离 600；价格暂定
    'ap': 110, 'shop_price': 150,
    'hp_multiplier': [40, 27], 'knockback_threshold_multiplier': [40, 27],
    # 绝招倍率先作用于数据行锚点（向下取整），运行时再乘 damage_multiplier（词 29 两者都缩放）：Lv40 锚点 2580 × 1519/1290 = 3038，
    # × 8/9 = 2700（45/43 时为 2400，405/344、471/400 时为 2699；单位菜单 STATUS 核对）
    'damage_multiplier': [8, 9], 'special_damage_multiplier': [1519, 1290],
    'move_speed_multiplier': [1, 1], 'production_interval_multiplier': [1, 1],
    'status_word_values': {'7': 600},
}
ONES = ('attack_wait_multiplier', 'attack_range_multiplier', 'knockback_distance_multiplier', 'ballistic_range_multiplier')

LOCALIZATION = {   # R9：名称按用户定为「机动兵」，各语言沿用原版 133 对「機動」的译法（EN RIDER、JP / KR バイク / 바이크、PT MOTOQ.、FR MOTARD、
                   # IT MOTOC.、RU ВСАДНИК；ES 原版亦为 RIDER；DE 原版为空，按德语）。R12：说明第 2、3 行用用户文本（简体原文照录，只在第二句后换行），
                   # 其余语言由代理按其意译写，待校对
    'EN': ('RIDER SOLDIER', 'STAND. ATK : Bike Throw     SPEC. ATK : Bike Throw\nA fanatic soldier of the Rebel Army bike squad.\nHurls the bike for a deadly blow, and fights on even after that.'),
    'JP': ('バイク兵', '通常攻撃：バイク投げ     特殊攻撃：バイク投げ\nモーデン軍バイク部隊の狂信的な兵士。\nバイクを投げて必殺の一撃を放ち、投げた後も戦い続ける。'),
    'KR': ('바이크병', '일반 공격: 바이크 던지기     특수 공격: 바이크 던지기\n모덴군 바이크 부대의 광신적인 병사.\n바이크를 던져 치명적인 일격을 가하고, 던진 뒤에도 계속 싸운다.'),
    'ES': ('SOLDADO RIDER', 'ATQ ESTÁND. : Lanzar moto     ATQ ESPEC. : Lanzar moto\nSoldado fanático del escuadrón de motos rebelde.\nLanza la moto como golpe letal y sigue luchando después.'),
    'PT': ('SOLDADO MOTOQUEIRO', 'ATQ. PADR. : Arremesso de moto   ATQ. ESPEC. : Arremesso de moto\nSoldado fanático do esquadrão de motos rebelde.\nArremessa a moto num golpe fatal e continua lutando depois.'),
    'RU': ('СОЛДАТ-ВСАДНИК', 'СТАНД. АТАК: Бросок мотоцикла СПЕЦ. АТАК: Бросок мотоцикла\nФанатичный солдат мотоотряда повстанцев.\nБросает мотоцикл как смертельный удар и продолжает бой.'),
    'FR': ('SOLDAT MOTARD', 'ATT. STAND : Lancer de moto   ATT. SPÉ : Lancer de moto\nSoldat fanatique de l\'escadron motorisé rebelle.\nIl projette sa moto pour un coup fatal et continue de combattre.'),
    'DE': ('MOTORRADSOLDAT', 'NORM. ANGR.: Motorradwurf SPEZ. ANGR.: Motorradwurf\nFanatischer Soldat der Motorradstaffel der Rebellen.\nSchleudert das Motorrad als tödlichen Schlag und kämpft danach weiter.'),
    'IT': ('SOLDATO MOTOCICLISTA', 'ATC STAND.: Lancio moto   ATC SPEC.: Lancio moto\nSoldato fanatico della squadra motociclisti ribelle.\nScaglia la moto come colpo letale e continua a combattere.'),
    'ZT': ('機動兵', '普通攻擊：拋擲機車     特殊攻擊：拋擲機車\n叛軍機車部隊的狂熱士兵。拋出機車使出致命一擊。\n哪怕拋出機車也會繼續作戰'),
    'ZS': ('机动兵', '普通攻击：抛掷机车     特殊攻击：抛掷机车\n叛军机车部队的狂热士兵。抛出机车使出致命一击。\n哪怕抛出机车也会继续作战'),
}
# R9（用户 2026-10-31）：头像改用用户在原生绿格上画好的构图（handoff/，导出素材见 make_icon_handoff.py）；R4–R8 为平骑帧翻转朝右、
# 46×43、锚点 [−5, −2]。取格内 x 5–49、y 4–44（头盔顶压在上边框第 4 行，前轮压在右侧边框上）
USER_ICON = HERE / 'handoff' / 'unit_cell_player_green_50x50 XX.png'
USER_CELL = HERE / 'handoff' / 'unit_cell_player_green_50x50.png'
ICON_BOX = (5, 4, 50, 45)
ICON_SIZE = (ICON_BOX[2] - ICON_BOX[0], ICON_BOX[3] - ICON_BOX[1])
ICON_ANCHOR = [-ICON_BOX[0], -ICON_BOX[1]]


def cmd(op, *v):
    return {'opcode': op, 'values': [int(x) for x in v]}


def show(key):
    """op0（值为矩形组键，写出时换为帧表偏移）。"""
    return {'opcode': 0, 'values': [key], 'key': True}


HIDE = cmd(0, -1)


# ---------- 切帧 ----------
_sheet = np.asarray(Image.open(SHEET).convert('RGB'))


def crop(box, bg):
    x, y, w, h = box
    a = _sheet[y:y + h, x:x + w]
    m = ~np.all(a == np.array(bg), axis=2)
    return np.dstack([a, (m * 255).astype(np.uint8)]).astype(np.uint8)


def contact_x(img, last):
    """后轮着地点：最后一行不透明像素段中，平骑帧取最右一段（last），其余取最左一段；返回段中点。"""
    m = img[..., 3] > 0
    bottom = int(np.nonzero(m.any(axis=1))[0].max())
    runs, start = [], None
    for x, v in enumerate(list(m[bottom]) + [False]):
        if v and start is None:
            start = x
        elif not v and start is not None:
            runs.append((start, x - 1)); start = None
    r = runs[-1] if last else runs[0]
    return (r[0] + r[1] + 1) // 2, bottom + 1


def load():
    tiles, anchors = {}, {}
    for name, boxes, kind in (('R', RIDE, 'ride'), ('W', WHEELIE, 'wheel'), ('E', EJECT, 'wheel'), ('T', TUMBLE, 'center'),
                              ('D', WHEELS, 'center'), ('X', EXHAUST, 'center'), ('S', SPRAY, 'spray')):
        for i, box in enumerate(boxes):
            img = crop(box, CELL_BG if name in 'XS' else SHEET_BG)
            if name in 'XS':
                m = img[..., 3] > 0
                if not m.any():
                    img = np.zeros((1, 1, 4), np.uint8)   # 全透明格以 1×1 透明块占位（同任务 4 的 atlas_pack 做法）
            h, w = img.shape[:2]
            if kind == 'ride':
                a = contact_x(img, True); a = (a[0] - ANCHOR_SHIFT, a[1])
            elif kind == 'wheel':
                a = contact_x(img, False); a = (a[0] - ANCHOR_SHIFT, a[1])
            elif kind == 'spray':
                a = (2, h)
            else:
                a = (w // 2, h // 2)
            tiles[f'{name}{i}'], anchors[f'{name}{i}'] = img, a
    rider = crop(RIDER, SHEET_BG)
    return tiles, anchors, rider


# ---------- 脚本 ----------
def frames(keys, step, ticks=None):
    out, t, k = [], 0, 0
    total = ticks if ticks is not None else len(keys) * step
    while t < total:
        n = min(step, total - t)
        out += [show(keys[k % len(keys)]), cmd(1, n)]
        t += n; k += 1
    return out


def with_exhaust(keys, step, ticks, every):
    """骑行帧序列，每 every tick 放一团尾气（op12 效果，画在车身之后）。"""
    out = []
    for t in range(ticks):
        if t % every == 0:
            out.append(cmd(12, SLOT['exhaust'], -1, *EXHAUST_AT))
        out += [show(keys[(t // step) % len(keys)]), cmd(1, 1)]
    return out


def scripts():
    R, W, E, T = ['R0', 'R1', 'R2'], ['W0', 'W1', 'W2'], ['E0', 'E1', 'E2', 'E3'], [f'T{i}' for i in range(8)]
    # 翘起：子层（槽 31）在后轮着地点处绘制锚点为后轮着地点的平骑帧 R0P，以 op2 绕后轮旋转；根层这 4 tick 隐藏。
    # （op14 会移动单位位置，不能用作绘制偏移：LAB r7 中用 op14 补偿后单位高度偏离地面 10）
    pop_sub = []
    for deg in POP_DEG:
        pop_sub += [cmd(2, POP_SIGN * round(deg * 4096 / 360)), show('R0P'), cmd(1, 2)]
    pop_sub += [cmd(2, 0), HIDE, cmd(1, 1), cmd(21)]
    pop = [cmd(11, SLOT['pop'], 0, *SPRAY_AT), HIDE, cmd(1, 2 * len(POP_DEG))]
    charge = ([cmd(3, 1), cmd(23, SOUND_REV)] + pop + [cmd(3, 2), cmd(11, SLOT['spray'], 1, *SPRAY_AT)]
              + with_exhaust(W, WHEELIE_STEP, CHARGE_T, EXHAUST_EVERY[0]) + [cmd(5)])
    # R12（用户 2026-10-31：中立动画应为 1-2-3-2-1-2-3-2-1，原为 1-2-3-1）：中立与编队页的静止展示往返播放（R0 R1 R2 R1 循环），
    # 行驶（槽 7 / 20）的车轮循环不变
    RP = R + R[-2:0:-1]
    s = {
        SLOT['deck']: frames(RP, RIDE_STEP) + [cmd(5)],
        SLOT['deck2']: frames(RP, RIDE_STEP) + [cmd(5)],
        SLOT['menu_wheelie']: frames(W, WHEELIE_STEP, 24) + [cmd(21)],
        3: [cmd(21)], 4: [cmd(21)], 5: [cmd(21)], 8: [cmd(21)], 12: [cmd(21)],
        SLOT['neutral']: [cmd(3, 1)] + frames(RP, RIDE_STEP) + [cmd(5)],
        SLOT['move']: [cmd(3, 1), cmd(23, SOUND_ENGINE)] + frames(R, RIDE_STEP, 9) + [cmd(21)],
        SLOT['attack']: charge, SLOT['special']: charge,
        SLOT['wheelie_loop']: [cmd(3, 2)] + frames(W, WHEELIE_STEP, 30) + [cmd(21)],
        **{k: [show('R0'), cmd(1, 1), cmd(21)] for k in SLOT['death']},
        SLOT['wheelie_short']: [cmd(3, 2)] + frames(W, 3) + [cmd(5)],
        # 原生 133 槽 18：攻击框 1 开 7 tick，共 28 tick 循环（爆炸画面 0xff04 由原生代码放出）；本单位另放两枚车轮
        SLOT['blast']: ([cmd(12, SLOT['wheel_a'], 1, 0, -10), cmd(12, SLOT['wheel_b'], 1, 0, -10), cmd(4, 1)]
                        + [HIDE, cmd(1, 1)] * 7 + [cmd(4, 0)] + [HIDE, cmd(1, 1)] * 21 + [cmd(21)]),
        SLOT['dust']: frames([f'X{i}' for i in range(12)], EXHAUST_STEP) + [cmd(21)],
        SLOT['move_loop']: [cmd(3, 1)] + frames(R, RIDE_STEP, 27) + [cmd(5)],
        SLOT['dash_native']: [cmd(3, 2), cmd(11, SLOT['spray'], 1, *SPRAY_AT)] + with_exhaust(W, 1, 30, EXHAUST_EVERY[1]) + [cmd(5)],
        SLOT['dash_native_sp']: [cmd(3, 2), cmd(11, SLOT['spray'], 1, *SPRAY_AT)] + with_exhaust(W, 1, 30, EXHAUST_EVERY[1]) + [cmd(5)],
        SLOT['charge']: charge,
        SLOT['dash']: ([cmd(3, 2), cmd(23, SOUND_ENGINE), cmd(11, SLOT['spray'], 1, *SPRAY_AT)]
                       + with_exhaust(W, 1, DASH_T, EXHAUST_EVERY[1]) + [cmd(21)]),
        SLOT['eject']: [cmd(3, 2)] + frames(E, EJECT_STEP) + [cmd(5)],
        SLOT['flight']: [cmd(3, 3), cmd(4, 2)] + frames(T, TUMBLE_STEP, FLIGHT_T) + [cmd(21)],   # R6：飞行中保留受击（受击框 3）
        # 效果对象（op12）以 op21 结束、播完即移除；R8（用户截图：异常的尾迹烟雾）：此前以 op5 结尾，尾气与车轮循环不消失、持续漂移
        # （LAB fx0：第 899 帧仍有 59 团尾气，最高升到离地约 250）
        SLOT['exhaust']: [cmd(7, *EXHAUST_DRIFT)] + frames([f'X{i}' for i in range(12)], EXHAUST_STEP) + [HIDE, cmd(1, 1), cmd(21)],
        SLOT['spray']: frames([f'S{i}' for i in range(8)], SPRAY_STEP, SPRAY_T) + [cmd(21)],
        SLOT['wheel_a']: [cmd(7, *WHEEL_HOPS[0])] + frames(['D0'], WHEEL_T) + [HIDE, cmd(1, 1), cmd(21)],
        SLOT['wheel_b']: [cmd(7, *WHEEL_HOPS[1])] + frames(['D1'], WHEEL_T) + [HIDE, cmd(1, 1), cmd(21)],
        SLOT['pop']: pop_sub,
    }
    return s


def bounds(tiles, anchors):
    """受击框 1 平骑、2 翘头（贴合车身，内缩 2）、3 飞行（翻滚帧中心）；攻击框 1 爆炸（原生 133 框 1 按原画朝左镜像）、2 飞行接触。"""
    def box(keys):
        x0 = min(-anchors[k][0] for k in keys); y0 = min(-anchors[k][1] for k in keys)
        x1 = max(tiles[k].shape[1] - anchors[k][0] for k in keys); y1 = max(tiles[k].shape[0] - anchors[k][1] for k in keys)
        return [x0 + 2, y0 + 2, x1 - x0 - 4, y1 - y0 - 2, 0]
    hits = [[0, 0, 0, 0, 0], box(['R0', 'R1', 'R2']), box(['W0', 'W1', 'W2', 'E0', 'E1', 'E2', 'E3']), [-20, -20, 40, 40, 0]]
    # 飞行接触框为整个车身（R6：撞到空中单位须爆炸；撞到地面单位时核心把车身移到离地 40 再爆炸）
    atks = [[0, 0, 0, 0, 7], [-46, -74, 88, 102, 7], [-22, -22, 44, 44, 7]]
    return hits, atks


def assemble(tiles, anchors, s):
    keys = list(tiles)
    page, xy = shelf_pack([Image.fromarray(tiles[k], 'RGBA') for k in keys])
    rects, words, start = [], [], {}
    for i, k in enumerate(keys):
        h, w = tiles[k].shape[:2]
        rects.append([xy[i][0], xy[i][1], w, h, int(anchors[k][0]), int(anchors[k][1]), 0, 0])
        start[k] = len(words)
        words += [1, i]
    # R0P：与 R0 同一图像，锚点为后轮着地点（翘起子层的旋转支点）
    r0 = keys.index('R0')
    rects.append(rects[r0][:4] + [rects[r0][4] + ANCHOR_SHIFT] + rects[r0][5:])
    start['R0P'] = len(words)
    words += [1, len(rects) - 1]
    anims = {}
    for slot, cmds in s.items():
        anims[slot] = [cmd(0, start[c['values'][0]]) if c.get('key') else c for c in cmds]
    return page, rects, words, anims


def rider_assets(rider):
    # 图集须为 2 的幂（GLES2；LAB bb3 中 28×43 的图集画成黑块），放进 32×64 画布
    h, w = rider.shape[:2]
    page = Image.new('RGBA', (32, 64), (0, 0, 0, 0))
    page.alpha_composite(Image.fromarray(rider, 'RGBA'), (0, 0))
    rects = [[0, 0, w, h, w // 2, h, 0, 0]]
    words = [1, 0]
    imp = json.loads((CONTENT / 'units' / 'pvz_imp_flight.json').read_text(encoding='utf-8'))['animations']
    anims = {k: v for k, v in imp.items()}
    anims['8'] = [cmd(3, 1), cmd(7, *RIDER_HOP), cmd(0, 0), cmd(1, 60), cmd(21)]
    hits = [[0, 0, 0, 0, 0], [-w // 2 + 3, -h + 2, w - 6, h - 2, 0]]
    return page, {'rects': rects, 'frames': words, 'script_count': len(anims), 'hit_bounds': hits,
                  'attack_bounds': [[0, 0, 0, 0, 0]]}, anims


# ---------- 落地单位：原版 162 的内部副本（R11） ----------
def native_scripts(uid):
    """原生单位的全部脚本（静态读取；同 artwork/ms7_bug_hive_20261029/build_bug_hive.py）。"""
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
    return [elfmem.script(d, frames, s)[0] for s in range(d[7])]


def rocketeer_unit():
    """槽 13 / 14 / 15 开头的死亡语音（op23）换为普通兵的三种，其余照原生 162。"""
    scripts = native_scripts(ROCKETEER_BASE)
    anims = {}
    for slot, voices in ROCKETEER_VOICES.items():
        cmds = [{'opcode': c['opcode'], 'values': list(c['values'])} for c in scripts[slot]]
        head = [c for c in cmds[:2] if c['opcode'] == 23]
        assert head and head[0]['values'] == [864] and (slot != 15 or [c['values'] for c in head] == [[864], [283]]), (slot, head)
        anims[str(slot)] = [cmd(23, v) for v in voices] + cmds[len(head):]
    ones = {k: [1, 1] for k in ('hp_multiplier', 'knockback_threshold_multiplier', 'damage_multiplier', 'special_damage_multiplier',
                                'move_speed_multiplier', 'production_interval_multiplier') + ONES}
    return {'key': ROCKETEER_KEY, 'base_id': ROCKETEER_BASE, 'faction': FACTION, 'identity': IDENTITY, 'available_from_start': True,
            **ones, 'shop_price': 10, 'ap': 35, 'production_reference_id': ROCKETEER_BASE, 'menu_reference_id': ROCKETEER_BASE,
            'internal_only': True, 'textures': [ROCKETEER_TEXTURE], 'icon': ROCKETEER_ICON, 'animations': anims,
            'localization': {lang: {'name': n, 'description': t} for lang, (n, t) in ROCKETEER_LOC.items()},
            'behaviors': [{'name': 'death_by_attribute', 'version': 1, 'params': dict(ROCKETEER_DEATH)}]}


# ---------- 头像 ----------
def user_icon():
    """用户构图中与原生绿格不同的像素（ICON_BOX 内），其余透明（同虫穴头像的做法；四角透明度的差异为导出所致，在 ICON_BOX 外）。"""
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
        if unit['key'] not in (KEY, RIDER_KEY) and icon.get('page') == 1 and 'atlas' not in icon:
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


# ---------- 审阅图（只按根层近似：不执行子层、效果对象、旋转与核心的移动） ----------
def strip(page, rects, words, hits, atks, anims, slot, ticks, scale=3):
    W, H, oy = 140, 110, 90
    cells = []
    for t in range(ticks):
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
            canvas.alpha_composite(page.crop((r[0], r[1], r[0] + r[2], r[1] + r[3])), (W // 2 - r[4], oy - r[5]))
        for table, idx, col in ((hits, hit, (0, 255, 0, 255)), (atks, atk, (255, 220, 0, 255))):
            if idx:
                x, y, w, h = table[idx][:4]
                d.rectangle([W // 2 + x, oy + y, W // 2 + x + w - 1, oy + y + h - 1], outline=col)
        d.text((2, 2), f'{slot}:{t}', fill=(255, 255, 0, 255))
        cells.append(canvas.resize((W * scale, H * scale), Image.NEAREST))
    cols = 8
    out = Image.new('RGBA', (cols * W * scale, ((len(cells) + cols - 1) // cols) * H * scale), (0, 0, 0, 255))
    for k, c in enumerate(cells):
        out.paste(c, ((k % cols) * W * scale, (k // cols) * H * scale))
    return out


def unit_common(v):
    return {'base_id': BASE, 'faction': FACTION, 'identity': IDENTITY, 'shop_price': v['shop_price'], 'available_from_start': True,
            'ap': v['ap'], 'hp_multiplier': v['hp_multiplier'], 'knockback_threshold_multiplier': v['knockback_threshold_multiplier'],
            'damage_multiplier': v['damage_multiplier'], 'special_damage_multiplier': v['special_damage_multiplier'],
            **{k: [1, 1] for k in ONES}, 'move_speed_multiplier': v['move_speed_multiplier'],
            'production_reference_id': BASE, 'production_interval_multiplier': v['production_interval_multiplier'],
            'status_word_values': v['status_word_values']}


def main():
    OUT.mkdir(exist_ok=True)
    tiles, anchors, rider = load()
    s = scripts()
    page, rects, words, anims = assemble(tiles, anchors, s)
    hits, atks = bounds(tiles, anchors)
    desc = {'rects': rects, 'frames': words, 'script_count': SCRIPT_COUNT, 'hit_bounds': hits, 'attack_bounds': atks}
    rpage, rdesc, ranims = rider_assets(rider)
    cell = user_icon()
    page.save(OUT / 'atlas.png'); rpage.save(OUT / 'rider.png'); Image.fromarray(cell, 'RGBA').save(OUT / 'icon.png')
    for name, ticks in (('charge', 48), ('dash', 8), ('eject', 12), ('flight', 24), ('neutral', 8), ('move_loop', 16),
                        ('blast', 8), ('exhaust', 24), ('spray', 16)):
        strip(page, rects, words, hits, atks, anims, SLOT[name], ticks).save(OUT / f'strip_{SLOT[name]:02d}_{name}.png')
    report = {'tiles': len(tiles), 'rects': len(rects), 'atlas': list(page.size), 'colors': len(set(page.getdata())),
              'anchors': {k: list(map(int, v)) for k, v in anchors.items()}, 'hit_bounds': hits, 'attack_bounds': atks}
    if '--preview' in sys.argv:
        (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k: v for k, v in report.items() if k != 'anchors'}, ensure_ascii=False))
        return
    index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
    for k in (KEY, RIDER_KEY, ROCKETEER_KEY):
        if k not in index['unit_ids']:
            index['unit_ids'][k] = max(index['unit_ids'].values()) + 1
    for tex, img in ((TEXTURE, page), (RIDER_TEXTURE, rpage)):
        obm = indexed_obm(img)
        (CONTENT / tex).write_bytes(obm)
        index['assets'][tex] = hashlib.blake2b(obm, digest_size=32).hexdigest()
    icon_raw = (CONTENT / 'unit_icon_02.obm').read_bytes()
    unit_path, rider_path = CONTENT / 'units' / FILE, CONTENT / 'units' / RIDER_FILE
    if unit_path.exists():   # 沿用已登记的位置；先清空旧头像范围（R9 由 46×43 改为 45×41）
        old = json.loads(unit_path.read_text(encoding='utf-8'))['icon']['rect']
        icon_raw = write_icon(icon_raw, np.zeros((old[3], old[2], 4), np.uint8), old)
        rect = [old[0], old[1], *ICON_SIZE]
    else:
        rect = find_icon_slot(icon_raw)
    (CONTENT / 'unit_icon_02.obm').write_bytes(write_icon(icon_raw, cell, rect))   # 该资源的摘要在 content.json 中为 null，保持不变
    v = VALUES
    loc = {lang: {'name': n, 'description': t} for lang, (n, t) in LOCALIZATION.items()}
    unit = {'key': KEY, **unit_common(v), 'image_direction': 270,
            'icon': {'page': 1, 'rect': list(rect), 'anchor': ICON_ANCHOR},
            'textures': [TEXTURE], 'sprite_descriptor': DESCRIPTOR,
            'animations': {str(k): anims[k] for k in sorted(anims)}, 'localization': loc, 'tags': ['ms7'],
            'behaviors': [{'name': 'bomb_bike', 'version': 1, 'params': {
                'charge_animation': SLOT['charge'], 'dash_animation': SLOT['dash'], 'eject_animation': SLOT['eject'],
                'flight_animation': SLOT['flight'], 'dash_speed': DASH_V0, 'dash_accel': DASH_ACCEL, 'dash_cap': DASH_CAP,
                'throw_range': THROW_RANGE, 'eject_speed': EJECT_SPEED, 'apex': APEX, 'gravity': GRAVITY,
                'land_offset': LAND_OFFSET, 'dash_limit': DASH_LIMIT, 'max_throw': MAX_THROW,
                'charge_ticks': 2 * len(POP_DEG) + CHARGE_T, 'eject_ticks': EJECT_STEP * len(EJECT),
                'rider_unit': RIDER_KEY}}]}
    rider_unit = {'key': RIDER_KEY, 'base_id': RIDER_BASE, 'faction': FACTION, 'identity': IDENTITY, 'shop_price': 10,
                  # R9：骑手生命 = 基准 160 × 4/3（Lv1–40 各等级等于原生 162；击退门槛倍率随生命，160 为 −1 不缩放），落地交给 162
                  'available_from_start': True, 'ap': 50, 'hp_multiplier': [4, 3], 'knockback_threshold_multiplier': [4, 3],
                  'production_reference_id': RIDER_BASE, 'production_interval_multiplier': [1, 1], 'special_damage_multiplier': [1, 1],
                  'image_direction': 270, 'icon': {'page': 1, 'rect': list(rect), 'anchor': ICON_ANCHOR},
                  'textures': [RIDER_TEXTURE], 'sprite_descriptor': RIDER_DESCRIPTOR,
                  'animations': {k: ranims[k] for k in sorted(ranims, key=int)}, 'localization': loc,
                  'menu_reference_id': 159, 'internal_only': True,
                  'behaviors': [{'name': 'para_drop_transform', 'version': 1, 'params': {'landing_unit': LANDING_UNIT}},
                                {'name': 'landing_keeps_hp', 'version': 1, 'params': {}},
                                {'name': 'thrown_flight', 'version': 1, 'params': {'forward': -18 - 2 * ANCHOR_SHIFT, 'height': 16, 'base_clearance': 0}}]}
    save_json(CONTENT / DESCRIPTOR, desc)
    save_json(CONTENT / RIDER_DESCRIPTOR, rdesc)
    save_json(unit_path, unit)
    save_json(rider_path, rider_unit)
    save_json(CONTENT / 'units' / ROCKETEER_FILE, rocketeer_unit())
    save_json(CONTENT / 'content.json', index)
    report.update(unit_ids={k: index['unit_ids'][k] for k in (KEY, RIDER_KEY, ROCKETEER_KEY)}, icon_rect=rect)
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'anchors'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
