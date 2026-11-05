# 《合金弹头7》任务 7（最终任务）关卡与新单位策划草案（2026-11-03）

状态：策划草案（R0）。游戏文件、核心、行为库与本体内容均未修改；脚本、截帧与测量结果在 `verification/ms7_m7_20261103/`。做法沿用任务 1–6（`docs/ms7/MS7_M1_STAGE_PLAN_2026-10-25.md` 至 `MS7_M6_STAGE_PLAN_2026-11-03.md`）。按 AGENTS 第 2.1 节末条只写在正式版工作区，不同步两个运行目录。未计算 SHA-256。

## 1. 用户要求（2026-11-03）

- 开始 MS7 / MSXX 任务 7（最终任务）的移植策划：3 个新单位、6 关。
- 最终关使用 MSA 的现成场景素材。
- 大门：MSA 有现成素材；逻辑按 MSD 的强度另定（与 MSA 不同）。
- 挪威海怪：在 MSA 中查找；本项目的版本按原作加入 6 个触手作为第一阶段。
- 带炮管的 Rebel Walker：新单位，逻辑与原版 Rebel Walker 相近，没有近距攻击，以炮管发射跟踪弹（同原作）。用户已提供素材表 `F:\egg\MS7\DS _ DSi - Metal Slug 7 - Enemies - Rebel Walker.png`。

## 2. 素材

### 2.1 背景素材表（`layers.py` → `overview/layers.txt`、`overview/m7_boxes.png`；分段预览 `crops.py` → `overview/sec1.png`、`sec2.png`、`sec3.png`、`boss.png`、`examples.png`）

`F:\egg\MS7\DS _ DSi - Metal Slug 7 - Backgrounds - Mission 7.png`：10516×2124，底色 (16,216,128) 不透明，无半透明像素；拆图者 Division（A JAPANESE SOLDIER），要求注明来源（采用时 `NOTICE.md` 补记，同任务 4–6）。坐标为素材表像素；逻辑宽按任务 4–6 的比例 × 1.6 估算，本任务的比例尚未用录像核对。

| 段 | 图层（外接框，素材像素） | 内容 | 宽 × 1.6 |
| --- | --- | --- | --- |
| SECTION 1 | #1 (30,84) 2560×896、#2 (2620,84) 2176×896 | #1：废铁塔林前的栈道，左段平、中段向右下倾斜（目视坡度约 0.27）、右段平，上方另有数段短平台；#2：阶梯形外框的阴云夜空（远景） | #1 4096（高 1434） |
| SECTION 2 | #5 (4877,197) 2816×72、#8 (4877,408) 3328×173、#10 (4877,611) 3328×298、#6 80×90、#9 143×247、#11 111×245 | #10：废铁洞内的走廊（钢架立柱、管道，三段斜纹平台与碎石地面），右端约 x 7600–8205 为大门的爪形底座与光柱；#8 为废铁堆墙（远景），#5 为顶部碎块带；#9、#11 为立柱件，#6 为小块 | #10 5325（高 477） |
| SECTION 3 | #15 (158,1070) 1792×328、#19 (527,1296) 1167×286、#16 (1980,1123) 1920×918、#20 193×48、#21 255×57、#25 159×124、#34 512×122 | #16：左侧多层台阶脚手架向上，上方接横向的管道栈道；#15、#19 为碎块顶棚与环形碎块带；#21 为梁件 | #16 3072（高 1469） |
| BOSS SECTION | #22 (4266,1253) 1536×384、#26 (4266,1667) 1536×128、#23 (5832,1279) 1408×490、#27–#33 (4789–6516, 1825–1832) 各 216–289 × 79–86 | #22：熔岩海与远处岩丘、漂浮残骸（左端为废铁崖与平台）；#26：熔岩面；#23：星空、红月与暗色山脊；#27–#33：沉在熔岩中的首领底座 7 态，触手由 5–6 条逐次减少，最后一态只剩一条焦黑的触手（`overview/boss_tentacle_states.png`） | #22 2458（高 614） |
| EXAMPLES | #7、#12、#18、#24；#13 为署名 | 拆图者合成的示例；#24 为首领段（熔岩海、红月、带六触手的首领） | — |

- 一屏为 711 × 280 素材像素（同任务 5、6）。尺寸参考与据点标记图样复制到 `verification/ms7_m7_20261103/handoff/`（`frame_guide.png`、`base_marker_L.png` / `base_marker_R.png`，与任务 6 相同）。
- 同目录的 `...Backgrounds - Unused Section.png`（3925×1272）为砖石室内，内容与任务 7 无关（`overview/unused_section.png`）。

