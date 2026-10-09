# 性能、预加载与“模拟器”反馈任务书（2026-10-09）

本文件供后续对话接手使用。本轮仅形成任务说明，未修改代码。接手前先阅读 `F:\egg\AGENTS.md`（第 2、9、12.1、29 节，以及第 78 节性能审计），并重新核查本文引用的文件与数值。

## 1. 反馈原文（英文社群，转述整理）

社群用户对 1.47.x 的意见如下，原意保留：

1. The custom-built structure seems to be the same as the original MSD Android structure.
2. It uses emulation,
3. which will have a lot of glitches,
4. and has lag depending on your memory or GPU.
5. s1xlv should focus on the memory / GPU part of the emulation.
6. Add a preloading system; it should be more of a real `.exe` rather than emulation.

反馈未附带硬件型号、分辨率、具体画面问题或日志。第 78 节记录过一位 Windows 10、8 GB 内存玩家的菜单卡顿反馈，其 CPU、GPU 与分辨率同样未知。

## 2. 现行技术事实（2026-10-09 核查，HEAD `2162b2f`，核心 r31）

逐条对应反馈，区分已实现事实与推测：

| 反馈 | 现行事实 | 证据 |
| --- | --- | --- |
| 结构与安卓原版相同 | 属实且为设计目标：游戏逻辑来自原版 ARM 代码，经静态重编译为 C++ 并编译成 x64 DLL，场景、资源格式（OBM/MSDF）与原版一致。 | `src/build.py`、`src/generated/blocks_*.cpp`、AGENTS 第 3 节 |
| 使用模拟 | 部分不准确：CPU 指令不经模拟器执行，`static_cpu.py` 写明 “No ARM engine”，全部指令在预编译 DLL 中运行。仍有一层**平台适配**：原版调用的 libc、文件 I/O、JNI（Java）、OpenGL ES 由 Python 宿主转接；其中高频无状态调用（`sin/cos/memcpy/memset/memmove/clock/pthread_mutex*` 及 25 个高频 GL 调用）已直接绑定到 C++ 核心，其余（含 `glTexImage2D`、`glTexSubImage2D`、着色器编译、文件读取、文字光栅化）经 Python。GLES2 经 ANGLE 转为 Direct3D 11。 | `static_cpu.py:1-4`、`native_imports.py`、`probe.py:437,708`、`graphics.py:1,154-157` |
| 大量故障 | 未获具体报告，无法确认；需要收集截图、版本与日志。 | — |
| 延迟取决于内存或 GPU | 可能成立但未经低配验证：游戏线程单线程同步推进逻辑与渲染提交；全屏按显示器实际分辨率渲染（逻辑画布 1280×720），未提供内部渲染分辨率上限；纹理在原生场景初始化时按需解码与上传，文字在首次显示时光栅化，可能在首次进入场景或战斗时产生短时卡顿。高配设备菜单稳态无超 33.33 ms 的帧（第 78 节）。 | `player.py:49-53,92-102`、`verification/system_requirements_20261008/audit_summary.json` |
| 预加载 | 已有部分预取：`asset_cache.py` 后台线程预读全部 MSDF 及 `menu*/stage*/prisoner*/popup*/icon*/point_bar/battle*` OBM 原始字节（上限 128 MiB）；`native_audio.py` 后台解码音频（上限 128 MiB）。**未实现**：单位图集预取、GPU 纹理预上传、着色器预热、文字光栅缓存持久化。 | `asset_cache.py:26-40`、`native_audio.py:19,40` |
| 更像 `.exe` | 启动入口已是 `MSD WINDOWS S1XLV.exe`，其启动随包 Python 3.12 宿主；核心逻辑已为原生 x64 DLL。“完全原生 .exe” 意味着把宿主层（平台适配、窗口、音频、存档、LAB、EVENT、社区内容等根目录约 1.1 万行 Python）改写为 C++，属于大型工程，需单独立项评估。 | `player.py`、`portable_launcher.py`、AGENTS 第 3 节 |

内存布局：客体地址空间固定 256 MiB（`probe.py:22`），资源与音频缓存各 128 MiB 上限；高配机菜单稳态工作集约 650 MiB（第 78 节）。这些数值不等于最低内存需求。

## 3. 任务目标与非目标

目标（按优先级）：

