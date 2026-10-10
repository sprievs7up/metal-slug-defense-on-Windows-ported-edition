"""模组加载（模组 M3）：扫描 mods/、校验清单与依赖、读取模组单位与覆盖补丁、分配模组单位 ID。

- 目录：游戏根目录 mods/<文件夹>/mod.json（MSD_MODS_DIR 可改）。
- 启用列表与加载顺序：用户目录 %LOCALAPPDATA%\\MSD_WINDOWS_S1XLV\\mods_enabled.json
  {"schema": 1, "enabled": ["模组 id", ...]}（MSD_MODS_ENABLED 可改）；文件不存在时不启用任何模组。M4 的 MOD 页写入该文件。
- 模组单位稳定键为 "<模组 id>.<名称>"；模组资源放在 assets/，文件名须以 "<模组 id>_" 开头（不与本体、原版或其他模组重名）。
  单位文件可按文件名引用本体资源与原版游戏资源（不重新分发原版素材）。
- 校验失败的模组整体跳过（记录原因，供 MOD 页显示），依赖它的模组随之跳过；本体内容不受影响。
- 覆盖补丁 patches/*.json：[{"target": 单位稳定键, "field": 字段, "value": 值}, ...]，只允许数值倍率与经济字段，
  目标为本体单位、本模组单位、所依赖模组的单位，或原版单位 "unit:<1–399>"（M3b）；按加载顺序应用，
  同一字段后加载者生效（记录覆盖关系）。原版单位的补丁相对原版数值，只作用于该原版单位（以它为基准的社区单位不受影响）。
- 世界与关卡（M5）campaign/*.json：每个文件为世界目录片段 {"scenes": [...], "music": [...], "worlds": [...]}（格式同
  campaign_content/catalog.json，不写 assets）；键以 "<模组 id>." 开头，与本体及已载入模组合并校验（campaign_catalog.Catalog）。
- 音效（M6）sounds/*.json：每个文件为音效条目列表（格式见 content_sounds.py），文件为本模组资源；单位动作脚本 op23 可写
  音效键，可见范围为本体、本模组与所依赖模组的音效。SoundID 由 CommunityContent 按加载顺序分配。
- 自制 EVENT（M6b）events/*.json：每个文件一个 EVENT（格式见 event_content.py），键以 "<模组 id>." 开头，图片为本模组资源；
  引用的单位、音效、场景限于本体、本模组与所依赖模组。
"""
from pathlib import Path
import copy
import json
import os
import re

import behaviors
import content_ids
import content_sounds
import content_locale
import event_content

ID_PATTERN = re.compile(r'[a-z][a-z0-9_]{1,31}')
RESERVED_IDS = frozenset(('s1xlv', 'original', 'body', 'test'))
VERSION_PATTERN = re.compile(r'\d+(\.\d+){0,3}')
PATCH_FIELDS = frozenset((
    'hp_multiplier', 'knockback_threshold_multiplier', 'damage_multiplier', 'special_damage_multiplier',
    'move_speed_multiplier', 'attack_range_multiplier', 'knockback_distance_multiplier', 'ballistic_range_multiplier',
    'attack_wait_multiplier', 'normal_projectile_distance_multiplier', 'special_projectile_distance_multiplier',
    'special_cooldown_multiplier', 'production_interval_multiplier', 'ap', 'shop_price'))
RATIONAL_FIELDS = PATCH_FIELDS - {'ap', 'shop_price'}


def mods_dir(game_root):
    value = os.environ.get('MSD_MODS_DIR')
    return Path(value) if value else Path(game_root) / 'mods'


def enabled_path():
    value = os.environ.get('MSD_MODS_ENABLED')
    if value:
        return Path(value)
    base = os.environ.get('LOCALAPPDATA')
    return Path(base) / 'MSD_WINDOWS_S1XLV' / 'mods_enabled.json' if base else None


def read_enabled(path=None):
    path = enabled_path() if path is None else path
    if path is None or not path.is_file():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema') != 1 or not isinstance(data.get('enabled'), list):
        raise ValueError('Unsupported mods_enabled.json')
    return [m for m in data['enabled'] if isinstance(m, str)]


