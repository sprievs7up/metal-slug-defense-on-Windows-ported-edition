"""侵略者之王（INVADER KING）按 MSA 7.13.0 原始动作记录移植（2026-10-22；行为 invader_king，核心 r82）。

来源：F:\\egg\\research\\metal_slug_attack\\decoded\\units\\1426（动作类 BattleAction_InvaderKing；图集 504100invader_king_01–05_out.obm，
四张 2048×2048、一张 2048×1024，矩形 536、帧 1072、脚本 90）。反汇编与对照见 verification/invader_king_20261022/。
- 原生动作类：MSD 原版侵略者 192（BattleAction_Alien）。其 update 对本单位整体由行为 invader_king 按 MSA
  BattleAction_InvaderKing::update 的状态与动作顺序执行，动作号即脚本号（与 MSA 相同，不重排）：待机 6、落下 7、着地踏击 8、
  近距攻击 10、跃起 11、绝招 12 → 13 → 15、击退（反击激光）16、损毁 18、受击 19 → 20；菜单 0（待机）、1（远距攻击演示）、2（绝招演示）。
- 脚本转换：
  * MSA 专有空操作指令（24–33、47–58）删除；op38（不透明度）删除（MSD 无此指令，MSA 各处为 100%）。
  * op34 / op35（onEventEveryTimeAtk）删除。近距攻击（10）的吐息段在 MSA 以 op35 打开逐次判定，改为在每次火焰音效（op23 643）处
    重新开启攻击框 2（第 41、47、55、61、69、75 tick，共 6 次）；行为对本单位置身体状态 0x20，使每次开启都建立新的攻击 ID。
  * op36（只在第一遍执行的挂子层）改为 op11；op45（对象或子层的速度与加速度）改为 op7（同蜈蚣长老）。
  * 激光弹体：MSA 的绘制按角度把激光身体段逐段重复（0xef1598）。天空激光 35–40 与反击激光 34 追加挂身体段的 op11（44 / 41，
    偏移为头部长度 41 原画像素），由行为每 tick 按激光长度拉伸该子层；地面激光 49–54 的根层即身体段，由行为拉伸根层。
  * op23 的 MSA 音效号改为本体音效键（MSA 原文件 .msa 复制为 .msdf，音量取 m_sound_data）。
  * 编队页（原生 CreateDeckObject 以动作 0 原尺寸绘制）：菜单待机 0 改为空根层挂两个追加的缩放副本——原槽 0 的帧（脚本 91）与
    其子层 22（脚本 90），各加 op19 [40,40]（父层 op19 不作用于子层），比例同钢铁哨兵的菜单槽（原生 IRON SLIDER）；本单位原点在
    身体前缘，两子层右移 MENU_SHIFT 原画像素，使缩小后的身体居于编队格。单位菜单的动作演示的待机用战斗待机 6
    （按画框缩放），远距与绝招演示为 MSA 菜单槽 1、2。
- 数值：生命 Lv40 100000、AP 999、出击（再出击）150 秒为用户指定（2026-10-22）；R2（用户同日）：近距攻击（攻击 1，火焰）Lv40 4400、
  远距攻击（攻击 2，跃起踏击）6000、远距攻击间隔 6 秒（词 27 = 180 帧）、绝招（攻击 3，激光，爆炸）9000 不变、首次冷却 15 秒（词 36 =
  450）、冷却 25 秒（词 35 = 750）；R3（用户同日）：近距等待（词 20）与绝招攻击间隔（词 34）亦为 6 秒（180）；R6（核心 r88）跃起间隔
  （词 27）10 秒（300）、生命 Lv40 60000；R7（用户 2026-10-23）跃起间隔 3 秒（词 27 = 90，出击着地后的等待同）；R8（同日）5 秒（词 27 = 150）；R9（同日）改回 3 秒（词 27 = 90）。其余为 MSA 1426 进化 1
  的值（暂定）：损毁爆炸（攻击 4）= 攻击 2 × 2/3（MSA 各等级同比，R2 后 Lv40 4000）、目标数 999、近 / 远攻击距离 100 / 1500、
  投射距离 1500、第二参数 300 / 300 / 1、
  击退门槛 99（MSA 值；第 6.1 节注明的例外）。价格 MSA 无勋章价，保持 192 的 150。
  版本技能（提亚马特、盾、太阳、马尔杜克）与狂热时光不实施。
- 头像：MSA unit_icon_02.obme 原格（m_unit_misc.pict 1072 → (1752,807) 40×40，锚点 [−5, −5]），写在 (1950,768)。
  名称与说明取 MSA 主数据表。
运行：E:\\anaconda3\\python.exe -I artwork/invader_king_20261022/build_invader_king.py [--report]
"""
from pathlib import Path
import hashlib
import json
import shutil
import struct
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MSA_UNIT = Path(r'F:\egg\research\metal_slug_attack\decoded\units\1426')
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
KEY = 's1xlv.invader_king'
FILE = 'invader_king.json'
TEXTURES = tuple(f'invader_king_{i}.obm' for i in range(5))
DESCRIPTOR = 'invader_king_descriptor.json'
BASE = 192
MSA_NOOP = set(range(24, 34)) | set(range(47, 59)) | {34, 35, 38}
BREATH_SLOT, BREATH_BOX, BREATH_SOUND = 10, 2, 643
BEAM_BODY = {34: (41, 41)} | {s: (44, 41) for s in range(35, 41)}   # 激光脚本 → (身体段脚本, 头部长度原画像素)
MENU_SLOT, MENU_BODY, MENU_SCALE, MENU_SHIFT = 0, 22, 40, 36   # 编队页缩小（追加脚本 90：子层 22 的副本，91：槽 0 帧的副本）
# 受击框（2026-10-23，AGENTS 第 250 节）：MSD BattleObject::setAnimationID_SkipUpdate 切换动作时清除受击框，MSA 沿用上一动作的受击框。
# 下列战斗动作的 MSA 脚本没有 op3（MSA 中沿用待机 6 的受击框 1），在 MSD 中播放期间本单位打不到；开头补 op3 1。损毁 18 不设（同原生）。
HIT_RECT_SLOTS = (7, 8, 11, 12, 13, 16, 19, 20)
HIT_RECT = 1
SOUNDS = {   # MSA SoundID → (本体音效键, MSA 文件, 音量 m_sound_data)
    643: ('s1xlv.iking_breath', 'cle_attack2.msa', 60),
    1391: ('s1xlv.iking_death_voice', 'shinrya_vo_dth.msa', 120),
    2097: ('s1xlv.iking_death_blast', 'exp_cloe.msa', 115),
    2215: ('s1xlv.iking_stomp', 'gwih_2.msa', 110),
    2382: ('s1xlv.iking_jump', 'gonge_jump.msa', 120),
    2417: ('s1xlv.iking_land', 'shinrya_land.msa', 95),
    2418: ('s1xlv.iking_laser', 'shinrya_atk.msa', 65),
    2419: ('s1xlv.iking_special', 'shinrya_sp.msa', 100),
}
KING = {   # 行为 invader_king 的参数（MSA 动作号）
    'neutral_animation': 6, 'fall_animation': 7, 'land_animation': 8, 'near_attack_animation': 10, 'jump_animation': 11,
    'special_start_animation': 12, 'special_animation': 13, 'special_end_animation': 15, 'knockback_animation': 16,
    'death_animation': 18, 'flinch_animation': 19, 'flinch_loop_animation': 20,
    'menu_neutral_animation': 6, 'menu_long_animation': 1, 'menu_special_animation': 2,
    'counter_laser_animation': 34, 'counter_laser_body_animation': 41, 'counter_burst_animation': 17,
    'sky_laser_first_animation': 35, 'sky_laser_count': 6, 'sky_laser_body_animation': 44,
    'ground_laser_first_animation': 49, 'ground_laser_count': 6, 'ground_impact_animation': 55,
}
ICON_CELL = (1752, 807, 40, 40)
ICON = {'page': 1, 'rect': [1950, 768, 40, 40], 'anchor': [-5, -5]}
PROVISIONAL = {
    # 用户指定：生命 Lv40 60000（R6，192 的 6000 × 10；初版 100000 = × 50/3）、AP 999、再出击 150 秒（192 的 550 帧 × 90/11 = 4500 帧）
    'ap': 999, 'shop_price': 150, 'hp_multiplier': [10, 1], 'production_interval_multiplier': [90, 11],
    # MSA 值：击退门槛 99（192 为 20）。伤害 R2（用户同日）：192 的 Lv40 近距 1500 / 远距 1060 / 绝招 2400 分别按词 15 / 22 / 29 的
    # 追加倍率换算为 4400 / 6000 / 9000（各自向下取整，damage_multiplier 为 1；初版 6028 / 90000 / 9000 以 damage_multiplier 4500/53）；
    # R7（用户 2026-10-23，核心 r89 激光每道各自结算）：绝招每道激光 Lv40 1000（2400 × 5/12），反击激光每道为其 9/2 即 4500（核心）
    'knockback_threshold_multiplier': [99, 20],
    'damage_multiplier': [1, 1], 'special_damage_multiplier': [5, 12], 'near_damage_multiplier': [44, 15],
    'normal_damage_multiplier': [300, 53],
    # 等待与冷却（帧，30 帧 = 1 秒）：R2 远距攻击间隔（词 27）77 → 180、绝招冷却（词 35）375 → 750、首次（词 36）250 → 450；
    # R3 近距等待（词 20）与绝招攻击间隔（词 34）77 → 180；R6（用户同日，核心 r88）每次跳跃的间隔（远距攻击间隔，词 27）180 → 300；
    # R7（用户 2026-10-23）出击着地后的等待与之后每次跳跃的间隔（同为词 27）300 → 90；R8（同日）90 → 150（5 秒）；
    # R9（同日，用户：5 秒太弱）150 → 90（3 秒）
    'status_word_values': {'6': 100, '7': 1500, '17': 999, '20': 180, '24': 999, '26': 1500, '27': 90,
                           '31': 999, '34': 180, '35': 750, '36': 450},
    'status_float_values': {'16': 300.0, '23': 300.0, '30': 1.0},
    'attack_attributes': {'melee': 1, 'normal': 0, 'special': 2},
}
ONES = ('move_speed_multiplier', 'attack_wait_multiplier', 'attack_range_multiplier', 'knockback_distance_multiplier',
        'ballistic_range_multiplier')


