"""MSD WINDOWS S1XLV unit tool for mod authors and AI assistants (docs/modding/ai_guide/).

Run from the game folder with the bundled Python:

    windows_runtime\\python.exe docs\\modding\\ai_guide\\tools\\msd_unit_tool.py base 221
    windows_runtime\\python.exe docs\\modding\\ai_guide\\tools\\msd_unit_tool.py build mods\\my_mod\\source\\my_unit.spec.json
    windows_runtime\\python.exe docs\\modding\\ai_guide\\tools\\msd_unit_tool.py preview my_mod my_unit
    windows_runtime\\python.exe docs\\modding\\ai_guide\\tools\\msd_unit_tool.py check my_mod

Commands
  base UID [UID ...]   Start the game core without a window, read original units (1-399): action class, sprite descriptor,
                       every animation script, stats at the six level anchors, faction. Writes base_<UID>.json and
                       base_<UID>.png (all scripts drawn frame by frame) to verification\\msd_unit_tool\\.
  build SPEC           Build one unit of a mod from a JSON spec (format in docs/modding/ai_guide/07_build_check_test.md):
                       atlas OBM, sprite descriptor, unit file, icon page, sounds, mod.json.
  preview MOD UNIT     Draw the built unit's scripts frame by frame to verification\\msd_unit_tool\\preview_<MOD>_<UNIT>.png.
  check MOD [MOD ...]  The full start-up check: run the game's mod loader and content installer without a window, with only
                       the given mods enabled. Catches errors that content_tool.py check-mods does not.

The tool never writes saves, settings or the player's mod list: the core runs on a temporary save under
verification\\msd_unit_tool\\runs\\, and the mod list, ID map and caches point there too.
"""
import argparse
import json
import os
import shutil
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'verification' / 'msd_unit_tool'
MODS = ROOT / 'mods'
sys.path.insert(0, str(ROOT))
for _name in ('.', 'native', 'angle'):
    if (ROOT / 'windows_runtime' / _name).is_dir():
        os.add_dll_directory(str(ROOT / 'windows_runtime' / _name))

COMMAND_LENGTHS = (2, 2, 2, 2, 2, 1, 3, 5, 2, 2, 3, 5, 5, 2, 3, 1, 1, 2, 2, 3, 3, 1, 5, 2)
ANCHOR_INDEX = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 13: 7, 14: 8, 15: 9, 16: 10, 17: 11, 18: 12, 19: 13, 20: 14,
                22: 15, 23: 16, 24: 17, 25: 18, 26: 19, 27: 20, 29: 21, 30: 22, 31: 23, 32: 24, 33: 25, 34: 26, 35: 27,
                36: 28, 38: 29, 39: 30, 40: 31}
FLOAT_WORDS = {5, 16, 18, 23, 25, 30, 32}
WORD_NAMES = {
    1: 'AP', 2: 'redeploy time (ticks)', 3: 'HP', 4: 'knock-back threshold', 5: 'move speed', 6: 'melee range',
    7: 'ranged attack range', 13: 'AP returned when destroyed', 14: 'Wi-Fi RP',
    15: 'melee damage', 16: 'melee knock-back power', 17: 'melee targets', 18: 'melee projectile speed',
    19: 'melee projectile distance', 20: 'wait after melee', 21: 'melee attribute',
    22: 'normal damage', 23: 'normal knock-back power', 24: 'normal targets', 25: 'normal projectile speed',
    26: 'normal projectile distance', 27: 'wait after normal attack', 28: 'normal attribute',
    29: 'special damage', 30: 'special knock-back power', 31: 'special targets', 32: 'special projectile speed',
    33: 'special projectile distance', 34: 'wait after special', 35: 'special cooldown', 36: 'first special cooldown',
    37: 'special attribute', 38: 'build time / first summon', 39: 'summon interval', 40: 'built unit', 41: 'child unit',
    8: 'resistance tier, attribute 0', 9: 'resistance tier, attribute 1', 10: 'resistance tier, attribute 2',
    11: 'resistance tier, attribute 3', 12: 'resistance tier, attribute 4'}
LEVELS = (1, 10, 20, 30, 40, 50)
IMAGE_TABLE, ACTIONS_GLOBAL = 0x10922f28, 0x109373f4
OP_NAMES = {0: 'frame', 1: 'wait', 2: 'rotate', 3: 'hit_box', 4: 'attack_box', 5: 'loop', 6: 'nudge', 7: 'move',
            8: 'move_x', 9: 'move_y', 10: 'layer', 11: 'layer_at', 12: 'effect', 13: 'nop', 14: 'offset', 15: 'ground',
            16: 'stop', 17: 'priority', 18: 'alpha', 19: 'scale', 20: 'accelerate', 21: 'end', 22: 'bullet', 23: 'sound'}
EMPTY_SCRIPT = [{'opcode': 0, 'values': [-1]}, {'opcode': 1, 'values': [1]}, {'opcode': 21, 'values': []}]


def fail(message):
    print('ERROR: ' + message)
    sys.exit(1)


def write_json(path, data, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, separators=(',', ':')) if compact else json.dumps(data, ensure_ascii=False, indent=1)
    path.write_text(text + '\n', encoding='utf-8')


