"""自定义音效（模组 M6）：本体与模组按稳定键登记音效文件，加载器分配原生音效表中未使用的 SoundID。

- 本体：community_content/content.json 的 "sounds" 列表，文件放在 community_content/。
- 模组：mod.json 的 content.sounds 指向目录，其中每个 *.json 为音效条目列表；文件为模组资源（assets/，以 "<模组 id>_" 开头）。
- 条目：{"key": 稳定键, "file": "<名称>.msdf", "type": "se"|"vo"|"bgm", "volume": 1–127（缺省 100）,
  "loop": [开始秒, 结束秒]（仅 bgm，可选）}。本体键以 "s1xlv." 开头，模组键以 "<模组 id>." 开头。
  文件为 MSDF（Ogg Vorbis 数据，以 OggS 开头），与原版音效文件相同。
- 引用：单位动作脚本 op23（播放音效）的参数可写音效键字符串，安装时换为分配的 SoundID。
  可见范围与单位引用相同：本体、本模组与所依赖模组。
- 分配：原生音效表（GetSoundData，651 条，SoundID 0–1030）之外、原生缓存数组（SoundID 0–1031）之内的空闲区段
  32–99、165–199、523–799，共 380 个；按本体、模组加载顺序依次分配，每次启动重新分配（SoundID 不写入存档）。
  1031 仍由扩展世界的关卡音乐使用。核查记录见 verification/m6_20261010/sound_refs.json（原生脚本与代码未引用这些区段）。
- 原生：核心 GetSoundData 钩子按社区头部 +152 的 1032 项指针表返回登记的记录（msd_community_sound_version）。
"""
from pathlib import Path
import json
import re
import struct

FREE_SOUND_IDS = tuple(range(32, 100)) + tuple(range(165, 200)) + tuple(range(523, 800))
NATIVE_SOUND_SLOTS = 1032
RECORD_SIZE = 24
# 类型 → (原生记录类型字, 复制其记录作为模板的原版 SoundID)。模板只提供其余字段，文件名、音量、循环点与 SoundID 均改写。
TYPES = {'se': (1, 201), 'vo': (2, 7), 'bgm': (0, 100)}
KEY_PATTERN = re.compile(r'[a-z][a-z0-9_]{1,31}\.[a-z0-9_][a-z0-9_.\-]{0,63}')
SOUND_OPCODE = 23


def check_entry(entry, prefix, resolve):
    """单个音效条目的静态检查；prefix 为键前缀（'s1xlv' 或模组 id）；resolve(文件名) 返回路径或 None。"""
    if not isinstance(entry, dict) or set(entry) - {'key', 'file', 'type', 'volume', 'loop'}:
        raise ValueError('sound entries contain key, file, type, volume and loop')
    key = entry.get('key')
    if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key) or key.split('.', 1)[0] != prefix:
        raise ValueError(f'sound key {key!r} must start with "{prefix}."')
    kind = entry.get('type', 'se')
    if kind not in TYPES:
        raise ValueError(f'{key}: type must be se, vo or bgm')
    volume = entry.get('volume', 100)
    if not isinstance(volume, int) or isinstance(volume, bool) or not 1 <= volume <= 127:
        raise ValueError(f'{key}: volume must be an integer 1–127')
    loop = entry.get('loop')
    if loop is not None:
        if kind != 'bgm' or not (isinstance(loop, list) and len(loop) == 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in loop)
                                 and 0 <= loop[0] < loop[1] <= 3600):
            raise ValueError(f'{key}: loop is [start, end] seconds for bgm entries')
    name = entry.get('file')
    if not isinstance(name, str) or Path(name).name != name or not name.endswith('.msdf'):
        raise ValueError(f'{key}: file must be a .msdf file name')
    source = resolve(name)
    if source is None:
        raise ValueError(f'{key}: missing sound file {name}')
    with open(source, 'rb') as stream:
        if stream.read(4) != b'OggS':
            raise ValueError(f'{key}: {name} is not Ogg Vorbis (MSDF) data')
    return source


def read_mod_sounds(folder, mod_id, assets):
    """模组 content.sounds 目录：每个 *.json 为条目列表。返回条目列表（文件须为本模组资源）。"""
    entries = []
    keys = set()
    for path in sorted(Path(folder).glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, list):
            raise ValueError(f'{path.name}: sound files contain a list of entries')
        for entry in data:
            check_entry(entry, mod_id, assets.get)
            if entry['key'] in keys:
                raise ValueError(f'duplicate sound key {entry["key"]}')
            keys.add(entry['key'])
            entries.append(dict(entry, source=str(assets[entry['file']])))
    return entries


def sound_references(unit):
    """单位动作脚本中以字符串写的音效键（op23）。"""
    return [cmd['values'][0] for commands in unit.get('animations', {}).values() for cmd in commands
            if cmd.get('opcode') == SOUND_OPCODE and cmd.get('values') and isinstance(cmd['values'][0], str)]


def check_unit_sounds(unit, visible):
    """单位引用的音效键须在可见范围内登记（visible：键集合）。"""
    for key in sound_references(unit):
        if key not in visible:
            raise ValueError(f'sound {key} is not registered or not visible')


def allocate(entries):
    """按登记顺序分配 SoundID；返回 键 → SoundID。"""
    if len(entries) > len(FREE_SOUND_IDS):
        raise ValueError(f'custom sound capacity exceeded ({len(entries)} > {len(FREE_SOUND_IDS)})')
    keys = [e['key'] for e in entries]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate sound keys')
    return dict(zip(keys, FREE_SOUND_IDS))


def resolve_animation(commands, ids):
    """把动作脚本中的音效键换为 SoundID（不修改原数据）。"""
    out = []
    for cmd in commands:
        values = cmd['values']
        if cmd['opcode'] == SOUND_OPCODE and values and isinstance(values[0], str):
            values = [ids[values[0]]] + list(values[1:])
        out.append({'opcode': cmd['opcode'], 'values': values})
    return out


def install(content, entries, ids):
    """写入音效记录与 SoundID 指针表；返回 (指针表地址, 条数)。content 为 CommunityContent（提供 p 与 alloc）。"""
    p = content.p
    if not entries:
        return 0, 0
    app = p.app_instance()
    table = [0] * NATIVE_SOUND_SLOTS
    for entry in entries:
        sid = ids[entry['key']]
        if p.call('_ZN7AppMain12GetSoundDataE7SoundID', app, sid):
            raise RuntimeError(f'SoundID {sid} is used by the original sound table')
        kind, template = TYPES[entry.get('type', 'se')]
        source = p.call('_ZN7AppMain12GetSoundDataE7SoundID', app, template)
        if not source:
            raise RuntimeError('missing original sound template')
        raw = bytearray(p.read(source, RECORD_SIZE))
        loop = entry.get('loop') or (0, 0)
        struct.pack_into('<Iff', raw, 0, p.cstr(entry['file']), float(loop[0]), float(loop[1]))
        struct.pack_into('<III', raw, 12, entry.get('volume', 100) * 256, sid, kind)
        table[sid] = content.alloc(raw)
    return content.alloc(struct.pack(f'<{NATIVE_SOUND_SLOTS}I', *table)), len(entries)
