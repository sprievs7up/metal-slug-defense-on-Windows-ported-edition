"""KT-21（UnitID 1043）资源与注册记录生成：OBM 图集、独立精灵描述符、图标及注册表条目。

依据 content_work/kt21_feasibility_20261005/design_verification_r1 的 R7 候选脚本（tools/kt21_r7.py），
并按 2026-10-06 用户确认将开火距离缩短至炮弹落点（状态词 7 = 224）。
运行：设置 MSD_REPO / MSD_APK / MSD_ASSETS / KT21_SOURCE 环境变量后执行；输出写入 OUT 目录（默认正式版仓库）。
"""
from pathlib import Path
import copy, json, os, struct, sys

TOOLS = Path(os.environ.get('KT21_TOOLS', r'F:\egg\research\metal_slug_defense\content_work\kt21_feasibility_20261005\design_verification_r1\tools'))
sys.path.insert(0, str(TOOLS))
from PIL import Image
import elfmem as native
from obm_tool import parse
from native_sim import flatten
from native_sets import native_set
from kt21_candidates import load_assets
from kt21_r5 import build_r5
from kt21_r6 import r6_set, LOCALIZATION
from kt21_r7 import r7_set, sv001_shell, calibrate, SHELL_RATIO

REPO = Path(os.environ.get('MSD_REPO', r'F:\egg\github\metal-slug-defense-on-Windows-ported-edition'))
OUT = Path(os.environ.get('KT21_OUT', str(REPO)))
CONTENT_IN = REPO / 'community_content'
CONTENT = OUT / 'community_content'
ASSETS = Path(os.environ.get('MSD_ASSETS', str(REPO / 'game_data/assets/com.snkplaymore.android003')))
KEY = 's1xlv.kt21'
TEXTURE, EFFECTS = 'kt21_out.obm', 'kt21_sv001_effects.obm'
DESCRIPTOR = 'kt21_descriptor.json'
FIRE_RANGE = 224            # 炮弹落点距车身中心 222；开火距离取 224（基寇卡 320 的 7/10）
FLAME_START, FLAME_TICKS = 20, 45
ALT_BASE = 21               # 受击收尾槽 21..25：喷火第 1–4、5–8、9–12、13–39、40–44 tick
ENDING_BULLETS = [18, 19, 20, 17]
SCRIPT_COUNT = 26


