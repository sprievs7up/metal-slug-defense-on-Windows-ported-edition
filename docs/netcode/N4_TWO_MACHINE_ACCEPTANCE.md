# N4 两机验收清单（2026-10-10；N5 补充第 1.1 节编号 7 与第 3 节 B5、B6；N5.5 补充编号 8、第 2 节 A7、A8 与第 3 节 B7；N6a 补充编号 9 与第 2.1 节 C 组；N6b 补充第 3.1 节 D 组）

依据：`docs/netcode/ROLLBACK_NETCODE_TASK_2026-10-09.md` 第 7 节 R4（跨 CPU 与两机验收留到用户有条件时集中进行；每台电脑运行一条命令，自动比对结果）。
工具：`tools/netplay_check/`（`netplay_check.py` 与 `.bat` 启动文件，说明见同目录 `README.md`）。网络层说明：`docs/netcode/N4_NETWORK_LAYER_2026-10-10.md`。

## 1. 准备

1. 两台电脑使用**同一份游戏目录**：把用户固定运行目录（`metal-slug-defense-on-Windows-ported-edition-main`）整个复制到另一台电脑。
   双方的宿主程序、核心与内容必须完全相同，否则工具会拒绝匹配并列出差异（这本身也是一项检查，见 B4）。
2. 工具不读写任何玩家存档：使用 `tools\netplay_check\fixture` 中的测试存档副本，LAB 设定、模组设定与缓存都写在结果目录。默认不启用任何模组。
3. 首次运行时 Windows 防火墙会询问是否允许 `windows_runtime\python.exe` 通信，请允许（至少“专用网络”）。网络被识别为“公用网络”时，
   局域网发现可能收不到：可把网络改为专用，或在防火墙中允许 UDP 47630（发现）、47631（对战）。
4. 记录两台电脑的 CPU（结果文件 `environment.cpu` 会自动记录）。最理想的组合是 Intel 与 AMD 各一台（跨 CPU 确定性）。
5. 每次运行的结果在游戏目录 `verification\netplay_check\<时间>_<命令>\result.json`，控制台最后一行显示“验收通过 PASS / 验收未通过 FAIL”。
   完成后请把双方的结果目录（至少 `result.json`，失败时连同 `console.log`）发回，以便分析。

每项默认进行 2 轮无窗口对战（第 1 轮打到分出胜负，第 2 轮为再战：互换编队、重新抽取种子与地图），双方输入由固定脚本产生。
每轮约 1–3 分钟（含启动约 15 秒）。通过标准：双方都显示 PASS；结果中每轮 `outcome.mismatched` 为空、`common_checksums` 大于 0、双方结束帧相同。

## 1.1 只有一台电脑时（`local_pair.bat`）

