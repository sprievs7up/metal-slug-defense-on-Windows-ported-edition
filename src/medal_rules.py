"""勋章商店与区域通关勋章的规则（2026-11-10 用户设定）。

勋章商店（原生场景 115–117，SC_MedalInit / SC_MedalEnd / SC_MedalLoop）的商品表共 18 项（原生顺序）：
0–7 为 KOF 单位组合包（msd_030–037_kofpack），8 为相川留美的支援物资（msd_023_rumi：购买后 15 天内每天登入领取 30 勋章），
9 为相川圆香的支援物资（msd_024_madoka：15 天内每天 50000 MSP），10–17 为勋章包（msd_001–008_medalpack）。
- 勋章包：数量表（SHOP_TABLE+0xc0，每项 int32；面板数字、确认文字与 setPurchaseOK 的入账都读此表）第 10–17 项乘以 PACK_FACTOR，
  价格仍为 FREE。第 8、9 项保持原值：setPurchaseOK 以第 8 项的 30 辨认留美，每天的发放量写在原生 GetLoginBonus 中。
- 支援物资以 MSP 购买，价格见 SUPPLY_PRICES；价格文字、余额核对与扣除在平台层 local_platform（buy_supply），
  之后的领取许可、15 天计数与“已購買”显示沿用原生流程（购买后回到主菜单即发放第 1 天的份额）。
  购买确认文字为原生 strMedal 17（参数依次为商品名称、价格）；繁体中文的原文“是否要以%s\n購買%？”参数次序与格式符有误，
  由本模块换为 CONFIRM_ZT。
- KOF 单位组合包页面停用：底栏的模式切换按钮（任务槽 app+0x33c4，GT_MedalShopModeChangeButton）移出画面
  （同原生隐藏任务的坐标 −16384），BACK（app+0x36d8）移到两个按钮原位置的中点；商品列表只有 MedalShopType 0。
  按钮任务在闸门关闭期间建立（场景 117 状态 0），本模块在同一帧原生返回后改写位置。

区域通关勋章（原生 BattleEndGetAreaResult：区域内全部小关首次通关时，按 ciBattleEndAreaClear[世界号][区域] 的奖励表逐项发放；
每项 12 字节：类型、编号、数量，类型 −1 结束；类型 11 为勋章，0 单位，2 道具，5 商店上架）：
- 表世界 1–3（世界号 0–2，各 16 个区域：12 个普通区域与 4 个限时区域）每区域 50；里世界 1 / 2 / 3（世界号 9 / 10 / 11）每区域 50 / 80 / 100；
  里地图扩展页（里世界 4 起，ura_world.py 把奖励表写入区域记录）每区域 URA_PAGE_MEDALS。
- 原生表已有勋章项的区域把数量换为上列数值，原生数量更大者保持（表世界 1–3 的最终区域为 100，用户决定保留）；
  没有的区域在商店上架项之前加入一项；单位、道具与商店上架项保持。
  奖励表副本建在宿主堆，各世界的区域指针数组改指副本。已通关的区域不补发。
"""
import struct

BASE = 0x10000000
SHOP_TABLE = BASE + 0x8fe6e8               # 原生勋章商店数据：+0x00 单位组合包（8 项 × 0x18），+0xc0 勋章数量（18 项）
PACK_FIRST = 10                            # 商品表中勋章包的起始序号
NATIVE_PACKS = (30, 90, 180, 330, 690, 1080, 1860, 3900)
PACK_FACTOR = 2
MEDAL_PACKS = {f'msd_{i:03d}_medalpack': n * PACK_FACTOR for i, n in enumerate(NATIVE_PACKS, 1)}
SUPPLIES = {'rumi': (23, 200000, 18), 'madoka': (24, 100000, 20)}      # 商品编号、MSP 价格、strMedal 中的商品名称序号
SUPPLY_PRICES = {f'msd_{number:03d}_{name}': price for name, (number, price, _) in SUPPLIES.items()}
SUPPLY_NAMES = {f'msd_{number:03d}_{name}': text for name, (number, _, text) in SUPPLIES.items()}
CONFIRM_TEXT = 17                                                      # strMedal：购买确认（商品名称、价格）
ZT = 9                                                                 # 原生语言编号：繁体中文
CONFIRM_ZT_NATIVE = '是否要以%s\n購買%？'
CONFIRM_ZT = '%s\n是否要以%s購買？'
MEDAL_SCENES = (115, 116, 117)
MODE_BUTTON, COCKPIT_BACK = 0x33c4, 0x36d8
BACK_PICTURE = 30
HIDDEN = -16384.0
LANGUAGE = 0x3d64

AREA_CLEAR_MEDALS = {0: 50, 1: 50, 2: 50, 9: 50, 10: 80, 11: 100}      # 世界号 → 每区域通关勋章
URA_PAGE_MEDALS = 100                                                  # 里地图扩展页（里世界 4 起）
RESULT_MEDAL, RESULT_SHOP = 11, 5
MAX_ROWS = 16                                                          # 原生结算队列（SetBattleEndStack）16 项


