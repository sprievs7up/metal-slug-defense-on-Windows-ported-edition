# 模组 M6a：自定义音效（2026-10-10，核心 r41）

M6 在任务书中包含自定义音效与自制 EVENT 两部分。本文件记录第一部分（自定义音效）；自制 EVENT 为 M6b，尚未实施。

## 1. 结果

- 本体与模组可按稳定键登记自己的音效文件（SE、VO、BGM），加载器分配 SoundID 并写入原生音效记录。
- 单位动作脚本 op23（播放音效）的参数可直接写音效键；关卡（扩展世界目录）的 `music` 可写类型为 `bgm` 的音效键。
- 可见范围与单位、关卡引用相同：本体、本模组与所依赖模组。未登记或不可见的键使该模组整体跳过。
- 核心 `MSD_Core_LAB_r41_20261010.dll`：GetSoundData 钩子按社区头部 +152 的指针表返回登记的记录，导出 `msd_community_sound_version()==1`。无音效时头部 +152/+156 为 0，钩子不生效。

## 2. SoundID 分配

原生音效表（`AppMain::GetSoundData`，24 字节记录线性表，以 SoundID 1033 结束）共 651 条，SoundID 0–1030。原生按 SoundID 定址的缓存与引用计数数组（`app+0x9b30` 指针、`app+0xab54` 字节）只有 0–1031 共 1032 项，生成代码中约 54 处直接按此定址；超过 1031 的 ID 需要逐处适配，本次未采用。

本次在 0–1031 内取原生表中不存在的区段：**32–99、165–199、523–799，共 380 个**（1031 仍是扩展世界的关卡音乐槽）。核查（`verification/m6_20261010/sound_refs.json`）：

- 全部 423 个原版精灵描述符脚本中的 op23 共引用 524 个 SoundID，均不在这三个区段；
- 生成代码中调用 22 个音效函数前以常量写入的 SoundID 共 64 个，均不在这三个区段；
- 以运算得到的 SoundID 未逐项追踪（属剩余风险）；原生请求表中不存在的 SoundID 时 GetSoundData 返回 0 而无声，分配后该请求会播放自定义音效。

分配按登记顺序（本体在前，模组按加载顺序）从 32 起依次进行，每次启动重新分配；SoundID 不写入存档，单位脚本在安装时换算。超过 380 个时：本体超限为启动错误；模组按加载顺序累计，使合计超限的模组被跳过（原因记录在 MOD 页）。

## 3. 数据格式

音效条目：

```json
{"key": "author_mod.cannon", "file": "author_mod_cannon.msdf", "type": "se", "volume": 100}
{"key": "author_mod.theme", "file": "author_mod_theme.msdf", "type": "bgm", "loop": [1.5, 40.0]}
```

| 字段 | 说明 |
| --- | --- |
| `key` | 本体为 `s1xlv.<名称>`，模组为 `<模组 id>.<名称>`。 |
| `file` | `.msdf` 文件名（Ogg Vorbis 数据，以 `OggS` 开头，与原版音频文件相同）；可用 `content_tool.py import-music` 由 `.ogg` 生成并做解码检查。不得与原版资源同名。 |
| `type` | `se`（缺省）、`vo`、`bgm`；原生记录的类型字与模板分别取原版 SoundID 201、7、100 的记录。 |
| `volume` | 1–127，缺省 100；写入原生记录的音量字（值 ×256，原版多数为 100×256）。 |
| `loop` | 仅 `bgm`：`[开始秒, 结束秒]`，原生循环时间字段；缺省不循环点（0, 0）。 |

- 本体：`community_content/content.json` 的 `"sounds": [...]`，文件放在 `community_content/`。目前本体未登记音效。
- 模组：`mod.json` 的 `"content": {"sounds": "sounds/"}`，该目录下每个 `*.json` 为条目列表；文件放在模组 `assets/`（以 `<模组 id>_` 开头）。

引用：

```json
{"opcode": 23, "values": ["author_mod.cannon"]}
```

关卡：`"music": "author_mod.theme"`（类型须为 `bgm`）。世界目录原有的 `music` 条目（扩展音乐槽 1031）保持可用。

## 4. 修改文件

