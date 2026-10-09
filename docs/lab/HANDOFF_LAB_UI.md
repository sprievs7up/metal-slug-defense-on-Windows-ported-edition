# LAB 交接说明（给 Claude Code，2026-10-06）

本文件供在本机运行的 Claude Code 接手 LAB（实验室）功能。完整设计、原生地址与历次实测记录见同目录 `lab_design_2026-10-06.md`（以下简称“设计文档”，章节号沿用）。

## 0. 工作约定（必须遵守）
- 只在正式版仓库 `F:\egg\github\metal-slug-defense-on-Windows-ported-edition` 开发；**禁止写入 `play_save*` 目录**（`play_save_max_level` 是用户的满级存档）。LAB 测试存档为 `lab_test_save`（满级存档副本）。
- `F:\egg\AGENTS.md` 为项目总规范，开工前阅读其文首摘要与第 2 节。
- 核心构建：在 `src` 目录运行
  `..\windows_runtime\python.exe build.py --library MSD_Core_LAB_rN_20261006.dll --no-activate`
  （N 递增；`--no-activate` 不改根目录与 src 的 `core_runtime.json`）。构建后把 `lab_launcher.py` 中 `LAB_CORE` 改为新文件名；LAB 启动器只为自己加载该核心，其他启动器不受影响。
- 便携 Python 的 `ctypes` 必须在 `portable_launcher`（由 `all_units_level1_launcher` 导入）之后导入，否则 `_ctypes` 加载失败。
- 运行：`windows_runtime\python.exe -B -I -S lab_launcher.py --windowed`（控制台可见异常）或双击 `Start_LAB.vbs`。菜单按 F7 进入 LAB 战斗，F5 退出。F12 截图到 `screenshots\`。
- 记录：`lab_probe.jsonl`（LAB 事件与采样）、`lab_player.log`、`lab_status.json`、`lab_launcher_error.log`。

## 1. 生成代码阅读要点
- 原生 ARM 代码静态重编译在 `src/generated/blocks_*.cpp`，块名 `b_<地址>`，客体地址 = so 偏移 + 0x10000000。符号用 `libAppMain.so`（`game_data/original.apk` 内 `lib/armeabi-v7a/`）的动态符号表解析。
- `add(c,x,~(k),1,true)` 等价于 `cmp x,#k`（结果 x−k）；`cond` 编号：1=EQ 2=NE 3=CS 4=CC 5=MI 6=PL 9=HI 10=LS 11=GE 12=LT 13=GT 14=LE（`src/aot_runtime.h`）。
- 钩子：`old=find_block(pc|1); register_block(pc|1, fn)`；fn 内可改寄存器后 `old(c)` 或直接设 `c.pc` 跳转；模拟调用为设置 r0–r3、`c.r[14]=返回块地址|1`、`c.pc=函数|1`（见 `src/audio_options.cpp`）。块地址必须是已存在的块起点。
- LAB 共享头 `0x1ffeb000`，魔数 `0x4c414231`（LAB1）：+4 功能位，+8 敌方队伍，+12 等待条补画状态。宿主 `lab.py` 的 `write_header()` 写入、离开时清零。0x1ffea000（音频）、0x1ffec000（扩展世界 EXT1）、0x1ffed000（活动）、0x1ffee000（社区）已被占用。

