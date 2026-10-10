"""联机内容清单（模组 M7，docs/netcode/M7_CONTENT_MANIFEST_2026-10-10.md）。

对战双方在匹配时交换清单并逐项比较，任一差异即拒绝匹配，并返回差异说明。清单由游戏启动后实际载入的内容生成：
- game：显示版本与联机协议版本。
- core：核心库文件名与文件摘要、LAB 钩子、行为库与联机接口版本。
- host：参与战斗逻辑的宿主程序文件摘要（换行统一为 LF 后计算，CRLF 与 LF 视为相同）。
- behaviors：行为库各行为的版本。
- mods：已载入模组（加载顺序）的 id、版本与文件摘要。
- units：每个社区单位（本体与模组）的 UnitID、规范化单位记录摘要与“实际数值”摘要（安装后原生数据行，以及 Lv1/10/20/30/40
  经 getUnitStatus、getUnitCreateParams 得到的含倍率等级数值）。
- stock：原版单位 1–399 的实际数值摘要（同上，覆盖补丁后）；patches：覆盖补丁列表。
- sounds：自定义音效键与分配的 SoundID。
- content：本体内容目录（community_content、campaign_content）各文件摘要。

摘要为 BLAKE2b-256（content_digest；用户 2026-10-09 确认的联机内容摘要算法），文件摘要按“大小 + 修改时间”缓存。
单位数值以安装后的原生数据与原生等级计算结果比较（规范化数值），加载器、倍率或补丁造成的数值差异按单位逐项报告。
"""
from pathlib import Path
import json
import struct

import content_digest

SCHEMA = 1
PROTOCOL = 5                        # 联机协议版本（N6b 连接请求带房间码；N6a 每帧输入 32 位；N5 为 3；N4 为 2；N3 原型 netplay_transport 为 1）
ROOT = Path(__file__).resolve().parent
ROW_SIZE = 0x390
STATUS_SIZE, CREATE_SIZE = 0xec, 28       # BattleUnitStatus、BattleUnitCreateParams（与 unit_catalog 相同）
LEVELS = (1, 10, 20, 30, 40)
# 参与战斗逻辑或内容安装的宿主模块（变更会改变确定性模拟或安装结果）。界面、菜单与素材工具不在其中。
HOST_MODULES = ('probe.py', 'static_cpu.py', 'native_imports.py', 'native_audio.py', 'audio_bridge.py',
                'community_content.py', 'behaviors.py', 'mod_loader.py', 'content_ids.py', 'content_sounds.py',
                'content_locale.py', 'campaign_catalog.py', 'community_maps.py', 'battle_controls.py',
                'lab.py', 'lab_runtime.py', 'lab_stages.py', 'netplay_state.py', 'netplay_session.py',
                'netplay_transport.py', 'netplay_net.py', 'netplay_match.py', 'netplay_desync.py', 'netplay_spectate.py',
                'netplay_regular.py', 'netplay_profile.py', 'netplay_lobby.py', 'content_manifest.py', 'behavior_library.json', 'netplay_pool.json')
CONTENT_DIRS = ('community_content', 'campaign_content')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)


def digest_text(path, cache):
    raw = path.read_bytes()
    if path.suffix in ('.py', '.json', '.md', '.txt'):
        return content_digest.blake2(raw.replace(b'\r\n', b'\n'))
    return cache.digest(path, raw)


