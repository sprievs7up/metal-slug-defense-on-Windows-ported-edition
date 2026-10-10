"""联机对战的回滚会话（N2/N3，docs/netcode/N1_N2_ROLLBACK_2026-10-10.md）。

在 LAB 双人对战（GameMode 1，P1 为队伍 0，P2 为队伍 1）之上运行。双方只交换逐帧输入；本地不等待对方，
对方尚未到达的输入按“无操作”预测，真实输入到达且与预测不同时恢复到该帧之前的状态，以真实输入重新模拟到当前帧。

每帧输入（32 位，联机协议 4 起）：低 4 位为出兵槽位 + 1（0 为不出兵），0x10 据点升级，0x20 全体绝招，0x40 弹头车；
位 8–31 为单体绝招的单位实例号 + 1（0 为无；N6a 常规联机点击单位发动，与普通关卡相同）。
帧号：联机第 0 帧为战斗开始（isBattlePlaying 首次为真且 LAB 开战处理完成）的那一帧；第 k 帧先应用双方第 k 帧的输入，
再推进一个原生帧。输入延迟 d：本地在第 t 帧采集的输入安排在第 t+d 帧执行。

逻辑与表现分离（N2）：
- 重模拟帧只运行原生逐帧逻辑与 LAB 的战斗逻辑处理（fix_units 等），不提交绘制调用（核心渲染抑制）、不送出画面、
  不推进混音、不写存档与记录、不处理界面任务；GL 对象的新建与删除由 GLLedger 管理。
- 镜头（BattleScreen +8）属于本地视图：恢复快照时保留当前镜头位置。
- 双方逐帧状态校验（语义字段 + 去指针对象字节 + 单位数据表的 CRC32，见 capture_state）每 interval 帧比较一次，分歧即判定不同步。

分歧处理（N5，netplay_desync 与 docs/netcode/N5_DESYNC_AND_TAMPER_2026-10-10.md）：
- 计算校验值时保留该帧各区域的内容（快照），校验一致后丢弃；分歧时交给外层与对方交换，生成分歧报告。
- 传送的校验值为与本方一侧绑定的 tag，每包冗余携带最近 TAG_REDUNDANCY 个已确认帧；对方的校验值超过 MISSING_LIMIT 帧
  未到达（而对战仍在确认推进）也判定为分歧（missing）。
- 已确认帧的双方输入按帧记录（input_log），供分歧报告与 N5.5 回放使用。
- 开战时（第 0 帧）另计算双方编队各单位的实际数值摘要（deck_digests），随 ready 消息比较。
"""
import ctypes
import struct
import time
import zlib

import netplay_desync
from netplay_state import GuestJournal, GLLedger, HostState

DEPLOY_MASK, AP, SPECIAL, SLUG = 0x0f, 0x10, 0x20, 0x40
SURRENDER = 0x80                       # 投降（N6a）：不改变模拟；双方按同一已确认帧判定本轮结束
UNIT_SHIFT = 8                         # 位 8–31：单体绝招的单位实例号 + 1
INPUT_MASK = 0xffffffff                # 有效输入位
PB = '_ZN26BattleControllerPlayerBase'
STATUS_WORDS = 17                      # BattleController::BaseStatus（0x44 字节，setupBaseStatus 复制到控制器 +0x3b8）
POINTER_LOW, POINTER_HIGH = 0x10000000, 0x20000000
UNIT_BYTES = 0x3f0
ROW_SIZE = 0x390
UNIT_AURA = (0x3d0, 0x3d4)             # 单位绝招光圈的显示类型（setEffectRenderer 的 SpAttackEffectType）：按视角设定，本地界面
SCREEN_TOUCH = (4, 0x40)               # BattleScreenTouch（BattleMain +4 指向，0x40 字节）的 5 个触点（各 12 字节：x、y、按下）：本地界面
VIRTUAL_EPOCH = 1_800_000_000          # 虚拟时钟的起点（秒），加上比赛种子派生的偏移
NETPLAY_FLAGS = 2                      # 核心：确定性数学（位 1）；渲染抑制（位 0）只在重模拟帧临时置位
SUPPRESS_DRAW = 1
TAG_REDUNDANCY = 4                     # 每个校验包携带的最近已确认校验帧数
MISSING_LIMIT = 300                    # 本方已确认帧超过对方最近校验帧这么多帧（30 帧每秒，10 秒）仍未收到：判定 missing
MAX_REPORT_SNAPSHOTS = 6
KEEP_MATCHED = 4


def encode(slot=None, ap=False, special=False, slug=False, unit=None):
    return ((0 if slot is None else (slot + 1) & DEPLOY_MASK) | (AP if ap else 0) | (SPECIAL if special else 0)
            | (SLUG if slug else 0) | (0 if unit is None else ((unit + 1) & 0xffffff) << UNIT_SHIFT))


def battle_rand_address(p):
    """原生 battleRand 的状态（.bss：+0 序号（负数为未初始化），+4..+16 四个状态字），按 initBattleRand（0x1d16c4）的 PC 相对取址求得。"""
    import probe
    return (p.word(probe.BASE + 0x1d16fc) + 0x1d16d0 + probe.BASE) & 0xffffffff


