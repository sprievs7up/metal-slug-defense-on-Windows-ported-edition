# 04. Animation scripts and slots

## Basics

- The game runs at **30 ticks per second**. A script is a list of commands executed by one sprite layer. Only waiting consumes time; every other command runs immediately in the same tick.
- A unit has `script_count` script **slots** (numbered from 0). The base unit's **action class** decides which slot is played in which situation. The slot numbers differ from class to class; there is no universal list.
- Every script must end with `"loop"` (start again) or `"end"` (stop on the last frame and tell the action class the action is over). Attacks, knock-back and deaths end with `"end"`; idle, walk and projectiles loop.
- With own frames you must write **every slot the base unit uses**. A slot you do not write becomes empty (nothing drawn, ends at once). The build tool lists the base unit's slots you did not write.

## Step 1: inspect the base unit

```
windows_runtime\python.exe docs\modding\ai_guide\tools\msd_unit_tool.py base 221
```

It prints the action class, facing, faction, script_count, the main stats at Lv1/10/20/30/40/50 and one line per non-empty slot: number of distinct frames, number of steps (frames shown, one preview cell each), length in ticks, `loop`/`end`, and events with the tick they happen at, for example `bullet[26, 1, -20, -50]@6` (fires the projectile script 26 at tick 6) or `attack_box[1]@4`. It also writes `verification\msd_unit_tool\base_221.json` (everything, including each script command) and `base_221.png` (every slot drawn frame by frame). **Look at the PNG**: it shows at a glance which slot is idle, walk, each attack, each death, the projectile and its explosion.

Then make the slot table of the plan: for each slot of the base unit, which of the player's actions replaces it, with the same role, a similar length and the events at similar moments (the action class may wait for the `end`, for the attack box, or for the projectile).

## Battle states and the slots of verified classes

The action class switches between these states:

| State | Meaning |
| --- | --- |
| 10 | idle / waiting |
| 20 | advancing |
| 30 | melee attack |
| 40 | normal (ranged) attack |
| 50 | special attack |
| 70 | pause after an attack |
| 80 | knocked back |
| 100 / 110 / 120 | death: normal / by explosion / by fire |

Menu slots (all classes): **0** is the deck and menu pose (played at original size), **2** is played in the shop after buying, **1** is probably the menu walk. The unit menu's ACTION preview plays the battle slots of states 10, 30, 40 and 50.

State → slot for classes verified in this project (other classes: use `base` and its PNG):

| Base unit (class) | 10 | 20 | 30 | 40 | 50 | 70 | 80 | 100 / 110 / 120 | Other |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 DI-COKKA (DiCokka) | 6 | 7 | 9 | 9 | 10 | 8 | 11 | 12 | projectile always 13, its hit 14 (op22's slot value is ignored) |
| 221 NATIVE(BIRD) (NativeBird) | 6 | 7 | 8 | 9 | 10 | 30 | 11 | 12 | normal attack's projectile 26 |
| 313 ZOMBIE (YOUNG MAN) (ZombieBrain) | 6 | 7 | 9 | 9 | 10 | 11 | 12 | 13 / 13 / 15 | projectile hit 21, landing 22 |
| 200 WINGED INVADER (WingedInvader) | 6 | 7 | 8 | 8 | 9 | 10 | – | 11 | |
| 394 IRON SLIDER | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | |
| 32 (Tnabe, anti-air position) | 6 | 6 | 8 | 9 | – | 6 | 12 | 13 | projectile ends: 51 hit, 48 landing |
| 2 REBEL INFANTRY (Zako) | – | – | – | – | – | – | – | 12 / 13 / 14 | see the note below |
| 162 ROCKET BOMB SOLDIER (MissileZako) | – | – | – | – | – | – | – | 13 / 13 / 15 | |
| 182 W.SOLDIER (ZakoSnow) | 7 | 7 | 7 | 7 | 7 | – | none | 13 / 13 / 15 | slot 7 keeps an attack box |
| 4 (Donou, sandbag) | 6 | 6 | – | – | – | – | – | 8 | 60 (hit) 7 |

"–" means not verified, not "unused". Always confirm with `base`.

**Rebel Infantry (2), observed but not verified state by state:** 6 idle, 7 walk, 9 knife (its normal attack: melee range 0, normal range 40), 11 grenade throw (special; fires projectile 15), 15 the flying grenade, 16 the grenade's explosion (no script refers to it; the class spawns it), 12/13/14 deaths. Slot 8 is a laughing loop (probably the pause after an attack), slot 10 is empty, slot 17 is a 2-tick pose with sounds 207 and 286; which slot plays during knock-back is not known.

**When a slot's role is unclear**, fill it with the most plausible pose of the same length (for a possible knock-back slot: the player's hit frames; for a pause: idle frames), write it into the plan as "unverified", and ask the player to watch that moment in the LAB (knock the unit back with a strong enemy, let it finish an attack) and report which frames appear. A slot that is empty in the base unit is most likely unused; a short filler does no harm.

