# 模组 M5：本体与模组提供的世界与关卡（2026-10-10，宿主，核心保持 r40）

依据：`docs/modding/MOD_SYSTEM_TASK_2026-10-09.md` 第 5 节 M5（世界/关卡由本体或模组提供；扩展世界界面在用户完成世界 4 / 里世界 4 规划后再显示）。正式版 HEAD `6bdf08e`，核心 `MSD_Core_LAB_r40_20261010.dll` 未改。

## 1. 内容来源与格式

| 来源 | 位置 | 资源 |
| --- | --- | --- |
| 本体 | `campaign_content/catalog.json`（schema 1，不变） | `assets` 登记文件名与 BLAKE2b-256 摘要（可为 `null`）；此前为 SHA-256 |
| 模组 | `mods/<文件夹>/campaign/*.json`，`mod.json` 的 `content` 写 `"campaign": "campaign/"` | 不写 `assets`；战场图集 `.obm` 与音乐 `.msdf` 放在模组 `assets/`（文件名以 `<模组 id>_` 开头），按文件名引用 |

每个模组片段文件可含 `scenes`、`music`、`worlds` 三个列表（字段格式见 `docs/CONTENT_AUTHORING.md`），同一模组的多个文件按文件名顺序合并。

规则：

1. 模组定义的世界、区域、关卡、场景、音乐的键须以 `<模组 id>.` 开头。
2. 引用（关卡的场景与音乐、敌军与奖励单位、世界/区域/关卡的 `requires`、场景图集与音乐文件）只能指向本体、本模组与 `depends` 中的模组；原版场景（0–137）、音乐（SoundID）与单位（1–399）以整数引用。本体目录不能引用模组内容。
3. 本体与已载入模组按加载顺序合并后整体校验：键唯一、场景 4096 / 关卡 100000 容量、解锁条件无循环、资源大小。
4. 某个模组的关卡内容校验失败时，该模组整体跳过（含其单位与补丁），依赖它的模组随之跳过；原因记录在 MOD 页。本体与其他模组不受影响。
5. 进度按关卡稳定键保存于存档目录的 `campaign_progress.json`；停用模组不删除其关卡进度与奖励单位进度，重新启用后恢复。
6. 战场 ID（138 起）按合并顺序在每次启动时分配，不写入存档。

## 2. 实现

| 文件 | 变化 |
| --- | --- |
| `campaign_catalog.py` | `Catalog(root, units, mods=(), cache=None)`：本体目录加模组片段；记录每个键与资源的来源（`owner`、`asset_owner`）并按来源的可见范围检查引用；资源摘要改为 BLAKE2（`content_digest`）；`merge_scenes` 使用 `content.mod_campaigns`。无模组时 `raw` 与本体目录相同。 |
| `mod_loader.py` | `content.campaign` 读取片段（每项须为对象）；每个模组在单位与补丁检查之后，与本体及已接受模组一起构造 `Catalog` 试校验，失败即跳过；`load(..., campaign_root=None, campaigns=None)` 按加载顺序返回已接受的片段；状态增加 `campaign`（世界、区域、关卡、战场、音乐数量）。 |
| `community_content.py` | `load_mods` 传入 `campaigns=self.mod_campaigns`；模组 `assets/` 中只把 `.obm` 登记为单位资源、`.json` 为描述符，其他文件（如 `.msdf`）由世界目录按引用读取。此前模组 `assets/` 中出现任何非 OBM 文件都会使启动报错（M3 遗留问题）。 |
| `mod_page.py` | 详情增加一行“世界 n 個・關卡 n 個・戰場 n 個・音樂 n 首”。 |
| `content_tool.py` | `validate` 不再要求 `core_runtime.json` 的 `sha256`（第 88 节记录的问题），可加 `--enable <模组 id ...>` 校验合并结果，输出合并后的 BLAKE2 内容摘要；`import-music` 输出 `blake2b`。 |
| `content_assets.py` | `import_png` 输出 `blake2b`。 |
| `tests/test_content_interfaces.py` | 新增 `test_mod_campaign_fragment`。 |

`community_campaign.py`（选关、建 Mission 表、战斗、结算、进度事务）未修改：模组关卡经合并目录进入同一路径。

## 3. 验证（`verification/m5_20261010/`，隔离存档，未计算 SHA-256）

- 测试模组（`make_mods.py`）：`worldmod`（自有 700×240 战场 PNG 导入的 OBM、音乐、单位 `worldmod.scout`；关卡 2 需要关卡 1，首胜奖励 `worldmod.scout`）、`world_addon`（依赖 worldmod，引用其战场、音乐、单位与关卡）、`quiet_world`（未启用）及 12 个各违反一条规则的模组与 1 个依赖失败模组的模组。
- 离线 `check_offline.py`：32/32 通过（`offline_checks.json`）——16 个模组的状态与原因、片段顺序、合并结果、资源来源、模组单位 ID、无模组时目录与摘要不变、依赖顺序与缺失、本体示例世界与模组的双向可见范围。
- 运行 `run_campaign.py`（核心 r40，开发预览 `ui_enabled=True`，三阶段共用状态目录）：
  - `play` 21 项：模组载入与世界列出、战场 ID 138、关卡 2 与附加世界初始锁定；模组关卡 1 使用模组战场与音乐（Mission 场景 138、音乐槽 1031）、胜利结算与进度写入；关卡 2 解锁并胜利、首胜奖励模组单位（UnitID 2048）；附加模组世界解锁、使用 worldmod 的战场与音乐并胜利。
  - `off`（停用全部模组）6 项：无模组世界；三关进度与奖励单位进度保留；本次运行未改写 `campaign_progress.json`。
  - `on`（再启用）8 项：世界恢复、进度保留、奖励单位重新拥有、解锁状态恢复。
- 截图：`runs/play_*/screens/`（自制战场上的模组敌军、附加世界关卡），`runs/detail_*/screens/00292_detail_worldmod.png`（MOD 页详情）。
- 回归：单元测试 5 项（不含经 SHA-256 联机指纹的 `test_large_catalog`）；M3 离线 19/19、M3 运行 7 项；M4 MOD 页 14 项；M5 前置探测（现行 `catalog.example` 路径在 r40 上选关、战斗、结算、进度）通过。

## 4. 限制与后续

- 扩展世界选择界面仍暂缓显示（第 19 节）；开发预览面板与结算后停留在女教官基地（场景 67）的行为沿用 2026-10-04 的接口，正式界面待世界 4 / 里世界 4 规划完成后设计。
- 模组只能使用自己 `assets/` 中的战场与音乐文件，或本体与所依赖模组的世界目录已登记的资源；依赖模组仅作为单位图集使用的文件不会因被引用而载入。
- 覆盖补丁仍只作用于单位；修改本体或原版关卡的补丁未支持。
- 本体世界目录仍为单一 `catalog.json`。
- 旧联机指纹（`online_session.fingerprint`）包含合并后的目录；联机按 Rollback 任务书另行设计。
- 关卡强化倍率（任务书第 10.3 节）与敌军 Lv41–50（第 10.2 节）未在本阶段实施。
