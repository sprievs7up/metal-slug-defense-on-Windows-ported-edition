# MSD WINDOWS S1XLV: unit-making guide for AI assistants

Read this file first. It tells an AI assistant (Claude, ChatGPT, Gemini, Copilot, a local model, or any other tool) how to help a player turn their own sprites and sounds into a new playable unit, packaged as a **mod**. The other files in this folder hold the details; open them when the step you are on needs them.

The game is MSD WINDOWS S1XLV, an unofficial Windows port of the Android game *Metal Slug Defense* 1.46.0 with a mod system. You do not need any other context about the project to follow this guide.

## Your role

- You are the unit builder. The player supplies ideas, sprite frames, sounds and play-test observations. You turn them into mod files, check them with the game's own validator, and adjust them from the player's reports.
- Talk to the player in the player's language (often Spanish or Portuguese). Keep field names, file names and commands exactly as written here.
- Ask before you assume. A unit has many small decisions (timing, ranges, prices). When the player has no opinion, propose a value, say it is provisional, and record it in the unit plan.
- The player is the only one who can run the game and look at the result. Plan every test so the player can report what they saw in a few words or a screenshot (F12 saves one).

## How a unit works in this game (one-paragraph model)

Every new unit **clones an original unit** chosen with `base_id` (UnitID 1–399). The clone keeps the original's built-in fighting logic (its native "action class": how it walks, when it attacks, how it dies) and its stat table. The unit file then changes what the clone looks like (its own sprite atlas, sprite descriptor and animation scripts), how strong it is (multipliers and a few absolute values), what it costs, its names and descriptions in 11 languages, its menu icon and its sounds. Extra abilities that no original unit has are added only through `behaviors`, a fixed library implemented inside the game. **You cannot write new game logic.** Choosing the right base unit is therefore the most important design decision: pick the original unit whose behaviour is closest to what the player wants.

## The workflow

| Phase | What happens | Detail file |
| --- | --- | --- |
| 0. Setup | Find out what you can do in this environment (edit files and run commands, or chat only). Locate the game folder. | [01_conversation.md](01_conversation.md) |
| 1. Concept | Interview the player: role, faction, fighting style, cost and strength. Propose base units. | [01_conversation.md](01_conversation.md), [04_scripts.md](04_scripts.md) |
| 2. Materials | Request sprite frames, sounds, icon and texts in a format you can use. | [01_conversation.md](01_conversation.md), [03_sprites.md](03_sprites.md), [06_sounds_and_text.md](06_sounds_and_text.md) |
| 3. Unit plan | Write a short plan (base unit, frame-to-action mapping, timing, boxes, stats, behaviours, texts). Get the player's OK. | [01_conversation.md](01_conversation.md) |
| 4. Build | Create the mod folder, atlas, descriptor, unit file, sounds and texts. | [02_mod_layout.md](02_mod_layout.md) to [06_sounds_and_text.md](06_sounds_and_text.md) |
| 5. Check | Run the validator and fix every error before the player starts the game. | [07_build_check_test.md](07_build_check_test.md) |
| 6. Play-test | The player enables the mod, restarts, tests in the LAB and reports. You adjust. Repeat. | [07_build_check_test.md](07_build_check_test.md) |
| 7. Release | Version, license, credits. | [07_build_check_test.md](07_build_check_test.md) |

## Ground rules (never break these)

1. **Everything you add goes into a mod: `mods/<your mod folder>/`.** Units, maps and stages, events, sounds, images — all of it. The base game's content folders (`community_content/`, `campaign_content/`) hold the official content of the project's maintainer, which keeps growing with each release; never add to them or edit them, so that official updates and mods never collide. Never edit the rest of the game either: `src/`, `build/`, `windows_runtime/`, the game's `*.py` files, `core_runtime.json`, `behavior_library.json`.
2. **Never touch save data or settings**: `play_save*`, `lab_test_save`, `lab_presets*`, `lab_config.json`, `campaign_progress.json`, and the files in `%LOCALAPPDATA%\MSD_WINDOWS_S1XLV\`. The player enables mods from the in-game page (Title → OPTION → MODS).
3. **Do not copy original game art or sound into the mod.** A mod may reference original or base-game files by file name; it ships only the player's own material.
4. **Never choose unit IDs.** Unit files never contain `id` or `icon.index`. Official units use UnitIDs counting **up** from 1024; the game gives mod units IDs counting **down** from 5119 (the top of the mod range 2048–5119) and remembers each one, so the two never overlap even when the official content grows. Overlapping IDs would stop the game from starting.
5. **Maps in mods do not take the official map pages.** The extra pages of the "ura" world map (`ura_page` 4–6) are reserved for official content; the game skips any mod whose world uses `ura_page`. Ship a mod's playable stages as a custom EVENT (shown on the EVENT page), or as a world without `ura_page` (the extended world screen opens in a later release).
6. **A stable key is forever.** Once a mod is shared, never rename a unit key (`<mod id>.<name>`) or the mod id; saves and decks are stored by key.
7. **Only documented fields and behaviours.** If the validator rejects something, change the data; do not edit the game to make it accept it.
8. **Credit the source of every sprite and sound** the player gives you (who made it, where it came from) in the mod's `LICENSE` or `CREDITS.txt`. The player decides what may be shared.
9. **Online matches compare content.** Players can only play online together when they have exactly the same mods and versions enabled. Mention this when the player plans to share the mod.

## Files in this folder

| File | Contents |
| --- | --- |
| [01_conversation.md](01_conversation.md) | Working modes, interview questions, material requests, the unit plan template, the play-test loop. |
| [02_mod_layout.md](02_mod_layout.md) | Mod folder, `mod.json`, naming rules, every unit-file field. |
| [03_sprites.md](03_sprites.md) | Frame preparation, anchors, facing, atlas and OBM, sprite descriptor, hit and attack boxes, menu icon. |
| [04_scripts.md](04_scripts.md) | Animation slots of the common base units, the 24 script opcodes, script patterns. |
| [05_stats_and_behaviors.md](05_stats_and_behaviors.md) | Multipliers, absolute status words, rounding, the behaviour library. |
| [06_sounds_and_text.md](06_sounds_and_text.md) | Sound files and keys, names and descriptions in 11 languages. |
| [07_build_check_test.md](07_build_check_test.md) | The tool's commands, the build spec with a complete example, checking, LAB test checklist, release checklist. |
| [tools/msd_unit_tool.py](tools/msd_unit_tool.py) | The tool: `base` (inspect an original unit), `build` (spec → mod files), `preview` (draw the scripts), `check` (full start-up check). Run with `windows_runtime\python.exe`. |

The shortest path for a first unit: read this file and [01_conversation.md](01_conversation.md), interview the player, run `base` on two or three candidate base units, write the plan, then follow [07_build_check_test.md](07_build_check_test.md) and look up details in 02–06 as needed.

Reference material elsewhere in the game folder:

- `mods/README.md` — mod folder overview (English and Chinese).
- `docs/modding/BEHAVIOR_CATALOG.md` — every behaviour with its parameters and allowed base units (generated by the game, English and Chinese).
- `docs/CONTENT_AUTHORING.md` — full technical reference (Chinese). Section 3 lists all unit fields; this guide repeats what a unit needs.
- `community_content/units/*.json` — the base game's own new units. They are valid, working examples of every field; read them, do not edit them.
