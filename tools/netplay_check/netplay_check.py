"""MSD WINDOWS S1XLV 联机验收工具（N4，docs/netcode/N4_TWO_MACHINE_ACCEPTANCE.md）。

两台电脑各运行一条命令即可：经局域网、会合服务器或直接连接进行一场无窗口联机对战（双方输入由固定脚本产生），
自动交换并逐项比较每 30 帧的战斗状态校验值，最后显示“通过 / 未通过”。默认进行 2 轮（第 2 轮为再战：互换编队、重新抽取种子与地图）。
不读写任何玩家存档：使用本目录 fixture 中测试存档的副本；LAB 设定、模组设定与缓存均写在结果目录中。
结果目录：游戏目录\\verification\\netplay_check\\<时间>_<命令>\\（result.json、probe.log）。

用法（在游戏目录中，以随包的 windows_runtime\\python.exe 运行）：
  局域网      A：netplay_check.py host                       B：netplay_check.py join（自动搜索局域网房间）
  直接连接    A：netplay_check.py host [--upnp]              B：netplay_check.py join --address <A 的地址>:47631
  会合服务器  S：netplay_check.py server                     A：netplay_check.py rdv-host --server <S>:47632
              B：netplay_check.py rdv-join --server <S>:47632 --code <A 显示的房间码>
  单机参照    netplay_check.py reference                     （不联网，输出校验值；可与另一台电脑的参照用 compare 比较）
  观战        C：netplay_check.py spectate（局域网）、spectate --address <A>:47631、spectate --server <S>:47632 --code <房间码>
  回放校验    netplay_check.py replay <回放文件> [--seek-test]
  比较结果    netplay_check.py compare <result.json> <result.json>
  本机双客户端 netplay_check.py local-pair [编号]            （local_pair.bat：在一台电脑上运行房主与加入方两个独立进程并汇总结果）
断线测试：--outage-at 600 --outage 4（第 600 帧起本机模拟断网 4 秒，应恢复）；--outage 15（超过断线判定，应体面结束）。
篡改检测（N5，模拟修改过的客户端）：--tamper ap@600（第 600 帧起锁定本方 AP）、base-hp@600、row@600（改动单位数据行）、
  withhold@300（不再发送校验值）、echo@300（把对方的校验值原样发回）；对方与本方都应检出分歧、交换分歧数据、生成分歧报告并体面结束
  （--expect-end desync）。--forge-manifest <manifest.json>：向对方报告指定的内容清单（伪造清单），实际内容不同时应在开战前被检出
  （--expect-end frame0）。分歧报告写入结果目录 desync_*.json。
"""
import argparse
import json
import os
import platform
import shutil
import socket
import struct
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIXTURE = HERE / 'fixture'
DECK_1 = [[3, 40], [51, 40], [16, 40], ['s1xlv.kt21', 40], ['s1xlv.white_mummy', 40],
          ['s1xlv.green_mummy', 40], ['s1xlv.mummy_generator_mk2', 40], ['s1xlv.pf_paratrooper', 40], [2, 40], [6, 40]]
DECK_2 = [[2, 40], [6, 40], [17, 40], ['s1xlv.heavy_b_future', 40], ['s1xlv.m15a_future', 40],
          ['s1xlv.pf_mortar', 40], ['s1xlv.di_cokka_mk2', 40], [98, 40], [117, 40], [28, 40]]
POOL = [1011, 1055, 2121, 3165]           # 验收用地图池（正式对战地图池在 N6 核查原版 Wi-Fi 对战后确定）
REFERENCE_SEED, REFERENCE_STAGE = 12345, 1011


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('host', 'join', 'rdv-host', 'rdv-join', 'server', 'reference', 'compare', 'replay', 'spectate',
                                            'local-pair'))
    parser.add_argument('files', nargs='*', help='compare：两个 result.json；local-pair：测试编号；replay：回放文件')
    parser.add_argument('--address', help='join：房主地址 IP:端口（不填时搜索局域网）')
    parser.add_argument('--server', help='rdv-host / rdv-join：会合服务器 地址:端口')
    parser.add_argument('--code', help='rdv-join：房间码')
    parser.add_argument('--code-file', help='rdv-join：从文件读取房间码（等待文件出现，测试用）')
    parser.add_argument('--port', type=int, default=None, help='host：对战端口（默认 47631；rdv-host 默认随机）；server：47632')
    parser.add_argument('--bind', default='0.0.0.0', help='绑定地址（测试时用 127.0.0.1）')
    parser.add_argument('--discovery-port', type=int, default=None, help='局域网发现端口（默认 47630）')
    parser.add_argument('--scan-target', action='append', help='join：发现查询的目标 IP:端口（默认广播）')
    parser.add_argument('--no-lan', action='store_true', help='host：不应答局域网发现')
    parser.add_argument('--upnp', action='store_true', help='host：尝试在路由器上自动开放对战端口（UPnP），结束时删除')
    parser.add_argument('--name', default=socket.gethostname())
    parser.add_argument('--rounds', type=int, default=2)
    parser.add_argument('--frames', type=int, default=0, help='每轮最多帧数（0 = 打到分出胜负）')
    parser.add_argument('--base-hp', type=float, default=0, help='测试：双方据点生命（长时测试避免提前结束）')
    parser.add_argument('--delay', type=int, default=2, help='输入延迟帧数（0 = 按网络延迟自动）')
    parser.add_argument('--disconnect-after', type=float, default=10.0, help='多少秒收不到对方的包判定为断线')
    parser.add_argument('--outage-at', type=int, default=0, help='断线测试：第几帧开始模拟本机断网')
    parser.add_argument('--outage', type=float, default=0, help='断线测试：模拟断网秒数')
    parser.add_argument('--expect-end', default='finished', choices=('finished', 'disconnected', 'desync', 'frame0', 'rejected'),
                        help='disconnected：断线测试，期望双方体面结束；desync / frame0：篡改测试，期望对战中 / 开战前检出分歧')
    parser.add_argument('--expect-region', help='篡改测试：分歧报告中应出现的区域（如 controller、unit、table、missing）')
    parser.add_argument('--wait', type=float, default=600, help='等待对方加入或连接的秒数')
    parser.add_argument('--connect-timeout', type=float, default=12.0)
    parser.add_argument('--use-my-mods', action='store_true', help='使用本机的模组启用列表（默认不启用模组）')
    parser.add_argument('--mods-enabled', help='测试：使用指定的模组启用列表文件')
    parser.add_argument('--out', help='结果目录')
    parser.add_argument('--fixture', help='测试存档目录（默认本目录 fixture）')
    # 以下为本机回环测试用
    parser.add_argument('--latency', type=float, default=0.0, help='测试：模拟单向延迟（毫秒）')
    parser.add_argument('--jitter', type=float, default=0.0)
    parser.add_argument('--loss', type=float, default=0.0)
    parser.add_argument('--nat', choices=('full_cone', 'port_restricted', 'symmetric'), help='测试：模拟本方路由器')
    parser.add_argument('--force-seed', type=int, help='测试：固定比赛种子（双方须相同）')
    parser.add_argument('--force-stage', type=int, help='测试：固定地图（双方须相同）')
    parser.add_argument('--swap-decks', action='store_true', help='reference：使用第 2 轮的编队（互换）')
    parser.add_argument('--warmup', type=int, default=0, help='测试：连接前先进行 N 帧本地 LAB 对战（使双方进程历史不同）')
    parser.add_argument('--warmup-stage', type=int, default=1165, help='测试：本地 LAB 对战的地图')
    parser.add_argument('--kill-at', type=int, default=0, help='测试：对战第 N 帧时本进程直接退出（模拟崩溃）')
    parser.add_argument('--pool', help='地图池，逗号分隔')
    parser.add_argument('--tamper', help='测试（N5）：模拟修改过的客户端，种类@帧：ap、base-hp、row、withhold、echo')
    parser.add_argument('--forge-manifest', help='测试（N5）：向对方报告此文件中的内容清单（伪造清单）')
    parser.add_argument('--save-manifest', action='store_true', help='把本机内容清单写入结果目录 manifest.json')
    parser.add_argument('--replay-dir', help='回放保存目录（默认结果目录 replays\\）')
    parser.add_argument('--no-replay', action='store_true', help='不保存回放')
    parser.add_argument('--seek-test', action='store_true', help='replay：同时测试暂停、倍速与前后跳转（N5.5）')
    parser.add_argument('--present', action='store_true', help='replay：逐帧显示（默认不显示，较快）')
    parser.add_argument('--spectators', type=int, default=4, help='房主：观战席位（0 = 不接受观战；R6：最多 4）')
    parser.add_argument('--regular', action='store_true',
                        help='N6a 常规联机：双方以各自存档的当前编队、单位等级与据点基础状态对战；P2 绑定本方底栏与视角')
    parser.add_argument('--touch-test', action='store_true',
                        help='N6a：另以原生触点点击底栏出兵格、AP 与弹头车按钮（经核心捕获转为联机输入）')
    return parser.parse_args(argv)


