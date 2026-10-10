"""世界、区域、战场与敌军配置的版本化内容契约。

内容来源（模组 M5）：本体目录 campaign_content/catalog.json，加上各已载入模组的 campaign/*.json 片段（按加载顺序合并）。
- 模组片段不写 assets；场景图集与音乐取自模组 assets/（文件名以 "<模组 id>_" 开头），也可引用本体与所依赖模组的资源。
- 模组定义的键（世界、区域、关卡、场景、音乐）须以 "<模组 id>." 开头。
- 引用（场景、音乐、敌军与奖励单位、解锁条件）只能指向本体、本模组与所依赖模组的内容；原版场景、音乐与单位以整数引用。
- 进度按关卡稳定键保存于 campaign_progress.json；停用模组后其进度保留。
"""
from pathlib import Path
import json,re,struct,math
from content_digest import DigestCache,blake2

def stable_key(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-zA-Z0-9_.-]{1,120}',value):
        raise ValueError('内容键仅允许字母、数字、下划线、点和连字符')
    return value

def integer(value,low,high):
    if type(value) is not int or not low<=value<=high:raise ValueError('整数配置超出范围')
    return value

class Catalog:
    def __init__(self,root,units,mods=(),cache=None,sounds=None):
        """root：本体目录；units：单位列表（key、id）；mods：已载入模组的片段 {'owner','raw','assets'（名→路径）,'visible'}。
        cache：资源路径 → 字节（重复校验时复用读取结果）。
        sounds：已登记音效键 → 类型（M6）；关卡 music 可写类型为 bgm 的音效键（可见范围同单位）。"""
        self.sounds=dict(sounds or {})
        self.root=Path(root);self.path=self.root/'catalog.json'
        body=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'schema':1,'assets':{},'scenes':[],'music':[],'worlds':[]}
        if body.get('schema')!=1:raise ValueError('未知世界目录版本')
        self.units={u['key']:u['id'] for u in units};self.assets={};self.keys=set(self.units)
        self.owner={};self.asset_owner={};cache={} if cache is None else cache
        def read(path):
            if path not in cache:cache[path]=Path(path).read_bytes()
            return cache[path]
        digests=DigestCache()
        for name,digest in body.get('assets',{}).items():
            if Path(name).name!=name or '\\' in name or name in ('.','..'):raise ValueError('资源要求独立文件名')
            if Path(name).suffix not in ('.obm','.msdf'):raise ValueError('运行资源要求 .obm 或 .msdf 文件')
            path=self.root/name;raw=read(path)
            if digest is not None and digests.digest(path,raw)!=digest:raise ValueError('资源校验值不一致：'+name)
            self.add_asset(name,raw,'body')
        digests.save()
        fragments=[{'owner':'body','raw':body,'visible':{'body'}}]
        for mod in mods:
            raw=mod['raw'];owner=mod['owner']
            if 'assets' in raw:raise ValueError(owner+'：模组片段的资源放在 assets/，不写 assets 字段')
            visible=set(mod['visible'])|{'body',owner}
            for row in (*raw.get('scenes',[]),*raw.get('music',[])):
                name=row.get('texture') if 'texture' in row else row.get('file')
                if isinstance(name,str) and name in mod['assets'] and name not in self.asset_owner:
                    if Path(name).suffix not in ('.obm','.msdf'):raise ValueError('运行资源要求 .obm 或 .msdf 文件')
                    self.add_asset(name,read(mod['assets'][name]),owner)
            fragments.append({'owner':owner,'raw':raw,'visible':visible})
        if sum(map(len,self.assets.values()))>512*1024*1024:raise ValueError('目录资源合计超过 512 MiB')
        self.raw=body if len(fragments)==1 else {'schema':1,'body':body,'mods':[{'id':f['owner'],'campaign':f['raw']} for f in fragments[1:]]}
        self.scenes={};self.music={};self.worlds={};self.visible={f['owner']:f['visible'] for f in fragments}
        for f in fragments:
            self.fragment=f
            for name in ('scenes','music','worlds'):getattr(self,name).update(self.index(name))
        if len(self.scenes)>4096:raise ValueError('当前场景容量为 4096')
        for scene in self.scenes.values():
            self.enter(scene)
            integer(scene.get('base_id',0),0,137)
            if scene.get('texture') not in self.assets or not scene['texture'].endswith('.obm'):raise ValueError('场景缺少已登记 OBM')
            self.see_asset(scene['texture'])
            raw=self.assets[scene['texture']]
            if len(raw)<8 or raw[:2]!=b'OI':raise ValueError('无效场景图集')
            w,h=struct.unpack_from('<HH',raw,4);kind,bits=raw[2:4]
            if kind==1 and bits==4:expected=72+(w*h+1)//2
            elif kind in (1,4) and bits==8:expected=8+(1024 if kind==1 else 512)+w*h
            elif kind in (0,1) and bits in (24,32):expected=8+w*h*(3 if kind==0 else 4)
            else:raise ValueError('无效 OBM 格式')
            if not 0<w<=8192 or not 0<h<=8192 or len(raw)!=expected:raise ValueError('场景图集尺寸或字节数不符合约定')
            if w&(w-1) or h&(h-1):raise ValueError('场景运行图集要求二的整数次幂画布；PNG 导入工具可补充透明边缘')
            if 'graphics' in scene:
                if scene.get('base_id',0)!=0:raise ValueError('自定义图块使用基础场景 0')
                graphics=scene['graphics'];rects=graphics['rects']
                if not 0<len(rects)<=4096:raise ValueError('图块数量超出范围')
                for rect in rects:
                    if len(rect)!=8:raise ValueError('图块要求八个 int16 字段')
                    for v in rect:integer(v,-32768,32767)
                    x,y,rw,rh=rect[:4]
                    if min(x,y)<0 or min(rw,rh)<=0 or x+rw>w or y+rh>h:raise ValueError('图块超出图集边界')
                for name in ('back','front'):
                    layers=graphics.get(name,[])
                    if len(layers)>64:raise ValueError('场景图层数量超出范围')
                    for frames in layers:
                        if not 0<len(frames)<=1024:raise ValueError('场景动画帧数超出范围')
                        for v in frames:integer(v,0,len(rects)-1)
            if any(name in scene for name in ('terrain','bases')) and 'bounds' not in scene:raise ValueError('地形与基地位置配置需要战场边界')
            if 'bounds' in scene:
                left,right=scene['bounds'];integer(left,0,10000);integer(right,left+100,20000)
                points=scene.get('terrain',[[0,0],[2*(right-left),0]])
                if len(points)<2 or points[0][0]!=0 or points[-1][0]!=2*(right-left):raise ValueError('地形需覆盖完整战场宽度')
                last=-1
                for x,y in points:
                    integer(x,last+1,40000);integer(y,-1000,1000);last=x
                bases=scene.get('bases',[min(68,(right-left)//4),right-left-47])
                if len(bases)!=2:raise ValueError('战场需要两端基地位置')
                for x in bases:integer(x,0,right-left)
                if bases[0]>=bases[1]:raise ValueError('基地位置顺序无效')
        for music in self.music.values():
            if music.get('file') not in self.assets or not music['file'].endswith('.msdf') or not self.assets[music['file']].startswith(b'OggS'):
                raise ValueError('音乐要求包含 Vorbis 数据的 .msdf 文件')
            self.enter(music);self.see_asset(music['file'])
            raw=self.assets[music['file']]
            if len(raw)<28 or raw[27+raw[26]:][:7]!=b'\x01vorbis':raise ValueError('音乐识别包要求 Ogg Vorbis')
            integer(music.get('base_sound_id',100),1,1030)
            start,end=music.get('loop_start',0),music.get('loop_end',0)
            if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in (start,end)) or end and end<=start:
                raise ValueError('音乐循环时间范围无效')
        self.stages={};self.locations={};self.areas={}
        for world in self.worlds.values():
            self.enter(world);self.title(world)
            for area in world.get('areas',[]):
                self.identity(area);self.title(area)
                self.areas[area['key']]=area
                for stage in area.get('stages',[]):
                    self.identity(stage);self.title(stage)
                    if stage.get('scene') not in self.scenes and not isinstance(stage.get('scene'),int):raise ValueError('未登记战场')
                    if not isinstance(stage['scene'],int):self.see(stage['scene'])
                    if isinstance(stage.get('scene'),int):integer(stage['scene'],0,137)
                    music=stage.get('music',100)
                    if type(music) is int:integer(music,1,1030)
                    elif music in self.music:self.see(music)
                    elif music in self.sounds:
                        if self.sounds[music]!='bgm':raise ValueError('关卡音乐要求类型为 bgm 的音效：'+str(music))
                        prefix=music.split('.',1)[0]
                        if prefix!='s1xlv' and prefix not in self.fragment['visible']:raise ValueError(f'{self.fragment["owner"]} 不能引用音效 {music}')
                    else:raise ValueError('未登记音乐')
                    integer(stage.get('template',1011),1,999999)
                    if type(stage.get('enemy_specials',True)) is not bool:raise ValueError('敌军绝招选项要求布尔值')
                    for name,default,low,high in [('stamina',0,0,1000),('reward_msp',0,0,999999),('enemy_base_hp',10000,1,100000000),('strength_steps',0,0,100)]:
                        integer(stage.get(name,default),low,high)
                    enemies=stage.get('enemies',[])
                    if not 0<len(enemies)<=32:raise ValueError('敌军名单要求 1–32 个条目')
                    for enemy in enemies:
                        self.unit_id(enemy['unit']);integer(enemy.get('level',40),1,200)
                    previous=-1
                    for wave in stage.get('waves',[]):
                        integer(wave['tick'],previous+1,32766);previous=wave['tick']
                        integer(wave['enemy'],0,len(enemies)-1)
                    if len(stage.get('waves',[]))>8192:raise ValueError('出击波次超过 8192')
                    rewards=stage.get('reward_units',[])
                    for unit in rewards:self.unit_id(unit)
                    self.stages[stage['key']]=stage;self.locations[stage['key']]=(world['key'],area['key'])
        if len(self.stages)>100000:raise ValueError('当前目录容量为 100000 条关卡')
        for item in [*self.worlds.values(),*(a for w in self.worlds.values() for a in w.get('areas',[])),*self.stages.values()]:
            self.enter(item)
            for key in item.get('requires',[]):
                if key not in self.stages:raise ValueError('解锁条件引用未登记关卡')
                self.see(key)
        # 解锁图的环会导致无法取得初始通关条件。
        from collections import deque
        effective={}
        for key,s in self.stages.items():
            world_key,area_key=self.locations[key];world=self.worlds[world_key]
            area=self.areas[area_key]
            effective[key]=[*world.get('requires',[]),*area.get('requires',[]),*s.get('requires',[])]
        pending={key:len(reqs) for key,reqs in effective.items()};followers={key:[] for key in self.stages}
        for key,reqs in effective.items():
            for req in reqs:followers[req].append(key)
        queue=deque(key for key,count in pending.items() if not count);visited=0
        while queue:
            key=queue.popleft();visited+=1
            for follower in followers[key]:
                pending[follower]-=1
                if not pending[follower]:queue.append(follower)
        if visited!=len(self.stages):raise ValueError('解锁条件存在循环')
        self.fragment=None
        self.fingerprint=blake2(json.dumps(self.raw,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
    def add_asset(self,name,raw,owner):
        if name in self.asset_owner:raise ValueError('资源文件名重复：'+name)
        if len(raw)>64*1024*1024:raise ValueError('单个资源超过 64 MiB')
        self.assets[name]=raw;self.asset_owner[name]=owner
    def identity(self,row):
        key=stable_key(row['key']);owner=self.fragment['owner']
        if key in self.keys:raise ValueError('内容键重复：'+key)
        if owner!='body' and not key.startswith(owner+'.'):raise ValueError(f'模组内容键须以 "{owner}." 开头：{key}')
        self.keys.add(key);self.owner[key]=owner
    def index(self,name):
        result={}
        for row in self.fragment['raw'].get(name,[]):self.identity(row);result[row['key']]=row
        return result
    def enter(self,row):
        """之后的引用检查以 row 所属来源的可见范围为准。"""
        self.fragment={'owner':self.owner[row['key']],'visible':self.visible[self.owner[row['key']]]}
    def see(self,key):
        if self.owner.get(key,'body') not in self.fragment['visible']:raise ValueError(f'{self.fragment["owner"]} 不能引用 {key}（只能引用本体、本模组与所依赖模组的内容）')
    def see_asset(self,name):
        if self.asset_owner[name] not in self.fragment['visible']:raise ValueError(f'{self.fragment["owner"]} 不能引用资源 {name}')
    def title(self,row):
        if not isinstance(row.get('title'),str) or not row['title'] or '\0' in row['title']:raise ValueError('标题应为有效文本')
    def unit_id(self,key):
        if type(key) is int:return integer(key,1,399)
        if key not in self.units:raise ValueError('未登记社区单位：'+str(key))
        if self.fragment is not None:
            prefix=key.split('.',1)[0]
            if prefix!='s1xlv' and prefix not in self.fragment['visible']:raise ValueError(f'{self.fragment["owner"]} 不能引用单位 {key}')
        return self.units[key]

def merge_scenes(content):
    catalog=Catalog(content.root.parent/'campaign_content',content.units,getattr(content,'mod_campaigns',()),
                    sounds={e['key']:e.get('type','se') for e in getattr(content,'sounds',[])})
    content.campaign_catalog=catalog
    for name in catalog.assets:
        if name in content.p.asset_cache.safe_names:raise ValueError('新增场景或音乐与原生资源文件名冲突：'+name)
    scenes=content.manifest.setdefault('stages',[])
    for scene in catalog.scenes.values():
        row=dict(scene);row['id']=138+len(scenes);row.setdefault('base_id',0);scenes.append(row)
    for name,raw in catalog.assets.items():
        if not name.endswith('.obm'):continue
        if name in content.assets and content.assets[name]!=raw:raise ValueError('社区资源与场景资源文件名冲突')
        content.assets[name]=raw;content.asset_dimensions[name]=struct.unpack_from('<HH',raw,4)
