# 联机验收工具 / Netplay acceptance tool（N4、N5、N5.5）

完整清单与步骤：`docs/netcode/N4_TWO_MACHINE_ACCEPTANCE.md`。Full checklist: same file.

两台电脑使用**同一份游戏目录**（把整个游戏文件夹复制到另一台电脑即可）。每台电脑运行一条命令，双方自动进行一场无窗口联机对战
（输入由固定脚本产生，默认 2 轮，第 2 轮为再战），自动比较双方每 30 帧的战斗状态校验值，最后显示“验收通过 PASS / 验收未通过 FAIL”。
不读写任何玩家存档；结果在游戏目录 `verification\netplay_check\<时间>_<命令>\result.json`。

Both computers use **the same game folder**. Run one command on each; the two play a headless match with scripted inputs
(2 rounds by default, the second is a rematch), compare battle-state checksums every 30 frames and print PASS / FAIL.
No player save is read or written. Results: `verification\netplay_check\<time>_<command>\result.json` in the game folder.

**只有一台电脑时 / One computer only**：双击 `local_pair.bat`，选择编号（1 标准、2 较差网络、3 断网恢复、4 断线结束、5 会合服务器 + 房间码、
6 经本机网卡地址、7 篡改检测、8 观战、9 常规联机（N6a：存档编队与发展进度、点击底栏与单位）、0 依次运行 1–5、7、8 与 9）。房主与加入方作为两个独立的游戏进程在本机互连，双方进度在同一窗口显示（[房主] / [加入方]），最后显示汇总。
一台电脑测不到跨 CPU（Intel/AMD）一致性与真实路由器打洞：请有 AMD 电脑的朋友运行 `reference.bat`，把 `result.json` 发回后用 `compare.bat` 比较。
Double-click `local_pair.bat` and pick a number; host and joiner run as two separate game processes on this PC.

| 场景 Scenario | 电脑 A | 电脑 B |
| --- | --- | --- |
| 局域网 LAN | `lan_host.bat` | `lan_join.bat` |
| 直接连接 Direct（A 的路由器开放 UDP 47631 或支持 UPnP） | `direct_host_upnp.bat` | `direct_join.bat <A的公网IP>:47631` |
| 会合服务器 Rendezvous（服务器 S 上先运行 `rendezvous_server.bat`） | `remote_host.bat <S>:47632`（显示房间码） | `remote_join.bat <S>:47632 <房间码>` |
| 单机参照 Reference（无法联网时比较确定性） | `reference.bat` | `reference.bat`，再 `compare.bat <A 的 result.json> <B 的 result.json>` |

首次运行时 Windows 防火墙会询问是否允许 `python.exe` 通信：请允许（专用网络）。
On first run Windows Firewall asks whether to allow `python.exe`; allow it (private networks).

命令行完整参数：`windows_runtime\python.exe tools\netplay_check\netplay_check.py --help`。
断线测试 Outage tests：`--outage-at 600 --outage 4`（应恢复 / should recover）、`--outage-at 600 --outage 20 --expect-end disconnected`（应体面结束 / should end gracefully）。

N5 分歧与篡改检测 Desync & tamper detection（`docs/netcode/N5_DESYNC_AND_TAMPER_2026-10-10.md`）：对战中双方状态不一致时，双方都结束本轮、交换分歧数据，
并在结果目录写出分歧报告 `desync_r<轮>_f<帧>_<时间>.json`（第一个不一致的帧、不一致的区域与数值），控制台显示报告摘要。
以下参数只用于测试（模拟修改过的客户端），一方加 `--tamper`，双方都加 `--expect-end desync`：
`--tamper ap@600`（锁定本方 AP）、`base-hp@600`（锁定本方据点生命）、`row@600`（改动单位数据行）、`withhold@300`（不发送校验值）、`echo@300`（把对方的校验值原样发回）。
`--forge-manifest <manifest.json>`：报告指定的内容清单（伪造清单），双方加 `--expect-end frame0`；`--save-manifest` 把本机内容清单写入结果目录。
Test-only options above simulate a modified client; both sides should detect the divergence, exchange data, write a desync report and end the round gracefully.

`fixture\` 为测试存档（与验证所用相同），不是玩家存档。`fixture\` holds a test save used only by this tool.

N5.5 回放与观战 Replays & spectating（`docs/netcode/N5_5_REPLAY_SPECTATE_2026-10-10.md`）：
- 每轮对战结束后，双方各自在结果目录 `replays\` 保存一份回放（`.msdreplay`，约 20–30 KB；`--no-replay` 不保存，`--replay-dir` 指定目录）。
  `replay_check.bat <回放文件>`（即 `netplay_check.py replay <回放文件> --seek-test`）无窗口重算该回放，逐点比较录制的校验值与结束帧，
  并测试暂停、倍速与前后跳转。另一台电脑（尤其 Intel 与 AMD 之间）重算同一份回放也应一致，可用于跨 CPU 验收。
  在游戏窗口中观看回放：`tools\replay_viewer\replay_viewer.bat`。
- 观战：房主默认开放 4 个观战席位（`--spectators 0` 不接受观战）。第三台电脑运行 `spectate.bat`（局域网）、`spectate.bat <A的地址>:47631`（直连）
  或 `spectate.bat <S>:47632 <房间码>`（会合服务器）；观战者落后约 2 秒，中途加入时先追上，重算并核对双方的校验值，不影响双方的对局。
  席位已满或内容不同时被拒绝并显示原因。
- Every round both players save a replay in `replays\`. `replay_check.bat <file>` re-simulates it without a window and compares it with the
  recorded checksums (also usable across Intel/AMD). The host accepts up to 4 spectators; run `spectate.bat` on a third computer
  (no argument: LAN; `IP:PORT`: direct; `SERVER:PORT CODE`: rendezvous). Spectators watch about 2 seconds behind and verify the checksums.

N6a 常规联机 Regular netplay（`docs/netcode/N6A_REGULAR_NETPLAY_2026-10-10.md`）：游戏内入口为主菜单“對戰” → “局域网”卡片（Wi-Fi VERSUS 菜单 → 建立房間 / 加入房間）。
本工具双方都加 `--regular` 时以测试存档的当前编队与发展进度（单位等级、据点基础状态）进行常规对战（官方 Wi-Fi 对战地图池），
`--touch-test` 另在固定帧经原生触点点击底栏（出兵格、AP 升级、弹头车）与绝招可用的本方单位（单体绝招）。一台电脑：`local_pair.bat 9`。
In-game: main menu VERSUS → LAN card. With `--regular` on both sides the tool plays the regular mode (save deck and development, official
Wi-Fi map pool); `--touch-test` also clicks the bottom bar and units through the native touch path. One PC: `local_pair.bat 9`.
