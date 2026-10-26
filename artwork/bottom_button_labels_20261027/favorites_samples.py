"""FAVORITES 文字样张：以原生底栏字形拼字，按主菜单六种配色各出一张，叠在空白按钮上预览（U1 D26 设计参照）。

依赖 extract_labels.py 的输出（out/manifest.json、out/glyphs/）。
字形：同一字母在各词中的形状逐像素相同。字母来源：目标配色的原生词含该字母时直接取用（像素与原生相同）；
否则取 SOURCES 中的原生字母换色。LAB 不是原生按钮，六种字母全部换色。
换色：各配色由底色 b（第 42 行主色）派生。亮于底色的像素为白色与底色的混合 W + t(b − W)，按最小二乘求 t 后
换成目标底色；暗于底色的像素在 HSV 中保留目标底色的色相，明度与饱和度按源像素相对源底色的比例缩放。
排字：字距 1；FAVORITES 宽 50 列，置于 x 5–54、第 37–42 行（与 CUSTOMIZE 相同，中心 29.5）。

输出（out/favorites/）：
  FAVORITES_<配色>.png        空白按钮 + 文字，60×48
  label_<配色>.png            只含文字的 60×48 透明图层
  preview_x4.png              每行：该配色的原生按钮、FAVORITES 样张（4 倍）
  preview_labels_x8.png       文字条（第 32–47 行）8 倍
  samples.json                每个字母的来源（原生直取 / 换色及来源词）
用法：E:\\anaconda3\\python.exe -I favorites_samples.py
"""
from pathlib import Path
import colorsys
import json

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'out'
DEST = OUT / 'favorites'
BLANK = ROOT / 'custom_content' / 'u1_button_blank.png'
WORD = 'FAVORITES'
FAMILIES = ('BACK', 'OPTION', 'SHOP', 'MEDAL', 'LAB', 'MISSION')   # 主菜单底栏六项
SOURCES = {'F': 'FREE', 'A': 'BACK', 'V': 'EVENT', 'O': 'OPTION', 'R': 'SORT', 'I': 'OPTION', 'T': 'OPTION',
           'E': 'MEDAL', 'S': 'SHOP'}
NON_NATIVE = {'LAB'}
TOP = 37
WHITE = 255


def base(manifest, name):
    h = manifest[name]['row_colors'][5]
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def recolor_pixel(c, src, dst):
    if sum(c) >= sum(src):
        t = (sum((WHITE - ci) * (WHITE - bi) for ci, bi in zip(c, src))
             / sum((WHITE - bi) ** 2 for bi in src))
        return tuple(max(0, min(255, round(WHITE + t * (di - WHITE)))) for di in dst)
    _, sb, vb = colorsys.rgb_to_hsv(*(x / 255 for x in src))
    _, sc, vc = colorsys.rgb_to_hsv(*(x / 255 for x in c))
    hd, sd, vd = colorsys.rgb_to_hsv(*(x / 255 for x in dst))
    s = min(1.0, sd * (sc / sb if sb else 1.0))
    return tuple(max(0, min(255, round(x * 255))) for x in colorsys.hsv_to_rgb(hd, s, vd * vc / vb))


def recolor(glyph, src, dst):
    out = glyph.copy()
    for y in range(glyph.height):
        for x in range(glyph.width):
            p = glyph.getpixel((x, y))
            if p[3]:
                out.putpixel((x, y), recolor_pixel(p[:3], src, dst) + (p[3],))
    return out


def glyph(manifest, word, letter):
    for i, g in enumerate(manifest[word]['glyphs']):
        if g['letter'] == letter:
            return Image.open(OUT / 'glyphs' / word / f'{i:02d}_{letter}.png').convert('RGBA')
    return None


def compose(manifest, family):
    pieces, record = [], []
    for letter in WORD:
        own = None if family in NON_NATIVE else glyph(manifest, family, letter)
        if own is not None:
            pieces.append(own)
            record.append({'letter': letter, 'from': family, 'recolored': False})
        else:
            source = SOURCES[letter]
            pieces.append(recolor(glyph(manifest, source, letter), base(manifest, source), base(manifest, family)))
            record.append({'letter': letter, 'from': source, 'recolored': True})
    width = sum(p.width for p in pieces) + len(pieces) - 1
    x = round(29.5 - (width - 1) / 2)
    layer = Image.new('RGBA', (60, 48))
    for p in pieces:
        layer.alpha_composite(p, (x, TOP))
        x += p.width + 1
    return layer, record


def main():
    manifest = json.loads((OUT / 'manifest.json').read_text(encoding='utf-8'))
    DEST.mkdir(parents=True, exist_ok=True)
    blank = Image.open(BLANK).convert('RGBA')
    samples, report = {}, {}
    for family in FAMILIES:
        layer, record = compose(manifest, family)
        button = blank.copy()
        button.alpha_composite(layer)
        layer.save(DEST / f'label_{family}.png')
        button.save(DEST / f'FAVORITES_{family}.png')
        samples[family] = button
        report[family] = {'base': manifest[family]['row_colors'][5], 'text_bbox': list(layer.getbbox()),
                          'letters': record}
    (DEST / 'samples.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')

    k, gap = 4, 16
    sheet = Image.new('RGBA', (2 * 60 * k + 3 * gap + 90, len(FAMILIES) * (48 * k + gap) + gap), (48, 48, 64, 255))
    d = ImageDraw.Draw(sheet)
    for n, family in enumerate(FAMILIES):
        y = gap + n * (48 * k + gap)
        native = Image.open(OUT / 'buttons' / f'{family}.png').convert('RGBA')
        sheet.alpha_composite(native.resize((60 * k, 48 * k), Image.NEAREST), (gap, y))
        sheet.alpha_composite(samples[family].resize((60 * k, 48 * k), Image.NEAREST), (2 * gap + 60 * k, y))
        d.text((3 * gap + 120 * k, y + 8), family, fill=(255, 255, 255, 255))
    sheet.save(DEST / 'preview_x4.png')

    k = 8
    sheet = Image.new('RGBA', (60 * k + 100, len(FAMILIES) * 2 * (16 * k + 4)), (48, 48, 64, 255))
    d = ImageDraw.Draw(sheet)
    for n, family in enumerate(FAMILIES):
        native = Image.open(OUT / 'buttons' / f'{family}.png').convert('RGBA')
        for j, im in enumerate((native, samples[family])):
            y = (2 * n + j) * (16 * k + 4)
            sheet.alpha_composite(im.crop((0, 32, 60, 48)).resize((60 * k, 16 * k), Image.NEAREST), (0, y))
            d.text((60 * k + 8, y + 8), family if j == 0 else 'FAVORITES', fill=(255, 255, 255, 255))
    sheet.save(DEST / 'preview_labels_x8.png')
    for family in FAMILIES:
        own = ''.join(r['letter'] for r in report[family]['letters'] if not r['recolored'])
        print(f"{family:8s} bbox={report[family]['text_bbox']} native letters={own or '-'}")


if __name__ == '__main__':
    main()