1. **P0 测量**：在低配条件下定位卡顿来源，建立可复现的指标，再决定优化方向。
2. **P1 预加载**：消除首次进入战斗、场景与菜单页时的加载卡顿。
3. **P2 降低宿主转接开销**：把测量证实的高频 Python 转接调用移入 C++ 核心。
4. **P3 GPU 负载选项**：内部渲染分辨率上限、低配模式。
5. **P4 对外说明**：向英文社群准确说明架构（见第 8 节草稿）。

非目标（本任务内不做，需另行立项与用户确认）：用 C++ 全量重写宿主；修改游戏逻辑、平衡参数与原版画面内容；更换图形后端。

## 4. P0：测量（先做，产出决定后续）

1. **逐帧分项计时**：在 `player.py` 游戏线程循环中记录核心推进、宿主转接、GL 提交、`Present/glFinish`、纹理上传、文字光栅化、文件读取、音频解码各自耗时；超过 33.33 ms 的帧写入卡顿记录（帧号、场景/状态、主因、调用计数）。`probe.py` 已有 `self.calls`（`collections.Counter`），可扩展为按名称计时。记录写入运行目录的独立诊断文件，默认关闭，经环境变量或配置开启；读取诊断文件遵循 AGENTS 第 9 节共享句柄要求。
2. **场景覆盖**：冷启动至标题、主菜单、首次进入强化/商店、首次战斗入场、战斗中 40/80 单位、EVENT 浏览页翻页、EVENT 地图、LAB 对战。每项记录首次与第二次进入的差异，用于区分“首次加载”与“稳态”成本。
3. **低配条件**：至少一种集成显卡（Intel UHD/Iris 或 AMD APU）+ 8 GB 内存配置；若本机无低配设备，可用 ANGLE 的 WARP（软件 D3D11）或限制显卡（`gpu_select.py` 选择集显）作为下限参考，并如实标注其与真实设备的差异。分辨率分别测 1280×720、1920×1080、2560×1440。
4. **社群取证**：准备英文问卷（CPU、GPU、内存、系统、分辨率、全屏/窗口、版本、卡顿出现的具体画面、`player_error.log` 与诊断文件）。
5. 产出：`verification/performance_<日期>/` 的报告，列出每个场景的 p50/p95/max 帧时间、卡顿帧主因分布、峰值内存。

## 5. P1：预加载系统（依据 P0 结果调整优先级）

原则：只提前做原本必然发生的加载，不改变原生资源的所有权与释放时机；预加载失败时退回原有按需路径；内存上限可配置，并提供低内存模式。

1. **原始字节预取扩展**：`asset_cache.py` 现按文件名模式预取。扩展为按“即将使用”预取：主菜单闲置时预取当前三组牌组单位的图集（单位 → 图集名可从原生精灵描述符表 `0x10922f28` 与社区注册表取得）；进入关卡选择/EVENT 地图时预取该关卡场景与 BGM；LAB 准备界面按双方牌组与所选地图预取。
2. **GPU 纹理预上传（重点）**：卡顿的主要候选是原生场景初始化时的 OBM 解码（`OGLTexture::loadDirectObmData` / `loadIndexObmData`）与 `glTexImage2D` 上传。可评估两种方案：
   - 在闸门合拢或加载画面期间，调用原生 `BattleSpriteFactory` / `Image::createImage` 的既有入口，提前为下一场景创建纹理，并确认原生缓存会复用（避免重复上传与泄漏）；
   - 或在宿主侧缓存“解码后像素”，缩短 `glTexImage2D` 前的解码时间。
   两者都需核查原生纹理释放点（场景结束、`BattleObjectFactory` 等），保证内存不随场景累积。
3. **着色器与管线预热**：启动或标题画面期间完成 ANGLE 着色器编译与一次空绘制，避免首次战斗时编译。
4. **文字光栅缓存**：`text_render.py` 与 `TEXT_RASTER` 记录显示文字首次出现时光栅化；评估按语言持久化到用户目录缓存（不写入存档目录、可安全删除）。
5. **音频**：核查 `native_audio.py` 预取是否覆盖战斗 SE 与 EVENT/LAB 的 BGM；未覆盖的按场景预取。

## 6. P2–P3：转接开销与 GPU 选项

