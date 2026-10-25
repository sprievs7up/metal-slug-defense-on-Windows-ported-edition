"""单位行为库（模组 M2）：behavior_library.json 为行为清单的唯一来源（名称、版本、适用的原版基类、参数表、说明），
构建时同时嵌入原生核心（msd_behavior_manifest），加载器核对两者一致。

单位文件以 "behaviors": [{"name": ..., "version": ..., "params": {...}}] 组合行为；本模块校验后把行为转换为
原生安装使用的内部字段（例如 flame_interrupt、child_unit_key），单位文件不得直接写这些内部字段。
特殊行为只由 C++ 实现；新增或扩展行为属于游戏本体更新（修改清单并重建核心）。"""
from pathlib import Path
import json
import re

LIBRARY_PATH = Path(__file__).resolve().parent / 'behavior_library.json'
# 由行为生成、单位文件不得直接填写的内部字段。
INTERNAL_FIELDS = frozenset((
    'child_unit_key', 'preview_unit_key', 'construction_time_multiplier', 'summoned_unit_key',
    'summon_interval_multiplier', 'summon_interval_additional_multiplier', 'landing_unit_key',
    'shot_action_reference_id', 'recovery_animation', 'flame_interrupt', 'ground_special_attack',
    'retained_special_weapon', 'zombie_spec', 'throw_child_key', 'native_action', 'second_form_key'))
# 与 content_sounds.KEY_PATTERN 相同（音效稳定键）。
SOUND_KEY_PATTERN = re.compile(r'[a-z][a-z0-9_]{1,31}\.[a-z0-9_][a-z0-9_.\-]{0,63}')


def load_library(path=LIBRARY_PATH):
    text = Path(path).read_text(encoding='utf-8')
    library = json.loads(text)
    if library.get('schema') != 1 or not isinstance(library.get('library_version'), int):
        raise ValueError('Unsupported behavior library')
    by_name = {}
    for entry in library['behaviors']:
        if entry['name'] in by_name:
            raise ValueError('Duplicate behavior in library: ' + entry['name'])
        by_name[entry['name']] = entry
    return library, by_name


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _length_ok(spec, value):
    if 'length' in spec:
        return len(value) == spec['length']
    return spec.get('min_length', 0) <= len(value) <= spec.get('max_length', 2**31)


def _rational_ok(spec, value):
    if not (isinstance(value, list) and len(value) == 2 and all(_int(v) and 0 < v <= 10000 for v in value)):
        return False
    low, high = spec.get('min', [1, 10000]), spec.get('max', [10000, 1])
    return not (value[0] * low[1] < low[0] * value[1] or value[0] * high[1] > high[0] * value[1])


def _check_param(behavior, name, spec, value, units):
    where = f'{behavior}.{name}'
    kind = spec['type']
    if kind == 'unit_key':
        unit = units.get(value) if isinstance(value, str) else None
        if unit is None:
            raise ValueError(f'{where}: unknown unit key {value!r}')
        if bool(unit.get('internal_only')) != bool(spec.get('internal')):
            raise ValueError(f'{where}: unit {value} must ' + ('' if spec.get('internal') else 'not ') + 'be internal')
    elif kind == 'rational':
        if not (isinstance(value, list) and len(value) == 2 and all(_int(v) and 0 < v <= 10000 for v in value)):
            raise ValueError(f'{where}: expected [numerator, denominator]')
        low, high = spec.get('min', [1, 10000]), spec.get('max', [10000, 1])
        if value[0] * low[1] < low[0] * value[1] or value[0] * high[1] > high[0] * value[1]:
            raise ValueError(f'{where}: {value} outside {low}..{high}')
    elif kind == 'int':
        if not _int(value) or not spec.get('min', -2**31) <= value <= spec.get('max', 2**31 - 1):
            raise ValueError(f'{where}: integer outside range')
    elif kind == 'int_list':
        if (not isinstance(value, list) or not _length_ok(spec, value)
                or any(not _int(v) or not spec.get('min', -2**31) <= v <= spec.get('max', 2**31 - 1) for v in value)):
            raise ValueError(f'{where}: expected {spec.get("length", "a list of")} integers in range')
    elif kind == 'rational_list':
        if not isinstance(value, list) or not _length_ok(spec, value) or not all(_rational_ok(spec, v) for v in value):
            raise ValueError(f'{where}: expected a list of [numerator, denominator] in range')
    elif kind == 'sound_key':
        if not isinstance(value, str) or not SOUND_KEY_PATTERN.fullmatch(value):
            raise ValueError(f'{where}: expected a sound key')
    elif kind == 'sound_list':
        if (not isinstance(value, list) or not _length_ok(spec, value)
                or any(not isinstance(v, str) or not SOUND_KEY_PATTERN.fullmatch(v) for v in value)):
            raise ValueError(f'{where}: expected a list of sound keys')
    else:
        raise ValueError(f'{where}: unsupported parameter type {kind}')


