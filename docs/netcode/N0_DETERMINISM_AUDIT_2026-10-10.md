# Rollback 联机 N0：确定性审计（2026-10-10，只读与隔离测试）

依据：`docs/netcode/ROLLBACK_NETCODE_TASK_2026-10-09.md` 第 5 节 N0。正式版 HEAD `6bdf08e`，核心 `MSD_Core_LAB_r40_20261010.dll`。本阶段与 M6 并行进行，按约定**未修改任何游戏文件**；不一致来源的修正以测试驱动中的等效处理验证，正式修改列入第 6 节，待 M6 的核心工作完成后实施。测试机为 i9-13900HX（Intel，支持 FMA3），未取得 AMD 或其他 CPU 的结果。

## 1. 方法

驱动 `verification/n0_20261010/n0_run.py`（沿用 M4 隔离环境：存档副本、写入审计、联机关闭、代理侧不计算 SHA-256）：

- 对战：LAB 1v1（原生联机 GameMode 1 战斗对象），地图 1011，固定双方编队（P1：基寇卡、吉利塔、马可、KT-21、白/绿木乃伊、MKII、正规军伞兵、士兵、爆竹红；P2：士兵、爆竹红、塔玛、未来重装 B 型、M-15A、正规军迫击炮兵、基寇卡 MK.II、胖英里、重装 B 型、M-15A），双方据点生命 2,000,000（避免提前结束）。
- 输入：双方脚本命令（与联机将交换的离散命令相同：出兵槽位、AP 升级、绝招、弹头车），按相对开战帧固定时刻执行；或双方段位 AI（PREDATOR 对 GOLD）。
- 每帧在 `step_frame` 之后记录：
  - **语义校验 h**：战斗帧号（BattleMain+0x48）、宿主随机数状态、双方 AP / 据点等级 / 10 格冷却字段、每个单位的 UnitID、实例号、坐标、生命。
  - **深度校验 d**：BattleMain 0x100、双方控制器 0x440、每个单位 0x3f0、对象管理器 0x200 字节，数值落在客体指针范围（0x10000000–0x1fffffff）的字视为指针置零后计算 CRC32。
  - **原始堆校验 raw**（每 150 帧）：整段客体堆 0x12000000–堆顶的 CRC32。
  - 堆顶、分配块数、各时钟/随机导入的调用次数与调用者。
- 比较：`compare.py` 逐帧比较两份记录。跨进程比较的两个进程**错开 70–76 秒启动**（真实时钟不同）；同进程比较为同一进程中先后两场。

## 2. 结果

| 场景 | 设置 | 跨进程（不同时间启动） | 同进程两场 |
| --- | --- | --- | --- |
| 脚本对战，完全控制（AP 9999） | 固定 `lrand48` 与 RandomMT 种子、分配清零 | 2 场 × 10000 帧，h 与 d 全部一致 | h 一致 10000 帧；d 仅第 0 帧 1 处不同 |
| 脚本对战，**正常 AP**（同本地双人对战） | 固定 `lrand48` 种子、分配清零 | 2 场 × 10000 帧，h 与 d 全部一致（两进程堆布局不同） | 同上 |
| 段位 AI 对战（PREDATOR 对 GOLD，最多 80 个单位） | 同上加 RandomMT 种子 | 2 场 × 5000 帧，h 与 d 全部一致 | **第 0 帧起分歧**（见 S7） |
| 脚本对战，不固定 RandomMT 种子 | 指定双方编队 | 3000 帧全部一致 | — |
| 未指定 P2 编队（原生 NPC 编队）、不固定种子 | — | **第 10 帧分歧**（见 S1） | — |
| 虚拟时钟（时间由帧号推导） | 不固定种子 | 1500 帧全部一致，**整段客体堆逐字节相同** | — |