def transform(record):
    stats = {'removed_msa_noop': {}, 'op36_to_op11': 0, 'op45_to_op7': 0, 'breath_reopens': 0, 'beam_bodies': 0, 'sounds': {}}
    animations = {}
    for slot in range(record['script_count']):
        out = []
        for c in record['scripts'][slot]:
            op, v = c[0], list(c[1:])
            if op in MSA_NOOP:
                stats['removed_msa_noop'][str(op)] = stats['removed_msa_noop'].get(str(op), 0) + 1
                continue
            if op == 36:
                op = 11
                stats['op36_to_op11'] += 1
            elif op == 45:
                op = 7
                stats['op45_to_op7'] += 1
            elif op == 23:
                if slot == BREATH_SLOT and v[0] == BREATH_SOUND and any(x['opcode'] == 4 and x['values'] == [BREATH_BOX] for x in out):
                    if out[-1] != {'opcode': 4, 'values': [BREATH_BOX]}:   # 第 41 tick 原有开启框 2，其后的火焰处重新开启
                        out.append({'opcode': 4, 'values': [BREATH_BOX]})
                        stats['breath_reopens'] += 1
                stats['sounds'][str(v[0])] = stats['sounds'].get(str(v[0]), 0) + 1
                v = [SOUNDS[v[0]][0]]
            assert op <= 23, (slot, c)
            out.append({'opcode': op, 'values': v})
        if slot in BEAM_BODY:
            body, head = BEAM_BODY[slot]
            at = next(i for i, x in enumerate(out) if x['opcode'] in (0, 1))
            out.insert(at, {'opcode': 11, 'values': [body, 1, 0, head]})
            stats['beam_bodies'] += 1
        if slot in HIT_RECT_SLOTS:
            assert not any(x['opcode'] == 3 for x in out), slot
            out.insert(0, {'opcode': 3, 'values': [HIT_RECT]})
            stats['hit_rect_added'] = stats.get('hit_rect_added', 0) + 1
        animations[str(slot)] = out
    assert stats['breath_reopens'] == 5 and stats['beam_bodies'] == 7, stats
    # 编队页：菜单待机改为空根层挂两个缩放副本（原槽 0 的帧、子层 22），右移 MENU_SHIFT
    extra = record['script_count']
    scale = {'opcode': 19, 'values': [MENU_SCALE, MENU_SCALE]}
    menu = animations[str(MENU_SLOT)]
    assert [x for x in menu if x['opcode'] == 11] == [{'opcode': 11, 'values': [MENU_BODY, 0, 0, 0]}], menu[:3]
    animations[str(extra)] = [scale] + animations[str(MENU_BODY)]
    animations[str(extra + 1)] = [scale] + [x for x in menu if x['opcode'] != 11]
    animations[str(MENU_SLOT)] = [{'opcode': 11, 'values': [extra + 1, 0, MENU_SHIFT, 0]},
                                  {'opcode': 11, 'values': [extra, 1, MENU_SHIFT, 0]},
                                  {'opcode': 0, 'values': [-1]}, {'opcode': 1, 'values': [24]}, {'opcode': 5, 'values': []}]
    stats['menu_scaled'] = {'slot': MENU_SLOT, 'copies': [extra, extra + 1], 'scale': MENU_SCALE, 'shift': MENU_SHIFT}
    return animations, stats