def resolve(unit, units, library):
    """校验单位的 behaviors 并返回 {行为名: 带默认值的参数}；units 为 稳定键 → 单位（含 internal_only）。"""
    _, by_name = library
    entries = unit.get('behaviors', [])
    if not isinstance(entries, list):
        raise ValueError(unit['key'] + ': behaviors must be a list')
    leaked = INTERNAL_FIELDS & set(unit)
    if leaked:
        raise ValueError(unit['key'] + ': use behaviors instead of internal fields ' + ', '.join(sorted(leaked)))
    resolved = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) - {'name', 'version', 'params'}:
            raise ValueError(unit['key'] + ': invalid behavior entry')
        name = entry.get('name')
        spec = by_name.get(name)
        if spec is None:
            raise ValueError(f'{unit["key"]}: unknown behavior {name!r}')
        if entry.get('version') != spec['version']:
            raise ValueError(f'{unit["key"]}: {name} requires version {spec["version"]}')
        if name in resolved:
            raise ValueError(f'{unit["key"]}: duplicate behavior {name}')
        if unit['base_id'] not in spec['base_classes']:
            raise ValueError(f'{unit["key"]}: {name} supports base units {spec["base_classes"]}, not {unit["base_id"]}')
        for field in spec.get('requires_fields', []):
            if not unit.get(field):
                raise ValueError(f'{unit["key"]}: {name} requires field {field}')
        params = entry.get('params', {})
        if not isinstance(params, dict) or set(params) - set(spec['params']):
            raise ValueError(f'{unit["key"]}: {name} has unknown parameters')
        values = {}
        for pname, pspec in spec['params'].items():
            if pname in params:
                value = params[pname]
            elif pspec.get('required'):
                raise ValueError(f'{unit["key"]}: {name} requires parameter {pname}')
            else:
                value = pspec.get('default')
            # 缺省为 null 的可选参数（如 balloon_flight.launch_sound）省略时不校验
            if value is not None or pspec.get('required') or 'default' not in pspec:
                _check_param(name, pname, pspec, value, units)
            values[pname] = value
        resolved[name] = values
    for name in resolved:
        for needed in by_name[name].get('requires_behaviors', []):
            if needed not in resolved:
                raise ValueError(f'{unit["key"]}: {name} requires behavior {needed}')
    stages = resolved.get('hp_stage_animations')
    if stages:
        thresholds, transitions = stages['thresholds'], stages['transitions']
        if len(transitions) != len(thresholds):
            raise ValueError(f'{unit["key"]}: hp_stage_animations needs one transition flag per threshold')
        if any(a[0] * b[1] <= b[0] * a[1] for a, b in zip(thresholds, thresholds[1:])):
            raise ValueError(f'{unit["key"]}: hp_stage_animations thresholds must decrease')
        if stages['rage_stage'] > len(thresholds):
            raise ValueError(f'{unit["key"]}: rage_stage outside the stages')
        if unit['base_id'] == 182 and (any(transitions) or stages['rage_stage']):
            # 雪地步兵（BattleAction_ZakoSnow）不处理状态 80：过渡动作与狂暴只用于基准 313
            raise ValueError(f'{unit["key"]}: base unit 182 supports in-place stages only (no transitions or rage)')
        if 'stage_knockback_animation' in resolved and 'no_knockback' in resolved:
            raise ValueError(f'{unit["key"]}: stage_knockback_animation cannot be combined with no_knockback')
        armor = resolved.get('armor_hit_sound')
        # until_stage 为档数 + 1 时所有档位都播放（2026-10-13 冰车：车身各档均为金属）
        if armor and armor['until_stage'] > len(thresholds) + 1:
            raise ValueError(f'{unit["key"]}: armor_hit_sound.until_stage outside the stages')
        if 'balloon_flight' in resolved and not transitions[0]:
            # 气球飞行：第 1 档为放手与落地，须有过渡动作（2026-10-15）
            raise ValueError(f'{unit["key"]}: balloon_flight needs a transition on stage 1')
        throw = resolved.get('throw_child_on_stage')
        if throw and (throw['stage'] > len(thresholds) or not transitions[throw['stage'] - 1]):
            raise ValueError(f'{unit["key"]}: throw_child_on_stage.stage must be a stage with a transition')
        if throw and units[throw['unit']]['base_id'] != 160:
            raise ValueError(f'{unit["key"]}: the thrown unit must use base unit 160')
    return resolved


