# metal slug defense on Windows ported edition

## English

This Windows port is based on the Android version of **Metal Slug Defense 1.46.0**. The game core is statically recompiled for Windows x64, with local adaptations for graphics, audio, input, and saving.

This edition adds keyboard controls and a **16:9 layout**. Expanded backgrounds and adjusted interface positions preserve the original proportions and visible content. Borderless fullscreen is enabled by default.

**Stamina regenerates at 1 point per second.** The original Android version regenerates 1 point per minute.

**Update 26.10.1**

- The version number changes to 26.10.1, separating this edition from the official version numbering. The naming follows the year-based scheme Minecraft adopted in 2026, and later versions use the same scheme.

**Update 1.47.3**

- Now you can play all EVENTS just like decade ago
- Historical EVENTs now use the original EventMSD event map, prisoner screen and shops, entered through an EVENT browser page with 13 separate entries (Part 1/Part 2 entries share progress).
- Units sold for medals during each EVENT are available in that EVENT's own shop (bottom SHOP in the instructor base) after the original unlock condition is met; they are no longer mixed into the normal shop.
- The bottom-bar buttons and panels used for EVENTs show the native press highlight, kept until the shutter closes, and the LAB button stays visible while the shutter opens and closes.

**Update 1.47.2**

- Added local two-player versus mode with keyboard/controller support (default controller layout: Xbox 360).

**Update 1.47.1**

- Added AI BOT difficulty levels for use in LAB.

**Update 1.47.0**

- Added an independent fully unlocked maximum-level save profile, including all available units, maximum army and base upgrades, and all POW effects from Maps 1, 2, and 3.
- Added LAB for extensively customizable battles, with available units determined by the player's unlock progress.

LAB documentation: [LAB fixes](docs/LAB_BUGFIX_2026.10.07.md), [LAB menu entry](docs/LAB_MENU_ENTRY_2026.10.07.md), and [LAB and title visuals](docs/LAB_VISUAL_TITLE_2026.10.07.md).

**Update 1.46.4**

- Updated two distinct Mummy variants and the Mummy Summoning Box.

**Update 1.46.3.1**

- Added seven Regular Army infantry units: **Regular Army Shield Soldier**, **Regular Army Rifleman**, **Regular Army Bazooka Soldier**, **Regular Army Gatling Soldier**, **Regular Army Paratrooper**, **Regular Army Rocket Bomb Soldier**, and **Regular Army Mortar Soldier**.
- Corrected parameter selection for retained weapons used by Marco, Fat Marco, Tarma, Fat Tarma, Eri, Christmas Eri, Fio, Fat Fio, and Christmas Fio. Subsequent ranged normal attacks use each character's native special-weapon damage, range, and hit behavior; Fat Eri's existing laser revision passed regression checks.

**Update 1.46.2**

- Added a selector for historical MSD Event missions.
- Enabled acquisition of Event units through the corresponding Event shops and POW rewards.
- Added three units: **DI-COKKA MK.II**, **DI-COKKA MK.III**, and **GIRIDA-O MK.II**.
- Fixed misaligned sprite pixels on **HEAVY B (Future)**.
- Added independent music and sound-effects controls.
- Restored native stationary-laser parameters and bounded damage for Fat Eri's enhanced normal attack, preserving the large-laser visuals.
- Events without a registered shop now hide SHOP in the base and map. Registered Event shops retain their catalog and exchange flow; ordinary unit shops retain native prices.
- Revised status-report file-lock exception handling and the rendering-thread release order on exit.

Level-unlock details: [level unlock verification](docs/UNIT_LEVEL_UNLOCK_2026.10.05.md).

**Update 1.46.1**

- Fixed persistent sprite flickering and body-part misalignment affecting Sol Dae Rokker and its enraged variant.
- Added three independent units: **NOP-03 SARUBIA (Future)**, **M-15A (Future)**, and **HEAVY B (Future)**.

### Controls

