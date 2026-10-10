"""Historical Event tables and isolated preview state for the Windows host."""
from pathlib import Path
import json,struct,os,base64,contextlib
HEADER=0x1ffed000
MAGIC=0x45565431
SAVE_FILES=('test.dat','historical_event_progress.json')
class _ShopExchangeRejected(Exception):
    pass
def atomic_bytes(path,raw):
    temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    temp.replace(path)
def recover_transaction(saves):
    journal=saves/'historical_event_transaction.json'
    if not journal.exists():return False
    data=json.loads(journal.read_text(encoding='utf-8'))
    if data.get('schema')!=1:raise ValueError('Unsupported Event transaction schema')
    for name in SAVE_FILES:
        raw=data['files'][name];path=saves/name
        if raw is None:path.unlink(missing_ok=True)
        else:atomic_bytes(path,base64.b64decode(raw,validate=True))
    journal.unlink();return True
class EventTrial:
    def __init__(self,p,root):
        self.p=p;self.root=Path(root);self.app=0;self.overlay=None;self.selected=None
        self.catalog=json.loads((self.root/'historical_events/catalog.json').read_text(encoding='utf-8'))['events']
        self.data={e['event_key']:json.loads((self.root/'historical_events/data'/Path(e['data_path']).name).read_text(encoding='utf-8')) for e in self.catalog}
        from event_phases import EventPhases
        self.phases=EventPhases(self.root,self.data);self.selected_phase=None
        self.phase_tables={};self.phase_shop_tables={}
        self.info=p.call('_ZN10BattleInfo11getInstanceEv');self.db=p.word(self.info)
        self.groups=p.word(self.db+0x14)
        self.original_groups=[p.read(self.groups+i*8,8) for i in range(14)]
        self.original_survival=p.read(self.db+0x20,16)
        self.progress_path=p.saves/'historical_event_progress.json'
        self.progress=json.loads(self.progress_path.read_text(encoding='utf-8')) if self.progress_path.exists() else {'schema':1,'events':{}}
        if self.progress.get('schema')!=1:raise ValueError('Unsupported Event progress schema')
        self.tables={};self.shop_tables={};self.native_shop_active=False;self.active_battle=None;self.last_scene=None
        self.last_message='';self.dirty=False;self.page=0;self.revision=0;self.hitboxes=[]
        self.renderer=None;self.image=None;self.original_currency=None;self.started=False;self.result=None
        self.transition_action=None;self.transition_frame=0
        p.uc.lib.msd_enable_historical_event_hooks()
        for key,d in self.data.items():
            rows=[]
            for s in d['stages']:
                words=list(s['scalar_words_120byte_layout'])
                words[17]=self.blob(b''.join(struct.pack('<3i',*r) for r in s['enemies']))
                for index,name in ((19,'schedule_packed'),(21,'waves_raw'),(23,'auxiliary_packed'),(28,'additional_units_raw')):
                    pointed=s['pointed_data'][name]
                    raw=bytes.fromhex(pointed['hex'])
                    if len(raw)!=pointed['count']*pointed['stride']:
                        raise ValueError(f'Invalid Event mission array: {key}/{s["id"]}/{name}')
                    # Enemy.update and runScriptAction seek by the signed -1
                    # terminator, independently of the MissionInfo count.
                    # Retain that count and reserve a valid end record even
                    # when the historical mission has no scheduled spawns.
                    if name=='schedule_packed':
                        if not raw or struct.unpack_from('<h',raw,len(raw)-4)[0]!=-1:
                            raw+=struct.pack('<hbb',-1,0,0)
                    words[index]=self.blob(raw)
                rows.append(struct.pack('<30I',*words))
            table={'missions':self.blob(b''.join(rows)),'count':len(rows)}
            if d.get('ex_survival'):
                ex=[]
                for s in d['ex_survival']:
                    words=list(s['raw_words'])
                    for i,raw in zip((13,14),s['pointed_tables_raw']):words[i]=self.blob(bytes.fromhex(raw))
                    ex.append(struct.pack('<16I',*words))
                table['ex']=self.blob(b''.join(ex));table['ex_count']=len(ex)
                drops=[]
                for row in d['drop_items']:
                    words=row['raw_words']
                    if len(words)==6:words=words[:5]+[0xffffffff]*15+words[5:]
                    assert len(words)==21
                    drops.append(struct.pack('<21I',*words))
                table['drops']=self.blob(b''.join(drops));table['drop_count']=len(drops)
            self.tables[key]=table
            products=d.get('shop',{}).get('rows',[])
            if products:
                records=[]
                for r in products:
                    raw=bytes.fromhex(r['raw_hex'])
                    if len(raw)!=32 or struct.unpack_from('<H',raw)[0]!=r['id'] or raw[2]!=r['type']:
                        raise ValueError(f'Invalid Event shop record: {key}/{r["id"]}')
                    records.append(struct.pack('<16I',r['id'],self.blob(raw),r['event_currency_price'],
                                               r['native_maximum'],0,r['type'],r['unit_id'],*([0]*9)))
                self.shop_tables[key]={'catalog':self.blob(struct.pack('<'+'I'*len(products),*[r['id'] for r in products])),
                                       'records':self.blob(b''.join(records)),'count':len(products)}
        # 自制 EVENT（M6b）：本体 community_content/events/ 与已载入模组的 EVENT 编译为同一结构（event_content.py）。
        import event_content
        self.custom_events=event_content.install(self)
        medal=json.loads((self.root/'historical_events/medal_shop.json').read_text(encoding='utf-8'))
        self.medal_catalog=[r for r in medal['rows'] if r['event_key'] in self.data]+self.custom_medal_rows
        self.medal_table=None;self.shop_kind='token';self.medal_owned=set()
        # 活动勋章单位的商品号登记为活动专属（src/event_trial_hooks.cpp event_exclusive_sku）。
        skus=sorted({r['menu_shop_id'] for r in self.medal_catalog})[:64]
        p.write(0x1ffef200,struct.pack('<II',0x4b535645,len(skus))+struct.pack('<'+'I'*len(skus),*skus))
        from event_native_map import NativeEventMap
        self.native_map=NativeEventMap(self)
        from event_native_selector import NativeEventSelector
        self.native_selector=NativeEventSelector(self)
        from event_browser import EventBrowser
        self.browser=EventBrowser(self)
    def blob(self,raw):
        if not raw:return 0
        addr=self.p.alloc(len(raw));self.p.write(addr,raw);return addr
    def mission_table(self,key,phase_id=None):
        phase_id=self.phases.resolve(key,phase_id);phase=self.phases.part(key,phase_id)
        source=self.tables[key]
        if phase is None or (len(phase['stage_ids'])==source['count'] and not phase.get('stage_overrides')):return source
        cache_key=(key,phase_id)
        if cache_key in self.phase_tables:return self.phase_tables[cache_key]
        rows=[]
        for index,sid in enumerate(phase['stage_ids']):
            words=list(struct.unpack('<30I',self.p.read(source['missions']+index*120,120)))
            override=phase.get('stage_overrides',{}).get(str(sid),{}).get('pointed_data',{})
            for field,offset in (('schedule_packed',19),('waves_raw',21),('auxiliary_packed',23),('additional_units_raw',28)):
                if field in override:
                    item=override[field];raw=bytes.fromhex(item['hex'])
                    if len(raw)!=item['count']*item['stride']:raise ValueError('Invalid source phase array')
                    words[offset]=self.blob(raw)
            rows.append(struct.pack('<30I',*words))
        table=dict(source);table['missions']=self.blob(b''.join(rows));table['count']=len(rows)
        if 'ex' in table:table['ex_count']=min(table['ex_count'],len(rows))
        self.phase_tables[cache_key]=table
        return table
    def shop_table(self,key,phase_id=None):
        phase_id=self.phases.resolve(key,phase_id);phase=self.phases.part(key,phase_id)
        source=self.shop_tables.get(key)
        if source is None or phase is None:return source
        allowed=set(phase['shop_ids']);products=self.data[key].get('shop',{}).get('rows',[])
        if len(allowed)==len(products):return source
        cache_key=(key,phase_id)
        if cache_key in self.phase_shop_tables:return self.phase_shop_tables[cache_key]
        selected=[(i,r) for i,r in enumerate(products) if r['id'] in allowed]
        if not selected:return None
        table={'catalog':self.blob(struct.pack('<'+'I'*len(selected),*[r['id'] for _,r in selected])),
               'records':self.blob(b''.join(self.p.read(source['records']+i*64,64) for i,_ in selected)),
               'count':len(selected)}
        self.phase_shop_tables[cache_key]=table
        return table
    def active_shop_table(self):
        return self.shop_table(self.selected,self.selected_phase) if self.selected else None
    def is_native_shop_context(self):
        if not self.selected or self.p.word(self.app+0x22bc)!=39:return False
        kind,mode=self.p.word(HEADER+8),self.p.word(self.app+0xb890)
        return bool((kind==1 and mode==6 and self.has_shop()) or (kind==2 and mode==2 and self.medal_table))
    # ---------- 活动勋章单位商店（每个活动独立目录，原生单位商店页面，原生勋章结算） ----------
    def medal_rows(self):
        if not self.selected:return []
        phase=self.selected_phase
        return [r for r in self.medal_catalog if r['event_key']==self.selected
                and (not r.get('phases') or phase is None or phase in r['phases'])]
    def has_medal_shop(self):
        return bool(self.medal_rows())
    def medal_permitted(self,row):
        rule=row['availability'];state=self.state()
        if rule['kind']=='event_available':return True
        if rule['kind']=='stage_win':
            return state['stages'].get(rule['local_stage_key'],{}).get('wins',0)>0
        if rule['kind']=='score':
            return max(state.get('score_peak',0),state['currency'])>=rule['minimum']
        return False
    def build_medal_table(self):
        p=self.p;rows=self.medal_rows();records=[]
        for r in rows:
            raw=bytearray(p.read(p.call('_Z15GetMenuShopData10MenuShopID',r['menu_shop_id']),32))
            if struct.unpack_from('<H',raw)[0]!=r['menu_shop_id'] or raw[2]!=2:raise ValueError(f"Invalid medal shop row {r['menu_shop_id']}")
            raw[0x14]=1
            records.append(struct.pack('<16I',r['menu_shop_id'],self.blob(bytes(raw)),r['medal_price'],1,0,2,r['unit_id'],
                                       int(self.medal_permitted(r)),*([0]*8)))
        table={'catalog':self.blob(struct.pack('<'+'I'*len(rows),*[r['menu_shop_id'] for r in rows])),
               'records':self.blob(b''.join(records)),'count':len(rows)}
        if self.medal_table:
            for key in ('catalog','records'):self.p.free(self.medal_table[key])
        self.medal_table=table
        self.medal_owned={r['unit_id'] for r in rows if self.unit_owned(r['unit_id'])}
        return table
    def unit_owned(self,uid):
        return self.p.call('_ZN7AppMain20GetUnitLevelSaveDataE6UnitID',self.app,uid)!=0xffffffff
    def poll_medal_purchase(self):
        """原生勋章购买完成后立即写入原生存档（勋章与单位均属原生进度）。"""
        owned={r['unit_id'] for r in self.medal_rows() if self.unit_owned(r['unit_id'])}
        new=owned-self.medal_owned
        if new:
            self.medal_owned=owned
            self.p.call('_ZN7AppMain17WriteMainSaveDataEv',self.app)
            self.p.log('HISTORICAL_MEDAL_SHOP_PURCHASE',self.selected,sorted(new))
    def state(self):
        state=self.progress['events'].setdefault(self.selected,{'currency':0,'stages':{},'inventory':{}})
        state['currency']=max(0,min(99999999,state['currency']))
        if 'purchase_counts' not in state:
            # 旧存档的商品计数按整个活动家族恢复，包含当前首期未显示的后期商品。
            rows=self.data[self.selected].get('shop',{}).get('rows',[])
            state['purchase_counts']={str(r['id']):state['inventory'].get(str(r['id']),0)//max(1,r['quantity']) for r in rows}
        return state
    def transition(self,action):
        if self.transition_action is not None:return False
        self.app=self.p.app_instance();self.transition_action=action;self.transition_frame=self.p.frame
        self.p.call('_ZN7AppMain15SetShutterCloseEv',self.app)
        self.p.log('HISTORICAL_SHUTTER_CLOSE')
        return True
    def select(self,key,enter=False,immediate=False,phase_id=None):
        phase_id=self.phases.resolve(key,phase_id)
        if enter and not immediate:return self.transition(lambda:self.select(key,True,True,phase_id=phase_id))
        p=self.p;self.app=p.app_instance()
        assert key in self.data
        if self.active_battle:raise RuntimeError('Cannot switch Event during battle')
        self.native_map.disable()
        self.native_selector.disable()
        for offset in (8,12,16,20,24,28,44,48):p.put(HEADER+offset,0)
        self.native_shop_active=False
        for i,raw in enumerate(self.original_groups):p.write(self.groups+i*8,raw)
        p.write(self.db+0x20,self.original_survival)
        if self.original_currency is None:
            self.original_currency=self.progress.setdefault('baseline_survival_currency',p.call('_ZN7AppMain24GetSurvivalPointSaveDataEv',self.app))
            self.dirty=True;self.flush()
        self.selected=key;self.selected_phase=phase_id;d=self.data[key];t=self.mission_table(key,phase_id)
        shop=self.active_shop_table()
        if shop:
            for offset,name in ((12,'catalog'),(16,'count'),(20,'records'),(24,'count')):p.put(HEADER+offset,shop[name])
        p.put(HEADER+36,self.app)
        group=d['stages'][0]['group']
        # 自制 EVENT 的关卡记录只经地图钩子按关卡编号查找（map_mission），不借用原生关卡组。
        if group is not None:p.write(self.groups+group*8,struct.pack('<II',t['missions'],t['count']))
        if 'ex' in t:p.write(self.db+0x20,struct.pack('<4I',t['ex'],t['ex_count'],t['drops'],t['drop_count']))
        self.state();self.overlay=None;self.page=0;self.revision+=1;p.put(HEADER,MAGIC);p.put(HEADER+4,0)
        p.call('_ZN7AppMain24SetSurvivalPointSaveDataEi',self.app,self.state()['currency'])
        p.put(self.app+0xc63c,4);p.put(self.app+0xc06c,1);p.put(self.app+0xc8c8,6)
        # 女教官基地的原生“出擊”进入 EventMSD 场景（158），由此处启用的历史数据回应。
        self.native_map.enable()
        # 原生 Survival 兑换商店（地图 BASE 区域，MenuShop 模式 6）在活动中读取该活动目录与原价。
        if self.has_shop():self.prepare_native_shop()
        p.put(HEADER+48,len(self.medal_rows()))
        self.prepare_item_hud()
        if enter:
            p.call('_ZN7AppMain12SceneEndFuncEi',self.app,p.word(self.app+0x22bc))
            p.call('_ZN7AppMain23SC_WiFiMenuInit_TagTeamEv',self.app)
        p.log('HISTORICAL_EVENT_SELECTED',key,t['count'],phase_id)
    def start_battle(self,index):
        if index not in self.native_map.active_table()['by_index']:raise ValueError('Stage is outside the selected Event phase')
        p=self.p;app=self.app;d=self.data[self.selected];s=d['stages'][index]
        cost=s['stamina_cost'];stamina=p.call('_ZN7AppMain18GetStaminaSaveDataEv',app)
        if stamina<cost:self.last_message='体力不足';return False
        p.call('_ZN7AppMain12SceneEndFuncEi',app,p.word(app+0x22bc))
        p.put(HEADER+164,self.native_map.active_table()['by_index'][index]['bgm_id'])
        p.call('_ZN7AppMain18AddStaminaSaveDataEi',app,-cost)
        legacy=d['controller'] in ('legacy_survival','current_cooperation')
        p.put(app+0xc030,0);p.put(app+0xc034,0)
        p.put(app+0xc8c8,5 if legacy else 3)
        p.put(app+0xc63c,3 if legacy else 1)
        p.put(app+0xc624,0);p.put(app+0xc628,0);p.put(app+0xc62c,0)
        name='_ZN7AppMain23BattleInit_SurvivalModeEi' if legacy else '_ZN7AppMain25BattleInit_StageClearModeEi'
        p.call(name,app,s['id'])
        p.call('_ZN7AppMain20BattleStartSetStatusEiii9WorldType',app,0,0,0,0)
        p.call('_ZN7AppMain18BattleStartSetUnitEv',app)
        if legacy:
            ptr=p.call('_ZN10BattleInfo17getExSurvivalInfoEi',self.info,s['id'])
            p.put(app+0xb9a4,p.word(ptr+8))
        p.call('_ZN7AppMain26SetContinueStageIDSaveDataEi',app,0)
        p.call('_ZN7AppMain11ChangeExeSTEi',app,99)
        music=self.native_map.active_table()['by_index'][index]['bgm_id']
        p.call('_ZN7AppMain10Sound_LoadE7SoundID',app,music)
        p.call('_ZN7AppMain20Sound_RequestPlayBGME7SoundIDi',app,music,0)
        self.active_battle={'index':index,'stage':s,'key':self.selected};self.overlay=None;self.revision+=1
        p.log('HISTORICAL_BATTLE_START',self.selected,s['id'])
        return True
    def update(self):
        self.app=self.p.app_instance()
        if not self.app:return
        from cockpit_hold import instance
        instance(self.p).tick()
        if self.p.word(HEADER+200):
            self.reset_event_context()
            self.transition_action=None
            self.p.log('HISTORICAL_MAIN_MENU_RESET')
        if self.transition_action is not None:
            if self.p.call('_ZN7AppMain12IsShutterEndEv',self.app):
                action=self.transition_action;self.transition_action=None;action()
                self.p.call('_ZN7AppMain14SetShutterOpenEv',self.app)
                self.p.call('_ZN7AppMain16setCockpitClosedEv',self.app)
                self.p.log('HISTORICAL_SHUTTER_OPEN')
            return
        self.last_scene=self.p.word(self.app+0x22bc)
        self.native_map.update()
        self.native_selector.update()
        self.browser.update()
        self.native_shop_active=self.is_native_shop_context()
        if self.native_shop_active and self.shop_kind=='medal':self.poll_medal_purchase()
        pending=self.p.word(HEADER+28)
        if pending:
            self.p.put(HEADER+28,0)
            self.native_shop_purchase(pending-1)
        if self.native_shop_active and self.last_scene==67 and not self.p.word(HEADER+84):
            self.p.put(HEADER+8,0);self.native_shop_active=False
        if not self.started and self.p.frame>=140:
            self.started=True
            self.p.call('_ZN7AppMain26SetContinueStageIDSaveDataEi',self.app,0)
        if self.p.word(HEADER+4) and self.active_battle:self.finish_battle()
        battle=self.p.word(self.app+0xc220) if self.active_battle else 0
        if battle and self.last_scene in (110,120) and not self.p.read(battle+0x1c,1)[0] and not self.p.call('_ZN10BattleMain15isBattlePlayingEv',battle):
            # The preview finalizes defeat locally; the legacy paid-continue
            # popup depends on service state outside the isolated Event profile.
            self.finish_battle()
        if self.selected and self.last_scene==67 and self.active_battle is None:
            self.p.put(self.app+0xc63c,4);self.p.put(self.app+0xc06c,1)
        # 原生合作流程（模式 6）在原生存档中增减活动积分，回写该活动的独立进度。
        if self.selected and self.data[self.selected]['controller']=='current_cooperation' and self.p.word(HEADER+84) and self.p.word(self.app+0xc8c8)==6:
            point=self.p.call('_ZN7AppMain24GetSurvivalPointSaveDataEv',self.app)
            if point!=self.state()['currency']:
                state=self.state();state['currency']=point;state['score_peak']=max(state.get('score_peak',0),point)
                self.dirty=True;self.flush()
        if self.overlay:self.draw()
    def flush(self):
        if not self.dirty:return
        atomic_bytes(self.progress_path,json.dumps(self.progress,ensure_ascii=False,indent=2).encode('utf-8'))
        self.dirty=False
    @contextlib.contextmanager
    def transaction(self):
        journal=self.p.saves/'historical_event_transaction.json'
        files={name:base64.b64encode((self.p.saves/name).read_bytes()).decode('ascii') if (self.p.saves/name).exists() else None for name in SAVE_FILES}
        atomic_bytes(journal,json.dumps({'schema':1,'files':files}).encode('utf-8'))
        previous=json.loads(json.dumps(self.progress));ram=self.p.read(self.app+0x3d08,0x5ab0)
        try:
            yield
            self.p.call('_ZN7AppMain20WriteMainSaveDataExeEv',self.app)
            if not self.p.call('_ZN7AppMain18SaveDataWriteCheckEv',self.app):raise RuntimeError('Event save verification failed')
            self.dirty=True;self.flush();journal.unlink()
        except Exception:
            self.p.write(self.app+0x3d08,ram);self.progress=previous;self.dirty=False
            recover_transaction(self.p.saves)
            raise
    def finish_battle(self):
        if hasattr(self.p,'campaign') and self.p.campaign.active:
            return self.p.campaign.finish()
        p=self.p;app=self.app;record=self.active_battle;d=self.data[self.selected]
        battle=p.word(app+0xc220)
        won=bool(p.read(battle+0x1c,1)[0])
        earned=p.call('_ZN10BattleMain13getGetMSPointEv',battle)
        if not won:earned=max(0,earned-p.call('_ZN10BattleMain14getGetMSPoint2Ev',battle))
        state=self.state();stage_key=record['stage']['local_stage_key']
        saved=state['stages'].setdefault(stage_key,{'attempts':0,'wins':0})
        saved['attempts']+=1;saved['wins']+=int(won)
        if won:saved['captures']=saved.get('captures',0)+p.call('_ZN10BattleMain14getGetPrisonerEv',battle)
        native_map=record.get('native_map',False)
        if native_map:
            rank=self.native_map.save_result(record,won,p.word(battle+0x48))
            if won:self.apply_prisoner_rewards()
            if won:self.apply_unit_rewards(record['stage'],saved)
        if d['currency']:state['currency']=min(99999999,state['currency']+earned)
        else:p.call('_ZN7AppMain18AddMSPointSaveDataEi',app,earned)
        self.result={'won':won,'earned':earned,'stage_id':record['stage']['id']}
        self.dirty=True;self.flush()
        p.put(HEADER,0);p.put(HEADER+4,0)
        # Preserve native teardown while using sidecar Event progression.
        # Mode 7 excludes the old fixed-area completion/reward arrays.
        p.put(app+0xc8c8,7)
        p.call('_ZN7AppMain12SC_BattleEndEv',app)
        if native_map:
            p.put(app+0xb160,159 if p.word(HEADER+84) else 32)
            p.put(app+0xb8dc,0)
            self.result.update(rank=rank,time=p.word(battle+0x48))
            self.active_battle=None;self.overlay=None
            p.call('_ZN7AppMain24SetSurvivalPointSaveDataEi',app,state['currency'])
            p.call('_ZN7AppMain26SetContinueStageIDSaveDataEi',app,0)
            p.call('_ZN7AppMain17WriteMainSaveDataEv',app)
            p.put(HEADER,MAGIC)
            p.log('HISTORICAL_BATTLE_RESULT',record['key'],self.result)
            return
        p.call('_ZN7AppMain25BattleEnd_ClearBattleMainEv',app)
        p.put(HEADER,MAGIC)
        self.active_battle=None
        p.put(app+0xc63c,4);p.put(app+0xc8c8,6)
        p.call('_ZN7AppMain24SetSurvivalPointSaveDataEi',app,state['currency'])
        p.call('_ZN7AppMain26SetContinueStageIDSaveDataEi',app,0)
        p.call('_ZN7AppMain17WriteMainSaveDataEv',app)
        p.call('_ZN7AppMain23SC_WiFiMenuInit_TagTeamEv',app)
        self.open('result');p.log('HISTORICAL_BATTLE_RESULT',record['key'],self.result)
    def reset_event_context(self):
        p=self.p
        self.native_map.disable()
        self.native_selector.disable()
        for i,raw in enumerate(self.original_groups):p.write(self.groups+i*8,raw)
        p.write(self.db+0x20,self.original_survival)
        p.write(HEADER,b'\0'*224)
        if self.selected is not None and self.original_currency is not None:
            p.call('_ZN7AppMain24SetSurvivalPointSaveDataEi',self.app,self.original_currency)
        self.selected=None;self.selected_phase=None;self.overlay=None;self.native_shop_active=False;self.active_battle=None
        self.hitboxes=[];self.result=None;self.page=0;self.revision+=1
        for offset in (0xb1ec,0xb1f0,0xb1f4,0xc030,0xc034,0xc63c,0xc06c,0xc8c8):p.put(self.app+offset,0)
    def leave(self,immediate=False):
        if self.active_battle:return
        if not immediate:return self.transition(lambda:self.leave(True))
        p=self.p
        self.reset_event_context()
        p.call('_ZN7AppMain12SceneEndFuncEi',self.app,p.word(self.app+0x22bc))
        p.call('_ZN7AppMain11ChangeExeSTEi',self.app,31)
    def leave_to_menu(self,immediate=False):
        """已进入的活动顶层（女教官基地）退出：恢复非活动上下文后直接返回主菜单（R10）。"""
        if self.active_battle:return
        if not immediate:return self.transition(lambda:self.leave_to_menu(True))
        p=self.p
        self.reset_event_context()
        p.call('_ZN7AppMain12SceneEndFuncEi',self.app,p.word(self.app+0x22bc))
        p.call('_ZN7AppMain11ChangeExeSTEi',self.app,27)
    def apply_unit_rewards(self,stage,saved):
        """自制 EVENT 小关的首次胜利单位奖励（与扩展世界相同：未拥有时给予 Lv1，开放阶段 20）。"""
        if not stage.get('reward_units') or saved.get('unit_rewards_claimed'):return
        p=self.p
        for uid in stage['reward_units']:
            if p.call('_ZN7AppMain20GetUnitLevelSaveDataE6UnitID',self.app,uid)==0xffffffff:
                p.call('_ZN7AppMain20SetUnitLevelSaveDataE6UnitIDi',self.app,uid,0)
                p.call('_ZN7AppMain24SetUnitLevelOpenSaveDataE6UnitIDi',self.app,uid,20)
        saved['unit_rewards_claimed']=True
        p.log('CUSTOM_EVENT_UNIT_REWARD',self.selected,stage['local_stage_key'],stage['reward_units'])
    def apply_prisoner_rewards(self):
        p=self.p;state=self.state();claims=state.setdefault('reward_claims',{})
        event=self.native_map.active_manifest();parts=self.data[self.selected]['controller']=='parts'
        for area in event['areas']:
            pid=area['prisoner_id']
            if pid<0 or str(pid) in claims:continue
            stages=[self.data[self.selected]['stages'][m['index']] for m in area['markers']]
            values=[state['stages'].get(s['local_stage_key'],{}).get('captures',0) for s in stages]
            limits=[m['pow_max'] for m in area['markers']]
            count=max(values,default=0) if parts else sum(values);maximum=max(limits,default=0) if parts else sum(limits)
            if maximum<=0 or count<maximum:continue
            reward=struct.unpack('<6I',bytes.fromhex(event['prisoners'][str(pid)]['raw_hex']))
            if reward[3]==1 and reward[4]!=0xffffffff:
                if p.call('_ZN7AppMain20GetUnitLevelSaveDataE6UnitID',self.app,reward[4])==0xffffffff:
                    p.call('_ZN7AppMain20SetUnitLevelSaveDataE6UnitIDi',self.app,reward[4],0)
                    if self.data[self.selected].get('custom'):p.call('_ZN7AppMain24SetUnitLevelOpenSaveDataE6UnitIDi',self.app,reward[4],20)
            claims[str(pid)]=True
            p.log('HISTORICAL_PRISONER_REWARD',self.selected,pid,reward[4])
        d=self.data[self.selected]
        if d.get('custom'):
            # 自制 EVENT（M6b-3）：parts 收齐全部零件、invitation 救出全部邀请函时给予 final_reward_units。
            stages=d['stages'];markers=[m for a in event['areas'] for m in a['markers']]
            if d['controller']=='parts':done=bool(event['prisoners']) and all(str(pid) in claims for pid in event['prisoners'])
            elif d['controller']=='invitation':
                done=any(m['pow_max'] for m in markers) and all(state['stages'].get(stages[m['index']]['local_stage_key'],{}).get('captures',0)>=m['pow_max'] for m in markers)
            else:done=False
            if done and d.get('final_reward_units') and not claims.get('final'):
                for uid in d['final_reward_units']:
                    if p.call('_ZN7AppMain20GetUnitLevelSaveDataE6UnitID',self.app,uid)==0xffffffff:
                        p.call('_ZN7AppMain20SetUnitLevelSaveDataE6UnitIDi',self.app,uid,0)
                        p.call('_ZN7AppMain24SetUnitLevelOpenSaveDataE6UnitIDi',self.app,uid,20)
                claims['final']=True
                p.log('CUSTOM_EVENT_FINAL_REWARD',self.selected,d['final_reward_units'])
        elif parts and all(str(pid) in claims for pid in event['prisoners']):
            if p.call('_ZN7AppMain20GetUnitLevelSaveDataE6UnitID',self.app,285)==0xffffffff:
                p.call('_ZN7AppMain20SetUnitLevelSaveDataE6UnitIDi',self.app,285,0)
    def open(self,page):
        if page=='shop':return self.open_native_shop()
        if page=='medal_shop':return self.open_medal_shop()
        if page=='stages':return self.native_map.open()
        if page=='events':return self.browser.open()
        if page=='main_menu':return self.leave_to_menu()
        if page in ('tasks','cooperation'):
            self.overlay=None
            if page=='tasks':
                visible=self.native_map.active_table()['by_index']
                stages=self.data[self.selected]['stages'];saved=self.state()['stages']
                wins=sum(saved.get(stages[i]['local_stage_key'],{}).get('wins',0)>0 for i in visible)
                title='EVENT PROGRESS';message=f"CLEAR: {wins}/{len(visible)}\nEVENT POINTS: {self.state()['currency']}"
            else:
                title='COOPERATION';message='Historical stages are available in single-player mode.\nThe original online cooperation service is unavailable.'
            self.p.call('_ZN7AppMain10SetPopupOKEPcS0_PFvvEiiii',self.app,self.p.cstr(message),self.p.cstr(title),0,290,30,-256,0)
            return
        self.overlay=page;self.page=0;self.last_message='';self.revision+=1;self.image=None
    # 战斗左下拾取物计数：1.46 原生合成代码沿用 1.39 版图集坐标（第 85 节），秘宝（1.37/1.38）为静态金币，圣诞（1.39）为旋转星形。
    HUD_ATLAS='event_otakara_ui_hud.obm'
    HUD_COIN=struct.pack('<8h',0,16,14,14,7,7,0,0)*9          # 1.39 图集 ConvEventOtakaraUI 第 0 项（金币）
    def prepare_item_hud(self):
        p=self.p
        atlas=frames=0
        # 自制 legacy_survival（M6b-4）沿用模板活动的图标样式（data['hud']：coin 或 star）。
        style=self.data[self.selected].get('hud') or {'melty_christmas_2015':'star','treasure_recovery_2015':'coin'}.get(self.selected)
        if style and (self.root/'historical_events/assets'/self.HUD_ATLAS).is_file():
            if not getattr(self,'hud_atlas_name',0):self.hud_atlas_name=p.cstr(self.HUD_ATLAS)
            atlas=self.hud_atlas_name
            if style=='coin':
                if not getattr(self,'hud_coin_frames',0):
                    self.hud_coin_frames=p.alloc(len(self.HUD_COIN));p.write(self.hud_coin_frames,self.HUD_COIN)
                frames=self.hud_coin_frames
        p.put(HEADER+216,atlas);p.put(HEADER+220,frames)
    def prepare_native_shop(self):
        p=self.p;t=self.active_shop_table()
        for i,r in enumerate(self.shop_rows()):p.put(t['records']+i*64+16,self.state()['purchase_counts'].get(str(r['id']),0))
        p.put(HEADER+12,t['catalog']);p.put(HEADER+16,t['count']);p.put(HEADER+20,t['records']);p.put(HEADER+24,t['count'])
        p.put(HEADER+28,0);p.put(HEADER+44,0);p.put(HEADER+36,self.app);p.put(HEADER+8,1)
    def open_native_shop(self,immediate=False):
        if not self.has_shop():return False
        if not immediate:return self.transition(lambda:self.open_native_shop(True))
        p=self.p;app=self.app;self.overlay=None;self.native_shop_active=True
        self.shop_map_return=self.native_map.active
        t=self.active_shop_table()
        for i,r in enumerate(self.shop_rows()):p.put(t['records']+i*64+16,self.state()['purchase_counts'].get(str(r['id']),0))
        p.put(HEADER+12,t['catalog']);p.put(HEADER+16,t['count']);p.put(HEADER+20,t['records']);p.put(HEADER+24,t['count'])
        p.put(HEADER+28,0);p.put(HEADER+44,0);p.put(HEADER+36,app);p.put(HEADER+8,1)
        self.shop_kind='token'
        mode=6
        p.call('_ZN7AppMain24SetSurvivalPointSaveDataEi',app,self.state()['currency'])
        p.call('_ZN7AppMain12SceneEndFuncEi',app,p.word(app+0x22bc))
        p.put(app+0xb890,mode)
        p.call('_ZN7AppMain15SC_MenuShopInitEv',app)
        p.log('HISTORICAL_NATIVE_SHOP',self.selected,mode,t['count'])
        return True
    def open_medal_shop(self,immediate=False):
        if not self.has_medal_shop():return False
        if not any(self.medal_permitted(r) and not self.unit_owned(r['unit_id']) for r in self.medal_rows()):
            # 原生目录不列出已拥有单位；无可购买商品时显示与原生 SC_MenuShopLoop 相同的空目录提示（字符串 13/14、SE 18），停留在女教官基地。
            p=self.p
            p.call('_ZN7AppMain23Sound_RequestPlayMenuSEE7SoundID',self.app,0x12)
            message=p.call('_Z13GetStringShopii',0xe,0xffffffff);title=p.call('_Z13GetStringShopii',0xd,0xffffffff)
            p.call('_ZN7AppMain10SetPopupOKEPcS0_PFvvEiiii',self.app,message,title,0,0x122,0x32,0xffffff00,0)
            from cockpit_hold import instance
            instance(p).release(p.word(self.app+0x36e0))
            p.log('HISTORICAL_MEDAL_SHOP_EMPTY',self.selected,self.selected_phase)
            return False
        if not immediate:return self.transition(lambda:self.open_medal_shop(True))
        p=self.p;app=self.app;self.overlay=None;self.native_shop_active=True;self.shop_kind='medal'
        t=self.build_medal_table()
        p.put(HEADER+12,t['catalog']);p.put(HEADER+16,t['count']);p.put(HEADER+20,t['records']);p.put(HEADER+24,t['count'])
        p.put(HEADER+28,0);p.put(HEADER+44,0);p.put(HEADER+36,app);p.put(HEADER+8,2)
        p.call('_ZN7AppMain12SceneEndFuncEi',app,p.word(app+0x22bc))
        p.put(app+0xb890,2)
        p.call('_ZN7AppMain15SC_MenuShopInitEv',app)
        p.log('HISTORICAL_MEDAL_SHOP',self.selected,self.selected_phase,t['count'],
              [r['menu_shop_id'] for r in self.medal_rows() if self.medal_permitted(r)])
        return True
    def close_native_shop(self,immediate=False):
        if not immediate:return self.transition(lambda:self.close_native_shop(True))
        p=self.p
        if self.shop_kind=='medal':self.poll_medal_purchase()
        for offset in (8,12,16,20,24,28,44):p.put(HEADER+offset,0)
        self.native_shop_active=False;self.shop_kind='token'
        p.call('_ZN7AppMain12SceneEndFuncEi',self.app,p.word(self.app+0x22bc))
        # 活动商店返回女教官基地，保留活动与分期身份。
        p.put(self.app+0xc63c,4);p.put(self.app+0xc06c,1);p.put(self.app+0xc8c8,6)
        # 原生基地初始化期间的面板钩子依据商店目录头决定隐藏标记（0xa0 持续保留），须先恢复目录头。
        if self.has_shop():self.prepare_native_shop()
        p.call('_ZN7AppMain23SC_WiFiMenuInit_TagTeamEv',self.app)
    def native_shop_purchase(self,sid):
        if not self.has_shop() or not (self.native_shop_active or self.p.word(HEADER+84)):return False
        p=self.p;row=next((r for r in self.shop_rows() if r['id']==sid),None)
        if row is None:raise ValueError('Purchase outside the selected Event catalog')
        if row['type']==2 and p.call('_ZN7AppMain20GetUnitLevelSaveDataE6UnitID',self.app,row['unit_id'])!=0xffffffff:
            return False
        state=self.state();cost=row['event_currency_price'];t=self.active_shop_table()
        if state['currency']<cost or state['purchase_counts'].get(str(sid),0)>=row['native_maximum']:
            return False
        getter='_ZN7AppMain20GetUnitLevelSaveDataE6UnitID' if row['type']==2 else '_ZN7AppMain18GetMSPointSaveDataEv' if row['type']==1 else '_ZN7AppMain21GetMedalCountSaveDataEv' if row['type']==3 else '_ZN7AppMain19GetMenuItemSaveDataE6ItemID'
        args=(self.app,row['unit_id']) if row['type'] in (0,2) else (self.app,)
        owned_before=p.call(getter,*args)
        original_records=p.read(t['records'],t['count']*64)
        before=p.call('_ZN7AppMain24GetSurvivalPointSaveDataEv',self.app)
        try:
            with self.transaction():
                p.put(HEADER+44,sid+1)
                try:p.call('_Z25PopupResultMenuShopBuyYesv')
                finally:p.put(HEADER+44,0)
                after=p.call('_ZN7AppMain24GetSurvivalPointSaveDataEv',self.app)
                p.log('NATIVE_SHOP_PURCHASE_CHECK',sid,before,after,cost,p.call('_ZN7AppMain20GetUnitLevelSaveDataE6UnitID',self.app,row['unit_id']) if row['type']==2 else -2)
                owned_after=p.call(getter,*args)
                granted=owned_after==0 if row['type']==2 else owned_after>owned_before
                if before-after==cost and cost>=0 and granted:
                    state['currency']=after
                    state['inventory'][str(sid)]=state['inventory'].get(str(sid),0)+row['quantity']
                    state['purchase_counts'][str(sid)]=state['purchase_counts'].get(str(sid),0)+1
                    self.last_message='兑换完成'
                    p.log('HISTORICAL_SHOP_EXCHANGE',self.selected,sid,cost,row['quantity'])
                    return True
                raise _ShopExchangeRejected('Native Event purchase did not apply the complete exchange')
        except _ShopExchangeRejected:
            p.write(t['records'],original_records)
            return False
        except Exception:
            p.write(t['records'],original_records);raise
    def native_point(self,x,y):
        scale=min(self.p.window_size[0]/960,self.p.window_size[1]/640)
        from probe import i32
        return x/scale-i32(self.p.word(self.app+0x3c)),y/scale-i32(self.p.word(self.app+0x40))
    def touch(self,action,x,y):
        if self.transition_action is not None:return True
        if not self.app:return False
        if self.browser.touch(action,x,y):return True
        scene=self.p.word(self.app+0x22bc)
        legacy_map=self.native_map.active and not self.p.word(HEADER+84)
        if scene==34 and not legacy_map and self.world_event_touch(action,x,y):return True
        if self.native_selector.active:
            xx,yy=self.native_point(x,y)
            if xx<175 and yy>=525:
                if action==3:self.native_selector.back()
                return True
        if legacy_map and not self.active_battle and scene==34:
            xx,yy=self.native_point(x,y)
            subscene=self.p.word(self.app+0x22dc)
            if xx<175 and yy>=525 and subscene in (4,7,9):
                if action==3:self.native_map.back()
                return True
            shop_center=480 if subscene==19 else (383 if subscene==13 else 365)
            if abs(xx-shop_center)<70 and yy>=525:
                if action==3:self.open_native_shop()
                return True
        if self.is_native_shop_context():
            xx,yy=self.native_point(x,y)
            if self.host_button(action,x,y,[(0x36d8,'cockpit',xx<175 and yy>=525,('close_shop',))]):return True
        if self.active_battle and scene==100 and not self.active_battle.get('native_map'):
            battle=self.p.word(self.app+0xc220)
            if battle and self.p.read(battle+0x1c,1)[0] and not self.p.call('_ZN10BattleMain15isBattlePlayingEv',battle):
                if action==3:self.p.call('_ZN7AppMain12SC_BattleEndEv',self.app)
                return True
        if self.overlay:
            if action==1:
                self.pointer_down=(x,y)
            if action==3:
                start=getattr(self,'pointer_down',None);self.pointer_down=None
                if start and abs(start[0]-x)+abs(start[1]-y)<32:
                    for rect,command in self.hitboxes:
                        a,b,w,h=rect
                        if a<=x<a+w and b<=y<b+h:self.command(*command);break
            return True
        xx,yy=self.native_point(x,y)
        scene=self.p.word(self.app+0x22bc)
        command=None
        if scene==67 and self.selected:
            # 宿主受理的原生按钮：底栏按钮写入原生按压字段（青色框与三灯），面板转送原生触点（白光）；
            # 释放在框内时保持反馈至闸门合拢，拖出框外取消。
            panel=self.has_shop() or self.has_medal_shop()
            buttons=[(0x36d8,'cockpit',xx<175 and yy>=525,('open','main_menu')),
                     (0x36e0,'cockpit',panel and 400<=xx<=555 and yy>=525,
                      ('open','medal_shop' if self.has_medal_shop() else 'shop')),
                     (0x3400,'panel',panel and 400<=xx<=655 and 430<=yy<=505,
                      ('open','shop' if self.has_shop() else 'medal_shop')),
                     (0x3378,'panel',self.data[self.selected]['controller']!='current_cooperation' and 400<=xx<=655 and 350<=yy<=425,
                      ('open','cooperation'))]
            if self.host_button(action,x,y,buttons):return True
            if 770<=xx<=915 and 218<=yy<=258:command=('open','events')
            elif 935<=xx<=1020 and 95<=yy<=190:command=('open','tasks')
        if command:
            if action==1:self.pending_touch=command
            if action==3 and getattr(self,'pending_touch',None)==command:
                self.pending_touch=None;self.command(*command)
            return True
        return False
    def host_button(self,action,x,y,buttons):
        """buttons: (任务槽, 'cockpit'|'panel', 是否命中, 命令)。返回 True 表示已处理。"""
        current=getattr(self,'host_press',None)
        if action==1:
            self.release_host_press()
            for slot,kind,hit,command in buttons:
                if not hit:continue
                task=self.p.word(self.app+slot)
                self.host_press={'slot':slot,'kind':kind,'task':task,'command':command,'cancelled':False,
                                 'hits':{b[0]:b for b in buttons}}
                if kind=='cockpit':
                    from cockpit_hold import instance
                    instance(self.p).hold(task)
                else:
                    from probe import Probe
                    Probe.touch_event(self.p,1,x,y)
                return True
            return False
        if current is None:return False
        inside=any(slot==current['slot'] and hit for slot,_,hit,_ in buttons)
        if action==5:
            if current['cancelled']:return True
            if current['kind']=='panel':
                from probe import Probe
                Probe.touch_event(self.p,5,x,y)
            if not inside:
                current['cancelled']=True;self.release_host_press(keep=current)
            return True
        if action==3:
            activate=inside and not current['cancelled']
            if current['kind']=='panel' or not activate:self.release_host_press(keep=current)
            self.host_press=None
            if activate:
                from lab_ui import play_se,SE_DECIDE,SE_CLOSE
                command=current['command']
                play_se(self.p,SE_CLOSE if command in (('open','main_menu'),('close_shop',),('open','shop'),('open','medal_shop')) else SE_DECIDE)
                if command==('close_shop',):self.close_native_shop()
                else:self.command(*command)
            return True
        return True
    def release_host_press(self,keep=None):
        current=keep or getattr(self,'host_press',None)
        if not current:return
        task=current['task']
        if task and self.p.word(self.app+current['slot'])==task:
            if current['kind']=='cockpit':
                from cockpit_hold import instance
                instance(self.p).release(task)
            else:
                from probe import Probe
                Probe.touch_event(self.p,3,-1000,-1000)
                self.p.call('_ZN7AppMain16ClearSelectPanelEP17GENERAL_TASK_BASEi',self.app,task,0)
        if keep is None:self.host_press=None
    def world_event_touch(self,action,x,y):
        """世界地图 EVENT（底栏任务 app+0x3748，图号 131）：底栏按钮按下即由原生受理，故不送入原生触点；
        按下期间写入原生按压字段（+0x174）显示蓝光，释放在框内时打开浏览页（R01）。"""
        xx,yy=self.native_point(x,y);inside=480<=xx<=640 and yy>=525
        pressed=getattr(self,"event_press",None);task=self.p.word(self.app+0x3748)
        from cockpit_hold import instance
        hold=instance(self.p)
        if action==1:
            if not inside:return False
            self.event_press=[True,False]
            hold.hold(task)
            return True
        if not pressed:return False
        if action==5:
            if not inside and not pressed[1]:
                pressed[1]=True
                hold.release(task)
            return True
        if action==3:
            self.event_press=None
            if not inside or pressed[1]:hold.release(task)
            if inside and not pressed[1]:
                from lab_ui import play_se,SE_DECIDE
                play_se(self.p,SE_DECIDE);self.open('events')
            return True
        return True
    def command(self,name,*args):
        if name=='open':self.open(args[0])
        elif name=='select':self.select(args[0],enter=True)
        elif name=='battle':
            if not self.start_battle(args[0]):self.revision+=1
        elif name=='page':self.page=max(0,self.page+args[0]);self.revision+=1
        elif name=='buy':self.buy(args[0]);self.revision+=1
        elif name=='close':
            if self.overlay=='events' and not self.selected:self.overlay=None
            elif self.overlay=='events':self.leave()
            else:self.overlay=None;self.revision+=1
    def shop_rows(self):
        rows=self.data[self.selected].get('shop',{}).get('rows',[])
        phase=self.phases.part(self.selected,self.selected_phase)
        allowed=set(phase['shop_ids']) if phase else None
        return [r for r in rows if allowed is None or r['id'] in allowed]
    def has_shop(self):
        table=self.active_shop_table()
        return bool(table and table['count'] and table['catalog'] and table['records'])
    def buy(self,index):
        p=self.p;row=self.shop_rows()[index];state=self.state()
        if row['type']==2 and p.call('_ZN7AppMain20GetUnitLevelSaveDataE6UnitID',self.app,row['unit_id'])!=0xffffffff:
            self.last_message='此单位已获得';return False
        cost=row['event_currency_price']
        if state['currency']<cost:self.last_message='活动货币不足';return False
        if row['type'] not in (0,1,2,3):self.last_message='此商品类别尚未适配';return False
        if not self.native_shop_active:self.open_native_shop()
        p.call('_ZN7AppMain24SetSurvivalPointSaveDataEi',self.app,state['currency'])
        for panel_index in range(p.word(self.app+0xb898)):
            panel=p.word(self.app+0x3380+panel_index*4)
            if p.word(panel+0x224)==row['id']:
                p.put(self.app+0xb894,panel_index)
                return self.native_shop_purchase(row['id'])
        self.last_message='此商品当前无法购买';return False
    def draw(self):
        from PIL import Image,ImageDraw,ImageFont
        from trial_overlay import SurfaceOverlay
        if self.renderer is None:self.renderer=SurfaceOverlay(self.p.graphics)
        if not hasattr(self,'fonts'):
            path=Path(os.environ['SystemRoot'])/'Fonts/msjh.ttc'
            self.fonts={size:ImageFont.truetype(str(path),size) for size in (18,22,26,34)}
        page=self.overlay
        key=(page,self.selected,self.page,self.revision)
        if key!=getattr(self,'image_key',None):
            self.image_key=key;self.hitboxes=[]
            if page is None:
                image=Image.new('RGBA',(580,180),(13,22,26,255));draw=ImageDraw.Draw(image)
                title=next(e['title_zh'] for e in self.catalog if e['event_key']==self.selected)
                draw.text((16,12),title,font=self.fonts[22],fill='#f1e4b3')
                state=self.state();wins=sum(v.get('wins',0)>0 for v in state['stages'].values())
                draw.text((16,57),f"已通关 {wins} / {len(self.data[self.selected]['stages'])}",font=self.fonts[22],fill='white')
                draw.text((16,96),f"活动货币：{state['currency']}" if self.data[self.selected]['currency'] else '历史活动 · 单人关卡',font=self.fonts[22],fill='#bce9e5')
                draw.rectangle((410,120,566,166),fill='#353c32',outline='#b1b7a4',width=2)
                draw.text((421,133),'EVENT SELECT',font=self.fonts[18],fill='white')
                self.rect=(560,125,580,180)
            else:
                image=Image.new('RGBA',(1280,720),(14,23,27,255));draw=ImageDraw.Draw(image)
                for y in range(0,720,24):draw.line((0,y,1280,y),fill=(20,38,41),width=1)
                draw.rectangle((20,18,1260,92),fill='#293534',outline='#82928a',width=4)
                title={'events':'EVENT SELECT','stages':'STAGE SELECT','shop':'EVENT SHOP','tasks':'EVENT PROGRESS','cooperation':'COOPERATION','result':'BATTLE RESULT'}[page]
                draw.text((48,33),title,font=self.fonts[34],fill='white')
                draw.text((1240,43),'TEST',font=self.fonts[22],fill='#e2c677',anchor='ra')
                def button(rect,text,command,sub=None,red=False):
                    x,y,w,h=rect;draw.rectangle((x,y,x+w,y+h),fill='#752c22' if red else '#353c32',outline='#b1b7a4',width=3)
                    for px,py in ((x+8,y+8),(x+w-8,y+8),(x+8,y+h-8),(x+w-8,y+h-8)):draw.ellipse((px-3,py-3,px+3,py+3),fill='#9ba591')
                    draw.text((x+22,y+13),text,font=self.fonts[26],fill='white')
                    if sub:draw.text((x+22,y+50),sub,font=self.fonts[18],fill='#b9d8c8')
                    self.hitboxes.append((rect,command))
                if page=='events':
                    for i,e in enumerate(self.catalog):
                        row,col=divmod(i,2)
                        button((45+col*615,115+row*101,575,88),e['title_zh'],('select',e['event_key']),f"{e['stage_count']} STAGES")
                elif page=='stages':
                    rows=self.data[self.selected]['stages'];count=(len(rows)+9)//10
                    draw.text((45,110),next(e['title_zh'] for e in self.catalog if e['event_key']==self.selected),font=self.fonts[22],fill='#e2c677')
                    for slot,s in enumerate(rows[self.page*10:self.page*10+10]):
                        row,col=divmod(slot,2);index=self.page*10+slot
                        won=self.state()['stages'].get(s['local_stage_key'],{}).get('wins',0)>0
                        button((45+col*615,150+row*88,575,76),f"STAGE {index+1:02}  {'CLEAR' if won else ''}",('battle',index),f"ID {s['id']}    体力 {s['stamina_cost']}")
                    if self.page>0:button((280,625,210,62),'PREVIOUS',('page',-1))
                    if self.page<count-1:button((760,625,210,62),'NEXT',('page',1))
                elif page=='shop':
                    rows=self.shop_rows();count=(len(rows)+7)//8
                    draw.text((45,108),f"活动货币：{self.state()['currency']}",font=self.fonts[22],fill='#e2c677')
                    for slot,r in enumerate(rows[self.page*8:self.page*8+8]):
                        row,col=divmod(slot,2);index=self.page*8+slot
                        if r['type']==2:
                            uid=r['unit_id'];ptr=self.p.call('_Z15GetMenuUnitName6UnitIDi',uid,self.p.word(self.app+0x3d64));name=self.p.string(ptr)
                            owned=self.p.call('_ZN7AppMain20GetUnitLevelSaveDataE6UnitID',self.app,uid)!=0xffffffff
                        else:
                            owned=False;ptr=self.p.call('_Z16GetEventItemName10MenuShopIDi',r['id'],self.p.word(self.app+0x3d64));name=self.p.string(ptr)
                            if not name:name=f"ITEM {r['unit_id']} × {r['quantity']}"
                        button((45+col*615,148+row*112,575,100),name[:30],('buy',index),f"价格 {r['event_currency_price']}   {'已获得' if owned else 'BUY'}")
                    if not rows:draw.text((90,245),'此活动的历史专属兑换配置仍在核查。',font=self.fonts[26],fill='white')
                    if self.page>0:button((280,625,210,62),'PREVIOUS',('page',-1))
                    if self.page<count-1:button((760,625,210,62),'NEXT',('page',1))
                elif page=='result':
                    draw.text((640,235),'MISSION COMPLETE' if self.result['won'] else 'MISSION FAILED',font=self.fonts[34],fill='#f0dc87',anchor='mm')
                    draw.text((640,330),f"关卡 {self.result['stage_id']}    获得 {self.result['earned']}",font=self.fonts[26],fill='white',anchor='mm')
                    button((410,450,460,90),'RETURN TO BASE',('close',))
                elif page=='tasks':
                    wins=sum(v.get('wins',0)>0 for v in self.state()['stages'].values())
                    draw.text((90,230),f"已通关 {wins} / {len(self.data[self.selected]['stages'])}",font=self.fonts[34],fill='white')
                    draw.text((90,310),'捕虏、零件及限时任务奖励正在适配。',font=self.fonts[26],fill='#e2c677')
                elif page=='cooperation':
                    draw.text((90,230),'当前版本支持全部已登记活动的单人战斗。',font=self.fonts[26],fill='white')
                    draw.text((90,305),'原版在线合作服务尚未恢复。',font=self.fonts[26],fill='#e2c677')
                button((45,625,210,62),'BACK',('close',))
                if self.last_message:draw.text((640,605),self.last_message,font=self.fonts[22],fill='#ffd385',anchor='mm')
                self.rect=(0,0,1280,720)
            self.image=image
        self.renderer.draw_image(self.image,key,self.rect)
    def close(self):
        self.flush()
        if self.renderer:self.renderer.close()
