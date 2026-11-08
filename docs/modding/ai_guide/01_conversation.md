# 01. Working with the player

This file covers phases 0–3 and 6 of the workflow: how you and the player exchange information, which questions to ask, which materials to request, and how to run the play-test loop.

## 0. Setup: find out how you can work

Ask, or check yourself, which of these two modes applies.

| Mode | You can | You produce | The player does |
| --- | --- | --- | --- |
| **A. Agent** (Claude Code, Codex, Cursor, Copilot agent, Aider, …) | read and write files, run commands | the files themselves; you run the build and the validator | supplies materials, runs the game, reports |
| **B. Chat only** (web chat, phone app) | read text and images the player pastes | complete file contents in code blocks, each with its exact path | saves each file, runs the commands you give, pastes the output back |

In both modes the binary files (atlas, icon page, sounds) are produced by the tool `docs/modding/ai_guide/tools/msd_unit_tool.py` from a JSON spec you write ([07_build_check_test.md](07_build_check_test.md)). You never have to emit binary data in chat. The same tool inspects original units and runs the full check.

Setup checklist:

1. The game folder. It is the folder that contains `MSD WINDOWS S1XLV.exe`, `windows_runtime\python.exe` and `mods\`. All commands in this guide run from that folder in a Windows terminal (PowerShell or cmd).
2. The game version: `branding.json` or the title screen. Write it into `mod.json` as the minimum (`"game_version": ">=26.11"`).
3. A mod id: lowercase ASCII letters, digits and `_`, starting with a letter (for example `pablo_tanks`). It is permanent (see the ground rules in [README.md](README.md)). Every file the mod ships starts with this id.
4. Whether the mod already exists. If `mods/<mod id>/` is there, read it first and extend it; never overwrite another person's mod.

## 1. Concept interview

Ask in small groups (three or four questions at a time), not as one long form. Summarise the answers back.

1. **What is it?** Name, one-sentence idea, where it comes from (another Metal Slug game, an original design, a fan sprite).
2. **Role.** Infantry, vehicle, aircraft, building or structure built by an engineer, summoner, support. Ground or air.
3. **Side and faction.** Which army it belongs to (Regular Army, Rebel Army, aliens/monsters, independent). This sets the faction logo and filter in the menus.
4. **How it fights.** Melee or ranged; what the normal attack is (bullets, a thrown object, a beam, a bite); what the special attack is; whether it can hit air units.
5. **Strength and cost.** Cheap fodder, mid-cost, or boss-like. Rough AP cost (deployment cost in battle; original infantry 50–150, tanks 200–400, bosses 999) and shop price in medals.
6. **Closest original unit.** Ask whether the player already knows an original unit that moves and attacks like the new one. If not, propose two or three from [04_scripts.md](04_scripts.md) (section "Choosing a base unit") and explain the difference in one line each.

Then state the decision: "Base unit: UnitID N (name). It walks / attacks / dies like this: … Your sprites will replace its look."

## 2. Material requests

Ask for exactly what the base unit needs (its action list is in [04_scripts.md](04_scripts.md)). Send the player this request, adapted:

**Sprites** (details in [03_sprites.md](03_sprites.md)):

- PNG with a transparent background, one frame per file. A sprite sheet is also fine if the frames sit on a regular grid or are clearly separated; say so and you will cut it.
- All frames of one unit at the same scale, facing the same way. Tell me which way they face (left or right).
- One folder per action, frames numbered in play order: `idle/01.png …`, `walk/`, `attack/`, `special/`, `hit/` (knocked back), `death/`. Optional: `death_explosion/`, `death_fire/`, `projectile/`, `effect/`, `retreat/`.
- For each attack: which frame fires or hits.
- The original frame timing if known (frames per second, or "each frame lasts N ticks"; the game runs at 30 ticks per second).
- A menu icon (or let me make one from the idle frame).

**Sounds** (details in [06_sounds_and_text.md](06_sounds_and_text.md)): Ogg Vorbis or WAV, one file per sound, named by use (`shot.ogg`, `death.ogg`). Or the name of an original game sound to reuse.

**Texts**: the unit name and a three-line description in the player's language. You translate into the other ten languages; ask the player to check the languages they know.

**Credits**: who made each sprite sheet and sound, and the source link.

If material is missing, propose a fallback and say what it costs: reuse the base unit's original death or projectile animation by leaving that slot unchanged, mirror frames, hold a frame longer, or skip an optional action.

## 3. The unit plan

Before building, write the plan and ask the player to confirm it. Keep it in the mod folder as `mods/<mod id>/notes/<unit>_plan.md` (mode A) or in the chat (mode B). Template:

```markdown
# <Unit name> (<mod id>.<unit>)
- Base unit: UnitID <n> <name>; action class <class>; facing of the sprites: left/right
- Role / faction: …
- AP <n>, shop price <n> medals, available from start: yes/no
- Stats vs. base unit: HP ×a/b, damage ×…, move speed ×…, range …, redeploy time ×…, special cooldown ×… (provisional values marked "(prov.)")
- Actions → slots:
  | Action | Slot | Frames | Ticks per frame | Events |
  | idle | 6 | idle/01–04 | 4 | loop |
  | normal attack | 9 | attack/01–08 | 3 | attack box 1 on frame 5, sound shot |
  …
- Hit box (body): x, y, w, h; attack boxes: …
- Projectile / effects: …
- Behaviours: … (or none)
- Sounds: key → file / original SoundID
- Texts: EN/ES/… name and description
- Credits: …
- Open questions: …
```

## 6. The play-test loop

After the validator passes ([07_build_check_test.md](07_build_check_test.md)), the player tests in the game. Give a numbered checklist that fits this unit, for example:

1. Title → OPTION → MODS: enable the mod, restart the game.
2. The unit appears in the shop (or CUSTOMIZE → UNIT) with the right icon, name and description. Buy it and add it to a deck.
3. Open its unit menu: the ACTION preview plays idle, walk, attacks and special.
4. Press F7 to open the LAB, put the unit on one side and a few enemies on the other, start the battle.
5. Watch: feet on the ground line, walking speed matches the leg motion, attacks hit at the right frame, the projectile flies from the weapon, the special works, knock-back and death play fully, sounds play.

Ask for the report in this form (the player may answer in any language):

```text
What I did:
What I expected:
What happened:            (screenshot with F12 if it is visual)
Stage / enemy used:
```

Then change one thing at a time where possible, rebuild, re-run the validator, and ask for the next test. Keep a short change log in the plan file: what changed and why. Mark values the player confirmed; keep the rest marked provisional.
