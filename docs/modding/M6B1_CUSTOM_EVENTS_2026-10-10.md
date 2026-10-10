# 模组 M6b-1：自制 EVENT 的格式与基础流程（2026-10-10，宿主，核心保持 r41）

M6b 按任务书第 11 节拆为四个子阶段；本文件记录 M6b-1。M6b-2（自制地图）、M6b-3（人质类）、M6b-4（积分与商店类）未实施。

## 1. 用户确认的规则

- **语言**：只填写一种语言时全部语言使用该文本；填写部分语言时未填写的语言使用英语；未填写英语时使用作者填写的第一种语言。适用于 EVENT、区域名、细则，以及本体与模组的单位文本、组合包文本（`content_locale.py`）。模组名称与说明在 MOD 页的显示规则相同（`mod_page.localized`）。
- **入口**：本体 EVENT 与模组 EVENT 使用同一格式，均经女教官基地进入；10 项历史活动保留现有数据。

## 2. 结果

- 本体 EVENT 放在 `community_content/events/*.json`（键 `s1xlv.`，目前没有），模组在 `mod.json` 写 `"content": {"events": "events/"}`。
- EVENT 出现在 EVENT 浏览页，按日期并入历史活动的循环序列；左屏可用 360×240 PNG/WebP（缺省为文字卡）；细则显示作者、日期、模组 id 与说明正文，与官方历史活动（SNK PLAYMORE CORPORATION）分开标注。
- “開始”进入原生女教官基地，“出擊”进入原生 EventMSD 地图（AREA SELECT），显示作者定义的区域与小关标记；区域名按游戏语言显示。
- 小关战斗、胜利结算、返回地图、MSP 奖励、首次胜利单位奖励；进度按关卡稳定键保存于 `historical_event_progress.json`（与历史活动相同的文件与事务流程）。停用模组后进度保留，重新启用后恢复。
- 引用：敌军与奖励单位（原版 1–399 或单位键）、战场（原版 0–137 或世界目录场景键）、音乐（原版 SoundID 或 bgm 音效键，M6a）；可见范围为本体、本模组与所依赖模组。
- 目前只支持 `"mode": "clear_reward"`；其他六种模式（rescue、parts、collaboration_rescue、invitation、legacy_survival、current_cooperation）在校验时给出“not supported yet”。

## 3. 数据格式

```json
{
  "schema": 1, "key": "author_mod.summer", "mode": "clear_reward",
  "names": {"EN": "Summer Festival", "ZS": "夏日祭"},
  "details": {"EN": "Optional text shown in the details popup."},
  "publisher": "author", "date": "2026-10-10", "order": 0,
  "image": "author_mod_summer.png",
  "areas": [
    {"key": "author_mod.summer.a1", "names": {"EN": "Harbor"}, "position": [420, 330],
     "stages": [
       {"key": "author_mod.summer.a1.s1", "marker": [-60, -20], "preview_frame": 0,
        "template": 1011, "scene": 21, "music": "author_mod.theme",
        "stamina": 5, "reward_msp": 40, "enemy_base_hp": 3000, "strength_steps": 0,
        "enemies": [{"unit": 2, "level": 10}, {"unit": "author_mod.scout", "level": 10}],
        "waves": [{"tick": 30, "enemy": 0}, {"tick": 120, "enemy": 1}],
        "reward_units": ["author_mod.scout"]}]}]
}
```

| 字段 | 说明 |
| --- | --- |
| `key` | EVENT 键；区域键以 EVENT 键开头，小关键以区域键开头。 |
| `areas` | 1–16 个（原生 EventMSD 每世界区域上限）；`position` 为世界地图图层（1440×709）上的像素坐标（x 0–1440，y 0–709），与原版区域坐标同一坐标系（M6b-2 核实后更正）。 |
| `stages` | 每区域 1–5 个（原生小关标记上限）；`marker` 为小关标记相对区域的偏移（±600），`preview_frame` 0–32。 |
| 小关其余字段 | 与扩展世界关卡相同（`docs/CONTENT_AUTHORING.md` 第 2 节）：模板关卡、战场、音乐、体力、MSP、敌方据点生命、关卡强化级数、敌军名单（1–32）、波次（升序，至多 8192）、首次胜利奖励单位（至多 8）。 |
| `image` | 360×240 的 `.png`/`.webp`；本体放在 `community_content/events/`，模组放在 `assets/`（以 `<模组 id>_` 开头）。 |
| `date`、`order` | 浏览页排序：插在日期不晚于它的最后一项之后，同日按 `order`。 |

## 4. 原生实现

