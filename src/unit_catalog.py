"""单位目录：单位数据与操作的统一入口，与界面无关（模组规格 M0 第 7 节）。

商店、强化列表、编队选择、LAB 选单位以及以后的新界面都从这里取数据。数据全部经原生接口读取：
名称与说明 GetMenuUnitName/Info，阵营 GetUnitAffiliation，等级 GetUnitLevelSaveData/GetUnitLevelOpenSaveData，
出击 AP 与再出击等待 getUnitCreateParams，价格与解锁 GetMenuShopPrice/IsMenuShopEnableSaveData（经原生单位商店目录），
等级数值 BattleInfo::getUnitStatus（含社区单位的倍率处理）。

操作接口（U1，依据 docs/ui/U1_UNIT_UI_KICKOFF_2026-10-11.md 附录 A.1–A.4）：强化 upgrade、开放阶段 open_stage、
购买 purchase / purchase_pack。各操作按原生事务的顺序调用原生存档函数（原生强化 SelectCustomBuy、开放阶段
PopupLevelOpenConfirmYesMedal / PopupResultLvLimitBreakMSP、商店 PopupResultMenuShopBuyYes），不直接写存档，
返回统一的结果对象（result）；音效与动画由界面按结果播放。

条目索引按游戏语言缓存；等级数值按 (UnitID, 等级) 按需计算并缓存。等级参数为界面等级 1–40。
"""
import ctypes
import math
import struct

FALLBACK_LANGUAGE = 0           # 当前语言无原生文字（例如编号 6、8）时显示英文（U1 D4）
LANGUAGE_OFFSET = 0x3d64
# getUnitStatus 输出（BattleUnitStatus）：字 0 UnitID、字 2 内部等级，自字 3（HP）起与数据行状态词编号一致（×4 定址）；
# 击退门槛与击退力为 ×100 的计量值，字 5 移动速度为浮点数。AP 与再出击等待取自 getUnitCreateParams。
STATUS_SIZE = 0xec
CREATE_SIZE = 28
SHOP_TYPE_UNIT = 2
ACTION_TABLE_GOT = 0x109373f4
# 建筑类：行动类为 Kouhei、Donou、Mortar_Kouhei、GuerrillaMortar_Kouhei（与 LAB AI 相同）。
BUILDER_VTABLES = (0x10929950, 0x10929980, 0x1092b600, 0x1092b750)
# 原生动作浏览点击时不演示特殊攻击的 UnitID（UnitActionViewerScreenTouch 0x20af64 按 getUnitID 逐个比较）：修筑、变身、
# 召唤箱、内部部件等。社区单位按其基准单位判断。
VIEWER_NO_SPECIAL = frozenset({5, 9, 10, 32, 33, 37, 64, 73, 74, 75, 76, 77, 78, 95, 108, 155, 160, 163, 167, 169, 171, 182,
                               184, 207, 219, 244, 245, 246, 264, 281, 282, 304, 305, 306, 308, 316, 346, 348, 350, 352,
                               355, 357, 366, 367, 369, 378, 392, 396})
SORT_KEYS = ('uid', 'level', 'ap', 'price', 'hp', 'dps', 'value', 'knockback_threshold', 'name', 'newest')
DETAIL_SORTS = {'hp', 'dps', 'value', 'knockback_threshold'}
SHOP_TYPE_PACK = 4
CORE_SHOP_BASE = 289            # 军队核心商店 ID = 289 + 阵营（GetUnitAffiliation）
LIMIT_BREAK_PAY = {'medal': 0, 'msp': 1}   # GetLvLimitBreakPrice 的付款类型（附录 A.3）
OPEN_STAGES = (20, 25, 30)      # 可付费提高上限的开放值（各 +5，至 35）


def _i32(raw, word):
    return struct.unpack_from('<i', raw, word * 4)[0]


def i32(value):
    return ctypes.c_int32(value).value


def result(action, key, ok, reason=None, before=None, after=None, **extra):
    """操作结果（M0 规格第 7.4 节）：ok、原因代码、货币变化（勋章、MSP）、操作前后的余额与等级信息。
    原因代码：not_owned、owned、locked、not_for_sale、sold_out、at_cap、no_stage、msp_short、medal_short、
    core_unsupported、rejected。"""
    before = before or {}
    after = after or before
    delta = {name: after.get(name, 0) - before.get(name, 0) for name in ('medal', 'msp')}
    return dict(action=action, key=key, ok=bool(ok), reason=reason, currency=delta, wallet=after, **extra)