- **P2**：以 P0 的调用计数与计时为依据，把高频且可无状态实现的转接（候选：`glTexSubImage2D`、`glUniform*` 余项、文件 `fread/fseek`）加入 `native_imports.py`/`src/native_imports.cpp` 的直接绑定表；需要宿主状态的调用保留在 Python。每项变更前后对比帧时间与画面像素。
- **P3**：在设置（原生 OPTION 页风格）或 `player` 配置中加入“内部渲染分辨率”（例如 原生 / 1920×1080 / 1280×720），以较低分辨率渲染后缩放到窗口；评估垂直同步与低配模式（减少粒子或特效属于改变画面内容，默认不做）。核查 `gpu_select.py` 在双显卡笔记本上默认选择独显。

## 7. 约束与验收

约束（AGENTS 现行要求）：
- 在正式版 Git 工作区开发；测试使用隔离存档（`verification/lab_ui_20261006/save` 副本），禁止写入任何 `play_save*`、`lab_test_save`、LAB 配置与预设。
- 不计算 SHA-256；不暂存、提交或推送（用户经 GitHub Desktop 操作）。
- 完成并验证后，按第 2.2、2.3 节以明确清单同步 `dist/MSD_Windows` 与用户固定运行副本，并更新 `F:\egg\AGENTS.md`。
- 测试存档在 UTC 换日后会弹出原生登入奖励；回归驱动可用 `verification/event_fixes_20261009/run_shifted.py` 前移宿主墙钟运行。
- 原生核心修改需重建 DLL（`src/build.py --library <新名> --no-activate --no-sha256`），并跑既有回归：13 入口原生流程、浏览页、勋章商店、按钮反馈、对战页、双人对战（入口见 AGENTS 第 83、85 节）。

验收（数值在 P0 后与用户确认）：
- 低配参考配置下，第二次及之后进入同一场景无超过 100 ms 的帧；首次进入战斗的最长卡顿较基线明显下降（具体比例依 P0 基线确定）。
- 稳态帧时间 p95 ≤ 33.33 ms（1280×720 内部分辨率）。
- 预加载开启后峰值内存记录在案，并提供低内存模式。
- 画面与原版逐像素对照不变（预加载不改变绘制结果）；全部既有回归通过。
- 报告只陈述实测条件下的结论，不推广到未测试的硬件。

## 8. 对英文社群的说明草稿（发布前由用户审定）

> Thanks for the feedback. A clarification on how S1XLV works: the game is not run in a CPU emulator. The original ARM game code is statically recompiled ahead of time into a native x64 Windows DLL, so all game logic runs as native code. That is also why the structure matches the original Android game: the goal is to preserve the original game exactly. What remains is a thin platform layer (written in Python) that provides what Android used to provide: file access, fonts, audio, input, and translating OpenGL ES calls to Direct3D 11 through ANGLE. The most frequent calls are already handled natively.
>
> We agree that loading hitches and performance on lower-end memory/GPUs need work. Next steps: measuring where the stutters come from on low-end hardware, adding preloading (unit textures, stage assets, shaders, text), and an internal render-resolution option for weaker GPUs. If you see glitches or lag, please share your CPU, GPU, RAM, resolution, game version, and where it happens (and `player_error.log` if present). That helps us fix the right thing.

## 9. 关键文件索引

| 范围 | 文件 |
| --- | --- |
| 游戏线程与窗口 | `player.py`、`window_layout.py`、`frame_pacer.py`、`gpu_select.py` |
| 原生调用转接 | `probe.py`（导入分派约 437 行，时钟约 708 行，文件约 755 行）、`static_cpu.py`、`native_imports.py`、`src/native_imports.cpp` |
| 图形 | `graphics.py`（ANGLE/GLES2，GL 函数签名表约 150 行） |
| 预取与缓存 | `asset_cache.py`、`native_audio.py`、`text_render.py` |
| 既有性能证据 | `verification/system_requirements_20261008/`（`sample_menus.py`、`audit_summary.json`）、`docs/VALIDATION_2026.10.02.1.md` |
| 构建 | `src/build.py`（`--library`、`--no-activate`、`--no-sha256`） |

## 10. 进度记录

### 10.1 精简版 P0（2026-10-09，已完成）

