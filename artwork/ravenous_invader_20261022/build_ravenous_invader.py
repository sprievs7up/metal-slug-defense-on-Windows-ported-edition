"""暴食侵略者（RAVENOUS INVADER）按 MSA 7.13.0 原始动作记录移植（2026-10-22，AGENTS 第 211 节）。

来源：F:\\egg\\research\\metal_slug_attack\\decoded\\units\\0859（msa_unit.py export 859，动作类 BattleAction_GruelingInvader）。
- 核对（verification/ravenous_invader_20261022/）：MSA 859 的动作记录是 MSD 原版侵略者 192（BattleAction_Alien，描述符 25 个脚本）
  的同一套动作：受击框、攻击框与全部帧号相同，去掉 MSA 专有的空操作指令后，各槽脚本与 192 逐条相同，差别只有
  (1) MSA 插入两槽（11 两次滚动，属版本技能“滚动攻击”；14 后仰后的近距反击，属版本技能“刺猬弹反击”），其后的槽号顺延；
  (2) 近距攻击与绝招各多一条 op23 232（SND_SE_tk317kar，MSD 同号同文件）；(3) 新增的碎块槽 27–51 不被前述各槽引用。
  因此基准取 192，原生动作类与状态 → 槽的对应不变，只换图集与描述符：MSD 槽 0–10 ← MSA 0–10，11 ← 12，12 ← 13，
  13–24 ← 15–26；子层与弹体（op10 / 11 / 12 / 22）引用的槽号按同一对应改写（MSA 19 / 20 → 17 / 18）。
- 图集 venusian_magaki_out.obm（1024×1024）与 venusian_magaki_magotto_out.obm（256×256）原样转为 OI 01 08。
- 数值（用户 2026-10-22）：以原版侵略者 192 为基准，生命与 AP ×2，击退门槛随生命 ×2；伤害 R2 改为近距 2000、绝招 3200（×4/3）；出击时间、
  移速、射程保持原版。攻击种类按 MSA：MSA 859 只有攻击 1（冲撞）与攻击 3（滚动攻击），无远距攻击，故状态词 7（远距开火距离）写 0，
  不进入状态 40（192 的吐酸）。价格保持 192 的 150 勋章。AP R3（用户同日）：360 → 270。
- 头像：MSA unit_icon_02.obme 中本单位的原格（m_unit_misc.pict 675 → (1013,600) 42×42，锚点 [−6, −3]）写入
  community_content/unit_icon_02.obm 的 (1750,768)。名称与说明取 MSA 主数据表（各语言原文；MSA 未翻译的语言为英文原文）。
运行：E:\\anaconda3\\python.exe -I artwork/ravenous_invader_20261022/build_ravenous_invader.py [--preview]
（--preview 只写 out/；否则写入 community_content/：两张图集、描述符、单位文件、unit_icon_02.obm 与 content.json）。
"""
from pathlib import Path
import copy
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MSA_UNIT = Path(r'F:\egg\research\metal_slug_attack\decoded\units\0859')
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
KEY = 's1xlv.ravenous_invader'
FILE = 'ravenous_invader.json'
TEXTURES = ('ravenous_invader.obm', 'ravenous_invader_maggot.obm')
DESCRIPTOR = 'ravenous_invader_descriptor.json'
BASE = 192
SCRIPT_COUNT = 25                    # 同 192
SLOT_FROM = {11: 12, 12: 13, **{s: s + 2 for s in range(13, 25)}}   # MSD 槽 ← MSA 槽（其余同号）
SUBLAYER_OPS = (10, 11, 12, 22)      # 首参数为脚本槽
MSA_ONLY = range(24, 73)
SUBLAYER_MSA = 36                    # MSA：挂子层（参数同 op11），本单位未使用
ICON_CELL = (1013, 600, 42, 42)      # MSA 头像图集中的暴食侵略者（pict 675）
ICON = {'page': 1, 'rect': [1750, 768, 42, 42], 'anchor': [-6, -3]}
NUMBERS = {   # 用户 2026-10-22：原版侵略者 192 的生命与 AP ×2；R2（同日）伤害改为近距 2000、绝招 3200（192 的 1500 / 2400 × 4/3）
    # R5（社区意见，用户 2026-10-25：相对价格与伤害过于耐打）：生命改为 192 的 1.5 倍（Lv40 9000），击退门槛随之 ×3/2（30）
    'ap': 270, 'shop_price': 150, 'hp_multiplier': [3, 2], 'damage_multiplier': [4, 3],   # AP R3（用户同日）：360 → 270
    'status_word_values': {'7': 0},
}
ONES = ('special_damage_multiplier', 'move_speed_multiplier', 'attack_wait_multiplier', 'attack_range_multiplier',
        'knockback_distance_multiplier', 'ballistic_range_multiplier')