def script(frame, side):
    """双方固定脚本输入（与 N3 相同）：出兵每 20 帧轮换槽位，据点升级、全体绝招、弹头车间隔触发。"""
    import netplay_session as ns
    t = frame - 1
    slot = (t // 20 + 3 * side) % 10 if t % 20 == 10 * side else None
    return ns.encode(slot=slot, ap=t % 300 == 150 + 7 * side, special=t % 450 == 225 + 11 * side,
                     slug=t % 900 == 600 + 13 * side)


def regular_script(session, frame, side):
    """常规联机的脚本输入：固定脚本 + 每 450 帧（错开）对本方第一个绝招就绪的单位发动单体绝招（点击单位，N6a）。"""
    value = script(frame, side)
    t = frame - 1
    if t % 450 == 330 + 17 * side:
        from battle_controls import team_units
        p = session.p
        controller = session.controllers[side]
        for unit in team_units(p, controller):
            if not p.read(unit + 0x3d4, 1)[0] and p.call('_ZNK10BattleUnit10isSpAttackEv', unit):
                import netplay_session as ns
                value |= ((int.from_bytes(p.read(unit + 0x62, 2), 'little') + 1) & 0xffffff) << ns.UNIT_SHIFT
                break
    return value


TOUCH_PLAN = ((420, 'slot', 0), (700, 'slot', 1), (980, 'ap', None), (1260, 'slot', 2), (1500, 'unit', None),
              (1800, 'unit', None), (2000, 'slug', None), (2200, 'unit', None))


class TouchTest:
    """N6a：在指定帧以原生触点点击底栏（槽位、AP 升级、弹头车）与战场上绝招可用的本方单位（单体绝招），记录核心捕获的操作数。
    坐标为 1280×720 逻辑坐标。"""

    def __init__(self, session):
        self.session = session
        self.sent = []
        self.missed = []                      # 当时找不到目标（例如没有绝招可用的单位）

    def position(self, kind, slot):
        """以原生命中函数 getUnitIndex（参考坐标：逻辑坐标 ÷ 1.125 − 88.9）在底栏高度上逐点查找目标，返回其中点的逻辑坐标。"""
        p = self.session.p
        op = self.session.operator
        if kind == 'unit':
            return self.unit_position()
        target = {'ap': 0x64, 'slug': 0x65}.get(kind, slot)
        y = 650
        hits = [x for x in range(0, 1280, 2)
                if p.call('_ZN20BattlePlayerOperator12getUnitIndexEii', op, int(x / 1.125 - 88.9) & 0xffffffff,
                          int(y / 1.125)) == target]
        return (hits[len(hits) // 2], y) if hits else None

    def unit_position(self):
        """绝招可用的本方单位在画面上的位置。原生 onGameScreenTouchEnded（0x1d74a8）：参考坐标 x 加 BattleScreen::getScreenPosition
        得世界 x，与单位 +0x8c 相差不超过 99、触点 y 与单位 +0x90 相差小于 80 即命中。"""
        import struct
        from battle_controls import team_units
        p = self.session.p
        op = self.session.operator
        controller = p.word(op + 0x18)
        camera = struct.unpack('<i', struct.pack('<I', p.call('_ZN12BattleScreen17getScreenPositionEv', p.word(op + 0x1c))))[0]
        for unit in team_units(p, controller):
            if p.read(unit + 0x3d4, 1)[0] or not p.call('_ZNK10BattleUnit10isSpAttackEv', unit):
                continue
            x, y = struct.unpack('<ff', p.read(unit + 0x8c, 8))
            lx, ly = (x - camera + 88.9) * 1.125, (y - 30) * 1.125
            if 40 <= lx <= 1240 and 0 <= ly <= 560:
                return int(lx), int(ly)
        return None

    def step(self, frame):
        for at, kind, slot in TOUCH_PLAN:
            if frame == at:
                pos = self.position(kind, slot)
                if pos:
                    self.session.queue_touch(1, *pos)
                    self.sent.append([frame, kind, slot, pos, 'down'])
                else:
                    self.missed.append([frame, kind])
            if frame == at + 3 and self.sent and self.sent[-1][0] == at:
                pos = self.sent[-1][3]
                self.session.queue_touch(3, *pos)

    def status(self):
        return {'sent': self.sent, 'missed': self.missed, 'captured': self.session.stats.get('native_actions'),
                'actions': dict(self.session.actions.stats)}


def cpu_name():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
            return winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
    except OSError:
        return platform.processor()


CONSOLE = sys.stdout                     # 游戏日志改写到结果目录的 console.log 后，进度文字仍显示在控制台


def memory_mb():
    """本进程的工作集与提交内存（MiB）。"""
    try:
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD), ('PeakWorkingSetSize', ctypes.c_size_t),
                        ('WorkingSetSize', ctypes.c_size_t), ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t),
                        ('PeakPagefileUsage', ctypes.c_size_t)]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL('kernel32')
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        ctypes.WinDLL('psapi').GetProcessMemoryInfo(ctypes.c_void_p(kernel.GetCurrentProcess()), ctypes.byref(counters),
                                                     counters.cb)
        return {'working_set': round(counters.WorkingSetSize / 2**20, 1), 'private': round(counters.PagefileUsage / 2**20, 1),
                'peak_working_set': round(counters.PeakWorkingSetSize / 2**20, 1)}
    except Exception:
        return None


def guest_heap(p):
    """客体堆（0x12000000 起，上限 0x1e000000）：顶部、已分配、空闲块与最大空闲块（MiB）。"""
    free = sum(size for _, size in p.free_blocks)
    return {'top': round((p.heap - 0x12000000) / 2**20, 1), 'allocated': round(sum(p.allocations.values()) / 2**20, 1),
            'free': round(free / 2**20, 1), 'largest_free': round(max((s for _, s in p.free_blocks), default=0) / 2**20, 2),
            'blocks': len(p.allocations)}


def say(text):
    print(text, file=CONSOLE, flush=True)


class Game:
    """无窗口游戏进程与逐帧辅助（每帧另调用 services 中各对象的 service/poll，保持网络连接）。"""

    def __init__(self, p, out, report):
        self.p, self.out, self.report = p, out, report
        self.services = []
        self.manifest = None                     # 本机实际内容清单（回放记录用）
        self.hub = None                          # 房主的观战转发（netplay_spectate.SpectatorHub）；开放房间时建立
        self.reported_manifest = None
        self.room_services = []                  # 房主：连接建立后仍需服务的房间对象（局域网应答、会合房间、打洞），供观战者加入
        self.room_cleanup = []

    def context(self):
        app = self.p.app_instance()
        return {'frame': self.p.frame, 'scene': self.p.word(app + 0x22bc), 'state': self.p.word(app + 0x22dc)}

    def service(self):
        for item in self.services:
            item()

    def frame(self):
        self.p.step_frame()
        self.service()

    def frames(self, count):
        for _ in range(count):
            self.frame()

    def wait(self, predicate, limit, tag):
        for _ in range(limit):
            self.frame()
            if predicate():
                return
        raise RuntimeError('等待超时: ' + tag + ' ' + json.dumps(self.context()))

    def until(self, predicate, seconds, frames=True):
        """等待条件成立：frames 为真时逐帧推进游戏，否则只处理网络（不推进原生帧）。"""
        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            if frames:
                self.frame()
                time.sleep(0.004)                    # 等待对方期间约 120 帧每秒，避免空转
            else:
                self.service()
                time.sleep(0.002)
            if predicate():
                return True
        return predicate()

    def tap(self, x, y):
        self.p.touch_event(1, x, y)
        self.frames(3)
        self.p.touch_event(3, x, y)

    def to_menu(self):
        self.wait(lambda: self.context()['scene'] == 20 and self.p.frame > 150, 1500, 'title')
        self.tap(640, 500)
        for _ in range(1800):
            self.frame()
            state = self.context()
            if state['scene'] == 28 and state['state'] == 1:
                self.frames(30)
                return
            if state['scene'] == 120 and self.p.frame % 30 == 0:          # 原生弹窗（登入奖励等）：OK
                self.tap(640, 435)
            if state['scene'] == 82 and self.p.frame % 30 == 0:           # 登入奖励页右下 OK
                self.tap(1165, 680)
        raise RuntimeError('等待主菜单超时 ' + json.dumps(self.context()))

    def versus_prep(self):
        lab = self.p.lab
        if not (lab.prep.open and lab.versus and not lab.prep.busy() and not lab.active):
            if not (lab.prep.open and lab.versus):
                lab.commands.append(('prep', 'versus'))
            self.wait(lambda: lab.prep.open and lab.versus and not lab.prep.busy() and not lab.active, 900, 'versus_prep')

    def warmup(self, frames, stage=1165):
        """本地 LAB 对战（双方段位 AI）若干帧后退出：使本进程的历史（堆布局、已载入资源等）与对方不同。"""
        import netplay_session as ns
        lab = self.p.lab
        self.versus_prep()
        saved = dict(lab.config)
        config = ns.NetplayBattle.match_config(None, stage, DECK_2, DECK_1)
        config.update(player_ai=True, enemy_ai=True)
        lab.config_override = config
        lab.config.update(config)
        lab.prep.command('start')
        self.wait(lambda: lab.active and lab.applied, 2400, 'warmup_start')
        self.frames(frames)
        lab.finish('netplay_check_warmup')
        self.wait(lambda: not lab.active and lab.prep.open and not lab.prep.busy(), 1200, 'warmup_end')
        lab.config_override = None
        lab.config = saved