## 2. 当前状态（已实机验证）
- LAB 入口：绕过 Wi-Fi 菜单直接建立 GameMode 1 战斗（设计文档 8.1），“同步中”自动关闭，F5 可退出。
- 敌方由玩家控制：Q–P 出兵、`[` AP 升级、`]` 弹头车、`\` 全体绝招；F4/F3 敌我 AI 开关（原生 AUTO，含自动绝招），F8 完全控制（宿主层：据点满级、AP 每帧补满、冷却清零）。
- 敌方牌组支持原版与社区单位（`lab_config.json`，可写 UnitID 或社区 key）。
- 双方 HP 对称（清除 +981 本地免伤标记）。
- 敌方绝招光圈为红色（宿主层第二个 `BattleEffectRenderer`，`aurR.obm` 换色）——用户截图已确认。
- 敌方绝招等待条：核心钩子 N1，2026-10-06 自动截图确认敌方单位下方显示等待条。
- T1–T7、T9 已实现（2026-10-06，当前 LAB 核心 `MSD_Core_LAB_r7_20261006.dll`，`msd_lab_hooks_version`=4），见第 2.1–2.3 节；待办为 T8 准备界面。

### 2.1 T1–T5 实施记录（2026-10-06）
- 验证入口：`verification/lab_ui_20261006/lab_driver.py <时间线.json> [--core DLL]`，按战斗开始后的帧号注入出兵/点击/拖动/截图；存档为同目录 `save/`（`lab_test_save` 副本），屏蔽真实鼠标。截图位于 `shots/<时间线名>/`。
- T1（r2）：`onGameScreenTouchEnded` 本方未命中时以敌方队伍/成员再跑一遍原生遍历（模拟调用 `getInstance` 返回 0x1d7642；本方列表为空时在 0x1d764a 入口进入），命中则在 0x1d76d2 改用敌方控制器 vtable+0x98。头部 +16 敌方控制器、+20 敌方成员、+24 补遍状态。验证：有/无我方单位两种情况下只有被点击的敌方单位发动，我方与其他敌方单位不受影响（`shots/t1/`）。
- T2（r3）：按用户 2026-10-06 修订布局 `[我方 AP][我方弹头车]▌我方 3 格▐敌方 3 格▐[敌方弹头车][敌方 AP]`。drawUI 每帧作为嵌套调用执行 11 遍（底栏外 1 遍、敌方 AP 框 1 遍、9 个底栏片段），各遍以软件裁剪与仿射变换（统一缩放 0.88，以底栏上沿为基准）排布；glScissor 由 Python 宿主处理，嵌套调用中不可用，故裁剪在 `Graphics::drawImageS/fillRect` 钩子内按源矩形完成。敌方各遍换入敌方控制器与出兵栏状态（头部 +0x70，7 字）以及敌方出兵格图集（宿主以敌方控制器调用 `createGrahics`，结果存头部 +0x40）。触点在 `onUITouchBegan/Moved/Ended` 入口按片段换回原生坐标，敌方片段处理期间换入敌方状态、出口块后换回。每侧最大滚动 = (槽位数−3)×格距；1–0 / Q–P 出兵时自动滚动到该格。中间分隔条旋转 180°；开场（MISSION START）起即为分栏布局。验证：双方出兵格点击、各自拖动滚动、按键自动滚动、双方 AP 升级与弹头车按钮、30 FPS（`shots/t2*`、`shots/slug`、`shots/intro`）。
- 与原方案的差异：敌方半区在完全控制关闭时同样响应点击（与 Q–P、`[` `]` 按键一致；否则完全控制开启时敌方 AP 恒为 MAX，按钮无法使用）。
- T3（r4）：出兵格循环的 `setClip` 前（原生已提交背景批次）在本遍 3 格窗口叠约 36% 不透明的蓝/红色块；警示条为独立片段，格子、头像、数字在其后绘制，不受影响（`shots/t3/`，像素抽样确认底纹保留）。
- T4：由 T2 修订布局取代——右侧为可操作的敌方 AP 升级与弹头车按钮，显示敌方自身状态，不再绘制影子按钮。
- T5（r5）：`drawApBar` 以敌方控制器单独执行一遍：框体翻转到右下，框内文字带（“AP:”、暗色占位数字、“/”）以无字底纹覆盖镜像后不翻转地平移绘制，数字平移，最后叠约 38% 红色底。显示敌方当前 AP/上限；完全控制下显示 9999/9999（是否改为“∞”待用户定）（`shots/t5/`）。
- 尚未验证：普通关卡中加载 LAB 核心时的原版行为（所有新钩子在 LAB 头为 0 时直接回落原生块，未做实机截图对照）。

### 2.3 T9、T6、T7（2026-10-06，核心 r7，钩子版本 4）
- T9 存档隔离（宿主层，`lab.py` enter_sandbox/leave_sandbox，`lab_launcher.py` LabProbe.sandbox_open）：LAB 启动时快照内存中的主存档映像（app+0x3d08，0x5ab0 字节），离开时还原；LAB 期间原生对存档目录的写入改写到内存中的虚拟文件，原生保存后的读回校验由虚拟文件提供。宿主异常与启动中途失败时同样还原。验证（`shots/t9*`）：LAB 期间 1 次原生保存全部虚拟化，存档目录无新增文件；离开后存档映像与 LAB 前快照的差异仅为保存种子与校验和（对照：普通保存同样变化）及区域选择界面每秒递增的体力计数（对照：区域选择界面内同样递增）。
- T6 战斗中菜单（`lab_menu.py`）：GameMode 1 无原生暂停页，采用宿主自绘面板（trial_overlay.SurfaceOverlay）；打开时置 BattleGameMaster+0x1c 暂停战斗（原生不显示暂停界面），关闭时还原。行：完全控制、我方/敌方 AI 自动出兵、我方/敌方自动释放绝招、重新开始、退出 LAB、继续。Esc 打开/关闭，鼠标点击或 ↑/↓ + Enter 选择；打开期间其他游戏按键与触点不送入战斗。重新开始 = 离开后 45 帧再启动。验证（`shots/t6`）：暂停期间单位不移动，开关写入生效，重新开始回到战斗，退出后隔离解除。
- T7 自动出兵与自动绝招拆分（原生钩子，功能位 16）：`noukinAutoPlay` 中 0x1cc018（弹头车）、0x1cc04e（逐单位绝招检查）、0x1cc070（出兵决策）三处按头部 +0x30 禁用位跳过；宿主在任一开关开启时对该方 startAutoPlay。“自动出兵”含弹头车。验证（`shots/t7a`、`t7b`）：仅自动绝招时手动出的单位自动发动、无新增出兵；仅自动出兵时持续出兵、就绪绝招不发动。
- 原生 AUTO 开启时该方出兵格显示为灰色（原版 AUTO 表现）。

### 2.4 T8 准备界面与支援钩子（2026-10-06，核心 r8，钩子版本 5）
- 支援钩子（原生，功能位 32）：0x1cc761 处弹头车发动按头部 +0x34（低字节我方、次字节敌方）选择效果；0 弹头车出击，1 除据点外全员 HP 回满（u+776 ← u+772），2 全员绝招立即可用（u+800 ← 0）；非弹头车效果累加 +0x38 计数供宿主提示。新增选项时同时扩展 `src/lab_hooks.cpp` apply_support 与 `lab.py` SUPPORT_OPTIONS。验证（`shots/t8_support`）：HP 回满不含据点，绝招就绪，未出弹头车，计数 2。
- 准备界面（`lab_prep.py`，宿主自绘全屏面板）：F7 打开/关闭；Esc 返回上一页或关闭。内容：双方牌组各 10 格（点击选单位，±调整 Lv1–40，“全部等级”一括应用）、双方据点初始等级 0–10、地图（原生联机地图表 0x108fd730+48 起，读至非 4 位 StageID 为止）、双方支援、完全控制与四个 AI 开关、预设 A/B/C、战斗履历。设定写入 `lab_config.json`（新增 player_deck、player_base_level、enemy_base_level），预设与履历在 `lab_presets/`（preset_X.json、history.jsonl）。
- 单位选择器：原版 1–399（排除原生名称带括号或为“-”的内部子单位，如“(沙包)”“(伞兵)”“(木乃伊召唤箱)”）与社区可选单位（用户确认内部子单位不可选择）；标签页：全部/社区/正规军/叛军/普特曼军/火星人/其他/联动（GetUnitAffiliation 0–5，依成员核对）。名称取 GetMenuUnitName(uid, app+0x3d64 当前语言)，原生只有 1–10 号语言（9 繁体中文，无简体），空名称回落英语（3）。用户确认保持原生繁体中文名称，不增加简体对照表。同一牌组内重复选择时两格互换（原生 entryUnit 会略过重复单位）。
- 开战：player_deck 非空时以 BattleController::entryUnit 按槽位写入我方牌组与等级，取代 BattleStartSetUnit，不读存档等级；据点等级在首个对战帧以原生 actionKyotenLevelup 逐级提升（AP 上限、回复量、升级成本随之更新），随后还原扣除的 AP；完全控制开启时仍为据点 MAX。退出 LAB 与战斗结束后回到准备界面并追加一条履历（胜方由双方据点 HP 判定）；“重新开始”不经准备界面。
- 用户实机反馈修订（同日）：
  - 音效消失的根因（已验证）：原生 BattleStartAndCompleteEffectScene::update（MISSION COMPLETE）与 BattleFailedEffectScene::update（MISSION FAILED）经 FrameworkInstance::blockRequest 调用 Sound_AddRequestBlock，屏蔽音效请求（app+38656+216，实测完成演出中由 0 变为 3），原生由之后的 SC_BattleEnd → Sound_InitRequestBlock 解除。LAB 跳过 SC_BattleEnd，只要有一场战斗自然结束（据点被毁），之后每场音效都被屏蔽；指令退出不触发演出，故自动测试曾未复现。`leave()` 补做 Sound_InitRequestBlock 后，实测离开时屏蔽位回到 0。
  - 准备界面改用原生素材（`lab_prep.py` PrepSkin）：menuparts.obm 标题栏、按钮（棕/米色/绿/红，九宫格缩放）、行框与 OK/BACK 图标按钮，popup.obm 面板，unit.obm 编组格（我方绿、敌方红、空格），单位头像取菜单表（+10 头像序号）→ ConvUnitIcon（页 0 unit_icon_01、页 1 unit_icon_02），社区单位取注册表 icon.rect（community_content/unit_icon_02.obm）；头像与格子同倍率最近邻缩放。履历页每场显示双方 10 个头像。截图：`shots/prep_skin/`。
  - 用户第二轮反馈修订（`lab_ui.py` 新增，`lab_prep.py`、`lab_menu.py` 重写）：
    - 界面文字随游戏语言（app+0x3d64：1 日语、9 繁体中文、10 简体中文，其余英语），超出宽度先缩小字号再截断；单位名称继续取 GetMenuUnitName（当前语言）。
    - 按钮按下下移 2 像素并压暗，同一按钮上抬起时播放原生菜单音效（Sound_RequestPlayMenuSE：13 确定、8 关闭/返回，依原生调用频次判定）。
    - 准备界面为独立全屏界面（pause_menu.obm 砖墙背景），打开时播放 MISSION BGM 135（SC_MissionMenuInit2 → Sound_RequestPlayBGMEx2），关闭准备界面时恢复进入 LAB 前正在播放的 BGM（F7 进入时读取 app+38656+212，即 Sound_PlayBGM 开始播放后保存的当前曲目；+208 为尚未处理的请求），读不到时才用地图 BGM 103。实测标题画面进入：100 → 135 → 返回后 100。
    - 闸门（第三轮改为原生）：F7 进入、返回地图、开始战斗时，按 SetShutterClose/SetShutterOpen（0x2137b8/0x213804）相同步骤创建 4 个原生闸门任务（ShutterActionDataInit、CTaskSystem2D::AllDelete(app+0x3830,5)、清空 app+0x3820 槽、createMenuTask(app, app+0x3820, 动作表, 4)，动作表取两函数的 pc 相对常量，开闸为同表 +224），不调用末尾 ChangeNT(17/18)。LAB 每帧 CTaskSystem2D::Caller(app+0x3830,5) 推进（GT_Shutter 经 ActionSub2D 移动并以 RequestCommonSE 播放原生音效），再 GraphicsOpt::drawStack(app+124) 立即绘制，使闸门位于宿主界面之上；IsShutterActionEnd 判定结束，开闸结束后删除任务。开战时持续推进已合拢的闸门，场景进入 99/100 后停止，由 SC_BattleInit 的原生开闸接手。战斗自然结束（演出后约 75 帧）、菜单退出、F5、重新开始先调用原生 SetShutterClose，IsShutterClose 后离开战斗，再以原生开闸任务打开准备界面。截图：shots/nshut（地图上原生闸门）、nshut2（F7、Esc 返回、开战）、nshut3（开战衔接逐帧）。
    - 修复：准备界面 Esc 曾在窗口线程直接调用原生音效，与游戏线程并发执行原生代码导致崩溃（AOT stopped，lr 位于 Sound_RequestPlaySE），现入队由游戏线程执行；fonts() 字体缓存失效使每次重绘约 110 ms（音频随之卡顿），修正后约 48 ms，按下反馈改为只叠加按钮区域的压暗小图、不重绘整个界面。
    - ESC 菜单：pause_window.obm 米色面板 + menuparts 标题栏与按钮，半透明压暗，8 帧滑入/滑出，开/选择/关闭播放原生音效。
    - 支援行移除（原生接口与 SUPPORT_OPTIONS 保留，加载时支援值归零，只有弹头车出击生效）。
    - 双方各新增“随机”“清空”：随机候选为可选单位中具有原生头像者（无头像的空单位不进入），等级取该方“全部等级”。
    - 优势设定：BattleObjectManager::createUnit（0x1df344）从 manager+72+(队伍×2+成员)×8 读取两个浮点数传给 createUnitStatus（含 0.2 常量），即里世界关卡强化级数；第一个为生命、第二个为攻击，各 ×(1+0.2×级数)。LAB 每帧写入双方值（0–10 级）。实测普通兵 Lv40 基础 540，我方生命 +3 级为 864；敌方 594 为原生 NPC 对手的 1.1 倍加成。
    - 验证：`shots/prep2`（闸门、主界面、随机/清空、选择器）、`shots/battle2`（菜单、自然结束闸门、回到准备界面、履历胜方）、`shots/adv`（强化值与 HP）、`shots/shut`（宿主闸门合拢画面）。重新开始的闸门衔接与长时间对战未单独截图。
  - 第二、三场 LAB 战斗后音效消失（初步修订，泄漏部分）：LAB 离开战斗时未经原生 SC_BattleEnd（SceneEndFunc 无战斗场景分支），SC_BattleInit 每场新建的菜单图片与 2D 任务不释放；`build_enemy_graphics` 新建的敌方出兵格对象也未释放。`leave()` 现按原生顺序补做 ClearMenuTask、CTaskSystem2D::AllDelete(app+0x3830,0,4)、RequestClear2D、Sound_StopBGM、Sound_InitRequestBlock，并按 ~BattlePlayerOperator 的方式释放敌方出兵格对象（每场 7 个），再 BattleEnd_ClearBattleMain。代码依据为静态调用分析；验证范围为两次进出战斗无错误、第二场正常开战，音效恢复待用户实机确认。
  - 敌方按键出兵补播与我方相同的原生出兵音效 8；完全控制下出兵后保留 8 帧冷却显示再清零，双方格子均显示原生出兵反馈。原生 AUTO 开启时该方手动出兵被原生拒绝（双方相同）。
  - 验证脚本改用 `verification/lab_ui_20261006/config/`（环境变量 MSD_LAB_CONFIG_DIR），不再改动仓库根目录的玩家 `lab_config.json`。
- 验证（`shots/t8_prep`、`t8_finish`）：准备界面与选择器绘制、社区标签、选择与互换、全员 Lv40 实际写入（UnitInfo+0x14 = 39）、据点等级 2/1 生效、10 格全部出现在底栏、退出与击破敌方据点后回到准备界面、履历胜方判定、预设保存与读取。测试期间的 `lab_config.json` 已还原为测试前内容，测试生成的 `lab_presets/` 已删除。

### 2.2 r6 修订（2026-10-06 用户反馈）
- 底栏两端增加底栏背景最外侧边缘块（源 x −88.89…−70，含 AP 框下方圆角），右端为镜像；缩放比改为按片段总宽占满屏宽计算（约 0.863），消除 AP 框左下/右下缺口与两侧空隙。
- AP 数值框从第 0 遍中排除，我方、敌方各单独执行 `drawApBar`，裁剪到框体下沿（D 520），由底栏照原版压住下沿。敌方框保留水平翻转（文字带不翻转），取消红底。
- 中间分隔条：上沿边框不动，只把条纹段（D 513 起）绕自身中心旋转 180°，与两侧条纹起点对齐。
- 蓝/红滤镜只覆盖上沿边框以下的骨架区，不透明度约 27%（`drawImageS` 不读取当前颜色，无法做纹理着色）。
- AP 升级按钮成本数字右移 2（D），实测与数字框中心一致（“MAX” 不移动）。
- 敌方 AP 按钮人物与敌方弹头车朝向与我方镜像。人物动画与我方同一逻辑：每帧推进在 `BattlePlayerOperator::update` 入口执行（开场前不动）；`BattleScene::onEventBaseLevelup` / `onEventFeverTimeStart` / `onEventBaseUnitDead` 入口对敌方精灵执行升级、LevelMAX、Escape/Win（敌方据点被毁 → Escape；我方据点被毁且敌方未满级 → Win）。验证见 `shots/fix3`–`fix6`（战斗结束通过直接调用 `onEventBaseUnitDead` 触发）。

## 3. 待办（按建议顺序；T1–T5 已完成，见第 2.1 节，以下保留原始说明）

### T1 鼠标点击敌方单位释放绝招（用户新反馈）
- 原生 `BattlePlayerOperator::onGameScreenTouchEnded`（0x1d74a8）：`BattleScreen::getScreenPosition()`（约 0x1d7630）取镜头，读控制器 +908，`getTeamUnitList(本方)`（约 0x1d7646），逐单位 `isSpAttack()`（0x1d766c/0x1d7672）与命中判断，命中后以本方控制器发动。
- 做法：本方列表未命中时，以敌方队伍再遍历一次，命中后调用**敌方控制器**的 `actionUnitSpAttack(uid)`（虚表 +0x98，参数为单位 +0x62 的 16 位 ID，与 `lab.py` 的 `enemy_special` 相同）。仅在 LAB 头有效时启用。

### T2 底部出兵栏左右分栏（设计文档 4、4.1b、4.2）
- 16:9 布局，按钮不缩放：AP 升级 x 122–253→约 51 起；弹头车 1025–1156→约 1098 起；出兵区由 5 格扩为左 3（我方）+ 右 3（敌方），格距 133、格宽约 109，中间分隔复用警示条贴图；两侧各自滚动浏览 10 格、各自的青色滚动箭头。
- 原生：整块 HUD 在 `BattlePlayerOperator::drawUI`（0x1d7ca8–0x1d9a90）；滚动位置 `getUnitPanelScreenPosition`（0x1d6df6）；点击换算 `getUnitIndex`（0x1d6e40，被 `onUITouchBegan/Moved/Ended` 调用）；按钮命中 `getScreenItem`（0x1d6d8c）；Operator 只绑定 operator+0x18 一个控制器。
- 绘制右半区：出兵格循环第二遍时临时把 operator+0x18 换成敌方控制器，画完换回（同 N1 的“再跑一遍”手法）。右半区点击路由到敌方 `createUnit`；完全控制关闭时只显示不响应。
- 键盘：1–0 我方、Q–P 敌方保持；按到不可见槽位时可自动滚动该半区。

### T3 敌我背景滤镜（设计文档 4.2b）
- 只染出兵栏**背景层**（两条警示条内缘之间、格子后面的金属骨架），左蓝右红，约 35–45% 不透明度；**警示条、格子、头像、数字均不染色**。在背景绘制后、首个格子绘制前 `Graphics::setColor`+`fillRect`（或 `setRenderMode` 乘法/叠加），随后复位。

### T4 敌方 AP 升级 / 弹头车影子按钮（设计文档 3.0）
- 在我方按钮之下以敌方状态再画一次：AP 升级影子在我方 AP 按钮左上、弹头车影子在右上，偏移约 (∓14, −7)，红色调约 55% 不透明，不超出底栏框架（底栏上沿 y≈573）。可用/已充满时提亮或闪烁，不可用时暗淡。示意：同目录 `enemy_ghost_mockup.png`。

### T5 右侧敌方 AP 数值框（设计文档 3.0）
- `drawApBar`（0x1d7ac4，`drawUI` 内 0x1d84dc、0x1d9788 调用）之后以敌方 AP/上限再画一次，位置镜像到右下（约 x 995–1280、y 505–570）；框体水平翻转（`setFlipMode`）并以红色为底，文字不翻转。完全控制下显示满值或“∞”（待用户定）。

### T6 LAB 战斗中菜单（设计文档 5）
- 本项目已在原生暂停页加入音频行（`src/audio_options.cpp`），LAB 菜单同法：完全控制开/关、我方 AI 自动出兵、我方自动绝招、敌方 AI 自动出兵、敌方自动绝招、重新开始、返回 LAB 准备界面、继续。注意：GameMode 1 中原生暂停/脱离不可用（因此目前用 F5 退出），需先确认暂停页能否在 LAB 中打开。

### T7 自动出兵与自动绝招拆成独立开关（设计文档 3.0）
- `BattleControllerPlayerBase::noukinAutoPlay`（0x1cbfe0）内 `isSpAttack` 调用点 0x1cc050 为自动绝招分支；按 LAB 头开关跳过或单独执行。

### T8 LAB 准备界面（MSA 实验室 7 项，设计文档“参考”节与 2）
- 我方/敌方牌组、单位等级（默认 Lv40；`GetUnitLevelSaveData` 钩子，不写存档）、一括设定、据点等级、支援、地图（联机地图表 0x8fd730+48 起：1011,1021,…）、战斗履历。当前用 `lab_config.json` 代替。

### T9 结算与存档
- 结束时直接返回菜单，但尚未拦截可能的奖励/存档写入（当前依赖测试存档副本）；正式化前需在 `SC_BattleEnd` 路径或 `WriteMainSaveData` 处拦截。

## 4. 验收方式
- 每项完成后：构建新 LAB 核心 → 启动 LAB → F12 截图对照设计文档的位置与颜色要求 → 检查 `lab_probe.jsonl` 与日志无异常 → 在普通关卡确认原版行为未变（LAB 头为 0 时钩子必须完全回落）。

## 2.5 正式版统一入口与战后返回、自动绝招修复（2026-10-07）

- 共用运行层移至 `lab_runtime.py`；`event_trial_launcher.py` 在完成 TrialProbe 定义后统一注册，普通、原满级、全解锁满级及全兵种 Lv1 入口均在非战斗界面支持 F7。`lab_launcher.py` 保留独立存档入口及现有 install_core/install/install_platform 接口。
- 正式默认与独立 LAB 核心为 `MSD_Core_LAB_r9_20261007.dll`，原生钩子版本 6，文件 27124273 字节。根与 src 核心配置指向同名实际 DLL；显示版本保持 1.47.0。
- 战后返回：四个原生闸门任务槽被原生释放时按过渡完成处理；宿主删除闸门任务同时写完成标记 app+0xc21c=1 并清闭合标记 app+0xc21d=0；恢复目标采用主菜单初始化27（稳态28）。修复准备页永久busy、普通页面触点仍被闭合标记阻止及返回目标31对应关卡地图的问题。返回请求统一在游戏线程处理，普通战斗99/100不打开准备覆盖层。
- 自动绝招：新增 getAutoPlay 钩子，对关闭自动放兵的 LAB 控制器向手动输入/UI返回0，底层+1052保留1以驱动noukinAutoPlay；AP、冷却、人数许可沿用原生，LAB头0时回落。数字键、鼠标与两队绝招、关闭增兵及重新启用AUTO均专项核验。
- 详细实施与条件见 `docs/LAB_BUGFIX_2026.10.07.md`；证据位于 `verification/lab_bugfix_20261007/auto/`、`verification/lab_navigation_20261007/` 与 `verification/lab_fixes_20261007/`。全部验证使用独立fixture，个人存档与玩家LAB设置保留；旧运行实例需正常退出并重新启动。

## 2.6 主菜单 LAB 图标入口（2026-10-07）

- 使用用户 `F:\egg\MSD_封面素材\lab.png` 的60×48 RGBA原图，发行至`custom_content/lab.png`，逐字节保持。主菜单底栏顺序为BACK、OPTION、SHOP、MEDAL、LAB、MISSION，点击LAB打开现有准备界面。
- `lab_menu_entry.py`共用原生发布的几何完成绘制与点击；`lab_runtime.py`注册输入与逐帧生命周期。原生底栏钩子纳入六项分配，保留原按钮动效、NEW角标及原生命中，MISSION维持最右侧。
- 当前核心为`MSD_Core_LAB_r10_20261007.dll`，27127611字节，LAB钩子7；独立菜单共享头0x1ffef000。LAB原生x700.8、y532，scale2；1280×720逻辑矩形887.4、598.5、135、108。
- 证据与边界见`docs/LAB_MENU_ENTRY_2026.10.07.md`及`verification/lab_menu_icon_20261007/`。图标点击、返回及窗口/全屏命中在隔离存档中验证，既有F7、玩家存档和LAB设置保持。

## 2.7 LAB 原生按压、入场与标题视觉修订（2026-10-07）

- 当前核心统一为 `MSD_Core_LAB_r13_20261007.dll`，27,130,197 字节，钩子版本 8。r13 保留 r12 的全部改动及第2.5节的分栏出兵格拖动修复，追加第2.8节子页面LAB点击修复；根目录与 src 的配置及 `lab_runtime.LAB_CORE` 均采用 r13，既有核心保留。
- LAB 使用原生图像及 Graphics 队列，与 MEDAL 同帧父任务位移、alpha 和闸门层级一致；从场景27初始化采用六项布局，稳态28/1开放输入。按压共用原生转换项79青色边框和37三灯，原PNG/纹理/矩形60×48保持，GLES2采样配置为CLAMP_TO_EDGE与NEAREST。
- `title_visuals.py` 导入用户282×247 LOGO原始RGBA，单矩形显示，无独立绿色底层；原透明背景、全部绿色描边、原生锚点及绘制缩放保持。禁止以全图绿色键清除边框。TAP SCREEN仅隐藏图集alpha，原生任务、几何及点击流程保持。
- 实施、当前验证条件与同步清单见 `docs/LAB_VISUAL_TITLE_2026.10.07.md` 及 `verification/lab_visual_title_20261007/`。个人存档与LAB玩家设置保持，验证均使用独立fixture。

### 2.5 分栏出兵格拖动修复（2026-10-07，核心 r12）
- 现象：双方任一侧编入 4–5 个单位时，该侧出兵格无法左右拖动。
- 原因：原生 BattlePlayerOperator::onUITouchMoved 在 0x1d7282 / 0x1d728c 两个入口块中以槽位数（controller+912）与可见格数（operator+12 为 0 时 5，否则 6）比较，不超过即放弃拖动；分栏后每侧只显示 3 格。
- 修复（`src/lab_hooks.cpp` drag_check）：分栏模式下两个块执行期间，若槽位数为 4–6，临时把计数视为 7，块返回后还原；滚动范围仍由 operator+104（max_scroll，(槽位数−3)×格距）限定。钩子版本保持 8，`lab_runtime.py` 改为加载 `src/build/MSD_Core_LAB_r12_20261007.dll`（在含 r11 改动的当前源码上构建）。
- 初次窗口验证（`verification/lab_ui_20261006/shots/drag2`、对照 `drag2_r11`）：我方 4 个单位、敌方 5 个单位，横向拖动后 r12 的滚动值分别为 118（上限 118）与 118（上限 236）；r11 同一操作两侧均保持 0。该次窗口记录限定上述 4/5 格条件。r12 钩子实际覆盖 4–6 格；7 格及以上沿用原生拖动判定。
- 本轮同步前追加 64 项内存隔离检查：两个拖动块、槽位 3–10、operator 模式 0/1 与分栏开关；4–6 格分栏判定、实际计数恢复及其他条件与 r11 控制流一致均通过。5 组原生菜单几何核查通过；实窗复核与本地部署证据位于 `verification/lab_visual_title_20261007/`。

## 2.8 子页面 LAB 点击修复（2026-10-07，核心 r13）

- 用户截图中的CUSTOMIZE、SHOP、OPTION同属scene28，分别为state3、4、2；MENU为state1。r12的LAB原生就绪条件仅接受state1，三个子页面存在图像可见、点击许可为0的情况。
- 原生就绪条件限定state1..4，保留闸门、cockpit与任务标记条件；lab_menu_entry.ready复核当前scene/state，阻止缓存许可在状态0/5/6继续接受触摸。主菜单及三个子页面共用现有坐标、按压青色边框、三灯、原生绘制层级与输入队列。
- 当前核心为MSD_Core_LAB_r13_20261007.dll，27,130,197字节，hooks8；r12的drag_check原始源码片段逐字节保持，核心接口与共享头保持。准备界面未开战时Esc/Back返回原子页，开战与战后清理继续使用现有SceneEndFunc(28)及菜单27→28路径，页面类型沿用原生记录；SHOP开战样例返回state4，无新增页面快照。
- 原生15项、宿主10项门槛检查通过；四页导航、返回后普通控件与子页面开战后的战后返回采用实际窗口独立fixture核查。证据与同步范围见docs/LAB_MENU_ENTRY_2026.10.07.md及verification/lab_submenu_fix_20261007/。用户存档、LAB设置、README已完成的重写及用户进程保持。

## 2.9 双侧 AP 反馈与敌方提示横幅（2026-10-07，核心 r15）

- 当前正式核心为 `MSD_Core_LAB_r15_20261007.dll`，27,134,094 字节，hooks9。根目录与 src 配置、普通及独立 LAB 入口统一加载该核心，保留 r12 拖动与 r13 菜单原生源码段。
- 敌方升级复用完整原生 `playBaseLevelupAction`，金币初始化与 OKAY 声音26同步，人物动画1第36帧播放敬礼声音7。新增原 `clock` 导入的同步回调，继续调用宿主既有计时函数；原声音请求、声道、解码器与混音接口保持。
- `createGrahics` 保留原 operator+208，宿主为敌方单独 new3116→BattleCoinAnimatorC2→initialize，保存至敌方图集字段+20。双方金币对象各自逐帧更新并在 AP 框及底栏之后绘制，敌方采用按钮中心镜像。退出时沿用原金币析构与 delete 流程。
- 敌方 LV UP、MAX、ATTACK 使用独立六槽队列及原生入场/停留/退场状态机；图像、文字与水平动画整体按 `x'=960-x` 镜像。共享头+0x100保存十个 operator 横幅字段，+0x128就绪，+0x140保存六个28字节槽；宿主先 release 槽内+4 Sprite，再清+0x100..+0x1e8。
- 主组57项、满级组30项、单帧推进26项运行检查通过，共113项；声音请求及混音活动/字节进度分别核验。基寇卡、马可、KT-21双侧普通攻击与绝招的62条请求及52.504秒实际PCM与r13逐条/逐字节一致，音频两组各21项及8项对照检查通过。
- 详细范围、13项本地正式目录同步清单与证据见 `docs/LAB_AP_FEEDBACK_2026.10.07.md` 和 `verification/lab_ap_feedback_20261007/`。个人存档、LAB设置及预设保留，显示版本保持1.47.0；Git提交与发布由用户执行。