def transform(record):
    """MSA 脚本 → 本体动画。返回 (动画字典, 统计)。"""
    inverse = {src: dst for dst, src in SLOT_FROM.items()}
    keep = {SLOT_FROM.get(s, s) for s in range(SCRIPT_COUNT)}
    stats = {'removed_msa_only': {}, 'sublayer_refs': {}, 'sounds': {}}
    animations = {}
    for slot in range(SCRIPT_COUNT):
        out = []
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
            elif op == 23:
                stats['sounds'][v[0]] = stats['sounds'].get(v[0], 0) + 1
            out.append({'opcode': op, 'values': v})
        animations[str(slot)] = out
    return animations, stats


def descriptor(record):
    rects = [list(r) for r in record['rects']]
    frames = list(record['frames'])
    if 0xffffffff in frames:    # 空帧（矩形 −1）改为追加的 1×1 透明矩形，同钢铁哨兵
        rects.append([255, 255, 1, 1, 0, 0, 0, 0])
        frames = [len(rects) - 1 if v == 0xffffffff else v for v in frames]
    return {'rects': rects, 'frames': frames, 'script_count': SCRIPT_COUNT,
            'hit_bounds': record['hit_bounds'], 'attack_bounds': record['attack_bounds']}


def preview_record(record, animations, desc):
    r = copy.deepcopy(record)
    r['rects'], r['frames'] = desc['rects'], desc['frames']
    r['scripts'] = [[[c['opcode'], *c['values']] for c in animations[str(i)]] for i in range(SCRIPT_COUNT)]
    r['script_count'] = SCRIPT_COUNT
    return r


# 中文说明第 2、3 行为用户 2026-10-22 文本（AGENTS 第 218 节；繁体按简体逐字转写），第 1 行攻击名称取 MSA
LORE = {'ZS': '主要捕食火星人为生的凶暴宇宙人。\n由于十分的饥饿，已经发狂到要吃掉这里的一切。',
        'ZT': '主要捕食火星人為生的兇暴宇宙人。\n由於十分的饑餓，已經發狂到要吃掉這裡的一切。'}


def localization():
    texts = json.loads(MSA_TEXTS.read_text(encoding='utf-8'))['859']
    out = {lang: {'name': t['name'], 'description': t['description']} for lang, t in texts.items()}
    for lang, lore in LORE.items():
        out[lang]['description'] = out[lang]['description'].split('\n')[0] + '\n' + lore
    return out


def unit_file(animations):
    unit = {'key': KEY, 'base_id': BASE, 'faction': 3, 'identity': 'Invader',
            'shop_price': NUMBERS['shop_price'], 'available_from_start': True, 'ap': NUMBERS['ap'],
            'hp_multiplier': NUMBERS['hp_multiplier'],
            # 击退门槛随生命倍率联动（第 6.1 节）：192 为 20，×3/2 为 30（R5；此前 ×2 为 40）
            'knockback_threshold_multiplier': list(NUMBERS['hp_multiplier']),
            'damage_multiplier': NUMBERS['damage_multiplier'],
            **{k: [1, 1] for k in ONES},
            'production_reference_id': BASE, 'production_interval_multiplier': [1, 1],
            'status_word_values': NUMBERS['status_word_values'],
            'icon': ICON, 'textures': list(TEXTURES), 'sprite_descriptor': DESCRIPTOR, 'animations': animations,
            'localization': localization(), 'tags': ['ms6', 'msa']}
    return unit


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
    assert record['names'] == ['venusian_magaki_out.obm', 'venusian_magaki_magotto_out.obm'] and record['script_count'] == 52
    atlases = [Image.open(MSA_UNIT / (n + '.png')).convert('RGBA') for n in record['names']]
    animations, stats = transform(record)
    desc = descriptor(record)
    unit = unit_file(animations)
    obms = [indexed_obm(a) for a in atlases]
    x, y, iw, ih = ICON_CELL
    cell = Image.open(MSA_ICONS).convert('RGBA').crop((x, y, x + iw, y + ih))
    cell.save(HERE / 'source' / f'msa_icon_ravenous_invader_{x}_{y}.png')
    report = {'stats': stats, 'colors': [len(set(a.getdata())) for a in atlases], 'obm_bytes': [len(o) for o in obms],
              'rects': len(desc['rects']), 'frames': len(desc['frames']), 'numbers': NUMBERS}
    pr = preview_record(record, animations, desc)
    lengths = {}
    for slot in (0, 6, 7, 8, 10, 11, 12, 13):
        sim = msa_unit.Sim(pr, atlases)
        sim.start(slot)
        frames, t = [], 0
        while t < 80:
            if t % 4 == 0:
                frames.append(sim.draw((480, 320), (240, 260), 2))
            sim.step()
            t += 1
            if sim.root.done:
                break
        lengths[slot] = t
        sheet = Image.new('RGB', (240 * min(len(frames), 10), 160 * ((len(frames) + 9) // 10)), (40, 40, 40))
        for i, im in enumerate(frames):
            sheet.paste(im.convert('RGB').resize((240, 160), Image.NEAREST), ((i % 10) * 240, (i // 10) * 160))
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
