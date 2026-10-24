# 扩展世界与社区敌军接口

核验日期：2026-10-04。接口版本：1。运行入口为项目根目录的 `event_trial_launcher.py`。世界目录为 `campaign_content/catalog.json`，社区单位目录为 `community_content/content.json`（内容索引）与 `community_content/units/`（逐单位文件，2026-10-10 M1a 起；此前为单一 `registry.json`，见 `docs/modding/M1A_REGISTRY_SPLIT_2026-10-10.md`）。示例配置保存在 `campaign_content/catalog.example.json`；默认目录保留空世界列表。

## 1. 使用流程

在游戏目录执行以下 PowerShell 命令：

```powershell
.\windows_runtime\python.exe content_tool.py install-example
.\windows_runtime\python.exe content_tool.py validate
```

示例登记世界 4、里世界 4及六款现有社区单位，复用原版场景与音乐。2026-10-04 根据用户要求，尚未完成的扩展入口及选择面板暂时隐藏，`F6` 暂不打开该界面。世界、区域、关卡、敌军、场景、音乐及独立进度接口保留，安装示例不会自动启用界面。独立开发预览可显式构造 `CommunityCampaign(p, trial, ui_enabled=True)`；正式启动入口采用默认停用状态。预览面板每页十项，战斗期间禁止打开。

`install-example` 仅适用于当前未登记世界的目录。已有内容通过编辑 JSON 追加。资源和目录修改在下一次正常启动时加载。

## 2. 世界、关卡及稳定内容键

目录格式为 schema 1，包含 `assets`、`scenes`、`music`、`worlds`。`worlds` 下依次登记 `areas` 和 `stages`。世界名称与数量由配置定义，可追加世界 5、里世界 5、世界 6及后续区域。原生固定世界进度数组保持其既有容量；扩展世界使用独立适配器和进度文件。

世界、区域、关卡、场景、音乐均使用 `key`。键长 1–120 字符，允许 ASCII 字母、数字、下划线、点与连字符，并要求目录内及社区单位键之间唯一。建议使用作者前缀，例如 `author.world5.area2.stage8`。修改展示标题或调整关卡顺序可以保留原有键；已发布内容的键应保持稳定。

最小关卡示例：

```json
{
  "schema": 1,
  "assets": {},
  "scenes": [],
  "music": [],
  "worlds": [{
    "key": "author.world5", "title": "世界 5",
    "areas": [{
      "key": "author.world5.area1", "title": "区域 1",
      "stages": [{
        "key": "author.world5.area1.stage1", "title": "关卡 1",
        "template": 1011, "scene": 0, "music": 100,
        "stamina": 0, "enemy_base_hp": 20000, "reward_msp": 100,
        "strength_steps": 0, "enemy_specials": true,
        "enemies": [
          {"unit": "s1xlv.m15a_future", "level": 40},
          {"unit": 3, "level": 40}
        ],
        "waves": [{"tick": 0, "enemy": 0}, {"tick": 90, "enemy": 1}],
        "reward_units": ["s1xlv.di_cokka_mk2"]
      }]
    }]
  }]
}
```