- 范围：用户按额度限定为精简版，只测两种分辨率（1280×720、1920×1080）、三个场景（冷启动、首次进入战斗、战斗中），测试条件只用一种（强制 Intel UHD 集显）。游戏代码未修改。
- 驱动与结果：`verification/performance_20261009/p0_measure.py`，汇总见同目录 `SUMMARY.md`，逐帧数据为 `runs/*/frames.jsonl`。分项计时在驱动中包装 `Probe.dispatch` 完成；本任务书第 4 节第 1 条所述 `player.py` 内置开关尚未实现。
- 结论（高端 CPU + 集显，pbuffer，无交换链）：
  - 战斗稳态 total p95 为 12.4 ms（1280×720）与 13.9 ms（1920×1080），集显 GPU p95 为 4.9 ms 与 6.5 ms，3596 帧中各只有 1 帧超过 33 ms（战斗结束时的场景释放）。
  - 卡顿集中在一次性加载点：
    - 启动第 1 帧约 0.85–0.92 秒，主要为着色器校验与链接，glValidateProgram 约 0.5 秒；
    - 进入战斗首帧约 0.47 秒，其中 fopen 约 0.19 秒、malloc 0.04 秒、glTexImage2D 0.03 秒，核心约 0.13 秒；
    - LAB 准备界面打开约 0.28 秒，为宿主 Python 绘制；
    - 标题首帧约 0.16–0.19 秒。
- P1 优先级建议：
  1. 着色器预热或程序缓存（启动）；
  2. 进入战斗前的资源预取（fopen、解码、纹理上传）；
  3. LAB 准备界面的绘制缓存。
  
  依据为上述实测，需与用户确认。
- 未覆盖：低端 CPU、8 GB 内存、真实窗口与垂直同步、音频输出、40/80 单位高负载、二次进入对比、普通关卡与 EVENT 战斗。第 4 节第 3 条要求的 WARP 下限参考与 2560×1440 均未测；社群问卷（第 4 节第 4 条）未发布。

### 10.2 P1 三项（2026-10-09，已完成并同步）

按用户确认的顺序实施。均为宿主修改，核心保持 r32；测量条件同 10.1（Intel UHD 集显，1280×720，pbuffer）。

1. **着色器缓存**：新增 `shader_cache.py`，由 `graphics.py` 在 `eglInitialize` 之后登记 ANGLE `EGL_ANDROID_blob_cache` 的存取回调，关闭时保存。
   - 缓存位于 `%LOCALAPPDATA%\MSD_WINDOWS_S1XLV\shader_cache\<渲染器 crc32>.bin`，不在存档目录内，删除后自动重建，上限 64 MiB。`MSD_SHADER_CACHE_DIR` 可改变目录，设为空值时停用。
   - 第二次启动时 76 次查找全部命中，glValidateProgram 519 → 34 ms，启动第 1 帧 960 → 464 ms。
   - 首次启动仍需编译。剩余开销主要是 GLSL 着色器对象的编译（glGetShaderiv 约 90 ms），以及资源打开。
   - 标题画面比对：开启缓存与关闭缓存的运行只在一处约 36×47 的小区域有差异，两次关闭缓存的运行之间同样有差异，判定为随时间变化的标题动画，与缓存无关。
2. **进入战斗前的读取**：逐文件计时显示，LAB 进入战斗首帧打开 178 个文件，实际读盘合计约 34 ms。主要开销来自 LAB 存档隔离 `sandbox_open` 对每次读取都做 `Path.resolve()`，合计约 110 ms。
   - 修改 `lab_runtime.py`：只读请求在尚无虚拟文件时，或请求 `.obm`/`.msdf` 时，跳过路径解析，直接按原流程处理。
   - LAB 进入战斗首帧 470 → 约 265–305 ms。剩余部分为实际读取、原生分配（malloc 约 30 ms）、纹理上传（约 25 ms）和核心资源初始化（约 100 ms）。
   - 现有预读（界面、关卡、音乐）合计约 160 MB，已超过 128 MB 缓存上限；单位图集读盘收益约 30 ms，因此本轮不扩大预读范围。
   - 普通关卡的本地目录试探在基类中提前返回，原本就没有这项开销。
