"""联机分歧处理（N5，docs/netcode/N5_DESYNC_AND_TAMPER_2026-10-10.md）。

- 周期校验值的传送值（tag）：BLAKE2b(轮次、帧、发送方一侧、h、d) 的 64 位。接收方以本方的 h、d 按对方一侧计算后比较。
  对方只收到本方的 tag，不能把它原样发回冒充自己的校验值（原样发回必然不符）。
- 状态快照（snapshot）：计算周期校验值时一并保留的区域内容（BattleMain、双方控制器、各单位去指针后的字节与语义字段、
  对象管理器、单位数据表的 CRC32）。校验一致后即丢弃；分歧时双方交换分歧帧附近的快照，逐区域、逐字比较。
- 分歧报告（report）：第一个不一致的帧、不一致的区域（字段名与双方数值、不同的字及偏移）、双方已确认输入的比较、
  单位数据表中不同的单位数据行，以及中英文说明。N5.5 的回放校验沿用同一格式。
"""
import base64
import hashlib
import json
import struct
import time
import zlib
from array import array
from pathlib import Path

SCHEMA = 1
ROW_SIZE = 0x390
UNIT_BYTES = 0x3f0
MAX_WORDS = 12                   # 每个区域列出的不同字数上限
MAX_REGIONS = 40
SIDE_NAMES = ('P1', 'P2')
# 出兵格信息位于控制器 +12 起，每格 28 字节（getUnitInfo，N5 调研 probe_layout.json）
SLOT_BASE, SLOT_SIZE = 12, 28
SLOT_FIELDS = {0: ('出兵 AP', 'deploy cost'), 0xc: ('可用', 'enabled'), 0x10: ('UnitID', 'UnitID'),
               0x18: ('冷却', 'cooldown')}
CONTROLLER_FIELDS = {1028: ('AP', 'AP')}
UNIT_FIELDS = {0x128: ('UnitID', 'UnitID'), 0x60: ('实例编号', 'instance'), 0x8c: ('X 坐标', 'x'), 0x90: ('Y 坐标', 'y'),
               776: ('生命', 'HP')}


def tag(number, frame, side, h, d):
    raw = struct.pack('<HiBII', number & 0xffff, frame, side & 1, h & 0xffffffff, d & 0xffffffff)
    return int.from_bytes(hashlib.blake2b(b'msd-netplay-checksum' + raw, digest_size=8).digest(), 'little')


def short_digest(raw):
    return hashlib.blake2b(raw, digest_size=8).hexdigest()


def pack(raw):
    return base64.b64encode(zlib.compress(raw, 6)).decode('ascii')


def unpack(text):
    return zlib.decompress(base64.b64decode(text))


def as_float(word):
    """按单精度浮点解释（坐标、生命等）；非规格化数（小整数）与过大的值不作浮点显示。"""
    value = struct.unpack('<f', struct.pack('<I', word & 0xffffffff))[0]
    if value != value or abs(value) >= 1e9 or 0 < abs(value) < 1e-6:
        return None
    return round(value, 3)


# ---------- 快照编码（随 desync_data 消息传送） ----------
def encode_snapshot(snapshot):
    return {'frame': snapshot['frame'], 'h': snapshot['h'], 'd': snapshot['d'],
            'battle_frame': snapshot['battle_frame'], 'rng48': snapshot['rng48'], 'sides': snapshot['sides'],
            'units': [list(u) for u in snapshot['units']], 'table_crc': snapshot.get('table_crc'),
            'blocks': {name: pack(raw) for name, raw in snapshot['blocks'].items() if raw is not None},
            'unit_bytes': pack(b''.join(snapshot['unit_bytes']))}


def decode_snapshot(data):
    raw = unpack(data['unit_bytes'])
    snapshot = dict(data)
    snapshot['blocks'] = {name: unpack(text) for name, text in data.get('blocks', {}).items()}
    snapshot['unit_bytes'] = [raw[i:i + UNIT_BYTES] for i in range(0, len(raw), UNIT_BYTES)]
    snapshot['units'] = [tuple(u) for u in data.get('units', [])]
    return snapshot