def descriptor(record):
    assert 0xffffffff not in record['frames']
    return {'rects': [list(r) for r in record['rects']], 'frames': list(record['frames']),
            'script_count': record['script_count'] + 2, 'hit_bounds': record['hit_bounds'],
            'attack_bounds': record['attack_bounds']}


def localization():
    texts = json.loads(MSA_TEXTS.read_text(encoding='utf-8'))['1426']
    return {lang: {'name': t['name'], 'description': t['description']} for lang, t in texts.items()}


def unit_file(animations):
    p = PROVISIONAL
    return {'key': KEY, 'base_id': BASE, 'faction': 3, 'identity': 'Invader',
            'shop_price': p['shop_price'], 'available_from_start': True, 'ap': p['ap'],
            'hp_multiplier': p['hp_multiplier'],
            'knockback_threshold_multiplier': p['knockback_threshold_multiplier'],
            'damage_multiplier': p['damage_multiplier'], 'special_damage_multiplier': p['special_damage_multiplier'],
            'near_damage_multiplier': p['near_damage_multiplier'], 'normal_damage_multiplier': p['normal_damage_multiplier'],
            **{k: [1, 1] for k in ONES},
            'production_reference_id': BASE, 'production_interval_multiplier': p['production_interval_multiplier'],
            'status_word_values': p['status_word_values'], 'status_float_values': p['status_float_values'],
            'attack_attributes': p['attack_attributes'],
            'image_direction': 90, 'special_effect_size': [360, 120], 'minimap_marker': [20, 20],
            'icon': ICON, 'textures': list(TEXTURES), 'sprite_descriptor': DESCRIPTOR, 'animations': animations,
            'localization': localization(), 'tags': ['ms6', 'msa'],
            'behaviors': [{'name': 'invader_king', 'version': 1, 'params': KING}]}


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
    assert record['names'] == [f'504100invader_king_0{i}_out.obm' for i in range(1, 6)] and record['script_count'] == 90
    atlases = [Image.open(MSA_UNIT / (n + '.png')).convert('RGBA') for n in record['names']]
    animations, stats = transform(record)
    desc = descriptor(record)
    unit = unit_file(animations)
    x, y, iw, ih = ICON_CELL
    cell = Image.open(MSA_ICONS).convert('RGBA').crop((x, y, x + iw, y + ih))
    cell.save(HERE / 'source' / f'msa_icon_invader_king_{x}_{y}.png')
    report = {'stats': stats, 'colors': [len(set(a.getdata())) for a in atlases], 'provisional': PROVISIONAL}
    if '--report' in sys.argv:
        print(json.dumps(report, ensure_ascii=False))
        return
    obms = [indexed_obm(a) for a in atlases]
    report['obm_bytes'] = [len(o) for o in obms]
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
