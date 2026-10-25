"""暴食飞行侵略者（RAVENOUS WINGED INVADER）按 MSA 7.13.0 原始动作记录移植（2026-10-22，AGENTS 第 212 节）。

来源：F:\\egg\\research\\metal_slug_attack\\decoded\\units\\1123（动作类 BattleAction_GruelingWingedInvader）。
- 核对（verification/ravenous_winged_invader_20261022/）：MSA 1123 与 MSD 原版飞行侵略者 200（BattleAction_WingedInvader，32 个脚本）
  的矩形尺寸与锚点、帧表、受击框逐项相同（只有图集位置不同）。去掉 MSA 专有空操作指令后，除攻击槽与弹体外各槽与 200 逐条相同
  （MSD 200 的本体槽开头多 op14[0,−10]）。MSD 200 的状态 → 槽：10 槽 6、20 槽 7、30 / 40 槽 8、50 槽 9、70 槽 10、100–120 槽 11。
  MSD 槽 ← MSA 槽：0–7 同号，8 ← 9，9 ← 11，10 ← 14，11–14 ← 17–20，15–18 ← 38–41，19 / 20 ← 36 / 37，21–28 同号，29–31 ← 32–34。
- 攻击：MSA 的普攻（槽 8）与绝招（槽 10 / 12）发射的弹体 29–31 不带 op7，由 GruelingWingedInvader::shotBullet 按目标方向
  （getTargetAngle）以 10° 间隔散开设定速度；记录中另有不瞄准的同一组弹幕（槽 9 / 11 / 13，弹体 32–34：正前方 10 像素/tick 与
  ±11.25°）。MSD 原生 WingedInvader::shotBullet 不瞄准（addBulletNotAim），速度来自弹体脚本，本单位采用后者：普攻一次 3 发、
  绝招 3 轮共 9 发。op22 的第 2 个值在 MSD 为攻击状态覆盖（0 为当前状态，30 / 40 / 50 以外不生成弹体），MSA 的 1–12 一律改为 0。
  弹体 32 的末尾 op21 改为 op5（MSD 原生弹体循环，飞行距离由状态词 26 / 33 限定）。
- 图集 Gluttony_winged_venusian_base_0/1/2_out.obm（各 512×512）原样转为 OI 01 08。
- 数值（用户 2026-10-22）：以原版飞行侵略者 200 为基准，生命与 AP ×2，伤害 R2 改回与 200 相同（每发 1200）；击退门槛 200 为 −1（每次受击都击退，
  加载器只缩放正值），保持；出击时间、移速、射程保持原版。价格保持 200 的 180 勋章。AP R3（用户同日）：400 → 300。
  R5（用户 2026-10-25）：普攻 3 发合计 2400（为 200 单发 1200 的 2 倍，每发 800）、绝招 9 发每发 300（Lv40），其余不变。
- 头像：MSA unit_icon_02.obme 中本单位的原格（m_unit_misc.pict 864 → (1295,730) 46×46，锚点 [−5, 1]）写入
  community_content/unit_icon_02.obm 的 (1800,768)。名称与说明取 MSA 主数据表；简体中文名称按用户用语为“暴食飞行侵略者”，
  简体说明中的“入侵者”按 MSD 简体用语改为“侵略者”。
运行：E:\\anaconda3\\python.exe -I artwork/ravenous_winged_invader_20261022/build_ravenous_winged_invader.py [--preview]
"""
from pathlib import Path
import copy
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MSA_UNIT = Path(r'F:\egg\research\metal_slug_attack\decoded\units\1123')
MSA_ICONS = Path(r'F:\egg\research\metal_slug_attack\decoded\unit_icons\unit_icon_02.obme.png')
MSA_TEXTS = REPO / 'verification' / 'ravenous_invader_20261022' / 'msa_texts.json'
sys.path.insert(0, r'F:\egg\research\metal_slug_attack\scripts')

from PIL import Image  # noqa: E402
import msa_unit  # noqa: E402

_PVZ = REPO / 'artwork' / 'pvz_zombies_20261012' / 'build_pvz_zombies.py'
_src = _PVZ.read_text(encoding='utf-8')
_src = _src.replace("sys.path.insert(0, str(RT / 'packages'))", "").replace("os.add_dll_directory(str(RT / 'native'))", "")
pvz = type(sys)('pvzb')
pvz.__dict__['__file__'] = str(_PVZ)
exec(compile(_src, str(_PVZ), 'exec'), pvz.__dict__)
indexed_obm, save_json = pvz.indexed_obm, pvz.save_json

CONTENT = REPO / 'community_content'
OUT = HERE / 'out'
KEY = 's1xlv.ravenous_winged_invader'
FILE = 'ravenous_winged_invader.json'
TEXTURES = ('ravenous_winged_invader_0.obm', 'ravenous_winged_invader_1.obm', 'ravenous_winged_invader_2.obm')
DESCRIPTOR = 'ravenous_winged_invader_descriptor.json'
BASE = 200
SCRIPT_COUNT = 32                    # 同 200
SLOT_FROM = {8: 9, 9: 11, 10: 14, 11: 17, 12: 18, 13: 19, 14: 20, 15: 38, 16: 39, 17: 40, 18: 41, 19: 36, 20: 37,
             29: 32, 30: 33, 31: 34}   # MSD 槽 ← MSA 槽（其余同号）
