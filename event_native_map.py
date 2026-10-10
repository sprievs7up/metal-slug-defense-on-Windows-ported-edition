"""Historical map metadata with bounded markers and isolated Event results."""
import json,struct
HEADER=0x1ffed000
# 原生 1.46 EventMSD 场景（158–162）按 c8c8 模式分派战斗：模式 3 为经典活动
# （关卡 ID 30000+1000w+10(a+1)+s+1），模式 4 为猫咪联动（40000+1000(w+1)+…），
# 模式 5 为 Survival 类活动（60000+1000(w+1)+…，BattleInit_SurvivalMode）。
# WorldType 决定原生底栏：3 为 Survival 商店，4 为合作基地，2 为猫咪地图布局，其余为通常底栏。
# 经典活动保留原生世界号（30xxx–33xxx 为世界 0–3）；1.46 的 WorldType 2 专用于猫咪地图，
# 经典活动使用 WorldType 1，EventAreaCheck 由钩子放行。CreatePrisonerTask 以世界 3 绘制巨灵战车零件、以世界 2 绘制
# 盛夏恐怖夜专用画面。万圣节与黑色诺亚原属其他世界，分配不触发专用画面的世界 4、5。
CLASSIC_WORLD={'halloween_2015':4,'kof_black_noah_2016':5}
def eventmsd_route(key,controller,first_stage_id=0):
    if key=='battle_cats_2015':return {'mode':4,'world_type':2,'base':40000,'world_offset':1,'world_shift':0}
    if key=='cooperation_2016_current' or controller=='current_cooperation':return {'mode':6,'world_type':4,'base':60000,'world_offset':1,'world_shift':0}
    if controller=='legacy_survival':
        route={'mode':5,'world_type':3,'base':60000,'world_offset':1,'world_shift':0}
        if key=='treasure_recovery_2015':route['base_position']=(300,200)
        return route
    world=CLASSIC_WORLD.get(key,(first_stage_id-30000)//1000 if 30000<=first_stage_id<34000 else 4)
    return {'mode':3,'world_type':1,'base':30000,'world_offset':0,'world_shift':world}
class NativeEventMap:
    def __init__(self,trial):
        self.t=trial;self.p=trial.p;self.tables={};self.active=False
        p=self.p
        manifest=json.loads((trial.root/'historical_events/native_maps.json').read_text(encoding='utf-8'));self.manifest=manifest
        # 自制 EVENT（event_content.compile_event）的地图清单；区域名按当前语言写入（enable）。
        manifest['events'].update(getattr(trial,'custom_maps',{}))
        self.routes={};self.view_manifests={};views=[]
        for key,data in manifest['events'].items():
            views.append((key,key,None,data))
            family=trial.phases.families.get(key)
            if family:
                for phase_id in family['parts']:
                    views.append(((key,phase_id),key,phase_id,trial.phases.map_view(key,phase_id,data)))
        for table_key,key,phase_id,data in views:
            self.view_manifests[table_key]=data
            mission_table=trial.mission_table(key,phase_id)
            route=self.routes[key]=eventmsd_route(key,trial.data[key]['controller'],trial.data[key]['stages'][0]['id'])
            shift=route['world_shift']
            records=[];indices=[];world_indices=[];names=[];worlds=[];by_index={}
            title=key.replace('_2015','').replace('_2016_current','').replace('_2016','').replace('_',' ').upper()
            worlds=[struct.pack('<3I',0,0,0)]*shift
            for local_world in range(data['world_count']):
                world=local_world+shift;area_ptrs=[]
                for area in (a for a in data['areas'] if a['world']==local_world):
                    a=area['area'];items=area['markers'];raw=bytearray.fromhex(area['raw_hex'])
                    if not 0<len(items)<=5:raise ValueError('Invalid Event marker count')
                    for slot in range(5):
                        pointer=0
                        if slot<len(items):
                            marker=items[slot];index=marker['index'];s=trial.data[key]['stages'][index]
                            virtual=route['base']+(world+route['world_offset'])*1000+(a+1)*10+slot+1
                            menu=bytearray(p.read(mission_table['missions']+index*120,120));struct.pack_into('<I',menu,0,virtual)
                            marker_raw=bytes.fromhex(marker['raw_hex'])
                            if len(marker_raw)!=24 or marker['preview_frame']>32:raise ValueError('Invalid Event marker')
                            pointer=trial.blob(marker_raw)
                            # 自制 EVENT 的邀请函（无区域奖励的俘虏）同样计入上限，救出数按上限保存（M6b-3）。
                            maximum=marker['pow_max'] if area['prisoner_id']>=0 or data.get('custom') else 0
                            records.append(struct.pack('<16I',virtual,s['id'],trial.blob(bytes(menu)),0,0,a,slot,index,world,marker['bgm_id'],maximum,0,*([0]*4)))
                            indices.append((a,slot,index));world_indices.append((world,a,slot,index));by_index[index]=marker
                            names.append(trial.blob((f'{title} / {local_world+1}-{a+1}').encode()+b'\0') if 'names' not in area else area['names'])
                        struct.pack_into('<I',raw,20+slot*4,pointer)
                    area_ptrs.append(trial.blob(bytes(raw)))
                if len(area_ptrs)>16:raise ValueError('Event world exceeds original area capacity')
                worlds.append(struct.pack('<3I',trial.blob(struct.pack('<'+'I'*len(area_ptrs),*area_ptrs)),len(area_ptrs),0))
            prisoners=[]
            for pid,reward in data['prisoners'].items():
                text_arrays=[]
                for field in ('names','info1','info2'):
                    text_arrays.append(trial.blob(struct.pack('<11I',*[trial.blob(text.encode('utf-8')+b'\0') for text in reward[field]])))
                prisoners.append(struct.pack('<5I',int(pid),trial.blob(bytes.fromhex(reward['raw_hex'])),*text_arrays))
            localized=any(isinstance(n,dict) for n in names)
            self.tables[table_key]={'worlds':trial.blob(b''.join(worlds)),'world_count':len(worlds),'localized_names':names if localized else None,
                              'area_count':len(data['areas']),'records':trial.blob(b''.join(records)),
                              'count':len(records),'indices':indices,'world_indices':world_indices,'by_index':by_index,
                              'names':0 if localized else trial.blob(struct.pack('<'+'I'*len(names),*names)),
                              'prisoners':trial.blob(b''.join(prisoners)),'prisoner_count':len(prisoners)}
        table=p.symbols['MenuImageDataTbl'];locale=p.word(p.app_instance()+0x3d64)
        self.cat_descriptor=p.word(table+locale*4)+64*12
        self.cat_draw_task=trial.blob(b'\0'*(3*0x228))
    def active_table(self):
        key=(self.t.selected,self.t.selected_phase) if self.t.selected_phase is not None else self.t.selected
        return self.tables[key]
    def active_manifest(self):
        key=(self.t.selected,self.t.selected_phase) if self.t.selected_phase is not None else self.t.selected
        return self.view_manifests[key]
    def localized_names(self,table):
        """自制 EVENT 的区域名（每个小关记录一项，取所在区域的名称）按当前游戏语言建表并缓存。"""
        import content_locale
        code=content_locale.current_code(self.p);cache=table.setdefault('names_by_language',{})
        if code not in cache:
            texts=[self.t.blob(n[code].encode('utf-8')+b'\0') for n in table['localized_names']]
            cache[code]=self.t.blob(struct.pack('<'+'I'*len(texts),*texts))
        return cache[code]
    def enable(self):
        t=self.t;p=self.p;table=self.active_table();state=t.state();self.active=True
        if table.get('localized_names'):table['names']=self.localized_names(table)
        route=self.routes[t.selected]
        for off,value in ((72,route['world_type']),(76,route['mode']),(84,1),(192,route['world_shift'])):p.put(HEADER+off,value)
        position=route.get('base_position')
        for off,value in ((204,position[0] if position else 0),(208,position[1] if position else 0)):
            p.put(HEADER+off,struct.unpack('<I',struct.pack('<f',float(value)))[0])
        p.put(HEADER+212,int(position is not None))
        p.put(HEADER+80,0);p.put(HEADER+36,t.app);bonuses=[]
        for world_type in (0,1):
            for world in range(3):
                for area in range(p.call('_Z10GetAreaNumi9WorldType',world,world_type)):
                    rate=p.call('_Z19GetAreaPrisonerRateii9WorldType',world,area,world_type)
                    bonuses.append(struct.pack('<4I',world,area,world_type,rate))
        p.put(HEADER+140,t.blob(b''.join(bonuses)));p.put(HEADER+144,len(bonuses))
        for i,(_,_,index) in enumerate(table['indices']):
            saved=state['stages'].get(t.data[t.selected]['stages'][index]['local_stage_key'],{})
            p.put(table['records']+i*64+12,int(saved.get('wins',0)>0));p.put(table['records']+i*64+16,saved.get('best_time',0))
            maximum=p.word(table['records']+i*64+40)
            p.put(table['records']+i*64+44,min(maximum,max(0,saved.get('captures',0))))
        for off,value in ((80,1),(88,table['area_count']),(92,table['records']),(96,table['count']),(100,table['names']),
                          (108,int(t.data[t.selected]['controller'] in ('legacy_survival','current_cooperation'))),(112,0),
                          (148,table['world_count']),(152,table['worlds']),(156,int(t.selected=='battle_cats_2015')),(164,0),
                          (168,table['prisoners']),(172,table['prisoner_count']),(176,int(self.has_prisoners(0))),
                          (180,0),(184,int(t.data[t.selected]['controller']=='parts')),(196,self.cat_draw_task)):
            p.put(HEADER+off,value)
    def has_prisoners(self,world):
        return any(a['world']==world and a['prisoner_id']>=0 and any(m['pow_max'] for m in a['markers'])
                   for a in self.active_manifest()['areas'])
    def disable(self):
        for off in (72,76,80,84,164,192,204,208,212):self.p.put(HEADER+off,0)
        self.active=False
    def open(self,immediate=False):
        t=self.t
        if not immediate:return t.transition(lambda:self.open(True))
        p=self.p;app=t.app;self.enable();t.overlay=None
        p.call('_ZN7AppMain12SceneEndFuncEi',app,p.word(app+0x22bc))
        for off in (0xb1ec,0xb1f0,0xb1f4):p.put(app+off,0)
        p.put(app+0xc030,0);p.put(app+0xc034,0);p.call('_ZN7AppMain11ChangeExeSTEi',app,158)
        p.log('HISTORICAL_NATIVE_MAP',t.selected,self.active_table()['area_count'])
    def update(self):
        t=self.t;p=self.p;app=t.app;pending=p.word(HEADER+112)
        # 自制地图图层与缩略图（M6b-2，event_content.MapArt）。
        if not hasattr(self,'art'):
            import event_content;self.art=event_content.MapArt(t)
        self.art.update()
        if self.active and not t.active_battle:
            p.put(HEADER+176,int(self.has_prisoners(p.word(app+0xc624)-self.routes[t.selected]['world_shift'] if p.word(HEADER+84) else p.word(app+0xb1ec))))
            if p.word(HEADER+180):
                p.put(HEADER+180,0);p.call('_ZN7AppMain12SceneEndFuncEi',app,p.word(app+0x22bc))
                p.call('_ZN7AppMain11ChangeExeSTEi',app,32)
        if pending:
            p.put(HEADER+112,0);index=pending-1;s=t.data[t.selected]['stages'][index]
            t.active_battle={'index':index,'stage':s,'key':t.selected,'native_map':True}
            p.call('_ZN7AppMain10Sound_LoadE7SoundID',app,self.active_table()['by_index'][index]['bgm_id'])
            p.call('_ZN7AppMain20Sound_RequestPlayBGME7SoundIDi',app,self.active_table()['by_index'][index]['bgm_id'],0)
            legacy=bool(p.word(HEADER+108))
            if not p.word(HEADER+84):p.put(app+0xc8c8,5 if legacy else 3);p.put(app+0xc63c,3 if legacy else 1)
            if legacy and not p.word(HEADER+84):
                ex=p.call('_ZN10BattleInfo17getExSurvivalInfoEi',t.info,s['id']);p.put(app+0xb9a4,p.word(ex+8))
            p.log('HISTORICAL_NATIVE_MAP_BATTLE',t.selected,s['id'])
    def save_result(self,record,won,time):
        t=self.t;p=self.p;table=self.active_table();saved=t.state()['stages'][record['stage']['local_stage_key']]
        if won:saved['best_time']=min(saved.get('best_time') or time,time)
        for i,(world,a,slot,index) in enumerate(table['world_indices']):
            if index==record['index']:
                p.put(table['records']+i*64+12,int(saved['wins']>0));p.put(table['records']+i*64+16,saved.get('best_time',0))
                maximum=p.word(table['records']+i*64+40)
                saved['captures']=min(maximum,max(0,saved.get('captures',0)))
                p.put(table['records']+i*64+44,saved['captures'])
                wt=self.routes[t.selected]['world_type'] if p.word(HEADER+84) else 0
                return p.call('_Z12GetStageRankiii9WorldType',world,a,slot,wt)
        raise ValueError('Historical stage absent from native map')
    def back(self,immediate=False):
        t=self.t
        if not immediate:return t.transition(lambda:self.back(True))
        p=self.p;p.call('_ZN7AppMain12SceneEndFuncEi',t.app,p.word(t.app+0x22bc))
        p.put(t.app+0xc63c,4);p.put(t.app+0xc8c8,6);p.call('_ZN7AppMain23SC_WiFiMenuInit_TagTeamEv',t.app)
