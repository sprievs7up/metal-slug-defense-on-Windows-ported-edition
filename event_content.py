"""自制 EVENT（模组 M6b-1）：可编写的 EVENT 数据格式、校验，以及编译为原生 EventMSD 流程使用的表。

来源：
- 本体：community_content/events/*.json（键 "s1xlv."；图片放在同一目录）。
- 模组：mod.json 的 content.events 目录中的 *.json（键 "<模组 id>."；图片为模组资源 assets/<模组 id>_*）。

格式（schema 1）：
{
  "schema": 1, "key": "author_mod.summer", "mode": "clear_reward",
  "names": {"EN": "...", "ZS": "..."},            名称（语言补全见 content_locale.py）
  "details": {"EN": "..."},                        可选：细则正文
  "publisher": "author", "date": "2026-10-10",     细则中的发行者与日期；浏览页按日期排序
  "order": 0,                                      可选：同日排序
  "image": "author_mod_summer.png",                可选：360×240 的 PNG/WebP 左屏图（缺省时生成文字卡）
  "areas": [                                       1–16 个区域
    {"key": "author_mod.summer.a1", "names": {...}, "position": [x, y],
     "stages": [                                   每区域 1–5 个小关
       {"key": "author_mod.summer.a1.s1", "marker": [dx, dy], "preview_frame": 0,
        "template": 1011, "scene": 0 或场景键, "music": 107 或 bgm 音效键,
        "stamina": 10, "reward_msp": 50, "enemy_base_hp": 3000, "strength_steps": 0,
        "enemies": [{"unit": 2 或单位键, "level": 10}], "waves": [{"tick": 30, "enemy": 0}],
        "reward_units": [单位键或 1–399]}]}]
}

自制地图（M6b-2，按猫咪大战争的局部适配方式）：
  "map": {"image": "author_mod_summer_map.png"}    可选：1440×709 的地图底图，替换原生活动地图的世界地图图层
  小关 "thumbnail": "author_mod_summer_s1.png"      可选：128×56 的小关缩略图（关卡信息窗口）
  地图坐标：区域 position 为世界地图图层（1440×709）上的像素坐标；区域总览以约 0.6529 倍绘制于 (9.9, 71.6)。

人质类玩法（M6b-3）：
  小关 "prisoners": 0–10                            该关俘虏数（原生关卡记录词 7，地图标记的上限）
  区域 "reward": {"unit": 单位, "portrait": 0–40, "names": {...}, "info1": {...}, "info2": {...}}
                                                    区域俘虏奖励（俘虏页的人物、名称与说明；portrait 为原生俘虏图像编号）
  EVENT "final_reward_units": [单位, ...]            parts 收齐全部零件、invitation 收齐全部邀请函时给予
  - rescue / collaboration_rescue：区域内各关救出的俘虏合计达到上限时给予该区域奖励单位（原生俘虏页显示达成）。
    collaboration_rescue 为猫咪联动的救人质玩法；自制版本使用经典地图路由与自制地图（猫咪专用两页地图未采用）。
  - parts：每个区域为一个零件（reward 不写 unit），区域内任一关救出全部俘虏即获得该零件；全部零件到齐给予 final_reward_units。
  - invitation：各关的俘虏为邀请函，全部救出给予 final_reward_units。含邀请函的区域自动生成俘虏页记录（不给单位，
    缺省名称“邀请函”；可用 reward 的 names、info1、info2、portrait 改写），原生俘虏页显示收集进度。

积分与商店类玩法（M6b-4）：
  legacy_survival：经原生 Survival 路由（WorldType 3、模式 5，关卡编号 61000+10×(区域+1)+小关+1）战斗，战斗所得为活动代币；
    "survival": {"template": "treasure_recovery_2015" | "melty_christmas_2015"}，每关的 Survival 记录（得分与掉落规则）
    取模板活动的第 "survival_row" 行（缺省为小关序号），掉落表取模板活动；战斗左下的拾取物图标随模板（金币或星形）。
  current_cooperation：经原生合作路由（WorldType 4、模式 6，离线合作编队），所得为合作积分；Survival 记录取原生合作表的
    第 survival_row 行。联机合作属 M7。
  "shop": [{"type": "unit"|"msp"|"medal"|"item", "unit": 单位, "item": ItemID, "amount": n, "price": 代币, "limit": n}]
    代币兑换店（legacy_survival、current_cooperation），使用历史活动商店的原生商品：单位商品取 31 个原生单位商品编号；
    msp 为原生面额 10000/50000/100000（不限次数，与历史活动相同），medal 为 10/30/50/100，item 为六阵营核心（ItemID 8–13，
    各 1 个）；同一商品只能列一次。自制商品在兑换店中始终开放（核心 r42 起）。
  "medal_shop": [{"unit": 单位, "price": 勋章, "available": "event" | {"stage": 小关键} | {"score": 积分}}]
    活动勋章商店（任何模式；女教官基地底栏 SHOP），所列单位只在该活动的勋章商店出售（与历史活动相同）。
  "part1": {"areas": k, "shop": m, "names": {...}, "date": "...", "image": "..."}
    分期（与历史活动的 PART1/PART2 相同）：PART1 为前 k 个区域与前 m 个兑换商品，PART2 为完整 EVENT；
    浏览页显示两个入口，进度、代币与购买次数共用。names 缺省为 EVENT 名称加 “(PART1)”，date、image 缺省同 EVENT。

运行（M6b-1）：所有自制 EVENT 经女教官基地进入原生 EventMSD 地图（经典活动路由：WorldType 1、模式 3、原生世界 4，
与万圣节相同，不触发专用画面）。关卡编号为 30000+1000×4+10×(区域+1)+小关+1，宿主按活动独立建表（选择活动时生效），
进度按关卡稳定键保存于 historical_event_progress.json。地图背景、区域与小关标记的其余字段取万圣节记录为模板；
自制地图图集与缩略图为 M6b-2。目前只支持 mode "clear_reward"；其他模式（M6b-3/4）校验时给出原因。
"""
from pathlib import Path
import json
import re
import struct

