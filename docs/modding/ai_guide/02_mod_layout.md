# 02. Mod folder, mod.json and the unit file

## Folder layout

```text
mods/
  <mod id>/                     the folder name may differ from the id, but keep them equal
    mod.json                    manifest (required)
    units/<unit>.json           one file per unit (only *.json directly in units/ are read)
    sounds/<unit>.json          sound list (only when the mod has sounds)
    assets/<mod id>_*           every file here MUST start with "<mod id>_": atlases (.obm), sprite descriptors (.json),
                                icon page (.obm), sounds (.msdf)
    source/                     the player's material and your build specs (not read by the game)
    notes/                      unit plans, change log (not read by the game)
    LICENSE or CREDITS.txt      rights and credits
```

`docs/modding/ai_guide/tools/msd_unit_tool.py build` creates `units/`, `assets/`, `sounds/` and `mod.json` for you from a spec in `source/` ([07_build_check_test.md](07_build_check_test.md)). You still need to know what it writes, so you can explain errors and edit fields by hand.

## mod.json

```json
{"schema": 1, "id": "pablo_tanks", "version": "1.0.0",
 "name": {"EN": "Pablo's Tanks", "ES": "Los tanques de Pablo"},
 "author": "Pablo", "license": "CC-BY-4.0",
 "game_version": ">=26.11", "behavior_library": ">=45",
 "depends": [], "conflicts": [],
 "description": {"EN": "Two new tanks for the Regular Army."},
 "content": {"units": "units/", "sounds": "sounds/"}}
```