# ---------- 环境 ----------
def prepare_environment(args, out):
    """在导入游戏模块之前设定：LAB 设定、内容缓存、模组设定写入结果目录；复制测试存档。"""
    (out / 'config').mkdir(parents=True, exist_ok=True)
    os.environ['MSD_LAB_CONFIG_DIR'] = str(out / 'config')
    os.environ['MSD_CONTENT_DIGEST_CACHE'] = str(out / 'content_digests.json')
    local = os.environ.get('LOCALAPPDATA')
    user_ids = Path(local) / 'MSD_WINDOWS_S1XLV' / 'mods_ids.json' if local else None
    user_enabled = Path(local) / 'MSD_WINDOWS_S1XLV' / 'mods_enabled.json' if local else None
    if args.use_my_mods and user_ids and user_ids.is_file():
        shutil.copyfile(user_ids, out / 'mods_ids.json')
    os.environ['MSD_MOD_ID_MAP'] = str(out / 'mods_ids.json')
    if args.mods_enabled:
        shutil.copyfile(args.mods_enabled, out / 'mods_enabled.json')
    elif args.use_my_mods and user_enabled and user_enabled.is_file():
        shutil.copyfile(user_enabled, out / 'mods_enabled.json')
    else:
        (out / 'mods_enabled.json').write_text('{"schema": 1, "enabled": []}', encoding='utf-8')
    os.environ['MSD_MODS_ENABLED'] = str(out / 'mods_enabled.json')
    fixture = Path(args.fixture) if args.fixture else FIXTURE
    save = out / 'save' / 'data/data/com.snkplaymore.android003'
    save.mkdir(parents=True, exist_ok=True)
    for name in ('test.dat', 'community_progress.json'):
        shutil.copyfile(fixture / 'data/data/com.snkplaymore.android003' / name, save / name)
    return out / 'save'


def bootstrap(args, out, report):
    save_root = prepare_environment(args, out)
    sys.path.insert(0, str(ROOT))
    import portable_launcher  # noqa: F401  随包 Python 与 ANGLE 的 DLL 目录
    import event_trial_launcher  # noqa: F401  正式入口的探针类与 LAB 运行时
    import player
    import lab as lab_module

    original_record = lab_module.Lab.record

    def isolated_record(self, kind, **values):          # LAB 运行记录写入结果目录
        root = self.root
        self.root = out
        try:
            return original_record(self, kind, **values)
        finally:
            self.root = root
    lab_module.Lab.record = isolated_record
    p = player.Probe(guest_root=save_root, log_name=str(out / 'probe.log'), window_handle=None,
                     window_size=(1280, 720), audio_mode='silent')
    p.initialize()
    report['core'] = Path(p.uc.library_path).name
    return Game(p, out, report)


# ---------- 连接 ----------
def make_endpoint(args, port):
    import netplay_net as nn
    sock = nn.SimNat(args.nat, '10.77.%d.2' % (1 if args.command.endswith('host') else 2)) if args.nat else None
    return nn.Endpoint((args.bind, port), sock=sock, latency_ms=args.latency, jitter_ms=args.jitter, loss=args.loss,
                       seed=os.getpid())


def establish(args, game, report, digest):
    """按命令建立连接，返回 (PeerLink, 角色)；失败时返回 (None, 原因)。连接期间不推进游戏帧。"""
    import netplay_net as nn
    info = {'name': args.name, 'version': report.get('game_version'), 'digest': digest[:16]}
    if args.command == 'spectate':
        info['role'] = 'spectator'
    deadline = time.perf_counter() + args.wait
    cleanup = []
    try:
        if args.command in ('host', 'rdv-host'):
            port = args.port if args.port is not None else (nn.GAME_PORT if args.command == 'host' else 0)
            endpoint = make_endpoint(args, port)
            listener = nn.Listener(endpoint, info, disconnect_after=args.disconnect_after)
            services = [listener.service]
            if args.spectators > 0:                       # 观战：开放房间时即接受观战连接（对手加入之前加入的观战者等待开战）
                from netplay_spectate import SpectatorHub
                game.hub = SpectatorHub(endpoint, game.reported_manifest, args.name, report.get('game_version', ''),
                                        args.spectators, args.disconnect_after)

            def pump():
                for item in services:
                    item()
                if game.hub is not None:
                    game.hub.service()
            if args.command == 'host':
                address = endpoint.address
                report['listen'] = list(address)
                if not args.no_lan:
                    discovery = (args.bind, args.discovery_port or nn.DISCOVERY_PORT)
                    responder = nn.LanResponder(lambda: dict(info, port=endpoint.address[1],
                                                             state='busy' if listener.link else 'open',
                                                             spectators=len(game.hub.watchers()) if game.hub else 0,
                                                             spectate=args.spectators), bind=discovery)
                    cleanup.append(responder.close)
                    services.append(responder.service)
                    report['discovery'] = list(discovery)
                if args.upnp:
                    import upnp_igd
                    mapping = upnp_igd.open_port(endpoint.address[1], 'MSD S1XLV netplay check')
                    report['upnp'] = mapping
                    if mapping.get('ok'):
                        cleanup.append(lambda: upnp_igd.close_port(mapping))
                        say(f"UPnP：路由器已开放端口，对方可直接连接 {mapping.get('external_ip')}:{mapping.get('external_port')}")
                    else:
                        say('UPnP 未成功：' + str(mapping.get('error')))
                say(f"等待对方加入：本机地址 {', '.join(f'{ip}:{p}' for ip, p in endpoint.candidates())}"
                    f"（Waiting for the opponent）")
            else:
                server = nn.parse_address(args.server, nn.RENDEZVOUS_PORT)
                rendezvous = nn.Rendezvous(endpoint, server, info)
                rendezvous.on_peer = lambda candidates, punch, peer: listener.punch(candidates, punch)
                rendezvous.register()
                services.append(rendezvous.service)
                shown = False
                while time.perf_counter() < deadline and listener.link is None:
                    pump()
                    if rendezvous.state == 'registered' and not shown:
                        shown = True
                        report['room_code'] = rendezvous.code
                        report['public'] = rendezvous.public
                        (game.out / 'room_code.txt').write_text(rendezvous.code, encoding='utf-8')
                        say(f'房间码 Room code：{rendezvous.code}    本方公网地址 public：{rendezvous.public}')
                    if rendezvous.state == 'failed':
                        return None, rendezvous.reason
                    time.sleep(0.005)
                cleanup.append(rendezvous.unregister)
            while time.perf_counter() < deadline and listener.link is None:
                pump()
                time.sleep(0.005)
            if listener.link is None:
                return None, 'timeout'
            report['peer'] = dict(listener.link.peer_info, address=list(listener.link.remote))
            if args.spectators > 0:                       # 观战：对战期间继续应答局域网发现、保持会合房间并打洞
                game.room_services, game.room_cleanup = services, cleanup[:]
                cleanup.clear()
            return listener.link, 'host'
        endpoint = make_endpoint(args, 0)
        if args.command == 'join' or (args.command == 'spectate' and not args.server):
            if args.address:
                candidates = [nn.parse_address(args.address, nn.GAME_PORT)]
            else:
                targets = ([nn.parse_address(t, nn.DISCOVERY_PORT) for t in args.scan_target] if args.scan_target
                           else nn.broadcast_targets(args.discovery_port or nn.DISCOVERY_PORT))
                say('搜索局域网房间…（Searching the LAN）')
                scanner = nn.LanScanner(targets, bind=(args.bind, 0))
                cleanup.append(scanner.close)
                rooms = []
                while time.perf_counter() < deadline and not rooms:
                    scan_end = time.perf_counter() + 1.0
                    while time.perf_counter() < scan_end:
                        scanner.service()
                        time.sleep(0.01)
                    wanted = ('open', 'busy') if args.command == 'spectate' else ('open',)
                    rooms = [r for r in scanner.rooms.values() if r.get('protocol') == nn.PROTOCOL and r.get('state') in wanted]
                report['lan_rooms'] = [{k: r.get(k) for k in ('name', 'address', 'version', 'digest', 'state')}
                                       for r in scanner.rooms.values()]
                if not rooms:
                    return None, 'no_lan_room'
                rooms.sort(key=lambda r: (r.get('digest') != digest[:16], r.get('name', '')))
                say('找到房间 Found：' + ', '.join(f"{r.get('name')} {r['address'][0]}:{r['address'][1]}" for r in rooms))
                candidates = [tuple(rooms[0]['address'])]
            connector = nn.Connector(endpoint, candidates, info, timeout=args.connect_timeout,
                                     disconnect_after=args.disconnect_after)
            while connector.state == 'connecting':
                connector.service()
                time.sleep(0.005)
        else:
            server = nn.parse_address(args.server, nn.RENDEZVOUS_PORT)
            code = args.code
            if not code and args.code_file:
                path = Path(args.code_file)
                while time.perf_counter() < deadline and not path.is_file():
                    time.sleep(0.05)
                code = path.read_text(encoding='utf-8').strip() if path.is_file() else None
            if not code:
                return None, 'no_room'
            rendezvous = nn.Rendezvous(endpoint, server, info)
            rendezvous.join(code)
            connector = None
            while True:
                endpoint.poll()
                rendezvous.service(keep_joining=connector is not None and connector.state == 'connecting')
                if rendezvous.state == 'failed':
                    return None, rendezvous.reason
                if connector is None and rendezvous.state == 'joined':
                    report['host_candidates'] = [list(c) for c in rendezvous.host_candidates]
                    report['public'] = rendezvous.public
                    connector = nn.Connector(endpoint, rendezvous.host_candidates, info, timeout=args.connect_timeout,
                                             punch_token=rendezvous.punch, disconnect_after=args.disconnect_after)
                if connector is not None:
                    connector.service()
                    if connector.state != 'connecting':
                        report['learned_candidates'] = connector.learned
                        break
                time.sleep(0.005)
            if connector.state == 'failed':
                return None, 'punch_failed'
        if connector.state != 'connected':
            return None, connector.reason or connector.state
        report['peer'] = dict(connector.link.peer_info, address=list(connector.link.remote))
        return connector.link, 'spectator' if args.command == 'spectate' else 'client'
    finally:
        for item in cleanup:
            try:
                item()
            except Exception:
                pass


