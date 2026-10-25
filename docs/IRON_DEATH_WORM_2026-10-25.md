# 钢铁死亡蠕虫（Iron Death Worm）

日期：2026-10-25（Asia/Shanghai）。状态：R2（第 8 节，核心 r92，行为 v2，行为库 19）已实现、工作区已验证，2026-10-25 按用户要求同步至两个固定运行目录（第 9 节）。第 2–6 节记 r91，与第 8 节不同之处以第 8 节为准。生成脚本 `artwork/iron_death_worm_20261025/build_iron_death_worm.py`，验证脚本与记录 `verification/iron_death_worm_20261025/`。移植前核查见 `docs/ms7/MS7_AA_TURRETS_IRON_DEATH_WORM_CHECK_2026-10-24.md`（AGENTS 第 263 节）。

## 1. 单位

| 稳定键 | UnitID | 基准 | 说明 |
| --- | --- | --- | --- |
| `s1xlv.iron_death_worm` | 1077 | 192（原版侵略者，`BattleAction_Alien`） | 可出击，开局可购买，阵营 1（Rebel Army）。图集 `iron_death_worm_0.obm`、`iron_death_worm_1.obm`（MSA `70003IronDeathWarm01_out.obm` 1024×1024 25 色、`70003IronDeathWarm_EF_out.obm` 1024×512 71 色，原样转为 OI 01 08），描述符 `iron_death_worm_descriptor.json`（MSA UnitID 1843 的动作记录：矩形 266、脚本 107，追加 5 个脚本至 112，受击框 2 → 74）。行为 `iron_death_worm`。原画朝向 90。 |

- 图像取 MSA 图集原样。MS7 素材表（Gussprint 拆图）与之为同一像素画、调色板换算不同，本单位未采用素材表。
- 名称与说明取 MSA 主数据表（按 language 列；法、德、意、俄在 MSA 中为英文原文）：钢铁死亡蠕虫 / 鋼鐵死亡蠕蟲 / IRON DEATH WORM。
- 头像为 MSA 原格（`m_unit_misc.pict` 1363 → `unit_icon_02.obme` (441,1464) 40×40，锚点 [−5, −5]），写在本体 `unit_icon_02.obm` 的 (232,770)。
- 音效：`s1xlv.irondw_atk`（MSA 2715 `irondw_atk.msa`，音量 115）、`s1xlv.irondw_move`（2716 `irondw_move.msa`，音量 100），复制为 `.msdf`（用户 2026-10-25 选 MSA 原文件）；200、203、225、425、808 为 MSD 同号同文件的原版音效。

## 2. MSA 的做法（反汇编 arm64 匿名类 `BattleAction_IronDeathWarm`，update 0xef25d8；辅助函数按反汇编确认，摘录在 `verification/iron_death_worm_20261025/disasm/`：`h_worm1.txt`–`h_worm7.txt`，跳转表解码 `jt.py`）

- 出击（startPosition）：置状态 78，钻出（槽 12，89 tick），播完待机（槽 6）并预约状态 10；其间置 +0x184 位 0x400（不近距攻击）、4（不发动绝招）。
- 移动（状态 20）：钻入（槽 7，89 tick，置不近距攻击）→ 移到敌方最前方单位前缘之前（x = 前缘 − 朝向 × 本单位宽度；无敌方单位时为敌方据点），限在本方据点与“推进上限 − 本单位宽度”之间（0x10dae34）→ 钻出（槽 12）→ 待机并预约状态 10。
- 近距攻击（状态 30）：掘削（槽 17，32 tick）：攻击框 1 全程开启，15 次抛出碎块弹体（脚本 22–24，无目的点；R3 更正，原记 18）。
- 绝招（状态 50）：记下当前位置 → 钻入或钻出进行中时先播完（钻入后在原处钻出）→ 绝招钻入（槽 25，82 tick：身体立起后飞离地面，攻击框 3）→ 在“前线”（敌方最前方单位的前缘，不越过本方推进上限，0x10f9bfc）至前线 + 朝向 × 攻击 3 投射距离（500）之间选生命最低的敌方单位（无则前线），移到其 x → 地下钻击（槽 33，80 tick：钻头自上方钻下，攻击框 3）→ 回到“前线 − 朝向 × 宽度”与原处中较靠后者 → 钻出 → 待机并进入绝招等待。地下钻击期间置 +0x184 位 8 / 0x10 / 0x40（不可接触、穿过、不可选为目标）。
- 受击（状态 80，MSA 的硬直）：槽 43 循环；击退门槛 −100，全部动作带 `EnableNockBack(false)`，MSA 中实际不击退。
- 损毁（100–120）：钻入（槽 25）→ 移到本方舞台外侧（我方 −220、敌方舞台宽度 + 220）→ 横穿（槽 44，速度 20）至舞台中央 → 爆炸（槽 49），碎块 50 / 52 / 54 落地后换为 51 / 53 / 55（0xef3134）。
- 绘制（draw 0xef2fb4）：按单位所在处的地面裁切后只画优先级 < 6 的层，清除裁切后再画优先级 ≥ 6 的层（地面土环与空中碎屑）；单位菜单演示（`ViewDrawIronDeathWarm`）同理。

## 3. MSD 中的实现（核心 r91，行为 `iron_death_worm`）

- 动作号即 MSA 脚本号；按 MSA update 中各状态实际播放的槽对应 MSD 的状态（MSA 状态 80 的槽 43 用作 MSD 的受击 70 与击退 80）。
- 脚本转换（生成脚本）：MSA 专有指令 24–35、47–58 删除；op36 → op11；op45 → op7；op42（子层偏移累加）→ op14（挂载偏移加累计增量）；2715 / 2716 换为本体音效键。追加脚本 107（损毁钻入：25 去掉攻击框）、108–111（编队页用的缩放副本，见下）。损毁碎块 50 / 52 / 54 按其 op7 运动离线求出落地 tick（y ≥ −帧高 / 2，取越过前后两 tick 中较近者，落地误差 2.9 / 1.7 / 0.8 原画像素），在该处停住并接上落地动作。
- 受击框（用户 2026-10-25 选“按可见部分分段设框，击退也补框”）：按 MSD 语义逐 tick 模拟（子层偏移、op7、op14、op19、op2 旋转、矩形翻转），取优先级 < 6 的层中各帧不透明像素在地面以上部分（旋转后的多边形裁到 y ≤ 0）的外接矩形；钻入 7、钻出 12、绝招钻入 25、地下钻击 33 每 4 tick 设一次（该段及前后各 1 tick 的并集，各 23 / 23 / 21 / 20 段，新增受击框 72 个）；身体全在地下时取钻孔矩形（土环在地面以上部分的横向范围，高 16 原画像素），贴地的可见部分不足钻孔高度时与之合并；受击 43 开头补 op3 1（同待机）。待机 6、掘削 17 保持 MSA 受击框 1（单位宽度由脚本 6 的受击框求得，原生 `setObjectSize`）。不采用 MSA 的不可选为目标标记，地下钻击中保持受击框。
- 地下钻击 33 首 tick 的两个音效移到第 1 tick（见下“攻击 ID”）。
- 编队页：原生 `CreateDeckObject` 以动作 0 原尺寸绘制且不按地面裁切；动作 0 改为空根层挂各部件 40% 的缩放副本（挂载偏移同比缩放，土环的纵向压扁同乘），几乎全在地下的末节 69 不挂。
- 核心块（`src/community_content.cpp` 钢铁死亡蠕虫一节）：与蜈蚣长老、侵略者之王共用侵略者类 `update` / `shotBullet`、弹体 `update` 的块与地面裁切绘制；击退判定块中钻入、钻出、绝招与损毁动作期间不击退（MSA 全部动作不击退；用户选定的击退门槛 300 只在待机与掘削中起作用）。
  - update：出场、移动、掘削、绝招、受击 / 击退（槽 43 持续 32 tick，同蜈蚣长老的击退时长）与损毁按 MSA 顺序执行；钻入、钻出与绝招一经开始即进行到底，其间进入的 70 / 80 立即预约状态 10。推进上限取敌方据点前缘（MSD 无 MSA 管理器 +0x238 的推进上限）；绝招目标不含战场道具 116，同生命取较靠前者（MSA 按对象地址排序后取第一个，本实施不使用地址）。损毁横穿的高度随地形（MSA 保持起点高度）。
  - 攻击 ID（用户 2026-10-25：整次掘削、整次绝招对同一目标只结算一次）：状态 30 / 50 记下第一次建立的 ID 并每 tick 写回（同侵略者之王 r84）；掘削碎块以 `addBulletNotAim` 发射后把弹体攻击 ID（+0x144）改为单位当前的 ID。绝招由钻入切换到地下钻击时，原生 `setAnimationID` 清空攻击 ID、脚本 op4 随即建新 ID，而碰撞判定在下一帧本单位 update 之前进行；尾调用切换时新 ID 会先结算一次（试做中据点受两次），故此切换改为钩子内嵌套调用并立即写回原 ID（该动作首 tick 无音效，嵌套调用不能执行音效导入）。
  - 弹体 update：碎块（+0x28 为 20）脚本播完或待定位置到地形高度时移除；动作号字段写 20，原生 `attackAction` 只结算伤害、不消失。
  - 绘制：按 MSA 分两遍——裁切中只画优先级 < 6 的层，恢复裁切后再画 ≥ 6 的层；隐藏的层把帧号减 2000（原生 `drawImpl` 跳过帧号 < 0 的层），绘制后加回。第二遍以第 4 个延续块返回（`GraphicsOpt::setClip` 中 str.w 指令后半字 0x101358d9，登记前确认无原生块）；蜈蚣长老与侵略者之王的绘制不变。