双击 `tools\netplay_check\local_pair.bat`，输入编号（也可 `local_pair.bat 3` 直接运行）。房主与加入方作为两个独立的游戏进程在本机互连，
各用独立的测试存档副本与结果目录；双方进度在同一窗口显示（[房主] / [加入方] / [服务器]），最后显示每项与总体的“通过 PASS / 未通过 FAIL”。
结果在 `verification\netplay_check\<时间>_local_pair\`（`local_pair.json` 为汇总，`caseN\host`、`caseN\join` 为双方结果）。

| 编号 | 内容 | 通过标准 |
| --- | --- | --- |
| 1 | 局域网发现（本机回环），2 轮打到分出胜负（第 2 轮再战） | 两轮双方一致 |
| 2 | 双方模拟单向延迟 100 ms、抖动 20 ms、丢包 2% | 同上 |
| 3 | 加入方第 600 帧起模拟断网 4 秒 | 自动恢复，两轮双方一致 |
| 4 | 加入方第 600 帧起模拟断网 20 秒 | 双方约 10 秒后判定断线并体面结束 |
| 5 | 本机启动会合服务器，房主登记房间码，加入方凭房间码连接 | 两轮双方一致 |
| 6 | 经本机网卡地址（局域网广播与网卡 IP） | 首次会弹出 Windows 防火墙提示，允许后两轮双方一致 |
| 7 | 篡改检测（N5）：加入方第 600 帧起锁定本方 AP（模拟内存修改） | 双方在第 630 帧附近检出分歧、交换分歧数据、写出分歧报告并回到准备界面 |
| 8 | 观战（N5.5）：另启动 2 名观战者（1 名开战前加入，1 名约 25 秒后中途加入），1 轮 | 双方一致；两名观战者重算的校验点全部与房主一致，中途加入者先追赶到缓冲位置 |
| 9 | 常规联机（N6a）：测试存档的当前编队与发展进度，经原生触点点击底栏与单位（单体绝招），模拟延迟 100 ms、抖动 20 ms、丢包 2%，2 轮 | 两轮双方一致 |
| 0 | 依次运行 1–5、7、8 与 9（约 20 分钟） | 全部通过 |

一台电脑覆盖不到的项目：Intel 与 AMD 的跨 CPU 一致性（两个进程使用同一颗 CPU）——请有 AMD 电脑的朋友运行 `reference.bat`（不需要联网），
把生成的 `result.json` 发回，在本机也运行 `reference.bat` 后用 `compare.bat` 比较（第 2 节 A6）；或把本机结果目录 `replays\` 中的一份回放发给对方，
由对方运行 `replay_check.bat <回放文件>` 重算（第 2 节 A7）；真实路由器的打洞与 UPnP、真实网络中断（编号 3、4 为模拟）；低配电脑的帧耗时与内存。

## 2. 局域网（两台电脑在同一路由器下）

| 项 | 电脑 A | 电脑 B | 通过标准 |
| --- | --- | --- | --- |
| A1 局域网发现 + 2 轮对战（跨 CPU 确定性） | `lan_host.bat` | `lan_join.bat` | 双方 PASS。B 的控制台列出找到的房间。 |
| A2 按 IP 直连 | `lan_host.bat` | `direct_join.bat <A 的局域网 IP>:47631`（A 的控制台第二行显示本机地址） | 双方 PASS |
| A3 短暂断网后恢复（模拟） | `windows_runtime\python.exe tools\netplay_check\netplay_check.py host` | `windows_runtime\python.exe tools\netplay_check\netplay_check.py join --outage-at 600 --outage 4` | 双方 PASS；B 的结果中 `rounds[0].outage` 有记录，`link.interruptions` 有一段约 4 秒的中断 |
| A4 真实断线后恢复 | `lan_host.bat` | `lan_join.bat`；第 1 轮进行中（控制台 frame 300 之后）拔掉 B 的网线或关闭 Wi-Fi 约 3 秒再恢复 | 双方 PASS（中断少于 10 秒时自动恢复） |
| A5 长时间断线体面结束 | `...netplay_check.py host --expect-end disconnected` | `...netplay_check.py join --expect-end disconnected`；第 1 轮进行中断开 B 的网络 20 秒以上 | 约 10 秒后双方显示断线并结束本轮，回到准备界面（`prep_returned` 为 true），双方 PASS，程序正常退出 |
| A6 单机参照比较（备用：两台电脑无法联网时） | `reference.bat` | `reference.bat` | 把 B 的 `result.json` 复制到 A，运行 `compare.bat <A 的 result.json> <B 的 result.json>`，显示 PASS |
| A7 回放重算（N5.5；在 Intel 与 AMD 之间进行时即为跨 CPU 检查） | A1 完成后，把 A 结果目录 `replays\` 中的 `.msdreplay` 复制到 B | `replay_check.bat <回放文件>`（可把文件拖到该 .bat 上） | 显示 PASS：校验点全部一致、结束帧相同，暂停 / 倍速 / 跳转各步骤均为 ok |
| A8 局域网观战（N5.5；需要第三台电脑 C，没有时跳过） | `lan_host.bat` | `lan_join.bat`；C 在 A 显示“等待对方加入”后运行 `spectate.bat`（对战开始后再运行则测试中途加入） | 三方 PASS；C 的 `result.json` 中 `spectate.rounds[i].verified` 等于 `recorded`，`mismatch` 为空 |

## 2.1 游戏内常规联机（N6a，两台电脑在同一局域网）

使用游戏本身（不是验收工具）：主菜单“對戰” → “局域网”卡片 → Wi-Fi VERSUS 菜单。游戏使用各自的玩家存档（名称与本地联机战绩写在存档目录的
`netplay_profile.json`），不需要准备测试存档。首次“建立房間”时 Windows 防火墙会询问是否允许网络访问，请同时勾选“专用网络”和“公用网络”（Windows 11 默认把新连接的网络设为“公用网络”）。

| 项 | 电脑 A | 电脑 B | 通过标准 |
| --- | --- | --- | --- |
| C1 局域网房间 + 2 轮（含再战） | 输入名称 → 建立房間 | 输入名称 → 加入房間，列表中出现 A 的房间（名称、地址、房间码）后点击 | 双方进入房间、显示对方名片；双方“準備”后出现对手画面并开战；P1（A）在左、P2（B）在右，B 的镜头从右侧据点开始、底栏为 B 的编队。打到分出胜负后双方回到房间，结果相反（一方勝利、一方敗北）；“再戰”第 2 轮同样完成；双方战绩随之更新 |
| C2 按 IP 直连 | 建立房間（窗口显示本机地址） | 加入房間 → 輸入 IP，填写 A 的地址 | 同 C1 第 1 轮 |
| C3 操作 | — | 对战中用鼠标点底栏出兵、AP 升级、弹头车，点击绝招可用的本方单位；键盘 1–0、空格、`、- | 操作在双方画面中同样生效；对战不出现“状态不一致”提示 |
| C4 Esc 菜单与投降 | 对战中按 Esc | — | 菜单打开时对战继续；选择投降并确认后双方结束本轮，A 显示敗北（你已投降），B 显示勝利（對手投降） |
| C5 断线 | — | 对战中断开 B 的网络 20 秒以上 | 约 10 秒后双方显示断线并回到房间（或大厅）；恢复网络后可重新建立房间 |
| C6 帧耗时（低配电脑） | 对战中观察画面是否卡顿 | 同左 | 记录电脑型号；卡顿时把游戏目录中的 `event_trial_player.log` 发回 |

