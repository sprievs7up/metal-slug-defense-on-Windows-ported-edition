# 模组 M7：联机内容清单与差异报告（2026-10-10）

依据：`docs/modding/MOD_SYSTEM_TASK_2026-10-09.md` 第 4.6、4.8 节与 M7 行；`docs/netcode/ROLLBACK_NETCODE_TASK_2026-10-09.md` 第 2 节。
本阶段完成 M7 的“内容清单与差异报告、拒绝匹配”部分；局域网发现与远程联机（会合、打洞）属于 N4，尚未实施。
2026-10-10 补记：N4 已实施（`docs/netcode/N4_NETWORK_LAYER_2026-10-10.md`）。联机协议版本改为 2；握手由 `netplay_match.Match` 先比较清单摘要，不同时双方再交换完整清单并各自列出差异；`netplay_net.py`、`netplay_match.py` 计入宿主文件比对。
2026-10-10 N5 补记：联机协议版本改为 3（校验 tag 包与分歧消息，`docs/netcode/N5_DESYNC_AND_TAMPER_2026-10-10.md`）；`netplay_desync.py` 计入宿主文件比对。开战时另比较双方编队各单位的实际数值摘要（清单之外的第 0 帧检查），伪造清单而实际数值不同的一方在开战前被拒绝。
2026-10-10 N5.5 补记：联机协议版本保持 3；`netplay_spectate.py` 计入宿主文件比对（`HOST_MODULES` 26 个）。回放文件保存完整清单与摘要，播放前与本机清单比较，不同时拒绝播放并列出差异；观战者加入时同样比较摘要（`docs/netcode/N5_5_REPLAY_SPECTATE_2026-10-10.md`）。
2026-10-10 N6a 补记：联机协议版本改为 4（32 位输入，单体绝招与投降）；`netplay_regular.py`、`netplay_profile.py`、`netplay_lobby.py` 与官方 Wi-Fi 对战地图池 `netplay_pool.json` 计入宿主文件比对（`HOST_MODULES` 30 个）。常规联机另在承诺—揭示中交换双方据点基础状态（`docs/netcode/N6A_REGULAR_NETPLAY_2026-10-10.md`）。
实现文件：`content_manifest.py`（清单生成、比较、差异文字）、`netplay_transport.py`（握手时交换与比较）。
摘要算法为 BLAKE2b-256（`content_digest`，用户 2026-10-09 确认），文件摘要按“大小 + 修改时间”缓存；这是游戏内功能，
与 AGENTS 第 12.1 节停用的“代理验证中的 SHA-256”无关。

## 1. 清单内容

由游戏启动、内容安装完成后的实际状态生成（`content_manifest.build(probe)`），JSON 格式，约 42 KB（zlib 压缩后约 24 KB，握手时以 base64 传输）。

| 类别 | 内容 | 说明 |
| --- | --- | --- |
| game | 显示版本、联机协议版本 | 协议版本见 `content_manifest.PROTOCOL` |
| core | 核心库文件名、文件摘要、导出接口版本（LAB 钩子、联机接口、社区单位、音效、图标页、原版补丁、行为库清单摘要） | 核心不同即拒绝 |
| host | 参与战斗逻辑或内容安装的宿主文件摘要（`HOST_MODULES`，M7 时 22 个；N4 后 24 个，N5 后 25 个，N5.5 后 26 个） | 换行统一为 LF 后计算，CRLF/LF 差异不计 |
| content | `community_content/`、`campaign_content/` 每个文件的摘要 | 本体内容 |
| behaviors | 行为库各行为版本与库版本 | |
| mods | 已载入模组（实际加载顺序）的 id、版本、全部文件摘要 | 顺序不同也拒绝（影响补丁覆盖与 ID 分配） |
| units | 每个社区单位：UnitID、规范化单位记录摘要、“实际数值”摘要 | 实际数值 = 安装后原生数据行 + Lv1/10/20/30/40 的 `getUnitStatus`（含倍率处理）与 `getUnitCreateParams`；数值块中引用本单位编号的字置零 |
| stock | 原版单位 1–399 的实际数值摘要（同上） | 覆盖补丁后的数值 |
| patches | 覆盖补丁列表（目标、字段、值） | |
| sounds | 自定义音效键与分配的 SoundID | |

## 2. 比较与拒绝

`content_manifest.diff(本方, 对方)` 逐项比较，返回差异列表，每项含类别、对象、双方值与中英文说明；`report()` 生成显示文字（超过 12 项时省略）。
握手（`netplay_transport.host_handshake` / `client_handshake`）：客户端发送清单，主机比较后回复是否接受并附本方清单；客户端也比较主机清单。任一方发现差异即拒绝，双方都记录差异说明。

差异类别：schema、protocol、display_version、core、core_version、host、content、behavior、mod_missing、mod_extra、mod_version、mod_files、mod_order、unit_missing、unit_extra、unit_id、unit_record、unit_numbers、stock_numbers、patches、sound。

## 3. 验证（`verification/netplay_20261010/`）

### 3.1 双客户端隔离测试（回环，`np_launch.py`，两个独立进程，各自隔离存档与模组目录）

测试模组由 `make_mods.py` 生成：mods_base（example_mod、quiet_mod、stock_mod）、mods_version（example_mod 版本 1.0.1）、mods_patch（example_mod 补丁值不同）、mods_stock（原版士兵补丁值不同）；启用列表 en_none / en_all / en_all_reordered；`idmap_swapped.json` 为客户端预置的不同 ID 映射。

见 `results/m7b_*.json`（最终清单代码）与 `results/m7_*.json`（首轮）。结果见第 5 节。

### 3.2 离线检查（`m7_offline.py`，结果 `results/m7_offline.json`）

以实际运行生成的清单为基础逐类改动：相同清单无差异；schema、protocol、display_version、core、core_version、host、content、behavior、unit_numbers、unit_record、unit_missing、stock_numbers、patches、sound、mod_missing、mod_order 各给出对应差异；宿主文件摘要对 CRLF/LF 不敏感；清单编码往返一致；差异文字超过上限时省略。20/20 通过。

## 4. 已知事项与待定

- 模组单位 ID：同一模组集合在两台机器上可能因启用历史不同而分配到不同 UnitID（ID 映射持久化于用户目录）。目前按“单位编号不同”拒绝匹配（推荐方案，确保确定性）。后续可在联机会话中按清单顺序重新分配 ID（需重启或运行时重映射，待用户决定）。
- 宿主文件摘要采用严格比较：两台机器的宿主程序不同（例如未同步的运行目录）即拒绝。
- 原版素材（OBM 图像等）不计入清单：碰撞与攻击判定数据位于原版程序库（启动时已核对固定摘要），图像只影响显示。
- 服务端裁决、防篡改与反作弊仍属 N5 后续设计；清单可由本地修改伪造，只用于发现无意的不一致。