def row_digests(raw, size=ROW_SIZE):
    """单位数据表逐行 CRC32（报告当前各数据行，用于指出被改动的单位）。"""
    return pack(array('I', [zlib.crc32(raw[i:i + size]) for i in range(0, len(raw) - size + 1, size)]).tobytes())


# ---------- 比较 ----------
def word_differences(mine, theirs, names=None, limit=MAX_WORDS):
    count = min(len(mine), len(theirs)) // 4
    a = struct.unpack('<%dI' % count, mine[:count * 4])
    b = struct.unpack('<%dI' % count, theirs[:count * 4])
    out, total = [], 0
    for index in range(count):
        if a[index] != b[index]:
            total += 1
            if len(out) < limit:
                offset = index * 4
                entry = {'offset': hex(offset), 'local': a[index], 'remote': b[index],
                         'local_float': as_float(a[index]), 'remote_float': as_float(b[index])}
                name = (names or (lambda o: None))(offset)
                if name:
                    entry['name'] = name
                out.append(entry)
    return out, total


def controller_name(offset):
    if offset in CONTROLLER_FIELDS:
        return CONTROLLER_FIELDS[offset][0]
    if SLOT_BASE <= offset < SLOT_BASE + 10 * SLOT_SIZE:
        slot, field = divmod(offset - SLOT_BASE, SLOT_SIZE)
        label = SLOT_FIELDS.get(field, ('+%#x' % field, ''))[0]
        return f'第 {slot + 1} 格 {label}'
    return None


def unit_name(offset):
    for base, (zh, _) in UNIT_FIELDS.items():
        if base <= offset < base + 4:
            return zh
    return None


def region(kind, zh, en, fields=None, words=None, total=0, **extra):
    return dict(extra, kind=kind, zh=zh, en=en, fields=fields or [], words=words or [], words_total=total)


def compare_snapshots(mine, theirs, local_side):
    """同一帧双方快照的区域差异。返回区域列表（按 BattleMain、宿主随机数、P1、P2、单位、对象管理器、数据表的顺序）。"""
    regions = []
    if mine['battle_frame'] != theirs['battle_frame']:
        regions.append(region('battle', 'BattleMain +0x48（语义字段）', 'BattleMain +0x48 (semantic field)',
                              fields=[{'name': '+0x48', 'local': mine['battle_frame'], 'remote': theirs['battle_frame']}]))
    if mine['rng48'] != theirs['rng48']:
        regions.append(region('rng', '宿主随机数状态（lrand48）', 'Host random state (lrand48)',
                              fields=[{'name': 'lrand48', 'local': mine['rng48'], 'remote': theirs['rng48']}]))
    words, total = word_differences(mine['blocks'].get('main', b''), theirs['blocks'].get('main', b''))
    if total:
        regions.append(region('main', 'BattleMain', 'BattleMain', words=words, total=total))
    for side in (0, 1):
        name = SIDE_NAMES[side]
        a, b = mine['sides'][side], theirs['sides'][side]
        fields = []
        if a['ap'] != b['ap']:
            fields.append({'name': 'AP', 'local': a['ap'], 'remote': b['ap']})
        if a['kyoten'] != b['kyoten']:
            fields.append({'name': '据点等级', 'local': a['kyoten'], 'remote': b['kyoten']})
        for slot, (x, y) in enumerate(zip(a['cooldowns'], b['cooldowns'])):
            if x != y:
                fields.append({'name': f'第 {slot + 1} 格冷却', 'local': x, 'remote': y})
        words, total = word_differences(mine['blocks'].get(name, b''), theirs['blocks'].get(name, b''), controller_name)
        if fields or total:
            who = '本方' if side == local_side else '对方'
            regions.append(region('controller', f'{name}（{who}）控制器', f'{name} controller', fields, words, total,
                                  side=side))

    def unit_label(team_name, uid, instance):
        # UnitID 0 为据点（LAB 对战的双方据点在单位列表中，UnitID 字为 0）
        if uid == 0:
            return f'{team_name} 据点（实例 {instance}）', f'{team_name} base (instance {instance})'
        return f'{team_name} 单位 UnitID {uid}（实例 {instance}）', f'{team_name} unit UnitID {uid} (instance {instance})'

    local_units = {(u[0], u[2]): (u, raw) for u, raw in zip(mine['units'], mine['unit_bytes'])}
    remote_units = {(u[0], u[2]): (u, raw) for u, raw in zip(theirs['units'], theirs['unit_bytes'])}
    for key in sorted(set(local_units) | set(remote_units)):
        team, instance = key
        side_name = SIDE_NAMES[team] if team in (0, 1) else str(team)
        if key not in remote_units:
            u = local_units[key][0]
            zh, en = unit_label(side_name, u[1], instance)
            regions.append(region('unit_only_local', zh + '只在本方存在', en + ' exists only locally',
                                  team=team, unit_id=u[1], instance=instance))
            continue
        if key not in local_units:
            u = remote_units[key][0]
            zh, en = unit_label(side_name, u[1], instance)
            regions.append(region('unit_only_remote', zh + '只在对方存在', en + ' exists only on the peer',
                                  team=team, unit_id=u[1], instance=instance))
            continue
        (a, raw_a), (b, raw_b) = local_units[key], remote_units[key]
        fields = []
        for index, field_name in ((1, 'UnitID'), (3, 'X 坐标'), (4, 'Y 坐标'), (5, '生命')):
            if a[index] != b[index]:
                signed = index == 5                         # 生命（+776）为有符号整数；坐标为单精度浮点
                fields.append({'name': field_name,
                               'local': a[index] - (1 << 32) if signed and a[index] & 0x80000000 else a[index],
                               'remote': b[index] - (1 << 32) if signed and b[index] & 0x80000000 else b[index],
                               'local_float': as_float(a[index]) if index in (3, 4) else None,
                               'remote_float': as_float(b[index]) if index in (3, 4) else None})
        words, total = word_differences(raw_a, raw_b, unit_name)
        if fields or total:
            zh, en = unit_label(side_name, a[1], instance)
            regions.append(region('unit', zh, en, fields, words, total, team=team, unit_id=a[1], instance=instance))
    words, total = word_differences(mine['blocks'].get('manager', b''), theirs['blocks'].get('manager', b''))
    if total:
        regions.append(region('manager', 'BattleObjectManager', 'BattleObjectManager', words=words, total=total))
    if mine.get('table_crc') is not None and theirs.get('table_crc') is not None and mine['table_crc'] != theirs['table_crc']:
        regions.append(region('table', '单位数据表（BattleInfo 数据行）', 'Unit data table (BattleInfo rows)',
                              fields=[{'name': 'CRC32', 'local': mine['table_crc'], 'remote': theirs['table_crc']}]))
    return regions[:MAX_REGIONS]