结论（限于本机与上述场景）：给定相同的初始条件（双方编队与等级、地图、随机种子）与相同的逐帧输入，战斗逻辑在两个独立进程间逐帧一致，满足 N0 的“1 万帧以上两进程一致”验收；Intel 与 AMD 的交叉验证尚未完成（第 5 节）。

## 3. 不一致来源与处理

| 编号 | 来源 | 证据 | 对联机的影响与处理 |
| --- | --- | --- | --- |
| S1 | `AppMain+0x9c` 的梅森旋转 `RandomMT`：`SC_TitleInit`、`SC_MainMenuInit` 以 `time()` 设种子；`MakeNPCInfo` 以它随机生成 LAB 的 NPC 对手编队（P2 未指定编队时），另有 `BattleCoinAnimator::start`、战斗结算等使用。 | 未指定 P2 编队时，不同启动时间 P2 编队不同（如 30/147/269… 与 398/188/222…）；只把偏移加在 `time()` 上即可复现。固定该种子后跨进程一致。 | 联机双方编队来自玩家自己的数据，不经 `MakeNPCInfo`。对战开始时仍应以比赛种子统一设定该 RandomMT（结算动画等表现层也用它）。 |
| S2 | 宿主 `lrand48`：状态在 Python（`probe.rng48`），不在客体内存。调用者：原版 AI（`startAutoPlay`、`setAutoPlayWaitTimer`）、`syncRand` 的模式 5 分支、`BattleScene::setupResourceAll` 的特定关卡分支、掉落物、若干单位动作（`BattleAction_Tetuyuki`、`BigShiee`、`EmainMacha`、`SolDeRoccaWrath::shotBullet` 等）。`setupResourceAll` 与 `onEventUnitDead2`（生存模式 9）在特定条件下调用 `srand48(time(NULL))`。 | 脚本对战 10000 帧内 `lrand48` 未被调用；AI 对战中被调用，固定种子后跨进程一致。 | 比赛开始时以比赛种子设定；N1 快照必须包含 `rng48`（或把该状态移入客体内存）；屏蔽战斗期间的 `srand48(time)`。 |
| S3 | `battleRand`（xorshift128，状态在客体 .bss）：首次使用时以 `time(NULL)` 设种子。调用者为专用战场 `BattleStage5_5` 的推进与场景效果。 | 静态反汇编（`initBattleRand` 0x1d16c4 → `time`）。本次地图 1011 未调用。 | 开战时以比赛种子初始化（钩子），否则该战场会分歧。快照需包含客体 .data/.bss，而不只是堆。 |
| S4 | `BattleCommonActions::syncRand`：BattleGameMaster+0x4828 为 5 时调用 `lrand48`，否则由对象坐标与帧号确定性计算。 | 静态反汇编。原版即为联机同步设计。 | 联机模式下不进入模式 5 分支即为确定性；否则按 S2 处理。 |
| S5 | 未初始化的堆内容：结构体填充字节与复用堆块中的残留数据（残留内容又来自含时间的界面文字等）。 | 不清零时深度校验从第 0 帧不同（如控制器 +0x18 填充字节、单位 +0xdc），语义校验一致；分配时清零后对象内部完全一致。 | 战斗逻辑未观察到读取这些字节。联机校验值不能直接对原始内存计算：改为分配清零（calloc 语义），或只对已知字段计算。 |
| S6 | 堆布局（对象地址）随开战前的分配历史而变，跨进程可不同。 | 正常 AP 组两进程堆顶与分配块数不同，战斗状态仍逐帧一致。 | 每台机器各自快照与恢复不受影响；校验值需去除指针。仍需留意任何按地址排序的原生逻辑（本次未观察到）。 |
| S7 | 核心中位于客体内存之外的 C++ 静态状态：LAB 段位 AI（`ai_rng` 从不重置、`lab_frame`、前线跟踪、饱和/投资/战术状态、单位来源记录等）；KT-21 喷火单次击退记录 `flame_marks`/`flame_owners`（战斗逻辑，开战时清零）；音效队列（表现层）。 | AI 对战同进程第二场从第 0 帧分歧，而跨进程一致；`community_content.cpp` 第 241–243 行。 | 回滚时不会随客体快照恢复，N1 必须把它们纳入快照或移入客体内存；`ai_rng` 等应在每场开战时以比赛种子重置。PvP 不使用 AI，但喷火击退记录属于战斗逻辑。 |
| S8 | 浮点：核心以 `-O2 -ffp-contract=off` 编译，SSE2 运算确定；但游戏 `sin`/`cos`/`sinf`/`cosf` 绑定的 MinGW 静态数学库实现使用 x87 `fsin`/`fcos` 指令。战斗中 `sinf`/`cosf` 每帧各约 1000–1450 次。 | `objdump` 可见 `fsin`/`fcos`；调用次数由 `msd_import_count` 统计。 | x87 超越函数指令在不同厂商 CPU 上可能有末位差异（本机无法验证）。建议改为核心内的软件实现（确定性多项式），需要核心修改。 |
| S9 | 宿主 Python 计算的数学函数（`tanf`、`acosf`、`atan2f`、`tan`、`atan2`、`pow`、`exp`、`log` 等）经 UCRT，UCRT 在支持 FMA3 的 CPU 上走不同实现。 | `fma_check.py`：同一输入在 FMA3 开/关时，20 万个样本中 `sin` 1960、`cos` 2056、`tan` 5673、`acos` 1053、`atan2` 15、`exp` 273 个结果不同。本次战斗中这些函数调用 0 次。 | 不支持 FMA3 的 CPU 会得到不同结果。启动时调用 `_set_FMA3_enable(0)` 统一路径，或改为核心软件实现。 |
| S10 | `clock()`：战斗中只由语音播放调度（`Sound_RequestPlayVO`、`Sound_PlayVO(_2P)`）调用。 | 调用者记录。 | 不影响战斗逻辑；表现层在重模拟时应静音（N2）。 |
| S11 | `time`/`localtime`/`clock_gettime`：开战前由标题、主菜单、日期显示调用；战斗中未调用。原生 PvE 敌军控制器以 `getSecondSince1970` 设种子（LAB 与联机不使用）。 | 调用者记录；虚拟时钟时整段堆逐字节相同。 | 只需处理 S1–S3 中被保存下来的时间种子。 |