def internal_fields(resolved):
    """行为 → 原生安装使用的内部字段。"""
    fields = {}
    if 'build_structure' in resolved:
        v = resolved['build_structure']
        fields.update(child_unit_key=v['structure'], preview_unit_key=v['structure'],
                      construction_time_multiplier=v['construction_time_multiplier'])
    if 'summon_units' in resolved:
        v = resolved['summon_units']
        fields.update(summoned_unit_key=v['unit'], summon_interval_multiplier=v['interval_multiplier'],
                      summon_interval_additional_multiplier=v['interval_additional_multiplier'])
    if 'spawn_child_unit' in resolved:
        fields['child_unit_key'] = resolved['spawn_child_unit']['unit']
    if 'para_drop_transform' in resolved:
        fields['landing_unit_key'] = resolved['para_drop_transform']['landing_unit']
    if 'insect_swarm_release' in resolved:
        fields['shot_action_reference_id'] = 157
    if 'recovery_slot' in resolved:
        fields['recovery_animation'] = resolved['recovery_slot']['animation']
    if 'flame_burst_interruptible' in resolved:
        v = resolved['flame_burst_interruptible']
        fields['flame_interrupt'] = {'flame_start_tick': v['flame_start_tick'], 'flame_ticks': v['flame_ticks'],
                                     'alternate_knockback_animation': v['alternate_knockback_animation'],
                                     'ending_bullet_animations': list(v['ending_bullet_animations']),
                                     'knockback_limit_per_special': int('single_knockback_per_special' in resolved)}
    if 'ground_special_attack' in resolved:
        fields['ground_special_attack'] = True
    if 'retained_special_weapon' in resolved:
        fields['retained_special_weapon'] = True
    # 2026-10-21 钢铁哨兵（行为库 v12）：原生保留的 IRON SLIDER 动作类；第二形态单位号写入数据行子单位字（不改菜单显示）。
    if 'iron_slider' in resolved:
        fields.update(native_action='IronSlider', second_form_key=resolved['iron_slider']['second_form'])
    if 'iron_slider_second_form' in resolved:
        fields['native_action'] = 'IronSlider_2'
    zombie = {'flags': 0}
    if 'hp_stage_animations' in resolved:
        v = resolved['hp_stage_animations']
        zombie.update(flags=zombie['flags'] | 1, thresholds=[list(t) for t in v['thresholds']],
                      transitions=list(v['transitions']), rage_stage=v['rage_stage'],
                      rage_speed=list(v['rage_speed_multiplier']), rage_damage=list(v['rage_damage_multiplier']))
    if 'no_knockback' in resolved:
        zombie['flags'] |= 2
    if 'front_nearest_target' in resolved:
        zombie['flags'] |= 64
    if 'stage_knockback_animation' in resolved:
        zombie['flags'] |= 128
    if 'no_death_splash' in resolved:
        zombie['flags'] |= 256
    if 'armor_hit_sound' in resolved:
        v = resolved['armor_hit_sound']
        zombie.update(flags=zombie['flags'] | 4, armor_sounds=list(v['sounds']), armor_until=v['until_stage'])
    if 'kill_sound' in resolved:
        zombie.update(flags=zombie['flags'] | 8, kill_sound=resolved['kill_sound']['sound'])
    if 'throw_child_on_stage' in resolved:
        v = resolved['throw_child_on_stage']
        zombie.update(flags=zombie['flags'] | 16, throw_stage=v['stage'], release_tick=v['release_tick'])
        fields['throw_child_key'] = v['unit']
    if 'thrown_flight' in resolved:
        v = resolved['thrown_flight']
        zombie.update(flags=zombie['flags'] | 32, flight_forward=v['forward'], flight_height=v['height'],
                      base_clearance=v['base_clearance'])
    # 2026-10-15 新单位（行为库 v8）
    if 'self_destruct_attack' in resolved:
        zombie['flags'] |= 512
        if resolved['self_destruct_attack']['unmirrored_from_tick'] >= 0:
            zombie['unmirror_tick'] = resolved['self_destruct_attack']['unmirrored_from_tick']
    if 'ground_only_attack' in resolved:
        zombie['flags'] |= 1024
    if 'walk_shoot' in resolved:
        zombie.update(flags=zombie['flags'] | 2048, walk_range=resolved['walk_shoot']['range'])
    if 'balloon_flight' in resolved:
        v = resolved['balloon_flight']
        zombie.update(flags=zombie['flags'] | 4096, pop_distance=v['pop_distance'])
        if v['launch_sound']:
            zombie['launch_sound'] = v['launch_sound']
    # 2026-10-18 Hunter（行为库 v9，基准 221 原住民（鸟））：ZSpec 字 33–38
    if 'lob_blast' in resolved:
        v = resolved['lob_blast']
        zombie.update(flags=zombie['flags'] | 8192, blast_slot=v['blast_animation'], fuse_slot=v['fuse_animation'],
                      spread_first=v['special_spread_first'], spread_count=v['special_spread_count'])
    if 'death_by_attribute' in resolved:
        v = resolved['death_by_attribute']
        zombie.update(flags=zombie['flags'] | 16384, death_explosion=v['explosion_animation'],
                      death_fire=v['fire_animation'])
        # 行为库 v10：三种死亡的另一版本（ZSpec 字 39–41，0 为不使用）
        for param, key in (('normal_variant_animation', 'death_normal_variant'),
                           ('explosion_variant_animation', 'death_explosion_variant'),
                           ('fire_variant_animation', 'death_fire_variant')):
            if v[param]:
                zombie[key] = v[param]
    # 2026-10-21 效果贴地（行为库 v11，ZSpec 字 42）：辣椒僵尸的火焰带沿地形绘制
    if 'ground_hugging_effect' in resolved:
        zombie.update(flags=zombie['flags'] | 32768, hug_animation=resolved['ground_hugging_effect']['animation'])
    # 2026-10-22 建筑损毁效果（行为库 v13，基准 4 沙包类）：能量核心
    if 'structure_death_effect' in resolved:
        zombie['flags'] |= 65536
    # 2026-10-22 飞行护盾（行为库 v14，基准 200 飞行侵略者类，ZSpec 字 43–52）
    if 'flying_shell' in resolved:
        v = resolved['flying_shell']
        zombie.update(flags=zombie['flags'] | 131072, shell=[v['height'], v['homing_animation'], v['arc_first_animation'],
                                                          v['arc_count'], v['rain_first_animation'], v['rain_count'],
                                                          v['rain_delay'], v['meteor_lifetime'], v['meteor_hp_percent'],
                                                          v['turn_rate']])
    # 2026-10-22 蜈蚣长老（行为库 v15，基准 192 侵略者类，ZSpec 字 53–76）：各动作号、圆环节数与弹体脚本
    if 'elder_centipede' in resolved:
        v = resolved['elder_centipede']
        zombie.update(flags=zombie['flags'] | 262144, centipede=[v[k] for k in (
            'appear_animation',
            'emerge_animation',
            'neutral_animation',
            'burrow_animation',
            'underground_animation',
            'long_attack_animation',
            'long_attack_end_animation',
            'dive_animation',
            'march_animation',
            'flinch_animation',
            'flinch_loop_animation',
            'knockback_animation',
            'death_animation',
            'smoke_first_animation',
            'wheel_parts',
            'ground_hit_animation',
            'ground_hit_alt_animation',
            'droplet_first_animation',
            'droplet_count',
            'splash_animation',
            'march_blob_animation',
            'march_blob_hit_animation',
            'march_dirt_animation',
            'ground_dust_animation',
        )])
    # 2026-10-22 侵略者之王（行为库 v17，基准 192 侵略者类，ZSpec 字 77–100）：各动作号与激光弹体脚本
    if 'invader_king' in resolved:
        v = resolved['invader_king']
        zombie.update(flags=zombie['flags'] | 1048576, king=[v[k] for k in (
            'neutral_animation',
            'fall_animation',
            'land_animation',
            'near_attack_animation',
            'jump_animation',
            'special_start_animation',
            'special_animation',
            'special_end_animation',
            'knockback_animation',
            'death_animation',
            'flinch_animation',
            'flinch_loop_animation',
            'menu_neutral_animation',
            'menu_long_animation',
            'menu_special_animation',
            'counter_laser_animation',
            'counter_laser_body_animation',
            'counter_burst_animation',
            'sky_laser_first_animation',
            'sky_laser_count',
            'sky_laser_body_animation',
            'ground_laser_first_animation',
            'ground_laser_count',
            'ground_impact_animation',
        )])
    # 2026-10-22 建筑受击光束（行为库 v16，基准 4 沙包类）：能量核心受击动作中的攻击框按普攻组结算
    if 'structure_hit_attack' in resolved:
        zombie['flags'] |= 524288
    # 2026-10-25 钢铁死亡蠕虫（行为库 v19 / 行为 v2，核心 r92，基准 192 侵略者类，ZSpec 字 104–116）：各动作号、地下行进、
    # 掘削碎块弹体脚本、损毁碎块脚本（MSA EffectAction_DeadBody，步长 2，落地动作为其后一个）；
    # R4（行为库 v20 / 行为 v3，核心 r95，字 117–119）：碎块滚动动作首槽、碎块爆炸动作、碎块引信 tick；
    # R5（行为库 v21 / 行为 v4，核心 r96，字 120）：绝招中的钻出动作（平常的钻出用 emerge_animation）
    if 'iron_death_worm' in resolved:
        v = resolved['iron_death_worm']
        zombie.update(flags=zombie['flags'] | 2097152, worm=[v[k] for k in (
            'neutral_animation',
            'burrow_animation',
            'emerge_animation',
            'near_attack_animation',
            'dive_animation',
            'drill_animation',
            'death_move_animation',
            'death_burst_animation',
            'underground_animation',
            'debris_first_animation',
            'debris_count',
            'dead_body_first_animation',
            'dead_body_count',
            'debris_roll_first_animation',
            'debris_burst_animation',
            'debris_fuse',
            'special_emerge_animation',
        )])
    if zombie['flags']:
        fields['zombie_spec'] = zombie
    return fields