| Key | Action |
| --- | --- |
| `1`–`9`, `0` | Deploy the unit in deck slots 1–10, respectively. The numeric keypad is also supported. |
| `Space` | Activate special attacks for all friendly units whose specials are ready, indicated by the blue glow. |
| <kbd>&#96;</kbd> (backtick) | Upgrade AP production. |
| `-` | Launch the Metal Slug attack when charged. |
| `=` | Attempt to deploy each of the ten deck slots from left to right. Continue through the remaining slots when a unit is unaffordable or on cooldown. |
| `F11` / `Alt+Enter` | Switch between borderless fullscreen and windowed mode. |
| `F9` | Toggle mute. |
| `Esc` | Back; pause or resume a battle. |
| `F12` | Save a screenshot. |
| `Alt+F4` | Close the game. |

Mouse controls remain available. Deployment and special attacks follow the game's AP, cooldown, readiness, unit-limit, and pause conditions.

### Run

Open the [project page](https://github.com/sprievs7up/metal-slug-defense-on-Windows-ported-edition), click the green **Code** button, and select **Download ZIP**. Extract the entire archive, open the extracted project folder, and run **MSD WINDOWS S1XLV.exe**. Windows 10/11 x64 is required; the runtime is bundled.

The normal, all-units Lv1, fully unlocked maximum-level, and LAB EXE launchers share the supplied application icon. Both original 512×512 PNG designs and a 192×192 PNG version are retained under `custom_content/`; the active design is `LOGOAPP2.png`. [Windows icon resources and launchers](docs/WINDOWS_APP_ICON_2026.10.08.md).

The package starts with an initial save. Units can be purchased with medals, and the original daily and event reward paths are preserved. Save files are created in `play_save/`; existing personal progress is excluded from the distributed package. Full campaign coverage and long-term stability remain under evaluation.

To update an existing installation, close the game, back up all existing `play_save*/` folders, extract the new package into a separate folder, and copy those complete save folders into it. The existing save format remains compatible; initial seeds are used only when the corresponding save does not exist.

### Optional all-units Lv1 save

Run **Start_MSD_All_Units_Level1.exe** from the extracted game folder; the corresponding VBS entry remains available. This entry uses the same formal game core and creates an independent save in `play_save_all_units_level1/` on first launch. The normal EXE continues to use `play_save/`; an existing local maximum-level launcher retains its separate save.

The preset owns all 399 original units and the 13 currently registered playable community units at **Lv1**. All nine upgrades under the native army/base customization menu also start at **Lv1**. Maps retain initial progress, no stages are cleared and no prisoners are collected; later stages and worlds require progression. Currency, items and the initial deck follow the formal initial save. World progression and faction-core level limits remain active.

Subsequent launches preserve upgrades, map progress and settings. To use this profile in a new installation, copy its entire `play_save_all_units_level1/` folder. The preset files under `game_data/all_units_level1/` are distributed independently of personal saves.

### Optional fully unlocked maximum-level save

Run **Start_MSD_All_Unlocked_Max_Level.exe**; the corresponding VBS entry remains available. On first launch, this entry creates `play_save_all_unlocked_max_level/` with all **399 original unit records (UnitIDs 1–399) and 17 playable community units at Lv40**, all **nine army/base upgrades at Lv30**, and all six faction cores owned. Maps 1, 2, and 3 have their stages unlocked and cleared, with all **48 area prisoner rewards at 100%**. Historical Event progress follows the initial profile.

This entry shares the current formal core and preserves its independent progress on subsequent launches. Existing normal and maximum-level saves retain their own directories. To migrate this profile, copy the entire `play_save_all_unlocked_max_level/` folder. Preset files are distributed under `game_data/all_unlocked_max_level/`; implementation and validation scope are recorded in [the profile report](docs/ALL_UNLOCKED_MAX_LEVEL_2026.10.07.md).

### Content authoring and networking interfaces

Configurable worlds, registered community enemies, independent scenes and music are documented in [CONTENT_AUTHORING.md](docs/CONTENT_AUTHORING.md). The unfinished world selection interface is temporarily hidden, and `F6` does not open it. The default catalog is empty; the supplied example can be installed with the authoring tool for development.

The self-hosted room and transport preparation is described in [ONLINE_INTERFACE.md](docs/ONLINE_INTERFACE.md). In-game multiplayer battle synchronization remains under development.

## 中文

本项目基于安卓原版 **《合金弹头塔防》（Metal Slug Defense）1.46.0**，将游戏移植至 Windows。游戏核心通过静态重编译生成 Windows x64 代码，并适配本地的图形、音频、输入与存档功能。

本版本新增键盘操控系统，并将画面调整为 **16:9 布局**。通过扩展背景与调整界面位置，保持角色及素材的原有比例，并保留原画面的可见内容。默认采用无边框全屏模式。

**体力每秒恢复 1 点。** 安卓原版的恢复速率为每分钟 1 点。

**26.10.1 更新**

- 版本号改为 26.10.1，与原版官方的版本体系区分；命名方式参照 Minecraft 于 2026 年启用的新命名方式，后续版本沿用。

**1.47.3 更新**

- 你现在可以游玩所有的EVENT了
- 历史 EVENT 改用原版活动地图、人质页面与商店，并由 EVENT 浏览页进入，共 13 个独立入口（第一部分与第二部分共享进度）。
- 各 EVENT 期间以勋章出售的单位，改在该 EVENT 的独立商店（女教官基地底栏 SHOP）中购买，满足原版开售条件后开放，不再与普通商店混在一起。
- EVENT 相关的底栏按钮与面板显示原生按压反馈，并保持至闸门合拢；LAB 按钮在开闸与关闸过程中保持显示。

**1.47.2 更新**

- 新添加本地双人对战功能，可使用键盘/手柄进行对战（手柄操作默认XBOX360操作模式）

**1.47.1 更新**

- 加入了不同等级的AI BOT以在LAB中使用

**1.47.0 更新**

- 新增全解锁满级独立存档入口，涵盖全部可用单位、满级我方阵营与基地强化，以及地图 1、2、3 的全部人质效果。
- 增加LAB 实验室功能，玩家现可以直接高度自定义对战内容（取决于你解锁的单位）

LAB 功能说明：[LAB 修复记录](docs/LAB_BUGFIX_2026.10.07.md)、[LAB 菜单入口说明](docs/LAB_MENU_ENTRY_2026.10.07.md)、[LAB 与标题视觉修订](docs/LAB_VISUAL_TITLE_2026.10.07.md)。

**1.46.4 更新**

- 更新两种不同的木乃伊以及木乃伊召唤箱

**1.46.3.1 更新**

- 新增七种正规军小兵：**正规军盾牌兵**、**正规军步枪兵**、**正规军反坦克兵**、**正规军加特林机枪兵**、**正规军伞兵**、**正规军冲天火箭弹兵**及**正规军迫击炮兵**。
- 修复马可、胖马可、塔玛、胖塔玛、英里、圣诞英里、菲欧、胖菲欧及圣诞菲欧保留武器时的参数选择错误。后续远程普攻沿用各自原生特殊武器的伤害、范围及命中行为；胖英里的既有激光修订通过回归检查。

**1.46.2 更新**

- 新增 MSD 历史 Event 任务选择功能。
- 支持通过对应 Event 商店及捕虏奖励获取活动单位。
- 新增三个单位：**基 · 寇卡坦克 MK.II**、**基 · 寇卡坦克 MK.III**、**吉利塔 · O MK.II**。
- 修复**未来重装 B 型**的像素错位问题。
- 新增音乐、音效独立开关。
- 修复胖子英里强化普攻的大激光参数，恢复原生静止激光与受限伤害行为，保留大激光显示。
- 未登记商店的 Event 隐藏基地与地图 SHOP；已登记商店保留目录与兑换流程，普通单位商店保留原生价格。
- 修订状态报告文件锁异常处理及退出时的渲染线程释放顺序。

等级解锁规则见 [等级解锁修复记录](docs/UNIT_LEVEL_UNLOCK_2026.10.05.md)。

**1.46.1 更新**

- 修复索尔罗卡（Sol Dae Rokker）及其愤怒版持续出现的贴图闪烁与身体部件错位问题。
- 新增三个独立单位：**爆竹红（未来）**、**M-15A 型（未来）**、**未来重装 B 型**。

### 按键操作

| 按键 | 功能 |
| --- | --- |
| `1`–`9`、`0` | 分别出击编队第 1–10 个槽位的单位；支持数字小键盘。 |
| `空格` | 使所有绝招已就绪的友方单位发动绝招，就绪状态以蓝光表示。 |
| <kbd>&#96;</kbd>（反引号） | 升级 AP 生产。 |
| `-` | 在充能完成后发动弹头车攻击。 |
| `=` | 从左至右依次尝试出击全部十个槽位；遇到 AP 不足或冷却中的单位时，继续尝试后续槽位。 |
| `F11` / `Alt+Enter` | 切换无边框全屏与窗口模式。 |
| `F9` | 切换静音状态。 |
| `Esc` | 返回；在战斗中暂停或恢复。 |
| `F12` | 保存截图。 |
| `Alt+F4` | 关闭游戏。 |

保留鼠标操作。出击与绝招均遵守游戏的 AP、冷却、就绪状态、单位数量上限及暂停条件。

### 运行方法

在[项目主页](https://github.com/sprievs7up/metal-slug-defense-on-Windows-ported-edition)点击绿色 **Code** 按钮，选择 **Download ZIP** 下载压缩包。完整解压后，打开解压得到的项目文件夹，启动 **MSD WINDOWS S1XLV.exe**。适用于 Windows 10/11 x64，运行依赖已随包提供。

普通、全兵种 Lv1、全解锁满级及 LAB 的 EXE 入口统一使用用户提供的应用图标。两份 512×512 PNG 原稿与 192×192 PNG 版本保留在 `custom_content/`，当前采用 `LOGOAPP2.png`。实施与资源规格见 [Windows 应用图标与入口说明](docs/WINDOWS_APP_ICON_2026.10.08.md)。

分发包采用初始存档，玩家可以使用勋章购买单位；原版每日奖励、活动奖励及对应解锁流程均保留。个人进度保存在 `play_save/`，分发包不包含已有个人进度。全关卡覆盖与长期运行稳定性仍需持续验证。

更新已有安装时，请先关闭游戏并备份所有已有的 `play_save*/` 存档目录，将新运行包解压至独立目录，再将这些完整存档目录复制至该目录。现有存档格式保持兼容；初始种子仅在对应存档不存在时使用。

### 全兵种 Lv1 可替代存档

在解压后的游戏目录中启动 **Start_MSD_All_Units_Level1.exe**，对应 VBS 入口继续可用。该入口使用同一正式版核心，首次启动时在 `play_save_all_units_level1/` 创建独立存档。普通 EXE 继续使用 `play_save/`；本地既有满级入口继续使用其独立存档。

该预设包含全部 **399 个原版兵种及当前登记的 13 个可用社区兵种**，均已拥有且初始为 **Lv1**。“我方阵营”的 **9 项强化均为 Lv1**。地图采用初始进度，关卡均未通关、捕虏均未收集，后续关卡及世界按游戏规则逐步解锁。货币、道具及初始编队沿用正式版初始存档。世界进度与军队核等级上限继续生效。

再次启动时保留已经完成的升级、地图进度及设置。迁移至新安装目录时，复制完整的 `play_save_all_units_level1/`。预设文件位于 `game_data/all_units_level1/`，发行文件与个人进度分别保存。

### 全解锁满级独立存档

启动 **Start_MSD_All_Unlocked_Max_Level.exe**，对应 VBS 入口继续可用。首次启动时在 `play_save_all_unlocked_max_level/` 创建独立存档，包含全部 **399 个原版单位记录（UnitID 1–399）和 17 款可选社区单位，均为 Lv40**；“我方阵营”的 **九项基地强化均为 Lv30**，六阵营核心全部持有。地图 1、2、3 的关卡开放并完成通关，**48 项区域人质奖励效果均为 100%**。历史活动进度沿用初始预设。

该入口共用当前正式版核心，后续启动保留该独立存档的游戏进度。既有普通入口和原满级入口继续使用各自存档目录。迁移时复制完整的 `play_save_all_unlocked_max_level/`；预设位于 `game_data/all_unlocked_max_level/`，实施与核验范围见 [独立预设说明](docs/ALL_UNLOCKED_MAX_LEVEL_2026.10.07.md)。

### 内容制作与联机预备接口

世界、社区敌军、独立场景和音乐的配置流程见 [CONTENT_AUTHORING.md](docs/CONTENT_AUTHORING.md)。尚未完成的世界选择界面暂时隐藏，`F6` 暂不打开该界面。默认目录保留空世界列表，示例通过内容制作工具安装用于开发。

自有服务器的房间与传输接口见 [ONLINE_INTERFACE.md](docs/ONLINE_INTERFACE.md)。游戏内双人战斗同步保留后续开发状态。