- 单位菜单的动作演示：待机 6、掘削 17（不发射碎块）、绝招钻到原处前方 250 后回到原处钻出；不出场。

## 4. 数值（用户 2026-10-25 选“同蜈蚣长老量级”；其余为 MSA 1843 的暂定值）

| 项目 | 值（Lv40） | 依据 |
| --- | --- | --- |
| 生命 | 50000（`hp_multiplier` [25, 3]；Lv1 / 10 / 20 / 30 / 40 = 16666 / 25000 / 33333 / 41666 / 50000） | 用户选定（同蜈蚣长老） |
| AP | 850（击毁返还 85） | 用户选定（同蜈蚣长老） |
| 掘削（近距） | 整次对同一目标 6000（`near_damage_multiplier` [4, 1]；Lv1–40 为 2000–6000），目标数 999，近距等待 60，第二参数 5 | 伤害用户选定；其余 MSA |
| 绝招（死亡钻头） | 整次对同一目标 6000（`special_damage_multiplier` [5, 2]），目标数 999，绝招等待 40，冷却 250、首次 200，第二参数 200，搜索距离（词 33）500 | 伤害与冷却用户选定（同蜈蚣长老）；其余 MSA |
| 攻击距离 | 近 20、远 0（无远距攻击） | MSA |
| 击退门槛 | 300（`knockback_threshold_multiplier` [15, 1]） | 用户选定（同蜈蚣长老；第 6.1 节的例外） |
| 出击时间 | 192 的 × 26/7（68.1 秒） | 同蜈蚣长老 |
| 属性 | 近距、绝招均为普通 | MSA atk_damage_effect 0 |
| 价格 | 150 勋章，开局可用 | 同蜈蚣长老 |
| 绝招蓝光 / 小地图标记 | 90×120 / 10×20 | MSA `aura_size` / `radar_size` |

- STATUS 的移动速度显示基准 192 的 3.00（本单位不步行，移动为钻入后移位）。

## 5. 验证（核心 r91，隔离存档，墙钟前移，未计算 SHA-256）

- 离线：`content_tool.py validate` 通过（音效 69）；`check_body_offline.py` 10/10；`check_ura4_offline.py` 19/19；单元测试 22 项中 21 项通过（另 1 项为既有的 `msd_aot` 导出检查）；`lab_probe.jsonl` 未变。
- LAB 1011（`run_final.sh`，`ana_final.py` → `final_summary.json`）：我方出击后钻出（89 tick）→ 钻入 → 移到敌方最前方单位前（x 940 / 1036；只剩据点时 1038，`runs/probe1_*`）→ 钻出 → 掘削；1500 帧内 8 次攻击（掘削 5、绝招 3），每次对每个目标只结算一次：据点每次 6000，叛军步兵 594、DI-COKKA 4620 一次击毁；每次掘削 15 个碎块（R3 更正，原记 18）；绝招钻离地面、钻到据点处、回原处钻出。敌方侧（`--swap`）逐项镜像（x 485，同 8 次、各一次结算）。存活中无受击框的帧 0 / 1486。
- 损毁（`runs/fin_death_*`）：第 150 帧预约 100 → 损毁钻入 82 tick → 自 x −220 以每 tick 40 横穿 23 tick 至舞台中央 700 → 爆炸 71 tick → 移除。
- 击退与受击（`runs/fin_knock_*`）：待机中强制击退 → 槽 43 约 33 帧后恢复；钻入途中强制 80 → 下一帧回到 20，钻入继续；状态 70 同样播放槽 43。槽 43 中受击框为 MSA 受击框 1。
- 受击框普查：静态（`audit/static_hitrect.json`）战斗中使用的 6、7、12、17、25、33、43 号动作开头均设受击框；动态（`audit/run_audit.py fin 1077` → `audit/audit_fin.json`）2473 帧（状态 10 / 20 / 30 / 50，动作 6、7、12、17、25、33）无受击框帧 0。
- 绘制：精灵层 +0x28 为层优先级（与层键一致，`runs/wdS_*` 的层导出），绘制后帧号已恢复；裁切字段清零（`--zero-clip`）时界面始终显示，第一次绘制后裁切为全屏（`runs/wdZ_*`）。截图对照 `sheet_wdS.png`、`sheet_wdD.png`。
- 单位菜单（`driver_ui_unit.py`，`runs/ui2_*`）：STATUS Lv40 生命 50000、AP 850、价格 150、掘削 / 绝招 6000、击退门槛 300；ACTION 三项（状态 10 / 30 / 50）正常；动作演示图像范围按签名 5cb4e2bd880311f1 并入两份 `unit_viewer_bounds.json`。编队页（`driver_deck.py`，`runs/deck3_*`）缩放后立于编队地面（`deck_compare.png`）。
- 共用块回归：蜈蚣长老同一 LAB 场景 r90（固定运行目录 `dist/MSD_Windows`，`MSD_VERIFY_ROOT`）与 r91（工作区）900 帧逐帧相同；侵略者之王在两者间自第 144 帧起不同（出击着地后首次跃起：r90 第 294 帧、r91 第 144 帧）。以 HEAD 源码与行为库 18 编译的对照核心在工作区与 r91 360 帧逐帧相同（`cmp_king_core.json`）；同步后固定运行目录换为 r91 也为第 144 帧。私有测试根目录中以同一套改动前的宿主与内容对照（`make_priv_root.py`）：r88、r89 二进制与由仓库源码重新编译的核心均为第 144 帧，只有已发布的 r90 二进制为第 294 帧；宿主 ZSpec 104 字与 128 字结果相同。即 r90 二进制与仓库中提交的源码不一致（r90 只改 `lab_hooks.cpp`，其 `community_content.o` 的来源未查明），r91 由仓库源码构建，恢复 r88 / r89 与源码的行为（与第 231、240 节“着地后等待跃起间隔 3 秒再跃起”的设计一致）。
- N1 回滚（`n1_unit.py`，P1 10 格均为本单位，每 150 帧绝招）：2400 帧、698 次回滚，参照与随机回滚逐帧一致（`n1_compare_final.json`，状态 10 / 20 / 30 / 50）。

## 6. 未覆盖

