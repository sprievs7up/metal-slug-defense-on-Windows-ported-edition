"""原生底栏按钮（60×48）的文字素材导出：供 FAVORITES 按钮（U1 D26）设计参照。

来源：原版 libAppMain.so 的 ConvMenuParts 表（VA 0x31c900，16 字节：x,y,w,h,锚点 x,y,—,页；页 0 = menuparts.obm，
页 1 = menuparts_02.obm）中全部 60×48 项；LAB 为宿主自带的 custom_content/lab.png（非原生）。
文字烘焙在按钮图内：深色底板第 37–42 行（共 6 行），文字像素 = 该 6 行、x 4–55 内非黑（max(RGB) > 12）的像素。
单字母按空列切分（字母间至少 1 列空隙）；切出的字母数与文字长度不符时记入 manifest 的 split_ok = false。

输出（out/）：
  buttons/<名称>.png          原按钮 60×48（1 倍）
  labels/<名称>.png           只含文字像素的 60×48 透明图层（原位置，可直接叠到空白按钮上）
  labels_tight/<名称>.png     文字像素的最小外框裁切（6 行高）
  glyphs/<名称>/<序号>_<字母>.png  单字母（6 行高，透明底）
  preview_labels_x8.png       文字条（第 32–47 行，含底板）8 倍预览
  preview_glyphs_x8.png       单字母 8 倍预览
  manifest.json               来源矩形、文字外框、每行主色、字母宽度
用法：E:\\anaconda3\\python.exe -I extract_labels.py
"""
from pathlib import Path
import json
import struct
import zipfile

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
APK = ROOT / 'game_data' / 'original.apk'
RES = ROOT / 'game_data' / 'assets' / 'com.snkplaymore.android003'
OUT = HERE / 'out'
CONV_MENU_PARTS = 0x31c900
ATLASES = {0: 'menuparts.obm', 1: 'menuparts_02.obm'}
TEXT_ROWS = (37, 43)            # 文字所在行（含 37，不含 43），同 unit_browser.LABEL_ROWS
TEXT_COLS = (4, 56)
DARK = 12
# ConvMenuParts 序号 → 按钮文字（序号由 60×48 项逐一核对图像得出；同字样的重复项只取第一项）
NATIVE = {30: 'BACK', 32: 'OPTION', 33: 'SHOP', 34: 'MEDAL', 36: 'OK', 99: 'ACHIEVEMENT', 100: 'RANKING',
          101: 'SORT', 102: 'STAGE', 105: 'CUSTOMIZE', 106: 'DECK', 112: 'POW', 115: 'ACHIEVEMENT_2',
          116: 'RANKING_2', 118: 'MAP', 119: 'MISSION', 120: 'FREE', 124: 'REMATCH', 131: 'FILTER', 132: 'EVENT',
          168: 'UNIT', 169: 'EVENT_2', 170: 'RESTORE'}
EXTRA = {'LAB': ROOT / 'custom_content' / 'lab.png'}
# 相连字母对的切分列（x < cut 属于左字母）：ACHIEVEMENT 的 NT、CUSTOMIZE 的 IZ、FILTER 的 LT
CUTS = {'ACHIEVEMENT': [51], 'CUSTOMIZE': [44], 'FILTER': [28]}
MAIN_MENU = ('BACK', 'OPTION', 'SHOP', 'MEDAL', 'LAB', 'MISSION')   # 主菜单底栏六项（historical_event_redesign R12）


def obm(name):
    raw = (RES / name).read_bytes()
    w, h = struct.unpack_from('<HH', raw, 4)
    if raw[:4] != b'OI\x01\x20':
        raise ValueError(f'{name}: 非 32 位 RGBA 图集')
    return Image.frombytes('RGBA', (w, h), raw[8:8 + w * h * 4])


def conv_table():
    lib = zipfile.ZipFile(APK).read('lib/armeabi-v7a/libAppMain.so')
    phoff, = struct.unpack_from('<I', lib, 0x1c)
    phentsize, phnum = struct.unpack_from('<HH', lib, 0x2a)
    segments = []
    for i in range(phnum):
        kind, off, va, _, filesz, _ = struct.unpack_from('<6I', lib, phoff + i * phentsize)
        if kind == 1:
            segments.append((va, off, filesz))

    def entry(index):
        va = CONV_MENU_PARTS + index * 16
        for start, off, size in segments:
            if start <= va < start + size:
                return struct.unpack_from('<8h', lib, off + va - start)
        raise ValueError(hex(va))
    return entry


def text_layer(button):
    layer = Image.new('RGBA', button.size)
    for y in range(*TEXT_ROWS):
        for x in range(*TEXT_COLS):
            p = button.getpixel((x, y))
            if p[3] and max(p[:3]) > DARK:
                layer.putpixel((x, y), p)
    return layer