### 2.2 Rebel Walker 素材表（用户 2026-11-03 提供）

`...Enemies - Rebel Walker.png`：589×1471，RGB，白底、效果格为粉底 (255,204,204)；拆图者 Gussprint，要求注明来源。行（帧数为目视计数）：IDLE 8 与 IDLE(LEGS)、WALKING 与 WALKING(LEGS)、JUMPING / LANDING 及其腿部、TURNING 11、TURNING（W/ ROCKET LAUNCHERS）11、HOVERING（表内注明不确定是否使用）、"OPEN WIDE!"、PLASMA CANNON、MELEE ATTACK（刀刃）、MORTAR（OPENING / SHOOTING）、WRECKED 与 WRECKED（W/ ROCKET LAUNCHERS）、DEBRIS 6；肩部火箭发射器 1 件（表内注明“按肩甲位置摆放并随之旋转”）、发射火光与烟 2 行、导弹 4 帧（带尾焰）、迫击炮弹多角度约 47 帧、爆炸与光环；右侧为调色板（`overview/rw_turn_rl.png`、`rw_wreck_rl.png`、`rw_debris_missile.png`）。

- 与 MSD 原生 228 图集逐像素比较（`rw_match.py` → `overview/rw_match.txt`，掩膜内平均色差）：迫击炮弹各帧为 0（原生图集含同一组帧）；火箭发射器 47、导弹 62–68、带发射器的转身帧 58–67，原生图集没有这些帧。带炮管的版本须从本素材表导入发射器与导弹；待机、行走、跳跃等帧在素材表中不带发射器，须按“摆放在肩甲并随之旋转”逐帧挂上发射器部件。

## 3. 参考录像（内置浏览器静音截帧，未下载）

- 录像 A：https://www.youtube.com/watch?v=KepHNkXkFq0 （Metal Slug XX (PSP) Mission 7 Finale Walkthrough，924.7 秒，1280×720，单人）。截帧拼图 `ref/shots/A_005_465_s20.jpg`、`A_485_922_s19.jpg`（全程）、`A_256_500_walker_gate.jpg`、`A_walkers_fine.jpg`、`A_506_722_kraken1.jpg`、`A_726_870_kraken2.jpg`（`decode_shot.py` 由工具结果解码）。内容为目视记录，未逐帧核对；DS 版（MS7）未查看，两作的差异未核对。

| 录像（秒） | 内容 | 素材 |
| --- | --- | --- |
| 5–150 | SECTION 1：废铁塔林前的栈道；坦克、直升机、步兵 | #1、#2 |
| 155–300 | SECTION 2：废铁洞走廊；红色 Rebel Walker（跳跃、近身）、飞行的未来兵 | #10、#8、#5 |
| 302–346 | 大门（中首领）：走廊右端出现巨大的环形时空门；门中放出飞行的蓝色未来兵，并发射绿色光环弹；346 秒白闪后消失 | #10 右端、MSA 564 |
| 350–500 | SECTION 3：多层脚手架与台阶；Rebel Walker 成群 | #16、#15、#19 |
| 504–520 | 进入熔岩海（漂浮残骸平台） | #22、#26、#23 |
| 522–690 | 首领第一阶段：本体停在画面左上，带刺钻头的分节触手从熔岩中升起、横扫或刺下，触手前端发射蓝色光环，另有熔岩火柱；触手逐条被击毁（626、650 秒为损毁的锈色触手） | #27–#33 为底座 7 态 |
| 698–714 | 本体沉入熔岩 | — |
| 714–867 | 首领第二阶段：本体悬停在画面上方（只见下半），投下卫星弹、发射弹体，伴蓝色光雾；867 秒坠落 | MSA 309 的形态 |
| 870–924 | 任务结束、解救俘虏、结算 | — |

- 带火箭发射器的 Rebel Walker 在本录像的截帧中未能分辨（截帧分辨率不足），原作的导弹发射方式（发数、升空后转向的轨迹）待以 DS 版或更清晰的录像核对。

## 4. MSA 数据（`msa_m7_names.py` → `overview/msa_m7_names.json`；`msa_m7_stats.py`、`msa_m7_summary.py` → `msa_m7_stats.json`、`msa_m7_summary.txt`；`msa_m7_classes.py` → `msa_m7_classes.txt`；导出 `F:\egg\research\metal_slug_attack\decoded\units\0260、0309、0310、0563、0564、0706、0977、1038、1288、1289、1291\`）

