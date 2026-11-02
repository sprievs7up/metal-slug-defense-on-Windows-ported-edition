"""单位动作演示（U1b，开工说明 D40、D11、D14 与附录 A.6；2026-10-12 修订见附录 E.4）：复用原生动作浏览对象
（UnitActionViewer*），由宿主决定动作与镜头位置，在宿主界面之上绘制。

原生动作浏览占用全局 BattleObjectManager 与 BattleStage，只在没有战斗时使用（单位强化界面覆盖主菜单期间）；
关闭时必须调用 UnitActionViewerUnitClear（释放对象、舞台与音效资源，游戏类型恢复 0）。

坐标：原生对象按“世界坐标 − 镜头”绘制到原生画面（960 基准，左右各留 app+0x3c），画布坐标 = (原生 x + 留边) × 1.125。
BattleObjectManager::draw 的前两个参数为镜头（第三个参数传 1.0，与原生一致）。镜头使单位起点的脚点落在指定的画布位置，
GraphicsOpt::setClip 以原生坐标裁切到画框内。

推进：每帧调用原生 UnitActionViewerUpdate，并把 app+0xb8c1（原生“特殊攻击进行中”标记，非 0 时跳过自动演示循环）
置 1，只保留其中的逐单位处理：建造类单位（工兵、召唤箱等）走到原生 x=320 时预约状态 40 开始修筑，修筑完成后
UnitActionGetViweUnit 改为返回建成的对象；部分单位首帧放到原生起点；最后推进 BattleObjectManager。
选择动作时对演示单位预约状态 30（近距离）、40（远距离）、50（特殊）；建造、空降等变身类单位先离屏快进到变身完成
（屏蔽音效与语音请求）再预约。动作结束回到待机后等待一段时间再次演示：与原生自动演示循环相同，把演示对象放回起点
后再预约，不重新建立单位。切换动作时重新建立单位（重新建立约需 20–30 ms，其中多为原生对象池的分配与释放），
以下情形不重新建立：再次选择待机时继续演示；演示对象已在待机时，回到待机则放回起点，切到某个攻击则放回起点后预约，
但该单位建立后已演示过特殊攻击时重新建立（特殊攻击会改变单位之后的状态，例如马可在特殊攻击后保留的武器、变形或
自爆；近距离与远距离攻击之间的切换与原生自动演示循环的交替相同）。

修筑完成后的工兵（行动类 BattleAction_Kouhei，状态 141 等待、142 返回）：战斗中返回己方据点后移除；浏览模式
（BattleGameMaster+0x4828 为 5）中只走回原生 x=100 即停止，且不能移除（原生 UnitActionGetViweUnit 经它取得建成的
对象）。演示中工兵停止后由宿主按原速度继续向左移动，离开画框后移到远处；离屏快进与测量时直接移到远处，图像范围
不计返回过程。

缩放：BattleObjectManager::draw 的第三个参数不改变画面大小。原生顶点先经 OGLRender+0x90 的矩阵（原生坐标 × 1.125
到画布像素）再经 +0x10 的正交投影；绘制演示期间把 +0x90 改为以脚点为中心缩小，提交后恢复。缩小视口的做法会在原画面
范围之外被投影裁去，因此不采用。裁切仍由 setClip 的剪刀矩形限定在画框内。
每个单位的待机与每个所选动作的图像范围：在画面的一块区域内离屏运行（待机 NEUTRAL_FRAMES 帧，动作直到结束后再
ACTION_TAIL 帧），每 SAMPLE_EVERY 帧以 MEASURE_SCALE 把全部对象（含弹体、投下物与建成的对象）叠画到同一块区域，
最后读回一次求包围盒（动作另在首个取样后读回一次，取单位自身的范围）；随后由界面重画覆盖。逐个取样读回会使每个
取样等待 GPU 完成（实测每次 1.4–2.7 ms），因此只在结束时读回。动作的范围在水平方向只计单位前后 H_EXTRA 以内，
远距离弹体可以飞出画框（D14）。再按画框大小选择缩放（不超过 1，不小于 MIN_SCALE）。

战场数据：原生 UnitActionViewerUnitSetup 先经 UnitActionViewerInitialize 调用 BattleStage::release，舞台的场景信息
（+4）与场景图像对象（+0xc）为空，再由 initializeViewMode 设定平地（+0x14 起）。下列行动类读取这两项，在动作浏览中
读取空指针后原生停止：
- BattleAction_DragonNosuke（UnitID 93 巨龍乃介；落地碎片 EffectAction_Nosuke 取场景图像的地面条带绘制）与
  BattleAction_KyotenNeko（298 CAT BASE；特殊攻击的弹体读取据点位置）：建立后与原生主菜单相同地以
  GetMainMenuBGStageID 的场景调用 BattleStage::initialize，再写回动作浏览的平地字段（+0x14 至 +0x2b）；离开时原生
  UnitActionViewerUnitClear 释放舞台。
- BattleAction_Kaladgolg（358 CALADBOLG）与 BattleAction_MordenAttack（361）：update 读取据点位置，原生在
  UnitActionViewerUnitSetup 内部推进第一帧时即停止（宿主无法在其释放舞台与推进之间载入场景），不建立演示，画框留空。
按行动类判定，社区与模组单位沿用基准单位的行动类。

图像范围的保存（BoundsStore）：随游戏附带 unit_viewer_bounds.json（原版与本体单位预先测量的结果），其余单位（模组
单位、新增后尚未重新生成的本体单位）首次演示时测量，结果存于用户目录（MSD_UNIT_VIEWER_CACHE 可改变路径，设为空值时
不保存）。记录以单位稳定键为键，社区单位另带单位定义的签名，签名不同时重新测量。
"""
import ctypes as C
import json
import os
import struct
from pathlib import Path