def folder_digests(folder, cache):
    folder = Path(folder)
    result = {}
    if folder.is_dir():
        for path in sorted(folder.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                result[path.relative_to(folder).as_posix()] = digest_text(path, cache)
    return result


def core_versions(lib):
    import ctypes
    versions = {}
    for name in ('msd_lab_hooks_version', 'msd_netplay_version', 'msd_community_unit_id_base',
                 'msd_community_sound_version', 'msd_community_icon_pages_version', 'msd_community_stock_profile_version'):
        function = getattr(lib, name, None)
        if function is not None:
            function.restype = ctypes.c_uint32
            versions[name] = function()
    manifest = getattr(lib, 'msd_behavior_manifest', None)
    if manifest is not None:
        manifest.restype = ctypes.c_char_p
        versions['behavior_manifest'] = content_digest.blake2(manifest())
    return versions


def build(p):
    """以已初始化的探针（社区内容已安装）生成内容清单。"""
    import branding
    cache = content_digest.DigestCache()
    community = getattr(p, 'community', None)
    library = Path(p.uc.library_path)
    manifest = {
        'schema': SCHEMA,
        'game': {'display_version': branding.load(ROOT)['display_version'], 'protocol': PROTOCOL},
        'core': {'library': library.name, 'digest': cache.digest(library, library.read_bytes()),
                 'versions': core_versions(p.uc.lib)},
        'host': {name: digest_text(ROOT / name, cache) for name in HOST_MODULES if (ROOT / name).is_file()},
        'content': {name: folder_digests(ROOT / name, cache) for name in CONTENT_DIRS},
        'behaviors': {}, 'mods': [], 'units': {}, 'stock': {}, 'patches': [], 'sounds': {},
    }
    try:
        import behaviors
        library_data, by_name = behaviors.load_library()
        manifest['behaviors'] = {name: entry.get('version') for name, entry in by_name.items()}
        manifest['behaviors']['_library'] = library_data.get('library_version')
    except Exception as error:                   # 行为库读取失败时仍生成清单，差异比较会指出
        manifest['behaviors'] = {'_error': type(error).__name__}
    info = p.call('_ZN10BattleInfo11getInstanceEv')
    db = p.word(info)
    rows, count = p.word(db + 4), p.word(db + 8)
    scratch = p.alloc(0x100)

    def numbers(uid):
        """安装后的原生数据行，以及 Lv1/10/20/30/40 的实际等级数值（getUnitStatus 含倍率处理、getUnitCreateParams 出击参数）。
        UnitID 字段置零（编号差异另行报告）。"""
        raw = bytearray(p.read(rows + uid * ROW_SIZE, ROW_SIZE)) if uid < count else bytearray()
        for level in LEVELS:
            p.write(scratch, bytes(0x100))
            p.call('_ZN10BattleInfo13getUnitStatusE6UnitIDiP16BattleUnitStatus', info, uid, level - 1, scratch)
            status = bytearray(p.read(scratch, STATUS_SIZE))
            status[0:4] = bytes(4)
            p.write(scratch, bytes(0x100))
            p.call('_ZN10BattleInfo19getUnitCreateParamsE6UnitIDiP22BattleUnitCreateParams', info, uid, level - 1, scratch)
            raw += status + p.read(scratch, CREATE_SIZE)
        if len(raw) >= 4 and uid < count:
            raw[0:4] = bytes(4)
        if uid >= 1024:                          # 社区单位：数值块中引用自身编号的字置零（编号差异另行报告）
            words = list(struct.unpack('<%dI' % (len(raw) // 4), raw))
            raw = struct.pack('<%dI' % len(words), *[0 if w == uid else w for w in words])
        return content_digest.blake2(bytes(raw))

    manifest['stock'] = {str(uid): numbers(uid) for uid in range(1, min(400, count))}
    if community is not None:
        mods_root = None
        try:
            import mod_loader
            mods_root = mod_loader.mods_dir(ROOT)
        except Exception:
            pass
        try:
            import mod_loader
            order = mod_loader.read_enabled()
        except Exception:
            order = []
        loaded = [s for s in getattr(community, 'mod_status', []) if s.get('state') == 'loaded']
        loaded.sort(key=lambda s: order.index(s['id']) if s['id'] in order else len(order))   # 实际加载顺序（启用列表顺序）
        for status in loaded:
            folder = Path(mods_root) / status['folder'] if mods_root else None
            files = folder_digests(folder, cache) if folder else {}
            manifest['mods'].append({'id': status['id'], 'version': status['version'],
                                     'digest': content_digest.blake2(canonical(files).encode('utf-8')), 'files': files})
        for unit in community.units:
            uid = unit['id']
            manifest['units'][unit['key']] = {'id': uid, 'record': content_digest.blake2(canonical(unit).encode('utf-8')),
                                              'numbers': numbers(uid), 'source': community.unit_source.get(unit['key'], 'body')}
        manifest['patches'] = [dict(entry) for entry in getattr(community, 'mod_patches', [])]
        manifest['sounds'] = {key: value for key, value in getattr(community, 'sound_ids', {}).items()}
    p.free(scratch)
    cache.save()
    return manifest


def digest(manifest):
    return content_digest.blake2(canonical(manifest).encode('utf-8'))


def summary(manifest):
    """各类别的摘要（握手时先比较；不同时再交换完整清单以列出差异）。"""
    return {key: content_digest.blake2(canonical(value).encode('utf-8')) for key, value in manifest.items()}


MESSAGES = {
    'schema': ('清单格式版本不同', 'Manifest schema differs'),
    'protocol': ('联机协议版本不同', 'Netplay protocol version differs'),
    'display_version': ('游戏版本不同', 'Game version differs'),
    'core': ('原生核心不同', 'Native core differs'),
    'core_version': ('核心接口版本不同', 'Core interface version differs'),
    'host': ('宿主程序文件不同', 'Host program file differs'),
    'content': ('本体内容文件不同', 'Built-in content file differs'),
    'behavior': ('行为库版本不同', 'Behavior library version differs'),
    'mod_missing': ('缺少模组', 'Missing mod'),
    'mod_extra': ('对方没有此模组', 'Peer lacks mod'),
    'mod_version': ('模组版本不同', 'Mod version differs'),
    'mod_files': ('模组文件不同', 'Mod files differ'),
    'mod_order': ('模组加载顺序不同', 'Mod load order differs'),
    'unit_missing': ('缺少单位', 'Missing unit'),
    'unit_extra': ('对方没有此单位', 'Peer lacks unit'),
    'unit_id': ('单位编号不同', 'Unit ID differs'),
    'unit_record': ('单位设定不同', 'Unit definition differs'),
    'unit_numbers': ('单位数值不同', 'Unit numbers differ'),
    'stock_numbers': ('原版单位数值不同', 'Original unit numbers differ'),
    'patches': ('覆盖补丁不同', 'Override patches differ'),
    'sound': ('音效不同', 'Sound differs'),
}


def diff(local, remote):
    """逐项比较两份清单；返回差异列表 [{'kind', 'item', 'local', 'remote', 'zh', 'en'}]，空列表表示一致。"""
    out = []

    def add(kind, item, mine=None, theirs=None):
        zh, en = MESSAGES[kind]
        out.append({'kind': kind, 'item': item, 'local': mine, 'remote': theirs,
                    'zh': f'{zh}：{item}' if item else zh, 'en': f'{en}: {item}' if item else en})

    if local.get('schema') != remote.get('schema'):
        add('schema', '', local.get('schema'), remote.get('schema'))
        return out
    lg, rg = local.get('game', {}), remote.get('game', {})
    if lg.get('protocol') != rg.get('protocol'):
        add('protocol', '', lg.get('protocol'), rg.get('protocol'))
    if lg.get('display_version') != rg.get('display_version'):
        add('display_version', '', lg.get('display_version'), rg.get('display_version'))
    lc, rc = local.get('core', {}), remote.get('core', {})
    if lc.get('digest') != rc.get('digest'):
        add('core', lc.get('library') or '', lc.get('library'), rc.get('library'))
    for name in sorted(set(lc.get('versions', {})) | set(rc.get('versions', {}))):
        if lc.get('versions', {}).get(name) != rc.get('versions', {}).get(name):
            add('core_version', name, lc.get('versions', {}).get(name), rc.get('versions', {}).get(name))
    for name in sorted(set(local.get('host', {})) | set(remote.get('host', {}))):
        if local['host'].get(name) != remote.get('host', {}).get(name):
            add('host', name)
    for folder in sorted(set(local.get('content', {})) | set(remote.get('content', {}))):
        mine, theirs = local.get('content', {}).get(folder, {}), remote.get('content', {}).get(folder, {})
        for name in sorted(set(mine) | set(theirs)):
            if mine.get(name) != theirs.get(name):
                add('content', f'{folder}/{name}', 'present' if name in mine else None, 'present' if name in theirs else None)
    for name in sorted(set(local.get('behaviors', {})) | set(remote.get('behaviors', {}))):
        if local['behaviors'].get(name) != remote.get('behaviors', {}).get(name):
            add('behavior', name, local['behaviors'].get(name), remote.get('behaviors', {}).get(name))
    lm = {m['id']: m for m in local.get('mods', [])}
    rm = {m['id']: m for m in remote.get('mods', [])}
    for mod_id in rm:
        if mod_id not in lm:
            add('mod_missing', f"{mod_id} {rm[mod_id].get('version')}", None, rm[mod_id].get('version'))
    for mod_id in lm:
        if mod_id not in rm:
            add('mod_extra', f"{mod_id} {lm[mod_id].get('version')}", lm[mod_id].get('version'), None)
        elif lm[mod_id].get('version') != rm[mod_id].get('version'):
            add('mod_version', mod_id, lm[mod_id].get('version'), rm[mod_id].get('version'))
        elif lm[mod_id].get('digest') != rm[mod_id].get('digest'):
            files = sorted(set(lm[mod_id].get('files', {})) | set(rm[mod_id].get('files', {})))
            changed = [f for f in files if lm[mod_id].get('files', {}).get(f) != rm[mod_id].get('files', {}).get(f)]
            add('mod_files', f"{mod_id}（{', '.join(changed[:5])}{'…' if len(changed) > 5 else ''}）")
    common = [m for m in lm if m in rm]
    if [m for m in common] != [m['id'] for m in remote.get('mods', []) if m['id'] in lm]:
        add('mod_order', ' → '.join(common), [m['id'] for m in local.get('mods', [])], [m['id'] for m in remote.get('mods', [])])
    lu, ru = local.get('units', {}), remote.get('units', {})
    for key in sorted(set(lu) | set(ru)):
        if key not in lu:
            add('unit_missing', key)
        elif key not in ru:
            add('unit_extra', key)
        else:
            if lu[key].get('id') != ru[key].get('id'):
                add('unit_id', key, lu[key].get('id'), ru[key].get('id'))
            if lu[key].get('numbers') != ru[key].get('numbers'):
                add('unit_numbers', key)
            elif lu[key].get('record') != ru[key].get('record'):
                add('unit_record', key)
    ls, rs = local.get('stock', {}), remote.get('stock', {})
    for uid in sorted(set(ls) | set(rs), key=int):
        if ls.get(uid) != rs.get(uid):
            add('stock_numbers', f'UnitID {uid}')
    if canonical(local.get('patches', [])) != canonical(remote.get('patches', [])):
        add('patches', '', len(local.get('patches', [])), len(remote.get('patches', [])))
    for key in sorted(set(local.get('sounds', {})) | set(remote.get('sounds', {}))):
        if local.get('sounds', {}).get(key) != remote.get('sounds', {}).get(key):
            add('sound', key, local.get('sounds', {}).get(key), remote.get('sounds', {}).get(key))
    return out


def report(differences, language='zh', limit=12):
    """拒绝匹配时显示的文字（每行一项，超过 limit 项时省略）。"""
    lines = [d[language] for d in differences[:limit]]
    if len(differences) > limit:
        lines.append(('……另有 %d 项差异' if language == 'zh' else '... %d more differences') % (len(differences) - limit))
    return '\n'.join(lines)


def encode(manifest):
    import zlib
    return zlib.compress(canonical(manifest).encode('utf-8'), 9)


def decode(raw):
    import zlib
    return json.loads(zlib.decompress(raw).decode('utf-8'))
