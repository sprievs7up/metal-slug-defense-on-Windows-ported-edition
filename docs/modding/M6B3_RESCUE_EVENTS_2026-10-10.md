# 模组 M6b-3：人质类自制 EVENT（2026-10-10，宿主，核心保持 r41）

## 1. 结果

自制 EVENT 新增四种模式，均经原生 EventMSD 地图、原生俘虏页（POW LIST）与战斗中的原生俘虏运行：

| 模式 | 规则 |
| --- | --- |
| `rescue` | 区域内各关救出的俘虏合计达到上限时，给予该区域 `reward.unit`（原生俘虏页显示 COMPLETE）。 |
| `collaboration_rescue` | 猫咪联动的救人质玩法，规则同 `rescue`。自制版本使用经典地图路由与自制地图（M6b-2）；猫咪专用的两页地图与每区域一关的路由未采用。 |
| `parts` | 每个区域是一个零件（`reward` 只写名称与人物，不写单位）；区域内任一关救出全部俘虏即获得该零件；全部零件到齐给予 `final_reward_units`。 |
| `invitation` | 各关的俘虏为邀请函；含邀请函的区域自动生成俘虏页记录（不给单位，缺省名称“邀请函/邀請函/招待状/Invitation”），全部救出给予 `final_reward_units`。 |

新字段：

```json
"final_reward_units": ["author_mod.boss"],                      // parts、invitation
"areas": [{"key": "...a1", "names": {...}, "position": [x, y],
  "reward": {"unit": "author_mod.vip", "portrait": 1,           // rescue / collaboration_rescue 写 unit
             "names": {"EN": "VIP"}, "info1": {...}, "info2": {...}},
  "stages": [{"key": "...s1", "prisoners": 2, ...}]}]
```

- `prisoners`：0–10，该关战斗中的俘虏数（原生关卡记录词 7），同时为地图标记与俘虏页的上限。
- `reward.portrait`：0–40，原生俘虏页人物图像编号；`names` 必填，`info1`/`info2` 缺省为“只要解放所有俘虏 / 就能获得奖励！”（四种语言，其余按语言规则补全）。
- 首次获得的奖励单位为 Lv1、开放阶段 20（与扩展世界首胜奖励相同）；原生俘虏页在达成时同样会显示获得单位。

## 2. 原生依据与实现

- 历史数据核对：关卡记录词 7 等于地图标记的 `pow_max`（盛夏 32011 为 2、巨灵 33011 为 1、黑色诺亚 12091 为 1）；区域记录 +16 为俘虏编号；俘虏记录为 6 个字（编号、人物图像、−1、1、奖励 UnitID、−1）加 11 种语言的名称与两行说明（按原生语言编号排列）。
- 编译：俘虏编号为 200+区域序号（避开原生 0–69；地图与俘虏页钩子按活动内俘虏表回应）；小关的 `prisoners` 写入关卡记录词 7 与标记上限；俘虏页文字按 `content_locale.language_codes` 的原生语言顺序写入。
- `event_native_map`：自制 EVENT 的无奖励俘虏（邀请函）同样计入上限（历史活动保持原规则）。
- `event_trial.apply_prisoner_rewards`：区域奖励沿用原有判定（rescue 合计、parts 取最大）；自制 EVENT 的 `parts` 与 `invitation` 在全部零件/邀请函到齐时给予 `final_reward_units`（`reward_claims.final`）；历史巨灵活动的 UnitID 285 规则保持。
- 核心未改。

## 3. 修改文件

`event_content.py`、`event_native_map.py`、`event_trial.py`（均含 `src/` 镜像）。

## 4. 验证（`verification/m6b3_20261010/`，隔离存档，核心 r41，未计算 SHA-256）

测试模组 `rescmod`：四个 EVENT 与四个奖励单位（只写英语）；7 个失败用例。战斗为受控胜利：战斗进行后每帧写入 `BattleMain+36`（`getGetPrisoner` 读取的救出数）并将敌方据点生命设为 0。

- 离线 10/10：奖励用于 clear_reward、clear_reward 设俘虏、parts 区域缺奖励、parts 奖励写单位、final_reward_units 用于 rescue、奖励区域无俘虏关、人物编号越界各自跳过并给出原因；奖励文字补全；邀请函缺省记录。
- play 18/18：rescue 的俘虏表与原生 POW 按钮、关卡记录词 7、部分救出不给奖励、补满后给予区域单位、救出数按上限保存、俘虏页（截图：COMPLETE、1/1、2/2）；collaboration_rescue 给予奖励；parts 的零件标志、第一个零件不触发最终奖励、两个零件到齐给予最终单位；invitation 的俘虏页记录（截图：邀請函、未達成）、第一封不触发、全部救出给予最终单位。
- restart 6/6：四个奖励单位、领取记录与地图上的救出数在重启后保持。
- 回归：M6b-1 离线 30/30 与 play 15/15、M6b-2 14/14、历史 EVENT 分期 91、原生地图与商店 156、浏览页 118 项通过。M6b-1 的失败用例 `bad_event_mode` 由 `rescue` 改为仍未支持的 `legacy_survival`。

过程中发现并修正：`references()` 的一次编辑使音乐与战场引用不再列出（未登记音乐未被拒绝而在编译时报错），修正后由 M6b-1 离线检查覆盖。

## 5. 限制

- 自制 EVENT 的俘虏图像使用原生人物编号；不支持自制人物图。
- 历史黑色诺亚活动（`invitation`，无俘虏记录）在 EventMSD 关卡页同样显示 POW 按钮，进入后显示原生缺省数据；该既有行为未修改。