class NetplayMode:
    """联机（与回放）对战期间的确定性设定，开战前进入、战斗结束后退出：
    分配清零、虚拟时钟、核心确定性数学、UCRT 关闭 FMA3 路径、各随机源以比赛种子设定、核心静态状态清零。"""

    def __init__(self, p, seed):
        self.p, self.seed = p, seed & 0xffffffff
        self.frame = 0                       # 当前模拟的联机帧（虚拟时钟据此推导）
        self.ucrt = None
        self.saved = None

    def clock(self, name, a):
        p = self.p
        ns = (VIRTUAL_EPOCH + self.seed % 86400) * 10**9 + self.frame * 33_333_333
        if name == 'clock_gettime':
            p.write(a[1], struct.pack('<II', ns // 10**9 & 0xffffffff, ns % 10**9))
            return 0
        if name == 'time':
            t = ns // 10**9
            if a[0]:
                p.put(a[0], t)
            return t & 0xffffffff
        return (self.frame * 33_333) & 0xffffffff

    def enter(self, reseed=True):
        p = self.p
        lib = p.uc.lib
        if not hasattr(lib, 'msd_netplay_version'):
            raise RuntimeError('原生核心缺少联机接口（需 r43 及以上）')
        lib.msd_netplay_get_flags.restype = ctypes.c_uint32
        self.saved = (p.zero_fill, p.virtual_clock, lib.msd_netplay_get_flags())
        p.zero_fill = True
        p.virtual_clock = self.clock
        lib.msd_netplay_set_flags(ctypes.c_uint32(NETPLAY_FLAGS))
        try:
            self.ucrt = ctypes.CDLL('ucrtbase')
            self.ucrt_fma3 = self.ucrt._get_FMA3_enable()
            self.ucrt._set_FMA3_enable(0)
        except (OSError, AttributeError):
            self.ucrt = None
        if reseed:
            self.reseed()

    def reseed(self):
        """开战前调用：宿主 lrand48、AppMain+0x9c 的 RandomMT、原生 battleRand、核心静态状态（AI 随机数等）。"""
        p, seed = self.p, self.seed
        p.rng48 = (seed << 16) | 0x330e
        p.call('_ZN8RandomMT7setSeedEj', p.word(p.app_instance() + 0x9c), seed)
        state = battle_rand_address(p)
        words, x = [], seed or 0x9e3779b9
        for _ in range(4):
            x = (x * 0x5851f42d + 0x14057b7f) & 0xffffffff
            words.append(x or 1)
        p.write(state, struct.pack('<i4I', 0, *words))
        p.uc.lib.msd_netplay_reset(ctypes.c_uint32(seed))

    def exit(self):
        if self.saved is None:
            return
        p = self.p
        p.zero_fill, p.virtual_clock, flags = self.saved
        p.uc.lib.msd_netplay_set_flags(ctypes.c_uint32(flags))
        if self.ucrt is not None:
            self.ucrt._set_FMA3_enable(self.ucrt_fma3)
        self.saved = None


def masked(raw):
    words = struct.unpack('<%dI' % (len(raw) // 4), raw[:len(raw) // 4 * 4])
    return struct.pack('<%dI' % len(words), *[0 if POINTER_LOW <= w < POINTER_HIGH else w for w in words])


def data_table(p):
    """原生单位数据表（BattleInfo 数据行，每行 0x390 字节）的地址与字节数。开战后不变（N5 调研：主菜单与战斗中 CRC 相同）。"""
    db = p.word(p.call('_ZN10BattleInfo11getInstanceEv'))
    return p.word(db + 4), p.word(db + 8) * ROW_SIZE


RESULT_FIELDS = (0x10, 0x60)           # BattleMain 中的战斗结果（BattleScene::battleFinish 经 scene+0x58 写入：胜负、用时等）


def capture_state(p, lab, controllers, manager_bytes=True, table=None, result_neutral=False):
    """战斗状态校验值（N0 第 6 节第 5 项）与该帧的区域快照。
    h：语义字段（帧号、宿主随机数、双方 AP/据点等级/10 格冷却、各单位 UnitID/实例/坐标/生命）的 CRC32；
    d：BattleMain、双方控制器（含 10 个出兵格信息）、各单位、对象管理器去指针后字节，以及单位数据表（N5）的 CRC32。分配清零后两台机器应逐帧相同。
    manager_bytes=False（联机第 0 帧）：不计对象管理器。BattleObjectManager 是静态单例，其中的暂存字段保留上一场战斗的数值，
    第 0 帧随进程历史而不同（全新进程为 0）；这些字段在第 30 帧前已被本场覆盖（N4 文档第 5.3 节：三种进程历史下第 30 帧起与全新进程相同）。
    单位数据表在战斗中不变，被改动（内存修改等）时 d 随之不同，分歧报告据此指出被改动的单位数据行。
    result_neutral（常规联机战斗停止后，N6a）：原生 battleFinish 按本方视角（BattleScene +0x2c，P2 一方为队伍 1）写入胜负与用时，
    两台机器不同；此后不计 BattleMain 的结果字段（RESULT_FIELDS，含 +0x48）。胜负另由双方据点生命与结束帧比较。
    读取范围（0x100 字节）超出 BattleMain 本身（0x60），其中的 BattleScreenTouch 触点记录（SCREEN_TOUCH）属于本地界面
    （常规联机中各自的鼠标点击），不计入校验值（N6a）。单位的绝招光圈显示类型（UNIT_AURA，Lab.fix_units 按视角设定：
    常规联机双方把全部单位设为类型 1，回放与观战按 P1 视角只设定对方单位）同样不计入（N6a）。"""
    main = p.word(p.app_instance() + 0xc220)
    mine, enemy = controllers
    rng48 = getattr(p, 'rng48', 0) & 0xffffffffffff
    raw_main = bytearray(p.read(main, 0x100))
    touch = p.word(main + 4)
    low, high = max(touch + SCREEN_TOUCH[0] - main, 0), min(touch + SCREEN_TOUCH[1] - main, 0x100)
    if touch and low < high:
        raw_main[low:high] = bytes(high - low)
    if result_neutral:
        raw_main[RESULT_FIELDS[0]:RESULT_FIELDS[1]] = bytes(RESULT_FIELDS[1] - RESULT_FIELDS[0])
    battle_frame = struct.unpack_from('<I', raw_main, 0x48)[0]
    sem = [battle_frame, rng48]
    blocks = {'main': masked(bytes(raw_main))}
    deep = zlib.crc32(blocks['main'])
    sides = []
    for name, controller in (('P1', mine), ('P2', enemy)):
        side = {'ap': p.call(PB + '5getAPEv', controller), 'kyoten': p.call(PB + '14getKyotenLevelEv', controller),
                'cooldowns': []}
        for slot in range(10):
            info = p.call('_ZNK16BattleController11getUnitInfoEi', controller, slot)
            side['cooldowns'].append(p.word(info + 0x18) if info else 0)
        sem += [side['ap'], side['kyoten']] + side['cooldowns']
        sides.append(side)
        blocks[name] = masked(p.read(controller, 0x440))
        deep = zlib.crc32(blocks[name], deep)
    manager = None
    units, unit_bytes = [], []
    for team in (0, 1):
        manager, members = lab.team_list(team)
        for unit in members:
            uid, instance = p.word(unit + 0x128), int.from_bytes(p.read(unit + 0x62, 2), 'little')
            x, y, hp = struct.unpack('<3I', p.read(unit + 0x8c, 8) + p.read(unit + 776, 4))
            sem += [uid, instance, x, y, hp]
            units.append((team, uid, instance, x, y, hp))
            raw = bytearray(p.read(unit, UNIT_BYTES))
            raw[UNIT_AURA[0]:UNIT_AURA[1]] = bytes(UNIT_AURA[1] - UNIT_AURA[0])
            unit_bytes.append(masked(bytes(raw)))
            deep = zlib.crc32(unit_bytes[-1], deep)
    blocks['manager'] = None
    if manager and manager_bytes:
        blocks['manager'] = masked(p.read(manager, 0x200))
        deep = zlib.crc32(blocks['manager'], deep)
    table_crc = None
    if table is not None:
        table_crc = zlib.crc32(p.read(*table))
        deep = zlib.crc32(struct.pack('<I', table_crc), deep)
    raw = struct.pack('<%dQ' % len(sem), *[v & 0xffffffffffffffff for v in sem])
    values = (zlib.crc32(raw), deep)
    snapshot = {'h': values[0], 'd': values[1], 'battle_frame': battle_frame, 'rng48': rng48, 'sides': sides,
                'units': units, 'unit_bytes': unit_bytes, 'blocks': blocks, 'table_crc': table_crc}
    return values, snapshot


def checksum(p, lab, controllers, manager_bytes=True, table=None):
    return capture_state(p, lab, controllers, manager_bytes, table)[0]


class NetplayBattle:
    """一场联机对战的回滚会话。local_side 为本地玩家的一方（0 = P1，1 = P2）。
    transport 为 None 时为本地参照（双方输入均由 local_input 提供，不回滚），用于确定性与回滚正确性对照。"""
    HISTORY = 900                            # 已确认帧的校验值、对方输入等的保留帧数

    def __init__(self, p, local_side, seed, delay=2, max_rollback=8, interval=30, transport=None, confirm_lag=0, journal=True):
        self.p, self.lab = p, p.lab
        self.local_side = local_side
        self.seed = seed
        self.delay = delay
        self.max_rollback = max_rollback
        self.interval = interval
        self.transport = transport
        self.confirm_lag = confirm_lag       # 无网络（本地参照与回滚测试）时保留可恢复的帧数
        self.use_journal = journal           # False：不建立回滚记录（不回滚的本地参照与回放校验，N5.5）
        self.mode = NetplayMode(p, seed)
        self.journal = None
        self.ledger = None
        self.host = None
        self.frame = 0                       # 最近模拟完成的帧
        self.local_inputs = {}               # 帧 → 本地输入
        self.remote_inputs = {}              # 帧 → 对方真实输入
        self.used_remote = {}                # 帧 → 模拟该帧时使用的对方输入（真实或预测）
        self.remote_contiguous = 0           # 对方输入已连续收到的最后一帧
        self.confirmed = 0
        self.rollback_from = None
        self.checksums = {}                  # 帧 → (h, d)，以最后一次模拟为准
        self.snapshots = {}                  # 帧 → 区域快照（校验一致后丢弃，N5）
        self.remote_checksums = {}           # 帧 → 对方 tag（N5）或 (h, d)（N3 传输）
        self.remote_latest = 0               # 已收到对方校验值的最近帧
        self.compared = {}
        self.last_match = 0                  # 最近一个双方一致的校验帧
        self.matched = []
        self.desync = None                   # 本方检测到的分歧：{'kind': 'checksum' | 'missing', 'frame', ...}
        self.frame_inputs = {}               # 帧 → 最后一次模拟该帧时的 (P1, P2) 输入
        self.input_log = []                  # 已确认帧的 (P1, P2) 输入，第 k 项为第 k + 1 帧（N5 报告、N5.5 回放）
        self.checksum_log = {}               # 已确认帧的全部周期校验值（不随保留期清理，N5.5 回放）
        self.on_commit = None                # 回调：(帧, 回滚记录) → 每帧提交后（回放关键帧，N5.5）
        self.on_applied = None               # 回调：(一方, 种类, 成功, 附加) → 显示帧中应用输入的结果（本地对战的提示，N5.5c）
        self.presenting = False
        self.ledger_confirm = True           # False：GL 对象登记不随确认清理（回放可跳回任意关键帧）
        self.deck_digests = None             # 第 0 帧：[[一方, 格, UnitID, 实际数值摘要]]
        self.table = None
        self.config = None
        self.sent_order = []
        self.controllers = None
        self.finished_frame = None           # 已确认的战斗结束帧
        self.surrender = None                # 已确认的投降：(帧, (P1 是否投降, P2 是否投降))
        self.local_input = None              # 回调：(帧, 一方) → 输入字节（脚本或界面采集）
        self.on_command = None               # 回调：本地双人对战键位指令（'left'、'deploy' 等）→ 由界面层转为输入
        self.events_end = {}                 # 帧 → 该帧模拟后战斗已停止（以最后一次模拟为准）
        self.audio_frames = {}               # 帧 → 该帧实际显示时各音频流运行的混音回调次数
        self.sent_checksums = set()
        self.se_sides = (0, 1)               # 出兵与弹头车的界面音效只为这些一方播放（常规联机只播放本方，N6a）
        self.ticks = 0
        self.stats = {'frames': 0, 'sync_waits': 0, 'audio_replay_blocks': 0, 'rollbacks': 0, 'rollback_frames': 0, 'max_rollback': 0, 'stalls': 0,
                      'resim_seconds': 0.0, 'step_seconds': 0.0, 'restore_seconds': 0.0, 'commit_seconds': 0.0,
                      'checksum_seconds': 0.0, 'max_tick_seconds': 0.0, 'max_rollback_seconds': 0.0}

    # ---------- 开战 ----------
    def match_config(self, stage, p1_deck, p2_deck, p1_status=None, p2_status=None):
        """本场设定（双方编队为 [单位, 等级(1–40)]，单位为 UnitID 或社区单位稳定键）：其余 LAB 开关一律关闭。
        p1_status / p2_status：双方的据点基础状态（17 字，常规联机由各自存档的发展进度决定，见 netplay_profile.base_status）；
        为 None 时沿用本机存档（LAB 与 N5.5 之前的行为）。"""
        config = {'stage_id': stage, 'player_deck': p1_deck, 'enemy_deck': p2_deck,
                  'player_base_level': 0, 'enemy_base_level': 0, 'player_hp_boost': 0, 'player_atk_boost': 0,
                  'enemy_hp_boost': 0, 'enemy_atk_boost': 0, 'player_support': 0, 'enemy_support': 0,
                  'full_control': False, 'player_ai': False, 'enemy_ai': False,
                  'player_auto_special': False, 'enemy_auto_special': False}
        if p1_status is not None and p2_status is not None:
            config.update(player_status=[int(v) & 0xffffffff for v in p1_status],
                          enemy_status=[int(v) & 0xffffffff for v in p2_status])
        return config

    def prepare(self, config):
        """在准备界面已打开（双人对战入口）时调用：进入确定性设定并开始战斗（之后由外层逐帧推进直至 ready()）。"""
        lab = self.lab
        self.config = dict(config)
        lab.config_override = dict(config)
        self.saved_lab_config = dict(lab.config)
        lab.config.update(config)            # 准备界面校验读取内存中的设定，不写入设定文件
        self.saved_support = (lab.player_support, lab.enemy_support)
        lab.player_support = int(config.get('player_support') or 0)    # 支援开关以本场设定为准（LAB 以属性生效，N5.5）
        lab.enemy_support = int(config.get('enemy_support') or 0)
        self.mode.enter(reseed=False)
        lab.start_hook = self.mode.reseed       # 在 Lab.start 开头、原生战斗初始化之前设定随机源
        lab.prep.command('start')

    def ready(self):
        """战斗已开始且 LAB 开战处理完成：可作为联机第 0 帧。"""
        lab, p = self.lab, self.p
        if not (lab.active and lab.applied and lab.network_wait_done):
            return False
        main = p.word(p.app_instance() + 0xc220)
        if not (main and p.word(main + 8) and p.call('_ZN10BattleMain15isBattlePlayingEv', main)):
            return False
        mine, enemy, _ = lab.controllers()
        return bool(mine and enemy)

    def begin(self):
        """以当前状态为联机第 0 帧：建立快照记录与 GL 对象登记，LAB 每帧处理交给本会话。"""
        p, lab = self.p, self.lab
        mine, enemy, _ = lab.controllers()
        self.controllers = (mine, enemy)
        self.screen = self.find_screen()
        self.journal = GuestJournal(p) if self.use_journal else None
        self.host = HostState(p)
        self.ledger = GLLedger(p.graphics) if hasattr(p, 'graphics') else None
        if self.ledger is not None:
            p.graphics.ledger = self.ledger
        self.frame = self.confirmed = self.remote_contiguous = 0
        self.mode.frame = 0
        self.table = data_table(p)
        self.record_checksum(0, False)
        self.battle_frame0 = p.word(p.word(p.app_instance() + 0xc220) + 0x48)
        self.deck_digests = self.unit_digests() if self.config else []
        self.checksum_log[0] = tuple(self.checksums[0])
        lab.netplay = self
        if self.journal is not None:
            self.journal.begin(0, self.host.capture())
        for frame in range(1, self.delay + 1):
            self.local_inputs[frame] = 0
        return self.checksums[0]

    def record_checksum(self, frame, manager_bytes=True):
        neutral = bool(self.config and self.config.get('player_status')) and frame > 0 and not self.playing()
        values, snapshot = self.timed('checksum_seconds', capture_state, self.p, self.lab, self.controllers, manager_bytes,
                                      self.table, neutral)
        snapshot['frame'] = frame
        self.checksums[frame] = values
        self.snapshots[frame] = snapshot
        return values

    def unit_digests(self):
        """双方编队各单位在本场等级下的实际数值摘要（getUnitStatus 与 getUnitCreateParams，含加载器倍率与覆盖补丁）。
        开战时随 ready 消息比较：伪造内容清单而实际数值不同的一方在开战前即被检出（N5）。"""
        p, lab = self.p, self.lab
        info = p.call('_ZN10BattleInfo11getInstanceEv')
        scratch = p.alloc(0x100)
        out = []
        try:
            for side, key in ((0, 'player_deck'), (1, 'enemy_deck')):
                for slot, entry in enumerate(lab.resolve_deck(self.config.get(key) or [])):
                    if entry is None:
                        continue
                    uid, level = entry
                    p.write(scratch, bytes(0x100))
                    p.call('_ZN10BattleInfo13getUnitStatusE6UnitIDiP16BattleUnitStatus', info, uid, level, scratch)
                    status = p.read(scratch, 0xec)
                    p.write(scratch, bytes(0x100))
                    p.call('_ZN10BattleInfo19getUnitCreateParamsE6UnitIDiP22BattleUnitCreateParams', info, uid, level, scratch)
                    out.append([side, slot, uid, netplay_desync.short_digest(status + p.read(scratch, 28))])
        finally:
            p.free(scratch)
        return out

    def base_hp(self):
        """双方据点的当前生命（单位 +776，有符号整数；回放记录的胜负依据）。"""
        p = self.p
        manager = p.call('_ZN19BattleObjectManager11getInstanceEv')
        values = []
        for team in (0, 1):
            base = p.call('_ZN19BattleObjectManager13getKyotenUnitE12BattleTeamID18BattleTeamMemberID', manager, team, 0)
            values.append(struct.unpack('<i', p.read(base + 776, 4))[0] if base else None)
        return values

    def end(self):
        """会话结束：执行推迟的 GL 删除，交还 LAB 的逐帧处理（之后由 LAB 正常结束战斗），退出确定性设定。"""
        p, lab = self.p, self.lab
        if self.ledger is not None:
            self.ledger.flush()
            p.graphics.ledger = None
        lab.netplay = None
        lab.config_override = None
        if getattr(self, 'saved_lab_config', None) is not None:
            lab.config = self.saved_lab_config
        if getattr(self, 'saved_support', None) is not None:
            lab.player_support, lab.enemy_support = self.saved_support
        self.mode.exit()
        if self.journal is not None:
            self.journal.close()                 # 释放回滚影子副本（再战时每场新建）

    def find_screen(self):
        p = self.p
        _, scene = self.lab.battle()
        operator = p.word(scene + 0x3c) if scene else 0
        return p.word(operator + 28) if operator else 0

    # ---------- 帧 ----------
    def timed(self, key, fn, *args):
        started = time.perf_counter()
        try:
            return fn(*args)
        finally:
            self.stats[key] += time.perf_counter() - started

    def playing(self):
        p = self.p
        main = p.word(p.app_instance() + 0xc220)
        return bool(main and p.word(main + 8) and p.call('_ZN10BattleMain15isBattlePlayingEv', main))

    def inputs_for(self, frame):
        """(P1, P2) 的输入；对方输入未到达时预测为无操作。"""
        local = self.local_inputs.get(frame, 0)
        if self.transport is None:
            remote = 0 if frame <= self.delay else self.local_input(frame, 1 - self.local_side) & INPUT_MASK
        else:
            remote = self.remote_inputs.get(frame, 0)
        self.used_remote[frame] = remote
        values = (local, remote) if self.local_side == 0 else (remote, local)
        self.frame_inputs[frame] = values
        return values

    def apply(self, side, value):
        """应用一方本帧输入。与 LAB 双人对战的出兵、据点升级、全体绝招、弹头车相同的原生调用；不写记录。
        on_applied 不为空且本帧显示时报告各项结果（本地对战据此显示与原双人对战相同的提示；联机为空）。"""
        if not value or not self.playing():
            return
        p, lab = self.p, self.lab
        controller = self.controllers[side]
        report = self.on_applied if self.presenting else None
        slot = (value & DEPLOY_MASK) - 1
        if slot >= 0:
            info = p.call('_ZNK16BattleController11getUnitInfoEi', controller, slot)
            reason = ('empty' if not info else 'unit_limit' if p.call('_ZNK16BattleController15isUnitCountOverEv', controller)
                      else None if p.call(PB + '12isUnitCreateEi', controller, slot) else 'cannot')
            created = False
            if reason is None:
                created = bool(p.call(p.word(p.word(controller) + 0x94), controller, slot))
                if created and side in self.se_sides:
                    p.call('_ZN17FrameworkInstance6playSEENS_9SoundTypeE7SoundIDi', 0, 8, 0)
                lab.reveal_slot(side == 1, slot)
            if report is not None:
                report(side, 'deploy', created, {'slot': slot, 'reason': reason, 'info': info})
        if value & AP:
            ok = bool(p.call(PB + '15isKyotenLevelupEv', controller))
            if ok:
                p.call(p.word(p.word(controller) + 0xa8), controller)
            if report is not None:
                report(side, 'ap', ok, None)
        if value & SPECIAL:
            from battle_controls import team_units
            ready = [u for u in team_units(p, controller)
                     if not p.read(u + 0x3d4, 1)[0] and p.call('_ZNK10BattleUnit10isSpAttackEv', u)]
            for unit in ready:
                p.call(p.word(p.word(controller) + 0x98), controller, int.from_bytes(p.read(unit + 0x62, 2), 'little'))
            if report is not None:
                report(side, 'special', bool(ready), {'count': len(ready)})
        unit_id = value >> UNIT_SHIFT
        if unit_id:
            # 单体绝招：与原生 onGameScreenTouchEnded 相同的条件（本方、绝招可用、+0x3d4 为 0）后经 vtable+0x98 发动。
            from battle_controls import team_units
            target = next((u for u in team_units(p, controller)
                           if int.from_bytes(p.read(u + 0x62, 2), 'little') == unit_id - 1), None)
            ok = bool(target and not p.read(target + 0x3d4, 1)[0] and p.call('_ZNK10BattleUnit10isSpAttackEv', target))
            if ok:
                p.call(p.word(p.word(controller) + 0x98), controller, unit_id - 1)
            if report is not None:
                report(side, 'special_unit', ok, {'unit': unit_id - 1})
        if value & SLUG:
            ok = bool(p.call(PB + '16isUseMetasuraHouEv', controller))
            if ok:
                if side in self.se_sides and self.se_sides != (0, 1):
                    p.call('_ZN17FrameworkInstance6playSEENS_9SoundTypeE7SoundIDi', 0, 12, 0)   # 原生底栏按下弹头车的音效
                p.call(p.word(p.word(controller) + 0xa0), controller)
            if report is not None:
                report(side, 'slug', ok, None)

    def logic_tick(self):
        """LAB 双人对战每帧的战斗逻辑部分（与 Lab.update 中开战后的处理相同顺序）：头部、优势设定、联机修正。"""
        lab = self.lab
        mine, enemy = self.controllers
        lab.publish_enemy(enemy)
        lab.apply_advantage(mine, enemy)
        if self.playing():
            lab.fix_units(mine, enemy)

    def lab_update(self):
        """实际显示帧中 Lab.update 的替代：本地界面指令转为输入，表现层（选中格光标、镜头），再做逻辑部分。"""
        lab = self.lab
        while lab.commands:
            command = lab.commands.popleft()
            if command[0] == 'vs' and command[1] == self.local_side and self.on_command is not None:
                self.on_command(command[2])
        lab.vs_view.prepare()
        if lab.vs_battle() and not lab.menu.open:
            lab.vs_camera.update()
        self.logic_tick()

    def logic_step(self):
        """重模拟帧：原生逐帧处理（渲染抑制）与战斗逻辑，不送出画面、不推进混音、不保存。"""
        p = self.p
        lib = p.uc.lib
        lib.msd_netplay_set_flags(ctypes.c_uint32(NETPLAY_FLAGS | SUPPRESS_DRAW))
        try:
            p.native('step')               # p.frame 只计实际显示帧（音频按显示帧计时，见 audio_replay）
            while p.pending:
                name, args = p.pending.pop(0)
                if isinstance(name, int):
                    p.call(name, *args)
                else:
                    p.native(name, *args)
            from local_platform import pump
            pump(p)
            self.logic_tick()
        finally:
            lib.msd_netplay_set_flags(ctypes.c_uint32(NETPLAY_FLAGS))

    def simulate(self, frame, present):
        p = self.p
        if frame != self.frame + 1:
            raise RuntimeError(f'联机帧须逐帧推进：{self.frame} → {frame}')
        self.mode.frame = frame
        self.presenting = present
        if self.ledger is not None:
            self.ledger.frame = frame
        if p.pending:
            raise RuntimeError('帧边界存在未执行的原生线程请求')
        values = self.inputs_for(frame)
        for side in (0, 1):
            self.apply(side, values[side])
        started = time.perf_counter()
        if present:
            before = self.audio_callbacks()
            p.step_frame()
            after = self.audio_callbacks()
            self.audio_frames[frame] = {obj: n - before.get(obj, n) for obj, n in after.items() if n != before.get(obj, n)}
        else:
            self.logic_step()
            self.audio_replay(frame)
        self.stats['step_seconds' if present else 'resim_seconds'] += time.perf_counter() - started
        if frame % self.interval == 0:
            self.record_checksum(frame)
        if self.finished_frame is None and frame not in self.events_end and not self.playing():
            self.events_end[frame] = self.base_hp()          # 战斗停止的帧：双方据点生命（回放记录胜负）
        if self.journal is not None:
            record = self.timed('commit_seconds', self.journal.commit, frame, self.host.capture())
            if self.on_commit is not None:
                self.on_commit(frame, record)
        self.frame = frame
        self.stats['frames'] += 1

    def restore(self, frame):
        """恢复到第 frame 帧末（镜头位置保留为当前值）。"""
        p = self.p
        camera = p.read(self.screen + 8, 4) if self.screen else None
        started = time.perf_counter()
        host = self.journal.restore(frame)
        self.host.apply(host)
        if self.ledger is not None:
            self.ledger.rollback(frame)
        if camera is not None:
            p.write(self.screen + 8, camera)       # 本地视图不随回滚改变；写入计入下一帧的改动页
        for f in [f for f in self.events_end if f > frame]:
            del self.events_end[f]
        self.stats['restore_seconds'] += time.perf_counter() - started
        self.frame = frame

    def camera(self):
        """镜头位置（BattleScreen +8）属于本地视图：只渲染帧与跳转恢复状态时保留当前位置。"""
        return self.p.read(self.screen + 8, 4) if self.screen else None

    def set_camera(self, value):
        if value is not None and self.screen:
            self.p.write(self.screen + 8, value)

    def render_paused(self):
        """只渲染（N5.5）：置原生暂停标记渲染当前状态一帧，再撤销本帧的全部改动（客体内存、宿主状态与 GL 对象），画面保持而状态不变。
        回放暂停与慢速、本地对战的暂停菜单使用；需要回滚记录（journal）。"""
        p = self.p
        if self.journal is None:
            return False
        master = p.call('_ZN16BattleGameMaster11getInstanceEv')
        if self.ledger is not None:
            self.ledger.frame = self.frame + 1
        if master:
            p.write(master + 0x1c, b'\x01')
        self.presenting = False
        p.step_frame()
        camera = self.camera()
        host = self.journal.restore(self.frame)
        self.host.apply(host)
        self.set_camera(camera)
        if self.ledger is not None:
            self.ledger.rollback(self.frame)
            self.ledger.frame = self.frame
        return True

    def audio_callbacks(self):
        bridge = getattr(self.p, 'audio_bridge', None)
        return {obj: stream.callbacks for obj, stream in bridge.streams.items()} if bridge is not None else {}

    def audio_replay(self, frame):
        """重模拟第 frame 帧之后：该帧实际显示时原生混音回调运行了 n 次（音频块已送出），这里以相同次数运行回调并丢弃输出。
        回滚恢复了客体混音状态（各声道播放位置）与宿主音频流状态；逐帧重放使播放位置与原时间线同步推进，
        输入未变时混音状态与原时间线逐字节相同，已听到的声音不重复；输入改变时新时间线的声音按实际经过时间前进。静音模式下 n 为 0。"""
        counts = self.audio_frames.get(frame)
        bridge = getattr(self.p, 'audio_bridge', None)
        if not counts or bridge is None:
            return
        for obj, count in counts.items():
            stream = bridge.streams.get(obj)
            for _ in range(count if stream is not None else 0):
                if not stream.queue or not stream.callback:
                    break
                block = stream.queue.popleft()
                stream.generated_bytes += len(block)
                stream.index = (stream.index + 1) & 0xFFFFFFFF
                stream.callbacks += 1
                address, context = stream.callback
                self.p.call(address, stream.interfaces['queue'], context, count=2_000_000, timeout=0)
                self.stats['audio_replay_blocks'] += 1

    def rollback(self, first):
        """自第 first 帧起以当前已知输入重新模拟到原当前帧（不显示；混音进度逐帧重放，见 audio_replay）。"""
        target = self.frame
        if first > target:
            return
        depth = target - first + 1
        started = time.perf_counter()
        self.restore(first - 1)
        for frame in range(first, target + 1):
            self.simulate(frame, present=False)
        elapsed = time.perf_counter() - started
        s = self.stats
        s['rollbacks'] += 1
        s['rollback_frames'] += depth
        s['max_rollback'] = max(s['max_rollback'], depth)
        s['max_rollback_seconds'] = max(s['max_rollback_seconds'], elapsed)

    # ---------- 网络 ----------
    def schedule_rollback(self, first):
        """下一次 tick 在显示新帧之前自第 first 帧起重算（测试用；网络输入到达时由 receive_input 设定）。"""
        if self.journal is None:
            return
        first = max(first, self.journal.base_frame + 1)
        if first <= self.frame:
            self.rollback_from = first if self.rollback_from is None else min(self.rollback_from, first)

    def receive_input(self, frame, value):
        if frame in self.remote_inputs or frame <= self.confirmed:
            return
        self.remote_inputs[frame] = value
        if frame <= self.frame and self.used_remote.get(frame) != value:
            self.rollback_from = frame if self.rollback_from is None else min(self.rollback_from, frame)
        while self.remote_contiguous + 1 in self.remote_inputs:
            self.remote_contiguous += 1

    def receive_checksum(self, frame, value):
        """对方的周期校验值：N5 为与对方一侧绑定的 tag（整数），N3 传输为 (h, d)。冗余携带的重复帧忽略。"""
        if frame in self.compared or frame < 0:
            return
        self.remote_checksums[frame] = value if isinstance(value, int) else tuple(value)
        self.remote_latest = max(self.remote_latest, frame)

    def round_number(self):
        return getattr(self.transport, 'round', 0) or 0

    def compare_checksums(self):
        for frame in sorted(f for f in self.remote_checksums if f <= self.confirmed and f not in self.compared):
            local = self.checksums.get(frame)
            if local is None:
                continue
            remote = self.remote_checksums[frame]
            if isinstance(remote, int):
                same = netplay_desync.tag(self.round_number(), frame, 1 - self.local_side, *local) == remote
            else:
                same = tuple(local) == remote
            self.compared[frame] = same
            if same:
                self.last_match = max(self.last_match, frame)
                self.matched.append(frame)           # 最近几个一致帧的快照保留（对方只在本方一致的帧报告分歧时用于比较）
                while len(self.matched) > KEEP_MATCHED:
                    self.snapshots.pop(self.matched.pop(0), None)
            elif self.desync is None:
                self.desync = {'kind': 'checksum', 'frame': frame, 'local': list(local),
                               'remote': remote if isinstance(remote, int) else list(remote)}
        if (self.desync is None and self.transport is not None and self.finished_frame is None
                and self.confirmed - self.remote_latest > MISSING_LIMIT):
            self.desync = {'kind': 'missing', 'frame': self.remote_latest + self.interval, 'confirmed': self.confirmed,
                           'remote_latest': self.remote_latest}

    def send_checksums(self):
        """把新确认的校验帧发给对方。N5 传输：每包携带最近 TAG_REDUNDANCY 个已确认帧的 tag（丢包由后续包补齐）。"""
        t = self.transport
        new = sorted(f for f in self.checksums if f <= self.confirmed and f not in self.sent_checksums)
        if not new:
            return
        for frame in new:
            self.sent_checksums.add(frame)
            self.sent_order.append(frame)
        if hasattr(t, 'send_checksum_tags'):
            recent = [f for f in self.sent_order[-TAG_REDUNDANCY:] if f in self.checksums]
            t.send_checksum_tags([(f, netplay_desync.tag(self.round_number(), f, self.local_side, *self.checksums[f]))
                                  for f in recent])
        else:
            for frame in new:
                t.send_checksum(frame, self.checksums[frame])
        del self.sent_order[:-TAG_REDUNDANCY]

    # ---------- 分歧（N5） ----------
    def desync_notice(self, peer=None):
        """结束对战时发给对方的分歧通知：本方检测结果，或（只由对方检测到时）对方通知的帧。"""
        if self.desync is not None:
            return {'kind': self.desync['kind'], 'frame': self.desync['frame'], 'by': 'local'}
        peer = peer or {}
        return {'kind': peer.get('kind', 'checksum'), 'frame': peer.get('frame'), 'by': 'peer'}

    def desync_payload(self, notice, peer=None):
        """desync_data 消息的内容：最近一致帧之后、至分歧帧为止本方保留的快照（最多 MAX_REPORT_SNAPSHOTS 个）、
        这些帧前后的已确认双方输入、当前单位数据表逐行 CRC32。"""
        frames = [notice.get('frame')] + [(peer or {}).get('frame')]
        upto = max([f for f in frames if isinstance(f, int)] or [self.confirmed])
        chosen = sorted(f for f in self.snapshots if self.last_match < f <= upto)[:MAX_REPORT_SNAPSHOTS]
        if upto in self.snapshots and upto not in chosen:
            chosen.append(upto)
        first = (min(chosen) if chosen else upto) - self.interval
        inputs = [[f, *self.input_log[f - 1]] for f in range(max(1, first + 1), min(upto, len(self.input_log)) + 1)]
        rows = netplay_desync.row_digests(self.p.read(*self.table)) if self.table else None
        detected = self.desync['frame'] if self.desync else (notice.get('frame') if notice.get('by') == 'local' else None)
        return {'kind': notice.get('kind'), 'detected': detected,
                'side': self.local_side, 'last_match': self.last_match, 'confirmed': self.confirmed,
                'snapshots': [netplay_desync.encode_snapshot(self.snapshots[f]) for f in chosen],
                'inputs': inputs, 'rows': rows}

    def update_confirmed(self):
        if self.transport is None:
            confirmed = max(0, self.frame - self.confirm_lag)
        else:
            confirmed = min(self.frame, self.remote_contiguous)
        if confirmed > self.confirmed:
            for frame in range(self.confirmed + 1, confirmed + 1):
                values = self.frame_inputs.pop(frame, (0, 0))
                self.input_log.append(values)
                if self.surrender is None and (values[0] | values[1]) & SURRENDER:
                    self.surrender = (frame, (bool(values[0] & SURRENDER), bool(values[1] & SURRENDER)))
                if frame in self.checksums:
                    self.checksum_log[frame] = tuple(self.checksums[frame])
            self.confirmed = confirmed
            if self.journal is not None:
                self.journal.confirm(confirmed)
            if self.ledger is not None and self.ledger_confirm:
                self.ledger.confirm(confirmed)
            for frame in [f for f in self.used_remote if f <= confirmed]:
                del self.used_remote[frame]
            if self.finished_frame is None:
                ended = [f for f in self.events_end if f <= confirmed]
                if ended:
                    self.finished_frame = min(ended)

    def tick(self):
        """外层每显示帧调用一次：收发、必要时回滚、推进一帧并显示。返回是否推进。"""
        started = time.perf_counter()
        t = self.transport
        if t is not None:
            for kind, payload in t.poll():
                if kind == 'input':
                    first, values = payload
                    for i, value in enumerate(values):
                        self.receive_input(first + i, value)
                elif kind in ('checksum', 'checksum_tag'):
                    self.receive_checksum(*payload)
        schedule = self.frame + 1 + self.delay
        if schedule not in self.local_inputs:
            self.local_inputs[schedule] = self.local_input(schedule, self.local_side) & INPUT_MASK
        if t is not None:
            first = max(t.peer_ack + 1, 1)
            last = min(schedule, first + 63)
            advantage = self.frame - t.peer_frame
            t.send_inputs(first, [self.local_inputs.get(f, 0) for f in range(first, last + 1)], ack=self.remote_contiguous,
                          frame=self.frame, advantage=advantage)
        if self.rollback_from is not None:
            first, self.rollback_from = self.rollback_from, None
            self.rollback(first)
        advanced = False
        self.ticks += 1
        # 时间同步（GGPO 做法）：双方各报告“本方帧 − 对方最近报告的帧”，差值的一半约为真实领先帧数（单向延迟相抵）；
        # 领先超过 1 帧的一方每 3 个显示帧让出 1 帧。
        sync = ((self.frame - t.peer_frame) - t.peer_advantage) / 2 if t is not None and t.peer_frame else 0
        if t is not None and self.frame + 1 - self.remote_contiguous > self.max_rollback:
            self.stats['stalls'] += 1
        elif sync > 1 and self.ticks % 3 == 0:
            self.stats['sync_waits'] += 1
        else:
            self.simulate(self.frame + 1, present=True)
            advanced = True
        self.update_confirmed()
        if t is not None:
            self.send_checksums()
            t.flush()
            self.compare_checksums()
        keep = min(self.confirmed, t.peer_ack if t is not None else self.confirmed) - 64
        for frame in [f for f in self.local_inputs if f < keep]:
            del self.local_inputs[frame]
        if self.confirmed >= getattr(self, 'next_cleanup', 300):   # 已确认且已比较（或超出保留期）的校验值不再需要
            self.next_cleanup = self.confirmed + 300
            old = self.confirmed - self.HISTORY
            for table in (self.checksums, self.remote_checksums, self.compared, self.remote_inputs, self.events_end,
                          self.audio_frames, self.snapshots):
                for frame in [f for f in table if f < old]:
                    del table[frame]
            self.sent_checksums = {f for f in self.sent_checksums if f >= old}
        self.stats['max_tick_seconds'] = max(self.stats['max_tick_seconds'], time.perf_counter() - started)
        return advanced

    def status(self):
        s = dict(self.stats)
        s.update(frame=self.frame, confirmed=self.confirmed, remote_contiguous=self.remote_contiguous,
                 finished_frame=self.finished_frame, surrender=self.surrender, desync=self.desync, last_match=self.last_match,
                 remote_latest=self.remote_latest, snapshots=len(self.snapshots), input_log=len(self.input_log),
                 compared=len(self.compared), mismatched=sum(1 for v in self.compared.values() if not v),
                 journal=dict(self.journal.stats) if self.journal else None,
                 journal_bytes=self.journal.memory_bytes() if self.journal else 0,
                 ledger=dict(self.ledger.stats) if self.ledger else None)
        return s

