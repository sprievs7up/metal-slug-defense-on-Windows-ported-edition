"""飞行护盾（FLYING SHELT）按 MSA 7.13.0 原始动作记录移植（2026-10-22，AGENTS 第 215 节；行为 flying_shell，核心 r79）。

来源：F:\\egg\\research\\metal_slug_attack\\decoded\\units\\0858（动作类 BattleAction_FlyingShell；用户选定未开放版 860 的移速 0.5，
860 与 858 共用此动作记录，代码中 860 另有飞行高度 80（858 为 140）与陨石只在换为追踪 / 下落动作后落地的分支，本单位按 860）。
- MSA 状态 → 槽（verification/flying_shell_20261022）：10 槽 6、20 槽 7、30 / 40 槽 8（普攻：花瓣 23 / 29 射出陨石 47 / 48）、
  50 槽 9（绝招：花瓣 30 / 32 射出陨石 49 / 50；槽 10 为加强版，用 51 / 52）、80 槽 11（受击）、70 槽 12、100–120 槽 13（损毁）。
  本单位以 MSD 原版飞行侵略者 200（BattleAction_WingedInvader）为原生动作类，其状态 → 槽为 10→6、20→7、30 / 40→8、50→9、70→10、
  100–120→11（播完移除）：MSD 槽 10 ← MSA 11，11 ← MSA 13，其余槽号沿用 MSA（部件、花瓣与陨石脚本的编号不变）。
- 脚本：op36（挂子层，只在第一遍执行）改为 op11（MSD 按脚本与层级取同一子层，循环中不重复建立）；MSA 专有空操作指令删除；
  op22 的第 2 个值（MSA 为 1–4）改为 0（MSD 为攻击状态覆盖，30 / 40 / 50 以外不生成弹体）。
- 陨石的追踪、绝招的落点与斜落、陨石生命与损毁爆炸由行为 flying_shell（核心 r79）实现；不被击退用行为 no_knockback。
- 图集 Flying_shell_out.obm（1024×1024，30 色）原样转为 OI 01 08；原画朝向 270（MSD 200 为 90）。
- 数值：生命 Lv40 12000（用户指定）；其余为 MSA 860 的值，暂定（用户 2026-10-22：先用 MSA 原值）：AP 800，普攻 / 绝招每颗陨石 Lv40 1200
  （= 200 的 1200），移速 0.5，远攻击距离 600，投射距离 900，目标数 999，弹速 6 / 8，攻击等待 40 / 15，绝招冷却 300、首次 150；
  出击时间按 MSA → MSD 的比例（侵略者 700 → 550、飞行侵略者 900 → 700，约 0.78）由 MSA 3000 换算为 200 的 700 × 10/3 ≈ 2334；
  价格 MSA 为 0（活动单位），暂取原版同为 AP 800 的侵略者阵营单位生化腦機器人 195 的 330 勋章。陨石生命为单位最大生命的 60%
  （MSA calcHp 为两项状态值之积 / 100，其状态编号未能对应到 MSD，60 为推定，行为参数 meteor_hp_percent）。
- R2（2026-10-22，用户指定，AGENTS 第 228 节）：每颗陨石的普攻 / 绝招伤害改为 1200 / 8 = 150（`damage_multiplier` [1, 8]，
  同时缩放普攻与绝招；MSA 的 8 颗陨石各自结算，按 MSA 原值一次攻击对单个目标最多 9600）；生命改为 Lv40 24000
  （`hp_multiplier` [40, 9]，击退门槛倍率随之联动）。陨石生命随之为 14400。其余数值不变。
- R3（2026-10-23，用户：MSA 中的移速若与现行不同则 × 2）：MSA 已开放的 858 移速 1.5，现行 0.5 取自未开放的 860，
  故移速改为 1.0（`move_speed_multiplier` [1, 6] → [1, 3]）。
- 头像：MSA unit_icon_02.obme 中本单位的原格（m_unit_misc.pict 674 → (1417,179) 40×40，锚点 [−5, −5]），写在 (1850,768)。
  名称与说明取 MSA 主数据表（简体中文名称为用户用语“飞行护盾”，与 MSA 相同）。
运行：E:\\anaconda3\\python.exe -I artwork/flying_shell_20261022/build_flying_shell.py [--preview]
"""
from pathlib import Path
import copy
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MSA_UNIT = Path(r'F:\egg\research\metal_slug_attack\decoded\units\0858')
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
KEY = 's1xlv.flying_shell'
FILE = 'flying_shell.json'
TEXTURE = 'flying_shell.obm'
DESCRIPTOR = 'flying_shell_descriptor.json'
BASE = 200
SLOT_FROM = {10: 11, 11: 13}         # MSD 槽 ← MSA 槽（其余同号）
SUBLAYER_OPS = (10, 11, 12, 22)
MSA_ONLY = range(24, 73)
SUBLAYER_MSA = 36
SHELL = {'height': 80, 'homing_animation': 45, 'arc_first_animation': 47, 'arc_count': 2,
         'rain_first_animation': 49, 'rain_count': 4}