## Choosing a base unit

Pick the class whose behaviour matches the player's idea; its look does not matter. Classes used by the base game's own new units (name, class, AP, Lv1 HP, range in battle units, script_count):

| UnitID | Name | Class | Kind | AP | HP Lv1 | Range | Scripts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | REBEL INFANTRY | Zako | infantry, knife + grenade | 25 | 180 | 40 | 18 |
| 42 | REBEL RIFLEMAN | ZakoRifle | infantry, rifle | 35 | 180 | 320 | 21 |
| 45 | BAZOOKA SOLDIER | ZakoBazooka | infantry, rocket | 30 | 180 | 240 | 19 |
| 48 | GATLING SOLDIER | ZakoGatling | infantry, rapid fire | 40 | 260 | 300 | 25 |
| 8 | SHIELDED SOLDIER | ZakoShield | infantry with shield | 30 | 500 | 35 | 22 |
| 162 | ROCKET BOMB SOLDIER | MissileZako | infantry, missile | 35 | 240 | 380 | 20 |
| 182 | W.SOLDIER | ZakoSnow | infantry, close range | 70 | 1200 | 0 | 21 |
| 160 | (paratrooper, lands) | ParaTrooper | drops from the sky | 40 | 180 | 240 | 34 |
| 61 | MUMMY | Mummy | slow melee monster | 35 | 800 | 70 | 27 |
| 221 | NATIVE(BIRD) | NativeBird | thrower, melee + lob | 60 | 1000 | 360 | 31 |
| 313 | ZOMBIE (YOUNG MAN) | ZombieBrain | monster, projectile | 80 | 1000 | 330 | 23 |
| 192 | INVADER | Alien | alien | 180 | 2000 | 330 | 25 |
| 3 | DI-COKKA | DiCokka | tank | 100 | 1400 | 320 | 16 |
| 28 | M-15A BRADLEY | M15A | missile vehicle | 90 | 1800 | 180 | 40 |
| 51 | GIRIDA-O | GiridaO | tank | 70 | 1400 | 280 | 37 |
| 6 | NOP-03 SARUBIA | Sarubia | heavy vehicle | 200 | 3500 | 210 | 18 |
| 117 | MV-280B | HeavyB | vehicle | 90 | 1000 | 380 | 33 |
| 377 | MV-280C VER.F | FutureJeep | jeep | 270 | 3000 | 450 | 19 |
| 133 | SPECIAL FORCE (RIDER) | Bike_P | motorbike | 90 | 900 | 450 | 23 |
| 228 | REBEL WALKER | LevelWalker | walker mech | 200 | 2000 | 350 | 76 |
| 187 | REGIMENTAL MH-6s | McsnlFive | helicopter (air) | 200 | 1000 | 220 | 43 |
| 200 | WINGED INVADER | WingedInvader | flying alien (air) | 200 | 1800 | 380 | 32 |
| 394 | IRON SLIDER | (boss) | boss | 999 | 10000 | 350 | 18 |
| 5 / 77 / 95 | SANDBAG / MUMMY GENERATOR / MAGGOT | Kouhei | engineer that builds a structure | 40–100 | 1 | – | 15 |
| 163 | MORTAR | Mortar_Kouhei | builds a mortar | 45 | 1 | – | 28 |
| 64 | (summoning box) | MummyGate | structure that summons | 0 | 1500 | – | 32 |

**Melee or normal attack?** Read the base unit's ranges (`base` prints them; `base_<id>.json` → `stats`): word 6 is the melee range, word 7 the normal range. A unit whose melee range is 0 attacks with its *normal* attack even when that attack is a knife (Rebel Infantry). Its damage then follows `normal_damage_multiplier` / word 22, not the melee fields. Use the same words with the player as the base unit's data, not the look of the attack.

Engineers, structures, summoners, paratroopers and formations need behaviours ([05_stats_and_behaviors.md](05_stats_and_behaviors.md)); start with a simpler class for a first unit. There are 399 original units; `base` works on any of them, and the player can open an original unit's ACTION page in the game to see how it fights.

## Spec script items and the opcodes behind them

In the build spec, `"scripts"` maps a slot number to a list of items. Each item becomes one or more opcodes. You can always use the raw form `{"op": N, "values": [...]}`.

