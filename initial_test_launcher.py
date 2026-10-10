"""初始进度的独立测试存档（play_save_initial_test）：首次启动以 game_data/seed.dat（正式版初始种子）建立，
社区单位均未拥有，单位商店有可购买的单位，供测试商店等流程。已有存档保持原值；删除该文件夹后重新启动即恢复初始进度。
不读写 play_save 等其他存档。"""
from pathlib import Path
import argparse
import os
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import portable_launcher  # noqa: E402,F401
import event_trial_launcher  # noqa: E402
import player  # noqa: E402

PROFILE = 'play_save_initial_test'
SEED = ROOT / 'game_data/seed.dat'
PACKAGE = 'com.snkplaymore.android003'


def initialize_profile(guest_root):
    """首次启动写入初始种子，已有原生存档保持原值。"""
    guest_root = Path(guest_root).resolve()
    if not guest_root.is_relative_to(ROOT):
        raise ValueError('独立存档目录必须位于当前游戏目录内')
    saves = guest_root / 'data/data' / PACKAGE
    native = saves / 'test.dat'
    if native.is_file():
        return guest_root
    data = SEED.read_bytes()
    saves.mkdir(parents=True, exist_ok=True)
    temporary = native.with_name(native.name + f'.init-{os.getpid()}.tmp')
    with temporary.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        if not native.exists():
            os.rename(temporary, native)
    finally:
        if temporary.exists():
            temporary.unlink()
    return guest_root


def create_player(self_test=False, *, guest_root=None, fullscreen=None):
    default = ROOT / ('verification/initial_test_self_test' if self_test else PROFILE)
    profile = initialize_profile(default if guest_root is None else guest_root)
    session = event_trial_launcher.create_player(self_test, fullscreen=fullscreen)
    player.TITLE = 'MSD WINDOWS S1XLV · 26.10.1 · 初始存档测试'
    session.guest_root = profile
    session.status_file = ROOT / 'initial_test_status.json'
    session.log_name = 'initial_test_player.log'
    return session


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description='MSD WINDOWS S1XLV：初始进度独立测试存档')
        parser.add_argument('--self-test', action='store_true')
        parser.add_argument('--mute', action='store_true')
        parser.add_argument('--windowed', action='store_true')
        args = parser.parse_args()
        session = create_player(args.self_test, fullscreen=False if args.windowed else None)
        session.mute_requested = args.mute
        sys.exit(session.run())
    except Exception:
        import ctypes
        import traceback
        error = traceback.format_exc()
        path = ROOT / 'initial_test_launcher_error.log'
        path.write_text(error, encoding='utf-8')
        if '--self-test' not in sys.argv:
            ctypes.windll.user32.MessageBoxW(None, '初始存档测试启动失败。错误记录：\n' + str(path),
                                            'MSD WINDOWS S1XLV', 0x10)
        sys.exit(1)
