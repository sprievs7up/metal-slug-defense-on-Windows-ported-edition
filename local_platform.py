"""Local Windows services for the archived game's original JNI contracts."""

from medal_rules import MEDAL_PACKS,SUPPLY_PRICES,SUPPLY_NAMES,LANGUAGE,native_text
CALLBACK_PREFIX='Java_com_snkplaymore_android003_MainActivity_'

def app_instance(p):
    # Equivalent to the original exported singleton getter; no native re-entry.
    getter=p.symbols['_ZN7AppMain11getInstanceEv']&~1
    return p.word(p.word(getter+6+p.word(getter+12)))

def callback(p,name,args,refs=()):
    for ref in refs:
        p.jni_retain(ref,'global')
        p.jni_release(ref)
    return CALLBACK_PREFIX+name,tuple(args),tuple(refs)

def queue_callback(p,name,args,refs=()):
    if not hasattr(p,'platform_callbacks'):p.platform_callbacks=[]
    p.platform_callbacks.append(callback(p,name,args,refs))

def queue_action(p,action):
    # 宿主动作：本帧原生返回之后由 pump 执行（此时可调用原生函数）。
    if not hasattr(p,'platform_callbacks'):p.platform_callbacks=[]
    p.platform_callbacks.append(action)

def buy_supply(p,sku):
    """支援物资（medal_rules.SUPPLY_PRICES）以 MSP 购买：余额足够时扣除，再按原生购买成功结束（setPurchaseOK 置领取许可并写存档）；
    不足时按原生购买失败结束，失败窗口的文字（strMedal 6）在回调期间换为原生 strShop 11（“还差 %d [deco2]”，%d 为不足额；
    该窗口按纯文字绘制，MSP 图标标记 [deco2] 写成“MSP”）。"""
    app=app_instance(p);price=SUPPLY_PRICES[sku]
    msp=p.call('_ZN7AppMain18GetMSPointSaveDataEv',app)
    ref=p.managed_obj(sku)
    p.log('LOCAL_SUPPLY_BUY',sku,price,'MSP',msp,'OK' if msp>=price else 'SHORT')
    if msp>=price:
        p.call('_ZN7AppMain18AddMSPointSaveDataEi',app,-price)
        queue_callback(p,'purchaseFinished',(p.env,0,0,ref),(ref,))
        return
    if not hasattr(p,'supply_text'):p.supply_text=p.alloc(256)
    text=native_text(p,'strShopTbl',11).replace('%d',str(price-msp)).replace('[deco2]','MSP').encode()[:255]
    p.write(p.supply_text,text+b'\0')
    slot=p.word(p.symbols['strMedalTbl']+4*p.word(app+LANGUAGE))+4*6
    original=p.word(slot);p.put(slot,p.supply_text)
    try:deliver(p,*callback(p,'purchaseFinished',(p.env,0,4,ref),(ref,)))
    finally:p.put(slot,original)

def string_array(p,values):
    refs=[p.managed_obj(value) for value in values]
    array=p.managed_obj({'kind':'objects','length':len(refs),'items':refs})
    for ref in refs:p.jni_release(ref)
    return array

