# 模组目录 / Mods folder

每个模组是本目录下的一个文件夹 / Each mod is one folder here:

```
mods/
  author_mod/
    mod.json            清单 / manifest
    units/*.json        单位 / units（格式同本体单位文件 / same format as body unit files）
    patches/*.json      覆盖补丁 / value patches（可选 / optional）
    campaign/*.json     世界与关卡 / worlds and stages（可选 / optional，格式见 docs/CONTENT_AUTHORING.md 第 6 节）
    sounds/*.json       音效 / sounds（可选 / optional，格式见 docs/CONTENT_AUTHORING.md 第 7 节）
    events/*.json       自制 EVENT / custom events（可选 / optional，格式见 docs/CONTENT_AUTHORING.md 第 8 节）
    assets/             资源，文件名以 "author_mod_" 开头 / assets, names start with "author_mod_"
    LICENSE
```

`mod.json`：

```json
{"schema": 1, "id": "author_mod", "version": "1.0.0", "name": {"EN": "My Mod", "ZS": "我的模组"},
 "author": "you", "license": "CC-BY-4.0", "game_version": ">=26.10", "behavior_library": ">=2",
 "depends": [], "conflicts": [], "content": {"units": "units/", "patches": "patches/"}}
```

- 单位稳定键写成 `author_mod.<名称>`；运行时 UnitID 由游戏分配并保持不变（2048–5119）。Unit keys are `author_mod.<name>`; the game assigns and keeps runtime UnitIDs (2048–5119).
- 特殊行为用 `behaviors` 组合，可用行为见 `docs/modding/BEHAVIOR_CATALOG.md`。Special behaviors are combined through `behaviors`; see `docs/modding/BEHAVIOR_CATALOG.md`.
- 单位可按文件名引用本体资源与原版游戏资源，不要把原版素材复制进模组。Units may reference body or original game assets by file name; do not copy original game art into a mod.
- 世界与关卡 / worlds and stages：`"content": {"campaign": "campaign/"}`，每个文件含 `scenes`、`music`、`worlds`（不写 `assets`）；键以 `author_mod.` 开头；战场图集与音乐放在 `assets/` 并按文件名引用；只能引用本体、本模组与所依赖模组的内容。Each file holds `scenes`, `music`, `worlds` (no `assets`); keys start with `author_mod.`; battlefield atlases and music live in `assets/`; references are limited to the base game, this mod and its dependencies. 扩展世界选择界面目前暂缓显示 / the world selection screen is not shown yet. 世界写 `"ura_page": 4`（及 `ura_background`、区域 `map_position` / `native_name` 或自定义名称 `name`（11 种语言）、关卡 `map_position` / `thumbnail`）时显示在原生里地图第 4 页起，每区域可有 6 关 / a world with `"ura_page": 4` appears as page 4 (onward) of the native ura map, up to 6 stages per area; an area names itself with `native_name` (original name table) or `name` (11 languages) 关卡写 `"menu_background": true` 时，通关后作为主菜单背景的候选 / a stage with `"menu_background": true` joins the main-menu background pool once cleared (docs/CONTENT_AUTHORING.md section 2).
- 音效 / sounds：`"content": {"sounds": "sounds/"}`，每个文件为条目列表 / each file is a list of `{"key": "author_mod.cannon", "file": "author_mod_cannon.msdf", "type": "se"}`（`se`/`vo`/`bgm`，可选 `volume` 1–127、`gain` 0.1–8（解码后乘到采样上，核心 r53 起）、bgm 的 `loop` [开始秒, 结束秒] / optional `volume`, `gain` 0.1–8 applied to the decoded samples (core r53+), `loop` for bgm）。单位动作脚本 op23 可写音效键 `{"opcode": 23, "values": ["author_mod.cannon"]}`，关卡 `music` 可写 bgm 音效键；SoundID 由游戏分配（本体与模组合计 380 个）。Unit scripts may use sound keys in op23 and stages may use bgm sound keys as `music`; the game assigns SoundIDs (380 in total). 音频为 Ogg Vorbis，采样率与声道数不限，载入时转换为游戏混音所用的 16 kHz 立体声 / Audio is Ogg Vorbis at any sample rate and channel count; it is converted to the game's 16 kHz stereo mix format on load (core r52+).
- 自制 EVENT / custom events：`"content": {"events": "events/"}`，每个文件一个 EVENT，出现在 EVENT 浏览页，经女教官基地进入原生活动地图；目前支持 `clear_reward` 模式。Each file is one event shown on the EVENT browse page and played through the native event base and map; all seven modes of the historical events are supported (clear_reward, rescue, collaboration_rescue, parts, invitation, legacy_survival, current_cooperation), with token exchange shops, event medal shops and PART1/PART2 phases / 已支持历史 EVENT 的全部七种模式、代币兑换店、活动勋章商店与分期. 可选自制地图 `"map": {"image": ...}`（1440×709，区域 `position` 为该图像素坐标）与小关 `"thumbnail"`（128×56）/ optional custom map art (1440×709; area `position` is a pixel on it) and stage thumbnails (128×56). 小关可写出兵循环 `loop`、条件触发 `triggers`、开战预置单位 `placed` 与道具和俘虏放置表 `items` / stages may define a spawn loop, conditional triggers, pre-placed enemies and item/prisoner positions (docs/CONTENT_AUTHORING.md 第 8 节). 区域图标显示序号 1、2、3…；可选 `map_music`（活动地图与俘虏页 BGM，SoundID 或 bgm 音效键）与人质奖励 `portrait_image`（俘虏页立绘图像，不超过 400×500）/ area icons show numbers 1, 2, 3…; optional `map_music` (event map and prisoner page BGM, a SoundID or bgm sound key) and `portrait_image` for prisoner rewards (portrait picture, up to 400×500). 小关可写评级时间 `rank_times`: [S, A, B, C, D]（秒，逐项递增；超过 C 为 D）/ stages may set `rank_times` (seconds, increasing; slower than C is D).
- 语言 / languages：名称、说明等只写一种语言时全部语言使用它；只翻译了部分语言时，其余语言使用英语（没有英语时用第一种）。If only one language is given it is used everywhere; otherwise missing languages fall back to English (or the first language given).
- 补丁格式 / patch format：`[{"target": "s1xlv.kt21", "field": "shop_price", "value": 250}]`，只能改数值倍率与经济字段 / numeric multipliers and economy fields only.
- 目标可以是本体或模组单位的稳定键，也可以是原版单位 `unit:1` … `unit:399`（只影响该原版单位）/ targets may be stable keys or original units `unit:1` … `unit:399` (affects only that original unit).
- 启用与加载顺序记录在 `%LOCALAPPDATA%\MSD_WINDOWS_S1XLV\mods_enabled.json`（标题画面 OPTION 的 MOD 页将提供设置），重启游戏后生效。The enabled list and load order live in `%LOCALAPPDATA%\MSD_WINDOWS_S1XLV\mods_enabled.json` (the MOD page in the title OPTION will manage it); changes apply after restarting.
- 发布前可运行 / Check before publishing：`windows_runtime\python.exe content_tool.py check-mods`
- 校验失败的模组会被整体跳过并记录原因，不影响游戏本体。A mod that fails validation is skipped with its reasons recorded; the base game is unaffected.
- 启用、停用与加载顺序在标题画面 OPTION →“MOD 設定”中操作，重启游戏后生效；可选 `description`（语言代码 → 文字）显示在详情中。/ Enable, disable and order mods in Title → OPTION → MODS; changes apply after restarting. Optional `description` (language → text) appears in the details.
