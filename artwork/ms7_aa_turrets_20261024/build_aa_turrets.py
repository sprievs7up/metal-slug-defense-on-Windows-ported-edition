"""MS7 任务 1（废品岛）的三种 AA Turret：完好、Broken A、Broken B（2026-10-24，AGENTS 第 264 节）。

用户 2026-10-24 决定：三种都是建筑单位（工兵修筑），另有“已经出现在场地”的版本供之后的 MS7 / MSXX 地图预置；
完好形态直射，Broken A / B 抛物线射击且两者距离不同；炮弹的生成点须与各帧的炮口精确对齐。
- 建筑：基准 32（原生 ANTI AIR-CRAFT 阵地 BattleAction_Tnabe，由 74 修筑）：状态 10 / 20 / 70 槽 6 待机，30 近距槽 8，
  40 远距槽 9，80 击退槽 12（之后改用 17 / 18 / 19，本单位与 6 / 8 / 9 相同），100–120 损毁槽 13（原生另放随机小爆炸，
  播完放共用爆炸 0xff04 并移除），无绝招。原生 shotBullet 以槽 51（命中目标）与 48（落地）为弹体结束动作。
  内部单位（internal_only），关卡 placed / 出兵名单可直接引用，即“已经出现在场地”的版本。
- 修筑者：基准 5（沙包工兵 BattleAction_Kouhei，同能量核心），行为 build_structure，修筑对象为对应建筑。
- 完好形态：MSA 388（Scrap Cannon，BattleAction_Turret7）的图集与脚本原样（7turret_base_0 / _1，与 MS7 素材表同一像素画），
  槽号改为 Tnabe 的；水平火球（MSA 弹体脚本 16，op22 偏移与炮口火光为 MSA 原值），目的距离 600（状态词 19 / 26；经 attack_range_multiplier 后运行时为 1028）。
- Broken A / B：MS7 素材表（F:\\egg\\MS7，Gussprint 拆图）切图，按 MSA 388 的 14 组颜色对应换色；锚点：y = 外框底边 − 4、
  x 由底座逐帧配准（同法在完好形态上与 MSA 388 的 22 帧锚点全部一致，verification/ms7_aa_turret_20261024/align_frames.py）；
  炮管 45°（两条轮廓线每行移 1 像素），炮口 = 开火帧中炮管端面（x + y 最小的像素线）的中点；炮弹按用户 2026-10-24 要求
  参照原版 IRON ISO（UnitID 9，BattleAction_Ironiso，脚本 36–47）的样式：红 / 青 / 黄三色轮换的圆球弹头，开火后每 tick 在同一
  炮口放出一段尾迹（共 5 段，由大到小，沿同一弹道飞行），颜色相位与大小次序同 IRON ISO；圆球取素材表 EXTRA 区左表（同一样式的
  MS7 版本，青 / 红 / 黄 × 5 种大小）。命中 / 落地为第 1 行空中爆点，带爆风攻击框 2。
- 三种炮弹均为火焰属性（用户 2026-10-24；近距与普攻两组的属性字 21 / 28 = 1）。
- 弹道（LAB 标定，原生 32，runs/tnabe_cal_*）：世界坐标 = 脚本坐标 × 2；op7 [vx, vy, ax, ay] 每 tick 位移 = 速度 / 100 × 2，
  每 tick 速度增量 = 加速度 / 100 × 2；LAB 记录的弹体位置为生成点之后一步。弹体与效果对象在第一次绘制前已更新两次（op7 位移
  两步、脚本走到第 2 帧；开火 tick 截图中弹头比记录位置远一步、显示颜色序列的第 2 色，r2shot / r2swap），生成点据此回退两步。
运行：E:\\anaconda3\\python.exe -I artwork/ms7_aa_turrets_20261024/build_aa_turrets.py [--preview]
（--preview 只写 out/；否则另写 community_content/ 的图集、描述符、6 个单位文件、unit_icon_02.obm 与 content.json）。
"""
from pathlib import Path
import hashlib
import json
import math
import struct
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CONTENT = REPO / 'community_content'
OUT = HERE / 'out'
SHEET = Path(r'F:\egg\MS7\DS _ DSi - Metal Slug 7 - Enemies - AA Turrets.png')
MSA_UNIT = Path(r'F:\egg\research\metal_slug_attack\decoded\units\0388')
MSA_ICONS = Path(r'F:\egg\research\metal_slug_attack\decoded\unit_icons\unit_icon_02.obme.png')

_PVZ = REPO / 'artwork' / 'pvz_zombies_20261012' / 'build_pvz_zombies.py'
_src = _PVZ.read_text(encoding='utf-8')
_src = _src.replace("sys.path.insert(0, str(RT / 'packages'))", "").replace("os.add_dll_directory(str(RT / 'native'))", "")
pvz = type(sys)('pvzb')
pvz.__dict__['__file__'] = str(_PVZ)
exec(compile(_src, str(_PVZ), 'exec'), pvz.__dict__)
indexed_obm, save_json, shelf_pack = pvz.indexed_obm, pvz.save_json, pvz.shelf_pack

