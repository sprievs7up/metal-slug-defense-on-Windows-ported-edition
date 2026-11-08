# 03. Sprites: frames, anchors, boxes, atlas and icon

## Coordinates

- Every frame is drawn relative to the **unit origin**: the point on the ground between the unit's feet. x grows to the right, **y is negative upwards** (a box from y −40 to 0 covers the 40 sprite pixels above the ground).
- Coordinates are in the art's own direction. If the art faces left (`image_direction` 270), "forward" is −x; if it faces right (90), forward is +x. The game mirrors everything (frames, boxes, offsets, movement) when the unit belongs to the other side. Never mirror the frames yourself.
- 1 sprite pixel = 2 battle units. Ranges and distances in the stats (`status word 7` etc.) are in battle units; script values (boxes, offsets) are in sprite pixels.
- Size reference: original infantry are about 40 sprite pixels tall, tanks 60–90, bosses 150+. Compare with the base unit's preview (`base_<UnitID>.png`). If the player's frames are much bigger or smaller than the original game's style, ask before scaling; scale only by whole numbers with nearest-neighbour, or not at all.

## What to ask the player for

- PNG with real transparency (no coloured background). If the sheet has a background colour, ask which colour is transparent and remove it yourself before building (mode A) or ask the player to.
- One frame per file, in one folder per action, numbered in play order: `idle/01.png`, `idle/02.png`, … The folder and file name without `.png` (for example `idle/01`) is the frame's name in the spec.
- All frames of a folder on the **same canvas size**, with the character standing at the same place. This is how sprite rips are usually cut; it keeps the feet still between frames.
- Projectiles and effects in their own folders (`projectile/`, `explosion/`), centred on their canvas.

## Anchors (where the feet are)

The tool needs, for every frame, the pixel inside the PNG that sits on the unit origin. Choose one of these in the spec:

| Spec | Anchor | Use when |
| --- | --- | --- |
| `"anchor": "canvas"` | bottom centre of the canvas, per folder | the frames were cut on uniform canvases with the feet on the bottom edge, centred |
| `"anchor": "folder"` (default) | bottom centre of the union of all opaque pixels of the folder | uniform canvases, feet not on the bottom edge; can drift sideways when a weapon sticks out in some frames |
| `"anchor": "frame"` | bottom centre of each frame's own opaque pixels | single still images; makes animations wobble |
| `"anchor": [x, y]` | the same pixel in every frame | all folders share one canvas |
| `"folder_anchors": {"projectile": [17, 16]}` | one pixel for a whole folder | flying projectiles (usually their centre), or any folder that needs a fix. Ground explosions and impact effects usually keep their origin on the ground (bottom centre); check the base unit's PNG for the same effect before choosing |
| `"anchors": {"walk/03": [30, 61]}` | one frame | single frames that jump |

Then **look at the preview** (`msd_unit_tool.py preview`): the white cross is the origin, the blue line is the ground. Check that:

- feet touch the line in idle, walk and attack frames;
- the body does not slide sideways between frames of one action;
- the body stands at the **same place relative to the cross in every action** (idle, walk, attacks, knock-back). A folder whose canvas was cut differently makes the unit jump whenever it switches action. `build` prints each folder's canvas size and foot pixel to help compare; fix such a folder with `folder_anchors`.

Fix anchors and rebuild until it looks right. A multimodal AI can read the PNG itself; otherwise ask the player to open it.

## Atlas pages (what the tool does)

- Frames are cropped to their opaque pixels; identical crops are stored once.
- Crops are packed into power-of-two pages up to 2048×2048, at most 16 pages, saved as `assets/<mod>_<name>.obm` (or `_0.obm`, `_1.obm`, …): 8-bit palette OBM, index 0 transparent.
- A page holds at most **255 colours** (semi-transparent colours are allowed and count as separate colours). With more, the tool reduces them and prints a WARNING; tell the player, and if the result looks wrong, ask for art with fewer colours or split the frames over more units.
- The sprite descriptor `assets/<mod>_<name>_descriptor.json` holds:
  - `rects`: `[x, y, w, h, ax, ay, flags, page]` — source rectangle on atlas `page`, and (ax, ay) = where the origin lies inside that rectangle (the tile's top-left is drawn at origin − (ax, ay)). `flags` bit 0 flips horizontally around the origin, bit 1 vertically. The tool writes flags 0.
  - `frames`: a flat list of groups `[count, rect index, rect index, …]`. A script shows a frame by the **offset of its group's first number in this flat list** (op0; with one rectangle per frame these are 0, 2, 4, …). Several rectangles in one group are drawn in order, later ones on top. The tool computes these offsets from frame names.
  - `script_count`, `hit_bounds`, `attack_bounds`.

## Hit boxes and attack boxes

Both are lists of `[x, y, w, h, extra]` in sprite pixels relative to the origin (top-left corner, width, height). Entry 0 is an empty placeholder that the tool adds; your boxes are numbered from 1 in the order you list them in the spec.

- **Hit box** (where the unit can be hit): give one box around the body, roughly the torso and legs, not the weapon or loose parts. Switching actions clears the hit box, so an action in which the unit can be hit must start with `{"hit_box": 1}`. **Follow the base unit's script**: where its slot sets a hit box, set yours; where it does not (original knock-back and death scripts usually have none), do not add one. The game also takes the unit's width and height from the first root script that sets a hit box. `{"hit_box": 0}` means "cannot be hit"; a unit must not stay unhittable for long in an action where the original can be hit.
- **Attack box** (what a melee blow or a projectile hits): switch it on at the frame that strikes, off two or three frames later: `{"attack_box": 1}` … `{"attack_box": -1}` (`-1` and `0` both switch it off; original scripts use 0). Each time the box is switched on, a new strike starts, so one on/off pair per intended hit. A projectile script switches its box on at the start and keeps it. The fifth value is not read by the scripts; the tool writes 0 for hit boxes and 7 for attack boxes (original attack boxes use 7 or 4).
- Size reference: original infantry hit box about 20×38 above the origin; melee boxes about 30×25 in front of the body.

The preview draws the hit box green and the attack box red for every frame.

## The menu icon

- Shown in the shop, the unit lists and the battle deployment bar, in a 50×50 cell whose inner frame is (5,5)–(45,45). Original icons face **right** and show the whole unit, about 40×40, bottom-aligned; small soldiers are drawn up to 46 pixels tall and may overlap the frame's top a little.
- Spec: `"icon": {"frame": "idle/01"}` (default: the first frame) or `"icon": {"file": "source/icon.png"}` for a hand-made icon. The tool mirrors a left-facing frame (`"mirror": false` to stop it), shrinks images larger than 40×46 (nearest neighbour; `"smooth": true` for smoother scaling; `"fit": 44` to allow a wider icon) and bottom-aligns it.
- All icons of one mod share one page `assets/<mod>_icons.obm` (512×512, 64×64 cells, 64 units). The cell of each unit is remembered in `source/icon_cells.json`; keep that file.
- A hand-made icon looks better than a shrunk frame. Offer it when the unit is larger than 40×46.
