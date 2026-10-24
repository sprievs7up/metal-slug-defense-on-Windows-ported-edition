"""能量核心（Power Core）按 MSA 7.13.0 原始动作记录移植（2026-10-22，AGENTS 第 208 节；方案
docs/ms6/POWER_CORE_PORT_PLAN_2026-10-22.md，用户 2026-10-22 选定以 MSD 原生沙包 Donou 为原生动作类、受击槽用方案 A）。

来源：F:\\egg\\research\\metal_slug_attack\\decoded\\units\\1576（msa_unit.py export 1576，建筑 EnergyCore1800）；修筑者 1575 与
MSA 沙包工兵 5、沙包 4 共用同一动作记录（donou.obm），两作共有单位的图集名与受击框相同，修筑者直接引用 MSD 原版图集 donou.obm。
- 建筑 s1xlv.power_core：内部单位，基准 4（BattleAction_Donou：状态 10 / 20 / 141 槽 6，受击 60 槽 7 播完回 10，
  损毁 100–120 槽 8 播完移除）。图集 51908EnergyCore_out.obm（256×256）原样转为 OI 01 08。脚本编号沿用 MSA，只换三槽：
  槽 7 ← MSA 槽 8（核心发亮）的一个周期（末尾 op5 改为 op21），槽 8 ← MSA 槽 9（损毁），槽 9 留空。删除空操作的 MSA 专有
  指令（24–35、47–58 等），op36（挂子层，菜单中跳过）改为 op11。行为 structure_death_effect：损毁动画播完后在原点放共用爆炸 0xff04。
  受击光束的攻击判定（用户 2026-10-22，行为 structure_hit_attack，核心 r81）：槽 7 一个周期（32 tick）内按 HIT_TICKS 开启攻击框 1
  （MSA 攻击框 1，同 MSA 槽 7 能量释放）8 次、第 31 tick 关闭，每次按普攻组对框内各目标结算 1 次火焰伤害，Lv40 每次 150、一个周期 1200。
- 修筑者 s1xlv.power_core_builder：基准 5（BattleAction_Kouhei），行为 build_structure（修筑对象为建筑），修筑时间与原版沙包工兵
  相同（用户 2026-10-22；不改写状态词 38，取基准 5 的值；此前按 MSA 写为 30），工兵生命按 MSA 为建筑生命的 6%（1575 / 1576 = 3000 / 50000 = 9000 / 150000）。
- 头像：MSA unit_icon_02.obme 中能量核心的头像 (122,1289) 40×43（核心与根须，与核心切图逐像素吻合）原样写入
  community_content/unit_icon_02.obm 的 (1700,768)，锚点 [−5, −2]（底边对齐选单位格内框下沿 45）；两单位共用。
- 数值（PROVISIONAL，变量名沿用）为用户 2026-10-22 指定的值，见下。
运行：E:\\anaconda3\\python.exe -I artwork/power_core_20261022/build_power_core.py [--preview]
（--preview 只写 out/；否则写入 community_content/：图集、描述符、两个单位文件、unit_icon_02.obm 与 content.json）。
"""
from pathlib import Path
import copy
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MSA_UNIT = Path(r'F:\egg\research\metal_slug_attack\decoded\units\1576')
MSA_ICONS = Path(r'F:\egg\research\metal_slug_attack\decoded\unit_icons\unit_icon_02.obme.png')
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
KEY_BUILDER, KEY = 's1xlv.power_core_builder', 's1xlv.power_core'
FILE_BUILDER, FILE = 'power_core_builder.json', 'power_core.json'
TEXTURE = 'power_core.obm'
DESCRIPTOR = 'power_core_descriptor.json'
SLOT_FROM = {7: 8, 8: 9}            # MSD Donou 槽 ← MSA 槽（受击 ← 核心发亮，损毁 ← 损毁）
EMPTY_SLOTS = (9,)
ONE_CYCLE = (7,)                     # 循环脚本只播一个周期（Donou 等动画播完才回待机）
# 受击光束的攻击判定（用户 2026-10-22：火焰，伸出 / 收回一个周期合计 1200，分多帧判定）。光束第 0–4 tick 伸出、4–28 tick 全长、
# 29–31 tick 收回；第 2、6 … 30 tick 各开启一次攻击框 1，第 31 tick 关闭。伤害为 MSA 1576 攻击 4 的各等级值（Lv1、10、20、30、40、50
# 锚点），Lv40 150 × 8 = 1200；目标数与第二参数（击退计量 ×100）同 MSA（999、0.1）。持续受击时周期连续播放，总伤害随受击时长增加。
HIT_TICKS = tuple(range(2, 32, 4))
HIT_CLOSE, HIT_CYCLE = 31, 32
HIT_DAMAGE = [50, 75, 100, 125, 150, 175]
# MSA 槽 8 以 op36 挂上与槽 7 相同的光束子层（op36 只在第一遍执行，MSA 战斗中可见）；False 时槽 7 只保留槽 8 自身的帧（核心发亮）。
HIT_BEAMS = True     # 用户 2026-10-22 确认保留光束（按 MSA 槽 8 原样）
# 受击框（2026-10-23，AGENTS 第 250 节）：MSD BattleObject::setAnimationID_SkipUpdate 切换动作时清除受击框，MSA 沿用上一动作的受击框。
# MSA 槽 8 没有 op3，受击槽 7 播放期间（状态 60）建筑无受击框，自爆摩托等攻击穿过；槽 7 开头补 op3，取待机槽 6 的受击框 1。
HIT_RECT = {7: 1}
SUBLAYER_MSA = 36                    # MSA：挂子层（参数同 op11），精灵在菜单标志下跳过
MSA_ONLY = range(24, 73)
ICON_CELL = (122, 1289, 40, 43)      # MSA 头像图集中的能量核心
ICON = {'page': 1, 'rect': [1700, 768, 40, 43], 'anchor': [-5, -2]}
# 数值（用户 2026-10-22 指定）：修筑者 AP 60、价格 50 勋章；建筑 Lv40 生命 9000 = 基准沙包 6000 × 3/2（暂定值为 MSA 的
# AP 45、价格 30、建筑 150000）；修筑者生命仍为建筑生命的 6%，再出击、修筑时间与其余倍率保持。
# 削弱（用户 2026-10-22，AGENTS 第 218 节）：修筑者 AP 90，建筑 Lv40 生命 6000（= 基准沙包，倍率 1）；价格保持 50。
# 修筑时间（用户同日）：与原版沙包工兵相同，不再写状态词 38。
PROVISIONAL = {
    'builder': {'ap': 90, 'shop_price': 50, 'available_from_start': True, 'production_interval_multiplier': [1, 1]},
    'core': {'hp_multiplier': [1, 1]},
}
LOCALIZATION = {   # 名称为用户指定（Power Core / 能量核心）；其余语言与说明由代理撰写，待校对
    'EN': ('POWER CORE', 'STAND. ATK : -     SPEC. ATK : -\nBuilds an Invader energy core at the front line.\nWhen hit, the core burns nearby enemies with energy beams.'),
    'JP': ('パワーコア', '通常攻撃：‐     特殊攻撃：‐\n前線にインベーダーのエネルギーコアを設置する。\nコアは攻撃を受けるとエネルギー光線で周囲の敵を焼く。'),
    'KR': ('파워 코어', '일반 공격: -     특수 공격: -\n전선에 인베이더의 에너지 코어를 설치한다.\n코어는 공격받으면 에너지 광선으로 주변의 적을 태운다.'),
    'ES': ('NÚCLEO DE ENERGÍA', 'ATQ ESTÁND. : -     ATQ ESPEC. : -\nConstruye un núcleo de energía invasor en el frente.\nAl recibir daño, quema a los enemigos cercanos con rayos.'),
    'PT': ('NÚCLEO DE ENERGIA', 'ATQ. PADR. : -   ATQ. ESPEC. : -\nConstrói um núcleo de energia invasor na linha de frente.\nAo ser atingido, queima os inimigos próximos com raios.'),
    'RU': ('ЭНЕРГОЯДРО', 'СТАНД. АТАК: -   СПЕЦ. АТАК: -\nСтроит энергоядро захватчиков на линии фронта.\nПри попадании ядро сжигает ближайших врагов лучами.'),
    'FR': ("NOYAU D'ÉNERGIE", "ATT. STAND : -   ATT. SPÉ : -\nConstruit un noyau d'énergie envahisseur sur la ligne de front.\nTouché, le noyau brûle les ennemis proches avec des rayons."),
    'DE': ('ENERGIEKERN', 'STD.-ANGR. : -   SPEZ.-ANGR. : -\nErrichtet einen Energiekern der Invasoren an der Front.\nBei Treffern verbrennt der Kern nahe Feinde mit Strahlen.'),
    'IT': ('NUCLEO ENERGETICO', 'ATC STAND.: -   ATC SPEC.: -\nCostruisce un nucleo energetico invasore in prima linea.\nSe colpito, il nucleo brucia i nemici vicini con raggi.'),
    # 中文说明第 2、3 行为用户 2026-10-22 文本（AGENTS 第 218 节；繁体按简体逐字转写）
    'ZT': ('能量核心', '普通攻擊：‐     特殊攻擊：‐\n侵略者所留下的能量核心。\n受到攻擊以能量光束燒灼周圍的敵人。'),
    'ZS': ('能量核心', '普通攻击：‐     特殊攻击：‐\n侵略者所留下的能量核心。\n受到攻击以能量光束烧灼周围的敌人。'),
}
ONES = ('knockback_threshold_multiplier', 'special_damage_multiplier', 'damage_multiplier', 'move_speed_multiplier',
        'attack_wait_multiplier', 'attack_range_multiplier', 'knockback_distance_multiplier', 'ballistic_range_multiplier')


