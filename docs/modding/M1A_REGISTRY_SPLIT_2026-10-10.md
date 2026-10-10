# M1a：注册表拆分、容量与 ID 映射、单位目录（2026-10-10）

依据：`MOD_SYSTEM_TASK_2026-10-09.md`、`M0_SPEC_AND_BOUNDARIES_2026-10-09.md`（第 2、3、5–7 节）。HEAD `6bdf08e`，核心 r35（本阶段不改核心）。M1a 只修改宿主；多页图标（改核心、重建 DLL）与 500–4096 个测试单位的完整验证属于 M1b。

## 1. 内容组织

- `community_content/registry.json`（schema 2）拆分为：
  - `community_content/content.json`（schema 3）：`unit_id_ranges`（本体 1024–2047、模组 2048–5119）、`unit_ids`（本体稳定键 → UnitID，只追加、不重排）、`units_dir`、`asset_digest`（`blake2b-256`）、`assets`、`unit_pack`（不含 `shop_id`）。
  - `community_content/units/<名称>.json`：每个本体单位一个文件，字段与键顺序沿用原记录；不写 `id` 与 `icon.index`，写了即拒绝加载。
- 加载器 `community_content.load_manifest` 把两者组装为原 schema 2 结构的内存清单：按 UnitID 排序，补回 `id`、`icon.index = 340 + (UnitID − 1024)`、组合包 `shop_id`。其他模块（`lab*`、`community_maps`、`campaign_catalog`、联机指纹）继续读取同一结构。
- 单位文件新增可选字段 `tags`（字符串列表）。来源（本体 `body` / 模组 id）由加载器记录在 `CommunityContent.unit_source`，不写入清单。
- 迁移脚本：`verification/m1a_20261010/migrate_registry.py`；原文件保存在同目录 `before/registry.json`。

## 2. 容量与编号

| 项目 | 迁移前 | M1a |
| --- | --- | --- |
| 单位数量常量 | `MAX_UNITS = 64` | 取消；由 `unit_id_ranges` 决定（槽位编号以 int16 写入原生表，上限 1024+32000） |
| UnitID | 必须按注册顺序连续 `1024+i` | 由 `unit_ids` 指定，可有空位 |
| 空位 | 不支持 | 占位记录（“未启用”）：复制原版 UnitID 2 的数据行、动作类与描述符，内部单位标记，名称“-”，不被拥有，不进商店与编队，商城许可关闭 |
| 已拥有单位紧凑列表 | 固定 512 个 int32 | `max(512, 400 + 槽位数)`，头部字段 40 传入实际值 |
| 组合包商店 ID | `512 + MAX_UNITS`（576） | 槽位数 ≤ 64 时仍为 576；超过时为 `512 + 槽位数`，避开单位商店 ID `512 + 槽位` |
| 资源摘要 | SHA-256，每次启动全部计算 | BLAKE2b-256，按“大小 + 修改时间”缓存于 `%LOCALAPPDATA%\MSD_WINDOWS_S1XLV\content_digests.json`（`MSD_CONTENT_DIGEST_CACHE` 可改路径，空值停用）；原为 null 的资源仍不核对 |

组合包商店 ID 可以移动的依据：`src/community_content.cpp` 中原生商店存档接口（`Set/IsMenuShopEnableSaveData`、新品标记）对组合包与社区单位均被钩子拦截，组合包状态由成员拥有情况推导，不写入原生存档。

## 3. ID 映射

- 本体：`content.json` 的 `unit_ids`，固定。本体 ID 不可移动：存档进度（`community_progress.json`）记录了 ID，加载器发现不一致会按原规则拒绝。
- 模组：`content_ids.ModIdMap`（`%LOCALAPPDATA%\MSD_WINDOWS_S1XLV\mods_ids.json`，`MSD_MOD_ID_MAP` 可改路径）。已有映射保持；新键优先使用调用方给出的候选 ID（例如存档进度记录的 ID），否则取模组区段内最小空闲 ID；停用模组的映射保留，重新启用时恢复。M3 的模组加载器接入后使用。

## 4. 单位目录 `unit_catalog.py`（只读部分）

