"""IRON CAB（s1xlv.iron_cab）资源与单位文件生成（2026-10-19）。

《合金弹头6》第 1 关多足列车的车头，素材取自《Metal Slug Attack》单位 IRON CAB（source/MSA_Iron_Cab.png），
由 cut_frames.py 切帧并计算锚点（frames/、frames.json）。按 MSA 素材原尺寸 1:1 使用（MSA 素材比 MS6 录像中的车头高约 28%，
verification/iron_cab_20261019/size_compare_ms6_vs_msa.jpg）。R1 曾因车顶约 1/3 在上方 HUD 之下而整体缩小到 0.65 倍，
缩小后像素画糊掉（用户 2026-10-19 实机反馈），R2 恢复原尺寸，素材像素不经重采样与改色。
R3（用户 2026-10-19）：激光炮后端的平涂块改画为圆形端盖、炮体加黑色描边（fix_cannon.py，写入 derived/cannon/）；
激光炮整体移到车体平底（x −39 起）正下方，放下与收起时从车底面竖直伸出与收回，伸出前完全藏在车体内
（炮体高于车底面的像素不画），不再从车头前缘或前部斜板处突然出现，炮杆也不再从腿部圆顶下方长出。
R4（用户 2026-10-19 实机截图）：本体再下移 4 像素（DROP 8），激光炮放下后再向下多伸出 8 像素。
R5（用户 2026-10-19）：光束改细（与炮口发射点的激光对齐，并以光球中心为中线），导弹发射改试 M-15A 的发射音效（SoundID 208）。
R7（用户 2026-10-19）：光束改为自制（make_beam.py），与炮口光球相接、色带取光球的环。
R8（用户 2026-10-19）：修正导弹落点（此前全部比设计近 108 世界单位），最远一枚落在开始射击的距离 550 处。
复用 PvZ 生成脚本的 Sheet、finish 与动作片段工具。

攻击方式依据 MSA 单位展示视频（https://www.youtube.com/watch?v=FIGLw7bCuFs ）：普通攻击从车顶发射管连续射出导弹，
导弹升空后竖直落到敌人身上（78.8–80.4 秒）；特殊攻击从车底放下激光炮，蓄力后放出横贯画面的贯穿光束（87.6–90.4 秒）。

基准为原版僵尸（青年）UnitID 313（BattleAction_ZombieBrain：状态 10/20/40/50/70/80/100·110/120 依次使用槽
6/7/9/10/11/12/13/15；槽 0–2 为菜单用的待机、行走与攻击），与巨型 Hunter Walker 相同：普通攻击按脚本 op22 发射导弹弹体，
弹体（BulletAction_ZombieBrain）的轨迹由弹体槽的 op7 决定，命中目标进入状态 60 播放槽 21、落地进入状态 61 播放槽 22。
特殊攻击的光束为单位自身帧上的攻击框 2（与 KT-21 喷火相同），每次 op4 重新开始一次攻击（可再次命中）。

数值（用户 2026-10-19 确认的草案）：AP 650（R6 用户设定；R1–R5 为 550）；Lv40 生命 36000；击退门槛随生命（第 6.1 节）；移速 1.8；再出击 1650 tick；
普通攻击射程 550、6 枚导弹每枚 Lv40 600（单体）；特殊攻击贯穿激光 3 段每段 Lv40 2800、光束长 800（世界单位），
冷却 2100 tick、出场后第一次 1400；无近距攻击；勋章 350、开局可购买、强化费用基数 550。

运行：windows_runtime/python.exe artwork/iron_cab_20261019/build_iron_cab.py
（写入 community_content/ 与本目录 out/、derived/；头像写入 community_content/unit_icon_02.obm 的空位；音效从 source/sounds/
复制为 community_content/ironcab_*.msdf 并登记在 content.json 的 sounds）。
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
sys.path.insert(0, str(REPO / 'artwork' / 'pvz_zombies_20261012'))
sys.path.insert(0, str(HERE))
import build_pvz_zombies as pvz  # noqa: E402
from build_pvz_zombies import F, op, loop  # noqa: E402
from PIL import Image  # noqa: E402
import fix_cannon  # noqa: E402
import make_beam  # noqa: E402

CONTENT = REPO / 'community_content'
FRAMES = HERE / 'frames'
DERIVED = HERE / 'derived'
OUT = HERE / 'out'
DATA = json.loads((HERE / 'frames.json').read_text(encoding='utf-8'))
CANNON = fix_cannon.build(DATA)     # 修正后的激光炮帧（derived/cannon/），锚点同吊杆

KEY = 's1xlv.iron_cab'
TEXTURE, DESCRIPTOR = 'iron_cab.obm', 'iron_cab_descriptor.json'
ICON_ATLAS = 'unit_icon_02.obm'
# 头像（2026-10-21 修订，AGENTS 第 188 节）：MSA 头像图集 unit_icon_02.obme 的原格 (480,647) 42×46（透明底剪影），
# 内框 40×40 在格的左下，向上越出 6 像素，锚点 −5,1（同原生 46 高头像）；原格副本由
# artwork/iron_sentinel_msa_20261021/msa_icons.py 保存。此前为 1:1 裁出的 40×40（锚点 −5,−5），填满内框而像被框住。
ICON_AT, ICON_SIZE, ICON_ANCHOR = (1600, 768), (42, 46), [-5, 1]
ICON_SOURCE = HERE.parent / 'iron_sentinel_msa_20261021' / 'source' / 'msa_icon_iron_cab_480_647.png'

# 音效：导弹爆炸取《合金弹头6》第 1 关 Boss（MS6_OST_ST01.osb），激光蓄力与发射取第 5 关 Boss（MS6_OST_ST05.osb）：
# SE_BS5_LASER1 前 0.2 秒渐强、频谱重心由 1.0 kHz 升到 5.2 kHz（蓄力），SE_BS5_LASER2 为 1.07 秒的持续高频（光束）。
# 被击败的大爆炸沿用原版基寇卡损毁音效（SoundID 253）。MSA 中 IRON CAB 的音效未经录像比对，以上为同作品的近似选用。
# R5（用户 2026-10-19）：导弹发射改试 M-15A 的发射音效（原版 SoundID 208 B4_MISSL，0.85 秒），仍在每次齐射第 1、4 枚播放；
# R1–R4 为 MS6 第 1 关 Boss 的 SE_BS1_MISSILE（source/sounds/ 保留，未登记）。
SOUND_SOURCE = HERE / 'source' / 'sounds'
SOUNDS = {'bomb': 'SE_BS1_BOMB', 'charge': 'SE_BS5_LASER1', 'laser': 'SE_BS5_LASER2'}
SND = {name: f's1xlv.ironcab_{name}' for name in SOUNDS}
LAUNCH_SOUND = 208
DEATH_BLAST = 253

WORLD = 2                       # 战场中 1 精灵像素 = 2 世界单位（状态词 7 等射程为世界单位）
SCALE = 1                       # R2（用户 2026-10-19）：不缩小，MSA 素材原尺寸 1:1（R1 的 0.65 倍缩小使像素画糊掉）
DROP = 8                        # 本体各帧下移的精灵像素（素材脚底在原点以上 1 行；R2/R3 为 4，R4 用户实机截图要求再下移 4；0.65 倍时为 3）
FRONT = round(62 * SCALE)       # 本体受击框半宽（精灵像素）：导弹落点距离从本体前缘算起
HIT_RECT = [-FRONT, -round(203 * SCALE) + DROP, 2 * FRONT, round(203 * SCALE) - DROP, 0]
WALK_HOLD = round(4 * 0.65 / SCALE)   # 行走每帧 tick：着地的脚每帧相对车体后移约 5.4 精灵像素（原尺寸），移速 1.8 时为 6 tick

# 普通攻击：导弹自发射管口竖直升空 → 画面外横移到落点上方 → 竖直落下（带攻击框 1）
NORMAL_RANGE = 550
MISSILE_DIST = tuple(NORMAL_RANGE * (i + 1) // 6 for i in range(6))   # 6 枚落点：91 … 550（世界单位，距本体前缘）
MISSILE_SLOTS = [16, 17, 18, 19, 20, 23]
TOP = 260                       # 横移高度（地面以上精灵像素；原尺寸导弹长 49，弹尾也在画面上沿之外）
RISE_V, FALL_V = 10.0, 9.0      # 上升、下落速度（精灵像素/tick）
TRAVEL_TICKS = 6
MISSILE_RECT = [-4, -10, 8, 10, 7]      # 攻击框 1：弹头（锚点为弹头尖端）
SHOT_TICKS = 3                  # 每枚导弹间隔

# 特殊攻击：激光炮吊杆顶端在原尺寸单位坐标中的位置。R3：车体底面自 x −39 起为平底（−101），前部斜板与车头在其左侧；
# 用户在截图上画线要求炮整体在该线右侧。修正后各帧炮体（不含蓄力光球与光束）最左为第 11 帧相对吊杆 −48，
# 吊杆放在 x 10 时各帧炮体都在 x −38 以右（第 0 帧最左 −34）。R4（用户 2026-10-19）：炮再向下多伸出 8 像素，
# 吊杆顶端在车底面以上 5 像素（仍被车体遮住，不需补画吊杆；R3 为 13 像素）。
# 放下时自完全藏在车体内的高度竖直下降（LOWER_FRAMES 帧），收起时倒放。
# 光束自光球中心向左 BEAM_LEN 精灵像素（800 世界单位，为玩法数值，不随画面缩小）
CANNON_AT = (10, -106)
LOWER_FRAMES = 12
HULL_CAP = -100                 # 行走第 1 帧中此行以上、且起点高于 −110 的不透明段属于车体，其余为腿
BEAM_LEN = 400
# 光束（R7，用户 2026-10-19：光束要与光球对齐、颜色连续，自制光束）：make_beam.py 按炮帧 4、5 的光球画出光束，
# 状态为 (炮帧, 光束半高)。发射时与炮帧同步每 2 tick 交替：帧 4（光球半径 16）配 17 像素、帧 5（半径 12）配 13 像素；
# 消散为帧 5 配 11、9 像素，再为帧 6 配 5、3、1 像素的细光束（帧 6 线条的颜色）。攻击框高度不变（32）。
# R5 用 MSA 素材的 beam 3/4（18/14）、R1–R4 用 beam 0/1（32/28），均自光球中心盖在光球上。
BEAM_FIRE = ((4, 8), (5, 6))
BEAM_FADE = ((5, 5), (5, 5), (5, 4), (5, 4), ('thin', 2), ('thin', 2), ('thin', 1), ('thin', 1), ('thin', 0))
BEAM = make_beam.build(CANNON, [st for st in dict.fromkeys(BEAM_FIRE + BEAM_FADE) if st[0] != 'thin'])
LASER_PULSES = (0, 6, 12)       # 光束开始后第 n tick 各开始一次攻击（共 3 段）

# 效果脚本槽（op12）
SLOT = {'boom_fx': 24, 'blast_fx': 25, 'smoke_fx': 26, 'debris': [27, 28, 29, 30], 'final': list(range(31, 40))}
SCRIPT_COUNT = 40

STATS = {
    'ap': 650, 'shop_price': 350, 'upgrade_cost_base': 550,      # R6：AP 550 → 650（用户设定）
    'hp_multiplier': [180, 17],                     # 僵尸（青年）Lv40 3400 → 36000
    'knockback_threshold_multiplier': [180, 17],    # 随生命（第 6.1 节）：30 → 318
    'production_interval_multiplier': [33, 13],     # 650 → 1650 tick
    'damage_multiplier': [1, 1],                    # 每枚导弹 Lv40 600
    'special_damage_multiplier': [14, 3],           # 激光每段 Lv40 2800
    'move_speed_multiplier': [3, 4],                # 2.4 → 1.8
}

TEXT = {
    'EN': ('IRON CAB', 'STAND. ATK : Missile barrage     SPEC. ATK : Piercing laser\n'
                       'A multi-legged walking weapon the Rebels built from a steam locomotive.\n'
                       'The laser cannon under its hull pierces a whole line of enemies.'),
    'JP': ('アイアンキャブ', '通常攻撃：ミサイル連射   特殊攻撃：貫通レーザー\n反乱軍が蒸気機関車を改造した多脚歩行兵器。\n'
                       '車体下のレーザー砲は敵の列をまとめて貫く。'),
    'KR': ('아이언 캡', '일반 공격: 미사일 연사   특수 공격: 관통 레이저\n반란군이 증기 기관차를 개조한 다각 보행 병기.\n'
                    '차체 아래의 레이저포는 적의 대열을 한꺼번에 꿰뚫는다.'),
    'ES': ('IRON CAB', 'ATQ. ESTÁND.: Ráfaga de misiles  ATQ. ESPEC.: Láser perforante\n'
                       'Arma andante de muchas patas que el Ejército Rebelde hizo con una locomotora.\n'
                       'El cañón láser bajo su casco atraviesa una fila entera de enemigos.'),
    'PT': ('IRON CAB', 'ATQ. PADR.: Rajada de mísseis   ATQ. ESPEC.: Laser perfurante\n'
                       'Arma andante de várias pernas que os Rebeldes fizeram com uma locomotiva.\n'
                       'O canhão laser sob o casco atravessa uma fileira inteira de inimigos.'),
    'RU': ('АЙРОН КЭБ', 'СТАНД. АТАК: Залп ракет   СПЕЦ. АТАК: Пробивающий лазер\n'
                        'Многоногое шагающее оружие, которое мятежники сделали из паровоза.\n'
                        'Лазерная пушка под корпусом пробивает целую шеренгу врагов.'),
    'FR': ('IRON CAB', 'ATT. STAND : Salve de missiles    ATT. SPÉ : Laser perforant\n'
                       'Arme marcheuse à plusieurs pattes construite par les rebelles à partir d’une locomotive.\n'
                       'Le canon laser sous sa coque transperce toute une ligne d’ennemis.'),
    'DE': ('IRON CAB', 'STAND. ATK : Raketensalve   SPEC. ATK : Durchschlagender Laser\n'
                       'Eine mehrbeinige Laufwaffe, von den Rebellen aus einer Dampflok gebaut.\n'
                       'Die Laserkanone unter dem Rumpf durchbohrt eine ganze Reihe von Feinden.'),
    'IT': ('IRON CAB', 'ATC STAND.: Raffica di missili  ATC SPEC.: Laser perforante\n'
                       'Arma camminante a più zampe costruita dai ribelli con una locomotiva.\n'
                       'Il cannone laser sotto lo scafo trafigge un’intera fila di nemici.'),
    'ZT': ('鐵甲車頭', '普通攻擊：飛彈齊射     特殊攻擊：貫穿雷射\n摩登軍以蒸汽機車改造的多足步行兵器。\n'
                   '車底的雷射砲能貫穿一整排敵人。'),
    'ZS': ('铁甲车头', '普通攻击：导弹齐射     特殊攻击：贯穿激光\n摩登军以蒸汽机车改造的多足步行兵器。\n'
                   '车底的激光炮能贯穿一整排敌人。'),
}


# ---------------------------------------------------------------- 帧
# 本体各姿势（行走帧、发射管闪光、激光炮、重画在上层的右侧腿、光球）按单位坐标合成为一张图块。SCALE 为 1（现行）时
# 不重采样，图块像素与 MSA 素材表逐像素相同；SCALE 小于 1 时（R1）合成后以单位原点为基准缩小（LANCZOS，预乘透明度），
# 透明度以 128 为界，颜色吸附回 MSA 素材表原有的 183 种颜色。原版爆炸与碎片为原生大小，不缩小。
SCALED = DERIVED / 'scaled'
_PALETTE = []


def palette():
    if not _PALETTE:
        sheet = Image.open(HERE / 'source' / 'MSA_Iron_Cab.png').convert('RGBA')
        colors = {c[:3] for c in sheet.getdata() if c[3] and c[:3] not in ((0, 255, 0), (255, 0, 255))}
        _PALETTE.extend(sorted(colors))
    return _PALETTE


_SNAP = {}


def snap(rgb):
    if rgb not in _SNAP:
        _SNAP[rgb] = min(palette(), key=lambda c: 0.3 * (c[0] - rgb[0]) ** 2 + 0.59 * (c[1] - rgb[1]) ** 2
                         + 0.11 * (c[2] - rgb[2]) ** 2)
    return _SNAP[rgb]


def scaled(img, ax, ay):
    """以图内 (ax, ay)（单位原点）为基准缩小 SCALE 倍，返回 (图, 新锚点 x, 新锚点 y)；输出像素格与单位原点对齐。
    SCALE 为 1 时原样返回（素材像素不经重采样与改色）。"""
    if SCALE == 1:
        return img, ax, ay
    w, h = img.size
    left, right = math.floor(-ax * SCALE), math.ceil((w - ax) * SCALE)
    top, bottom = math.floor(-ay * SCALE), math.ceil((h - ay) * SCALE)
    pad = 8
    big = Image.new('RGBA', (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    big.paste(img, (pad, pad))
    box = (left / SCALE + ax + pad, top / SCALE + ay + pad, right / SCALE + ax + pad, bottom / SCALE + ay + pad)
    out = big.convert('RGBa').resize((right - left, bottom - top), Image.LANCZOS, box=box).convert('RGBA')
    cut = 128
    if not any(a >= cut for a in out.getchannel('A').getdata()):
        # 极细的光束末段（1 像素高）缩小后不足半透明：凡有覆盖的像素都保留
        cut = 1
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a >= cut:                                      # RGBa → RGBA 时已按透明度还原颜色
                px[x, y] = (*snap((r, g, b)), 255)
            else:
                px[x, y] = (0, 0, 0, 0)
    return out, -left, -top


def store(img, ax, ay):
    """缩小后的图块按内容命名存入 derived/scaled/（同一合成结果只存一份），返回 Sheet 的部件元组（含 DROP）。"""
    SCALED.mkdir(parents=True, exist_ok=True)
    digest = hashlib.blake2b(img.tobytes() + struct.pack('<HHii', *img.size, ax, ay), digest_size=10).hexdigest()
    path = SCALED / f'{digest}.png'
    if not path.exists():
        img.save(path)
    return path, ax, ay


def compose(parts):
    """parts：[(路径, 锚点 x, 锚点 y, dx, dy)]（原尺寸、单位坐标）按次序叠成一张图，返回 (图, 原点 x, 原点 y)。"""
    tiles = []
    for path, ax, ay, dx, dy in parts:
        img = Image.open(path).convert('RGBA')
        tiles.append((img, dx - ax, dy - ay))
    x0 = min(x for _, x, _ in tiles); y0 = min(y for _, _, y in tiles)
    x1 = max(x + i.width for i, x, _ in tiles); y1 = max(y + i.height for i, _, y in tiles)
    canvas = Image.new('RGBA', (x1 - x0, y1 - y0), (0, 0, 0, 0))
    for img, x, y in tiles:
        canvas.alpha_composite(img, (x - x0, y - y0))
    return canvas, -x0, -y0


_SCALED_CACHE = {}


def scaled_part(parts, dx=0, dy=0):
    """原尺寸部件合成并缩小后的 Sheet 部件元组；(dx, dy) 为缩小后的偏移（精灵像素，另加 DROP）。"""
    key = tuple(parts)
    if key not in _SCALED_CACHE:
        img, ax, ay = compose(parts)
        _SCALED_CACHE[key] = store(*scaled(img, ax, ay))
    path, ax, ay = _SCALED_CACHE[key]
    return (path, ax, ay, dx, dy + DROP)


def raw(name, i, dx=0, dy=0):
    """原尺寸部件（单位坐标），供合成。"""
    f = DATA[name][i]
    return (FRAMES / f['file'], f['ax'], f['ay'], dx, dy)


def scaled_single(sheet, name, i, dx=0, dy=0, drop=0):
    """单独缩小的部件（导弹、烟雾、光束、损毁车体）组成的一帧；锚点按 frames.json。"""
    part = scaled_part([raw(name, i)], dx, dy)
    return sheet.frame([(part[0], part[1], part[2], part[3], part[4] - DROP + drop)])


def native_single(sheet, name, i, dx=0, dy=0):
    """原版效果帧（不缩小）。"""
    f = DATA[name][i]
    return sheet.frame([(FRAMES / f['file'], f['ax'], f['ay'], dx, dy)])


def s(v):
    """原尺寸单位坐标换算为缩小后的精灵像素。"""
    return round(v * SCALE)


def muzzle():
    """发射管口：发射管静止帧中橙色炮口环的中心（缩小后的单位坐标，未含 DROP）。"""
    f = DATA['launcher'][0]
    img = Image.open(FRAMES / f['file']).convert('RGBA')
    pts = [(x, y) for y in range(img.height) for x in range(img.width)
           if img.getpixel((x, y))[3] and img.getpixel((x, y))[0] > 200 and img.getpixel((x, y))[1] < 140
           and img.getpixel((x, y))[2] < 100]
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return s(cx - f['ax']), s(cy - f['ay'])


def hull_bottom():
    """行走第 1 帧每列车体的下沿（单位坐标）；无车体的列不在结果中。"""
    f = DATA['walk'][0]
    img = Image.open(FRAMES / f['file']).convert('RGBA')
    out = {}
    for X in range(img.width):
        bottom, start = None, None
        for Y in range(img.height):
            y = Y - f['ay']
            if y >= HULL_CAP:
                break
            opaque = img.getpixel((X, Y))[3] > 0
            if opaque and start is None:
                start = y
            if not opaque and start is not None:
                if start < -110:
                    bottom = y - 1
                start = None
        if start is not None and start < -110:
            bottom = HULL_CAP - 1
        if bottom is not None:
            out[X - f['ax']] = bottom
    return out


HULL = None
CLIPPED = DERIVED / 'cannon_clipped'


def cannon_part(k, x, y):
    """修正后的激光炮第 k 帧（或 make_beam 合成的带光束炮帧，k 为 (炮帧, 光束半高)）放在吊杆 (x, y)（原尺寸单位坐标），
    高于车体下沿的像素去掉（藏在车体内），返回合成部件。放下与收起只用第 0 帧，其所有列都须有车体（cannon_rise 核对）；
    蓄力光球与光束等只在完全放下后出现。"""
    global HULL
    if HULL is None:
        HULL = hull_bottom()
    if isinstance(k, tuple):
        f = BEAM[k]['frame']
        img = Image.open(make_beam.OUT / f['file']).convert('RGBA')
    else:
        f = CANNON[k]
        img = Image.open(fix_cannon.OUT / f['file']).convert('RGBA')
    px = img.load()
    for j in range(img.height):
        for i in range(img.width):
            if px[i, j][3]:
                ux, uy = x - f['ax'] + i, y - f['ay'] + j
                if ux in HULL and uy <= HULL[ux]:
                    px[i, j] = (0, 0, 0, 0)
    CLIPPED.mkdir(parents=True, exist_ok=True)
    digest = hashlib.blake2b(img.tobytes() + struct.pack('<HHii', *img.size, f['ax'], f['ay']), digest_size=10).hexdigest()
    path = CLIPPED / f'{digest}.png'
    if not path.exists():
        img.save(path)
    return (path, f['ax'], f['ay'], x, y)


def cannon_rise():
    """第 0 帧完全藏入车体所需的上移量（精灵像素）。"""
    global HULL
    if HULL is None:
        HULL = hull_bottom()
    f = CANNON[0]
    img = Image.open(fix_cannon.OUT / f['file']).convert('RGBA')
    cx, cy = CANNON_AT
    pixels = [(cx - f['ax'] + i, cy - f['ay'] + j) for j in range(img.height) for i in range(img.width)
              if img.getpixel((i, j))[3]]
    assert all(ux in HULL and HULL[ux] == HULL_CAP - 1 for ux, _ in pixels), 'cannon must sit under the flat belly'
    return max(uy - HULL[ux] for ux, uy in pixels)


def orb_point():
    """光球中心（原尺寸单位坐标）。"""
    meta = DATA['meta']
    return round(CANNON_AT[0] + meta['orb_center'][0]), round(CANNON_AT[1] + meta['orb_center'][1])


# ---------------------------------------------------------------- 脚本
def pose(sheet, mid=(), behind=(), dx=0):
    """站立姿势（行走第 1 帧）：behind < 组装帧 < mid < 右侧一对腿（重画在上层），合成后缩小。"""
    return sheet.frame([scaled_part(list(behind) + [raw('walk', 0)] + list(mid) + [raw('legs', 0)], dx)])


def body_parts(state, x, oy):
    """光束直段：自 x（右缘，缩小后的精灵像素）向左平铺到光束末端（光球中心以左 BEAM_LEN），末块按剩余宽度裁切。"""
    f = BEAM[state]['body']
    tile = make_beam.OUT / f['file']
    img = Image.open(tile)
    end = s(orb_point()[0]) - BEAM_LEN
    out = []
    while x - img.width >= end:
        out.append((tile, f['ax'], f['ay'], x, oy + DROP))
        x -= img.width
    if x > end:
        piece = store(img.crop((img.width - (x - end), 0, img.width, img.height)), x - end, f['ay'])
        out.append((piece[0], piece[1], piece[2], x, oy + DROP))
    return out


def missile_script(sheet, distance, mouth):
    up = [scaled_single(sheet, 'missile_up', i) for i in range(2)]
    down = [scaled_single(sheet, 'missile_down', i) for i in range(2)]
    rise = math.ceil((TOP + mouth[1]) / RISE_V)
    out = [op(7, 0, round(-RISE_V * 100), 0, 0)]
    for t in range(rise):
        out += F(up[t // 2 % 2], 1)
    # 发射管口在车体中心以后 mouth[0] 像素：横移量 = 管口到车体中心 + 中心到前缘 + 前缘到落点。
    # R8（用户 2026-10-19 反馈导弹全部落空）：R1–R7 误减去 mouth[0]，6 枚导弹都比设计落点近 2 × 27 精灵像素（108 世界单位），
    # 最远一枚只落在前缘以外 442，而开始射击的距离（状态词 7）为 550。
    vx = -(FRONT + distance / WORLD + mouth[0]) / TRAVEL_TICKS
    out += [op(7, round(vx * 100), 0, 0, 0)] + F(-1, TRAVEL_TICKS)
    out += [op(7, 0, round(FALL_V * 100), 0, 0), op(4, 1)]
    fall = math.ceil(TOP / FALL_V)
    for t in range(0, fall + 20, 2):            # 正常情况在此之前落地（状态 61）
        out += F(down[t // 2 % 2], 2)
    return out + [op(4, -1)] + F(-1, 1) + [op(21)]


def boom_script(sheet, sound=True):
    out = [op(4, -1)] + ([op(23, SND['bomb'])] if sound else [])
    for i in range(len(DATA['boom'])):
        out += F(native_single(sheet, 'boom', i), 1)
    return out + F(-1, 1) + [op(21)]


def blast_script(sheet):
    out = []
    for i in range(len(DATA['blast'])):
        out += F(native_single(sheet, 'blast', i), 1)
    return out + F(-1, 1) + [op(21)]


def smoke_script(sheet):
    out = [op(7, 0, -30, 0, 0)]
    for i in range(len(DATA['smoke'])):
        out += F(scaled_single(sheet, 'smoke', i), 2)
    return out + F(-1, 1) + [op(21)]


DEBRIS = [('debris_a', -220, -520, 40), ('debris_a', 260, -480, 40), ('debris_b', -360, -420, 40), ('debris_b', 160, -600, 40)]
DEBRIS_FROM = round(-123 * SCALE)   # 碎片自地面以上抛出（原尺寸 123 像素）


# 报废后的大爆炸（R9，用户 2026-10-20：残骸落地后不要闪烁消失，改为几 tick 后爆炸、炸成铁片与木屑后消失）。
# 爆炸为原版大型单位的爆炸（共用效果 402 动画 0x17，DAI-MANJI、HOZUMI、CRAB MECHA L、DEN-DEN HOUSE 等使用，先白闪后火球与黑烟），
# 经 op12 直接引用（BattleUnitDefault::createObject → addEffect，编号 ≥ 0xff00 时取共用效果 402），不占本单位图集。
# 碎屑：铁片沿用原版共用效果 402 动画 11、12 的帧（debris_a / debris_b）；原版没有木屑图块，木屑为同样形状按 MSA 素材表
# 车厢木箱的 6 级木色重新着色（wood_a / wood_b，生成于 derived/wood/）。
DEATH_FUSE = 10                                  # 残骸落地后到大爆炸的间隔（tick）
FINAL_BLASTS = [(0, (0, -20)), (3, (-46, 6)), (6, (44, -4))]       # (相对 tick, 位置)：三团大爆炸先后出现；R9b 整体下移 40
                                                                  # （用户：爆炸主体在残骸处，火团下缘贴近地面）
FINAL_FROM = -60                                 # 碎屑自残骸中部抛出
FINAL_DEBRIS = [('wood_a', -260, -560, 40), ('wood_b', -140, -640, 40), ('wood_a', 120, -600, 40),
                ('wood_b', 300, -520, 40), ('wood_b', -380, -440, 40), ('wood_a', 220, -460, 40),
                ('debris_a', -200, -500, 40), ('debris_b', 360, -580, 40), ('debris_a', 60, -680, 40)]
METAL_TO_WOOD = {(41, 33, 16): (33, 33, 0), (82, 74, 57): (74, 49, 8), (123, 115, 99): (107, 82, 41),
                 (173, 165, 148): (140, 123, 82), (231, 222, 206): (214, 198, 156), (255, 255, 255): (214, 198, 156)}


def wood_frames():
    """把铁片帧（debris_a / debris_b）按 METAL_TO_WOOD 换为木色，写入 derived/wood/，登记为 DATA['wood_a'] / ['wood_b']。"""
    out_dir = HERE / 'derived' / 'wood'
    out_dir.mkdir(parents=True, exist_ok=True)
    for src, dst in (('debris_a', 'wood_a'), ('debris_b', 'wood_b')):
        DATA[dst] = []
        for f in DATA[src]:
            img = Image.open(FRAMES / f['file']).convert('RGBA')
            px = img.load()
            for y in range(img.height):
                for x in range(img.width):
                    r, g, b, a = px[x, y]
                    if a:
                        px[x, y] = METAL_TO_WOOD[(r, g, b)] + (a,)
            name = f['file'].replace(src, dst)
            img.save(out_dir / name)
            DATA[dst].append(dict(f, file=str(Path('..') / 'derived' / 'wood' / name)))


def debris_script(sheet, name, vx, vy, g, height=None, blink=True):
    """碎片抛出、落地后停留；blink 为假时（R9 报废大爆炸的碎屑）落地停留 12 tick 后直接消失，不闪烁。"""
    frames = [native_single(sheet, name, i) for i in range(len(DATA[name]))]
    ticks = pvz.throw_ticks(-DEBRIS_FROM if height is None else height, vy, g)
    out = [op(7, vx, vy, 0, g)]
    for t in range(ticks):
        out += F(frames[t % len(frames)], 1)
    if not blink:
        return out + [op(7, 0, 0, 0, 0)] + F(frames[0], 12) + F(-1, 1) + [op(21)]
    out += [op(7, 0, 0, 0, 0)] + F(frames[0], 20)
    for _ in range(3):
        out += F(-1, 2) + F(frames[0], 2)
    return out + F(-1, 1) + [op(21)]


def normal_attack(sheet, mouth, slots, with_shots=True):
    """站定 → 发射管逐发闪光并射出导弹（每 SHOT_TICKS tick 一枚）→ 闪光渐退。"""
    flash = lambda k: pose(sheet, mid=[raw('launcher', k)])
    stand = pose(sheet)
    out = [op(3, 1)] + F(stand, 6)
    for n, slot in enumerate(slots):
        if with_shots:
            out += [op(22, slot, 0, mouth[0], mouth[1] + DROP), op(12, SLOT['smoke_fx'], 0, mouth[0], mouth[1] + DROP)]
            if n % 3 == 0:
                out.append(op(23, LAUNCH_SOUND))
        out += F(flash(1 + n % 2), 1) + F(flash(3), SHOT_TICKS - 1)
    for k in (4, 5, 6):
        out += F(flash(k), 2)
    return out + F(stand, 2) + [op(21)]


def special_attack(sheet):
    """放下激光炮 → 蓄力（光球由小变大）→ 满蓄力闪动 → 放出光束（3 段攻击）→ 光束变细消散 → 炮口冷却 → 收起。"""
    cx, cy = CANNON_AT
    ox, oy = orb_point()
    sox, soy = s(ox), s(oy)
    cannon = lambda k, dy=0: cannon_part(k, cx, cy + dy)
    orb = lambda name, i: [scaled_part([raw(name, i)], sox, soy)]      # 光球在前方，不与右侧腿重叠：单独缩小后叠在上层
    front = lambda *mid, extra=(): sheet.frame([scaled_part([raw('walk', 0), *mid, raw('legs', 0)])] + list(extra))
    rise = cannon_rise()
    lowered = [front(cannon(0, -round(rise * (1 - (i + 1) / (LOWER_FRAMES + 1))))) for i in range(LOWER_FRAMES)]
    out = [op(3, 1), op(4, -1)]
    for fr in lowered:                                       # 0–11：自车底竖直放下（高于车体下沿的部分不画）
        out += F(fr, 1)
    out += F(front(cannon(0)), 4)                            # 12–15
    out += [op(23, SND['charge'])] + F(front(cannon(1)), 4)  # 16–19：开始蓄力
    for i in range(len(DATA['orb'])):                        # 20–53：光球由小变大
        out += F(front(cannon(1), extra=orb('orb', i)), 2)
    full = [front(cannon(2)), front(cannon(3))] + [front(cannon(3), extra=orb('orb_big', k)) for k in (0, 1, 2, 0)]
    for fr in full:                                          # 54–65：满蓄力闪动
        out += F(fr, 2)
    out.append(op(23, SND['laser']))
    def beam(state, extra=()):
        """带光束的炮帧：炮帧 4、5 用 make_beam 合成的帧（光球与光束开头）加直段；帧 6 的细光束自光球中心起。"""
        if state[0] == 'thin':
            return front(cannon(6), extra=body_parts(state, sox, soy) + list(extra))
        return front(cannon(state), extra=body_parts(state, cx + BEAM[state]['split'], soy) + list(extra))
    for t in range(18):                                      # 66–83：光束，3 段攻击
        if t in LASER_PULSES:
            out.append(op(4, 2))
        out += F(beam(BEAM_FIRE[t // 2 % 2]), 1)             # 炮口光球与光束同步、每 2 tick 交替
    out.append(op(4, -1))
    spark = lambda k: [scaled_part([raw('beam_spark', k % 4)], sox - BEAM_LEN * j // 3, soy) for j in (1, 2, 3)]
    for n, state in enumerate(BEAM_FADE):                    # 84–92：光束变细消散
        out += F(beam(state, spark(n + 2)), 1)
    for k in range(7, 12):                                   # 93–102：炮口冷却
        out += F(front(cannon(k)), 2)
    for fr in reversed(lowered):                             # 103–114：竖直收回车体
        out += F(fr, 1)
    return out + F(pose(sheet), 1) + [op(21)]


def knockback_script(sheet, walk):
    out = [op(4, -1), op(3, 1), op(7, 160, 0, -16, 0)]
    for i in range(5):
        out += F(walk[(-i) % len(walk)], 2)
    return out + [op(7, 0, 0, 0, 0), op(16)] + F(walk[0], 10) + [op(21)]


def death_script(sheet):
    """被击败：站定抖动并接连小爆炸（30 tick）→ 大爆炸与碎片，残骸车体落地（腿被爆炸遮住后不再画出）→ 冒烟停留 DEATH_FUSE tick →
    原版大型单位爆炸（0x17 三团），残骸炸开、铁片与木屑四散后消失（R9；此前停留 45 tick 后闪烁消失）。"""
    out = [op(4, -1), op(23, SND['bomb'])]
    pops = [(s(x), s(y)) for x, y in ((-40, -169), (31, -151), (-9, -120), (49, -182), (-55, -111))]   # 原尺寸单位坐标
    for i in range(15):
        if i % 3 == 0:
            x, y = pops[i // 3]
            out.append(op(12, SLOT['boom_fx'], 0, x, y))
        if i == 6:
            out.append(op(23, SND['bomb']))
        out += F(pose(sheet, dx=1 if i % 2 else -1), 2)
    out += [op(23, DEATH_BLAST)]
    for x, y in ((0, -146), (-46, -92), (46, -102)):
        out.append(op(12, SLOT['blast_fx'], 0, s(x), s(y)))
    for slot in SLOT['debris']:
        out.append(op(12, slot, 0, 0, DEBRIS_FROM))
    out += F(pose(sheet), 4)
    v, y = 0.0, s(-89)                                       # 残骸（损毁车体）自与完好车体顶边对齐处落到地面
    while y < 0:
        v += 1.5
        y = min(0, y + v)
        out += F(scaled_single(sheet, 'destroyed', 0, 0, round(y), drop=DROP), 1)
    wreck = scaled_single(sheet, 'destroyed', 0, drop=DROP)
    out.append(op(12, SLOT['smoke_fx'], 0, s(-22), s(-80)))
    out += F(wreck, DEATH_FUSE)                              # R9：落地后停留几 tick（此前停留 45 tick 后闪烁 3 次消失）
    out.append(op(23, DEATH_BLAST))
    t = 0
    for tick, (x, y) in FINAL_BLASTS:                        # 原版大型单位爆炸，三团先后出现
        while t < tick:
            out += F(wreck if t < 2 else -1, 1)              # 残骸在第一团的白闪中再画 2 tick，之后不再画出
            t += 1
        out.append(op(12, 0xff17, 0, s(x), s(y)))
        if tick == 0:
            for slot in SLOT['final']:                       # 铁片与木屑自残骸中部四散
                out.append(op(12, slot, 0, 0, s(FINAL_FROM)))
    return out + F(-1, 40) + [op(21)]                         # 残骸已炸开（第 2 tick 起不再画出），等爆炸与碎屑播完


def build():
    wood_frames()
    sheet = pvz.Sheet()
    walk = [sheet.frame([scaled_part([raw('walk', i)])]) for i in range(len(DATA['walk']))]
    stand = pose(sheet)
    sheet.scripts[0] = sheet.scripts[6] = sheet.scripts[11] = loop([stand], [30], first=[op(3, 1)])
    sheet.scripts[1] = sheet.scripts[7] = loop(walk, [WALK_HOLD] * len(walk), first=[op(3, 1)])
    mouth = muzzle()
    for distance, slot in zip(MISSILE_DIST, MISSILE_SLOTS):
        sheet.scripts[slot] = missile_script(sheet, distance, mouth)
    sheet.scripts[9] = normal_attack(sheet, mouth, MISSILE_SLOTS)
    sheet.scripts[2] = normal_attack(sheet, mouth, MISSILE_SLOTS, with_shots=False)
    sheet.scripts[10] = special_attack(sheet)
    sheet.scripts[12] = knockback_script(sheet, walk)
    sheet.scripts[13] = sheet.scripts[15] = death_script(sheet)
    sheet.scripts[21] = sheet.scripts[22] = boom_script(sheet)
    sheet.scripts[SLOT['boom_fx']] = boom_script(sheet, sound=False)
    sheet.scripts[SLOT['blast_fx']] = blast_script(sheet)
    sheet.scripts[SLOT['smoke_fx']] = smoke_script(sheet)
    for slot, (name, vx, vy, g) in zip(SLOT['debris'], DEBRIS):
        sheet.scripts[slot] = debris_script(sheet, name, vx, vy, g)
    for slot, (name, vx, vy, g) in zip(SLOT['final'], FINAL_DEBRIS):
        sheet.scripts[slot] = debris_script(sheet, name, vx, vy, g, height=-s(FINAL_FROM), blink=False)
    ox, oy = orb_point()
    half = s(16)
    laser_rect = [s(ox) - BEAM_LEN, s(oy) - half + DROP, BEAM_LEN, 2 * half, 7]
    obm, desc, animations, page = pvz.finish(sheet, SCRIPT_COUNT, HIT_RECT, [MISSILE_RECT, laser_rect])
    return obm, desc, animations, page, sheet, {'mouth': mouth, 'orb': (s(ox), s(oy)), 'laser_rect': laser_rect,
                                                'cannon_at': list(CANNON_AT), 'cannon_rise': cannon_rise()}


def render(sheet, key, origin=(260, 300), size=(560, 340)):
    """按 Sheet 的矩形把一帧画到透明底（原点在 origin），供预览核对。"""
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    for r in key:
        t, ax, ay = sheet.rects[r]
        tile, _ = sheet.tiles[t]
        img.alpha_composite(tile, (origin[0] - ax, origin[1] - ay))
    return img


def preview(sheet, animations_raw):
    """各动作抽样帧：深色底，红线为单位原点，蓝线为地面。"""
    from PIL import ImageDraw
    picks = []
    for slot, label in ((7, 'walk'), (9, 'normal'), (10, 'special'), (13, 'death')):
        seen = []
        for cmd in sheet.scripts[slot]:
            if cmd['opcode'] == 0 and isinstance(cmd['values'][0], tuple) and cmd['values'][0] not in seen:
                seen.append(cmd['values'][0])
        step = max(1, len(seen) // 8)
        picks += [(label, k) for k in seen[::step][:8]]
    cols = 4
    cw, ch = 560, 340
    out = Image.new('RGBA', (cw * cols, ch * math.ceil(len(picks) / cols)), (40, 44, 52, 255))
    d = ImageDraw.Draw(out)
    for n, (label, key) in enumerate(picks):
        x0, y0 = n % cols * cw, n // cols * ch
        out.alpha_composite(render(sheet, key), (x0, y0))
        d.line([(x0 + 260, y0 + 10), (x0 + 260, y0 + 330)], fill=(255, 80, 80, 140))
        d.line([(x0 + 10, y0 + 300), (x0 + cw - 10, y0 + 300)], fill=(80, 200, 255, 140))
        d.text((x0 + 6, y0 + 4), label, fill=(255, 255, 255, 255))
    return out


def icon_atlas():
    """头像写入社区合并图集（RGBA32）的空位；目标区域须为空或为本单位先前写入。"""
    raw = bytearray((CONTENT / ICON_ATLAS).read_bytes())
    assert raw[:4] == b'OI\x01\x20'
    w, h = struct.unpack_from('<HH', raw, 4)
    for unit_file in (CONTENT / 'units').glob('*.json'):
        unit = json.loads(unit_file.read_text(encoding='utf-8'))
        if unit['key'] == KEY or 'atlas' in unit['icon']:
            continue
        x, y, iw, ih = unit['icon']['rect']
        assert (x + iw <= ICON_AT[0] or x >= ICON_AT[0] + ICON_SIZE[0] or y + ih <= ICON_AT[1]
                or y >= ICON_AT[1] + ICON_SIZE[1]), unit['key']
    icon = Image.open(ICON_SOURCE).convert('RGBA')
    assert icon.size == ICON_SIZE
    for j in range(ICON_SIZE[1]):
        for i in range(ICON_SIZE[0]):
            at = 8 + ((ICON_AT[1] + j) * w + ICON_AT[0] + i) * 4
            raw[at:at + 4] = bytes(icon.getpixel((i, j)))
    return bytes(raw), icon


def unit_file(animations):
    return {
        'key': KEY, 'base_id': 313, 'faction': 1, 'identity': 'Rebel Army',
        'shop_price': STATS['shop_price'], 'available_from_start': True, 'ap': STATS['ap'],
        'upgrade_cost_base': STATS['upgrade_cost_base'],
        'hp_multiplier': STATS['hp_multiplier'],
        'knockback_threshold_multiplier': STATS['knockback_threshold_multiplier'],
        'production_reference_id': 313, 'production_interval_multiplier': STATS['production_interval_multiplier'],
        'damage_multiplier': STATS['damage_multiplier'], 'special_damage_multiplier': STATS['special_damage_multiplier'],
        'move_speed_multiplier': STATS['move_speed_multiplier'], 'knockback_distance_multiplier': [1, 1],
        # 状态词 7 开始射击的距离；24 每枚导弹命中目标数；31 光束每段命中目标数（贯穿）；35/36 绝招冷却（之后 / 出场后第一次）
        'status_word_values': {'7': NORMAL_RANGE, '24': 1, '31': 99, '35': 2100, '36': 1400},
        # 小地图标记（数据行 +0x34c/+0x350）：按原版大型单位标记与图像尺寸的比例（宽约 1/25、高约 1/21.5）换算（2026-10-20）
        'minimap_marker': [16, 20],
        'icon': {'page': 1, 'rect': [*ICON_AT, *ICON_SIZE], 'anchor': ICON_ANCHOR},
        'textures': [TEXTURE], 'sprite_descriptor': DESCRIPTOR, 'animations': animations,
        'localization': {code: {'name': n, 'description': d} for code, (n, d) in TEXT.items()},
        'tags': ['ms6', 'msa'],
    }


def main():
    OUT.mkdir(exist_ok=True)
    obm, desc, animations, page, sheet, points = build()
    preview(sheet, animations).save(OUT / 'preview_actions.png')
    if '--preview' in sys.argv:          # 只生成预览，不写 community_content
        print(json.dumps({'atlas': list(page.size), 'rects': len(desc['rects']), 'colors': len(set(page.getdata())),
                          **points}))
        return
    icon_raw, icon = icon_atlas()
    files = {TEXTURE: obm, ICON_ATLAS: icon_raw}
    index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
    if KEY not in index['unit_ids']:
        index['unit_ids'][KEY] = max(index['unit_ids'].values()) + 1
    for name, raw in files.items():
        (CONTENT / name).write_bytes(raw)
        if index['assets'].get(name, '') is not None:     # unit_icon_02.obm 登记为 null（不做摘要核对）
            index['assets'][name] = hashlib.blake2b(raw, digest_size=32).hexdigest()
    sounds = [e for e in index.get('sounds', []) if not e['key'].startswith('s1xlv.ironcab_')]
    for name, source in SOUNDS.items():
        target = f'ironcab_{name}.msdf'
        shutil.copyfile(SOUND_SOURCE / f'{source}.ogg', CONTENT / target)
        sounds.append({'key': SND[name], 'file': target, 'type': 'se'})
    index['sounds'] = sounds
    pvz.save_json(CONTENT / DESCRIPTOR, desc)
    pvz.save_json(CONTENT / 'units' / 'iron_cab.json', unit_file(animations))
    pvz.save_json(CONTENT / 'content.json', index)
    page.save(OUT / 'iron_cab_atlas.png')
    icon.resize((ICON_SIZE[0] * 8, ICON_SIZE[1] * 8), Image.NEAREST).save(OUT / 'icon_8x.png')
    report = {'unit_id': index['unit_ids'][KEY], 'atlas': list(page.size), 'rects': len(desc['rects']),
              'frame_words': len(desc['frames']), 'colors': len(set(page.getdata())), **points}
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