## 2.10 敌方首次触发资源准备（2026-10-07，核心 r16）

- 用户报告我方尚未升级时，敌方首次升级缺少人物、金币及提示。冷启动复现显示GFX/PANEL/BANNER均就绪、缓存406为空；完整升级动作先创建横幅，首次分配/文件加载在同步嵌套调用中止。r15原检查采用我方先升级，保留其顺序范围。
- `build_enemy_graphics` 发布GFX_READY前，以顶层原生Factory.create(SpriteID2)创建并持有 `enemy_feedback_resource`。该Sprite的ImageIndex406参与原生600槽资源保留扫描，未调用AP动作、动画、横幅或声音。正常退出先释放实际横幅再释放此资源，abort及窗口关闭亦执行幂等释放。
- 当前核心为 `MSD_Core_LAB_r16_20261007.dll`，27,134,094字节，hooks9。原生钩子及音频源码保持r15内容，宿主完成资源准备。证据位于 `verification/lab_ap_enemy_first_20261007/`，修订说明见 `docs/LAB_AP_FEEDBACK_2026.10.07.md`。
- 新增97项检查通过：鼠标/键盘/延迟首升各19，首次ATTACK7，两轮重入27，abort清理6。每轮均无我方AP请求，敌方声音26/7各1并实际PCM消费；pin索引406在退出后恢复-1，重复释放幂等。
- 按F:\egg\AGENTS.md第2.2、2.3节，同时同步dist/MSD_Windows及用户指定的metal-slug-defense-on-Windows-ported-edition-main运行副本，个人存档与LAB设置保留；显示版本保持1.47.0。

