"""Fall Climber 的素材提取与骨架几何（2026-11-01，AGENTS 第 313 节 R3 起；build_fall_climber.py 使用）。

- 素材：原作精灵表 F:\\egg\\MS7\\DS _ DSi - Metal Slug 7 - Enemies - Fall Climber.png（The Spriters Resource 27276；Gussprint 拆图，
  大激光 esreveR；须注明来源）。背景色（白、粉格子、亮绿、暗绿）转透明后按 8 邻接连通块切出部件，编号按（y // 20, x）排序，与离线示意
  verification/ms7_m4_units_20261031/fc_sheet_cut.py 的编号相同；由多个碎块组成的效果帧按格子整块裁切。
- 拼合：用户提供的整机图 F:\\egg\\MS7\\Fallmecha.webp（素材 1:1，第一形态）逐部件模板匹配的结果（离线示意 fc_fallmecha_match.py，
  docs/MS7_M4_UNITS_2026-10-31.md 第 18.11 节），坐标为部件外接框左上角相对头壳顶中点（素材像素，y 向下）。第二形态的破损部件按与
  完好部件透明区域交并比最大的偏移对齐后套用同一拼合（同示意第 12 版）。
- 游戏中的静止姿势：头部露出行走线 PEEK（第二形态机体再抬高 RISE），两手底边落在行走线、中心距身体 ±HAND_X；肩（上臂齿盘中心）
  随机体，肘以两段反向运动学求出（上臂长、前臂长取整机图中的长度，肘取整机图的弯向）。上臂与“肘护盖 + 前臂”两块按此姿势预先转好，
  核心运行时只写相对此姿势的转角。
坐标约定：本文件中“原点”为单位位置（身体中心、行走线上），原画朝左（image_direction 270，左手 = 前方的手）。"""
import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

SHEET = Path(r'F:\egg\MS7\DS _ DSi - Metal Slug 7 - Enemies - Fall Climber.png')
BG = [(255, 255, 255), (255, 204, 204), (0, 248, 0), (0, 128, 0)]
CREDITS_Y = 3720

_a = np.asarray(Image.open(SHEET).convert('RGB'))
_fg = np.ones(_a.shape[:2], bool)
for _c in BG:
    _fg &= ~np.all(_a == np.array(_c), axis=2)