def sound_keys(unit):
    """行为参数中引用的音效键（生命分档单位的防具受击、击毙与气球出场音效）。"""
    spec = unit.get('zombie_spec') or {}
    return (list(spec.get('armor_sounds', [])) + ([spec['kill_sound']] if spec.get('kill_sound') else [])
            + ([spec['launch_sound']] if spec.get('launch_sound') else []))


def apply(units_by_key, library):
    """校验全部单位的行为并把内部字段写入单位字典（就地）；返回 {稳定键: 已解析行为}。"""
    result = {}
    for key, unit in units_by_key.items():
        resolved = resolve(unit, units_by_key, library)
        unit.update(internal_fields(resolved))
        result[key] = resolved
    return result


def markdown(library):
    """作者指南中的行为目录（中英），由行为库生成。"""
    data, by_name = library
    out = [f'# 单位行为目录 / Unit behavior catalog（行为库版本 {data["library_version"]}）', '',
           '本文件由 `content_tool.py list-behaviors --markdown` 从 `behavior_library.json` 生成，请勿手工修改。',
           'Generated from `behavior_library.json` by `content_tool.py list-behaviors --markdown`; do not edit by hand.', '',
           '单位文件写法 / Usage in a unit file:', '', '```json',
           '"behaviors": [{"name": "spawn_child_unit", "version": 1, "params": {"unit": "author_mod.child"}}]', '```', '']
    for name, spec in by_name.items():
        out += [f'## {name}（v{spec["version"]}）', '', f'- 适用的原版基准单位 / base_id: {", ".join(map(str, spec["base_classes"]))}']
        if spec.get('requires_fields'):
            out.append(f'- 需要字段 / requires fields: {", ".join(spec["requires_fields"])}')
        if spec.get('requires_behaviors'):
            out.append(f'- 需要行为 / requires behaviors: {", ".join(spec["requires_behaviors"])}')
        out += ['', spec['doc']['ZS'], '', spec['doc']['EN'], '']
        if spec['params']:
            out += ['| 参数 / parameter | 类型 / type | 约束 / constraints |', '| --- | --- | --- |']
            for pname, p in spec['params'].items():
                rules = '; '.join(f'{k}: {json.dumps(v, ensure_ascii=False)}' for k, v in p.items() if k != 'type')
                out.append(f'| `{pname}` | {p["type"]} | {rules} |')
            out.append('')
        else:
            out += ['无参数 / no parameters.', '']
    return '\n'.join(out)


def describe(library):
    """作者工具用的文字清单。"""
    lines = []
    _, by_name = library
    for name, spec in by_name.items():
        lines.append(f'{name} v{spec["version"]}  base_classes={spec["base_classes"]}')
        for pname, p in spec['params'].items():
            extra = {k: v for k, v in p.items() if k != 'type'}
            lines.append(f'    {pname}: {p["type"]} {json.dumps(extra, ensure_ascii=False)}')
        for field in ('requires_fields', 'requires_behaviors'):
            if spec.get(field):
                lines.append(f'    {field}: {spec[field]}')
        lines.append('    ' + spec['doc']['ZS'])
    return '\n'.join(lines)
