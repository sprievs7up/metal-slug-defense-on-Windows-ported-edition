"""单位浏览大菜单（U1a，docs/ui/U1_UNIT_UI_KICKOFF_2026-10-11.md 第 2、3.1、3.6 节与附录 A）。

强化（custom）与商店（shop）共用的浏览组件：每页 3×3 张卡片（D15），左右按钮、滚轮与 ←/→ 翻页（D8，首末页循环），
页码与等级为原生银色数字（D21）；排序、筛选与名称搜索在 SORT 面板中；收藏（D13）与显示切换在底栏。
卡片构图依据已确认样张（make_mockups.py / make_detail_mockups.py）：原生卡片底板、选单位格与头像同为 2 倍、头像按
ConvUnitIcon 锚点放置（D16、D19）、格内绿色调为 MSA 色调（D18）、原生 EVENT 进度条按当前上限计算并显示 MAX
（D7、D24、D27、D36）、阵营标志（position_icon.obm）。素材全部在运行时从原生图集读取。

强化（U1b）：主菜单“強化”子页的“單位”面板（app+0x339c）由本组件接管——按下与白光交给原生面板，抬起后经宿主闸门
（lab_ui.Shutter，原生闸门任务）打开本界面，界面覆盖原生主菜单（场景 28 状态 3），BACK 经闸门回到该页；点击卡片进入
单位菜单（unit_menu）。
商店（U1c）：主菜单 SHOP 子页的 UNIT 卡（app+0x33ac）以同样方式接管，界面覆盖 SHOP 子页（场景 28 状态 4）；只列已开放且
未拥有的单位（D30），卡片 BUY 与单位菜单 BUY 打开购买确认（D32，unit_menu）；PACK 进入原生单位商店页面（场景 38/39），
期间原生商品目录只含可购买的组合包（D33，购买界面沿用原版），页面上的 BACK / Esc 回到本界面。操作与数据经 unit_catalog。
排序、筛选、页码与显示设定、收藏保存在当前存档目录的 unit_browser.json（R7、D13），不写入原生存档。
动效（D52，unit_motion）：按下白光按原生亮版渐变；弹窗（SORT 面板、单位菜单各窗口）按原生弹窗开合；浏览大菜单与单位
菜单之间按原生列表面板进出；翻页时卡片整体平移。过渡由画面状态（view_state）的变化触发，期间不接受输入（翻页除外）。
"""
import json
import math
import os
import struct
import time
from pathlib import Path

from lab_ui import W, H, SE_DECIDE, SE_CLOSE, Skin, Shutter, play_se
from unit_motion import Layers, Lights, Motion, color_map, lighten, relight, panels_in, panels_out, popup_close, popup_open, slide

STATE_NAME = 'unit_browser.json'
STATE_SCHEMA = 1
COLS, ROWS = 3, 3
PAGE_SIZE = COLS * ROWS
LEFT, TOP, RIGHT, BOTTOM = 78, 128, 1202, 560
GAP_X = 16
CARD_SCALE = 2
CARD_EDGES = (4, 4, 8, 9)                     # 卡片底板四边（原图像素，D19）
CARD_H = (CARD_EDGES[1] + 50 + CARD_EDGES[3]) * CARD_SCALE
CARD_W = (RIGHT - LEFT - GAP_X * (COLS - 1)) // COLS
GAP_Y = (BOTTOM - TOP - CARD_H * ROWS) // (ROWS - 1)
CARD_ROW1 = 9                                 # 右侧第一行顶边距内框（D36）
NATIVE_TO_CANVAS = 1280 / 1137.78             # 原生 960 基准（16:9 宽 1137.8）到 1280×720 画布
BAR_LEFT, BAR_RIGHT, BAR_Y = 45, 1098, H - 122
CUSTOMIZE_UNIT_PANEL = 0x339c                  # 主菜单 CUSTOMIZE 子页的“單位”面板（GT_MenuPanel，附录 A.5）
SHOP_UNIT_CARD = 0x33ac                        # 主菜单 SHOP 子页的 UNIT 卡（GT_MenuGenrePanel，附录 A.4）
# 主菜单子页（场景 28 的状态）→ (入口任务槽, 原生任务函数, 模式)
ENTRIES = {3: (CUSTOMIZE_UNIT_PANEL, 'GT_MenuPanel', 'custom'), 4: (SHOP_UNIT_CARD, 'GT_MenuGenrePanel', 'shop')}
COCKPIT_BACK = 0x36d8                          # 原生底栏 BACK 按钮任务（附录 A.5）
COCKPIT_CUSTOMIZE = 0x3704                     # 编队页底栏 CUSTOMIZE（SelectCockpitDeck：场景 50 原生强化）
SCENE_MAIN, SCENE_SHOP_INIT, SCENE_SHOP = 28, 38, 39
SCENE_DECK_INIT, SCENE_DECK, SCENE_DECK_END = 54, 55, 56   # SC_DeckInit / SC_DeckLoop / SC_DeckEnd
POPUP_SCENES = range(119, 123)
TUTORIAL_SHOP_UNIT = 15                        # SelectPanelMainMenuShop 选 UNIT 卡时的 DelTutorialData 序号
# 原生面板的 NEW 标记为教学提示位（IsPanelNew：面板 0xf“單位”对应 9，面板 8“強化”对应 7）。位 7、9 在关卡结算时
# （BattleEndGetStageResult）重新设上，进入单位强化场景时由 SC_CustomInit 清除（选面板时 SelectPanelMainMenu 另清 9）。
# 本界面不进入场景 50，打开时同样清除，否则“單位（強化）”面板的 NEW 一直显示（2026-10-14）。
TUTORIAL_CUSTOM_UNIT = (7, 9)
BUTTON_SCALE = 2.25

# 原生素材（图集, (x, y, w, h)）
HEADER = ('menuparts.obm', (0, 68, 568, 51))
BOTTOM_BAR = ('menuparts.obm', (0, 0, 568, 67))
ARROW = ('menuparts.obm', (1003, 62, 18, 18))         # 向右；向左为水平镜像
TITLE_CUSTOMIZE = ('shop.obm', (0, 476, 132, 18))
TITLE_SHOP = ('shop.obm', (391, 277, 63, 18))
TITLE_UNIT = ('shop.obm', (434, 179, 47, 14))
CARD = ('shop.obm', (0, 0, 444, 69))
CELL = ('unit.obm', (362, 151, 50, 50))
MAX = ('shop.obm', (85, 495, 40, 12))
RED = ('shop.obm', (392, 253, 84, 23))                 # 原生红色按钮（BUY）
GAUGE = ('event_task_ui.obm', (0, 67, 60, 16))
GAUGE_FILL = ('event_task_ui.obm', (0, 84, 50, 10))
GAUGE_FULL = ('event_task_ui.obm', (0, 95, 50, 10))
POPUP = ('popup_2.obm', (0, 0, 300, 192))              # 原生弹窗（青色边）
TAB_OFF, TAB_ON = ('menuparts.obm', (0, 154, 190, 33)), ('menuparts.obm', (0, 120, 190, 33))
DLG_RED = ('menuparts.obm', (282, 168, 90, 23))        # 原生弹窗 OK（红）
DLG_BROWN = ('menuparts.obm', (282, 216, 90, 23))      # 原生弹窗按钮（棕）
FIELD = ('menuparts.obm', (191, 120, 190, 23))         # 米色底板（搜索框）
PRESS_FRAME = (('menuparts.obm', (563, 155, 66, 54)), (3, 3))   # ConvMenuParts 79：按下青色框
# 按下白光的亮版（与原图 alpha 轮廓相同的原生图块，D52）
RED_LIT = ('shop.obm', (322, 318, 84, 23))             # RED 的亮版（GT_MenuShopWindowDraw 图 5 → 6）
DLG_RED_LIT = ('menuparts.obm', (191, 216, 90, 23))    # 弹窗 OK 的亮版（GT_PopupOKDraw 图 4 → 5）
DLG_BROWN_LIT = ('menuparts.obm', (282, 192, 90, 23))
LIGHT_PARTS = {'buy': (RED, RED_LIT), 'lv_up': (RED, RED_LIT), 'lv_lock': (RED, RED_LIT),
               'open': (TAB_OFF, TAB_ON), 'act': (TAB_OFF, TAB_ON), 'sort': (TAB_OFF, TAB_ON),
               'direction': (TAB_OFF, TAB_ON), 'source': (TAB_OFF, TAB_ON),
               'limit_pay': (DLG_RED, DLG_RED_LIT), 'confirm_ok': (DLG_RED, DLG_RED_LIT), 'buy_ok': (DLG_RED, DLG_RED_LIT),
               'message_ok': (DLG_RED, DLG_RED_LIT), 'ok': (DLG_RED, DLG_RED_LIT),
               'confirm_cancel': (DLG_BROWN, DLG_BROWN_LIT), 'buy_cancel': (DLG_BROWN, DLG_BROWN_LIT),
               'reset': (DLG_BROWN, DLG_BROWN_LIT)}
LIGHT_INSTANT = {'limit_pay', 'confirm_ok', 'buy_ok', 'message_ok', 'ok', 'confirm_cancel', 'buy_cancel', 'reset'}
LIGHT_NONE = {'bar', 'lv_na', 'lv_col', 'panel', 'outside', 'search', 'desc_bar', 'desc_text'}
SORT_PANEL = (40, 96, 1200, 500)
CARD_CLIP = (LEFT - 8, TOP - 8, RIGHT - LEFT + 16, BOTTOM - TOP + 16)   # 翻页平移的裁切范围（卡片区）
PRESS_LAMPS = (('menuparts.obm', (221, 247, 22, 6)), (-19, -2))  # ConvMenuParts 37：三灯
CONV_MENU_PARTS = 0x1031c900                   # ConvMenuParts（16 字节：x,y,w,h,锚点 x,y,—,页）
CONV_POSITION = 0x1030a1c0                     # position_icon.obm 转换表 53（阵营 0–5）
MENU_TABLE_LITERAL = (0x101652d0, 0x101652b4)  # GetMenuUnitData 的菜单表（320 行 × 20 字节，+10 头像序号）
ICON_PAGES = {0: 'unit_icon_01.obm', 1: 'unit_icon_02.obm'}
BUTTONS = {'back': 30, 'sort': 101, 'deck': 106, 'free': 120, 'map': 118}   # 底栏原生按钮（ConvMenuParts）
# FAVORITES 按钮图（用户设计，D26）：收藏筛选关闭 / 开启（文字为金色）
FAVORITES_BUTTONS = {'favorites': 'u1_button_favorites.png', 'favorites_on': 'u1_button_favorites_on.png'}
CELL_TINT = (0, 80, 50)                        # D18
GAUGE_FRAME_RANGE = 0.6                        # D27
GAUGE_COLORS = ((200, 84, 0), (255, 166, 0), (226, 110, 0), (255, 204, 0))   # D24：升级中、充满
GAUGE_FRAME_ROWS = (0, 1, 2, 3, 4, 5, 10, 11, 12, 13, 14, 15)                  # D36
GAUGE_FILL_ROWS = (0, 2, 4, 5, 7, 9)
LABEL_ROWS = (37, 43)                          # 底栏按钮标签字形行（PACK 拼字，D33）
FAVORITE_STAR = (255, 214, 60, 255)