| 字段 | 语义及当前边界 |
| --- | --- |
| `template` | 原生 Mission 模板，默认 1011；模板须存在，保留其评级阈值等基础规则。当前适配执行基地摧毁型关卡。 |
| `scene` | 原版场景整数 ID 0–137，或独立场景稳定键。 |
| `music` | 原版 SoundID 1–1030，或独立音乐稳定键，默认 100。 |
| `stamina` | 消耗体力，0–1000，默认 0；不足时禁止入场。 |
| `enemy_base_hp` | 敌军基地基础 HP，1–100000000，默认 10000。 |
| `reward_msp` | 关卡 MSP 奖励，0–999999，默认 0；实际收益沿用原生战斗计算。 |
| `strength_steps` | 敌军关卡强化参数，0–100，默认 0；生命值与伤害使用 `1 + 0.2 × 参数` 倍率。 |
| `enemy_specials` | 原生敌军绝招决策开关，默认 `true`；冷却、动作状态和攻击距离继续由原生单位处理。 |
| `enemies` | 1–32 条名单；`unit` 使用原版整数 ID 1–399 或社区单位稳定键。 |
| `level` | 敌军配置等级，1–200，默认 40；当前基础参数插值在显示等级 40 达到最终锚点。 |
| `waves` | 明确的出击时序；`enemy` 为名单的从零开始索引。`tick` 严格递增，0–32766；每关最多 8192 条。 |
| `loop` | 可选，1–32766：出兵计时到该帧时回到 0（原版活动为 1080 帧，即 36 秒循环）；缺省不循环，出兵表执行一遍后不再出兵。2026-10-19 起。 |
| `triggers` | 可选，出兵触发，与自制 EVENT 相同：`when` 为 `time`（计时等于 `value`）、`base_hp`（敌方据点生命低于 `value`%）或 `front`（我方最前单位与敌方据点距离小于 `value`）；动作为 `spawn`（名单序号，出兵一次）、`jump`（把出兵计时设为该帧，可跳入 `loop` 之后只由触发进入的出兵段）或 `strength`（追加关卡强化级数）；`repeat` 缺省为每场一次。连同 `loop` 至多 32 条。2026-10-19 起。 |
| `placed` | 可选，开战时已在战场上的敌方单位 `{"enemy": 名单序号, "x": 场景横坐标}`，至多 32 个。2026-10-19 起。 |
| `difficulty`、`rank_times` | 可选，难度标签 0–5 与评级时间 `[S, A, B, C, D]`（秒，逐项递增），与自制 EVENT 相同；缺省沿用模板关卡。2026-10-19 起。 |
| `ura_page`、`ura_background`（世界） | 可选：写 `ura_page`（4–6，自 4 起连续）时，该世界显示在原生里地图的第 4 页起（里世界 4 为原生世界号 12，关卡编号按原生规则 (世界号+1)×1000 + (区域+1)×10 + 关卡+1），不出现在扩展世界选择界面；`ura_background` 为 571×320 的 PNG / WebP 网格背景（左右两块各约 285 宽，同原生里地图背景），翻页时的交叉淡入与亮度起伏由原生绘制。需要核心 r69 起。2026-10-19 起。 |
| `map_position`、`native_name` 或 `name`（区域）；`map_position`、`thumbnail`（关卡） | 里地图扩展页使用：区域的地图坐标 `[x, y]`（0–1440、0–709）与区域名称——`native_name` 为原生区域名称编号（0–56，各语言文字取自原版，例如 31 为「中非」），或写 `name` 自定义名称（11 种语言 `EN`、`JP`、`KR`、`ES`、`PT`、`FR`、`DE`、`IT`、`ZS`、`ZT`、`RU` 各一项，每项 1–64 字节；宿主追加到原生名称表之后，2026-10-21 起，例如里世界 4「泰国」），两者写且只写一个；每区域 1–6 关，关卡坐标 `[dx, dy]` 为相对区域坐标（−200…200、−80…80；进入区域后画面坐标约为 640 + 3.375·dx、342 + 3.375·dy，里地图右上为计时框、左上为区域名称条），`thumbnail` 为 128×56 略缩图。扩展页的区域按原版里世界整体开放、不设人质，`requires` 与 `reward_units` 写了即拒绝；进度按关卡与区域稳定键保存于 `campaign_progress.json`（字段 `seen`、`wins`、`best_time`，区域在 `areas`）。2026-10-19 起。 |
| `requires` | 世界、区域或关卡的前置通关键列表；相关上级条件同时生效，目录校验拒绝循环依赖。 |
| `reward_units` | 首次胜利解锁单位的列表；已拥有单位保留既有等级，奖励采用正常进度保存流程。 |

当前目录校验上限为 100000 条关卡，扩展场景总容量为 4096。实际战斗按所选世界建立 Mission 表。已验证一万条关卡目录和长链解锁条件；十万条实际运行及大量场景的内存、性能表现仍需专项测量。世界、区域与关卡容量分别评估，原版“五项 Mission 扩展”入口继续保留其历史接口范围。

## 3. 当前与后续社区单位作为敌军

