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