import content_locale

SCHEMA = 1
MODES = ('clear_reward', 'rescue', 'parts', 'collaboration_rescue', 'invitation', 'legacy_survival', 'current_cooperation')
SUPPORTED_MODES = frozenset(MODES)
SURVIVAL_MODES = frozenset(('legacy_survival', 'current_cooperation'))
SURVIVAL_TEMPLATES = {'treasure_recovery_2015': 'coin', 'melty_christmas_2015': 'star'}
SHOP_TYPES = {'item': (0, 'melty_christmas_2015', 289), 'msp': (1, 'treasure_recovery_2015', 299),
              'unit': (2, 'treasure_recovery_2015', 262), 'medal': (3, 'treasure_recovery_2015', 295)}
# 原生商品编号与内容绑定（历史活动商店核对）：MSP 299–301、勋章 295–298、阵营核心 289–294（ItemID 8–13）。
NATIVE_PACKS = {'msp': {10000: 299, 50000: 300, 100000: 301}, 'medal': {10: 295, 30: 296, 50: 297, 100: 298},
                'item': {8: 289, 9: 290, 10: 291, 11: 292, 12: 293, 13: 294}}
SHOP_POOL_EVENTS = ('treasure_recovery_2015', 'melty_christmas_2015', 'cooperation_2016_current')
PRISONER_MODES = frozenset(('rescue', 'collaboration_rescue', 'parts', 'invitation'))
# 自制俘虏编号（区域记录 +16，int16）：原生地图与俘虏页钩子按活动内的俘虏表回应；200+区域序号，避开原生 0–69。
PRISONER_BASE = 200
DEFAULT_INFO = {'info1': {'EN': 'Rescue all prisoners', 'ZT': '只要解放所有俘虜', 'ZS': '只要解放所有俘虏', 'JP': '捕虜を全員解放すると'},
                'info2': {'EN': 'to unlock this reward!', 'ZT': '就能獲得獎勵！', 'ZS': '就能获得奖励！', 'JP': '報酬を獲得できる！'}}
INVITATION_NAMES = {'EN': 'Invitation', 'ZT': '邀請函', 'ZS': '邀请函', 'JP': '招待状'}
CUSTOM_WORLD = 4
STAGE_BASE = 30000
TEMPLATE_EVENT = 'halloween_2015'
IMAGE_SIZE = (360, 240)
MAX_AREAS, MAX_STAGES_PER_AREA = 16, 5
DATE_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}')
EVENT_FIELDS = {'schema', 'key', 'mode', 'names', 'details', 'publisher', 'date', 'order', 'image', 'map', 'areas',
                'final_reward_units', 'survival', 'shop', 'medal_shop', 'part1'}
AREA_FIELDS = {'key', 'names', 'position', 'stages', 'reward'}
STAGE_FIELDS = {'key', 'marker', 'preview_frame', 'template', 'scene', 'music', 'stamina', 'reward_msp', 'enemy_base_hp',
                'strength_steps', 'enemies', 'waves', 'reward_units', 'thumbnail', 'prisoners', 'survival_row'}
# 自制地图（M6b-2）：原生 EventMSD 地图的世界地图图层由两个转换项组成（GraphicsOpt::drawConv 记录，
# verification/m6b1_20261010/diag_draw.py）：0x10306ab4 为 (0,0) 起 823×680，0x10306ac4 为 617×709、锚点 x −823，
# 合成 1440×709；区域总览以约 0.6529 倍绘制于 (9.9, 71.6)，区域放大时同一图层放大。小关缩略图为 128×56，
# 万圣节缩略图组（区域记录 +12 = 34）的预览帧 f 使用转换项 0x10307bde + 16·f。宿主以 drawConv 替换表
# （LAB 头部 +0xb40，与浏览页、VERSUS 页共用，各在自身场景写入）换入作者图像，位置与缩放沿用原生绘制。
MAP_SIZE = (1440, 709)
MAP_CONVS = (0x10306ab4, 0x10306ac4)
THUMB_SIZE = (128, 56)
THUMB_CONV_BASE = 0x10307bde
REPLACE_MAGIC = 0x47505356


def body_dir(root):
    return Path(root) / 'community_content' / 'events'


def integer(value, low, high, what):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{what} must be an integer {low}–{high}')
    return value


def check_key(key, prefix, what):
    if not isinstance(key, str) or not key.startswith(prefix + '.') or len(key) > 128 or '\0' in key or len(key) <= len(prefix) + 1:
        raise ValueError(f'{what} key {key!r} must start with "{prefix}."')


