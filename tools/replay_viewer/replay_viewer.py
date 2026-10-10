"""MSD WINDOWS S1XLV 回放查看器（N5.5 测试工具，docs/netcode/N5_5_REPLAY_SPECTATE_2026-10-10.md）。

在游戏窗口中播放一份回放（.msdreplay）：自动进入 LAB 双人对战并按记录的输入重算，画面底部显示进度、速度与校验状态。
不读写玩家存档：使用联机验收工具的测试存档副本，LAB 设定与运行记录写在结果目录（游戏目录\\verification\\replay_viewer\\<时间>\\）。
回放与本机内容（单位、模组、程序文件等）不同时拒绝播放并显示差异。游戏内的回放入口与历史记录界面属于 N6。

按键：空格 暂停 / 继续；← / → 后退 / 前进 10 秒（Shift：60 秒）；↑ / ↓ 加速 / 减速（0.25×–8×）；Home 回到开头；
      鼠标拖动 移动镜头；F11 全屏；Esc 退出。
用法（在游戏目录中）：windows_runtime\\python.exe tools\\replay_viewer\\replay_viewer.py [回放文件]
      不指定文件时播放用户回放目录（%LOCALAPPDATA%\\MSD_WINDOWS_S1XLV\\netplay\\replays）中最新的一个。
测试：--auto 按内置脚本自动操作并截图后退出；--hidden 不显示窗口。
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools' / 'netplay_check'))

# 自动脚本：(开始播放后的显示帧, 指令)。截图写入结果目录。
AUTO_SCRIPT = [(90, ('capture', 'playing')), (100, ('pause',)), (130, ('capture', 'paused')), (140, ('seek', 300)),
               (150, ('capture', 'seek_forward')), (160, ('seek', -300)), (170, ('capture', 'seek_back')),
               (180, ('pause',)), (190, ('speed', 2)), (250, ('capture', 'speed_4x')), (260, ('speed', -2)),
               (270, ('camera', -400)), (280, ('capture', 'camera')), (290, ('start',)), (300, ('capture', 'start')),
               (310, ('exit',))]


def newest_replay():
    import netplay_replay as nr
    folder = nr.default_dir()
    files = sorted(list(folder.glob('*' + nr.SUFFIX)) + list((folder / 'kept').glob('*' + nr.SUFFIX)),
                   key=lambda p: p.stat().st_mtime, reverse=True) if folder.is_dir() else []
    return files[0] if files else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('replay', nargs='?')
    parser.add_argument('--fullscreen', action='store_true')
    parser.add_argument('--auto', action='store_true', help='测试：按内置脚本操作、截图后退出')
    parser.add_argument('--hidden', action='store_true', help='测试：不显示窗口')
    parser.add_argument('--out', help='结果目录')
    args = parser.parse_args(argv)
    out = Path(args.out) if args.out else ROOT / 'verification' / 'replay_viewer' / time.strftime('%Y%m%d_%H%M%S')
    out.mkdir(parents=True, exist_ok=True)
    import netplay_check as nc
    environment = argparse.Namespace(use_my_mods=False, mods_enabled=None, fixture=None)
    save_root = nc.prepare_environment(environment, out)
    import portable_launcher  # noqa: F401  随包 Python 与 ANGLE 的 DLL 目录
    import event_trial_launcher  # noqa: F401  正式入口的探针类与 LAB 运行时
    import glfw
    import lab as lab_module
    import lab_runtime
    import netplay_replay as nr
    import player

    path = Path(args.replay) if args.replay else newest_replay()
    if path is None or not path.is_file():
        print('没有可播放的回放 No replay to play:', args.replay or nr.default_dir())
        return 2
    replay = nr.load(path)
    report = {'replay': str(path), 'summary': nr.summary(replay), 'out': str(out), 'captures': [], 'started': time.strftime('%H:%M:%S')}

    original_record = lab_module.Lab.record

    def isolated_record(self, kind, **values):              # LAB 运行记录写入结果目录
        root = self.root
        self.root = out
        try:
            return original_record(self, kind, **values)
        finally:
            self.root = root
    lab_module.Lab.record = isolated_record

    holder = {}

    def factory(probe):
        viewer = nr.ReplayViewer(probe, replay, probe.log)
        holder['viewer'] = viewer
        if args.auto:
            viewer.auto = list(AUTO_SCRIPT)
            viewer.auto_start = None
        return viewer
    lab_runtime.DRIVER_FACTORY = factory

    if args.hidden:
        original_hint = glfw.window_hint
        glfw.window_hint = lambda hint, value: original_hint(hint, glfw.FALSE if hint == glfw.VISIBLE else value)

    base = player.Player

    class ViewerPlayer(base):
        drag = None

        def viewer(self):
            viewer = holder.get('viewer')
            return viewer if viewer is not None and self.ready else None

        def key(self, window, key, scan, action, mods):
            if key == glfw.KEY_F11 or (key == glfw.KEY_ENTER and mods & glfw.MOD_ALT) or key == glfw.KEY_F12:
                return super().key(window, key, scan, action, mods)
            if action not in (glfw.PRESS, glfw.REPEAT):
                return
            if key == glfw.KEY_ESCAPE:
                self.stop.set()
                return
            viewer = self.viewer()
            if viewer is None or viewer.phase != 'playing':
                return
            far = 1800 if mods & glfw.MOD_SHIFT else 300
            command = {glfw.KEY_SPACE: ('pause',), glfw.KEY_LEFT: ('seek', -far), glfw.KEY_RIGHT: ('seek', far),
                       glfw.KEY_UP: ('speed', 1), glfw.KEY_DOWN: ('speed', -1), glfw.KEY_HOME: ('start',)}.get(key)
            if command and (action == glfw.PRESS or command[0] == 'seek'):
                viewer.command(*command)

        def mouse_button(self, window, button, action, mods):
            if button != glfw.MOUSE_BUTTON_LEFT:
                return
            point = self.coordinates(*glfw.get_cursor_pos(window), clamp=True)
            self.drag = point[0] if action == glfw.PRESS and point else None

        def cursor(self, window, x, y):
            viewer = self.viewer()
            if self.drag is None or viewer is None or viewer.phase != 'playing':
                return
            point = self.coordinates(x, y, clamp=True)
            if point is not None and int(point[0] - self.drag):
                viewer.command('camera', int(point[0] - self.drag))
                self.drag = point[0]

    player.TITLE = 'MSD WINDOWS S1XLV · Replay'
    session = ViewerPlayer(fullscreen=args.fullscreen)
    session.guest_root = save_root
    session.status_file = out / 'viewer_status.json'
    session.log_name = str(out / 'viewer.log')
    session.settings_path = out / 'window_settings.json'
    if args.auto:
        original_drive = nr.ReplayViewer.drive

        def scripted(self):
            """测试脚本：开始播放后按显示帧发出指令并截图。"""
            if self.phase == 'playing':
                self.auto_start = self.p.frame if self.auto_start is None else self.auto_start
                elapsed = self.p.frame - self.auto_start
                while self.auto and self.auto[0][0] <= elapsed:
                    _, command = self.auto.pop(0)
                    if command[0] == 'capture':
                        self.pending_capture = command[1]
                    elif command[0] == 'exit':
                        report['final'] = self.battle.status()
                        session.stop.set()
                    else:
                        self.command(*command)
            elif self.phase in ('rejected', 'error') and self.p.frame > 600:
                session.stop.set()
            drawn = original_drive(self)
            name = getattr(self, 'pending_capture', None)
            if name and drawn:
                self.pending_capture = None
                target = out / f'{len(report["captures"]):02d}_{name}.png'
                self.p.graphics.capture(target)
                report['captures'].append({'name': name, 'file': target.name, 'frame': self.battle.frame,
                                           'paused': self.battle.paused, 'speed': self.battle.speed,
                                           'verified': len(self.battle.verified_frames), 'mismatch': self.battle.mismatch is not None})
            return drawn
        nr.ReplayViewer.drive = scripted
    code = session.run()
    viewer = holder.get('viewer')
    if viewer is not None:
        report.update(phase=viewer.phase, error=viewer.error,
                      differences=[d.get('zh') for d in (viewer.differences or [])],
                      verified=len(viewer.battle.verified_frames) if viewer.battle else None,
                      recorded=len(viewer.battle.recorded) if viewer.battle else None,
                      mismatch=viewer.battle.mismatch if viewer.battle else None)
    report['exit_code'] = code
    report['player_error'] = session.error
    (out / 'viewer_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps({k: report.get(k) for k in ('phase', 'verified', 'recorded', 'mismatch', 'exit_code', 'player_error')},
                     ensure_ascii=False, default=str))
    return code or 0


if __name__ == '__main__':
    sys.exit(main())