def transform(record):
    """MSA 脚本 → 本体动画（编号沿用 MSA，SLOT_FROM 的槽换成来源槽）。返回 (动画字典, 统计)。"""
    stats = {'removed_msa_only': {}, 'sublayer_to_op11': 0, 'one_cycle': 0, 'sounds': {}}
    animations = {}
    for slot in range(record['script_count']):
        if slot in EMPTY_SLOTS:
            animations[str(slot)] = [{'opcode': 0, 'values': [-1]}, {'opcode': 1, 'values': [1]}, {'opcode': 21, 'values': []}]
            continue
        cmds = record['scripts'][SLOT_FROM.get(slot, slot)] or [[0, -1], [1, 1], [21]]
        out = []
        for c in cmds:
            op, v = c[0], list(c[1:])
            if op == SUBLAYER_MSA:
                if slot in ONE_CYCLE and not HIT_BEAMS:
                    stats['hit_sublayers_dropped'] = stats.get('hit_sublayers_dropped', 0) + 1
                    continue
                op = 11
                stats['sublayer_to_op11'] += 1
            elif op in MSA_ONLY:
                stats['removed_msa_only'][str(op)] = stats['removed_msa_only'].get(str(op), 0) + 1
                continue
            elif op == 23:
                stats['sounds'][v[0]] = stats['sounds'].get(v[0], 0) + 1
            out.append({'opcode': op, 'values': v})
        if slot in ONE_CYCLE and out[-1]['opcode'] == 5:
            out[-1] = {'opcode': 21, 'values': []}
            stats['one_cycle'] += 1
        if slot in ONE_CYCLE:
            out = beam_hits(out)
            stats['beam_hits'] = len(HIT_TICKS)
        if slot in HIT_RECT:
            out.insert(0, {'opcode': 3, 'values': [HIT_RECT[slot]]})
            stats['hit_rect_added'] = stats.get('hit_rect_added', 0) + 1
        animations[str(slot)] = out
    return animations, stats