ICON_CELL = (1417, 179, 40, 40)      # MSA 头像图集中的飞行护盾（pict 674）
ICON = {'page': 1, 'rect': [1850, 768, 40, 40], 'anchor': [-5, -5]}
PROVISIONAL = {   # 生命与每颗陨石伤害为用户指定（R2），AP 650 为用户指定（2026-10-22，原 MSA 800）；其余为 MSA 860 的值或换算（暂定）
    'ap': 650, 'shop_price': 330, 'hp_multiplier': [40, 9], 'damage_multiplier': [1, 8],
    # 移速：R3（用户 2026-10-23：MSA 已开放的 858 为 1.5，与 860 的 0.5 不同，按用户要求 × 2）200 的 3 × 1/3 = 1.0（此前 [1, 6] 即 0.5）
    'move_speed_multiplier': [1, 3], 'production_interval_multiplier': [10, 3],
    'status_word_values': {'7': 600, '24': 999, '26': 900, '27': 40, '31': 999, '33': 900, '34': 15, '35': 300, '36': 150},
    'status_float_values': {'25': 6, '32': 8},
}
ONES = ('special_damage_multiplier', 'attack_wait_multiplier', 'attack_range_multiplier',
        'knockback_distance_multiplier', 'ballistic_range_multiplier')


def transform(record):
    stats = {'sublayer_to_op11': 0, 'removed_msa_only': {}, 'bullet_state_zeroed': 0, 'sounds': {}}
    animations = {}
    for slot in range(record['script_count']):
        out = []
        for c in record['scripts'][SLOT_FROM.get(slot, slot)]:
            op, v = c[0], list(c[1:])
            if op == SUBLAYER_MSA:
                op = 11
                stats['sublayer_to_op11'] += 1
            elif op in MSA_ONLY:
                stats['removed_msa_only'][str(op)] = stats['removed_msa_only'].get(str(op), 0) + 1
                continue
            if op in SUBLAYER_OPS:
                assert v[0] not in SLOT_FROM.values() or v[0] == 13, (slot, c)
                if op == 22 and v[1] != 0:
                    v[1] = 0
                    stats['bullet_state_zeroed'] += 1
            elif op == 23:
                stats['sounds'][v[0]] = stats['sounds'].get(v[0], 0) + 1
            out.append({'opcode': op, 'values': v})
        animations[str(slot)] = out
    return animations, stats


def descriptor(record):
    assert 0xffffffff not in record['frames']
    return {'rects': [list(r) for r in record['rects']], 'frames': list(record['frames']),
            'script_count': record['script_count'], 'hit_bounds': record['hit_bounds'],
            'attack_bounds': record['attack_bounds']}


def preview_record(record, animations):
    r = copy.deepcopy(record)
    r['scripts'] = [[[c['opcode'], *c['values']] for c in animations[str(i)]] for i in range(record['script_count'])]
    return r