BODY_OP14 = range(6, 15)             # MSD 200 的这些槽以 op14[0,−10] 开头（飞行高度的绘制偏移）
BULLET_LOOP = (29,)                  # 末尾 op21 改为 op5
SUBLAYER_OPS = (10, 11, 12, 22)
MSA_ONLY = range(24, 73)
SUBLAYER_MSA = 36
ICON_CELL = (1295, 730, 46, 46)      # MSA 头像图集中的暴食飞行侵略者（pict 864）
ICON = {'page': 1, 'rect': [1800, 768, 46, 46], 'anchor': [-5, 1]}
NUMBERS = {   # 用户 2026-10-22：原版飞行侵略者 200 的生命与 AP ×2；R2（同日）伤害改回与 200 相同（每发 1200，普攻自带 3 向）
    'ap': 300, 'shop_price': 180, 'hp_multiplier': [2, 1], 'damage_multiplier': [1, 1],   # AP R3（用户同日）：400 → 300
    # R5（用户 2026-10-25）：普攻 3 发合计为 200 单发 1200 的 2 倍（每发 800，词 22 × 2/3）；绝招 9 发每发 300（词 29 × 1/4）
    'special_damage_multiplier': [1, 4], 'normal_damage_multiplier': [2, 3],
}
ONES = ('move_speed_multiplier', 'attack_wait_multiplier', 'attack_range_multiplier',
        'knockback_distance_multiplier', 'ballistic_range_multiplier')


def transform(record):
    """MSA 脚本 → 本体动画。返回 (动画字典, 统计)。"""
    inverse = {src: dst for dst, src in SLOT_FROM.items()}
    keep = {SLOT_FROM.get(s, s) for s in range(SCRIPT_COUNT)}
    stats = {'removed_msa_only': {}, 'sublayer_refs': {}, 'bullet_state_zeroed': 0, 'op14_added': 0, 'sounds': {}}
    animations = {}
    for slot in range(SCRIPT_COUNT):
        out = [{'opcode': 14, 'values': [0, -10]}] if slot in BODY_OP14 else []
        stats['op14_added'] += slot in BODY_OP14
        for c in record['scripts'][SLOT_FROM.get(slot, slot)]:
            op, v = c[0], list(c[1:])
            if op == SUBLAYER_MSA:
                op = 11
            elif op in MSA_ONLY:
                stats['removed_msa_only'][str(op)] = stats['removed_msa_only'].get(str(op), 0) + 1
                continue
            if op in SUBLAYER_OPS:
                assert v[0] in keep, (slot, c)
                new = inverse.get(v[0], v[0])
                if new != v[0]:
                    stats['sublayer_refs'][f'{v[0]}->{new}'] = stats['sublayer_refs'].get(f'{v[0]}->{new}', 0) + 1
                v[0] = new
                if op == 22 and v[1] != 0:
                    v[1] = 0
                    stats['bullet_state_zeroed'] += 1
            elif op == 23:
                stats['sounds'][v[0]] = stats['sounds'].get(v[0], 0) + 1
            out.append({'opcode': op, 'values': v})
        if slot in BULLET_LOOP and out[-1]['opcode'] == 21:
            out[-1] = {'opcode': 5, 'values': []}
        animations[str(slot)] = out
    return animations, stats


def descriptor(record):
    rects = [list(r) for r in record['rects']]
    frames = list(record['frames'])
    assert 0xffffffff not in frames
    return {'rects': rects, 'frames': frames, 'script_count': SCRIPT_COUNT,
            'hit_bounds': record['hit_bounds'], 'attack_bounds': record['attack_bounds']}


def preview_record(record, animations, desc):
    r = copy.deepcopy(record)
    r['rects'], r['frames'] = desc['rects'], desc['frames']
    r['scripts'] = [[[c['opcode'], *c['values']] for c in animations[str(i)]] for i in range(SCRIPT_COUNT)]
    r['script_count'] = SCRIPT_COUNT
    return r


# 中文说明第 2、3 行为用户 2026-10-22 文本（AGENTS 第 218 节；繁体按简体逐字转写），第 1 行攻击名称取 MSA
LORE = {'ZS': '不用乘坐UFO，可以自己飞行的暴食侵略者。\n由于十分的饥饿，已经发狂到要吃掉这里的一切。',
        'ZT': '不用乘坐UFO，可以自己飛行的暴食侵略者。\n由於十分的饑餓，已經發狂到要吃掉這裡的一切。'}


def localization():
    texts = json.loads(MSA_TEXTS.read_text(encoding='utf-8'))['1123']
    out = {lang: {'name': t['name'], 'description': t['description']} for lang, t in texts.items()}
    out['ZS'] = {'name': '暴食飞行侵略者', 'description': out['ZS']['description'].replace('入侵者', '侵略者')}
    for lang, lore in LORE.items():
        out[lang]['description'] = out[lang]['description'].split('\n')[0] + '\n' + lore
    return out