- 编译（`event_content.compile_event`）：每个小关生成 120 字节原生关卡记录（写法同扩展世界），关卡编号为 `30000 + 1000×4 + 10×(区域+1) + 小关+1`（经典活动路由的原生世界 4，即万圣节使用的世界，不触发专用画面）；区域记录与小关标记记录以万圣节的原始记录为模板，写入坐标、小关数、人质编号 −1、音乐与预览帧。生成的数据与历史活动使用同一套结构（`trial.data`、`trial.tables`、地图清单、浏览条目），选择、基地、地图、战斗与结算沿用现有原生 EventMSD 流程与钩子，未改核心。
- 自制 EVENT 不借用原生关卡组：关卡记录只经地图钩子（`map_mission`）按关卡编号查找。
- 区域名：每个小关记录一项名称（取所在区域），按当前语言建表并缓存（`NativeEventMap.localized_names`），进入地图时写入。
- 地图背景、区域缩略图与小关标记的图形字段沿用万圣节模板；自制地图图集、缩略图、多页地图为 M6b-2。

## 5. 修改文件

| 文件 | 内容 |
| --- | --- |
| `event_content.py`（新增，含 `src/` 镜像） | 格式校验、引用检查、本体目录读取、编译。 |
| `content_locale.py`（新增，含 `src/` 镜像） | 语言补全规则与原生语言编号映射。 |
| `event_trial.py` | 初始化时编译自制 EVENT；自制 EVENT 不写原生关卡组；首次胜利单位奖励（`apply_unit_rewards`）。 |
| `event_native_map.py` | 合并自制 EVENT 的地图清单；区域名按语言建表。 |
| `event_browser.py` | 自制 EVENT 按日期并入；左屏图路径；细则作者与模组来源（`detail_lines`）；名称按 11 种语言。 |
| `community_content.py` | 单位与组合包文本的语言补全；接收模组 EVENT。 |
| `mod_loader.py` | `content.events`、引用可见范围、单位文本语言补全、`load(..., events=)`、状态 `events` 计数。 |
| `mod_page.py` | 详情显示 EVENT 数。 |

以上 `.py` 均有 `src/` 镜像。核心未改（r41）。

## 6. 验证（`verification/m6b1_20261010/`，隔离存档，核心 r41，未计算 SHA-256）

测试内容（`make_mods.py`）：`eventmod`（EVENT：两个区域三个小关，名称只写简体与日语、区域名部分翻译；模组单位只写英语；一个 bgm 音效）、依赖它的 `event_addon`、9 个失败用例，以及本体测试目录 `body_events/`（运行时将 `event_content.body_dir` 指向该目录，未写入游戏本体目录）。

- 离线 `check_offline.py` 30/30：语言补全三条规则与完整文本保持原顺序、未知语言与空文本拒绝；本体单位不变；两个有效模组载入；模式未支持、键前缀、图片尺寸、不可见单位引用、未登记音乐、小关超过 5 个、未知语言代码、日期格式、单位文本为空各自使模组跳过并给出原因；EVENT 与区域名的语言补全；模组单位只写英语时补全；小关编号；本体 EVENT 读取与本体可见范围；游戏本体目前无 EVENT；无模组时无 EVENT。
- 运行 `run_events.py`：
  - play 15/15：浏览页顺序（本体测试 EVENT 按日期插在一周年之后，模组 EVENT 在末尾）、左屏图替换、细则文字（作者、模组、说明）、名称补全；进入基地与 EventMSD 地图（WorldType 1、模式 3）、两个区域位于作者坐标、区域名按语言（繁中回退英语）；关卡记录中的敌军为模组单位与原版单位；战斗音乐为 bgm 音效键的 SoundID；胜利返回地图、进度与首胜奖励记录、奖励单位已拥有。
  - restart 3/3：重启后进度、奖励单位与地图通关标记保持。
  - off 4/4：停用全部模组后模组 EVENT 不出现，EVENT 进度与单位进度保留；re-enable 3/3：再启用后恢复。
  - others 4/4：依赖模组的 EVENT 与本体 EVENT 进入各自地图（坐标正确），地图与基地 BACK 返回主菜单并清除活动状态。
- 历史 EVENT 回归（r41，无模组）：`event_repair_20261008` 的分期 91 项、原生地图与商店（13 个入口）156 项、浏览页 118 项全部通过。
- 其他回归：M6a 离线 25/25、M5 离线 32/32、单元测试 6 项通过。M3 离线检查为 14/19：其失败用例 `bad_text`（单位缺少日语文本）按本次确认的语言规则成为有效模组，另外 4 项为该单位多占一个 ID 的连带结果，属预期的行为变化。

截图：`runs/play_*/sheet.png`（浏览页、细则、基地、地图、区域、战斗、结算后）。

## 7. 限制与待办

- 只支持 `clear_reward`；M6b-3/4 实施其他模式、人质与积分、商店、分期。
- 地图背景与缩略图固定使用万圣节模板，单世界（单页）；自制地图图集、缩略图与多页为 M6b-2。
- 小关解锁条件（`requires`）未支持，全部小关在地图中开放。
- 实际战斗为受控胜利（将敌方据点生命设为 0），自然通关未覆盖；实机窗口操作未覆盖。
- `content_tool.py check-mods` 已报告 EVENT 数与跳过原因；`validate` 尚未汇总 EVENT。