| 文件 | 内容 |
| --- | --- |
| `content_sounds.py`（新增，含 `src/` 镜像） | 条目校验、模组音效读取、单位引用检查、分配、动作脚本换算、原生记录与指针表写入。 |
| `community_content.py` | `check_unit` 允许 op23 首参数为字符串；`load_sounds`（本体与模组音效、与原版资源同名检查、单位引用可见范围）；安装时换算脚本，头部 +152/+156；按文件名提供音效文件；核心能力检查。 |
| `mod_loader.py` | `content.sounds`；模组单位的音效引用按依赖可见范围检查；关卡校验时传入可见音效；`load(..., sounds=, body_sounds=)`；状态增加 `sounds` 计数。 |
| `campaign_catalog.py` | `Catalog(..., sounds=)`：关卡 `music` 可写 bgm 音效键（类型与可见范围检查）。 |
| `community_campaign.py` | 音效键作为关卡音乐时使用分配的 SoundID（不占用扩展音乐槽 1031）；LAB 打开期间拒绝打开与开始扩展世界。 |
| `lab_prep.py` | 准备界面的 BGM 135 保持只在主菜单场景 27/28 生效。 |
| `mod_page.py` | 详情显示音效数。 |
| `content_tool.py` | `check-mods`、`validate` 识别本体与模组音效。 |
| `src/community_content.cpp` | GetSoundData 钩子查表；`msd_community_sound_version`。 |
| `tests/test_content_interfaces.py` | 新增 `test_stage_music_sound_key`。 |
| `mods/README.md`、`docs/CONTENT_AUTHORING.md` | 作者说明。 |

## 5. 验证（`verification/m6_20261010/`，隔离存档，核心 r41，未计算 SHA-256）

测试模组（`make_mods.py`）：`soundmod`（三个音效：SE、SE、BGM；KT-21 副本单位的开炮与突进改用自定义音效；一个以 bgm 音效键为音乐的关卡）、依赖它的 `sound_addon`（单位引用 `soundmod.cannon`）及 11 个失败用例。测试音频为原版音频文件的副本，选取与被替换原声明显不同的素材，仅用于验证。

- 离线 `check_offline.py` 25/25：前缀、非 Ogg 数据、缺文件、非 bgm 写循环点、类型、扩展名、未登记键、未声明依赖的引用、关卡音乐类型与可见范围、合计超过 380 个各自使模组跳过并给出原因；分配 32/33/34；容量 380 与超限拒绝；空闲区段与原生表无交集；op23 换算且不修改单位数据；无模组时无音效。
- 运行 `run_sounds.py --part lab` 11/11：SoundID 与原生记录（文件名、音量 120×256、类型、循环点）、原生表 651 条不变、已安装脚本 op23 为 32/33；LAB 战斗前预载（引用计数 2）、我方出击后开炮音效在原生通道上播放 3 次（增益 3047，为同类原版音效 2539 的 120/100）、突进音效播放 3 次、退出后引用计数归零。
- 运行 `--part stage` 11/11：模组关卡的 BGM 表为 SoundID 34，扩展音乐槽 1031 未占用；打开隔离存档的音乐开关后，该 BGM 在原生通道上连续播放 120 帧，增益 2539。
- 运行 `--no-mods` 2/2：头部 +152/+156 为 0，原生表与五个空闲 ID 的查询结果不变。
- 无模组时安装一致性（`dump_install.py` + `compare_dumps.py`，`install_comparison.json`）：M5 同步版加载器与 M6 加载器在同一 r41 核心上，社区头部、数据段、GOT、分配表逐字节相同；客体堆仅两处 2496 字节的原生随机数状态因启动时间种子不同。
- 回归（r41）：M3 离线 19/19、M3 运行（模组单位购买、编队、LAB、保留武器、重启）全部通过；M5 离线 32/32、M5 运行 play 阶段通过；M4 MOD 页 ALL PASS；单元测试 6 项通过。

截图：`runs/lab_*/screens/`（自定义开炮、突进音效首次播放时刻）、`runs/stage_*/screens/stage_bgm.png`。

## 6. 限制与待办

- 容量 380 个，为同时启用的本体与模组音效合计；使合计超限的模组被跳过。超过 1031 的 SoundID 需要逐处适配原生缓存数组，列为后续选项。
- 本体音效（`content.json` 的 `sounds`）只做了离线条目检查，本体目前未登记音效，运行路径与模组相同。
- 实际听感未在实机听辨；验证依据为原生通道的声音对象与增益。
- 已修复的既有问题（同日追加）：测试中 LAB 战斗以“退出”结束后回到 LAB 准备界面（准备界面仍打开，按设计保持 MISSION BGM 135），此时直接开始扩展世界关卡，准备界面的 BGM 保持逻辑会持续请求 135 覆盖关卡音乐（原版 BGM 107 的关卡同样）。LAB 正常关闭后两者均连续播放（`diag_bgm.py --close-lab`）。修正：`community_campaign.py` 在 LAB 准备界面打开或 LAB 战斗进行中拒绝打开与开始扩展世界（`lab_open`）；`lab_prep.py` 的 BGM 保持只在主菜单场景 27/28 生效。`run_bgm_fix.py` 两次运行各 5/5：回到准备界面后仍为 135、准备界面打开期间扩展世界入口被拒绝、关闭 LAB 后主菜单 BGM 101、关卡 BGM（107 与音效键 34）连续 240 帧播放且无其他 BGM 请求。该路径只在开发预览中可达（扩展世界界面不显示）。
- 联机内容清单（M7）应计入音效键、文件摘要与分配结果。