def check_event(raw, prefix, resolve):
    """静态检查（不依赖其他内容）；返回补全语言后的副本。resolve(文件名) 返回资源路径或 None。"""
    if not isinstance(raw, dict) or raw.get('schema') != SCHEMA:
        raise ValueError('event files need "schema": 1')
    unknown = set(raw) - EVENT_FIELDS
    if unknown:
        raise ValueError('unknown event fields: ' + ', '.join(sorted(unknown)))
    event = json.loads(json.dumps(raw))
    check_key(event.get('key'), prefix, 'event')
    key = event['key']
    if event.get('mode') not in MODES:
        raise ValueError(f'{key}: mode must be one of ' + ', '.join(MODES))
    if event['mode'] not in SUPPORTED_MODES:
        raise ValueError(f'{key}: mode {event["mode"]} is not supported yet (M6b-1 supports clear_reward)')
    event['names'] = content_locale.fill(event.get('names'), f'{key} names')
    if any(not isinstance(v, str) or '\0' in v or len(v) > 64 for v in event['names'].values()):
        raise ValueError(f'{key}: names must be text up to 64 characters')
    if 'details' in event:
        event['details'] = content_locale.fill(event['details'], f'{key} details')
        if any(not isinstance(v, str) or '\0' in v or len(v) > 400 for v in event['details'].values()):
            raise ValueError(f'{key}: details must be text up to 400 characters')
    if not isinstance(event.get('publisher'), str) or not event['publisher'] or len(event['publisher']) > 64:
        raise ValueError(f'{key}: publisher is required')
    if not isinstance(event.get('date'), str) or not DATE_PATTERN.fullmatch(event['date']):
        raise ValueError(f'{key}: date must be YYYY-MM-DD')
    integer(event.get('order', 0), -1000000, 1000000, f'{key} order')
    if 'image' in event:
        name = event['image']
        if not isinstance(name, str) or Path(name).name != name or Path(name).suffix.lower() not in ('.png', '.webp'):
            raise ValueError(f'{key}: image must be a .png or .webp file name')
        source = resolve(name)
        if source is None:
            raise ValueError(f'{key}: missing image {name}')
        from PIL import Image
        with Image.open(source) as image:
            if image.size != IMAGE_SIZE:
                raise ValueError(f'{key}: image must be 360×240 (got {image.size[0]}×{image.size[1]})')
        event['image_path'] = str(source)
    if 'map' in event:
        art = event['map']
        if not isinstance(art, dict) or set(art) != {'image'}:
            raise ValueError(f'{key}: map is {{"image": file}}')
        event['map_path'] = str(check_image(art['image'], resolve, MAP_SIZE, f'{key} map image'))
    areas = event.get('areas')
    if not isinstance(areas, list) or not 1 <= len(areas) <= MAX_AREAS:
        raise ValueError(f'{key}: areas must list 1–{MAX_AREAS} areas (original EventMSD capacity)')
    seen = set()
    mode = event['mode']
    finals = event.get('final_reward_units', [])
    if not isinstance(finals, list) or len(finals) > 8:
        raise ValueError(f'{key}: final_reward_units lists up to 8 units')
    for unit in finals:
        check_unit_ref(unit, key)
    if finals and mode not in ('parts', 'invitation'):
        raise ValueError(f'{key}: final_reward_units is used by parts and invitation events')
    for area in areas:
        if not isinstance(area, dict) or set(area) - AREA_FIELDS:
            raise ValueError(f'{key}: areas contain key, names, position and stages')
        check_key(area.get('key'), key, 'area')
        area['names'] = content_locale.fill(area.get('names'), f'{area["key"]} names')
        if any(not isinstance(v, str) or '\0' in v or len(v) > 48 for v in area['names'].values()):
            raise ValueError(f'{area["key"]}: names must be text up to 48 characters')
        position = area.get('position')
        if not (isinstance(position, list) and len(position) == 2):
            raise ValueError(f'{area["key"]}: position is [x, y]')
        # 区域坐标为世界地图图层（MAP_SIZE）上的像素位置（原生区域记录同一坐标系，如万圣节 (1175, 300)）。
        integer(position[0], 0, MAP_SIZE[0], f'{area["key"]} position x')
        integer(position[1], 0, MAP_SIZE[1], f'{area["key"]} position y')
        stages = area.get('stages')
        if not isinstance(stages, list) or not 1 <= len(stages) <= MAX_STAGES_PER_AREA:
            raise ValueError(f'{area["key"]}: stages must list 1–{MAX_STAGES_PER_AREA} stages (original marker capacity)')
        for stage in stages:
            check_stage(stage, area['key'])
            if 'thumbnail' in stage:
                stage['thumbnail_path'] = str(check_image(stage['thumbnail'], resolve, THUMB_SIZE, f'{stage["key"]} thumbnail'))
        check_area_reward(area, mode)
        if mode not in PRISONER_MODES and any(s.get('prisoners', 0) for s in stages):
            raise ValueError(f'{area["key"]}: prisoners are used by rescue, collaboration_rescue, parts and invitation events')
        for item in [area] + stages:
            if item['key'] in seen:
                raise ValueError(f'duplicate key {item["key"]}')
            seen.add(item['key'])
    check_shops(event, mode)
    check_part1(event, resolve)
    stage_keys = {s["key"] for a in event["areas"] for s in a["stages"]}
    for row in event.get('medal_shop', []):
        if isinstance(row.get('available'), dict) and 'stage' in row['available'] and row['available']['stage'] not in stage_keys:
            raise ValueError(f'{key}: medal_shop stage {row["available"]["stage"]} is not a stage of this event')
    return event


def check_part1(event, resolve):
    part = event.get('part1')
    if part is None:
        return
    key = event['key']
    if not isinstance(part, dict) or set(part) - {'areas', 'shop', 'names', 'date', 'image'}:
        raise ValueError(f'{key}: part1 contains areas, shop, names, date and image')
    integer(part.get('areas'), 1, len(event['areas']) - 1, f'{key} part1 areas (PART2 is the whole event)')
    integer(part.get('shop', 0), 0, len(event.get('shop', [])), f'{key} part1 shop')
    part['names'] = content_locale.fill(part['names'], f'{key} part1 names') if 'names' in part else \
        {code: text + ' (PART1)' for code, text in event['names'].items()}
    if 'date' in part and (not isinstance(part['date'], str) or not DATE_PATTERN.fullmatch(part['date'])):
        raise ValueError(f'{key}: part1 date must be YYYY-MM-DD')
    if 'image' in part:
        part['image_path'] = str(check_image(part['image'], resolve, IMAGE_SIZE, f'{key} part1 image'))


