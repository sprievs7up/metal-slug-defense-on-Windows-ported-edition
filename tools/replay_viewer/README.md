# 回放查看器 / Replay viewer（N5.5）

说明：`docs/netcode/N5_5_REPLAY_SPECTATE_2026-10-10.md`。游戏内的回放入口与历史记录界面属于 N6，本工具为测试与查看用。

在游戏窗口中播放一份回放（`.msdreplay`）：自动进入 LAB 双人对战，按记录的双方输入重算对局，画面底部显示进度、速度与校验状态
（重算的战斗状态与对局中录制的校验值逐点比较）。回放所需的单位、模组与程序文件与本机不同时拒绝播放，并列出差异。

- 打开：把回放文件拖到 `replay_viewer.bat` 上；直接双击则播放用户回放目录中最新的一个。
- 回放目录：联机对战与本地双人对战每场自动保存，保留最近 100 份，位于 `%LOCALAPPDATA%\MSD_WINDOWS_S1XLV\netplay\replays\`；
  该目录下 `kept\` 子目录中的文件不会被自动删除。联机验收工具的回放保存在其结果目录的 `replays\` 中。
- 按键：空格 暂停 / 继续；← / → 后退 / 前进 10 秒（按住 Shift：60 秒）；↑ / ↓ 加速 / 减速（0.25×–8×）；Home 回到开头；
  鼠标拖动 移动镜头；F11 全屏；Esc 退出。
- 不读写玩家存档：使用联机验收工具的测试存档副本；LAB 设定与运行记录写在 `游戏目录\verification\replay_viewer\<时间>\`。

Drag a `.msdreplay` file onto `replay_viewer.bat` (or double-click it to play the newest replay). The viewer re-simulates the match from the
recorded inputs and compares the result with the checksums recorded during the match; a replay made with different content is refused and
the differences are listed. Keys: Space pause, ←/→ seek 10 s (Shift 60 s), ↑/↓ speed 0.25×–8×, Home restart, mouse drag camera, F11 fullscreen,
Esc quit. Replays are saved automatically (latest 100) in `%LOCALAPPDATA%\MSD_WINDOWS_S1XLV\netplay\replays\`; files in `kept\` are never pruned.
No player save is read or written.

命令行 Command line：`windows_runtime\python.exe tools\replay_viewer\replay_viewer.py [回放文件] [--fullscreen]`。
无窗口的重算校验 Headless check：`tools\netplay_check\replay_check.bat <回放文件>`。