## 2.11 准备界面顶栏与地图选择、复制对方、战后 BGM 与退出、双方音效通道（2026-10-07，核心 r17）

- 顶栏：此前使用 ConvMenuParts 第 1 项 `(0,0,568,67)`（底部按钮栏底板）并以九宫格拉伸到 1280 宽。现改用原生各菜单顶栏第 0 项 `(0,68,568,51)`，按原生 2 倍（1280×720 画布上 2.25 倍，1278×115）等比放大并居中，不拉伸。顶栏高度由 67 改为 115，牌组、面板、选择单位与履历页面相应下移；OK/BACK 位于铆钉条上方。
- 据点初始等级移到牌组标题行（`据点 < Lv > `）；每行新增“复制敌方 / 复制我方”，复制对方牌组的单位、格位与各格等级。
- 地图：新增 `lab_stages.py`，运行时读取原生区域表（GetAreaNum/GetAreaData 以 0x902384 为基址，WorldType 0 的世界 w 位于第 w+3 行）。开放地图 1–3（世界 0–2，各 67 关）与里地图 1–3（世界 9–11，61/61/54 关），共 377 关，均有 Mission 记录。战斗 StageID 按 SC_BattleStart 关卡模式的 `(世界+1)×1000+(区域+1)×10+(小关+1)` 计算；Mission BGM 为 0 时 `setupResourceAll` 以同一 StageID 调用 GetStageBgmID，地图与音乐随 StageID 一致。缩略图按 LoadThumbnailImage（区域缩略图号→0x31d420 文件对→按语言的 ImageDataInfo）与 GT_InfoWindowDraw（drawPict 转换表 28、GetStageThumbnail 图块）读取，每关为 128×56 原生图块，界面 2 倍显示。面板为“世界 < >”“小关 < >”两个选择器，上方缩略图与“区域名 区域-小关”。
- 敌方默认配兵：联机 GameMode 1 的敌方为 BattleControllerNetPlayer，不读取 Mission 敌军波次；捕虏（UnitID 116）与 UnitID 363 只在游戏类型 1/7 生成，LAB 为 2。运行核对：1055、1165、3165、12125 关关闭双方 AI 运行 15 秒，敌方队伍只有据点。
- 战后 BGM：战斗结束后 `leave` 进入原生主菜单初始化（27→28），SC_MainMenuLoop 状态 0 在闸门结束时请求一次主菜单 BGM 101，覆盖准备界面的 135。准备界面打开且闸门静止时每帧核对当前 BGM，不是 135 时重新请求（`hold_bgm`）。
- 退出：准备界面退出一律回到主菜单主画面（出击 / 强化 / Wi-Fi 对战）。已在场景 28 子状态 1 时恢复 BGM 101 并开闸；其他情况清零 `app+0xb168`（SC_MainMenuLoop 状态 0 据此进入 OPTION=1、CUSTOMIZE=3、SHOP=4 子画面），再 SceneEndFunc + ChangeExeST(27)，由 SC_MainMenuInit 的 SetShutterOpen 开闸。取代 2.8 节“未开战时 Esc/Back 返回原子页”的行为。
- 音效通道（钩子版本 10，功能位 64）：原生每个端口每帧收 3 条请求（第 4 条按优先级淘汰），在 3 个 CAudioPresenter 间轮换，满时停止最早者。BattleObject::playSE 以对象 +0x70 选端口，我方为端口 0（通道 app+0x9b00..08），敌方为端口 1（app+0x9b18..20）。LAB 战斗中改为每端口每帧至多 24 条请求（同帧同 SoundID 合并），通道为原生 3 个加宿主建立的 8 个，每方 11 个；优先空闲通道，全部占用时停止最早开始者。扩展通道由宿主按 Sound_Create 的方式建立（operator new 0xb0 → CAudioPresenter(CMediaManager) → setInit → 音量属性 4），每进程一次，头部 +0x300 魔数 'LSE1'、+0x304 个数、+0x310/+0x330 指针、+0x380 统计。播放、停止、音量与缓冲释放沿用原生函数；Sound_Stop 标志 2、Sound_ChangeVolumeSE、bufferReleaseCheck 同时处理扩展通道。原生 Sound_Stop 没有处理 Sound_StopSE_2P 的 0x200 位（置位后保留），扩展通道与原生一致不据此停止。CMediaManager 有 32 个播放槽，通道只在播放期间登记；嵌套调用的导入仅 memset、pthread_mutex 与 clock，均由核心直接处理。非 LAB 战斗请求走原生路径。
- 核心 `MSD_Core_LAB_r17_20261007.dll`，27,139,792 字节，hooks10；根目录与 src 配置、两份 `lab_runtime.py` 统一。最终核心 8 次隔离运行 69 项检查通过（地图 1–3、里地图 1/3 的普通与头目关；战场与 BGM 对应、只有据点、双方端口均播放且并发超过 3（满载时每方 11）、战后 BGM 135、退出到主菜单子状态 1 与 BGM 101、主菜单直接进出）。证据见 `verification/lab_prep_r17_20261007/`（`verification_summary.json`、`stage_dump.json`、`runs/`、`ui_shots/`）。听感、长时间对战与其他设备表现待用户实机核验。