def localization():
    texts = json.loads(MSA_TEXTS.read_text(encoding='utf-8'))['858']
    return {lang: {'name': t['name'], 'description': t['description']} for lang, t in texts.items()}


def unit_file(animations):
    p = PROVISIONAL
    return {'key': KEY, 'base_id': BASE, 'faction': 3, 'identity': 'Invader',
            'shop_price': p['shop_price'], 'available_from_start': True, 'ap': p['ap'],
            'hp_multiplier': p['hp_multiplier'],
            # 击退门槛随生命倍率联动（第 6.1 节）；200 为 −1（加载器只缩放正值），不被击退由行为 no_knockback 实现
            'knockback_threshold_multiplier': list(p['hp_multiplier']),
            'damage_multiplier': p['damage_multiplier'], 'move_speed_multiplier': p['move_speed_multiplier'],
            **{k: [1, 1] for k in ONES},
            'production_reference_id': BASE, 'production_interval_multiplier': p['production_interval_multiplier'],
            'status_word_values': p['status_word_values'], 'status_float_values': p['status_float_values'],
            'image_direction': 270, 'special_effect_size': [280, 90], 'minimap_marker': [12, 10],
            'icon': ICON, 'textures': [TEXTURE], 'sprite_descriptor': DESCRIPTOR, 'animations': animations,
            'localization': localization(), 'tags': ['ms6', 'msa'],
            'behaviors': [{'name': 'no_knockback', 'version': 1, 'params': {}},
                          {'name': 'flying_shell', 'version': 1, 'params': SHELL}]}


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
    assert record['names'] == ['Flying_shell_out.obm'] and record['script_count'] == 53
    atlas = Image.open(MSA_UNIT / (record['names'][0] + '.png')).convert('RGBA')
    animations, stats = transform(record)
    desc = descriptor(record)
    unit = unit_file(animations)
    obm = indexed_obm(atlas)
    x, y, iw, ih = ICON_CELL
    cell = Image.open(MSA_ICONS).convert('RGBA').crop((x, y, x + iw, y + ih))
    cell.save(HERE / 'source' / f'msa_icon_flying_shell_{x}_{y}.png')
    report = {'stats': stats, 'colors': len(set(atlas.getdata())), 'obm_bytes': len(obm), 'provisional': PROVISIONAL}
    pr = preview_record(record, animations)
    lengths = {}
    for slot in (0, 6, 8, 9, 10, 11):
        sim = msa_unit.Sim(pr, [atlas])
        sim.start(slot)
        frames, t = [], 0
        while t < 80:
            if t % 4 == 0:
                frames.append(sim.draw((640, 480), (320, 360), 1))
            sim.step()
            t += 1
            if sim.root.done:
                break
        lengths[slot] = t
        sheet = Image.new('RGB', (320 * min(len(frames), 10), 240 * ((len(frames) + 9) // 10)), (40, 40, 40))
        for i, im in enumerate(frames):
            sheet.paste(im.convert('RGB').resize((320, 240), Image.NEAREST), ((i % 10) * 320, (i // 10) * 240))
        sheet.save(OUT / f'preview_slot{slot:02d}.png')
    report['preview_ticks'] = lengths
    if '--preview' in sys.argv:
        print(json.dumps(report, ensure_ascii=False))
        return
    index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
    if KEY not in index['unit_ids']:
        index['unit_ids'][KEY] = max(index['unit_ids'].values()) + 1
    (CONTENT / TEXTURE).write_bytes(obm)
    index['assets'][TEXTURE] = hashlib.blake2b(obm, digest_size=32).hexdigest()
    (CONTENT / 'unit_icon_02.obm').write_bytes(write_icon(cell))   # 该资源的摘要在 content.json 中为 null，保持不变
    save_json(CONTENT / DESCRIPTOR, desc)
    save_json(CONTENT / 'units' / FILE, unit)
    save_json(CONTENT / 'content.json', index)
    report['unit_id'] = index['unit_ids'][KEY]
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