def check_image(name, resolve, size, what):
    if not isinstance(name, str) or Path(name).name != name or Path(name).suffix.lower() not in ('.png', '.webp'):
        raise ValueError(f'{what} must be a .png or .webp file name')
    source = resolve(name)
    if source is None:
        raise ValueError(f'{what}: missing file {name}')
    from PIL import Image
    with Image.open(source) as image:
        if image.size != size:
            raise ValueError(f'{what} must be {size[0]}×{size[1]} (got {image.size[0]}×{image.size[1]})')
    return source


def check_shops(event, mode):
    key = event['key']
    survival = event.get('survival')
    if mode == 'legacy_survival':
        if not isinstance(survival, dict) or set(survival) != {'template'} or survival['template'] not in SURVIVAL_TEMPLATES:
            raise ValueError(f'{key}: survival is {{"template": ' + ' | '.join(SURVIVAL_TEMPLATES) + '}')
    elif survival is not None:
        raise ValueError(f'{key}: survival is used by legacy_survival events')
    shop = event.get('shop', [])
    if shop and mode not in SURVIVAL_MODES:
        raise ValueError(f'{key}: the token exchange shop is used by legacy_survival and current_cooperation events')
    if not isinstance(shop, list) or len(shop) > 40:
        raise ValueError(f'{key}: shop lists up to 40 items')
    for item in shop:
        if not isinstance(item, dict) or item.get('type') not in SHOP_TYPES or set(item) - {'type', 'unit', 'item', 'amount', 'price', 'limit'}:
            raise ValueError(f'{key}: shop items contain type (unit, msp, medal, item), unit, item, amount, price and limit')
        if item['type'] == 'unit':
            check_unit_ref(item.get('unit'), key)
            if 'item' in item or item.get('amount', 1) != 1 or item.get('limit', 1) != 1:
                raise ValueError(f'{key}: unit items have amount 1 and limit 1')
        elif 'unit' in item:
            raise ValueError(f'{key}: only unit items name a unit')
        if item['type'] == 'item':
            if item.get('item') not in NATIVE_PACKS['item'] or item.get('amount', 1) != 1:
                raise ValueError(f'{key}: item entries are army cores (ItemID 8–13), amount 1')
        elif 'item' in item:
            raise ValueError(f'{key}: only item entries name an ItemID')
        if item['type'] == 'msp' and 'limit' in item:
            raise ValueError(f'{key}: msp packs have no purchase limit (native global count)')
        if item['type'] in ('msp', 'medal') and item.get('amount') not in NATIVE_PACKS[item['type']]:
            raise ValueError(f'{key}: {item["type"]} amount must be one of ' + ', '.join(map(str, NATIVE_PACKS[item['type']])))
        integer(item.get('amount', 1), 1, 1000000, f'{key} shop amount')
        integer(item.get('price'), 0, 99999999, f'{key} shop price')
        integer(item.get('limit', 1), 1, 99999999, f'{key} shop limit')
    packs = [(i['type'], i.get('item', i.get('amount'))) for i in shop if i['type'] != 'unit']
    if len(set(packs)) != len(packs):
        raise ValueError(f'{key}: each native pack can be listed once')
    if sum(i['type'] == 'unit' for i in shop) > 31:
        raise ValueError(f'{key}: shop lists up to 31 units')
    medals = event.get('medal_shop', [])
    if not isinstance(medals, list) or len(medals) > 16:
        raise ValueError(f'{key}: medal_shop lists up to 16 units')
    for row in medals:
        if not isinstance(row, dict) or set(row) - {'unit', 'price', 'available'}:
            raise ValueError(f'{key}: medal_shop rows contain unit, price and available')
        check_unit_ref(row.get('unit'), key)
        integer(row.get('price'), 0, 32767, f'{key} medal price')
        available = row.get('available', 'event')
        if not (available == 'event' or isinstance(available, dict) and len(available) == 1 and
                (isinstance(available.get('stage'), str) or type(available.get('score')) is int)):
            raise ValueError(f'{key}: medal_shop available is "event", {{"stage": key}} or {{"score": n}}')


def check_area_reward(area, mode):
    reward = area.get('reward')
    with_prisoners = any(s.get('prisoners', 0) for s in area.get('stages', []) if isinstance(s, dict))
    if reward is None:
        if mode == 'parts':
            raise ValueError(f'{area["key"]}: every parts area is a part and needs a reward (names, portrait)')
        if mode == 'invitation' and with_prisoners:
            area['reward'] = reward = {'names': dict(INVITATION_NAMES)}
        else:
            return
    if mode not in PRISONER_MODES:
        raise ValueError(f'{area["key"]}: area rewards are used by rescue, collaboration_rescue, parts and invitation events')
    if not isinstance(reward, dict) or set(reward) - {'unit', 'portrait', 'names', 'info1', 'info2'}:
        raise ValueError(f'{area["key"]}: reward contains unit, portrait, names, info1 and info2')
    if mode in ('parts', 'invitation'):
        if 'unit' in reward:
            raise ValueError(f'{area["key"]}: {mode} areas give no unit; the unit is final_reward_units')
    else:
        check_unit_ref(reward.get('unit'), area['key'])
    integer(reward.get('portrait', 0), 0, 40, f'{area["key"]} reward portrait')
    for field in ('names', 'info1', 'info2'):
        if field == 'names' or field in reward:
            reward[field] = content_locale.fill(reward.get(field), f'{area["key"]} reward {field}')
        else:
            reward[field] = content_locale.fill(DEFAULT_INFO[field], field)
        if any(not isinstance(v, str) or '\0' in v or len(v) > 64 for v in reward[field].values()):
            raise ValueError(f'{area["key"]}: reward {field} must be text up to 64 characters')
    if not any(s.get('prisoners', 0) for s in area.get('stages', []) if isinstance(s, dict)):
        raise ValueError(f'{area["key"]}: a reward area needs at least one stage with prisoners')


