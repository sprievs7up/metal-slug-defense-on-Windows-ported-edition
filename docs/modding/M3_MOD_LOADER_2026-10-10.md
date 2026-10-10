# M3：模组加载器（2026-10-10）

依据：`MOD_SYSTEM_TASK_2026-10-09.md` 第 4.3、4.4、4.8 节，`M0_SPEC_AND_BOUNDARIES_2026-10-09.md` 第 2、3 节。核心保持 r38（本阶段只改宿主）。用户确认：覆盖补丁先支持本体与模组单位，修改原版 1–399 号单位的补丁需要核心改动，作为 M3b。

## 1. 约定

- **目录**：游戏根目录 `mods/<文件夹>/mod.json`（`MSD_MODS_DIR` 可改）；`mods/README.md` 为中英简要说明。
- **启用与加载顺序**：`%LOCALAPPDATA%\MSD_WINDOWS_S1XLV\mods_enabled.json` `{"schema":1,"enabled":[...]}`（`MSD_MODS_ENABLED` 可改）。文件不存在时不启用任何模组；M4 的 MOD 页写入该文件，启停于重启后生效。
- **`mod.json`**：`schema` 1、`id`（小写字母开头，2–32 位小写字母、数字、下划线；`s1xlv`、`original`、`body`、`test` 保留）、`version`（点分整数）、`name`（语言 → 文本）、`author`、`license`，可选 `game_version`、`behavior_library`（版本约束，如 `">=1.47, <2"`）、`depends`（`{"id","version"}`）、`conflicts`、`content`（本阶段支持 `units`、`patches`）。
- **单位**：文件格式同本体单位文件；稳定键须为 `<模组 id>.<名称>`；不写 `id` 与 `icon.index`。UnitID 在模组区段 2048–5119 内由 `content_ids.ModIdMap` 分配并持久化（优先沿用存档进度记录的 ID），停用后保留，重新启用时恢复。
- **资源**：`assets/` 下文件名须以 `<模组 id>_` 开头（不能与本体、原版或其他模组重名，也就不能替换它们）。`.obm` 为图集，`.json` 为精灵描述符。单位可按文件名引用本体资源和原版游戏资源（例如 `marco_out.obm`），原版素材不需要也不应复制进模组。
- **可见范围**：模组单位与补丁只能引用本体单位、本模组单位与所依赖模组的单位。
- **覆盖补丁** `patches/*.json`：`[{"target": 稳定键, "field": 字段, "value": 值}]`。字段限数值倍率（生命、击退门槛、伤害、绝招伤害、移速、射程、受击后退、弹道、攻击等待、弹体距离、绝招冷却、生产间隔）与经济（`ap`、`shop_price`）；按加载顺序应用，同一字段后加载者生效，全部记录在 `CommunityContent.mod_patches`。目标为原版单位（`unit:<id>`）的补丁由 M3b 实现，见 `M3B_ORIGINAL_UNIT_PATCHES_2026-10-10.md`。
- **失败处理**：清单错误、版本不符、依赖缺失或被跳过、冲突、单位或资源校验失败（与本体单位使用同一套检查：`check_unit`、`check_references`、`check_unit_assets`，以及行为库校验）时，该模组整体跳过；依赖它的模组随后跳过。原因记录在 `CommunityContent.mod_status`（供 MOD 页显示）与日志 `COMMUNITY_MOD`。本体内容不受影响。

## 2. 实现

- `mod_loader.py`：扫描、清单校验、依赖与冲突、单位与补丁校验、ID 分配、补丁应用，返回模组单位、资源路径、补丁记录与各模组状态（`loaded`、`skipped`、`disabled`、`missing`）。
- `community_content.py`：单位检查拆分为模块级函数 `check_unit`、`check_references`、`check_unit_assets`（本体与模组共用）；`CommunityContent.load_mods` 在本体清单之后合并模组单位与资源，重新分配图标页与组合包商店 ID；资源按路径读取（模组资源位于模组目录）；原版图集按需读取尺寸（`AssetDims`）；`unit_source` 为模组 id；模组单位的旧 ID 与当前不同时以当前为准（编队处理见 M4）。有模组时清单增加 `mods`（id 与版本，联机内容清单使用）。
- `unit_catalog.py`：条目的出击 AP 改取 `getUnitCreateParams`（原生 `GetMenuUnitCost` 不返回社区单位的出击 AP，模组测试中发现）。
- `content_tool.py check-mods [--mods 目录] [--enable id ...]`：离线校验模组目录，输出各模组状态、原因、单位与补丁（使用临时 ID 映射，不写存档与用户目录）。

## 3. 验证（`verification/m3_20261010/`，隔离存档，未计算 SHA-256）

- 测试模组（`make_mods.py`）：有效模组 `example_mod`（步枪兵改色单位引用本体图集、马可类单位引用原版图集并使用 `retained_special_weapon`、自带图标页、对本体步枪兵的价格与生命补丁）与 `addon_mod`（依赖前者并修补其单位 AP）；有效但未启用的 `quiet_mod`；以及 10 个各自违反一条规则的模组（JSON 错误、行为基类不符、资源前缀、依赖缺失、依赖被跳过的模组、冲突、游戏版本、修补原版单位、单位键前缀、缺少语言）；启用列表另含未安装的 `ghost_mod`。
- 离线 19 项（`check_mods.py`）：各模组状态与原因、模组单位与 ID、行为与补丁、资源；加载顺序改变后 ID 不变；停用模组后其 ID 保留、不分给其他模组；重新启用恢复原 ID；无模组时本体不变。
- 运行（`run_mods.py`，核心 r38）：模组状态与合并；单位目录（来源、AP 50、价格 20、被补丁的本体步枪兵价格 12）；原生勋章购买模组单位（扣 20 勋章并获得）；模组单位放入编队；LAB 我方出兵马可类模组单位、敌方出兵另一模组单位，马可类模组单位绝招后保留武器参数组替换 65 次；关闭时社区进度写入两个模组单位。重启运行：ID、拥有状态（Lv1 / Lv40）与编队保持，其余检查同样通过。
- 无模组：M2 同步版加载器与 M3 加载器（启用列表为空）原生安装逐字节相同（以时间为种子的随机数状态除外）；本体内容运行回归 10 项通过；M2 离线 21 项通过。

## 4. 后续

- M3b：修改原版单位的补丁（需要核心让原版单位也经过倍率处理）。
- M4：标题 OPTION 的 MOD 页（读写启用列表、显示 `mod_status`）；停用模组后编队与进度的保护与恢复。
- 本阶段模组内容类型为单位与补丁；关卡、地图（M5）与 EVENT（M6）在对应阶段加入 `content`。