已注册单位的敌军身份由运行注册表解析。新增社区单位沿用 schema 2 的素材、动画、参数、名称、图标和稳定键约定，在关卡中填入其 `key` 即可。敌军名单与出击路径支持当前 1024–1029 及后续登记 ID；接口验证还使用了隔离登记的第七款单位 1030。

社区单位容量（2026-10-10 M1 起）：本体 ID 1024–2047（`content.json` 的 `unit_ids`，只追加、不重排）、模组 2048–5119；ID 可以不连续，空位由加载器以未启用占位记录填充。单位文件不写 `id` 与 `icon.index`。`content.json` 可选 `disabled_units`（本体稳定键列表）暂不载入对应本体单位：UnitID 保留、单位文件不读取，社区进度中的拥有与等级保留，编队格按稳定键暂存，移出列表后恢复（2026-10-13 起用于暂时停用 PVZ 巨人与小鬼）。图标写 `"page": 1`（`unit_icon_02.obm`）或 `"atlas": "<图集>.obm"`（`rect` 为图集中的矩形，`anchor` 取负值即矩形左上角在 50×50 选单位格中的位置，格的内框为 (5,5)–(45,45)：40×40、锚点 [-5,-5] 恰好填满内框；原生透明底剪影头像多为 46 高、锚点 [-5,1]，向上越出内框 6 像素，2026-10-21 记）（图标页，页号由加载器分配，见 `docs/modding/M1B_ICON_PAGES_AND_SCALE_2026-10-10.md`）。缺失登记的 ID 继续由原生边界处理。特殊行为（修筑、召唤、投放、喷火、保留武器等）在单位文件中以 `behaviors` 组合，可用行为与参数见 `docs/modding/BEHAVIOR_CATALOG.md`（`content_tool.py list-behaviors`）。`status_word_values`（直接写入数据行的状态词）的值可为一个整数（六个等级锚点相同）或六个整数的列表（Lv1、Lv10、Lv20、Lv30、Lv40、Lv50 锚点，2026-10-15 起）。可选 `upgrade_cost_base`（1–100000，2026-10-17 起）写入数据行 +0x354：单次强化 MSP = 该值 ×（3L+5），L 为内部等级（界面等级 −1），原生 AI 也以此值计单位战力；未写时沿用 `base_id` 单位的值。可选 `attack_attributes`（`{"melee"|"normal"|"special": 0–4}`，近距组 `melee` 2026-10-18 起）写入数据行的攻击属性（近距词 21、普攻词 28、绝招词 37）：1 为火焰、2 为爆炸，决定被击杀单位的死亡状态（120 / 110）。可选 `minimap_marker`（`[宽, 高]`，各 1–64，2026-10-20 起）写入数据行 +0x34c / +0x350（BattleUnitStatus 字 45 / 46），为战斗顶部小地图的标记大小：原版大多数单位为 4×4，大型单位为 10×10 至 20×20（例如 BULL DRILL 20×20、IRON NOKANA 16×12）；未写时沿用 `base_id` 单位的值。大型单位按图像尺寸换算（宽约 1/25、高约 1/21.5，与原版大型单位相同），例如 IRON CAB 16×20、巨型 Hunter Walker 10×13。可选 `image_direction`（90 或 270，2026-10-21 起）为图像表中的原画朝向（90 朝右、270 朝左），原生按此决定是否镜像；未写时沿用 `base_id` 单位的值。可选 `near_damage_multiplier`（`[分子, 分母]`，2026-10-21 起）为近距伤害（词 15）六个等级锚点的追加倍率（向下取整），与 `special_damage_multiplier` 相同，之后再经 `damage_multiplier`。可选 `normal_damage_multiplier`（`[分子, 分母]`，2026-10-22 起）为远距伤害（词 22）六个等级锚点的追加倍率，规则同 `near_damage_multiplier`；三组伤害都须为指定值时，可令 `damage_multiplier` 为 [1, 1]，以三个追加倍率分别设定。可选 `status_float_values`（`{"词": 数值}`，2026-10-21 起）为浮点状态词的绝对值，限第二参数 16 / 23 / 30 与弹速 18 / 25 / 32，写入六个等级锚点；整数状态词仍写在 `status_word_values`。可选 `special_effect_size`（`[宽, 高]`，各 0–1000，2026-10-21 起）写入数据行 +0x344 / +0x348（BattleUnitStatus 字 43 / 44），为绝招可发动时单位脚下蓝光的大小：原生 `BattleUnit::draw` 以两倍值为宽高、以单位脚点为中心绘制，为 0 时取当前帧第一个矩形的尺寸；原版大型载具多为 [160, 90]（蓝光约与本体等宽，高约为本体的 0.4–0.5）。主槽不画帧、部件全部为子层的单位须写此项，否则蓝光按空帧画成脚点处的小光点（例如 IRON SENTINEL [380, 120]）；未写时沿用 `base_id` 单位的值。动作脚本 op12（生成独立效果）的第一个值可写原版共用效果编号 0xff00 + n（共用效果 UnitID 402 的动画 n，2026-10-20 起）：例如 0xff02 小爆炸、0xff03 中爆炸、0xff04 基寇卡损毁的爆炸、0xff17 大型单位的爆炸（白闪后火球与黑烟）、0xff11 据点被毁的火柱，不占本单位图集。模组的目录结构、清单与启用方式见 `mods/README.md` 与 `docs/modding/M3_MOD_LOADER_2026-10-10.md`，发布前可运行 `content_tool.py check-mods`。单位注册与关卡登记属于两个步骤，关卡目录不会自动生成单位素材或独立行动类。完整单位素材约定见开发目录的 `CONTENT_EXTENSION_CONTRACT.txt` 与既有社区注册表。

