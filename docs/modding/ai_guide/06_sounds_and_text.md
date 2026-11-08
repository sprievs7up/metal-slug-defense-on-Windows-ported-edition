# 06. Sounds and texts

## Sounds

- Format: **Ogg Vorbis**, any sample rate, mono or stereo (the game converts to its 16 kHz stereo mix when loading). The game stores it unchanged with the extension `.msdf`.
- The game folder has no WAV/MP3 → Ogg converter. Ask the player to export Ogg from Audacity (File → Export → Ogg Vorbis) or with ffmpeg: `ffmpeg -i shot.wav -c:a libvorbis -q:a 5 shot.ogg`. Trim silence at the start so the sound plays on the right tick.
- Put the files in `source/sounds/` and list them in the build spec:

```json
"sounds": [
  {"key": "pablo_tanks.cannon", "file": "source/sounds/cannon.ogg", "type": "se"},
  {"key": "pablo_tanks.death", "file": "source/sounds/death.ogg", "type": "vo", "gain": 1.5}
]
```

  `type`: `se` effect, `vo` voice, `bgm` music. Optional: `volume` 1–127, `gain` 0.1–8 (multiplies the samples, for quiet recordings), `loop` `[start s, end s]` for music. The tool copies each file to `assets/<mod>_<name>.msdf` and writes `sounds/<unit>.json`.
- In scripts: `{"sound": "pablo_tanks.cannon"}`, or the short form `{"sound": "cannon"}` for a sound listed in the same spec.
- **Original sounds** are used by number: `{"sound": 202}`. `base` shows the numbers the base unit plays and in which slot (for example the Rebel Infantry: 809 in its normal death, 807 explosion death, 808 + 283 fire death, 202 grenade explosion, 207 + 286 in slot 17). Reusing the base unit's sounds in the matching slots is a good default when the player has none. To hear a sound, the player can watch that original unit in the LAB.
- A mod may use only its own sounds, the base game's and those of mods listed in `depends`. All mods together share about 290 free sound slots; keep the count small.

## Names and descriptions

Each unit has a name and a description in up to 11 languages:

| Code | Language | Code | Language |
| --- | --- | --- | --- |
| EN | English | RU | Russian |
| JP | Japanese | FR | French |
| KR | Korean | DE | German |
| ES | Spanish | IT | Italian |
| PT | Portuguese | ZT | Chinese (traditional) |
| | | ZS | Chinese (simplified) |

- At least one language is required. A missing language falls back to English, or to the first language given. Write all 11: write the player's language from their words, translate the others yourself, and ask the player to check the languages they know. Say which ones are machine translations in the plan.
- Names are short and in capitals for Latin scripts, like the original units (`HEAVY TANK`, `TANQUE PESADO`).
- Descriptions follow the original three-line layout, lines separated by `\n`:

```text
STAND. ATK : Machine gun     SPEC. ATK : Cannon x3
A heavy tank built for the Regular Army.
Slow but hard to stop.
```

  Line 1 names the normal and special attacks, separated by three to five spaces, with these labels (the most common form in the base game's units):

  | Code | Line 1 | Code | Line 1 |
  | --- | --- | --- | --- |
  | EN | `STAND. ATK : …     SPEC. ATK : …` | RU | `СТАНД. АТАК: …     СПЕЦ. АТАК: …` |
  | JP | `通常攻撃：…     特殊攻撃：…` | FR | `ATT. STAND : …     ATT. SPÉ : …` |
  | KR | `일반 공격: …     특수 공격: …` | DE | `STAND. ATK : …     SPEC. ATK : …` |
  | ES | `ATQ. ESTÁND.: …     ATQ. ESPEC.: …` | IT | `ATC STAND.: …     ATC SPEC.: …` |
  | PT | `ATQ. PADR.: …     ATQ. ESPEC.: …` | ZT | `普通攻擊：…     特殊攻擊：…` |
  | | | ZS | `普通攻击：…     特殊攻击：…` |

  Lines 2–3 describe the unit. Keep each line under about 50 characters; longer text wraps in the unit menu.
- When the description names an original unit, use that unit's official name in each language (the player can see it in the game with the language switched).