- 数值为用户选定的暂定组（已按此同步）。
- 关卡预置（`placed`）的出场与 MSD 关卡中的平衡；两机联机；MSA 录像对照（绝招与掘削未逐帧比对）。
- MSA 的版本技能、能力类型 14、状态 75 / 78 的技能用途未实施；MSA 推进上限（管理器 +0x238）在 MSD 中以敌方据点前缘代替。
- 损毁碎块的落地按单位脚下为平地离线换算，坡道上会有偏差。

## 7. 同步（2026-10-25）

- 用户要求按现行暂定数值同步（AGENTS 第 2.2、2.3 节的持续授权）。脚本 `verification/iron_death_worm_20261025/deploy_wd.py`，记录 `deployment.json`，覆盖前副本 `sync/<目录>/before/`。同步时两目录均无 Python 进程。
- 覆盖（覆盖前核对目标与修改前副本逐字节相同；宿主与核心源码 4 项按统一换行比较，目标与工作区均为 CRLF；`docs/ms7/` 核查文档核对目标 = 工作区去掉第 9 节本次补记）：宿主与行为库 3 项及 `src/` 镜像、两份 `core_runtime.json` 与 `lab_runtime.py`、`src/community_content.cpp`、`src/community_blocks.inc`、`content.json`、`unit_icon_02.obm`、`NOTICE.md`、两份 `unit_viewer_bounds.json`、`docs/modding/BEHAVIOR_CATALOG.md`、`docs/ms7/` 核查文档。新增：r91（根 `build/` 与 `src/build/`，目标的旧核心保留）、单位文件、图集 2、描述符、音效 2 与本文档。两目录各写入 28 个文件，同步后与工作区逐字节一致；保护文件 131、338 个不变；两目录核心为 r91。生成脚本 `artwork/` 不同步（同此前各单位）。
- 复测（两目录自身的宿主、核心与内容，`MSD_VERIFY_ROOT`，隔离存档，未计算 SHA-256）：`content_tool.py validate` 通过，内容摘要与工作区相同（音效 69）；我方出击与敌方侧两场景各 1500 帧的双方单位与弹体记录（不计对象地址字段）与工作区逐帧相同（`run_installed.sh`、`cmp_installed.py` → `cmp_installed.json`）；单位菜单 STATUS（生命 50000、AP 850、价格 150、掘削 / 绝招 6000、击退门槛 300）与 ACTION 三项正常，动作演示使用随附的图像范围。运行中的游戏需重启加载。
- 同步带来的另一变化：两目录的核心由 r90 换为 r91 后，侵略者之王出击着地后的首次跃起由已发布 r90 二进制的行为改为仓库源码（r88 / r89）的行为（见第 5 节共用块回归）。

## 8. R2（2026-10-25，核心 r92，行为 `iron_death_worm` v2，行为库 19）：按 MSA 底层代码逐条核对与修正

- 起因（用户）：动作整体生硬、钻回地下尤其生硬；移动应像蜈蚣长老那样在地下推移到敌方前线再钻出；出现直接卡在天上的情况；用户指出“很多东西并没有按照MSA的底层代码来进行移植”。
- 核对：`verification/iron_death_worm_20261025/msa_r2/FINDINGS_R2.md`（MSA `BattleSprite::runScript` 跳转表 0x18f44c8 与长度表 0x18f459c、`BattleSprite::EventCallback` 虚表 0x49f9db0 与 `BattleUnit` 的实现、update / createObject / shotBullet、`EffectAction_DeadBody`、通用待机 0x10d7b1c / 攻击 0x10d8e94 / 击退 0x10d811c、`changeState` 0x10eb570、对象 update 0x10ec208、默认弹体动作 0x4ae5b10；MSD `runScript` 0x1dbcd8、`getAnimationStatus`、`actionMoveX/Y`、`setAnimationID`、`BulletAction_Alien` 与 `BattleBulletDefault::attackAction`）。

| 项 | MSA | r91 | r92 |
| --- | --- | --- | --- |
| 部件挂载 op36 | 只在第一遍执行，父层循环时部件不被重置 | 改为 op11（每遍执行，`getAnimationStatus` 把部件重置到开头）：待机 6、43、横穿 44、编队 0 / 1 每 70 tick 重新挂载，部件动画跳回起点 | op11，父层循环前的等待改为 32767 tick |
| 损毁 | 第 0 帧播放 25；横穿 44 开始时置不可接触 / 穿过 / 不可选为目标 | 另做的 107（去攻击框）；未置标记，横穿被敌方单位挡住后悬在空中、不移除 | 播放 25（含攻击框，结算组 50），横穿时置三标记；不另设超时 |
| 指令 24–35、47–58 | `EventCallback` 判定开关 | 作为无关指令删除 | 作用由核心实现（见下行与击退、掘削两行）；op24 / op28 / op30（技能眩晕 / 技能回避 / 禁止技能硬直）在 MSD 中无对应 |
| 击退 | 击退为状态 70，全部动作 op26 `EnableNockBack(false)`，`changeState` 拒绝；状态 80 为技能硬直 | MSD 70 / 80 播放 43，32 tick（取自蜈蚣长老），门槛 300 | 用户选照 MSA：不击退（`wd_guard` 恒真）；MSD 70（据点被毁时的胜利动作）按 MSA 默认分支不切换动作 |
| 掘削 17 | op35 / op34 `EveryTimeAtk`：攻击框 32 tick 内每 tick 换攻击 ID，同一目标每 tick 可受击；碎块命中后转入状态 60 消失，落地消失 | 整次只结算一次（6000）；碎块与攻击框共用 ID，命中不消失，脚本播完移除 | 用户选照 MSA：每 tick `BattleUnit::refreshAttackStatus`，每次 188；碎块新建攻击 ID，`attackAction` 走 `BattleBulletDefault`（结算后状态 60 消失），落地移除、播完不移除 |
| 绝招 | 25 第 60 tick 清除攻击框，33 重新建立，两段各自结算；钻击中置三标记 | 嵌套调用使两段共用攻击 ID（只结算一次），33 首 tick 的音效后移 | 两段各自结算，音效顺序恢复 MSA；三标记按用户要求不置（保持受击框） |
| op45 | 速度 = v + a，位移 v, v + a, v + 2a, … | 原样改为 op7（位移 v, v, v + a, …） | 加速度不为 0 时每 tick 补 op7（v + k·a） |
| 损毁碎块 50 / 52 / 54 | `EffectAction_DeadBody`：下落中 y ≥ 地形高度 − 当前帧第一个矩形高 / 2 时改播 51 / 53 / 55 并清除移动，播完移除 | 平地离线换算落地 tick | 核心按地形实时判定（以弹体承载，`createObject` 0x10181ec5 与弹体 update） |
| 火焰 92 | `EffectAction_DeadBody::createObject`：播完接 93（清除移动） | 只播 92 | 92 后接 op16 与 93 |
| 待机 | 状态第一 tick 强制重播 6 | 动作不同时才设 6 | 同 MSA |
| 其余状态 | 默认分支（空） | 设待机 | 不切换动作 |
| 移动 | 钻入后瞬移到敌方最前方单位前缘之前再钻出 | 同 MSA | 用户要求：地下行进（动作 111 挂土环 100 × 5 随行与发射层 112，每 4 tick 放一团尘土 21，受击框为钻孔；移速 5，同蜈蚣长老）；转入 10 / 30 / 50 时原处钻出，30 接掘削、50 接绝招钻入 |
| R1 草稿的部件插值 | 无 | — | 撤销 |