修筑类单位（工兵，原生动作类 `BattleAction_Kouhei`）的生命方式（2026-10-20 起，核心 r71）：`content.json` 的 `engineer_hp` 为缺省方式，`{"mode": "hp", "percent": 5, "minimum": 300, "units": {}}` 表示工兵生命 = max(300, 修筑对象同等级生命 × 5%)，受击后生命仍大于 0 时继续行进或修筑，耗尽时按原生撤退；`"mode": "hit_and_run"` 为原生的一击即跑（生命 1、受击即撤退）。原版工兵在 `units` 中按 UnitID 单独设定（例如 `"5": {"mode": "hit_and_run"}`），本体与模组单位在单位文件写同格式的 `engineer_hp`（不含 `units`）；单独设定可只写 `percent`（1–100）或 `minimum`（1–1000000），方式沿用缺省。只适用于动作类为 `BattleAction_Kouhei` 的单位（原版 24 个，社区单位按 `base_id`），迫击炮兵类不适用；未写 `engineer_hp` 的内容目录保持原生。详见 `docs/ENGINEER_HP_2026-10-20.md`。

### 原版单位外观替换（stock_sprites）

`content.json` 可写 `"stock_sprites": {"原版 UnitID": "替换文件.json"}`，替换原版单位的动作外观（数据行、动作类与其他单位不变）。替换文件含 `textures`（原版图集名或已在 `assets` 登记的本体图集）、`sprite_descriptor`（以原版描述符为底本：原版矩形与帧原样在前，新增的矩形与帧追加在后，受击框与攻击框取原版）与 `animations`（改写的脚本，其余脚本沿用原版）。改写脚本时，攻击框、发射、音效、弹起等指令须保持原版所在的 tick 与脚本总长。现有用途为 Walter（385）与 Tyra（381）的补帧（`walter_rian_*`、`tyra_elson_*`，生成脚本 `artwork/msadv_frames_20261024/build_stock_sprites.py`）。

## 4. 新场景、OBM 与 PNG

新增场景可使用独立 OBM 图集。PNG 输入通过统一导入工具转换为原生 OBM：

```powershell
.\windows_runtime\python.exe content_tool.py import-png .\art\author_desert.png .\campaign_content\author_desert.obm
```

工具输出文件名、BLAKE2b-256 摘要（`blake2b`，2026-10-10 M5 起；此前为 SHA-256）、原始尺寸与运行画布尺寸。将摘要登记到目录的 `assets`（也可登记 `null` 跳过核对），再登记场景：