- `catalog(p)` 返回进程内共用实例。`index()` 生成条目（稳定键，原版为 `original.<UnitID>`；UnitID、来源、阵营、名称、拥有、等级、开放等级、AP、商店 ID、价格、是否解锁、标签），按游戏语言缓存；购买、强化后调用 `refresh()`。
- `stats(uid, level)`（界面等级 1–40）经原生 `BattleInfo::getUnitStatus` 与 `getUnitCreateParams` 读取：HP、击退门槛、移动速度、AP、再出击等待、AP 返还、近距/远距开火距离，近战、普通、特殊三组攻击（是否具备、伤害、击退力、弹体距离、等待或冷却、属性、射程分类），以及沿用 LAB AI 公式的每秒伤害与综合强度。
- `list(filters, sort, descending, page, page_size, level)`、`detail(key, level)`、`compare(keys, level)`；筛选与排序项见模块说明。购买、强化等操作接口在 U1 实现。
- 已核实的原生字段：`BattleUnitStatus` 字 0 UnitID、字 2 内部等级，字 3 起与数据行状态词编号一致，字 48/49 为射程分类；`BattleUnitCreateParams` 字 0 AP、字 1 再出击等待；商品类型 2 为单位（`GetMenuShopUniqueID` 返回 UnitID），4 为组合包。
- LAB 选单位（`lab_prep.LabPrep.unit_list`）已改为读取目录，列表与迁移前逐项一致。

## 5. 验证（`verification/m1a_20261010/`，隔离存档，未写入任何个人存档，未计算 SHA-256）

- 离线 13 项（`check_manifest.py`）：组装清单与原 registry 除摘要值外完全相同、字段顺序、空位与组合包编号、非法 ID 拒绝、模组 ID 映射持久化与保留。
- 安装一致性（`dump_install.py`、`compare_dumps.py`）：迁移前加载器与新加载器各自完成原生安装后，社区头部、`.got/.data/.data.rel.ro/.data.rel.ro.local/.bss`、分配表逐字节相同；客体堆只有两处 2496 字节不同，为以启动时间为种子的原生随机数状态（种子差 6 秒，等于两次运行的启动间隔）。
- 运行 11 项（本体内容）：KT-21、白/绿木乃伊、基寇卡 MKII 的 Lv40 数值与既有参数记录一致；吉利塔、基寇卡 MKII、正规军步枪兵价格 30/30/15；内部单位排除；LAB 列表一致；进入主菜单。目录索引 395 条约 18 ms；4096 个合成条目的筛选、排序与翻页每次 1–4 ms。
- 运行 10 项（空位场景，仅运行副本把 KT-21 改为 UnitID 1100）：77 个槽位、57 个占位记录；占位记录未拥有、名称“-”、商城关闭、数值为 UnitID 2；移动后的 KT-21 数值与名称正确；组合包商店 ID 589、价格 150；商店目录不含占位槽位与 576；进入主菜单。
- 单元测试 3 项通过。`test_large_catalog` 与 `content_tool.py validate` 会经联机指纹计算 SHA-256，未运行。

## 6. 未覆盖与后续

- 原生商店、强化、编队界面在单位数量较多与组合包 ID 移动后的实际显示与购买（M1b 用批量测试单位验证）；紧凑列表大于 512 时原生遍历与 memset 长度（M1b）。
- 编队中引用了占位 ID 的格子：空位场景下存档编队仍保留原 ID（例如 1043）；按设计在 M4 处理（停用内容在内存中视为空格）。
- 原版 LAB 列表包含 36 个原生名称为“-”或空的单位（显示为“UID n”），属迁移前既有行为，本阶段保持不变。
- 历史生成脚本 `artwork/mummy_variants_20261005/integrate_units.py`、`artwork/kt21_20261006/integrate_kt21.py`、`verify_descriptor.py` 仍读写 `registry.json`，重新运行前需要改为 `content.json` 与 `units/`。
- `content_tool.py validate` 仍要求 `core_runtime.json` 的 `sha256` 字段（第 88 节记录的既有问题）。
- 两个固定运行目录：按用户决定，于 M1b 完成后与 M1b 一并同步（2026-10-10 完成，见 AGENTS 第 99 节与 `verification/m1b_20261010/deployment_*.json`）。同步时需新增 `content.json`、`units/`、`content_ids.py`、`content_digest.py`、`unit_catalog.py` 及 src 镜像，目标目录中旧的 `registry.json` 不再被读取。
