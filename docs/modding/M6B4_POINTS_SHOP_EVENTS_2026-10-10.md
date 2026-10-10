# 模组 M6b-4：积分与商店类自制 EVENT、活动勋章商店与分期（2026-10-10，核心 r42）

## 1. 结果

| 内容 | 说明 |
| --- | --- |
| `legacy_survival` | 经原生 Survival 路由（WorldType 3、模式 5）战斗，关卡编号 61000+10×(区域+1)+小关+1；战斗所得为活动代币（存于该 EVENT 进度，原生 SURVIVAL 点数在活动中显示代币）。`"survival": {"template": "treasure_recovery_2015" | "melty_christmas_2015"}`：每关的 Survival 记录（得分与掉落规则）取模板活动的第 `survival_row` 行（缺省为小关序号），掉落表取模板活动；战斗左下的拾取物图标随模板（金币或星形）。 |
| `current_cooperation` | 经原生合作路由（WorldType 4、模式 6）：原生合作编队（含编队 AP 上限规则）与战斗，所得为合作积分。Survival 记录取原生 1.46 合作表的第 `survival_row` 行。联机合作属 M7。 |
| 代币兑换店 `shop` | legacy_survival、current_cooperation：`unit`（至多 31 个，原生单位商品编号）、`msp`（原生面额 10000/50000/100000，不限次数）、`medal`（10/30/50/100，可设次数）、`item`（六阵营核心 ItemID 8–13，各 1 个）；同一面额商品只列一次。 |
| 活动勋章商店 `medal_shop` | 任何模式：`{"unit", "price", "available": "event" | {"stage": 小关键} | {"score": 积分}}`；女教官基地底栏 SHOP 打开，所列单位只在该活动的勋章商店出售（与历史活动相同的专售）。 |
| 分期 `part1` | `{"areas": k, "shop": m, "names", "date", "image"}`：PART1 为前 k 个区域与前 m 个兑换商品，PART2 为完整 EVENT；浏览页两个入口，进度、代币与购买次数共用。 |

## 2. 原生依据

- 历史数据：Survival 记录 16 字（编号、得分与掉落参数、两张指向表、计数），掉落表每条 21 字；`getExSurvivalInfo` 按关卡编号在 `db+0x20` 表中查找（选择活动时写入）。兑换商品 32 字节原生记录 `(编号 u16, 类型, -, 单位/物品 ID, 图标, 数量, …, 价格)`；历史商店的面额商品与编号绑定：MSP 299–301、勋章 295–298、阵营核心 289–294。
- 原生商店按 `IsMenuShopEnable(编号)` 决定是否列出商品，开放位属于玩家存档并按历史商品编号而定；MSP 面额的售罄判定使用原生全局购买计数（勋章面额已由既有钩子改为活动内计数）。
- 核心 r42（`src/event_trial_hooks.cpp`）：`custom_token_row`——代币兑换店中，记录 +28 为 2 的商品（宿主只为自制 EVENT 写入）`IsMenuShopEnable`/`IsMenuShopEnable2` 返回开放；历史活动商品的 +28 为 0，沿用原生判定。导出 `msd_custom_event_shop_version()==1`，自制 EVENT 含兑换店时宿主检查。
- 已持有的阵营核心（单持有物品）原生商店不列出，与历史活动相同。

## 3. 修改文件

| 文件 | 内容 |
| --- | --- |
| `event_content.py`（含 `src/` 镜像） | 模式扩展到全部 7 种；`survival`、`shop`、`medal_shop`、`part1` 的校验与编译（Survival 表、兑换店表、勋章商店行、分期家族与两个浏览入口）；Survival/合作路由的关卡编号。 |
| `event_native_map.py`（含镜像） | `current_cooperation` 模式使用合作路由。 |
| `event_trial.py`（含镜像） | 自制勋章商店行并入活动勋章目录与专售登记；合作积分回写与基地“協力”面板按模式判定；拾取物图标按 EVENT 的模板样式。 |
| `src/event_trial_hooks.cpp` | `custom_token_row`、`msd_custom_event_shop_version`。 |
| 核心配置 | 根/src `core_runtime.json`、两份 `lab_runtime.py` 与根 `build/` 改为 `MSD_Core_LAB_r42_20261010.dll`。 |

## 4. 验证（`verification/m6b4_20261010/`，隔离存档，核心 r42，未计算 SHA-256）

测试模组 `tokenmod`（legacy_survival 两关、四类兑换商品、勋章商店；分期 EVENT `saga` 两个区域）、`coopmod`（current_cooperation）、6 个失败用例。

- 离线 9/9：模板不在列表、兑换店用于 clear_reward、单位商品数量不为 1、勋章开放条件引用不存在的小关、非原生 MSP 面额、MSP 设次数各自跳过并给出原因；Survival 路由编号；兑换与勋章单位列入引用。
- token 15/15：兑换商品记录与勋章商店行、勋章单位专售登记；Survival 路由（H+72=3、模式 5）与 Survival 表、`survival_row` 取模板第 6 行；开售前勋章单位不可购；自然战斗（玩家方原生自动出兵 1800 帧）后胜利，拾取物图标为金币样式，代币 0→110 与结算一致；胜利后勋章单位开放；兑换四类商品全部成功（单位、MSP +10000、勋章 +10、阵营核心 +1；测试存档已持有全部核心，隔离存档中先清除核心 8），代币扣除与购买次数正确，单位不可重复购买，自制商品记录开放标记为 2；勋章商店购买扣 30 勋章并获得单位。
- coop 5/5：合作路由（H+72=4、模式 6）、Survival 合作记录；原生合作编队（编队 AP 超上限时以勋章追加，隔离存档）进入战斗（场景 74→100）、自然战斗后胜利返回地图，合作积分 0→15 记入 EVENT 进度。
- phase 6/6：两个浏览入口（PART1 按日期在前）、名称（PART1 缺省加后缀）、分期关卡前缀；PART1 地图 1 区域 1 商品，PART2 2 区域 2 商品；PART1 通关在 PART2 中显示为已通关。
- restart 2/2：奖励单位、代币与购买次数在重启后保持。
- 回归（r42）：M6b-1 play/restart/off/others 15/3/4/4、M6b-2 14、M6b-3 18/6；历史 EVENT 分期 91、原生地图与商店 156、浏览页 118、历史勋章商店 20、商店反馈 9 项；M6a 11/11/2；M5 play、M4 MOD 页通过。M3 运行检查的 `merged` 项因其 `bad_text` 单位按新语言规则载入（多一个槽位）而不符，与 M6b-1 记录的预期变化相同。

## 5. 限制

- Survival 得分与掉落规则只能从两个历史模板中选行，不能逐项编写。
- 兑换商品只限原生面额与阵营核心；单位商品至多 31 个。
- 合作活动的联机部分未实施（M7）；离线合作沿用原生编队规则。
- 代币来自原生战斗得分；受控验证使用自然战斗 1800 帧，未覆盖完整通关与长时间游玩。
