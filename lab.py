"""LAB 战斗入口原型：绕过 Wi-Fi 菜单直接建立 1v1（GameMode 1）战斗，敌方由玩家手动控制。

原型范围（2026-10-06）：
- F7：在非战斗界面启动 LAB 战斗（NPC 对手信息由原生 MakeNPCInfo 生成，可用 lab_config.json 覆盖敌方牌组；
  敌方单位经 BattleController::entryUnit 以完整 UnitID 写入，原版 0–399 与社区单位均可用）。
- Q–P：敌方 1–10 号槽位出兵；[ 敌方 AP 升级；] 敌方弹头车；\\ 敌方全体绝招。
- F8：完全控制模式开/关（宿主层方案 B：据点满级、AP 每帧补满、出兵冷却每帧清零）。
- F5：退出 LAB 战斗并返回菜单（联机模式下原生暂停/脱离不可用，正式版并入 LAB 战斗菜单）。
- F4：敌方 AI 自动出兵 开/关；F3：我方 AI 自动出兵 开/关。自动绝招为独立开关（战斗中菜单，钩子版本 ≥ 4）。
- Esc：战斗中菜单（lab_menu.py，打开期间暂停战斗）：完全控制、四个 AI 开关、重新开始、退出、继续。
- 存档隔离（T9）：LAB 期间原生存档写入改写到内存，离开时还原内存中的主存档映像。
- 战斗结束或进入结算场景时直接返回主菜单，不进入 Wi-Fi 结算。

所有原生调用均为已核实的导出符号；运行记录写入 lab_probe.jsonl 与 lab_player.log。
"""
from pathlib import Path
import collections
import os
import struct
import json
import time

CONFIG_NAME = 'lab_config.json'
DEFAULT_CONFIG = {
    'schema': 1,
    'stage_id': 1011,          # 原生联机地图表首项（0x8fd730+48 起：1011,1021,1022,...）
    'enemy_deck': None,        # None=原生 NPC 牌组；或至多 10 项 [单位, 等级(1-40)]，单位为 UnitID 或社区单位 key，null=空槽
    'player_deck': None,       # None=存档牌组与存档等级（BattleStartSetUnit）；格式同 enemy_deck
    'player_base_level': 0,    # 开战时的据点等级 0–10（10=MAX）；完全控制开启时为 MAX
    'enemy_base_level': 0,
    'player_hp_boost': 0,      # 优势设定：原生关卡强化级数（生命/攻击各 ×(1+0.2×级数)），0–10
    'player_atk_boost': 0,
    'enemy_hp_boost': 0,
    'enemy_atk_boost': 0,
    'full_control': True,
    'enemy_ai': False,             # 敌方 AI 自动出兵（含弹头车）
    'player_ai': False,            # 我方 AI 自动出兵（含弹头车）
    'enemy_auto_special': False,   # 敌方自动释放绝招
    'player_auto_special': False,  # 我方自动释放绝招
    'player_support': 0,           # 支援（弹头车按钮效果）：见 SUPPORT_OPTIONS
    'enemy_support': 0,
    'player_ai_tier': 'SILVER',    # AI 段位（AI_TIERS 名称），我方与敌方各自独立
    'enemy_ai_tier': 'SILVER',
    'versus': False,               # 本地双人对战（docs/lab/local_versus_design_2026-10-06.md 第 5 节）
    'versus_keys': None,           # 双人键位（None 为 VERSUS_KEYS 默认）；值为 GLFW 键名（KEY_ 之后部分）
    'versus_pad': None,            # 双人手柄功能键（None 为 lab_versus_input.PAD_DEFAULTS）；值为 PAD_BINDABLE 名称
    'versus_pad_single': 'p2',     # 只连接一只手柄时分配给的玩家
}
# 双人对战默认键位（用户 2026-10-08 修订）：玩家1（P1）为左半区，玩家2（P2）为右半区。
# 出兵、绝招、AP、弹头车依次为 R T Y U 与 M , . /（同一行相邻四键）。
VERSUS_ACTIONS = ('left', 'right', 'ap', 'deploy', 'special', 'slug')
VERSUS_KEYS = {'p1': {'left': 'A', 'right': 'D', 'ap': 'Y', 'deploy': 'R', 'special': 'T', 'slug': 'U'},
               'p2': {'left': 'LEFT', 'right': 'RIGHT', 'ap': 'PERIOD', 'deploy': 'M', 'special': 'COMMA', 'slug': 'SLASH'}}
# 双人对战期间暂时关闭的 LAB 开关（开战时保存、离开战斗时还原，不写入设定文件）。
VERSUS_OVERRIDES = ('full_control', 'player_ai', 'enemy_ai', 'player_auto_special', 'enemy_auto_special')
# 支援选项（与 src/lab_hooks.cpp apply_support 编号一致；新增选项在两处同时扩展）。
SUPPORT_OPTIONS = ('弹头车出击', '除据点外全员 HP 回满', '全员绝招立即可用')
PLAYER_FAMILY = ('BattleControllerPlayerBase', 'BattleControllerPlayer', 'BattleControllerNetPlayer',
                 'BattleControllerNetMultiPlayer', 'BattleControllerNetRaidPlayer')
ENEMY_DECK = 0xC081           # app 偏移：10×2 字节（UID 低 8 位 | UID 高 2 位 + 等级<<2）
APP_ONLINE = 0xC030           # 1=联机分支
APP_ONLINE_KIND = 0xC034      # 0=1v1
APP_NPC = 0xC061              # 字节，1=NPC 对手（GetPlayerInfo 调 MakeNPCInfo）
APP_MENU_MODE = 0xC63C
SCENE_BATTLE = 100
LAB_HEADER = 0x1ffeb000        # 与 src/lab_hooks.cpp 共用；0x1ffea000/0x1ffec000/0x1ffed000/0x1ffee000 已被占用
LAB_MAGIC = 0x4c414231         # "LAB1"
LAB_FLAG_ENEMY_GAUGE = 1
LAB_FLAG_ENEMY_TOUCH = 2         # 点击敌方单位释放绝招（lab_hooks 版本 ≥ 2）
LAB_FLAG_SPLIT_BAR = 4           # 底栏左右分栏：我方 AP/弹头车/3 格 | 敌方 3 格/弹头车/AP（版本 ≥ 3）
LAB_FLAG_AUTO_SPLIT = 16         # AI 自动出兵与自动绝招分开控制（版本 ≥ 4）
LAB_AUTO_DISABLE = 0x30          # 头部偏移：位 0/1 我方 出兵/绝招 关闭，位 2/3 敌方 出兵/绝招 关闭
LAB_FLAG_SUPPORT = 32            # 支援：弹头车按钮可换为其他效果（版本 ≥ 5）
LAB_SUPPORT = 0x34               # 头部偏移：低字节我方、次字节敌方的支援选项
LAB_SUPPORT_COUNT = 0x38         # 头部偏移：非弹头车支援的发动计数（原生累加）
LAB_ENEMY_GFX_READY = 0x3c       # 头部偏移：敌方出兵格图集已就绪
LAB_ENEMY_GFX = 0x40             # 头部偏移：敌方 operator+188…+220（9 字）
LAB_ENEMY_PANEL_READY = 0x6c     # 头部偏移：敌方出兵栏状态已初始化
LAB_ENEMY_PANEL = 0x70           # 头部偏移：敌方 operator+24/32/96/100/104/112/116（7 字，+12 为滚动值）
LAB_ENEMY_BANNER = 0x100         # 钩子版本 9：敌方横幅队列与播放状态（10 字）
LAB_ENEMY_BANNER_READY = 0x128
LAB_ENEMY_BANNER_SLOTS = 0x140   # 六个原生横幅槽，每槽 28 字节，+4 为 BattleSprite
LAB_FLAG_SE_EXTEND = 64          # 钩子版本 10：LAB 战斗中双方音效通道扩展
LAB_SE_MAGIC = 0x300             # 头部偏移：'LSE1' 表示扩展通道已建立（LAB 结束时保留）
LAB_SE_COUNT = 0x304             # 每端口扩展通道数
LAB_SE_EXTRA = 0x310             # 端口 0（1P）与端口 1（2P）各 8 字的 CAudioPresenter 指针
LAB_SE_STATS = 0x380             # 每端口 8 字统计：请求、同帧合并、满队、播放、抢占、最大并发、当前并发、播放后未登记；+0x40 起每端口 6 字诊断
LAB_FLAG_AI_TIER = 128           # 钩子版本 11：AI 段位（反应间隔、开局据点目标）
LAB_FLAG_VERSUS = 256            # 钩子版本 14：双人对战中双方胜利均播放 MISSION COMPLETE（changeScene 4→3，计数 +0x780）
LAB_FLAG_VS_CURSOR = 512         # 钩子版本 15：双人对战选中格光标插入原生出兵格绘制（头部 +0xa00，lab_versus.py）
LAB_FLAG_NET_CAPTURE = 1024      # 钩子版本 22：常规联机——原生底栏与点击单位的操作记入核心缓冲区（netplay_regular），不立即执行
LAB_AI_TIER = 0x500              # 头部偏移：我方 +0x500、敌方 +0x520（+0x380..0x3f7 为音效统计），各 [启用, 等待下限, 等待上限, 据点目标]
AI_ALWAYS_URGENT = 0x3fffffff
# AI 段位：(名称, 等级, 反应间隔下限/上限（帧，30 帧/秒，均匀随机）, 紧急阈值, 开局据点目标（-1 为原生逻辑）,
# 出兵理解度 0–100（0 为原生选择；越高越重视单位价值、越愿意积累 AP、误判越少，见 src/lab_hooks.cpp ai_choose）)。
# 紧急阈值写入 controller+0x424：己方场上单位 AI 战力（数据行 +0x354）合计低于阈值 −30（据点等级 1 时为阈值/2 −30）
# 时，原生 AI 不再保留 AP 而直接出兵；原生每场以 rand()%220 抽取。据点目标与准备界面据点等级同一编号（0–10）。
AI_TIERS = (('ROOKIE', -2, 160, 320, 50, 1, 0), ('BRONZE', -1, 80, 160, 80, 2, 0), ('SILVER', 0, 30, 90, 110, -1, 0),
            ('GOLD', 1, 18, 54, 300, 3, 35), ('PLATINUM', 2, 10, 32, 800, 4, 55), ('DIAMOND', 3, 6, 18, 1500, 4, 70),
            ('MASTER', 4, 3, 10, AI_ALWAYS_URGENT, 5, 85), ('PREDATOR', 5, 1, 6, AI_ALWAYS_URGENT, 5, 100))