# ---------- 对战 ----------
def percentiles(values):
    if not values:
        return None
    values = sorted(values)
    pick = lambda q: round(values[min(len(values) - 1, int(len(values) * q))] * 1000, 2)
    return {'p50': pick(0.5), 'p95': pick(0.95), 'p99': pick(0.99), 'max': round(values[-1] * 1000, 2)}


def set_base_hp(p, value):
    # 测试参数：把单精度浮点的位模式写入据点生命（+776 为整数字段），2000000 的等效生命约 12.4 亿，只用于使长时间测试不提前结束。
    # N4 起的参照均以此方式生成，保持不变。
    manager = p.call('_ZN19BattleObjectManager11getInstanceEv')
    for team in (0, 1):
        base = p.call('_ZN19BattleObjectManager13getKyotenUnitE12BattleTeamID18BattleTeamMemberID', manager, team, 0)
        p.write(base + 776, struct.pack('<f', value))


def back_to_prep(game):
    lab = game.p.lab
    try:
        game.wait(lambda: not lab.active and lab.prep.open and not lab.prep.busy(), 2400, 'back_to_prep')
        return True
    except RuntimeError:
        return False


def battle(game, link, match, m, args):
    """一轮联机对战。返回本轮记录（结束原因、校验值、结果比较、耗时统计）。"""
    import netplay_session as ns
    from frame_pacer import FramePacer
    p, lab = game.p, game.p.lab
    record = {'match': m, 'started': time.strftime('%H:%M:%S'), 'memory_before': memory_mb(), 'guest_heap_before': guest_heap(p)}
    if args.regular:
        import netplay_regular
        session = netplay_regular.RegularBattle(p, m['side'], m['seed'], delay=m['delay'], interval=30)
        session.local_input = lambda frame, side: regular_script(session, frame, side) | session.collect(frame, side)
    else:
        session = ns.NetplayBattle(p, m['side'], m['seed'], delay=m['delay'], interval=30)
        session.local_input = script
    session.prepare(session.match_config(m['stage'], m['p1_deck'], m['p2_deck'], m.get('p1_status'), m.get('p2_status')))
    game.wait(session.ready, 2400, 'battle_start')
    if args.base_hp:
        set_base_hp(p, args.base_hp)
    checksum0 = session.begin()
    record['frame0'] = {'checksum': list(checksum0), 'battle_frame': session.battle_frame0, 'units': session.deck_digests}
    match.send_ready(checksum0, session.battle_frame0, session.deck_digests)
    started = time.perf_counter()
    while match.poll() == 'locked' and time.perf_counter() - started < 120:     # 等待对方到达第 0 帧：不推进原生帧
        time.sleep(0.002)
    record['ready_wait_seconds'] = round(time.perf_counter() - started, 3)
    if match.state != 'battle':
        if match.state == 'rejected' and 'frame0_mismatch' in str(match.reason):
            record['desync_report'] = exchange_desync(game, link, match, session, frame0=True)
        session.end()
        lab.finish('netplay_not_started')
        record.update(end='not_started', match_state=match.state, match_reason=match.reason,
                      differences=match.differences, prep_returned=back_to_prep(game))
        return record
    session.transport = link
    peer = (match.peer or {}).get('name', '?')
    names = [args.name, peer] if m['side'] == 0 else [peer, args.name]
    if game.hub is not None:
        game.hub.begin_round(session, m['round'], m, names, {'base_hp': args.base_hp} if args.base_hp else None)
    pacer = FramePacer(30)
    history, ticks, tick_times = {}, 0, []
    outage_done = False
    tamper = Tamper(args.tamper, game, session, link, m) if args.tamper else None
    touch = TouchTest(session) if args.regular and args.touch_test else None
    end = None
    loop_started = time.perf_counter()
    try:
        while end is None:
            if args.outage and not outage_done and session.frame >= args.outage_at:
                outage_done = True
                link.endpoint.blackout(args.outage)
                record['outage'] = {'frame': session.frame, 'seconds': args.outage}
                say(f'模拟断网 {args.outage} 秒（frame {session.frame}）')
            if args.kill_at and session.frame >= args.kill_at:
                say(f'模拟崩溃：第 {session.frame} 帧直接退出')
                os._exit(3)
            if tamper is not None:
                tamper.apply()
            if touch is not None:
                touch.step(session.frame + 1)
            t0 = time.perf_counter()
            session.tick()
            tick_times.append(time.perf_counter() - t0)
            match.poll()
            if game.hub is not None:
                game.hub.service()
                for item in game.room_services:
                    item()
            ticks += 1
            for f in [f for f in session.checksums if f <= session.confirmed and f not in history]:
                history[f] = session.checksums[f]
            if session.desync is not None or match.peer_desync is not None:
                end = 'desync'
            elif session.finished_frame is not None and session.confirmed >= session.finished_frame + 30:
                end = 'finished'
            elif args.frames and session.frame >= args.frames:
                end = 'frame_limit'
            elif link.state == 'disconnected':
                end = 'disconnected'
            elif link.state == 'closed' or match.state in ('left', 'disconnected'):
                end = 'peer_left'
            elif ticks > 30 * 60 * 15:
                end = 'stuck'
            if ticks % 300 == 0:
                say(f"  frame {session.frame}  confirmed {session.confirmed}  rollbacks {session.stats['rollbacks']}"
                    f"  rtt {link.status()['srtt_ms']} ms  link {link.state}")
            if end is None:
                pacer.wait()
    finally:
        pacer.close()
    for f in [f for f in session.checksums if f <= session.confirmed]:
        history[f] = session.checksums[f]
    record.update(end=end, loop_seconds=round(time.perf_counter() - loop_started, 2), ticks=ticks, memory_after=memory_mb(),
                  guest_heap_after=guest_heap(p),
                  tick_ms=percentiles(tick_times), status=session.status(), link=link.status(),
                  checksums={str(f): list(v) for f, v in sorted(history.items())})
    if tamper is not None:
        record['tamper'] = tamper.status()
    if touch is not None:
        record['touch_test'] = touch.status()
    if end == 'desync':
        record['desync_report'] = exchange_desync(game, link, match, session)
    record['replay'] = save_replay(game, session, m, end, args, names)
    if game.hub is not None:
        game.hub.end_round({'end': end, 'finished_frame': session.finished_frame})
        record['spectators'] = game.hub.status()['spectators']
    session.end()
    if end != 'finished':
        lab.finish('netplay_' + end)
    if link.state in ('connected', 'interrupted') and match.state == 'battle':
        match.send_result({'confirmed': session.confirmed, 'finished_frame': session.finished_frame, 'reason': end,
                           'checksums': record['checksums']})
        game.until(lambda: match.state != 'battle' or link.state not in ('connected', 'interrupted'), 60)
    record['outcome'] = match.outcome
    record['match_state'] = match.state
    record['prep_returned'] = back_to_prep(game)
    return record