TEX_MSA0, TEX_MSA1, TEX_MS7 = 'aa_turret_0.obm', 'aa_turret_1.obm', 'aa_turret_ms7.obm'
SCRIPT_COUNT = 54
SLOT_HIT, SLOT_GROUND = 51, 48          # 原生 Tnabe::shotBullet：命中目标 0x33、落地 0x30
SLOT_NEAR_BULLET, SLOT_FAR_BULLET = 22, 23
SLOT_FX = (52, 53)                       # 完好形态：MSA 14（底座烟尘）、15（炮口火光与烟）
BALL_RADIUS = 5                          # 弹头（最大的圆，直径 10）半径（像素）：第一次绘制时弹头紧贴炮口外
SHELL_BOX = 8                            # 尾迹弹攻击框半边长（脚本单位）：原生以攻击框底边触地判定落地（LAB 标定）
LAND_MARGIN = 16                         # 落点 = 射程 + 16（世界）：停在射程边界的目标处于弹道下降段（LAB：落点等于射程时边界外侧 7 以内的据点打不到）
BALL_COLORS = ('red', 'cyan', 'yellow')   # IRON ISO 弹头的颜色轮换次序（脚本 36 / 42：帧 82 红、92 青、102 黄）
# IRON ISO 尾迹脚本 37–41 / 43–47：（颜色相位，大小序号 0–4）；第 k 段在开火后第 k tick 放出
TRAIL = ((1, 0), (2, 1), (0, 2), (1, 3), (2, 4))
SLOT_TRAIL = {22: 24, 23: 29}            # 近 / 远弹的尾迹脚本起始槽（各 5 段）
FIRE_ATTRIBUTE = 1                        # 火焰（原生攻击属性 1：BattleUnit::damage 以目标数据行字 8 + 1 的档位乘倍率）
EXPLOSION_ATTRIBUTE = 2                   # 爆炸（原生 32 与 IRON ISO 9 的属性字 21 / 28 均为 2；R5 用于 Broken α / β）
G = 0.6                                  # 抛物线弹的重力（脚本单位 / tick²，世界 1.2，同原生 32 远距弹）
# 数值（用户 2026-10-24）：Lv40 伤害完好 1000、A 900、B 1000；生命与 AP 参照原版建筑——完好形态（直射）参照加农炮
# （SPIKE BUNKER 75 修筑的 33：生命 Lv1 / 10 / 20 / 30 / 40 = 800 / 1400 / 2000 / 2600 / 3200，修筑者 AP 70），A / B 参照抛物线炮
# （ANTI AIR-CRAFT 74 修筑的 32，即本单位的基准：850 / 1475 / 2100 / 2725 / 3350，AP 60），A、B 生命相同；A 的炮弹快、B 的慢
# （炮管同为 45°、重力相同，快者飞得远：A 用加长的射程 × 10/7 = 185 / 500，B 用原生 130 / 350）。价格 100 仍为暂定（MSA 387）。
# 射程：完好近 / 远 = 原生 130 / 350 × 12/7（222 / 600，MSA 远距 600）。抛物线落点 = 各自射程 + LAND_MARGIN。
# R5（用户 2026-10-25）：AP 完好 100、α 80、β 90；生命完好与 β 不变、α 3600；伤害 α 850、β 1050、完好 1000 不变；
# α / β 为爆炸属性，完好仍为火焰；α 的射程为 IRON ISO（UnitID 9，状态词 6 / 7 = 240 / 460）的 90%（216 / 414），远于 β，
# 弹道仍为 45°、重力不变，落点由 516 降为约 430，弧顶随之降低；α 的攻击间隔快于 β（暂取 β 的 3/4，用户未给数值）；β 射程不变。
IRONISO_RANGE = (240, 460)               # 原生 IRON ISO 建筑 9 的状态词 6 / 7
# R6（用户 2026-10-25）：β 伤害 1200；α 的远距射程再加到吉利塔 · O MK.II（本体 1029，基准 GIRIDA-O 51 的远距 280 × 3/2，
# 游戏内读数 420；该单位无近距攻击），α 的近距射程仍为 IRON ISO 的 90%（216）。
GIRIDA_MK2_RANGE = 420
# R8（用户 2026-10-25）：削弱完好形态，远距射程 600 → 300，近距 222 与火球目的距离不变。attack_range_multiplier 由原生在
# 等级插值后应用（combat profile），状态词绝对值为倍率前的值：状态词 7 写 175，运行时 175 × 12/7 = 300（整除）；
# 状态词 19 / 26 写 600，运行时目的距离为 1028（R5、R7 的游戏内读数）。
INTACT_FAR_RANGE = 300
assert INTACT_FAR_RANGE * 7 % 12 == 0
TYPES = {
    'intact': {'key': 's1xlv.aa_turret', 'builder': 's1xlv.aa_turret_builder', 'file': 'aa_turret.json',
               'builder_file': 'aa_turret_builder.json', 'descriptor': 'aa_turret_descriptor.json',
               'range': [12, 7], 'destination': 600, 'tags': ['ms7', 'msa']},
    'broken_a': {'key': 's1xlv.aa_turret_broken_a', 'builder': 's1xlv.aa_turret_broken_a_builder',
                 'file': 'aa_turret_broken_a.json', 'builder_file': 'aa_turret_broken_a_builder.json',
                 'descriptor': 'aa_turret_broken_a_descriptor.json',
                 # 近距 IRON ISO 的 90%（R5）、远距吉利塔 · O MK.II（R6）；近 / 远比例与原生 32 不同，以状态词 6 / 7 绝对值写入
                 'ranges': (IRONISO_RANGE[0] * 9 // 10, GIRIDA_MK2_RANGE),
                 'rows': (4, 5, 6, 7), 'counts': (2, 6, 7, 1), 'tags': ['ms7']},
    'broken_b': {'key': 's1xlv.aa_turret_broken_b', 'builder': 's1xlv.aa_turret_broken_b_builder',
                 'file': 'aa_turret_broken_b.json', 'builder_file': 'aa_turret_broken_b_builder.json',
                 'descriptor': 'aa_turret_broken_b_descriptor.json', 'range': [1, 1],
                 'rows': (8, 9, 10, 11), 'counts': (2, 6, 6, 1), 'tags': ['ms7']},
}
NATIVE_RANGE = (130, 350)                # 原生 32 的状态词 6 / 7
SHOP_PRICE = 100                          # 暂定（MSA 387）
# 生命倍率以基准 32 为底：完好 3200 / 3350 = 64/67（Lv40 3200，Lv1 811，加农炮为 800）；伤害倍率以 32 的 750 为底
# R5：α 生命 3600 / 3350 = 72/67、伤害 850 / 750 = 17/15，β 伤害 1050 / 750 = 7/5；α 的攻击后等待为 β（原生 32）的 3/4（向上取整）：
# 远距词 27 32 → 24（attack_wait_multiplier），近距词 20 15 → 12（无对应倍率字段，以状态词绝对值写入）
VALUES = {'intact': {'ap': 100, 'hp_multiplier': [64, 67], 'damage_multiplier': [4, 3], 'attribute': FIRE_ATTRIBUTE,
                     'status_word_values': {'7': INTACT_FAR_RANGE * 7 // 12}},
          'broken_a': {'ap': 80, 'hp_multiplier': [72, 67], 'damage_multiplier': [17, 15], 'attribute': EXPLOSION_ATTRIBUTE,
                       'attack_wait_multiplier': [3, 4], 'status_word_values': {'20': -(-15 * 3 // 4)}},
          'broken_b': {'ap': 90, 'hp_multiplier': [1, 1], 'damage_multiplier': [8, 5], 'attribute': EXPLOSION_ATTRIBUTE}}   # R6：1200 / 750
LOCALIZATION = {   # 名称与说明由代理撰写，待用户确定与校对
    'intact': {
        'EN': ('AA TURRET', 'STAND. ATK : Cannon     SPEC. ATK : -\nAn anti-aircraft turret the Rebel Army set up on Scrap Island.\nFires fire shells straight ahead.'),
        'JP': ('対空砲台', '通常攻撃：砲撃     特殊攻撃：‐\nモーデン軍がスクラップ島に設置した対空砲台。\n火炎弾をまっすぐ撃ち出す。'),
        'KR': ('대공 포대', '일반 공격: 포격     특수 공격: -\n모덴군이 고철 섬에 설치한 대공 포대.\n화염탄을 똑바로 발사한다.'),
        'ES': ('TORRETA AA', 'ATQ ESTÁND. : Cañón     ATQ ESPEC. : -\nTorreta antiaérea del Ejército Rebelde en la Isla Chatarra.\nDispara proyectiles incendiarios en línea recta.'),
        'PT': ('TORRE AA', 'ATQ. PADR. : Canhão   ATQ. ESPEC. : -\nTorre antiaérea do Exército Rebelde na Ilha da Sucata.\nDispara projéteis incendiários em linha reta.'),
        'RU': ('ЗЕНИТНАЯ ТУРЕЛЬ', 'СТАНД. АТАК: Пушка   СПЕЦ. АТАК: -\nЗенитная турель армии мятежников на Острове Хлама.\nСтреляет зажигательными снарядами прямо вперёд.'),
        'FR': ('TOURELLE DCA', 'ATT. STAND : Canon   ATT. SPÉ : -\nTourelle antiaérienne des rebelles sur l\'île de la Ferraille.\nTire des obus incendiaires droit devant.'),
        'DE': ('FLAK-GESCHÜTZ', 'STD.-ANGR. : Kanone   SPEZ.-ANGR. : -\nFlakgeschütz der Rebellenarmee auf der Schrottinsel.\nFeuert Brandgranaten geradeaus.'),
        'IT': ('TORRETTA AA', 'ATC STAND.: Cannone   ATC SPEC.: -\nTorretta antiaerea dei ribelli sull\'Isola dei Rottami.\nSpara proiettili incendiari in linea retta.'),
        'ZT': ('防空砲台', '普通攻擊：砲擊     特殊攻擊：‐\n摩登軍設置在廢鐵島上的防空砲台。\n向正前方發射火焰砲彈。'),
        'ZS': ('防空炮台', '普通攻击：炮击     特殊攻击：‐\n摩登军设置在废品岛上的防空炮台。\n向正前方发射火焰炮弹。'),
    },
    'broken_a': {
        # R5：名称按用户“破损炮台”α / β，其他语言同样去掉“防空”；末句改为爆炸炮弹、射程远、射速快（不再写火焰）
        'EN': ('BROKEN TURRET α', 'STAND. ATK : Flak shell   SPEC. ATK : -\nA damaged anti-aircraft turret on Scrap Island.\nLobs shells in a long arc at a fast rate.'),
        'JP': ('破損砲台α', '通常攻撃：高射砲弾   特殊攻撃：‐\nスクラップ島に残された破損した対空砲台。\n砲弾を遠くへ放物線状に速いペースで撃ち出す。'),
        'KR': ('파손 포대 α', '일반 공격: 고사포탄   특수 공격: -\n고철 섬에 남은 파손된 대공 포대.\n포탄을 먼 곳에 포물선으로 빠르게 연달아 쏜다.'),
        'ES': ('TORRETA ROTA α', 'ATQ ESTÁND. : Proyectil   ATQ ESPEC. : -\nTorreta antiaérea dañada de la Isla Chatarra.\nLanza proyectiles en un arco largo a ritmo rápido.'),
        'PT': ('TORRE DANIF. α', 'ATQ. PADR. : Projétil   ATQ. ESPEC. : -\nTorre antiaérea danificada da Ilha da Sucata.\nLança projéteis em um arco longo em ritmo rápido.'),
        'RU': ('ПОВРЕЖД. ТУРЕЛЬ α', 'СТАНД. АТАК: Снаряд   СПЕЦ. АТАК: -\nПовреждённая зенитная турель с Острова Хлама.\nЧасто бросает снаряды по длинной дуге.'),
        'FR': ('TOURELLE HS α', 'ATT. STAND : Obus   ATT. SPÉ : -\nTourelle antiaérienne endommagée de l\'île de la Ferraille.\nLance des obus en arc long à cadence rapide.'),
        'DE': ('BESCH. GESCHÜTZ α', 'STD.-ANGR. : Flakgranate   SPEZ.-ANGR. : -\nBeschädigtes Flakgeschütz auf der Schrottinsel.\nFeuert Granaten in weitem Bogen mit hoher Kadenz.'),
        'IT': ('TORRETTA ROTTA α', 'ATC STAND.: Proiettile   ATC SPEC.: -\nTorretta antiaerea danneggiata dell\'Isola dei Rottami.\nLancia proiettili con un arco lungo a ritmo rapido.'),
        'ZT': ('破損砲台α', '普通攻擊：高射砲彈   特殊攻擊：‐\n殘留在廢鐵島上的破損防空砲台。\n以拋物線向遠處發射砲彈，射速較快。'),
        'ZS': ('破损炮台α', '普通攻击：高射炮弹   特殊攻击：‐\n残留在废品岛上的破损防空炮台。\n以抛物线向远处发射炮弹，射速较快。'),
    },
    'broken_b': {
        'EN': ('BROKEN TURRET β', 'STAND. ATK : Flak shell   SPEC. ATK : -\nA damaged anti-aircraft turret on Scrap Island.\nLobs powerful shells in a short arc at a slow rate.'),
        'JP': ('破損砲台β', '通常攻撃：高射砲弾   特殊攻撃：‐\nスクラップ島に残された破損した対空砲台。\n強力な砲弾を近くへ放物線状にゆっくり撃ち出す。'),
        'KR': ('파손 포대 β', '일반 공격: 고사포탄   특수 공격: -\n고철 섬에 남은 파손된 대공 포대.\n강력한 포탄을 가까운 곳에 포물선으로 천천히 쏜다.'),
        'ES': ('TORRETA ROTA β', 'ATQ ESTÁND. : Proyectil   ATQ ESPEC. : -\nTorreta antiaérea dañada de la Isla Chatarra.\nLanza potentes proyectiles en un arco corto a ritmo lento.'),
        'PT': ('TORRE DANIF. β', 'ATQ. PADR. : Projétil   ATQ. ESPEC. : -\nTorre antiaérea danificada da Ilha da Sucata.\nLança projéteis potentes em um arco curto em ritmo lento.'),
        'RU': ('ПОВРЕЖД. ТУРЕЛЬ β', 'СТАНД. АТАК: Снаряд   СПЕЦ. АТАК: -\nПовреждённая зенитная турель с Острова Хлама.\nМедленно бросает мощные снаряды по короткой дуге.'),
        'FR': ('TOURELLE HS β', 'ATT. STAND : Obus   ATT. SPÉ : -\nTourelle antiaérienne endommagée de l\'île de la Ferraille.\nLance de puissants obus en arc court à cadence lente.'),
        'DE': ('BESCH. GESCHÜTZ β', 'STD.-ANGR. : Flakgranate   SPEZ.-ANGR. : -\nBeschädigtes Flakgeschütz auf der Schrottinsel.\nFeuert starke Granaten in kurzem Bogen mit niedriger Kadenz.'),
        'IT': ('TORRETTA ROTTA β', 'ATC STAND.: Proiettile   ATC SPEC.: -\nTorretta antiaerea danneggiata dell\'Isola dei Rottami.\nLancia potenti proiettili con un arco corto a ritmo lento.'),
        'ZT': ('破損砲台β', '普通攻擊：高射砲彈   特殊攻擊：‐\n殘留在廢鐵島上的破損防空砲台。\n以拋物線向近處發射威力較大的砲彈，射速較慢。'),
        'ZS': ('破损炮台β', '普通攻击：高射炮弹   特殊攻击：‐\n残留在废品岛上的破损防空炮台。\n以抛物线向近处发射威力较大的炮弹，射速较慢。'),
    },
}
ONES = ('special_damage_multiplier', 'move_speed_multiplier', 'attack_wait_multiplier',
        'knockback_distance_multiplier', 'ballistic_range_multiplier')

# MS7 素材表 → MSA 调色板：MSA 388 与素材表完好形态逐像素一致的 14 个矩形中的 14 组颜色对应
# （verification/ms7_aa_worm_20261024/match_aa_page0.json）；Broken A 另有 (160,64,0)，按同色系 (120,32,0) → (132,41,8)
# 的换算写为 (173,74,8)。效果（尾迹弹、爆点、爆炸）的颜色在 MSA 中无对应，按 round((v / 8 + 1) × 255 / 31)（0 保持 0）推定。
BODY_COLORS = {
    (8, 8, 0): (16, 16, 0), (24, 24, 0): (33, 33, 8), (40, 40, 32): (49, 49, 41), (48, 32, 8): (57, 41, 16),
    (72, 0, 0): (82, 0, 0), (72, 72, 64): (82, 82, 74), (80, 64, 32): (90, 74, 41), (96, 0, 0): (107, 0, 0),
    (120, 32, 0): (132, 41, 8), (120, 104, 64): (132, 115, 74), (120, 120, 112): (132, 132, 123),
    (168, 152, 96): (181, 165, 107), (168, 160, 144): (181, 173, 156), (224, 224, 208): (239, 239, 222),
    (160, 64, 0): (173, 74, 8),
}
SHEET_BG = ((255, 255, 255), (0, 248, 0), (0, 128, 0), (0, 0, 0))
# 第 1 行空中爆点（暗红弹壳 → 褐 → 橙 → 黄色星形 → 火花）：火花稀疏，列投影会把一帧切成几段，按帧间 ≥ 3 列的空隙切取；
# 行带 = 上方白底之下至下一行烟雾之上（y 799–861）。R4（2026-10-24）：原区间切掉第 7 帧 x 181–193 与各帧 y 846 以下的火星。
BURST_COLS = ((3, 13), (17, 28), (32, 44), (48, 63), (67, 93), (97, 126), (130, 167), (171, 193))
BURST_ROWS = (799, 862)
# 第 4 行起的命中爆炸（白圈 → 橙圈 → 爆炸）：9 帧之间均有空列，按空列切取；行带 = 上一行烟雾之下至下一行之上（y 939–978）。
# R4（2026-10-24）：原区间自 y 930 起、含上一行烟雾的下缘碎块，切掉第 978 行（第 6–8 帧），前 3 帧按圆心等距切开而互相切进对方。完好形态的火球命中用这 9 帧。
EXPLOSION_COLS = ((3, 37), (41, 69), (73, 97), (101, 131), (136, 169), (174, 210), (215, 251), (256, 298), (303, 348))
EXPLOSION_ROWS = (939, 979)


# ---------- 素材表 ----------
def load_sheet():
    return np.array(Image.open(SHEET).convert('RGB')).astype(np.int32)


def sheet_rows(a):
    """精灵区（y < 795，白底）按 8 连通块求外框（面积 ≥ 300 且宽高 ≥ 20，标题文字与分隔线除外），按纵向重叠归行。"""
    fg = ~((a[:795] == 255).all(-1))
    n, _, st, _ = cv2.connectedComponentsWithStats(fg.astype(np.uint8), connectivity=8)
    boxes = sorted((tuple(int(v) for v in st[i][:4]) for i in range(1, n)
                    if st[i][4] >= 300 and st[i][2] >= 20 and st[i][3] >= 20), key=lambda b: (b[1], b[0]))
    rows = []
    for b in boxes:
        cy = b[1] + b[3] / 2
        for r in rows:
            if r['y0'] <= cy <= r['y1']:
                r['boxes'].append(b); r['y0'] = min(r['y0'], b[1]); r['y1'] = max(r['y1'], b[1] + b[3]); break
        else:
            rows.append({'y0': b[1], 'y1': b[1] + b[3], 'boxes': [b]})
    return [sorted(r['boxes']) for r in rows]


def crop(a, b):
    x, y, w, h = b
    blk = a[y:y + h, x:x + w]
    return blk, ~(blk == 255).all(-1)


def shift_score(a, ref, box, dx, K=14):
    (ra, rm), (ia, im) = crop(a, ref), crop(a, box)
    rh, rw = rm.shape
    ih, iw = im.shape
    score = 0
    for r in range(K):
        ry, iy = rh - 1 - r, ih - 1 - r
        xs = np.arange(rw) - dx
        ok = (xs >= 0) & (xs < iw)
        rx, ix = np.arange(rw)[ok], xs[ok]
        score += int((rm[ry, rx] & im[iy, ix] & (ra[ry, rx] == ia[iy, ix]).all(-1)).sum())
    return score


def register_dx(a, ref, box, R=10):
    """外框底边对齐（dy = 0），横向偏移取底部 14 行颜色相同数最多者：box 的列 c 对应 ref 的列 c + dx。"""
    return max((shift_score(a, ref, box, dx), dx) for dx in range(-R, R + 1))[1]


def to_rgba(blk, mask, table=None):
    out = np.zeros(blk.shape[:2] + (4,), np.uint8)
    for (y, x) in zip(*np.nonzero(mask)):
        c = tuple(int(v) for v in blk[y, x])
        out[y, x, :3] = table[c] if table is not None else fx_color(c)
        out[y, x, 3] = 255
    return out


def fx_color(c):
    return tuple(0 if v == 0 else min(255, int(round((v // 8 + 1) * 255 / 31))) for v in c)


def sheet_mask(blk):
    m = np.ones(blk.shape[:2], bool)
    for c in SHEET_BG:
        m &= ~(blk == c).all(-1)
    return m


def base_center(mask, rows=6):
    xs = np.nonzero(mask[-rows:])[1]
    return int(round((xs.min() + xs.max()) / 2))


def broken_frames(a, rows, spec):
    """Broken 两型的各帧：RGBA（MSA 调色板）、锚点 (ax, ay) 与行内序号。"""
    idle, fire, dest, wreck = (rows[r] for r in spec['rows'])
    assert tuple(map(len, (idle, fire, dest, wreck))) == spec['counts'], [len(idle), len(fire), len(dest), len(wreck)]
    ref = idle[0]
    _, ref_mask = crop(a, ref)
    ax0 = base_center(ref_mask)
    offsets = [register_dx(a, ref, b) for b in idle + fire]
    chain = [register_dx(a, ref, dest[0])]                 # 损毁段逐帧对前一帧链式配准（底座逐帧变形）
    seq = dest + wreck
    for prev, cur in zip(seq, seq[1:]):
        chain.append(chain[-1] + register_dx(a, prev, cur, R=8))
    frames = []
    for (group, boxes, dxs) in (('idle', idle, offsets[:len(idle)]), ('fire', fire, offsets[len(idle):]),
                                ('dest', dest, chain[:len(dest)]), ('wreck', wreck, chain[len(dest):])):
        for i, (b, dx) in enumerate(zip(boxes, dxs)):
            blk, m = crop(a, b)
            unknown = {tuple(int(v) for v in blk[y, x]) for y, x in zip(*np.nonzero(m))} - set(BODY_COLORS)
            assert not unknown, unknown
            frames.append({'group': group, 'i': i, 'box': list(b), 'img': to_rgba(blk, m, BODY_COLORS),
                           'ax': ax0 - dx, 'ay': b[3] - 4, 'dx': dx, 'mask': m})
    return frames, ax0


def muzzle(frame):
    """炮管 45° 指向左上：端面为 x + y 最小的不透明像素线（限左上四分之一），返回端面中点（像素角点坐标）。"""
    m = frame['mask']
    h, w = m.shape
    ys, xs = np.nonzero(m[:h // 2, :w // 2])
    s = xs + ys
    face = np.nonzero(s == s.min())[0]
    top, bottom = face[np.argmin(ys[face])], face[np.argmax(ys[face])]
    return ((xs[top] + xs[bottom]) / 2, (ys[top] + ys[bottom]) / 2), int(s.min()), len(face), int(ys[bottom])


def barrel_is_45(frame, face_bottom, n=6):
    """炮管 45° 的核对：端面下沿以下第 3 行起 n 行，左轮廓逐行右移 1 像素、右上轮廓（行内最右的炮管像素）逐行右移 1 像素。"""
    m = frame['mask']
    rows = range(face_bottom + 3, face_bottom + 3 + n)
    left = [int(np.nonzero(m[y])[0].min()) for y in rows]
    return all(b - a == 1 for a, b in zip(left, left[1:]))


# ---------- 效果 ----------
def sfx_tiles(a):
    tiles = {}
    # EXTRA 网格：黑线分格；左表 5 列为实心圆（由大到小），行为青、红、黄（IRON ISO 炮弹样式的 MS7 版本）
    region = a[970:1025, 210:380]
    black = (region == 0).all(-1)
    vcols = [210 + x for x in range(black.shape[1]) if black[:, x].sum() >= 30]
    hrows = [970 + y for y in range(black.shape[0]) if black[y].sum() >= 60]
    assert vcols[:6] == [220, 231, 242, 253, 264, 275] and hrows == [984, 995, 1006, 1017], (vcols, hrows)
    for ri, color in enumerate(('cyan', 'red', 'yellow')):
        for ci in range(5):
            xa, xb = vcols[ci], vcols[ci + 1]
            ya, yb = hrows[ri], hrows[ri + 1]
            blk = a[ya + 1:yb, xa + 1:xb]
            m = sheet_mask(blk)
            ys, xs = np.nonzero(m)
            blk, m = blk[ys.min():ys.max() + 1, xs.min():xs.max() + 1], m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            tiles[f'ball_{color}_{ci}'] = to_rgba(blk, m)
    for name, cols, (y0, y1) in (('burst', BURST_COLS, BURST_ROWS), ('explosion', EXPLOSION_COLS, EXPLOSION_ROWS)):
        for k, (x0, x1) in enumerate(cols):
            # 切取框左右外侧一列在行带内必须无精灵像素（框内为整帧、不含相邻帧）
            assert not sheet_mask(a[y0:y1, x0 - 1:x0]).any() and not sheet_mask(a[y0:y1, x1 + 1:x1 + 2]).any(), (name, k)
            blk = a[y0:y1, x0:x1 + 1]
            m = sheet_mask(blk)
            ys, xs = np.nonzero(m)
            tiles[f'{name}_{k}'] = (to_rgba(blk[ys.min():ys.max() + 1, xs.min():xs.max() + 1],
                                            m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]),
                                    (x0 + int(xs.min()), y0 + int(ys.min())))
    return tiles


# ---------- 弹道 ----------
def flight(S, v, acc, ground=0.0, limit=200):
    """脚本坐标的逐 tick 位置（第 k 次更新后 = S + Σ_{j<k} (v + j·acc)，k ≥ 1；第一次绘制为 k = 2），到达地面为止。"""
    pts, p, vv = [], np.array(S, float), np.array(v, float)
    for _ in range(limit):
        p = p + vv
        pts.append((p.copy(), vv.copy()))
        if p[1] + SHELL_BOX >= ground:     # 攻击框底边触地
            break
        vv = vv + acc
    return pts


def solve_speed(M_art, land_world):
    """45° 发射（脚本坐标向左上），重力 G：求使落地处距原点 land_world（世界）的初速 s。"""
    def landing(s):
        d = np.array([-1.0, -1.0]) / math.sqrt(2)
        v = d * s
        S = np.array(M_art) + d * BALL_RADIUS - 2 * v
        pts = flight(S, v, np.array([0.0, G]))
        return -pts[-1][0][0] * 2
    lo, hi = 0.2, 30.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if landing(mid) < land_world:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ---------- 脚本 ----------
def cmd(op, *v):
    return {'opcode': op, 'values': list(v)}


EMPTY = [cmd(0, -1), cmd(1, 1), cmd(21)]
KNOCKBACK_TICKS = 12                     # 击退（状态 80）动作时长：保持 R0–R6 的 12 tick（原生 Tnabe 在该动作播完时离开状态 80）


def knockback_idle(idle_script):
    """R7（用户 2026-10-25）：击退照 MSA——Turret7 的状态 80 播放第 11 号动作（与待机相同的帧 42 / 2），受损帧只在损毁时出现。
    取待机循环的帧序列重复至 KNOCKBACK_TICKS 后以 op21 结束；开头补 op3（MSD 切换动作清空受击框）。"""
    seq, cur = [], None
    for c in idle_script:
        if c['opcode'] == 0:
            cur = c['values'][0]
        elif c['opcode'] == 1:
            seq.append((cur, c['values'][0]))
    out, t, i = [cmd(3, 1)], 0, 0
    while t < KNOCKBACK_TICKS:
        f, w = seq[i % len(seq)]
        w = min(w, KNOCKBACK_TICKS - t)
        out += [cmd(0, f), cmd(1, w)]
        t, i = t + w, i + 1
    return out + [cmd(21)]


def msa_scripts(record):
    """MSA 388 → 完好形态（槽号按 Tnabe）：去掉 MSA 空操作 24–28；op11 子层 14 / 15 → 52 / 53；弹体 16 → 22 / 23。
    op22 偏移、炮口火光（子层 15）位置与带翻转标志的效果矩形均为 MSA 原值（翻转以锚点为中心，MSA 与 MSD 相同）。MSD 中弹体
    在第一次绘制前已更新两次；火球首次出现时处在炮口火光之内，开火 tick 截图中火光与火球之间无空隙（shot_intact_zoom.png）。"""

    def conv(slot, bullet=None):
        out = []
        for c in record['scripts'][slot]:
            op, v = c[0], list(c[1:])
            if op in (24, 25, 26, 27, 28):
                continue
            if op == 11:
                v[0] = {14: SLOT_FX[0], 15: SLOT_FX[1]}[v[0]]
            if op == 22:
                if bullet is None:
                    continue
                v[0] = bullet
            out.append(cmd(op, *v))
        return out
    s = {i: list(EMPTY) for i in range(SCRIPT_COUNT)}
    s[0] = conv(0)
    s[1] = conv(1)
    s[2] = conv(9)                       # 动作演示：开火动作，不发弹
    s[6] = conv(6)
    s[8] = conv(9, SLOT_NEAR_BULLET)
    s[9] = conv(9, SLOT_FAR_BULLET)
    # 击退：R0–R6 曾放 MSA 第 12 号（MSA 状态 70 的受损摇晃，帧 26–32 往返）；R7 改为 MSA 击退所用的待机画面（第 11 号）
    s[12] = knockback_idle(s[6])
    for k in (13, 14, 15, 16):
        s[k] = conv(13)
    s[17], s[18], s[19], s[20] = s[6], s[8], s[9], s[6]
    s[SLOT_NEAR_BULLET] = conv(16)
    s[SLOT_FAR_BULLET] = conv(16)
    s[SLOT_FX[0]] = conv(14)
    s[SLOT_FX[1]] = conv(15)
    return s


def explosion_script(frame_ids, blast):
    out = ([cmd(4, 2)] if blast else [])
    for k, f in enumerate(frame_ids):
        out += [cmd(0, f), cmd(1, 2)]
        if blast and k == 1:
            out.append(cmd(4, 0))
    return out + [cmd(0, -1), cmd(1, 1), cmd(21)]


def broken_scripts(fr, shot, bullets, burst, burst_ground):
    """fr：组名 → 帧号列表；shot：近 / 远两种弹体（偏移与脚本）；burst / burst_ground：空中 / 落地爆点帧号。"""
    idle, fire, dest, wreck = fr['idle'], fr['fire'], fr['dest'], fr['wreck']
    s = {i: list(EMPTY) for i in range(SCRIPT_COUNT)}
    loop = [cmd(0, idle[0]), cmd(1, 2), cmd(0, idle[1]), cmd(1, 2), cmd(5)]
    s[0] = list(loop)
    s[1] = list(loop)
    s[6] = [cmd(3, 1)] + loop

    def attack(bullet):
        frames_t = [idle[0]] * 3 + sum(([f, f] for f in fire), []) + [idle[0]]
        shot_t = 3
        events = {shot_t: [cmd(23, 200)]}
        if bullet is not None:
            off = shot[bullet]['offset']
            events[shot_t].insert(0, cmd(22, bullet, 0, *off))
            for k in range(len(TRAIL)):     # 同 IRON ISO：op12 第 2 值为绘制优先级，5 → 1
                events.setdefault(shot_t + 1 + k, []).append(cmd(12, SLOT_TRAIL[bullet] + k, len(TRAIL) - k, *off))
        out, cur, run = [cmd(3, 1)], None, 0
        for t, f in enumerate(frames_t):
            if f != cur or t in events:
                if run:
                    out.append(cmd(1, run))
                    run = 0
                if f != cur:
                    out.append(cmd(0, f))
                    cur = f
                out += events.get(t, [])
            run += 1
        return out + [cmd(1, run), cmd(21)]
    s[2] = attack(None)
    s[8] = attack(SLOT_NEAR_BULLET)
    s[9] = attack(SLOT_FAR_BULLET)
    s[12] = knockback_idle(s[6])         # 击退：R7 起为待机画面（R0–R6 为损毁前 4 帧往返），受损帧只在损毁时出现
    death = sum(([cmd(0, f), cmd(1, 2)] for f in dest), []) + [cmd(0, wreck[0]), cmd(1, 6), cmd(0, -1), cmd(1, 1), cmd(21)]
    for k in (13, 14, 15, 16):
        s[k] = list(death)
    s[17], s[18], s[19], s[20] = s[6], s[8], s[9], s[6]
    for slot in (SLOT_NEAR_BULLET, SLOT_FAR_BULLET):
        s[slot] = shot[slot]['script']
        for k, trail in enumerate(shot[slot]['trail']):
            s[SLOT_TRAIL[slot] + k] = trail
    s[SLOT_HIT] = explosion_script(burst, True)
    s[SLOT_GROUND] = explosion_script(burst_ground, True)
    return s


def ball_scripts(op7, ball_ids, n_land):
    """IRON ISO 样式：弹头（op4 攻击框 1，大小 0，颜色每 tick 红→青→黄循环）与 5 段尾迹效果（同一 op7，大小与颜色相位按 TRAIL）。
    尾迹沿弹头的弹道晚 1–5 tick 飞行，各自在落到弹头的落点时结束（n_land tick 后消失）。"""
    head = [cmd(4, 1), cmd(7, *op7)]
    for c in BALL_COLORS:
        head += [cmd(0, ball_ids[(c, 0)]), cmd(1, 1)]
    head.append(cmd(5))
    trails = []
    for phase, size in TRAIL:
        t = [cmd(7, *op7)]
        for k in range(n_land):
            t += [cmd(0, ball_ids[(BALL_COLORS[(phase + k) % 3], size)]), cmd(1, 1)]
        trails.append(t + [cmd(0, -1), cmd(1, 1), cmd(21)])
    return head, trails


# ---------- 头像 ----------
ICON_SIZE = (46, 43)
ICON_ANCHOR = [-5, -2]


def find_icon_slots(page, n, start=(1748, 768)):
    raw = bytearray(page)
    w, h = struct.unpack_from('<HH', raw, 4)
    alpha = np.frombuffer(bytes(raw[8:8 + w * h * 4]), np.uint8).reshape(h, w, 4)[..., 3]
    used = []
    for f in CONTENT.glob('units/*.json'):
        icon = json.loads(f.read_text(encoding='utf-8'))['icon']
        if icon.get('page') == 1 and 'atlas' not in icon:    # PvZ 单位的头像在自身图集中（无 page）
            used.append(icon['rect'])
    iw, ih = ICON_SIZE
    slots = []
    for y in range(start[1], h - ih, 2):
        for x in range(start[0] if y == start[1] else 0, w - iw, 2):
            r = [x, y, iw, ih]
            if any(not (x + iw + 2 <= u[0] or x >= u[0] + u[2] + 2 or y + ih + 2 <= u[1] or y >= u[1] + u[3] + 2)
                   for u in used + slots):
                continue
            if alpha[y:y + ih, x:x + iw].any():
                continue
            slots.append(r)
            if len(slots) == n:
                return slots
    raise RuntimeError('no free icon slot')


def write_icons(cells_rects):
    raw = bytearray((CONTENT / 'unit_icon_02.obm').read_bytes())
    assert raw[:4] == b'OI\x01\x20'
    w, h = struct.unpack_from('<HH', raw, 4)
    for cell, (ax, ay, iw, ih) in cells_rects:
        for j in range(ih):
            for i in range(iw):
                at = 8 + ((ay + j) * w + ax + i) * 4
                raw[at:at + 4] = bytes(int(v) for v in cell[j, i])
    return bytes(raw)


def icon_from_frame(img, msa_icon, msa_frame):
    """MSA 头像为待机帧左右镜像后的 46×43 裁切；按红色徽记的中心对齐同一取景，裁出 Broken 两型的头像。"""
    def roundel(rgba):
        r, g, b, a = (rgba[..., k].astype(int) for k in range(4))
        m = (a > 0) & (r >= 80) & (g <= 10) & (b <= 10)
        m[int(rgba.shape[0] * 0.6):] = False        # 底座上的红色饰线不计（只取上部的徽记）
        ys, xs = np.nonzero(m)
        return xs.mean(), ys.mean()
    mx, my = roundel(msa_icon)
    fx, fy = roundel(msa_frame[:, ::-1])
    # MSA 头像的裁切位置（镜像后帧内），用于核对取景规则
    msa_off = (fx - mx, fy - my)
    src = img[:, ::-1]
    sx, sy = roundel(src)
    x0, y0 = int(round(sx - mx)), int(round(sy - my))
    iw, ih = ICON_SIZE
    cell = np.zeros((ih, iw, 4), np.uint8)
    for j in range(ih):
        for i in range(iw):
            y, x = y0 + j, x0 + i
            if 0 <= y < src.shape[0] and 0 <= x < src.shape[1]:
                cell[j, i] = src[y, x]
    return cell, msa_off, (x0, y0)


# ---------- 主流程 ----------
def main():
    OUT.mkdir(exist_ok=True)
    (HERE / 'source').mkdir(exist_ok=True)
    a = load_sheet()
    rows = sheet_rows(a)
    assert [len(r) for r in rows[:12]] == [2, 8, 4, 8, 2, 6, 7, 1, 2, 6, 6, 1], [len(r) for r in rows[:12]]
    record = json.loads((MSA_UNIT / 'record.json').read_text(encoding='utf-8'))
    assert record['atlases'][0]['file'] == '7turret_base_0_out.obm' and record['script_count'] == 18
    msa0 = Image.open(MSA_UNIT / '7turret_base_0_out.obm.png').convert('RGBA')
    msa1 = Image.open(MSA_UNIT / '7turret_base_1_outt.obm.png').convert('RGBA')
    report = {'types': {}}

    # Broken 两型的帧
    broken = {}
    for name in ('broken_a', 'broken_b'):
        frames, ax0 = broken_frames(a, rows, TYPES[name])
        fire0 = next(f for f in frames if f['group'] == 'fire' and f['i'] == 0)
        idle0 = next(f for f in frames if f['group'] == 'idle' and f['i'] == 0)
        (mx, my), smin, nface, fb = muzzle(fire0)
        (ix, iy), ismin, _, ib = muzzle(idle0)
        assert barrel_is_45(fire0, fb) and barrel_is_45(idle0, ib), name
        broken[name] = {'frames': frames, 'ax0': ax0, 'muzzle_frame': (mx, my), 'muzzle_art': (mx - fire0['ax'], my - fire0['ay']),
                        'idle_muzzle_art': (ix - idle0['ax'], iy - idle0['ay'])}
        report['types'][name] = {'ax0': ax0, 'offsets': [[f['group'], f['i'], f['dx']] for f in frames],
                                 'fire0_muzzle_in_frame': [mx, my], 'fire0_face_sum': smin, 'face_pixels': nface,
                                 'fire0_anchor': [fire0['ax'], fire0['ay']], 'muzzle_art': broken[name]['muzzle_art'],
                                 'idle_muzzle_art': broken[name]['idle_muzzle_art']}

    # 效果与圆球（弹头与尾迹）
    tiles = sfx_tiles(a)
    balls = {(c, k): tiles[f'ball_{c}_{k}'] for c in BALL_COLORS for k in range(5)}

    # MS7 图集：Broken 两型的帧、尾迹弹、空中爆点、命中爆炸
    items = []   # (键, RGBA, 锚点)
    for name in ('broken_a', 'broken_b'):
        for f in broken[name]['frames']:
            items.append(((name, f['group'], f['i']), f['img'], (f['ax'], f['ay'])))
    for k, img in balls.items():
        items.append((('ball',) + k, img, (img.shape[1] // 2, img.shape[0] // 2)))     # 圆心
    for k in range(len(BURST_COLS)):
        img, _ = tiles[f'burst_{k}']
        items.append((('burst', k), img, (img.shape[1] // 2, img.shape[0] // 2)))     # 空中爆点：中心落在弹体位置
    for k in range(len(EXPLOSION_COLS)):
        img, _ = tiles[f'explosion_{k}']
        items.append((('explosion', k), img, (img.shape[1] // 2, img.shape[0] // 2)))  # 爆炸：中心落在命中处
    page, pos = shelf_pack([Image.fromarray(img, 'RGBA') for _, img, _ in items], sizes=((512, 256), (512, 512), (1024, 512)))
    rect_of = {}
    for i, (k, img, anchor) in enumerate(items):
        x, y = pos[i]
        rect_of[k] = [x, y, img.shape[1], img.shape[0], int(anchor[0]), int(anchor[1]), 0]
        if k[0] == 'burst':     # 落地爆点：同一块图，底边中点落在地面
            rect_of[('burst_ground', k[1])] = [x, y, img.shape[1], img.shape[0], img.shape[1] // 2, img.shape[0] - 1, 0]
    report['ms7_atlas'] = list(page.size)
    report['ms7_colors'] = len(set(page.getdata()))

    descriptors, scripts, preview = {}, {}, {}
    # 完好形态：MSA 388 的矩形（页 0 / 1）+ MS7 图集中的命中爆炸（页 2）
    rects = [list(r) for r in record['rects']]
    frames_list = list(record['frames'])
    ms7_frame = {}

    def add_frame(key, page_index):
        rects.append(rect_of[key] + [page_index])
        frames_list.extend([1, len(rects) - 1])
        return len(frames_list) - 2
    for k in range(len(EXPLOSION_COLS)):
        ms7_frame[('explosion', k)] = add_frame(('explosion', k), 2)
    s = msa_scripts(record)
    s[SLOT_HIT] = explosion_script([ms7_frame[('explosion', k)] for k in range(len(EXPLOSION_COLS))], False)
    s[SLOT_GROUND] = s[SLOT_HIT]
    descriptors['intact'] = {'rects': rects, 'frames': frames_list, 'script_count': SCRIPT_COUNT,
                             'hit_bounds': record['hit_bounds'], 'attack_bounds': record['attack_bounds']}
    scripts['intact'] = s
    report['types']['intact'] = {'msa_shot_offset': [c[1:] for c in record['scripts'][9] if c[0] == 22],
                                 'msa_flash_offset': [c[1:] for c in record['scripts'][9] if c[0] == 11]}

    # Broken 两型：页 0 为 MS7 图集
    for name in ('broken_a', 'broken_b'):
        spec, info = TYPES[name], broken[name]
        rects, frames_list, fid = [], [], {}

        def add(key):
            rects.append(rect_of[key] + [0])
            frames_list.extend([1, len(rects) - 1])
            return len(frames_list) - 2
        groups = {}
        for f in info['frames']:
            groups.setdefault(f['group'], []).append(add((name, f['group'], f['i'])))
        ball_ids = {k: add(('ball',) + k) for k in balls}
        burst_ids = [add(('burst', k)) for k in range(len(BURST_COLS))]
        burst_ground_ids = [add(('burst_ground', k)) for k in range(len(BURST_COLS))]
        M = np.array(info['muzzle_art'], float)
        d = np.array([-1.0, -1.0]) / math.sqrt(2)
        shot = {}
        ranges = list(spec['ranges']) if 'ranges' in spec else [r * spec['range'][0] // spec['range'][1] for r in NATIVE_RANGE]
        for slot, land in zip((SLOT_NEAR_BULLET, SLOT_FAR_BULLET), [r + LAND_MARGIN for r in ranges]):
            sp = solve_speed(M, land)
            v = d * sp
            op7 = [int(round(v[0] * 100)), int(round(v[1] * 100)), 0, int(round(G * 100))]
            while True:
                v_used = np.array(op7[:2], float) / 100
                S_used = np.round(M + d * BALL_RADIUS - 2 * v_used).astype(int)    # 第一次绘制（两次更新后）弹头紧贴炮口外
                pts = flight(S_used, v_used, np.array([0.0, op7[3] / 100]))
                # 落点按 tick 离散、初速取整后可能落在目标之前（R5：α 422.6 < 430）：初速逐级加 1 至落点不低于目标
                if -pts[-1][0][0] * 2 >= land:
                    break
                op7[0] -= 1
                op7[1] -= 1
            head, trails = ball_scripts(op7, ball_ids, len(pts))
            shot[slot] = {'offset': [int(S_used[0]), int(S_used[1])], 'op7': op7, 'ticks': len(pts),
                          'land_world': round(-pts[-1][0][0] * 2, 1), 'apex_world': round(-min(p[1] for p, _ in pts) * 2, 1),
                          'script': head, 'trail': trails}
        s = broken_scripts(groups, shot, (SLOT_NEAR_BULLET, SLOT_FAR_BULLET), burst_ids, burst_ground_ids)
        idle0 = info['frames'][0]
        hb = [-idle0['ax'] + 4, -idle0['ay'] + 2, idle0['img'].shape[1] - 8, idle0['ay'] + 1, 0]
        descriptors[name] = {'rects': rects, 'frames': frames_list, 'script_count': SCRIPT_COUNT,
                             'hit_bounds': [[0, 0, 0, 0, 0], hb],
                             'attack_bounds': [[0, 0, 0, 0, 0], [-SHELL_BOX, -SHELL_BOX, 2 * SHELL_BOX, 2 * SHELL_BOX, 7], [-17, -38, 37, 38, 7]]}
        scripts[name] = s
        report['types'][name]['shots'] = {str(k): {kk: vv for kk, vv in v.items() if kk not in ('script', 'trail')} for k, v in shot.items()}
        preview[name] = {'groups': groups, 'shot': shot, 'ball_ids': ball_ids, 'burst_ids': burst_ids}

    # 头像
    msa_icon_page = np.array(Image.open(MSA_ICONS).convert('RGBA'))
    msa_icon = msa_icon_page[953:953 + 43, 92:92 + 46]
    r0 = record['rects'][0]
    msa_idle = np.array(msa0)[r0[1]:r0[1] + r0[3], r0[0]:r0[0] + r0[2]]
    icons = {'intact': msa_icon}
    for name in ('broken_a', 'broken_b'):
        cell, msa_off, at = icon_from_frame(broken[name]['frames'][0]['img'], msa_icon, msa_idle)
        icons[name] = cell
        report['types'][name]['icon_crop'] = at
    report['msa_icon_roundel_offset'] = msa_off
    for name, cell in icons.items():
        Image.fromarray(cell, 'RGBA').save(OUT / f'icon_{name}.png')

    # 审阅图：炮口与弹体前几 tick 的位置
    previews(a, record, msa0, msa1, page, rect_of, descriptors, scripts, broken, preview)
    if '--preview' in sys.argv:
        (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, default=float)[:3000])
        return

    index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
    for name in ('intact', 'broken_a', 'broken_b'):
        for key in (TYPES[name]['builder'], TYPES[name]['key']):
            if key not in index['unit_ids']:
                index['unit_ids'][key] = max(index['unit_ids'].values()) + 1
    obms = {TEX_MSA0: indexed_obm(msa0), TEX_MSA1: indexed_obm(msa1), TEX_MS7: indexed_obm(page)}
    for fn, data in obms.items():
        (CONTENT / fn).write_bytes(data)
        index['assets'][fn] = hashlib.blake2b(data, digest_size=32).hexdigest()
    icon_raw = (CONTENT / 'unit_icon_02.obm').read_bytes()
    keys_with_icons = {json.loads(f.read_text(encoding='utf-8'))['key'] for f in CONTENT.glob('units/*.json')}
    existing = {}
    for name in ('intact', 'broken_a', 'broken_b'):
        f = CONTENT / 'units' / TYPES[name]['file']
        if f.exists():
            existing[name] = json.loads(f.read_text(encoding='utf-8'))['icon']['rect']
    need = [n for n in ('intact', 'broken_a', 'broken_b') if n not in existing]
    slots = find_icon_slots(icon_raw, len(need)) if need else []
    icon_rects = dict(existing)
    icon_rects.update(dict(zip(need, slots)))
    (CONTENT / 'unit_icon_02.obm').write_bytes(write_icons([(icons[n], icon_rects[n]) for n in ('intact', 'broken_a', 'broken_b')]))
    textures = {'intact': [TEX_MSA0, TEX_MSA1, TEX_MS7], 'broken_a': [TEX_MS7], 'broken_b': [TEX_MS7]}
    for name in ('intact', 'broken_a', 'broken_b'):
        spec = TYPES[name]
        save_json(CONTENT / spec['descriptor'], descriptors[name])
        builder, building = unit_files(name, scripts[name], textures[name], icon_rects[name])
        save_json(CONTENT / 'units' / spec['builder_file'], builder)
        save_json(CONTENT / 'units' / spec['file'], building)
    save_json(CONTENT / 'content.json', index)
    report['unit_ids'] = {k: index['unit_ids'][k] for n in TYPES for k in (TYPES[n]['builder'], TYPES[n]['key'])}
    report['icon_rects'] = icon_rects
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, default=float)[:3000])


def unit_files(name, anims, textures, icon_rect):
    spec = TYPES[name]
    loc = {lang: {'name': n, 'description': t} for lang, (n, t) in LOCALIZATION[name].items()}
    icon = {'page': 1, 'rect': list(icon_rect), 'anchor': ICON_ANCHOR}
    ones = {k: [1, 1] for k in ONES}
    val = VALUES[name]
    common = {'faction': 1, 'identity': 'Rebel Army', 'shop_price': SHOP_PRICE, 'available_from_start': True, 'ap': val['ap']}
    builder = {'key': spec['builder'], 'base_id': 5, **common, 'hp_multiplier': [1, 1], 'knockback_threshold_multiplier': [1, 1],
               'damage_multiplier': [1, 1], 'attack_range_multiplier': [1, 1], **ones,
               'production_reference_id': 5, 'production_interval_multiplier': [1, 1],
               'icon': icon, 'animations': {}, 'localization': loc, 'textures': ['donou.obm'], 'tags': spec['tags'],
               'behaviors': [{'name': 'build_structure', 'version': 1,
                              'params': {'structure': spec['key'], 'construction_time_multiplier': [1, 1]}}]}
    building = {'key': spec['key'], 'base_id': 32, **common, 'hp_multiplier': val['hp_multiplier'],
                # 击退门槛随生命倍率联动（第 6.1 节，原生 32 为 10）
                'knockback_threshold_multiplier': val['hp_multiplier'],
                'damage_multiplier': val['damage_multiplier'], 'attack_range_multiplier': spec.get('range', [1, 1]), **ones,
                'production_reference_id': 5, 'production_interval_multiplier': [1, 1],
                'image_direction': 270, 'menu_reference_id': 5, 'internal_only': True,
                'icon': icon, 'textures': textures, 'sprite_descriptor': spec['descriptor'],
                'animations': {str(k): v for k, v in sorted(anims.items())}, 'localization': loc, 'tags': spec['tags']}
    if 'attack_wait_multiplier' in val:
        building['attack_wait_multiplier'] = val['attack_wait_multiplier']
    # 完好形态为火焰（用户 2026-10-24），Broken α / β 为爆炸（R5，用户 2026-10-25）
    building['attack_attributes'] = {'melee': val['attribute'], 'normal': val['attribute']}
    words = dict(val.get('status_word_values', {}))
    if 'ranges' in spec:
        words.update({'6': spec['ranges'][0], '7': spec['ranges'][1]})
    if 'destination' in spec:
        # 直射火球：目的距离（状态词 19 / 26）> 0 且弹速为 0 时，原生按脚本 op7 运动、越过目的点结束（addBulletImpl）
        words.update({'19': spec['destination'], '26': spec['destination']})
    if words:
        building['status_word_values'] = dict(sorted(words.items(), key=lambda kv: int(kv[0])))
    return builder, building


# ---------- 审阅图 ----------
def draw_rect(canvas, page_img, rect, origin, S, mirror=False):
    x, y, w, h, ax, ay = rect[:6]
    tile = page_img.crop((x, y, x + w, y + h))
    left = -ax
    if rect[6] & 1:     # 原生 GraphicsOpt::drawConv：翻转标志与单位镜像按位异或，以锚点为中心翻转（瓦片占 [ax − w, ax]）
        tile = tile.transpose(Image.FLIP_LEFT_RIGHT)
        left = ax - w
    tile = tile.resize((w * S, h * S), Image.NEAREST)
    canvas.alpha_composite(tile, (int(round(origin[0] + left * S)), int(round(origin[1] - ay * S))))


def previews(a, record, msa0, msa1, page, rect_of, descriptors, scripts, broken, preview):
    S = 6
    pages = {'intact': [msa0, msa1, page], 'broken_a': [page], 'broken_b': [page]}
    for name in ('intact', 'broken_a', 'broken_b'):
        desc, s = descriptors[name], scripts[name]

        def frame_rects(fid):
            n = desc['frames'][fid]
            return [desc['rects'][r] for r in desc['frames'][fid + 1:fid + 1 + n]]
        # 远距攻击槽 9 的逐 tick 帧序列与弹体（按脚本与标定的运动模型）
        seq, bullet, subs, effects = [], None, [], []
        cur = None
        for c in s[9]:
            if c['opcode'] == 0:
                cur = c['values'][0]
            elif c['opcode'] == 12:          # 效果对象（尾迹）：自放出的 tick 起按其脚本的 op7 运动
                effects.append((len(seq), c['values'][0], c['values'][2], c['values'][3]))
            elif c['opcode'] == 11:          # 子层：自挂上的 tick 起按其脚本播放，位置为 (x, y)
                subs.append((len(seq), c['values'][0], c['values'][2], c['values'][3]))
            elif c['opcode'] == 22:
                bullet = {'slot': c['values'][0], 'offset': c['values'][2:4], 'start_tick': len(seq)}
            elif c['opcode'] == 1:
                seq += [cur] * c['values'][0]
        bs = s[bullet['slot']]
        op7 = next(c['values'] for c in bs if c['opcode'] == 7)
        bframes = []
        cur = None
        for c in bs:
            if c['opcode'] == 0:
                cur = c['values'][0]
            elif c['opcode'] == 1:
                bframes += [cur] * c['values'][0]
            elif c['opcode'] == 5:
                break
        while len(bframes) < 12:
            bframes += bframes[-4:] if len(bframes) >= 4 else bframes
        v = np.array(op7[:2], float) / 100
        acc = np.array(op7[2:4], float) / 100
        tiles = []
        t0 = bullet['start_tick']
        for t in range(max(0, t0 - 2), min(len(seq), t0 + 10)):
            W, H = 150 * S, 110 * S
            canvas = Image.new('RGBA', (W, H), (70, 74, 84, 255))
            org = (100 * S, 95 * S)
            for r in frame_rects(seq[t]):
                draw_rect(canvas, pages[name][r[7]], r, org, S)
            for t_on, sub, sx, sy in subs:
                fs = []
                cur = None
                for c in s[sub]:
                    if c['opcode'] == 0:
                        cur = c['values'][0]
                    elif c['opcode'] == 1:
                        fs += [cur] * c['values'][0]
                    elif c['opcode'] in (5, 21):
                        break
                k_sub = t - t_on
                if 0 <= k_sub < len(fs) and fs[k_sub] is not None and fs[k_sub] >= 0:
                    for r in frame_rects(fs[k_sub]):
                        draw_rect(canvas, pages[name][r[7]], r, (org[0] + sx * S, org[1] + sy * S), S)
            for t_on, eff, ex, ey in effects:
                k_eff = t - t_on
                if k_eff < 0:
                    continue
                es = s[eff]
                e7 = next(c['values'] for c in es if c['opcode'] == 7)
                fs = []
                cur = None
                for c in es:
                    if c['opcode'] == 0:
                        cur = c['values'][0]
                    elif c['opcode'] == 1:
                        fs += [cur] * c['values'][0]
                    elif c['opcode'] in (5, 21):
                        break
                if k_eff + 1 < len(fs) and fs[k_eff + 1] is not None and fs[k_eff + 1] >= 0:     # 第一次绘制前已更新两次
                    q, vq = np.array([ex, ey], float), np.array(e7[:2], float) / 100
                    for _ in range(k_eff + 2):
                        q = q + vq
                        vq = vq + np.array(e7[2:4], float) / 100
                    for r in frame_rects(fs[k_eff + 1]):
                        draw_rect(canvas, pages[name][r[7]], r, (org[0] + q[0] * S, org[1] + q[1] * S), S)
            d = ImageDraw.Draw(canvas)
            k = t - t0
            if k >= 0:
                p = np.array(bullet['offset'], float)
                vv = v.copy()
                for _ in range(k + 2):
                    p = p + vv
                    vv = vv + acc
                for r in frame_rects(bframes[k + 1]):
                    draw_rect(canvas, pages[name][r[7]], r, (org[0] + p[0] * S, org[1] + p[1] * S), S)
                d.ellipse((org[0] + p[0] * S - 4, org[1] + p[1] * S - 4, org[0] + p[0] * S + 4, org[1] + p[1] * S + 4), outline=(0, 255, 255), width=2)
            if name != 'intact':
                mx, my = broken[name]['muzzle_art']
                d.line((org[0] + mx * S - 10, org[1] + my * S, org[0] + mx * S + 10, org[1] + my * S), fill=(255, 0, 255), width=2)
                d.line((org[0] + mx * S, org[1] + my * S - 10, org[0] + mx * S, org[1] + my * S + 10), fill=(255, 0, 255), width=2)
            d.line((org[0] - 8, org[1], org[0] + 8, org[1]), fill=(255, 255, 0), width=1)
            d.text((6, 6), f'{name} slot9 t{t}' + (f' bullet k{k}' if k >= 0 else ''), fill=(255, 255, 255))
            tiles.append(canvas)
        sheet = Image.new('RGB', (tiles[0].width * 2, tiles[0].height * ((len(tiles) + 1) // 2)), (40, 40, 40))
        for i, tl in enumerate(tiles):
            sheet.paste(tl.convert('RGB'), ((i % 2) * tl.width, (i // 2) * tl.height))
        sheet.save(OUT / f'muzzle_{name}.png')
        # 全部动作的帧条（待机 6、近距 8、远距 9、击退 12、损毁 13）
        for slot in (6, 8, 9, 12, 13):
            seq = []
            cur = None
            for c in s[slot]:
                if c['opcode'] == 0:
                    cur = c['values'][0]
                elif c['opcode'] == 1:
                    seq += [cur] * c['values'][0]
            S2 = 3
            W2 = 110 * S2
            strip = Image.new('RGBA', (W2 * min(len(seq), 12), 90 * S2 * ((len(seq) + 11) // 12)), (70, 74, 84, 255))
            for i, fid in enumerate(seq):
                tile = Image.new('RGBA', (W2, 90 * S2), (70, 74, 84, 255))
                if fid is not None and fid >= 0:
                    for r in frame_rects(fid):
                        draw_rect(tile, pages[name][r[7]], r, (70 * S2, 80 * S2), S2)
                ImageDraw.Draw(tile).line((70 * S2 - 6, 80 * S2, 70 * S2 + 6, 80 * S2), fill=(255, 255, 0))
                strip.alpha_composite(tile, ((i % 12) * W2, (i // 12) * 90 * S2))
            strip.convert('RGB').save(OUT / f'strip_{name}_slot{slot:02d}.png')
    # 弹道示意（世界坐标）
    W, H = 1200, 360
    img = Image.new('RGB', (W, H), (30, 32, 38))
    d = ImageDraw.Draw(img)
    gy = 320
    d.line((0, gy, W, gy), fill=(120, 120, 120))
    for name, col in (('broken_a', (255, 160, 60)), ('broken_b', (90, 200, 255))):
        for slot, sh in preview[name]['shot'].items():
            v = np.array(sh['op7'][:2], float) / 100
            pts = flight(np.array(sh['offset'], float), v, np.array([0.0, sh['op7'][3] / 100]))
            xy = [(60 - p[0] * 2, gy + p[1] * 2) for p, _ in pts]
            d.line([(60 - sh['offset'][0] * 2, gy + sh['offset'][1] * 2)] + xy, fill=col, width=2)
            d.text((xy[-1][0] - 20, gy + 8 + (12 if slot == SLOT_FAR_BULLET else 0)), f'{name} {slot}: {sh["land_world"]:.0f}', fill=col)
    img.save(OUT / 'trajectories.png')


if __name__ == '__main__':
    main()