def native_text(p, table, index):
    """原生文字表（strShopTbl、strMedalTbl 等：每种语言一个指针数组）中当前语言的第 index 项。只读内存，可在 JNI 回调内使用。"""
    app = p.app_instance()
    language = p.word(app + LANGUAGE) if app else 0
    return p.string(p.word(p.word(p.symbols[table] + 4 * language) + 4 * index))


def reward_rows(rows, medals):
    """奖励表加入勋章项：已有勋章项时取原数量与 medals 中较大者，否则放在商店上架项之前（没有上架项时放在末尾）。"""
    rows = [(kind, ident, max(count, medals) if kind == RESULT_MEDAL else count) for kind, ident, count in rows]
    if not any(kind == RESULT_MEDAL for kind, _, _ in rows):
        at = next((k for k, row in enumerate(rows) if row[0] == RESULT_SHOP), len(rows))
        rows.insert(at, (RESULT_MEDAL, 0, medals))
    return rows


def pack_rows(rows):
    return b''.join(struct.pack('<3i', *row) for row in rows) + struct.pack('<3i', -1, 0, 0)


def ura_area_rewards():
    """里地图扩展页一个区域的通关奖励表（区域记录 +0x48，核心 msd_ura_world_version 3）。"""
    return pack_rows(reward_rows([], URA_PAGE_MEDALS))


class MedalRules:
    def __init__(self, p):
        self.p = p
        self.mode_button = p.symbols['_ZN7AppMain28GT_MedalShopModeChangeButtonEP17GENERAL_TASK_BASE']
        self.cockpit_button = p.symbols['_ZN7AppMain16GT_CockpitButtonEP17GENERAL_TASK_BASE']
        self.install_packs()
        self.install_confirm_text()
        self.install_area_rewards()

    def install_confirm_text(self):
        p = self.p
        slot = p.word(p.symbols['strMedalTbl'] + 4 * ZT) + 4 * CONFIRM_TEXT
        if p.string(p.word(slot)) != CONFIRM_ZT_NATIVE:
            raise RuntimeError('勋章商店的繁体中文购买确认文字与预期不符')
        p.put(slot, p.cstr(CONFIRM_ZT))

    def install_packs(self):
        p = self.p
        address = SHOP_TABLE + 0xc0 + 4 * PACK_FIRST
        if struct.unpack(f'<{len(NATIVE_PACKS)}i', p.read(address, 4 * len(NATIVE_PACKS))) != NATIVE_PACKS:
            raise RuntimeError('勋章商店数量表与预期不符')
        p.write(address, struct.pack(f'<{len(NATIVE_PACKS)}i', *(n * PACK_FACTOR for n in NATIVE_PACKS)))
        p.log('MEDAL_SHOP_PACKS', list(MEDAL_PACKS.values()), SUPPLY_PRICES)

    def native_rows(self, pointer):
        p = self.p
        rows = []
        while len(rows) < MAX_ROWS:
            row = struct.unpack('<3i', p.read(pointer + 12 * len(rows), 12))
            if row[0] == -1:
                return rows
            rows.append(row)
        raise RuntimeError('区域通关奖励表没有结束标记')

    def install_area_rewards(self):
        p = self.p
        table = p.symbols['ciBattleEndAreaClear']
        report = {}
        for world, medals in AREA_CLEAR_MEDALS.items():
            pointers = p.word(table + 4 * world)
            count = p.call('_Z10GetAreaNumi9WorldType', world, 0)
            for area in range(count):
                rows = reward_rows(self.native_rows(p.word(pointers + 4 * area)), medals)
                raw = pack_rows(rows)
                copy = p.alloc(len(raw))
                p.write(copy, raw)
                p.put(pointers + 4 * area, copy)
            report[world] = (count, medals)
        p.log('AREA_CLEAR_MEDALS', report, 'ura', URA_PAGE_MEDALS)

    def update(self):
        """勋章商店场景：模式切换按钮移出画面，BACK 居中。任务每次进入场景重新建立，位置在建立后的第一帧改写。"""
        p = self.p
        app = p.app_instance()
        if not app or p.word(app + 0x22bc) not in MEDAL_SCENES:
            return
        button = p.word(app + MODE_BUTTON)
        if not button or p.word(button) != self.mode_button:
            return
        x = struct.unpack('<f', p.read(button + 0x84, 4))[0]
        if x == HIDDEN:
            return
        back = p.word(app + COCKPIT_BACK)
        if back and p.word(back) == self.cockpit_button and p.word(back + 0x50) == BACK_PICTURE:
            back_x = struct.unpack('<f', p.read(back + 0x84, 4))[0]
            p.write(back + 0x84, struct.pack('<f', (back_x + x) / 2))
        p.write(button + 0x84, struct.pack('<2f', HIDDEN, HIDDEN))
