"""单位行为库（模组 M2）：behavior_library.json 为行为清单的唯一来源（名称、版本、适用的原版基类、参数表、说明），
构建时同时嵌入原生核心（msd_behavior_manifest），加载器核对两者一致。

单位文件以 "behaviors": [{"name": ..., "version": ..., "params": {...}}] 组合行为；本模块校验后把行为转换为
原生安装使用的内部字段（例如 flame_interrupt、child_unit_key），单位文件不得直接写这些内部字段。
特殊行为只由 C++ 实现；新增或扩展行为属于游戏本体更新（修改清单并重建核心）。"""
from pathlib import Path
import json

LIBRARY_PATH = Path(__file__).resolve().parent / 'behavior_library.json'
# 由行为生成、单位文件不得直接填写的内部字段。
INTERNAL_FIELDS = frozenset((
    'child_unit_key', 'preview_unit_key', 'construction_time_multiplier', 'summoned_unit_key',
    'summon_interval_multiplier', 'summon_interval_additional_multiplier', 'landing_unit_key',
    'shot_action_reference_id', 'recovery_animation', 'flame_interrupt', 'ground_special_attack',
    'retained_special_weapon'))


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
        if (not isinstance(value, list) or len(value) != spec['length']
                or any(not _int(v) or not spec.get('min', -2**31) <= v <= spec.get('max', 2**31 - 1) for v in value)):
            raise ValueError(f'{where}: expected {spec["length"]} integers in range')
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
            _check_param(name, pname, pspec, value, units)
            values[pname] = value
        resolved[name] = values
    for name in resolved:
        for needed in by_name[name].get('requires_behaviors', []):
            if needed not in resolved:
                raise ValueError(f'{unit["key"]}: {name} requires behavior {needed}')
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
    return fields


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
