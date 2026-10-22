"""蜈蚣长老（ELDER CENTIPEDE）按 MSA 7.13.0 原始动作记录移植（2026-10-22，AGENTS 第 216 节；行为 elder_centipede，核心 r80）。

来源：F:\\egg\\research\\metal_slug_attack\\decoded\\units\\1234（动作类 BattleAction_Eldercentipedo；图集 elder_centipedo_out.obm
1024×1024、elder_centipedo_ef_out.obm 512×512，矩形 330、帧 660、脚本 284）。反汇编与对照见 verification/elder_centipede_20261022/。
- 原生动作类：MSD 原版侵略者 192（BattleAction_Alien）。其 update 对本单位整体由行为 elder_centipede（核心 r80）按 MSA
  BattleAction_Eldercentipedo::update 的状态与动作顺序执行，动作号即脚本号（与 MSA 相同，不重排）：出土 7、出土（地下发起）9、
  待机 11、钻地 16、地下移动 23、喷酸 28、喷酸收尾 32、绝招入地 44、大前行 50、受击 60 / 65、击退 70、损毁 75。
- 脚本转换：
  * MSA 专有空操作指令（24–33、47–58）删除。
  * op45 / op46（对象或子层的速度与加速度，÷100；根层另乘精灵缩放）改为 op7：MSD 根层 op7 经 onEventMoveAnimation 设定对象速度
    （同样 ÷100 并乘精灵缩放、按朝向翻转，只在第一遍执行），子层 op7 设定子层自身速度（÷100），与 MSA 两指令的换算相同。
  * op42（子层偏移累加）改为 op14（设定偏移）：值为挂载该子层的父层 op11 偏移加 op42 的增量（各脚本在已用动作中只有一种父层偏移，
    逐一断言）。
  * op12（独立对象）中，MSA createObject（0xe46ac4）建立为“随父对象动作存在”的部件对象（类型 A / C：身体各节；类型 B：喷酸时的
    头部 30 及其喷口 161、162、飞沫发射脚本 157）与绝招中不建立、由 drawSpAttack 自行绘制的圆环各节（52、242–266），改为 op11
    子层：随单位动作切换消失、与单位一同按地面裁切绘制；圆环各节的位置、旋转与显隐由行为每 tick 写入。其余 op12（尘土、碎块、
    地面泥土、绝招泥土 132 等）保持独立效果对象。
  * op22 的第 2 个值（MSA 为绘制优先级）保留；弹体由行为按脚本号发射：地面攻击 18 / 20 以绝招组结算（MSA shotBullet 以 0x32 建立），
    飞沫 35–42 以普攻组结算、命中或落地时放溅射 43（MSA 0x4c40430 以 0x28 建立，命中效果 0x2b）。
  * op23 的 MSA 音效号改为本体音效键（MSA 原文件 .msa 复制为 .msdf，音量取 m_sound_data）。
- 数值：生命 Lv40 50000（用户指定，192 的 6000 × 25/3）；其余为 MSA 1234 的值（暂定，用户 2026-10-22：先用 MSA 原值，暂定期间
  不同步运行目录）：AP 600、远攻击距离 300、普攻（强酸喷射）与绝招（蜈蚣大前行）Lv40 9000（192 的 1060 × 450/53；绝招 2400 ×
  450/53 × 53/120）、目标数 999、投射距离 150 / 1500、攻击等待 40 / 绝招等待 50、绝招冷却 250、首次 200、移速 5（192 的 3 × 5/3）、
  击退门槛 300（192 的 20 × 15）、出击时间 MSA 2600 按 700 → 550 的比例为 192 的 × 26/7。无近距离攻击（词 6 写 0）。价格 MSA 为 0，
  保持 192 的 150。版本技能（甲虫装甲、食人细菌、古代细菌、强化大前行）不实施。
- 头像：MSA unit_icon_02.obme 原格（m_unit_misc.pict 939 → (1585,590) 43×46，锚点 [−5, 1]），写在 (1900,768)。
  名称与说明取 MSA 主数据表。
R2（2026-10-22，用户实机报告钻地时头部下落、全身无受击判定、毒液半路消失，并指定伤害；verification/elder_centipede_r2_20261022/）：
- 受击框：MSA 的受击框 4 / 5 只在头部（精灵单位 y −170…−106，MSD onEventSetHitRect ×2 后离地 212–340），MSD 的地面单位弹体与近战
  攻击框够不到。追加 3 个受击框（MSA 原有 9 个保持）：9 为立起身体的外接矩形（各动作逐 tick 模拟所得，body_bounds.py），10 / 11 为
  入地动作的受击框 7 / 8 向下延至地面；各脚本的 op3 4、5 → 9，7 → 10，8 → 11（op3 在子层中同样设定单位受击框）。地下移动仍无受击框。
  MSD BattleObject::setAnimationID_SkipUpdate 在每次切换动作时把受击框右下 +0xd4 / +0xd8 清零（getHitRect 视为无受击框），MSA 则沿用
  上一动作的受击框；无 op3 的受击 60 / 65、击退 70、大前行 50 与大前行后出土 7 另补 op3（60 / 65 / 70 → 9、50 → 11 于开头，7 → 9 于
  与出土 9 的 op3 5 相同的位置）。损毁 75 不设。
- 部件结束：MSA 的部件对象（op12，类型 A / C）在自身动画结束时移除；改为 op11 子层后，MSD 子层脚本结束（op21）只停止脚本，子层仍按
  末帧绘制、速度与加速度继续累加。钻地动作 16 的部件 92（立起的身体，16 tick）结束后其头部 139 停在末帧随加速度一直下落（实机所见
  “头部直接掉下去”）；受击动作 60 的第一组 7 节（182–236）结束后停在原处与第二组重叠。这 8 个脚本在 op21 前补 op0 −1（结束时隐藏），
  只用于这些位置（139 只由 92 引用，182–236 另由未使用的槽 61 / 69 引用）。
- 飞沫：MSD BattleBullet::update 在弹体越过目的 x（发射者 ± 投射距离，状态词 26）时交给弹体动作结束；MSA 飞沫发射（0xe47a9c，
  经 0x10e3de0）以 −9999 为射程（不限）。状态词 26 由 MSA 的 150 改为 1500（飞沫在落地、命中或动画结束时移除）；数据行 +0x370
  （AI 攻击距离）随之为 1500，原生 AI 只按是否大于 79 区分远程，判断不变。
- 伤害（用户指定）：每滴毒液（远距离攻击）Lv40 1500、钻地大招（绝招组）Lv40 8000：damage_multiplier [1, 1]、normal_damage_multiplier
  [75, 53]（192 的 1060 → 1500）、special_damage_multiplier [10, 3]（192 的 2400 → 8000）。地面攻击 18 / 20（钻地、出土与大前行）、
  大前行头部与酸块按 MSA 同属绝招组。
R3（2026-10-22，用户）：每滴毒液 250（对据点一次喷酸约 24 滴命中，合计 6000）、钻地大招 6000：normal_damage_multiplier [25, 106]
（192 的 1060 → 250）、special_damage_multiplier [5, 2]（192 的 2400 → 6000）。
R4（2026-10-23，用户）：绝招组每次命中 667（special_damage_multiplier [667, 2400]）。大前行中圆环各节越过地面处各生成一次地面攻击，
与头部、酸块各自结算，一次大前行对同一目标命中多次（LAB：敌方据点 9 次、SLUG GIGANT 7 次），R3 的每次 6000 使合计约 54000；
用户选择保留多次命中、每次 667（据点合计约 6000）。钻地与出土的地面攻击同属绝招组，同为每次 667。
运行：E:\\anaconda3\\python.exe -I artwork/elder_centipede_20261022/build_elder_centipede.py [--report]
"""
from pathlib import Path
import hashlib
import json
import shutil
import struct
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MSA_UNIT = Path(r'F:\egg\research\metal_slug_attack\decoded\units\1234')
MSA_DATA = Path(r'F:\egg\research\metal_slug_attack\data\files')
MSA_ICONS = Path(r'F:\egg\research\metal_slug_attack\decoded\unit_icons\unit_icon_02.obme.png')
MSA_TEXTS = REPO / 'verification' / 'ravenous_invader_20261022' / 'msa_texts.json'