_rgba = np.dstack([_a, (_fg * 255).astype(np.uint8)])
_lab, _ = ndimage.label(_fg[:CREDITS_Y], structure=np.ones((3, 3)))
_objs = ndimage.find_objects(_lab)
_order = sorted([i for i, sl in enumerate(_objs) if int((_lab[sl] == i + 1).sum()) >= 40],
                key=lambda i: (_objs[i][0].start // 20, _objs[i][1].start))


def part(k, rect=False):
    """编号 k 的部件（只取该连通块）；rect=True 时按外接框整块裁（含框内其他块）。"""
    i = _order[k]
    sl = _objs[i]
    img = _rgba[sl].copy()
    if not rect:
        img[..., 3] = np.where(_lab[sl] == i + 1, img[..., 3], 0)
    return Image.fromarray(img, 'RGBA')


def cell(x, y, w, h):
    return Image.fromarray(_rgba[y:y + h, x:x + w].copy(), 'RGBA')


def mirror(img):
    return img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)


# ---------- 整机图的拼合（素材像素，相对头壳顶中点；part 为编号，flip 镜像，angle 为 PIL 逆时针转角） ----------
REF = {
    'upper_L': (97, False, 120, (-126.0, 26), (98, 79)), 'upper_R': (97, True, 240, (28.0, 26), (98, 79)),
    'cap_L': (101, False, 60, (-146.0, 58), (54, 47)), 'cap_R': (101, True, 300, (92.0, 58), (54, 47)),
    'fore_L': (102, False, 0, (-152.0, -2), (40, 76)), 'fore_R': (102, True, 0, (112.0, -2), (40, 76)),
    'hip_L': (110, True, 0, (-62.0, 96), (40, 42)), 'hip_R': (110, False, 0, (22.0, 96), (40, 42)),
    'claw_L': (112, False, 0, (-69.0, 105), (54, 57)), 'claw_R': (112, True, 0, (15.0, 105), (54, 57)),
    'body': (0, False, 0, (-72.0, 20), (144, 94)), 'engine': (56, False, 0, (-30.0, 34), (60, 80)),
    'gun_L': (5, False, 0, (-56.0, 31), (32, 32)), 'gun_R': (20, False, 0, (24.0, 31), (32, 32)),
    'head': (3, False, 0, (-51.0, 0), (102, 39)),
    'hand_L': (104, False, 0, (-159.0, -23), (73, 54)), 'hand_R': (104, True, 0, (86.0, -23), (73, 54)),
}
DAMAGED = {0: 1, 97: 98, 101: 108, 102: 103, 104: 105, 110: 111, 112: 113}
GEAR, ARM_END = (18.5, 68.8), (18.5, 4.0)          # #97 内：齿盘中心（肩）与另一端（肘）
PEEK, RISE, HAND_X = 20, 16, 122.5
WRIST_DY = 2                                       # 腕点：前臂上端以下 2 像素（前臂伸入手筒，整机图中前臂画在手之前；R7）
STEAM_AT = {'L': (-56, 61), 'R': (8, 47)}          # 引擎蒸汽格左上角（相对头壳顶中点），左侧为表内第一行、右侧第二行
CORE_AT = (-32, 12)                                # 玻璃罩格（64×32）左上角
CORE_ANCHOR = (0, 37)                              # 蓄力光球与激光帧底部半球对齐的点（玻璃罩底边中点）
MUZZLE = {'L': (-35.5, 34.5), 'R': (35.5, 34.5)}   # 炮口（第 10 帧炮管顶上方 1.5，示意第 14 版）
_ST1 = [(3, 51), (53, 101), (103, 151), (153, 201), (203, 251), (253, 301), (303, 351), (353, 401), (403, 435), (437, 485)]
_ST2 = [(3, 51), (53, 101), (103, 151), (153, 185), (187, 235), (237, 285), (287, 335), (337, 385), (387, 435), (437, 485)]


def align(base, img, r=12):
    """img 相对 base（均不镜像）的偏移：透明区域交并比最大。"""
    a = np.asarray(base)[..., 3] > 0
    b = np.asarray(img)[..., 3] > 0
    H, W = a.shape[0] + 2 * r + b.shape[0], a.shape[1] + 2 * r + b.shape[1]
    best = None
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            ca = np.zeros((H, W), bool)
            cb = np.zeros((H, W), bool)
            ca[r + 12:r + 12 + a.shape[0], r + 12:r + 12 + a.shape[1]] = a
            cb[r + 12 + dy:r + 12 + dy + b.shape[0], r + 12 + dx:r + 12 + dx + b.shape[1]] = b
            iou = (ca & cb).sum() / max(1, (ca | cb).sum())
            if best is None or iou > best[0]:
                best = (iou, dx, dy)
    return best[1], best[2]


def rot_point(p, size, size2, ang):
    """PIL rotate(ang, expand=True)（屏幕上逆时针）下点 p 的新坐标。"""
    th = math.radians(ang)
    dx, dy = p[0] - size[0] / 2, p[1] - size[1] / 2
    return (size2[0] / 2 + math.cos(th) * dx + math.sin(th) * dy, size2[1] / 2 - math.sin(th) * dx + math.cos(th) * dy)


def posed(name, form, pivots=(), extra=0.0):
    """按整机图摆放部件（第二形态用破损部件并对齐），再顺时针多转 extra 度（屏幕坐标）。
    返回 (图, 左上角相对头壳顶中点, {枢点名: 相对头壳顶中点})。"""
    k_int, flip, ang, rel, _ = REF[name]
    k_use = k_int if form == 1 else DAMAGED.get(k_int, k_int)
    base = part(k_int)
    dx, dy = (0, 0) if k_use == k_int else align(base, part(k_use))
    pad = 16
    cw, ch = base.width + 2 * pad, base.height + 2 * pad
    canvas = Image.new('RGBA', (cw, ch))
    canvas.alpha_composite(part(k_use), (pad + dx, pad + dy))
    pts = {n: (p[0] + pad, p[1] + pad) for n, p in pivots}
    ref_pts = dict(pts)
    if flip:
        canvas = mirror(canvas)
        pts = {n: (cw - p[0], p[1]) for n, p in pts.items()}
        ref_pts = dict(pts)
    # 整机图中的外接框：完好部件按整机图的转角旋转后的尺寸
    rb = base.rotate(ang, expand=True) if ang else base
    r0 = canvas.rotate(ang, expand=True, resample=Image.NEAREST) if ang else canvas
    off0 = ((r0.width - rb.width) / 2, (r0.height - rb.height) / 2) if ang else (pad, pad)
    tl0 = (rel[0] - off0[0], rel[1] - off0[1])                          # r0 的左上角
    pts0 = {n: rot_point(p, canvas.size, r0.size, ang) if ang else p for n, p in ref_pts.items()}
    piv = {n: (tl0[0] + p[0], tl0[1] + p[1]) for n, p in pts0.items()}   # 整机图中的枢点（相对头壳顶中点）
    if extra:
        a2 = ang - extra
        r = canvas.rotate(a2, expand=True, resample=Image.NEAREST)
        pts2 = {n: rot_point(p, canvas.size, r.size, a2) for n, p in ref_pts.items()}
        # 以第一个枢点为不动点放置
        n0 = pivots[0][0]
        tl = (piv[n0][0] - pts2[n0][0], piv[n0][1] - pts2[n0][1])
        canvas, pts_now = r, pts2
    else:
        canvas, pts_now, tl = r0, pts0, tl0
    bb = canvas.getchannel('A').getbbox()
    canvas = canvas.crop(bb)
    tl = (tl[0] + bb[0], tl[1] + bb[1])
    return canvas, tl, {n: (tl[0] + p[0] - bb[0], tl[1] + p[1] - bb[1]) for n, p in pts_now.items()}


def ang(v):
    return math.degrees(math.atan2(v[1], v[0]))


def ik(S, H, L1, L2, sign0):
    dx, dy = H[0] - S[0], H[1] - S[1]
    d0 = math.hypot(dx, dy)
    d = min(max(d0, abs(L1 - L2) + 1e-3), L1 + L2 - 1e-3)
    a = (L1 * L1 - L2 * L2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, L1 * L1 - a * a))
    ux, uy = dx / d0, dy / d0
    px, py = S[0] + a * ux, S[1] + a * uy
    for e in ((px - h * uy, py + h * ux), (px + h * uy, py - h * ux)):
        if np.sign(dx * (e[1] - S[1]) - dy * (e[0] - S[0])) == sign0:
            return e
    return (px - h * uy, py + h * ux)


