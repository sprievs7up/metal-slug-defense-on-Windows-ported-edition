"""Register additive native content and persist its progress per save profile."""
from pathlib import Path
import json,struct,io,os
import content_ids
import behaviors
import content_sounds
import content_locale
from content_digest import DigestCache

HEADER=0x1ffee000
RECORD_SIZE=0x90
UNIT_ID_BASE=1024
ORIGINAL_UNITS=400
CONTENT_INDEX='content.json'
# 组合包商店 ID：槽位数不超过 64 时沿用既有 576，超过后取 512+槽位数，避开单位商店 ID 512+槽位。
LEGACY_PACK_SHOP_ID=576
# 未启用槽位（停用模组或本体空位）的占位记录复制原版 UnitID 2 的数据行、动作类与描述符，并标记为内部单位。
PLACEHOLDER_BASE_ID=2
PLACEHOLDER_TEXT='-'
# 已拥有单位紧凑列表的最小容量（原有 512 个 int32）；单位较多时按 400+槽位数扩大。
OWNED_LIST_MIN=512
# 多页图标（M1b）：页 0/1 为原版 unit_icon_01/02（菜单图像 33/34）；单位文件以 icon.atlas 指定图标页图集，
# 加载器按图集首次出现顺序（UnitID 升序）分配页 2 起的页号。页表每页 16 字节，见 src/community_content.cpp。
ICON_PAGE_FIRST=2
ICON_PAGE_ENTRY=16
MENU_IMAGE_TABLE=0x10901d00
MENU_IMAGE_UNIT_ICON_02=34
IMAGE_DESC_SIZE=64
LANGUAGES=frozenset(('EN','JP','KR','ES','PT','RU','FR','DE','IT','ZT','ZS'))
COMMAND_LENGTHS=(2,2,2,2,2,1,3,5,2,2,3,5,5,2,3,1,1,2,2,3,3,1,5,2)
ANCHOR_INDEX={1:0,2:1,3:2,4:3,5:4,6:5,7:6,13:7,14:8,15:9,16:10,17:11,18:12,19:13,20:14,
              22:15,23:16,24:17,25:18,26:19,27:20,29:21,30:22,31:23,32:24,33:25,34:26,35:27,36:28,38:29,39:30,40:31}

def anchor_offsets(word):
    return [word*4]+[(42+33*i+ANCHOR_INDEX[word])*4 for i in range(5)]

def ratio(value):
    """解析整数或精确有理数倍率，保持既有注册表的整数格式。"""
    if isinstance(value,int) and not isinstance(value,bool):value=(value,1)
    if not isinstance(value,(list,tuple)) or len(value)!=2:raise ValueError('Invalid rational unit multiplier')
    a,b=value
    if any(not isinstance(v,int) or isinstance(v,bool) or not 0<v<=10000 for v in (a,b)) or a>100*b:raise ValueError('Invalid rational unit multiplier')
    return a,b

# 原版单位覆盖补丁（M3b）。倍率组字段由原生在等级插值后应用（与社区单位相同的 combat profile）；其余写入数据行。
PROFILE_ORDER=('hp_multiplier','damage_multiplier','move_speed_multiplier','attack_range_multiplier',
               'knockback_distance_multiplier','ballistic_range_multiplier')
PROFILE_FIELDS=frozenset(PROFILE_ORDER)