from PIL import Image  # noqa: E402

_PVZ = REPO / 'artwork' / 'pvz_zombies_20261012' / 'build_pvz_zombies.py'
_src = _PVZ.read_text(encoding='utf-8')
_src = _src.replace("sys.path.insert(0, str(RT / 'packages'))", "").replace("os.add_dll_directory(str(RT / 'native'))", "")
pvz = type(sys)('pvzb')
pvz.__dict__['__file__'] = str(_PVZ)
exec(compile(_src, str(_PVZ), 'exec'), pvz.__dict__)
indexed_obm, save_json = pvz.indexed_obm, pvz.save_json

CONTENT = REPO / 'community_content'
OUT = HERE / 'out'
KEY = 's1xlv.elder_centipede'
FILE = 'elder_centipede.json'
TEXTURES = ('elder_centipede_0.obm', 'elder_centipede_1.obm')
DESCRIPTOR = 'elder_centipede_descriptor.json'
BASE = 192
MSA_NOOP = set(range(24, 34)) | set(range(47, 59))
# MSA createObject 跳转表 0x467c36c（verification/elder_centipede_20261022/script_tree.py）
TYPE_A = {92, 93, 95, 143, 164}
TYPE_B = {30}
TYPE_C = {63, 64, 66, 138, 182, 184, 186, 188, 192, 194, 196, 197, 201, 203, 205, 206, 210, 212, 214, 215, 219, 221, 223,
          224, 228, 230, 232, 233, 236, 238, 240, 241}
