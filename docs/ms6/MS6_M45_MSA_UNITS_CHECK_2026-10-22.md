# MS6 任务 4 / 5 拟移植的 6 个 MSA 单位：资料核查

日期：2026-10-22（Asia/Shanghai）。性质：只读核查。游戏代码、内容、核心与两个固定运行目录未改动；未计算 SHA-256。
依据：MSA 7.13.0 官方数据（`F:\egg\research\metal_slug_attack\`，arm64 `libAppMain.so` build-id `9acaace5…`）与 MSD 1.46 原生库（`game_data/original.apk` 的 armeabi-v7a `libAppMain.so`）。脚本与输出在 `verification/ms6_m45_msa_units_20261022/`。

## 1. 结论

- 6 个单位在 MSA 7.13.0 数据中均有完整资料：动作记录、全部图集、脚本引用的全部音效均在转储中且可解码；主数据表中有数值、单位说明与技能说明。6 个单位都没有单独立绘（`unit_illust_<UnitID>`），MSA 中本无此文件。
- MSD 1.46 原生库中没有这 6 个单位的动作类（钢铁哨兵属于 MSD 保留了未发布动作类的情形，这 6 个不属于），移植时行为须在 C++ 行为库中新写，或以 MSD 原生的相近动作类加钩子实现。
- 一千八百万能量核心在 MSA 中由两个单位组成：1575 为修筑者（动作类 `KouheiHp`，图集为沙包兵 `donou.obm`），1576 为修筑出的建筑（`EnergyCore1800`）。修筑对象由主数据表 `m_unit_make` 指定（1575 → 1576，修筑时间 30），与 MSD 沙包工兵 5 → 沙包 4 的方式相同；MSD 本体已有的工兵生命设定（AGENTS 第 6.3 节）对应 MSA 的 `KouheiHp`。

## 2. 单位、UnitID 与动作类

| 用户名称 | MSA 名称（英 / 简中 / 繁中） | MSA UnitID | 开放 | 动作类 |
| --- | --- | --- | --- | --- |
| 飞行护盾 | FLYING SHELT / 飞行护盾 / 飛行護盾 | 858 | 2018-05-30 | `BattleAction_FlyingShell` |
| 暴食侵略者 | RAVENOUS INVADER / 暴食侵略者 / 暴食侵略者 | 859 | 2018-05-30 | `BattleAction_GruelingInvader` |
| 暴食飞行侵略者 | RAVENOUS WINGED INVADER / 暴食飞行入侵者 / 暴食飛行侵略者 | 1123 | 2019-05-02 | `BattleAction_GruelingWingedInvader` |
| Elder Centipede | ELDER CENTIPEDE / 蜈蚣长老 / 蜈蚣長老 | 1234 | 2019-09-19 | `BattleAction_Eldercentipedo` |
| 侵略者之王 | INVADER KING / 侵略者之王 / 侵略者之王 | 1426 | 2020-05-29 | `BattleAction_InvaderKing`（`createActionInvaderKing`） |
| 能量核心（修筑者） | 18000000 ENERGY CORE / 一千八百万能量核心 | 1575 | 2021-01-08 | `BattleAction_KouheiHp`（`createActionKouheiHp`） |
| 能量核心（建筑） | 同上 | 1576 | 未开放（2030-12-31，只由 1575 修筑） | `BattleAction_EnergyCore1800` |

关联项（同名或由上述单位派生）：

| UnitID | 名称 | 动作类 | 与主单位的差异 |
| --- | --- | --- | --- |
| 860 | FLYING SHELT（未开放） | `FlyingShell` | 动作记录与 858 相同；移速 0.5（858 为 1.5），绘制优先级 −10（858 为 −70），其余数值相同 |
| 1714 | KING'S COCOON 王之茧（2021-08-15 开放） | `createActionKingCocoon` | 技能说明：“巨大的摇篮”持续时间结束后王之茧变为侵略者之王；生命 Lv1 500000，AP 600 |
| 1715 | KING'S COCOON（未开放） | `createActionInvaderKing` | 动作记录与 1426 相同、数值相同、无能力类型 14，即王之茧变成的侵略者之王 |
| 1717 | KING'S COCOON（未开放） | `createActionKingCocoon` | 与 1714 相比生产时间 2100（1714 为 3200）、无能力类型 14 |
| 1070 / 1080、1569 | 飞行护盾 TYPE-B、TYPE-G | `FlyingShell_TypeB` 等 | 同系列变体，本次未展开 |
| 1407 / 1416 | 蜈蚣长老（熔岩） | `EldercentipedoRed` | 同系列变体，本次未展开 |

UnitID → 动作类的取得方式：MSA 库中该对应表为 0x4c80330 起每项 0x18 字节、下标为 UnitID 的数组，由无符号的初始化函数 0xc6d44c 填写（多数项为 `operator new` 建立的动作对象，350 项为 `createAction*()` 的返回值）。`msa_action_table.py` 以 unicorn 执行该函数、拦截 PLT 调用后按虚表符号还原类名，共 1977 项；已知项核对：287 / 288 → `IronSlider` / `IronSlider_2`，192 → `Alien`，200 → `WingedInvader`，5 → `Kouhei`。输出 `action_table.json`，重跑结果逐字节相同。

## 3. 资源

| UnitID | 图集（均为 PALETTE8 RGBA5551） | 矩形 / 帧 | 受击框 / 攻击框 | 脚本 | 脚本引用的音效（SoundID 名称，均有 `.msa`） |
| --- | --- | --- | --- | --- | --- |
| 858 | `Flying_shell_out.obm` 1024×1024 | 218 / 218 | 3 / 2 | 53 | 2122 SND_FSLT_ATK |
| 859 | `venusian_magaki_out.obm` 1024×1024、`venusian_magaki_magotto_out.obm` 256×256 | 388 / 390 | 3 / 5 | 52 | 232、283、330、345、869 |
| 1123 | `Gluttony_winged_venusian_base_0/1/2_out.obm` 各 512×512 | 228 / 228 | 2 / 2 | 43 | 345、869 |
| 1234 | `elder_centipedo_out.obm` 1024×1024、`elder_centipedo_ef_out.obm` 512×512 | 330 / 330 | 9 / 3 | 284 | 1359、2190、2191、2203、2273–2275 |
| 1426 | `504100invader_king_01/02/04/05_out.obm` 各 2048×2048、`_03` 2048×1024 | 536 / 536 | 2 / 12 | 90 | 643、1391、2097、2215、2382、2417–2419 |
| 1575 | `donou.obm` 512×256 | 51 / 51 | 4 / 1 | 17 | 281 SND_SE_DONOU、289 SND_SE_DONO_BREAK |
| 1576 | `51908EnergyCore_out.obm` 256×256 | 28 / 28 | 2 / 2 | 35 | 2516 SND_ANA_LAZER1_SSS |
| 1714 | `61006KIngCocoon01…04` 共 4 张（最大 2048×2048） | 271 / 271 | 3 / 1 | 43 | 2097、2185、2502、2592、2599 |

- 导出位置：`F:\egg\research\metal_slug_attack\decoded\units\<UnitID>\`（`record.json` 与图集 PNG，2026-10-22 新导出 858、859、860、1123、1234、1426、1575、1576、1714、1715、1717）。8 个动作记录的槽 0（菜单）与槽 6 预览均可正常绘制（`verification/ms6_m45_msa_units_20261022/preview/sheet_slot0_slot6.png`）。
- 图集全部为 8 位调色板，按钢铁哨兵的做法可直接转为 MSD 的 `OI 01 08`。侵略者之王的 5 张图集共约 1890 万像素（4 张 2048×2048），远大于现有任何本体单位。
- 图像朝向（图像表第二字）：858、859、1234、1714 为 270，1123、1426、1575、1576 为 90。
- 缩放与旋转：1123 有 4 处 op19 [75,75]（钢铁哨兵式的“缩小一号”，按记忆 `msa-port-no-shrink` 的规则处理前须逐处核对所属部件）；1234 的 op2 旋转 1479 处（节段身体运行时转向），op19 有 80 / 65 / 55 / 60 等多种比例；1426 的 op19 为 87–117 的逐帧缩放动画。

## 4. 数值（MSA 进化 1，等级插值锚点 Lv1 / 40 / 50）

| UnitID | AP | 生产时间 | 生命 | 击退门槛 | 移速 | 攻击 1 | 攻击 2 | 攻击 3 | 攻击 4 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 858 | 800 | 3000 | 25000 / 75000 / 87500 | −100 | 1.5 | — | 400 / 1200 / 1400 | 400 / 1200 / 1400 | — |
| 859 | 100 | 900 | 10000 / 30000 / 35000 | 10 | 4 | 300 / 900 / 1050 | — | 500 / 1500 / 1750 | 400 / 1200 / 1400 |
| 1123 | 120 | 800 | 10000 / 30000 / 35000 | −1 | 3 | — | 800 / 2400 / 2800 | 1400 / 4200 / 4900 | — |
| 1234 | 600 | 2600 | 100000 / 300000 / 350000 | 300 | 5 | — | 3000 / 9000 / 10500 | 3000 / 9000 / 10500 | — |
| 1426 | 10000 | 3600 | 800000 / 2400000 / 2800000 | 99 | — | 2000 / 6000 / 7000 | 30000 / 90000 / 105000 | 3000 / 9000 / 10500 | 20000 / 60000 / 70000 |
| 1575 | 45 | 1000 | 3000 / 9000 / 10500 | −100 | 8 | — | — | — | — |
| 1576 | 45 | 1000 | 50000 / 150000 / 175000 | −100 | 7 | — | — | — | 50 / 150 / 175 |

- 攻击 1 / 2 / 3 对应 MSD 的近战 / 远程 / 绝招组（MSA README 第 4.5 节）；攻击 4 为技能触发的附加攻击（859 被击退时的近程反击、1576 回避时的反击等）。
- 其他进化数值（射程、弹速、目标数、冷却、第二参数）与 ev5（AP 858 为 640、1426 为 2000 等）见 `units_summary.json`。MSD 无进化等级；钢铁哨兵的数值由用户逐项指定（第 182、194 节），这 6 个单位的数值同样待用户决定。
- 击退门槛 −100：MSA 中有 369 个单位为 −100、181 个为 −1，−100 的含义未核对（推定为不被击退）。MSD 原生对非正门槛按每次受击都击退处理（第 6.1 节），移植时需另行处理。

## 5. 单位说明与技能说明（MSA 简体中文文本摘要）

| UnitID | 普通 / 特殊攻击 | 4 项技能（版本技能 1–4，依次） |
| --- | --- | --- |
| 858 | 陨石 / 陨石结界；为保护飞行核心而造的巨大飞行兵器，前进时散布陨石 | 装甲强化、万能装甲、武装强化、陨石结界（特殊攻击次数增加） |
| 859 | 冲撞 / 滚动攻击；捕食火星人的凶暴宇宙人 | 刺猬弹反击（被击退时进行近程攻击）、武装强化、装甲强化、滚动攻击 |
| 1123 | 多次射击 / 入侵者火炎；不乘 UFO、自行飞行的入侵者 | 武装强化、万能装甲、多次射击（命中时有几率击退）、入侵者火炎 |
| 1234 | 强酸喷射 / 蜈蚣大前行；太古巨大生物 | 甲虫装甲、食人细菌（命中使属性耐性无效）、古代细菌（命中降低攻击力）、蜈蚣大前行 |
| 1426 | 侵略 / 神；可召唤无数存在 | 提亚马特（宇宙军所属奖励发动时生产侵略者之王，可发动 1 次狂热时光）、盾（友军宇宙军 HP 增加）、太阳（友军宇宙军攻击力强化）、马尔杜克（狂热时光延长） |
| 1575 | — / —；为纪念 1800 万下载撒下的能量源 | 装甲强化、武装强化、自我防卫（几率回避并在回避时攻击）、能量干涉（命中时几率禁止敌方特殊攻击） |

- 版本技能（`m_unit_ver` → `m_skill`）、属性耐性、狂热时光、所属阵营奖励均为 MSA 系统，MSD 无对应机制；钢铁哨兵移植时属性倍率未实施（第 176、182 节）。这些技能是否以其他方式实现由用户决定。
- 1576 的单位说明与技能说明为空（技能与 1575 同号：35、108、70、10）；“能量核心”的名称与用途说明按用户要求另写。

## 6. 动作类结构（符号表与虚表）

| 动作类 | 覆盖的虚函数 | 其他方法 |
| --- | --- | --- |
| `FlyingShell`（858 / 860） | update、shotBullet、startPosition、actionViewPosition | createMeteo、wobbling（浮动）、getGroundHigh、baseReturn、calcHp、bulletSp_getStartPos、bulletSp_setFallSpeed、getSpAtkTargetXpos、dead、spAttack |
| `GruelingInvader`（859） | 只有 update | —（其余沿用默认单位类） |
| `GruelingWingedInvader`（1123） | update、createObject、shotBullet、startPosition、actionViewPosition | createBullet、getTargetAngle、getAttackHitRect、getAppearXpos、reAppear、longAttack、spAttack |
| `Eldercentipedo`（1234） | update、createObject、shotBullet、draw、startPosition、actionViewPosition | appear、move、neutral、longAttack、spAttack、getSpAttackParts / PartsPos、spAttackHitRect、spAttackDisable、spAttackPlaySE、createSpAttackBullet、createSpAttackGroundEffect、createSmoke、resetSmoke、dead |
| `InvaderKing`（1426 / 1715） | update、createObject、shotBullet、damageAction、startPosition、actionViewPosition | appear、getAppearPos、longAttack、spAttack、createSpLaser、createSpGroundLaser、nockback、getNockbackLaserLength、setNockbackLaserTargetPos、clearGuardState、waitKingCocoon、waitKingCocoonState、dead；静态成员 kingCocoonBossAppeard、kingCocoonBossContinuePosX |
| `KouheiHp`（1575） | damageAction（4 字节），update 与 startPosition 沿用 `Kouhei` | — |
| `EnergyCore1800`（1576） | 只有 update | kouhei |

- 这些单位没有专用的 `BulletAction_*` 类；陨石、激光、强酸等投射物由单位动作类自身的 createObject / shotBullet / createMeteo / createSpLaser 等建立，经未导出的辅助函数，实施时逐个反汇编。
- MSD 原生已有的相关类：`Alien`（侵略者 192）、`AlienUFO`（193）、`WingedInvader`（200）、`BrainRobot`、`CrabTank`、`VFO`、`Kouhei`、`Donou`（沙包）等。`GruelingInvader` 与 `GruelingWingedInvader` 的父类为默认单位类，与 `Alien` / `WingedInvader` 无继承关系，图集也不同。

## 7. 能量核心（Power Core）的建筑特性

- 修筑：1575（`KouheiHp`）出场后以移速 8 走向前线，修筑 `m_unit_make` 指定的 1576，修筑时间 30（各等级相同）。MSA 中同类的工兵—建筑对共 19 个 `KouheiHp` 单位（如 950 → 951）与 27 个 `Kouhei` 单位（如 5 → 4 沙包、75 → 33 碉堡）。MSD 原生工兵的修筑对象为状态字 40（`BattleAction_Kouhei::update` 状态 50 以 `getStatus(39)` 调用 `createChildObject`），同一模式。
- 修筑者受击：`KouheiHp::damageAction` 只有 4 字节（推定为空函数，未逐条核对），即受击不撤退、生命耗尽才退场；1575 的生命为自身数值表（3000 / 9000 / 10500）。MSD 的工兵生命设定（`engineer_hp` 的 `hp` 方式）按修筑对象生命的百分比计算、耗尽时撤退，二者的生命来源不同，移植时以百分比或新增字段表达，待定。
- 建筑本体（`EnergyCore1800::update`，状态 → 动作槽）：10 / 20 播放槽 6（待机，不移动）；75 播放槽 7（能量释放：五道光束、攻击框 1、音效 2516，播完回状态 10）；80 播放槽 8（核心发亮的循环；MSA 普通受击不进入此状态，推定由硬直类技能触发，未核对）；100 / 110 / 120 播放槽 9，播完后在原点放共用爆炸 0xff04 并移除；131 为修筑开始时工兵交给它的状态（重算生命、播放槽 7、转入状态 75）。其余状态交给默认单位处理。每帧在条件满足时调用 3 个未导出的设定函数（参数均为 1），推定为控制效果免疫一类，未核对。
- 建筑数值：生命 50000 / 150000 / 175000，击退门槛 −100，攻击只有攻击 4（50 / 150 / 175，近攻击距离 10），配合技能“自我防卫”在回避时反击；本身不主动攻击。
- 与 MSD 原生沙包 `BattleAction_Donou` 比较：两作的沙包均为状态 10 / 20 槽 6、受击状态 60 槽 7（`damageAction` 在生命大于 0 时预约，播完转状态 10）、损毁状态 100 / 110 / 120 槽 8（播完移除）；MSD 另有状态 141 槽 6（修筑期间），MSA 另有状态 70 槽 15。（2026-10-22 更正：初稿把状态 60 写成修筑，把能量核心槽 7 写成出现动作。）用户已选定以 `Donou` 为原生动作类，方案见 `docs/ms6/POWER_CORE_PORT_PLAN_2026-10-22.md`。

## 8. MSA 专有脚本指令（24 号以后）

`msa_script_ops.py` 解析 `BattleSprite::runScript`（0xd4d5e0）的跳转表，`msa_callback_overrides.py` 找到战斗对象的 3 个派生回调虚表（0x4ae6de8、0x4ae7290、0x4ae7fb8）。结果（`script_ops.txt`）：

| 指令 | 长度 | 作用 | 在战斗对象上的效果 | 本次 6 个单位中的使用 |
| --- | --- | --- | --- | --- |
| 24–29 | 1 | SkillStun / EnableNockBack / SkillAvoid 的 false / true | 派生类实现为空（返回 0） | 全部 |
| 30–33 | 1 | 未命名回调（虚表 +0xc0 / +0xc8）的 true / false | 派生类未覆盖，基类空函数 | 858、859、1123、1234、1426、1576、1714 |
| 34 / 35 | 1 | onEventEveryTimeAtk(false / true) | 转调对象虚函数 +0x1c8，推定为攻击框逐帧生效，未核对 | 859、1426、1576 |
| 36 | 5 | 挂子层（同 op11：脚本、层级、x、y），只在第一遍执行（runScript 在 op5 循环回开头时置 AnimationStatus +0x50，op36 见此标志即跳过；2026-10-22 补） | 有效 | 858（28 处）、1426、1576、1714 |
| 38 / 41 | 2 | 不透明度（百分比 × 2.55）与混合方式 1 / 7 | 有效 | 1426（38） |
| 39 | 6 | 子层偏移加 ((c−a)/100, (d−b)/100) | 有效 | — |
| 42 | 3 | 子层偏移加 (x, y) | 有效 | 1234（14 处） |
| 37 / 43 / 44 | 2 | 按攻击框表设定弹消框（旧 / 新）与组合攻击框 | 有效 | — |
| 45 | 5 | 主层：经 onEventMoveSpeedAnimation 按朝向设定对象速度与加速度（÷100）；子层：设定子层自身速度 | 有效 | 1234（127 处）、1426、1714 |
| 46 | 5 | 子层自身速度与加速度（÷100） | 有效 | 1234（166 处） |
| 47–58 | 1 | 未命名回调（+0xd8–+0x118） | 派生类未覆盖，基类空函数 | 1426（47）、1576 / 1714（57）、1714（58） |

- MSD 的指令只有 0–23。可删除的空操作：24–33、47–58（钢铁哨兵已删除 24 / 26 / 28）。可转换的：36 → op11。需要核心支持或离线换算的：38 / 41（不透明度）、42（子层偏移累加）、45 / 46（子层运动），以及 34 / 35 的确切语义。蜈蚣长老的节段运动依赖 45 / 46（共 293 处）与 op2 旋转（1479 处），是 6 个单位中脚本改造量最大的一个。

## 9. 移植前待决定 / 待核对事项

1. 数值：MSA 数值与 MSD 为同一尺度（钢铁哨兵核查，共有单位比值中位数 1.0），但侵略者之王（Lv40 生命 2400000、AP 10000）、蜈蚣长老（Lv40 生命 300000）远高于 MSD 现有单位；各单位的 AP、生命、伤害、击退门槛等按第 6.1 节由用户逐项指定。
2. 版本技能、属性耐性、狂热时光、所属阵营奖励是否以其他方式实现（第 5 节）。
3. 侵略者之王的出场方式（MSA 为阵营奖励触发与王之茧 1714 孵化），以及是否一并移植王之茧。
4. 飞行护盾用 858（移速 1.5）或 860（0.5）的数值。
5. 能量核心：名称 Power Core / 能量核心；修筑者 1575 用 MSA 沙包兵图集 `donou.obm`（MSD 原生沙包工兵是否使用同一图集未核对）；修筑者生命的表达方式（第 7 节）。
6. 击退门槛 −100 的含义（第 4 节），1123 的 op19 75 是否按“不缩小一号”改为 100，各动作类的状态与动作槽对应、投射物的建立方式（第 6 节），均在实施前逐个反汇编核对。
7. 侵略者之王的图集体积（第 3 节）对载入时间与显存的影响，实施时实测。

## 10. 产物

- 研究目录：`decoded/units/` 新增 11 个 UnitID 的导出；`decoded/master_tables/` 新增 `m_string_unit_info`、`m_string_skill_name`、`m_string_skill_info`（`msa_decode.py tables --names`）。
- `verification/ms6_m45_msa_units_20261022/`：`msa_action_table.py`（UnitID → 动作类，`action_table.json`）、`unit_summary.py`（`units_summary.json`）、`msa_script_ops.py`（`script_ops.txt`）、`msa_callback_overrides.py`、`msa_vtable.py`、`msa_func_bounds.py`、`preview/`（槽 0 与槽 6 预览）。脚本只读输入，运行方式见各文件开头说明。