def handle_java_call(p,method,arg):
    name=method[1]
    if name=='showEndDialogView':
        # 原生标题画面 Back 请求 Android 退出确认框；Windows 版直接按关闭窗口的正常流程结束。
        p.log('LOCAL_EXIT_REQUEST',name,p.frame)
        if p.stop_event is not None:p.stop_event.set()
        return True,0
    if name in ('purchasesInit','purchasesFinalize'):
        p.local_store_state=2 if name=='purchasesInit' else 0
        p.log('LOCAL_MEDAL_STORE',name)
        return True,0
    if name=='getAppStoreState':return True,getattr(p,'local_store_state',0)
    if name=='checkUnCosumableData':return True,0
    if name=='getPurchasesData':
        products=[p.objects[ref] for ref in p.objects[arg(0)]['items']]
        titles=[f'{MEDAL_PACKS[sku]} MEDALS' if sku in MEDAL_PACKS else native_text(p,'strMedalTbl',SUPPLY_NAMES[sku]) if sku in SUPPLY_NAMES else sku for sku in products]
        prices=['FREE' if sku in MEDAL_PACKS else f'{SUPPLY_PRICES[sku]} MSP' if sku in SUPPLY_PRICES else '--' for sku in products]
        descriptions=['Local medal reward' if sku in MEDAL_PACKS else 'Local supply reward' if sku in SUPPLY_PRICES else 'Unavailable' for sku in products]
        arrays=[string_array(p,values) for values in (titles,prices,['inapp']*len(products),descriptions,products)]
        queue_callback(p,'purchaseListFinished',(p.env,0,len(products),*arrays),arrays)
        p.log('LOCAL_MEDAL_CATALOG',products)
        return True,0
    if name=='requestUnManagedConsume' and method[2]=='()V':return True,0
    if name in ('requestBilling','requestUnManagedConsume'):
        sku=p.objects[arg(0)]
        if sku in SUPPLY_PRICES:
            # 支援物资以 MSP 购买：余额核对与扣除调用原生存档函数，延后到本帧原生返回之后。
            queue_action(p,lambda p:buy_supply(p,sku))
            return True,0
        # Completion remains in the original game: it selects the SKU quantity,
        # adds medals with the original cap, and commits its own save format.
        code=0 if sku in MEDAL_PACKS else 4
        ref=p.managed_obj(sku)
        queue_callback(p,'purchaseFinished',(p.env,0,code,ref),(ref,))
        p.log('LOCAL_MEDAL_BUY',sku,MEDAL_PACKS.get(sku,0),'FREE',code)
        return True,0
    if name in ('consumeBilling','unManagedBilling','restoreBilling'):
        # No remote receipts exist for a local reward. Restoration finishes empty.
        sku=p.objects[arg(0)] if name=='consumeBilling' else ''
        ref=p.managed_obj(sku)
        queue_callback(p,'purchaseFinished',(p.env,0,5 if name!='restoreBilling' else 2,ref),(ref,))
        return True,0
    if name in ('eventTracking','PartyTrackEvent','PartyTrackPayment'):
        p.log('LOCAL_ANALYTICS_DISABLED',name)
        return True,0
    if name=='isGameCenterEnable':return True,0
    if name in ('signIn','signOut'):
        p.log('LOCAL_SIGN_IN_UNAVAILABLE',name)
        return True,0
    if name in ('cancelRoom','resetDisconnectedPlayer','clearInvitationId'):
        p.log('LOCAL_NETWORK_IDLE',name)
        return True,0
    if name=='getDisconnectedPlayerNum':return True,0
    if name=='setRoomVariant' and method[2]=='(I)V':
        p.local_room_variant=arg(0)
        p.log('LOCAL_ROOM_VARIANT',p.local_room_variant)
        return True,0
    if name in ('sendDataTCP','sendDataUDP') and method[2]=='([BLjava/lang/String;)V':
        # These original player-info announcements are redundant in NPC mode.
        # Read the game's exported singleton without re-entering native execution.
        app=app_instance(p)
        if app and p.read(app+0xc061,1)==b'\x01' and p.word(app+0xc63c)==4:
            if not hasattr(p,'local_npc_message_counts'):p.local_npc_message_counts={}
            p.local_npc_message_counts[name]=p.local_npc_message_counts.get(name,0)+1
            if p.local_npc_message_counts[name]==1:p.log('LOCAL_NPC_NETWORK_MESSAGE_OMITTED',name)
            return True,0
    if name=='startQuickGame' and method[2]=='(III)V':
        app=app_instance(p)
        if app and p.word(app+0xc06c)==1 and p.word(app+0xc63c)==4:
            p.log('LOCAL_EVENT_MATCH_REQUEST_OMITTED')
            return True,0
    if name=='getLeaderboardMyRank':
        p.local_leaderboard_rank=-1
        p.log('LOCAL_LEADERBOARD_UNAVAILABLE')
        return True,0
    if name=='getLeaderboardMyRankNum':return True,0xffffffff
    if name=='getDisplayDefaultName':return True,p.managed_obj('----------')
    if name=='showLeaderboard':
        p.log('LOCAL_LEADERBOARD_UNAVAILABLE')
        return True,0
    if name=='isShowMoreAppsState':return True,0
    return False,0

def deliver(p,name,args,refs):
    # A real Java -> JNI native call has an implicit local-reference frame.
    locals_before={ref:counts['local'] for ref,counts in p.jni_refs.items()}
    p.log('LOCAL_CALLBACK',name,[hex(x) for x in args],[(hex(ref),p.jni_refs.get(ref)) for ref in refs])
    try:p.call(name,*args)
    finally:
        for ref,counts in list(p.jni_refs.items()):
            extra=counts['local']-locals_before.get(ref,0)
            for _ in range(max(0,extra)):p.jni_release(ref)
        for ref in refs:p.jni_release(ref,'global')

def pump(p):
    """Deliver Java-to-native callbacks only after the active native frame returns."""
    callbacks=getattr(p,'platform_callbacks',None)
    while callbacks:
        entry=callbacks.pop(0)
        if callable(entry):entry(p)
        else:deliver(p,*entry)
