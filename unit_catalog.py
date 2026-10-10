"""单位目录（只读部分）：单位数据的统一入口，与界面无关（模组规格 M0 第 7 节）。

商店、强化列表、编队选择、LAB 选单位以及以后的新界面都从这里取数据。数据全部经原生接口读取：
名称与说明 GetMenuUnitName/Info，阵营 GetUnitAffiliation，等级 GetUnitLevelSaveData/GetUnitLevelOpenSaveData，
AP GetMenuUnitCost，价格与解锁 GetMenuShopPrice/IsMenuShopEnableSaveData（经原生单位商店目录），
等级数值 BattleInfo::getUnitStatus（含社区单位的倍率处理）。目录不写存档；购买、强化等操作接口在 U1 阶段实现。

条目索引按游戏语言缓存；等级数值按 (UnitID, 等级) 按需计算并缓存。等级参数为界面等级 1–40。
"""
import math
import struct

FALLBACK_LANGUAGE = 3
LANGUAGE_OFFSET = 0x3d64
# getUnitStatus 输出（BattleUnitStatus）：字 0 UnitID、字 2 内部等级，自字 3（HP）起与数据行状态词编号一致（×4 定址）；
# 击退门槛与击退力为 ×100 的计量值，字 5 移动速度为浮点数。AP 与再出击等待取自 getUnitCreateParams。
STATUS_SIZE = 0xec
CREATE_SIZE = 28
SHOP_TYPE_UNIT = 2
ACTION_TABLE_GOT = 0x109373f4
# 建筑类：行动类为 Kouhei、Donou、Mortar_Kouhei、GuerrillaMortar_Kouhei（与 LAB AI 相同）。
BUILDER_VTABLES = (0x10929950, 0x10929980, 0x1092b600, 0x1092b750)
SORT_KEYS = ('uid', 'ap', 'price', 'hp', 'dps', 'value', 'knockback_threshold', 'name', 'newest')
DETAIL_SORTS = {'hp', 'dps', 'value', 'knockback_threshold'}


def _i32(raw, word):
    return struct.unpack_from('<i', raw, word * 4)[0]


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
            level = p.call('_ZN7AppMain20GetUnitLevelSaveDataE6UnitID', app, uid)
            level = None if level == 0xffffffff else level + 1
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
                # 出击 AP 取 getUnitCreateParams（与等级数值同源；GetMenuUnitCost 对社区单位不返回出击 AP）。
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
        """拥有状态、等级或价格变化后（购买、强化、换语言）重建索引；等级数值缓存保留。"""
        self.entries = None

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

    def stats(self, uid, level=40):
        cached = self.details.get((uid, level))
        if cached is not None:
            return cached
        raw = self.status(uid, level)
        create = self.create_params(uid, level)
        # 状态词 48/49 为界面射程分类（SetUnitInfoParam 依此选择六档距离标签）。
        categories = (_i32(raw, 48), _i32(raw, 49))

        def group(damage, force, distance, wait, attribute, present, category):
            return {'present': present, 'damage': _i32(raw, damage), 'knockback_force': _i32(raw, force) / 100,
                    'distance': _i32(raw, distance), 'wait': _i32(raw, wait), 'attribute': _i32(raw, attribute),
                    'range_category': category}

        attacks = {
            'near': group(15, 16, 19, 20, 21, _i32(raw, 6) > 0 and _i32(raw, 15) > 0, None),
            'normal': group(22, 23, 26, 27, 28, _i32(raw, 22) > 0, categories[0]),
            'special': group(29, 30, 33, 35, 37, _i32(raw, 29) > 0, categories[1]),
        }
        attacks['special']['first_cooldown'] = _i32(raw, 36)
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
        self.details[(uid, level)] = result
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
          faction（集合）、source（集合）、owned（True/False）、unlocked（True/False）、tags（须全部具备）、
          attack（集合，'near'/'normal'/'special' 须全部具备）、ap 与 price（(最小, 最大)，含端点）、text（名称或稳定键子串，不分大小写）。
        sort 取 SORT_KEYS 之一；同值按 UnitID 排序。返回 (本页条目, 总数)。"""
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
            items = [e for e in items if all(self.stats(e['uid'], level)['attacks'][a]['present'] for a in filters['attack'])]
        if sort in DETAIL_SORTS:
            def value(e):
                return self.stats(e['uid'], level)[sort]
        elif sort == 'name':
            def value(e):
                return e['name'].casefold()
        elif sort == 'newest':
            def value(e):
                return e['order']
        elif sort == 'price':
            def value(e):
                return -1 if e['price'] is None else e['price']
        else:
            def value(e):
                return e[sort]
        items = sorted(items, key=lambda e: e['uid'])
        items.sort(key=value, reverse=descending)
        start = max(0, page) * page_size
        return items[start:start + page_size], len(items)