### 4.1 条目

| UnitID | 名称（英 / 简） | 动作类 | 开放 |
| --- | --- | --- | --- |
| 260 / 310 | KRAKEN / 挪威海怪；KRAKEN(ボス専用) | `BattleAction_Kraken` | 未开放 |
| 309 | KRAKEN（简体名「巨型章鱼」，日文 クラーケン） | `BattleAction_Kraken` | 2000-01-01（玩家单位） |
| 706 / 717 | KRAKEN MK II / 挪威海怪 MK Ⅱ | `BattleAction_KrakenMk2` | 2017-11-28 / 未开放 |
| 1038 | GOLDEN KRAKEN / 金色挪威海怪 | `BattleAction_KrakenGold` | 2019-01-11 |
| 1288 / 1289 / 1291 | MASTER KRAKEN / 挪威海怪长官（1289 为手臂） | `MasterKraken` / `MasterKrakenArm` | 2019-11-25 / 未开放 |
| 563 | BIG GATE / 大门（修筑者） | `createActionKouhei`（工兵） | 2017-06-15 |
| 564 | BIG GATE / 大门（门本体） | `BattleAction_BigGate` | 未开放（由 563 修筑） |
| 1527–1529、1788–1795 | GOLDEN BIG GATE、DARK GATE | 各自的类 | 2020–2021，本任务不采用 |
| 228 / 573 | REBEL WALKER / 叛军 沃克 | `BattleAction_LevelWalker` | 未开放 / 2017-06-29 |
| 977 | REBEL WALKER MK Ⅱ（普攻卫星弹、绝招诱导光线弹） | `BattleAction_LevelWalkerMk2` | 2018-10-17 |

### 4.2 挪威海怪 KRAKEN（309 为已开放的玩家单位）

- 说明（简体）：“普通攻击：卫星导弹 特殊攻击：熔岩弹 / 从未来而来的魔登军究极兵器。拥有熔岩都无法穿破的强固装甲。”
- 数值（309，首次进化等级 3）：生命 Lv1 54450 / Lv40 163350，击退门槛 10，移速 1.6，AP 2000，生产时间 3000，近 / 远攻击距离 30 / 450；攻击 1 伤害 Lv40 2359.5（等待 10），攻击 2 1089（卫星导弹，弹速 9、投射距离 600），攻击 3 1815（熔岩弹，投射距离 800、冷却 800、首次 600），攻击 4 10890（投射距离 1200）；绘制优先级 −100，耐性普通 / 爆炸 / 火焰 / 首领均为 1。260 为同一动作记录的敌方版本（Lv40 生命 90000），310 为首领版（108900，移速 1.0）。
- 图集：`BSKRAKEN_base_out.obm`（1024×1024）一张，186 个矩形、63 个脚本、受击框 3、攻击框 8。内容为圆顶外壳、带炮管的下半身、卫星弹（圆筒）、熔岩弹（橙色火焰盘）、蓝色光雾轮廓、烟与爆炸、损毁后的本体（`decoded\units\0309\BSKRAKEN_base_out.obm.png`；动作槽预览 `msa_0309/slot_<n>.png`、`overview/msa_0309_slots.png`、`msa_key_slots.png`）。图集中没有触手。
- 动作类（arm64 符号大小）：`update` 1512、`spAttack` 1064、`dead` 412、`move` 380、`shotBullet` 312、`summonUnitWall` 268、`returnShortAttack` 220、`wall` 192、`createSatellite` 92、`playerAppearState` 76、`actionMoveYurayura` 76、`actionViewPosition` 72、`isSpAttackDistance` 44，合计约 4.7 KB（UNION 约 12.5 KB）。`actionMoveYurayura` 推定为悬浮摇摆，`summonUnitWall` / `wall` 的作用未解读。
- 音效：SoundID 344 `OgE_Shot_S`（12 处）、294 `BOMBS1`（5）、500 `kraken_sp1`、501 `kraken_sp2`、502 `B4_EXPBB_MID`（`m_sound_data`）。
- MK II（706）另有火柱效果图集 `BSKRAKEN_red_eff_base_1_out.obm`，同样没有触手。MASTER KRAKEN（1289 手臂）的图集 `41707master_kraken_arm_out.obm` 有分节的臂段与带刺的钻头，预览中动作槽 12 以 op12 逐节生成臂段（`msa_1289/slot_<n>.png`、`overview/msa_1289_slots.png`；预览不执行动作类，实际运动未核对），外形与原作触手相近，属 MSA 原创单位的素材。