def table_rows(local_rows, remote_rows):
    """当前数据表逐行比较：不同的行号（即 UnitID）。"""
    if not local_rows or not remote_rows:
        return []
    a = array('I')
    a.frombytes(unpack(local_rows))
    b = array('I')
    b.frombytes(unpack(remote_rows))
    out = [uid for uid in range(min(len(a), len(b))) if a[uid] != b[uid]]
    if len(a) != len(b):
        out.append(f'count {len(a)} != {len(b)}')
    return out


def compare_inputs(mine, theirs):
    a = {f: (x, y) for f, x, y in mine or []}
    b = {f: (x, y) for f, x, y in theirs or []}
    common = sorted(set(a) & set(b))
    return {'compared': len(common), 'differ': [[f, list(a[f]), list(b[f])] for f in common if a[f] != b[f]][:20]}


# ---------- 报告 ----------
KIND_TEXT = {
    'checksum': ('对战状态不一致（周期校验值不同）', 'Battle state diverged (periodic checksum mismatch)'),
    'missing': ('长时间收不到对方的校验值', 'Peer checksums stopped arriving'),
    'frame0': ('开战时双方状态不同（第 0 帧）', 'States differ at battle start (frame 0)'),
    'replay': ('回放与原对战不一致', 'Replay diverged from the original battle'),
}