# 界面语言：原生语言编号 → 文字表序号（繁中、简中、日、英、西、葡、韩，D4）；其余显示英文。
LANG_INDEX = {9: 0, 8: 1, 1: 2, 0: 3, 3: 4, 4: 5, 2: 6}
NATIVE_LANGUAGES = {0, 1, 2, 3, 4, 5, 7, 9, 10}   # 有原生文字的编号（附录 A.9）
TEXT = {
    'sort': ('排序', '排序', '並べ替え', 'SORT', 'ORDENAR', 'ORDENAR', '정렬'),
    'filter': ('篩選', '筛选', '絞り込み', 'FILTER', 'FILTRAR', 'FILTRAR', '필터'),
    'uid': ('預設', '默认', '標準', 'DEFAULT', 'PREDETERMINADO', 'PADRÃO', '기본'),
    'level': ('等級', '等级', 'レベル', 'LEVEL', 'NIVEL', 'NÍVEL', '레벨'),
    'ap': ('AP', 'AP', 'AP', 'AP', 'AP', 'AP', 'AP'),
    'price': ('價格', '价格', '価格', 'PRICE', 'PRECIO', 'PREÇO', '가격'),
    'hp': ('HP', 'HP', 'HP', 'HP', 'HP', 'HP', 'HP'),
    'dps': ('每秒傷害', '每秒伤害', '秒間ダメージ', 'DPS', 'DPS', 'DPS', '초당 피해'),
    'value': ('綜合強度', '综合强度', '総合力', 'POWER', 'PODER', 'PODER', '종합 전력'),
    'knockback_threshold': ('抗擊退', '抗击退', 'ノックバック耐性', 'KNOCKBACK RES.', 'RES. EMPUJE', 'RES. EMPURRÃO',
                            '넉백 저항'),
    'name': ('名稱', '名称', '名前', 'NAME', 'NOMBRE', 'NOME', '이름'),
    'newest': ('新加入', '新加入', '新着', 'NEWEST', 'RECIENTES', 'RECENTES', '최신'),
    'ascending': ('由低到高', '由低到高', '昇順', 'ASCENDING', 'ASCENDENTE', 'CRESCENTE', '오름차순'),
    'descending': ('由高到低', '由高到低', '降順', 'DESCENDING', 'DESCENDENTE', 'DECRESCENTE', '내림차순'),
    'original': ('原版', '原版', 'オリジナル', 'ORIGINAL', 'ORIGINAL', 'ORIGINAL', '오리지널'),
    'body': ('S1XLV', 'S1XLV', 'S1XLV', 'S1XLV', 'S1XLV', 'S1XLV', 'S1XLV'),
    'mod': ('MOD', 'MOD', 'MOD', 'MOD', 'MOD', 'MOD', 'MOD'),
    'search': ('搜尋名稱', '搜索名称', '名前で検索', 'SEARCH NAME', 'BUSCAR NOMBRE', 'BUSCAR NOME', '이름 검색'),
    'reset': ('預設設定', '恢复默认', '初期設定', 'Return to default', 'Restablecer', 'Restaurar', '기본 설정'),
    'empty': ('沒有符合條件的單位', '没有符合条件的单位', '該当するユニットがありません', 'NO MATCHING UNITS',
              'NO HAY UNIDADES', 'NENHUMA UNIDADE', '해당 유닛이 없습니다'),
}
# 原生已有译文的文字（strCustomize 27“預設設定”、strShop 0“購買”），优先读取原生字串。
NATIVE_TEXT = {'reset': ('_Z18GetStringCustomizeii', 27), 'buy': ('_Z13GetStringShopii', 0)}
CUSTOM_SORTS = ('uid', 'level', 'ap', 'hp', 'dps', 'value', 'knockback_threshold', 'name', 'newest')
SHOP_SORTS = ('uid', 'price', 'ap', 'hp', 'dps', 'value', 'knockback_threshold', 'name', 'newest')
SOURCES = ('original', 'body', 'mod')
CARD_CACHE_LIMIT = 160
STAT_WARM_PER_FRAME = 60
BUY_RECT = (CARD_W - CARD_EDGES[2] * CARD_SCALE - 8 - 104, CARD_EDGES[1] * CARD_SCALE + 52, 104, 46)   # D35


def default_settings(mode):
    return {'sort': 'uid', 'descending': False, 'factions': [0, 1, 2, 3, 4, 5], 'sources': list(SOURCES),
            'text': '', 'page': 0, 'favorites_only': False}


# ---------------------------------------------------------------- 图像工具（与已确认样张同一算法）
def scaled(img, factor):
    from PIL import Image
    return img.resize((max(1, round(img.width * factor)), max(1, round(img.height * factor))), Image.NEAREST)


def nine4(src, w, h, edges, k):
    """四边厚度不同的九宫格：边与角按 k 倍放大，中间拉伸（卡片底板，D19）。"""
    from PIL import Image
    l, t, r, b = edges
    sw, sh = src.size
    xs = ((0, l, 0, l * k), (l, sw - r, l * k, w - r * k), (sw - r, sw, w - r * k, w))
    ys = ((0, t, 0, t * k), (t, sh - b, t * k, h - b * k), (sh - b, sh, h - b * k, h))
    out = Image.new('RGBA', (w, h))
    for sx0, sx1, dx0, dx1 in xs:
        for sy0, sy1, dy0, dy1 in ys:
            if dx1 > dx0 and dy1 > dy0:
                out.alpha_composite(src.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0), Image.NEAREST),
                                    (dx0, dy0))
    return out


def slice9(src, w, h, edges, k=2):
    """九宫格：源图先按 k 倍放大，四角保持；中间列横向拉伸、中间行纵向平铺（原生弹窗与列表按钮）。"""
    from PIL import Image
    s = scaled(src, k)
    l, t, r, b = (e * k for e in edges)
    sw, sh = s.size
    out = Image.new('RGBA', (w, h))
    xs = ((0, l, 0, l), (l, sw - r, l, w - r), (sw - r, sw, w - r, w))
    ys = ((0, t, 0, t), (t, sh - b, t, h - b), (sh - b, sh, h - b, h))
    for sx0, sx1, dx0, dx1 in xs:
        for sy0, sy1, dy0, dy1 in ys:
            if dx1 <= dx0 or dy1 <= dy0 or sx1 <= sx0 or sy1 <= sy0:
                continue
            piece = s.crop((sx0, sy0, sx1, sy1))
            if dx1 - dx0 != piece.width:
                piece = piece.resize((dx1 - dx0, piece.height), Image.NEAREST)
            for y in range(dy0, dy1, piece.height):
                for x in range(dx0, dx1, piece.width):
                    out.alpha_composite(piece.crop((0, 0, min(piece.width, dx1 - x), min(piece.height, dy1 - y))),
                                        (x, y))
    return out


def pick_rows(img, rows):
    from PIL import Image
    out = Image.new('RGBA', (img.width, len(rows)))
    for i, r in enumerate(rows):
        out.paste(img.crop((0, r, img.width, r + 1)), (0, i))
    return out


def lum(c):
    return (c[0] * 299 + c[1] * 587 + c[2] * 114) // 1000


def tint_cell(cell, target):
    """选单位格内部的绿色按原生绿通道比例换算到目标色（D18），边框与横纹明暗保持。"""
    out = cell.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a and g > r + 40 and g > b + 20:
                k = g / 122
                px[x, y] = (min(255, round(target[0] * k)), min(255, round(target[1] * k)),
                            min(255, round(target[2] * k)), a)
    return out


def frame_to_metal(src, cell, rng):
    """进度条框的中性灰阶按相对亮度换成选单位格边框的暖灰金属色，只取较深的 rng 亮度范围（D24、D27）。"""
    metal = sorted({(lum(c), c[:3]) for c in cell.getdata() if c[3] > 200 and not c[1] > c[0] + 40 and lum(c) > 10})
    cmin, cmax = metal[0][0], metal[-1][0]
    out = src.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a > 0 and lum((r, g, b)) >= 40:
                t = (lum((r, g, b)) - 45) / (254 - 45)
                target = cmin + max(0.0, min(1.0, t)) * (cmax - cmin) * rng
                px[x, y] = min(metal, key=lambda m: abs(m[0] - target))[1] + (a,)
    return out


def ramp(fill, dark, light):
    """填充条保留原生横向明暗分层，换成 dark→light 色带（D24）。"""
    out = fill.copy()
    px = out.load()
    values = [px[0, y][1] for y in range(out.height)]
    lo, hi = min(values), max(values)
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a:
                t = (g - lo) / max(1, hi - lo)
                px[x, y] = tuple(round(dark[i] + (light[i] - dark[i]) * t) for i in range(3)) + (a,)
    return out


def star_polygon(cx, cy, r):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