### 4.3 大门 BIG GATE（563 修筑者 + 564 门本体）

- 说明（简体）：“连接着未来和现在的兵器。为了援助现在的莫丁军，未来的莫丁军会门里面出来。”技能均作用于“已生产的 F.反坦克兵”（移速、生命、攻击）与本体生命。
- 563（修筑者，`createActionKouhei`）：AP 280、生产时间 2500、价格 120、移速 8.0、生命 1；564（门）：生命 Lv1 33000 / Lv40 99000、击退门槛 −100、不移动、远攻击距离 600、攻击 3 冷却 600 / 首次 600、无伤害值；耐性普通 / 爆炸 / 火焰 0、首领 1；绘制优先级 −78。
- 图集：`BigGate1_out.obm`（1024×512：蓝色漩涡、铜色与红色的环、绿 / 橙 / 蓝光环、青绿色爆炸与黑烟、爪形底座）、`BigGate2_out.obm`（暗色圆点）、`BigGate3_out.obm`（F.反坦克兵小图）；51 个矩形、32 个脚本。槽 7、8 在第 32、64 tick 以 op12 生成独立对象（推定为召唤效果；槽 7 每次 1 个、槽 8 每次 3 个）并播放 SoundID 390（`sol_wolf_1`）（`msa_0564/slot_<n>.png`）。
- 动作类：`BigGate::update` 1112、`RandumBurst` 240（损毁时随机爆炸）、`createObject` 48，另有 `EffectAction_BigGateSummon::update` 272（召唤效果），合计约 1.7 KB。
- MSD 对应：MSA 的 F.反坦克兵对应 MSD 原生 210 F.BAZOOKA SOLDIER（`BattleAction_FutureZakoLaser`）；MSD 原生召唤建筑为 64（`BattleAction_MummyGate`，由 77 MUMMY GENERATOR 工兵修筑）。本体已有行为 `build_structure`、`summon_units` / `summon_internal_unit`、`summon_on_hit`、`structure_death_effect` 与工兵生命设定（AGENTS 第 6.3 节），MSA 大门的“工兵修筑、定时放出单位、损毁爆炸”流程可先以这些行为组合，不足之处再加核心改动。

### 4.4 最终关背景 MSA bg 158（`msa_bg_export.py 4a108a0` → `msa/record.json`、`msa/script_dump.txt`；图集 PNG 取自任务 6 的 `verification/ms7_m6_20261103/msa/`）

- `m_bg` 158 = `ms7_7st_base_out.obm`：左右端 0 / 1024、据点 100 / 940（图集像素）；`m_bg_land_point` 158 为 (0,405)–(9999,405)（平地）。用于 MSA 关卡 7623 等 39 关（任务 6 `msa_bg.py` 的 `msa/msa_bg_ms7.json`），其中终极任务 22002 的配乐为 `bgm_ms7_boss.ogg`。
- 动作记录（`libAppMain.so` 0x4a108a0，2 张图集、71 个矩形、72 帧、33 个脚本）：页 0（1024×1024）为熔岩地面 1024×250（矩形 0，锚点 (0,−261)）与星空红月 1024×512（矩形 1）；页 1 `ms7_7st_f_out.obm`（512×256）为漂浮残骸平台 10 个（含翻转）、熔岩波纹 8 帧、熔岩泡。脚本 0 以 op36 在 x 180–780 一带、y 375 每 60 挂一块残骸（脚本 2–13 各自的波纹相位，每帧 24 tick），脚本 14–25 为错开相位的波纹 8 帧（每帧 3 tick），脚本 26–32 为间隔出现的熔岩泡（每帧 2 tick）。
- 按 × 1.6 换算，场地宽 1638 逻辑、据点 160 / 1504，约为一屏（可见宽约 1138 逻辑）的 1.4 倍。DS 素材表的 #22 + #26 + #23 为同类画面、宽 2458 逻辑，可作加宽的取材。

## 5. MSD 原生 Rebel Walker（228）