# ------------------------------------------------------------------ OBM images
def decode_obm(raw):
    """OBM bytes -> PIL RGBA image (8-bit palette, 24-bit RGB and 32-bit RGBA; other kinds return None)."""
    from PIL import Image
    if len(raw) < 8 or raw[:2] != b'OI':
        raise ValueError('not an OBM image')
    kind, bits = raw[2], raw[3]
    w, h = struct.unpack_from('<HH', raw, 4)
    if kind == 1 and bits == 8:
        palette = [raw[8 + 4 * i:12 + 4 * i] for i in range(256)]
        return Image.frombytes('RGBA', (w, h), b''.join(palette[i] for i in raw[1032:1032 + w * h]))
    if kind == 4 and bits == 8:      # original game atlases: 256-entry RGBA5551 palette
        def c5551(v):
            return bytes((((v >> 11) & 31) * 255 // 31, ((v >> 6) & 31) * 255 // 31, ((v >> 1) & 31) * 255 // 31, 255 if v & 1 else 0))
        palette = [c5551(v) for v in struct.unpack_from('<256H', raw, 8)]
        return Image.frombytes('RGBA', (w, h), b''.join(palette[i] for i in raw[520:520 + w * h]))
    if kind == 1 and bits == 32:
        return Image.frombytes('RGBA', (w, h), raw[8:8 + 4 * w * h])
    if kind == 0 and bits in (24, 32):
        return Image.frombytes('RGB', (w, h), raw[8:8 + 3 * w * h]).convert('RGBA')
    return None                       # 4-bit kinds are not drawn by this tool


def encode_obm8(image):
    """PIL RGBA image (power-of-two size) -> 8-bit palette OBM. Index 0 is transparent black, as the game expects."""
    rgba = image.convert('RGBA')
    pixels = rgba.tobytes()
    palette, indices = {b'\0\0\0\0': 0}, bytearray()
    for i in range(0, len(pixels), 4):
        color = pixels[i:i + 4] if pixels[i + 3] else b'\0\0\0\0'
        index = palette.get(color)
        if index is None:
            if len(palette) == 256:
                raise ValueError('more than 255 colours in one atlas page')
            index = palette[color] = len(palette)
        indices.append(index)
    table = b''.join(palette) + b'\0' * (4 * (256 - len(palette)))
    return b'OI\x01\x08' + struct.pack('<HH', *rgba.size) + table + bytes(indices), len(palette) - 1


def encode_obm32(image):
    rgba = image.convert('RGBA')
    return b'OI\x01\x20' + struct.pack('<HH', *rgba.size) + rgba.tobytes()


def limit_colors(image, report, label):
    """Reduce a page to 255 opaque colours when needed (fully transparent pixels stay index 0)."""
    from PIL import Image
    rgba = image.convert('RGBA')
    colors = {c for c in rgba.getdata() if c[3]}
    if len(colors) <= 255:
        return rgba
    alpha = rgba.getchannel('A')
    reduced = rgba.convert('RGB').quantize(colors=255, method=Image.Quantize.MEDIANCUT).convert('RGB')
    out = Image.merge('RGBA', (*reduced.split(), alpha))
    report.append(f'WARNING {label}: {len(colors)} colours reduced to 255 (check the preview; give fewer colours to keep them exact)')
    return out


# ------------------------------------------------------------------ headless core
def boot(tag, enabled=()):
    """Start the game core without a window on a temporary save; returns (probe, run folder)."""
    run = OUT / 'runs' / f'{tag}_{time.strftime("%Y%m%d_%H%M%S")}_{os.getpid()}'
    (run / 'config').mkdir(parents=True)
    write_json(run / 'mods_enabled.json', {'schema': 1, 'enabled': list(enabled)})
    env = {'MSD_LAB_CONFIG_DIR': run / 'config', 'MSD_CONTENT_DIGEST_CACHE': run / 'content_digests.json',
           'MSD_MOD_ID_MAP': run / 'mods_ids.json', 'MSD_UNIT_VIEWER_CACHE': run / 'unit_viewer_bounds.json',
           'MSD_MODS_ENABLED': run / 'mods_enabled.json', 'MSD_MODS_DIR': MODS}
    for key, value in env.items():
        os.environ[key] = str(value)
    os.environ['MSD_SHADER_CACHE_DIR'] = ''
    console = (run / 'console.log').open('w', encoding='utf-8', buffering=1)
    stdout, sys.stdout = sys.stdout, console
    try:
        import player
        p = player.Probe(guest_root=run / 'save', log_name=str(run / 'probe.log'), window_handle=None,
                         window_size=(1280, 720), audio_mode='silent')
        p.initialize()
    finally:
        sys.stdout = stdout
    return p, run


def read_cstr(p, address):
    raw = p.read(address, 128)
    return raw[:raw.index(b'\0')].decode('utf-8', 'replace')


def read_script(p, address):
    cmds, pos = [], address
    while len(cmds) < 4000:
        op = struct.unpack('<i', p.read(pos, 4))[0]
        if not 0 <= op < len(COMMAND_LENGTHS):
            return cmds, f'unknown opcode {op}'
        n = COMMAND_LENGTHS[op]
        cmds.append({'opcode': op, 'values': list(struct.unpack('<%di' % (n - 1), p.read(pos + 4, 4 * (n - 1))))})
        pos += 4 * n
        if op in (5, 21):
            return cmds, None
    return cmds, 'no op5/op21 within 4000 commands'


def read_descriptor(p, address):
    w = struct.unpack('<8I', p.read(address, 32))
    names = [read_cstr(p, p.word(w[1] + 4 * k)) for k in range(w[0])]
    rects_va, frames_va, hits_va, atks_va = w[2:6]
    rects = [list(struct.unpack('<8h', p.read(rects_va + 16 * i, 16))) for i in range((frames_va - rects_va) // 16)]
    frames = list(struct.unpack('<%dI' % ((hits_va - frames_va) // 4), p.read(frames_va, hits_va - frames_va)))
    hits = [list(struct.unpack('<5i', p.read(hits_va + 20 * i, 20))) for i in range((atks_va - hits_va) // 20)]
    scripts, notes = {}, {}
    for k in range(w[7]):
        va = p.word(w[6] + 4 * k)
        if va:
            scripts[str(k)], note = read_script(p, va)
            if note:
                notes[str(k)] = note
    used = [c['values'][0] for s in scripts.values() for c in s if c['opcode'] == 4] + [0]
    atks = [list(struct.unpack('<5i', p.read(atks_va + 20 * i, 20))) for i in range(max(used) + 1)]
    return {'textures': names, 'rects': rects, 'frames': frames, 'hit_bounds': hits, 'attack_bounds': atks,
            'script_count': w[7], 'scripts': scripts, 'script_notes': notes}


def unit_row(p, uid):
    """Status words at the six level anchors (Lv1, 10, 20, 30, 40, 50) from the original data row."""
    db = p.word(p.call('_ZN10BattleInfo11getInstanceEv'))
    row = p.read(p.word(db + 4) + uid * 0x390, 0x390)
    out = {}
    for word, index in sorted(ANCHOR_INDEX.items()):
        offsets = [word * 4] + [(42 + 33 * i + index) * 4 for i in range(5)]
        fmt = '<f' if word in FLOAT_WORDS else '<i'
        values = [struct.unpack_from(fmt, row, off)[0] for off in offsets]
        out[str(word)] = {'name': WORD_NAMES.get(word, ''), 'levels': [round(v, 3) if word in FLOAT_WORDS else v for v in values]}
    for word in (8, 9, 10, 11, 12, 21, 28, 37):
        out[str(word)] = {'name': WORD_NAMES.get(word, ''), 'value': struct.unpack_from('<i', row, word * 4)[0]}
    return out


def script_summary(script, frame_starts):
    ticks, frames, events, end, steps = 0, [], [], 'none', 0
    for c in script:
        op, v = c['opcode'], c['values']
        if op == 0 and v[0] != -1 and v[0] not in frames:
            frames.append(v[0])
        elif op == 1:
            ticks += max(1, v[0])
            steps += 1
        elif op in (3, 4, 12, 22, 23, 10, 11, 7, 15):
            events.append(f'{OP_NAMES[op]}{v}@{ticks}')
        elif op in (5, 21):
            end = 'loop' if op == 5 else 'end'
    return {'commands': len(script), 'ticks': ticks, 'frames': len(frames), 'steps': steps, 'ends': end, 'events': events[:12]}


def cmd_base(args):
    p, run = boot('base')
    try:
        vt = {v + 8: k for k, v in p.symbols.items() if k.startswith('_ZTV')}
        actions = p.word(ACTIONS_GLOBAL)
        names = p.symbols['strMenuUnitNameEN']
        app = p.app_instance()
        for uid in args.uids:
            if not 1 <= uid <= 399:
                fail('base units are original UnitIDs 1-399')
            obj = p.word(actions + uid * 4)
            cls = vt.get(p.word(obj), '?') if obj else None
            d = p.word(IMAGE_TABLE + uid * 8)
            info = {'uid': uid, 'name_en': read_cstr(p, p.word(names + uid * 4)) if p.word(names + uid * 4) else '',
                    'action_class': (cls or '').replace('_ZTV', '').lstrip('0123456789'),
                    'image_direction': p.word(IMAGE_TABLE + uid * 8 + 4),
                    'faction': p.call('_ZN7AppMain18GetUnitAffiliationE6UnitID', app, uid) & 0xffffffff,
                    'stats': unit_row(p, uid), 'descriptor': read_descriptor(p, d) if d else None}
            desc = info['descriptor']
            if desc:
                info['slots'] = {k: script_summary(s, None) for k, s in sorted(desc['scripts'].items(), key=lambda kv: int(kv[0]))}
            path = OUT / f'base_{uid}.json'
            write_json(path, info)
            print(f'UnitID {uid} {info["name_en"]!r}: class {info["action_class"]}, faces {"right" if info["image_direction"] == 90 else "left"} '
                  f'({info["image_direction"]}), faction {info["faction"]}, script_count {desc and desc["script_count"]}, '
                  f'textures {desc and desc["textures"]}')
            s = info['stats']
            print('  Lv1/10/20/30/40/50  AP %s  HP %s  range %s  normal dmg %s  special dmg %s  speed %s  redeploy %s' % (
                s['1']['levels'][0], s['3']['levels'], s['7']['levels'][0], s['22']['levels'], s['29']['levels'],
                s['5']['levels'][0], s['2']['levels'][0]))
            if desc:
                for k, sm in info['slots'].items():
                    if sm['frames'] or sm['events']:
                        print(f'  slot {k:>3}: {sm["frames"]:>2} distinct frames, {sm["steps"]:>3} steps, {sm["ticks"]:>4} ticks, '
                              f'{sm["ends"]:<4} {" ".join(sm["events"])}')
                sheet = render_sheet(desc, lambda name: original_texture(name), f'UnitID {uid} {info["name_en"]} ({info["action_class"]})')
                if sheet:
                    sheet.save(OUT / f'base_{uid}.png')
            print(f'  -> {path}' + (f' and {path.with_suffix(".png")}' if desc else ''))
    finally:
        p.close()


def original_texture(name):
    import probe
    path = Path(probe.RESOURCE_ROOT) / probe.PKG / name
    return decode_obm(path.read_bytes()) if path.is_file() else None


# ------------------------------------------------------------------ preview sheet
def timeline(script, limit=96):
    """Root-layer frames in play order: [(frame start, ticks, active hit box, active attack box, notes)]."""
    out, frame, hit, atk, notes = [], -1, 0, -1, []
    for c in script:
        op, v = c['opcode'], c['values']
        if op == 0:
            frame = v[0]
        elif op == 3:
            hit = v[0]
        elif op == 4:
            atk = v[0]
        elif op in (12, 22, 23, 10, 11, 7, 8, 9, 15):
            notes.append(OP_NAMES[op] + ''.join(f' {x}' for x in v))
        elif op == 1:
            out.append((frame, max(1, v[0]), hit, atk, notes))
            notes = []
            if len(out) >= limit:
                break
        elif op in (5, 21):
            if notes:
                out.append((frame, 0, hit, atk, notes))
            break
    return out


def render_sheet(desc, texture, title, scale=2):
    """One row per script; each cell shows a frame at the unit origin (cross), the ground line (y 0),
    the hit box (green) and the attack box (red). Labels: tick count, events."""
    from PIL import Image, ImageDraw
    pages = [texture(n) for n in desc['textures']]
    rects, frames = desc['rects'], desc['frames']
    tiles = {}

    def frame_image(start):
        if start in tiles:
            return tiles[start]
        parts = []
        if 0 <= start < len(frames):
            for r in frames[start + 1:start + 1 + frames[start]]:
                x, y, w, h, ax, ay, flags, page = rects[r]
                img = pages[page] if page < len(pages) else None
                if img is None or w <= 0 or h <= 0:
                    continue
                tile = img.crop((x, y, x + w, y + h))
                if flags & 1:
                    tile = tile.transpose(Image.FLIP_LEFT_RIGHT)
                if flags & 2:
                    tile = tile.transpose(Image.FLIP_TOP_BOTTOM)
                ox = -(w - ax) if flags & 1 else -ax
                oy = -(h - ay) if flags & 2 else -ay
                parts.append((tile, ox, oy))
        tiles[start] = parts
        return parts

    rows = []
    for key in sorted(desc['scripts'], key=int):
        line = timeline(desc['scripts'][key])
        if any(f != -1 for f, *_ in line) or any(n for *_, n in line):
            rows.append((key, line))
    if not rows:
        return None
    # common cell size from all frames and boxes
    left = top = -8
    right = bottom = 8
    for _, line in rows:
        for f, _, hit, atk, _ in line:
            for tile, ox, oy in frame_image(f):
                left, top = min(left, ox), min(top, oy)
                right, bottom = max(right, ox + tile.width), max(bottom, oy + tile.height)
    left, top, right, bottom = left - 4, top - 4, right + 4, max(bottom, 0) + 18
    cw, ch = (right - left) * scale, (bottom - top) * scale
    cols = min(12, max(len(line) for _, line in rows))
    bands = [(key, line[i:i + cols], i) for key, line in rows for i in range(0, max(1, len(line)), cols)]
    sheet = Image.new('RGBA', (60 + cols * (cw + 4), 24 + len(bands) * (ch + 4)), (40, 40, 48, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text((4, 4), title + '   (green: hit box, red: attack box, cross: unit origin, line: ground)', fill=(255, 255, 255, 255))
    boxes = lambda table, i: table[i] if 0 <= i < len(table) and (table[i][2] or table[i][3]) else None
    for r, (key, line, first) in enumerate(bands):
        y0 = 24 + r * (ch + 4)
        draw.text((4, y0 + 4), f'slot {key}' if first == 0 else f'slot {key}' + chr(10) + '(cont.)', fill=(255, 255, 0, 255))
        for c, (f, ticks, hit, atk, notes) in enumerate(line):
            x0 = 60 + c * (cw + 4)
            cell = Image.new('RGBA', ((right - left), (bottom - top)), (90, 90, 100, 255))
            for tile, ox, oy in frame_image(f):
                cell.alpha_composite(tile, (ox - left, oy - top))
            cell = cell.resize((cw, ch), Image.NEAREST)
            sheet.paste(cell, (x0, y0))
            ox, oy = x0 - left * scale, y0 - top * scale
            draw.line((x0, oy, x0 + cw - 1, oy), fill=(150, 220, 255, 255))
            draw.line((ox - 4, oy, ox + 4, oy), fill=(255, 255, 255, 255))
            draw.line((ox, oy - 4, ox, oy + 4), fill=(255, 255, 255, 255))
            for table, i, color in ((desc['hit_bounds'], hit, (0, 255, 0, 255)), (desc['attack_bounds'], atk, (255, 60, 60, 255))):
                b = boxes(table, i)
                if b:
                    draw.rectangle((ox + b[0] * scale, oy + b[1] * scale, ox + (b[0] + b[2]) * scale, oy + (b[1] + b[3]) * scale), outline=color)
            label = f'{ticks}t' + (' ' + ', '.join(notes) if notes else '')
            draw.text((x0 + 2, y0 + ch - 12), label[:max(8, cw // 6)], fill=(255, 255, 255, 255))
    return sheet


def cmd_preview(args):
    mod_dir = MODS / args.mod
    unit = json.loads((mod_dir / 'units' / f'{args.unit}.json').read_text(encoding='utf-8'))
    desc = json.loads(find_asset(mod_dir, unit['sprite_descriptor']).read_text(encoding='utf-8'))
    desc['textures'] = unit.get('textures', [unit.get('texture')])
    desc['scripts'] = unit['animations']

    def texture(name):
        path = find_asset(mod_dir, name)
        return decode_obm(path.read_bytes()) if path else None
    sheet = render_sheet(desc, texture, f'{unit["key"]} (base {unit["base_id"]})')
    path = OUT / f'preview_{args.mod}_{args.unit}.png'
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    print(f'-> {path}')


def find_asset(mod_dir, name):
    import probe
    for folder in (mod_dir / 'assets', ROOT / 'community_content', Path(probe.RESOURCE_ROOT) / probe.PKG):
        if (folder / name).is_file():
            return folder / name
    return None


# ------------------------------------------------------------------ build
def compile_script(items, frame_of, sounds, where):
    out = []
    for item in items:
        if item == 'loop':
            out.append({'opcode': 5, 'values': []})
            continue
        if item == 'end':
            out.append({'opcode': 21, 'values': []})
            continue
        if not isinstance(item, dict):
            fail(f'{where}: unknown script item {item!r}')
        if 'frames' in item or 'frame' in item:
            names = item.get('frames') or [item['frame']]
            ticks = item.get('ticks', 1)
            ticks = ticks if isinstance(ticks, list) else [ticks] * len(names)
            if len(ticks) != len(names):
                fail(f'{where}: "ticks" list must have one value per frame')
            for name, t in zip(names, ticks):
                out += [{'opcode': 0, 'values': [frame_of(name, where)]}, {'opcode': 1, 'values': [int(t)]}]
            continue
        simple = {'hide': lambda v: [(0, [-1]), (1, [int(v)])], 'wait': lambda v: [(1, [int(v)])],
                  'hit_box': lambda v: [(3, [int(v)])], 'attack_box': lambda v: [(4, [int(v)])],
                  'move': lambda v: [(7, [int(x) for x in v])], 'move_x': lambda v: [(8, [int(v)])],
                  'move_y': lambda v: [(9, [int(v)])], 'nudge': lambda v: [(6, [int(x) for x in v])],
                  'offset': lambda v: [(14, [int(x) for x in v])], 'ground': lambda v: [(15, [])],
                  'stop': lambda v: [(16, [])], 'priority': lambda v: [(17, [int(v)])],
                  'alpha': lambda v: [(18, [int(v)])], 'scale': lambda v: [(19, [int(x) for x in v])],
                  'rotate': lambda v: [(2, [int(v)])], 'accelerate': lambda v: [(20, [int(x) for x in v])]}
        key = next((k for k in item if k in simple), None)
        if key:
            out += [{'opcode': op, 'values': vals} for op, vals in simple[key](item[key])]
        elif 'sound' in item:
            value = item['sound']
            if isinstance(value, str) and '.' not in value:
                value = sounds.get(value, value)
            out.append({'opcode': 23, 'values': [value]})
        elif 'effect' in item or 'bullet' in item or 'layer' in item:
            kind = 'effect' if 'effect' in item else 'bullet' if 'bullet' in item else 'layer'
            slot = item[kind]
            if isinstance(slot, str) and slot.startswith('shared:'):
                slot = 0xff00 + int(slot[7:], 0)
            x, y = item.get('at', [0, 0])
            if kind == 'effect':
                out.append({'opcode': 12, 'values': [int(slot), int(item.get('priority', 0)), int(x), int(y)]})
            elif kind == 'bullet':
                out.append({'opcode': 22, 'values': [int(slot), int(item.get('group', 0)), int(x), int(y)]})
            else:
                out.append({'opcode': 11, 'values': [int(slot), int(item.get('priority', 0)), int(x), int(y)]})
        elif 'op' in item:
            op, values = item['op'], item.get('values', [])
            if not 0 <= op < len(COMMAND_LENGTHS) or len(values) != COMMAND_LENGTHS[op] - 1:
                fail(f'{where}: op{op} takes {COMMAND_LENGTHS[op] - 1 if 0 <= op < 24 else "?"} values')
            out.append({'opcode': op, 'values': values})
        else:
            fail(f'{where}: unknown script item {item!r}')
    if not out or out[-1]['opcode'] not in (5, 21):
        fail(f'{where}: a script must end with "loop" (op5) or "end" (op21)')
    return out


def load_frames(folder, spec, report):
    from PIL import Image
    mode = spec.get('anchor', 'folder')
    per_frame = spec.get('anchors', {})
    per_folder = spec.get('folder_anchors', {})
    files = sorted(p for p in folder.rglob('*.png'))
    if not files:
        fail(f'no PNG frames under {folder}')
    frames = {}
    for path in files:
        name = path.relative_to(folder).with_suffix('').as_posix()
        img = Image.open(path).convert('RGBA')
        box = img.getbbox()
        if box is None:
            report.append(f'note: frame {name} is fully transparent (use "hide" instead)')
            continue
        frames[name] = {'image': img, 'box': box, 'group': name.rsplit('/', 1)[0] if '/' in name else ''}
    groups = {}
    for name, f in frames.items():
        groups.setdefault(f['group'], []).append(name)
    for group, names in groups.items():
        sizes = {frames[n]['image'].size for n in names}
        if group in per_folder:
            anchor = per_folder[group]
        elif mode == 'folder' and len(sizes) == 1:
            boxes = [frames[n]['box'] for n in names]
            union = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
            anchor = [(union[0] + union[2]) // 2, union[3]]
        elif mode == 'canvas' and len(sizes) == 1:
            w, h = next(iter(sizes))
            anchor = [w // 2, h]
        elif isinstance(mode, list):
            anchor = mode
        else:
            anchor = None
            if mode in ('folder', 'canvas'):
                report.append(f'note: frames in "{group or "."}" have different canvas sizes; anchored per frame (bottom centre)')
        for n in names:
            box = frames[n]['box']
            frames[n]['anchor'] = per_frame.get(n) or anchor or [(box[0] + box[2]) // 2, box[3]]
    return frames


def pack_pages(tiles, report, max_size=2048):
    """Shelf-pack tile images into power-of-two pages; returns [(page image, {tile index: (x, y)})]."""
    from PIL import Image
    order = sorted(range(len(tiles)), key=lambda i: (-tiles[i].height, -tiles[i].width))
    pages, remaining = [], order
    while remaining:
        placed = None
        for W, H in ((256, 256), (512, 256), (512, 512), (1024, 512), (1024, 1024), (2048, 1024), (2048, 2048)):
            if W > max_size or H > max_size:
                continue
            x = y = shelf = 0
            pos, rest = {}, []
            for i in remaining:
                w, h = tiles[i].width + 1, tiles[i].height + 1
                if w > W or h > H:
                    fail(f'a frame is larger than {W}x{H}')
                if x + w > W:
                    x, y, shelf = 0, y + shelf, 0
                if y + h > H:
                    rest.append(i)
                    continue
                pos[i] = (x, y)
                x += w
                shelf = max(shelf, h)
            placed = (W, H, pos, rest)
            if not rest:
                break
        W, H, pos, rest = placed
        page = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        for i, (px, py) in pos.items():
            page.paste(tiles[i], (px, py))
        pages.append((page, pos))
        remaining = rest
        if len(pages) > 16:
            fail('more than 16 atlas pages; reduce frames or their size')
    return pages


def update_icon_page(mod, mod_dir, unit_name, icon_img, report):
    """Shared icon page assets/<mod>_icons.obm (512x512, 64x64 cells); cells are kept in source/icon_cells.json."""
    from PIL import Image
    cells_path = mod_dir / 'source' / 'icon_cells.json'
    cells = json.loads(cells_path.read_text(encoding='utf-8')) if cells_path.is_file() else {}
    if unit_name not in cells:
        used = set(cells.values())
        cells[unit_name] = next(i for i in range(64) if i not in used)
    cell = cells[unit_name]
    page_path = mod_dir / 'assets' / f'{mod}_icons.obm'
    page = decode_obm(page_path.read_bytes()) if page_path.is_file() else Image.new('RGBA', (512, 512), (0, 0, 0, 0))
    cx, cy = (cell % 8) * 64, (cell // 8) * 64
    page.paste(Image.new('RGBA', (64, 64), (0, 0, 0, 0)), (cx, cy))
    page.paste(icon_img, (cx, cy))
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_bytes(encode_obm32(page))
    write_json(cells_path, cells)
    return f'{mod}_icons.obm', [cx, cy, icon_img.width, icon_img.height]


def make_icon(spec, frames, mod_dir, facing, report):
    from PIL import Image
    icon = spec.get('icon', {})
    if 'file' in icon:
        img = Image.open(mod_dir / icon['file']).convert('RGBA')
    else:
        name = icon.get('frame') or next(iter(sorted(frames)))
        if name not in frames:
            fail(f'icon frame {name!r} not found')
        img = frames[name]['image']
    img = img.crop(img.getbbox())
    if icon.get('mirror', facing == 'left'):
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    fit = int(icon.get('fit', 40))
    if img.width > fit or img.height > 46:
        k = min(fit / img.width, 46 / img.height)
        img = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))), Image.LANCZOS if icon.get('smooth') else Image.NEAREST)
        report.append(f'note: icon scaled to {img.width}x{img.height}; supply a hand-made icon file for best quality')
    # the 50x50 cell's inner frame is (5,5)-(45,45); bottom-align, centre horizontally
    left, top = 5 + (40 - img.width) // 2, 45 - img.height
    return img, [-left, -top]


def cmd_build(args):
    spec_path = Path(args.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    mod, name = spec.get('mod'), spec.get('name')
    import re
    if not isinstance(mod, str) or not re.fullmatch(r'[a-z][a-z0-9_]{1,31}', mod) or mod in ('s1xlv', 'original', 'body', 'test'):
        fail('"mod" must match [a-z][a-z0-9_]{1,31} and not be s1xlv/original/body/test')
    if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9_]{1,40}', name):
        fail('"name" must be lowercase letters, digits and _')
    mod_dir = MODS / mod
    unit = dict(spec.get('unit') or {})
    for forbidden in ('id', 'key', 'textures', 'texture', 'sprite_descriptor', 'animations'):
        if forbidden in unit:
            fail(f'"unit" must not contain "{forbidden}" (the tool writes it)')
    if 'base_id' not in unit:
        fail('"unit" needs base_id')
    report = []
    base_path = OUT / f'base_{unit["base_id"]}.json'
    base = json.loads(base_path.read_text(encoding='utf-8')) if base_path.is_file() else None
    if base is None:
        report.append(f'WARNING: no {base_path.name}; run "base {unit["base_id"]}" first so missing slots can be reported')
    script_count = spec.get('script_count') or (base and base['descriptor']['script_count'])
    if not script_count:
        fail('give "script_count" (at least the base unit\'s script_count) or run the base command first')
    if base and script_count < base['descriptor']['script_count']:
        fail(f'script_count {script_count} is smaller than the base unit\'s {base["descriptor"]["script_count"]}')
    facing = spec.get('facing')
    if facing not in ('left', 'right'):
        fail('"facing" must be "left" or "right" (the direction the art faces)')

    frames = load_frames((mod_dir / spec['frames_folder']).resolve(), spec, report)
    folders = {}
    for fname, f in frames.items():
        folders.setdefault(f['group'] or '.', (f['image'].size, tuple(f['anchor'])))
    report.append('anchors (canvas size -> foot pixel): ' + '; '.join(f'{g} {s[0]}x{s[1]} -> {a}' for g, (s, a) in sorted(folders.items()))
                  + '  (compare across folders: a different body position per folder makes the unit jump between actions)')
    # tiles: cropped frames, identical ones shared
    tile_images, tile_index, rects, rect_index, frame_words, frame_start = [], {}, [], {}, [], {}
    for fname in sorted(frames):
        f = frames[fname]
        crop = f['image'].crop(f['box'])
        key = crop.tobytes() + bytes(crop.size)
        if key not in tile_index:
            tile_index[key] = len(tile_images)
            tile_images.append(crop)
        t = tile_index[key]
        rkey = (t, f['anchor'][0] - f['box'][0], f['anchor'][1] - f['box'][1])
        if rkey not in rect_index:
            rect_index[rkey] = len(rects)
            rects.append(rkey)
        frame_start[fname] = len(frame_words)
        frame_words += [1, rect_index[rkey]]
    pages = pack_pages(tile_images, report)
    where = {}
    for p_i, (page, pos) in enumerate(pages):
        for t, xy in pos.items():
            where[t] = (p_i, xy)
    rect_rows = []
    for t, ax, ay in rects:
        p_i, (x, y) = where[t]
        rect_rows.append([x, y, tile_images[t].width, tile_images[t].height, ax, ay, 0, p_i])
    textures = []
    (mod_dir / 'assets').mkdir(parents=True, exist_ok=True)
    for p_i, (page, _) in enumerate(pages):
        fname = f'{mod}_{name}' + (f'_{p_i}' if len(pages) > 1 else '') + '.obm'
        raw, colors = encode_obm8(limit_colors(page, report, fname))
        (mod_dir / 'assets' / fname).write_bytes(raw)
        textures.append(fname)

    def frame_of(fname, where_):
        if fname not in frame_start:
            fail(f'{where_}: frame {fname!r} not found under {spec["frames_folder"]}')
        return frame_start[fname]

    sound_keys = {}
    sound_entries = []
    for s in spec.get('sounds', []):
        key = s['key']
        if not key.startswith(mod + '.'):
            fail(f'sound key {key} must start with "{mod}."')
        src = mod_dir / s['file']
        raw = src.read_bytes()
        if raw[:4] != b'OggS':
            fail(f'{s["file"]} is not Ogg Vorbis (convert it first, see 06_sounds_and_text.md)')
        target = f'{mod}_{key.split(".", 1)[1]}.msdf'
        shutil.copyfile(src, mod_dir / 'assets' / target)
        entry = {'key': key, 'file': target, 'type': s.get('type', 'se')}
        for opt in ('volume', 'gain', 'loop'):
            if opt in s:
                entry[opt] = s[opt]
        sound_entries.append(entry)
        sound_keys[key.split('.', 1)[1]] = key

    animations = {}
    for slot, items in spec.get('scripts', {}).items():
        if not str(slot).isdigit() or not 0 <= int(slot) < script_count:
            fail(f'script slot {slot} outside 0..{script_count - 1}')
        animations[str(int(slot))] = compile_script(items, frame_of, sound_keys, f'slot {slot}')
    used = {c['values'][0] for script in animations.values() for c in script if c['opcode'] == 0}
    unused = [n for n in sorted(frame_start) if frame_start[n] not in used and n != spec.get('icon', {}).get('frame')]
    if unused:
        report.append('note: frames packed but used by no script: ' + ', '.join(unused))
    if base:
        missing = [k for k, s in base.get('slots', {}).items() if (s['frames'] or s['events']) and k not in animations]
        if missing:
            report.append('WARNING: the base unit uses these slots, which the spec does not write (they will be empty): ' + ', '.join(missing))
    for slot in range(script_count):
        animations.setdefault(str(slot), [dict(c) for c in EMPTY_SCRIPT])

    hit = [[0, 0, 0, 0, 0]] + [list(b) + [0] * (5 - len(b)) for b in spec.get('hit_boxes', [])]
    attack = [[0, 0, 0, 0, 0]] + [list(b) + [7] * (5 - len(b)) for b in spec.get('attack_boxes', [])]
    for k, script in animations.items():
        for c in script:
            if c['opcode'] == 3 and not 0 <= c['values'][0] < len(hit):
                fail(f'slot {k}: hit_box {c["values"][0]} does not exist (use 0 for none)')
            if c['opcode'] == 4 and not -1 <= c['values'][0] < len(attack):
                fail(f'slot {k}: attack_box {c["values"][0]} does not exist (use -1 for none)')
    descriptor = {'rects': rect_rows, 'frames': frame_words, 'script_count': script_count, 'hit_bounds': hit, 'attack_bounds': attack}
    desc_name = f'{mod}_{name}_descriptor.json'
    write_json(mod_dir / 'assets' / desc_name, descriptor, compact=True)

    icon_img, anchor = make_icon(spec, frames, mod_dir, facing, report)
    atlas, rect = update_icon_page(mod, mod_dir, name, icon_img, report)

    unit.setdefault('image_direction', 90 if facing == 'right' else 270)
    if 'hp_multiplier' in unit and 'knockback_threshold_multiplier' not in unit:
        unit['knockback_threshold_multiplier'] = unit['hp_multiplier']
        report.append('note: knockback_threshold_multiplier set equal to hp_multiplier (the project default)')
    out = {'key': f'{mod}.{name}', **unit, 'icon': {'atlas': atlas, 'rect': rect, 'anchor': anchor},
           'textures': textures, 'sprite_descriptor': desc_name, 'animations': animations}
    write_json(mod_dir / 'units' / f'{name}.json', out)
    content = {'units': 'units/'}
    if sound_entries:
        write_json(mod_dir / 'sounds' / f'{name}.json', sound_entries)
        content['sounds'] = 'sounds/'
    manifest_path = mod_dir / 'mod.json'
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest.setdefault('content', {}).update({k: v for k, v in content.items() if k not in manifest['content']})
    else:
        info = spec.get('mod_info', {})
        manifest = {'schema': 1, 'id': mod, 'version': info.get('version', '1.0.0'), 'name': info.get('name', {'EN': mod}),
                    'author': info.get('author', 'unknown'), 'license': info.get('license', 'see LICENSE'),
                    'game_version': info.get('game_version', '>=26.11'), 'content': content}
        if 'description' in info:
            manifest['description'] = info['description']
        report.append('note: created mod.json')
    write_json(manifest_path, manifest)
    print(f'built {mod}.{name}: {len(frames)} frames, {len(tile_images)} tiles, {len(pages)} atlas page(s) {textures}, '
          f'{len(rect_rows)} rects, script_count {script_count}, {len(spec.get("scripts", {}))} scripts written, '
          f'{len(sound_entries)} sounds, icon cell {rect}')
    for line in report:
        print(line)


# ------------------------------------------------------------------ check
def cmd_check(args):
    try:
        p, run = boot('check', args.mods)
    except Exception as error:   # the game itself would fail to start the same way
        print('FAILED: the game cannot start with these mods enabled')
        print(f'  {type(error).__name__}: {error}')
        print(f'  details: {OUT / "runs"} (newest folder, console.log / probe.log)')
        sys.exit(1)
    try:
        status = getattr(p.community, 'mod_status', [])
        ok = True
        for s in status:
            print(f'mod {s["id"]}: {s["state"]}' + ('' if not s['reasons'] else ' - ' + '; '.join(s['reasons'])))
            ok = ok and s['state'] == 'loaded'
        wanted = set(args.mods)
        missing = wanted - {s['id'] for s in status}
        for m in sorted(missing):
            print(f'mod {m}: not found in mods/ (folder with a mod.json whose "id" is {m})')
            ok = False
        for u in p.community.units:
            if u['key'].split('.', 1)[0] in wanted:
                print(f'  unit {u["key"]} -> UnitID {u["id"]}')
        print('PASSED: the game starts and installs these mods' if ok else 'FAILED: see the reasons above')
        sys.exit(0 if ok else 1)
    finally:
        p.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    b = sub.add_parser('base')
    b.add_argument('uids', type=int, nargs='+')
    s = sub.add_parser('build')
    s.add_argument('spec')
    v = sub.add_parser('preview')
    v.add_argument('mod')
    v.add_argument('unit')
    c = sub.add_parser('check')
    c.add_argument('mods', nargs='+')
    parser.add_argument('--mods-dir', help='mods folder (default: <game>/mods)')
    args = parser.parse_args()
    if args.mods_dir:
        global MODS
        MODS = Path(args.mods_dir).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    {'base': cmd_base, 'build': cmd_build, 'preview': cmd_preview, 'check': cmd_check}[args.command](args)


if __name__ == '__main__':
    main()