# ---------------------------------------------------------------- 素材
class Art:
    """原生素材：图集（经 lab_ui.Skin，含社区图标页）、转换表、卡片部件与单位头像。全部缓存。"""

    def __init__(self, p, lab):
        self.p = p
        self.skin = Skin(lab)
        self.cache = {}
        self.icons = None
        self.root = Path(lab.root)

    def part(self, spec):
        key = ('part', spec)
        if key not in self.cache:
            name, (x, y, w, h) = spec
            self.cache[key] = self.skin.atlas(name).crop((x, y, x + w, y + h))
        return self.cache[key]

    def conv(self, index):
        """ConvMenuParts 第 index 项：(图像, 锚点 x, 锚点 y)。"""
        key = ('conv', index)
        if key not in self.cache:
            x, y, w, h, ax, ay, _, page = struct.unpack('<8h', self.p.read(CONV_MENU_PARTS + index * 16, 16))
            atlas = 'menuparts_02.obm' if page == 1 else 'menuparts.obm'
            self.cache[key] = (self.part((atlas, (x, y, w, h))), ax, ay)
        return self.cache[key]

    def conv_scaled(self, index, k):
        key = ('conv_scaled', index, k)
        if key not in self.cache:
            img, ax, ay = self.conv(index)
            self.cache[key] = (scaled(img, k), ax, ay)
        return self.cache[key]

    def logo(self, faction, k=2, dim=False):
        """阵营标志（position_icon.obm，转换表 53）；dim 为真时透明度降为三分之一（筛选关闭）。"""
        key = ('logo', faction, k, dim)
        if key not in self.cache:
            if not 0 <= faction <= 5:
                self.cache[key] = None
            elif dim:
                logo = self.logo(faction, k).copy()
                logo.putalpha(logo.getchannel('A').point(lambda a: a // 3))
                self.cache[key] = logo
            else:
                x, y, w, h = struct.unpack('<4h', self.p.read(CONV_POSITION + faction * 16, 8))
                self.cache[key] = scaled(self.part(('position_icon.obm', (x, y, w, h))), k)
        return self.cache[key]

    def slice(self, spec, w, h, edges, k=2):
        """原生弹窗、列表按钮等的九宫格结果（缓存）。"""
        key = ('slice', spec, w, h, edges, k)
        if key not in self.cache:
            self.cache[key] = slice9(self.part(spec), w, h, edges, k)
        return self.cache[key]

    def cell(self):
        key = ('cell',)
        if key not in self.cache:
            self.cache[key] = scaled(tint_cell(self.part(CELL), CELL_TINT), CARD_SCALE)
        return self.cache[key]

    def card_base(self, w, lit=False):
        """卡片底板；lit 为真时为按下的亮版：底板内部（四边以内）按原生列表按钮原图与亮版（ConvMenuParts 110 → 111）
        的平均颜色比提亮，边框不变（D52）。"""
        from PIL import Image
        key = ('card_base', w, lit)
        if key not in self.cache:
            if not lit:
                self.cache[key] = nine4(self.part(CARD), w, CARD_H, CARD_EDGES, CARD_SCALE)
            else:
                base = self.card_base(w).copy()
                ratio = self.lit_ratio()
                left, top, right, bottom = (e * CARD_SCALE for e in CARD_EDGES)
                inner = base.crop((left, top, w - right, CARD_H - bottom))
                channels = [band.point(lambda v, r=r: min(255, round(v * r))) for band, r in zip(inner.split()[:3], ratio)]
                inner = Image.merge('RGBA', channels + [inner.getchannel('A')])
                base.paste(inner, (left, top))
                self.cache[key] = base
        return self.cache[key]

    def lit_ratio(self):
        """原生列表按钮亮版与原图的逐通道平均颜色比（两图逐像素配对，只计不同的不透明像素）。"""
        key = ('lit_ratio',)
        if key not in self.cache:
            pairs = [(a, b) for a, b in zip(self.part(TAB_OFF).getdata(), self.part(TAB_ON).getdata())
                     if a[3] == 255 and a != b]
            self.cache[key] = tuple(sum(b[c] for _, b in pairs) / max(1, sum(a[c] for a, _ in pairs)) for c in range(3))
        return self.cache[key]

    def color_map(self, base, lit):
        key = ('color_map', base, lit)
        if key not in self.cache:
            self.cache[key] = color_map(self.part(base), self.part(lit))
        return self.cache[key]

    def gauge_frame(self):
        key = ('gauge_frame',)
        if key not in self.cache:
            self.cache[key] = pick_rows(frame_to_metal(self.part(GAUGE), self.part(CELL), GAUGE_FRAME_RANGE),
                                        GAUGE_FRAME_ROWS)
        return self.cache[key]

    def gauge_fill(self, full):
        key = ('gauge_fill', full)
        if key not in self.cache:
            dark, light = GAUGE_COLORS[2:] if full else GAUGE_COLORS[:2]
            self.cache[key] = pick_rows(ramp(self.part(GAUGE_FULL if full else GAUGE_FILL), dark, light),
                                        GAUGE_FILL_ROWS)
        return self.cache[key]

    def gauge(self, level, cap, w, k=CARD_SCALE):
        """原生 EVENT 任务进度条（D24、D36）：框左右各 5 列保持、中间拉长；按当前上限计算，达到上限用充满填充。"""
        from PIL import Image
        key = ('gauge', min(level, cap), cap, w)
        if key in self.cache:
            return self.cache[key]
        src = self.gauge_frame()
        fh = src.height
        frame = Image.new('RGBA', (w, fh * k))
        frame.alpha_composite(scaled(src.crop((0, 0, 5, fh)), k), (0, 0))
        frame.alpha_composite(src.crop((5, 0, 55, fh)).resize((w - 10 * k, fh * k), Image.NEAREST), (5 * k, 0))
        frame.alpha_composite(scaled(src.crop((55, 0, 60, fh)), k), (w - 5 * k, 0))
        inner = w - 10 * k
        full = level >= cap
        fw = inner if full else round(inner * level / max(1, cap) / k) * k
        if fw > 0:
            fill = self.gauge_fill(full)
            frame.alpha_composite(fill.resize((fw, fill.height * k), Image.NEAREST), (5 * k, 3 * k))
        self.cache[key] = frame
        return frame

    def button(self, name):
        """底栏按钮（60×48）：原生 BACK / SORT，FAVORITES 为用户设计的按钮图（D26，筛选开启时为 favorites_on），
        PACK 为原生 FREE 拼字（D33）。"""
        key = ('button', name)
        if key in self.cache:
            return self.cache[key]
        from PIL import Image
        if name in BUTTONS:
            img = self.conv(BUTTONS[name])[0]
        elif name in FAVORITES_BUTTONS:
            img = Image.open(self.root / 'custom_content' / FAVORITES_BUTTONS[name]).convert('RGBA')
        elif name == 'blank':
            img = Image.open(self.root / 'custom_content' / 'u1_button_blank.png').convert('RGBA')
        elif name == 'pack':
            img = self.button('free').copy()
            blank, back, map_ = self.button('blank'), self.button('back'), self.button('map')
            y0, y1 = LABEL_ROWS
            img.paste(blank.crop((6, y0, 54, y1)), (6, y0))
            for i, (src, col) in enumerate(((map_, 34), (back, 24), (back, 30), (back, 36))):
                img.paste(src.crop((col, y0, col + 5, y1)), (18 + i * 6, y0))
        else:
            raise KeyError(name)
        self.cache[key] = img
        return img

    def icon_table(self):
        """UnitID → (图集, 矩形, 锚点)。原版：菜单表 +10 头像序号 → ConvUnitIcon（x,y,w,h,锚点 x,y,—,页）；
        社区单位：单位文件 icon（rect、anchor、page 或 atlas）。"""
        if self.icons is None:
            p = self.p
            menu = (p.word(MENU_TABLE_LITERAL[0]) + MENU_TABLE_LITERAL[1] + 0x818) & 0xffffffff
            conv = p.symbols['ConvUnitIcon']
            icons = {}
            for row in range(320):
                uid = p.word(menu + row * 20)
                index = struct.unpack('<h', p.read(menu + row * 20 + 10, 2))[0]
                if uid and 0 <= index < 340:
                    x, y, w, h, ax, ay, _, page = struct.unpack('<8h', p.read(conv + index * 16, 16))
                    if w > 0 and h > 0:
                        icons[uid] = (ICON_PAGES.get(page, ICON_PAGES[1]), (x, y, w, h), (ax, ay))
            community = getattr(p, 'community', None)
            for unit in (community.units if community is not None else []):
                icon = unit.get('icon')
                if icon:
                    icons[unit['id']] = (icon.get('atlas') or ICON_PAGES[icon.get('page', 1)], tuple(icon['rect']),
                                         tuple(icon.get('anchor', (0, 0))))
            self.icons = icons
        return self.icons

    def icon(self, uid):
        key = ('icon', uid)
        if key not in self.cache:
            entry = self.icon_table().get(uid)
            if entry is None:
                self.cache[key] = None
            else:
                name, rect, anchor = entry
                try:
                    img = self.part((name, rect))
                except (OSError, ValueError, KeyError):
                    img = None
                self.cache[key] = (scaled(img, CARD_SCALE), anchor) if img is not None and img.getbbox() else None
        return self.cache[key]

    def background(self):
        """原生商店 / 强化背景（shopback.obm，D23）：主景 512×224 按 2.25 倍置于画布左端（y=65），
        右侧以图集底部 8 块图块纵向拼成延伸列。"""
        key = ('background',)
        if key not in self.cache:
            from PIL import Image
            img = Image.new('RGBA', (W, H), (0, 0, 0, 255))
            scene = scaled(self.part(('shopback.obm', (0, 0, 512, 224))), 2.25)
            img.alpha_composite(scene, (0, 65))
            column = Image.new('RGBA', (56, 224))
            y = 0
            for i, x in enumerate((0, 57, 114, 171, 228, 285, 342, 399)):
                rows = 31 if i < 6 else 19
                column.alpha_composite(self.part(('shopback.obm', (x, 225, 56, rows))), (0, y))
                y += rows
            img.alpha_composite(scaled(column, 2.25), (scene.width, 65))
            self.cache[key] = img
        return self.cache[key]


# ---------------------------------------------------------------- 浏览组件
class UnitBrowser:
    def __init__(self, p, lab, root):
        self.p, self.lab, self.root = p, lab, Path(root)
        self.art = None
        self.open = False
        self.mode = 'custom'
        self.panel = None                     # None 或 'sort'
        self.search_focus = False
        self.commands = []                    # 窗口线程写入（键、字符、滚轮），游戏线程处理
        self.state = None
        self.pressed = self.pressed_rect = None
        self.pointer_inside = False
        self.hitboxes = []
        self.overlay = self.press_overlay = None
        self.static_layers = {}
        self.cards = {}                       # 卡片图像 LRU（键含单位、等级、上限、收藏、显示、语言）
        self.card_order = []
        self.revision = 0
        self.page_items, self.total = [], 0
        self.query_key = None
        self.rendered = None
        self.rendered_key = None
        self.prefetch = []
        self.timings = []
        self.fonts = {}
        self.text_cache = {}
        self.native_strings = {}
        self.on_open_unit = None              # (key) → None；U1b 接入单位菜单
        self.on_buy = None                    # (key) → None；未设置时打开购买确认（unit_menu.open_buy）
        self.on_pack = None                   # () → None；未设置时进入原生组合包页面（enter_packs）
        self.on_back = None                   # () → bool；U1b/U1c 接入原生返回；返回假或未设置时关闭本组件
        self.packs = None
        self.pages, self.all_items = 1, []
        self.stat_queue = None
        self.panel_base = None
        self.menu = None                      # 单位菜单（unit_menu.UnitMenu，U1b）
        self.shutter = Shutter(lab)           # 进入与离开时的原生闸门
        self.entry_pressed = False            # “單位”面板 / UNIT 卡的按压（交给原生显示白光）
        self.entry_cancelled = False
        self.entry_box = None
        self.entry_mode = None
        self.packs_native = False             # 原生组合包页面（PACK，D33）显示中：本界面暂停绘制
        self.saved_catalog = None             # 组合包页面期间暂存的原生商品目录（社区头部 +44 / +48）
        self.pack_list = None
        self.back_press = None                # 组合包 / 编队页面上原生底栏按钮的按压（宿主受理）：{'slot','task','cancelled'}
        self.deck_native = False              # 原生编队页（DECK，D53）显示中：本界面暂停绘制
        self.layers = {}                      # 最近一次合成的各画面分层：'grid' / 'menu' → {'chrome', 卡片或面板, 'page'}
        self.gl = None                        # 动效与按下白光的纹理层（unit_motion.Layers）
        self.motion = None                    # 进行中的过渡（unit_motion.Motion）
        self.motion_drawn = False             # 本帧画了过渡（单位菜单的动作演示在过渡结束后的下一帧开始）
        self.shown_state = None               # 当前画面状态（view_state），变化时开始过渡
        self.slide_dir = 0                    # 翻页方向（flip 设定，过渡开始时取用）
        self.lights = Lights()                # 按下白光
        self.lit_cache = {}
        self.black = None
        self.icon_lights = {}        # 图标类按钮（箭头、收藏、阵营标志）：命令 → (图标图像, 画布位置)，按下时只让图标本身变亮
        self.layer_serial = 0                 # 每次合成分层时递增，作为分层纹理的键（空闲帧预先上传）
        self.frames = {}                      # 弹窗空框（按弹窗种类缓存）

    # ---------- 状态与持久化 ----------
    def state_path(self):
        return self.p.saves / STATE_NAME

    def load_state(self):
        state = {'schema': STATE_SCHEMA, 'favorites': [], 'custom': default_settings('custom'),
                 'shop': default_settings('shop')}
        try:
            data = json.loads(self.state_path().read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = None
        if isinstance(data, dict):
            favorites = data.get('favorites')
            if isinstance(favorites, list):
                state['favorites'] = [k for k in favorites if isinstance(k, str)][:10000]
            for mode in ('custom', 'shop'):
                saved = data.get(mode)
                if not isinstance(saved, dict):
                    continue
                settings = state[mode]
                sorts = SHOP_SORTS if mode == 'shop' else CUSTOM_SORTS
                if saved.get('sort') in sorts:
                    settings['sort'] = saved['sort']
                for name in ('descending', 'favorites_only'):
                    if isinstance(saved.get(name), bool):
                        settings[name] = saved[name]
                factions = saved.get('factions')
                if isinstance(factions, list) and all(isinstance(f, int) and 0 <= f <= 5 for f in factions):
                    settings['factions'] = sorted(set(factions))
                sources = saved.get('sources')
                if isinstance(sources, list) and all(s in SOURCES for s in sources):
                    settings['sources'] = [s for s in SOURCES if s in sources]
                if isinstance(saved.get('text'), str) and len(saved['text']) <= 40:
                    settings['text'] = saved['text']
                if isinstance(saved.get('page'), int) and saved['page'] >= 0:
                    settings['page'] = saved['page']
        self.state = state

    def save_state(self):
        if self.state is None:
            return
        path = self.state_path()
        try:
            temporary = path.with_name(path.name + '.tmp')
            temporary.write_text(json.dumps(dict(self.state, schema=STATE_SCHEMA), ensure_ascii=False, indent=1),
                                 encoding='utf-8')
            os.replace(temporary, path)
        except OSError as error:
            self.p.log('UNIT_BROWSER_SAVE_ERROR', type(error).__name__, str(error))

    @property
    def settings(self):
        return self.state[self.mode]

    def favorites(self):
        return set(self.state['favorites'])

    def toggle_favorite(self, key):
        favorites = self.state['favorites']
        if key in favorites:
            favorites.remove(key)
        else:
            favorites.append(key)
        self.save_state()
        self.invalidate()

    # ---------- 打开与关闭 ----------
    def set_open(self, value, mode='custom'):
        if value:
            if not self.open:
                # 离开时回到的主菜单子页（1 MENU 主画面、2 OPTION、3 CUSTOMIZE、4 SHOP），取打开时的子页
                state = self.p.word(self.p.app_instance() + 0x22dc)
                self.return_page = state if 1 <= state <= 4 else (4 if mode == 'shop' else 3)
            if self.state is None:
                self.load_state()
            self.mode = mode
            self.open = True
            self.panel = None
            self.panel_base = None
            self.search_focus = False
            if self.art is None:
                self.art = Art(self.p, self.lab)
            self.refresh()
        elif self.open:
            self.open = False
            self.panel = None
            self.search_focus = False
            if self.menu is not None:
                self.menu.close()
            self.save_state()
        self.pressed = None
        self.motion = self.shown_state = None
        self.slide_dir = 0
        self.lights.clear()

    def invalidate(self):
        self.query_key = None
        self.revision += 1

    def refresh(self):
        """存档数据变化后（打开页面、购买、强化）：更新目录条目的拥有状态、等级与解锁，重查组合包。"""
        self.catalog().refresh_state(shop=self.mode == 'shop')
        self.packs = None
        self.static_layers.clear()
        self.invalidate()

    def data_changed(self):
        """强化、开放阶段与购买之后：条目状态与货币变化，卡片按新等级与上限重画。"""
        self.refresh()

    def catalog(self):
        from unit_catalog import catalog
        return catalog(self.p)

    def unit_menu(self):
        if self.menu is None:
            from unit_menu import UnitMenu
            self.menu = UnitMenu(self)
        return self.menu

    def language(self):
        app = self.p.app_instance()
        return self.p.word(app + 0x3d64) if app else 0

    def tr(self, key):
        if key in NATIVE_TEXT and self.language() in NATIVE_LANGUAGES:
            value = self.native_text(key)
            if value:
                return value
        values = TEXT[key]
        return values[LANG_INDEX.get(self.language(), 3)]

    def native_text(self, key):
        language = self.language()
        cache_key = (key, language)
        if cache_key not in self.native_strings:
            symbol, index = NATIVE_TEXT[key]
            try:
                value = self.p.string(self.p.call(symbol, index, language)).strip()
            except Exception:
                value = ''
            if not value:
                try:
                    value = self.p.string(self.p.call(symbol, index, 0)).strip()
                except Exception:
                    value = ''
            self.native_strings[cache_key] = value
        return self.native_strings[cache_key]

    # ---------- 查询 ----------
    def filters(self):
        s = self.settings
        out = {'faction': set(s['factions'])}
        if set(s['sources']) != set(SOURCES):
            wanted = set(s['sources'])
            out['_sources'] = wanted
        if s['text']:
            out['text'] = s['text']
        if s['favorites_only']:
            out['keys'] = self.favorites()
        if self.mode == 'shop':
            out['owned'], out['unlocked'] = False, True
        else:
            out['owned'] = True
        return out

    def query(self):
        """当前页条目与总数（筛选、排序经 unit_catalog.list；来源按原版 / S1XLV / 模组三类）。"""
        s = self.settings
        key = (self.mode, self.revision, self.language())
        if key == self.query_key:
            return
        began = time.perf_counter()
        catalog = self.catalog()
        filters = self.filters()
        sources = filters.pop('_sources', None)
        if sources is not None:
            names = {e['source'] for e in catalog.index()}
            allowed = set()
            for name in names:
                kind = 'original' if name == 'original' else 'body' if name == 'body' else 'mod'
                if kind in sources:
                    allowed.add(name)
            filters['source'] = allowed
        items, total = catalog.list(filters, sort=s['sort'], descending=s['descending'], page=0,
                                    page_size=10 ** 9, level='owned' if self.mode == 'custom' else 1)
        pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        s['page'] = min(max(s['page'], 0), pages - 1)
        self.stat_queue = None                 # 列表变化后按新列表重新排定预算
        self.all_items = items
        self.total = total
        self.pages = pages
        self.page_items = items[s['page'] * PAGE_SIZE:(s['page'] + 1) * PAGE_SIZE]
        self.query_key = key
        self.last_query_ms = (time.perf_counter() - began) * 1000

    def flip(self, delta):
        """翻页（首末页循环，D8）。"""
        self.query()
        if self.pages <= 1:
            return False
        s = self.settings
        s['page'] = (s['page'] + delta) % self.pages
        self.page_items = self.all_items[s['page'] * PAGE_SIZE:(s['page'] + 1) * PAGE_SIZE]
        self.slide_dir = 1 if delta > 0 else -1
        self.revision += 1
        self.query_key = (self.mode, self.revision, self.language())
        return True

    # ---------- 文字 ----------
    def font(self, size):
        """与原生界面相同的按语言选字（text_render.font_for）；简体中文（8）用微软雅黑。"""
        language = self.language()
        key = (language, size)
        if key not in self.fonts:
            import text_render
            if language == 8:
                self.fonts[key] = text_render.font_for(self.p, size, 10)
            else:
                self.fonts[key] = text_render.font_for(self.p, size, language)
        return self.fonts[key]

    def text(self, img, xy, value, size, fill=(240, 240, 240, 255), anchor='lm', stroke=2, width=None):
        """原生字体绘制（text_render.font_for，以基线定位）；anchor 为 l/m/r 与 a/m 的组合；width 限宽时缩小字号。
        文字先绘制成小图并缓存（按语言、内容、字号、颜色、描边），再贴到目标图像。"""
        from PIL import Image, ImageDraw
        font = self.font(size)
        if width is not None:
            while size > 12 and font.getlength(value) > width:
                size -= 1
                font = self.font(size)
        key = (self.language(), value, size, fill, stroke)
        cached = self.text_cache.get(key)
        if cached is None:
            asc, desc = font.getmetrics()
            w = math.ceil(font.getlength(value)) + 2 * stroke + 4
            h = asc + desc + 2 * stroke + 4
            layer = Image.new('RGBA', (max(1, w), max(1, h)))
            font.draw(ImageDraw.Draw(layer), (stroke + 2, stroke + 2 + asc), value, fill=fill, stroke_width=stroke,
                      stroke_fill=(0, 0, 0, 255))
            cached = self.text_cache[key] = (layer, font.getlength(value), asc, desc, stroke + 2)
            if len(self.text_cache) > 2000:
                self.text_cache.pop(next(iter(self.text_cache)))
        layer, w, asc, desc, pad = cached
        x, y = xy
        if anchor[0] == 'm':
            x -= w / 2
        elif anchor[0] == 'r':
            x -= w
        top = y if anchor[1] == 'a' else y + (asc - desc) / 2 - asc
        img.alpha_composite(layer, (round(x - pad), round(top - pad)))

    # ---------- 原生数字 ----------
    def conv_paste(self, img, index, x, y, k):
        sprite, ax, ay = self.art.conv_scaled(index, k)
        img.alpha_composite(sprite, (round(x - ax * k), round(y - ay * k)))

    def number(self, img, x, y, value, digits, k, pitch, lead=True):
        """与原生 AppMain::drawNum2 相同：x 为最左一位，从右向左绘制，数值取完后用暗色 0 补位（lead=False 时不补位）。"""
        value = max(0, int(value))
        count = max(len(str(value)), digits if lead else 0)
        cx = x + (count - 1) * pitch
        base = 9
        for _ in range(count):
            self.conv_paste(img, base + value % 10, cx, y, k)
            value //= 10
            if value == 0:
                base = 20
            cx -= pitch
        return x + count * pitch

    def counter(self, img, icon_x, y, icon, colon_dx, digits_dx, value, digits):
        """原生顶栏勋章 / MSP 计数（GT_CockpitMedalDraw / GT_CockpitMSPDraw，D20）。"""
        k = NATIVE_TO_CANVAS
        s = 2 * k
        self.conv_paste(img, icon, icon_x * k, y, s)
        self.conv_paste(img, 8, (icon_x + colon_dx) * k, y, s)
        self.number(img, (icon_x + digits_dx) * k, y, value, digits, s, 18 * k)

    def level_label(self, img, x, y, level, cap):
        """等级 / 上限（D21）：原生银色数字与第 85 项斜线，2 倍。"""
        k, pitch = CARD_SCALE, 9 * CARD_SCALE
        y -= 11 * k // 2
        x = self.number(img, x, y, level, 0, k, pitch, lead=False)
        self.conv_paste(img, 85, x + 1, y, k)
        self.number(img, x + 12 * k, y, cap, 0, k, pitch, lead=False)

    # ---------- 画面 ----------
    def static_layer(self, names=None):
        """背景、顶栏（标题字样）、底栏与按钮：随模式、语言、组合包按钮与底栏状态变化。names 为底栏按钮（单位菜单只有 BACK）。"""
        s = self.settings
        packs = self.mode == 'shop' and bool(self.pack_available())
        if names is None:
            # 强化：BACK、FAVORITES、DECK、SORT（D53）；商店：BACK、FAVORITES、（PACK）、SORT（D33）
            names = (['back', 'favorites'] + (['deck'] if self.mode == 'custom' else [])
                     + (['pack'] if packs else []) + ['sort'])
        key = (self.mode, tuple(names), s['favorites_only'])
        if key in self.static_layers:
            return self.static_layers[key]
        from PIL import ImageDraw
        art = self.art
        img = art.background().copy()
        img.alpha_composite(scaled(art.part(HEADER), 2.25), (1, 0))
        t1 = scaled(art.part(TITLE_SHOP if self.mode == 'shop' else TITLE_CUSTOMIZE), 2)
        t2 = scaled(art.part(TITLE_UNIT), 2)
        img.alpha_composite(t1, (36, 36))
        img.alpha_composite(t2, (36 + t1.width + 14, 40))
        img.alpha_composite(scaled(art.part(BOTTOM_BAR), 2.25), (1, H - 151))
        d = ImageDraw.Draw(img)
        self.bar_boxes = []
        for i, name in enumerate(names):
            x = round(BAR_LEFT + (BAR_RIGHT - BAR_LEFT) * i / max(1, len(names) - 1))
            img.alpha_composite(scaled(self.bar_button(name), BUTTON_SCALE), (x, BAR_Y))
            self.bar_boxes.append(((x, BAR_Y, round(60 * BUTTON_SCALE), round(48 * BUTTON_SCALE)), ('bar', name)))
        self.static_layers[key] = (img, list(self.bar_boxes))
        return self.static_layers[key]

    def bar_button(self, name):
        """底栏按钮图：收藏筛选开启时 FAVORITES 为 favorites_on（D26）。"""
        return self.art.button('favorites_on' if name == 'favorites' and self.settings['favorites_only'] else name)

    def chrome(self, names):
        """静态层加顶栏勋章与 MSP 计数（单位菜单使用）：返回 (图像, 底栏点击区域)。"""
        static, bar_boxes = self.static_layer(names)
        img = static.copy()
        wallet = self.catalog().wallet()
        self.counter(img, 654, 41, 6, 40, 56, wallet['medal'], 6)
        self.counter(img, 871, 41, 7, 68, 84, wallet['msp'], 8)
        return img, list(bar_boxes)

    def pack_available(self):
        """可再购买的组合包（打开页面与数据刷新时重新查询，D33）。"""
        if self.packs is None:
            try:
                self.packs = [e for e in self.catalog().packs() if e['purchasable']]
            except Exception as error:
                self.p.log('UNIT_BROWSER_PACKS_ERROR', type(error).__name__, str(error))
                self.packs = []
        return self.packs

    def card_key(self, entry):
        favorite = entry['key'] in self.favorites()
        s = self.settings
        if self.mode == 'shop':
            return ('shop', entry['uid'], entry['price'], favorite, self.language())
        cap = self.catalog().cap_of(entry['uid'])
        return ('custom', entry['uid'], entry['level'], cap, favorite, self.language())

    def card_image(self, entry, lit=False):
        key = self.card_key(entry) + (('lit',) if lit else ())
        image = self.cards.get(key)
        if image is None:
            image = self.render_card(entry, key, lit)
            self.cards[key] = image
            self.card_order.append(key)
            while len(self.card_order) > CARD_CACHE_LIMIT:
                self.cards.pop(self.card_order.pop(0), None)
        return image

    def render_card(self, entry, key, lit=False):
        """卡片（make_mockups.card / make_detail_mockups.shop_card）：底板、选单位格与头像（原生锚点）、阵营标志与名称、
        强化为等级进度条 + 等级 / 上限 + MAX，商店为勋章售价 + BUY；DISPLAY 为 ap 时显示出击 AP。"""
        from PIL import ImageDraw
        art = self.art
        k = CARD_SCALE
        w = CARD_W
        img = art.card_base(w, lit).copy()
        d = ImageDraw.Draw(img)
        ix, iy = CARD_EDGES[0] * k, CARD_EDGES[1] * k
        cell = art.cell()
        img.alpha_composite(cell, (ix, iy))
        icon = art.icon(entry['uid'])
        if icon is not None:
            sprite, (ax, ay) = icon
            img.alpha_composite(sprite, (ix + round(-ax * k), iy + round(-ay * k)))
        x0 = ix + cell.width + 14
        right = w - CARD_EDGES[2] * k - 8
        logo = art.logo(entry['faction'])
        row1 = iy + CARD_ROW1
        favorite = self.card_key(entry)[-2]
        name_x = x0
        if logo is not None:
            img.alpha_composite(logo, (x0, row1))
            name_x = x0 + logo.width + 8
        mid = row1 + 15
        room = right - name_x - (26 if favorite else 0)
        self.text(img, (name_x, mid), entry['name'], 22, anchor='lm', width=room)
        if favorite:
            d.polygon(star_polygon(right - 8, mid, 11), fill=FAVORITE_STAR, outline=(60, 30, 0, 255), width=2)
        if self.mode == 'shop':
            self.conv_paste(img, 6, x0 + 2, iy + 62, 2)
            self.conv_paste(img, 8, x0 + 46, iy + 62, 2)
            self.number(img, x0 + 62, iy + 62, entry['price'] or 0, 0, 2, 18, lead=False)
            bx, by, bw, bh = BUY_RECT
            img.alpha_composite(art.slice(RED, bw, bh, (5, 5, 5, 5), 2), (bx, by))
            self.text(img, (bx + bw / 2, by + bh / 2), self.tr('buy'), 24, anchor='mm', width=bw - 12)
        else:
            level = entry['level'] or 1
            cap = self.card_key(entry)[3]
            by = iy + 44
            g = art.gauge(level, cap, right - x0)
            img.alpha_composite(g, (x0, by))
            ly = by + g.height + 4
            if level >= cap:
                mx = scaled(art.part(MAX), 2)
                img.alpha_composite(mx, (right - mx.width, ly - 1))
            self.level_label(img, x0, ly + 11, level, cap)
        return img

    def card_box(self, index):
        r, c = divmod(index, COLS)
        return (LEFT + c * (CARD_W + GAP_X), TOP + r * (CARD_H + GAP_Y), CARD_W, CARD_H)

    def compose(self):
        """整页图像：静态层 + 计数 + 卡片 + 翻页箭头与页码；同时登记点击区域与分层（self.layers['grid']）。"""
        from PIL import Image, ImageDraw
        began = time.perf_counter()
        art = self.art
        self.icon_lights = {}
        if self.menu is not None and self.menu.active:
            img, self.hitboxes = self.menu.compose()
            self.last_compose_ms = (time.perf_counter() - began) * 1000
            return img
        if self.panel == 'sort' and self.panel_base is not None:
            # 面板为模态：面板打开期间底下的页面保持打开面板时的画面，只重画面板；关闭面板后按新的排序与筛选重画整页。
            img = self.panel_base.copy()
            self.hitboxes = self.compose_panel(img)
            self.prefetch = list(self.page_items)        # 面板打开期间预先生成新条件下首页的卡片
            self.last_compose_ms = (time.perf_counter() - began) * 1000
            return img
        static, bar_boxes = self.static_layer()
        img = static.copy()
        boxes = list(bar_boxes)
        wallet = self.catalog().wallet()
        self.counter(img, 654, 41, 6, 40, 56, wallet['medal'], 6)
        self.counter(img, 871, 41, 7, 68, 84, wallet['msp'], 8)
        # 卡片画在独立的透明层（过渡时整页或逐行移动），再叠到底层之上
        cards = Image.new('RGBA', (W, H))
        for i, entry in enumerate(self.page_items):
            x, y, w, h = self.card_box(i)
            cards.alpha_composite(self.card_image(entry), (x, y))
            boxes.append(((x, y, w, h), ('card', entry['key'])))
            if self.mode == 'shop':
                bx, by, bw, bh = BUY_RECT
                boxes.append(((x + bx, y + by, bw, bh), ('buy', entry['key'])))
        if not self.page_items:
            self.text(cards, (W // 2, (TOP + BOTTOM) // 2), self.tr('empty'), 28, anchor='mm')
        nav = Image.new('RGBA', (W, H))                 # 翻页箭头与页码：切换画面时随卡片离开与进入，翻页平移时留在原处
        self.nav_rects = []
        if self.pages > 1:
            arrow = scaled(art.part(ARROW), 3)
            mid = (TOP + BOTTOM) // 2 - arrow.height // 2
            right_box = (RIGHT + 14, mid, arrow.width, arrow.height)
            left_box = (LEFT - 14 - arrow.width, mid, arrow.width, arrow.height)
            flipped = arrow.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            nav.alpha_composite(arrow, right_box[:2])
            nav.alpha_composite(flipped, left_box[:2])
            self.icon_lights[('page', 1)] = (arrow, right_box[:2])
            self.icon_lights[('page', -1)] = (flipped, left_box[:2])
            # 点击区域在可见箭头外各放宽 12 像素
            boxes.append(((right_box[0] - 12, right_box[1] - 12, right_box[2] + 24, right_box[3] + 24), ('page', 1)))
            boxes.append(((left_box[0] - 12, left_box[1] - 12, left_box[2] + 24, left_box[3] + 24), ('page', -1)))
            page, pages = self.settings['page'] + 1, self.pages
            k, pitch = 2, 18
            width = (len(str(page)) + len(str(pages))) * pitch + 12 * k
            x0 = x = RIGHT + 64 - width
            x = self.number(nav, x, TOP - 4, page, 0, k, pitch, lead=False)
            self.conv_paste(nav, 85, x + 1, TOP - 4, k)
            self.number(nav, x + 12 * k, TOP - 4, pages, 0, k, pitch, lead=False)
            counter = nav.getchannel('A').crop((x0 - 8, 0, W, TOP - 8)).getbbox()
            if counter:
                self.nav_rects.append(((x0 - 8 + counter[0] - 4, counter[1] - 4, counter[2] - counter[0] + 8,
                                        counter[3] - counter[1] + 8), 0))
            for bx, by, bw, bh in (left_box, right_box):
                self.nav_rects.append(((bx - 4, by - 4, bw + 8, bh + 8), 1))
        chrome = img.copy()
        items = cards.copy()
        items.alpha_composite(nav)                      # 页码压在右上卡片的边角之上，翻页平移时同样在卡片之上
        img.alpha_composite(items)
        self.layers['grid'] = {'chrome': chrome, 'nav': nav, 'items': items, 'cards': cards,
                               'page': img.copy() if self.panel == 'sort' else img, 'serial': self.stamp()}
        if self.panel == 'sort':
            boxes = self.compose_panel(img)
        self.hitboxes = boxes
        self.last_compose_ms = (time.perf_counter() - began) * 1000
        return img

    # ---------- SORT 面板 ----------
    def shaded(self, img):
        """面板底下的页面：压暗一次后缓存为面板打开期间的底层。"""
        from PIL import Image
        out = img.copy()
        out.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, 140)))
        return out

    def toggle_button(self, img, rect, label, on, size=24):
        """面板内的列表按钮：开启为米色底深色字，关闭为棕色底白字（原生列表按钮）。"""
        bx, by, bw, bh = rect
        img.alpha_composite(self.art.slice(TAB_ON if on else TAB_OFF, bw, bh, (8, 8, 8, 8), 2), (bx, by))
        self.text(img, (bx + bw / 2, by + bh / 2), label, size, (40, 30, 20, 255) if on else (240, 240, 240, 255),
                  'mm', 0 if on else 2, bw - 24)

    def compose_panel(self, img):
        """排序与筛选面板（原生弹窗、列表按钮与阵营标志）：上为排序项与方向（5 列 2 行），下为阵营标志、
        来源与名称搜索；底部为“預設設定”（strCustomize 27）与 OK。面板打开时只登记面板内的点击区域。"""
        art = self.art
        x, y, w, h = 40, 96, 1200, 500
        # 原生弹窗为半透明；面板下方再压暗一层，减少底下卡片文字透出
        from PIL import Image
        img.alpha_composite(Image.new('RGBA', (w, h), (0, 0, 0, 110)), (x, y))
        img.alpha_composite(art.slice(POPUP, w, h, (6, 6, 6, 6), 2), (x, y))
        gold = (245, 225, 90, 255)
        boxes = []
        s = self.settings
        left, inner = x + 40, w - 80
        gap = 20
        # 排序：9 项与升降方向共 10 格，5 列 2 行
        self.text(img, (left, y + 34), self.tr('sort'), 26, gold, 'lm')
        sorts = SHOP_SORTS if self.mode == 'shop' else CUSTOM_SORTS
        bw, bh = (inner - 4 * gap) // 5, 58
        cells = [(name, name == s['sort']) for name in sorts]
        for i, (name, on) in enumerate(cells):
            row, col = divmod(i, 5)
            rect = (left + col * (bw + gap), y + 60 + row * (bh + 16), bw, bh)
            self.toggle_button(img, rect, self.tr(name), on)
            boxes.append((rect, ('sort', name)))
        i = len(cells)
        row, col = divmod(i, 5)
        rect = (left + col * (bw + gap), y + 60 + row * (bh + 16), bw, bh)
        self.toggle_button(img, rect, self.tr('descending' if s['descending'] else 'ascending'), False)
        boxes.append((rect, ('direction',)))
        # 筛选：阵营标志（原生 4 倍，无底框；关闭时变淡），其下为来源按钮与名称搜索
        fy = y + 60 + 2 * (bh + 16) + 30
        self.text(img, (left, fy), self.tr('filter'), 26, gold, 'lm')
        ly, ls, lgap = fy + 24, 60, 44
        for faction in range(6):
            lx = left + faction * (ls + lgap)
            logo = art.logo(faction, 4, dim=faction not in s['factions'])
            if logo is not None:
                spot = (lx + (ls - logo.width) // 2, ly + (ls - logo.height) // 2)
                img.alpha_composite(logo, spot)
                self.icon_lights[('faction', faction)] = (logo, spot)
            boxes.append(((lx - lgap // 2, ly - 8, ls + lgap, ls + 16), ('faction', faction)))
        sy, sw = ly + ls + 18, 184
        for i, name in enumerate(SOURCES):
            rect = (left + i * (sw + gap), sy, sw, bh)
            self.toggle_button(img, rect, self.tr(name), name in s['sources'])
            boxes.append((rect, ('source', name)))
        tx = left + 3 * (sw + gap) + 20
        tw, th = left + inner - tx, bh
        img.alpha_composite(art.slice(FIELD, tw, th, (6, 6, 6, 6), 2), (tx, sy))
        if s['text'] or self.search_focus:
            caret = '|' if self.search_focus and (self.p.frame // 15) % 2 == 0 else ''
            self.text(img, (tx + 18, sy + th / 2), s['text'] + caret, 24, (40, 30, 20, 255), 'lm', 0, tw - 36)
        else:
            self.text(img, (tx + 18, sy + th / 2), self.tr('search'), 22, (120, 100, 80, 255), 'lm', 0, tw - 36)
        boxes.append(((tx, sy, tw, th), ('search',)))
        # 預設設定与 OK
        reset = scaled(art.part(DLG_BROWN), 2.25)
        ok = scaled(art.part(DLG_RED), 2.25)
        ry = y + h - 24 - ok.height
        rx, ox = x + w // 2 - 60 - reset.width, x + w // 2 + 60
        img.alpha_composite(reset, (rx, ry))
        self.text(img, (rx + reset.width / 2, ry + reset.height / 2), self.tr('reset'), 22, anchor='mm',
                  width=reset.width - 16)
        img.alpha_composite(ok, (ox, ry))
        self.text(img, (ox + ok.width / 2, ry + ok.height / 2), 'OK', 24, anchor='mm')
        boxes.append(((rx, ry, reset.width, reset.height), ('reset',)))
        boxes.append(((ox, ry, ok.width, ok.height), ('ok',)))
        # 面板内空白处吞掉点击（点击区域按倒序检索，置于最前即优先级最低）
        return [((x, y, w, h), ('panel',))] + boxes

    # ---------- 命令 ----------
    def command(self, name, *args):
        s = self.settings
        if name == 'page':
            self.flip(args[0])
            return
        if name == 'card':
            if self.on_open_unit is not None:
                self.on_open_unit(args[0])
            else:
                self.unit_menu().open(args[0])
                self.revision += 1
            return
        if name == 'buy':
            # 卡片上的 BUY（D35）：不进入单位菜单，直接打开购买确认（D32），确认窗口画在浏览大菜单之上。
            if self.on_buy is not None:
                self.on_buy(args[0])
            else:
                self.unit_menu().open_buy(args[0])
                self.revision += 1
            return
        if name == 'bar':
            which = args[0]
            if which == 'back':
                self.back(sound=False)
            elif which == 'favorites':
                s['favorites_only'] = not s['favorites_only']
                s['page'] = 0
                self.save_state()
            elif which == 'pack':
                if self.on_pack is not None:
                    self.on_pack()
                else:
                    self.enter_packs()
            elif which == 'deck':
                self.enter_deck()
            elif which == 'sort':
                self.panel = 'sort'
                self.search_focus = False
                self.panel_base = self.shaded(self.rendered)
            self.invalidate()
            return
        # SORT 面板
        if name == 'sort':
            s['sort'] = args[0]
        elif name == 'direction':
            s['descending'] = not s['descending']
        elif name == 'faction':
            factions = set(s['factions'])
            factions ^= {args[0]}
            if factions:
                s['factions'] = sorted(factions)
        elif name == 'source':
            sources = set(s['sources'])
            sources ^= {args[0]}
            if sources:
                s['sources'] = [x for x in SOURCES if x in sources]
        elif name == 'search':
            self.search_focus = True
        elif name == 'reset':
            keep = s['favorites_only']
            self.state[self.mode] = default_settings(self.mode)
            self.state[self.mode]['favorites_only'] = keep
        elif name == 'ok':
            self.panel = None
            self.panel_base = None
            self.search_focus = False
            self.save_state()
        if name not in ('search', 'ok'):
            self.settings['page'] = 0
        self.search_focus = name == 'search'
        self.invalidate()

    def text_input(self, character):
        if not (self.open and self.panel == 'sort' and self.search_focus):
            return
        s = self.settings
        if character == '\b':
            s['text'] = s['text'][:-1]
        elif character.isprintable() and len(s['text']) < 40:
            s['text'] += character
        s['page'] = 0
        self.invalidate()

    def wants_text(self):
        return self.open and self.panel == 'sort' and self.search_focus

    def native_page(self):
        """原生页面（组合包页面或编队页）显示中：本界面暂停绘制与输入，只受理该页的 BACK 等（pack_touch / deck_touch）。"""
        return self.packs_native or self.deck_native

    def wants_keys(self):
        return (self.open and not self.native_page()) or self.busy()

    def busy(self):
        """进入或离开的闸门动画进行中（期间不接受输入）。"""
        return self.shutter.state != 'open'

    def in_menu(self):
        return self.menu is not None and self.menu.active

    def locked(self):
        """过渡进行中（翻页平移除外）：不接受输入，与原生弹窗、面板的动作结束前不受理按压相同。"""
        return self.motion is not None and not self.motion.interruptible

    # ---------- 输入 ----------
    def touch(self, action, x, y):
        """页面打开时拦截全部触点（返回 True）。按下时登记命令，抬起于同一区域时执行。
        页面关闭时只处理主菜单“單位”面板的入口（entry_touch）；闸门动画期间吞掉全部触点。"""
        if self.busy():
            return True
        if not self.open:
            return self.entry_touch(action, x, y)
        if self.packs_native:
            return self.pack_touch(action, x, y)
        if self.deck_native:
            return self.deck_touch(action, x, y)
        if self.locked():
            return True
        if self.in_menu():
            return self.menu_touch(action, x, y)
        hit = rect = None
        for box, command in reversed(self.hitboxes):
            left, top, w, h = box
            if left <= x < left + w and top <= y < top + h:
                hit, rect = command, box
                break
        if action == 1:
            self.pressed, self.pressed_rect, self.pointer_inside = hit, rect, hit is not None
            if self.panel == 'sort' and hit is None:
                # 面板外点击：与 OK 相同，关闭面板
                self.pressed, self.pressed_rect = ('ok',), None
        elif action == 5:
            self.pointer_inside = self.pressed is not None and hit == self.pressed
        elif action == 3:
            pressed, self.pressed = self.pressed, None
            if pressed == ('ok',) and self.pressed_rect is None and hit is None:
                hit = pressed
            if hit is not None and hit == pressed and hit != ('panel',):
                play_se(self.p, SE_CLOSE if hit == ('bar', 'back') else SE_DECIDE)
                self.command(*hit)
        return True

    def key(self, name):
        """键盘：←/→ 翻页（单位菜单中为上一个 / 下一个单位）、↑/↓ 滚动 ACTION 说明条、Enter 确定（面板中关闭面板）、
        Backspace 删除搜索字。"""
        if not self.open or self.busy() or self.native_page() or self.locked():
            return
        if self.in_menu():
            if self.menu.panel is None and name in ('left', 'right'):
                play_se(self.p, SE_DECIDE)
                self.menu.command('nav', -1 if name == 'left' else 1)
            elif self.menu.panel == 'action' and name in ('up', 'down'):
                self.menu.scroll_desc(-1 if name == 'up' else 1)
            return
        if self.wants_text() and name == 'backspace':
            self.text_input('\b')
        elif self.panel == 'sort':
            if name == 'enter':
                play_se(self.p, SE_DECIDE)
                self.command('ok')
        elif name in ('left', 'right'):
            if self.flip(-1 if name == 'left' else 1):
                play_se(self.p, SE_DECIDE)

    def wheel(self, dy):
        if self.native_page() or self.locked():
            return
        if self.in_menu():
            if self.open and self.menu.panel is None and dy and not self.busy():
                play_se(self.p, SE_DECIDE)
                self.menu.command('nav', -1 if dy > 0 else 1)
            elif self.open and self.menu.panel == 'action' and dy and not self.busy():
                self.menu.scroll_desc(-1 if dy > 0 else 1)       # ACTION 说明条：滚轮向上为上一行
            return
        if self.open and self.panel is None and dy:
            if self.flip(-1 if dy > 0 else 1):
                play_se(self.p, SE_DECIDE)

    def back(self, sound=True):
        """Esc / BACK：单位菜单中逐层返回；面板打开时关闭面板；否则交给 on_back，未设置时经闸门离开本界面
        （由主菜单“單位”面板进入时回到 CUSTOMIZE 子页）。"""
        if self.busy() or self.locked():
            return True
        if not self.open:
            return False
        if self.packs_native:
            # 原生组合包页面：页面本身的 Esc 与 BACK 相同（回到本界面）；原生弹窗显示中交给原生（取消弹窗）。
            if self.pack_scene() in POPUP_SCENES:
                return False
            if self.pack_page_ready():
                play_se(self.p, SE_CLOSE)
                self.return_from_packs()
            return True
        if self.deck_native:
            # 原生编队页：Esc 与页面的 BACK 相同（回到本界面）；原生弹窗显示中交给原生。
            if self.pack_scene() in POPUP_SCENES:
                return False
            if self.deck_page_ready():
                play_se(self.p, SE_CLOSE)
                self.return_from_deck()
            return True
        if sound:
            play_se(self.p, SE_CLOSE)
        if self.in_menu():
            self.menu.back()
            self.revision += 1
            return True
        if self.panel is not None:
            self.command('ok')
            return True
        if self.on_back is not None and self.on_back():
            return True
        self.leave()
        return True

    # ---------- 入口与离开（U1b 强化、U1c 商店，闸门） ----------
    def entry_task(self):
        """当前主菜单子页的入口任务与模式：CUSTOMIZE 子页的“單位”面板（强化），SHOP 子页的 UNIT 卡（商店）。
        原生任务处于稳态（入场、离场动画期间不受理）时返回 (任务, 模式)，否则 None。VERSUS 页借用 SHOP 子页，显示期间不受理。"""
        p = self.p
        app = p.app_instance()
        if not app or p.word(app + 0x22bc) != SCENE_MAIN:
            return None
        spec = ENTRIES.get(p.word(app + 0x22dc))
        if spec is None:
            return None
        slot, function, mode = spec
        if mode == 'shop':
            page = getattr(p, 'versus_page', None)
            if page is not None and (page.state != 'closed' or getattr(page, 'lobby_return', None) == 'armed'):
                return None
        task = p.word(app + slot)
        symbol = f'_ZN7AppMain{len(function)}{function}EP17GENERAL_TASK_BASE'
        if not task or (p.word(task) & ~1) != (p.symbols[symbol] & ~1):
            return None
        return task, mode

    def entry_rect(self, task):
        """原生面板的点击区（任务 +0xf4..+0x100：相对位置的偏移与宽高，原生坐标）换算到画布。"""
        p = self.p
        f = lambda offset: struct.unpack('<f', p.read(task + offset, 4))[0]
        margin = struct.unpack('<i', p.read(p.app_instance() + 0x3c, 4))[0]
        x = (f(0x84) + f(0x9c) + f(0xf4) + margin) * NATIVE_TO_CANVAS
        y = (f(0x88) + f(0xa0) + f(0xf8)) * NATIVE_TO_CANVAS
        return (x, y, f(0xfc) * NATIVE_TO_CANVAS, f(0x100) * NATIVE_TO_CANVAS)

    def entry_allowed(self):
        lab = self.lab
        if lab is None or lab.active or lab.prep.open or lab.prep.busy():
            return False
        trial = getattr(self.p, 'event_trial', None)
        return not (trial is not None and trial.browser.active)

    def entry_touch(self, action, x, y):
        """主菜单“單位”面板 / SHOP 子页 UNIT 卡：按下与拖动交给原生（原生白光），在点击区内抬起时由宿主打开本界面，
        原生选择不触发。"""
        p = self.p
        if action == 1:
            self.entry_end()
            found = self.entry_task()
            if found is None or not self.entry_allowed():
                return False
            task, mode = found
            rect = self.entry_rect(task)
            if not (rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]):
                return False
            self.entry_pressed, self.entry_cancelled, self.entry_box = True, False, rect
            self.entry_mode = mode
            p.native_touch(action, x, y)
            return True
        if not self.entry_pressed:
            return False
        rect = self.entry_box
        inside_box = rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]
        if action == 5:
            if self.entry_cancelled or not inside_box:
                self.entry_cancelled = True
                p.native_touch(5, -1000, -1000)
                self.entry_clear()
            else:
                p.native_touch(5, x, y)
            return True
        if action == 3:
            found = self.entry_task()
            activate = not self.entry_cancelled and inside_box and found is not None and found[1] == self.entry_mode
            self.entry_end()
            if activate:
                if self.entry_mode == 'shop':
                    # 与原生 SelectPanelMainMenuShop 选 UNIT 卡相同：结束该卡的教学提示。
                    p.call('_ZN7AppMain15DelTutorialDataEi', p.app_instance(), TUTORIAL_SHOP_UNIT)
                else:
                    # 与原生进入单位强化场景（SC_CustomInit）相同：结束“強化”“單位”面板的 NEW 提示。
                    for bit in TUTORIAL_CUSTOM_UNIT:
                        p.call('_ZN7AppMain15DelTutorialDataEi', p.app_instance(), bit)
                self.enter(self.entry_mode)
            return True
        return True

    def entry_clear(self):
        found = self.entry_task()
        if found:
            self.p.call('_ZN7AppMain16ClearSelectPanelEP17GENERAL_TASK_BASEi', self.p.app_instance(), found[0], 0)

    def entry_end(self):
        if not self.entry_pressed:
            return
        try:
            self.p.native_touch(3, -1000, -1000)          # 框外释放：结束原生触点，原生选择不触发
        finally:
            try:
                self.entry_clear()
            finally:
                self.entry_pressed = self.entry_cancelled = False

    def enter(self, mode):
        """闸门合拢后打开本界面（目录索引在合拢期间建立），再开闸。记下主菜单子页（离开时回到该页）。"""
        play_se(self.p, SE_DECIDE)
        self.commands = []

        def reveal():
            began = time.perf_counter()
            self.set_open(True, mode)
            self.query()
            self.p.log('UNIT_BROWSER_ENTER', mode, round((time.perf_counter() - began) * 1000, 1))
            self.shutter.open()
        self.shutter.close(reveal)

    def leave(self):
        """闸门合拢后关闭本界面（单位动作演示随之释放），与原生 BACK（SelectCockpitFuncBack → 场景 27）相同：
        结束当前场景并进入主菜单初始化，SC_MainMenuLoop 按 app+0xb168 回到进入前的子页（CUSTOMIZE 为 3），
        由 SC_MainMenuInit 的 SetShutterOpen 开闸。宿主闸门的任务重置会清除子页背景任务，因此不直接开闸。"""
        def done():
            p = self.p
            app = p.app_instance()
            self.restore_catalog()
            self.set_open(False)
            page = getattr(self, 'return_page', 3)
            # SC_MainMenuLoop 状态 0 的返回子画面 app+0xb168：0 MENU、1 OPTION、3 CUSTOMIZE、4 SHOP（第 61 节）
            p.put(app + 0xb168, {1: 0, 2: 1, 3: 3, 4: 4}.get(page, 3))
            # 当前场景为主菜单（28）或去过组合包页面后的原生商店（39，SceneEndFunc 调用 SC_MenuShopEnd）。
            p.call('_ZN7AppMain12SceneEndFuncEi', app, p.word(app + 0x22bc))
            p.call('_ZN7AppMain11ChangeExeSTEi', app, 27)
            self.shutter.release()
            p.log('UNIT_BROWSER_LEAVE', p.frame)
        self.shutter.close(done)

    # ---------- 组合包（U1c，D33：购买界面沿用原版） ----------
    def enter_packs(self):
        """PACK：闸门合拢后进入原生单位商店（场景 38，模式 2 UNIT），原生商品目录在此期间只含可购买的组合包，
        组合包的卡片、售价与折扣、购买弹窗、音效与结算均为原生。页面上的 BACK / Esc 经闸门回到本界面（pack_touch）。"""
        packs = [e['shop_id'] for e in self.pack_available()]
        if not packs or self.packs_native:
            return

        def go():
            p = self.p
            app = p.app_instance()
            if self.menu is not None:
                self.menu.close()
            self.packs_native = True
            self.swap_catalog(packs)
            p.put(app + 0xb890, 2)                    # 商店模式 UNIT（SelectPanelMainMenuShop 选 UNIT 卡时写入）
            p.put(app + 0xb89c, 0)
            p.call('_ZN7AppMain12SceneEndFuncEi', app, p.word(app + 0x22bc))
            p.call('_ZN7AppMain11ChangeExeSTEi', app, SCENE_SHOP_INIT)   # SC_MenuShopInit 以 SetShutterOpen 开闸
            self.shutter.release()
            p.log('UNIT_BROWSER_PACKS_ENTER', packs, p.frame)
        self.shutter.close(go)

    def swap_catalog(self, shop_ids):
        """原生商品目录（社区头部 +44 指针、+48 项数；r47/r48 起原生建页、翻页与回溯均读此目录）暂改为组合包列表。"""
        from community_content import HEADER
        p = self.p
        if self.saved_catalog is None:
            self.saved_catalog = (p.word(HEADER + 44), p.word(HEADER + 48))
        self.pack_list = p.alloc(max(4, 4 * len(shop_ids)))
        p.write(self.pack_list, struct.pack('<%dI' % len(shop_ids), *shop_ids))
        p.put(HEADER + 44, self.pack_list)
        p.put(HEADER + 48, len(shop_ids))
        # 组合包页面中勋章不足只提示、不询问前往商店（D45；核心钩子 shop_short_ok，头部 +164）。
        if getattr(p.uc.lib, 'msd_community_shop_short_ok_version', None) is not None:
            p.put(HEADER + 164, 1)

    def restore_catalog(self):
        if self.saved_catalog is None:
            return
        from community_content import HEADER
        p = self.p
        p.put(HEADER + 44, self.saved_catalog[0])
        p.put(HEADER + 48, self.saved_catalog[1])
        if getattr(p.uc.lib, 'msd_community_shop_short_ok_version', None) is not None:
            p.put(HEADER + 164, 0)
        self.saved_catalog = None

    def pack_scene(self):
        app = self.p.app_instance()
        return self.p.word(app + 0x22bc) if app else 0

    def pack_page_ready(self):
        """原生组合包页面已开闸且无弹窗：场景 39，闸门任务槽为空，闭合标记已清除（SC_ShutterOpen 完成）。"""
        p = self.p
        app = p.app_instance()
        if self.pack_scene() != SCENE_SHOP:
            return False
        if any(p.word(app + 0x3820 + 4 * i) for i in range(4)):
            return False
        return p.read(app + 0xc21d, 1)[0] == 0

    def pack_touch(self, action, x, y):
        """原生组合包页面：底栏 BACK 由宿主受理（按下期间以 cockpit_hold 保持原生青色框与三灯，原生不选择），
        在按钮内抬起时经闸门回到本界面；其余触点交给原生（卡片、购买弹窗、FILTER 与其他底栏按钮）。"""
        from cockpit_hold import instance
        p = self.p
        app = p.app_instance()
        rect = (BAR_LEFT, BAR_Y, round(60 * BUTTON_SCALE), round(48 * BUTTON_SCALE))
        inside = rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]
        press = self.back_press
        if action == 1:
            self.release_back_press()
            if not inside or not self.pack_page_ready():
                return False
            task = p.word(app + COCKPIT_BACK)
            self.back_press = {'task': task, 'cancelled': False}
            instance(p).hold(task)
            return True
        if press is None:
            return False
        if action == 5:
            if not inside and not press['cancelled']:
                press['cancelled'] = True
                self.release_back_press(keep=True)
            return True
        if action == 3:
            activate = inside and not press['cancelled'] and self.pack_page_ready()
            self.release_back_press()
            if activate:
                play_se(p, SE_CLOSE)
                self.return_from_packs()
        return True

    def release_back_press(self, keep=False):
        press = self.back_press
        if press is None:
            return
        from cockpit_hold import instance
        task = press['task']
        app = self.p.app_instance()
        if task and app and self.p.word(app + press.get('slot', COCKPIT_BACK)) == task:
            instance(self.p).release(task)
        if not keep:
            self.back_press = None

    def return_from_packs(self):
        """闸门合拢后恢复商品目录并重新显示本界面（拥有状态与可购买组合包重新读取），再开闸。原生商店场景 39 留在
        本界面之下；离开本界面时由 leave 结束（SC_MenuShopEnd）并回到主菜单 SHOP 子页。"""
        self.release_back_press()

        def done():
            self.restore_catalog()
            self.packs_native = False
            self.refresh()
            self.shutter.open()
            self.p.log('UNIT_BROWSER_PACKS_RETURN', self.p.frame)
        self.shutter.close(done)

    def watch_packs(self):
        """原生组合包页面经其他底栏按钮离开（OPTION、SHOP、MEDAL、CUSTOMIZE）：恢复商品目录，本界面随之关闭
        （之后按原生流程显示）。勋章不足时只提示、不转往勋章商店（D45）。"""
        scene = self.pack_scene()
        if scene in (SCENE_SHOP_INIT, SCENE_SHOP) or scene in POPUP_SCENES or self.busy():
            return
        self.release_back_press()
        self.restore_catalog()
        self.packs_native = False
        self.set_open(False)
        self.p.log('UNIT_BROWSER_PACKS_LEFT', scene, self.p.frame)

    # ---------- 编队（D53：强化浏览大菜单的 DECK） ----------
    def enter_deck(self):
        """DECK：闸门合拢后进入原生编队页（场景 54，与主菜单 CUSTOMIZE 子页“牌組”面板相同的场景），本界面暂停绘制。
        编队页的 BACK、CUSTOMIZE 与 Esc 由宿主受理，经闸门回到本界面（deck_touch、return_from_deck）；其余底栏按钮
        （OPTION、SHOP、MEDAL）、SORT 与拖放编队均为原生，经 OPTION、SHOP、MEDAL 离开时本界面关闭（watch_deck）。"""
        if self.deck_native or self.mode != 'custom':
            return

        def go():
            p = self.p
            app = p.app_instance()
            if self.menu is not None:
                self.menu.close()
            self.deck_native = True
            # 编队页的原生 BACK（未经宿主受理时）经 SelectCockpitFuncBack 回到主菜单初始化（b16c 为 0），按 b168 回到 CUSTOMIZE 子页。
            p.put(app + 0xb16c, 0)
            p.put(app + 0xb168, 3)
            p.call('_ZN7AppMain12SceneEndFuncEi', app, p.word(app + 0x22bc))
            p.call('_ZN7AppMain11ChangeExeSTEi', app, SCENE_DECK_INIT)   # SC_DeckInit 以 SetShutterOpen 开闸
            self.shutter.release()
            p.log('UNIT_BROWSER_DECK_ENTER', p.frame)
        self.shutter.close(go)

    def deck_page_ready(self):
        """原生编队页已开闸且无弹窗：场景 55，闸门任务槽为空，闭合标记已清除。"""
        p = self.p
        app = p.app_instance()
        if self.pack_scene() != SCENE_DECK:
            return False
        if any(p.word(app + 0x3820 + 4 * i) for i in range(4)):
            return False
        return p.read(app + 0xc21d, 1)[0] == 0

    def deck_touch(self, action, x, y):
        """原生编队页：底栏 BACK 与 CUSTOMIZE 由宿主受理（按下期间以 cockpit_hold 保持原生青色框与三灯，原生不选择），
        在按钮内抬起时经闸门回到本界面；其余触点交给原生（编队、拖放、SORT 与其他底栏按钮）。"""
        from cockpit_hold import instance
        p = self.p
        app = p.app_instance()
        size = (round(60 * BUTTON_SCALE), round(48 * BUTTON_SCALE))
        # 编队页底栏 6 个按钮等距（BACK、OPTION、SHOP、MEDAL、CUSTOMIZE、SORT），与本界面底栏同一行、同样的两端位置。
        lefts = {COCKPIT_BACK: BAR_LEFT, COCKPIT_CUSTOMIZE: round(BAR_LEFT + (BAR_RIGHT - BAR_LEFT) * 4 / 5)}

        def inside(slot):
            left = lefts[slot]
            return left <= x < left + size[0] and BAR_Y <= y < BAR_Y + size[1]
        press = self.back_press
        if action == 1:
            self.release_back_press()
            slot = next((s for s in lefts if inside(s)), None)
            if slot is None or not self.deck_page_ready():
                return False
            task = p.word(app + slot)
            if not task:
                return False
            self.back_press = {'slot': slot, 'task': task, 'cancelled': False}
            instance(p).hold(task)
            return True
        if press is None:
            return False
        if action == 5:
            if not inside(press['slot']) and not press['cancelled']:
                press['cancelled'] = True
                self.release_back_press(keep=True)
            return True
        if action == 3:
            slot = press['slot']
            activate = inside(slot) and not press['cancelled'] and self.deck_page_ready()
            self.release_back_press()
            if activate:
                play_se(p, SE_CLOSE if slot == COCKPIT_BACK else SE_DECIDE)
                self.return_from_deck()
        return True

    def return_from_deck(self):
        """闸门合拢后结束编队页（SC_DeckEnd 释放编队页对象；编队在页内即时写入存档），在本界面之下重建主菜单
        （直接调用 SC_MainMenuInit，CUSTOMIZE 子页），重新读取拥有状态与等级后显示本界面，再开闸。
        SC_MainMenuInit 末尾的 SetShutterOpen 进入原生开闸状态（ChangeNT 18，由 SC_ShutterOpen 推进闸门任务），
        原生闸门会画在本界面之下；改为 ChangeNT 0（app+0x22c8），由本界面的闸门推进并画在本界面之上。"""
        self.release_back_press()

        def done():
            p = self.p
            app = p.app_instance()
            p.put(app + 0xb160, 27)                  # SC_DeckEnd 末尾的 ChangeST(b160)
            p.call('_ZN7AppMain12SceneEndFuncEi', app, p.word(app + 0x22bc))
            p.put(app + 0xb168, 3)
            p.put(app + 0xb16c, 0)
            p.call('_ZN7AppMain15SC_MainMenuInitEv', app)
            p.put(app + 0x22c8, 0)
            self.deck_native = False
            self.refresh()
            self.shutter.open()
            p.log('UNIT_BROWSER_DECK_RETURN', p.frame)
        self.shutter.close(done)

    def watch_deck(self):
        """原生编队页经 OPTION、SHOP、MEDAL 离开（或原生 BACK 未经宿主受理）：本界面关闭，之后按原生流程显示。"""
        scene = self.pack_scene()
        if scene in (SCENE_DECK_INIT, SCENE_DECK, SCENE_DECK_END) or scene in POPUP_SCENES or self.busy():
            return
        self.release_back_press()
        self.deck_native = False
        self.set_open(False)
        self.p.log('UNIT_BROWSER_DECK_LEFT', scene, self.p.frame)

    def menu_touch(self, action, x, y):
        """单位菜单：按下登记，在同一区域抬起时执行；模态面板外的点击视为取消（与原生弹窗相同）。"""
        menu = self.menu
        hit = rect = None
        for box, command in reversed(self.hitboxes):
            left, top, w, h = box
            if left <= x < left + w and top <= y < top + h:
                hit, rect = command, box
                break
        if menu.desc_drag is not None:
            # ACTION 说明条滚动：按下后的移动与抬起交给单位菜单，不触发其他命令
            if action == 5:
                menu.desc_move(y)
            elif action == 3:
                menu.desc_release()
            return True
        if action == 1 and hit is not None and hit[0] in ('desc_bar', 'desc_text'):
            self.pressed = None
            menu.desc_press(hit[0], y)
            return True
        if action == 1:
            if menu.panel is not None and hit is None:
                hit, rect = ('outside',), None
            self.pressed, self.pressed_rect = hit, rect
            self.pointer_inside = hit is not None and rect is not None
        elif action == 5:
            self.pointer_inside = self.pressed is not None and hit == self.pressed
        elif action == 3:
            pressed, self.pressed = self.pressed, None
            if pressed == ('outside',) and hit is None:
                play_se(self.p, SE_CLOSE)
                menu.outside()
                self.revision += 1
            elif hit is not None and hit == pressed and hit != ('panel',):
                if hit == ('bar', 'back'):
                    self.back()
                    return True
                if hit[0] not in ('lv_up', 'lv_na', 'confirm_ok', 'buy_ok') and hit != ('limit_pay', 'msp'):
                    play_se(self.p, SE_DECIDE)      # 强化、开放阶段交易与购买的音效由结果决定（附录 A.10）
                menu.command(*hit)
                self.revision += 1
        return True

    # ---------- 帧 ----------
    def process_commands(self):
        while self.commands:
            item = self.commands.pop(0)
            if item[0] == 'text':
                self.text_input(item[1])
            elif item[0] == 'key':
                self.key(item[1])
            elif item[0] == 'wheel':
                self.wheel(item[1])

    def draw(self):
        if self.open and self.packs_native:
            self.watch_packs()
        elif self.open and self.deck_native:
            self.watch_deck()
        elif self.open:
            self.draw_page()
            if self.in_menu() and not self.motion_drawn:  # 过渡的各帧（含最后一帧）不演示，下一帧开始
                self.menu.draw_live()
        self.shutter.update_and_draw()

    def draw_page(self):
        self.process_commands()
        self.query()
        if self.overlay is None:
            from trial_overlay import SurfaceOverlay
            self.overlay = SurfaceOverlay(self.p.graphics)
        if self.gl is None:
            from unit_motion import Layers
            self.gl = Layers(self.p.graphics)
        caret = (self.p.frame // 15) % 2 if self.wants_text() else 0
        key = ('unit_browser', self.revision, self.language(), caret)
        image = None
        if self.overlay.cached != key:
            previous_items = self.layers.get('grid', {}).get('cards')
            image = self.compose()
            self.rendered, self.rendered_key = image, key
            state = self.view_state()
            if self.shown_state is not None and state != self.shown_state:
                self.start_motion(self.shown_state, state, previous_items)
            self.shown_state = state
            self.slide_dir = 0
            self.timings.append({'frame': self.p.frame, 'query_ms': round(getattr(self, 'last_query_ms', 0), 2),
                                 'compose_ms': round(self.last_compose_ms, 2), 'page': self.settings['page'],
                                 'total': self.total})
            del self.timings[:-200]
            self.schedule_prefetch()
        began = time.perf_counter()
        self.overlay.draw_image(image, key, (0, 0, W, H))
        if image is not None:
            self.timings[-1]['upload_ms'] = round((time.perf_counter() - began) * 1000, 2)
        self.motion_drawn = self.motion is not None
        if self.motion is not None:
            if self.motion.draw(self.gl):
                self.motion = None
        else:
            self.draw_press()
        if image is None and self.motion is None:
            self.run_prefetch()
            self.preload_layers()

    def repaint(self):
        """以已上传的界面图像重画整个画面（不重新合成或上传），再画按下反馈；供动作演示测量后覆盖测量区域。"""
        if self.overlay is not None and self.overlay.cached is not None:
            self.overlay.draw_image(None, self.overlay.cached, (0, 0, W, H))
            self.draw_press(advance=False)

    # ---------- 过渡（D52） ----------
    def view_state(self):
        """画面状态：(底层 'grid' / 'menu', 弹窗, 浏览大菜单页码)。卡片 BUY 的购买确认画在浏览大菜单之上。"""
        if self.in_menu():
            menu = self.menu
            return ('grid' if menu.standalone else 'menu', menu.panel, None)
        return ('grid', 'sort' if self.panel == 'sort' else None, self.settings['page'])

    def popup_rect(self, panel):
        return SORT_PANEL if panel == 'sort' else self.unit_menu().panel_rect(panel)

    def popup_frame(self, panel):
        """空窗口（开合期间只显示窗口框与底色，与原生相同）。"""
        from PIL import Image
        x, y, w, h = self.popup_rect(panel)
        img = Image.new('RGBA', (w, h))
        if panel == 'sort':
            img.alpha_composite(Image.new('RGBA', (w, h), (0, 0, 0, 110)))
        img.alpha_composite(self.art.slice(POPUP, w, h, (6, 6, 6, 6), 2))
        return img

    def panel_rects(self, kind):
        """列表面板进出时逐个移动的区域：浏览大菜单为三行卡片，单位菜单为左侧面板、画框与说明条。"""
        if kind == 'menu':
            return self.unit_menu().motion_rects()
        rows = [(LEFT - 4, TOP + r * (CARD_H + GAP_Y) - 4, RIGHT - LEFT + 8, CARD_H + 8) for r in range(ROWS)]
        return rows + list(getattr(self, 'nav_rects', []))

    def stamp(self):
        self.layer_serial += 1
        return self.layer_serial

    def preload_layers(self):
        """空闲帧：把当前画面的分层（底层、面板层、整页）预先上传为纹理（每帧至多一张），过渡开始时只需上传新画面。"""
        if self.gl is None or self.shown_state is None:
            return
        base = self.shown_state[0]
        layers = self.layers.get(base)
        if not layers:
            return
        for part in ('chrome', 'items', 'page'):
            name, key = ('base', base, part), ('base', layers['serial'], part)
            if self.gl.cached(name) != key:
                self.gl.upload(name, layers[part], key)
                return

    def popup_frame_cached(self, panel):
        rect = self.popup_rect(panel)
        cached = self.frames.get(panel)
        if cached is None or cached[0] != rect:
            cached = self.frames[panel] = (rect, self.popup_frame(panel))
        return cached[1]

    def start_motion(self, old, new, previous_items):
        """按画面状态的变化选择过渡：翻页平移；弹窗开合（换窗口时先关后开）；浏览大菜单与单位菜单之间先离开后进入。
        画面分层与弹窗空框的纹理按名称与键共用（空闲帧已预先上传的不再上传）。"""
        from PIL import Image
        ob, op, opage = old
        nb, np_, npage = new
        if self.black is None:
            self.black = Image.new('RGBA', (4, 4), (0, 0, 0, 255))
        images, keys = {'black': self.black}, {'black': ('black',)}

        def layer(base, part):
            name = ('base', base, part)
            images[name] = self.layers[base][part]
            keys[name] = ('base', self.layers[base]['serial'], part)
            return name

        def frame(panel):
            name = ('frame', panel)
            images[name] = self.popup_frame_cached(panel)
            keys[name] = ('frame', panel, self.popup_rect(panel))
            return name

        frames, interruptible = [], False
        if ob == nb and op == np_:
            if nb == 'grid' and op is None and opage != npage and self.slide_dir and previous_items is not None:
                grid = self.layers['grid']
                x, y, w, h = CARD_CLIP
                box = (x, y, x + w, y + h)                  # 只上传卡片区（平移只画在这一块之内）
                images.update(chrome=grid['chrome'].crop(box), nav=grid['nav'].crop(box),
                              old=previous_items.crop(box), new=grid['cards'].crop(box))
                frames = slide('chrome', 'old', 'new', CARD_CLIP, self.slide_dir, top='nav')
                interruptible = True
        else:
            if op is not None:
                frames += popup_close(self.popup_rect(op), layer(ob, 'page'), frame(op))
            if ob != nb:
                frames += panels_out(layer(ob, 'chrome'), layer(ob, 'items'), self.panel_rects(ob))
                frames += panels_in(layer(nb, 'chrome'), layer(nb, 'items'), self.panel_rects(nb))
            if np_ is not None:
                frames += popup_open(self.popup_rect(np_), layer(nb, 'page'), frame(np_), op is None or ob != nb)
        self.lights.clear()
        self.motion = Motion((old, new), images, frames, interruptible, keys) if frames else None
        if self.motion is not None:
            self.p.log('UNIT_BROWSER_MOTION', old, new, len(frames))

    def schedule_prefetch(self):
        """相邻两页的卡片在之后的空闲帧逐张生成（每帧至多一张），使翻页时卡片已在缓存中。"""
        self.prefetch = []
        if self.pages <= 1 or self.panel is not None:
            return
        page = self.settings['page']
        for delta in (1, -1):
            other = (page + delta) % self.pages
            self.prefetch += self.all_items[other * PAGE_SIZE:(other + 1) * PAGE_SIZE]

    def run_prefetch(self):
        """空闲帧：先生成相邻页卡片（每帧一张），再预算数值类排序所需的等级数值（每帧至多 STAT_WARM_PER_FRAME 个），
        使排序与攻击筛选在首次使用时不需要一次计算全部单位。"""
        budget = 3 if self.panel is not None else 1     # 面板打开期间画面不变，每帧可多生成几张
        while self.prefetch and budget:
            entry = self.prefetch.pop(0)
            if self.card_key(entry) not in self.cards:
                self.card_image(entry)
                budget -= 1
        if self.prefetch or budget == 0:
            return
        if self.panel is not None:
            return
        catalog = self.catalog()
        if self.stat_queue is None:
            level = (lambda e: e['level'] or 1) if self.mode == 'custom' else (lambda e: 1)
            self.stat_queue = [(e['uid'], level(e)) for e in self.all_items]
        done = 0
        while self.stat_queue and done < STAT_WARM_PER_FRAME:
            uid, level = self.stat_queue.pop()
            if (uid, level) not in catalog.details:
                catalog.stats(uid, level)
                done += 1

    def draw_press(self, advance=True):
        """按下反馈：底栏为原生青色框与三灯（按住时显示）；其余按钮与卡片为按下白光（Lights，每帧推进一次）。"""
        if self.rendered is None:
            return
        command = self.pressed
        if command is not None and command[0] == 'bar' and self.pointer_inside and self.pressed_rect is not None:
            if self.press_overlay is None:
                from trial_overlay import SurfaceOverlay
                self.press_overlay = SurfaceOverlay(self.p.graphics)
            press_key = ('unit_browser_press', self.rendered_key, command)
            part, rect = None, getattr(self, 'press_rect', None)
            if self.press_overlay.cached != press_key:
                part, rect = self.cockpit_press(command)
                self.press_rect = rect
            self.press_overlay.draw_image(part, press_key, rect)
        if advance:
            lit = command if command is not None and command[0] not in LIGHT_NONE else None
            self.lights.update(lit, self.pressed_rect, self.pointer_inside, lit is not None and lit[0] in LIGHT_INSTANT)
        names = set()
        for command, (value, rect, _) in self.lights.values.items():
            if value <= 0:
                continue
            name = ('light', command)
            names.add(name)
            key = (self.rendered_key, command)
            lit = self.light_image(command, rect)
            if lit is None:
                continue
            image, dst = lit
            self.gl.draw(name, image, key, dst, alpha=value / 255)
        self.gl.drop(lambda name: isinstance(name, tuple) and name[0] == 'light' and name not in names)

    def cockpit_press(self, command):
        """底栏按下：原生青色框与三灯（GT_CockpitButtonDraw）。"""
        x, y, w, h = self.pressed_rect
        k = BUTTON_SCALE
        (frame, (fx, fy)), (lamps, (lx, ly)) = PRESS_FRAME, PRESS_LAMPS
        left, top = x - round(fx * k), y - round(fy * k)
        fw, fh = round(frame[1][2] * k), round(frame[1][3] * k)
        out = self.rendered.crop((left, top, left + fw, top + fh)).copy()
        out.alpha_composite(scaled(self.art.part(frame), k), (0, 0))
        out.alpha_composite(scaled(self.bar_button(command[1]), k), (x - left, y - top))
        out.alpha_composite(scaled(self.art.part(lamps), k), (x - round(lx * k) - left, y - round(ly * k) - top))
        return out, (left, top, fw, fh)

    def light_image(self, command, rect):
        """按下白光的亮版与其画布矩形：卡片为底板亮版的卡片（Art.card_base），原生按钮为同一图块的亮版（LIGHT_PARTS，
        按颜色对照替换画面中的按钮底色，文字不变），图标类按钮（icon_lights）为图标本身提亮；其余不显示。"""
        key = (self.rendered_key, command)
        cached = self.lit_cache.get(key)
        if cached is not None:
            return cached
        x, y, w, h = rect
        kind = command[0]
        entry = next((e for e in self.page_items if e['key'] == command[1]), None) if kind == 'card' else None
        if entry is not None:
            lit = (self.card_image(entry, lit=True), rect)
        elif kind in LIGHT_PARTS:
            lit = (relight(self.rendered.crop((x, y, x + w, y + h)), self.art.color_map(*LIGHT_PARTS[kind])), rect)
        elif command in self.icon_lights:
            icon, (ix, iy) = self.icon_lights[command]
            lit = (lighten(icon), (ix, iy, icon.width, icon.height))
        else:
            lit = None
        if len(self.lit_cache) > 16:
            self.lit_cache.pop(next(iter(self.lit_cache)))
        self.lit_cache[key] = lit
        return lit

    def close(self):
        self.save_state() if self.open else None
        for overlay in (self.overlay, self.press_overlay, self.gl):
            if overlay is not None:
                overlay.close()
        self.overlay = self.press_overlay = self.gl = None