原版联机设计的参考：`BattleControllerNetPlayer::update` 按命令附带的帧号与当前帧（BattleGameMaster+4）比较，落后过多时调整游戏速度；即原版 Wi-Fi 对战本身就是“交换带帧号的输入命令”的确定性同步模型，这与 Rollback 的前提一致。

## 4. 其他测量

- 战斗中单位峰值：脚本对战 61–62、AI 对战 80。
- 开战时客体堆顶约 55 MiB（自启动以来累计，含界面与音频），存活分配约 6,500–7,000 块。快照大小与耗时属于 N1。
- 战斗中被调用的随机/时间导入：脚本对战仅 `clock`（每 300 帧约 16 次，语音）；AI 对战另有 `lrand48`。

## 5. 未覆盖

- 不同 CPU（Intel 与 AMD、无 FMA3 的型号）：只有本机结果。S8、S9 是跨机器分歧的主要风险。
- 只测试了地图 1011；`BattleStage5_5` 等专用战场、全部地图与全部单位未覆盖。
- 音频为静音模式，帧由驱动直接推进（无实时节拍与窗口输入）；真实音频回调、窗口线程输入转发未纳入。
- 模组单位与覆盖补丁、2v2、超过 10000 帧的单场。

跨机器验证方法（在另一台电脑上运行同一版本的正式版工作区）：