# 场上投资升级据点（钩子版本 13，见 src/lab_hooks.cpp ai_invest）：达到开局据点目标后，己方场上出兵单位（不含召唤单位）
# 的 AP 合计 ≥ k × 本级升级费用并持续 D 帧时，AP 足够即升级据点，不足时暂停出兵最长 L 帧。
# 停滞兜底：据点等级 S 帧未变化时不论 F 均保留 AP 直至升级（压力下照常出兵），保证逐级升至满级。
# 每段 (k×100, L 帧, D 帧, S 帧)；k 为 0 时不启用（SILVER 保持原生逻辑）。低段位系数高、延迟长、兜底晚，升级“慢半拍”。
AI_INVEST = {'ROOKIE': (300, 90, 90, 1200), 'BRONZE': (250, 120, 60, 900), 'SILVER': (0, 0, 0, 0),
             'GOLD': (200, 150, 20, 600), 'PLATINUM': (170, 180, 10, 450), 'DIAMOND': (140, 210, 6, 360),
             'MASTER': (120, 240, 3, 300), 'PREDATOR': (100, 300, 1, 240)}
LAB_INVEST_SERIAL = 0x700        # 每场开战递增，钩子据此清空单位来源记录；+0x710 投资统计、+0x750 单位来源统计
LAB_AI_STATS = 0x540             # 头部偏移：每方 8 字统计（出兵、积累帧、建筑类暂缓、改选、压力出兵、最近 UnitID、AP 合计、建筑类出兵），+0x580 起建筑类出兵位置
AI_TIER_NAMES = tuple(t[0] for t in AI_TIERS)
SE_EXTRA_PER_PORT = 8            # 原生 3 + 扩展 8 = 每方 11 个通道；CMediaManager 32 个播放槽，原生通道只在播放时占用
AURA_STRING = 0x103011c3       # BattleEffectRenderer 构造函数引用的 "aura.obm"（.rodata 0x3011c3）
RESULT_SCENES = (110, 120)
RESULT_FALLBACK_FRAMES = 450     # 战斗停止后原生仍未离开场景 100 时的兜底（15 秒）；实测 FAILED 演出约 140 帧后离开
SAVE_RAM = 0x3d08              # app 偏移：主存档映像（与 event_trial.EventTrial.transaction 相同）
SAVE_RAM_SIZE = 0x5ab0
AUDIO_WORDS = (0x3d5c, 0x3d60)   # 音乐、音效开关（audio_options.MUSIC / EFFECTS，位于 SAVE_RAM 内）
AUDIO_HEADER, AUDIO_MAGIC = 0x1ffea000, 0x41554431   # audio_options 共享头：+4 为修订计数
PRESET_DIR = 'lab_presets'
SWITCHES = ('full_control', 'enemy_ai', 'player_ai', 'enemy_auto_special', 'player_auto_special',
            'player_support', 'enemy_support')
# 双人对战与 LAB 互不切换（用户 2026-10-08 要求）：模式只由入口决定（VERSUS 页本地对战为双人对战，LAB 图标与 F7 为 LAB），
# 不作为开关保存，预设与设定文件不改变模式。
PB = '_ZN26BattleControllerPlayerBase'
# BattleObjectManager::createUnit（0x1df344）以 manager+72+(队伍×2+成员)×8 的两个浮点数调用
# BattleObjectFactory::createUnitObject → createUnitStatus（0.2 常量所在函数）；里世界关卡把关卡强化级数写入敌方的这一对值。
ADVANTAGE_BASE = 72


def T(p, key, *args):
    from lab_ui import T as text
    return text(p, key, *args)