| Field | Rule |
| --- | --- |
| `schema` | always `1` |
| `id` | `[a-z][a-z0-9_]{1,31}`; not `s1xlv`, `original`, `body`, `test`. Permanent. |
| `version` | `1`, `1.0`, `1.0.0` or `1.0.0.0` (digits only). Raise it on every shared change. |
| `name`, `description` | language code → text (`EN`, `JP`, `KR`, `ES`, `PT`, `RU`, `FR`, `DE`, `IT`, `ZT`, `ZS`). Missing languages fall back to English, then to the first language given. |
| `author`, `license` | required strings. |
| `game_version` | optional minimum, e.g. `">=26.11"` (the game's version is in `branding.json`, `display_version`). |
| `behavior_library` | optional minimum version of the behaviour library (`docs/modding/BEHAVIOR_CATALOG.md` title shows the current one). Write it when you use `behaviors`. |
| `depends`, `conflicts` | other mod ids. A mod may use sounds and units of the mods it depends on. |
| `content` | keys allowed: `units`, `patches`, `campaign`, `sounds`, `events`. This guide uses `units` and `sounds`. |

The mod is checked as a whole when the game starts. If anything fails, the whole mod is skipped and the reasons are logged; the base game still starts. **Exception:** a few errors (wrong OBM byte size, wrong number of textures when there is no descriptor, a missing required unit field) can stop the game from starting. Always run the full check (`msd_unit_tool.py check`) before giving the mod to the player.

## Names and references

- Unit key: `<mod id>.<name>` (e.g. `pablo_tanks.heavy_tank`). The tool uses `name` = the spec's `name` (lowercase, digits, `_`).
- Sound key: `<mod id>.<name>` (e.g. `pablo_tanks.cannon`).
- Files are referenced by file name only, never by path. The game looks for a referenced file in this order: this mod's `assets/`, the base game's `community_content/`, the original game's resources (`game_data/assets/com.snkplaymore.android003/`). So a mod may use an original atlas or sound by name without shipping it.
- The sprite descriptor must be a file of the mod itself.
- The game assigns the runtime UnitID and keeps it in `%LOCALAPPDATA%\MSD_WINDOWS_S1XLV\mods_ids.json`. Mod units are numbered **downward from 5119** (mod range 2048–5119); official units count upward from 1024, so the two cannot overlap. Never write `id` or `icon.index`. (`msd_unit_tool.py check` runs with a fresh, temporary ID file, so it always shows the IDs a first-time install would get.)
- Everything the mod adds stays in the mod folder ([README.md](README.md), rule 1). The extra ura-map pages are reserved for official content: the game skips a mod whose world uses `ura_page` (rule 5).

## How the base unit is used

`base_id` (1–399) selects the original unit to clone. The new unit takes from it:

- the **action class**: all fighting logic, which animation slot is played in which situation, how projectiles fly, how it dies;
- the **data row**: AP, HP, ranges, damages, speeds, cooldowns at every level, attributes, resistances;
- unless the unit has its own `sprite_descriptor`: its atlases, frames, boxes and scripts.

Everything in the unit file then adjusts this clone. Run `msd_unit_tool.py base <UnitID>` to see what the base unit has ([04_scripts.md](04_scripts.md)).

## Two ways to give a unit its look

| | A. Own frames (the normal case) | B. Repaint the base unit's atlas |
| --- | --- | --- |
| Use when | the player has their own sprite frames | the player only recolours or redraws the original sprite sheet in place |
| Files | own atlas OBM(s) + own `sprite_descriptor` + all scripts | `textures` = repainted copies of the base atlases (same count, same size, same layout), no descriptor |
| Scripts | every slot must be written (unwritten slots would point at the base unit's frame numbers) | unchanged scripts are inherited; you may override single slots |
| Tool | `msd_unit_tool.py build` does it all | convert each repainted PNG with `content_tool.py import-png in.png assets/<mod>_<name>_0.obm` and write the unit file by hand |

The rest of this guide describes way A. For way B, `base` writes `base_<UnitID>.png` so you can see which atlas page holds which frames; the texture names of the base unit are in `base_<UnitID>.json` (`descriptor.textures`). Original atlases use a 16-bit palette format; the repainted page must be converted from PNG (256 colours max, index 0 is transparent).

## The unit file

The tool writes `units/<name>.json` from the spec's `"unit"` object and adds `key`, `textures`, `sprite_descriptor`, `animations`, `icon` and (if missing) `image_direction`. Put every other field in the spec's `"unit"` object.

### Required

| Field | Meaning |
| --- | --- |
| `base_id` | original UnitID to clone (1–399). |
| `faction` | 0–4, the faction logo and menu filter: 0 Regular Army (e.g. 5 SANDBAG), 1 Rebel Army (2 REBEL INFANTRY, 3 DI-COKKA), 2 the faction of 133 SPECIAL FORCE (RIDER), 3 invaders and zombies (192 INVADER, 313 ZOMBIE), 4 independents, mummies and natives (61 MUMMY, 221 NATIVE(BIRD)). `base` prints the faction of any original unit. |
| `ap` | deployment cost in battle (1–100000). |
| `shop_price` | medals (1–32767). |
| `available_from_start` | `true`: on sale from the start. `false`: also write `shop_unlock_reference_id` (an original UnitID 0–511; the unit goes on sale when that one does). |
| `hp_multiplier` | HP × [a, b] relative to the base unit. |
| `production_reference_id` | original UnitID whose redeploy time is used (normally the same as `base_id`). |
| `production_interval_multiplier` | redeploy time × [a, b]. |
| `special_damage_multiplier` | special-attack damage × [a, b]. |
| `localization` | language code → `{"name": …, "description": …}`; at least one language ([06_sounds_and_text.md](06_sounds_and_text.md)). |
| `icon` | written by the tool. |
| `textures`, `sprite_descriptor`, `animations` | written by the tool. |

`[a, b]` means the fraction a/b; a and b are integers 1–10000 and a/b ≤ 100. `[1, 1]` keeps the base value.

### Optional (most common)

| Field | Meaning |
| --- | --- |
| `knockback_threshold_multiplier` | how much damage it takes before being knocked back, × [a, b]. Project rule: same as `hp_multiplier` unless the player wants otherwise (the tool fills it in). |
| `damage_multiplier`, `move_speed_multiplier`, `attack_range_multiplier`, `attack_wait_multiplier`, `special_cooldown_multiplier`, `knockback_distance_multiplier`, … | see [05_stats_and_behaviors.md](05_stats_and_behaviors.md). |
| `status_word_values`, `status_float_values` | absolute values for single stats ([05](05_stats_and_behaviors.md)). |
| `behaviors` | extra abilities from the behaviour library ([05](05_stats_and_behaviors.md)). |
| `attack_attributes` | `{"melee": n, "normal": n, "special": n}`, 0–4: 1 fire, 2 explosion (decides how the victim dies). |
| `attribute_resistance_tiers` | five integers 0–3 (damage ×0.8 / ×1.0 / ×1.2 / ×1.5 per attack attribute). |
| `image_direction` | 90 if the art faces right, 270 if it faces left (the tool sets it from `"facing"`). |
| `minimap_marker` | `[w, h]` 1–64, the battle minimap mark (infantry 4×4; big units ≈ image width/25 × height/21.5). |
| `special_effect_size` | `[w, h]` of the blue glow under the unit when its special is ready (big vehicles ≈ [160, 90]). |
| `draw_priority` | −1000…1000; lower is drawn first (behind). Big units use about −90. |
| `upgrade_cost_base` | MSP cost base for upgrades (1–100000). |
| `menu_reference_id` | original UnitID whose menu record is used; needed only for base units that have no menu record of their own (the full check reports it). |
| `internal_only` | `true` for helper units that are never bought (summoned or built units). |
| `tags` | free strings, e.g. `["ms6"]`. |
| `identity` | free text shown nowhere; e.g. `"Rebel Army"`. |

### Forbidden

`id`, `icon.index`, and the internal adapter fields (`zombie_spec`, `native_action`, `child_unit_key`, `flame_interrupt`, …). The validator answers "use behaviors instead"; use the matching behaviour from the library.