```
windows_runtime\python.exe verification\n0_20261010\run_shifted.py verification\n0_20261010\n0_run.py --tag other --normal-ap --zero-alloc --battles 1 --frames 10000
python verification\n0_20261010\compare.py verification\n0_20261010\runs\apE_*\battle_0.jsonl verification\n0_20261010\runs\other_*\battle_0.jsonl
```

参考记录为本机的 `runs/apE_*/battle_0.jsonl`（正常 AP）；`identical: true` 即一致，否则 `first` 给出首个分歧帧。

## 6. 建议修正（N0 的实施部分，待 M6 的核心工作完成后进行）

1. **比赛种子**：开战时由双方约定的种子统一设定 `rng48`、`AppMain+0x9c` 的 RandomMT、`battleRand` 状态（钩住 `initBattleRand` 或开战时写入）、段位 AI 的 `ai_rng`；屏蔽战斗期间的 `srand48(time)`。
2. **数学函数**：`sin`/`cos`/`sinf`/`cosf` 改为核心内的软件实现；宿主 Python 数学函数改为核心实现或启动时 `_set_FMA3_enable(0)`。需用 Intel 与 AMD 两台机器验证。
3. **分配清零**：`malloc`/`realloc` 新块清零，使深度校验与回放校验可直接覆盖对象内存。
4. **客体外状态清单**（交给 N1）：`rng48`、核心 C++ 静态状态（S7）、宿主 Python 中每帧读写战斗的状态（如 LAB 每帧写入的单位标记），逐项纳入快照或移入客体内存。
5. **联机校验值**：采用本审计的语义字段加去指针的对象字节（分配清零后），不使用原始堆 CRC。
6. LAB 本身无需修改：未指定 P2 编队时使用随机 NPC 编队是设计行为（`lab.py` 第 27 行）。

## 7. 文件

`verification/n0_20261010/`：`n0_run.py`（驱动）、`compare.py`、`fma_check.py` 与 `fma_check.json`、`xref.py`/`armdis.py`（静态调用者检索与反汇编）、`elf/libAppMain.so`（自原版 APK 读取的副本）、`runs/`（各次运行的逐帧记录、报告与截图）。主要对比运行：`fixC/fixD`、`apE/apF`、`aiC/aiD`、`noseedC/noseedD`、`v1/v2`、`off*`、`k_*`、`zA/zB`。

## 8. r42 复核与修正实施状态（2026-10-10，见 `docs/netcode/N1_N2_ROLLBACK_2026-10-10.md`）

- r42 复核：脚本对战（正常 AP、完全控制）2 场 × 10000 帧与 AI 对战 2 场 × 5000 帧跨进程逐帧一致；同进程结论与 r40 相同（运行 `runs/r42*`）。
- 第 6 节建议修正的实施（联机与回放模式，`netplay_session.NetplayMode`，本地游戏不变）：
  1. 比赛种子：已实施（宿主 `lrand48`、RandomMT、`battleRand`、核心静态状态 `msd_netplay_reset`）；`srand48(time)` 与时间种子由虚拟时钟确定。
  2. 数学函数：核心 sin/cos/sinf/cosf 软件实现（r43，误差 ≤ 1 ulp）；宿主 UCRT 关闭 FMA3 路径。跨 CPU 交叉验证仍待另一台电脑。
  3. 分配清零：已实施（`Probe.zero_fill`）。
  4. 客体外状态清单：核心静态状态以 `msd_netplay_state_*` 纳入快照；宿主侧状态见 N1 文档第 3.1 节。
  5. 联机校验值：采用本审计的语义字段与去指针对象字节（`netplay_session.checksum`）。
- 新增证据：捕获模式（原生混音回调按帧时间运行）与静音模式 3000 帧逐帧一致，混音不影响战斗逻辑（第 5 节“真实音频回调未纳入”的部分覆盖；实时输出模式未单独测量）。
- r43 在非联机对战中与 r42 逐帧一致（`runs/r43apC_*`、`runs/r43aiC_*`）。