```json
{
  "key": "author.desert", "base_id": 0,
  "texture": "author_desert.obm",
  "bounds": [0, 700],
  "terrain": [[0, 338], [1400, 338]],
  "bases": [68, 653],
  "graphics": {
    "rects": [[0, 0, 384, 240, 0, 0, 0, 0]],
    "back": [[0]], "front": []
  }
}
```

`bounds` 沿用原生场景的半宽坐标，实际战场宽度为 `2 × (right - left)`。`terrain` 为覆盖整个实际宽度的 `[x,y]` 折线，x 严格递增；y 使用原生地形坐标。`bases` 沿用 SceneInfo 的半宽基地坐标。地形或基地配置需要同时声明边界。

`graphics.rects` 每条包含八个 int16 字段：图集 x、图集 y、宽、高、锚点 x、锚点 y、翻转字段、保留字段。`back`、`front` 是背景与前景图层列表，每层列出对应图块的动画帧索引。当前支持最多 4096 个图块、每组 64 层、每层 1024 帧。独立图块布局使用通用场景构造器 `base_id: 0`；复用既有布局时可以省略 `graphics` 并指定相应原生 `base_id`。

图块锚点使用原生偏移语义。通用背景构造器的基础绘制纵坐标为 `32 × 原生缩放`；锚点 0 可直接绘制背景。地面纹理可登记为额外图块或前景层，实际行走高度由 `terrain` 决定。该接口支持原生图块层和动画；独立相机、视差速度及新增目标规则仍需对应适配。

PNG 导入要求单帧、通道位深不超过 8 位的 RGB/RGBA、灰度或调色板格式，尺寸不超过 8192×8192。运行格式为 RGBA 调色板和 8 位索引，索引 0 保留透明黑色，调色板总容量 256。超过颜色容量时工具明确拒绝导入，像素颜色调整由作者显式完成。

当前 GLES 场景采样要求二的整数次幂画布。工具补充透明边缘并保持原始图像、像素坐标与 RGBA 数值，执行解码往返检查；已有 OBM 也需符合运行画布约束。隔离验证同时检查了原生显示和 GPU 纹理像素。图块宽高使用原始素材范围，避免将透明边缘计入可见图块。

**图像源场景与 2 倍素材（2026-10-19 起，核心 r68 起）：**

- `texture` 也可填写登记过的无损 PNG / WebP（本体登记在 `assets`，模组放在 `assets/`）。启动时只读取尺寸与摘要；原生打开图集时宿主才把它解码为 32 位直接 RGBA 的 OBM（补透明边缘到二的整数次幂），颜色数与半透明不受 256 色调色板限制，仓库中只保存压缩后的源文件。原生载入时使用的文件名为“源文件名 + `.obm`”。
- 场景可写 `"resolution": 2`，表示图集按 2 倍精灵比例制作（例如《合金弹头6》的背景）：绘制时 1 个图集像素对应 1 个逻辑单位，可见高度为 448 像素，矩形锚点按 2 倍像素填写。缺省 `1` 为原版比例（1 个图集像素对应 2 个逻辑单位，可见高度 224 像素）。`bounds`、`terrain`、`bases` 始终使用逻辑单位，与 `resolution` 无关。需要核心导出 `msd_community_stage_scale_version()==1`。
- 场景可写 `water`（水面上的水花，2026-10-22 起）：`{"range": [左, 右], "min_y": 起水高度, "draw_y": 水花画线, "color": [r, g, b], "strength": 1–255}`，坐标为逻辑单位。原生水面场景（如表世界 1-3）的做法：地面单位的 x 在范围内且 y 不小于起水高度时，在其脚下画共用效果 402 的水花（宽单位画多处），纵向固定在画线；水花按 `color` 染色（`strength` 缺省 230，越大越接近该颜色）。水面本身的动态效果用场景图层的多帧动画（`graphics` 中一层多帧）制作。
- 场景可写 `bullet_walls`（子弹墙，2026-10-22 起）：至多 16 个多边形，每个 3–32 个 `[x, y]`（逻辑单位）。子弹从墙外进入多边形时按原生落地处理（弹体的 hitGround：播放命中或爆炸动画后移除），从墙内发出的子弹不拦截。墙不改地形，地面、空降、飞行与产兵单位的移动不受影响。
- `water` 与 `bullet_walls` 需要 `bounds`，并需要核心导出 `msd_community_scene_fx_version()==1`（核心 r76 起）。
- 自制地形在安装时补上原版同样的终止点 `[9999, 末点 y]`。

