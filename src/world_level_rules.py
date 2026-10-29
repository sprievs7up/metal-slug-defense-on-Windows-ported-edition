"""启用原版世界开放、阶段勋章解锁与社区核心权限规则。"""


class WorldLevelRules:
    def __init__(self, p):
        self.p = p
        if (not hasattr(p.uc.lib, 'msd_native_level_rules_version')
                or p.uc.lib.msd_native_level_rules_version() != 1):
            raise RuntimeError('原版等级解锁流程需要匹配的游戏核心')
        p.uc.lib.msd_enable_world_level_rules()
        # 最终区域通关后的后继入口属于原生结算结果；兼容历史缺失状态。
        restored = []
        for world in (0, 1):
            if (p.call('_Z19IsAreaClearSaveDataii9WorldType', world, 11, 0)
                    and not p.call('_Z12IsAreaEnableii9WorldType', world + 1, 0, 0)):
                p.call('_Z21SetAreaEnableSaveDataiib9WorldType', world + 1, 0, 0, 0)
                restored.append(world + 1)
        p.log('NATIVE_PLAYER_LEVEL_RULES', 1)
        if restored:
            p.log('NATIVE_WORLD_ENTRY_RECOVERY', restored)
        self.boss_areas_checked = False

    def update(self):
        """头目区域经 RAID（雷達）救满时原生缺少战斗结算的永久开放（核心 msd_raid_boss_area_rules_version 起补上）；
        此前留下的存档按 BattleEndGetPrisoner 的条件补齐：有头目、俘虏星期为 −1、救出率 100% 而关卡开放位不全。
        救出率与开放位在原生载入存档后才可读（初始化时读为 0），于首次进入主菜单（场景 28）时检查一次。"""
        if self.boss_areas_checked:
            return
        p = self.p
        app = p.app_instance()
        if not app or p.word(app + 0x22bc) != 28:
            return
        self.boss_areas_checked = True
        boss_areas = []
        for world in (0, 1, 2):
            for area in range(p.call('_Z10GetAreaNumi9WorldType', world, 0)):
                if p.call('_Z11GetAreaBossii9WorldType', world, area, 0) == 0xffffffff:
                    continue
                prisoner = p.call('_Z15GetAreaPrisonerii9WorldType', world, area, 0)
                if (p.call('_Z18GetPrisonerWeekday10PrisonerID', prisoner) != 0xffffffff
                        or p.call('_Z19GetAreaPrisonerRateii9WorldType', world, area, 0) != 100):
                    continue
                stages = range(p.call('_Z11GetStageNumii9WorldType', world, area, 0))
                if not all(p.call('_ZN7AppMain21IsStageEnableSaveDataEiii9WorldType', app, world, area, s, 0) for s in stages):
                    p.call('_Z21SetAreaEnableSaveDataiib9WorldType', world, area, 0, 0)
                    boss_areas.append((world, area))
        if boss_areas:
            p.log('NATIVE_BOSS_AREA_RECOVERY', boss_areas)
