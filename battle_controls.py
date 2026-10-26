"""Keyboard battle actions using original controller and unit readiness checks."""
import json
import time

KEYS={'special_all':'SPACE','upgrade_ap':'`','slug_attack':'-','deploy_all':'='}

def player_controller(p,main):
    # The visible unit/AP panels dispatch through this operator's controller.
    # Resolve it for every action: Event/NPC setup and temporary deck changes
    # can rebuild the operator or change the scene's team-selection index.
    scene=p.call('_ZN10BattleMain12getMainSceneEv',main)
    if scene:
        operator=p.word(scene+0x3c)
        if 0x10000000<=operator<0x1ffff000 and p.word(operator)==p.symbols['_ZTV20BattlePlayerOperator']+8:
            controller=p.word(operator+0x18)
            if 0x10000000<=controller<0x1ffff000:return controller
    return p.call('_ZN10BattleMain19getPlayerControllerEv',main)


def context(p):
    app=p.app_instance()
    scene=p.word(app+0x22bc) if app else None
    if scene!=100:return None,'not_battle',scene
    main=p.word(app+0xc220)
    if not main or not p.word(main+8) or not p.call('_ZN10BattleMain15isBattlePlayingEv',main):
        return None,'not_playing',scene
    master=p.call('_ZN16BattleGameMaster11getInstanceEv')
    if p.read(master+0x1c,1)[0]:return None,'paused',scene
    controller=player_controller(p,main)
    if not controller or p.word(p.word(controller)+0x94)!=p.symbols['_ZN26BattleControllerPlayerBase10createUnitEi']:
        return None,'controller',scene
    return controller,None,scene


def drop_stale_unit_press(p):
    # onUITouchBegan checks isUnitCreate (AP and cooldown) and records the
    # pressed slot at operator+0x20; onUITouchEnded then creates that unit
    # after checking only the unit limit. A keyboard deploy while the slot is
    # held spends the AP and starts the cooldown, so the release would create
    # a second unit. Called before a release reaches the native TouchEvent.
    app=p.app_instance()
    main=p.word(app+0xc220) if app and p.word(app+0x22bc)==100 else 0
    if not main or not p.word(main+8):return
    scene=p.call('_ZN10BattleMain12getMainSceneEv',main)
    operator=p.word(scene+0x3c) if scene else 0
    if not 0x10000000<=operator<0x1ffff000 or p.word(operator)!=p.symbols['_ZTV20BattlePlayerOperator']+8:return
    slot=p.word(operator+0x20)
    controller=p.word(operator+0x18)
    if slot<10 and 0x10000000<=controller<0x1ffff000 and not p.call('_ZN26BattleControllerPlayerBase12isUnitCreateEi',controller,slot):
        p.put(operator+0x20,0xffffffff)


def team_units(p,controller):
    manager=p.call('_ZN19BattleObjectManager11getInstanceEv')
    team=p.word(controller+0x38c)
    member=p.word(controller+0x39c)
    first=p.call('_ZN19BattleObjectManager15getTeamUnitListE12BattleTeamID18BattleTeamMemberID',manager,team,0)
    units=[];unit=first;seen=set()
    while unit and unit not in seen:
        if not 0x10000000<=unit<0x1ffff000 or len(seen)>=4096:
            raise RuntimeError('Invalid native battle unit list')
        seen.add(unit)
        if p.word(unit+0x74)==member:units.append(unit)
        link=p.word(unit+0x120)
        unit=link-0x11c if link else 0
    return units


def perform(p,action):
    if action not in KEYS:raise ValueError(action)
    controller,blocked,scene=context(p)
    result={'action':action,'key':KEYS[action],'scene':scene,'reason':blocked,'success':False}
    messages={'not_battle':'当前界面无法操作','not_playing':'战斗尚未开始或已经结束',
              'paused':'战斗已暂停','controller':'当前战斗控制器不支持此操作'}
    text=messages.get(blocked,'')
    if controller is not None:
        if action=='special_all':
            ready=[u for u in team_units(p,controller)
                   if not p.read(u+0x3d4,1)[0] and p.call('_ZNK10BattleUnit10isSpAttackEv',u)]
            result['unit_ids']=[]
            for unit in ready:
                unit_id=int.from_bytes(p.read(unit+0x62,2),'little')
                p.call(p.word(p.word(controller)+0x98),controller,unit_id)
                result['unit_ids'].append(unit_id)
            result.update(reason='triggered' if ready else 'no_ready_units',success=bool(ready),count=len(ready))
            text=f'已触发 {len(ready)} 个单位的绝招' if ready else '没有绝招就绪单位'
        elif action=='upgrade_ap':
            level=p.call('_ZN26BattleControllerPlayerBase14getKyotenLevelEv',controller)
            cost=p.word(controller+0x400)
            ap=p.call('_ZN26BattleControllerPlayerBase5getAPEv',controller)
            result.update(level_before=level,cost=cost,ap=ap)
            if p.call('_ZN26BattleControllerPlayerBase15isKyotenLevelupEv',controller):
                p.call(p.word(p.word(controller)+0xa8),controller)
                result.update(reason='upgraded',success=True,
                              level_after=p.call('_ZN26BattleControllerPlayerBase14getKyotenLevelEv',controller),
                              ap_after=p.call('_ZN26BattleControllerPlayerBase5getAPEv',controller))
                text='AP 生产已升级'
            else:
                result['reason']='max_level' if p.call('_ZN26BattleControllerPlayerBase16isKyotenLevelMaxEv',controller) else 'insufficient_ap'
                text='AP 生产已达到最高等级' if result['reason']=='max_level' else f'AP 不足：{ap} / {cost}'
        elif action=='slug_attack':
            if p.call('_ZN26BattleControllerPlayerBase16isUseMetasuraHouEv',controller):
                p.call('_ZN17FrameworkInstance6playSEENS_9SoundTypeE7SoundIDi',0,12,0)
                p.call(p.word(p.word(controller)+0xa0),controller)
                result.update(reason='launched',success=True)
                text='弹头车已出击'
            else:
                result['reason']='not_charged'
                text='弹头车尚未就绪'
        elif action=='deploy_all':
            result['attempts']=[]
            result['ap_before']=p.call('_ZN26BattleControllerPlayerBase5getAPEv',controller)
            for slot in range(10):
                p.activate_unit_slot(slot)
                result['attempts'].append(dict(p.last_unit_result))
            count=sum(r['reason']=='created' for r in result['attempts'])
            result.update(reason='completed',success=bool(count),count=count,
                          ap_after=p.call('_ZN26BattleControllerPlayerBase5getAPEv',controller))
            text=f'已出击 {count} 种单位 · AP {result["ap_after"]}'
    p.last_unit_result=result
    p.unit_feedback={'text':f'{result["key"]} · {text}','until':time.perf_counter()+2.5,
                     'success':result['success'],'visible':scene==100}
    p.log('KEY_BATTLE_RESULT',json.dumps(result,ensure_ascii=False))
    return result