**地形与单位位置（2026-10-20 起，核心 r70 起；以后的地图编辑器与关卡制作同样遵守）：**

原生只有部分单位动作类在移动时按 `terrain` 改写单位高度（`BattleCommonActions::actionMove`）：下一步地形比单位当前高度高出 40 以上视为高台，清除移动；低于 40 以上视为悬空而下落。由此在原版没有、自制战场坡道较陡时出现的问题，核心在自制场景（ID ≥ 138）中统一处理，原版场景保持原路径：

- 击退等滑行：受击击退（状态 80）等由动画脚本推动的横向滑行中，原生不改写高度，单位在坡道上只横向位移；向上坡被推开后低于地形，超过 40 即永远走不动。贴地的单位（与所在 x 的地形相差不超过 2、未在下落）本帧只有横向位移时，高度改为新 x 处的地形。
- 据点出兵：原生把新单位放在据点前缘、高度取据点的高度。据点在地面时改为出兵点的地形高度。
- 正规军运兵车（UnitID 396，`BattleAction_TruckSlug`）放兵：原生放在车前“车宽 + 45”处、高度取车的高度。车在坡道上时步兵可能落在地形之下 40 以上而停住；改为放兵点的地形高度。其他放兵单位的动作类自行处理。

制作地形时：

- 双方据点前后的出兵区保持平坦（已制作的关卡为据点外侧到据点前约 220 逻辑单位）。
- 同一段折线的坡度不宜使单步（单位每帧移动约 1–8）升降超过 40；需要坑或台阶时两侧留缓坡（见 `docs/ms6/MS6_STAGE_PORT_PLAN_2026-10-19.md` 8.1.3 节）。
- 行走线按画面中的地面绘制后，在战斗中采样单位位置（y 与 `getAltitude` 之差）并在坡道上检查击退与放兵。检查脚本见 `verification/ura_world4_20261019/spawn_fix/`（`run_natural.py` 自然对战、`run_knock.py` 击退、`run_truck.py` 运兵车放兵、`run_spawn.py` 出兵点）。

新增资源要求独立文件名，避免与原生资源或社区资源产生冲突。单文件上限 64 MiB，目录资源合计上限 512 MiB；登记值须匹配文件 BLAKE2b-256 摘要（按“大小+修改时间”缓存，见 `content_digest.py`）。PNG、PSD 源稿及其坐标保留在作者素材目录。

## 5. 独立关卡音乐

输入采用 Ogg Vorbis，工具完成原生解码检查后生成 `.msdf` 文件：

```powershell
.\windows_runtime\python.exe content_tool.py import-music .\audio\author_desert.ogg .\campaign_content\author_desert.msdf
```

将输出的 `blake2b` 摘要登记至 `assets`，在 `music` 中登记：

```json
{"key": "author.desert_bgm", "file": "author_desert.msdf", "base_sound_id": 100}
```

关卡的 `music` 填入 `author.desert_bgm`。`base_sound_id` 复用原生音乐描述符的类型参数；可选 `loop_start`、`loop_end` 沿用原生循环时间字段，默认零。独立音乐复用已核验的空闲 SoundID 1031，并在切换时停止播放、释放引用及清除缓存指针；胜负音乐继续采用既有结算流程。已验证两个独立曲目的顺序加载与 PCM 输出。

本轮音效与音乐的独立关闭功能按用户要求暂缓。设置界面和 F9 总静音继续保留现行行为；后续恢复该功能时需要采用原版按钮样式。

## 6. 模组提供的世界与关卡（M5）

