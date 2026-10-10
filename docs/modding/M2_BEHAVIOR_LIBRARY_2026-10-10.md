# M2：单位行为库（2026-10-10）

依据：`MOD_SYSTEM_TASK_2026-10-09.md` 第 4.2 节、`M0_SPEC_AND_BOUNDARIES_2026-10-09.md` 第 3.3 节。核心 r37 → **r38**（`MSD_Core_LAB_r38_20261010.dll`）。

用户确认的做法（2026-10-10）：先建立行为库框架、再参数化与泛化；适用的原版基类保持现状（以后有新单位需要时再扩展，每次扩展做原生分析与回归）；十类角色的“首次绝招后保留强化武器”纳入行为库；单位文件中原有的平铺写法全部迁移，不保留兼容。

## 1. 结构

- **唯一来源** `behavior_library.json`（根目录，`src/` 镜像）：每个行为有名称、版本、适用的原版基准单位（`base_classes`）、需要的字段或行为、参数表（类型 `unit_key`、`rational`、`int`、`int_list`，以及必填、默认值、范围）和中英说明。库版本 `library_version` 为 2。
- **核心嵌入**：`src/build.py` 把该文件原文生成 `src/behavior_manifest.inc` 编入核心，导出 `msd_behavior_manifest()`。加载器比较核心内嵌的清单与文件，不一致时拒绝启动，以免核心与数据不配套。
- **加载器** `behaviors.py`：校验单位文件中的 `behaviors` 列表，规则包括：行为存在且版本相同、基准单位在适用范围内、不重复、需要的字段与行为齐全、参数类型与范围正确、`unit_key` 指向的单位存在且内部/可选属性正确。校验通过后转换为原生安装使用的内部字段（`flame_interrupt`、`child_unit_key` 等）。单位文件直接写这些内部字段会被拒绝。
- **作者工具**：`content_tool.py list-behaviors` 输出文字清单；`--markdown <文件>` 生成中英行为目录 `docs/modding/BEHAVIOR_CATALOG.md`（由清单生成，不手工修改）。

## 2. 行为清单（库版本 2）

| 行为 | 适用基准 | 参数 | 来源（现有本体单位） |
| --- | --- | --- | --- |
| `build_structure` | 77 | `structure`（内部单位），`construction_time_multiplier` | 木乃伊召唤箱 MKII |
| `summon_units` | 64 | `unit`（可选单位），`interval_multiplier`、`interval_additional_multiplier` | MKII 箱体 |
| `spawn_child_unit` | 159、163 | `unit`（内部单位） | 正规军伞兵、迫击炮兵 |
| `para_drop_transform` | 160 | `landing_unit`（可选单位） | 正规军伞兵空降体 |
| `insect_swarm_release` | 61 | — | 绿木乃伊 |
| `recovery_slot` | 61（需精灵描述符） | `animation` | 绿木乃伊 |
| `flame_burst_interruptible` | 3（需精灵描述符） | `flame_start_tick`、`flame_ticks`、`alternate_knockback_animation`、`ending_bullet_animations` | KT-21 |
| `single_knockback_per_special` | 3（需上一项） | — | KT-21 |
| `ground_special_attack` | 3 | — | KT-21 |
| `retained_special_weapon` | 16、17、18、19、96、97、98、99、344、362 | — | 原版十类角色（新增：社区单位可用） |

数值倍率、经济、`status_word_values`、`attack_parameter_references`、`attack_attributes`、`sprite_descriptor` 等仍为单位文件中的普通字段，不属于行为。

## 3. 原生改动（r38）

- `msd_behavior_manifest()`：导出行为库清单。
- 保留强化武器：`src/aot_runtime.cpp` 的四处判定（脚本替换、丢枪效果、胖形态持枪帧、参数组替换）与胖英里激光，原来按原版 UnitID 写定，改为经 `msd_retained_class()` 取得角色类。原版十类角色为其自身 UnitID；社区单位在逐单位行为标记表（头部 +116）位 1 置位时取其基准 UnitID。位 0 仍为地面绝招。导出 `msd_community_retained_weapon_version()`。
- 诊断计数：头部 +140、+144 分别累计社区单位与原版角色的保留武器参数组替换次数，只计数，不影响行为。
- 其余行为原有的原生实现不变，参数原本就由逐单位参数表提供（喷火 8 词表、恢复槽表、落地目标表、显示目标表等）。

## 4. 迁移

- `verification/m2_20261010/migrate_behaviors.py` 把 7 个单位文件（KT-21、绿木乃伊、MKII、MKII 箱体、伞兵、伞兵空降体、迫击炮兵）的内部字段改为 `behaviors`。转换回的内部字段与原值逐项相同，没有新增默认值。原文件在 `verification/m2_20261010/before/units/`。

## 5. 验证（`verification/m2_20261010/`，隔离存档，未计算 SHA-256）

- 离线 21 项（`check_behaviors.py`）：行为库与 `src` 镜像一致；本体单位解析结果；15 类拒绝用例，覆盖基准不符、未知行为、版本不符、重复、缺参数、多余参数、整数越界、倍率越界、列表长度、内部/可选单位不符、未知单位键、缺少依赖行为、缺少字段、单位文件直接写内部字段；文字目录覆盖全部行为。
- 安装一致性（`dump_install.py`、`compare_dumps.py`）：迁移前加载器（r37 同步版，平铺字段的原单位文件）与新加载器在 r38 上分别完成原生安装，社区头部、数据段、GOT 与分配表逐字节相同；客体堆只有以启动时间为种子的随机数状态不同（`install_comparison_final.json`）。
- 运行回归：本体内容 10 项（含 KT-21、木乃伊三种、MKII、正规军单位的 LAB 战斗出兵）与 500 个测试单位 10 项在 r38 上通过；使用 r37（没有行为库导出）时加载器按设计拒绝启动。
- 保留强化武器（`make_retained_fixture.py`、`run_retained.py`，LAB，我方只有被测单位，自动绝招）：
  - 马可：原版 UnitID 16 参数组替换 78 次，带行为的克隆 76 次，不带行为的克隆 0 次。
  - 胖英里（激光路径）：带行为的克隆对据点的单次伤害值集合与原版相同（4、48、96、144），不带行为的克隆不同（48、101、450、498、1505）。

## 6. 后续

- 新单位需要把某个行为用到其他原版基准时，按“原生分析 → 扩展 `base_classes` → 回归”处理，并提升该行为的版本号或库版本。
- 行为参数的联机内容清单（M7）以行为名、版本与参数值计入。
- 模组加载器（M3）读取模组单位文件时使用同一套 `behaviors.apply` 校验。