def split_glyphs(layer, cuts=()):
    cols = [x for x in range(*TEXT_COLS) if any(layer.getpixel((x, y))[3] for y in range(*TEXT_ROWS))]
    runs = []
    for x in cols:
        if runs and x == runs[-1][1] + 1 and x not in cuts:
            runs[-1][1] = x
        else:
            runs.append([x, x])
    return [(a, b + 1) for a, b in runs]


def row_colors(layer):
    """每行出现最多的文字颜色（字母主体的竖向渐变）。"""
    result = []
    for y in range(*TEXT_ROWS):
        count = {}
        for x in range(*TEXT_COLS):
            p = layer.getpixel((x, y))
            if p[3]:
                count[p[:3]] = count.get(p[:3], 0) + 1
        result.append('#%02x%02x%02x' % max(count, key=count.get) if count else None)
    return result


def main():
    entry = conv_table()
    atlases = {k: obm(v) for k, v in ATLASES.items()}
    buttons = {}
    sources = {}
    for index, name in NATIVE.items():
        x, y, w, h, _, _, _, page = entry(index)
        if (w, h) != (60, 48):
            raise ValueError(f'ConvMenuParts {index} 不是 60×48')
        buttons[name] = atlases[page].crop((x, y, x + w, y + h))
        sources[name] = {'conv_menu_parts': index, 'atlas': ATLASES[page], 'rect': [x, y, w, h]}
    for name, path in EXTRA.items():
        buttons[name] = Image.open(path).convert('RGBA')
        sources[name] = {'file': str(path.relative_to(ROOT)).replace('\\', '/'), 'native': False}
    for sub in ('buttons', 'labels', 'labels_tight', 'glyphs'):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    manifest = {}
    glyph_rows = []
    for name, button in buttons.items():
        word = name.split('_')[0]
        layer = text_layer(button)
        box = layer.getbbox()
        button.save(OUT / 'buttons' / f'{name}.png')
        layer.save(OUT / 'labels' / f'{name}.png')
        layer.crop((box[0], TEXT_ROWS[0], box[2], TEXT_ROWS[1])).save(OUT / 'labels_tight' / f'{name}.png')
        runs = split_glyphs(layer, CUTS.get(word, ()))
        split_ok = len(runs) == len(word)
        glyph_dir = OUT / 'glyphs' / name
        glyph_dir.mkdir(exist_ok=True)
        glyphs = []
        for i, (a, b) in enumerate(runs):
            letter = word[i] if split_ok else '_'
            glyph = layer.crop((a, TEXT_ROWS[0], b, TEXT_ROWS[1]))
            glyph.save(glyph_dir / f'{i:02d}_{letter}.png')
            glyphs.append({'letter': letter, 'x': a, 'width': b - a})
        glyph_rows.append((name, [layer.crop((a, TEXT_ROWS[0], b, TEXT_ROWS[1])) for a, b in runs], word, split_ok))
        manifest[name] = dict(sources[name], text=word, text_bbox=list(box), split_ok=split_ok,
                              row_colors=row_colors(layer), glyphs=glyphs, main_menu=name in MAIN_MENU)
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')

    k = 8
    order = list(MAIN_MENU) + [n for n in buttons if n not in MAIN_MENU]
    sheet = Image.new('RGBA', (60 * k + 140, len(order) * (16 * k + 6)), (48, 48, 64, 255))
    d = ImageDraw.Draw(sheet)
    for n, name in enumerate(order):
        y = n * (16 * k + 6)
        sheet.alpha_composite(buttons[name].crop((0, 32, 60, 48)).resize((60 * k, 16 * k), Image.NEAREST), (0, y))
        d.text((60 * k + 8, y + 8), name + (' *' if name in MAIN_MENU else ''), fill=(255, 255, 255, 255))
    sheet.save(OUT / 'preview_labels_x8.png')

    width = max(sum(g.width + 2 for g in gl) for _, gl, _, _ in glyph_rows) * k + 140
    sheet = Image.new('RGBA', (width, len(glyph_rows) * (6 * k + 22)), (0, 0, 0, 255))
    d = ImageDraw.Draw(sheet)
    for n, (name, gl, word, ok) in enumerate(glyph_rows):
        y = n * (6 * k + 22)
        d.text((4, y + 2), name + ('' if ok else '  (split mismatch)'), fill=(255, 255, 0, 255))
        x = 4
        for g in gl:
            sheet.alpha_composite(g.resize((g.width * k, g.height * k), Image.NEAREST), (x, y + 16))
            x += (g.width + 2) * k
    sheet.save(OUT / 'preview_glyphs_x8.png')
    for name in order:
        m = manifest[name]
        print(f"{name:14s} split_ok={m['split_ok']!s:5s} bbox={m['text_bbox']} widths={[g['width'] for g in m['glyphs']]}")


if __name__ == '__main__':
    main()