def check_stage(stage, area_key):
    if not isinstance(stage, dict) or set(stage) - STAGE_FIELDS:
        raise ValueError(f'{area_key}: unknown stage fields ' + ', '.join(sorted(set(stage) - STAGE_FIELDS)) if isinstance(stage, dict) else 'stage must be an object')
    check_key(stage.get('key'), area_key, 'stage')
    k = stage['key']
    marker = stage.get('marker', [0, 0])
    if not (isinstance(marker, list) and len(marker) == 2):
        raise ValueError(f'{k}: marker is [dx, dy]')
    for v in marker:
        integer(v, -600, 600, f'{k} marker offset')
    integer(stage.get('preview_frame', 0), 0, 32, f'{k} preview_frame')
    integer(stage.get('prisoners', 0), 0, 10, f'{k} prisoners')
    integer(stage.get('survival_row', 0), 0, 63, f'{k} survival_row')
    integer(stage.get('template', 1011), 1, 999999, f'{k} template')
    scene = stage.get('scene')
    if type(scene) is int:
        integer(scene, 0, 137, f'{k} scene')
    elif not isinstance(scene, str):
        raise ValueError(f'{k}: scene is an original scene number 0–137 or a scene key')
    music = stage.get('music', 100)
    if type(music) is int:
        integer(music, 1, 1030, f'{k} music')
    elif not isinstance(music, str):
        raise ValueError(f'{k}: music is an original SoundID or a bgm sound key')
    for name, default, low, high in (('stamina', 0, 0, 1000), ('reward_msp', 0, 0, 999999),
                                     ('enemy_base_hp', 10000, 1, 100000000), ('strength_steps', 0, 0, 100)):
        integer(stage.get(name, default), low, high, f'{k} {name}')
    enemies = stage.get('enemies')
    if not isinstance(enemies, list) or not 1 <= len(enemies) <= 32:
        raise ValueError(f'{k}: enemies must list 1–32 entries')
    for enemy in enemies:
        if not isinstance(enemy, dict) or set(enemy) - {'unit', 'level'}:
            raise ValueError(f'{k}: enemies contain unit and level')
        check_unit_ref(enemy.get('unit'), k)
        integer(enemy.get('level', 40), 1, 200, f'{k} enemy level')
    waves = stage.get('waves', [])
    if not isinstance(waves, list) or len(waves) > 8192:
        raise ValueError(f'{k}: waves must list up to 8192 entries')
    previous = -1
    for wave in waves:
        if not isinstance(wave, dict) or set(wave) != {'tick', 'enemy'}:
            raise ValueError(f'{k}: waves contain tick and enemy')
        previous = integer(wave['tick'], previous + 1, 32766, f'{k} wave tick (ascending)')
        integer(wave['enemy'], 0, len(enemies) - 1, f'{k} wave enemy index')
    rewards = stage.get('reward_units', [])
    if not isinstance(rewards, list) or len(rewards) > 8:
        raise ValueError(f'{k}: reward_units lists up to 8 units')
    for unit in rewards:
        check_unit_ref(unit, k)


def check_unit_ref(value, where):
    if type(value) is int:
        integer(value, 1, 399, f'{where} original unit')
    elif not isinstance(value, str):
        raise ValueError(f'{where}: units are original UnitIDs 1–399 or unit keys')


def stages(event):
    for area in event['areas']:
        yield from area['stages']


def references(event):
    """(种类, 键)：unit、sound、scene。整数引用（原版内容）不列出。"""
    for stage in stages(event):
        for enemy in stage['enemies']:
            if isinstance(enemy['unit'], str):
                yield 'unit', enemy['unit']
        for unit in stage.get('reward_units', []):
            if isinstance(unit, str):
                yield 'unit', unit
        if isinstance(stage.get('music'), str):
            yield 'sound', stage['music']
        if isinstance(stage.get('scene'), str):
            yield 'scene', stage['scene']
    for area in event['areas']:
        if isinstance(area.get('reward', {}).get('unit'), str):
            yield 'unit', area['reward']['unit']
    for unit in event.get('final_reward_units', []):
        if isinstance(unit, str):
            yield 'unit', unit
    for row in event.get('shop', []) + event.get('medal_shop', []):
        if isinstance(row.get('unit'), str):
            yield 'unit', row['unit']


def check_references(event, units, sounds, scenes, visible):
    """units：单位键集合；sounds：音效键 → 类型；scenes：场景键集合；visible(前缀) 判断可见范围（本体、本模组、依赖）。"""
    for kind, key in references(event):
        prefix = key.split('.', 1)[0]
        known = {'unit': units, 'sound': sounds, 'scene': scenes}[kind]
        if key not in known or not visible(prefix):
            raise ValueError(f'{event["key"]}: {kind} {key} is not registered or not visible')
        if kind == 'sound' and sounds[key] != 'bgm':
            raise ValueError(f'{event["key"]}: stage music {key} must be a bgm sound')


def read_folder(folder, prefix, resolve):
    """目录中的 *.json（每个文件一个 EVENT）；返回校验后的列表。"""
    events = []
    for path in sorted(Path(folder).glob('*.json')):
        try:
            events.append(check_event(json.loads(path.read_text(encoding='utf-8')), prefix, resolve))
        except (ValueError, KeyError, TypeError, OSError) as error:
            raise ValueError(f'{path.name}: {error}')
    keys = [e['key'] for e in events]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate event keys')
    return events


def load_body(root):
    """本体 EVENT（community_content/events/）。目录不存在时为空。"""
    folder = body_dir(root)
    if not folder.is_dir():
        return []
    return [dict(e, source='body') for e in read_folder(folder, 's1xlv', lambda n: folder / n if (folder / n).is_file() else None)]