from content_digest import blake2

STATE_NEUTRAL = 10
ACTION_STATES = {'neutral': STATE_NEUTRAL, 'near': 30, 'normal': 40, 'special': 50}
SHARED_EFFECT_ID = 402            # 原生共用效果（0xffNN）的图片描述符，按 UnitID 传给 BattleSpriteFactory::setupResource
CANVAS = 1.125                    # 原生 960 基准到 1280×720 画布
SOUND_BLOCK = 3                   # Sound_RequestPlaySE（位 0）与 Sound_RequestPlayVO（位 1）的请求屏蔽
VIEWER_FLAGS = 0xb8c0             # app+0xb8c0 原生浏览的触点请求、+0xb8c1 特殊攻击进行中（非 0 时跳过自动演示循环）
REPEAT_WAIT = 45                  # 动作结束回到待机后再次演示前的等待帧数
PRELUDE_LIMIT = 900               # 变身类单位快进到变身完成的帧数上限
SETTLE_LIMIT = 120                # 变身后等待建成对象进入待机的帧数上限
NEUTRAL_FRAMES = 240              # 待机测量的帧数（8 秒）：覆盖建造、空降、升起等入场过程
ACTION_LIMIT = 600                # 动作测量的帧数上限
ACTION_TAIL = 45                  # 动作结束后继续测量的帧数（弹体、投下物与落地爆炸）
SAMPLE_EVERY = 4
UNIT_STATE = 0x84                 # BattleObject 状态（原生 UnitActionViewerUpdate 以 10 表示待机）
UNIT_X, UNIT_Y = 0x8c, 0x90       # 位置（+0x94 / +0x98 为上一帧位置，原生复位时一并写入）
MEASURE_REGION = (360, 150, 560, 360)  # 测量用的画布区域（测量后由界面重画覆盖）
MEASURE_SCALE = 0.25              # 测量时的缩放：区域可容纳缩放 1 时 2240×1440 的图像
KEY = (255, 0, 255)               # 测量区域的底色（与之不同的像素视为单位图像）
H_EXTRA = 300                     # 动作范围在单位前后可计入的水平距离（画布像素）
FIT_MARGIN = 12                   # 图像与画框边缘的最小距离（画布像素）
MIN_SCALE = 0.3
DEFAULT_BOUNDS = (-90.0, -200.0, 90.0, 10.0)   # 测量失败时的图像范围（相对起点脚点，缩放 1 的画布像素）
ACTION_TABLE = 0x109373f4         # 各 UnitID 行动类对象表的指针
KOUHEI_VTABLE = 0x10929950        # BattleAction_Kouhei（工兵类修筑单位）
STAGE_VTABLES = {0x1092a970: 'BattleAction_DragonNosuke', 0x1092dd10: 'BattleAction_KyotenNeko'}
UNSUPPORTED_VTABLES = {0x1092d590: 'BattleAction_Kaladgolg', 0x1092d5f0: 'BattleAction_MordenAttack'}
VIEW_GROUND = (0x14, 0x18)        # BattleStage 中动作浏览平地的字段（偏移、长度）
WORKER_WAIT, WORKER_RETURN = 0x8d, 0x8e   # BattleAction_Kouhei 修筑完成后的等待、返回状态
WORKER_SPEED = 8.0                # 工兵返回的移动速度（原生单位 / 帧，实测；未取得实测值时使用）
WORKER_HALF = 60.0                # 判断工兵离开画框时计入的半宽（原生单位）
WORKER_AWAY = 20000.0             # 工兵移到的远处（起点左侧，原生单位）
BOUNDS_VERSION = 1                # 图像范围数据的版本（测量方法改变时递增，旧数据随之不用）
SHIPPED_BOUNDS = Path(__file__).with_name('unit_viewer_bounds.json')