def build_report(local, remote, local_side, number=0, notes=None):
    """local / remote：双方 desync_data 的内容（remote 为 None 表示未收到对方数据）。"""
    kind = (local or {}).get('kind') or (remote or {}).get('kind') or 'checksum'
    report = {'schema': SCHEMA, 'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'round': number, 'local_side': local_side,
              'kind': kind, 'detected': {'local': (local or {}).get('detected'), 'remote': (remote or {}).get('detected')},
              'last_match': {'local': (local or {}).get('last_match'), 'remote': (remote or {}).get('last_match')},
              'peer_data': remote is not None, 'frame': None, 'checksums': None, 'regions': [], 'inputs': None,
              'table_rows': [], 'notes': notes or []}
    mine = {s['frame']: decode_snapshot(s) for s in (local or {}).get('snapshots', [])}
    theirs = {s['frame']: decode_snapshot(s) for s in (remote or {}).get('snapshots', [])} if remote else {}
    common = sorted(set(mine) & set(theirs))
    differing = [f for f in common if (mine[f]['h'], mine[f]['d']) != (theirs[f]['h'], theirs[f]['d'])]
    if differing:
        frame = differing[0]
        report['frame'] = frame
        report['battle_frame'] = {'local': mine[frame]['battle_frame'], 'remote': theirs[frame]['battle_frame']}
        report['checksums'] = {'local': [mine[frame]['h'], mine[frame]['d']], 'remote': [theirs[frame]['h'], theirs[frame]['d']]}
        report['regions'] = compare_snapshots(mine[frame], theirs[frame], local_side)
        report['matched_frames'] = [f for f in common if f not in differing]
    else:
        detected = [x.get('detected') for x in (local, remote) if x and x.get('detected') is not None]
        report['frame'] = detected[0] if detected else None
        report['matched_frames'] = common
    report['flags'] = []
    if kind == 'checksum' and remote is not None and common and not differing:
        # 双方快照（各自的 h、d）相同而对方传来的 tag 与之不符：对方发送的校验值不是由其状态计算的（例如原样发回本方的值）。
        report['flags'].append('forged_checksum')
        report['notes'].append({'zh': '双方该帧的状态相同，但对方发来的校验值与其状态不符（可能使用了修改过的程序）',
                                'en': 'States match, but the checksum sent by the peer does not match its state (modified program?)'})
    if remote is not None:
        report['inputs'] = compare_inputs(local.get('inputs'), remote.get('inputs'))
        report['table_rows'] = table_rows(local.get('rows'), remote.get('rows'))
    report['text'] = {'zh': describe(report, 'zh'), 'en': describe(report, 'en')}
    return report


def safe_report(local, remote, local_side, number=0, notes=None):
    """build_report 的保护包装：生成报告时出现异常（如对方发来格式不符的数据）不影响结束流程，返回只含基本信息与错误的报告。"""
    try:
        return build_report(local, remote, local_side, number, notes)
    except Exception as error:                      # noqa: BLE001  报告属于诊断信息，任何异常都不应中断联机流程
        kind = (local or {}).get('kind') or 'checksum'
        report = {'schema': SCHEMA, 'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'round': number, 'local_side': local_side,
                  'kind': kind, 'frame': (local or {}).get('detected'), 'peer_data': remote is not None, 'regions': [],
                  'table_rows': [], 'inputs': None, 'flags': ['report_error'], 'notes': notes or [],
                  'error': f'{type(error).__name__}: {error}'}
        title = KIND_TEXT.get(kind, KIND_TEXT['checksum'])
        report['text'] = {'zh': [title[0], '  分歧报告生成失败：' + report['error']],
                          'en': [title[1], '  Failed to build the desync report: ' + report['error']]}
        return report


def describe(report, language='zh'):
    zh = language == 'zh'
    title = KIND_TEXT.get(report['kind'], KIND_TEXT['checksum'])[0 if zh else 1]
    lines = [title + (f'：第 {report["frame"]} 帧' if zh else f': frame {report["frame"]}') if report['frame'] is not None else title]
    if not report['peer_data']:
        lines.append('未收到对方的分歧数据，只能报告本方检测结果' if zh else 'No divergence data from the peer; local detection only')
    for item in report['regions'][:12]:
        text = item['zh' if zh else 'en']
        details = [f"{f['name']} {f.get('local_float') if f.get('local_float') is not None else f['local']}"
                   f" / {f.get('remote_float') if f.get('remote_float') is not None else f['remote']}" for f in item['fields'][:4]]
        if item['words_total']:
            details.append((f'{item["words_total"]} 个字不同' if zh else f'{item["words_total"]} words differ'))
        lines.append('  ' + text + (('：' if zh else ': ') + '，'.join(details) if details else ''))
    if len(report['regions']) > 12:
        lines.append(('  ……另有 %d 个区域' if zh else '  ... %d more regions') % (len(report['regions']) - 12))
    if report['table_rows']:
        rows = ', '.join(str(x) for x in report['table_rows'][:8])
        lines.append(('  单位数据表中不同的数据行（UnitID）：' if zh else '  Differing unit data rows (UnitID): ') + rows)
    inputs = report.get('inputs')
    if inputs and inputs['differ']:
        lines.append(('  双方记录的已确认输入不同：%d 帧' if zh else '  Confirmed inputs differ on %d frames') % len(inputs['differ']))
    if report['kind'] == 'missing':
        lines.append('  对方停止发送校验值，可能使用了修改过的程序或网络异常' if zh
                     else '  The peer stopped sending checksums (modified program or network problem)')
    for note in report.get('notes', []):
        lines.append('  ' + str(note.get(language, note) if isinstance(note, dict) else note))
    return lines