HEAD_PARTS = {157, 161, 162}          # 头部 30 的喷口与飞沫发射脚本（MSA 0x4c40430 / 0x4c40438，随头部存在）
WHEEL = {52, *range(242, 267)}        # 绝招圆环各节（MSA 不建立，drawSpAttack 绘制）
TO_OP11 = TYPE_A | TYPE_B | TYPE_C | HEAD_PARTS | WHEEL
USED = (7, 9, 11, 16, 23, 28, 32, 44, 50, 51, 60, 65, 70, 75)
# 大前行（MSA 槽 50；51 为版本技能“强化大前行”的两周版，不使用）：前 26 条 op11 为圆环各节，MSA 节偏移表 0x467c474 与之逐项相同。
# 圆环中心在单位前方 140 精灵单位处（MSA getSpAttackPartsPos）。
MARCH_SLOTS = (50, 51)
WHEEL_CENTER = 140
SOUNDS = {   # MSA SoundID → (本体音效键, MSA 文件, 音量 m_sound_data)
    1359: ('s1xlv.ecentipede_death', 'elder_vo_dth.msa', 110),
    2190: ('s1xlv.ecentipede_move1', 'olds_move1.msa', 110),
    2191: ('s1xlv.ecentipede_move2', 'olds_move2.msa', 100),
    2203: ('s1xlv.ecentipede_sand_rise', 'sand_rise_mid.msa', 100),
    2273: ('s1xlv.ecentipede_spray1', 'elder_1.msa', 90),
    2274: ('s1xlv.ecentipede_spray2', 'elder_2.msa', 70),
    2275: ('s1xlv.ecentipede_spray3', 'elder_3.msa', 60),
}
CENTIPEDE = {   # 行为 elder_centipede 的参数（MSA 动作号）
    'appear_animation': 7, 'emerge_animation': 9, 'neutral_animation': 11, 'burrow_animation': 16,
    'underground_animation': 23, 'long_attack_animation': 28, 'long_attack_end_animation': 32,
    'dive_animation': 44, 'march_animation': 50, 'flinch_animation': 60, 'flinch_loop_animation': 65,
    'knockback_animation': 70, 'death_animation': 75, 'smoke_first_animation': 86, 'wheel_parts': 26,
    'ground_hit_animation': 18, 'ground_hit_alt_animation': 20, 'droplet_first_animation': 35, 'droplet_count': 8, 'splash_animation': 43,
    'march_blob_animation': 116, 'march_blob_hit_animation': 115, 'march_dirt_animation': 132, 'ground_dust_animation': 19,
}
ICON_CELL = (1585, 590, 43, 46)
ICON = {'page': 1, 'rect': [1900, 768, 43, 46], 'anchor': [-5, 1]}
PROVISIONAL = {
    # AP 850 为用户指定（2026-10-22，原 MSA 600）
    'ap': 850, 'shop_price': 150, 'hp_multiplier': [25, 3], 'knockback_threshold_multiplier': [15, 1],
    # R3（用户 2026-10-22）：每滴毒液 250；R4（用户 2026-10-23）：绝招组每次命中 667（R3 为 6000，R2 为 8000）
    'damage_multiplier': [1, 1], 'normal_damage_multiplier': [25, 106], 'special_damage_multiplier': [667, 2400],
    'move_speed_multiplier': [5, 3], 'production_interval_multiplier': [26, 7],
    # R2：词 26 由 MSA 的 150 改为 1500（MSA 飞沫射程不限，见文首）
    'status_word_values': {'6': 0, '7': 300, '24': 999, '26': 1500, '27': 40, '31': 999, '33': 1500, '34': 50, '35': 250, '36': 200},
}
# R2 受击框（精灵单位 [x, y, 宽, 高, 0]，原画坐标）：9 立起身体（动作 9 / 11 / 28 / 32 / 60 / 65 / 70 的外接矩形约 x −34…128、
# y −176…0），10 / 11 为 MSA 受击框 7 / 8 向下延至地面（入地动作 44 与其后的大前行）。
HIT_BOUNDS_R2 = [[-34, -176, 162, 176, 0], [-44, -183, 73, 183, 0], [-153, -207, 67, 207, 0]]
HIT_REMAP = {4: 9, 5: 9, 7: 10, 8: 11}
HIDE_AT_END = {139, 182, 192, 201, 210, 219, 228, 236}   # R2：部件结束时隐藏（见文首）
HIT_INSERT = {7: (36, 9), 50: (0, 11), 60: (0, 9), 65: (0, 9), 70: (0, 9)}   # R2：槽 → （MSA 指令序号, 受击框），在该指令前补 op3
ONES = ('attack_wait_multiplier', 'attack_range_multiplier', 'knockback_distance_multiplier', 'ballistic_range_multiplier')


