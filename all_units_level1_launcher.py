"""启用全兵种 Lv1、初始地图进度的独立正式版存档。"""
from pathlib import Path
import argparse
import os
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import portable_launcher
import event_trial_launcher
import player

PROFILE = 'play_save_all_units_level1'
SEEDS = ROOT / 'game_data/all_units_level1'
PACKAGE = 'com.snkplaymore.android003'


def initialize_profile(guest_root):
    """首次启动使用专用种子，已有原生存档保持原值。"""
    guest_root = Path(guest_root).resolve()
    if not guest_root.is_relative_to(ROOT):
        raise ValueError('独立存档目录必须位于当前游戏目录内')
    saves = guest_root / 'data/data' / PACKAGE
    native = saves / 'test.dat'
    if native.is_file():
        return guest_root
    sources = ((SEEDS / 'seed_community.json', saves / 'community_progress.json'),
               (SEEDS / 'seed.dat', native))
    payloads = [(source.read_bytes(), target) for source, target in sources]
    saves.mkdir(parents=True, exist_ok=True)
    lock = saves / 'profile_initialization.lock'
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        if native.is_file():
            return guest_root
        for data, target in payloads:
            if target.exists():
                continue
            # 临时文件完整写入后登记，Windows rename 拒绝覆盖已有目标。
            temporary = target.with_name(target.name + f'.init-{os.getpid()}.tmp')
            with temporary.open('xb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.rename(temporary, target)
            finally:
                if temporary.exists():
                    temporary.unlink()
    finally:
        os.close(descriptor)
        lock.unlink()
    return guest_root


def create_player(self_test=False, *, guest_root=None, fullscreen=None):
    default = ROOT / ('verification/all_units_level1_self_test' if self_test else PROFILE)
    profile = initialize_profile(default if guest_root is None else guest_root)
    session = event_trial_launcher.create_player(self_test, fullscreen=fullscreen)
    player.TITLE = 'MSD WINDOWS S1XLV · 26.10.1 · 全兵种 Lv1'
    session.guest_root = profile
    session.status_file = ROOT / 'all_units_level1_status.json'
    session.log_name = 'all_units_level1_player.log'
    return session


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description='MSD WINDOWS S1XLV：全兵种 Lv1 独立存档')
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
        path = ROOT / 'all_units_level1_launcher_error.log'
        path.write_text(error, encoding='utf-8')
        if '--self-test' not in sys.argv:
            ctypes.windll.user32.MessageBoxW(None, '全兵种 Lv1 存档启动失败。错误记录：\n' + str(path),
                                            'MSD WINDOWS S1XLV', 0x10)
        sys.exit(1)
