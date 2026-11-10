"""Local Windows font selection shared by JNI measurements and rasterization."""
from pathlib import Path
import os
from functools import lru_cache
from PIL import ImageFont

FONT_DIR = Path(os.environ['SystemRoot']) / 'Fonts'
# These installed font files were checked against all exported JP/KR/ZT text.
LANGUAGE_FONTS = {1: ('msgothic.ttc', 'msjh.ttc', 'msyh.ttc', 'arial.ttf'),
                  2: ('malgun.ttf',),
                  9: ('msjh.ttc', 'msyh.ttc', 'mingliu.ttc', 'arial.ttf'),
                  10: ('msyh.ttc', 'msjh.ttc', 'mingliu.ttc', 'arial.ttf')}
KOREAN_FALLBACK = frozenset('\u2010\u30fb')
# 所选字体缺少字形的字符（例：英语等语言文字中的全角“：”“％”，Arial 无此字形，画出来是方框）依次在这些已安装的字体中
# 查找（2026-11-11）；都没有时仍用所选字体。行高与基线仍按所选字体，不随回退字体变化。
GLYPH_FALLBACKS = ('msjh.ttc', 'msyh.ttc', 'msgothic.ttc', 'malgun.ttf', 'seguisym.ttf', 'arial.ttf')


def glyph_signature(font, character):
    mask = font.getmask(character)
    return mask.size, mask.getbbox(), bytes(mask) if mask.size[0] and mask.size[1] else b''


def has_glyph(font, character):
    """字体是否有该字符的字形：与未定义字形（以 U+FFFF 取得）的栅格比较；结果按字体缓存。"""
    cache = font.__dict__.setdefault('msd_glyphs', {})
    known = cache.get(character)
    if known is None:
        if character.isspace() or not character.isprintable():
            known = True
        else:
            if 'missing' not in cache:
                cache['missing'] = glyph_signature(font, '\uffff')
            known = glyph_signature(font, character) != cache['missing']
        cache[character] = known
    return known

class FontLayout:
    def __init__(self, primary, fallback=None, extra_paths=(), size=0):
        self.primary, self.fallback = primary, fallback
        metrics = [font.getmetrics() for font in (primary, fallback) if font is not None]
        self.metrics = max(v[0] for v in metrics), max(v[1] for v in metrics)
        self.extra_paths, self.size = tuple(extra_paths), size
        self.extras = None                 # 缺字回退的字体，首次遇到缺字时载入
        self.choice = {}                   # 字符 → 所用字体

    def font_of(self, character):
        font = self.choice.get(character)
        if font is None:
            if self.fallback is not None and character in KOREAN_FALLBACK:
                font = self.fallback
            elif has_glyph(self.primary, character):
                font = self.primary
            else:
                if self.extras is None:
                    self.extras = ([self.fallback] if self.fallback is not None else []) + [
                        ImageFont.truetype(str(path), self.size, index=0) for path in self.extra_paths]
                font = next((extra for extra in self.extras if has_glyph(extra, character)), self.primary)
            self.choice[character] = font
        return font

    def getmetrics(self):
        return self.metrics

    def runs(self, text):
        runs = []
        for character in text:
            font = self.font_of(character)
            if runs and runs[-1][0] is font:
                runs[-1] = font, runs[-1][1] + character
            else:
                runs.append((font, character))
        return runs

    @lru_cache(maxsize=2048)
    def getlength(self, text):
        return sum(font.getlength(run) for font, run in self.runs(text))

    def draw(self, draw, position, text, **kwargs):
        x, y = position
        for font, run in self.runs(text):
            draw.text((x, y), run, font=font, anchor='ls', **kwargs)
            x += font.getlength(run)

def font_for(probe, size, language):
    selection_key=language,int(size)
    selected=getattr(probe,'font_selection',None)
    if selected is None:probe.font_selection=selected={}
    if selection_key in selected:return selected[selection_key]
    names = LANGUAGE_FONTS.get(language, ('arial.ttf',))
    primary_path = next((FONT_DIR / name for name in names if (FONT_DIR / name).is_file()), None)
    if primary_path is None:
        raise RuntimeError('Required Windows font is unavailable: ' + ', '.join(names))
    fallback_path = None
    if language == 2 and primary_path.name.lower() == 'malgun.ttf':
        fallback_path = next((FONT_DIR / name for name in ('msjh.ttc', 'msyh.ttc', 'msgothic.ttc')
                              if (FONT_DIR / name).is_file()), None)
    key = language, str(primary_path), str(fallback_path), int(size)
    if not hasattr(probe, 'fonts'):
        probe.fonts = {}
    if key not in probe.fonts:
        primary = ImageFont.truetype(str(primary_path), size, index=0)
        fallback = ImageFont.truetype(str(fallback_path), size, index=0) if fallback_path else None
        extras = [FONT_DIR / name for name in GLYPH_FALLBACKS
                  if (FONT_DIR / name).is_file() and FONT_DIR / name not in (primary_path, fallback_path)]
        probe.fonts[key] = FontLayout(primary, fallback, extras, size)
        probe.log('FONT_SELECTED', language, size, primary_path.name,
                  fallback_path.name if fallback_path else None)
    selected[selection_key]=probe.fonts[key]
    return selected[selection_key]