def exchange_desync(game, link, match, session, frame0=False):
    """分歧（N5）：向对方发送分歧通知与本方数据，等待对方数据（最多 15 秒，只处理网络），生成并保存分歧报告。"""
    import netplay_desync as nd
    if frame0:
        notice = {'kind': 'frame0', 'frame': 0, 'by': 'local'}
    else:
        notice = session.desync_notice(match.peer_desync)
    payload = session.desync_payload(notice, match.peer_desync)
    match.send_desync(notice, payload)
    game.until(lambda: match.peer_desync_data is not None or link.state not in ('connected', 'interrupted'), 15, frames=False)
    notes = [{'zh': d.get('zh'), 'en': d.get('en')} for d in match.differences or []] if frame0 else None
    report = nd.safe_report(payload, match.peer_desync_data, session.local_side, match.round, notes=notes)
    path = nd.save(report, game.out)
    say('分歧报告 Desync report：' + str(path))
    for line in report['text']['zh']:
        say('  ' + line)
    return {'path': str(path), 'kind': report['kind'], 'frame': report['frame'], 'peer_data': report['peer_data'],
            'notice': notice, 'peer_notice': match.peer_desync,
            'regions': [f"{r['kind']}:{r['zh']}" for r in report['regions']], 'table_rows': report['table_rows'],
            'flags': report.get('flags', []), 'inputs': report['inputs'], 'text': report['text']}


class Tamper:
    """测试（N5）：模拟修改过的客户端。种类@帧，自该帧起每帧施加（锁定数值）：
    ap 本方 AP 锁定为 5000；base-hp 本方据点生命（整数）锁定为 99999；row 本方编队第 1 格单位的数据行（Lv1 生命锚点）加 1000；
    withhold 不再发送校验值；echo 把收到的对方校验值原样发回（冒充本方的校验值）。"""

    def __init__(self, spec, game, session, link, m):
        self.kind, _, frame = spec.partition('@')
        self.frame = int(frame or 600)
        self.game, self.session, self.link, self.m = game, session, link, m
        self.started = None
        self.applied = 0
        self.row = None
        if self.kind not in ('ap', 'base-hp', 'row', 'withhold', 'echo'):
            raise ValueError('未知的篡改种类: ' + self.kind)

    def begin(self):
        p, session, link = self.game.p, self.session, self.link
        self.started = session.frame
        say(f'测试：模拟修改过的客户端 {self.kind}（frame {session.frame}）')
        if self.kind == 'withhold':
            link.send_checksum_tags = lambda entries: None
            link.send_checksum = lambda frame, value: None
        elif self.kind == 'echo':
            seen = {}
            receive = session.receive_checksum

            def capture(frame, value):
                seen[frame] = value
                receive(frame, value)
            session.receive_checksum = capture
            send = link.send_checksum_tags
            link.send_checksum_tags = lambda entries: send([(f, seen[f]) for f, _ in entries if f in seen])
        elif self.kind == 'row':
            deck = self.m['p1_deck'] if session.local_side == 0 else self.m['p2_deck']
            uid = p.lab.resolve_deck(deck)[0][0]
            rows, _ = session.table
            address = rows + uid * 0x390 + 0x0c
            self.row = (uid, address, (p.word(address) + 1000) & 0xffffffff)

    def apply(self):
        if self.session.frame < self.frame:
            return
        if self.started is None:
            self.begin()
        p, session = self.game.p, self.session
        if self.kind == 'ap':                                 # 控制器 +1028 为 AP（单精度浮点）
            p.write(session.controllers[session.local_side] + 1028, struct.pack('<f', 5000.0))
        elif self.kind == 'base-hp':                          # 据点生命（+776，整数）
            manager = p.call('_ZN19BattleObjectManager11getInstanceEv')
            base = p.call('_ZN19BattleObjectManager13getKyotenUnitE12BattleTeamID18BattleTeamMemberID', manager,
                          session.local_side, 0)
            p.put(base + 776, 99999)
        elif self.kind == 'row':
            p.put(self.row[1], self.row[2])
        self.applied += 1

    def status(self):
        return {'kind': self.kind, 'frame': self.frame, 'started': self.started, 'applied': self.applied,
                'row_unit': self.row[0] if self.row else None}


def judge(record, args):
    outcome = record.get('outcome') or {}
    if args.expect_end == 'disconnected':
        return record.get('end') in ('disconnected', 'peer_left') and record.get('prep_returned')
    if args.expect_end in ('desync', 'frame0'):
        report = record.get('desync_report') or {}
        if args.expect_end == 'desync':
            ended = record.get('end') == 'desync'
        else:
            ended = record.get('end') == 'not_started' and 'frame0_mismatch' in str(record.get('match_reason'))
        found = ' '.join([str(report.get('kind'))] + list(report.get('regions') or []) + list(report.get('flags') or [])
                         + (['table_rows'] if report.get('table_rows') else []))
        region_ok = not args.expect_region or args.expect_region in found
        return bool(ended and report.get('peer_data') and region_ok and record.get('prep_returned'))
    if record.get('end') not in ('finished', 'frame_limit') or not outcome:
        return False
    if outcome.get('mismatched') or not outcome.get('common_checksums'):
        return False
    if record['end'] == 'finished' and outcome.get('local_finished') != outcome.get('peer_finished'):
        return False
    return bool(record.get('prep_returned'))


def play(game, link, role, args, manifest, report):
    import netplay_match as nm
    p = game.p
    known = {u['key'] for u in p.community.units if not u.get('internal_only')}
    if args.pool:
        pool = [int(s) for s in args.pool.split(',')]
    elif args.regular:
        pool = json.loads((ROOT / 'netplay_pool.json').read_text(encoding='utf-8'))['stages']
    else:
        pool = POOL
    development = None
    if args.regular:
        import netplay_profile
        development = netplay_profile.development(p)
        report['development'] = development
    match = nm.Match(link, role, manifest, name=args.name, delay=args.delay, pool=pool,
                     version=report.get('game_version', ''), known_keys=known,
                     profile={'name': args.name} if args.regular else None, mode='regular' if args.regular else None)
    match.start()
    if role == 'host' and args.spectators > 0 and game.hub is None:
        from netplay_spectate import SpectatorHub
        game.hub = SpectatorHub(link.endpoint, manifest, args.name, report.get('game_version', ''), args.spectators,
                                args.disconnect_after)
    game.services = [match.poll] + ([game.hub.service] if game.hub else []) + list(game.room_services)
    report['rounds'] = []
    if not game.until(lambda: match.state not in ('hello', 'comparing'), 120):
        report['match'] = match.status()
        return False
    if match.state != 'decks':
        report['match'] = match.status()
        say('拒绝匹配 Rejected：' + str(match.reason))
        if match.differences:
            import content_manifest
            say(content_manifest.report(match.differences, 'zh'))
        return False
    ok = True
    for number in range(1, args.rounds + 1):
        game.versus_prep()
        swap = number % 2 == 0
        if development is not None:
            match.lock_deck(development['deck'], development['status'])
        else:
            deck = (DECK_1 if (role == 'host') != swap else DECK_2)
            match.lock_deck(deck)
        if not game.until(lambda: match.state != 'decks', 120) or match.state != 'locked':
            report['match'] = match.status()
            return False
        m = dict(match.match)
        if args.force_seed is not None:
            m['seed'] = args.force_seed
        if args.force_stage is not None:
            m['stage'] = args.force_stage
        say(f"第 {number} 轮 Round {number}：stage {m['stage']}  seed {m['seed']}  delay {m['delay']}  "
            f"本方 {'P1' if m['side'] == 0 else 'P2'}")
        record = battle(game, link, match, m, args)
        record['passed'] = judge(record, args)
        report['rounds'].append(record)
        outcome = record.get('outcome') or {}
        say(f"  结束 end={record['end']}  比较 compared={outcome.get('common_checksums')}  "
            f"不一致 mismatched={len(outcome.get('mismatched') or [])}  {'通过 PASS' if record['passed'] else '未通过 FAIL'}")
        ok = ok and record['passed']
        if record['end'] not in ('finished', 'frame_limit') or match.state != 'result':
            break
        if number < args.rounds:
            match.request_rematch()
            if not game.until(lambda: match.state != 'result', 120) or match.state != 'decks':
                report['match'] = match.status()
                return False
    if game.hub is not None:
        game.hub.close('done')
        report['spectators'] = game.hub.status()
    if match.state == 'result':
        match.leave('done')
        game.until(lambda: match.state != 'leaving', 10)
    report['match'] = match.status()
    expected = 1 if args.expect_end in ('disconnected', 'desync', 'frame0') else args.rounds
    return ok and len(report['rounds']) == expected


def spectate(game, link, args, manifest, report):
    """观战（N5.5b）：发送 hello，按房主转发的输入重算每一轮并以房主的周期校验值核对。--rounds 为观看的轮数。"""
    import content_manifest
    from netplay_spectate import SpectatorClient
    client = SpectatorClient(link, manifest, args.name, report.get('game_version', ''))
    game.services = [client.poll]
    game.until(lambda: client.state != 'hello', 20, frames=False)
    info = report['spectate'] = {'state': client.state, 'reason': client.reason, 'rounds': []}
    if client.state == 'rejected':
        info['differences'] = client.differences
        say('无法观战 Rejected：' + str(client.reason))
        if client.differences:
            say(content_manifest.report(client.differences, 'zh'))
        return args.expect_end == 'rejected'
    if client.state != 'watching':
        return False
    say(f"观战中 Watching：{(client.host or {}).get('name')}")
    seen = set()
    while len(info['rounds']) < args.rounds:
        if not game.until(lambda: (client.current is not None and client.current not in seen) or client.state != 'watching',
                          args.wait):
            break
        if client.current is None or client.current in seen:
            break
        seen.add(client.current)
        record = watch_round(game, client, client.rounds[client.current], args)
        info['rounds'].append(record)
        say(f"  观战第 {record['round']} 轮：结束 {record['end']}  校验 {record['verified']}/{record['recorded']}"
            f"  开始时已有 {record['joined_frames']} 帧  追赶 {record['catchup_frames']} 帧  {'通过 PASS' if record['passed'] else '未通过 FAIL'}")
    info.update(state=client.state, reason=client.reason)
    client.leave()
    return len(info['rounds']) == args.rounds and all(r['passed'] for r in info['rounds'])