def parent_offsets(record):
    """各脚本在已用动作树中被 op11 / op12 挂载时的偏移（op42 换算用）。"""
    seen, out = set(), {}

    def walk(s):
        if s in seen:
            return
        seen.add(s)
        for c in record['scripts'][s]:
            if c[0] in (11, 12, 36):
                out.setdefault(c[1], set()).add((c[3], c[4]))
                walk(c[1])
    for u in USED:
        walk(u)
    return out


def transform(record):
    offsets = parent_offsets(record)
    stats = {'removed_msa_noop': {}, 'op45_46_to_op7': 0, 'op42_to_op14': {}, 'op12_to_op11': 0, 'wheel_parts': {}, 'sounds': {}}
    animations = {}
    for slot in range(record['script_count']):
        out = []
        for k, c in enumerate(record['scripts'][slot]):
            if slot in HIT_INSERT and k == HIT_INSERT[slot][0]:
                out.append({'opcode': 3, 'values': [HIT_INSERT[slot][1]]})
                stats.setdefault('op3_insert', []).append(slot)
            op, v = c[0], list(c[1:])
            if op in MSA_NOOP:
                stats['removed_msa_noop'][str(op)] = stats['removed_msa_noop'].get(str(op), 0) + 1
                continue
            if op in (45, 46):
                op = 7
                stats['op45_46_to_op7'] += 1
            elif op == 42:
                parents = offsets.get(slot)
                assert parents is None or len(parents) == 1, (slot, parents)
                px, py = next(iter(parents)) if parents else (0, 0)
                op, v = 14, [px + v[0], py + v[1]]
                stats['op42_to_op14'][str(slot)] = v
            elif op == 12 and v[0] in TO_OP11:
                op = 11
                stats['op12_to_op11'] += 1
                if slot in MARCH_SLOTS and v[0] in WHEEL:
                    v[2] = v[2] - WHEEL_CENTER     # 角度 0 时的位置（原画坐标，前方为 −x）；行为按 x + 140 还原 MSA 节偏移
                    stats['wheel_parts'][str(slot)] = stats['wheel_parts'].get(str(slot), 0) + 1
            elif op == 23:
                stats['sounds'][str(v[0])] = stats['sounds'].get(str(v[0]), 0) + 1
                v = [SOUNDS[v[0]][0]]
            elif op == 3 and v[0] in HIT_REMAP:
                v = [HIT_REMAP[v[0]]]
                remap = stats.setdefault('op3_remap', {})
                remap[str(slot)] = remap.get(str(slot), 0) + 1
            assert op <= 23, (slot, c)
            if op == 21 and slot in HIDE_AT_END:
                assert out[-1]['opcode'] in (1, 16) and any(c['opcode'] == 0 for c in out) and \
                    [c for c in out if c['opcode'] == 0][-1]['values'] != [-1], slot
                out.append({'opcode': 0, 'values': [-1]})
                stats.setdefault('hide_at_end', []).append(slot)
            out.append({'opcode': op, 'values': v})
        animations[str(slot)] = out
    return animations, stats


def descriptor(record):
    assert 0xffffffff not in record['frames']
    assert len(record['hit_bounds']) == 9
    return {'rects': [list(r) for r in record['rects']], 'frames': list(record['frames']),
            'script_count': record['script_count'], 'hit_bounds': record['hit_bounds'] + HIT_BOUNDS_R2,
            'attack_bounds': record['attack_bounds']}


