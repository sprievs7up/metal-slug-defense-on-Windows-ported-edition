# 合作活动单位的获取路径与直接给予（2026-11-10，AGENTS 第 367 节及 R1）

适用：历史 EVENT 合作活动 `cooperation_2016_current`（第一期 5 区域 20 关，第二期 6 区域 24 关）。数据为 `historical_events/unit_rewards.json`，宿主实现为 `event_trial.py`（含 `src/` 镜像），区域任务计分门槛由核心 r160 的钩子换算（`src/event_trial_hooks.cpp`）。

## 1. 现状核查（静态反汇编与隔离运行）

合作关卡在本移植中为本地单人流程：活动浏览页 → 女教官基地 → 出擊 → 活动地图选区域与关卡 → 选难度 → MISSION START → 战斗。战斗中只有玩家自己的编队与敌方，不需要联网，也没有 NPC 队友；基地“協力”面板对应原版的联网搜索搭档，获得下列单位不需要使用。

每场胜利按关卡得到固定点数（与击杀数、战斗时长无关；隔离实测各区域相同）：NORMAL 20、HARD 25、EXPERT 30、HELL 45；战败为 0。原生 `SC_BattleEnd` 的合作分支把这一点数同时加到三处：合作评价点数（`AddSurvivalPointSaveData`，宿主回写为活动积分，兑换店的货币）、累计评价点数（`AddTagTeamRankPointSaveData`，基地显示为“階級積分”，不因兑换减少）与该区域的分数（`AddTagTeamJobScoreNumSaveData`，区域任务的计分项）。

| 单位 | 原生获取方式 | 修改前的状态 |
| --- | --- | --- |
| 霍特‧萊恩 385、泰勒‧艾爾森 381、葛姆雷特 386、紅眼 382、EMAIN MACHA 384、正規軍卡車 396 | 区域任务（分数 2000 + 该区域 4 关 S 级）两项领取后，`PopupResultJobAreaJobRewordEventMSD` 按区域号查表 `0x8fda4c` 以 `SetUnitBuySaveData` 直接给予 | 可正常领取（新玩家存档实测第 6 区域 → 正規軍卡車）；每区 2000 分需 45–100 场胜利 |
| 大魔王 373–376 | `SC_BattleEnd`：`GetTagTeamMyRank() > 21`（階級積分 10000–99999）时开放兑换店商品 334–337，每个 10000 点购买 | 达标后才可购买；新玩家兑换店不列出 |
| 巨型章魚 380（挪威海怪） | 兑换店商品 341（5000 点）；1.46 原生代码中无可达的购买位写入（`SaveDataInitUserData`、`UpdateAppVersion`、`BattleEndGetResult` 均不含 341，区域与关卡结算表无对应项） | 永远不列出，无法获得 |
| Party People 370–372 | 宿主勋章店规则 `score`：活动积分峰值 ≥ 10000 后以 10 / 30 / 90 勋章购买 | 达标后才可购买 |
| Cabrakan 342 | `BattleEndClearEventStage`：WorldType 3 世界 0 区域 4 关卡 3（合作第 5 区域第 4 关 61054）首次通关时 `BattleEndGetResult(5, 317)`，兑换店 2000 点购买 | 本移植合作活动以 WorldType 4 运行，判定不成立，永远不列出 |

## 2. 现行规则（用户决定）

- 区域任务的计分项：满额门槛由 2000 改为 400（`area_task_score`），四级各 100 分；每级的奖励（10000 MSP、50000 MSP、5 勋章、10 勋章）、S 评级项与区域奖励单位不变。每区需 9–20 场胜利。
- 大魔王 ×4、巨型章魚、Party People ×3：階級積分（累计评价点数）达到 1000 时直接给予，约 23–50 场胜利；完成约三个区域的计分项（3 × 400）时即已达到。
- Cabrakan：61054 在宿主活动进度中有胜利记录时开放兑换店商品 317 的购买位（`SetMenuShopEnableNewSaveData`，商店显示 NEW），仍以 2000 点购买。
- Party People 在 `medal_shop.json` 中的开售条件为 `unit_reward`：不在勋章店列出，商品号仍登记为活动专属（普通商店不出现）。第一期因此没有勋章店商品，基地底栏 SHOP 打开兑换店（既有回退）。

## 3. 实现

### 3.1 区域任务计分门槛（核心 r160）