def f2i(value):
    return struct.unpack('<I', struct.pack('<f', float(value)))[0]


def fword(p, address):
    return struct.unpack('<f', p.read(address, 4))[0]


def cache_path():
    value = os.environ.get('MSD_UNIT_VIEWER_CACHE')
    if value is not None:
        return Path(value) if value else None
    base = os.environ.get('LOCALAPPDATA')
    return Path(base) / 'MSD_WINDOWS_S1XLV' / 'unit_viewer_bounds.json' if base else None


class BoundsStore:
    """图像范围：随游戏附带的数据与用户目录中的测量结果（见模块说明）。units[键] = {'sig', 'transforms', 'bounds': {动作: [左, 上, 右, 下]}}。"""
    def __init__(self, shipped=SHIPPED_BOUNDS, path=None):
        self.path = cache_path() if path is None else path
        self.shipped = self.read(shipped)
        self.user = self.read(self.path)

    @staticmethod
    def read(path):
        if path is None:
            return {}
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict) or data.get('version') != BOUNDS_VERSION or not isinstance(data.get('units'), dict):
            return {}
        return data['units']

    def records(self, key, signature):
        for table in (self.user, self.shipped):
            record = table.get(key)
            if isinstance(record, dict) and record.get('sig', '') == signature:
                yield record

    def bounds(self, key, signature, action):
        for record in self.records(key, signature):
            value = record.get('bounds', {}).get(action)
            if isinstance(value, list) and len(value) == 4:
                return tuple(float(v) for v in value)
        return None

    def transforms(self, key, signature):
        for record in self.records(key, signature):
            if isinstance(record.get('transforms'), bool):
                return record['transforms']
        return None

    def put(self, key, signature, action, bounds, transforms=None):
        record = self.user.get(key)
        if not isinstance(record, dict) or record.get('sig', '') != signature:
            record = self.user[key] = {'sig': signature, 'bounds': {}}
        record['bounds'][action] = [round(v, 1) for v in bounds]
        if transforms is not None:
            record['transforms'] = bool(transforms)

    def save(self):
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.json.tmp')
            temporary.write_text(json.dumps({'version': BOUNDS_VERSION, 'units': self.user}), encoding='utf-8')
            os.replace(temporary, self.path)
        except OSError:
            pass


