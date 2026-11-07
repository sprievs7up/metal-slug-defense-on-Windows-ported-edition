"""2026-11-07：界面标题图（16 行原生标题字体，与 CUSTOMIZE / SHOP 等原生标题同一字号）。

用途：单位强化 / 商店界面标题的 UNIT（unit_browser.py，原为商店卡片标签的 12 行 UNIT），LAB 系准备界面顶栏的英文标题（lab_ui.py）。
排字同 make_titles.py：每个字母取原生实例（按左右邻字选取），字距取原生同字母对众数，否则取该字号默认值；
单词间距为原生两词标题（MEDAL SHOP、PAUSE MENU、POW LIST、Wi-Fi VERSUS）的填充间距 7 列；VERSUS 用 profile.obm 的原生整词像素。
输出 titles/<标题，空格写作 _>_16.png：第 0–1 行为空行，第 2 行为上轮廓，第 3–18 行为填充；首字母填充左列为第 3 列。
报告 titles/ui_titles_report.json（每个字母所用实例、是否拼接字形、字距来源、填充范围）。
用法：windows_runtime\\python.exe -I make_ui_titles.py（在本目录运行；PIL 经 native_font 导入）
"""
from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from native_font import load_db, word_reference, Image  # noqa: E402
from make_titles import typeset  # noqa: E402

SIZE = 16
WORD_GAP = 7
TITLES = ['UNIT', 'LAB SETUP', 'VERSUS SETUP', 'VS CPU', 'SELECT UNIT', 'CONTROLS', 'HOW TO PLAY', 'HISTORY']


def word_image(db, imgs, word):
    """(图像, 填充左列, 填充右列, 报告)。"""
    if word == 'VERSUS':
        w = next(w for w in db['words'] if w['text'] == 'VERSUS')
        gs = [db['glyphs'][g] for g in w['glyphs']]
        ox = gs[0]['abs_x'] + gs[0]['fl'] - 3
        return (word_reference(db, imgs, w), 3, gs[-1]['abs_x'] + gs[-1]['fr'] - ox,
                {'word': word, 'source': w['key'], 'native_word': True})
    img, used, pos, gap_src = typeset(db, imgs, word, SIZE)
    return (img, pos[0] + db['glyphs'][used[0]]['fl'], pos[-1] + db['glyphs'][used[-1]]['fr'],
            {'word': word, 'glyphs': used, 'gaps_from': gap_src,
             'composite_letters': [db['glyphs'][g]['ch'] for g in used if db['glyphs'][g].get('composite')]})


def title_image(db, imgs, text):
    parts = [word_image(db, imgs, w) for w in text.split(' ')]
    xs, x = [], 0
    for k, (img, fl, fr, _) in enumerate(parts):
        if k:
            prev_img, prev_fl, prev_fr, _ = parts[k - 1]
            x = xs[-1] + prev_fr + 1 + WORD_GAP - fl
        xs.append(x)
    width = max(x + img.width for x, (img, *_) in zip(xs, parts))
    height = max(img.height for img, *_ in parts)
    out = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    for x, (img, *_) in zip(xs, parts):
        out.alpha_composite(img, (x, 0))
    fill = [parts[0][1] + xs[0], parts[-1][2] + xs[-1]]
    return out, {'words': [r for *_, r in parts], 'word_x': xs, 'fill_columns': fill, 'size': [width, height]}


def main():
    db, imgs = load_db(with_composites=True)
    out = HERE / 'titles'
    report = {'size': SIZE, 'word_gap': WORD_GAP}
    for text in TITLES:
        img, info = title_image(db, imgs, text)
        name = text.replace(' ', '_') + f'_{SIZE}'
        img.save(out / (name + '.png'))
        report[name] = info
        print(name, info['size'], 'composite:', sum((w.get('composite_letters') or [] for w in info['words']), []))
    (out / 'ui_titles_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