def _turn(img, tl, pivot, deg):
    """图（左上角 tl）绕 pivot 顺时针转 deg 度（屏幕坐标，最近邻）；返回 (图, 左上角)。"""
    pad = int(math.hypot(*img.size)) + 4
    big = Image.new('RGBA', (pad * 2, pad * 2))
    big.alpha_composite(img, (int(round(pad - (pivot[0] - tl[0]))), int(round(pad - (pivot[1] - tl[1])))))
    r = big.rotate(-deg, resample=Image.NEAREST, center=(pad, pad))
    bb = r.getchannel('A').getbbox()
    return r.crop(bb), (pivot[0] - (pad - bb[0]), pivot[1] - (pad - bb[1]))


def arm_rest(form, side):
    """一侧手臂在游戏中静止姿势的几何（相对原点）与预先转好的图（R7 起四块）。
    链：肩 S（上臂齿盘）—上臂—肘 E（上臂另一端）—前臂—腕 W（前臂上端中点，固定在手上：相对手底中点为 WH）；两段反向运动学以 W 为目标。
    上臂绕 S 转，前臂绕 E 转（上端落在 W），肘护盖绕 E 转上臂与前臂转角的平均（关节两侧各弯一半）；手不转。
    返回 dict：S、E、H（手底中点）、W、WH、L1（S–E）、L2（E–W）、sign（肘的弯向）、upper / cap / fore / hand（图, 左上角）。"""
    peek = PEEK + (RISE if form == 2 else 0)
    up0, up_tl0, up_p0 = posed(f'upper_{side}', form, (('S', GEAR), ('E', ARM_END)))
    S0, E0 = up_p0['S'], up_p0['E']
    fo0, fo_tl0, _ = posed(f'fore_{side}', form)
    cap0, cap_tl0, _ = posed(f'cap_{side}', form)
    hk, hflip, _, hrel, hsize = REF[f'hand_{side}']
    H0 = (hrel[0] + hsize[0] / 2, hrel[1] + hsize[1])
    W0 = (fo_tl0[0] + fo0.width / 2, fo_tl0[1] + WRIST_DY)
    WH = (W0[0] - H0[0], W0[1] - H0[1])
    L1, L2 = math.dist(S0, E0), math.dist(E0, W0)
    sign0 = np.sign((W0[0] - S0[0]) * (E0[1] - S0[1]) - (W0[1] - S0[1]) * (E0[0] - S0[0]))
    H = (-HAND_X if side == 'L' else HAND_X, peek)                       # 相对头壳顶中点：手底在行走线
    W = (H[0] + WH[0], H[1] + WH[1])
    E = ik(S0, W, L1, L2, sign0)
    d_up = ang((E[0] - S0[0], E[1] - S0[1])) - ang((E0[0] - S0[0], E0[1] - S0[1]))
    d_low = ang((W[0] - E[0], W[1] - E[1])) - ang((W0[0] - E0[0], W0[1] - E0[1]))
    d_up, d_low = (d_up + 180) % 360 - 180, (d_low + 180) % 360 - 180
    up, up_tl, up_p = posed(f'upper_{side}', form, (('S', GEAR), ('E', ARM_END)), extra=d_up)
    fo, fo_tl = _turn(fo0, fo_tl0, E0, d_low)
    cap, cap_tl = _turn(cap0, cap_tl0, E0, (d_up + d_low) / 2)
    move = (E[0] - E0[0], E[1] - E0[1])                                  # 肘由整机图位置移到静止姿势
    fo_tl, cap_tl = (fo_tl[0] + move[0], fo_tl[1] + move[1]), (cap_tl[0] + move[0], cap_tl[1] + move[1])
    hand = part(hk if form == 1 else DAMAGED[hk])
    if hflip:
        hand = mirror(hand)
    hand_tl = (H[0] - hand.width / 2, H[1] - hand.height)
    o = (0.0, -float(peek))                                              # 头壳顶中点相对原点
    sh = lambda p: (p[0] + o[0], p[1] + o[1])                           # noqa: E731
    return {'S': sh(up_p['S']), 'E': sh(E), 'H': sh(H), 'W': sh(W), 'WH': WH, 'L1': L1, 'L2': L2, 'sign': int(sign0),
            'upper': (up, sh(up_tl)), 'cap': (cap, sh(cap_tl)), 'fore': (fo, sh(fo_tl)), 'hand': (hand, sh(hand_tl)),
            'd_up': d_up, 'd_low': d_low}


def body_parts(form):
    """机体组的部件（相对原点的左上角）：[(名称, 图, 左上角)]，按由后到前的次序。"""
    peek = PEEK + (RISE if form == 2 else 0)
    out = []
    for name in ('hip_L', 'hip_R', 'claw_L', 'claw_R', 'body', 'engine'):
        img, tl, _ = posed(name, form)
        out.append((name, img, (tl[0], tl[1] - peek)))
    return out