## 2.12 音效扩展音量修复与界面语言跟随（2026-10-07，核心 r18）

- 用户报告 r17 中大量单位变为无声。原因：原生 `Sound_PlaySE` 两支都在 0x1c76f0 以 `vcvt.f32.s32` 把整数音量（app+0x9ae8，淡出支再乘 app+0xaf5c 后右移 8 位）转为浮点再传给 `CAudioPresenter::play`；r17 的分派把整数位模式直接当浮点传入，play 设置的通道增益（presenter+0xac）为 0。LAB 战斗中所有经扩展分派的音效（双方单位攻击、受击、爆炸等 SE）因此静音，语音走另一路径不受影响。r18 按原生方式转换。
- 对照（1011 关、双方 AI、40 秒）：r16（无扩展）原生通道增益 1523–2539；r17 播放过的通道增益 0.0；r18 原生与扩展通道增益同为 2031/2539。战斗段 PCM 均方根 r16 6342、r17 4162、r18 9819（双方牌组随机，仅作参考）。
- 同时加入播放槽整理：CMediaManager 的 delAudioPresenter 找到项即返回（0x138b10），stop 实际不注销，槽位由混音回调在通道已结束（+0）或已停止（+0x60）时清空；play 追加不查重。每次 play 前按混音回调的同一规则清除已结束、已停止与重复项，并统计播放后未登记次数（统计第 8 字）。对照运行（头部 +0x308=1 跳过整理）未出现重复项或未登记，本项不是 r17 无声的原因，作为同一规则下的预防保留。
- 界面语言：准备界面的单位名称列表与地图目录（区域名、按语言的缩略图表）此前每进程只读取一次，切换游戏语言后仍显示旧语言。现按 app+0x3d64 缓存，语言改变后重新读取；缩略图缓存键含语言。繁中→日语→繁中依次进入 LAB，单位名、地图标签与区域名随之切换。
- 核心 `MSD_Core_LAB_r18_20261007.dll`，hooks10；r18 6 次隔离运行 56 项检查通过（1011 双方 AI、10045、12125/1165 关闭 AI、主菜单直接进出），另有语言切换 3 步检查。证据见 `verification/lab_prep_r17_20261007/verification_summary.json`（comparison_runs 为 r16/r17 对照）与 `shots/t_lang`（lab_ui_20261006）。

## 2.13 AI 段位、原生尺寸图标按钮与按下光效、韩文字形（2026-10-07，核心 r19）

