"""多语言文本的补全规则（模组 M6b，2026-10-10 用户确认）：本体与模组的单位、组合包、EVENT 共用。

- 只填写一种语言时，全部语言使用该文本；
- 填写了部分语言时，未填写的语言使用英语；未填写英语时使用作者填写的第一种语言。
"""

LANGUAGES = ('EN', 'JP', 'KR', 'ES', 'PT', 'RU', 'FR', 'DE', 'IT', 'ZT', 'ZS')


def fill(texts, what='text'):
    """texts：语言代码 → 值（字符串或对象），按上述规则补全为 11 种语言；未知语言代码或空值报错。"""
    if not isinstance(texts, dict) or not texts:
        raise ValueError(f'{what} requires at least one language')
    unknown = set(texts) - set(LANGUAGES)
    if unknown:
        raise ValueError(f'{what} has unknown language codes: ' + ', '.join(sorted(unknown)))
    if any(value in (None, '', {}) for value in texts.values()):
        raise ValueError(f'{what} has an empty language entry')
    if len(texts) == len(LANGUAGES):
        return dict(texts)                       # 已完整：保持原顺序（安装时按此顺序写入字符串）
    fallback = texts['EN'] if 'EN' in texts else next(iter(texts.values()))
    return {code: texts.get(code, fallback) for code in LANGUAGES}


def language_codes(p):
    """原生语言编号（app+0x3d64）→ 语言代码，依据原生单位文字表 strMenuUnitInfoTbl 的排列。"""
    table = p.symbols['strMenuUnitInfoTbl']
    order = {p.word(table + i * 4): i for i in range(11)}
    return {order[p.symbols['strMenuUnitInfo' + code]]: code for code in LANGUAGES}


def current_code(p):
    app = p.app_instance()
    index = p.word(app + 0x3d64) if app else 0
    return language_codes(p).get(index, 'EN')