- `dump_units.py` / `native_info.py`（核心 r139，隔离存档，`runs/rw_*`、`runs/ni228_*`）：动作类 `BattleAction_LevelWalker`（另有 `BulletAction_LevelWalker_L` / `_SP`、`EventAction_LevelWalker_L` / `_SP`），图集 `levelwalker_out.obm`（512×512，`overview/native_228_atlas.png`、`native_228_atlas_rects.png`），239 个矩形、76 个脚本、受击框 [−22,−37,40,37]。
- 数值：生命 Lv1 2000 / Lv40 6000，AP 200，生产时间 600，移速 3.5，击退门槛 15；近距 Lv40 1750（射程 50，即刀刃）、远距 1750（射程 350，等待 15，光束）、绝招 800（等待 80，卫星弹）；价格 120。
- 名称：EN REBEL WALKER、JP レベルウォーカー、KR 레벨 워커、ES CAMINANTE REBELDE、PT CAMINHANTE REBELDE、FR MARCHEUR REBELLE、IT WALKER RIBELLE、RU РЭБЭЛ УОКЕР、ZT 雷貝爾沃克；DE 与 ZS 为空（按惯例取英语与繁体转写「雷贝尔沃克」）。说明 ZT：“普通攻擊：鐳射彈 特殊攻擊：衛星彈 / 從未來而來的莫迪軍新兵器。已小型和輕快的動作為特徵。”
- MSA 228 与 MSD 同类（MSA Lv40 生命 5000）；MSA 977 MK Ⅱ 为绿色换色、无发射器（`decoded\units\0977\levelwalker_Mk2_out.obm.png`）。

## 6. 新单位方案（草案，待用户决定）

### 6.1 带炮管的 Rebel Walker

- 以原生 228 为基准（`base_id` 228，沿用 `BattleAction_LevelWalker` 的行走、跳跃与受击），近距攻击去掉，以肩部发射器发射追踪导弹。图像：原生图集 + 本素材表的发射器、导弹、发射火光（8 位、256 色以内，放第二页）；发射器按肩甲位置逐帧挂上。
- 追踪：本体现有的追踪只在专用行为内（UNION 弹体种类 5：水平射出后每帧转向至多约 6°；飞行护盾陨石 `homing_animation`；鼹鼠弹俯冲）。建议新增通用行为（例 `homing_bullets`：弹体脚本、转向上限、开始转向的帧、最长追踪帧），以 UNION 种类 5 的核心实现为底，需行为库与核心改动。
- 待定：远距光束与绝招卫星弹是否保留；导弹属远距普攻或绝招、每次发数、射程与伤害；是否同作玩家单位与关卡敌方；名称（候选「雷贝尔沃克（炮管）」等）。

### 6.2 大门

- 素材用 MSA 564（环形门、漩涡、爪形底座、召唤效果、损毁爆炸），沿用既有规则（op19 75% 改为 100%，偏移与判定框 × 4/3）。
- 逻辑由用户另定。可选的组成：(a) 玩家单位，工兵修筑后定时放出未来兵（同 MSA，基准 77 + 64 与 `build_structure`、`summon_units`）；(b) 关卡中首领，按原作放出飞行的未来兵并发射绿色光环；(c) 两者兼有。放出的单位（MSA 为 F.反坦克兵，原作为飞行的未来兵）、间隔、生命（MSA Lv40 99000）与是否自身攻击待用户定。

### 6.3 挪威海怪（第一阶段 6 触手）

- 第二阶段按 MSA 309 的 `BattleAction_Kraken` 移植（悬浮、卫星导弹、熔岩弹、损毁），逐条解读 MSA 底层代码。
- 第一阶段为本项目追加：6 条触手。建议做法：触手为 6 个内部单位，各有生命，可被选为目标；本体在触手全部被击毁前不受伤（或按比例减伤），全部被击毁后进入第二阶段；与 UNION 的三机做法相同（生成、隐去、回滚状态登记、单位菜单演示另需处理）。另一做法为本体部件判定（核心 r95 的部件条目），触手不作单位。
- 触手素材：MSA 309 / 260 / 310 / 706 均无触手；DS 背景表 #27–#33 为底座 7 态（静态，触手不动）；MASTER KRAKEN 1289 的臂段与钻头为外形相近的 MSA 素材。原作触手的升起、横扫、刺下与蓝色光环须有逐帧素材，来源待用户决定（MSA 1289 拼装、DS 底座 7 态、或用户另提供原作首领精灵表）。
- 数值起点：MSA 309 Lv40 生命 163350、AP 2000、生产时间 3000；按以往 MSA 单位的做法由用户削弱后设定（AGENTS 第 6.1 节逐项记录）。

## 7. 关卡分配草案（未出示意图；取材以用户标定为准）