class Lab:
    def __init__(self, p, root):
        self.p = p
        self.root = Path(root)
        # 设定与预设目录：默认仓库根目录；验证脚本以 MSD_LAB_CONFIG_DIR 指向独立目录，不改动玩家的 lab_config.json。
        self.config_dir = Path(os.environ.get('MSD_LAB_CONFIG_DIR', root))
        self.commands = collections.deque()
        self.config = self.load_config()
        self.active = False
        self.saved_flags = None
        self.versus = False           # 当前模式（双人对战 / LAB），由打开准备界面的入口决定
        self.vs_saved = None          # 双人对战：开战时保存的 LAB 开关（VERSUS_OVERRIDES）；None 表示非双人对战
        self.vs_cursor = [0, 0]       # 双人对战：P1、P2 的选中格
        from lab_versus import VersusCursor
        self.vs_view = VersusCursor(self)
        from lab_versus_input import VersusCamera
        self.vs_camera = VersusCamera(self)   # 右摇杆与鼠标拖动的镜头仲裁
        self.pad_status = ()                  # 窗口线程写入：((jid, 玩家, 名称), …)
        self.started_frame = 0
        self.applied = False
        self.apply_switches()
        self.support_count = 0
        self.player_units = self.enemy_units = []
        self.cooldown_seen = {}
        from lab_menu import LabMenu
        from lab_prep import LabPrep
        self.menu = LabMenu(self)
        self.prep = LabPrep(self)
        self.restart_at = None
        self.finishing = None             # 战斗结束：原生闸门合拢后离开（原因, 是否回到准备界面, 是否重新开始）
        self.release_shutter_on_battle = False
        self.classes = {}
        for name, address in p.symbols.items():
            if name.startswith('_ZTV') and 'BattleController' in name:
                body = name[4:]
                digits = ''
                while body and body[0].isdigit():
                    digits += body[0]
                    body = body[1:]
                self.classes[address + 8] = body[:int(digits)] if digits else body
        self.last_sample = 0.0
        self.native_hooks = 0
        self.red_renderer = None
        self.red_aura = None
        self.sandbox = False
        self.save_snapshot = None
        self.virtual_files = {}
        self.virtual_write_count = 0
        # 联机对战（netplay_session.NetplayBattle）：config_override 为本场设定（不读写玩家的 lab_config.json）；
        # netplay 非 None 时，战斗中每帧的处理交给联机会话（输入、逻辑与表现分离），见 update。
        self.config_override = None
        self.netplay = None
        self.netplay_mode = None      # 'regular'：常规联机（原生底栏、操作捕获，见 header_flags 与 netplay_regular）
        self.start_hook = None        # 开战时（原生战斗初始化之前）调用一次：联机会话在此以比赛种子设定各随机源
        p.log('LAB_READY', json.dumps(self.config, ensure_ascii=False))

    # ---------- 配置与记录 ----------
    def load_config(self):
        path = self.config_dir / CONFIG_NAME
        if not path.is_file():
            path.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding='utf-8')
            return dict(DEFAULT_CONFIG)
        data = json.loads(path.read_text(encoding='utf-8'))
        config = dict(DEFAULT_CONFIG)
        config.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
        for key in ('enemy_deck', 'player_deck'):
            deck = config[key]
            if deck is not None and (not isinstance(deck, list) or len(deck) > 10):
                raise ValueError(f'lab_config.json: {key} 须为至多 10 项的列表')
        return config

    def save_config(self):
        for name in SWITCHES:
            self.config[name] = getattr(self, name)
        if getattr(self, 'vs_saved', None):
            self.config.update(self.vs_saved)        # 双人对战期间的临时关闭不写入设定
        (self.config_dir / CONFIG_NAME).write_text(json.dumps(self.portable_config(), ensure_ascii=False, indent=2), encoding='utf-8')

    def portable_config(self):
        """写入文件的设定：牌组中的模组单位以稳定键保存（模组 UnitID 随启用情况分配，停用后再启用时按键找回）。"""
        community = getattr(self.p, 'community', None)
        sources = getattr(community, 'unit_source', {})
        keys = {u['id']: u['key'] for u in (community.units if community is not None else []) if sources.get(u['key'], 'body') != 'body'}
        config = dict(self.config)
        for name in ('enemy_deck', 'player_deck'):
            if isinstance(config.get(name), list):
                config[name] = [[keys.get(e[0], e[0]), e[1]] if isinstance(e, list) and isinstance(e[0], int) else e
                                for e in config[name]]
        return config

    # ---------- 预设与履历（lab_presets/） ----------
    def preset_path(self, name):
        folder = self.config_dir / PRESET_DIR
        folder.mkdir(exist_ok=True)
        return folder / f'preset_{name}.json'

    def save_preset(self, name):
        self.save_config()
        self.preset_path(name).write_text(json.dumps(self.portable_config(), ensure_ascii=False, indent=2), encoding='utf-8')

    def load_preset(self, name):
        path = self.preset_path(name)
        if not path.is_file():
            return False
        data = json.loads(path.read_text(encoding='utf-8'))
        self.config.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
        self.apply_switches()
        self.save_config()
        return True

    def apply_switches(self):
        for name in SWITCHES:
            value = self.config[name]
            setattr(self, name, int(value) % len(SUPPORT_OPTIONS) if name.endswith('_support') else bool(value))
        # 支援接口（原生钩子与 SUPPORT_OPTIONS）保留；界面暂只开放弹头车出击，其余选项不生效。
        self.player_support = self.enemy_support = 0

    def read_history(self):
        path = self.config_dir / PRESET_DIR / 'history.jsonl'
        if not path.is_file():
            return []
        entries = []
        for line in path.read_text(encoding='utf-8').splitlines()[-200:]:
            try:
                entries.append(json.loads(line))
            except ValueError:
                pass
        return entries

    def write_history(self, reason):
        mine, enemy, _ = self.controllers()
        alive = {}
        for side, controller in (('player', mine), ('enemy', enemy)):
            base = self.p.call('_ZNK16BattleController11getBaseUnitEv', controller) if controller else 0
            alive[side] = bool(self.valid(base) and struct.unpack('<f', self.p.read(base + 776, 4))[0] > 0)
        winner = 'player' if alive['player'] and not alive['enemy'] else (
            'enemy' if alive['enemy'] and not alive['player'] else None)
        entry = {'time': time.strftime('%m-%d %H:%M'), 'reason': reason, 'winner': winner,
                 'seconds': (self.p.frame - self.started_frame) / 30, 'stage_id': self.config['stage_id'],
                 'player_units': [e[0] if e else 0 for e in self.player_units],
                 'enemy_units': [e[0] if e else 0 for e in self.enemy_units], 'versus': bool(self.versus)}
        with self.preset_path('A').parent.joinpath('history.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def community_uid(self, key):
        community = getattr(self.p, 'community', None)
        for unit in (community.units if community is not None else []):
            if unit['key'] == key:
                return unit['id']
        return None

    def stage_catalog(self):
        """原生地图 1–3 与里地图 1–3 的全部小关（lab_stages.StageCatalog，首次使用及游戏语言改变时读取原生表）。"""
        language = self.p.word(self.app() + 0x3d64)
        if getattr(self, 'stages', None) is None or self.stages.language != language:
            from lab_stages import StageCatalog
            self.stages = StageCatalog(self.p)
        return self.stages

    def stage_label(self, sid):
        try:
            self.stage_catalog().load()
            entry = self.stages.by_id.get(int(sid))
        except (TypeError, ValueError):
            entry = None
        if not entry:
            return str(sid)
        return T(self.p, 'stage_no', T(self.p, f"world_{entry['world']}"), entry['area'] + 1, entry['stage'] + 1)

    def resolve_deck(self, deck):
        """把配置项解析为 10 个 (UnitID, 存档等级) 或 None；单位可写 UnitID 或社区单位 key。"""
        community = getattr(self.p, 'community', None)
        units = community.units if community is not None else []
        by_key = {u['key']: u['id'] for u in units}
        # 内部子单位（internal_only，如伞兵/迫击炮子单位、生成器箱体）不可直接编入牌组。
        known = set(range(400)) | {u['id'] for u in units if not u.get('internal_only')}
        result = []
        for index in range(10):
            entry = deck[index] if index < len(deck) else None
            if entry is None:
                result.append(None)
                continue
            unit, level = entry
            uid = by_key.get(unit) if isinstance(unit, str) else int(unit)
            if uid is None or uid not in known:
                # 未载入的单位（模组停用或卸载）按空格处理，设定中的原值保留，重新启用后恢复。
                self.p.log('LAB_DECK_UNIT_UNAVAILABLE', index, unit)
                result.append(None)
                continue
            if not 1 <= int(level) <= 40:
                raise ValueError(f'enemy_deck 第 {index + 1} 项：等级 {level} 超出 1–40')
            result.append((uid, int(level) - 1))
        return result

    def affiliation(self, uid):
        return self.p.call('_ZN7AppMain18GetUnitAffiliationE6UnitID', self.app(), uid)

    def stand_in(self, uid):
        """取与 uid 同阵营、编号 < 400 的原版单位，仅供原生阵营一致性判断使用。"""
        if not hasattr(self, 'stand_ins'):
            self.stand_ins = {}
            for candidate in range(1, 400):
                self.stand_ins.setdefault(self.affiliation(candidate), candidate)
        faction = self.affiliation(uid)
        if faction not in self.stand_ins:
            raise ValueError(f'UnitID {uid} 的阵营 {faction} 无原版对应单位')
        return self.stand_ins[faction]

    def feedback(self, text, success=True):
        self.p.unit_feedback = {'text': 'LAB · ' + text, 'until': time.perf_counter() + 2.5,
                                'success': success, 'visible': True}
        self.p.log('LAB_FEEDBACK', text)

    def record(self, kind, **values):
        values.update(kind=kind, frame=self.p.frame)
        with (self.root / 'lab_probe.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(values, ensure_ascii=False, default=str) + '\n')

    # ---------- 原生对象 ----------
    def app(self):
        return self.p.app_instance()

    def valid(self, address):
        return 0x10000000 <= address < 0x1ffff000

    def battle(self):
        p = self.p
        app = self.app()
        if not app or p.word(app + 0x22bc) != SCENE_BATTLE:
            return None, None
        main = p.word(app + 0xc220)
        if not main or not p.word(main + 8):
            return None, None
        scene = p.call('_ZN10BattleMain12getMainSceneEv', main)
        return main, scene

    def controllers(self):
        """返回 (我方控制器, 敌方控制器, 场景信息)。"""
        p = self.p
        main, scene = self.battle()
        if not scene:
            return None, None, None
        from battle_controls import player_controller
        mine = player_controller(p, main)
        team = p.word(mine + 0x38c) if mine else None
        enemy = None
        found = []
        for index in range(8):
            address = p.word(scene + 0x40 + index * 4)
            if not self.valid(address):
                continue
            cls = self.classes.get(p.word(address))
            if cls is None:
                continue
            found.append((index, cls, hex(address), p.word(address + 0x38c)))
            if cls in PLAYER_FAMILY and address != mine and p.word(address + 0x38c) != team:
                enemy = address
        return mine, enemy, {'game_mode': p.word(scene + 0x24), 'controllers': found}

    # ---------- 启动与离开 ----------
    def start(self):
        p = self.p
        app = self.app()
        scene = p.word(app + 0x22bc)
        if scene in (99, SCENE_BATTLE) or self.active:
            self.feedback(T(self.p, 'fb_busy'), False)
            return
        if self.versus and self.config_override is None and self.netplay is None:
            # 本地双人对战（N5.5c）：经确定性会话运行并录制回放（versus_session；MSD_VERSUS_SESSION=0 时不使用）。
            import versus_session
            if versus_session.enabled():
                self.local_driver = versus_session.LocalVersusDriver(self)
                p.session_driver = self.local_driver
        if self.start_hook is not None:
            hook, self.start_hook = self.start_hook, None
            hook()
        self.config = self.load_config() if self.config_override is None else dict(self.config_override)
        self.config.update({name: getattr(self, name) for name in SWITCHES})
        if self.config_override is not None:
            self.config.update(self.config_override)
        self.vs_restore()
        if self.versus:
            # 双人对战：完全控制、双方 AI 与自动绝招关闭（正常 AP 增长与冷却），离开战斗时还原。
            self.vs_saved = {name: getattr(self, name) for name in VERSUS_OVERRIDES}
            for name in VERSUS_OVERRIDES:
                setattr(self, name, False)
            self.vs_cursor = [0, 0]
            self.vs_camera.reset()
        # 先完成全部校验与查表，确认无误后才改动原生场景状态。
        configured = None
        if self.config['enemy_deck'] is not None:
            configured = self.resolve_deck(self.config['enemy_deck'])
            for entry in configured:
                if entry is not None and entry[0] >= 400:
                    self.stand_in(entry[0])
        player_deck = None
        if self.config['player_deck'] is not None:
            player_deck = self.resolve_deck(self.config['player_deck'])
        self.prep.set_open(False)
        self.saved_flags = {name: p.word(app + offset) for name, offset in
                            (('online', APP_ONLINE), ('kind', APP_ONLINE_KIND), ('menu', APP_MENU_MODE))}
        self.saved_flags['npc'] = p.read(app + APP_NPC, 1)[0]
        self.enter_sandbox()
        p.call('_ZN7AppMain12SceneEndFuncEi', app, scene)
        p.put(app + APP_ONLINE, 1)
        p.put(app + APP_ONLINE_KIND, 0)
        p.write(app + APP_NPC, b'\x01')
        p.put(app + APP_MENU_MODE, 4)
        p.call('_ZN7AppMain13GetPlayerInfoEv', app)
        native_deck = self.read_enemy_deck()
        if configured is not None:
            deck = configured
        else:
            deck = [None if entry is None else (entry[0], entry[1] - 1) for entry in native_deck]
        # 原生对手数据区只容 10 位 UID：UID ≥ 400 的单位以同阵营原版单位代写，
        # 仅用于 BattleStartSetStatusEnemy 的全同阵营判断；实际单位随后以完整 UID 写入。
        self.write_enemy_deck([None if e is None else (e[0] if e[0] < 400 else self.stand_in(e[0]), e[1])
                               for e in deck])
        stage = int(self.config['stage_id'])
        self.stage_catalog().load()
        if self.stages.by_id and stage not in self.stages.by_id:
            stage = DEFAULT_CONFIG['stage_id']
        p.call('_ZN7AppMain22BattleInit_OnlinerModeEi12BattleTeamID', app, stage, 0)
        p.call('_ZN7AppMain20BattleStartSetStatusEiii9WorldType', app, 0, 0, 0, 0)
        main = p.word(app + 0xc220)
        if player_deck is None:
            p.call('_ZN7AppMain18BattleStartSetUnitEv', app)
            player_deck = [None] * 10
            for slot in range(10):
                uid = p.call('_ZN7AppMain19GetDeckUnitSaveDataEii', app, slot, 0xffffffff)
                if uid not in (0, 0xffffffff) and not uid & 0x80000000:
                    player_deck[slot] = (uid, p.call('_ZN7AppMain20GetUnitLevelSaveDataE6UnitID', app, uid))
        else:
            # 取代 BattleStartSetUnit：与原生相同按槽位顺序调用 entryUnit，等级取准备界面设定，不读存档。
            mine = p.call('_ZN10BattleMain19getPlayerControllerEv', main)
            for entry in player_deck:
                uid, level = (0xffffffff, 0) if entry is None else entry
                p.call('_ZN16BattleController9entryUnitE6UnitIDib', mine, uid, level, 0)
        p.call('_ZN7AppMain25BattleStartSetStatusEnemyEv', app)
        # 取代 BattleStartSetUnitEnemy（0x1e8966）：与原生相同按槽位顺序调用 entryUnit，空槽传 -1，
        # 但 UnitID 不经 10 位编码，社区单位可直接写入。
        enemy = p.call('_ZN10BattleMain18getEnemyControllerEv', main)
        for entry in deck:
            uid, level = (0xffffffff, 0) if entry is None else entry
            p.call('_ZN16BattleController9entryUnitE6UnitIDib', enemy, uid, level, 0)
        if self.config.get('player_status') and self.config.get('enemy_status'):
            # 常规联机（N6a）：双方据点基础状态取自本场设定（各自存档的发展进度），不使用本机存档。
            mine = p.call('_ZN10BattleMain19getPlayerControllerEv', main)
            self.apply_base_status(mine, self.config['player_status'], player_deck)
            self.apply_base_status(enemy, self.config['enemy_status'], deck)
        p.call('_ZN7AppMain26SetContinueStageIDSaveDataEi', app, 0)
        # 战斗对象已按联机 1v1（GameMode 1）建立；应用层联机标记随即清除，
        # 使 AppMain::BattleConnectionCheck 与战斗循环不再检查 CGameCenter 连接状态（无对端时会弹出“通讯中断”）。
        p.put(app + APP_ONLINE, 0)
        if self.native_hooks >= 10:
            self.ensure_se_channels()
        self.write_header(True)
        p.call('_ZN7AppMain11ChangeExeSTEi', app, 99)
        self.active = True
        self.applied = False
        self.seen_playing = False
        self.network_wait_done = False
        self.idle_frames = 0
        self.last_scene = None
        self.started_frame = p.frame
        self.player_units, self.enemy_units = list(player_deck), list(deck)
        self.cooldown_seen = {}
        self.record('start', from_scene=scene, stage_id=stage, native_npc_deck=native_deck,
                    enemy_deck=[None if e is None else [e[0], e[1] + 1] for e in deck],
                    player_deck=[None if e is None else [e[0], e[1] + 1] for e in player_deck],
                    saved_flags=self.saved_flags, config=self.config)
        if self.netplay_mode != 'regular':
            self.feedback(T(p, 'fb_start', self.stage_label(stage)))

    # ---------- 存档隔离（T9） ----------
    def enter_sandbox(self):
        """LAB 期间不改动玩家存档：
        1. 快照内存中的主存档映像（app+0x3d08，0x5ab0 字节，与 EventTrial.transaction 相同），离开时还原，
           战斗中原生对体力、续关、奖励等存档字段的改动不会被之后的正常保存带出；
        2. 原生对存档目录的写入改写到内存中的虚拟文件（lab_launcher.LabProbe.filecall），
           同一文件的读回（原生保存后的校验）由虚拟文件提供，磁盘上的存档文件不被打开写入。"""
        p = self.p
        self.save_snapshot = p.read(self.app() + SAVE_RAM, SAVE_RAM_SIZE)
        self.virtual_files = {}
        self.sandbox = True
        self.record('sandbox_enter')

    def leave_sandbox(self):
        p = self.p
        if self.save_snapshot is not None:
            restored = p.read(self.app() + SAVE_RAM, SAVE_RAM_SIZE) != self.save_snapshot
            # 战斗中菜单的音乐 / 音效开关属于玩家设定：还原存档映像后保留当前值，并递增 audio_options 的修订计数，
            # 使其在 LAB 结束后写入实际存档（与原生暂停页一致）。
            audio = [p.word(self.app() + offset) for offset in AUDIO_WORDS]
            p.write(self.app() + SAVE_RAM, self.save_snapshot)
            if [p.word(self.app() + offset) for offset in AUDIO_WORDS] != audio:
                for offset, value in zip(AUDIO_WORDS, audio):
                    p.put(self.app() + offset, value)
                if p.word(AUDIO_HEADER) == AUDIO_MAGIC:
                    p.put(AUDIO_HEADER + 4, p.word(AUDIO_HEADER + 4) + 1)
            self.record('sandbox_leave', ram_restored=restored,
                        virtual_writes=sorted(self.virtual_files), write_count=self.virtual_write_count)
        self.save_snapshot = None
        self.virtual_files = {}
        self.virtual_write_count = 0
        self.sandbox = False

    def abort(self, native=True):
        """宿主异常时的回退：还原存档映像、关闭隔离并清零共享头。
        native=False 用于退出游戏：只做内存还原，原生对象随进程结束释放（退出后原生调用已被取消）。"""
        self.active = False
        self.vs_restore()
        try:
            if self.sandbox:
                self.leave_sandbox()
        finally:
            try:
                self.write_header(False)
            finally:
                if native:
                    self.release_enemy_feedback_resource()
                else:
                    self.enemy_feedback_resource = 0

    def apply_base_status(self, controller, words, deck):
        """以 17 字的据点基础状态（BattleController::BaseStatus）取代原生 BattleStartSetStatus / SetStatusEnemy 的结果：
        阵营一致标记（controller+0x3a0）按本场编队重算（原生我方按存档编队、敌方按对手数据计算：全部非空格单位阵营相同时为 1），
        再以原生 setupBaseStatus（vtable+0xd4）写入状态并重算 AP 上限、回复量、升级成本与单位能力加成。"""
        p = self.p
        factions = [self.affiliation(entry[0]) for entry in deck if entry is not None]
        same = 1 if factions and all(f == factions[0] for f in factions) else 0
        p.write(controller + 0x3a0, bytes((same,)))
        scratch = p.alloc(0x44)
        try:
            p.write(scratch, struct.pack('<17I', *[int(v) & 0xffffffff for v in words]))
            p.call(p.word(p.word(controller) + 0xd4), controller, scratch)
        finally:
            p.free(scratch)

    def read_enemy_deck(self):
        p = self.p
        app = self.app()
        deck = []
        for slot in range(10):
            low, high = p.read(app + ENEMY_DECK + slot * 2, 2)
            uid = low | ((high & 3) << 8)
            deck.append(None if uid & 0x200 else [uid, (high >> 2) + 1])
        return deck

    def write_enemy_deck(self, deck):
        p = self.p
        app = self.app()
        for slot in range(10):
            entry = deck[slot] if slot < len(deck) else None
            if entry is None:
                raw = bytes((0xff, 0x03))   # UID 位 9 置位 → 原生视为空槽
            else:
                uid, level = int(entry[0]), int(entry[1])
                raw = bytes((uid & 0xff, ((uid >> 8) & 3) | ((level & 0x3f) << 2)))
            p.write(app + ENEMY_DECK + slot * 2, raw)

    def leave(self, reason, reopen_prep=True):
        p = self.p
        app = self.app()
        scene = p.word(app + 0x22bc)
        self.record('leave', reason=reason, scene=scene)
        self.menu.set_open(False, animate=False)
        try:
            self.write_history(reason)
        except Exception as error:
            p.log('LAB_HISTORY_ERROR', type(error).__name__, str(error))
        try:
            self.release_enemy_graphics()
            # 原生战斗结束先经 SC_BattleEnd（0x1ea098）再进结算，结算后 SC_BattleEndLoop 才 BattleEnd_ClearBattleMain。
            # LAB 不进结算，SceneEndFunc 也无战斗场景分支，此处按原生顺序补做 SC_BattleEnd 的清理：
            # 菜单任务与 2D 任务（SC_BattleInit 每场新建的菜单图片等）、2D 绘制请求、BGM 与音效请求屏蔽位。
            # 缺少这一步时每场战斗的这些对象不释放，客机内存逐场减少，之后的战斗中音效载入失败。
            p.call('_ZN7AppMain13ClearMenuTaskEv', app)
            p.call('_ZN13CTaskSystem2D9AllDeleteEii', app + 0x3830, 0, 4)
            p.call('_ZN7AppMain14RequestClear2DEv', app)
            p.call('_ZN7AppMain13Sound_StopBGMEv', app)
            p.call('_ZN7AppMain22Sound_InitRequestBlockEv', app)
            p.call('_ZN7AppMain25BattleEnd_ClearBattleMainEv', app)
        except Exception as error:
            p.log('LAB_CLEAR_ERROR', type(error).__name__, str(error))
        if self.saved_flags:
            p.put(app + APP_ONLINE, self.saved_flags['online'])
            p.put(app + APP_ONLINE_KIND, self.saved_flags['kind'])
            p.put(app + APP_MENU_MODE, self.saved_flags['menu'])
            p.write(app + APP_NPC, bytes((self.saved_flags['npc'],)))
        self.leave_sandbox()
        self.write_header(False)
        p.call('_ZN7AppMain12SceneEndFuncEi', app, scene)
        # 27 为原生主菜单初始化，28 为其稳态；31 属于关卡地图初始化。常规联机（N6a）回到 Wi-Fi VERSUS 菜单（66）。
        target, self.return_scene = getattr(self, 'return_scene', None) or 27, None
        p.call('_ZN7AppMain11ChangeExeSTEi', app, target)
        self.active = False
        self.vs_restore()
        self.finishing = None
        if reopen_prep:
            self.prep.show(from_closed=True)   # 原生闸门已合拢：宿主闸门接手并在准备界面上打开（T8）
        if target == 27:
            self.feedback(T(p, 'fb_back') if reopen_prep else T(p, 'fb_back_menu'))

    def finish(self, reason, reopen_prep=True, restart=False):
        """结束 LAB 战斗：先以原生 SetShutterClose 合拢闸门（与原生战斗结束相同的画面），合拢后离开战斗。"""
        if self.finishing is not None:
            return
        self.menu.set_open(False)
        p = self.p
        try:
            p.call('_ZN7AppMain15SetShutterCloseEv', self.app())
            self.finishing = (reason, reopen_prep, restart, p.frame)
        except Exception as error:
            p.log('LAB_SHUTTER_ERROR', type(error).__name__, str(error))
            self.leave(reason, reopen_prep)
            if restart:
                self.restart_at = p.frame + 45

    def poll_finish(self):
        reason, reopen_prep, restart, since = self.finishing
        p = self.p
        closed = p.call('_ZN7AppMain14IsShutterCloseEv', self.app()) if p.frame - since > 2 else 0
        if closed or p.frame - since > 90:
            self.leave(reason, reopen_prep and not restart)
            if restart:
                self.restart_at = p.frame + 10

    def warm_prep(self):
        """主菜单（28/1）稳定 30 帧后，每帧预热一项准备界面缓存（见 LabPrep.warm）。"""
        app = self.app()
        idle = (not self.prep.open and self.prep.warm_steps != []
                and self.p.word(app + 0x22bc) == 28 and self.p.word(app + 0x22dc) == 1)
        self.menu_idle_frames = getattr(self, 'menu_idle_frames', 0) + 1 if idle else 0
        if self.menu_idle_frames > 30:
            self.prep.warm()

    # ---------- 每帧 ----------
    def update(self):
        if self.netplay is not None and self.active:
            self.netplay.lab_update()
            return
        while self.commands:
            command = self.commands.popleft()
            try:
                self.execute(command)
            except Exception as error:
                self.p.log('LAB_COMMAND_ERROR', command, type(error).__name__, str(error))
                if self.sandbox and not self.active:
                    self.leave_sandbox()   # 启动中途失败：还原存档映像并关闭隔离
                self.feedback(T(self.p, 'fb_failed', command, error), False)
        if self.release_shutter_on_battle and self.p.word(self.app() + 0x22bc) in (99, SCENE_BATTLE):
            # 原生闸门在进入战斗场景的下一帧才开始绘制；宿主闸门再保持 2 帧，避免中间一帧露出主菜单。
            since = getattr(self, 'battle_scene_since', None)
            if since is None:
                self.battle_scene_since = since = self.p.frame
            if self.p.frame - since < 2:
                since = None
        else:
            since = None
            self.battle_scene_since = None
        if self.release_shutter_on_battle and since is not None:
            self.release_shutter_on_battle = False
            self.battle_scene_since = None
            self.prep.shutter.release()          # SC_BattleInit 的 SetShutterOpen 接管（原生开闸）
        if not self.active:
            if self.restart_at is not None and self.p.frame >= self.restart_at:
                self.restart_at = None
                self.start()
            self.warm_prep()
            self.prep.draw()
            return
        self.vs_view.prepare()                   # 双人对战选中格光标：写入头部，由原生钩子在出兵格绘制中画出
        if self.vs_battle() and not self.menu.open and self.finishing is None:
            self.vs_camera.update()              # 右摇杆镜头（与 P1 鼠标拖动仲裁）
        self.menu.draw()
        self.prep.draw()
        if self.finishing is not None:
            self.poll_finish()
            return
        p = self.p
        app = self.app()
        scene = p.word(app + 0x22bc)
        if scene != self.last_scene:
            self.record('scene', scene=scene, previous=self.last_scene)
            self.last_scene = scene
        main = p.word(app + 0xc220)
        if not self.network_wait_done and self.valid(main):
            self.finish_network_wait(main)
        playing = bool(self.valid(main) and p.word(main + 8) and
                       p.call('_ZN10BattleMain15isBattlePlayingEv', main))
        if playing and not self.network_wait_done:
            # 联机等待场景已由原生自行结束（常规联机经原生 Wi-Fi 对手画面开战时，N6a）：战斗已开始即视为等待完成。
            self.network_wait_done = True
            self.record('network_wait_absent')
        if playing:
            self.seen_playing = True
            self.idle_frames = 0
        elif self.seen_playing:
            master = p.call('_ZN16BattleGameMaster11getInstanceEv')
            paused = p.read(master + 0x1c, 1)[0] if master else 0
            # 战斗停止且非暂停：离开战斗场景、战斗对象销毁或停止满 2 秒，视为结束并直接返回菜单。
            if not paused:
                self.idle_frames += 1
            if not self.valid(main):
                self.leave(f'battle_finished_scene_{scene}')
                return
            if not paused and (scene != SCENE_BATTLE or self.idle_frames >= RESULT_FALLBACK_FRAMES):
                # 原生 MISSION COMPLETE / FAILED 演出播放完毕后原生离开战斗场景（100→101），此时合拢闸门再回到准备界面；
                # 停止计时仅作原生未离开场景时的兜底（此前 75 帧会在演出中途合拢）。
                self.finish(f'battle_finished_scene_{scene}')
                return
        elif scene in RESULT_SCENES and p.frame - self.started_frame > 5:
            # 尚未开战即出现弹窗（110/120）：记录后退出，避免停在无对端的联机流程中。
            self.leave(f'popup_before_battle_scene_{scene}')
            return
        mine, enemy, info = self.controllers()
        now = time.monotonic()
        if now - self.last_sample > (2 if p.frame - self.started_frame < 900 else 15):
            self.last_sample = now
            self.record('sample', scene=scene, info=info, playing=playing,
                        mine=self.describe(mine), enemy=self.describe(enemy))
        if not (mine and enemy):
            return
        # 原生钩子所需的敌方信息在开场（MISSION START）前即写入，底栏分栏从开场画面起生效。
        self.publish_enemy(enemy)
        self.apply_advantage(mine, enemy)
        if self.native_hooks >= 3 and not p.word(LAB_HEADER + LAB_ENEMY_GFX_READY):
            self.build_enemy_graphics(enemy)
        if not playing:
            return
        self.fix_units(mine, enemy)
        if not self.applied:
            self.applied = True
            if self.native_hooks >= 13:
                p.put(LAB_HEADER + LAB_INVEST_SERIAL, (p.word(LAB_HEADER + LAB_INVEST_SERIAL) + 1) & 0xffffffff)
                for offset in range(0x10, 0x80, 4):
                    p.put(LAB_HEADER + LAB_INVEST_SERIAL + offset, 0)
            self.apply_ai(mine, enemy)
            if self.full_control:
                for controller in (mine, enemy):
                    p.call(PB + '20actionKyotenLevelMaxEv', controller)
            else:
                self.apply_base_levels(mine, enemy)
            self.record('applied', mine=self.describe(mine), enemy=self.describe(enemy))
        if self.full_control:
            for controller in (mine, enemy):
                level = p.call(PB + '14getKyotenLevelEv', controller)
                maximum = p.call(PB + '8getMaxAPEi', controller, level)
                ap = p.call(PB + '5getAPEv', controller)
                if maximum > ap:
                    p.call(PB + '6plusAPEi', controller, maximum - ap)
                if not self.recent_create(controller):
                    p.call(PB + '24clearCreateUnitWaitTimerEv', controller)

    def publish_enemy(self, enemy):
        """头部：+4 功能位，+8 敌方队伍，+16 敌方控制器，+20 敌方成员（controller+924，与 onGameScreenTouchEnded 的 r9 相同）。"""
        p = self.p
        p.put(LAB_HEADER + 4, self.header_flags())
        p.put(LAB_HEADER + 8, p.word(enemy + 0x38c))
        p.put(LAB_HEADER + 16, enemy)
        p.put(LAB_HEADER + 20, p.word(enemy + 924))
        p.put(LAB_HEADER + LAB_SUPPORT, self.player_support | (self.enemy_support << 8))
        count = p.word(LAB_HEADER + LAB_SUPPORT_COUNT)
        if count != self.support_count:
            self.support_count = count
            self.feedback(T(p, 'fb_support'))

    def apply_advantage(self, mine, enemy):
        """优势设定：写入双方的原生强化级数（每帧覆盖，作用于此后生成的单位）。"""
        import struct
        p = self.p
        manager = p.call('_ZN19BattleObjectManager11getInstanceEv')
        if not self.valid(manager):
            return
        for controller, side in ((mine, 'player'), (enemy, 'enemy')):
            index = p.word(controller + 0x38c) * 2 + p.word(controller + 924)
            if not 0 <= index < 8:
                continue
            hp = float(int(self.config.get(side + '_hp_boost', 0)))
            atk = float(int(self.config.get(side + '_atk_boost', 0)))
            p.write(manager + ADVANTAGE_BASE + index * 8, struct.pack('<ff', hp, atk))

    def build_enemy_graphics(self, enemy):
        """底栏分栏的敌方出兵格图集。BattlePlayerOperator::createGrahics 以 operator+24 的控制器生成
        出兵格头像、成本数字等合成图（operator+188…+220，只新建不释放旧对象）；这里临时换入敌方控制器调用一次，
        把结果交给原生钩子（头部 +0x40 起 9 字，+0x3c 置 1），随后还原我方的值。
        createGrahics 保留 +208，敌方金币按原生初始化流程单独构建。"""
        p = self.p
        _, scene = self.battle()
        operator = p.word(scene + 0x3c)
        if not self.valid(operator):
            return
        offsets = [188 + 4 * i for i in range(9)]
        mine = [p.word(operator + o) for o in offsets]
        controller = p.word(operator + 24)
        p.put(operator + 24, enemy)
        try:
            p.call('_ZN20BattlePlayerOperator13createGrahicsEv', operator)
            built = [p.word(operator + o) for o in offsets]
        finally:
            p.put(operator + 24, controller)
            for o, value in zip(offsets, mine):
                p.put(operator + o, value)
        if self.native_hooks >= 9:
            coin = p.call('_Znwj', 3116)
            p.call('_ZN18BattleCoinAnimatorC2Ev', coin)
            p.call('_ZN18BattleCoinAnimator10initializeEv', coin)
            built[5] = coin
            # 提示横幅共用 SpriteID2；顶层加载完整执行分配与文件导入，LAB 期间持有原生资源。
            factory = p.call('_ZN19BattleSpriteFactory11getInstanceEv')
            self.enemy_feedback_resource = p.call('_ZN19BattleSpriteFactory6createE8SpriteID', factory, 2)
        for i, value in enumerate(built):
            p.put(LAB_HEADER + LAB_ENEMY_GFX + 4 * i, value)
        p.put(LAB_HEADER + LAB_ENEMY_GFX_READY, 1)
        # 只记录本次新建的对象（与我方相同的字段是共用对象，由 operator 析构释放），离开战斗时释放。
        self.enemy_gfx_owned = {o: b for o, b, m in zip(offsets, built, mine) if b and b != m}
        self.record('enemy_graphics', operator=hex(operator), fields=[hex(v) for v in built])

    def release_enemy_graphics(self):
        """按 ~BattlePlayerOperator（0x1d6668）对 operator+188…+220 的释放方式释放敌方出兵格对象：
        +188/+192/+196/+216 虚析构（vtable[1]），+200 delete[]，+204/+220 BattleSprite::release，
        +208 BattleCoinAnimator 析构后 delete；+212 原生不释放。须在 BattleEnd_ClearBattleMain 之前调用。"""
        p = self.p
        self.release_enemy_banners()
        self.release_enemy_feedback_resource()
        owned, self.enemy_gfx_owned = getattr(self, 'enemy_gfx_owned', {}), {}
        p.put(LAB_HEADER + LAB_ENEMY_GFX_READY, 0)
        for offset, obj in owned.items():
            if offset in (188, 192, 196, 216):
                p.call(p.word(p.word(obj) + 4), obj)
            elif offset == 200:
                p.call('_ZdaPv', obj)
            elif offset in (204, 220):
                p.call('_ZN12BattleSprite7releaseEv', obj)
            elif offset == 208:
                p.call('_ZN18BattleCoinAnimatorD2Ev', obj)
                p.call('_ZdlPv', obj)
        if owned:
            self.record('enemy_graphics_released', fields={o: hex(v) for o, v in owned.items()})

    def release_enemy_feedback_resource(self):
        """释放 LAB 持有的横幅图像资源，允许原生工厂在后续清理中回收。"""
        sprite = getattr(self, 'enemy_feedback_resource', 0)
        self.enemy_feedback_resource = 0
        if sprite:
            self.p.call('_ZN12BattleSprite7releaseEv', sprite)

    def release_enemy_banners(self):
        """依原生横幅槽清理流程释放敌方 Sprite，清除固定共享区中的队列与播放状态。"""
        if self.native_hooks < 9:
            return
        p = self.p
        released = []
        if p.word(LAB_HEADER + LAB_ENEMY_BANNER_READY) == 1:
            for index in range(6):
                slot = LAB_HEADER + LAB_ENEMY_BANNER_SLOTS + index * 28
                sprite = p.word(slot + 4)
                if sprite:
                    p.call('_ZN12BattleSprite7releaseEv', sprite)
                    p.put(slot + 4, 0)
                    released.append(hex(sprite))
        p.write(LAB_HEADER + LAB_ENEMY_BANNER, bytes(0xe8))
        if released:
            self.record('enemy_banners_released', sprites=released)

    def finish_network_wait(self, main):
        """联机战斗开场的 BattleSceneNetworkWait（场景类型 6）等待对端同步；LAB 无对端，
        找到该场景对象后调用其原生 finish()（与同步完成时相同，置 +21 完成标记）。"""
        p = self.p
        vtable = p.symbols['_ZTV22BattleSceneNetworkWait'] + 8
        candidates = []
        for index in range(25):
            word = p.word(main + index * 4)
            if not self.valid(word):
                continue
            candidates.append(word)
            for inner in range(16):
                deeper = p.word(word + inner * 4)
                if self.valid(deeper):
                    candidates.append(deeper)
        for address in candidates:
            if p.word(address) == vtable:
                if not p.read(address + 21, 1)[0]:
                    p.call('_ZN22BattleSceneNetworkWait6finishEv', address)
                    self.record('network_wait_finished', address=hex(address))
                # 原生各结束分支均在完成前调用 CloseContentsWindow 关闭“同步中”窗口（0x1d6280/0x1d6284）。
                p.call('_ZN7AppMain19CloseContentsWindowEv', self.app())
                self.network_wait_done = True
                return

    def write_header(self, active):
        p = self.p
        self.release_enemy_banners()
        p.put(LAB_HEADER + 0xa00, 0)            # 双人对战光标（lab_versus.VS_CUR）
        p.put(LAB_HEADER + LAB_ENEMY_GFX_READY, 0)
        p.put(LAB_HEADER + LAB_ENEMY_PANEL_READY, 0)
        p.put(LAB_HEADER + LAB_SUPPORT_COUNT, 0)
        self.support_count = 0
        if not active:
            for offset in range(0, 32, 4):
                p.put(LAB_HEADER + offset, 0)
            return
        p.put(LAB_HEADER + 4, self.header_flags())
        p.put(LAB_HEADER + 12, 0)
        p.put(LAB_HEADER, LAB_MAGIC)

    def header_flags(self):
        if self.netplay_mode == 'regular':
            # 常规联机：原生单方底栏（不分栏、不显示与点击对方单位），本方操作经捕获钩子转为联机输入。
            flags = LAB_FLAG_AUTO_SPLIT | LAB_FLAG_SUPPORT | LAB_FLAG_AI_TIER
            if self.p.word(LAB_HEADER + LAB_SE_MAGIC) == 0x4c534531:
                flags |= LAB_FLAG_SE_EXTEND
            return flags | (LAB_FLAG_NET_CAPTURE if self.native_hooks >= 22 else 0)
        flags = LAB_FLAG_ENEMY_GAUGE if self.native_hooks >= 1 else 0
        if self.native_hooks >= 2:
            flags |= LAB_FLAG_ENEMY_TOUCH
        if self.native_hooks >= 3:
            flags |= LAB_FLAG_SPLIT_BAR
        if self.native_hooks >= 4:
            flags |= LAB_FLAG_AUTO_SPLIT
        if self.native_hooks >= 5:
            flags |= LAB_FLAG_SUPPORT
        if self.native_hooks >= 10 and self.p.word(LAB_HEADER + LAB_SE_MAGIC) == 0x4c534531:
            flags |= LAB_FLAG_SE_EXTEND
        if self.native_hooks >= 11:
            flags |= LAB_FLAG_AI_TIER
        if self.native_hooks >= 14 and self.vs_battle():
            flags |= LAB_FLAG_VERSUS
        if self.native_hooks >= 15 and self.vs_battle():
            flags |= LAB_FLAG_VS_CURSOR
        return flags

    def ai_tier(self, side):
        name = self.config.get(side + '_ai_tier', 'SILVER')
        return AI_TIERS[AI_TIER_NAMES.index(name) if name in AI_TIER_NAMES else AI_TIER_NAMES.index('SILVER')]

    def apply_ai_tiers(self, mine, enemy):
        """写入双方 AI 段位：头部段位块（原生钩子读取反应间隔与据点目标）与 controller+0x424 紧急阈值。
        startAutoPlay 只在 AUTO 由关转开时重抽 +0x420/+0x424，此处在其后写入。"""
        if self.native_hooks < 11:
            return
        p = self.p
        for index, (controller, side) in enumerate(((mine, 'player'), (enemy, 'enemy'))):
            name, _, low, high, urgency, target, smart = self.ai_tier(side)
            block = LAB_HEADER + LAB_AI_TIER + index * 0x20
            k, hold, delay, stall = AI_INVEST[name] if self.native_hooks >= 13 else (0, 0, 0, 0)
            for offset, value in ((4, low), (8, high), (12, target & 0xffffffff), (16, AI_TIER_NAMES.index(name)),
                                  (20, smart if self.native_hooks >= 12 else 0), (24, k), (28, hold | (delay << 12) | ((stall // 10) << 20))):
                p.put(block + offset, value)
            for offset in range(0, 0x20, 4):
                p.put(LAB_HEADER + LAB_AI_STATS + index * 0x20 + offset, 0)
            for offset in (0x40, 0x48):
                p.put(LAB_HEADER + LAB_AI_STATS + offset + index * 4, 0)
            for slot in range(10):
                p.put(LAB_HEADER + LAB_AI_STATS + 0x60 + index * 0x28 + slot * 4, 0)
            for offset in (0, 4):
                p.put(LAB_HEADER + LAB_AI_STATS + 0xb0 + index * 8 + offset, 0)
            p.put(block, 1)
            p.put(controller + 0x424, urgency)

    def ensure_se_channels(self):
        """建立 LAB 音效扩展通道（每进程一次，之后各场 LAB 共用，不释放）。做法与 AppMain::Sound_Create 相同：
        operator new(0xb0) → CAudioPresenter(CMediaManager app+0xab50) → setInit(端口号, 1, 1)；端口号取该端口
        原生第 1 个音效通道的值（+0x40），音量属性 4 取当前音效音量 app+0x9ae8。播放槽的登记与注销由原生
        play/stop 完成。指针写入头部 +0x310 起，最后写魔数，钩子据此启用。"""
        p = self.p
        app = self.app()
        if p.word(LAB_HEADER + LAB_SE_MAGIC) == 0x4c534531:
            return
        manager = p.word(app + 0xab50)
        if not self.valid(manager):
            return
        volume = p.word(app + 0x9ae8)
        created = []
        for port, first in ((0, 0x9b00), (1, 0x9b18)):
            native = p.word(app + first)
            if not self.valid(native):
                return
            for index in range(SE_EXTRA_PER_PORT):
                presenter = p.call('_Znwj', 0xb0)
                p.call('_ZN15CAudioPresenterC2EP13CMediaManager', presenter, manager)
                p.call('_ZN15CAudioPresenter7setInitEiii', presenter, p.word(native + 0x40), 1, 1)
                p.call('_ZN15CAudioPresenter12setAttributeEii', presenter, 4, volume)
                p.put(LAB_HEADER + LAB_SE_EXTRA + port * 0x20 + index * 4, presenter)
                created.append(hex(presenter))
        p.put(LAB_HEADER + LAB_SE_COUNT, SE_EXTRA_PER_PORT)
        for offset in range(0, 0x80, 4):
            p.put(LAB_HEADER + LAB_SE_STATS + offset, 0)
        p.put(LAB_HEADER + LAB_SE_MAGIC, 0x4c534531)
        self.record('se_channels', per_port=SE_EXTRA_PER_PORT, presenters=created)

    def se_stats(self):
        """音效扩展统计（验证用）：每端口 [请求, 同帧合并, 满队, 播放, 抢占, 最大并发, 当前并发]。"""
        p = self.p
        stats = [[p.word(LAB_HEADER + LAB_SE_STATS + port * 0x20 + i * 4) for i in range(8)] for port in (0, 1)]
        debug = [[p.word(LAB_HEADER + LAB_SE_STATS + 0x40 + port * 0x20 + i * 4) for i in range(6)] for port in (0, 1)]
        return stats + debug

    def reveal_slot(self, enemy, slot):
        """分栏每侧只显示 3 格：按键出兵的槽位不在可见范围时，把该侧滚动到能看见它。常规联机不分栏，不改动底栏。"""
        if self.native_hooks < 3 or not self.active or self.netplay_mode == 'regular':
            return
        p = self.p
        _, scene = self.battle()
        if not scene:
            return
        operator = p.word(scene + 0x3c)
        import struct
        pitch = round(struct.unpack('<f', p.read(operator + 108, 4))[0])
        if pitch <= 0:
            return
        address = LAB_HEADER + LAB_ENEMY_PANEL + 12 if enemy else operator + 100
        if enemy and not p.word(LAB_HEADER + LAB_ENEMY_PANEL_READY):
            return
        scroll = p.word(address)
        scroll = scroll - (1 << 32) if scroll & 0x80000000 else scroll
        first = max(0, round(scroll / pitch))
        if first <= slot <= first + 2:
            return
        first = slot if slot < first else slot - 2
        p.put(address, max(0, min(first, 7)) * pitch)

    def red_aura_bytes(self):
        """aura.obm（OI 04 04，256×256，16 色 RGB5_A1 调色板 + 4bpp）调色板换色：
        各色 R←max(R,G,B)，G、B←min(R,G,B)；洋红透明键保持不变。亮蓝/青 → 亮红，白芯保持白色。"""
        if self.red_aura is None:
            import struct
            import probe
            raw = bytearray((Path(probe.RESOURCE_ROOT) / probe.PKG / 'aura.obm').read_bytes())
            if raw[:4] != b'OI\x04\x04' or len(raw) != 8 + 32 + 128 * 256:
                raise ValueError('aura.obm 格式与预期不符')
            for index in range(16):
                value = struct.unpack_from('<H', raw, 8 + index * 2)[0]
                r, g, b, a = (value >> 11) & 31, (value >> 6) & 31, (value >> 1) & 31, value & 1
                if (r, g, b) != (31, 0, 31):
                    hi, lo = max(r, g, b), min(r, g, b)
                    value = (hi << 11) | (lo << 6) | (lo << 1) | a
                struct.pack_into('<H', raw, 8 + index * 2, value)
            self.red_aura = bytes(raw)
        return self.red_aura

    def ensure_red_renderer(self):
        """构造第二个 BattleEffectRenderer（12 字节），其图像以 aurR.obm 载入（由宿主返回红色版本）。
        仅在构造期间把 .rodata 中的 "aura.obm" 改为 "aurR.obm"，随即还原。整个会话复用同一对象。"""
        if self.red_renderer is not None:
            return self.red_renderer
        p = self.p
        if p.read(AURA_STRING, 9) != b'aura.obm\x00':
            self.red_renderer = 0
            self.record('red_aura_unavailable', reason='string_mismatch')
            return 0
        renderer = p.call('_Znwj', 12)
        p.write(AURA_STRING, b'aurR.obm\x00')
        try:
            p.call('_ZN20BattleEffectRendererC1Ev', renderer)
        finally:
            p.write(AURA_STRING, b'aura.obm\x00')
        self.red_renderer = renderer if self.valid(p.word(renderer + 4)) else 0
        self.record('red_aura_renderer', address=hex(renderer), image=hex(p.word(renderer + 4)))
        return self.red_renderer

    def team_list(self, team):
        p = self.p
        manager = p.call('_ZN19BattleObjectManager11getInstanceEv')
        unit = p.call('_ZN19BattleObjectManager15getTeamUnitListE12BattleTeamID18BattleTeamMemberID', manager, team, 0)
        units = []
        seen = set()
        while unit and unit not in seen and self.valid(unit) and len(seen) < 4096:
            seen.add(unit)
            units.append(unit)
            link = p.word(unit + 0x120)
            unit = link - 0x11c if link else 0
        return manager, units

    def fix_units(self, mine, enemy, red_team=None):
        """联机模式的本地修正（每帧）：
        1. BattleScene::setupResourceAll 在 GameMode 1 中把本方据点 +981 置 1（据点 HP 由对端同步，本地不扣血，
           BattleUnit::damage 0x1e0aa8 据此跳过扣血）。LAB 无对端，双方单位与据点 +981 一律清零，伤害本地结算、两边对称。
        2. BattleObjectManager::createUnit（0x1df418）只为本地玩家队伍设置绝招特效渲染器（+972/+976）；
           为敌方单位补设同一渲染器（类型 1），使敌方也显示绝招可释放光圈。
        red_team（常规联机 P2 视角，N6a）：显示红色光圈的队伍为队伍 0（P1），本方 P2 的单位补设原生渲染器（类型 1）。
        光圈类型随视角不同（常规联机双方的全部单位为类型 1，回放与观战按 P1 视角只设定对方单位），属于显示，周期校验不计入
        （netplay_session.UNIT_AURA；渲染器指针按指针屏蔽）。"""
        p = self.p
        enemy_team = p.word(enemy + 0x38c) if red_team is None else red_team
        cleared = 0
        red = self.ensure_red_renderer()
        for team in (0, 1):
            manager, units = self.team_list(team)
            renderer = p.word(manager + 64)
            if red and renderer:
                # 原渲染器的动画帧（+8，浮点）由原生逐帧推进；红色渲染器同步该帧号。
                p.put(red + 8, p.word(renderer + 8))
            enemy_renderer = red or renderer
            for unit in units:
                if p.read(unit + 981, 1)[0]:
                    p.write(unit + 981, b'\x00')
                    cleared += 1
                if team == enemy_team and enemy_renderer and p.word(unit + 972) != enemy_renderer:
                    p.call('_ZN10BattleUnit17setEffectRendererEP20BattleEffectRendererNS_18SpAttackEffectTypeE',
                           unit, enemy_renderer, 1)
                elif (red_team is not None and team != enemy_team and renderer
                      and (p.word(unit + 972) != renderer or p.word(unit + 976) != 1)):
                    p.call('_ZN10BattleUnit17setEffectRendererEP20BattleEffectRendererNS_18SpAttackEffectTypeE',
                           unit, renderer, 1)
        for controller in (mine, enemy):
            base = p.call('_ZNK16BattleController11getBaseUnitEv', controller)
            if self.valid(base) and p.read(base + 981, 1)[0]:
                p.write(base + 981, b'\x00')
                cleared += 1
        if cleared and not getattr(self, 'reported_invulnerable', False):
            self.reported_invulnerable = True
            self.record('cleared_remote_hp_lock', count=cleared)

    def recent_create(self, controller, frames=8):
        """完全控制每帧清零出兵冷却；刚出兵的槽位保留冷却显示若干帧（格子变红的原生出兵反馈），之后再清零。"""
        p = self.p
        seen = self.cooldown_seen.setdefault(controller, {})
        recent = False
        for slot in range(10):
            info = p.call('_ZNK16BattleController11getUnitInfoEi', controller, slot)
            cooldown = p.word(info + 0x18) if info else 0
            if info and cooldown and not cooldown & 0x80000000:
                first = seen.setdefault(slot, p.frame)
                recent = recent or p.frame - first < frames
            else:
                seen.pop(slot, None)
        return recent

    def apply_base_levels(self, mine, enemy):
        """准备界面设定的据点初始等级：以原生 actionKyotenLevelup 逐级提升（同时更新 AP 上限、回复量与升级成本，
        并触发原生升级事件），随后还原升级扣除的 AP。"""
        p = self.p
        for controller, key in ((mine, 'player_base_level'), (enemy, 'enemy_base_level')):
            target = max(0, min(10, int(self.config.get(key, 0))))
            ap = p.word(controller + 1028)
            while p.call(PB + '14getKyotenLevelEv', controller) < target:
                before = p.call(PB + '14getKyotenLevelEv', controller)
                p.call(PB + '19actionKyotenLevelupEv', controller)
                if p.call(PB + '14getKyotenLevelEv', controller) == before:
                    break
            p.put(controller + 1028, ap)

    def apply_ai(self, mine, enemy):
        """原生 AUTO 同时负责出兵（含弹头车）与绝招；任一开关开启即启动该方 AUTO，
        关闭的部分由原生钩子跳过（头部 +0x30，版本 ≥ 4）。旧核心下两项随“自动出兵”一起开关。"""
        p = self.p
        split = self.native_hooks >= 4
        disable = 0
        for shift, controller, deploy, special in ((0, mine, self.player_ai, self.player_auto_special),
                                                   (2, enemy, self.enemy_ai, self.enemy_auto_special)):
            enabled = (deploy or special) if split else deploy
            p.call(PB + ('13startAutoPlayEv' if enabled else '13resetAutoPlayEv'), controller)
            disable |= ((0 if deploy else 1) | (0 if special else 2)) << shift
        p.put(LAB_HEADER + LAB_AUTO_DISABLE, disable if split else 0)
        self.apply_ai_tiers(mine, enemy)

    def menu_command(self, command):
        """战斗中菜单（lab_menu.LabMenu）的选择结果。"""
        kind = command[0]
        if kind == 'toggle':
            name = command[1]
            setattr(self, name, not getattr(self, name))
            if name == 'full_control':
                if self.full_control:
                    self.applied = False       # 重新执行据点满级
            else:
                mine, enemy, _ = self.controllers()
                if self.active and mine and enemy:
                    self.apply_ai(mine, enemy)
            self.record('menu_toggle', name=name, value=getattr(self, name))
        elif kind == 'cycle':
            name = command[1]
            setattr(self, name, (getattr(self, name) + 1) % len(SUPPORT_OPTIONS))
            self.record('menu_cycle', name=name, value=getattr(self, name))
        elif kind == 'audio':
            # 音乐 / 音效开关：改写原生存档字，audio_options 在下一帧应用音量并保存（LAB 期间写入隔离的虚拟存档，
            # 离开时 leave_sandbox 保留该值并写入实际存档）。
            app = self.app()
            self.p.put(app + command[1], 0 if self.p.word(app + command[1]) else 1)
            self.record('menu_audio', offset=hex(command[1]), value=self.p.word(app + command[1]))
            self.menu.revision += 1
        elif kind == 'restart':
            self.finish('menu_restart', restart=True)   # 合拢闸门 → 离开 → 重新开始（原生开场闸门打开）
        elif kind == 'exit':
            self.finish('menu_exit')
        elif kind == 'close':
            self.menu.set_open(False)

    def describe(self, controller):
        if not controller:
            return None
        p = self.p
        slots = []
        for slot in range(10):
            unit = p.call('_ZNK16BattleController11getUnitInfoEi', controller, slot)
            if not unit:
                slots.append(None)
                continue
            cooldown = p.word(unit + 0x18)
            slots.append([p.word(unit + 0x10), p.word(unit),
                          cooldown - (1 << 32) if cooldown & 0x80000000 else cooldown])
        return {'address': hex(controller), 'class': self.classes.get(p.word(controller)),
                'team': p.word(controller + 0x38c), 'ap': p.call(PB + '5getAPEv', controller),
                'auto': p.call(PB + '11getAutoPlayEv', controller),
                'kyoten_level': p.call(PB + '14getKyotenLevelEv', controller), 'slots': slots}

    # ---------- 指令 ----------
    def execute(self, command):
        kind = command[0]
        if kind == 'start':
            self.start()
            return
        if kind == 'prep_key':
            if self.prep.open:
                self.prep.key(*command[1:])
            return
        if kind == 'prep':
            if not self.active and not self.prep.busy():
                if not self.prep.open:
                    # 打开方式决定模式：VERSUS 页本地对战为双人对战；主菜单 LAB 图标与 F7 为 LAB。
                    self.versus = len(command) > 1 and command[1] == 'versus'
                if self.prep.open:
                    self.prep.hide()
                elif self.p.word(self.app() + 0x22bc) in (99, SCENE_BATTLE):
                    self.feedback(T(self.p, 'fb_busy'), False)
                else:
                    self.prep.show()
            return
        if kind == 'exit':
            if self.active:
                self.finish('user_exit')
            return
        if kind == 'menu':
            if self.active:
                self.menu.set_open(not self.menu.open)
            return
        if kind == 'menu_move':
            if self.menu.open:
                self.menu.move(command[1])
            return
        if kind == 'menu_select':
            if self.menu.open:
                self.menu.activate()
            return
        if kind == 'toggle_full':
            self.full_control = not self.full_control
            if self.full_control and self.active:
                self.applied = False
            self.feedback(T(self.p, 'fb_full', T(self.p, 'on' if self.full_control else 'off')))
            return
        if kind in ('toggle_enemy_ai', 'toggle_player_ai'):
            if kind == 'toggle_enemy_ai':
                self.enemy_ai = not self.enemy_ai
            else:
                self.player_ai = not self.player_ai
            mine, enemy, _ = self.controllers()
            if self.active and mine and enemy:
                self.apply_ai(mine, enemy)
            self.feedback(T(self.p, 'fb_ai', T(self.p, 'on' if self.enemy_ai else 'off'),
                            T(self.p, 'on' if self.player_ai else 'off')))
            return
        if not self.active:
            return
        mine, enemy, _ = self.controllers()
        if not enemy:
            self.feedback(T(self.p, 'fb_no_enemy'), False)
            return
        p = self.p
        if kind == 'vs':
            if self.vs_battle():
                self.versus_action(command[1], (mine, enemy)[command[1]], command[2])
            return
        if self.vs_battle():
            return                                  # 双人对战期间停用 LAB 直出键（Q–P、[ ] \）
        if kind == 'enemy_unit':
            self.enemy_slot(enemy, command[1])
        elif kind == 'enemy_ap':
            if p.call(PB + '15isKyotenLevelupEv', enemy):
                p.call(p.word(p.word(enemy) + 0xa8), enemy)
                self.feedback(T(p, 'fb_enemy_ap'))
            else:
                self.feedback(T(p, 'fb_enemy_ap_no'), False)
        elif kind == 'enemy_slug':
            if p.call(PB + '16isUseMetasuraHouEv', enemy):
                p.call(p.word(p.word(enemy) + 0xa0), enemy)
                if not (self.native_hooks >= 5 and self.enemy_support):
                    self.feedback(T(p, 'fb_enemy_slug'))   # 支援效果由 publish_enemy 依原生计数提示
            else:
                self.feedback(T(p, 'fb_enemy_slug_no'), False)
        elif kind == 'enemy_special':
            from battle_controls import team_units
            ready = [u for u in team_units(p, enemy)
                     if not p.read(u + 0x3d4, 1)[0] and p.call('_ZNK10BattleUnit10isSpAttackEv', u)]
            for unit in ready:
                p.call(p.word(p.word(enemy) + 0x98), enemy, int.from_bytes(p.read(unit + 0x62, 2), 'little'))
            self.feedback(T(p, 'fb_enemy_special', len(ready)) if ready else T(p, 'fb_enemy_special_none'), bool(ready))

    def back(self):
        """在游戏线程处理 LAB 返回请求，过渡期间消费输入以保持单一导航流程。"""
        if self.finishing is not None or self.prep.busy():
            return True
        if self.prep.open:
            self.prep.key('escape')
            return True
        if self.active:
            self.menu.set_open(not self.menu.open)
            return True
        return False

    # ---------- 本地双人对战 ----------
    def vs_restore(self):
        if getattr(self, 'vs_saved', None):
            for name, value in self.vs_saved.items():
                setattr(self, name, value)
        self.vs_saved = None

    def vs_battle(self):
        return self.active and getattr(self, 'vs_saved', None) is not None

    def versus_keys(self):
        """双人键位：{'p1': {动作: GLFW 键名}, 'p2': …}；设定缺项时以默认补齐。"""
        configured = self.config.get('versus_keys') or {}
        return {side: {action: (configured.get(side) or {}).get(action, default)
                       for action, default in VERSUS_KEYS[side].items()} for side in VERSUS_KEYS}

    def versus_pad(self):
        """双人手柄功能键：{'p1': {动作: 按键名}, 'p2': …}；左右选择固定为十字键与左摇杆。"""
        from lab_versus_input import PAD_DEFAULTS
        configured = self.config.get('versus_pad') or {}
        return {side: {action: (configured.get(side) or {}).get(action, default)
                       for action, default in PAD_DEFAULTS.items()} for side in ('p1', 'p2')}

    def versus_action(self, side, controller, action):
        """side 0 为 P1（我方），1 为 P2（敌方）。选格、出兵、AP 升级、全体绝招、弹头车（支援接口 0 号）。"""
        p = self.p
        label = ('P1', 'P2')[side]
        slots = max(1, min(10, p.word(controller + 0x390)))
        if action in ('left', 'right'):
            cursor = max(0, min(slots - 1, self.vs_cursor[side] + (1 if action == 'right' else -1)))
            self.vs_cursor[side] = cursor
            self.reveal_slot(side == 1, cursor)
            return
        if action == 'deploy':
            self.deploy_slot(controller, self.vs_cursor[side], label, side == 1)
        elif action == 'ap':
            if p.call(PB + '15isKyotenLevelupEv', controller):
                p.call(p.word(p.word(controller) + 0xa8), controller)
                self.feedback(T(p, 'fb_vs_ap', label))
            else:
                self.feedback(T(p, 'fb_vs_ap_no', label), False)
        elif action == 'slug':
            if p.call(PB + '16isUseMetasuraHouEv', controller):
                p.call(p.word(p.word(controller) + 0xa0), controller)
                self.feedback(T(p, 'fb_vs_slug', label))
            else:
                self.feedback(T(p, 'fb_vs_slug_no', label), False)
        elif action == 'special':
            from battle_controls import team_units
            ready = [u for u in team_units(p, controller)
                     if not p.read(u + 0x3d4, 1)[0] and p.call('_ZNK10BattleUnit10isSpAttackEv', u)]
            for unit in ready:
                p.call(p.word(p.word(controller) + 0x98), controller, int.from_bytes(p.read(unit + 0x62, 2), 'little'))
            self.feedback(T(p, 'fb_vs_special', label, len(ready)) if ready else T(p, 'fb_vs_special_none', label),
                          bool(ready))

    def deploy_slot(self, controller, slot, label, enemy_side):
        """双方共用的选格出兵：与 enemy_slot 相同的原生检查、出兵与音效。"""
        p = self.p
        main, _ = self.battle()
        if not main or not p.call('_ZN10BattleMain15isBattlePlayingEv', main):
            return
        info = p.call('_ZNK16BattleController11getUnitInfoEi', controller, slot)
        if not info:
            self.feedback(T(p, 'fb_empty_slot', label), False)
            return
        if p.call('_ZNK16BattleController15isUnitCountOverEv', controller):
            self.feedback(T(p, 'fb_unit_limit', label), False)
            return
        if not p.call(PB + '12isUnitCreateEi', controller, slot):
            self.feedback(T(p, 'fb_cannot', label, p.call(PB + '5getAPEv', controller), p.word(info)), False)
            return
        created = p.call(p.word(p.word(controller) + 0x94), controller, slot)
        if created:
            p.call('_ZN17FrameworkInstance6playSEENS_9SoundTypeE7SoundIDi', 0, 8, 0)
        self.record('vs_unit', side=label, slot=slot + 1, unit_id=p.word(info + 0x10), created=bool(created))
        self.reveal_slot(enemy_side, slot)
        self.feedback(T(p, 'fb_vs_deployed' if created else 'fb_rejected', label), bool(created))

    def enemy_slot(self, enemy, slot):
        p = self.p
        key = 'QWERTYUIOP'[slot]
        main, _ = self.battle()
        if not main or not p.call('_ZN10BattleMain15isBattlePlayingEv', main):
            self.feedback(T(p, 'fb_not_playing', key), False)
            return
        info = p.call('_ZNK16BattleController11getUnitInfoEi', enemy, slot)
        if not info:
            self.feedback(T(p, 'fb_empty_slot', key), False)
            return
        if p.call('_ZNK16BattleController15isUnitCountOverEv', enemy):
            self.feedback(T(p, 'fb_unit_limit', key), False)
            return
        if not p.call(PB + '12isUnitCreateEi', enemy, slot):
            self.feedback(T(p, 'fb_cannot', key, p.call(PB + '5getAPEv', enemy), p.word(info)), False)
            return
        created = p.call(p.word(p.word(enemy) + 0x94), enemy, slot)
        if created:
            # 与我方按键出兵（probe.activate_unit_slot）相同的原生出兵音效。
            p.call('_ZN17FrameworkInstance6playSEENS_9SoundTypeE7SoundIDi', 0, 8, 0)
        self.record('enemy_unit', slot=slot + 1, unit_id=p.word(info + 0x10), created=bool(created))
        self.reveal_slot(True, slot)
        self.feedback(T(p, 'fb_deployed' if created else 'fb_rejected', key), bool(created))