def beam_hits(cmds):
    """受击槽：帧 0 共 32 tick 的帧序列（停 1 tick、再停 31 tick）改为按 HIT_TICKS 开启攻击框 1、HIT_CLOSE 关闭，总长不变。"""
    tail = [[c['opcode'], *c['values']] for c in cmds[-5:]]
    assert tail == [[0, 0], [1, 1], [0, 0], [1, 31], [21]], tail
    marks = {t: 1 for t in HIT_TICKS}
    marks[HIT_CLOSE] = 0
    points = sorted(marks) + [HIT_CYCLE]
    seq = [{'opcode': 0, 'values': [0]}, {'opcode': 1, 'values': [points[0]]}]
    for at, nxt in zip(points, points[1:]):
        seq += [{'opcode': 4, 'values': [marks[at]]}, {'opcode': 0, 'values': [0]}, {'opcode': 1, 'values': [nxt - at]}]
    return cmds[:-5] + seq + [{'opcode': 21, 'values': []}]


def descriptor(record):
    rects = [list(r) for r in record['rects']]
    frames = list(record['frames'])
    if 0xffffffff in frames:    # 空帧（矩形 −1）改为追加的 1×1 透明矩形（第 0 页右下角像素），同钢铁哨兵
        rects.append([255, 255, 1, 1, 0, 0, 0, 0])
        frames = [len(rects) - 1 if v == 0xffffffff else v for v in frames]
    return {'rects': rects, 'frames': frames, 'script_count': record['script_count'],
            'hit_bounds': record['hit_bounds'], 'attack_bounds': record['attack_bounds']}


def preview_record(record, animations):
    r = copy.deepcopy(record)
    r['scripts'] = [[[c['opcode'], *(x if isinstance(x, int) else 0 for x in c['values'])] for c in animations[str(i)]]
                    for i in range(record['script_count'])]
    return r


def localization():
    return {lang: {'name': name, 'description': text} for lang, (name, text) in LOCALIZATION.items()}