- 数值：`near_damage_multiplier` [4, 1] → [47, 375]（掘削与碎块每次命中 Lv40 188 ≈ 6000 ÷ 32）；绝招每次结算 6000 不变（钻入与钻击各自结算）；击退门槛 300 保留，本单位不击退；地下行进移速 5。其余同第 4 节。
- 仍与 MSA 不同之处（用户决定，或 MSD 无对应）：地下行进（用户要求）；钻击中不置三标记、钻入 / 钻出 / 绝招的分段受击框（用户要求，MSA 中沿用待机受击框）；损毁横穿高度随地形（AGENTS 第 6.2 节；MSA 保持起点高度）；MSA 状态 75 / 78 的技能用途、op24 / op28 / op30、管理器 0x10f6fa8（绝招瞬移后对我方置 +0x1fd，作用未查明）未实施。
- 验证（核心 r92，隔离存档，墙钟前移，未计算 SHA-256；`verification/iron_death_worm_20261025/`，`run_r2.sh`、`run_r2_all.sh`、`ana_r2.py`）：
  - LAB 1011 我方与敌方侧各 1500 帧（`r2_main` / `r2_swap`）：出场钻出 → 钻入 → 地下行进（x −30 → 555，118 tick × 5）→ 遇敌在原处钻出 → 掘削 / 绝招；存活中无受击框 0 / 1486 帧，未进入状态 80。
  - 掘削对敌方据点（`r2_base`）：每次攻击框 32 次命中、碎块约 7 次，均为 188（合计 7332）；对叛军步兵每次 3–4 次。
  - 绝招：钻入 25 与钻击 33 各自结算，据点受钻击 6000。
  - 损毁（`r2_death`）：25 → 横穿 44 越过敌方单位 → 舞台中央爆炸 49 → 第 506 帧移除；碎块 52 / 54 落地改播 53 / 55（y 255 / 258），50 飞出舞台边缘后移除。
  - 压力测试（`run_stress_r2.sh`，双方 AI、编队含本单位，3000 帧，舞台 1011 与 10041）：12 个实例无停住、无受击框为空的帧，全部损毁经 25 → 44 → 49 后移除（`runs/r2_stress_*/ana_stress.txt`）。
  - 待机连续性（`r2_idle`，状态 70 中待机持续 316 tick，`ana_idle.py`）：部件 67 / 68 / 69 与 5 个土环的帧序列与各自周期（32 / 24 / 24 / 18）一致，0 处不一致。
  - op45（`ana_op45.py`）：9 个碎块各 12–16 段位移与 MSA 序列一致（误差 0），r91 模型每段偏差 1.6。
  - 强制状态（`r2_knock`）：LAB 强制 80 时不切换动作并预约回到 10 / 20；强制 70 时不切换动作。
  - 受击框动态普查 2473 帧无空档（`audit/audit_r2.json`）；静态普查中实际使用的根动作开头均设受击框（`audit/static_hitrect_r2.json`）。
  - 单位菜单 STATUS：Lv40 生命 50000、AP 850、价格 150、掘削 188、绝招 6000；ACTION 三项正常，图像范围签名 f2d79c8558743256 并入两份 `unit_viewer_bounds.json`。
  - N1 回滚：2400 帧、698 次回滚，参照与随机回滚逐帧一致（`n1_compare_r2.json`，状态 10 / 20 / 30 / 50）。
  - 共用块回归：蜈蚣长老与侵略者之王在 r91（`dist/MSD_Windows`，只读）与 r92（工作区）下 900 帧逐帧相同（`cmp_regress_r2.json`）。
  - `content_tool.py validate`（音效 69）、`check_body_offline.py` 10/10、`check_ura4_offline.py` 19/19、单元测试 21/22（既有 `msd_aot`），`lab_probe.jsonl` 未变。
- 未覆盖：地下行进的画面观感（地面只见压扁的土环带，尘土团不明显）与关卡平衡待实机评估；两机联机；MSA 录像逐帧对照。

## 9. R2 同步（2026-10-25）

- 用户要求按 R2 同步（含核心 r92）。`verification/iron_death_worm_20261025/deploy_r2.py`（AGENTS 第 2.2、2.3 节持续授权，记录 `deployment_r2.json`、`sync_r2/`）：覆盖宿主与行为库 3 项及 `src/` 镜像、两份 `core_runtime.json` 与 `lab_runtime.py`、`src/community_content.cpp`、`docs/modding/BEHAVIOR_CATALOG.md`、单位文件、描述符与本文档（覆盖前与第 7 节同步写入的版本逐字节相同），两份 `unit_viewer_bounds.json` 以目标文件为底本只替换本单位一项（目标中暴食飞行侵略者一项已由 AGENTS 第 266 节同步替换；合并后各单位条目与工作区相同，只有说明字段不同），新增 r92（根 `build/` 与 `src/build/`，旧核心保留）；图集、音效、头像图集、`content.json`、`NOTICE.md` 与 `src/community_blocks.inc` 在 R2 中未改变，不写入。两目录各写入 19 个文件，同步后逐字节一致，保护文件 131、339 个不变，同步时无 Python 进程，两目录核心 r92。
- 两目录自身程序（`MSD_VERIFY_ROOT`，`run_installed_r2.sh`、`cmp_installed_r2.py`，结果 `cmp_installed_r2.json`）：`content_tool.py validate` 通过，内容摘要与工作区相同；我方出击与绝招、敌方侧各 1500 帧与掘削据点 700 帧三个场景的单位与弹体记录（不计对象地址字段）与工作区逐帧相同；单位菜单 STATUS（Lv40 生命 50000、AP 850、价格 150、掘削 188、绝招 6000）与 ACTION 正常。运行中的游戏需重启加载。

## 10. R3（2026-10-25，核心 r94）：绝招分段输出、地下不设受击框、掘削 400

- 起因（用户）：掘削每次命中提高到 400；绝招自上而下钻击时，与精灵重叠的单位不受伤害，要求钻击为分段输出；在地下向前线行进时不应被攻击（与蜈蚣长老的地下前行一致），“他还在地下的时候，却能被输出到，这显然不应该有这种情况的出现”。
- 原因（`ana_sp.py`，`runs/r3_sp_*`，核心 r93）：钻离 25 与钻击 33 使用 MSA 的固定攻击框 3（受击框 [2, −289, 129, 310]，只覆盖钻头前方），并在每个动作中对同一目标只结算一次；钻击中与可见钻身重叠的 DI-COKKA（x 约 1021）有 12 tick 与受击框相交、0 tick 与攻击框相交，未受伤害。地下行进 111 与钻入 / 钻出中身体全在地下的段落使用 r91 起的“钻孔矩形”（土环在地面以上的范围），因此地下仍可被击中。
- 用户决定（2026-10-25）：钻离 25 与钻击 33 每 4 tick 一段、每段 400；攻击范围跟随可见钻身；钻离与钻击同样分段。
- 实施：
  - 生成脚本：受击框分段（7 / 12 / 25 / 33，每 4 tick 一段，取该段及前后各 1 tick 中地面以上可见身体的外接矩形）不再并入钻孔矩形，全在地下的段落设受击框 0；地下行进 111 的受击框改为 0（MSA 地下移动脚本同样以 op3 0 设空）。25 与 33 在 MSA 的攻击时段（25 第 0–60 tick、33 第 0–59 tick）内每 4 tick 写一条 op4，攻击框为同一段的可见身体外接矩形（新增攻击框 20 个，标志 7 同 MSA 攻击框 3），无可见部分时为 0，时段结束处 op4 0；原有的 op4 3 / op4 0 由分段取代。`special_damage_multiplier` [5, 2] → [1, 6]（192 绝招 Lv40 2400 × 1/6 = 400），`near_damage_multiplier` [47, 375] → [4, 15]（1500 × 4/15 = 400）。只有单位文件（数值与 7、12、25、33、111 五个脚本）与描述符（受击框 74 → 72、攻击框 4 → 24）改变，图集、头像、音效与 `content.json` 不变。
  - 核心 r94（`MSD_Core_LAB_r94_20261025.dll`，`msd_community_iron_death_worm_version` 2 → 3，宿主要求 ≥ 3）：25 与 33 播放中置身体状态 0x20（`BattleObject::changeStateAttackIDReset` 0x101780ac，标记位 16），每条 op4 经 `initAttackStatus` 建立新攻击 ID，框内各目标每段各受 1 次；离开这两个动作时清除。行为库与行为参数不变。
