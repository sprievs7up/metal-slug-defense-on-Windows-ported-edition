# KT-21 坡地绝招移动修复（2026-10-09）

KT-21 的稳定键为 `s1xlv.kt21`，UnitID 1043，以原生 DiCokka（UnitID 3）初始化。单位登记及动画命令位于 `community_content/registry.json`；独立精灵描述符为 `community_content/kt21_descriptor.json`；生成参数维护于 `artwork/kt21_20261006/integrate_kt21.py`。原生扩展入口位于 `src/community_content.cpp`，对应分派登记位于 `src/community_blocks.inc`。

本次缺陷来源于基类绝招更新路径。`BattleAction_DiCokka::update`（0x10192571）在状态 50 播放动画槽 10、等待动画完成并开始攻击等待；冲刺脚本改变水平位置后，该分支缺少地形移动处理。`BattleAction_HeavyB::update`（0x1017a0ad）与 `BattleAction_MobilSlug::update`（0x10188421）的同状态分支每帧调用 `BattleCommonActions::actionMove(object,0)`（0x10178b41）。该原生方法保留脚本水平运动，查询当前战场地形并处理坡地高度、阶差阻挡和下落。

修复新增可选登记字段 `ground_special_attack:true`，当前用于以 DiCokka 初始化的地面绝招。宿主在社区头部偏移 116 登记逐单位 uint32 标记表，位 0 表示启用。原生钩子仅对已登记、真实 BattleUnit 本体且输入状态为 50 的实例转入 HeavyB 绝招更新；其余实例和状态继续原始 DiCokka 更新。该参考分支使用相同动画槽、完成标记与攻击等待接口，未引用 HeavyB 专属单位参数。宿主检查导出 `msd_community_ground_special_version()==1`，避免修订登记加载到缺少支持的旧核心。

现有 AP、生命、击退门槛、受击后退、伤害、射程、生产间隔及绝招冷却保持当前值。槽 10 的两项运动参数继续为 `[-500,0,-125,0]` 与 `[250,0,-125,0]`，维持此前 2.5 倍突进设定。火焰属性、受击收尾弹体与同次绝招击退限制保持既有路径；本次未直接改写单位纵向坐标或地形数据。

候选核心为 `MSD_Core_LAB_r32_KT21Ground_20261009.dll`，由 HEAD `25e5589` 的 r31 基础与本修订构建；显示版本保持 1.47.3。构建命令：

```powershell
windows_runtime/python.exe src/build.py --library MSD_Core_LAB_r32_KT21Ground_20261009.dll --no-activate --no-sha256
```

验证记录位于 `verification/kt21_ground_special_20261009/`。Python 语法、登记结构差异、根模块与 src 镜像核对及 Windows x64 DLL 构建通过。C++ 调度回归直接执行生产钩子与原生生成分支，以观测桩记录动画、攻击等待和公共移动调用；覆盖绝招首帧、持续与结束及回退条件。该检查覆盖分派和调用语义，实际关卡的坡地渲染与战斗表现由用户核验。未启动游戏、计算 SHA-256 或写入个人存档。

固定同步目录为 `F:\egg\research\metal_slug_defense\windows_native\dist\MSD_Windows` 与 `F:\egg\metal-slug-defense-on-Windows-ported-edition-main\metal-slug-defense-on-Windows-ported-edition-main`。同步清单及加载配置记录于本验证目录的 `deployment.json`；普通、原满级和全解锁满级入口在正常退出后重新启动加载修订。已有 r31 核心保留；Git 提交、推送及发布由用户执行。
