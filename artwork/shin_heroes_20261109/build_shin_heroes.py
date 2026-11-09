"""“真”主角四人组 s1xlv.shin_marco / shin_tarma / shin_eri / shin_fio（2026-11-09）。
设计与核对见 verification/shin_heroes_20261109/summary.md；示意动画 R1 经用户确认后开工。

来源：
- 原生描述符与脚本（source/native_units.json，verification/ms7_rwalker_20261106/runs/shin_units_* 的导出）；原生图集第 0 页起原样引用。
- 用户素材表 F:\\egg\\MSFIX（Marco / Tarma / Eri / Fio 表与 MS2/X Weapon SFX 表）：持枪上半身 + 腿部的拼合帧（compose.py）、Big 弹体（sfx.py / preview.py 的 Big）。
做法：
- 原生矩形 / 帧表原样在前（未改写的脚本仍指向原生帧），新矩形、新帧追加在后；Eri 的 Big 激光帧按原生帧 246–320 的编排顺序追加，核心加偏移（big_weapon）。
- 中立 / 前进 / 近战换持枪帧；编队页（槽 0）为持武器待机（source/deck_<名>.npz，verification/shin_heroes_20261109/deck_idle/）；普通攻击 = 原版大招（去掉武器语音与收尾丢枪）；特殊攻击 = 同一动作，弹体换 Big 并保留语音；胜利（脚本 11）、购买后（脚本 2）、击退、死亡保持原版。
- 普通攻击组（状态字 22–28）取原版大招组（29–34、37）的数值；特殊攻击伤害 × 3/2。
- 头像：待机第 0 帧按外框裁出，单位原点放在格内 (23, 44)（同 CLARK / RALF 等原生头像），右侧超出格 50 的枪口裁去。
运行：E:\\anaconda3\\python.exe -I artwork/shin_heroes_20261109/build_shin_heroes.py [--preview]
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

_PVZ = REPO / 'artwork' / 'pvz_zombies_20261012' / 'build_pvz_zombies.py'
_src = _PVZ.read_text(encoding='utf-8')
_src = _src.replace("sys.path.insert(0, str(RT / 'packages'))", "").replace("os.add_dll_directory(str(RT / 'native'))", "")
pvz = type(sys)('pvzb')
pvz.__dict__['__file__'] = str(_PVZ)
exec(compile(_src, str(_PVZ), 'exec'), pvz.__dict__)
indexed_obm, save_json, shelf_pack = pvz.indexed_obm, pvz.save_json, pvz.shelf_pack

VERIFY = REPO / 'verification' / 'shin_heroes_20261109'
sys.path.insert(0, str(VERIFY))
import preview as PV  # noqa: E402

CONTENT = REPO / 'community_content'
OUT = HERE / 'out'
SOURCE = HERE / 'source'
NATIVE = json.loads((SOURCE / 'native_units.json').read_text(encoding='utf-8'))
TEXTS = json.loads((SOURCE / 'native_texts.json').read_text(encoding='utf-8'))
ORIGIN = 128   # compose.BOX 画布中的单位原点
# 原生头像格内的单位原点：男性同 CLARK / RALF。女性以持相同造型武器的 TYRA 为参照（用户）：左缘与脚底线对齐 TYRA（左缘 13、脚底 45）；
# 两人的枪比 TYRA 长 5 像素，原点取 (23, 44) 时枪身完整，右缘 52 等于原生头像的最大右缘
ICON_ORIGIN = {'marco': (23, 44), 'tarma': (23, 44), 'eri': (23, 44), 'fio': (23, 44)}
ICON_RIGHT = {'marco': 50, 'tarma': 50, 'eri': 52, 'fio': 52}
ICON_ANCHOR_BASE = (5, 3)


# 编队页（槽 0）的持武器待机：帧取 source/deck_<名>.npz，(帧序号, 停留 tick)，循环播放（用户确认的示意第 2 行）
_DECK_WIPE = [(0, 3), (1, 3), (2, 3), (3, 4), (4, 8), (5, 3), (6, 5), (7, 4), (8, 4),
              (9, 4), (10, 4), (11, 4), (12, 4), (13, 4), (14, 4), (15, 4)]
DECK_IDLE = {
    # 8 帧行第 5–8 帧，帧与停留同原版马可脚本 0（F14–F20）
    'marco': [(0, 4), (1, 4), (2, 4), (3, 6), (2, 5), (1, 5)],
    # 12 帧行，按原版塔玛脚本 0 的节奏展开：正放、末两帧交替、倒放
    'tarma': [(0, 3), (1, 3), (2, 2), (3, 2), (4, 2), (5, 2), (6, 2), (7, 2), (8, 3), (9, 3), (10, 3), (11, 3),
              (10, 3), (11, 3), (10, 2), (11, 2), (9, 1), (8, 1), (7, 1), (6, 2), (5, 1), (4, 2), (3, 2), (2, 2), (1, 3), (0, 3)],
    # 全身 16 帧行，首尾姿势相近，直接循环
    'eri': _DECK_WIPE,
    'fio': _DECK_WIPE,
}


def cmd(op, *v):
    return {'opcode': op, 'values': list(v)}


HEROES = {
    'marco': dict(uid=16, identity='Regular Army (PF)', ap=90, hp=[25, 8], voice=800, gun_throw=23),
    'tarma': dict(uid=17, identity='Regular Army (PF)', ap=90, hp=[10, 3], voice=803, gun_throw=23),
    'eri': dict(uid=18, identity='Regular Army (Sparrows)', ap=100, hp=[46, 15], voice=801, gun_throw=28),
    'fio': dict(uid=19, identity='Regular Army (Sparrows)', ap=110, hp=[10, 3], voice=802, gun_throw=28),
}
ZS_TEXT = {
    'marco': ('马可', '普通攻击：手枪     特殊攻击：重机枪\n正规军少校。经过千锤百炼的军人，擅长写程序。\n持有相当好用的重机枪。'),
    'tarma': ('塔玛', '普通攻击：手枪     特殊攻击：散弹枪\n正规军上尉。墨镜是他的注册商标。\n拥有可以一次打倒多数敌人的散弹枪。'),
    'eri': ('英里', '普通攻击：手枪     特殊攻击：激光枪\n正规军情报特殊部队的下士。拥有「孟菲斯炸弹女」的绰号。\n拥有最大射程极佳的激光枪。'),
    'fio': ('菲欧', '普通攻击：手枪     特殊攻击：火箭炮\n正规军情报特殊部队的军士长。性格稳重，但有点天然呆\n拥有火力强大的火箭炮。'),
}


# 说明第一行：普通攻击改写为原版特殊攻击的名称，特殊攻击名称后加“大”（用户 2026-11-09）。名称取原版该语言第一行冒号后的文字。
HANDGUN = {'EN': 'Handgun', 'JP': 'ハンドガン', 'KR': '권총', 'ES': 'Revólver', 'PT': 'Pistola', 'FR': 'Pistolet', 'IT': 'Pistola',
           'ZS': '手枪', 'ZT': '手槍', 'RU': 'Пистолет'}
BIG_SUFFIX = {'EN': ' (Big)', 'JP': '（大）', 'KR': ' (대)', 'ES': ' (grande)', 'PT': ' (grande)', 'FR': ' (grand)', 'IT': ' (grande)',
              'ZS': '（大）', 'ZT': '（大）', 'RU': ' (большой)'}


def retitle(code, info):
    first, rest = info.split(chr(10), 1)
    first = first.replace('Pistolet ATT. STAND', 'Pistolet   ATT. SPÉ')   # 法语 Eri 原文第二个标签误写为 ATT. STAND，其余三人为 ATT. SPÉ
    sep = '：' if code in ('JP', 'ZS', 'ZT') else ':'
    head, tail = first.rsplit(sep, 1)
    special = tail.strip()
    assert head.count(HANDGUN[code]) == 1, (code, first)
    return head.replace(HANDGUN[code], special) + sep + tail.rstrip() + BIG_SUFFIX[code] + chr(10) + rest


def localization(name, uid):
    t = TEXTS[str(uid)]
    out = {}
    for code, (nm, info) in t.items():
        if code == 'DE':
            nm, info = t['EN']
            info = retitle('EN', info)
        elif code != 'ZS':
            info = retitle(code, info)
        nm = nm.strip()
        if code == 'ZS':
            nm, info = ZS_TEXT[name]
            info = retitle('ZS', info)
            out[code] = {'name': '真 ' + nm, 'description': info}
        elif code == 'ZT':
            out[code] = {'name': '真 ' + nm, 'description': info}
        elif code == 'JP':
            out[code] = {'name': '真 ' + nm, 'description': info}
        elif code == 'KR':
            out[code] = {'name': '진 ' + nm, 'description': info}
        elif code == 'RU':
            out[code] = {'name': 'СИН ' + nm, 'description': info}
        else:
            out[code] = {'name': 'SHIN ' + nm, 'description': info}
    return out


class Sheet:
    """追加矩形与帧：tiles（PIL RGBA）→ 矩形 [x, y, w, h, ax, ay, 0, page]，帧 = [数量, 矩形序号...]。"""

    def __init__(self, native, page_index):
        self.rects = [list(r) for r in native['rects']]
        self.frames = list(native['frames'])
        self.page_index = page_index
        self.tiles, self.anchor, self.rect_index, self.extruded = [], [], [], []

    def add(self, img, ax, ay, extrude=False):
        self.tiles.append(img)
        self.anchor.append((ax, ay))
        self.extruded.append(extrude)
        return len(self.tiles) - 1

    def new_frame(self, tile):
        return self.new_frame_multi([tile])

    def new_frame_multi(self, tiles):
        at = len(self.frames)
        self.frames += [len(tiles)] + [('tile', t) for t in tiles]
        return at

    def composite(self, arr):
        """BOX 画布的拼合帧 → 裁切后新帧（原点在 BOX (128, 128)）。"""
        yy, xx = np.where(arr[..., 3] > 0)
        x0, y0 = int(xx.min()), int(yy.min())
        t = arr[y0:yy.max() + 1, x0:xx.max() + 1]
        return self.new_frame(self.add(Image.fromarray(t, 'RGBA'), ORIGIN - x0, ORIGIN - y0))

    def finish(self):
        # 首尾相接绘制的帧（激光光束段、拆成多块的火箭）在图集中向外复制一圈边缘像素：缩放后屏幕像素中心正好落在矩形边界时，
        # 采样点在矩形外，打包间隔的透明像素会形成 1 像素接缝（用户截图，2560×1440 时逐段 72 像素一条）；矩形本身不变
        packed = [Image.fromarray(np.pad(np.array(t), ((1, 1), (1, 1), (0, 0)), mode='edge'), 'RGBA') if e else t for t, e in zip(self.tiles, self.extruded)]
        page, pos = shelf_pack(packed)
        rect_of = {}
        for i, tile in enumerate(self.tiles):
            x, y = pos[i]
            if self.extruded[i]:
                x, y = x + 1, y + 1
            ax, ay = self.anchor[i]
            rect_of[i] = len(self.rects)
            self.rects.append([x, y, tile.width, tile.height, ax, ay, 0, self.page_index])
        self.frames = [rect_of[v[1]] if isinstance(v, tuple) else v for v in self.frames]
        return page


def native_script(desc, i):
    return [cmd(c[0], *c[1:]) for c in desc['scripts'][i]]


def ping_pong(frames, holds):
    order = list(range(len(frames))) + list(range(len(frames) - 2, 0, -1))
    seq = []
    for k, i in enumerate(order):
        seq += [cmd(0, frames[i]), cmd(1, holds[k % len(holds)])]
    return seq + [cmd(5)]


def retime(native_seq, frames):
    """按原生脚本的 op0 顺序换帧（同样的停留），op0 个数与 frames 相同。"""
    out, it = [], iter(frames)
    for c in native_seq:
        if c['opcode'] == 0 and c['values'][0] >= 0:
            out.append(cmd(0, next(it)))
        else:
            out.append(cmd(c['opcode'], *c['values']))
    return out


def attack_scripts(desc, hero, big_slot):
    """由原版大招脚本 10 得到普通攻击（9）与 Big（10）。big_slot：{原版弹体动作号: Big 弹体动作号}（Eri 为空，Big 由核心处理）。"""
    base = [c for c in native_script(desc, 10) if not (c['opcode'] == 12 and c['values'][0] == hero['gun_throw'])]
    normal = [c for c in base if not (c['opcode'] == 23 and c['values'][0] == hero['voice'])]
    assert len(normal) == len(base) - 1
    special = []
    for c in base:
        if c['opcode'] == 22 and c['values'][0] in big_slot:
            special.append(cmd(22, big_slot[c['values'][0]], *c['values'][1:]))
        else:
            special.append(cmd(c['opcode'], *c['values']))
    return normal, special


def build_hero(name, big):
    hero = HEROES[name]
    uid = hero['uid']
    native = NATIVE[str(uid)]['descriptor']
    parts = np.load(SOURCE / f'parts_{name}.npz')
    sheet = Sheet(native, len(native['names']))
    idle = [sheet.composite(a) for a in parts['idle']]
    walk = [sheet.composite(a) for a in parts['walk']]
    melee = [sheet.composite(a) for a in parts['melee']]
    seq = [int(v) for v in parts['melee_seq']]
    anims = {}
    s6 = native_script(native, 6)
    holds = [c['values'][0] for c in s6 if c['opcode'] == 1][:4 + 2]
    walk_native = native_script(native, 7)
    walk_holds = [c['values'][0] for c in walk_native if c['opcode'] == 1]
    assert len(walk_holds) == len(walk), (name, len(walk_holds), len(walk))
    anims['0'] = []   # 编队页待机，其帧追加在全部帧之后（见函数末尾），已有帧号不变
    anims['1'] = [c for f, h in zip(walk, walk_holds) for c in (cmd(0, f), cmd(1, h))] + [cmd(5)]
    anims['6'] = [cmd(3, 1)] + ping_pong(idle, holds)
    anims['7'] = [cmd(3, 1)] + [c for f, h in zip(walk, walk_holds) for c in (cmd(0, f), cmd(1, h))] + [cmd(5)]
    anims['8'] = retime(native_script(native, 8), [melee[i] for i in seq])
    attack_bounds = [list(b) for b in native['attack_bounds']]
    behaviors = None
    script_count = native['script_count']
    extra = {}
    if name == 'marco':
        box = len(attack_bounds)
        x, y, w_, h_, f_ = attack_bounds[3]
        attack_bounds.append([x * 3 // 2, y * 3 // 2, w_ * 3 // 2, h_ * 3 // 2, f_])
        w, h = big.tracer.size
        fr = sheet.new_frame(sheet.add(big.tracer, w // 2, h // 2))
        anims['21'] = [cmd(4, box), cmd(0, fr), cmd(1, 1), cmd(21)]
        normal, special = attack_scripts(native, hero, {22: 21})
    elif name == 'tarma':
        box = len(attack_bounds)
        x, y, w_, h_, f_ = attack_bounds[3]
        attack_bounds.append([x * 3 // 2, y * 3 // 2, w_ * 3 // 2, h_ * 3 // 2, f_])
        K = script_count
        script_count += 1
        # 原版爆焰在消散段逐帧前移（左缘 0 → 68，右缘约 96 不变）。Big 帧按原版每帧的重心 ×1.5 放置，贴枪口的帧（原版左缘 ≤ 2）左缘为 0。
        # 全部贴枪口时消散段的烟团会逐帧退回枪口，看起来像被吸回（用户指出）。
        u = PV.Unit(uid)
        s22_frames = [c['values'][0] for c in native_script(native, 22) if c['opcode'] == 0]
        assert len(s22_frames) == len(big.shot)
        frames, placed = [], []
        for F, (im, iw, ih) in zip(s22_frames, big.shot):
            na = u.frame(F, PV.BOX)[..., 3] > 0
            ys, xs = np.where(na)
            ncx, ncy, nleft = float(xs.mean()) - ORIGIN, float(ys.mean()) - ORIGIN, int(xs.min()) - ORIGIN
            ba = np.array(im)[..., 3] > 0
            by, bx = np.where(ba)
            left = 0 if nleft <= 2 else int(round(ncx * 1.5 - float(bx.mean())))
            top = int(round(ncy * 1.5 - float(by.mean())))
            frames.append(sheet.new_frame(sheet.add(im, -left, -top)))
            placed.append((F, nleft, left, top, iw, ih, round(left + float(bx.mean()), 1)))
        extra['shot'] = placed
        s22 = native_script(native, 22)
        seq22 = retime(s22, frames)
        anims[str(K)] = [cmd(4, box) if c['opcode'] == 4 and c['values'][0] == 3 else c for c in seq22]
        normal, special = attack_scripts(native, hero, {22: K})
    elif name == 'eri':
        first = len(sheet.frames)
        for F in range(246, 322, 2):
            if F < 278:
                level = ((F - 246) % 8) // 2
                color = (F - 246) // 8
                if level == 0:
                    im = big.balls[color]
                    ax, ay = 7, 10
                else:
                    # 光束段的起点 = 发射点 + 球帧第一个矩形的宽度（BulletAction_Eri::draw）：原版各级球帧宽度相同（21），
                    # 渐隐时球缩小但矩形宽度保持，光束起点才不会逐级退回枪口
                    base_im = big.balls[color]
                    w_ = base_im.width * (4 - level) // 4
                    small = base_im.resize((w_, w_), Image.NEAREST)
                    im = Image.new('RGBA', base_im.size, (0, 0, 0, 0))
                    # 原版球帧自带一段光束连到光束段；球缩小后从球心到矩形右缘补同级粗细的光束，否则球与光束之间有空隙
                    tile = big.tiles[color]
                    h_ = (12, 8, 4, 2)[level]
                    strip = tile.crop((0, (tile.height - h_) // 2, base_im.width // 2, (tile.height - h_) // 2 + h_))
                    im.paste(strip, (base_im.width // 2, base_im.height // 2 - h_ // 2))
                    im.alpha_composite(small, ((base_im.width - w_) // 2, (base_im.height - w_) // 2))
                    ax, ay = 7, 10
            elif F < 310:
                level = ((F - 278) % 8) // 2
                color = (F - 278) // 8
                tile = big.tiles[color]
                h_ = (12, 8, 4, 2)[level]
                im = tile.crop((0, (tile.height - h_) // 2, tile.width, (tile.height - h_) // 2 + h_))
                ax, ay = 8, h_ // 2
            else:
                k = (F - 310) // 2
                color = k % 4
                im = big.impacts[color][k]
                ax, ay = 19, im.height // 2   # 左缘固定（同原版 6 帧左缘固定在 −24），避免各帧按中心对齐造成前后抖动
            at = sheet.new_frame(sheet.add(im, ax, ay, extrude=True))
            assert at == first + (F - 246), (at, F)
        normal, special = attack_scripts(native, hero, {})
        behaviors = [{'name': 'big_weapon', 'version': 1, 'params': {'laser_frame_delta': first - 246, 'laser_frame_limit': first, 'laser_half_box': 30}}]
        extra['delta'] = first - 246
    else:  # fio
        rocket_box, blast_box = len(attack_bounds), len(attack_bounds) + 1
        x, y, w_, h_, f_ = attack_bounds[3]
        attack_bounds.append([x * 3 // 2, y * 3 // 2, w_ * 3 // 2, h_ * 3 // 2, f_])
        x, y, w_, h_, f_ = attack_bounds[4]
        attack_bounds.append([x * 3 // 2, y * 3 // 2, w_ * 3 // 2, h_ * 3 // 2, f_])
        K = script_count
        script_count += 3
        # 8 帧：水平 ×2 / 档 1 ×2 / 档 2 ×2 / 档 3 ×2（尾焰两态）；锚点同原生火箭：弹头在 +11，垂直居中
        # 原生 BattleBullet::update 的触地判定读取当前帧第一个矩形的高度（getImageHeightSize）：Big 帧拆成多个矩形，第一个矩形的高度取原生同档帧的高度，
        # 触地判定与原生相同（Big 帧更高时火箭下沉段会提前触地爆炸）
        native_map = {328: 0, 330: 1, 316: 2, 318: 3, 320: 4, 322: 5, 324: 6, 326: 7}
        rk = [None] * 8
        for nF, i in native_map.items():
            im, iw, ih = big.rocket[i]
            native_h = native['rects'][native['frames'][nF + 1]][3]
            h0 = min(ih, native_h)
            y0 = (ih - h0) // 2
            ax, ay = iw - 12, ih // 2
            tiles = [sheet.add(im.crop((0, y0, iw, y0 + h0)), ax, ay - y0, extrude=True)]
            if y0 > 0:
                tiles.append(sheet.add(im.crop((0, 0, iw, y0)), ax, ay, extrude=True))
            if y0 + h0 < ih:
                tiles.append(sheet.add(im.crop((0, y0 + h0, iw, ih)), ax, ay - (y0 + h0), extrude=True))
            rk[i] = sheet.new_frame_multi(tiles)
        def swap(seq, boxes):
            out = []
            for c in seq:
                if c['opcode'] == 0 and c['values'][0] in native_map:
                    out.append(cmd(0, rk[native_map[c['values'][0]]]))
                elif c['opcode'] == 4 and c['values'][0] in boxes:
                    out.append(cmd(4, boxes[c['values'][0]]))
                else:
                    out.append(cmd(c['opcode'], *c['values']))
            return out
        anims[str(K)] = swap(native_script(native, 31), {3: rocket_box})
        anims[str(K + 1)] = swap(native_script(native, 32), {3: rocket_box})
        # 爆炸画面同原版脚本 33，只换攻击框（×1.5）；曾叠加的火球取自火焰喷射的素材行，用户指出后移除
        anims[str(K + 2)] = swap(native_script(native, 33), {4: blast_box})
        normal, special = attack_scripts(native, hero, {31: K})
        behaviors = [{'name': 'big_weapon', 'version': 1, 'params': {'rocket_loop_animation': K + 1, 'rocket_explosion_animation': K + 2}}]
    anims['9'] = normal
    anims['10'] = special
    deck = [sheet.composite(a) for a in np.load(SOURCE / f'deck_{name}.npz')['frames']]
    anims['0'] = [c for i, h in DECK_IDLE[name] for c in (cmd(0, deck[i]), cmd(1, h))] + [cmd(5)]
    page = sheet.finish()
    desc = {'rects': sheet.rects, 'frames': sheet.frames, 'script_count': script_count,
            'hit_bounds': [list(b) for b in native['hit_bounds']], 'attack_bounds': attack_bounds}
    return page, desc, anims, behaviors, extra, parts['idle'][0]


def icon_image(arr, name):
    yy, xx = np.where(arr[..., 3] > 0)
    x0, x1, y0, y1 = int(xx.min()), int(xx.max()) + 1, int(yy.min()), int(yy.max()) + 1
    origin = ICON_ORIGIN[name]
    right = ORIGIN + (ICON_RIGHT[name] - origin[0])   # 原点右侧的列数上限
    x1 = min(x1, right)
    t = arr[y0:y1, x0:x1]
    return Image.fromarray(t, 'RGBA'), [-(origin[0] - (ORIGIN - x0)), -(origin[1] - (ORIGIN - y0))]


def free_icon_slot(raw, w, iw, ih, taken):
    used = list(taken)
    for p in CONTENT.glob('units/*.json'):
        u = json.loads(p.read_text(encoding='utf-8'))
        icon = u.get('icon') or {}
        if 'atlas' in icon or icon.get('page') != 1:
            continue
        used.append(icon['rect'])
    for y in (770, 820, 870):
        for x in range(0, 2048 - iw, 2):
            if any(not (x + iw + 4 <= a or x >= a + c + 4 or y + ih <= b or y >= b + d) for a, b, c, d in used):
                continue
            if all(raw[8 + ((y + j) * w + x + i) * 4 + 3] == 0 for j in range(ih) for i in range(iw)):
                return [x, y, iw, ih]
    raise RuntimeError('no free icon slot')


def write_icon(raw, cell, rect):
    w = struct.unpack_from('<H', raw, 4)[0]
    x0, y0, iw, ih = rect
    for j in range(ih):
        for i in range(iw):
            at = 8 + ((y0 + j) * w + x0 + i) * 4
            raw[at:at + 4] = bytes(cell.getpixel((i, j)))


def unit_file(name, desc_name, tex, anims, behaviors, icon):
    hero = HEROES[name]
    uid = hero['uid']
    r = NATIVE[str(uid)]['row']
    w = lambda i: r[str(i)]

    def one(values):
        assert len(set(values)) == 1, values
        return values[0]
    data = {'key': f's1xlv.shin_{name}', 'base_id': uid, 'faction': 0, 'identity': hero['identity'], 'shop_price': 0, 'available_from_start': False, 'shop_unlock_reference_id': 136,
            'world_clear_reward': {'world': 1, 'area': 11, 'world_type': 0},   # 通关表世界 2 主线（最后一个 Mission）后直接获得，不经商店（用户，同 KT-21）
           
            'ap': hero['ap'],
            # 用户设定：Lv40 生命 3000 / 3600 / 2300 / 2600，击退门槛同倍率；移速、大招等待、生产间隔同原版
            'hp_multiplier': hero['hp'], 'knockback_threshold_multiplier': hero['hp'], 'damage_multiplier': [1, 1],
            'special_damage_multiplier': [3, 2], 'move_speed_multiplier': [1, 1], 'attack_wait_multiplier': [1, 1],
            'attack_range_multiplier': [1, 1], 'knockback_distance_multiplier': [1, 1], 'ballistic_range_multiplier': [1, 1],
            'production_reference_id': uid, 'production_interval_multiplier': [1, 1],
            # 普通攻击 = 原版大招：普通攻击组取特殊攻击组的数值（六个等级锚点）；攻击等待取原版大招的等待（用户确认）
            'status_word_values': {'22': w(29), '24': w(31), '26': w(33), '27': w(34)},
            'attack_attributes': {'normal': w(37)},
            'status_float_values': {'23': one(w(30)), '25': one(w(32))},
            'image_direction': 90,
            'icon': icon, 'textures': tex, 'sprite_descriptor': desc_name, 'animations': anims,
            'localization': localization(name, uid), 'tags': ['shin']}
    if behaviors:
        data['behaviors'] = behaviors
    return data


def main():
    OUT.mkdir(exist_ok=True)
    big = PV.Big()
    results = {}
    icon_raw = bytearray((CONTENT / 'unit_icon_02.obm').read_bytes())
    width = struct.unpack_from('<H', icon_raw, 4)[0]
    taken = []
    report = {}
    index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
    for name in HEROES:
        page, desc, anims, behaviors, extra, idle0 = build_hero(name, big)
        desc_name = f'shin_{name}_descriptor.json'
        tex_name = f'shin_{name}.obm'
        native_names = NATIVE[str(HEROES[name]['uid'])]['descriptor']['names']
        obm = indexed_obm(page)
        page.save(OUT / f'shin_{name}_page.png')
        save_json(OUT / desc_name, desc)
        cell, anchor = icon_image(idle0, name)
        cell.save(OUT / f'icon_{name}.png')
        unit_path = CONTENT / 'units' / f'shin_{name}.json'
        if unit_path.exists():
            old_rect = json.loads(unit_path.read_text(encoding='utf-8'))['icon']['rect']
            write_icon(icon_raw, Image.new('RGBA', tuple(old_rect[2:]), (0, 0, 0, 0)), old_rect)   # 先清空原矩形，新矩形沿用原左上角
            rect = old_rect[:2] + [cell.width, cell.height]
            x_, y_, w_, h_ = rect
            assert all(icon_raw[8 + ((y_ + j) * width + x_ + i) * 4 + 3] == 0 for j in range(h_) for i in range(w_)), (name, rect, 'overlaps another icon')
        else:
            rect = free_icon_slot(bytes(icon_raw), width, cell.width, cell.height, taken)
        taken.append(rect)
        icon = {'page': 1, 'rect': rect, 'anchor': anchor}
        tex = native_names + [tex_name]
        data = unit_file(name, desc_name, tex, anims, behaviors, icon)
        results[name] = dict(rect=rect, anchor=anchor, page=list(page.size), colors=len(set(page.getdata())), obm=len(obm), scripts=desc['script_count'], **extra)
        if '--preview' in sys.argv:
            continue
        key = data['key']
        if key not in index['unit_ids']:
            index['unit_ids'][key] = max(index['unit_ids'].values()) + 1
        (CONTENT / tex_name).write_bytes(obm)
        index['assets'][tex_name] = hashlib.blake2b(obm, digest_size=32).hexdigest()
        write_icon(icon_raw, cell, rect)
        save_json(CONTENT / desc_name, desc)
        save_json(unit_path, data)
    if '--preview' not in sys.argv:
        (CONTENT / 'unit_icon_02.obm').write_bytes(bytes(icon_raw))
        save_json(CONTENT / 'content.json', index)
    (OUT / 'build_report.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False))


if __name__ == '__main__':
    main()
