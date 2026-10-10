static const char BEHAVIOR_MANIFEST[]=R"MSD({
  "schema": 1,
  "library_version": 2,
  "param_types": {
    "unit_key": "单位稳定键；internal 为 true 时须为内部单位（internal_only），为 false 时须为可选单位",
    "rational": "[分子, 分母] 正整数倍率",
    "int": "整数，min/max 含端点",
    "int_list": "整数列表，length 为固定长度，min/max 作用于每个元素"
  },
  "behaviors": [
    {
      "name": "build_structure",
      "version": 1,
      "base_classes": [
        77
      ],
      "params": {
        "structure": {
          "type": "unit_key",
          "required": true,
          "internal": true
        },
        "construction_time_multiplier": {
          "type": "rational",
          "default": [
            1,
            1
          ],
          "min": [
            1,
            100
          ],
          "max": [
            100,
            1
          ]
        }
      },
      "doc": {
        "ZS": "工兵类单位：出击后修筑指定的内部单位（如召唤箱）。修筑时间按倍率调整（状态词 38，向上取整）；兵种浏览、出兵格与属性面板显示修筑完成后的单位。",
        "EN": "Builder units construct the given internal unit after deployment. The construction time (status word 38, rounded up) is scaled by the multiplier. The unit viewer, deck card and status panel show the finished structure."
      }
    },
    {
      "name": "summon_units",
      "version": 1,
      "base_classes": [
        64
      ],
      "params": {
        "unit": {
          "type": "unit_key",
          "required": true,
          "internal": false
        },
        "interval_multiplier": {
          "type": "rational",
          "default": [
            1,
            1
          ],
          "min": [
            1,
            100
          ],
          "max": [
            100,
            1
          ]
        },
        "interval_additional_multiplier": {
          "type": "rational",
          "default": [
            1,
            1
          ],
          "min": [
            1,
            100
          ],
          "max": [
            100,
            1
          ]
        }
      },
      "doc": {
        "ZS": "召唤箱类单位：按计量周期召唤指定的可选单位。首次计量（状态词 38）与后续间隔（状态词 39，含计量零值的一帧）先按 interval_multiplier、再按 interval_additional_multiplier 调整。",
        "EN": "Summoning structures periodically summon the given selectable unit. The first gauge (status word 38) and later intervals (status word 39, including the zero-gauge frame) are scaled by interval_multiplier, then by interval_additional_multiplier."
      }
    },
    {
      "name": "spawn_child_unit",
      "version": 1,
      "base_classes": [
        159,
        163
      ],
      "params": {
        "unit": {
          "type": "unit_key",
          "required": true,
          "internal": true
        }
      },
      "doc": {
        "ZS": "投放与架设类单位：出击时由原生流程生成指定的内部单位（伞兵运输、迫击炮架设）。属性面板显示内部单位的数值。",
        "EN": "Deployer units (paratrooper drop, mortar emplacement) spawn the given internal unit through the native flow. The status panel shows the internal unit's values."
      }
    },
    {
      "name": "para_drop_transform",
      "version": 1,
      "base_classes": [
        160
      ],
      "params": {
        "landing_unit": {
          "type": "unit_key",
          "required": true,
          "internal": false
        }
      },
      "doc": {
        "ZS": "空降中的内部单位：落地后转换为指定的可选单位（替代原生固定的 UnitID 45）。",
        "EN": "Falling paratrooper (internal unit) turns into the given selectable unit on landing, replacing the native fixed UnitID 45."
      }
    },
    {
      "name": "insect_swarm_release",
      "version": 1,
      "base_classes": [
        61
      ],
      "params": {},
      "doc": {
        "ZS": "地面木乃伊类单位改用垂吊木乃伊（UnitID 157）的发射动作：攻击时释放虫群。虫群脚本、伤害与距离由单位的精灵描述符与攻击参数决定。",
        "EN": "Ground mummy units use the hanging mummy's (UnitID 157) shot action and release an insect swarm. Swarm scripts, damage and range come from the unit's sprite descriptor and attack parameters."
      }
    },
    {
      "name": "recovery_slot",
      "version": 1,
      "base_classes": [
        61
      ],
      "requires_fields": [
        "sprite_descriptor"
      ],
      "params": {
        "animation": {
          "type": "int",
          "required": true,
          "min": 0,
          "max": 255
        }
      },
      "doc": {
        "ZS": "受击后的恢复动作改用精灵描述符中的指定动画槽（原生固定为槽 26）；用于自定义描述符把槽 26 另作他用的情形。",
        "EN": "The recovery animation after being knocked back uses the given sprite-descriptor slot instead of the native slot 26, for descriptors that use slot 26 for something else."
      }
    },
    {
      "name": "flame_burst_interruptible",
      "version": 1,
      "base_classes": [
        3
      ],
      "requires_fields": [
        "sprite_descriptor"
      ],
      "params": {
        "flame_start_tick": {
          "type": "int",
          "required": true,
          "min": 0,
          "max": 255
        },
        "flame_ticks": {
          "type": "int",
          "required": true,
          "min": 6,
          "max": 200
        },
        "alternate_knockback_animation": {
          "type": "int",
          "required": true,
          "min": 0,
          "max": 255
        },
        "ending_bullet_animations": {
          "type": "int_list",
          "required": true,
          "length": 4,
          "min": 0,
          "max": 255
        }
      },
      "doc": {
        "ZS": "坦克类单位的绝招喷火：喷火阶段受击时，按已喷出的时长改用收尾受击动画（alternate_knockback_animation 起 5 个槽），并由收尾弹体动画完成最后一次判定（ending_bullet_animations 依次对应起始段三组与标准收尾）。",
        "EN": "Tank-class special flame attack. When knocked back during the flame, the unit switches to an ending knockback animation chosen by elapsed flame time (5 slots starting at alternate_knockback_animation), and an ending bullet animation performs the final hit (ending_bullet_animations: three early-phase groups and the standard ending)."
      }
    },
    {
      "name": "single_knockback_per_special",
      "version": 1,
      "base_classes": [
        3
      ],
      "requires_behaviors": [
        "flame_burst_interruptible"
      ],
      "params": {},
      "doc": {
        "ZS": "同一次绝招的喷火对同一目标最多击退一次。",
        "EN": "One special attack's flame knocks back the same target at most once."
      }
    },
    {
      "name": "ground_special_attack",
      "version": 1,
      "base_classes": [
        3
      ],
      "params": {},
      "doc": {
        "ZS": "坦克类单位的绝招状态（50）每帧沿用原生冲刺单位的地形移动流程，坡地上冲刺不悬空。",
        "EN": "During the special attack state (50), tank-class units use the native dash units' terrain movement every frame, so dashes follow slopes."
      }
    },
    {
      "name": "retained_special_weapon",
      "version": 1,
      "base_classes": [
        16,
        17,
        18,
        19,
        96,
        97,
        98,
        99,
        344,
        362
      ],
      "params": {},
      "doc": {
        "ZS": "马可、塔玛、英里、菲欧及其胖形态、圣诞英里、圣诞菲欧类单位：首次绝招后保留强化武器，之后的远程普通攻击使用原生绝招参数组（伤害、命中与射程），并保持持枪动作；胖英里保留大激光。与原版十类角色的行为相同。",
        "EN": "Marco, Tarma, Eri, Fio, their fat forms, Christmas Eri and Christmas Fio class units keep the special weapon after the first special attack: later ranged normal attacks use the native special-attack parameter group (damage, hit and range) and keep the armed pose; Fat Eri keeps the large laser. Same behaviour as the ten stock characters."
      }
    }
  ]
}
)MSD";