原生四级门槛 500 / 1000 / 1500 / 2000 是 `PopupResultJobScoreRewordEventMSD`、`OpenEventMSDJobWindow`、`GT_EventMSDJobMeterScoreDraw` 中的立即数，分数都经 `GetTagTeamJobScoreNumSaveData`（0x169280，`app + (区域 + 0x24ea) × 4`）读取。宿主启动时把 `area_task_score` 写入 `0x1ffef340`（'JOBS' + 门槛，须为 4 的倍数；核心导出 `msd_event_job_score_version` 时才写入）。

- 钩子 `job_score_scaled`（块 0x10169281）：上述三个函数的四个调用点（返回地址 0x1f48c8、0x1f81aa、0x1f8398、0x1f9776）得到 `分数 × 2000 / 门槛`，原生的领取判定、进度条与“下一门槛”选择不变。
- 钩子 `job_score_text`（块 0x101f81df，任务窗口文字“分數: x / y”的组字块，r9 分数、r10 门槛）：换回实际分数与实际门槛。

存档中的区域分数保持实际值；此前已超过 400 分的区域直接显示为满额、可领取。

### 3.2 单位给予（宿主）

给予方式与原生区域任务奖励相同（`SetUnitBuySaveData`，单位带 NEW 标记，并按原生规则补进编队空位），随后写入原生存档。大魔王与巨型章魚同时静默写入其兑换店商品 334–337、341 的开放位（单位已拥有，目录不列出），原生在階級積分达到 10000 时因此不再显示“追加商品”。条件在进入活动、战斗结算、活动积分变化后核对；核对与弹窗只在活动基地（场景 67 状态 1）或活动地图（场景 160 状态 9 / 13）连续静止 30 帧时进行，避开闸门动作、战斗、商店、原生弹窗与首次进入基地时的说明文字窗口（`GT_TagTeamTextWindow`）。已达到条件的旧存档在进入活动时补发。

弹窗沿用原生写法：标题为合作文字 `GetStringCoop` 10「階級積分」，内容为 `GetStringLoginBonus` 3「獲得了「%s」。」，同名多个时为 1「獲得了%d個「%s」。」；单位名取 `GetMenuUnitName`（游戏语言）；每个弹窗至多 2 行（八个单位共 3 个弹窗）。日、韩文的 1 号格式 `%s` 在 `%d` 之前，按占位符种类替换。

## 4. 验证（`verification/event_task_units_20261110/summary.md`，隔离存档，未计算 SHA-256）

- 修改前核查：`driver_probe.py`（区域任务给予、兑换店目录与购买位、本地一战的增量）、`driver_gain.py`（各难度每场得分：自然打完的 NORMAL 一场约 69 秒得 20；受控胜利 NORMAL 20、HARD 25、EXPERT 30、HELL 45，第 1、2、3、5、6 区域取样相同）。
- 核心 r160：`driver_probe.py --seed --area 5 --score 400` 领取四级计分奖励与区域奖励（正規軍卡車），窗口显示“分數: 400 / 400”；`--score 399 --expect-incomplete` 只领取三级、区域奖励不发放，显示“399 / 400”。
- `driver_rewards.py --seed --part1`：8 项通过（階級積分 1000 进入基地后八个单位给予、弹窗 3 个且在开场说明之后；商品 334–337、341 开放位已写入；勋章店目录不含 Party People；61054 胜利后商品 317 开放、兑换店列出 317 且不列出 334–337、341）。
- `driver_rewards.py --seed --battle`（第二期）：8 项通过（990 点进入活动不给予；本地出击一场受控胜利至 1010 点，回到地图后给予并弹窗；再把階級積分写为 9990 后赢一场至 10010、段位 22，无“追加商品”弹窗）。
- `tests/`（unittest discover）22 项中 21 项通过，`msd_aot` 导出检查为既有失败。

## 5. 未覆盖与限制

- 只验证了繁体中文画面；其余语言的格式串经静态读取（德文、简体表为空，由游戏自身的文字回退处理，未实机查看）。
- 新获得的单位按原生规则补进编队空位，编队 AP 可能超过所选难度的上限（NORMAL 1000、HARD 1500 等），此时原生提示以 30 勋章追加上限 500 或需自行调整编队。
- 每场得分只取样了第 1、2、3、5、6 区域的部分难度；通关评级对得分的影响未单独测量。
- 自制 EVENT 中合作模式（`current_cooperation`）的区域任务同样按 `area_task_score` 换算，未实测。
- 实机鼠标操作、全解锁存档、两机联机未测。
