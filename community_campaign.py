"""扩展世界入口、原生战斗适配及稳定内容键进度。"""
from pathlib import Path
import json,struct,base64,contextlib,io
from event_trial import HEADER,MAGIC,atomic_bytes
from content_panel import Panel

EXT=0x1ffec000
EXT_MAGIC=0x45585431
MUSIC_SLOT=1031
SAVE_FILES=('test.dat','community_progress.json','campaign_progress.json')

def recover(saves):
    path=Path(saves)/'campaign_transaction.json'
    if not path.exists():return
    record=json.loads(path.read_text(encoding='utf-8'))
    if record.get('schema')!=1 or set(record['files'])!=set(SAVE_FILES):raise ValueError('未知扩展进度事务')
    for name,raw in record['files'].items():
        target=Path(saves)/name
        if raw is None:target.unlink(missing_ok=True)
        else:atomic_bytes(target,base64.b64decode(raw,validate=True))
    path.unlink()

class CommunityCampaign:
    def __init__(self,p,trial,*,ui_enabled=False):
        self.p=p;self.trial=trial;self.content=p.community;self.catalog=self.content.campaign_catalog
        # 未完成的选择界面默认停用；独立开发预览可显式启用。
        self.ui_enabled=ui_enabled
        self.path=p.saves/'campaign_progress.json'
        self.progress=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'schema':1,'stages':{}}
        if self.progress.get('schema')!=1:raise ValueError('未知扩展世界存档版本')
        self.panel=Panel(p);self.opened=False;self.page=0;self.world=None;self.area=None;self.active=False;self.message='';self.music_key=None
        self.scene_ids={s['key']:s['id'] for s in self.content.manifest.get('stages',[])}
        self.allocated=[];self.visible=False;self.original_filecall=p.filecall
        p.filecall=self.filecall
        if not hasattr(p.uc.lib,'msd_content_interface_version') or p.uc.lib.msd_content_interface_version()!=1:
            raise RuntimeError('扩展接口需要与宿主匹配的原生核心')
        p.put(EXT,EXT_MAGIC)
    def filecall(self,name,args):
        if name in ('fopen','fopen64'):
            leaf=Path(self.p.string(args[0])).name
            if leaf in self.catalog.assets and leaf.endswith('.msdf'):
                mode=self.p.string(args[1])
                if mode not in ('rb','r'):return 0
                handle=self.p.alloc(16);self.p.handles[handle]=io.BytesIO(self.catalog.assets[leaf]);return handle
        return self.original_filecall(name,args)
    def unlocked(self,item):
        return all(self.progress['stages'].get(key,{}).get('wins',0)>0 for key in item.get('requires',[]))
    def lab_open(self):
        """LAB 准备界面打开或 LAB 战斗进行中（准备界面保持其 BGM 135，并使用隔离存档）。"""
        lab=getattr(self.p,'lab',None)
        return lab is not None and (getattr(lab,'active',False) or getattr(getattr(lab,'prep',None),'open',False))
    def open(self):
        if not self.ui_enabled:return False
        if self.lab_open():return False
        if self.trial.active_battle:return False
        if self.p.word(self.p.app_instance()+0x22bc) not in (28,31,34,67):return False
        if self.trial.selected:
            self.clear_music();self.trial.leave(True);self.clear_runtime()
        self.opened=True;self.active=False;self.world=None;self.area=None;self.page=0;self.message='';return True
    def rows(self):
        if self.world is None:return list(self.catalog.worlds.values())
        world=self.catalog.worlds[self.world]
        if self.area is None:return world.get('areas',[])
        return next(a for a in world['areas'] if a['key']==self.area)['stages']
    def update(self):
        p=self.p;app=p.app_instance()
        self.visible=False
        if self.active and not self.trial.selected:
            self.active=False;self.clear_music();self.clear_runtime()
        if self.active and self.trial.overlay=='result':
            self.trial.overlay=None;self.opened=True;self.message='通关完成' if self.trial.result['won'] else '本次挑战未完成'
        if not self.ui_enabled:
            self.opened=False;self.panel.boxes=[];return
        if self.opened:
            self.visible=True
            rows=self.rows();page=rows[self.page*10:self.page*10+10];buttons=[]
            for item in page:
                clear=self.progress['stages'].get(item['key'],{}).get('wins',0)>0
                label=item['title']+(' · 已通关' if clear else '')+(' · 未解锁' if not self.unlocked(item) else '')
                buttons.append((label,('choose',item['key'])))
            if not buttons:buttons=[('当前暂无已安装扩展关卡',None)]
            title='扩展世界' if self.world is None else self.catalog.worlds[self.world]['title']
            if self.message:title+=' · '+self.message
            foot=[('返回',('back',))]
            if self.page:foot.append(('上一页',('page',-1)))
            if (self.page+1)*10<len(rows):foot.append(('下一页',('page',1)))
            self.panel.draw(title,buttons,foot,key=(self.world,self.area,self.page))
        elif not self.trial.active_battle and not self.trial.overlay and not p.word(EXT+8) and p.word(app+0x22bc) in (28,31,34,67):
            self.visible=True
            # 入口置于既有菜单内，关闭面板后继续使用原生界面。
            self.panel.draw('扩展世界',[],[('进入',('open',))],rect=(995,100,280,150))
        else:self.panel.boxes=[]
    def touch(self,action,x,y):
        if not self.ui_enabled or not self.visible:return False
        command=self.panel.hit(x,y)
        if not self.opened and (self.trial.active_battle or self.p.word(EXT+8) or self.trial.overlay):return False
        if not self.opened and not command:return False
        if action==1:return True
        if action!=3:return True
        if command:
            op=command[0]
            if op=='open':self.open()
            elif op=='page':self.page+=command[1]
            elif op=='back':
                if self.area is not None:self.area=None
                elif self.world is not None:self.world=None
                else:
                    self.opened=False
                    if self.active:
                        self.clear_music();self.trial.leave(True);self.active=False;self.clear_runtime()
                self.page=0
            elif op=='choose':
                item=next(r for r in self.rows() if r['key']==command[1])
                if not self.unlocked(item):self.message='通关条件尚未满足'
                elif self.world is None:self.world=item['key'];self.page=0
                elif self.area is None:self.area=item['key'];self.page=0
                else:self.start(item['key'])
        return True
    def blob(self,raw):
        ptr=self.p.alloc(len(raw));self.p.write(ptr,raw);self.allocated.append(ptr);return ptr
    def clear_runtime(self):
        self.p.put(EXT+12,0);self.p.put(EXT+16,0)
        for ptr in self.allocated:self.p.free(ptr)
        self.allocated=[]
    def clear_music(self):
        p=self.p;app=p.app_instance()
        p.call('_ZN7AppMain13Sound_StopBGMEv',app)
        if self.music_key is not None:
            counter=app+0xab54+MUSIC_SLOT
            if p.read(counter,1)[0]>64:raise RuntimeError('独立音乐槽引用计数超出原生释放范围')
            while p.read(counter,1)[0]:p.call('_ZN7AppMain13Sound_ReleaseE7SoundID',app,MUSIC_SLOT)
            # 原生释放流程保留缓存指针；独立音乐槽在释放后清除该指针。
            p.put(app+0x9b30+MUSIC_SLOT*4,0)
        p.put(EXT+4,0);self.music_key=None
    def prepare_world(self,key):
        p=self.p;t=self.trial;self.clear_runtime();world=self.catalog.worlds[key];records=[];stages=[];bgm={}
        for index,s in enumerate(stage for a in world['areas'] for stage in a['stages']):
            source=p.call('_ZN10BattleInfo14getMissionInfoEi',t.info,s.get('template',1011))
            if not source:raise ValueError('原生关卡模板不存在')
            words=list(struct.unpack('<30I',p.read(source,120)));words[0]=1000000+index
            words[1]=s['scene'] if type(s['scene']) is int else self.scene_ids[s['scene']]
            words[4]=s.get('enemy_base_hp',10000);words[6]=s.get('reward_msp',0);words[8]=s.get('stamina',0)
            words[16]=struct.unpack('<I',struct.pack('<f',float(s.get('strength_steps',0))))[0]
            enemies=[(i,self.catalog.unit_id(e['unit']),e.get('level',40)) for i,e in enumerate(s['enemies'])]
            words[17]=self.blob(b''.join(struct.pack('<3i',*e) for e in enemies));words[18]=len(enemies)
            waves=s.get('waves',[])
            words[19]=self.blob(b''.join(struct.pack('<hbb',w['tick'],w['enemy'],0) for w in waves)+struct.pack('<hbb',-1,0,0));words[20]=len(waves)
            for off in (21,22,23,24,28,29):words[off]=0
            records.append(struct.pack('<30I',*words))
            stage=dict(s,id=words[0],group=0,local_stage_key=s['key'],stamina_cost=words[8]);stages.append(stage)
            music=s.get('music',100)
            # 音效键（M6，类型 bgm）使用分配的 SoundID；世界目录的音乐使用扩展音乐槽 1031。
            bgm[index]={'bgm_id':music if type(music) is int else self.content.sound_ids.get(music,MUSIC_SLOT)}
        table=self.blob(b''.join(records));p.put(EXT+12,table);p.put(EXT+16,len(stages))
        p.write(t.groups,struct.pack('<II',table,len(stages)))
        event_key='campaign.'+key
        t.data[event_key]={'stages':stages,'controller':'stage_clear','currency':None}
        t.tables[event_key]={'missions':table,'count':len(stages)}
        t.native_map.tables[event_key]={'by_index':bgm}
        return event_key
    def set_music(self,key):
        p=self.p;app=p.app_instance()
        if type(key) is int or key in self.content.sound_ids:return
        music=self.catalog.music[key]
        if p.call('_ZN7AppMain12GetSoundDataE7SoundID',app,MUSIC_SLOT):raise RuntimeError('扩展音乐槽与原生资源冲突')
        source=p.call('_ZN7AppMain12GetSoundDataE7SoundID',app,music.get('base_sound_id',100))
        if not source:raise ValueError('音乐模板不存在')
        raw=bytearray(p.read(source,24))
        filename=self.blob(music['file'].encode()+b'\0')
        struct.pack_into('<I',raw,0,filename);struct.pack_into('<I',raw,16,MUSIC_SLOT)
        struct.pack_into('<ff',raw,4,float(music.get('loop_start',0)),float(music.get('loop_end',0)))
        p.put(EXT+4,self.blob(bytes(raw)));self.music_key=key
    def start(self,key):
        if self.lab_open():return False
        stage=self.catalog.stages[key];world=self.catalog.locations[key][0]
        if not self.unlocked(stage) or not self.unlocked(self.catalog.worlds[world]):return False
        area_key=self.catalog.locations[key][1]
        if not self.unlocked(self.catalog.areas[area_key]):return False
        p=self.p;t=self.trial;t.app=p.app_instance()
        if p.call('_ZN7AppMain18GetStaminaSaveDataEv',t.app)<stage.get('stamina',0):self.message='体力不足';return False
        t.reset_event_context();self.clear_music();event_key=self.prepare_world(world)
        self.set_music(stage.get('music',100));t.selected=event_key
        p.put(HEADER,MAGIC);p.put(HEADER+4,0)
        p.put(EXT+20,int(stage.get('enemy_specials',True)))
        index=next(i for i,s in enumerate(t.data[event_key]['stages']) if s['key']==key)
        self.active=True;self.opened=False;started=t.start_battle(index)
        if started:
            controller=p.call('_ZN10BattleMain18getEnemyControllerEv',p.word(t.app+0xc220))
            # 启用原生敌军决策，并应用关卡的绝招策略。
            p.call('_ZN21BattleControllerEnemy14setEnemyActiveEb',controller,1)
            p.call('_ZN21BattleControllerEnemy16setEnemySpAttackEb',controller,int(stage.get('enemy_specials',True)))
        return started
    def finish(self):
        p=self.p;t=self.trial;app=t.app;record=t.active_battle;stage=record['stage'];battle=p.word(app+0xc220)
        won=bool(p.read(battle+0x1c,1)[0]);ticks=p.word(battle+0x48)
        earned=max(0,p.call('_ZN10BattleMain13getGetMSPointEv',battle))
        if not won:earned=max(0,earned-p.call('_ZN10BattleMain14getGetMSPoint2Ev',battle))
        prisoners=p.call('_ZN10BattleMain14getGetPrisonerEv',battle) if won else 0
        files={name:base64.b64encode((p.saves/name).read_bytes()).decode() if (p.saves/name).exists() else None for name in SAVE_FILES}
        journal=p.saves/'campaign_transaction.json';atomic_bytes(journal,json.dumps({'schema':1,'files':files}).encode())
        previous=json.loads(json.dumps(self.progress));ram=p.read(app+0x3d08,0x5ab0);community=json.loads(json.dumps(self.content.progress))
        records=p.read(self.content.records,len(self.content.units)*0x90)
        from community_content import HEADER as CONTENT_HEADER
        previous_dirty=p.word(CONTENT_HEADER+24)
        try:
            saved=self.progress['stages'].setdefault(stage['key'],{'attempts':0,'wins':0,'captures':0,'rank':0})
            saved['attempts']+=1;saved['wins']+=int(won);saved['captures']+=prisoners
            if won:
                saved['best_ticks']=min(saved.get('best_ticks',ticks),ticks)
                # 评级以原生关卡阈值为依据。
                mission=p.word(EXT+12)+record['index']*120
                thresholds=struct.unpack('<5I',p.read(mission+44,20))
                saved['rank']=max(saved['rank'],sum(ticks<=v for v in thresholds if v))
                if not saved.get('unit_rewards_claimed',False):
                    for unit in stage.get('reward_units',[]):
                        uid=self.catalog.unit_id(unit)
                        if p.call('_ZN7AppMain20GetUnitLevelSaveDataE6UnitID',app,uid)==0xffffffff:
                            p.call('_ZN7AppMain20SetUnitLevelSaveDataE6UnitIDi',app,uid,0)
                            p.call('_ZN7AppMain24SetUnitLevelOpenSaveDataE6UnitIDi',app,uid,20)
                    saved['unit_rewards_claimed']=True
            p.call('_ZN7AppMain18AddMSPointSaveDataEi',app,earned)
            p.call('_ZN7AppMain26SetContinueStageIDSaveDataEi',app,0)
            p.call('_ZN7AppMain20WriteMainSaveDataExeEv',app)
            if not p.call('_ZN7AppMain18SaveDataWriteCheckEv',app):raise RuntimeError('原生存档写入核验失败')
            self.content.flush()
            atomic_bytes(self.path,json.dumps(self.progress,ensure_ascii=False,indent=2).encode());journal.unlink()
        except Exception:
            self.progress=previous;self.content.progress=community;p.write(app+0x3d08,ram);p.write(self.content.records,records)
            p.put(CONTENT_HEADER+24,previous_dirty);recover(p.saves);raise
        p.put(HEADER,0);p.put(HEADER+4,0);p.put(app+0xc8c8,7)
        p.call('_ZN7AppMain12SC_BattleEndEv',app);p.call('_ZN7AppMain25BattleEnd_ClearBattleMainEv',app)
        t.active_battle=None;t.result={'won':won,'earned':earned,'stage_id':stage['id']};t.overlay=None
        p.put(app+0xc63c,4);p.put(app+0xc8c8,6)
        p.call('_ZN7AppMain23SC_WiFiMenuInit_TagTeamEv',app)
        p.put(HEADER,MAGIC);self.opened=True;self.message='通关完成' if won else '本次挑战未完成'
        p.log('COMMUNITY_CAMPAIGN_RESULT',stage['key'],won,earned,ticks)
    def close(self):
        self.panel.close();self.p.filecall=self.original_filecall