def stage_id(area, slot, mode='clear_reward'):
    if mode in SURVIVAL_MODES:
        # 原生 Survival / 合作路由（event_native_map.eventmsd_route：基数 60000，世界偏移 1）。
        return 60000 + 1000 + (area + 1) * 10 + slot + 1
    return STAGE_BASE + CUSTOM_WORLD * 1000 + (area + 1) * 10 + slot + 1


def build_mission(trial, stage, sid, ids):
    """120 字节原生关卡记录（与扩展世界 community_campaign.prepare_world 的写法相同）。"""
    p = trial.p
    source = p.call('_ZN10BattleInfo14getMissionInfoEi', trial.info, stage.get('template', 1011))
    if not source:
        raise ValueError(f'{stage["key"]}: original mission template {stage.get("template", 1011)} does not exist')
    words = list(struct.unpack('<30I', p.read(source, 120)))
    words[0] = sid
    scene = stage['scene']
    words[1] = scene if type(scene) is int else ids['scenes'][scene]
    words[4] = stage.get('enemy_base_hp', 10000)
    words[6] = stage.get('reward_msp', 0)
    words[7] = stage.get('prisoners', 0)          # 俘虏数（原生关卡记录词 7，与地图标记上限一致）
    words[8] = stage.get('stamina', 0)
    words[16] = struct.unpack('<I', struct.pack('<f', float(stage.get('strength_steps', 0))))[0]
    enemies = [(i, unit_id(e['unit'], ids), e.get('level', 40)) for i, e in enumerate(stage['enemies'])]
    words[17] = trial.blob(b''.join(struct.pack('<3i', *e) for e in enemies))
    words[18] = len(enemies)
    waves = stage.get('waves', [])
    # Enemy.update 以 -1 结束记录查找（与历史活动相同），无波次时也保留结束记录。
    words[19] = trial.blob(b''.join(struct.pack('<hbb', w['tick'], w['enemy'], 0) for w in waves) + struct.pack('<hbb', -1, 0, 0))
    words[20] = len(waves)
    for off in (21, 22, 23, 24, 28, 29):
        words[off] = 0
    return struct.pack('<30I', *words)


def unit_id(value, ids):
    return value if type(value) is int else ids['units'][value]