| Spec item | Opcode | Meaning |
| --- | --- | --- |
| `{"frame": "walk/01", "ticks": 2}` | op0 + op1 | show a frame, then wait n ticks |
| `{"frames": ["walk/01", "walk/02"], "ticks": 2}` | op0 + op1 … | a sequence; `"ticks"` may be one number or one per frame |
| `{"hide": n}` | op0 −1 + op1 | draw nothing for n ticks |
| `{"wait": n}` | op1 | keep the current frame n ticks |
| `{"hit_box": i}` | op3 | hit box i (0 = none) |
| `{"attack_box": i}` | op4 | attack box i (−1 or 0 = off); each switch-on starts a new strike |
| `{"sound": "mod.key"}` or `{"sound": 202}` | op23 | play a sound key of this mod, or an original SoundID |
| `{"move": [vx, vy, ax, ay]}` | op7 | velocity and acceleration in 0.01 sprite px per tick (x forward/back follows the art's direction, y negative = up); starts this tick |
| `{"move_x": vx}` / `{"move_y": vy}` | op8 / op9 | only one axis (op8 also clears x acceleration) |
| `{"stop": true}` | op16 | stop moving |
| `{"ground": true}` | op15 | snap to the ground height here |
| `{"nudge": [x, y]}` | op6 | one-off push of the position (0.01 px units) |
| `{"offset": [x, y]}` | op14 | draw/position offset (sprite px), set, not added |
| `{"bullet": slot, "group": g, "at": [x, y]}` | op22 | fire a projectile running script `slot`, from (x, y); g = 0 uses the current attack's stats, 30/40/50 = melee/normal/special stats. Some classes ignore `slot` and use a fixed projectile slot |
| `{"effect": slot, "priority": p, "at": [x, y]}` | op12 | spawn an independent effect running script `slot` (or `"shared:3"` for shared effect 3); the effect script **must end with "end"** or it never disappears |
| `{"layer": slot, "priority": p, "at": [x, y]}` | op11 | run script `slot` as a child layer on top of the unit (flash, smoke) at offset (x, y) |
| `{"rotate": t}` | op2 | layer rotation, t × 360/4096 degrees |
| `{"alpha": a}` | op18 | opacity 0–100 |
| `{"scale": [sx, sy]}` | op19 | scale in percent ([100, 100] = normal) |
| `{"priority": p}` | op17 | layer drawing order |
| `{"accelerate": [x, y]}` | op20 | add acceleration |
| `"loop"` / `"end"` | op5 / op21 | end of script |

Shared effects (`"shared:N"`, from the original game, no atlas needed): 2 small explosion, 3 medium explosion, 4 vehicle wreck explosion, 0x11 base destroyed fire column, 0x17 big unit explosion.

Notes:

- After `"loop"`, the root layer no longer runs `move`, `move_x`, `move_y`, `priority` or `scale` on later rounds; put movement before the loop or in an `"end"` script.
- `{"hit_box": 0}` is "no hit box". Do not use −1 for hit boxes.
- Projectiles and effects are updated twice before they are first drawn; start their first frame a little behind the muzzle.
- Inside a child layer (`layer`), boxes ignore the layer's own offset.

## Script patterns

```json
"6":  [{"hit_box": 1}, {"frames": ["idle/01","idle/02","idle/03","idle/02"], "ticks": 4}, "loop"],
"7":  [{"hit_box": 1}, {"frames": ["walk/01","walk/02","walk/03","walk/04","walk/05","walk/06"], "ticks": 2}, "loop"],
"8":  [{"hit_box": 1}, {"frames": ["melee/01","melee/02","melee/03"], "ticks": 2},
       {"attack_box": 2}, {"sound": "pablo.slash"}, {"frames": ["melee/04","melee/05"], "ticks": 2},
       {"attack_box": -1}, {"frames": ["melee/06","melee/07"], "ticks": 3}, "end"],
"9":  [{"hit_box": 1}, {"frames": ["shoot/01","shoot/02"], "ticks": 2},
       {"bullet": 26, "group": 0, "at": [-24, -22]}, {"sound": "pablo.shot"},
       {"frames": ["shoot/03","shoot/04"], "ticks": 3}, "end"],
"11": [{"move": [300, 0, -10, 0]}, {"frames": ["hit/01","hit/02","hit/03"], "ticks": 3}, {"stop": true}, "end"],
"12": [{"sound": "pablo.death"}, {"frames": ["death/01","death/02","death/03","death/04"], "ticks": 3}, {"wait": 30}, "end"],
"26": [{"attack_box": 1}, {"frames": ["projectile/01","projectile/02"], "ticks": 1}, "loop"]
```

- **Idle**: four to eight frames, played forwards and back (1-2-3-2) when the art has no idle cycle of its own.
- **Walk**: the leg motion must match the move speed. If the player raises the speed, shorten the ticks per frame in the same ratio.
- **Knock-back**: copy the base unit's knock-back script structure (movement values and duration, hit box or none; `base` shows them). The sign of `move` depends on the art's direction: an original left-facing tank uses `move [500, …]`, a right-facing soldier `move [-400, …]`. If the base unit has no recognisable knock-back slot, see "When a slot's role is unclear" above.
- **Death**: end on the last frame, or with `{"hide": 1}` before `"end"` if the body should disappear. Keep the length close to the base unit's death script (repeat or hold frames to fill it).
- **Attack timing**: put the attack box or the `bullet` at the same tick as in the base script (shown by `base`), so the class's timing still fits. When the player's strike frame comes earlier or later in their animation, adjust the frames around it: hold wind-up frames longer, drop or merge frames, or start the sequence a few frames later, so the strike lands on the base tick. Record such changes in the plan for the player to confirm.