模组在 `mod.json` 的 `content` 中写 `"campaign": "campaign/"`，该目录下每个 `*.json` 为一个目录片段，可含 `scenes`、`music`、`worlds` 三个列表，格式与本节以上相同，**不写 `assets`**：场景图集与音乐文件放在模组 `assets/`（文件名以 `<模组 id>_` 开头），按文件名引用。规则：

- 模组定义的世界、区域、关卡、场景、音乐的键须以 `<模组 id>.` 开头。
- 引用只能指向本体、本模组与所依赖模组（`depends`）的内容：场景、音乐、关卡解锁条件、敌军与奖励单位；原版场景、音乐与单位以整数引用。本体目录不能引用模组内容。
- 本体目录与已载入模组按加载顺序合并后整体校验（键唯一、容量、解锁循环）。某个模组的关卡校验失败时，该模组整体跳过（含其单位），原因显示在 MOD 页，本体与其他模组不受影响。
- 进度按关卡稳定键保存于 `campaign_progress.json`；停用模组后其关卡进度与奖励单位进度保留，重新启用后恢复。
- 发布前可运行 `content_tool.py check-mods`，或 `content_tool.py validate --enable <模组 id ...>` 查看合并后的世界与关卡数量。

扩展世界选择界面仍按用户要求暂缓显示（待世界 4 / 里世界 4 规划完成）；目录、战斗、结算与进度接口对本体与模组均已可用。详见 `docs/modding/M5_CAMPAIGN_CONTENT_2026-10-10.md`。

## 7. 自定义音效（M6）

本体与模组可登记自己的音效文件，并以稳定键引用：

```json
{"key": "author_mod.cannon", "file": "author_mod_cannon.msdf", "type": "se", "volume": 100}
{"key": "author_mod.theme", "file": "author_mod_theme.msdf", "type": "bgm", "loop": [1.5, 40.0]}
```

- 文件为 `.msdf`（Ogg Vorbis 数据），可用 `content_tool.py import-music <输入.ogg> <输出.msdf>` 生成并做解码检查；不得与原版资源同名。
- `type` 为 `se`（缺省）、`vo`、`bgm`；`volume` 1–127（缺省 100）；`loop` 仅用于 `bgm`；`gain` 0.1–8（缺省 1，核心 r53 起）在解码后放大或减小采样，超过满幅 60% 的部分柔和压缩，用于素材本身偏小声的情形。
- 本体写在 `community_content/content.json` 的 `sounds` 列表（键 `s1xlv.`，文件放在 `community_content/`）；模组写在 `content.sounds` 目录的 `*.json` 列表中（键 `<模组 id>.`，文件放在模组 `assets/`）。
- 单位动作脚本播放音效：`{"opcode": 23, "values": ["author_mod.cannon"]}`；关卡音乐：`"music": "author_mod.theme"`（类型须为 `bgm`）。只能引用本体、本模组与所依赖模组的音效。
- SoundID 由游戏在原生音效表的空闲区段（32–99、165–199、523–799）中按加载顺序分配，本体与模组合计 380 个；使合计超限的模组被跳过。详见 `docs/modding/M6A_CUSTOM_SOUNDS_2026-10-10.md`。
- 音频文件为 Ogg Vorbis，采样率与声道数不限：原生混音只输出 16 kHz 立体声，其他格式在载入时转换（核心 r52 起）。

## 8. 自制 EVENT（M6b）

本体 EVENT 放在 `community_content/events/*.json`（键 `s1xlv.`），模组在 `content.events` 目录（键 `<模组 id>.`），每个文件一个 EVENT：名称、细则、作者、日期、可选 360×240 左屏图，以及 1–16 个区域（地图坐标与区域名）、每区域 1–5 个小关（标记偏移、预览帧与扩展世界关卡相同的战斗字段）。EVENT 出现在 EVENT 浏览页（按日期并入循环），经女教官基地进入原生活动地图；进度按关卡稳定键保存。目前支持 `clear_reward`（通关与首胜奖励）及人质类 `rescue`、`collaboration_rescue`、`parts`、`invitation`（小关 `prisoners`、区域 `reward`、`final_reward_units`，见 `docs/modding/M6B3_RESCUE_EVENTS_2026-10-10.md`），以及积分与商店类 `legacy_survival`、`current_cooperation`（代币兑换店 `shop`、活动勋章商店 `medal_shop`、分期 `part1`，见 `docs/modding/M6B4_POINTS_SHOP_EVENTS_2026-10-10.md`）。可选自制地图：`"map": {"image": ...}`（1440×709，替换活动地图的世界地图图层，区域 `position` 即该图上的像素坐标）与小关 `"thumbnail"`（128×56）。格式与示例见 `docs/modding/M6B1_CUSTOM_EVENTS_2026-10-10.md`、`docs/modding/M6B2_CUSTOM_EVENT_MAPS_2026-10-10.md`。