| 关 | 草案取材 | 内容 |
| --- | --- | --- |
| 1 | SECTION 1 #1 + 远景 #2 | 栈道（左平、中段斜坡、右平），斜坡上的出兵区按第 6.2 节拉平 |
| 2 | SECTION 2 #10 左段 + #8 / #5 | 废铁洞走廊，Rebel Walker 首次出场 |
| 3 | SECTION 2 #10 右段（大门底座） | 大门关：门作敌方中首领或据点旁的召唤建筑 |
| 4 | SECTION 3 #16 台阶脚手架 | 纵向结构，按任务 3–6 的做法横向重拼 |
| 5 | SECTION 3 #16 上段管道栈道 + #15 / #19，或 DS 熔岩海 #22 | 首领前一关 |
| 6 | MSA bg 158（熔岩海、红月、漂浮残骸） | 挪威海怪首领战；宽度原样 1638 逻辑，或以 #22 / #26 / #23 加宽 |

## 8. 区域、配乐与音效（建议）

- 区域：里世界 4 第 12 区域 `s1xlv.ura4.m12`，关卡 13121–13126（区域表每世界 16 个，第 12 区域无需翻页）；名称与里地图位置待定。
- 配乐：MSXX `STRM_STG7`（`F:\egg\MS7\MSXX-audio-wav\BGM\`，尚未使用）作第 1–5 关；首领关候选 `STRM_BOSS3`（尚未使用）或 MSA `bgm_ms7_boss.msa`、`bgm_ms7_st7.msa`。循环点按原版循环音轨核对。
- 音效：MSA 309 / 564 的音效见第 4.2、4.3 节；MSXX SE 中有 `GATE.wav` 与 `ST7_*` 22 条（例 `ST7_HOUDAN_SHOT`、`ST7_OGUFO_WARP1`、`ST7_F322BEAM`），按“移植单位的音效取自原作”的规则对照录像选用。

## 9. 待用户决定

1. 六关取材：在素材表副本上框定各关区域与据点（尺寸参考 `handoff/`）；第 6 关 MSA bg 158 的宽度（原样或加宽）。
2. 带炮管的 Rebel Walker：保留哪些攻击、导弹的组别与数值、追踪做法（第 6.1 节）、是否作玩家单位。
3. 大门：作玩家单位、敌方中首领或两者；放出的单位、间隔、生命与自身攻击（第 6.2 节）。
4. 挪威海怪：触手素材来源与做法（第 6.3 节）、第一阶段本体是否受伤、数值、是否作玩家单位。
5. 区域名、里地图位置、配乐。

## 10. 文件（`verification/ms7_m7_20261103/`）

| 文件 | 内容 |
| --- | --- |
| `layers.py` → `overview/layers.txt`、`m7_boxes.png` | 背景素材表图层外接框 |
| `crops.py` → `overview/sec1/2/3.png`、`boss.png`、`boss_pieces.png`、`examples.png`；`overview/sec1_track.png`、`sec2_gate_end.png`、`boss_tentacle_states.png`、`unused_section.png` | 分段预览 |
| `overview/rw_turn_rl.png`、`rw_wreck_rl.png`、`rw_debris_missile.png`；`rw_match.py` → `overview/rw_match.txt` | Rebel Walker 素材表分段与原生图集比较 |
| `run_shifted.py`、`ui_harness.py`、`ui_common.py`、`dump_units.py`、`native_info.py`（复制自 `ms7_m4_units_20261031`）→ `runs/rw_*`、`runs/ni228_*` | 原生 228 / 194 的描述符、数值与名称 |
| `native_atlas.py` → `overview/native_228_atlas.png`、`native_228_atlas_rects.png` | 原生 228 图集 |
| `msa_m7_names.py`、`msa_m7_stats.py`、`msa_m7_summary.py`、`msa_m7_classes.py` → `overview/msa_m7_*.json/txt` | MSA 名称、数值、动作类 |
| `msa_0309/`、`msa_0564/`、`msa_1289/`、`overview/msa_0309_slots.png`、`msa_0564_slots.png`、`msa_1289_slots.png`、`msa_key_slots.png` | MSA 动作槽预览 |
| `msa_bg_export.py` → `msa/record.json`、`msa/script_dump.txt`；`msa/ms7_7st_*.png` | MSA bg 158 |
| `decode_shot.py`、`ref/shots/A_*.jpg` | 录像 A 截帧拼图 |
| `handoff/` | 尺寸参考与据点标记图样 |
