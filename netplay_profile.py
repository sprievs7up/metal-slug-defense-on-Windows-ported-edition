"""联机玩家资料与发展进度（N6a，docs/netcode/N6A_REGULAR_NETPLAY_2026-10-10.md）。

- 玩家名称与本地联机战绩：原版名称取自 Google Play（CGameCenter 显示名称），存档中没有名称字段；本移植版保存在当前存档目录的
  netplay_profile.json（R7 补充：名称存于当前存档；随普通、满级等各存档入口区分）。战绩只在本机统计（R8：不写入原生 Wi-Fi 字段，不计 RP）。
- 常规联机的编队与发展进度（R7）：编队为存档当前默认编队（GetDeckUnitSaveData(格, -1)，与 World / EVENT 出击的 BattleStartSetUnit 相同），
  等级为存档单位等级；据点基础状态由原生 BattleStartCreateBattleStatus 按我方阵营强化与人质效果计算。
  传送给对方的基础状态与原版 Wi-Fi 对手数据（MakePlayerInfo → BattleStartSetStatusEnemy）相同：第 3 字为 40，第 8、14–16 字为 0
  （原版只用于本机玩家的战前道具与人质，联机模式中不生效）；双方都按此规则建立，模拟对称。
"""
import json
import math
import os
import struct
import time
import unicodedata

PROFILE_NAME = 'netplay_profile.json'
SCHEMA = 1
NAME_MAX_CHARS = 16
NAME_MAX_BYTES = 48                     # 原生名牌复制至多 0x30 字节（MakePlayerInfo 0x21e79e）
STATUS_WORDS = 17
STATUS_FLOATS = (9, 10, 11, 12, 13)    # 人质效果倍率（单精度浮点位模式）
STATUS_BYTES = (6, 7)                   # 原版对手数据中以 1 字节传送


def profile_path(p):
    return p.saves / PROFILE_NAME


def default_profile():
    """port：远程房主使用的端口（N6b，0 为默认 47631）；last_address：上次按地址加入时输入的地址。"""
    return {'schema': SCHEMA, 'name': '', 'record': {'wins': 0, 'losses': 0, 'draws': 0}, 'port': 0, 'last_address': '',
            'updated': None}


def load(p):
    profile = default_profile()
    path = profile_path(p)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return profile
    if isinstance(data, dict):
        name = data.get('name')
        if isinstance(name, str) and clean_name(name) == name:
            profile['name'] = name
        record = data.get('record') or {}
        for key in ('wins', 'losses', 'draws'):
            value = record.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 10**7:
                profile['record'][key] = value
        port = data.get('port')
        if isinstance(port, int) and not isinstance(port, bool) and (port == 0 or 1024 <= port < 65536):
            profile['port'] = port
        address = data.get('last_address')
        if isinstance(address, str) and len(address) <= 80 and address.isprintable():
            profile['last_address'] = address
        profile['updated'] = data.get('updated')
    return profile


def save(p, profile):
    """临时文件写入后替换（与社区进度相同的原子写法）。"""
    path = profile_path(p)
    data = dict(profile, schema=SCHEMA, updated=time.strftime('%Y-%m-%d %H:%M:%S'))
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(temporary, path)
    return data


def clean_name(text):
    """去掉首尾空白与控制字符；超过 NAME_MAX_CHARS 个字符或 NAME_MAX_BYTES 字节（UTF-8）时截断。"""
    if not isinstance(text, str):
        return ''
    text = ''.join(ch for ch in text if unicodedata.category(ch)[0] != 'C').strip()
    text = text[:NAME_MAX_CHARS]
    while len(text.encode('utf-8')) > NAME_MAX_BYTES:
        text = text[:-1]
    return text.strip()


def valid_name(text):
    return bool(text) and clean_name(text) == text


def record_result(p, outcome):
    """一轮结束后更新本地战绩：outcome 为 'win'、'loss' 或 'draw'；其他（未打完、断线等）不计。"""
    if outcome not in ('win', 'loss', 'draw'):
        return load(p)
    profile = load(p)
    key = {'win': 'wins', 'loss': 'losses', 'draw': 'draws'}[outcome]
    profile['record'][key] += 1
    return save(p, profile)


# ---------- 存档的发展进度 ----------
def current_deck(p):
    """存档当前默认编队：10 格 [单位, 等级(1–40)] 或 None；社区单位写稳定键（联机编队格式，netplay_match.validate_deck）。"""
    app = p.app_instance()
    community = getattr(p, 'community', None)
    keys = {u['id']: u['key'] for u in community.units} if community is not None else {}
    internal = {u['id'] for u in community.units if u.get('internal_only')} if community is not None else set()
    deck = []
    for slot in range(10):
        uid = p.call('_ZN7AppMain19GetDeckUnitSaveDataEii', app, slot, 0xffffffff)
        if uid in (0, 0xffffffff) or uid & 0x80000000 or uid in internal or (uid >= 400 and uid not in keys):
            deck.append(None)
            continue
        level = p.call('_ZN7AppMain20GetUnitLevelSaveDataE6UnitID', app, uid)
        level = level - (1 << 32) if level & 0x80000000 else level
        if level < 0:                                    # 未拥有（-1）：原生出击同样不会建立该格
            deck.append(None)
            continue
        deck.append([keys.get(uid, uid), max(1, min(40, level + 1))])
    return deck


def base_status(p):
    """本方据点基础状态（17 个 uint32），规则同原版 Wi-Fi 对手数据（见模块说明）。"""
    app = p.app_instance()
    scratch = p.alloc(0x48)
    try:
        p.write(scratch, bytes(0x48))
        p.call('_ZN7AppMain29BattleStartCreateBattleStatusERN16BattleController10BaseStatusE', app, scratch)
        words = list(struct.unpack('<17I', p.read(scratch, 0x44)))
    finally:
        p.free(scratch)
    return normalize_status(words)


def normalize_status(words):
    words = [int(v) & 0xffffffff for v in words]
    words[3] = 40
    for index in (8, 14, 15, 16):
        words[index] = 0
    for index in STATUS_BYTES:
        words[index] &= 0xff
    return words


def status_error(words):
    """对方发送的基础状态的结构检查（不能防止修改过的客户端谎报，只拒绝格式错误与明显越界的值）。"""
    if not isinstance(words, list) or len(words) != STATUS_WORDS:
        return 'status_size'
    if any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 0xffffffff for v in words):
        return 'status_value'
    if normalize_status(words) != words:
        return 'status_rule'
    if words[0] > 200000 or words[1] > 200000 or words[2] > 200000:
        return 'status_range'
    for index in STATUS_FLOATS:
        value = struct.unpack('<f', struct.pack('<I', words[index]))[0]
        if not math.isfinite(value) or not 0.0 <= value <= 100.0:
            return 'status_range'
    return None


def development(p):
    """常规联机本方的设定：编队、基础状态。"""
    return {'deck': current_deck(p), 'status': base_status(p)}