def save_json(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').replace('\n', '\r\n').encode('utf-8'))


def indexed_obm(image):
    rgba = image.convert('RGBA')
    colors = list(dict.fromkeys(rgba.getdata()))
    assert len(colors) <= 256, len(colors)
    lut = {color: index for index, color in enumerate(colors)}
    raw = b'OI\x01\x08' + struct.pack('<HH', *image.size)
    return raw + b''.join(bytes(c) for c in colors).ljust(1024, b'\0') + bytes(lut[c] for c in rgba.getdata())


def shelf_pack(tiles, pad=1, sizes=((512, 512), (1024, 512), (1024, 1024), (2048, 1024))):
    order = sorted(range(len(tiles)), key=lambda i: (-tiles[i].height, -tiles[i].width))
    for W, H in sizes:
        x = y = shelf = 0
        pos, ok = {}, True
        for i in order:
            w, h = tiles[i].width + pad, tiles[i].height + pad
            if x + w > W:
                x, y, shelf = 0, y + shelf, 0
            if w > W or y + h > H:
                ok = False
                break
            pos[i] = (x, y)
            x += w
            shelf = max(shelf, h)
        if ok:
            page = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            for i, (px, py) in pos.items():
                page.paste(tiles[i], (px, py))
            return page, pos
    raise ValueError('atlas overflow')


def build_scripts():
    A = load_assets()
    r3, r5, r5p, F, info, comps, ramp = build_r5(A)
    r6 = r6_set(r5)
    sv = sv001_shell()
    v, flight = calibrate(r6, F, sv['flight_px'] * SHELL_RATIO[0] / SHELL_RATIO[1])
    r7, death = r7_set(r6, F, v)
    # 突进与制动的水平速度、加速度按 5/2 缩放，保持动作时序。
    for command in r7.scripts[10]:
        if command[0] == 7:
            command[1] = command[1] * 5 // 2
            command[3] = command[3] * 5 // 2
    return r7, F, v, flight, sv


def sv001_impact_offsets(r7):
    """槽 14 复制 SV-001 脚本 21：帧图块直接引用原生 metalslug.obm 矩形（第 1 页），保留原生翻转标记与锚点。"""
    d, names, rects, frames = native.sprite_desc(native.desc_of('MetalSlug'))
    sv = native_set('MetalSlug')
    raw = {}
    pos = 0
    while pos < len(frames):
        n = frames[pos]
        raw[pos] = frames[pos + 1:pos + 1 + n]
        pos += n + 1
    sv_frames = [c[1] for c in sv.scripts[21] if c[0] == 0 and c[1] >= 0]
    ours = [c[1] for c in r7.scripts[14] if c[0] == 0 and c[1] >= 0]
    assert len(sv_frames) == len(ours)
    mapping = {}
    for o, s in zip(ours, sv_frames):
        assert names[rects[raw[s][0]][7]] == 'metalslug.obm'
        mapping[o] = [rects[i] for i in raw[s]]
    return mapping


def descriptor_and_animations(r7):
    impact = sv001_impact_offsets(r7)
    # 收集本单位图块（去重）
    tiles, tile_index, frame_rects = [], {}, {}
    used = set()
    for cmds in r7.scripts.values():
        used.update(c[1] for c in cmds if c[0] == 0 and c[1] >= 0)
    for off in sorted(used):
        if off in impact:
            continue
        ids = []
        for img, ax, ay in r7.frames[off]:
            key = (img.size, ax, ay, img.tobytes())
            if key not in tile_index:
                tile_index[key] = len(tiles)
                tiles.append((img, ax, ay))
            ids.append(tile_index[key])
        frame_rects[off] = ids
    page, pos = shelf_pack([t[0] for t in tiles])
    rects = [[pos[i][0], pos[i][1], t[0].width, t[0].height, t[1], t[2], 0, 0] for i, t in enumerate(tiles)]
    impact_rect_index = {}
    for off, rs in impact.items():
        ids = []
        for r in rs:
            key = tuple(r)
            if key not in impact_rect_index:
                impact_rect_index[key] = len(rects)
                rects.append([*r[:7], 1])
            ids.append(impact_rect_index[key])
        frame_rects[off] = ids
    table, offset_map = [], {}
    for off in sorted(frame_rects):
        offset_map[off] = len(table)
        table += [len(frame_rects[off]), *frame_rects[off]]
    scripts = {k: [list(c) for c in v] for k, v in r7.scripts.items()}
    # 槽 2：商店动作预览（原生基寇卡槽 2 不发射弹体）
    scripts[2] = [c for c in scripts[9] if c[0] != 22]
    scripts[5] = [[21]]
    # 槽 21..25：喷火阶段受击。第 0 tick 在喷出坐标生成收尾对象，其后与槽 11 受击滑行相同。
    knock = scripts[11]
    for j, slot in enumerate(ENDING_BULLETS):
        scripts[ALT_BASE + j] = [[22, slot, 0, 0, 0]] + [list(c) for c in knock]
    scripts[ALT_BASE + 4] = [[12, 16, 0, 0, 0]] + [list(c) for c in knock]
    for k, cmds in scripts.items():
        flatten(cmds)
        for c in cmds:
            if c[0] == 0 and c[1] >= 0:
                c[1] = offset_map[c[1]]
    assert set(scripts) == set(range(SCRIPT_COUNT)), sorted(scripts)
    atk = r7.attack_rects
    desc = {'rects': rects, 'frames': table, 'script_count': SCRIPT_COUNT,
            'hit_bounds': [[0, 0, 0, 0, 0], [-36, -60, 72, 60, 0]],
            'attack_bounds': [[0, 0, 0, 0, 0], list(atk[1]), list(atk[2]), list(atk[3])]}
    animations = {str(k): [{'opcode': c[0], 'values': c[1:]} for c in v] for k, v in sorted(scripts.items())}
    return desc, animations, page, len(tiles)


def icon_tile():
    A = load_assets()
    f = A['idle'][0].transpose(Image.FLIP_LEFT_RIGHT)
    return f.crop((f.width - 46, 0, f.width, 42))


def main():
    r7, F, v, flight, sv = build_scripts()
    desc, animations, page, ntiles = descriptor_and_animations(r7)
    CONTENT.mkdir(parents=True, exist_ok=True)
    registry = json.loads((CONTENT_IN / 'registry.json').read_text(encoding='utf-8'))
    units = [u for u in registry['units'] if u['key'] != KEY]
    index = len(units)
    assert UNIT_ID(index) == 1043, index
    files = {TEXTURE: indexed_obm(page), EFFECTS: (ASSETS / 'metalslug.obm').read_bytes()}
    icon = parse((CONTENT_IN / 'unit_icon_02.obm').read_bytes()).convert('RGBA')
    tile = icon_tile()
    ix, iy = 1350, 768
    region = icon.crop((ix, iy, ix + 72, iy + 72))
    assert region.getbbox() is None, '新增图标区域含有既有像素。'
    icon.paste(tile, (ix, iy))
    files['unit_icon_02.obm'] = b'OI\x01\x20' + struct.pack('<HH', *icon.size) + icon.tobytes()
    for name, raw in files.items():
        (CONTENT / name).write_bytes(raw)
        registry['assets'][name] = None
    save_json(CONTENT / DESCRIPTOR, desc)
    unit = {
        'key': KEY, 'id': 1043, 'base_id': 3, 'faction': 1, 'identity': 'Rebel Army',
        'ground_special_attack': True,
        'shop_price': 0, 'available_from_start': False, 'shop_unlock_reference_id': 136,
        'world_clear_reward': {'world': 1, 'area': 11, 'world_type': 0},
        'ap': 200, 'hp_multiplier': [15, 7],
        'knockback_threshold_multiplier': [4, 1],
        'production_reference_id': 59, 'production_interval_multiplier': [1, 1],
        'special_damage_multiplier': [82, 225], 'damage_multiplier': [11, 9],
        'move_speed_multiplier': [11, 10], 'attack_wait_multiplier': [1, 1],
        'attack_range_multiplier': [1, 1], 'knockback_distance_multiplier': [99, 200], 'ballistic_range_multiplier': [1, 1],
        'special_cooldown_multiplier': [3, 2],
        'attack_attributes': {'special': 1},
        # 状态词绝对值（六个等级锚点）：7 开火距离；25/26 普攻弹体速度与目的距离置零，炮弹由脚本 op7 控制（同 SV-001 绝招组）；
        # 32/33 绝招组同理，喷火收尾对象静止于喷出坐标。
        'status_word_values': {'7': FIRE_RANGE, '25': 0, '26': 0, '32': 0, '33': 0},
        'flame_interrupt': {'flame_start_tick': FLAME_START, 'flame_ticks': FLAME_TICKS,
                            'alternate_knockback_animation': ALT_BASE, 'ending_bullet_animations': ENDING_BULLETS,
                            'knockback_limit_per_special': 1},
        'icon': {'page': 1, 'index': 340 + index, 'rect': [ix, iy, tile.width, tile.height], 'anchor': [-5, -5]},
        'textures': [TEXTURE, EFFECTS], 'sprite_descriptor': DESCRIPTOR,
        'animations': animations,
        'localization': {k: {'name': n, 'description': d} for k, (n, d) in LOCALIZATION.items()},
    }
    registry['units'] = units + [unit]
    save_json(CONTENT / 'registry.json', registry)
    report = {'unit_id': 1043, 'icon_index': 340 + index, 'tiles': ntiles, 'atlas': list(page.size),
              'rects': len(desc['rects']), 'frame_words': len(desc['frames']), 'scripts': SCRIPT_COUNT,
              'shell_op7_v': v, 'shell_flight': flight, 'sv001_shell': sv, 'fire_range': FIRE_RANGE}
    print(json.dumps(report, ensure_ascii=False))
    return report


def UNIT_ID(i):
    return 1024 + i


if __name__ == '__main__':
    main()