def write_enabled(ids, path=None):
    """写入启用列表与加载顺序（MOD 页使用；重启游戏后生效）。先写临时文件再替换。"""
    path = enabled_path() if path is None else path
    if path is None:
        raise RuntimeError('LOCALAPPDATA is not set')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps({'schema': 1, 'enabled': list(ids)}, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def version_tuple(text):
    if not isinstance(text, str) or not VERSION_PATTERN.fullmatch(text):
        raise ValueError(f'invalid version {text!r}')
    return tuple(int(v) for v in text.split('.'))


def satisfies(version, constraint):
    """constraint：逗号分隔的 >=、<=、>、<、== 条件，例如 ">=26.10, <27"；空值表示不限。"""
    if not constraint:
        return True
    current = version_tuple(version)
    for part in constraint.split(','):
        m = re.fullmatch(r'\s*(>=|<=|==|>|<)\s*(\S+)\s*', part)
        if not m:
            raise ValueError(f'invalid version constraint {constraint!r}')
        op, other = m.group(1), version_tuple(m.group(2))
        width = max(len(current), len(other))
        a, b = current + (0,) * (width - len(current)), other + (0,) * (width - len(other))
        if not {'>=': a >= b, '<=': a <= b, '==': a == b, '>': a > b, '<': a < b}[op]:
            return False
    return True


def original_uid(target):
    """'unit:<1–399>' → UnitID；其他返回 None。"""
    m = re.fullmatch(r'unit:(\d{1,3})', target)
    return int(m.group(1)) if m and 1 <= int(m.group(1)) <= 399 else None


class Mod:
    def __init__(self, folder):
        self.folder = folder
        self.id = None
        self.version = None
        self.manifest = {}
        self.units = {}            # 稳定键 → 单位数据（未分配 ID）
        self.patches = []
        self.campaign = None       # 世界目录片段（合并后的 scenes、music、worlds）
        self.sounds = []           # 音效条目（M6）
        self.events = []           # 自制 EVENT（M6b）
        self.assets = {}           # 资源名 → 路径
        self.state = 'disabled'
        self.reasons = []

    def status(self):
        return {'id': self.id, 'version': self.version, 'folder': self.folder.name, 'state': self.state,
                'reasons': list(self.reasons), 'units': sorted(self.units), 'patches': len(self.patches),
                'name': self.manifest.get('name'), 'author': self.manifest.get('author'),
                'license': self.manifest.get('license'), 'description': self.manifest.get('description'),
                'depends': [d.get('id') for d in self.manifest.get('depends', []) if isinstance(d, dict)],
                'conflicts': [c for c in self.manifest.get('conflicts', []) if isinstance(c, str)],
                'game_version': self.manifest.get('game_version'), 'campaign': campaign_counts(self.campaign),
                'sounds': len(self.sounds), 'events': len(self.events)}


def campaign_counts(raw):
    if not raw:
        return None
    # 状态显示用的计数；格式错误的条目不计入（校验原因另行记录）。
    worlds = [w for w in raw.get('worlds', []) if isinstance(w, dict)]
    areas = [a for w in worlds for a in w.get('areas', []) if isinstance(a, dict)]
    return {'worlds': len(worlds), 'areas': len(areas), 'stages': sum(len(a.get('stages', [])) for a in areas),
            'scenes': len(raw.get('scenes', [])), 'music': len(raw.get('music', []))}


def read_mod(folder, game_version, library_version):
    """读取并校验单个模组目录（不涉及其他模组）；失败时 state='skipped' 并记录原因。"""
    mod = Mod(folder)
    try:
        data = json.loads((folder / 'mod.json').read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('schema') != 1:
            raise ValueError('mod.json schema must be 1')
        mod.manifest = data
        mod.id = data.get('id')
        if not isinstance(mod.id, str) or not ID_PATTERN.fullmatch(mod.id) or mod.id in RESERVED_IDS:
            raise ValueError(f'invalid mod id {mod.id!r}')
        mod.version = data.get('version')
        version_tuple(mod.version)
        name = data.get('name')
        if not isinstance(name, dict) or not name or any(not isinstance(v, str) or not v for v in name.values()):
            raise ValueError('name must map language codes to text')
        for field in ('author', 'license'):
            if not isinstance(data.get(field), str) or not data[field]:
                raise ValueError(f'{field} is required')
        description = data.get('description')
        if description is not None and not (isinstance(description, dict) and all(isinstance(v, str) for v in description.values())):
            raise ValueError('description must map language codes to text')
        if not satisfies(game_version, data.get('game_version')):
            raise ValueError(f'requires game version {data["game_version"]} (current {game_version})')
        if not satisfies(str(library_version), data.get('behavior_library')):
            raise ValueError(f'requires behavior library {data["behavior_library"]} (current {library_version})')
        for dep in data.get('depends', []):
            if not isinstance(dep, dict) or not isinstance(dep.get('id'), str):
                raise ValueError('depends entries need an id')
            satisfies('0', dep.get('version'))      # 只检查约束格式
        if any(not isinstance(c, str) for c in data.get('conflicts', [])):
            raise ValueError('conflicts must list mod ids')
        content = data.get('content', {})
        unknown = set(content) - {'units', 'patches', 'campaign', 'sounds', 'events'}
        if unknown:
            raise ValueError('unsupported content types in this version: ' + ', '.join(sorted(unknown)))
        assets_dir = folder / 'assets'
        if assets_dir.is_dir():
            for path in sorted(assets_dir.iterdir()):
                if path.is_file():
                    if not path.name.startswith(mod.id + '_'):
                        raise ValueError(f'asset {path.name} must start with "{mod.id}_"')
                    mod.assets[path.name] = path
        if 'sounds' in content:
            mod.sounds = content_sounds.read_mod_sounds(folder / content['sounds'], mod.id, mod.assets)
        if 'events' in content:
            mod.events = [dict(e, source=mod.id) for e in
                          event_content.read_folder(folder / content['events'], mod.id, mod.assets.get)]
        if 'units' in content:
            for path in sorted((folder / content['units']).glob('*.json')):
                unit = json.loads(path.read_text(encoding='utf-8'))
                key = unit.get('key') if isinstance(unit, dict) else None
                if not isinstance(key, str) or not key.startswith(mod.id + '.') or len(key) <= len(mod.id) + 1:
                    raise ValueError(f'{path.name}: unit key must start with "{mod.id}."')
                if key in mod.units:
                    raise ValueError(f'duplicate unit key {key}')
                if 'id' in unit or not isinstance(unit.get('icon'), dict) or 'index' in unit['icon']:
                    raise ValueError(f'{path.name}: unit files must not fix runtime identities')
                # 语言补全（M6b）：只写一种语言时全部套用，部分翻译时未填写者用英语（无英语时用第一种）。
                unit['localization'] = content_locale.fill(unit.get('localization'), f'{path.name} localization')
                mod.units[key] = unit
        if 'patches' in content:
            for path in sorted((folder / content['patches']).glob('*.json')):
                entries = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(entries, list):
                    raise ValueError(f'{path.name}: patches must be a list')
                for entry in entries:
                    if not isinstance(entry, dict) or set(entry) != {'target', 'field', 'value'}:
                        raise ValueError(f'{path.name}: patch entries need target, field and value')
                    if entry['field'] not in PATCH_FIELDS:
                        raise ValueError(f'{path.name}: field {entry["field"]} cannot be patched')
                    if not isinstance(entry['target'], str):
                        raise ValueError(f'{path.name}: patch target must be a string')
                    if entry['target'].startswith('unit:') and original_uid(entry['target']) is None:
                        raise ValueError(f'{path.name}: original unit target must be unit:1 … unit:399')
                    mod.patches.append(dict(entry, source=path.name))
        if 'campaign' in content:
            mod.campaign = {'scenes': [], 'music': [], 'worlds': []}
            for path in sorted((folder / content['campaign']).glob('*.json')):
                part = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(part, dict) or set(part) - {'schema', 'scenes', 'music', 'worlds'} or part.get('schema', 1) != 1:
                    raise ValueError(f'{path.name}: campaign files contain schema 1 scenes, music and worlds lists')
                for name in ('scenes', 'music', 'worlds'):
                    if not isinstance(part.get(name, []), list) or not all(isinstance(v, dict) for v in part.get(name, [])):
                        raise ValueError(f'{path.name}: {name} must be a list of objects')
                    mod.campaign[name] += part.get(name, [])
        mod.state = 'valid'
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        mod.state = 'skipped'
        mod.reasons.append(str(error))
    return mod


def body_scene_keys(campaign_root):
    """本体世界目录（campaign_content/catalog.json）登记的场景键。"""
    path = Path(campaign_root) / 'catalog.json'
    if not path.is_file():
        return set()
    return {s.get('key') for s in json.loads(path.read_text(encoding='utf-8')).get('scenes', []) if isinstance(s, dict)}


class LazyDims(dict):
    """资源名 → (宽, 高)，按需读取 OBM 文件头；resolver(name) 返回文件路径或 None。"""

    def __init__(self, resolver):
        super().__init__()
        self.resolver = resolver

    def __contains__(self, name):
        return dict.__contains__(self, name) or self.resolver(name) is not None

    def __missing__(self, name):
        source = self.resolver(name)
        if source is None:
            raise KeyError(name)
        with open(source, 'rb') as stream:
            head = stream.read(8)
        if head[:2] != b'OI':
            raise ValueError(f'{name}: not an OBM image')
        self[name] = (int.from_bytes(head[4:6], 'little'), int.from_bytes(head[6:8], 'little'))
        return self[name]


def load(game_root, body_units, enabled=None, game_version='0', library=None, preferred_ids=None, id_map=None,
         stock_assets=None, body_assets=(), body_root=None, stock_root=None, campaign_root=None, campaigns=None,
         sounds=None, body_sounds=(), events=None):
    """按启用列表加载模组。body_units：本体单位（稳定键 → 已组装单位，含 id）。
    返回 (模组单位列表（含 id，已转换行为）, 资源名 → 路径, 补丁记录, 各模组状态)。
    stock_assets：判断原版资源文件是否存在的函数（单位引用原版图集时使用）。
    campaigns：传入列表时追加已载入模组的世界目录片段（按加载顺序，供 campaign_catalog.Catalog 使用）；
    campaign_root：本体世界目录（缺省为 game_root/campaign_content）。
    sounds：传入列表时追加已载入模组的音效条目（按加载顺序）；body_sounds：本体音效键 → 类型（单位与关卡引用的可见范围）。
    events：传入列表时追加已载入模组的自制 EVENT（M6b，按加载顺序）。"""
    library = library or behaviors.load_library()
    root = mods_dir(game_root)
    enabled = read_enabled() if enabled is None else enabled
    found = {}
    statuses = []
    if root.is_dir():
        for folder in sorted(p for p in root.iterdir() if p.is_dir() and (p / 'mod.json').is_file()):
            mod = read_mod(folder, game_version, library[0]['library_version'])
            if mod.id is None or mod.id in found:
                if mod.id in found:
                    mod.state, mod.reasons = 'skipped', [f'duplicate mod id {mod.id} (also in {found[mod.id].folder.name})']
                statuses.append(mod)
                continue
            found[mod.id] = mod
            statuses.append(mod)
    import community_content as cc
    order = [m for m in enabled if m in found]
    missing = [m for m in enabled if m not in found]
    active = {}
    for mod_id in order:
        mod = found[mod_id]
        if mod.state != 'valid':
            continue
        mod.state = 'enabled'
        active[mod_id] = mod
    for mod in found.values():
        if mod.state == 'valid':
            mod.state = 'disabled'
    # 依赖、冲突与加载顺序（依赖须先于本模组加载）；被跳过的模组使依赖它的模组也跳过。
    changed = True
    while changed:
        changed = False
        for mod_id in [m for m in order if m in active]:
            mod = active[mod_id]
            problems = []
            for dep in mod.manifest.get('depends', []):
                other = active.get(dep['id'])
                if other is None:
                    problems.append(f'missing or disabled dependency {dep["id"]}')
                elif not satisfies(other.version, dep.get('version')):
                    problems.append(f'dependency {dep["id"]} {other.version} does not satisfy {dep["version"]}')
                elif order.index(dep['id']) > order.index(mod_id):
                    problems.append(f'dependency {dep["id"]} must load before {mod_id}')
            for other in mod.manifest.get('conflicts', []):
                if other in active:
                    problems.append(f'conflicts with enabled mod {other}')
            if problems:
                mod.state, mod.reasons = 'skipped', problems
                del active[mod_id]
                changed = True
    # 单位：依赖可见范围内的键引用、行为校验与资源存在性；失败则整个模组跳过（依赖它的模组随后再判定）。
    all_units = dict(body_units)
    assets = {}
    stock_assets = stock_assets or (lambda name: False)
    accepted = []
    fragments = []
    campaign_root = Path(game_root) / 'campaign_content' if campaign_root is None else Path(campaign_root)
    campaign_cache = {}
    for mod_id in [m for m in order if m in active]:
        mod = active[mod_id]
        deps = {d['id'] for d in mod.manifest.get('depends', [])}
        if any(d not in [a.id for a in accepted] for d in deps):
            mod.state, mod.reasons = 'skipped', ['a dependency was skipped']
            continue
        used = len(body_sounds) + sum(len(m.sounds) for m in accepted)
        if used + len(mod.sounds) > len(content_sounds.FREE_SOUND_IDS):
            mod.state, mod.reasons = 'skipped', [f'custom sound capacity exceeded ({used + len(mod.sounds)} > {len(content_sounds.FREE_SOUND_IDS)})']
            continue
        visible_sounds = set(body_sounds) | {e['key'] for m in accepted if m.id in deps for e in m.sounds} | {e['key'] for e in mod.sounds}
        visible = {k: v for k, v in all_units.items()
                   if '.' not in k or k.split('.', 1)[0] in ('s1xlv', mod_id) or k.split('.', 1)[0] in deps}
        trial = dict(visible)
        provisional = {}
        for k, u in mod.units.items():
            unit = copy.deepcopy(u)
            unit['key'], unit['id'] = k, 0
            unit['icon'] = dict(unit['icon'], index=340, page=2 if 'atlas' in unit['icon'] else unit['icon'].get('page'))
            provisional[k] = unit
        trial.update(provisional)
        mod_assets = dict(assets, **mod.assets)

        def resolver(name, mod_assets=mod_assets):
            if not isinstance(name, str) or Path(name).name != name:
                return None
            if name in mod_assets:
                return mod_assets[name]
            if name in body_assets and body_root is not None:
                return Path(body_root) / name
            if stock_root is not None and stock_assets(name):
                return Path(stock_root) / name
            return None
        dims = LazyDims(resolver)
        try:
            for key, unit in provisional.items():
                unit.update(behaviors.internal_fields(behaviors.resolve(unit, trial, library)))
            for key, unit in provisional.items():
                descriptor = unit.get('sprite_descriptor')
                if descriptor and descriptor not in mod.assets:
                    raise ValueError(f'{key}: sprite descriptor {descriptor} must be a mod asset')
                try:
                    cc.check_unit(unit)
                    cc.check_references(unit, trial)
                    content_sounds.check_unit_sounds(unit, visible_sounds)
                    cc.check_unit_assets(unit, dims, lambda name: mod_assets[name], stock_assets)
                except (ValueError, KeyError, TypeError) as error:
                    raise ValueError(f'{key}: {error}')
            for entry in mod.patches:
                if entry['target'].startswith('unit:'):
                    pass
                elif entry['target'] not in trial:
                    raise ValueError(f'patch target {entry["target"]} is not visible to {mod_id}')
                if entry['field'] in RATIONAL_FIELDS:
                    v = entry['value']
                    if not (isinstance(v, list) and len(v) == 2 and all(isinstance(x, int) and not isinstance(x, bool) and 0 < x <= 10000 for x in v) and v[0] <= 100 * v[1]):
                        raise ValueError(f'patch {entry["target"]}.{entry["field"]}: expected a rational [a, b]')
                elif not (isinstance(entry['value'], int) and not isinstance(entry['value'], bool)
                          and (0 < entry['value'] <= 100000 if entry['field'] == 'ap' else 0 <= entry['value'] <= 32767)):
                    raise ValueError(f'patch {entry["target"]}.{entry["field"]}: integer outside range')
            if mod.events:
                known_sounds = dict(body_sounds) if isinstance(body_sounds, dict) else dict.fromkeys(body_sounds, 'se')
                known_sounds.update((e['key'], e.get('type', 'se')) for m in accepted + [mod] for e in m.sounds)
                scenes = body_scene_keys(campaign_root) | {s.get('key') for m in accepted + [mod] if m.campaign
                                                           for s in m.campaign.get('scenes', [])}
                allowed = {'s1xlv', mod_id} | deps
                for event in mod.events:
                    event_content.check_references(event, set(all_units) | set(provisional), known_sounds, scenes,
                                                   lambda prefix: prefix in allowed)
            if mod.campaign is not None:
                import campaign_catalog
                fragment = {'owner': mod_id, 'raw': mod.campaign, 'assets': mod.assets, 'visible': deps}
                units_seen = [{'key': k, 'id': 0} for k in {**all_units, **provisional}]
                known_sounds = dict(body_sounds) if isinstance(body_sounds, dict) else dict.fromkeys(body_sounds, 'se')
                known_sounds.update((e['key'], e.get('type', 'se')) for m in accepted + [mod] for e in m.sounds)
                campaign_catalog.Catalog(campaign_root, units_seen, fragments + [fragment], cache=campaign_cache, sounds=known_sounds)
        except (ValueError, KeyError, TypeError, OSError, AttributeError) as error:
            mod.state, mod.reasons = 'skipped', [str(error)]
            continue
        accepted.append(mod)
        if mod.campaign is not None:
            fragments.append({'owner': mod_id, 'raw': mod.campaign, 'assets': mod.assets, 'visible': deps})
        all_units.update({k: dict(u, id=0) for k, u in mod.units.items()})
        assets.update(mod.assets)
    # ID：持久化映射，优先沿用存档进度记录的 ID。
    mod_keys = [k for mod in accepted for k in mod.units]
    ids = id_map.assign(mod_keys, preferred=preferred_ids or {}) if id_map is not None and mod_keys else {}
    units = []
    for mod in accepted:
        for key, unit in mod.units.items():
            assembled = {'key': key, 'id': ids[key]}
            assembled.update((n, v) for n, v in copy.deepcopy(unit).items() if n != 'key')
            assembled['icon'] = dict(index=340 + ids[key] - content_ids.UNIT_ID_BASE, **unit['icon'])
            units.append(assembled)
    by_key = dict(body_units)
    by_key.update({u['key']: u for u in units})
    for unit in units:
        unit.update(behaviors.internal_fields(behaviors.resolve(unit, by_key, library)))
    # 补丁：按加载顺序应用到合并后的单位数据（本体单位副本与模组单位）。
    applied = []
    original_patches = {}
    for mod in accepted:
        for entry in mod.patches:
            if entry['target'].startswith('unit:'):
                # 原版单位：只记录，由 CommunityContent.install 写入原版数据行与倍率组。
                stock = original_patches.setdefault(original_uid(entry['target']), {})
                previous = stock.get(entry['field'])
                stock[entry['field']] = copy.deepcopy(entry['value'])
                applied.append({'mod': mod.id, 'target': entry['target'], 'field': entry['field'], 'value': entry['value'],
                                'previous': previous, 'source': entry['source']})
                continue
            target = by_key[entry['target']]
            previous = target.get(entry['field'])
            target[entry['field']] = copy.deepcopy(entry['value'])
            applied.append({'mod': mod.id, 'target': entry['target'], 'field': entry['field'], 'value': entry['value'],
                            'previous': previous, 'source': entry['source']})
    if campaigns is not None:
        campaigns.extend(fragments)
    if sounds is not None:
        sounds.extend(e for mod in accepted for e in mod.sounds)
    if events is not None:
        events.extend(e for mod in accepted for e in mod.events)
    for mod in accepted:
        mod.state = 'loaded'
    for mod_id in missing:
        stub = Mod(Path(mod_id)); stub.id = mod_id; stub.state = 'missing'; stub.reasons = ['enabled but not installed']
        statuses.append(stub)
    return units, assets, applied, [m.status() for m in statuses]