def localization():
    texts = json.loads(MSA_TEXTS.read_text(encoding='utf-8'))['1234']
    return {lang: {'name': t['name'], 'description': t['description']} for lang, t in texts.items()}


def unit_file(animations):
    p = PROVISIONAL
    return {'key': KEY, 'base_id': BASE, 'faction': 3, 'identity': 'Invader',
            'shop_price': p['shop_price'], 'available_from_start': True, 'ap': p['ap'],
            'hp_multiplier': p['hp_multiplier'],
            # 击退门槛取 MSA 原值 300（用户 2026-10-22：生命以外先用 MSA 原值；第 6.1 节注明的例外）
            'knockback_threshold_multiplier': p['knockback_threshold_multiplier'],
            'damage_multiplier': p['damage_multiplier'], 'normal_damage_multiplier': p['normal_damage_multiplier'],
            'special_damage_multiplier': p['special_damage_multiplier'],
            'move_speed_multiplier': p['move_speed_multiplier'],
            **{k: [1, 1] for k in ONES},
            'production_reference_id': BASE, 'production_interval_multiplier': p['production_interval_multiplier'],
            'status_word_values': p['status_word_values'],
            'image_direction': 270, 'special_effect_size': [90, 125], 'minimap_marker': [16, 16],
            'icon': ICON, 'textures': list(TEXTURES), 'sprite_descriptor': DESCRIPTOR, 'animations': animations,
            'localization': localization(), 'tags': ['ms6', 'msa'],
            'behaviors': [{'name': 'elder_centipede', 'version': 1, 'params': CENTIPEDE}]}


def write_icon(cell):
    raw = bytearray((CONTENT / 'unit_icon_02.obm').read_bytes())
    assert raw[:4] == b'OI\x01\x20'
    w, h = struct.unpack_from('<HH', raw, 4)
    ax, ay, iw, ih = ICON['rect']
    assert ax + iw <= w and ay + ih <= h
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
    assert record['names'] == ['elder_centipedo_out.obm', 'elder_centipedo_ef_out.obm'] and record['script_count'] == 284
    atlases = [Image.open(MSA_UNIT / (n + '.png')).convert('RGBA') for n in record['names']]
    animations, stats = transform(record)
    desc = descriptor(record)
    unit = unit_file(animations)
    obms = [indexed_obm(a) for a in atlases]
    x, y, iw, ih = ICON_CELL
    cell = Image.open(MSA_ICONS).convert('RGBA').crop((x, y, x + iw, y + ih))
    cell.save(HERE / 'source' / f'msa_icon_elder_centipede_{x}_{y}.png')
    report = {'stats': stats, 'colors': [len(set(a.getdata())) for a in atlases], 'obm_bytes': [len(o) for o in obms],
              'provisional': PROVISIONAL}
    if '--report' in sys.argv:
        print(json.dumps(report, ensure_ascii=False))
        return
    index = json.loads((CONTENT / 'content.json').read_text(encoding='utf-8'))
    if KEY not in index['unit_ids']:
        index['unit_ids'][KEY] = max(index['unit_ids'].values()) + 1
    for name, raw in zip(TEXTURES, obms):
        (CONTENT / name).write_bytes(raw)
        index['assets'][name] = hashlib.blake2b(raw, digest_size=32).hexdigest()
    # 已登记的音效条目原位更新、未登记的追加（保持其他内容追加的条目的次序）
    sounds = list(index.get('sounds', []))
    for key, source, volume in SOUNDS.values():
        target = key.split('.', 1)[1] + '.msdf'
        shutil.copyfile(MSA_DATA / source, CONTENT / target)
        entry = {'key': key, 'file': target, 'type': 'se', 'volume': volume}
        at = next((i for i, e in enumerate(sounds) if e['key'] == key), None)
        if at is None:
            sounds.append(entry)
        else:
            sounds[at] = entry
    index['sounds'] = sounds
    (CONTENT / 'unit_icon_02.obm').write_bytes(write_icon(cell))   # 该资源的摘要在 content.json 中为 null，保持不变
    save_json(CONTENT / DESCRIPTOR, desc)
    save_json(CONTENT / 'units' / FILE, unit)
    save_json(CONTENT / 'content.json', index)
    report['unit_id'] = index['unit_ids'][KEY]
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