def patch_stock_row(row,fields):
    """把补丁写入原版单位的数据行（0x390 字节），取整规则与社区单位相同。"""
    def scale(offsets,pair,mode):
        a,b=ratio(pair)
        for off in offsets:
            v=struct.unpack_from('<i',row,off)[0]
            if mode=='positive_round':
                if v>0:struct.pack_into('<i',row,off,(2*v*a+b)//(2*b))
            elif mode=='positive_ceil':
                if v>0:struct.pack_into('<i',row,off,(v*a+b-1)//b)
            elif mode=='ceil':struct.pack_into('<i',row,off,(v*a+b-1)//b)
            else:struct.pack_into('<i',row,off,v*a//b)
    if 'ap' in fields:
        for off in (4,0xa8,0x12c,0x1b0,0x234,0x2b8):struct.pack_into('<i',row,off,fields['ap'])
    if 'shop_price' in fields:struct.pack_into('<i',row,0x358,fields['shop_price'])
    if 'production_interval_multiplier' in fields:scale(anchor_offsets(2),fields['production_interval_multiplier'],'ceil')
    if 'special_damage_multiplier' in fields:scale(anchor_offsets(29),fields['special_damage_multiplier'],'floor')
    if 'attack_wait_multiplier' in fields:scale(anchor_offsets(27)+anchor_offsets(34),fields['attack_wait_multiplier'],'ceil')
    if 'special_cooldown_multiplier' in fields:scale(anchor_offsets(35)+anchor_offsets(36),fields['special_cooldown_multiplier'],'positive_ceil')
    if 'knockback_threshold_multiplier' in fields:scale(anchor_offsets(4),fields['knockback_threshold_multiplier'],'positive_round')
    if 'normal_projectile_distance_multiplier' in fields:scale(anchor_offsets(26),fields['normal_projectile_distance_multiplier'],'floor')
    if 'special_projectile_distance_multiplier' in fields:scale(anchor_offsets(33),fields['special_projectile_distance_multiplier'],'floor')

def assign_icon_pages(units):
    """按 UnitID 升序、图集首次出现顺序为 icon.atlas 分配页号（2 起）。"""
    pages={}
    for unit in sorted(units,key=lambda u:u['id']):
        atlas=unit['icon'].get('atlas')
        if atlas is not None:unit['icon']['page']=pages.setdefault(atlas,ICON_PAGE_FIRST+len(pages))

def stock_dir():
    import probe
    return Path(probe.RESOURCE_ROOT)/probe.PKG

def stock_asset_exists(name):
    """单位可按文件名引用原版游戏资源（不重新分发原版素材）。"""
    return isinstance(name,str) and Path(name).name==name and (stock_dir()/name).is_file()

class AssetDims(dict):
    """资源名 → (宽, 高)；未登记的原版资源按需读取文件头。"""
    def __missing__(self,name):
        if not stock_asset_exists(name):raise KeyError(name)
        with (stock_dir()/name).open('rb') as stream:head=stream.read(8)
        self[name]=struct.unpack_from('<HH',head,4);return self[name]

def load_manifest(root):
    """读取内容索引 content.json（schema 3）与 units/ 逐单位文件，组装为既有 schema 2 结构的内存清单。

    单位按 UnitID 排序；加载器补回 id（content.json 的 unit_ids）与 icon.index（340+槽位，槽位为 UnitID−1024）；
    组合包补回 shop_id。单位文件不得自行写定这两项。返回 (清单, 本体区段, 模组区段)。"""
    index=json.loads((root/CONTENT_INDEX).read_text(encoding='utf-8'))
    if index.get('schema')!=3:raise ValueError('Unsupported community content index schema')
    if index.get('asset_digest')!='blake2b-256':raise ValueError('Unsupported community asset digest')
    body,mods=content_ids.check_ranges(index.get('unit_id_ranges'))
    unit_ids=index.get('unit_ids');content_ids.check_body_ids(unit_ids,body)
    folder=index.get('units_dir')
    if not isinstance(folder,str) or Path(folder).name!=folder:raise ValueError('Invalid unit folder')
    units={}
    for path in sorted((root/folder).glob('*.json')):
        data=json.loads(path.read_text(encoding='utf-8'))
        key=data.get('key') if isinstance(data,dict) else None
        if key not in unit_ids or key in units:raise ValueError('Unregistered or duplicate body unit file: '+path.name)
        if 'id' in data or not isinstance(data.get('icon'),dict) or 'index' in data['icon']:raise ValueError('Unit files must not fix runtime identities: '+path.name)
        uid=unit_ids[key]
        unit={'key':key,'id':uid}
        unit.update((name,value) for name,value in data.items() if name!='key')
        unit['icon']=dict(index=340+uid-UNIT_ID_BASE,**data['icon'])
        if isinstance(unit.get('localization'),dict):unit['localization']=content_locale.fill(unit['localization'],'unit text')
        if ('atlas' in data['icon'])==('page' in data['icon']):raise ValueError('Unit icon requires either page 1 or an atlas: '+path.name)
        units[key]=unit
    if set(units)!=set(unit_ids):raise ValueError('Missing body unit files: '+', '.join(sorted(set(unit_ids)-set(units))))
    # 特殊行为（M2）：按行为库校验 behaviors 并转换为原生安装使用的内部字段。
    behaviors.apply(units,behaviors.load_library())
    manifest={'schema':2,'original_android_version':index.get('original_android_version'),
              'units':sorted(units.values(),key=lambda u:u['id']),'assets':index['assets'],'unit_id_base':UNIT_ID_BASE}
    assign_icon_pages(manifest['units'])
    for name,value in index.items():
        if name in manifest or name in ('unit_id_ranges','unit_ids','units_dir','asset_digest'):continue
        if name=='unit_pack' and value:
            if 'shop_id' in value:raise ValueError('The unit pack shop ID is assigned by the loader')
            if isinstance(value.get('localization'),dict):value=dict(value,localization=content_locale.fill(value['localization'],'pack text'))
            slots=manifest['units'][-1]['id']-UNIT_ID_BASE+1
            value=dict(value,shop_id=LEGACY_PACK_SHOP_ID if slots<=64 else 512+slots)
        manifest[name]=value
    return manifest,body,mods

def check_unit(u):
    """单位数据的静态检查（不依赖其他单位与资源）；本体与模组单位共用。"""
    if not isinstance(u['key'],str) or not u['key'] or '\0' in u['key']:raise ValueError('Invalid stable unit key')
    tags=u.get('tags',[])
    if not isinstance(tags,list) or any(not isinstance(t,str) or not t or '\0' in t for t in tags):raise ValueError('Invalid unit tags')
    if not 0<u['base_id']<400:raise ValueError('Invalid original unit reference')
    if not u.get('available_from_start') and (not isinstance(u.get('shop_unlock_reference_id'),int) or not 0<=u['shop_unlock_reference_id']<512):raise ValueError('Invalid original shop unlock reference')
    if set(u['localization'])!=LANGUAGES:raise ValueError('All eleven unit localizations are required')
    reward=u.get('world_clear_reward')
    if 'world_clear_reward' in u:
        if (not isinstance(reward,dict) or set(reward)!=set(('world','area','world_type'))
                or any(not isinstance(value,int) or isinstance(value,bool) for value in reward.values())
                or not 0<=reward['world']<3 or not 0<=reward['area']<16
                or reward['world_type'] not in (0,1) or u.get('internal_only')
                or u.get('available_from_start') or u['shop_price']!=0):
            raise ValueError('Invalid native world-clear unit reward')
    if (not isinstance(u['shop_price'],int) or isinstance(u['shop_price'],bool)
            or not (0<=u['shop_price']<=32767 if reward is not None else 0<u['shop_price']<=32767)
            or not 0<u['ap']<=100000):raise ValueError('Unit price/AP outside supported range')
    if u['icon']['page']!=1 and not (u['icon']['page']>=ICON_PAGE_FIRST and isinstance(u['icon'].get('atlas'),str)):raise ValueError('Community icons must use unit_icon_02 or an icon page atlas')
    ratio(u['hp_multiplier'])
    if not isinstance(u['production_reference_id'],int) or not 0<u['production_reference_id']<400:raise ValueError('Invalid production reference unit')
    if u['faction'] not in range(5):raise ValueError('Invalid native faction filter')
    rect=u['icon']['rect'];anchor=u['icon']['anchor']
    if len(rect)!=4 or len(anchor)!=2 or any(not isinstance(v,int) or not -32768<=v<=32767 for v in [*rect,*anchor]):raise ValueError('Invalid icon geometry')
    if rect[0]<0 or rect[1]<0 or rect[2]<=0 or rect[3]<=0:raise ValueError('Invalid icon rectangle')
    for key in ('production_interval_multiplier','special_damage_multiplier','attack_wait_multiplier',
                'damage_multiplier','move_speed_multiplier','attack_range_multiplier',
                'knockback_distance_multiplier','ballistic_range_multiplier',
                'knockback_threshold_multiplier','normal_projectile_distance_multiplier',
                'special_projectile_distance_multiplier','summon_interval_multiplier',
                'construction_time_multiplier','summon_interval_additional_multiplier'):
        ratio(u.get(key,[1,1]))
    ratio(u.get('special_cooldown_multiplier',[1,1]))
    for word,value in u.get('status_word_values',{}).items():
        if not word.isdigit() or int(word) not in ANCHOR_INDEX or int(word) in (1,2,3,4,5,13,14) or not isinstance(value,int) or isinstance(value,bool) or not -2147483648<=value<=2147483647:raise ValueError('Invalid absolute status word')
    flame=u.get('flame_interrupt')
    if flame is not None:
        bullets=flame.get('ending_bullet_animations')
        values=[flame.get('flame_start_tick'),flame.get('flame_ticks'),flame.get('alternate_knockback_animation'),flame.get('knockback_limit_per_special')]
        if u['base_id']!=3 or not u.get('sprite_descriptor') or not isinstance(bullets,list) or len(bullets)!=4 or any(not isinstance(v,int) or isinstance(v,bool) or not 0<=v<256 for v in values+bullets) or not 6<=values[1]<=200 or values[3] not in (0,1):raise ValueError('Invalid flame interruption adapter')
    for group,reference in u.get('attack_parameter_references',{}).items():
        if group not in ('normal','special') or reference.get('group') not in ('normal','special') or not isinstance(reference.get('unit_id'),int) or not 0<reference['unit_id']<400:raise ValueError('Invalid attack parameter reference')
    for group,attribute in u.get('attack_attributes',{}).items():
        if group not in ('normal','special') or not isinstance(attribute,int) or isinstance(attribute,bool) or attribute not in range(5):raise ValueError('Invalid native attack attribute')
    if 'shot_action_reference_id' in u and (u['base_id']!=61 or u['shot_action_reference_id']!=157):raise ValueError('Unsupported mummy projectile action reference')
    grounded=u.get('ground_special_attack',False)
    if not isinstance(grounded,bool) or (grounded and u['base_id']!=3):raise ValueError('Unsupported grounded special attack')
    if not isinstance(u.get('normal_attack_range_from_projectile',False),bool):raise ValueError('Invalid projectile attack-range flag')
    for group,category in u.get('attack_range_categories',{}).items():
        if group not in ('normal','special') or not isinstance(category,int) or isinstance(category,bool) or not 0<=category<=5:raise ValueError('Invalid native menu attack-range category')
    for text in u['localization'].values():
        if not isinstance(text['name'],str) or not isinstance(text['description'],str) or not text['name'] or not text['description'] or '\0' in text['name']+text['description']:raise ValueError('Invalid unit text')
    for commands in u['animations'].values():
        if not 0<len(commands)<=10000:raise ValueError('Animation command capacity exceeded')
        for cmd in commands:
            opcode=cmd['opcode'];values=cmd['values']
            if not isinstance(opcode,int) or not 0<=opcode<len(COMMAND_LENGTHS) or len(values)!=COMMAND_LENGTHS[opcode]-1:raise ValueError('Invalid animation command arity')
            # op23（播放音效）的参数可写音效稳定键（M6），安装时换为分配的 SoundID。
            if any(not (isinstance(v,int) and not isinstance(v,bool) and -2147483648<=v<=2147483647 or opcode==content_sounds.SOUND_OPCODE and i==0 and isinstance(v,str)) for i,v in enumerate(values)):raise ValueError('Invalid animation command value')

def check_references(u,by_key):
    """单位间引用（内部子单位、空降落地、召唤、预览）。"""
    if not isinstance(u.get('internal_only',False),bool):raise ValueError('Invalid internal unit flag')
    child=u.get('child_unit_key')
    if child is not None and (child not in by_key or not by_key[child].get('internal_only') or child==u['key']):raise ValueError('Invalid internal child reference')
    landing=u.get('landing_unit_key')
    if landing is not None and (u['base_id']!=160 or landing not in by_key or by_key[landing].get('internal_only')):raise ValueError('Invalid paratrooper landing reference')
    summoned=u.get('summoned_unit_key')
    if summoned is not None and (u['base_id']!=64 or summoned not in by_key or summoned==u['key'] or by_key[summoned].get('internal_only')):raise ValueError('Invalid mummy gate summon reference')
    preview=u.get('preview_unit_key')
    if preview is not None and (preview!=child or preview not in by_key):raise ValueError('Invalid unit preview reference')

def check_unit_assets(u,dims,descriptor_path,is_stock):
    """纹理、图标矩形与精灵描述符检查。dims：资源名 → (宽, 高)（含引用的原版图集）；descriptor_path：描述符文件名 → 路径；
    is_stock：原版资源文件是否存在。返回精灵描述符（无则 None）。"""
    desc=None
    for name in u.get('textures',[u.get('texture')]):
        if name not in dims and not is_stock(name):raise ValueError('Unregistered unit texture: '+str(name))
    icon_atlas=u['icon'].get('atlas','unit_icon_02.obm')
    if icon_atlas not in dims:raise ValueError('Missing community icon atlas: '+icon_atlas)
    width,height=dims[icon_atlas];x,y,w,h=u['icon']['rect']
    if x+w>width or y+h>height:raise ValueError('Icon rectangle outside its atlas')
    filename=u.get('sprite_descriptor')
    if filename:
        if Path(filename).name!=filename or not filename.endswith('.json'):raise ValueError('Invalid sprite descriptor path')
        desc=json.loads(descriptor_path(filename).read_text(encoding='utf-8'))
        rects=desc['rects'];frames=desc['frames'];textures=u.get('textures',[u.get('texture')])
        if not 1<=len(rects)<=8192 or not 1<=len(frames)<=65536 or not 1<=desc['script_count']<=256:raise ValueError('Invalid sprite descriptor capacity')
        for x,y,w,h,ax,ay,flags,page in rects:
            if any(not isinstance(v,int) or not -32768<=v<=32767 for v in (x,y,w,h,ax,ay,flags,page)) or not 0<=page<len(textures):raise ValueError('Invalid sprite rectangle')
            width,height=dims[textures[page]]
            if min(x,y,w,h)<0 or x+w>width or y+h>height:raise ValueError('Sprite rectangle outside its atlas')
        starts=set();pos=0
        while pos<len(frames):
            starts.add(pos);count=frames[pos]
            if not isinstance(count,int) or not 0<=count<=64 or pos+count>=len(frames) or any(not isinstance(v,int) or not 0<=v<len(rects) for v in frames[pos+1:pos+1+count]):raise ValueError('Invalid sprite frame')
            pos+=count+1
        for key,commands in u['animations'].items():
            if not 0<=int(key)<desc['script_count']:raise ValueError('Animation index outside sprite descriptor')
            for cmd in commands:
                op,values=cmd['opcode'],cmd['values']
                if op==0 and values[0]!=-1 and values[0] not in starts:raise ValueError('Animation references invalid frame')
                if op in (10,11,12,22) and not 0<=values[0]<desc['script_count']:raise ValueError('Animation references invalid child script')
                if op in (3,4) and not -1<=values[0]<len(desc['hit_bounds' if op==3 else 'attack_bounds']):raise ValueError('Animation references invalid collision rectangle')
        for field in ('hit_bounds','attack_bounds'):
            if not 1<=len(desc[field])<=256 or any(len(r)!=5 or any(not isinstance(v,int) or not -2147483648<=v<=2147483647 for v in r) for r in desc[field]):raise ValueError('Invalid sprite collision bounds')
    flame=u.get('flame_interrupt')
    if flame and (flame['alternate_knockback_animation']+5>desc['script_count'] or any(v>=desc['script_count'] for v in flame['ending_bullet_animations'])):raise ValueError('Flame interruption animation outside sprite descriptor')
    if 'recovery_animation' in u:
        value=u['recovery_animation']
        if u['base_id']!=61 or not filename or not isinstance(value,int) or isinstance(value,bool) or not 0<=value<desc['script_count']:raise ValueError('Invalid mummy recovery animation')
    return desc

class CommunityContent:
    def __init__(self,p,root=None):
        self.p=p
        self.root=Path(root or Path(__file__).resolve().parent/'community_content')
        self.manifest,self.body_range,self.mod_range=load_manifest(self.root)
        self.units=self.manifest['units']
        if not self.units:raise ValueError('No community units')
        self.path=p.saves/'community_progress.json'
        self.progress=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'schema':1,'units':{}}
        if self.progress.get('schema')!=1:raise ValueError('Unsupported community progress schema')
        self.descriptor_paths={}
        self.load_mods()
        # 槽位 = UnitID − 1024；未登记的槽位以占位记录填充（未启用）。
        self.slot_count=self.units[-1]['id']-UNIT_ID_BASE+1
        self.slots=[None]*self.slot_count
        for u in self.units:self.slots[u['id']-UNIT_ID_BASE]=u
        # 来源：本体内容为 'body'，模组单位为模组 id。不写入清单，以免改变内容结构。
        self.unit_source={u['key']:self.mod_unit_source.get(u['key'],'body') for u in self.units}
        keys=set()
        for u in self.units:
            if u['key'] in keys:raise ValueError('Unstable or duplicate community unit identity')
            check_unit(u);keys.add(u['key'])
        by_key={u['key']:u for u in self.units}
        for u in self.units:check_references(u,by_key)
        self.load_sounds()
        self.unit_pack=self.manifest.get('unit_pack')
        if self.unit_pack:
            pack=self.unit_pack
            if pack.get('id')!=10 or not 512+self.slot_count<=pack.get('shop_id')<=32767:raise ValueError('Invalid community pack identity')
            if not isinstance(pack.get('shop_price'),int) or not 0<pack['shop_price']<=32767:raise ValueError('Invalid community pack price')
            if not 1<=len(pack.get('units',[]))<=7 or len(set(pack['units']))!=len(pack['units']):raise ValueError('Invalid community pack members')
            if any(key not in by_key or by_key[key].get('internal_only') for key in pack['units']):raise ValueError('Invalid community pack unit')
            if set(pack.get('localization',{}))!=LANGUAGES:raise ValueError('All eleven pack localizations are required')
            if any(not isinstance(text.get(field),str) or not text[field] or '\0' in text[field] for text in pack['localization'].values() for field in ('name','description')):raise ValueError('Invalid pack text')
        self.assets={};self.asset_dimensions=AssetDims();digests=DigestCache()
        for name,digest in self.manifest['assets'].items():
            if Path(name).name!=name or not name.lower().endswith('.obm'):raise ValueError('Invalid content asset name')
            source=self.asset_paths.get(name,self.root/name)
            raw=source.read_bytes()
            if digest is not None and digests.digest(source,raw)!=digest:raise ValueError('Content asset checksum mismatch: '+name)
            if len(raw)<8 or raw[:2]!=b'OI':raise ValueError('Unsupported content texture header: '+name)
            width,height=struct.unpack_from('<HH',raw,4);kind,bits=raw[2:4]
            if kind==1 and bits==4:expected=8+64+(width*height+1)//2
            elif kind in (1,4) and bits==8:expected=8+(1024 if kind==1 else 512)+width*height
            elif kind in (0,1) and bits in (24,32):expected=8+width*height*(3 if kind==0 else 4)
            else:raise ValueError('Unsupported content texture format: '+name)
            if not 0<width<=8192 or not 0<height<=8192 or len(raw)!=expected:raise ValueError('Invalid content texture dimensions or byte count: '+name)
            self.asset_dimensions[name]=(width,height)
            self.assets[name]=raw
        digests.save()
        self.icon_pages=sorted({(u['icon']['page'],u['icon']['atlas']) for u in self.units if 'atlas' in u['icon']})
        if [page for page,_ in self.icon_pages]!=list(range(ICON_PAGE_FIRST,ICON_PAGE_FIRST+len(self.icon_pages))):raise ValueError('Non-contiguous icon pages')
        if len(self.icon_pages)>32767-ICON_PAGE_FIRST:raise ValueError('Icon page capacity exceeded')
        self.sprite_descriptors={}
        for u in self.units:
            desc=check_unit_assets(u,self.asset_dimensions,self.descriptor_path,stock_asset_exists)
            if desc:self.sprite_descriptors[u['key']]=desc
        from campaign_catalog import merge_scenes
        merge_scenes(self)
        import community_maps
        community_maps.validate(self.manifest,self.assets)
        self.overridden_assets=set()
        self.legacy_ids={}
        for u in self.units:
            saved=self.progress['units'].get(u['key'],{})
            if u['key'] in self.mod_unit_source:
                # 模组单位：ID 由持久化映射决定；存档记录的旧 ID 不同时以当前 ID 为准（编队处理见 M4）。
                if saved.get('id',u['id'])!=u['id']:p.log('COMMUNITY_MOD_UNIT_ID_CHANGED',u['key'],saved.get('id'),u['id'])
                continue
            previous=saved.get('id',u['id'])
            if previous!=u['id']:
                if previous!=400+u['id']-UNIT_ID_BASE:raise ValueError('Unsupported legacy unit identity')
                self.legacy_ids[previous]=u['id']
        self.deck_migration_done=not self.legacy_ids
        self.decks_reconciled=False
        self.original_filecall=p.filecall
        def filecall(name,args):
            leaf=Path(p.string(args[0])).name if name=='fopen' else None
            if leaf in self.assets and p.string(args[1]).startswith('r'):
                self.overridden_assets.add(leaf)
                handle=p.alloc(16);p.handles[handle]=io.BytesIO(self.assets[leaf]);return handle
            if leaf in self.sound_files and p.string(args[1]) in ('rb','r'):
                handle=p.alloc(16);p.handles[handle]=io.BytesIO(Path(self.sound_files[leaf]).read_bytes());return handle
            return self.original_filecall(name,args)
        p.filecall=filecall
        self.original_host=p.host
        def host(a,size=1):
            # memset operates on the list's full allocation during rebuilding.
            if hasattr(self,'app') and a==self.app+0xb240:a=self.custom_list
            elif hasattr(self,'app') and a==self.app+0xb9d4:a=self.deck_list
            return self.original_host(a,size)
        p.host=host
        if not hasattr(p.uc.lib,'msd_community_unit_id_base') or p.uc.lib.msd_community_unit_id_base()!=UNIT_ID_BASE:raise RuntimeError('Native core lacks the separated community unit namespace')
        extended=any(isinstance(u['hp_multiplier'],list) or any(key in u for key in
            ('damage_multiplier','move_speed_multiplier','attack_range_multiplier','knockback_distance_multiplier','ballistic_range_multiplier')) for u in self.units)
        if extended and (not hasattr(p.uc.lib,'msd_community_combat_profile_version') or p.uc.lib.msd_community_combat_profile_version()!=1):raise RuntimeError('Native core lacks rational combat profiles')
        if any(not u['available_from_start'] for u in self.units) and (not hasattr(p.uc.lib,'msd_community_shop_gate_version') or p.uc.lib.msd_community_shop_gate_version()!=1):raise RuntimeError('Native core lacks original-shop unlock references')
        if self.unit_pack and (not hasattr(p.uc.lib,'msd_community_unit_pack_version') or p.uc.lib.msd_community_unit_pack_version()!=1):raise RuntimeError('Native core lacks community unit packs')
        if any(u.get('landing_unit_key') for u in self.units) and (not hasattr(p.uc.lib,'msd_community_paratrooper_landing_version') or p.uc.lib.msd_community_paratrooper_landing_version()!=1):raise RuntimeError('Native core lacks paratrooper landing references')
        if any(u.get('child_unit_key') for u in self.units) and (not hasattr(p.uc.lib,'msd_community_display_status_version') or p.uc.lib.msd_community_display_status_version()!=1):raise RuntimeError('Native core lacks child display status references')
        if any('recovery_animation' in u for u in self.units) and (not hasattr(p.uc.lib,'msd_community_mummy_variant_version') or p.uc.lib.msd_community_mummy_variant_version()!=1):raise RuntimeError('Native core lacks mummy recovery and viewer adaptation')
        if any(u.get('flame_interrupt') for u in self.units) and (not hasattr(p.uc.lib,'msd_community_flame_interrupt_version') or p.uc.lib.msd_community_flame_interrupt_version()!=1):raise RuntimeError('Native core lacks the flame interruption adapter')
        if any(u.get('retained_special_weapon') for u in self.units) and (not hasattr(p.uc.lib,'msd_community_retained_weapon_version') or p.uc.lib.msd_community_retained_weapon_version()!=1):raise RuntimeError('Native core lacks retained special weapons for community units')
        if any(u.get('ground_special_attack') for u in self.units) and (not hasattr(p.uc.lib,'msd_community_ground_special_version') or p.uc.lib.msd_community_ground_special_version()!=1):raise RuntimeError('Native core lacks grounded special attacks')
        # 行为库：核心内嵌的清单须与 behavior_library.json 相同（同一构建来源）。
        if any(u.get('behaviors') for u in self.units):
            if not hasattr(p.uc.lib,'msd_behavior_manifest'):raise RuntimeError('Native core lacks the behavior library')
            import ctypes
            p.uc.lib.msd_behavior_manifest.restype=ctypes.c_char_p
            if json.loads(p.uc.lib.msd_behavior_manifest().decode('utf-8'))!=behaviors.load_library()[0]:
                raise RuntimeError('Native core behavior library differs from behavior_library.json')
        if any(PROFILE_FIELDS&set(f) for f in self.stock_patches().values()) and (not hasattr(p.uc.lib,'msd_community_stock_profile_version') or p.uc.lib.msd_community_stock_profile_version()!=1):raise RuntimeError('Native core lacks combat profiles for original units')
        if self.sounds and (not hasattr(p.uc.lib,'msd_community_sound_version') or p.uc.lib.msd_community_sound_version()!=1):raise RuntimeError('Native core lacks custom sounds')
        if self.icon_pages and (not hasattr(p.uc.lib,'msd_community_icon_pages_version') or p.uc.lib.msd_community_icon_pages_version()!=1):raise RuntimeError('Native core lacks multi-page unit icons')
        p.uc.lib.msd_enable_community_content()
        self.ready=False

    def stock_patches(self):
        """模组覆盖补丁中针对原版单位的部分：UnitID → {字段: 值}（按加载顺序，后者覆盖前者）。"""
        import mod_loader
        result={}
        for entry in getattr(self,'mod_patches',[]):
            uid=mod_loader.original_uid(entry['target']) if entry['target'].startswith('unit:') else None
            if uid is not None:result.setdefault(uid,{})[entry['field']]=entry['value']
        return result

    def descriptor_path(self,name):
        return self.descriptor_paths.get(name,self.root/name)

    def load_sounds(self):
        """本体（content.json 的 sounds）与已载入模组的音效：校验、分配 SoundID，检查单位引用的可见范围（M6）。"""
        body=self.manifest.get('sounds',[])
        if not isinstance(body,list):raise ValueError('content.json sounds must be a list')
        entries=[]
        for entry in body:
            source=content_sounds.check_entry(entry,'s1xlv',lambda name:self.root/name if (self.root/name).is_file() else None)
            entries.append(dict(entry,source=str(source)))
        entries+=self.mod_sounds
        self.sound_ids=content_sounds.allocate(entries)
        self.sounds=entries;self.sound_files={}
        for entry in entries:
            if self.sound_files.setdefault(entry['file'],entry['source'])!=entry['source']:raise ValueError('Duplicate sound file name: '+entry['file'])
            # 宿主按文件名提供音效文件；与原版资源同名会替换原版音效，不允许。
            if stock_asset_exists(entry['file']):raise ValueError('Sound file name is used by an original asset: '+entry['file'])
        body_keys={e['key'] for e in entries if e['key'].startswith('s1xlv.')}
        for u in self.units:
            # 本体单位只引用本体音效；模组单位的可见范围已由 mod_loader 检查，此处确认已登记。
            try:content_sounds.check_unit_sounds(u,set(self.sound_ids) if u['key'] in self.mod_unit_source else body_keys)
            except ValueError as error:raise ValueError(u['key']+': '+str(error))
        if entries:self.p.log('COMMUNITY_SOUNDS',{k:v for k,v in self.sound_ids.items()})

    def load_mods(self):
        """按启用列表加载模组单位、资源与覆盖补丁（mod_loader），合并进清单；失败的模组被跳过并记录原因。"""
        import mod_loader,branding
        body={u['key']:u for u in self.units}
        preferred={key:data['id'] for key,data in self.progress['units'].items() if isinstance(data,dict) and isinstance(data.get('id'),int)}
        id_map=content_ids.ModIdMap(content_ids.default_map_path(),self.mod_range)
        game_root=Path(__file__).resolve().parent
        self.mod_campaigns=[];self.mod_sounds=[];self.mod_events=[]
        units,assets,patches,status=mod_loader.load(game_root,body,game_version=branding.load(game_root)['display_version'],
                                                   preferred_ids=preferred,id_map=id_map,stock_assets=stock_asset_exists,
                                                   body_assets=set(self.manifest['assets']),body_root=self.root,stock_root=stock_dir(),
                                                   campaign_root=self.root.parent/'campaign_content',campaigns=self.mod_campaigns,
                                                   sounds=self.mod_sounds,body_sounds={e.get('key'):e.get('type','se') for e in self.manifest.get('sounds',[]) if isinstance(e,dict)},
                                                   events=self.mod_events)
        id_map.save()
        self.mod_status=status;self.mod_patches=patches
        self.mod_unit_source={u['key']:u['key'].split('.',1)[0] for u in units}
        self.asset_paths={}
        for name,source in assets.items():
            # 单位使用 .json 描述符与 .obm 图集；其他资源（如关卡音乐 .msdf）由世界目录按引用读取（M5）。
            if name.lower().endswith('.json'):self.descriptor_paths[name]=source
            elif name.lower().endswith('.obm'):self.asset_paths[name]=source;self.manifest['assets'][name]=None
        if units:
            self.units=sorted(self.units+units,key=lambda u:u['id']);self.manifest['units']=self.units
            assign_icon_pages(self.units)
            pack=self.manifest.get('unit_pack')
            if pack:
                slots=self.units[-1]['id']-UNIT_ID_BASE+1
                pack['shop_id']=LEGACY_PACK_SHOP_ID if slots<=64 else 512+slots
        loaded=[s for s in status if s['state']=='loaded']
        if loaded:self.manifest['mods']=[{'id':s['id'],'version':s['version']} for s in loaded]
        for s in status:
            if s['state'] not in ('disabled',):self.p.log('COMMUNITY_MOD',s['id'],s['state'],s['reasons'])

    def alloc(self,raw):
        p=self.p;a=p.alloc(len(raw));p.write(a,bytes(raw));return a

    def replace_global(self,old,new):
        p=self.p;hits=[]
        # Global data and GOT references use relocated pointers, not code bytes.
        for section in p.elf.iter_sections():
            if section.name not in ('.got','.data','.data.rel.ro','.data.rel.ro.local','.bss'):continue
            start=0x10000000+section['sh_addr'];raw=p.read(start,section['sh_size'])
            for off in range(0,len(raw)-3,4):
                if struct.unpack_from('<I',raw,off)[0]==old:p.put(start+off,new);hits.append(start+off)
        if not hits:raise RuntimeError('Unresolved native global: '+hex(old))
        return hits

    def install(self):
        # n 为槽位数（UnitID 1024 至最大已登记 ID）；原生记录、数据行、描述符与各逐单位表均按槽位定址。
        p=self.p;n=self.slot_count;info=p.call('_ZN10BattleInfo11getInstanceEv');db=p.word(info)
        if p.word(db+8)!=400:raise RuntimeError('Unexpected original unit table size')
        base=p.word(db+4);original=p.read(base,400*0x390);rows=bytearray(original)+bytearray((UNIT_ID_BASE-400)*0x390)
        # 原版单位的覆盖补丁（M3b）：数据行字段写入复制的原版行；社区单位仍以未修改的 original 为基准。
        stock_patches=self.stock_patches()
        for uid,fields in stock_patches.items():
            row=memoryview(rows)[uid*0x390:(uid+1)*0x390];patch_stock_row(row,fields)
        table=0x10922f28;original_images=p.read(table,423*8);images=bytearray(original_images)
        actions_global=0x109373f4;actions=p.word(actions_global);action_rows=bytearray(p.read(actions,400*4))+bytearray((UNIT_ID_BASE-400)*4)
        menu=(p.word(0x101652d0)+0x101652b4+0x818)&0xffffffff
        menu_rows={}
        for j in range(320):menu_rows.setdefault(p.word(menu+j*20),menu+j*20)
        shopbase=(p.word(0x101655d8)+0x101655ce+0x19c)&0xffffffff
        language_table=p.symbols['strMenuUnitInfoTbl']
        language_order={p.word(language_table+i*4):i for i in range(11)}
        records=bytearray(n*RECORD_SIZE)
        placeholder_text=None
        for i,u in enumerate(self.slots):
            if u is None:
                # 未启用槽位：原版 UnitID 2 的数据行、动作类与描述符；内部单位标记使其不被拥有、不进入商店与编队。
                uid=UNIT_ID_BASE+i;bid=PLACEHOLDER_BASE_ID
                row=bytearray(original[bid*0x390:(bid+1)*0x390]);struct.pack_into('<I',row,0,uid);rows+=row
                action_rows+=struct.pack('<I',p.word(actions+bid*4))
                images+=p.read(table+bid*8,8)
                menurow=bytearray(p.read(menu_rows[bid],20));struct.pack_into('<II',menurow,0,uid,uid)
                struct.pack_into('<h',menurow,10,340+i)
                shoprow=bytearray(p.read(shopbase+23*32,32));struct.pack_into('<H',shoprow,0,512+i)
                struct.pack_into('<I',shoprow,4,uid);struct.pack_into('<h',shoprow,16,0)
                values=(uid,bid,512+i,self.alloc(menurow),self.alloc(shoprow),423+i,0xffffffff,20,0,0,0,0)
                struct.pack_into('<12I',records,i*RECORD_SIZE,*values)
                struct.pack_into('<I',records,i*RECORD_SIZE+0x8c,1)
                if placeholder_text is None:placeholder_text=p.cstr(PLACEHOLDER_TEXT)
                for lang in range(11):
                    for offset in (0x30,0x5c):struct.pack_into('<I',records,i*RECORD_SIZE+offset+lang*4,placeholder_text)
                continue
            uid=u['id'];bid=u['base_id'];row=bytearray(original[bid*0x390:(bid+1)*0x390])
            struct.pack_into('<I',row,0,uid)
            for off in (4,0xa8,0x12c,0x1b0,0x234,0x2b8):struct.pack_into('<i',row,off,u['ap'])
            # 击毁 AP 返还（状态词 13）与 Wi-Fi 对战 RP（状态词 14）的六个等级锚点固定为本单位 AP 的 10%，向下取整（原版多数单位采用同一关系）。
            for off in (0x34,0xc4,0x148,0x1cc,0x250,0x2d4,0x38,0xc8,0x14c,0x1d0,0x254,0x2d8):struct.pack_into('<i',row,off,u['ap']//10)
            # 有理数生命值在原生等级插值完成后缩放，避免中间等级的重复取整。
            if isinstance(u['hp_multiplier'],int):
                for off in (12,0xb0,0x134,0x1b8,0x23c,0x2c0):struct.pack_into('<i',row,off,struct.unpack_from('<i',row,off)[0]*u['hp_multiplier'])
            a,b=u['production_interval_multiplier'];ref=u['production_reference_id']
            for off in (8,0xac,0x130,0x1b4,0x238,0x2bc):
                v=struct.unpack_from('<i',original,ref*0x390+off)[0];struct.pack_into('<i',row,off,(v*a+b-1)//b)
            for group,reference in u.get('attack_parameter_references',{}).items():
                target=22 if group=='normal' else 29;source=22 if reference['group']=='normal' else 29
                for word in range(5):
                    for dest,origin in zip(anchor_offsets(target+word),anchor_offsets(source+word)):
                        row[dest:dest+4]=original[reference['unit_id']*0x390+origin:reference['unit_id']*0x390+origin+4]
                attribute=28 if group=='normal' else 37;source_attribute=28 if reference['group']=='normal' else 37
                row[attribute*4:attribute*4+4]=original[reference['unit_id']*0x390+source_attribute*4:reference['unit_id']*0x390+source_attribute*4+4]
            # 原生攻击属性为非等级字段：普攻词 28、绝招词 37；1 表示火焰。
            for group,attribute in u.get('attack_attributes',{}).items():
                struct.pack_into('<i',row,(28 if group=='normal' else 37)*4,attribute)
            for field,words in (('normal_projectile_distance_multiplier',(26,)),('special_projectile_distance_multiplier',(33,)),
                                ('summon_interval_multiplier',(38,39)),('construction_time_multiplier',(38,))):
                a,b=ratio(u.get(field,[1,1]))
                for word in words:
                    for off in anchor_offsets(word):
                        value=struct.unpack_from('<i',row,off)[0]
                        # 原生箱体在计量降至负值的 tick 召唤；后续间隔包含计量零值的一帧。
                        if field=='summon_interval_multiplier' and word==39 and a!=b:
                            scaled=((value+1)*a+b-1)//b-1
                        else:scaled=(value*a+b-1)//b if 'time' in field or 'interval' in field else value*a//b
                        struct.pack_into('<i',row,off,scaled)
            if 'summon_interval_additional_multiplier' in u:
                # 附加倍率作用于既有召唤与修筑倍率处理后的计量；后续间隔包含计量零值的一帧。
                a,b=ratio(u['summon_interval_additional_multiplier'])
                for word in (38,39):
                    for off in anchor_offsets(word):
                        value=struct.unpack_from('<i',row,off)[0]
                        scaled=((value+1)*a+b-1)//b-1 if word==39 else (value*a+b-1)//b
                        struct.pack_into('<i',row,off,scaled)
            if u.get('normal_attack_range_from_projectile'):
                # 远距普通攻击的开火门槛采用已缩放的普通弹体目的距离。
                for destination,source in zip(anchor_offsets(7),anchor_offsets(26)):
                    row[destination:destination+4]=row[source:source+4]
                # 原生距离元数据随普通及特殊弹体行程共同更新。
                row[0x370:0x374]=row[26*4:27*4]
                row[0x374:0x378]=row[33*4:34*4]
            # SetUnitInfoParam 根据状态词 48/49 选择六档距离标签。
            for group,category in u.get('attack_range_categories',{}).items():
                struct.pack_into('<i',row,0x368 if group=='normal' else 0x36c,category)
            a,b=u['special_damage_multiplier']
            for off in (0x74,0xfc,0x180,0x204,0x288,0x30c):struct.pack_into('<i',row,off,struct.unpack_from('<i',row,off)[0]*a//b)
            # Native status IDs 24/31 map to status words 27/34.
            # These six anchors match getUnitStatus's level interpolation.
            # Production time and the special-readiness timer remain separate.
            a,b=u.get('attack_wait_multiplier',[1,1])
            for off in (0x6c,0xf8,0x17c,0x200,0x284,0x308,
                        0x88,0x110,0x194,0x218,0x29c,0x320):
                value=struct.unpack_from('<i',row,off)[0]
                struct.pack_into('<i',row,off,(value*a+b-1)//b)
            # 绝招冷却：词 35（每次绝招后）与词 36（出击后首次）的六个等级锚点按倍率向上取整。
            a,b=ratio(u.get('special_cooldown_multiplier',[1,1]))
            for word in (35,36):
                for off in anchor_offsets(word):
                    value=struct.unpack_from('<i',row,off)[0]
                    if value>0:struct.pack_into('<i',row,off,(value*a+b-1)//b)
            # 登记的状态词绝对值写入六个等级锚点（例如开火距离及脚本控制弹体的速度与目的距离）。
            for word,value in u.get('status_word_values',{}).items():
                for off in anchor_offsets(int(word)):struct.pack_into('<i',row,off,value)
            # 击退门槛为状态词 4（原生插值后乘 100 作为击退计量）；六个等级锚点按倍率四舍五入。
            # 非正值（原版 -1）表示每次受击均击退，计量不回填，该标记保持原值。
            a,b=u.get('knockback_threshold_multiplier',[1,1])
            for off in (0x10,0xb4,0x138,0x1bc,0x240,0x2c4):
                value=struct.unpack_from('<i',row,off)[0]
                if value>0:struct.pack_into('<i',row,off,(2*value*a+b)//(2*b))
            struct.pack_into('<i',row,0x378,u['faction']);rows+=row
            child_key=u.get('child_unit_key') or u.get('summoned_unit_key')
            if child_key:
                child=next(entry['id'] for entry in self.units if entry['key']==child_key)
                struct.pack_into('<I',rows,len(rows)-0x390+0xa4,child)
            action=p.word(actions+bid*4)
            if 'shot_action_reference_id' in u:
                reference=p.word(actions+u['shot_action_reference_id']*4)
                methods=bytearray(p.read(p.word(action),40))
                methods[8:12]=p.read(p.word(reference)+8,4)
                action=self.alloc(struct.pack('<I',self.alloc(methods)))
            action_rows+=struct.pack('<I',action)
            descriptor=p.word(table+bid*8);header=bytearray(p.read(descriptor,32))
            textures=u.get('textures',[u.get('texture')]);image_count=p.word(descriptor)
            desc=self.sprite_descriptors.get(u['key'])
            if desc:image_count=len(textures)
            if not 1<=image_count<=16 or len(textures)!=image_count:raise ValueError('Texture bindings must match the unit atlas count')
            struct.pack_into('<I',header,0,image_count)
            struct.pack_into('<I',header,4,self.alloc(struct.pack('<'+'I'*image_count,*[p.cstr(t) for t in textures])))
            count=p.word(descriptor+28);scripts=list(struct.unpack('<'+'I'*count,p.read(p.word(descriptor+24),count*4)))
            if desc:
                raw_rects=b''.join(struct.pack('<8h',*r) for r in desc['rects'])
                # 原生绘制函数按 uint32_t 读取帧条目；矩形描述符仍采用 int16_t。
                raw_frames=struct.pack('<'+'I'*len(desc['frames']),*desc['frames'])
                raw_hits=b''.join(struct.pack('<5i',*r) for r in desc['hit_bounds'])
                raw_attacks=b''.join(struct.pack('<5i',*r) for r in desc['attack_bounds'])
                blob=self.alloc(raw_rects+raw_frames+raw_hits+raw_attacks)
                struct.pack_into('<4I',header,8,blob,blob+len(raw_rects),blob+len(raw_rects)+len(raw_frames),blob+len(raw_rects)+len(raw_frames)+len(raw_hits))
                count=desc['script_count']
                scripts=(scripts+[self.alloc(struct.pack('<i',5))]*max(0,count-len(scripts)))[:count]
                struct.pack_into('<I',header,28,count)
            for key,commands in u['animations'].items():
                if not 0<=int(key)<count:raise ValueError('Animation index outside base unit descriptor')
                values=[v for cmd in content_sounds.resolve_animation(commands,self.sound_ids) for v in [cmd['opcode'],*cmd['values']]]
                scripts[int(key)]=self.alloc(struct.pack('<'+'i'*len(values),*values))
            struct.pack_into('<I',header,24,self.alloc(struct.pack('<'+'I'*count,*scripts)))
            images+=struct.pack('<II',self.alloc(header),p.word(table+bid*8+4))
            menu_bid=u.get('menu_reference_id',bid)
            menurow=p.read(menu_rows[menu_bid],20)
            # 原生修筑单位分别登记生产入口与完成箱体的界面预览标识。
            preview_id=next(entry['id'] for entry in self.units if entry['key']==u['preview_unit_key']) if u.get('preview_unit_key') else uid
            menurow=bytearray(menurow);struct.pack_into('<II',menurow,0,uid,preview_id)
            struct.pack_into('<h',menurow,8,u['faction']);struct.pack_into('<h',menurow,10,u['icon']['index'])
            shoprow=bytearray(p.read(shopbase+23*32,32));struct.pack_into('<H',shoprow,0,512+i)
            struct.pack_into('<I',shoprow,4,uid);struct.pack_into('<h',shoprow,16,u['shop_price'])
            data=self.progress['units'].get(u['key'],{})
            level=int(data.get('level',-1));opened=int(data.get('level_open',20))
            if not -1<=level<=39 or not 0<=opened<=40:raise ValueError('Invalid community unit progress')
            # 原版初购保存上限为 20；兼容此前写入世界即时上限 10 的进度。
            opened=max(20,opened)
            values=(uid,bid,512+i,self.alloc(menurow),self.alloc(shoprow),423+i,level&0xffffffff,opened,int(data.get('custom_time',0)),int(data.get('new',0)),int(data.get('shop_new',0)),u['shop_price'])
            struct.pack_into('<12I',records,i*RECORD_SIZE,*values)
            struct.pack_into('<I',records,i*RECORD_SIZE+0x88,int(data.get('deck_time',0)))
            struct.pack_into('<I',records,i*RECORD_SIZE+0x8c,int(u.get('internal_only',False)))
            for code,text in u['localization'].items():
                lang=language_order[p.symbols['strMenuUnitInfo'+code]]
                for offset,field in ((0x30,'name'),(0x5c,'description')):struct.pack_into('<I',records,i*RECORD_SIZE+offset+lang*4,p.cstr(text[field]))
        self.records=self.alloc(records);p.put(db+4,self.alloc(rows));p.put(db+8,UNIT_ID_BASE+n)
        p.put(actions_global,self.alloc(action_rows));imageptr=self.alloc(images)
        factory=p.call('_ZN19BattleSpriteFactory11getInstanceEv');cache=p.word(factory+0xe108)
        p.put(factory+0xe108,self.alloc(p.read(cache,423*4)+bytes(n*4)))
        # Stock UI sprites remain independent; custom IDs need additional cells.
        # Custom uses fifty visible panels; Deck uses ten slots. Main-menu and
        # shop preview caches are indexed by UID and require sparse allocation.
        for name in ('m_MainMenuObject','m_MenuShopBattleObject'):
            if name not in p.symbols:raise RuntimeError('Missing native UID preview cache: '+name)
            old=p.symbols[name]
            size=next(s['st_size'] for s in p.elf.get_section_by_name('.dynsym').iter_symbols() if s.name==name)
            if size!=ORIGINAL_UNITS*4:raise RuntimeError('Unexpected native UI pointer array size: '+name)
            self.replace_global(old,self.alloc(p.read(old,size)+bytes((UNIT_ID_BASE+n)*4-size)))
        # Append icon rectangles; keep all 340 original entries unchanged.
        # 占位槽位沿用原版图标条目 3 的矩形（该槽位不进入任何列表）。
        conv=p.symbols['ConvUnitIcon'];rects=bytearray(p.read(conv,340*16))
        battle_icons=bytearray();placeholder_icon=p.read(conv+3*16,16)
        for u in self.slots:
            if u is None:rect=placeholder_icon
            else:ic=u['icon'];rect=struct.pack('<8h',*ic['rect'],*ic['anchor'],0,ic['page'])
            rects+=rect;battle_icons+=rect
        self.icon_conv=self.alloc(rects);self.icon_references=self.replace_global(conv,self.icon_conv)
        p.log('COMMUNITY_ICON_REFERENCES',[(hex(a),p.read(a-8,24).hex()) for a in self.icon_references])
        # Each menu picture also has an action-offset map and a terminated
        # rectangle script. Extending rectangles alone leaves ID 340 blank.
        offsets=bytearray(p.read(0x10305fcc,340*2));icon_scripts=bytearray(p.read(0x10305a7c,340*4))
        for i in range(n):
            offsets+=struct.pack('<H',(340+i)*2)
            icon_scripts+=struct.pack('<hh',340+i,-1)
        self.icon_offsets=self.alloc(offsets);self.icon_scripts=self.alloc(icon_scripts)
        # Obtain the native unit-shop list's PC-relative root.
        # The add-PC at 0x20bb9c uses the literal at 0x20bee4.
        catalog_base=(p.word(0x1020bee4)+0x1020bba0)&0xffffffff
        self.catalog_source=catalog_base
        catalog=p.read(catalog_base+0x74,259*4)
        shop_ids=[512+i for i,u in enumerate(self.slots) if u is not None and not u.get('internal_only') and not u.get('world_clear_reward')]
        pack_pointer=0
        if self.unit_pack:
            pack=self.unit_pack;shop_ids.append(pack['shop_id'])
            raw=bytearray(p.read(shopbase+16*32,32))+bytearray(96)
            struct.pack_into('<H',raw,0,pack['shop_id']);struct.pack_into('<I',raw,4,pack['id'])
            struct.pack_into('<h',raw,16,pack['shop_price'])
            member_ids=[next(u['id'] for u in self.units if u['key']==key) for key in pack['units']]
            individual_price=sum(next(u['shop_price'] for u in self.units if u['key']==key) for key in pack['units'])
            struct.pack_into('<h',raw,24,max(0,(individual_price-pack['shop_price'])*100//individual_price))
            struct.pack_into('<II',raw,32,len(member_ids),self.alloc(struct.pack('<'+'I'*len(member_ids),*member_ids)))
            for code,text in pack['localization'].items():
                lang=language_order[p.symbols['strMenuUnitInfo'+code]]
                for offset,field in ((40,'name'),(84,'description')):struct.pack_into('<I',raw,offset+lang*4,p.cstr(text[field]))
            pack_pointer=self.alloc(raw)
        self.shop_catalog=self.alloc(catalog+struct.pack('<'+'I'*len(shop_ids),*shop_ids))
        # 已拥有单位紧凑列表：原版 399 个加全部社区槽位，最少沿用原有 512 个 int32；取 8 的倍数（原生栈暂存表按此长度，保持 8 字节对齐）。
        self.owned_list_capacity=max(OWNED_LIST_MIN,(ORIGINAL_UNITS+n+7)//8*8)
        self.app=p.app_instance();self.custom_list=self.alloc(bytes(self.owned_list_capacity*4));self.deck_list=self.alloc(bytes(self.owned_list_capacity*4))
        import community_maps
        stage_pointer,stage_count,mission_count=community_maps.install(self,info,db)
        fields=(0x434f4d32,n,self.records,UNIT_ID_BASE+n,423+n,imageptr,0,self.app,self.custom_list,self.deck_list,self.owned_list_capacity,self.shop_catalog,259+len(shop_ids),self.alloc(battle_icons),self.icon_offsets,self.icon_scripts,stage_pointer,stage_count,mission_count)
        units=self.slots;empty={}
        profiles=bytearray()
        for u in units:
            u=u or empty
            values=[ratio(u['hp_multiplier']) if isinstance(u.get('hp_multiplier'),list) else (1,1)]
            values.extend(ratio(u.get(key,[1,1])) for key in ('damage_multiplier','move_speed_multiplier',
                'attack_range_multiplier','knockback_distance_multiplier','ballistic_range_multiplier'))
            profiles+=struct.pack('<12I',*(v for pair in values for v in pair))
        # 原生商城许可对参考值 >=512 返回关闭；免费通关奖励同时从商城目录排除；占位槽位关闭。
        unlocks=struct.pack('<'+'I'*n,*(512 if u is None or u.get('world_clear_reward') else 0xffffffff if u['available_from_start'] else u['shop_unlock_reference_id'] for u in units))
        fields+= (self.alloc(profiles),1,p.symbols['_ZTV10BattleUnit']+8,p.symbols['_ZTV12BattleBullet']+8,self.alloc(unlocks))
        landing_ids={u['key']:u['id'] for u in self.units}
        landings=struct.pack('<'+'I'*n,*(landing_ids[u['landing_unit_key']] if u and u.get('landing_unit_key') else 0 for u in units))
        display_ids=struct.pack('<'+'I'*n,*(landing_ids[u['child_unit_key']] if u and u.get('child_unit_key') else UNIT_ID_BASE+i for i,u in enumerate(units)))
        fields+=(pack_pointer,self.alloc(landings),self.alloc(display_ids))
        recoveries=struct.pack('<'+'I'*n,*((u or empty).get('recovery_animation',26) for u in units))
        fields+=(self.alloc(recoveries),)
        # 喷火受击收尾与单次击退限制：每单位 8 词（标记、喷火起点与时长 tick、收尾受击槽起点、四个收尾弹体动画）。
        flames=bytearray()
        for u in units:
            f=(u or empty).get('flame_interrupt')
            if f:flames+=struct.pack('<8I',1|(2 if f['knockback_limit_per_special'] else 0),f['flame_start_tick'],f['flame_ticks'],f['alternate_knockback_animation'],*f['ending_bullet_animations'])
            else:flames+=bytes(32)
        fields+=(self.alloc(flames),)
        # 头部偏移 116：逐单位行为标记。位 0 地面绝招（复用原生冲刺单位的地形移动流程），
        # 位 1 保留强化武器（原生按基准角色类处理，见 src/aot_runtime.cpp）。
        grounded=struct.pack('<'+'I'*n,*(int((u or empty).get('ground_special_attack',False))|2*int((u or empty).get('retained_special_weapon',False)) for u in units))
        fields+=(self.alloc(grounded),)
        # 头部偏移 120/124：多页图标的页表与页数（无图标页时为 0）。
        self.icon_page_table=self.icon_page_desc=0;self.icon_page_infos=[]
        if self.icon_pages:
            info=p.read(MENU_IMAGE_TABLE+MENU_IMAGE_UNIT_ICON_02*12,12)
            table=bytearray()
            for _,atlas in self.icon_pages:
                name=p.cstr(atlas)
                table+=struct.pack('<4I',name,0,0,0)
                self.icon_page_infos.append(self.alloc(struct.pack('<I',name)+info[4:]))
            self.icon_page_table=self.alloc(table)
            # 战斗面板共用的页 ImageDesc：原生每次换页时重新载入，同一时刻只占一页像素。
            self.icon_page_desc=p.alloc(IMAGE_DESC_SIZE);p.call('_ZN9ImageDescC1Ev',self.icon_page_desc)
        # 头部偏移 128：扩展 ConvUnitIcon 的地址（原生绘制以矩形是否落在社区段判定图标页）；
        # 132/136：战斗面板共用的页 ImageDesc 与其中当前载入的页号（0xffffffff 为无）。
        fields+=(self.icon_page_table,len(self.icon_pages),self.icon_conv if self.icon_pages else 0,
                 self.icon_page_desc,0xffffffff if self.icon_pages else 0)
        # 头部偏移 140/144：保留武器诊断计数（原生累加）；148：原版单位倍率组指针表（400 项，未修改的为 0；无原版补丁时为 0）。
        stock_table=0
        if any(PROFILE_FIELDS&set(f) for f in stock_patches.values()):
            pointers=[0]*400
            for uid,f in stock_patches.items():
                if PROFILE_FIELDS&set(f):
                    pairs=[ratio(f.get(key,[1,1])) for key in PROFILE_ORDER]
                    pointers[uid]=self.alloc(struct.pack('<12I',*(v for pair in pairs for v in pair)))
            stock_table=self.alloc(struct.pack('<400I',*pointers))
        fields+=(0,0,stock_table)
        # 头部偏移 152/156：自定义音效的 SoundID → 记录指针表（1032 项）与登记数（M6；无音效时为 0）。
        fields+=content_sounds.install(self,self.sounds,self.sound_ids)
        p.write(HEADER,struct.pack('<%dI'%len(fields),*fields));self.ready=True
        self.map_initial_choices_applied=not (self.manifest.get('missions') or self.manifest.get('campaign_choices'))
        assert p.read(p.word(db+4),400*0x390)==bytes(rows[:400*0x390])
        p.log('COMMUNITY_REGISTERED',n,'unit IDs',[u['id'] for u in self.units])

    def grant_world_clear_rewards(self):
        p=self.p
        # 奖励在已加载进度的常规菜单中协调；LAB 隔离期间保留社区进度。
        if not self.ready or p.word(self.app+0x22bc)!=28 or getattr(getattr(p,'lab',None),'sandbox',False):return
        for u in self.units:
            i=u['id']-UNIT_ID_BASE
            reward=u.get('world_clear_reward')
            if reward is None or struct.unpack('<i',p.read(self.records+i*RECORD_SIZE+24,4))[0]!=-1:continue
            if not p.call('_Z19IsAreaClearSaveDataii9WorldType',reward['world'],reward['area'],reward['world_type']):continue
            p.call('_ZN7AppMain20SetUnitLevelSaveDataE6UnitIDi',self.app,u['id'],0)
            # 既有开放阶段保留，等级上限及阵营核心权限由原生接口协调。
            p.call('_ZN7AppMain24GetUnitLevelOpenSaveDataE6UnitID',self.app,u['id'])
            p.call('_ZN7AppMain21AddUnitNewFlgSaveDataE6UnitID',self.app,u['id'])
            p.log('COMMUNITY_WORLD_CLEAR_REWARD',u['key'],reward['world'],reward['area'],reward['world_type'])

    def sync_icon_pages(self):
        """多页图标的纹理与战斗图源：原生绘制请求的页（标记位 0）在下一帧前创建纹理，场景切换时释放（原生菜单图像同样按场景载入与释放）；
        战斗面板用过的共用 ImageDesc 在下一帧释放（面板已合成到自身图像）。"""
        p=self.p
        if not self.ready or not self.icon_page_table:return
        scene=p.word(self.app+0x22bc);changed=scene!=getattr(self,'icon_page_scene',None);self.icon_page_scene=scene
        if p.word(self.icon_page_desc):
            p.call('_ZN9ImageDesc7releaseEv',self.icon_page_desc);p.put(HEADER+136,0xffffffff)
        for i in range(len(self.icon_pages)):
            entry=self.icon_page_table+i*ICON_PAGE_ENTRY
            image,flags=p.word(entry+4),p.word(entry+12)
            if image and changed:
                p.call(p.word(p.word(image)+4),image);p.put(entry+4,0);image=0
            if flags&1 and not image:
                info=self.icon_page_infos[i]
                image=p.call('_ZN5Image11createImageEPKciiPhi',p.word(info),0x50a if p.read(info+5,1)[0] else 0x505,p.word(info+8),0,0xffffffff)
                if image:
                    p.call('_ZN10OGLTexture21setTransparentEnabledEh',image,p.read(info+4,1)[0])
                    p.call('_ZN10OGLTexture11setFileInfoEPK13ImageDataInfo',image,info)
                    p.put(entry+4,image)
                p.log('COMMUNITY_ICON_PAGE_LOADED',self.icon_pages[i][1],hex(image))
            if flags:p.put(entry+12,0)

    def flush(self):
        p=self.p
        # 关闭窗口时停止事件已设置，原生调用会被 Probe.call 取消；此时只写社区进度（只读内存），
        # 奖励协调、图标页、旧编队迁移与地图初始选择留待下次启动。
        stopping=getattr(p,'stop_event',None) is not None and p.stop_event.is_set()
        if not stopping:
            self.sync_icon_pages()
            self.grant_world_clear_rewards()
            if self.ready and not self.deck_migration_done and p.word(self.app+0x22bc)==28:
                self.migrate_legacy_decks()
            if self.ready and self.deck_migration_done and not self.decks_reconciled and p.word(self.app+0x22bc)==28:
                self.reconcile_decks()
            if self.ready and not self.map_initial_choices_applied and p.word(self.app+0x22bc)==28:
                import community_maps
                community_maps.enable_initial_choices(self);self.map_initial_choices_applied=True
        if not self.ready or not p.word(HEADER+24):return
        for u in self.units:
            i=u['id']-UNIT_ID_BASE
            values=struct.unpack('<5I',p.read(self.records+i*RECORD_SIZE+24,20))
            self.progress['units'][u['key']]={'id':u['id'],'level':struct.unpack('<i',struct.pack('<I',values[0]))[0],
             'level_open':values[1],'custom_time':values[2],'new':values[3],'shop_new':values[4],
             'deck_time':p.word(self.records+i*RECORD_SIZE+0x88)}
        temporary=self.path.with_suffix('.json.tmp')
        with temporary.open('w',encoding='utf-8') as stream:
            json.dump(self.progress,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,self.path);p.put(HEADER+24,0)

    def deck_address(self,deck,slot):
        # 原生 Get/SetDeckUnitSaveData：第 0 组位于 app+0x4ed0，第 1、2 组位于 app+0x8830 起每组 10 格；空格为 -1。
        return self.app+(0x13b4+slot if deck==0 else 0x220c+10*(deck-1)+slot)*4

    def reconcile_decks(self):
        """模组启停后的原生编队协调（M4），只改内存中的编队，原生正常保存时写入：
        - 编队格的社区 UnitID 按社区进度记录的“ID → 稳定键”核对；单位仍载入但 ID 已变的改写为当前 ID；
        - 单位未载入（模组停用、卸载或校验失败）的格改为空格（-1），原值以稳定键记入社区进度 parked_deck_slots；
        - 已记录的格在单位重新载入、已拥有、该格仍为空且同组没有该单位时恢复，其余情况保留记录（单位未载入）或放弃（格已被占用）。"""
        p=self.p;by_key={u['key']:u for u in self.units};by_id={u['id']:u for u in self.units}
        saved_key={}
        for key,data in self.progress['units'].items():
            if isinstance(data,dict) and isinstance(data.get('id'),int):saved_key.setdefault(data['id'],key)
        owned=lambda u:struct.unpack('<i',p.read(self.records+(u['id']-UNIT_ID_BASE)*RECORD_SIZE+24,4))[0]>=0
        held=[e for e in self.progress.get('parked_deck_slots',[]) if isinstance(e,dict)]
        kept,events=[],[]
        for deck in range(3):
            for slot in range(10):
                a=self.deck_address(deck,slot);uid=struct.unpack('<i',p.read(a,4))[0]
                if uid<UNIT_ID_BASE:continue
                unit=by_id.get(uid);key=saved_key.get(uid)
                if unit is not None and not unit.get('internal_only') and (key in (None,unit['key'])
                        or self.progress['units'].get(unit['key'],{}).get('id')==uid):continue
                target=by_key.get(key) if key else None
                if target is not None and not target.get('internal_only'):
                    p.put(a,target['id']);events.append(('remapped',deck,slot,uid,target['id'],key))
                else:
                    p.put(a,0xffffffff);kept.append({'deck':deck,'slot':slot,'key':key,'id':uid})
                    events.append(('parked',deck,slot,uid,key))
        for entry in held:
            deck,slot,key=entry.get('deck'),entry.get('slot'),entry.get('key')
            if deck not in range(3) or slot not in range(10) or any(k['deck']==deck and k['slot']==slot for k in kept):continue
            unit=by_key.get(key) if key else None
            if unit is None:
                kept.append(entry)            # 单位仍未载入：保留记录
                continue
            a=self.deck_address(deck,slot)
            same_deck=[struct.unpack('<i',p.read(self.deck_address(deck,s),4))[0] for s in range(10)]
            if same_deck[slot]==-1 and unit['id'] not in same_deck and owned(unit) and not unit.get('internal_only'):
                p.put(a,unit['id']);events.append(('restored',deck,slot,unit['id'],key))
            else:
                events.append(('dropped',deck,slot,key))
        changed=kept!=held or events
        self.progress['parked_deck_slots']=kept
        self.decks_reconciled=True
        if changed:p.put(HEADER+24,1)
        p.log('COMMUNITY_DECK_RECONCILE',events,len(kept))

    def migrate_legacy_decks(self):
        # Migrate only in-memory loaded decks; ordinary game saves persist them.
        # The original test.dat and sidecar are never rewritten by an installer.
        p=self.p;changed=[]
        for deck in range(3):
            for slot in range(10):
                old=p.call('_ZN7AppMain19GetDeckUnitSaveDataEii',self.app,slot,deck)
                if old in self.legacy_ids:
                    new=self.legacy_ids[old]
                    p.call('_ZN7AppMain19SetDeckUnitSaveDataEi6UnitIDi',self.app,slot,new,deck)
                    changed.append({'deck':deck,'slot':slot,'old':old,'new':new})
        self.deck_migration_done=True
        p.put(HEADER+24,1)
        p.log('COMMUNITY_LEGACY_DECK_MIGRATION',changed)