def compile_event(trial, event, templates, ids):
    """注册到 EventTrial：catalog、data、tables、地图清单与浏览条目。templates：万圣节的区域与小关标记原始记录。"""
    key = event['key']
    area_template, marker_template = templates
    rows, data_stages, areas = [], [], []
    art = {'map': event.get('map_path'), 'thumbs': {}}
    prisoners = {}
    index = 0
    for a, area in enumerate(event['areas']):
        raw = bytearray(area_template)
        struct.pack_into('<ii', raw, 4, *area['position'])
        pid = PRISONER_BASE + a if 'reward' in area else -1
        struct.pack_into('<hH', raw, 16, pid, len(area['stages']))
        if pid >= 0:
            reward = area['reward']
            unit = unit_id(reward['unit'], ids) if 'unit' in reward else 0xffffffff
            words = (pid, reward.get('portrait', 0), 0xffffffff, 1, unit, 0xffffffff)
            # 俘虏页文字按原生语言编号排列（prisoner_text 以语言编号取下标）。
            order = [ids['languages'][i] for i in range(11)]
            prisoners[str(pid)] = {'raw_hex': struct.pack('<6I', *words).hex(),
                                   **{field: [reward[field][code] for code in order] for field in ('names', 'info1', 'info2')}}
        markers = []
        for slot, stage in enumerate(area['stages']):
            sid = stage_id(a, slot, event['mode'])
            rows.append(build_mission(trial, stage, sid, ids))
            music = stage.get('music', 100)
            bgm = music if type(music) is int else ids['sounds'][music]
            # 自制缩略图（M6b-2）占用该小关所在格的预览帧（帧号 = 小关序号），由替换表按当前区域换入。
            frame = slot if 'thumbnail_path' in stage else stage.get('preview_frame', 0)
            if 'thumbnail_path' in stage:
                art['thumbs'].setdefault(a, {})[slot] = stage['thumbnail_path']
            marker = bytearray(marker_template)
            struct.pack_into('<iiII', marker, 0, *stage.get('marker', [0, 0]), bgm, frame)
            markers.append({'stage_id': sid, 'index': index, 'raw_hex': marker.hex(), 'bgm_id': bgm,
                            'preview_frame': frame, 'pow_max': stage.get('prisoners', 0)})
            data_stages.append({'id': sid, 'index': index, 'group': None, 'local_stage_key': stage['key'],
                                'stamina_cost': stage.get('stamina', 0),
                                'reward_units': [unit_id(u, ids) for u in stage.get('reward_units', [])]})
            index += 1
        areas.append({'world': 0, 'area': a, 'raw_hex': raw.hex(), 'prisoner_id': pid, 'markers': markers,
                      'names': area['names']})
    mode = event['mode']
    currency = 'event_points' if mode in SURVIVAL_MODES else None
    trial.data[key] = {'event_key': key, 'controller': mode, 'currency': currency, 'stages': data_stages,
                       'shop': {'rows': shop_rows(trial, event, ids)}, 'custom': True,
                       'final_reward_units': [unit_id(u, ids) for u in event.get('final_reward_units', [])],
                       'hud': SURVIVAL_TEMPLATES.get(event.get('survival', {}).get('template'))}
    trial.tables[key] = {'missions': trial.blob(b''.join(rows)), 'count': len(rows)}
    if mode in SURVIVAL_MODES:
        trial.tables[key].update(survival_tables(trial, event, [s['id'] for s in data_stages]))
    if trial.data[key]['shop']['rows']:
        trial.shop_tables[key] = build_shop_table(trial, trial.data[key]['shop']['rows'])
    trial.custom_medal_rows += medal_rows(trial, event, ids)
    trial.catalog.append({'event_key': key, 'title_zh': event['names']['ZS'], 'stage_count': len(rows),
                          'controller': event['mode'], 'currency': None, 'custom': True})
    trial.custom_maps[key] = {'world_count': 1, 'areas': areas, 'prisoners': prisoners, 'custom': True}
    if art['map'] or art['thumbs']:
        trial.custom_art[key] = art
    entry = {'event_key': key, 'date': event['date'], 'order': event.get('order', 0), 'names': event['names'],
             'details': event.get('details'), 'publisher': event['publisher'],
             'image_path': event.get('image_path'), 'source': event.get('source', 'body')}
    part = event.get('part1')
    if part is None:
        trial.custom_browse.append(entry)
        return
    # 分期（M6b-4）：沿用 event_phases 的家族结构（前缀关卡与商品，区域不拆分），两个浏览入口共用进度。
    first = [s['id'] for a in range(part['areas']) for s in data_stages if s['id'] // 10 % 100 == a + 1]
    products = [r['id'] for r in trial.data[key]['shop']['rows']]
    trial.phases.families[key] = {'progress_key': key, 'default_part2': True, 'custom': True, 'parts': {
        'part1': {'stage_ids': first, 'shop_ids': products[:part.get('shop', 0)]},
        'part2': {'stage_ids': [s['id'] for s in data_stages], 'shop_ids': products}}}
    trial.custom_browse.append(dict(entry, names=part['names'], date=part.get('date', event['date']), entry_key=key + '#part1',
                                    phase_id='part1', image_path=part.get('image_path', event.get('image_path'))))
    trial.custom_browse.append(dict(entry, entry_key=key + '#part2', phase_id='part2'))


def survival_tables(trial, event, stage_ids):
    """每关一条 Survival 记录（16 字，原生 getExSurvivalInfo 按关卡编号查找）与掉落表。"""
    p = trial.p
    rows = [s.get('survival_row') for s in stages(event)]
    ex = []
    if event['mode'] == 'legacy_survival':
        source = trial.data[event['survival']['template']]
        template_rows = source['ex_survival']
        for index, (sid, row) in enumerate(zip(stage_ids, rows)):
            pick = template_rows[min(index if row is None else row, len(template_rows) - 1)]
            words = list(pick['raw_words'])
            words[0] = sid
            for i, raw in zip((13, 14), pick['pointed_tables_raw']):
                words[i] = trial.blob(bytes.fromhex(raw))
            ex.append(struct.pack('<16I', *words))
        drops = []
        for item in source['drop_items']:
            words = item['raw_words']
            if len(words) == 6:
                words = words[:5] + [0xffffffff] * 15 + words[5:]
            drops.append(struct.pack('<21I', *words))
        drop_ptr, drop_count = trial.blob(b''.join(drops)), len(drops)
    else:
        # 合作：原生 1.46 Survival 表（选择活动前保存的 db+0x20）中的合作记录与掉落表。
        table, count, drop_ptr, drop_count = struct.unpack('<4I', trial.original_survival)
        native = [p.read(table + i * 64, 64) for i in range(count)]
        coop = [r for r in native if 61000 <= struct.unpack_from('<I', r)[0] < 62000] or native
        for index, (sid, row) in enumerate(zip(stage_ids, rows)):
            words = list(struct.unpack('<16I', coop[min(index if row is None else row, len(coop) - 1)]))
            words[0] = sid
            ex.append(struct.pack('<16I', *words))
    return {'ex': trial.blob(b''.join(ex)), 'ex_count': len(ex), 'drops': drop_ptr, 'drop_count': drop_count}


def shop_rows(trial, event, ids):
    """代币兑换店商品：同类原生记录为模板，商品编号取历史活动商店使用的原生编号（活动内唯一）。"""
    items = event.get('shop', [])
    if not items:
        return []
    native = {r['id']: r for k in SHOP_POOL_EVENTS for r in trial.data[k]['shop'].get('rows', [])}
    unit_pool = iter(sorted(sid for sid, r in native.items() if r['type'] == 2))
    template = next(r for r in trial.data['treasure_recovery_2015']['shop']['rows'] if r['id'] == 262)
    rows = []
    for item in items:
        kind = SHOP_TYPES[item['type']][0]
        amount = item.get('amount', 1)
        if item['type'] == 'unit':
            sid, target = next(unit_pool), unit_id(item['unit'], ids)
            raw = bytearray(bytes.fromhex(template['raw_hex']))
            struct.pack_into('<H', raw, 0, sid)
            struct.pack_into('<I', raw, 4, target)
        else:
            # 原生面额商品：沿用该商品编号的原生记录（内容与编号绑定）。
            sid = NATIVE_PACKS[item['type']][item['item'] if item['type'] == 'item' else amount]
            raw = bytearray(bytes.fromhex(native[sid]['raw_hex']))
            target = native[sid]['unit_id']
        limit = 99999999 if item['type'] == 'msp' else item.get('limit', 1)
        rows.append({'id': sid, 'type': kind, 'unit_id': target, 'quantity': amount, 'raw_hex': raw.hex(),
                     'event_currency_price': item['price'], 'native_maximum': limit})
    return rows


def build_shop_table(trial, products):
    """与 EventTrial 初始化中的历史活动商店表相同的结构（目录、64 字节记录）。"""
    records = []
    for r in products:
        raw = bytes.fromhex(r['raw_hex'])
        # +28 = 2：自制商品在兑换店中始终开放（src/event_trial_hooks.cpp custom_token_row，核心 r42）。
        records.append(struct.pack('<16I', r['id'], trial.blob(raw), r['event_currency_price'], r['native_maximum'], 0,
                                   r['type'], r['unit_id'], 2, *([0] * 8)))
    return {'catalog': trial.blob(struct.pack('<' + 'I' * len(products), *[r['id'] for r in products])),
            'records': trial.blob(b''.join(records)), 'count': len(products)}


def menu_shop_id(trial, uid):
    """单位的原生商品编号：社区单位为 512+槽位；原版单位按原生商品表查找单位类商品。"""
    if uid >= 1024:
        return 512 + uid - 1024
    cache = getattr(trial, 'unit_shop_ids', None)
    if cache is None:
        cache = trial.unit_shop_ids = {}
        for sid in range(512):
            row = trial.p.call('_Z15GetMenuShopData10MenuShopID', sid)
            if row and trial.p.read(row + 2, 1)[0] == 2:
                cache.setdefault(struct.unpack('<I', trial.p.read(row + 4, 4))[0], sid)
    if uid not in cache:
        raise ValueError(f'original unit {uid} has no unit shop entry')
    return cache[uid]


def medal_rows(trial, event, ids):
    rows = []
    for row in event.get('medal_shop', []):
        uid = unit_id(row['unit'], ids)
        available = row.get('available', 'event')
        if available == 'event':
            rule = {'kind': 'event_available'}
        elif 'stage' in available:
            if available['stage'] not in {s['key'] for s in stages(event)}:
                raise ValueError(f'{event["key"]}: medal_shop stage {available["stage"]} is not a stage of this event')
            rule = {'kind': 'stage_win', 'local_stage_key': available['stage']}
        else:
            rule = {'kind': 'score', 'minimum': available['score']}
        rows.append({'event_key': event['key'], 'menu_shop_id': menu_shop_id(trial, uid), 'unit_id': uid,
                     'medal_price': row['price'], 'availability': rule})
    return rows


def install(trial):
    """读取本体与已载入模组的 EVENT 并编译（EventTrial 初始化时调用；社区内容与扩展世界已安装）。"""
    content = trial.p.community
    trial.custom_maps, trial.custom_browse, trial.custom_art, trial.custom_medal_rows = {}, [], {}, []
    events = load_body(trial.root) + list(getattr(content, 'mod_events', []))
    if not events:
        return []
    native = json.loads((trial.root / 'historical_events/native_maps.json').read_text(encoding='utf-8'))['events'][TEMPLATE_EVENT]
    templates = (bytes.fromhex(native['areas'][0]['raw_hex']), bytes.fromhex(native['areas'][0]['markers'][0]['raw_hex']))
    sounds = {e['key']: e.get('type', 'se') for e in content.sounds}
    scenes = {row['key']: row['id'] for row in content.manifest.get('stages', []) if 'key' in row}
    units = {u['key']: u['id'] for u in content.units}
    import content_locale as locale
    ids = {'units': units, 'sounds': content.sound_ids, 'scenes': scenes, 'languages': locale.language_codes(trial.p)}
    if any(e.get('shop') for e in events):
        lib = trial.p.uc.lib
        if not hasattr(lib, 'msd_custom_event_shop_version') or lib.msd_custom_event_shop_version() != 1:
            raise RuntimeError('Native core lacks custom event exchange shops (r42)')
    for event in events:
        if event.get('source', 'body') == 'body':
            # 本体 EVENT 只引用本体与原版内容。
            check_references(event, units, sounds, scenes, lambda prefix: prefix == 's1xlv')
        compile_event(trial, event, templates, ids)
    trial.p.log('CUSTOM_EVENTS', [e['key'] for e in events])
    return events


class MapArt:
    """自制地图图层与小关缩略图（M6b-2）：所选自制 EVENT 的原生地图场景（158–160）中写入 drawConv 替换表，离开时清除。"""

    def __init__(self, trial):
        self.t = trial
        self.images = {}
        self.written = None

    def image(self, path):
        if path not in self.images:
            from PIL import Image
            from lab_versus import create_native_image
            with Image.open(path) as source:
                self.images[path] = create_native_image(self.t.p, source.convert('RGBA'))
        return self.images[path]

    def entries(self, art):
        p = self.t.p
        rows = []
        if art['map']:
            image = self.image(art['map'])
            for conv in MAP_CONVS:
                x, y, w, h, ax, ay, flags, page = struct.unpack('<8h', p.read(conv, 16))
                # 作者底图为单张 1440×709：第二个转换项的源矩形从 x=823 起（与锚点 −823 对应）。
                rows.append((conv, image, (-ax, 0, w, h, ax, ay, flags, 0)))
        area = p.word(p.app_instance() + 0xc628)
        for slot, path in sorted(art['thumbs'].get(area, {}).items()):
            rows.append((THUMB_CONV_BASE + 16 * slot, self.image(path), (0, 0) + THUMB_SIZE + (0, 0, 0, 0)))
        return rows

    def update(self):
        t, p = self.t, self.t.p
        import lab
        header = lab.LAB_HEADER + 0xb40
        app = p.app_instance()
        art = t.custom_art.get(t.selected) if t.selected else None
        active = bool(art and app and t.native_map.active and p.word(app + 0x22bc) in (158, 159, 160))
        if not active:
            if self.written is not None:
                if p.word(header) == REPLACE_MAGIC:
                    p.put(header, 0)
                self.written = None
            return
        rows = self.entries(art)
        if rows == self.written:
            return
        for i, (conv, image, rect) in enumerate(rows[:8]):
            e = header + 0x10 + i * 32
            p.put(e, conv); p.put(e + 4, 0); p.put(e + 8, image); p.put(e + 12, 0)
            p.write(e + 16, struct.pack('<8h', *rect))
        p.put(header + 4, min(8, len(rows)))
        p.put(header, REPLACE_MAGIC)
        self.written = rows