def catalog(p):
    """每个游戏进程共用一个目录实例。"""
    if getattr(p, 'unit_catalog', None) is None:
        p.unit_catalog = UnitCatalog(p)
    return p.unit_catalog


class UnitCatalog:
    def __init__(self, p):
        self.p = p
        self.entries = None
        self.by_key = {}
        self.language = None
        self.details = {}
        self.unit_details = {}          # (UnitID, 等级) → 该单位自身的数值（unit_stats）
        self.displays = {}              # UnitID → 显示数值所用的单位（display_uid）
        self.scratch = None
        self.create_scratch = None

    # ---------- 索引 ----------
    def app(self):
        return self.p.app_instance()

    def current_language(self):
        return self.p.word(self.app() + LANGUAGE_OFFSET)

    def text(self, symbol, uid):
        for language in (self.language, FALLBACK_LANGUAGE):
            try:
                value = self.p.string(self.p.call(symbol, uid, language))
            except Exception:
                value = ''
            if value and value != '-':
                return value
        return ''

    def shop_map(self):
        """原生单位商店目录（原版 259 项加社区追加项）中 UnitID → 商店 ID。
        商品类型 2 为单位（GetMenuShopUniqueID 返回 UnitID，GetMenuShopValue 为数量），类型 4 为组合包，排除。"""
        p = self.p
        community = getattr(p, 'community', None)
        if community is None or not community.ready:
            return {}
        from community_content import HEADER
        pointer, count = p.word(HEADER + 44), p.word(HEADER + 48)
        result = {}
        for i in range(count):
            sid = p.word(pointer + i * 4)
            if p.call('_Z15GetMenuShopType10MenuShopID', sid) == SHOP_TYPE_UNIT:
                result.setdefault(p.call('_Z19GetMenuShopUniqueID10MenuShopID', sid), sid)
        return result

    def index(self):
        """全部可选单位的条目：原版 1–399（名称带括号或为“-”者为内部子单位，排除）与社区非内部单位。"""
        language = self.current_language()
        if self.entries is not None and self.language == language:
            return self.entries
        p, app = self.p, self.app()
        self.language = language
        shops = self.shop_map()
        community = getattr(p, 'community', None)
        units = [(uid, None) for uid in range(1, 400)]
        if community is not None:
            units += [(u['id'], u) for u in community.units if not u.get('internal_only')]
        entries = []
        for order, (uid, unit) in enumerate(units):
            # 与 LAB 选单位既有规则一致：原版名称以括号开头者为内部子单位；无名称者显示为“UID n”。
            name = self.text('_Z15GetMenuUnitName6UnitIDi', uid) or f'UID {uid}'
            if unit is None and name.startswith('('):
                continue
            level = i32(p.call('_ZN7AppMain20GetUnitLevelSaveDataE6UnitID', app, uid))
            level = level + 1 if level >= 0 else None
            sid = shops.get(uid)
            entry = {
                'key': unit['key'] if unit else f'original.{uid}',
                'uid': uid,
                'source': community.unit_source[unit['key']] if unit else 'original',
                'faction': p.call('_ZN7AppMain18GetUnitAffiliationE6UnitID', app, uid),
                'name': name,
                'owned': level is not None,
                'level': level,
                'level_open': p.call('_ZN7AppMain24GetUnitLevelOpenSaveDataE6UnitID', app, uid) if level is not None else None,
                # 出击 AP 取 getUnitCreateParams 字 0（GetMenuUnitCost 返回强化 MSP 费用，附录 A.1）。
                'ap': _i32(self.create_params(uid, level or 1), 0),
                'shop_id': sid,
                'price': p.call('_Z16GetMenuShopPrice10MenuShopID', sid) if sid is not None else None,
                'unlocked': bool(p.call('_ZN7AppMain24IsMenuShopEnableSaveDataE10MenuShopID', app, sid)) if sid is not None else None,
                'tags': list(unit.get('tags', [])) if unit else [],
                'order': order,
            }
            if self.is_builder(uid):
                entry['tags'].append('builder')
            entries.append(entry)
        self.entries = entries
        self.by_key = {e['key']: e for e in entries}
        return entries

    def refresh(self):
        """重建索引（内容或语言变化时）；等级数值缓存保留。只有拥有状态、等级与解锁变化时用 refresh_state。"""
        self.entries = None

    def refresh_state(self, shop=True):
        """就地更新各条目的拥有状态、等级、开放值与（shop 为真时）商品解锁；索引尚未建立或语言变化时重建。
        每条目 1–3 次原生调用（完整重建约 7–9 次），供打开界面与操作后使用。"""
        if self.entries is None or self.language != self.current_language():
            return self.index()
        p, app = self.p, self.app()
        for entry in self.entries:
            uid = entry['uid']
            level = i32(p.call('_ZN7AppMain20GetUnitLevelSaveDataE6UnitID', app, uid))
            level = level + 1 if level >= 0 else None
            entry['owned'], entry['level'] = level is not None, level
            entry['level_open'] = (p.call('_ZN7AppMain24GetUnitLevelOpenSaveDataE6UnitID', app, uid)
                                   if level is not None else None)
            if shop and entry['shop_id'] is not None:
                entry['unlocked'] = bool(p.call('_ZN7AppMain24IsMenuShopEnableSaveDataE10MenuShopID', app, entry['shop_id']))
        return self.entries

    def native_base(self, uid):
        """原版单位为自身；社区单位为登记的基准单位（base_id）。"""
        if uid < 400:
            return uid
        community = getattr(self.p, 'community', None)
        unit = next((u for u in getattr(community, 'units', None) or () if u.get('id') == uid), None)
        return unit.get('base_id', uid) if unit else uid

    def is_builder(self, uid):
        table = self.p.word(ACTION_TABLE_GOT)
        action = self.p.word(table + uid * 4) if table else 0
        return bool(action) and self.p.word(action) in BUILDER_VTABLES

    # ---------- 等级数值 ----------
    def status(self, uid, level):
        p = self.p
        if self.scratch is None:
            self.scratch = p.alloc(STATUS_SIZE)
        p.write(self.scratch, bytes(STATUS_SIZE))
        p.call('_ZN10BattleInfo13getUnitStatusE6UnitIDiP16BattleUnitStatus',
               p.call('_ZN10BattleInfo11getInstanceEv'), uid, level - 1, self.scratch)
        return p.read(self.scratch, STATUS_SIZE)

    def create_params(self, uid, level):
        """BattleInfo::getUnitCreateParams：字 0 为出击 AP，字 1 为再出击等待（tick，未含基地强化）。"""
        p = self.p
        if self.create_scratch is None:
            self.create_scratch = p.alloc(CREATE_SIZE)
        p.write(self.create_scratch, bytes(CREATE_SIZE))
        p.call('_ZN10BattleInfo19getUnitCreateParamsE6UnitIDiP22BattleUnitCreateParams',
               p.call('_ZN10BattleInfo11getInstanceEv'), uid, level - 1, self.create_scratch)
        return p.read(self.create_scratch, CREATE_SIZE)

    def display_uid(self, uid):
        """显示数值所用的单位。原生信息窗口 AppMain::SetUnitInfoParam（0x1eccfc）的生命与移速取自 GetMenuUnitID（菜单
        数据字 1）：修筑类单位为建成后的建筑，空降、架设类为落地或架好后的单位（例如沙包 5→4、金屬要塞 367→366、
        傘兵 159→160）；没有菜单数据时原生返回 2，此处取自身。社区单位同第 30 节 menu_display_id 钩子，取 child_unit_key
        登记的子单位（例如正規軍傘兵 1034→1037、木乃伊召喚箱 MKII 1041→1042），没有时为自身。"""
        value = self.displays.get(uid)
        if value is None:
            p = self.p
            if uid >= 400:
                units = getattr(getattr(p, 'community', None), 'units', None) or ()
                unit = next((u for u in units if u.get('id') == uid), None)
                child = unit.get('child_unit_key') if unit else None
                value = next((u['id'] for u in units if child and u.get('key') == child), uid)
            else:
                value = p.call('_Z13GetMenuUnitID6UnitID', uid) if p.call('_Z15GetMenuUnitData6UnitID', uid) else uid
            self.displays[uid] = value
        return value

    def second_form_uid(self, uid):
        """第二形态（行为 iron_slider 的 second_form，内部单位）的 UnitID；没有时为 None。"""
        if uid < 400:
            return None
        units = getattr(getattr(self.p, 'community', None), 'units', None) or ()
        unit = next((u for u in units if u.get('id') == uid), None)
        form = unit.get('second_form_key') if unit else None
        return next((u['id'] for u in units if form and u.get('key') == form), None)

    def stats(self, uid, level=40):
        """界面显示的数值（STATUS、LV UP、排序与攻击筛选）。生命、击退门槛、移速、击毁返还与各攻击组取 display_uid
        的单位（实际在战场上作战的单位），AP 与再出击等待取购买的单位本身（原生信息窗口同此）；action_attacks 为单位
        本身的攻击组，ACTION 的按钮按它决定（原生动作浏览演示的是购买的单位，修筑类先建成再演示）。
        有第二形态的单位（钢铁哨兵）生命为两形态同等级生命之和（用户 2026-10-22）。"""
        cached = self.details.get((uid, level))
        if cached is not None:
            return cached
        own = self.unit_stats(uid, level)
        display = self.display_uid(uid)
        if display == uid:
            result = dict(own, display_uid=uid, action_attacks=own['attacks'])
        else:
            result = dict(self.unit_stats(display, level), uid=uid, ap=own['ap'],
                          production_interval=own['production_interval'], builder=own['builder'],
                          display_uid=display, action_attacks=own['attacks'])
        form = self.second_form_uid(uid)
        if form is not None:
            result = dict(result, hp=result['hp'] + self.unit_stats(form, level)['hp'])
        self.details[(uid, level)] = result
        return result

    def unit_stats(self, uid, level=40):
        """UnitID 自身的数值（不经 display_uid）。"""
        cached = self.unit_details.get((uid, level))
        if cached is not None:
            return cached
        raw = self.status(uid, level)
        create = self.create_params(uid, level)
        # 状态词 48/49 为界面射程分类（SetUnitInfoParam 依此选择六档距离标签）。
        categories = (_i32(raw, 48), _i32(raw, 49))

        def group(damage, force, targets, distance, wait, attribute, present, category, reach=0):
            # 词 17/24/31 为每次攻击可命中的目标数上限（0 视为 255；原生说明窗口 ≤1 为 SINGLE，>1 为 SPREAD，附录 A.7）
            limit = _i32(raw, targets)
            return {'present': present, 'damage': _i32(raw, damage), 'knockback_force': _i32(raw, force) / 100,
                    'targets': 255 if limit == 0 else limit, 'range': reach,
                    'distance': _i32(raw, distance), 'wait': _i32(raw, wait), 'attribute': _i32(raw, attribute),
                    'range_category': category}

        # 近距离 / 远距离按原生动作浏览（UnitActionViewerUpdate 0x20b2b4）的判定：BattleUnit::isEnableShortAttack 为
        # 词 6≠0，isEnableLongAttack 为词 7>99；词 7 非零而不大于 99 时原生同样按近距离演示（状态 30）。远距离攻击
        # 使用普攻组（词 22–28）；词 6 为 0 的近距离攻击（例如普通兵的小刀，词 7=40）在战斗中同样由普攻组结算，
        # 其数值取普攻组，词 6 非 0 时取近距组（词 15–21）。
        near_reach, far_reach = _i32(raw, 6), _i32(raw, 7)
        short = near_reach != 0 or (far_reach != 0 and far_reach <= 99)
        if near_reach != 0:
            near = group(15, 16, 17, 19, 20, 21, short, None, near_reach)
        else:
            near = group(22, 23, 24, 26, 27, 28, short, categories[0], far_reach if short else 0)
        attacks = {
            'near': near,
            'normal': group(22, 23, 24, 26, 27, 28, far_reach > 99, categories[0], far_reach),
            # 特殊攻击按原生判定：BattleUnit::isSpAttack（0x1e0e36）在词 36 为 0 时恒为否；原生动作浏览另有排除表。
            # 不造成伤害的特殊攻击（召唤、防御、缩回壳里等，词 29 为 0）同样存在。
            'special': group(29, 30, 31, 33, 35, 37,
                             _i32(raw, 36) != 0 and self.native_base(uid) not in VIEWER_NO_SPECIAL, categories[1]),
        }
        attacks['special']['first_cooldown'] = _i32(raw, 36)
        attacks['special']['interval'] = _i32(raw, 34)      # 特殊攻击等待（词 34）；wait 为之后的冷却（词 35）
        hp = _i32(raw, 3)
        threshold = _i32(raw, 4) / 100
        builder = self.is_builder(uid)
        # 每秒伤害与综合强度沿用 LAB AI 的单位价值公式（src/lab_hooks.cpp ai_unit_value）。
        dps = max(attacks['normal']['damage'], 0) * 30 / (max(attacks['normal']['wait'], 0) + 30)
        if attacks['special']['damage'] > 0:
            dps += attacks['special']['damage'] * 30 / max(attacks['special']['wait'], 30)
        if builder:
            value = max(_i32(raw, 50), 1) * 12
        else:
            value = math.sqrt(max(hp, 1) * max(dps, 1)) * (1 + min(max(threshold, 0), 40) / 40)
        result = {
            'uid': uid, 'level': level, 'ap': _i32(create, 0), 'production_interval': _i32(create, 1), 'hp': hp,
            'knockback_threshold': threshold,
            'move_speed': struct.unpack_from('<f', raw, 0x14)[0],
            'ap_reward': _i32(raw, 13),
            'attack_range': {'near': _i32(raw, 6), 'far': _i32(raw, 7)},
            'attacks': attacks, 'dps': dps, 'value': value, 'builder': builder,
        }
        self.unit_details[(uid, level)] = result
        return result

    # ---------- 查询 ----------
    def detail(self, key, level=40):
        entry = self.by_key.get(key) or {e['key']: e for e in self.index()}.get(key)
        if entry is None:
            raise KeyError(key)
        return dict(entry, stats=self.stats(entry['uid'], level))

    def compare(self, keys, level=40):
        return [self.detail(key, level) for key in keys]

    def list(self, filters=None, sort='uid', descending=False, page=0, page_size=50, level=40):
        """筛选、排序与分页。filters：
          faction（集合）、source（集合）、owned（True/False）、unlocked（True/False）、keys（稳定键集合，例如收藏）、
          tags（须全部具备）、attack（集合，'near'/'normal'/'special' 须全部具备）、ap 与 price（(最小, 最大)，含端点）、text（名称或稳定键子串，不分大小写）。
        sort 取 SORT_KEYS 之一；同值按 UnitID 排序。level 为数值类排序与攻击筛选所用的等级（界面等级），
        'owned' 表示各单位的当前等级（未拥有为 Lv1）。返回 (本页条目, 总数)。"""
        def lv(e):
            return (e['level'] or 1) if level == 'owned' else level
        if sort not in SORT_KEYS:
            raise ValueError('Unsupported sort key: ' + str(sort))
        filters = filters or {}
        items = self.index()
        if 'faction' in filters:
            items = [e for e in items if e['faction'] in filters['faction']]
        if 'source' in filters:
            items = [e for e in items if e['source'] in filters['source']]
        for name in ('owned', 'unlocked'):
            if name in filters:
                items = [e for e in items if bool(e[name]) == filters[name]]
        if 'keys' in filters:
            keys = set(filters['keys'])
            items = [e for e in items if e['key'] in keys]
        if filters.get('tags'):
            wanted = set(filters['tags'])
            items = [e for e in items if wanted <= set(e['tags'])]
        for name in ('ap', 'price'):
            if name in filters:
                low, high = filters[name]
                items = [e for e in items if e[name] is not None and low <= e[name] <= high]
        if filters.get('text'):
            needle = filters['text'].casefold()
            items = [e for e in items if needle in e['name'].casefold() or needle in e['key'].casefold()]
        if filters.get('attack'):
            items = [e for e in items if all(self.stats(e['uid'], lv(e))['attacks'][a]['present'] for a in filters['attack'])]
        if sort in DETAIL_SORTS:
            def value(e):
                return self.stats(e['uid'], lv(e))[sort]
        elif sort == 'name':
            def value(e):
                return e['name'].casefold()
        elif sort == 'newest':
            def value(e):
                return e['order']
        elif sort == 'price':
            def value(e):
                return -1 if e['price'] is None else e['price']
        elif sort == 'level':
            def value(e):
                return e['level'] or 0
        else:
            def value(e):
                return e[sort]
        items = sorted(items, key=lambda e: e['uid'])
        items.sort(key=value, reverse=descending)
        start = max(0, page) * page_size
        return items[start:start + page_size], len(items)

    # ---------- 等级上限与费用（附录 A.1–A.3） ----------
    def entry(self, key):
        self.index()                      # 索引已失效（refresh）时先重建，避免取到旧条目
        entry = self.by_key.get(key)
        if entry is None:
            raise KeyError(key)
        return entry

    def wallet(self):
        p, app = self.p, self.app()
        return {'medal': i32(p.call('_ZN7AppMain21GetMedalCountSaveDataEv', app)),
                'msp': i32(p.call('_ZN7AppMain18GetMSPointSaveDataEv', app))}

    def saved_level(self, uid):
        """界面等级（内部等级 +1）；未拥有为 None。"""
        level = i32(self.p.call('_ZN7AppMain20GetUnitLevelSaveDataE6UnitID', self.app(), uid))
        return level + 1 if level >= 0 else None

    def cap_of(self, uid):
        """有效等级上限（只取上限，供卡片进度条；规则同 level_cap）。"""
        p = self.p
        base = i32(p.call('_Z19GetMenuUnitMaxLevel6UnitID', uid))
        if base <= 10:
            return base
        return max(base, i32(p.call('_ZN7AppMain24GetUnitLevelOpenSaveDataE6UnitID', self.app(), uid)))

    def level_cap(self, key):
        """有效等级上限与下一次提高上限的方式（附录 A.2）：基础上限 GetMenuUnitMaxLevel（按已开放普通世界数为 10/20/20），
        开放值 GetUnitLevelOpenSaveData（本项目钩子按军队核心协调为 35/40）；基础 ≤ 10 时上限为基础值，否则为
        max(基础, 开放值)。next：world（世界进度）、open_stage（可购买开放阶段，附价格）、core（需要军队核心）、max。"""
        p, app = self.p, self.app()
        uid = self.entry(key)['uid']
        base = i32(p.call('_Z19GetMenuUnitMaxLevel6UnitID', uid))
        opened = i32(p.call('_ZN7AppMain24GetUnitLevelOpenSaveDataE6UnitID', app, uid))
        cap = base if base <= 10 else max(base, opened)
        info = {'level': self.saved_level(uid), 'cap': cap, 'base': base, 'open': opened, 'prices': None}
        if cap >= 40:
            info['next'] = 'max'
        elif base <= 10:
            info['next'] = 'world'
        elif opened in OPEN_STAGES:
            info['next'] = 'open_stage'
            info['prices'] = {pay: i32(p.call('_ZN7AppMain20GetLvLimitBreakPriceEiNS_22LV_LIMITBREAK_PAY_TYPEE', app,
                                              opened, kind)) for pay, kind in LIMIT_BREAK_PAY.items()}
        else:
            info['next'] = 'core'
            info['core_shop'] = CORE_SHOP_BASE + p.call('_ZN7AppMain18GetUnitAffiliationE6UnitID', app, uid)
        return info

    def upgrade_cost(self, key, level_from, level_to):
        """界面等级 level_from 升到 level_to 的 MSP 合计：原生 GetMenuUnitCost(uid, 内部等级 L) = P×(3L+5)，逐级相加。"""
        uid = self.entry(key)['uid']
        return sum(i32(self.p.call('_Z15GetMenuUnitCost6UnitIDi', uid, level - 1)) for level in range(level_from, level_to))

    # ---------- 操作（附录 A.1、A.3、A.4） ----------
    def upgrade(self, key, levels):
        """强化 levels 级（'max' 为升到当前上限），按原生 SelectCustomBuy 的顺序逐级执行：扣 MSP、AddUnitLevelSaveData、
        原生核心自动开放判断、SetUnitCustomTimeSaveData。目标超出上限时按上限处理；MSP 不足时不执行任何一级。"""
        p, app = self.p, self.app()
        entry = self.entry(key)
        uid = entry['uid']
        before = self.wallet()
        info = self.level_cap(key)
        level = info['level']
        if level is None:
            return result('upgrade', key, False, 'not_owned', before, cap=info)
        target = info['cap'] if levels == 'max' else min(level + int(levels), info['cap'])
        if target <= level:
            return result('upgrade', key, False, 'at_cap', before, cap=info)
        cost = self.upgrade_cost(key, level, target)
        if before['msp'] < cost:
            return result('upgrade', key, False, 'msp_short', before, cap=info, cost=cost, need=cost - before['msp'])
        done = level
        for _ in range(target - level):
            internal = done - 1
            step = i32(p.call('_Z15GetMenuUnitCost6UnitIDi', uid, internal))
            p.call('_ZN7AppMain18AddMSPointSaveDataEi', app, -step)
            new = i32(p.call('_ZN7AppMain20AddUnitLevelSaveDataE6UnitIDi', app, uid, 1))
            if new <= internal:
                p.call('_ZN7AppMain18AddMSPointSaveDataEi', app, step)      # 钩子拒绝（上限）：退回本级费用
                break
            done = new + 1
            opened = i32(p.call('_ZN7AppMain24GetUnitLevelOpenSaveDataE6UnitID', app, uid))
            need = (opened - 30) // 5 if opened > 29 else 0
            stock = i32(p.call('_Z16GetMenuShopStock10MenuShopID',
                               CORE_SHOP_BASE + p.call('_ZN7AppMain18GetUnitAffiliationE6UnitID', app, uid)))
            if new > 33 and stock >= need and new >= opened - 1:
                p.call('_ZN7AppMain24SetUnitLevelOpenSaveDataE6UnitIDi', app, uid, opened + 5)
            p.call('_ZN7AppMain25SetUnitCustomTimeSaveDataE6UnitID', app, uid)
        self.refresh_state()
        after = self.wallet()
        return result('upgrade', key, done > level, None if done > level else 'rejected', before, after,
                      level_before=level, level_after=done, levels=done - level, cost=before['msp'] - after['msp'],
                      cap=self.level_cap(key))

    def open_stage(self, key, pay='medal'):
        """购买开放阶段（20→25→30→35），按原生 PopupLevelOpenConfirmYesMedal / PopupResultLvLimitBreakMSP 的顺序：
        扣勋章或 MSP，SetUnitLevelLimitBreak（钩子限制 35→40）。"""
        p, app = self.p, self.app()
        uid = self.entry(key)['uid']
        before = self.wallet()
        info = self.level_cap(key)
        if info['level'] is None:
            return result('open_stage', key, False, 'not_owned', before, cap=info)
        if info['next'] != 'open_stage':
            return result('open_stage', key, False, 'no_stage', before, cap=info)
        price = info['prices'][pay]
        if before[pay] < price:
            return result('open_stage', key, False, pay + '_short', before, cap=info, price=price,
                          need=price - before[pay])
        add = '_ZN7AppMain21AddMedalCountSaveDataEi' if pay == 'medal' else '_ZN7AppMain18AddMSPointSaveDataEi'
        p.call(add, app, -price)
        p.call('_ZN7AppMain22SetUnitLevelLimitBreakE6UnitIDi', app, uid, info['open'])
        cap = self.level_cap(key)
        if cap['open'] <= info['open']:
            p.call(add, app, price)                                           # 钩子拒绝：退回
            return result('open_stage', key, False, 'rejected', before, self.wallet(), cap=cap, price=price)
        self.refresh_state()
        return result('open_stage', key, True, None, before, self.wallet(), cap=cap, price=price, pay=pay)

    def community_purchase_supported(self):
        """社区与模组单位经原生 SetUnitBuySaveData 购买时，获得时间写入 app+0x857c+4·uid（无上界，附录 A.11）；
        核心提供对应钩子之前不经本接口购买 UnitID ≥ 400 的单位。"""
        version = getattr(self.p.uc.lib, 'msd_community_get_time_version', None)
        return bool(version and version())

    def shop_price(self, shop_id, uid=None):
        """勋章售价：GetMenuShopPrice，单位商品按 getUnitDiscountRate（数据行 +0x360，原版均为 0）打折，同原生。"""
        p = self.p
        price = i32(p.call('_Z16GetMenuShopPrice10MenuShopID', shop_id))
        if uid is not None:
            rate = i32(p.call('_ZN7AppMain19getUnitDiscountRateE6UnitID', self.app(), uid))
            if rate > 0:
                price = int(price - price * 0.01 * rate)
        return price

    def _buy(self, action, key, shop_id, uids, uid=None):
        p, app = self.p, self.app()
        before = self.wallet()
        if any(u >= 400 for u in uids) and not self.community_purchase_supported():
            return result(action, key, False, 'core_unsupported', before, shop_id=shop_id)
        price = self.shop_price(shop_id, uid)
        value = i32(p.call('_Z16GetMenuShopValue10MenuShopID', shop_id))
        stock = i32(p.call('_Z16GetMenuShopStock10MenuShopID', shop_id))
        maximum = i32(p.call('_Z17GetMenuShopMaxmum10MenuShopID', shop_id))
        if before['medal'] < price:
            return result(action, key, False, 'medal_short', before, shop_id=shop_id, price=price,
                          need=price - before['medal'])
        if value + stock > maximum:
            return result(action, key, False, 'sold_out', before, shop_id=shop_id, price=price)
        p.call('_ZN7AppMain21AddMedalCountSaveDataEi', app, -price)
        p.call('_Z16AddMenuShopStock10MenuShopIDi', shop_id, value)
        self.refresh_state()
        return result(action, key, True, None, before, self.wallet(), shop_id=shop_id, price=price)

    def purchase(self, key):
        """购买单位（原生 PopupResultMenuShopBuyYes 的顺序：余额、库存上限、AddMedalCountSaveData、AddMenuShopStock）。"""
        entry = self.entry(key)
        if entry['owned']:
            return result('purchase', key, False, 'owned', self.wallet())
        if entry['shop_id'] is None:
            return result('purchase', key, False, 'not_for_sale', self.wallet())
        if not entry['unlocked']:
            return result('purchase', key, False, 'locked', self.wallet(), shop_id=entry['shop_id'])
        return self._buy('purchase', key, entry['shop_id'], [entry['uid']], entry['uid'])

    def packs(self):
        """原生单位商店目录中的组合包（商品类型 4）：商店 ID、名称、售价、包内 UnitID、是否可购买。
        可购买与原生单位商店的列出条件相同：显示类型 0（GetMenuShopDisplayType；1 只在模式 6、2 不显示）、已开放
        （IsMenuShopEnableSaveData）、未售完（IsMenuShopSoldOut：包内单位全部拥有即售完，原版组合包库存恒为 0）。"""
        p = self.p
        community = getattr(p, 'community', None)
        if community is None or not community.ready:
            return []
        from community_content import HEADER
        pointer, count = p.word(HEADER + 44), p.word(HEADER + 48)
        language = self.current_language()
        out = []
        for i in range(count):
            sid = p.word(pointer + i * 4)
            if p.call('_Z15GetMenuShopType10MenuShopID', sid) != SHOP_TYPE_PACK:
                continue
            pack = p.call('_Z19GetMenuShopUniqueID10MenuShopID', sid)
            units = []
            for j in range(16):
                uid = i32(p.call('_Z17GetUnitPackDataID10UnitPackIDi', pack, j))
                if uid < 0:
                    break
                units.append(uid)
            display = i32(p.call('_Z22GetMenuShopDisplayType10MenuShopID', sid))
            enabled = bool(p.call('_ZN7AppMain24IsMenuShopEnableSaveDataE10MenuShopID', self.app(), sid))
            sold_out = bool(p.call('_Z17IsMenuShopSoldOut10MenuShopID', sid))
            try:
                name = p.string(p.call('_Z15GetMenuShopName10MenuShopIDi', sid, language))
            except Exception:
                name = ''
            out.append({'shop_id': sid, 'pack': pack, 'name': name, 'price': self.shop_price(sid), 'units': units,
                        'purchasable': display == 0 and enabled and not sold_out})
        return out

    def purchase_pack(self, shop_id):
        """购买组合包：与 purchase 相同的原生顺序；包内已拥有的单位保持等级（原生 AddMenuShopStock 只为未拥有者调用
        SetUnitBuySaveData）。"""
        pack = next((e for e in self.packs() if e['shop_id'] == shop_id), None)
        if pack is None:
            return result('purchase_pack', None, False, 'not_for_sale', self.wallet(), shop_id=shop_id)
        if not pack['purchasable']:
            return result('purchase_pack', None, False, 'sold_out', self.wallet(), shop_id=shop_id)
        return self._buy('purchase_pack', None, shop_id, pack['units'])