class UnitViewer:
    def __init__(self, p):
        self.p = p
        self.uid = None
        self.action = 'neutral'
        self.pending = False            # 所选动作尚未开始（在绘制阶段测量并开始，见 prepare）
        self.cycle = 0                  # 本轮动作的帧数
        self.idle = 0                   # 回到待机后的帧数
        self.started = False            # 本轮已离开待机
        self.start_x, self.start_y = 300.0, 400.0
        self.bounds = {}                # (UnitID, 动作) → 图像范围 (左, 上, 右, 下)，相对起点脚点、缩放 1 的画布像素
        self.transforms = {}            # UnitID → 待机期间是否变身（建造、空降等）
        self.kouhei = {}                # UnitID → 行动类对象的 vtable
        self.store = BoundsStore()
        self.key = None                 # 演示单位的稳定键（图像范围按此保存）
        self.signatures = {}
        self.fresh = False              # 单位刚建立、尚未推进
        self.quick = False              # 开始所选动作时不重新建立（演示对象已在待机）
        self.specialed = False          # 建立后已演示过特殊攻击
        self.view = None                # 上一次绘制的 (缩放, 起点脚点, 画框)
        self.worker_x = None            # 工兵上一帧的位置与移动量
        self.worker_step = WORKER_SPEED

    def app(self):
        return self.p.app_instance()

    def active(self):
        return self.uid is not None

    def unit(self):
        return self.p.call('_ZN7AppMain21UnitActionGetViweUnitEv', self.app())

    def kyoten(self):
        manager = self.p.call('_ZN19BattleObjectManager11getInstanceEv')
        return self.p.call('_ZN19BattleObjectManager13getKyotenUnitE12BattleTeamID18BattleTeamMemberID', manager, 0, 0)

    def transformed(self):
        """原生 UnitActionGetViweUnit 已改为返回建成或变身后的对象。"""
        return self.unit() != self.kyoten()

    def action_class(self, uid):
        """UnitID 的行动类对象的 vtable（0 表示没有）。"""
        if uid not in self.kouhei:
            table = self.p.word(ACTION_TABLE)
            action = self.p.word(table + uid * 4) if table else 0
            self.kouhei[uid] = self.p.word(action) if action else 0
        return self.kouhei[uid]

    def supported(self, uid):
        """原生动作浏览能否演示该单位（见模块说明“战场数据”）。"""
        return self.action_class(uid) not in UNSUPPORTED_VTABLES

    def load_stage(self):
        """为读取战场数据的单位载入场景（见模块说明“战场数据”）。"""
        p, app = self.p, self.app()
        info = p.call('_ZN10BattleInfo11getInstanceEv')
        mission = p.call('_ZN10BattleInfo14getMissionInfoEi', info, p.call('_ZN7AppMain20GetMainMenuBGStageIDEv', app))
        if not mission:
            return
        stage = p.call('_ZN11BattleStage11getInstanceEv')
        offset, length = VIEW_GROUND
        ground = p.read(stage + offset, length)
        p.call('_ZN11BattleStage10initializeEi', stage, p.word(mission + 4))
        p.write(stage + offset, ground)

    def worker(self):
        """修筑完成后等待或返回中的工兵（见模块说明）；其他情况返回 0。"""
        if self.action_class(self.uid) != KOUHEI_VTABLE:
            return 0
        k = self.kyoten()
        if not k or k == self.unit() or self.p.word(k + UNIT_STATE) not in (WORKER_WAIT, WORKER_RETURN):
            return 0
        return k

    def place_worker(self, k, x):
        y = fword(self.p, k + UNIT_Y)
        self.p.write(k + UNIT_X, struct.pack('<ff', x, y))
        self.p.write(k + UNIT_X + 8, struct.pack('<ff', x, y))

    def send_worker_away(self):
        """离屏快进与测量：工兵直接移到远处。"""
        k = self.worker()
        if k and fword(self.p, k + UNIT_X) > self.start_x - WORKER_AWAY / 2:
            self.place_worker(k, self.start_x - WORKER_AWAY)

    def lead_worker_out(self):
        """演示：工兵返回途中停止（原生浏览模式止于 x=100）后按原速度继续向左，离开画框后移到远处。"""
        k = self.worker()
        if not k:
            self.worker_x = None
            return
        x = fword(self.p, k + UNIT_X)
        if x <= self.start_x - WORKER_AWAY / 2:
            return
        if self.view is None:
            self.place_worker(k, self.start_x - WORKER_AWAY)
            return
        scale, point, frame = self.view
        if point[0] + (x - self.start_x + WORKER_HALF) * CANVAS * scale < frame[0]:
            self.place_worker(k, self.start_x - WORKER_AWAY)
            return
        last, self.worker_x = self.worker_x, x
        if last is None or self.p.word(k + UNIT_STATE) != WORKER_RETURN:
            return
        if x < last:
            self.worker_step = last - x
        elif x == last:
            self.place_worker(k, x - self.worker_step)
            self.worker_x = x - self.worker_step

    def setup(self, uid):
        """建立演示单位（原生 UnitActionViewerUnitSetup：清除旧对象、浏览模式、按 UnitID 设定起点、载入音效）。"""
        p, app = self.p, self.app()
        p.call('_ZN7AppMain25UnitActionViewerUnitSetupE6UnitID', app, uid)
        self.preload_spawned(uid)
        if self.action_class(uid) in STAGE_VTABLES:
            self.load_stage()
        self.uid = uid
        self.start_x = float(p.word(app + 0xb8b0))
        self.start_y = float(p.word(app + 0xb8b4))
        self.cycle = self.idle = 0
        self.started = False
        self.worker_x, self.worker_step = None, WORKER_SPEED
        self.fresh = True
        self.specialed = False

    def preload_spawned(self, uid):
        """为演示单位行为参数引用的社区单位建立图像与音效（BattleSpriteFactory::setupResource / setupSoundResource）。

        2026-11-02 UNION（AGENTS 第 319 节 R15）：原生演示只为演示单位建立图像（建立对象时按需新建），开战时则沿子单位字链预载。
        核心钩子内嵌套建立的单位（UNION 的 1、2 号机）不能新建图像，所得精灵的纹理未载入，绘制时不显示或在 Graphics::drawImageSE 停止。
        共用效果图像 402（命中、爆炸等 0xffNN 效果）同理：核心钩子在演示中经嵌套调用放出共用效果时留下页为空的图像，社区单位的演示一并预载。
        UnitActionViewerUnitSetup 释放上一演示的资源后由此预载；UNION 在三机图像都已建立后才生成三机。"""
        units = getattr(getattr(self.p, 'community', None), 'units', None) or ()
        unit = next((u for u in units if u.get('id') == uid), None)
        if unit is None:
            return
        keys = {v for b in unit.get('behaviors') or () for v in (b.get('params') or {}).values() if isinstance(v, str)}
        ids = [u['id'] for u in units if u.get('key') in keys and u.get('id') not in (None, uid)]
        factory = self.p.call('_ZN19BattleSpriteFactory11getInstanceEv')
        self.p.call('_ZN19BattleSpriteFactory13setupResourceE6UnitID', factory, SHARED_EFFECT_ID)
        for child in ids:
            self.p.call('_ZN19BattleSpriteFactory13setupResourceE6UnitID', factory, child)
            self.p.call('_ZN19BattleSpriteFactory18setupSoundResourceE6UnitID', factory, child)

    def clear(self):
        if self.uid is None:
            return
        self.p.call('_ZN7AppMain25UnitActionViewerUnitClearEv', self.app())
        self.uid = None
        self.pending = False

    def state(self):
        unit = self.unit()
        return self.p.word(unit + UNIT_STATE) if unit else None

    def trigger(self):
        if self.action == 'neutral':
            return
        unit = self.unit()
        if unit:
            self.p.call('_ZN12BattleObject18reserveChangeStateEib', unit, ACTION_STATES[self.action], 1)
            self.fresh = False
            self.specialed = self.specialed or self.action == 'special'

    def advance(self):
        """原生 UnitActionViewerUpdate 推进一帧，跳过其自动演示循环（见模块说明）。"""
        app = self.app()
        self.p.write(app + VIEWER_FLAGS, b'\x00\x01')
        self.p.call('_ZN7AppMain22UnitActionViewerUpdateEv', app)
        self.fresh = False

    def block_sound(self, on):
        name = '_ZN7AppMain21Sound_AddRequestBlockENS_14SoundBlockTypeE' if on else \
            '_ZN7AppMain21Sound_DelRequestBlockENS_14SoundBlockTypeE'
        self.p.call(name, self.app(), SOUND_BLOCK)

    def fast_forward(self):
        """变身类单位：推进到原生改为返回建成或变身后的对象，再等它进入待机（屏蔽音效由调用者负责）。"""
        for _ in range(PRELUDE_LIMIT):
            if self.transformed():
                break
            self.advance()
        for _ in range(SETTLE_LIMIT):
            if self.state() == STATE_NEUTRAL:
                break
            self.advance()

    def start(self):
        """开始所选动作：演示对象已在待机时直接放回起点后预约（quick），否则重新建立单位（刚建立且未推进时不重复建立）；
        变身类单位先离屏快进到变身完成。"""
        if self.quick:
            self.quick = False
            self.reset_position()
            self.send_worker_away()
            self.cycle = self.idle = 0
            self.started = False
            self.trigger()
            return
        if not self.fresh:
            self.setup(self.uid)
        if self.action != 'neutral' and self.transforms.get(self.uid):
            self.block_sound(True)
            try:
                self.fast_forward()
            finally:
                self.block_sound(False)
            self.send_worker_away()
            self.cycle = self.idle = 0
            self.started = False
        self.trigger()

    def play(self, uid, action='neutral', key=None):
        """请求演示 uid 的动作：换单位时立即建立单位（供查询），测量与开始在绘制阶段进行（prepare）。
        key 为单位稳定键（图像范围按此保存，见 BoundsStore）。原生动作浏览无法演示的单位不建立演示。"""
        if not self.supported(uid):
            self.clear()
            self.key, self.action, self.quick = key, action, False
            return
        if self.uid != uid:
            self.setup(uid)
            self.key = key
            self.quick = False
        else:
            self.key = key if key is not None else self.key
            if action == 'neutral' and self.action == 'neutral' and not self.pending:
                return                    # 已在演示待机
            self.quick = not self.pending and self.idle_ready() and (action == 'neutral' or not self.specialed)
        self.uid, self.action, self.pending = uid, action, True

    def idle_ready(self):
        """演示对象已在待机（变身类单位须已变身）：从待机切到某个动作时可直接放回起点后预约，不重新建立。"""
        transforms = self.transforms.get(self.uid)
        if transforms is None or self.state() != STATE_NEUTRAL:
            return False
        return not transforms or self.transformed()

    def prepare(self):
        """绘制阶段：所选动作尚未开始时，取得图像范围（已保存的结果，或测量）再开始。返回 True 表示进行了测量、
        画面须由调用者重画。"""
        if not self.pending or self.uid is None:
            return False
        self.pending = False
        measured = False
        for action in ('neutral', self.action):
            if (self.uid, action) in self.bounds or self.recall(action):
                continue
            self.measure(action)
            self.remember(action)
            measured = True
        if measured:
            self.quick = False            # 测量推进了演示对象，须重新建立
            self.store.save()
        self.start()
        return measured

    def signature(self):
        """社区单位定义的签名（定义改变时重新测量）；原版单位为空。"""
        key = self.key
        if key not in self.signatures:
            community = getattr(self.p, 'community', None)
            unit = next((u for u in getattr(community, 'units', None) or () if u.get('key') == key), None)
            value = ''
            if unit is not None:
                try:
                    text = json.dumps(unit, sort_keys=True, default=str)
                except TypeError:
                    text = repr(unit)
                value = blake2(text.encode('utf-8'))[:16]
            self.signatures[key] = value
        return self.signatures[key]

    def recall(self, action):
        """从已保存的结果取得图像范围；待机的记录同时给出是否变身。"""
        if self.key is None:
            return False
        signature = self.signature()
        transforms = self.store.transforms(self.key, signature) if action == 'neutral' else None
        if action == 'neutral' and transforms is None:
            return False
        bounds = self.store.bounds(self.key, signature, action)
        if bounds is None:
            return False
        if action == 'neutral':
            self.transforms[self.uid] = transforms
        self.bounds[(self.uid, action)] = bounds
        return True

    def remember(self, action):
        if self.key is not None:
            self.store.put(self.key, self.signature(), action, self.bounds[(self.uid, action)],
                           self.transforms.get(self.uid) if action == 'neutral' else None)

    def update(self):
        """每帧推进一次；动作结束回到待机 REPEAT_WAIT 帧后，与原生自动演示循环相同，放回起点再预约。"""
        if self.uid is None:
            return
        self.advance()
        self.lead_worker_out()
        if self.action == 'neutral':
            return
        self.cycle += 1
        state = self.state()
        if state != STATE_NEUTRAL:
            self.started, self.idle = True, 0
        elif self.started or self.cycle > 60:
            self.idle += 1
            if self.idle >= REPEAT_WAIT:
                self.reset_position()
                self.cycle = self.idle = 0
                self.started = False
                self.trigger()

    def reset_position(self):
        """与原生自动演示循环相同：把演示对象放回起点（app+0xb8b0 / 0xb8b4；变身后原生已改为建成对象的位置）。"""
        p, app, unit = self.p, self.app(), self.unit()
        if not unit:
            return
        x, y = float(p.word(app + 0xb8b0)), float(p.word(app + 0xb8b4))
        p.write(unit + UNIT_X, struct.pack('<ff', x, y))
        p.write(unit + UNIT_X + 8, struct.pack('<ff', x, y))

    # ---------- 测量 ----------
    def measure(self, action):
        """离屏运行 action，每 SAMPLE_EVERY 帧以 MEASURE_SCALE 把全部对象叠画到测量区域，结束时读回像素求图像范围
        （相对起点脚点、缩放 1 的画布像素；动作另在首个有图像的取样后读回一次，取单位自身的范围）。待机运行
        NEUTRAL_FRAMES 帧并记录是否变身；动作先快进变身类单位，运行到动作结束后 ACTION_TAIL 帧，水平范围只计单位
        前后 H_EXTRA 以内。测量会写入画面，调用者随后须重画界面。"""
        from PIL import Image, ImageChops
        p, gfx = self.p, self.p.graphics
        f = gfx.function
        rx, ry, rw, rh = MEASURE_REGION
        anchor = (rx + rw / 2, ry + rh * 0.72)
        sx, sy, sw, sh = gfx.surface_rect((rx, gfx.logical_size[1] - ry - rh, rw, rh))
        first = union = None
        reads, xs = 0, []
        transformed = False
        if sw > 0 and sh > 0:
            clear = (C.c_float * 4)()
            f('glGetFloatv', 'up')(0x0C22, C.cast(clear, C.c_void_p))
            scissor = f('glIsEnabled', 'u', C.c_ubyte)(0x0C11)
            box = (C.c_int * 4)()
            f('glGetIntegerv', 'up')(0x0C10, C.cast(box, C.c_void_p))
            pixels = (C.c_ubyte * (sw * sh * 4))()
            key = Image.new('RGB', (sw, sh), KEY)
            kx, ky, k = rw / sw, rh / sh, 1.0 / MEASURE_SCALE

            def read_box():
                """读回测量区域，求至今叠画的全部图像的包围盒。"""
                nonlocal reads
                reads += 1
                f('glReadPixels', 'iiiiuup')(sx, sy, sw, sh, 0x1908, 0x1401, C.cast(pixels, C.c_void_p))
                shot = Image.frombuffer('RGBA', (sw, sh), pixels, 'raw', 'RGBA', 0, 1).convert('RGB')
                bbox = ImageChops.difference(shot, key).getbbox()          # 行 0 为画面底部
                if not bbox:
                    return None
                return ((rx + bbox[0] * kx - anchor[0]) * k, (ry + rh - bbox[3] * ky - anchor[1]) * k,
                        (rx + bbox[2] * kx - anchor[0]) * k, (ry + rh - bbox[1] * ky - anchor[1]) * k)

            keep = self.action
            self.block_sound(True)
            try:
                if not self.fresh:
                    self.setup(self.uid)
                self.action = action
                if action != 'neutral':
                    if self.transforms.get(self.uid):
                        self.fast_forward()
                        self.send_worker_away()
                    self.trigger()
                f('glEnable', 'u')(0x0C11)
                f('glScissor', 'iiii')(sx, sy, sw, sh)
                f('glClearColor', 'ffff')(KEY[0] / 255, KEY[1] / 255, KEY[2] / 255, 1.0)
                f('glClear', 'u')(0x4000)
                left = sampled = False
                tail = None
                limit = NEUTRAL_FRAMES if action == 'neutral' else ACTION_LIMIT
                for frame in range(limit):
                    if frame % SAMPLE_EVERY == 0:
                        self.render(anchor, MEASURE_REGION, MEASURE_SCALE)
                        sampled = True
                        if action != 'neutral' and first is None:
                            first = read_box()
                    unit = self.unit()
                    if unit:
                        xs.append((fword(p, unit + UNIT_X) - self.start_x) * CANVAS)
                    if action == 'neutral':
                        transformed = transformed or self.transformed()
                    else:
                        state = self.state()
                        if state != STATE_NEUTRAL:
                            left = True
                        elif (left or frame > 60) and tail is None:
                            tail = ACTION_TAIL
                        if tail is not None:
                            tail -= 1
                            if tail <= 0:
                                break
                    self.advance()
                    self.send_worker_away()
                if sampled:
                    union = read_box()
            finally:
                self.block_sound(False)
                f('glClearColor', 'ffff')(*clear)
                f('glScissor', 'iiii')(*box)
                f('glEnable' if scissor else 'glDisable', 'u')(0x0C11)
                self.action = keep
        if action == 'neutral':
            self.transforms[self.uid] = transformed
        if union is None:
            bounds = DEFAULT_BOUNDS
        else:
            l, t, r, b = union[0] - 4, union[1] - 4, union[2] + 4, union[3] + 4
            if action != 'neutral' and xs and first is not None:
                # 水平只计单位（首个取样的姿态加上动作中的位移）前后 H_EXTRA 以内
                l0, r0 = first[0], first[2]
                l = max(l, l0 + min(xs) - xs[0] - H_EXTRA)
                r = min(r, r0 + max(xs) - xs[0] + H_EXTRA)
            bounds = (l, t, r, b)
        self.bounds[(self.uid, action)] = bounds
        p.log('UNIT_VIEWER_BOUNDS', self.uid, action, [round(v) for v in bounds], reads,
              self.transforms.get(self.uid))
        return bounds

    # ---------- 布局与绘制 ----------
    def layout(self, foot, frame):
        """缩放与脚点：所选动作（或待机）的图像范围缩放后放入画框。返回 (缩放, 起点脚点的画布坐标)。
        图像水平居中（带位移的动作范围已含位移，起点靠左、终点靠右）；纵向保持 foot 的高度，图像越过画框上下边时
        上下移动。脚点（落地位置）同样计入范围。"""
        l, t, r, b = self.bounds.get((self.uid, self.action)) or self.bounds.get((self.uid, 'neutral')) \
            or DEFAULT_BOUNDS
        t, b = min(t, 0.0), max(b, 0.0)
        fx, fy, fw, fh = frame
        room_w, room_h = fw - 2 * FIT_MARGIN, fh - 2 * FIT_MARGIN
        scale = max(MIN_SCALE, min(1.0, room_w / max(r - l, 1.0), room_h / max(b - t, 1.0)))
        x = fx + fw / 2 - scale * (l + r) / 2
        y = min(foot[1], fy + fh - FIT_MARGIN - b * scale)
        y = max(y, fy + FIT_MARGIN - t * scale)
        return scale, (x, y)

    def camera(self, foot):
        """原生坐标的镜头 (x, y)：单位起点的脚点落在 foot（画布坐标）。"""
        margin = self.p.word(self.app() + 0x3c)
        return self.start_x - (foot[0] / CANVAS - margin), self.start_y - foot[1] / CANVAS

    def render(self, foot, frame, scale):
        """以 foot 为中心、按 scale 缩小绘制全部演示对象（改写模型矩阵），裁切到 frame（画布 x, y, w, h）。"""
        p, app = self.p, self.app()
        g = p.word(app + 0x7c)
        margin = p.word(app + 0x3c)
        cx, cy = self.camera(foot)
        clip = (round(frame[0] / CANVAS - margin), round(frame[1] / CANVAS), round(frame[2] / CANVAS),
                round(frame[3] / CANVAS))
        p.call('_ZN11GraphicsOpt7setClipEiiii', g, *clip)
        manager = p.call('_ZN19BattleObjectManager11getInstanceEv')
        matrix = p.word(p.word(g) + 0x3c) + 0x90          # GraphicsOpt → Graphics → OGLRender 的模型矩阵（列主序）
        saved = p.read(matrix, 64)
        if scale != 1.0:
            m = list(struct.unpack('<16f', saved))
            m[0], m[5] = m[0] * scale, m[5] * scale
            m[12] = m[12] * scale + (1 - scale) * foot[0]
            m[13] = m[13] * scale + (1 - scale) * foot[1]
            p.write(matrix, struct.pack('<16f', *m))
        try:
            p.call('_ZN19BattleObjectManager4drawEfff', manager, f2i(cx), f2i(cy), f2i(1.0))
            p.call('_ZN11GraphicsOpt9clearClipEv', g)
            p.call('_ZN11GraphicsOpt9drawStackEv', g)
        finally:
            p.write(matrix, saved)

    def draw(self, foot, frame):
        """在宿主界面之上绘制：frame 为画框（画布 x, y, w, h），foot 为缩放 1 时单位起点的脚点（画布坐标）。"""
        if self.uid is None:
            return
        scale, point = self.layout(foot, frame)
        self.view = (scale, point, frame)
        self.render(point, frame, scale)