- 无受击框的段落（R3 起为设计）：钻入 7 第 84–88 tick、钻出 12 第 0–7 tick、钻击 33 第 72–79 tick、地下行进 111 全程；钻离 25 全程有受击框（身体升离地面）。
- 损毁沿用 25（MSA 同），损毁钻入中同样按段结算（R2 为一次结算）；`r3_death` 中钻入第 1 tick 对叛军步兵 400、DI-COKKA 320，第 5 tick 194（步兵剩余生命）。
- 验证（核心 r94，隔离存档，墙钟前移，未计算 SHA-256；`verification/iron_death_worm_20261025/`，`run_r3.sh`、`run_r3_all.sh`、`ana_r3.py`、`chk_nohit_r3.py`）：
  - 绝招（`r3b_sp`，与 `r3_sp` 同一场景）：与钻身重叠的叛军步兵在 25 中每 4 tick 受 400（第 1、5、…、57 tick，15 段合计 6000），在 33 中 14 段合计 5600（第 0 段钻身仍在空中）；每次 25 / 33 建立 15 个攻击 ID，身体状态 0x20 在两动作的每一帧均已置位；DI-COKKA 第 1 tick 受 320（耐性）后被击退离开范围。`r3_main` 中敌方据点每次钻击受 15 段合计 6000（r92 为 0 或 6000 一次）。
  - 掘削对敌方据点（`r3_base`）：每次 31 帧有伤害，合计 14800（攻击框 32 次与碎块约 5 次，各 400；r92 为 6956）。
  - 受击框：`r3_main` / `r3_swap` / 两场压力测试中，存活时无受击框的帧只在 111 与上列段落内（7 第 84–88、12 第 0–7、33 第 72–79 tick，`chk_nohit_r3.py`）；静态普查与 R2 相比只多出 12（第 8 tick 起设框）与 111（全程为 0）两项（`audit/static_hitrect_r3.json`）。
  - 压力测试（`run_stress_r3.sh`，舞台 1011 与 10041，各 3000 帧）：6 个实例无停住，损毁的 5 个均经 25 → 44 → 49 后移除。
  - 强制状态（`r3_knock`）与损毁（`r3_death`，第 506 帧移除）与 R2 相同。
  - 单位菜单 STATUS：Lv40 生命 50000、AP 850、价格 150、掘削 400、绝招 400；ACTION 正常，图像范围不变，签名 f2d79c8558743256 → e464405a70d875b4 并入两份 `unit_viewer_bounds.json`（只替换本单位一项）。
  - N1 回滚：2400 帧、698 次回滚，参照与随机回滚逐帧一致（`n1_compare_r3.json`；须 `--base-hp 2000000 --weak-p2`，否则敌方据点于第 820 帧被毁）。
  - 共用块回归：蜈蚣长老与侵略者之王在 r93（`dist/MSD_Windows`，只读）与 r94（工作区）下 900 帧逐帧相同（`cmp_regress_r3.json`）。
  - `content_tool.py validate`（音效 69）、`check_body_offline.py` 10/10、`check_ura4_offline.py` 19/19、单元测试 21/22（既有 `msd_aot`），`lab_probe.jsonl` 未变。
- 仍与 MSA 不同之处（用户决定）：25 / 33 的攻击框按可见钻身分段、每段各自结算（MSA 为固定攻击框 3、整段一次）；地下段落不设受击框按蜈蚣长老的做法（MSA 只在钻击 33 与损毁地下移动中置不可选为目标等标记）。
- 未覆盖：关卡与对战中的平衡（掘削对据点每次约 14800、绝招对与钻身重叠的目标最多 6000，对大型目标的合计随重叠段数变化）；两机联机。修改前副本 `before_r3/`。

## 11. 音效清单（2026-10-25，供替换音效）

各动作中的 op23（tick 自该动作开始计，子层按挂上时刻换算；30 tick 为 1 秒）。数字为 MSD 原版 SoundID（文件名取 `verification/m6_20261010/sound_table.json`），键为本体音效（`content.json` 的 `sounds`）。清单由生成脚本写入 `artwork/iron_death_worm_20261025/out/build_report.json` 的 `stats.sound_events`。

| 动作 | 用途（MSD 状态） | 时长（tick） | 音效（tick：音效） |
| --- | --- | --- | --- |
| 7 钻入（R5 起移动用 2 倍速副本 120，时刻减半） | 移动开始（20） | 89 | 0：`s1xlv.irondw_drill_stop`（R6；此前为 425 `bull_drill_1.ogg`）、`s1xlv.irondw_move`；41（子层 8）：`s1xlv.irondw_move` |
| 12 钻出 | 出场、地下行进结束、绝招回位（20 / 30 / 50） | 89 | 9：425、`s1xlv.irondw_move`；50（子层 13，第 9 tick 挂上）：`s1xlv.irondw_move` |
| 17 掘削 | 近距攻击（30） | 32 | 0：`s1xlv.irondw_atk` |
| 25 钻离地面 | 绝招开始（50）、损毁开始（100） | 82 | 0：425、`s1xlv.irondw_move`；39：`s1xlv.irondw_move` |
| 33 地下钻击 | 绝招（50） | 80 | 0：`s1xlv.irondw_drill_stop`（R6；此前为 425）、`s1xlv.irondw_move`；41：`s1xlv.irondw_move` |
| 44 损毁横穿 | 损毁（100） | 循环 | 0（子层 106）：425、`s1xlv.irondw_move` |
| 49 爆炸 | 损毁（100） | 71 | 0：225 `B4_EXPPL.ogg` |
| 55 损毁碎块落地 | 损毁碎块 | 47 | 16：203 `B4_EXP3.ogg`、808 `B4_DET3M.ogg`（语音类） |
| 111 地下行进 | 移动（20） | 循环 | 无（MSA 无此动作） |
| 116 碎块爆炸（R4） | 掘削碎块 | 29 | 0：203 `B4_EXP3.ogg` |

- 现用 `s1xlv.irondw_atk`（MSA 2715，音量 115）、`s1xlv.irondw_move`（MSA 2716，音量 100）为 MSA 原文件；200（`B4_CAN1.ogg`）在生成脚本的同号表中，现行脚本未使用。
- 替换方法：本体音效须为 Ogg Vorbis 的 `.msdf`（以 `OggS` 开头），采样率与声道数不限（核心 r52 起载入时转换为 16 kHz 立体声）。WAV 可在 `E:\anaconda3\python.exe -I` 中以 soundfile（libsndfile，`format='OGG', subtype='VORBIS'`，分块写入，同 `artwork/iron_sentinel_20261020/build_iron_sentinel.py` 的 `encode_ogg`）或本机 `E:\小丸工具箱\tools\ffmpeg.exe`（含 libvorbis）编码，再以 `content_tool.py import-music` 做解码检查；文件放在 `community_content/`，键 `s1xlv.<名称>`，在 `content.json` 的 `sounds` 登记（`type` 为 `se`，`volume` 1–127，必要时 `gain` 0.1–8）。生成脚本中 MSA 2715 / 2716 的对应在 `SOUNDS`，原版同号音效在 `NATIVE_SOUNDS`；按动作替换时在 `convert` 的 op23 换算处增加按槽与 tick 的对应。SoundID 空闲区段合计 380 个，现用 69 个（R4 曾为 71 个，音效回退后恢复，见第 15 节）。
- se 类音效只播放一遍；地下行进 111 若要持续的地下声（如 MSXX `BOSS1_DIVE1` 第 1.86 秒起的循环段），需在 111 的循环中按音效长度重复 op23。
- 候选（AGENTS 第 268 节，`F:\egg\MS7\MSXX-audio-wav\说明.md`，用途按名称推定、未与画面对照）：`BOSS1_OUT`（1.94 s，钻出）、`BOSS1_DIVE1` / `BOSS1_DIVE2`（3.56 / 1.30 s，潜入）、`DRILL_STAR` / `DRILL_LOOP1` / `DRILL_LOOP2` / `DRILL_STOP`、`DRILL_OPEN` / `DRILL_CLOSE`、`SAW_SPIN`、`SCRAP_THROW`、`ST1_B4_STONS`。MSXX SE 为 11025 Hz 单声道。动作时长：钻入 / 钻出各约 2.97 秒、钻离 2.73 秒、钻击 2.67 秒、掘削 1.07 秒。