出兵控制（2026-10-15，与历史活动关卡记录相同的原生字段）：小关可写 `"loop"`（出兵表计时到该帧时回到 0，历史活动为 1080 帧即 36 秒）；`"triggers"`（`when` 为 `time` 计时等于、`base_hp` 敌方据点生命低于百分比、`front` 我方最前单位与敌方据点距离小于；动作为 `spawn` 出兵、`jump` 设定出兵计时或 `strength` 追加关卡强化级数；`repeat` 缺省为每场一次；连同 loop 至多 32 条）；`"placed"`（开战时已在战场上的敌方单位，`x` 为战场横坐标）；`"items"`、`"item_level"`、`"prisoner_chance"`（道具与俘虏的放置表：每场随机取约 67% 的位置，俘虏与道具藏在战场中，攻击打中后现身；人质类玩法的俘虏只经此表出现，自制 EVENT 的俘虏为常规关卡的俘虏，需核心 r60 起）。说明见 `event_content.py` 文首与 `docs/pvz/PVZ_EVENT_PART1_2026-10-15.md`。

地图与俘虏页（2026-10-15）：区域图标显示区域序号 1、2、3…（不再使用万圣节模板的“!”图标）；EVENT 可写 `"map_music"`（活动地图与俘虏页的 BGM，原生 SoundID 或 bgm 音效键；原版最新 EVENT 的地图 BGM 为 156，缺省时经典路由为 103）；人质类区域奖励可用 `"portrait_image"`（PNG/WebP，不超过 400×500，俘虏页立绘以图像底边中点对齐原生立绘的脚底位置）代替原生立绘编号 `portrait`，两者择一。

评级时间（2026-10-18）：小关可写 `"rank_times": [S, A, B, C, D]`（秒，1–3600，逐项递增），写入原生关卡记录词 11–15。原生结算（`BattleScene::battleFinish`）与地图评级（`GetStageRank`）以通关用时的整秒数依次比较 S、A、B、C，不超过即为该级，超过 C 为 D；D 值只记录在词 15（与原版数据相同），评级不读取。评级另给关卡奖励 MSP 的额外奖励：S 50%、A 30%、B 20%、C 10%、D 无。缺省沿用模板关卡（1011 为 18/35/55/85/86）。

语言规则（单位、组合包、EVENT 共用）：只写一种语言时全部语言使用该文本；部分翻译时未填写的语言使用英语，未写英语时使用第一种。

## 9. 进度、奖励与验证范围

每个存档目录新增 `campaign_progress.json`，按稳定关卡键记录挑战次数、胜利次数、捕虏数量、评级、最佳用时及首次单位奖励状态。原生 MSP、社区单位进度和扩展关卡进度使用 `campaign_transaction.json` 协调保存；写入失败恢复文件与内存，启动时恢复未完成事务。评级使用模板的原生时间阈值，捕虏数量来自实际战斗结果。独立捕虏编排、捕虏集齐奖励和复杂关卡目标需后续扩展配置。

当前验证覆盖六款敌军的实际波次出击、受控冷却与距离下的原生绝招决策、后续单位登记、独立场景与音乐、受控胜负结算、奖励重启、故障回滚和原生菜单返回。全新增关卡的自然通关、长期运行与不同硬件表现保留待核验状态。证据摘要见 `CONTENT_INTERFACE_VALIDATION.json`。
