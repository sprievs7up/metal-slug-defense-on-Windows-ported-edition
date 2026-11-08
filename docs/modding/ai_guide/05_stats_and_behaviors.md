# 05. Stats and behaviours

## Start from the base unit's numbers

`msd_unit_tool.py base <UnitID>` prints the main stats and writes every stat at the six level anchors (Lv1, 10, 20, 30, 40, 50) to `base_<UnitID>.json` (`stats`). The game interpolates between anchors. Talk about balance with the player in terms of these numbers ("Lv40 HP 3000 → 4000 means hp_multiplier [4, 3]").

## Multipliers

All are fractions `[a, b]` (a, b integers 1–10000, a/b ≤ 100) applied to the base unit's values at every level.

| Field | Changes | Rounding |
| --- | --- | --- |
| `hp_multiplier` (required) | HP | down |
| `knockback_threshold_multiplier` | damage needed to knock it back | nearest; only positive thresholds |
| `damage_multiplier` | melee, normal and special damage | down |
| `near_damage_multiplier`, `normal_damage_multiplier`, `special_damage_multiplier` (required) | one damage group, applied before `damage_multiplier` | down |
| `move_speed_multiplier` | walking speed | – |
| `attack_range_multiplier` | firing range and projectile travel distance | – |
| `ballistic_range_multiplier` | thrown/lobbed projectile distance | – |
| `normal_projectile_distance_multiplier`, `special_projectile_distance_multiplier` | projectile travel distance of one group | down |
| `knockback_distance_multiplier` | how far it slides when knocked back | – |
| `production_interval_multiplier` (required) | redeploy time | up |
| `attack_wait_multiplier` | pause after normal and special attacks | up |
| `special_cooldown_multiplier` | special cooldown (first and later) | up |

Rules of this project (apply them unless the player decides otherwise, and write the decision in the plan):

- When HP changes, set `knockback_threshold_multiplier` to the same fraction. The build tool does this when the field is missing. Some original units have the threshold −1 (word 4 in `base_<id>.json`): they are knocked back by **every** hit, and the multiplier has no effect on them. To make such a unit sturdier, choose another base unit or the `no_knockback` behaviour.
- Knock-back distance, damage, move speed and redeploy time do **not** follow HP. Set each one on purpose and record "unchanged" for the others.
- Do not fake one stat by changing another (for example, more HP instead of a damage reduction).
- AP returned when the unit is destroyed and the Wi-Fi RP are always 10 % of its AP; the game sets them.

## Absolute values: status words

When a multiplier cannot express what the player wants (for example "range exactly 400"), write the stat directly:

```json
"status_word_values": {"7": 400, "26": 400, "22": [280, 420, 560, 700, 840, 980]},
"status_float_values": {"25": 12.0}
```

A single integer applies to all six anchors; a list of six gives Lv1, 10, 20, 30, 40, 50. The battle multipliers (HP, damage, speed, range) are applied **after** these values (a range written as 175 with `attack_range_multiplier` [12, 7] becomes 300). Status words not allowed here: 1–5, 13, 14 (use `ap`, the multipliers and the automatic values).

| Word | Stat | Word | Stat |
| --- | --- | --- | --- |
| 6 | melee range (0 = no melee) | 7 | ranged attack range (≤ 99 = no ranged attack) |
| 8–12 | resistance tiers (use `attribute_resistance_tiers`) | | |
| 15 | melee damage | 22 | normal attack damage |
| 16* | melee knock-back power | 23* | normal knock-back power |
| 17 | melee targets | 24 | normal targets |
| 18* | melee projectile speed | 25* | normal projectile speed |
| 19 | melee projectile distance | 26 | normal projectile distance |
| 20 | pause after melee (ticks) | 27 | pause after normal attack (ticks) |
| 21 | melee attribute | 28 | normal attribute |
| 29 | special damage | 30* | special knock-back power |
| 31 | special targets | 32* | special projectile speed |
| 33 | special projectile distance | 34 | pause after special |
| 35 | special cooldown (ticks, after each use) | 36 | first special cooldown (0 = no special at all) |
| 38 | build time / first summon | 39 | summon interval |

\* Float words: write them in `status_float_values` (0–10000).

Other single fields: `attack_attributes`, `attribute_resistance_tiers`, `minimap_marker`, `special_effect_size`, `draw_priority`, `upgrade_cost_base` ([02_mod_layout.md](02_mod_layout.md)).

To remove a special attack, write `"status_word_values": {"29": 0, "35": 0, "36": 0}` (no cooldown means no special; the base game's PvZ zombies do this). An enemy-only variant that should simply never use its special can instead use `{"35": 30000, "36": 30000}`. Keep the special slot filled (for example with the normal attack) so the unit menu preview still has something to show.

## Behaviours

Abilities that the base class does not have come only from the behaviour library, implemented inside the game. The full list with parameters, defaults, limits and the base units each behaviour accepts is `docs/modding/BEHAVIOR_CATALOG.md` (English and Chinese). Usage:

```json
"behaviors": [
  {"name": "no_knockback", "version": 1, "params": {}},
  {"name": "death_by_attribute", "version": 1,
   "params": {"explosion_animation": 14, "fire_animation": 16}}
]
```

- `version` must equal the version in the catalog heading (`## name（vN）`).
- `base_id` must be one of the behaviour's listed base units, or the mod is rejected ("… supports base units [3], not 42").
- Unknown parameters are rejected. `unit_key` parameters take the key of another unit of this mod (often an `internal_only` helper unit); `animation` parameters take slot numbers of this unit, which must exist in its descriptor and be written in its scripts.
- Add `"behavior_library": ">=<current version>"` to `mod.json`.

Common needs and where to look in the catalog: no knock-back (`no_knockback`), different death per attack attribute (`death_by_attribute`), builders and structures (`build_structure`), summoners (`summon_units`, `summon_internal_unit`, `summon_on_hit`), spawned helpers (`spawn_child_unit`), piercing shots (`piercing_shots`), several HP stages with their own animations (`hp_stage_animations`), extra sounds on hits or kills (`armor_hit_sound`, `kill_sound`).

If the player wants something that neither the base class nor a behaviour provides, say so plainly, offer the closest base unit or behaviour, and do not try to imitate it with stats.