## 12. R3 同步（2026-10-25）

- 用户要求按 R3 同步（含核心 r94）。`verification/iron_death_worm_20261025/deploy_r3.py`（AGENTS 第 2.2、2.3 节持续授权，记录 `deployment_r3.json`、`sync_r3/`）：覆盖宿主 `community_content.py` 与 `src/` 镜像、`src/community_content.cpp`、两份 `core_runtime.json` 与 `lab_runtime.py`（覆盖前与工作区 R3 修改前的副本 `before_r3/` 逐字节相同，即 AGENTS 第 269 节同步写入的版本），单位文件、描述符与本文档（覆盖前与第 9 节同步写入的版本逐字节相同）；两份 `unit_viewer_bounds.json` 以目标文件为底本只替换本单位一项（合并后各单位条目与工作区相同，只有说明字段不同）；新增 r94（根 `build/` 与 `src/build/`，旧核心保留）。图集、音效、头像图集、`content.json`、行为库与 `behaviors.py` 在 R3 中未改变，不写入。两目录各写入 14 个文件，同步后逐字节一致，保护文件 131、343 个不变，同步时无 Python 进程，两目录核心 r94。同步前后以 `cmp_rundirs_r3.py` 比较工作区与两目录：R3 相关文件之外的差异（`lab_config.json` 等个人设置与既有的目录差异）未改动。
- 两目录自身程序（`MSD_VERIFY_ROOT`，`run_installed_r3.sh`、`cmp_installed_r3.py`，结果 `cmp_installed_r3.json`）：`content_tool.py validate` 通过，内容摘要与工作区相同（音效 69）；我方出击与绝招、敌方侧各 1500 帧，掘削据点 700 帧与绝招重叠场景 1400 帧（同 `r3b_sp`）四个场景的单位与弹体记录（不计对象地址字段）与工作区逐帧相同；单位菜单 STATUS（Lv40 生命 50000、AP 850、价格 150、掘削 400、绝招 400）与 ACTION 正常，动作演示使用随附的图像范围。运行中的游戏需重启加载。

## 13. R4（2026-10-25，核心 r95，行为 `iron_death_worm` v3，行为库 20）：部件判定、碎块弹跳爆炸、钻地音效、生命与绝招

- 用户要求（2026-10-25）：① 掘削抛出的碎块落地后不立即消失，随惯性滚动 / 弹跳，过 0.X 秒爆炸，碰到敌军立即爆炸（类似猎人炸药的判断，无索敌），同 MS7 / MSXX；② `DRILL_STOP` 用于缩回地面、`DRILL_STAR` 用于钻出地面（MSA 两处都只用一个音效）；③ 钻出地面后的判定框远大于贴图，要求只比贴图大一点点、贴合贴图，不用一个大框框住全部贴图；④ 生命 60000，钻地伤害 6000 改为 8000。
- 用户选择（2026-10-25）：引信 0.5 秒（15 tick）；爆炸用蠕虫图集的 MSA 小爆炸 103，伤害同掘削 400，范围取爆炸图像大小；钻入（7、33）用 `DRILL_STOP`、钻出（12、25）用 MSXX 的 `DRILL_STAR`（现用 MSA 2716 与 `DRILL_STAR` 频谱不吻合，相关 0.10，不是同一文件）；绝招每个动作 16 段 × 500（攻击时段由 MSA 的 60 / 59 tick 延长到 64）。部件判定同时用于受击与绝招攻击（代理决定，同“攻击范围跟随可见钻身”）。
- 部件判定（MSD 原生每个单位只有一个受击框与一个攻击框）：
  - 生成脚本：每段（4 tick）身体层地面以上的不透明像素按 2 精灵像素栅格化，按行或按列分成至多 8 个条带、各取外接矩形，取总面积较小的分法；部件接在描述符受击框 / 攻击框表中该段外框之后（第 5 值 0x57445054），同一外框与部件只登记一次。待机 6 仍设 MSA 受击框 1（原生按其求单位宽度，宽度不变），部件为待机循环 288 tick 的并集；掘削 17 每 4 tick 一段，外框仍为受击框 1 的值。受击框表 72 → 793 条、攻击框表 24 → 294 条，宿主的框表上限由 256 放宽到 2048。
  - 核心 r95：`BattleSprite::runScript` 的 op3 / op4（块 0x101dbde6 / 0x101dbe2e）把本单位的框号记在 +0x3c / +0x40；`BattleObject::hitTest`（0x101ddbca，`BattleObjectManager::advanceFrame` 的全部命中判定经此）在受击方为本单位且当前框有部件时按部件判定，单位攻击单位的判定（返回地址 0x101dfb75，攻击方 r5）中攻击方为本单位时按攻击部件判定。换算同 op3 / op4（朝向与原画朝向不同时 x 取 −(x + w)，× 2 加单位位置取整）。外框不变，仍供原生的其他用途（索敌距离、前线等）。
- 掘削碎块（核心 r95）：落地时以本 tick 的位移为速度（横向 × 0.7、纵向反向 × 0.25），改播滚动动作 113–115（根层开碎块攻击框 2、挂旋转子层 117–119，旋转取碎块脚本的一周），由核心每 tick 加重力 1.6（碎块脚本 op45 的加速度 80 × 2 / 100），落到地形高度 − 落地时帧高的一半时再弹起，纵向速度不大于 3 时贴地滚动、横向 × 0.85；落地 15 tick 后，或碰到敌方单位（由 `BattleBulletDefault::attackAction` 结算 400 并预约状态 60）时，改播爆炸 116（挂 MSA 小爆炸 103，下移 12 使爆炸中心在碎块处；攻击框 (−16, −12, 32, 32) 开 4 tick，伤害同碎块；音效 203 `B4_EXP3`），29 tick 后移除。改播动作时保留攻击 ID，碰到的目标不被爆炸再结算一次。弹跳系数等为代理所定（0.45 时第一跳约 97 像素、在空中超过引信时长，改为 0.25）。
- 音效（已回退，见第 15 节）：MSXX 音频提取包（AGENTS 第 268 节）的 `DRILL_STOP.wav` / `DRILL_STAR.wav` 编码为 Ogg Vorbis（`irondw_drill_stop.msdf` / `irondw_drill_star.msdf`，11025 Hz 单声道，音量 100），钻入 7（含子层 8）与钻击 33 的 2716 换为前者，钻出 12（含子层 13）与钻离 25 的换为后者；损毁横穿 106 等保持 2716。`NOTICE.md` 中英两段补记来源。生成脚本在目标文件已存在时不重新编码（libsndfile 每次取随机的 Ogg 流序列号）。
- 数值：`hp_multiplier` [25, 3] → [10, 1]（Lv40 60000）；`special_damage_multiplier` [1, 6] → [5, 24]（Lv40 每段 500）；击退门槛 300 为用户指定，保持（本单位不击退）；其余不变。
- 行为 v3（行为库 20，ZSpec 字 117–119）：`debris_roll_first_animation`、`debris_burst_animation`、`debris_fuse`；核心版本 4，宿主要求 ≥ 4。行为目录重新生成；行为说明中地下行进的“受击框在钻孔处”（R3 起已不设）一并更正。
- 验证（核心 r95，隔离存档，墙钟前移，未计算 SHA-256；`verification/iron_death_worm_20261025/`：`run_r4.sh`、`run_r4_all.sh`、`ana_probe_r4.py`、`ana_debris_r4.py`、`render_parts.py`，图 `r4/`）：
  - 部件判定探针（`driver_battle.py --probe-hit`，在外框四周外扩 16 的范围内每 8 个点以 1 × 1 矩形调用 `hitTest`）：我方与敌方侧各 13 帧（钻出、钻入、钻离、钻击、待机、掘削），结果与按描述符部件算出的期望逐点相同（0 处不符；敌方侧按镜像）；钻出 / 钻入中命中点占外框内点的 39–44%，钻离 60–68%，钻击 54–58%。
  - 掘削碎块（我方、敌方侧、掘削据点）：每个碎块都爆炸（引信与碰撞约各半），落地后弹起（多为两次）再贴地滚动 18–150 像素，落地 15 tick 后在地面爆炸；碰到敌方单位的在空中或滚动中立即爆炸；26 个碎块的攻击 ID 在滚动与爆炸中均不变；爆炸攻击框只开 4 tick。游戏内截图 `r4/debris_ingame.png`（碎块在地面滚动后出现小爆炸）。掘削对据点每次合计 14800（同 R3）。
  - 绝招：敌方据点每次钻击 16 段合计 8000；与钻身重叠的叛军步兵在钻击中 13 段合计 6500、在钻离中 12 段合计 6000（钻身尚在空中或已离开地面的段落碰不到地面上的步兵）；每个动作建立 16 个攻击 ID。
  - 同一场景（`r3_main` / `r4_main`）中本单位所受伤害 21780 → 18360（外框中的空白处不再中弹）。
  - 无受击框的帧（我方、敌方侧、两场压力测试）只在地下段落（同 R3）；压力测试 12 个实例无停住，损毁的均移除；静态普查只多出碎块弹体脚本 113–119（弹体不设受击框）；损毁与强制状态的动作序列与 R3 相同。
  - 单位菜单 STATUS：Lv40 生命 60000、AP 850、价格 150、掘削 400、绝招 500；ACTION 正常，图像范围不变，签名 e464405a70d875b4 → 92ba0c1572ed9e1a 并入两份 `unit_viewer_bounds.json`。
  - N1 回滚 2400 帧、698 次回滚逐帧一致（`n1_compare_r4.json`）；蜈蚣长老与侵略者之王在 r94（`dist/MSD_Windows`，只读）与 r95 下 900 帧逐帧相同（`cmp_regress_r4.json`）。
  - `content_tool.py validate`（音效 71）、`check_body_offline.py` 10/10、`check_ura4_offline.py` 19/19、单元测试 21/22（既有 `msd_aot`），`lab_probe.jsonl` 未变。