3. **LAB 准备界面**：整张画面原本已按版本号缓存，首次打开慢是因为缓存未命中。
   - 新增 `LabPrep.warm` 与 `Lab.warm_prep`：主菜单（28/1）稳定 30 帧后，每帧预热一项，依次为底纹、单位列表、地图目录、当前关卡缩略图。所用函数与打开时相同，画面结果不变。
   - 首次打开 210–280 → 约 105 ms。代价是主菜单空闲时有两帧稍超预算（约 57 ms、37 ms），每次启动只发生一次。

**附带修复**：第 90 节同步 r32 时，`core_runtime.json` 已改为 r32，`lab_runtime.LAB_CORE` 仍指向 r31。注册表中 KT-21 的 `ground_special_attack` 需要 r32，所以独立 LAB 入口（`Start_LAB.exe`/`lab_launcher.py`）启动时报 “Native core lacks grounded special attacks” 并退出。现已改为 r32。普通入口读取 `core_runtime.json`，不受影响。

**验证**：
- 精简 P0 驱动多次运行：冷启动、LAB 首次进入战斗、战斗，均成功。
- 窗口模式退出路径驱动 4 组（battle-close×2、menu-close、title-esc）退出码均为 0、无错误日志，窗口模式下缓存文件正常写出。
- 未运行 EVENT、双人对战、浏览页等其他回归。

**同步**：每个目标 9 个文件，目标为 `dist/MSD_Windows` 与用户固定运行副本。
- 文件清单：`graphics.py`、`shader_cache.py`、`lab_runtime.py` 及三者的 src 镜像，`lab.py`、`lab_prep.py`、本任务书。
- 同步前目标文件与 HEAD 一致，同步后逐字节一致；两个目标分别有 131、75 个存档与 LAB 设置文件，同步前后大小与修改时间不变。
- 覆盖前副本位于 `verification/performance_20261009/sync_before/`。

**未做**：首次启动的着色器编译（可考虑在加载画面期间编译）、P2 宿主转接迁移（malloc 线性空闲块搜索等）、P3 内部渲染分辨率，以及低配 CPU 与 8 GB 内存的实测。

**追加修复（同日，用户报告）**：LAB/双人对战按 OK 后会闪现一帧主菜单或 SHOP。

- 逐帧截图复现：场景进入战斗初始化（100）的当帧，宿主就松开了自己的闸门，而原生闸门要到下一帧才开始绘制，中间一帧露出主菜单。该问题与缓存无关，在本次 P1 修改之前就存在。
- 修复：`lab.py` 中宿主闸门在场景切换后再保持 2 帧才交给原生闸门。修复后逐帧截图确认不再露出主菜单。
- `lab.py` 已同步两个运行目录。

### 10.3 阶段状态与 P4 更新稿（2026-10-09）

- P1：用户确认的三项已完成（10.2）。第 5 节的其余项（扩大预读、GPU 纹理预上传、文字光栅缓存、音频预取核查、首次启动的着色器预热）实测单项收益均在几十毫秒以内，列为可选项。第 7 节的验收条件（低配实测、二次进入无超过 100 ms 的帧）尚未验证。
- P2、P3：依实测数据（战斗中宿主转接 p95 约 0.5 ms，集显 1080p 下 GPU p95 6.5 ms）暂缓，待取得低配设备数据后再决定。
- P4：以下为更新后的英文说明，取代第 8 节草稿，发布前由用户审定。

> Thanks for the feedback. A clarification on how S1XLV works: the game is not run in a CPU emulator. The original ARM game code is statically recompiled ahead of time into a native x64 Windows DLL, so all game logic runs as native code. That is also why the structure matches the original Android game: the goal is to preserve it exactly. What remains is a thin platform layer (Python) that provides what Android used to provide: file access, fonts, audio, input, and OpenGL ES through ANGLE (Direct3D 11).
>
> We measured it on an Intel UHD integrated GPU at 1280×720 and 1920×1080. In battle, frames take about 12–14 ms at the 95th percentile, well within the 33 ms budget of the 30 FPS target, and the GPU part is only about 5–7 ms. The stutters people notice come from one-time loading moments, not from battles themselves. The next update addresses these:
> - shaders are now cached after the first launch (the first frame on later launches is about 2× faster);
> - entering a LAB battle no longer does slow per-file path checks (about 470 → 280 ms);
> - the LAB setup screen is prepared while the main menu is idle (first open about 250 → 105 ms).
>
> Our test machine has a fast CPU, so results on low-end CPUs or 8 GB RAM may differ. If you still see lag or glitches, please share your CPU, GPU, RAM, resolution, game version, where it happens, and `player_error.log` if present.

