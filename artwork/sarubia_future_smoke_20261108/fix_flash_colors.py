"""未来爆竹红发白帧颜色修正（2026-11-08，用户按样张确认）：改写 community_content/sarubia_future.obm 中配错的像素，并同步 content.json 的摘要。
原因：2026-10-02 换色把原版高光 (230,197,106) 统一换成车体蓝灰 (132,148,156)，只有紧贴暖色的像素换成暖色高光，发白帧整块被照亮的面板内部因此变成蓝灰。
规则（单位矩形 0–29，局部 py = y − ay + 96；只改调色板索引，调色板、尺寸与其他像素不变；可重复运行）：
- 原版 (230,197,106) 且当前为蓝灰：py ≥ 60（车身下部黄条）→ (230,197,106)；其余（橙色面板、炮口内部）→ (255,206,115)；
- 原版与当前都是棕灰 (164,148,131)（帧 32 圆盘标志内）→ (132,148,156)。
用法：E:/anaconda3/python.exe -I fix_flash_colors.py"""
import re, sys, struct
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'verification' / 'msadv_tyra_walk_20261023'))
sys.path.insert(0, str(REPO))
from frames import Unit  # noqa: E402
import content_digest  # noqa: E402

ATLAS = REPO / 'community_content' / 'sarubia_future.obm'
INDEX = REPO / 'community_content' / 'content.json'
SRC, GREY, WARM, TAN = (230, 197, 106), (132, 148, 156), (255, 206, 115), (164, 148, 131)
HEADER = 8 + 1024


def main():
    u = Unit(6)
    stock = u.atlas(0)
    raw = bytearray(ATLAS.read_bytes())
    assert raw[:4] == b'OI\x01\x08'
    w, h = struct.unpack_from('<HH', raw, 4)
    pal = np.frombuffer(bytes(raw[8:HEADER]), np.uint8).reshape(-1, 4)
    idx = np.frombuffer(bytes(raw[HEADER:HEADER + w * h]), np.uint8).reshape(h, w).copy()

    def find(rgb):
        hits = [i for i in range(1, 256) if tuple(int(v) for v in pal[i][:3]) == rgb and pal[i][3] == 255]
        assert hits, rgb
        return hits[0]

    target = {'bar': find(SRC), 'warm': find(WARM), 'grey': find(GREY)}
    counts = {'warm': 0, 'bar': 0, 'grey': 0}
    for i in range(30):
        x, y, rw, rh, ax, ay, *_ = u.rects[i]
        for yy in range(rh):
            for xx in range(rw):
                s = stock[y + yy, x + xx]
                if not s[3]:
                    continue
                sa = tuple(int(v) for v in s[:3])
                sb = tuple(int(v) for v in pal[idx[y + yy, x + xx]][:3])
                if sa == SRC and sb == GREY:
                    kind = 'bar' if yy - ay + 96 >= 60 else 'warm'
                elif sa == TAN and sb == TAN:
                    kind = 'grey'
                else:
                    continue
                idx[y + yy, x + xx] = target[kind]
                counts[kind] += 1
    raw[HEADER:HEADER + w * h] = idx.tobytes()
    ATLAS.write_bytes(bytes(raw))

    text = INDEX.read_bytes().decode('utf-8')
    assert '\r\n' in text
    digest = content_digest.blake2(ATLAS.read_bytes())
    new, n = re.subn(r'    "sarubia_future\.obm": "[0-9a-f]{64}"', f'    "sarubia_future.obm": "{digest}"', text)
    assert n == 1
    INDEX.write_bytes(new.encode('utf-8'))
    print(counts, 'digest', digest)


if __name__ == '__main__':
    main()