def unit_files(animations):
    common = {'faction': 3, 'identity': 'Invader', 'shop_price': PROVISIONAL['builder']['shop_price'],
              'available_from_start': PROVISIONAL['builder']['available_from_start'], 'ap': PROVISIONAL['builder']['ap']}
    ones = {k: [1, 1] for k in ONES}
    builder = {'key': KEY_BUILDER, 'base_id': 5, **common, 'hp_multiplier': [1, 1], **ones,
               'production_reference_id': 5,
               'production_interval_multiplier': PROVISIONAL['builder']['production_interval_multiplier'],
               'engineer_hp': {'mode': 'hp', 'percent': 6},
               'icon': ICON, 'animations': {}, 'localization': localization(), 'textures': ['donou.obm'],
               'tags': ['ms6', 'msa'],
               'behaviors': [{'name': 'build_structure', 'version': 1,
                              'params': {'structure': KEY, 'construction_time_multiplier': [1, 1]}}]}
    core = {'key': KEY, 'base_id': 4, **common, 'hp_multiplier': PROVISIONAL['core']['hp_multiplier'], **ones,
            'production_reference_id': 5, 'production_interval_multiplier': [1, 1],
            # 原画朝向：MSA 1576 的图像表为 90（朝右）
            'image_direction': 90, 'menu_reference_id': 5, 'internal_only': True,
            'icon': ICON, 'textures': [TEXTURE], 'sprite_descriptor': DESCRIPTOR, 'animations': animations,
            'localization': localization(), 'tags': ['ms6', 'msa'],
            # 受击光束：普攻组伤害（字 22）、目标数（字 24）、第二参数（字 23）与火焰属性（字 28）
            'status_word_values': {'22': HIT_DAMAGE, '24': 999}, 'status_float_values': {'23': 0.1},
            'attack_attributes': {'normal': 1},
            'behaviors': [{'name': 'structure_death_effect', 'version': 1, 'params': {}},
                          {'name': 'structure_hit_attack', 'version': 1, 'params': {}}]}
    # 击退门槛随生命倍率联动（第 6.1 节）；沙包为 −100，加载器只缩放正值，Donou 也不经过击退计量。
    core['knockback_threshold_multiplier'] = list(core['hp_multiplier'])
    return builder, core


def write_icon(cell):
    raw = bytearray((CONTENT / 'unit_icon_02.obm').read_bytes())
    assert raw[:4] == b'OI\x01\x20'
    w, h = struct.unpack_from('<HH', raw, 4)
    ax, ay, iw, ih = ICON['rect']
    for other in CONTENT.glob('units/*.json'):
        unit = json.loads(other.read_text(encoding='utf-8'))
        icon = unit['icon']
        if unit['key'] in (KEY, KEY_BUILDER) or 'atlas' in icon or icon['page'] != 1:
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
    assert record['names'] == ['51908EnergyCore_out.obm'] and record['script_count'] == 35
    atlas = Image.open(MSA_UNIT / (record['names'][0] + '.png')).convert('RGBA')
    animations, stats = transform(record)
    desc = descriptor(record)
    builder, core = unit_files(animations)
    obm = indexed_obm(atlas)
    x, y, iw, ih = ICON_CELL
    cell = Image.open(MSA_ICONS).convert('RGBA').crop((x, y, x + iw, y + ih))
    cell.save(HERE / 'source' / f'msa_icon_power_core_{x}_{y}.png')
    report = {'stats': stats, 'colors': len(set(atlas.getdata())), 'obm_bytes': len(obm),
              'hit_bounds': desc['hit_bounds'], 'attack_bounds': desc['attack_bounds'], 'provisional': PROVISIONAL}
    # 预览：MSD 槽 0、6、7、8（与 msa_unit preview 相同的绘制）
    pr = preview_record(record, animations)
    lengths = {}
    for slot in (0, 2, 6, 7, 8):
        sim = msa_unit.Sim(pr, [atlas])
        sim.start(slot)
        frames, t = [], 0
        while t < 80:
            if t % 4 == 0:
                frames.append(sim.draw((480, 320), (240, 260), 2))
            sim.step()
            t += 1
            if sim.root.done:   # 主脚本以 op21 结束（Donou 据此转入下一状态）
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
    for key in (KEY_BUILDER, KEY):
        if key not in index['unit_ids']:
            index['unit_ids'][key] = max(index['unit_ids'].values()) + 1
    (CONTENT / TEXTURE).write_bytes(obm)
    index['assets'][TEXTURE] = hashlib.blake2b(obm, digest_size=32).hexdigest()
    (CONTENT / 'unit_icon_02.obm').write_bytes(write_icon(cell))   # 该资源的摘要在 content.json 中为 null，保持不变
    save_json(CONTENT / DESCRIPTOR, desc)
    save_json(CONTENT / 'units' / FILE_BUILDER, builder)
    save_json(CONTENT / 'units' / FILE, core)
    save_json(CONTENT / 'content.json', index)
    report['unit_ids'] = {KEY_BUILDER: index['unit_ids'][KEY_BUILDER], KEY: index['unit_ids'][KEY]}
    (OUT / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