def unit_file(animations):
    return {'key': KEY, 'base_id': BASE, 'faction': 3, 'identity': 'Invader',
            'shop_price': NUMBERS['shop_price'], 'available_from_start': True, 'ap': NUMBERS['ap'],
            'hp_multiplier': NUMBERS['hp_multiplier'],
            # 击退门槛随生命倍率联动（第 6.1 节）；200 为 −1，加载器只缩放正值
            'knockback_threshold_multiplier': list(NUMBERS['hp_multiplier']),
            'damage_multiplier': NUMBERS['damage_multiplier'],
            'special_damage_multiplier': NUMBERS['special_damage_multiplier'],
            'normal_damage_multiplier': NUMBERS['normal_damage_multiplier'],
            **{k: [1, 1] for k in ONES},
            'production_reference_id': BASE, 'production_interval_multiplier': [1, 1],
            'icon': ICON, 'textures': list(TEXTURES), 'sprite_descriptor': DESCRIPTOR, 'animations': animations,
            'localization': localization(), 'tags': ['ms6', 'msa']}


def write_icon(cell):
    raw = bytearray((CONTENT / 'unit_icon_02.obm').read_bytes())
    assert raw[:4] == b'OI\x01\x20'
    w, h = struct.unpack_from('<HH', raw, 4)
    ax, ay, iw, ih = ICON['rect']
    for other in CONTENT.glob('units/*.json'):
        unit = json.loads(other.read_text(encoding='utf-8'))
        icon = unit['icon']
        if unit['key'] == KEY or 'atlas' in icon or icon['page'] != 1:
            continue
        x, y, ow, oh = icon['rect']
        assert x + ow <= ax or x >= ax + iw or y + oh <= ay or y >= ay + ih, unit['key']
    for j in range(ih):
        for i in range(iw):
            at = 8 + ((ay + j) * w + ax + i) * 4
            raw[at:at + 4] = bytes(cell.getpixel((i, j)))
    return bytes(raw)


def main():
    OUT.mkdir(exist_ok=True)
    (HERE / 'source').mkdir(exist_ok=True)
    record = json.loads((MSA_UNIT / 'record.json').read_text(encoding='utf-8'))
    assert record['names'] == ['Gluttony_winged_venusian_base_%d_out.obm' % i for i in range(3)] and record['script_count'] == 43
    atlases = [Image.open(MSA_UNIT / (n + '.png')).convert('RGBA') for n in record['names']]
    animations, stats = transform(record)
    desc = descriptor(record)
    unit = unit_file(animations)
    obms = [indexed_obm(a) for a in atlases]
    x, y, iw, ih = ICON_CELL
    cell = Image.open(MSA_ICONS).convert('RGBA').crop((x, y, x + iw, y + ih))
    cell.save(HERE / 'source' / f'msa_icon_ravenous_winged_invader_{x}_{y}.png')
    report = {'stats': stats, 'colors': [len(set(a.getdata())) for a in atlases], 'obm_bytes': [len(o) for o in obms],
              'rects': len(desc['rects']), 'frames': len(desc['frames']), 'numbers': NUMBERS}
    pr = preview_record(record, animations, desc)
    lengths = {}
    for slot in (0, 6, 7, 8, 9, 10, 11):
        sim = msa_unit.Sim(pr, atlases)
        sim.start(slot)
        frames, t = [], 0
        while t < 80:
            if t % 4 == 0:
                frames.append(sim.draw((640, 320), (240, 260), 2))
            sim.step()
            t += 1
            if sim.root.done:
                break
        lengths[slot] = t
        sheet = Image.new('RGB', (320 * min(len(frames), 10), 160 * ((len(frames) + 9) // 10)), (40, 40, 40))
        for i, im in enumerate(frames):
            sheet.paste(im.convert('RGB').resize((320, 160), Image.NEAREST), ((i % 10) * 320, (i // 10) * 160))
        sheet.save(OUT / f'preview_slot{slot:02d}.png')
    report['preview_ticks'] = lengths
    if '--preview' in sys.argv:
        print(json.dumps(report, ensure_ascii=False))
        return
    index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
    if KEY not in index['unit_ids']:
        index['unit_ids'][KEY] = max(index['unit_ids'].values()) + 1
    for name, obm in zip(TEXTURES, obms):
        (CONTENT / name).write_bytes(obm)
        index['assets'][name] = hashlib.blake2b(obm, digest_size=32).hexdigest()
    (CONTENT / 'unit_icon_02.obm').write_bytes(write_icon(cell))   # 该资源的摘要在 content.json 中为 null，保持不变
    save_json(CONTENT / DESCRIPTOR, desc)
    save_json(CONTENT / 'units' / FILE, unit)
    save_json(CONTENT / 'content.json', index)
    report['unit_id'] = index['unit_ids'][KEY]
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
