# 单位行为目录 / Unit behavior catalog（行为库版本 2）

本文件由 `content_tool.py list-behaviors --markdown` 从 `behavior_library.json` 生成，请勿手工修改。
Generated from `behavior_library.json` by `content_tool.py list-behaviors --markdown`; do not edit by hand.

单位文件写法 / Usage in a unit file:

```json
"behaviors": [{"name": "spawn_child_unit", "version": 1, "params": {"unit": "author_mod.child"}}]
```

## build_structure（v1）

- 适用的原版基准单位 / base_id: 77

工兵类单位：出击后修筑指定的内部单位（如召唤箱）。修筑时间按倍率调整（状态词 38，向上取整）；兵种浏览、出兵格与属性面板显示修筑完成后的单位。

Builder units construct the given internal unit after deployment. The construction time (status word 38, rounded up) is scaled by the multiplier. The unit viewer, deck card and status panel show the finished structure.

| 参数 / parameter | 类型 / type | 约束 / constraints |
| --- | --- | --- |
| `structure` | unit_key | required: true; internal: true |
| `construction_time_multiplier` | rational | default: [1, 1]; min: [1, 100]; max: [100, 1] |

## summon_units（v1）

- 适用的原版基准单位 / base_id: 64

召唤箱类单位：按计量周期召唤指定的可选单位。首次计量（状态词 38）与后续间隔（状态词 39，含计量零值的一帧）先按 interval_multiplier、再按 interval_additional_multiplier 调整。

Summoning structures periodically summon the given selectable unit. The first gauge (status word 38) and later intervals (status word 39, including the zero-gauge frame) are scaled by interval_multiplier, then by interval_additional_multiplier.

| 参数 / parameter | 类型 / type | 约束 / constraints |
| --- | --- | --- |
| `unit` | unit_key | required: true; internal: false |
| `interval_multiplier` | rational | default: [1, 1]; min: [1, 100]; max: [100, 1] |
| `interval_additional_multiplier` | rational | default: [1, 1]; min: [1, 100]; max: [100, 1] |

## spawn_child_unit（v1）

- 适用的原版基准单位 / base_id: 159, 163

投放与架设类单位：出击时由原生流程生成指定的内部单位（伞兵运输、迫击炮架设）。属性面板显示内部单位的数值。

Deployer units (paratrooper drop, mortar emplacement) spawn the given internal unit through the native flow. The status panel shows the internal unit's values.

| 参数 / parameter | 类型 / type | 约束 / constraints |
| --- | --- | --- |
| `unit` | unit_key | required: true; internal: true |

## para_drop_transform（v1）

- 适用的原版基准单位 / base_id: 160

空降中的内部单位：落地后转换为指定的可选单位（替代原生固定的 UnitID 45）。

Falling paratrooper (internal unit) turns into the given selectable unit on landing, replacing the native fixed UnitID 45.

| 参数 / parameter | 类型 / type | 约束 / constraints |
| --- | --- | --- |
| `landing_unit` | unit_key | required: true; internal: false |

## insect_swarm_release（v1）

- 适用的原版基准单位 / base_id: 61

地面木乃伊类单位改用垂吊木乃伊（UnitID 157）的发射动作：攻击时释放虫群。虫群脚本、伤害与距离由单位的精灵描述符与攻击参数决定。

Ground mummy units use the hanging mummy's (UnitID 157) shot action and release an insect swarm. Swarm scripts, damage and range come from the unit's sprite descriptor and attack parameters.

无参数 / no parameters.

## recovery_slot（v1）

- 适用的原版基准单位 / base_id: 61
- 需要字段 / requires fields: sprite_descriptor

受击后的恢复动作改用精灵描述符中的指定动画槽（原生固定为槽 26）；用于自定义描述符把槽 26 另作他用的情形。

The recovery animation after being knocked back uses the given sprite-descriptor slot instead of the native slot 26, for descriptors that use slot 26 for something else.

| 参数 / parameter | 类型 / type | 约束 / constraints |
| --- | --- | --- |
| `animation` | int | required: true; min: 0; max: 255 |

## flame_burst_interruptible（v1）

- 适用的原版基准单位 / base_id: 3
- 需要字段 / requires fields: sprite_descriptor

坦克类单位的绝招喷火：喷火阶段受击时，按已喷出的时长改用收尾受击动画（alternate_knockback_animation 起 5 个槽），并由收尾弹体动画完成最后一次判定（ending_bullet_animations 依次对应起始段三组与标准收尾）。

Tank-class special flame attack. When knocked back during the flame, the unit switches to an ending knockback animation chosen by elapsed flame time (5 slots starting at alternate_knockback_animation), and an ending bullet animation performs the final hit (ending_bullet_animations: three early-phase groups and the standard ending).

| 参数 / parameter | 类型 / type | 约束 / constraints |
| --- | --- | --- |
| `flame_start_tick` | int | required: true; min: 0; max: 255 |
| `flame_ticks` | int | required: true; min: 6; max: 200 |
| `alternate_knockback_animation` | int | required: true; min: 0; max: 255 |
| `ending_bullet_animations` | int_list | required: true; length: 4; min: 0; max: 255 |

## single_knockback_per_special（v1）

- 适用的原版基准单位 / base_id: 3
- 需要行为 / requires behaviors: flame_burst_interruptible

同一次绝招的喷火对同一目标最多击退一次。

One special attack's flame knocks back the same target at most once.

无参数 / no parameters.

## ground_special_attack（v1）

- 适用的原版基准单位 / base_id: 3

坦克类单位的绝招状态（50）每帧沿用原生冲刺单位的地形移动流程，坡地上冲刺不悬空。

During the special attack state (50), tank-class units use the native dash units' terrain movement every frame, so dashes follow slopes.

无参数 / no parameters.

## retained_special_weapon（v1）

- 适用的原版基准单位 / base_id: 16, 17, 18, 19, 96, 97, 98, 99, 344, 362

马可、塔玛、英里、菲欧及其胖形态、圣诞英里、圣诞菲欧类单位：首次绝招后保留强化武器，之后的远程普通攻击使用原生绝招参数组（伤害、命中与射程），并保持持枪动作；胖英里保留大激光。与原版十类角色的行为相同。

Marco, Tarma, Eri, Fio, their fat forms, Christmas Eri and Christmas Fio class units keep the special weapon after the first special attack: later ranged normal attacks use the native special-attack parameter group (damage, hit and range) and keep the armed pose; Fat Eri keeps the large laser. Same behaviour as the ten stock characters.

无参数 / no parameters.