- 未覆盖：关卡与对战中的平衡与实机观感（碎块弹跳与爆炸、部件判定后本单位更难被打中）；两机联机；部件判定只作用于伤害碰撞，原生的索敌距离与前线仍按外框与单位宽度。修改前副本 `verification/iron_death_worm_20261025/before_r4/`。

## 14. R4 同步（2026-10-25）

- 用户要求按 R4 同步（含核心 r95）。`verification/iron_death_worm_20261025/deploy_r4.py`（AGENTS 第 2.2、2.3 节持续授权，记录 `deployment_r4.json`、`sync_r4/`）：覆盖宿主与行为库 3 项及 `src/` 镜像、`src/community_content.cpp`、`src/community_blocks.inc`、两份 `core_runtime.json` 与 `lab_runtime.py`、`docs/modding/BEHAVIOR_CATALOG.md`、单位文件、描述符、`content.json`、`NOTICE.md` 与本文档（覆盖前与工作区 R4 修改前的副本 `before_r4/` 逐字节相同，即第 12 节同步后的版本）；两份 `unit_viewer_bounds.json` 以目标文件为底本只替换本单位一项（合并后各单位条目与工作区相同，只有说明字段不同）；新增 r95（根 `build/` 与 `src/build/`，旧核心保留）与 2 条音效 `irondw_drill_stop.msdf`、`irondw_drill_star.msdf`。图集、头像图集与 `src/behavior_manifest.inc`（运行目录本无此文件）不写入。两目录各写入 24 个文件，同步后逐字节一致，保护文件 131、345 个不变，同步时无 Python 进程，两目录核心 r95；同步后以 `cmp_rundirs_r3.py` 比较，工作区与两目录的其余差异与 R3 同步后相同（`lab_config.json` 等个人设置与既有的目录差异）。
- 两目录自身程序（`MSD_VERIFY_ROOT`，`run_installed_r4.sh`、`cmp_installed_r4.py`，结果 `cmp_installed_r4.json`）：`content_tool.py validate` 通过，内容摘要与工作区相同（音效 71）；我方出击与绝招、敌方侧各 1500 帧与掘削据点 700 帧在两目录、绝招重叠场景 1400 帧在用户副本与工作区逐帧相同；`dist/MSD_Windows` 的绝招重叠场景自第 1329 帧起有 70 帧不同，差异只在损毁碎块弹体（动作 52–55）记录的攻击框偏移（+0xdc–+0xe8）：这些弹体从不开攻击框（开关 +0xec 为 0），该处为未初始化内存，记录驱动自 R4 起才读取弹体的这一字段；排除后逐帧相同。单位菜单 STATUS（Lv40 生命 60000、AP 850、价格 150、掘削 400、绝招 500）与 ACTION 正常，动作演示使用随附的图像范围。运行中的游戏需重启加载。

## 15. R4 音效回退（2026-10-25）

- 用户要求“回退音效的修改”。生成脚本去掉 MSXX 的 `DRILL_STOP` / `DRILL_STAR`（常量、op23 换算、编码与登记），钻入 7（含子层 8）、钻击 33、钻出 12（含子层 13）与钻离 25 恢复 MSA 2716（`s1xlv.irondw_move`），重新生成后单位文件只有这 8 处 op23 改变；`content.json` 去掉两条音效登记、`NOTICE.md` 去掉两句来源说明，两者恢复为 R4 修改前的原样；工作区删除 `community_content/irondw_drill_stop.msdf`、`irondw_drill_star.msdf`。核心（r95）、行为库、描述符、图集与其余 R4 内容（部件判定、碎块弹跳爆炸、生命 60000、绝招 16 段 × 500）不变。修改前副本 `verification/iron_death_worm_20261025/before_r4_sound/`（`patch_gen_r4_sound_revert.py`）。
- 验证（核心 r95，隔离存档，墙钟前移，未计算 SHA-256）：`content_tool.py validate` 通过（音效 69）；我方出击与绝招 1500 帧（`r4s_main`，同 `r4_main` 的参数）双方单位、弹体与效果记录除音效外逐帧相同，原先播放 DRILL_STOP / DRILL_STAR（SoundID 166 / 167）的 28 帧改为播放 `irondw_move`（165）。
- 同步（同日，用户要求）：`verification/iron_death_worm_20261025/deploy_r4s.py`（AGENTS 第 2.2、2.3 节持续授权，记录 `deployment_r4s.json`、`sync_r4s/`）：两目录覆盖单位文件、`content.json`、`NOTICE.md` 与本文档（覆盖前与第 14 节同步写入的版本逐字节相同），同步后逐字节一致，保护文件 131、346 个不变，两目录核心 r95。`dist/MSD_Windows` 删除 R4 同步新增的 `irondw_drill_stop.msdf`、`irondw_drill_star.msdf`（删除前与 R4 写入的内容逐字节相同，副本在 `sync_r4s/dist/before/`）。同步时用户副本的游戏正在运行（`pythonw.exe` 45932，全解锁满级入口，9:35 启动，已载入 R4 的两条音效），游戏可能在播放时才读取音效文件，该目录的这两个文件暂不删除；回退后的 `content.json` 不再登记它们，重启后不会使用。两目录自身程序（`MSD_VERIFY_ROOT`）：`content_tool.py validate` 通过（音效 69）；我方出击与绝招 1500 帧在用户副本与工作区（`r4s_main`）逐帧相同（含音效）；`dist/MSD_Windows` 只在一个空弹体对象（UnitID −1、动作 −1、状态 0，攻击框未开）记录的攻击框偏移与攻击 ID 上不同（未初始化内存），排除后逐帧相同（含音效）。运行中的游戏需退出后重启加载。

## 16. R5（2026-10-25，核心 r96，行为 `iron_death_worm` v4，行为库 21）：钻入 / 钻出 2 倍速