- AI 段位（钩子版本 11，功能位 128）：控制面板“我方 AI / 敌方 AI”两行为“开/关 + 段位选择器”，双方各自设定，默认 SILVER；段位名只用英文大写，配色参考 APEX 色系。8 段：ROOKIE −2、BRONZE −1、SILVER 0、GOLD +1、PLATINUM +2、DIAMOND +3、MASTER +4、PREDATOR +5。
- 原生 AI（BattleControllerPlayerBase::noukinAutoPlay 0x1cbfe0）每次出兵、弹头车或绝招后等待 rand() & mask 帧（mask = controller+0x420，startAutoPlay 以 rand()%240 抽取，整场固定）。段位接管 setAutoPlayWaitTimer（0x1cbfca），在 [下限, 上限] 内均匀随机：ROOKIE 160–320、BRONZE 80–160、SILVER 30–90、GOLD 18–54、PLATINUM 10–32、DIAMOND 6–18、MASTER 3–10、PREDATOR 1–6（帧，30 帧/秒）。等待期间原生整帧跳过，自动绝招同样受其节奏影响。
- 紧急阈值（controller+0x424，原生 rand()%220）：己方场上单位 AI 战力（数据行 +0x354）合计低于阈值 −30（据点等级 1 时为阈值/2 −30）时 AI 直接出兵。段位依次为 0、0、110、300、800、1500、永远紧急（0x3fffffff）、永远紧急。
- 开局据点目标（据点等级 controller+0x3fc，与准备界面同一编号 0–10）：ROOKIE 1、BRONZE 2、SILVER 原生逻辑、GOLD 3、PLATINUM 4、DIAMOND 4、MASTER 5、PREDATOR 5。低于目标且对方前线未推进到距己方据点 60% 以内（原生 r7≥2 同一判据）时，在出兵决策入口（0x1cc070）优先升级据点，AP 不足则保留 AP；达到目标后，AI 自身对 isKyotenLevelup（0x1cbd48，按返回地址限定在 noukinAutoPlay 内）的调用只在 AP 已满且没有可出单位时放行。原生在不处于劣势时会持续升据点至满级，SILVER 保留该行为。“己方不足 4 个单位不出远程”规则保持原生。
- 头部：+0x500 我方、+0x520 敌方，各 [启用, 等待下限, 等待上限, 据点目标, 段位序号]。开发中曾放在 +0x3c0，与音效统计（+0x380..+0x3f7）重叠，已移开。
- 选择器：原生左右按钮、压暗的原生按钮底板、段位色加黑色描边与底部色带；文字色按 4.5:1 亮度对比自动提亮（仅 PREDATOR 由 #E0302E 提至 #E44947）。AI 关闭时文字为灰色，色带降为 15% 饱和度、55% 亮度。
- 顶栏 OK/BACK：按用户确认的比例等比缩小为 1.5 倍（按钮 90×72，y 13–85；按下青色框 99×81，y 9–90），整体位于顶栏深色区（原图第 3–40 行，画布 y 7–92）内，不碰顶部亮线与下沿铆钉条。（开发中曾按主菜单底栏按钮的 2.25 倍、135×108 实施，用户修订。）按下期间按 GT_CockpitButtonDraw（0x2003bc）叠加 ConvMenuParts 79 青色框（锚点 3,3）与 37 三灯（锚点 −19,−2），不压暗、不下移；拖出按钮时取消，抬起执行 OK/BACK 后青色框保持到闸门合拢。
- 韩文：游戏语言为韩语（app+0x3d64 = 2）时单位名称与区域名为韩文，界面主字体不含韩文字形。含韩文的字符串改用 Malgun Gothic（malgunbd.ttf）；界面文字在韩语下沿用英文。另：语言 10 为俄语，lab_ui.LANGS 将其映射为简体中文，按用户要求未处理。
- 核心 `MSD_Core_LAB_r19_20261007.dll`，hooks11。验证：4 组对战覆盖 8 段及 SILVER 对 SILVER，共 27 项检查通过（每次记录到的等待均在段位区间内、紧急阈值写入、首次出兵时据点达到目标或属于防守例外）；r17/r18 回归 3 次运行全部通过；段位选择器开/关两组截图、OK 按住截图与韩语界面截图见 `verification/lab_ai_tier_r19_20261007/`。实际对战强度与手感待用户实机核验。

## 2.14 AI 出兵选择：单位价值、积累 AP、建筑类单位与随机积累策略（2026-10-07，核心 r20）

- 用户要求：段位越高越“明白”高 AP 单位的价值（依 HP、伤害、击退权衡）并为其积累 AP；建筑类单位不直接进入最前线；高段位在“用便宜单位填补”与“囤积等待大单位冷却”之间随机切换。
- 钩子版本 12：在 noukinAutoPlay 出兵调用点 0x1cc40e（r5 为原生选择的槽位）按段位“理解度” s 选择槽位或暂不出兵；ROOKIE/BRONZE/SILVER 的 s 为 0（原生选择），GOLD 35、PLATINUM 55、DIAMOND 70、MASTER 85、PREDATOR 100（`lab.py` AI_TIERS 第 7 列，头部段位块 +20）。
- 单位价值 S = √(HP × 每秒伤害) × (1 + min(击退门槛, 40)/40)，取 BattleInfo::getUnitStatus 等级状态：+0xc HP、+0x10 击退门槛×100、+0x58 普攻伤害、+0x6c 普攻等待（木乃伊 40 与已记录值一致）、+0x74 绝招伤害、+0x8c 绝招冷却；每秒伤害 = 普攻×30/(等待+30) + 绝招×30/max(冷却,30)。建筑类（单位行动表 [0x109373f4][UnitID] 的 vtable 为 Kouhei/Donou/Mortar_Kouhei/GuerrillaMortar_Kouhei：UID 4、5、73–77、95、108、155、163、171、184 等及社区 1036、1041）本体 HP 1，以原生 AI 战力（状态 +0xc8）×12 估计。排序值 = S / AP^(1−0.75s) × (1 + 0.6(1−s)·u)，u∈[−1,1]。
- 积累：目标为据点 AP 上限内、冷却完毕或即将完毕的排序最高者；目标暂不能出时积累 AP（本帧不出兵、不设等待）。策略每次出兵后随机重抽（各 50%）：A 填补——只看 3s 秒内冷却结束的单位，出其他单位后余下 AP 不少于目标×(1+s) 时才出，最长积累 s×450 帧；B 囤积——看 30s 秒内冷却结束的单位，期间不出其他单位，最长积累 s×900 帧。压力（对方前线推进到距己方据点 (0.4−0.2s)×场宽以内，或对方场上战力（不含据点）比己方高 400+1200s 以上）时改出能买得起的最高者。
- 建筑类：工兵行动（BattleAction_Kouhei::update）在遇到攻击范围内的敌人时于原地建成，建成位置即接触线。s>0 时建筑类只在对方有单位在场、且对方前线位于己方半场（≤0.5 场宽）时出击。
- 开发中修正：① 队伍单位链表为环形，遍历须在回到首个单位时结束（此前计数放大数百倍；r8 支援钩子 apply_support 同类循环一并修正）；② 原生战力合计含据点、据点战力随等级大幅变化，自定义比较排除 getKyotenUnit；③ ROOKIE/BRONZE 紧急阈值 0 时 90 秒内不出兵，改为 50/80。原生模式判定同样包含据点，未修改。
- 统计：头部 +0x540 每方 8 字（出兵、积累帧、建筑类暂缓、改选、压力出兵、最近 UnitID、AP 合计、建筑类出兵）、+0x580 建筑类出兵时前线最大值、+0x588 无敌方时建筑类出兵、+0x5a0/+0x5c8 各槽出兵次数、+0x5f0 进入策略 B 次数与 B 下出兵。
- 验证（加速模式，同一混合牌组：士兵、盾牌兵、基寇卡、重装 B、SV-001、大象、爆竹红、木乃伊、木乃伊召唤箱工兵、沙包）：出兵平均 AP SILVER（原生）122.7，GOLD 45.6、PLATINUM 64.2、DIAMOND 62.2、MASTER 76.1、PREDATOR 96.5；积累帧随段位增加（GOLD 86 → PREDATOR 1868）；s>0 段位建筑类出兵时前线最大 0.498，均有敌方在场，SILVER 原生为 0.79。高段位约半数阶段为策略 B。代价：囤积阶段出兵数减少，PREDATOR 对 SILVER 在 90 秒内未再摧毁据点（A/B 之前为 2287 帧）。r20 共 11 次运行 76 项检查通过，回归 8 次运行通过。证据 `verification/lab_ai_tier_r19_20261007/verification_summary_r20.json`、`driver_value.py`、`runs_value/`。
- 加速验证：driver_r17/driver_ai/driver_value 默认以无等待的 FramePacer 替换 30 Hz 节拍（约 300 fps，约 10 倍实时；`--realtime` 恢复）。游戏逻辑按帧推进，结果与实时一致；同一进程种子固定，重复运行结果相同。
- 核心 `MSD_Core_LAB_r20_20261007.dll`，hooks12。实际强度与手感待用户实机核验。

## 2.15 标题画面 Esc 退出与对战中关闭窗口（2026-10-07，宿主修订，核心保持 r20）

- 用户要求：标题画面按 Esc 直接退出游戏且不报错；对战进行中关闭游戏不报错（LAB 对战本身不保存）。
- 复现（`verification/exit_paths_20261007/driver_exit.py`，隔离存档 `verification/lab_ui_20261006/save/`）：① 标题 Esc 经原生 Back 调用 Java `showEndDialogView()V`（Android 退出确认框），宿主未实现该回调而抛出 RuntimeError，写 player_error.log 并弹出错误框；② LAB 对战中关闭窗口时停止事件已设置，`LabProbe.close` → `lab.abort` → `release_enemy_feedback_resource` 的原生调用被 `Probe.call` 以 ProbeCancelled 取消，异常记入 `self.error`，退出码 1；③ 对照组（主菜单关闭）一次运行中帧 140 的诊断标题截图遇帧缓冲 0×0（窗口最小化），PIL 抛出 SystemError 中止游戏线程。
- 修订：`local_platform.handle_java_call` 处理 `showEndDialogView`，记录 `LOCAL_EXIT_REQUEST` 并设置停止事件，按关闭窗口的正常流程结束；`Lab.abort(native=True)` 新增参数，`LabProbe.close` 在停止事件已设置时以 `native=False` 调用，只还原内存存档映像与共享头，原生横幅资源随进程释放；`player.py` 帧 140 的标题截图失败时记录 `WINDOW_TITLE_CAPTURE_SKIPPED` 并继续。普通关卡关闭路径（event_trial/campaign/online 的 close）不含原生调用，`lab_menu_entry.close` 已有同类停止判断。
- 验证：标题 Esc、LAB 对战中关闭、主菜单关闭、主菜单 Esc 四组均退出码 0、无 player_error.log、状态 `closed`；标题 Esc 于下一帧记录 `LOCAL_EXIT_REQUEST`；主菜单 Esc 仍返回标题（场景 28→20）且不退出；对战中关闭时 LAB 存档写入均为虚拟文件。普通关卡战斗中关闭未单独运行。
- 修改文件：`player.py`、`local_platform.py`、`lab.py`、`lab_runtime.py` 及 `src/` 镜像（`lab.py` 无镜像），共 7 项，已同步两个运行目录。