def replay_report(frame, local, recorded, number=0, notes=None):
    """回放重算与录制的周期校验值不同（N5.5）：只有本方的重算结果，报告第一个不一致的帧与 h、d 中不同的部分。"""
    differ = [name for name, a, b in (('h', local[0], recorded[0]), ('d', local[1], recorded[1])) if a != b]
    report = {'schema': SCHEMA, 'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'round': number, 'local_side': None,
              'kind': 'replay', 'frame': frame, 'checksums': {'local': list(local), 'recorded': list(recorded)},
              'differ': differ, 'peer_data': False, 'regions': [], 'table_rows': [], 'inputs': None, 'flags': [],
              'notes': notes or []}
    zh = '语义校验（单位、AP、冷却等）不同' if 'h' in differ else '对象内存或单位数据表不同（语义字段相同）'
    en = 'semantic checksum differs' if 'h' in differ else 'object memory or unit data table differs (semantic fields match)'
    report['text'] = {'zh': [f"{KIND_TEXT['replay'][0]}：第 {frame} 帧", '  ' + zh] + ['  ' + str(n.get('zh', n)) for n in report['notes']],
                      'en': [f"{KIND_TEXT['replay'][1]}: frame {frame}", '  ' + en] + ['  ' + str(n.get('en', n)) for n in report['notes']]}
    return report


def save(report, directory):
    """写入 directory/desync_r<轮次>_f<帧>_<时间>.json，返回路径。"""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    frame = report.get('frame')
    path = directory / f"desync_r{report.get('round', 0)}_f{frame if frame is not None else 'x'}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


# ---------- 第 0 帧（开战前一刻）的比较 ----------
def frame0_differences(mine, theirs):
    """ready 消息（checksum、battle_frame、units）不同时的差异列表（与内容清单差异相同的格式：kind、item、zh、en）。"""
    out = []
    if mine.get('checksum') != theirs.get('checksum'):
        out.append({'kind': 'frame0', 'item': 'checksum', 'local': mine.get('checksum'), 'remote': theirs.get('checksum'),
                    'zh': '开战时状态校验值不同', 'en': 'Frame-0 state checksum differs'})
    if mine.get('battle_frame') != theirs.get('battle_frame'):
        out.append({'kind': 'frame0', 'item': 'battle_frame', 'local': mine.get('battle_frame'),
                    'remote': theirs.get('battle_frame'), 'zh': '开战时 BattleMain +0x48 不同', 'en': 'Frame-0 BattleMain +0x48 differs'})
    a = {(u[0], u[1]): u for u in mine.get('units') or []}
    b = {(u[0], u[1]): u for u in theirs.get('units') or []}
    for key in sorted(set(a) | set(b)):
        side, slot = key
        x, y = a.get(key), b.get(key)
        if x != y:
            uid = (x or y)[2]
            out.append({'kind': 'deck_unit', 'item': f'{SIDE_NAMES[side]} {slot + 1} UnitID {uid}', 'local': x, 'remote': y,
                        'zh': f'开战时单位实际数值不同：{SIDE_NAMES[side]} 第 {slot + 1} 格 UnitID {uid}',
                        'en': f'Unit numbers differ at battle start: {SIDE_NAMES[side]} slot {slot + 1} UnitID {uid}'})
    return out
