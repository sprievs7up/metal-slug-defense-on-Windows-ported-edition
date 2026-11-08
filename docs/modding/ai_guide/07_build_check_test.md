# 07. Build, check, play-test, release

All commands run in a terminal opened in the game folder. `T` below stands for `docs\modding\ai_guide\tools\msd_unit_tool.py`:

```
windows_runtime\python.exe docs\modding\ai_guide\tools\msd_unit_tool.py <command> …
```

| Command | Needs the game core | What it does |
| --- | --- | --- |
| `base 221 [42 …]` | yes (starts it without a window, a few seconds) | inspect original units ([04_scripts.md](04_scripts.md)); writes `verification\msd_unit_tool\base_<id>.json/.png` |
| `build mods\<mod>\source\<unit>.spec.json` | no | build one unit of a mod from its spec |
| `preview <mod> <unit>` | no | draw the built unit's scripts to `verification\msd_unit_tool\preview_<mod>_<unit>.png` |
| `check <mod> [<mod> …]` | yes | the full start-up check with only these mods enabled; prints `PASSED` or `FAILED` with reasons |

The tool never touches saves, settings or the player's enabled-mod list: the core runs on a temporary save in `verification\msd_unit_tool\runs\` (safe to delete). Run `base` for the chosen base unit **before** `build`, so `build` can warn about slots you have not written. In chat-only mode (B), give the player these commands one at a time and ask them to paste the output.

## The build spec

One JSON file per unit, kept in the mod's `source/` folder. Paths inside it are relative to the mod folder.

| Key | Required | Meaning |
| --- | --- | --- |
| `mod` | yes | mod id |
| `name` | yes | unit name (lowercase letters, digits, `_`); key becomes `<mod>.<name>` |
| `facing` | yes | `"left"` or `"right"`: the direction the art faces |
| `frames_folder` | yes | folder with one subfolder per action, PNG frames inside |
| `anchor`, `folder_anchors`, `anchors` | no | where the feet are ([03_sprites.md](03_sprites.md)); default `"folder"` |
| `script_count` | no | default: the base unit's (from `base`); never smaller |
| `hit_boxes`, `attack_boxes` | yes (in practice) | lists of `[x, y, w, h]`; numbered from 1 |
| `scripts` | yes | slot number → list of items ([04_scripts.md](04_scripts.md)); unwritten slots become empty |
| `icon` | no | `{"frame": "idle/01"}` (default first frame) or `{"file": "source/icon.png"}`; options `mirror`, `fit`, `smooth` |
| `sounds` | no | list of `{"key", "file", "type", …}` ([06_sounds_and_text.md](06_sounds_and_text.md)) |
| `unit` | yes | every unit-file field except `key`, `textures`, `sprite_descriptor`, `animations`, `icon` ([02_mod_layout.md](02_mod_layout.md)) |
| `mod_info` | no | used only when `mod.json` does not exist yet: `name`, `author`, `license`, `version`, `game_version`, `description` |

Complete example (a thrower based on NATIVE(BIRD), UnitID 221; its slots: 6 idle, 7 walk, 8 melee, 9 normal attack, 10 special, 11 knock-back, 12 death, 26 projectile, 30 pause after attacking, 0–2 menu). **These slot numbers are for base 221 only**; for another base unit, take them from `base` ([04_scripts.md](04_scripts.md)):

