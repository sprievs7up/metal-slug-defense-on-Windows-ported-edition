"""VS CPU（与 CPU 对战，docs/lab/vs_cpu_plan_2026-10-11.md）。

VERSUS 页第一张卡进入；准备界面与本地双人对战相同的设定（双方单位与等级、据点等级、优势、地图），另选玩家所在一边
（P1 左 / P2 右）与 CPU 段位（LAB 的 AI 段位）。设定、预设与履历保存在独立的 lab_cpu_config.json 与 lab_presets_cpu/。
准备界面的“我方 / 敌方”设定即 P1 / P2。

战斗（本模块与 lab.Lab 中的 cpu 分支）：
- 原生单方底栏：LAB 头部只设自动出兵与绝招分开、支援、AI 段位、音效扩展四项功能位，不设敌方等待条（CPU 的绝招等待条不显示）、
  点击敌方单位、底栏分栏、双方胜利均为 COMPLETE（胜负演出按玩家视角）与双人光标；与常规联机（N6a）的界面相同，不经联机捕获。
- 玩家在 P2：开场前把底栏绑定到 P2 控制器、原生界面事件的本方队伍（BattleScene +0x2c / +0x64）改为 P2、镜头移到 P2 据点，
  处理与 netplay_regular.RegularBattle.bind_view 相同；离开战斗时先还原，再由 LAB 释放 P2 出兵格图集。
- 控制器固定按 P1 / P2 取得（开战时记下），不随底栏绑定改变，准备界面的设定因此对应到正确的一边。
- 绝招光圈：玩家单位 P1 为原生蓝色、P2 为 LAB 红色渲染器；CPU 单位不显示（原生只为对象管理器的本地队伍 P1 设渲染器，
  玩家在 P2 时逐帧把 CPU 单位的光圈类型清零）。点击绝招就绪的本方单位由原生处理。
- CPU 一方以所选段位自动出兵与施放绝招；玩家一方的 AI、自动绝招与完全控制关闭；支援选项保留接口，暂不在界面中显示。
- 暂停菜单、MISSION COMPLETE / FAILED 演出、闸门与回到准备界面沿用 LAB。
"""
import struct

from netplay_regular import OPERATOR_GFX, SCENE_MEMBER, SCENE_TEAM

CONFIG_NAME = 'lab_cpu_config.json'
PRESET_DIR = 'lab_presets_cpu'
SIDES = ('p1', 'p2')
# VS CPU 战斗期间由模式决定的 LAB 开关（开战时保存、离开战斗时还原，不写入设定文件）。
OVERRIDES = ('full_control', 'player_ai', 'enemy_ai', 'player_auto_special', 'enemy_auto_special',
             'player_support', 'enemy_support')
SET_EFFECT = '_ZN10BattleUnit17setEffectRendererEP20BattleEffectRendererNS_18SpAttackEffectTypeE'


def side_index(config):
    return 1 if config.get('cpu_side') == 'p2' else 0


class CpuBattle:
    def __init__(self, lab, side, p1, p2):
        self.lab, self.p = lab, lab.p
        self.side = side                       # 玩家所在一边：0 为 P1，1 为 P2
        self.controllers = (p1, p2)
        self.bound = None                      # (operator, 原控制器, 原队伍, 原成员, scene)
        self.camera_moved = False

    def human(self):
        return self.controllers[self.side]

    # ---------- P2 视角 ----------
    def bind(self):
        """玩家在 P2 时，开场前把底栏与原生界面事件的本方队伍改为 P2（只做一次）。"""
        if self.side != 1 or self.bound is not None:
            return
        import lab as labmod
        p, lab = self.p, self.lab
        _, scene = lab.battle()
        operator = p.word(scene + 0x3c) if scene else 0
        if not lab.valid(operator) or not p.word(labmod.LAB_HEADER + labmod.LAB_ENEMY_GFX_READY):
            return
        p2 = self.controllers[1]
        self.swap_gfx(operator)
        self.bound = (operator, p.word(operator + 24), p.word(scene + SCENE_TEAM), p.word(scene + SCENE_MEMBER), scene)
        p.put(operator + 24, p2)
        pitch = struct.unpack('<f', p.read(operator + 108, 4))[0]
        visible = 6 if p.read(operator + 12, 1)[0] else 5
        p.put(operator + 104, int((p.word(p2 + 912) - visible) * pitch) & 0xffffffff)   # 最大滚动（BattlePlayerOperator::initialize）
        p.put(operator + 100, 0)
        p.write(operator + 112, struct.pack('<f', 0.0))
        p.put(scene + SCENE_TEAM, p.word(p2 + 0x38c))
        p.put(scene + SCENE_MEMBER, p.word(p2 + 0x39c))
        lab.record('cpu_bind_p2', operator=hex(operator))

    def move_camera(self):
        """玩家在 P2：镜头移到 P2 据点（原生按场地宽度限定），开战后执行一次。"""
        if self.side != 1 or self.camera_moved or self.bound is None:
            return
        screen = self.p.word(self.bound[0] + 28)
        if screen:
            self.p.call('_ZN12BattleScreen12movePositionEi', screen, 100000)
        self.camera_moved = True

    def swap_gfx(self, operator):
        import lab as labmod
        p = self.p
        base = labmod.LAB_HEADER + labmod.LAB_ENEMY_GFX
        for i in range(OPERATOR_GFX[1]):
            a, b = operator + OPERATOR_GFX[0] + 4 * i, base + 4 * i
            va, vb = p.word(a), p.word(b)
            p.put(a, vb)
            p.put(b, va)

    def unbind(self):
        if not self.bound:
            return
        p = self.p
        operator, controller, team, member, scene = self.bound
        self.bound = None
        p.put(operator + 24, controller)
        self.swap_gfx(operator)
        p.put(scene + SCENE_TEAM, team)
        p.put(scene + SCENE_MEMBER, member)

    # ---------- 每帧 ----------
    def fix_units(self):
        """GameMode 1 的据点与单位 +981（对端同步扣血标记）清零，伤害在本地结算（与 Lab.fix_units 相同）；绝招光圈按玩家一边设定。"""
        lab, p = self.lab, self.p
        human_team = p.word(self.human() + 0x38c)
        red = lab.ensure_red_renderer() if self.side == 1 else 0
        for team in (0, 1):
            manager, units = lab.team_list(team)
            renderer = p.word(manager + 64)
            if red and renderer:
                p.put(red + 8, p.word(renderer + 8))          # 红色渲染器同步原生光圈的动画帧
            for unit in units:
                if p.read(unit + 981, 1)[0]:
                    p.write(unit + 981, b'\x00')
                kind = p.word(unit + 976)
                if team == human_team:
                    if red and (p.word(unit + 972) != red or kind != 1):
                        p.call(SET_EFFECT, unit, red, 1)
                elif kind != 0:
                    p.call(SET_EFFECT, unit, p.word(unit + 972), 0)   # CPU 单位：不显示光圈
        for controller in self.controllers:
            base = p.call('_ZNK16BattleController11getBaseUnitEv', controller)
            if lab.valid(base) and p.read(base + 981, 1)[0]:
                p.write(base + 981, b'\x00')