完成后可把双方用户目录 `%LOCALAPPDATA%\MSD_WINDOWS_S1XLV\netplay\replays\` 中本次的回放各发回一份（同一轮双方的回放应能互相重算一致，见 A7）。

## 3. 远程（两台电脑在不同网络，例如一台用手机热点）

| 项 | 操作 | 通过标准 |
| --- | --- | --- |
| B1 会合服务器 + 打洞 | 在一台可公网访问的电脑或云服务器 S 上运行会合服务器（`rendezvous_server.bat`，或 `python3 rendezvous_server.py`，见 `docs/netcode/RENDEZVOUS_SERVER.md`，放行 UDP 47632）。A：`remote_host.bat <S>:47632`，控制台显示房间码；B：`remote_join.bat <S>:47632 <房间码>` | 双方 PASS。若打洞失败，B 显示“无法连接：双方网络无法直接互通……”，A 等待超时；请记录双方网络类型（家庭宽带 / 手机热点 / 公司网络） |
| B2 直接连接（A 的路由器支持 UPnP） | A：`direct_host_upnp.bat`，控制台显示“UPnP：路由器已开放端口，对方可直接连接 <公网IP>:47631”；B：`direct_join.bat <该地址>` | 双方 PASS。UPnP 未成功时 A 显示原因（可跳过本项，或在路由器上手动把 UDP 47631 转发到 A 后重试） |
| B3 远程断线恢复（模拟） | 同 B1，B 改用 `...netplay_check.py rdv-join --server <S>:47632 --code <房间码> --outage-at 600 --outage 4` | 双方 PASS |
| B5 篡改检测（N5） | A：`...netplay_check.py host --rounds 1 --expect-end desync`；B：`...netplay_check.py join --rounds 1 --expect-end desync --tamper ap@600`（远程时改用 rdv-host / rdv-join） | 双方 PASS；双方结果目录各有 `desync_r1_f630_*.json`，报告指出 P2 控制器的 AP 不同 |
| B6 伪造内容清单（N5） | A：`...netplay_check.py host --rounds 1 --save-manifest`，显示“等待对方加入”后按 Ctrl+C 结束（此时结果目录已写入 `manifest.json`），把该文件复制到 B。再按 B4 修改 B 的一个单位数值文件后，A：`...host --rounds 1 --expect-end frame0`；B：`...join --rounds 1 --expect-end frame0 --forge-manifest <manifest.json>` | 匹配通过而开战前（第 0 帧）被拒绝，双方列出“开战时单位实际数值不同”或“开战时状态校验值不同”，并写出分歧报告。测试后务必恢复该文件 |
| B7 远程观战（N5.5；需要第三台电脑 C，没有时跳过） | 同 B1；C 在 A 显示房间码后运行 `spectate.bat <S>:47632 <房间码>` | 三方 PASS（判定同 A8） |
| B4 内容不一致拒绝匹配 | 在 B 的游戏目录中修改一个参与比对的文件（例如先备份 `community_content\units\kt21.json`，再把其中的 `"ap": 200` 改为 `201`），再进行 A1 | 双方都显示“拒绝匹配 Rejected：content”，并列出差异（例如“单位设定不同”或“单位数值不同”）。测试后务必恢复该文件 |

## 3.1 游戏内远程联机（N6b，地址 + 房间码，不需要服务器）

使用游戏本身：主菜单“對戰” → “远程”卡片。两台电脑在不同网络（例如一台用手机热点，或不同家庭）。房主（A）建立房间后，把窗口中的一个地址与房间码告诉 B。
房主必须能被 B 直接访问（见 `docs/netcode/N6B_REMOTE_DIRECT_2026-10-10.md` 第 2 节）。请记录双方的网络类型（家庭宽带 / 手机热点、是否有 IPv6）与结果。

| 项 | 电脑 A（房主） | 电脑 B | 通过标准 |
| --- | --- | --- | --- |
| D1 UPnP 公网 IPv4 | 建立房間，窗口出现“公網 IPv4（路由器已開放連接埠）”一行 | 加入房間，输入该地址与房间码 | 连上并完成一轮；若 A 的窗口显示 UPnP 失败、运营商级 NAT 或内部地址，记录提示文字后进行 D2–D4 |
| D2 手动转发端口 | 在路由器上把 UDP 47631（或窗口中“更改連接埠”设定的端口）转发到 A；公网 IP 取路由器状态页显示的 WAN IP | 输入 `公网IP:端口` 与房间码 | 连上并完成一轮 |
| D3 IPv6 | 窗口出现“IPv6”一行（双方网络都有 IPv6 时） | 输入 `[IPv6 地址]:端口` 与房间码 | 连上并完成一轮；连不上时记录是否为路由器阻挡外来 IPv6 |
| D4 虚拟局域网 | 双方加入同一虚拟网（Radmin VPN、Hamachi、ZeroTier 等），A 建立房间 | 输入 A 在虚拟网中的地址与房间码（或在“局域网”卡片的列表中选择） | 连上并完成一轮 |
| D5 房间码不正确 | 建立房間 | 输入正确地址与错误的房间码 | B 显示“無法連接：房間碼不正確”，A 的房间仍在等待；再输入正确的房间码可以连上 |
| D6 房主不可访问 | 不做任何端口设置（或在运营商级 NAT 网络中）建立房間 | 输入地址与房间码 | 约 12 秒后 B 显示“對方沒有回應”及说明（不应卡住）；互换房主后再试并记录结果 |

完成后可把双方用户目录 `%LOCALAPPDATA%\MSD_WINDOWS_S1XLV\netplay\replays\` 中本次的回放各发回一份。

## 4. 结果解读

- `rounds[i].outcome.common_checksums`：双方共同比较的校验点数（每 30 帧一个）；`mismatched`：不一致的帧（应为空）。
- `rounds[i].status.rollbacks / max_rollback / stalls`：回滚次数、最大回滚帧数、因等待对方输入而暂停的帧数。
- `rounds[i].tick_ms`：每帧处理耗时（p50/p95/p99/最大，毫秒），超过 33 ms 的帧会造成掉帧；低配电脑请特别留意。
- `rounds[i].memory_before / memory_after`：进程内存（MiB）。
- `link.srtt_ms`：平滑往返延迟（包含对方每帧处理的间隔，约多 0–33 ms）；`link.interruptions`：中断开始时刻与持续秒数。
- 失败时 `error` 或 `connect_failure`、`match.reason`、`match.differences` 给出原因。
- `rounds[i].replay`（N5.5）：本轮保存的回放（路径、大小、帧数、校验点数）。回放校验的结果在 `replay`：`verified_points` 应等于 `recorded_points`，`mismatch` 为空。
- `spectate.rounds[i]`（观战者，N5.5）：`verified` / `recorded` 校验点、`catchup_frames`（中途加入时追赶的帧数）、`median_lag_late`（落后帧数，约 60 帧即 2 秒）。

## 5. 常见问题

| 现象 | 处理 |
| --- | --- |
| B 找不到局域网房间 | 确认 A 已显示“等待对方加入”；防火墙允许 python.exe；网络为专用；或改用 A2 按 IP 直连 |
| “无法连接：对方没有回应” | 地址或端口错误、A 未运行或防火墙拦截 |
| “拒绝匹配 Rejected：content” | 两台电脑的游戏目录不同；按差异列表同步文件 |
| “无法连接：双方网络无法直接互通” | 打洞失败（对称型 NAT 等），按设计不提供中继；可改用 B2 并在路由器开放端口 |
| 某轮 FAIL 且 `mismatched` 非空 | 确定性问题（不同步），请发回双方完整结果目录 |
| 某轮 `end` 为 `desync`（未使用 `--tamper`） | 对战中状态不一致（N5）：双方结果目录的 `desync_*.json` 指出第一个不一致的帧与区域，请连同完整结果目录发回 |