```json
{
 "mod": "pablo_tribe", "name": "swamp_hunter", "facing": "left",
 "frames_folder": "source/swamp_hunter", "anchor": "canvas",
 "folder_anchors": {"projectile": [17, 16]},
 "hit_boxes": [[-10, -38, 20, 38]],
 "attack_boxes": [[-9, -9, 18, 18], [-40, -30, 32, 26]],
 "scripts": {
  "0":  [{"frames": ["idle/01","idle/02","idle/03","idle/04"], "ticks": 4}, "loop"],
  "1":  [{"frames": ["walk/01","walk/02","walk/03","walk/04","walk/05","walk/06"], "ticks": 2}, "loop"],
  "2":  [{"frames": ["idle/01","idle/02","idle/03","idle/04"], "ticks": 4}, "end"],
  "6":  [{"hit_box": 1}, {"frames": ["idle/01","idle/02","idle/03","idle/04"], "ticks": 4}, "loop"],
  "7":  [{"hit_box": 1}, {"frames": ["walk/01","walk/02","walk/03","walk/04","walk/05","walk/06"], "ticks": 2}, "loop"],
  "8":  [{"hit_box": 1}, {"frames": ["melee/01","melee/02","melee/03"], "ticks": 2}, {"attack_box": 2},
         {"frames": ["melee/04","melee/05"], "ticks": 2}, {"attack_box": -1}, {"frames": ["melee/06"], "ticks": 4}, "end"],
  "9":  [{"hit_box": 1}, {"frames": ["throw/01","throw/02","throw/03"], "ticks": 2},
         {"bullet": 26, "group": 0, "at": [-20, -20]}, {"sound": 865}, {"frames": ["throw/04","throw/05"], "ticks": 3}, "end"],
  "10": [{"hit_box": 1}, {"frames": ["throw/01","throw/02","throw/03"], "ticks": 2},
         {"bullet": 26, "group": 0, "at": [-20, -20]}, {"frames": ["throw/04","throw/05"], "ticks": 3}, "end"],
  "11": [{"move": [300, 0, -10, 0]}, {"frames": ["hit/01","hit/02","hit/03"], "ticks": 3}, "end"],
  "12": [{"frames": ["death/01","death/02","death/03","death/04"], "ticks": 3}, {"wait": 30}, "end"],
  "26": [{"attack_box": 1}, {"frames": ["projectile/01","projectile/02","projectile/03"], "ticks": 1}, "loop"],
  "30": [{"hit_box": 1}, {"frames": ["idle/01","idle/02","idle/03","idle/04"], "ticks": 4}, "loop"]
 },
 "icon": {"frame": "idle/01"},
 "unit": {
  "base_id": 221, "faction": 4, "ap": 80, "shop_price": 100, "available_from_start": true,
  "hp_multiplier": [4, 3], "production_reference_id": 221, "production_interval_multiplier": [1, 1],
  "special_damage_multiplier": [1, 1],
  "localization": {
   "EN": {"name": "SWAMP HUNTER", "description": "STAND. ATK : Dynamite     SPEC. ATK : Dynamite\nA hunter of the swamp tribe.\nThrows lit dynamite."},
   "ES": {"name": "CAZADOR DEL PANTANO", "description": "ATQ. ESTÁND.: Dinamita     ATQ. ESPEC.: Dinamita\nCazador de la tribu del pantano.\nLanza dinamita encendida."}
  }
 },
 "mod_info": {"name": {"EN": "Pablo's Tribe"}, "author": "Pablo", "license": "CC-BY-4.0", "version": "1.0.0"}
}
```

`build` prints what it made, then notes and WARNINGs. Treat every WARNING: a slot the base unit uses but the spec does not write, a reduced colour count, a frame folder anchored per frame. Then run `preview` and look at the sheet: feet on the ground line, no sideways sliding, boxes where they should be, attack boxes and `bullet` at the intended frames.

## Checking

1. `T check <mod>` — must print `PASSED` and list the units with their UnitIDs. On `FAILED`, read the reasons (they name the file and field), fix the spec or files, rebuild, check again. The run's `console.log` and `probe.log` are in the newest folder under `verification\msd_unit_tool\runs\`.
2. Optional quick check without the core: `windows_runtime\python.exe content_tool.py check-mods --enable <mod>` (add `--mods <folder>` for a mods folder other than `mods\`) prints JSON; the mod's `state` must be `loaded`. It misses some errors that `check` finds.

`build` also prints each frame folder's canvas size and foot pixel, and the frames that no script uses; use them to spot actions that will jump and material you forgot.

Common errors and fixes:

| Message (part) | Fix |
| --- | --- |
| `asset … must start with "<mod>_"` | rename the file in `assets/` |
| `unit key must start with "<mod>."` | the unit `key` / spec `mod` is wrong |
| `… supports base units [..], not N` | that behaviour does not work with this `base_id` |
| `Animation references invalid frame` / `child script` / `collision rectangle` | a frame, slot or box number in a script does not exist |
| `Sprite rectangle outside its atlas` | the atlas was rebuilt without the descriptor, or edited by hand; rebuild |
| `use behaviors instead` | an internal field was written; use the behaviour |
| `Invalid rational unit multiplier` | a fraction outside 1–10000 or above ×100 |
| `"ura_page" is reserved for official content` | remove `ura_page` from the mod's world; publish its stages as a custom EVENT |

## Play-test (the player)

1. Start the game, Title → OPTION → MODS, enable the mod, restart the game. (Mods take effect after a restart.)
2. Shop or CUSTOMIZE → UNIT: icon, name, description, price. Buy it (it is on sale from the start when `available_from_start` is true).
3. Unit menu → ACTION: idle, walk, melee, normal attack, special.
4. F7 opens the LAB. Its unit list contains every unit, owned or not. Put the new unit on one side and a few enemies on the other; also try it as the enemy, so you see it mirrored.
5. Check, and report with the template in [01_conversation.md](01_conversation.md): feet on the ground, walk speed vs. legs, attacks hit at the right frame, projectile start point and flight, special, knock-back, every death type (fire and explosion deaths need enemies with those attacks), sounds, the unit's size next to original units.

F12 saves a screenshot. Fix one thing at a time, rebuild, `check`, and ask for the next test.

## Release

- Raise `version` in `mod.json` for every shared change; never rename the mod id or unit keys after release.
- `LICENSE` or `CREDITS.txt`: author of the mod, the source and author of every sprite and sound, and the licence the player chose. Original game material is not included; files referenced by name are not copied.
- Share the whole `mods/<mod id>/` folder (zip it). `source/` may be left out if the player prefers; keep it for future rebuilds.
- Players install it by unzipping into their `mods/` folder and enabling it in OPTION → MODS. Online matches only pair players with the same mods and versions.