### 10.4 P2 宿主转接（2026-10-09，已完成并同步）

依据实测排名，只处理有数据支持的两项，核心不重建（仍为 r32）。

1. **三个每帧 GL 调用改为直接绑定**：`glClear`、`glDepthFunc`、`glClearColor` 加入 `native_imports.GRAPHICS`，复用核心已有的调用类型 32（单个整数参数）和 53（四个浮点参数）。经核查，宿主对这三个调用没有附加状态；`clear_bars` 从 GL 状态读回清屏色。`glViewport` 需要做坐标缩放，继续留在 Python。
2. **`Probe.free` 改为二分插入并只与相邻块合并**：空闲块表本来就保持“按地址排序且相邻块已合并”，因此结果与原来的整表排序加全量合并完全相同。`alloc` 的首次适配逻辑未改。
   - `verification/performance_20261009/test_allocator.py`：40 组随机种子各 5000 步，每次分配返回的地址与空闲块表逐步一致；在约 290 个空闲块的碎片程度下，速度为原来的 4.8 倍。

**A/B 实测**（`p0_measure.py --p2-off` 作对照，60 秒战斗，交替各两轮，Intel UHD，1280×720）：
- 战斗中每帧宿主转接 p50：0.12–0.15 → 0.06 ms；
- 战斗中最长一帧：18.6–19.8 → 9.2–11.1 ms；
- 战斗中 p95：6.0–6.5 → 5.7 ms。

这台机器上收益很小，符合 P0 的判断（宿主转接不是瓶颈）。

**测量修正**：10.1 节的 P0 基线运行时，驱动把 probe 日志逐行刷写到 console.log，这会抬高每帧耗时；当时战斗 p50 为 8.2 ms，在与游戏一致的条件（stdout 为 None）下约为 3.5–4 ms。10.1 节中卡顿点的结论（一次性加载帧）不受影响。

**验证**：分配器等价性测试、A/B 实测、120 秒战斗完整运行（进入、对战、结束）均成功；窗口模式 battle-close、menu-close 退出码均为 0。未运行 EVENT、双人对战、浏览页回归。

**同步**：每个目标 5 个文件，目标为 `dist/MSD_Windows` 与用户固定运行副本：`probe.py`、`native_imports.py` 及二者的 src 镜像、本任务书。同步前目标文件与 HEAD 一致。

**未做**：`alloc` 的首次适配线性查找（需要更复杂的数据结构，收益未测）、`fopen` 与 `glTexImage2D`（进入战斗时的一次性开销）。

### 10.5 P3 内部渲染分辨率上限（2026-10-09，已完成并同步）

- **设置**：游戏根目录 `display_settings.json` 的 `max_render_height`，默认 0（按窗口实际分辨率渲染，行为不变）；环境变量 `MSD_MAX_RENDER_HEIGHT` 可覆盖。例如设为 1080 时，2560×1440 全屏以 1920×1080 渲染。
- **实现**（`graphics.py`）：使用 ANGLE `EGL_ANGLE_window_fixed_size` 创建固定尺寸的窗口表面，高度为上限值，宽度按窗口宽高比计算，由 D3D 在呈现时放大到窗口。
  - 窗口宽高比变化（切换全屏或窗口）时重建表面，GL 上下文和已加载资源保留，并重新设置垂直同步间隔。
  - 鼠标坐标按窗口尺寸换算，不受影响；扩展不可用时回退到普通窗口表面。
  - pbuffer（验证驱动）路径不变。
- **验证**：
  - 真实窗口退出路径驱动在上限 480 下 battle-close 退出码 0，日志记录 `RENDER_FIXED_SIZE 853 480 window 1280 720`，标题截图为 853×480 且内容正确；
  - `verification/performance_20261009/test_render_cap.py` 在真实窗口中依次测试 1280×720 → 1440×900（重建为 768×480）→ 同尺寸（不处理）→ 去掉上限（1280×720 普通表面）→ 重新开启，各步清屏读回正确。
- **限制**：
  - 放大由 DXGI 完成，像素画会略显柔和；
  - 尚无游戏内设置界面，需手动编辑 JSON；
  - 低端显卡上的实际收益未测。