- 用户要求：钻出 / 缩回的速度为现在的 200%，动画播放一并加快；不影响大招的速度。
- 生成脚本：钻入 7 与钻出 12（连同各自的子层 8–11、13–16）按 2 倍速重采样为副本 120 / 121（子层 122–129）：新第 k tick 显示原第 2k tick 的帧、旋转、偏移与缩放，挂载与音效在原 tick 的一半处（向下取整）；时长 89 → 45 tick。原 7 / 12 保留在描述符中。行为参数 `burrow_animation` 120、`emerge_animation` 121，新增 `special_emerge_animation` 12（行为 v4，行为库 21，ZSpec 字 120）。受击框分段规则收紧为“该段 4 tick 中身体全在地下时不设受击框”（R3 / R4 按前后各加 1 tick 判断）；大招用到的 12 / 25 / 33 与待机 6、掘削 17 的受击框与攻击框换算出的值与 R4 相同（只有框表序号变化），新钻出 121 前 4 tick、新钻入 120 末 5 tick 不设受击框。受击框表 793 → 973 条。
- 核心 r96：大招中的钻出（绝招开始时在地下先于原处钻出、钻击后回原处钻出）改用字 120（原速的 12）；出场、移动结束与为近距攻击的钻出用字 106（2 倍速）；`msd_community_iron_death_worm_version` 5，宿主要求 ≥ 5。
- 验证（核心 r96，隔离存档，墙钟前移，未计算 SHA-256；`verification/iron_death_worm_20261025/`：`run_r5.sh`、`run_r5_all.sh`、`ana_r5.py`，图 `r5/fast_vs_orig.png`）：我方与敌方侧中钻入 120 与钻出 121 均为 45 tick（R4 的 7 / 12 为 89 tick），大招 25 → 33 → 12 合计 251 tick、大招中的钻出 12 为 89 tick（同 R4）；地下行进中发动大招（`r5_spunder`）时先以原速的 12 钻出（89 tick）再钻离，之后移动用 2 倍速的钻入；2 倍速钻出第 4 / 15 / 30 / 44 tick 的画面与原速第 8 / 30 / 60 / 88 tick 相同；存活时无受击框的帧只在地下段落（121 前 4 tick、120 末 5 tick、大招中 12 前 8 tick、33 末 8 tick、地下行进）；压力测试 12 个实例无停住、损毁的均移除；损毁与强制状态流程正常；单位菜单 STATUS 不变（Lv40 生命 60000、AP 850、价格 150、掘削 400、绝招 500），ACTION 正常，图像范围不变，签名 92ba0c1572ed9e1a → d6c2965b61331596 并入两份 `unit_viewer_bounds.json`；N1 回滚 2400 帧、698 次回滚逐帧一致；蜈蚣长老与侵略者之王在 r95（`dist/MSD_Windows`，只读）与 r96 下 900 帧逐帧相同；`content_tool.py validate`（音效 69）、`check_body_offline.py` 10/10、`check_ura4_offline.py` 19/19、单元测试 21/22（既有 `msd_aot`），`lab_probe.jsonl` 未变。
- 未覆盖：实机观感；两机联机。修改前副本 `verification/iron_death_worm_20261025/before_r5/`。
- 同步（同日，用户要求）：`verification/iron_death_worm_20261025/deploy_r5.py`（第 2.2、2.3 节持续授权，记录 `deployment_r5.json`、`sync_r5/`）。两目录覆盖宿主与行为库 3 项及 `src/` 镜像、`src/community_content.cpp`、两份 `core_runtime.json` 与 `lab_runtime.py`、`BEHAVIOR_CATALOG.md`、单位文件、描述符与单位文档（覆盖前与工作区 R5 修改前的副本逐字节相同，即音效回退同步后的版本），两份 `unit_viewer_bounds.json` 以目标文件为底本只替换本单位一项，新增 r96（根 `build/` 与 `src/build/`，旧核心保留）；同步后逐字节一致，保护文件 131、347 个不变，同步时无 Python 进程，两目录核心 r96；工作区与两目录的其余差异与此前相同（用户副本另有按用户决定保留的两条 MSXX 音效文件）。两目录自身程序（`MSD_VERIFY_ROOT`，`run_installed_r5.sh`、`cmp_installed_r5.py`，结果 `cmp_installed_r5.json`）：`content_tool.py validate` 通过（音效 69）；我方出击与绝招、敌方侧各 1500 帧与地下发动大招 700 帧三个场景与工作区逐帧相同（含音效；攻击框未开的弹体不计其攻击框偏移与攻击 ID）；单位菜单 STATUS（Lv40 生命 60000、AP 850、价格 150、掘削 400、绝招 500）与 ACTION 正常。运行中的游戏需重启加载。（文档补写后单独再同步，`deploy_r5.py --docs-only`。）

## 17. R6 钻入音效（2026-10-25）

- 用户说明：钻入与钻出各播两个音效——“钻出”声（原版 425 `bull_drill_1`）与石块声（MSA 2716 `s1xlv.irondw_move`）；R4 把石块声换成了 MSXX 的 DRILL_STAR / DRILL_STOP（钻出变为“钻出、钻出”，缩回变为“钻出、钻入”），换错了音效；要求钻出为“钻出、石块声”，缩回为“钻入、石块声”。核对（MSXX WAV 与两者的对数频谱相关）：425 与 `DRILL_STAR` 最接近（0.59），2716 与 `ST1_B4_STONS`（石块，0.69）及 `BOSS1_*` 最接近，与用户的说明一致。
- 实施：生成脚本把缩回地面的钻入 7（2 倍速副本 120 随之）与钻击 33（自空中钻入地下；R4 时用户把它归入“钻入”）中的 425 换为 MSXX 的 `DRILL_STOP`（`s1xlv.irondw_drill_stop`，音量 100），石块声保持；钻出 121、绝招中的钻出 12 与钻离 25 不变。重新生成后单位文件只有这 3 处 op23 改变；`content.json` 登记该音效（SoundID 按载入顺序为 166）；`community_content/irondw_drill_stop.msdf` 取 R4 编码的同一文件（与用户副本中保留的文件逐字节相同；生成脚本在文件已存在时不重新编码）；`NOTICE.md` 中英补记来源。核心（r96）与其余内容不变。修改前副本 `verification/iron_death_worm_20261025/before_r6/`（`patch_gen_r6.py`、`patch_notice_r6.py`）。
- 验证（核心 r96，隔离存档，墙钟前移，未计算 SHA-256）：`content_tool.py validate` 通过（音效 70）；我方出击与绝招 1500 帧（`r6_main`，同 `r5_main`）双方单位、弹体与效果记录除音效外逐帧相同；钻出（121、大招中的 12、钻离 25）开始时播放 425 与 165，钻入（120）与钻击 33 开始时播放 166（DRILL_STOP）与 165。
- 同步（同日，用户要求）：`verification/iron_death_worm_20261025/deploy_r6.py`（第 2.2、2.3 节持续授权，记录 `deployment_r6.json`、`sync_r6/`）。两目录覆盖单位文件、`content.json`、`NOTICE.md` 与单位文档（覆盖前与工作区 R6 修改前的副本逐字节相同，即 R5 同步后的版本）；`dist/MSD_Windows` 新增 `irondw_drill_stop.msdf`，用户副本中按用户决定保留的同名文件与工作区逐字节相同，不再写入（同时保留的 `irondw_drill_star.msdf` 仍未登记、不使用）。同步后逐字节一致，保护文件 131、349 个不变，同步时无 Python 进程，两目录核心 r96。两目录自身程序（`MSD_VERIFY_ROOT`）：`content_tool.py validate` 通过（音效 70）；我方出击与绝招 1500 帧与工作区逐帧相同（含音效，`cmp_installed_r6.json`），SoundID 165 / 166 分配相同。运行中的游戏需重启加载。（文档补写后单独再同步，`deploy_r6.py --docs-only`。）