## 2.16 AI 场上投资升级据点与停滞兜底（2026-10-08，核心 r21，钩子版本 13）

- 用户反馈：段位 AI 常停在据点 3/4/5 级不再升级。原因（r20）：达到开局据点目标后，`ai_levelup_query` 只在“AP 已满且没有任何可出单位”时放行 AI 的据点升级；积累策略使 AP 很少达到上限，10 格中通常总有可出单位，升级通道实际关闭。r20 GOLD 对 GOLD 240 秒内双方均停在 3 级（`verification/lab_ai_invest_r21_20261007/runs/mirror_r20_*`）。
- 规则（`src/lab_hooks.cpp` ai_invest，在出兵决策入口 0x1cc070、开局目标逻辑之后执行；SILVER 保持原生）：
  - 场上投资 F：己方场上存活单位（HP>0，不含据点）的出兵 AP 合计，按己方卡组同一 UnitID 的出兵费用计价。召唤单位不计入（用户要求）；变身单位（伞兵落地、工兵建成、迫击炮架设等）按最初出兵单位计入一次。
  - 投资触发：F ≥ k × 本级升级费用（controller+1024）并持续 D 帧 → AP 足够即升级（与原生 0x1cc464 相同的虚函数），不足时暂停出兵保留 AP，最长 L 帧；超时后须再出一次兵才重新触发；F < 0.7×阈值退出。
  - 停滞兜底（用户要求“不能因等待触发而停滞”）：达到开局目标后据点等级 S 帧未变化时，不论 F 均进入投资，不设暂停上限，保留 AP 直至可升级；本级升级费用超过 AP 上限时不触发。
  - 压力（对方前线距己方据点 ≤(0.4−0.2s) 场宽，或对方场上战力高出 400+1200s 以上）时照常出兵。
- 参数（`lab.py` AI_INVEST，(k×100, L, D, S)，帧）：ROOKIE (300, 90, 90, 1200)、BRONZE (250, 120, 60, 900)、SILVER 关闭、GOLD (200, 150, 20, 600)、PLATINUM (170, 180, 10, 450)、DIAMOND (140, 210, 6, 360)、MASTER (120, 240, 3, 300)、PREDATOR (100, 300, 1, 240)。低段位系数高、反应延迟长、兜底晚，表现为“慢半拍”。
- 单位来源（原生核查）：卡组出兵经 `BattleController::onEventUnitCreate`，召唤与变身经 `BattleObject::createChildObject`（原生 20 余个 summon 函数均调用），二者最终调用 `BattleObjectManager::createUnit`。钩子位于其成功出口 0x1df440（r4 新单位、r6 队伍），以栈上返回地址（sp+52：0x1c9683 出兵、0x1de213 子单位）区分来源，父对象为调用者 r4（sp+24）。子单位在 300 帧内父单位消失且父单位只生成过这一个子单位时视为变身，否则为召唤。对象池指针会复用，记录以指针 + 生成序号区分，新单位生成时同一指针的旧记录失效。单位 UnitID 取单位状态 +0x128 首字。
- 更正：单位 +0x62 为每个单位的实例编号，不是 UnitID。r20 验证脚本 `driver_value.py` 以 +0x62 匹配卡组 UnitID 统计出兵，只匹配到少数单位，其报告中的“出兵平均 AP”（第 2.14 节所列数值）不可靠；钩子内统计（+0x540 起）不受影响。onEventUnitCreate 出口块的 r0 不总是有效单位（开发初版据此记录，宿主读取无效地址导致随机 AOT 停止），已改为上述出口钩子。
- 头部：段位块 +24 k×100、+28 L（位 0–11）| D（位 12–19）| S/10（位 20–31）；+0x700 场次编号（宿主每场开战递增，钩子据此清空记录）；+0x710 起每方 8 字（触发、投资升级、超时、暂停帧、最近 F、最近阈值、压力跳过、据点等级）；+0x750 起每方 4 字（出兵、变身继承、召唤、当前计入单位数）；+0x770 起每方 1 字（停滞兜底触发次数）。
- 验证（`verification/lab_ai_invest_r21_20261007/`，加速模式，隔离存档 `verification/lab_ui_20261006/save`，混合牌组含工兵/沙包/木乃伊召唤箱工兵）：最终参数 9 次运行（7 段同段对战与 GOLD、PREDATOR 对 SILVER，各 240 秒）检查全部通过，达到开局目标后无停滞。同段对战升至 10 级用时：PREDATOR 44 秒、MASTER 49 秒、DIAMOND 49/64 秒、PLATINUM 75 秒、GOLD 138/156 秒；BRONZE 240 秒内到 7/9 级，ROOKIE 到 5/6 级；升级最大间隔 ROOKIE 约 57 秒、BRONZE 约 39 秒、GOLD 约 22 秒、PREDATOR 8 秒。SILVER 未触发投资，行为与 r20 相同。r19/r20 段位检查（等待区间、紧急阈值、建筑类出兵位置、开局目标）同时通过。`summarize.py` 汇总各次运行。实际对战手感待用户实机核验。

## 2.16 战斗结束演出播放完毕后再合拢闸门（2026-10-08，宿主修订，核心保持 r21）

- 用户报告：被敌方击败时 MISSION FAILED 演出未播放完即合拢闸门回到 LAB，要求 MISSION COMPLETE / FAILED 演出完全播放完毕后再合拢。
- 原因：`Lab.update` 在战斗停止后满足“场景离开 100”或“停止计时满 75 帧”任一条件即调用 `finish`（原生 SetShutterClose）。实测（1-1，据点 HP 置 0，加速模式逐帧记录与截图）：战斗于置 0 后第 15 帧停止，原 75 帧计时在第 90 帧合拢，此时 FAILED 文字仍在入场；演出文字在第 130–140 帧退场，原生于第 155 帧（COMPLETE 为第 135 帧）自行由场景 100 进入 101。
- 修订（`lab.py`）：以原生离开场景 100 作为演出结束点；停止计时改为 15 秒兜底（`RESULT_FALLBACK_FRAMES = 450`），仅在原生未离开场景时生效。
- 验证（`verification/lab_result_anim_20261008/driver_result.py`，隔离存档 `verification/lab_ui_20261006/save/`）：FAILED 与 COMPLETE 各一场，`finish` 只调用一次，原因均为 `battle_finished_scene_101`（FAILED 第 155 帧、COMPLETE 第 135 帧），未触发兜底；合拢前截图显示文字完整入场与退场，合拢后准备界面正常打开（`runs/lose_48624/contact.png`、`runs/win_49972/contact.png`）。`--observe` 模式记录原生完整演出（`runs/lose_observe_47012`）。
- 同步：两个运行目录的 `lab.py` 与提交 1.47.1（HEAD 7bdc26d）相同，工作区 `lab.py` 另含其他会话未完成的双人对战修改；同步文件为 HEAD 版本加本修订（与 HEAD 差异仅上述两处），见 `verification/lab_result_anim_20261008/sync_files/lab.py`，同步前副本在同目录 `dist_before/`、`user_install_before/`。同步文件未单独运行，行为验证基于工作区 `lab.py`（相同修改）。


## 2.17 本地双人对战（2026-10-08，核心 r22–r24，钩子版本 14–16）

- 结束演出（hooks14，功能位 256）、出兵格光标（hooks15，功能位 512，头部 +0xa00）、主菜单“對戰”与 VERSUS 子页面（hooks16，drawConv 替换表 +0xb40 'VSPG'，诊断记录 +0xb00 'DLOG'）、准备界面的按鍵設定 / 操作說明页、手柄（`lab_versus_input.py`，`player.Player.poll_input` 窗口线程轮询）与右摇杆镜头仲裁（原生 `BattleScreen::movePosition`）。
- 详细机制、参数与验证见 `docs/lab/local_versus_design_2026-10-06.md` 第 6 节；驱动位于 `verification/lab_versus_20261008/`。
- 2026-10-08 修订（宿主，核心 r24）：模式只由入口决定、VERSUS 页 SHOP 按钮原生切换、默认键位 R T Y U / M , . /、选项页音频两行逐行入场、战斗中菜单音频开关、玩家1 / 玩家2 文字；见设计文档第 6.7 节。

## 2.18 对战卡片固定 VS 字样及上下留白（2026-10-08，宿主修订，核心保持 r24）