def watch_round(game, client, entry, args):
    from frame_pacer import FramePacer
    from netplay_spectate import SpectateBattle
    p, lab = game.p, game.p.lab
    game.versus_prep()
    battle = SpectateBattle(p, entry)
    battle.prepare(battle.replay_config())
    game.wait(battle.ready, 2400, 'battle_start')
    setup = entry['info'].get('setup') or {}
    if setup.get('base_hp'):
        set_base_hp(p, setup['base_hp'])
    battle.begin()
    joined = len(entry['inputs'])
    pacer = FramePacer(30)
    ticks, started, first_shown, end = 0, time.perf_counter(), None, None
    lags = []
    try:
        while end is None:
            client.poll()
            if battle.tick() and first_shown is None:
                first_shown = time.perf_counter() - started
            ticks += 1
            if battle.started:
                lags.append(battle.total - battle.frame)
            if battle.ended():
                end = 'finished'
            elif client.state != 'watching' and battle.frame >= battle.total:
                end = 'host_' + str(client.state)
            elif ticks > 30 * 60 * 20:
                end = 'stuck'
            if ticks % 300 == 0:
                say(f"  spectate frame {battle.frame}/{battle.total}  verified {len(battle.verified_frames)}")
            if end is None:
                pacer.wait()
    finally:
        pacer.close()
    recorded = {f for f in battle.recorded if f <= battle.frame}
    steady = lags[len(lags) // 2:] if lags else []
    record = {'round': entry['info']['round'], 'end': end, 'frames': battle.frame, 'verified': len(battle.verified_frames),
              'recorded': len(recorded), 'mismatch': battle.mismatch, 'joined_frames': joined,
              'catchup_frames': battle.stats['catchup_frames'], 'stalls': battle.stats['spectate_stalls'],
              'max_lag': battle.stats['max_lag'], 'median_lag_late': sorted(steady)[len(steady) // 2] if steady else None,
              'first_frame_seconds': round(first_shown, 2) if first_shown is not None else None,
              'seconds': round(time.perf_counter() - started, 1), 'host_end': entry.get('end')}
    battle.end()
    lab.finish('spectate')
    record['prep_returned'] = back_to_prep(game)
    record['passed'] = (end == 'finished' and battle.mismatch is None and recorded <= battle.verified_frames
                        and bool(recorded) and record['prep_returned'])
    return record


def reference(game, args, report):
    """单机参照：同一设定由一个进程模拟双方（不回滚、不联网），输出每 30 帧校验值。"""
    import netplay_session as ns
    p = game.p
    game.versus_prep()
    decks = (DECK_2, DECK_1) if args.swap_decks else (DECK_1, DECK_2)
    seed = args.force_seed if args.force_seed is not None else REFERENCE_SEED
    stage = args.force_stage if args.force_stage is not None else REFERENCE_STAGE
    session = ns.NetplayBattle(p, 0, seed, delay=2, interval=30)
    session.local_input = script
    session.prepare(session.match_config(stage, *decks))
    game.wait(session.ready, 2400, 'battle_start')
    if args.base_hp:
        set_base_hp(p, args.base_hp)
    checksum0 = session.begin()
    history = {0: checksum0}
    while True:
        session.tick()
        for f in [f for f in session.checksums if f <= session.confirmed and f not in history]:
            history[f] = session.checksums[f]
        if session.finished_frame is not None and session.confirmed >= session.finished_frame + 30:
            break
        if args.frames and session.frame >= args.frames:
            break
    match = {'round': 1, 'seed': seed, 'stage': stage, 'p1_deck': decks[0], 'p2_deck': decks[1], 'delay': 2}
    replay = save_replay(game, session, match, 'finished' if session.finished_frame is not None else 'frame_limit', args,
                         ['reference P1', 'reference P2'], kind='reference')
    session.end()
    report['rounds'] = [{'match': {'seed': seed, 'stage': stage, 'p1_deck': decks[0], 'p2_deck': decks[1]},
                         'end': 'finished' if session.finished_frame is not None else 'frame_limit',
                         'finished_frame': session.finished_frame, 'frame0': {'checksum': list(checksum0)},
                         'checksums': {str(f): list(v) for f, v in sorted(history.items())}, 'replay': replay}]
    return True


def save_replay(game, session, m, end, args, names, kind='netplay'):
    """本轮回放（N5.5）：保存到 --replay-dir 或结果目录 replays\\。返回摘要（失败时记录错误，不影响验收结果）。"""
    if args.no_replay or not session.input_log:
        return None
    try:
        import netplay_replay as nr
        if game.manifest is None:
            import content_manifest
            game.manifest = content_manifest.build(game.p)
        replay = nr.build(session, kind, game.manifest, m, names=names, end=end,
                          setup={'base_hp': args.base_hp} if args.base_hp else None, version=game.report.get('game_version', ''))
        path = nr.save(replay, Path(args.replay_dir) if args.replay_dir else game.out / 'replays')
        return dict(nr.summary(replay), path=str(path), bytes=path.stat().st_size, checksums=len(replay['checksums']),
                    result=replay['result'])
    except Exception:
        return {'error': traceback.format_exc()[-800:]}


def replay_command(game, args, report):
    """回放校验（N5.5）：比较内容清单（不同即拒绝并列出差异），按记录的输入重算并逐点比较周期校验值；--seek-test 另测试暂停、倍速与跳转。"""
    import content_manifest
    import netplay_desync as nd
    import netplay_replay as nr
    import netplay_session as ns
    p = game.p
    path = Path(args.files[0]) if args.files else None
    if path is None or not path.is_file():
        say('请指定回放文件 Specify a replay file')
        return False
    replay = nr.load(path)
    info = report['replay'] = dict(nr.summary(replay), path=str(path))
    manifest = content_manifest.build(p)
    differences = nr.check_content(replay, manifest)
    if differences:
        info.update(state='rejected', differences=differences)
        say('回放与本机内容不同，拒绝播放 Replay rejected: content differs')
        say(content_manifest.report(differences, 'zh'))
        return args.expect_end == 'rejected'
    say(f"回放 Replay：stage {info['stage']}  {info['frames']} 帧  校验点 {len(replay['checksums'])}  {info['names']}")
    game.versus_prep()
    battle = nr.ReplayBattle(p, replay, journal=args.seek_test)
    battle.prepare(battle.replay_config())
    game.wait(battle.ready, 2400, 'battle_start')
    setup = replay.get('setup') or {}
    if setup.get('base_hp'):
        set_base_hp(p, setup['base_hp'])
    battle.begin()
    started = time.perf_counter()
    steps = run_seek_test(battle, ns) if args.seek_test else None
    if not args.seek_test:
        battle.verify(present=args.present)
    seconds = time.perf_counter() - started
    recorded = set(battle.recorded)
    finished_ok = battle.finished_frame == (replay.get('result') or {}).get('finished_frame')
    info.update(state='played', verified_points=len(battle.verified_frames), recorded_points=len(recorded),
                missing_points=sorted(recorded - battle.verified_frames)[:10], frames=battle.frame,
                finished_frame=battle.finished_frame, finished_matches=finished_ok, seconds=round(seconds, 2),
                ms_per_frame=round(seconds * 1000 / max(1, battle.stats['frames']), 3), mismatch=battle.mismatch,
                steps=steps, status=battle.status())
    if battle.mismatch is not None:
        info['mismatch_report'] = str(nd.save(battle.mismatch, game.out))
        for line in battle.mismatch['text']['zh']:
            say('  ' + line)
    battle.end()
    p.lab.finish('replay')
    info['prep_returned'] = back_to_prep(game)
    ok = battle.mismatch is None and recorded <= battle.verified_frames and finished_ok and info['prep_returned']
    if steps is not None:
        ok = ok and all(step.get('ok', True) for step in steps)
    say(f"  校验点 {len(battle.verified_frames)}/{len(recorded)}  结束帧 {battle.finished_frame}  {round(seconds, 1)} 秒"
        f"  {'一致 PASS' if ok else '不一致 FAIL'}")
    return ok if args.expect_end != 'rejected' else False


def run_seek_test(battle, ns):
    """暂停（只渲染帧不改变状态）、前后跳转、倍速与慢速。各步骤记录帧号、耗时与是否发现不一致。"""
    p, lab = battle.p, battle.lab
    total = battle.total
    steps = []

    def state():
        return ns.capture_state(p, lab, battle.controllers, True, battle.table)[0]

    def step(name, action, **extra):
        t0 = time.perf_counter()
        action()
        steps.append(dict(extra, step=name, frame=battle.frame, ms=round((time.perf_counter() - t0) * 1000, 1),
                          mismatch=battle.mismatch is not None))
        return steps[-1]

    step('play', lambda: [battle.advance(True) for _ in range(min(total, 1200) - battle.frame)])
    before = state()
    entry = step('pause_10_frames', lambda: [battle.render_paused() for _ in range(10)])
    entry['ok'] = state() == before and battle.frame == min(total, 1200)
    for target in (450, 1500, 2400, 1000):
        step(f'seek_{target}', lambda target=target: battle.seek(min(total, target)))
        steps[-1]['ok'] = battle.frame == min(total, target)
    battle.speed = 4.0
    step('speed_4x_60_ticks', lambda: [battle.tick() for _ in range(60)])
    battle.speed = 0.5
    before_slow = battle.frame
    step('speed_half_40_ticks', lambda: [battle.tick() for _ in range(40)])
    steps[-1]['ok'] = battle.finished() or battle.frame - before_slow == 20
    battle.speed = 1.0
    step('play_to_end', lambda: [battle.tick() for _ in range(total - battle.frame)])
    steps[-1]['ok'] = battle.finished()
    say('  ' + '  '.join(f"{s['step']}@{s['frame']}:{s['ms']}ms" for s in steps))
    return steps


def compare(paths):
    a, b = [json.loads(Path(x).read_text(encoding='utf-8')) for x in paths]
    rows, ok = [], True
    for index, (ra, rb) in enumerate(zip(a.get('rounds', []), b.get('rounds', []))):
        ca, cb = ra.get('checksums', {}), rb.get('checksums', {})
        common = sorted(set(ca) & set(cb), key=int)
        mismatched = [f for f in common if ca[f] != cb[f]]
        same = bool(common) and not mismatched
        ok = ok and same
        rows.append({'round': index + 1, 'compared': len(common), 'mismatched': mismatched[:10],
                     'first_mismatch': mismatched[0] if mismatched else None})
    print(json.dumps({'a': {'cpu': a.get('environment', {}).get('cpu'), 'command': a.get('command')},
                      'b': {'cpu': b.get('environment', {}).get('cpu'), 'command': b.get('command')},
                      'rounds': rows, 'passed': ok and bool(rows)}, ensure_ascii=False, indent=2))
    say('通过 PASS' if ok and rows else '未通过 FAIL')
    return 0 if ok and rows else 1


# ---------- 本机双客户端（local_pair.bat） ----------
LOCAL_CASES = {
    '1': ('标准测试：局域网发现（本机回环），2 轮打到分出胜负（第 2 轮为再战）', 'lan', [], [], 'finished'),
    '2': ('较差网络：双方模拟单向延迟 100 ms、抖动 20 ms、丢包 2%，2 轮', 'lan',
          ['--latency', '100', '--jitter', '20', '--loss', '0.02'], [], 'finished'),
    '3': ('断网恢复：加入方第 600 帧起模拟断网 4 秒（应自动恢复），2 轮', 'lan', [], ['--outage-at', '600', '--outage', '4'],
          'finished'),
    '4': ('断线结束：加入方第 600 帧起模拟断网 20 秒（双方应在约 10 秒后判定断线并体面结束）', 'lan',
          ['--expect-end', 'disconnected', '--rounds', '1'], ['--outage-at', '600', '--outage', '20'], 'disconnected'),
    '5': ('会合服务器 + 房间码：本机启动会合服务器，房主登记房间码，加入方凭房间码连接，2 轮', 'rdv', [], [], 'finished'),
    '6': ('经本机网卡地址（局域网广播与网卡 IP；首次会弹出 Windows 防火墙提示，请允许），2 轮', 'nic', [], [], 'finished'),
    '7': ('篡改检测：加入方第 600 帧起锁定本方 AP（模拟内存修改），双方应检出分歧、生成分歧报告并体面结束', 'lan',
          ['--expect-end', 'desync', '--rounds', '1'], ['--tamper', 'ap@600'], 'desync'),
    '8': ('观战：另启动 2 名观战者（1 名开战前加入，1 名约 25 秒后中途加入），房主转发输入，观战者重算并核对，1 轮', 'lan',
          ['--rounds', '1'], [], 'finished'),
    '9': ('常规联机（N6a）：双方以测试存档的当前编队与发展进度开战，经原生触点点击底栏与单位（单体绝招），'
          '模拟单向延迟 100 ms、抖动 20 ms、丢包 2%，2 轮', 'lan',
          ['--regular', '--touch-test', '--latency', '100', '--jitter', '20', '--loss', '0.02'], [], 'finished'),
}
LOCAL_SPECTATORS = {'8': [('观战者1', 0.0), ('观战者2', 25.0)]}      # 编号 → [(名称, 启动延迟秒)]


def local_pair(args):
    """在本机启动房主（必要时另启动会合服务器）与加入方两个独立进程，转发双方进度并汇总结果。
    两个进程各用独立的测试存档副本与结果目录。测试编号 0 依次运行 1–5、7、8 与 9（6 会弹出防火墙提示，需单独运行）。
    编号 8 另启动观战者进程（LOCAL_SPECTATORS）。"""
    import subprocess
    import threading
    sys.path.insert(0, str(ROOT))
    import netplay_net as nn
    case = args.files[0] if args.files else None
    if case is None:
        say('本机双客户端联机测试：在这台电脑上运行两个独立的游戏进程（房主与加入方）并互相连接；不读写玩家存档。')
        for key, item in LOCAL_CASES.items():
            say(f'  {key}. {item[0]}')
        say('  0. 依次运行 1–5、7、8 与 9（约 20 分钟）')
        try:
            import unicodedata
            raw = unicodedata.normalize('NFKC', input('请输入编号后按回车（直接回车为 1）：'))   # 全角数字按半角处理
            case = raw.replace(chr(0xFEFF), '').strip() or '1'      # 去掉管道输入可能带有的 BOM
        except EOFError:
            case = '1'
    cases = ['1', '2', '3', '4', '5', '7', '8', '9'] if case == '0' else [case]
    if any(c not in LOCAL_CASES for c in cases):
        say('没有这个编号：' + case)
        return 2
    base = Path(args.out) if args.out else ROOT / 'verification' / 'netplay_check' / f"{time.strftime('%Y%m%d_%H%M%S')}_local_pair"
    base.mkdir(parents=True, exist_ok=True)
    wrapper = os.environ.get('NETPLAY_CHECK_CHILD_PREFIX')      # 仅供开发验证：以包装脚本启动子进程
    script = str(Path(__file__).resolve())
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    summary = {'cases': {}, 'out': str(base)}

    def command(argv):
        return [sys.executable] + ([wrapper] if wrapper else []) + [script] + argv

    def pump(proc, label):
        for raw in proc.stdout:
            line = raw.decode('utf-8', errors='replace').rstrip()
            if line and not line.startswith('{"run"'):
                say(f'[{label}] {line}')

    for number in cases:
        title, mode, both, join_extra, expect = LOCAL_CASES[number]
        out = base / f'case{number}'
        outs = {'host': out / 'host', 'join': out / 'join'}
        say('')
        say(f'===== 测试 {number}：{title} =====')
        if mode == 'nic':
            ips = nn.local_ipv4()
            if not ips:
                say('本机没有可用的网卡地址，跳过测试 6。')
                summary['cases'][number] = {'title': title, 'passed': False, 'skipped': 'no_ipv4'}
                continue
            host = ['host', '--wait', '240']
            join = ['join', '--wait', '90'] + [x for ip in ips for x in ('--scan-target', f'{ip}:{nn.DISCOVERY_PORT}')]
            join += ['--scan-target', f'255.255.255.255:{nn.DISCOVERY_PORT}']
        elif mode == 'rdv':
            host = ['rdv-host', '--bind', '127.0.0.1', '--server', f'127.0.0.1:{nn.RENDEZVOUS_PORT}', '--wait', '240']
            join = ['rdv-join', '--bind', '127.0.0.1', '--server', f'127.0.0.1:{nn.RENDEZVOUS_PORT}', '--code-file',
                    str(outs['host'] / 'room_code.txt'), '--wait', '120']
        else:
            host = ['host', '--bind', '127.0.0.1', '--wait', '240']
            join = ['join', '--bind', '127.0.0.1', '--scan-target', f'127.0.0.1:{nn.DISCOVERY_PORT}', '--wait', '90']
        procs, threads = {}, []
        timers = []
        server = None
        if mode == 'rdv':
            server = subprocess.Popen([sys.executable, str(ROOT / 'rendezvous_server.py'), '--host', '127.0.0.1', '--port',
                                       str(nn.RENDEZVOUS_PORT), '--stats-every', '0'], cwd=str(ROOT), env=env,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            threads.append(threading.Thread(target=pump, args=(server, '服务器'), daemon=True))
            threads[-1].start()
        for role, label, argv in (('host', '房主', host), ('join', '加入方', join)):
            outs[role].mkdir(parents=True, exist_ok=True)
            full = argv + ['--name', f'{args.name}-{role}'] + both + (join_extra if role == 'join' else [])
            full += ['--out', str(outs[role])]
            procs[role] = subprocess.Popen(command(full), cwd=str(ROOT), env=env, stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT)
            threads.append(threading.Thread(target=pump, args=(procs[role], label), daemon=True))
            threads[-1].start()
        for index, (label, delay) in enumerate(LOCAL_SPECTATORS.get(number, []), start=1):
            role = f'spectator{index}'
            outs[role] = out / role
            outs[role].mkdir(parents=True, exist_ok=True)
            spectate_args = ['spectate', '--bind', '127.0.0.1', '--scan-target', f'127.0.0.1:{nn.DISCOVERY_PORT}', '--wait', '180',
                             '--name', f'{args.name}-{role}', '--out', str(outs[role])] + both

            def start(role=role, label=label, argv=spectate_args):
                procs[role] = subprocess.Popen(command(argv), cwd=str(ROOT), env=env, stdout=subprocess.PIPE,
                                               stderr=subprocess.STDOUT)
                thread = threading.Thread(target=pump, args=(procs[role], label), daemon=True)
                thread.start()
                threads.append(thread)
            if delay:
                timer = threading.Timer(delay, start)
                timer.start()
                timers.append(timer)
            else:
                start()
        started = time.time()
        first_exit = None
        for timer in timers:
            timer.join()
        while any(p.poll() is None for p in procs.values()):
            if first_exit is None and any(p.poll() is not None for p in procs.values()):
                first_exit = time.time()
            if (first_exit is not None and time.time() - first_exit > 90) or time.time() - started > 1800:
                for role, p in procs.items():
                    if p.poll() is None:
                        say(f'[{"房主" if role == "host" else "加入方"}] 对方已结束，等待超时，结束本进程')
                        p.terminate()
                break
            time.sleep(0.2)
        for p in procs.values():
            p.wait()
        if server is not None:
            server.terminate()
            server.wait()
        for thread in threads:
            thread.join(timeout=2)
        results = {}
        for role in [r for r in outs if r == 'host' or r == 'join' or r.startswith('spectator')]:
            path = outs[role] / 'result.json'
            results[role] = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        passed = all(r.get('passed') for r in results.values())
        rows = []
        for role, r in results.items():
            for index, record in enumerate((r.get('spectate') or {}).get('rounds') or []):
                rows.append({'role': role, 'round': index + 1, 'end': record.get('end'), 'passed': record.get('passed'),
                             'compared': record.get('verified'), 'mismatched': 0 if record.get('mismatch') is None else 1,
                             'rollbacks': None, 'tick_p99_ms': None, 'joined_frames': record.get('joined_frames')})
            for index, record in enumerate(r.get('rounds') or []):
                outcome = record.get('outcome') or {}
                rows.append({'role': role, 'round': index + 1, 'end': record.get('end'), 'passed': record.get('passed'),
                             'compared': outcome.get('common_checksums'), 'mismatched': len(outcome.get('mismatched') or []),
                             'rollbacks': (record.get('status') or {}).get('rollbacks'),
                             'tick_p99_ms': (record.get('tick_ms') or {}).get('p99')})
        failures = {k: r.get('connect_failure') or (r.get('match') or {}).get('reason') or (r.get('error') or '')[-300:] or None
                    for k, r in results.items()}
        summary['cases'][number] = {'title': title, 'passed': passed, 'expect_end': expect,
                                    'exit_codes': {k: p.returncode for k, p in procs.items()}, 'failure': failures,
                                    'rounds': rows, 'out': str(out)}
        say(f'----- 测试 {number} 结果：{"通过 PASS" if passed else "未通过 FAIL"} -----')
        for row in rows:
            compared = '—' if row['compared'] is None else f"{row['compared']} 点"
            who = {'host': '房主', 'join': '加入方'}.get(row['role'], row['role'])
            say(f"  {who} 第 {row['round']} 轮：结束 {row['end']}，比较 {compared}，"
                f"不一致 {row['mismatched']} 点，回滚 {row['rollbacks']} 次，帧耗时 p99 {row['tick_p99_ms']} ms，"
                f"{'通过' if row['passed'] else '未通过'}")
        if not passed:
            for role, failure in failures.items():
                if failure:
                    say(f"  {({'host': '房主', 'join': '加入方'}).get(role, role)}：{failure}")
    (base / 'local_pair.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    total = bool(summary['cases']) and all(c['passed'] for c in summary['cases'].values())
    say('')
    say('===== 汇总 =====')
    for number, item in summary['cases'].items():
        say(f"  测试 {number}：{'通过 PASS' if item['passed'] else '未通过 FAIL'}  {item['title']}")
    say(('全部通过 PASS' if total else '有未通过的测试 FAIL') + f'    结果目录：{base}')
    return 0 if total else 1


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors='replace')
    except (AttributeError, ValueError):
        pass
    args = parse_args(argv)
    if args.command == 'compare':
        return compare(args.files)
    if args.command == 'local-pair':
        return local_pair(args)
    if args.command == 'server':
        sys.path.insert(0, str(ROOT))
        import rendezvous_server
        sys.argv = [str(ROOT / 'rendezvous_server.py'), '--host', args.bind, '--port', str(args.port or 47632)]
        say(f'会合服务器运行中 Rendezvous server on {args.bind}:{args.port or 47632}（UDP）；Ctrl+C 结束')
        rendezvous_server.main()
        return 0
    out = Path(args.out) if args.out else ROOT / 'verification' / 'netplay_check' / f"{time.strftime('%Y%m%d_%H%M%S')}_{args.command}"
    out.mkdir(parents=True, exist_ok=True)
    sys.stdout = (out / 'console.log').open('w', encoding='utf-8', errors='replace', buffering=1)
    report = {'command': args.command, 'args': vars(args), 'out': str(out), 'started': time.strftime('%Y-%m-%d %H:%M:%S'),
              'environment': {'cpu': cpu_name(), 'platform': platform.platform(), 'python': platform.python_version(),
                              'host': socket.gethostname()}}
    game = None
    link = None
    passed = False
    try:
        game = bootstrap(args, out, report)
        import branding
        import content_manifest
        report['game_version'] = branding.load(ROOT)['display_version']
        say(f"MSD WINDOWS S1XLV {report['game_version']} 联机验收 {args.command}  core {report['core']}  CPU {report['environment']['cpu']}")
        game.to_menu()
        if args.warmup:
            game.warmup(args.warmup, args.warmup_stage)
            report['warmup'] = [args.warmup, args.warmup_stage]
        if args.command == 'reference':
            passed = reference(game, args, report)
        elif args.command == 'replay':
            passed = replay_command(game, args, report)
        else:
            started = time.perf_counter()
            manifest = content_manifest.build(game.p)
            game.manifest = manifest
            if args.save_manifest:
                (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
            if args.forge_manifest:                       # 测试：伪造清单（向对方报告指定文件中的清单，实际内容不变）
                manifest = json.loads(Path(args.forge_manifest).read_text(encoding='utf-8'))
                report['forged_manifest'] = args.forge_manifest
            digest = content_manifest.digest(manifest)
            game.reported_manifest = manifest                # 向对方与观战者报告的清单（--forge-manifest 时为伪造的清单）
            report['manifest'] = {'digest': digest, 'seconds': round(time.perf_counter() - started, 2),
                                  'mods': [(m['id'], m['version']) for m in manifest['mods']]}
            link, role = establish(args, game, report, digest)
            if link is None:
                report['connect_failure'] = role
                import netplay_net as nn
                say(nn.connect_failure_text(role, 'zh'))
                say(nn.connect_failure_text(role, 'en'))
            else:
                report['role'] = role
                say(f"已连接 Connected：{report.get('peer')}")
                if role == 'spectator':
                    passed = spectate(game, link, args, manifest, report)
                else:
                    passed = play(game, link, role, args, manifest, report)
                report['link'] = link.status()
    except Exception:
        report['error'] = traceback.format_exc()
        say(report['error'])
    finally:
        report['passed'] = bool(passed)
        report['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
        (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        if link is not None:
            try:
                link.close()
            except Exception:
                pass
        elif game is not None and game.hub is not None:     # 对手未加入：通知已连接的观战者房间关闭
            try:
                game.hub.close('room_closed')
            except Exception:
                pass
        for item in (game.room_cleanup if game is not None else []):
            try:
                item()
            except Exception:
                pass
        if game is not None:
            try:
                game.p.close()
            except Exception:
                pass
        if sys.stdout is not CONSOLE:
            sys.stdout.close()
            sys.stdout = CONSOLE
        say(('验收通过 PASS' if passed else '验收未通过 FAIL') + f'    结果 result：{out / "result.json"}')
        say(json.dumps({'run': str(out), 'passed': bool(passed)}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