- 用户自行设计 `custom_content/versus_card_{local,lan,online}.png` 的 98×102 人物图标；三张卡的 VS、原生卡框与底部文字由程序保留。`placeholder_art()` 仅包含占位士兵，`versus_mark()` 保留当前原生裁切像素，`card_image()` 在人物图层上独立叠加 VS。
- VS 图块为 34×20，透明边缘 bbox 为 (2,2,31,20)，完整图块左上角由 (32,14) 上移至 (32,5)。卡片内容相对 112×144 卡框偏移 (7,7)，VS 上方可见像素留白为 7+5+2=14；下方标签裁切后贴至 98×123 内容下沿，底部留白为 144−7−123=14。LAN、ONLINE 的灰度与“準備中”处理保持。
- 离线验证：三张卡、四种语言、缺省头像及透明/不透明用户图的 76 项像素、位置、留白和尺寸检查通过；人物图标、标签及提示在 VS 修改区域外逐像素保持。证据 `verification/lab_versus_20261008/fixed_vs_20261008/verification.json`。本轮未启动游戏，用户人物素材与实际窗口效果待其使用时核验。
- 同步清单：`lab_versus_page.py`、本文件及 `docs/lab/local_versus_design_2026-10-06.md`；目标为第 2.2、2.3 节的两个固定运行目录。个人存档、LAB 配置、预设及核心保持，部署记录见同一验证目录的 `deployment.json`。

## 2.19 用户三张对战人物插画接入（2026-10-08）

- 用户原稿位于 `F:\MSD宣传\versus_card_{local,lan,online}.png`，三图均为 98×102 RGBA。原样接入 `custom_content/` 与 `src/custom_content/`，对应文件逐字节一致；用户原稿、像素、透明度及配色保持。
- 用户最终要求三图下移以避让 VS，`card_image()` 将用户人物图统一绘制于 (0,16)，原 PNG 像素、尺寸及透明度保持；缺省士兵位置保持。VS 固定位置 (32,5)、卡框、底部文字和未实现模式的灰度/“準備中”保持。
- 移动后 LOCAL/LAN/ONLINE 至 VS 的最小纵向空隙分别为 14/2/12 px，至底部标签均为 6 px；与 VS 及底部标签的非透明像素交集均为 0，全部人物可见像素保留。
- 三卡四语言的离线合成与固定 VS 像素检查通过，原生 shop.obm 卡框/底板的 4 倍最近邻合成预览已核验。本轮未启动游戏；证据 `verification/lab_versus_20261008/user_card_art_20261008/verification.json`、`cards_preview_4x.png`。
- 同步清单为六项人物素材、`lab_versus_page.py` 及两份 LAB 文档，共九项，目标为两个固定运行目录；部署与保护检查见同一验证目录的 `deployment.json`。核心、配置、存档及 LAB 预设保持，图片重载通过正常退出和重新启动完成。

## 2.20 对战原生按压反馈与 LOCAL 关闸修复（2026-10-08，宿主修订，核心保持 r24）

- 原因：原入口向底栏 SHOP 模拟按下/松开，入口与三卡触点由宿主截断，LOCAL 在关闸前清除 VSPG。隔离基准实际复现 SHOP 蓝光、白光缺失及关闸前的原生 ITEM/MSP/UNIT 商店显现。
- `lab_versus_page.py` 复用入口 `GT_MenuPanel` 与三卡 `GT_MenuGenrePanel` 的原生按压路径；松开时框外释放并 `ClearSelectPanel`，业务由宿主处理。开页临时登记 SHOP 布局选择并调用 `SelectCockpitMainMenu()`，底栏 SHOP 按压状态保持 0，原生入场及单次确定音保留。入场就绪、拖出取消、重新移回及异常释放均已处理。
- LOCAL 使用 `local_transition` 保持 VSPG，待闸门闭合且准备界面打开后撤掉替换。准备界面返回 MENU 与用户主动进入正常 SHOP 的原生路径保持；用户插画、固定 VS 及其坐标保持。
- 验证：实际 r24、1280×720 ANGLE pbuffer 的 35/35 项检查通过，121 张 GPU 截图；入口与三卡白光为 64/128/192/255，SHOP 无误按压，LOCAL 关闸期间 VSPG 持续保留，正常 SHOP/三卡/OPTION 返回及拖出移回取消通过。证据 `verification/versus_feedback_20261008/final_/20261008_170449_29364/report.json` 与 `frames.jsonl`。所有验证写入限定独立 fixture，SHA-256 抛错守卫记录计算尝试 0。
- 同步 `lab_versus_page.py` 及两份 LAB 文档至两个固定运行目录，清单与保护检查见 `verification/versus_feedback_20261008/deployment.json`。核心、配置、个人存档与素材保持，更新通过正常退出与重新启动加载。

## 2.21 AI 拟真出兵：AP 饱和轮流出兵、压前线与骚扰、相持出建筑（2026-10-09，核心 r33，钩子版本 18）

- 用户反馈：AP 满级后 AI 仍死等最高 AP 单位冷却，完全不出中、低 AP 单位；建筑类单位只在敌人逼近家门口时才出。用户确认的规则适用于全部段位（含 SILVER，用户认为原版 AI 过于简单），且不同段位的反应时刻须不同。
- 原因（r20/r21 `ai_choose`）：积累目标包含冷却中的单位（策略 A 看 3s 秒、B 看 30s 秒），高段位排序几乎不扣 AP，目标总是大单位；B 期间不出其他单位，A 要求余量不少于目标 AP×(1+s)。建筑类只在对方前线进入己方半场（≤0.5 场宽）时放行。另外 `ai_levelup_query` 要求“AP 已满且无可出单位”才放行据点升级。
- 饱和轮流出兵（`ai_saturated_pick`，在 `ai_choose` 开头，全部段位）：据点等级 ≥9，或 AP ≥98% 上限并持续该段位的反应延迟（块 +4/+8 区间随机）后，在已冷却、AP 足够、非建筑类单位中按 AP 从高到低出兵；最高 AP 单位冷却中时，只在出兵后余下 AP 仍够买它时出次一级单位，否则等待 AP 回复；AP 已满且可升据点时交由据点升级。`ai_levelup_query` 改为 AP 已满即放行（`ai_ap_full`）。
- 前置规则（`ai_pre_rules`，出兵决策入口 0x1cc070，位于开局据点目标与场上投资之前，全部段位）：① 相持建筑：`front_observe` 每帧记录对方前线位置，连续 150 帧（5 秒）波动 ≤6% 场宽、再加段位反应延迟后视为相持，先出已冷却的建筑类单位，出后计时重新开始；② 据点等级 0–1：己方场上单位少于 2 时随机出 100 AP 以内单位压前线；③ 据点等级 2–5：每隔 300–600 帧加段位反应延迟，随机出 1–2 个 100 AP 以内单位骚扰。选定后跳转原生出兵调用点 0x1cc40e（同一栈帧，0x1cc070–0x1cc40e 之间无 sp 变化），出兵后原生设定反应等待。统计：头部 +0x6f0 起每方 2 字（前置规则出兵、饱和出兵）。
- 验证（`verification/lab_ai_player_r33_20261009/`，10 倍加速，隔离存档，地图 1011，混合牌组，每场 240 秒）：r32/r33 各 5 组（PREDATOR、GOLD、ROOKIE、SILVER 同段对战及 PREDATOR 对 ROOKIE），`summary.json`。满级阶段 AP 满档秒数 r32 为 9/22（PREDATOR）、65/53（GOLD），r33 为 0/0、0/6；满级后出兵种类 r33 为 7–9 种。建筑出场前线位置 r33 为 0.16–1.0 场宽（r32 规则限 ≤0.5）。ROOKIE 同段 240 秒据点 3/4 级（r32 5/6），PREDATOR 对 ROOKIE 时 ROOKIE 于 71 秒失败（r32 94 秒），段位差距扩大。已知现象：牌组较高 AP 单位全部冷却时，PREDATOR 满级后会以 AP 余量连续出最便宜单位（本牌组士兵 UID 2 约 70 次），属规则按 AP 递减的结果。驱动的出兵记录改用 UnitID +0x128（+0x62 为实例编号）；“首次出兵在开局目标之后”检查放宽为允许 0–1 级压前线。实际手感待用户实机核验。

## 2.22 敌方弹头车按钮 “MAX” 显示为 “XAM” 的修复（2026-10-09，核心 r34，钩子版本 19）

- 原因：分栏底栏的敌方弹头车片段整体水平翻转，只排除 ty≥590 的图块（成本牌等）。“MAX” 字样画在按钮框图块内（底栏图集 73×71、源 v 103，u 343/417 两帧交替；绘制 tx 808、ty 496），随按钮框一起翻转。新增诊断 SLOG（头部 +0xb10，默认关闭）逐条记录翻转片段的 drawImageS 参数后确认。
- 修复（`DrawHook`）：翻转片段中的按钮框图块保留翻转后的位置（x 范围不变），图像恢复正向（a、b 取反，tx 加 a′·w）；按钮内的弹头车图像（独立 Image）仍翻转，朝向与此前一致。LAB 与本地双人对战共用该路径。
- 验证（`verification/lab_slug_max_20261009/`，双方 AI 关闭，等待敌方充能满）：修复前截图为 “XAM”；修复后充满后第 1–8、12、16、20、24 帧及之后截图均为 “MAX”，无交替闪烁；未充满状态与我方外观一致。
