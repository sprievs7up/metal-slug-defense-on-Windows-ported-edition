"""Register additive native content and persist its progress per save profile."""
from pathlib import Path
import json,struct,hashlib,io,os

HEADER=0x1ffee000
RECORD_SIZE=0x90
MAX_UNITS=64
UNIT_ID_BASE=1024
ORIGINAL_UNITS=400
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

class CommunityContent:
    def __init__(self,p,root=None):
        self.p=p
        self.root=Path(root or Path(__file__).resolve().parent/'community_content')
        self.manifest=json.loads((self.root/'registry.json').read_text(encoding='utf-8'))
        if self.manifest.get('schema')!=2:raise ValueError('Unsupported community content schema')
        if self.manifest.get('unit_id_base')!=UNIT_ID_BASE:raise ValueError('Unsafe community unit namespace')
        self.units=self.manifest['units']
        if not 0<len(self.units)<=MAX_UNITS:raise ValueError('Community unit capacity exceeded')
        keys=set()
        for i,u in enumerate(self.units):
            if not isinstance(u['key'],str) or not u['key'] or '\0' in u['key']:raise ValueError('Invalid stable unit key')
            if u['id']!=UNIT_ID_BASE+i or u['key'] in keys:raise ValueError('Unstable or duplicate community unit identity')
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
            if u['icon']['index']!=340+i:raise ValueError('Non-contiguous community icon identity')
            if u['icon']['page']!=1:raise ValueError('Community icons must use unit_icon_02')
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
                    if any(not isinstance(v,int) or not -2147483648<=v<=2147483647 for v in values):raise ValueError('Invalid animation command value')
            keys.add(u['key'])
        by_key={u['key']:u for u in self.units}
        for u in self.units:
            if not isinstance(u.get('internal_only',False),bool):raise ValueError('Invalid internal unit flag')
            child=u.get('child_unit_key')
            if child is not None and (child not in by_key or not by_key[child].get('internal_only') or child==u['key']):raise ValueError('Invalid internal child reference')
            landing=u.get('landing_unit_key')
            if landing is not None and (u['base_id']!=160 or landing not in by_key or by_key[landing].get('internal_only')):raise ValueError('Invalid paratrooper landing reference')
            summoned=u.get('summoned_unit_key')
            if summoned is not None and (u['base_id']!=64 or summoned not in by_key or summoned==u['key'] or by_key[summoned].get('internal_only')):raise ValueError('Invalid mummy gate summon reference')
            preview=u.get('preview_unit_key')
            if preview is not None and (preview!=child or preview not in by_key):raise ValueError('Invalid unit preview reference')
        self.unit_pack=self.manifest.get('unit_pack')
        if self.unit_pack:
            pack=self.unit_pack
            if pack.get('id')!=10 or pack.get('shop_id')!=512+MAX_UNITS:raise ValueError('Invalid community pack identity')
            if not isinstance(pack.get('shop_price'),int) or not 0<pack['shop_price']<=32767:raise ValueError('Invalid community pack price')
            if not 1<=len(pack.get('units',[]))<=7 or len(set(pack['units']))!=len(pack['units']):raise ValueError('Invalid community pack members')
            if any(key not in by_key or by_key[key].get('internal_only') for key in pack['units']):raise ValueError('Invalid community pack unit')
            if set(pack.get('localization',{}))!=LANGUAGES:raise ValueError('All eleven pack localizations are required')
            if any(not isinstance(text.get(field),str) or not text[field] or '\0' in text[field] for text in pack['localization'].values() for field in ('name','description')):raise ValueError('Invalid pack text')
        self.assets={};self.asset_dimensions={}
        for name,digest in self.manifest['assets'].items():
            if Path(name).name!=name or not name.lower().endswith('.obm'):raise ValueError('Invalid content asset name')
            raw=(self.root/name).read_bytes()
            if digest is not None and hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Content asset checksum mismatch: '+name)
            if len(raw)<8 or raw[:2]!=b'OI':raise ValueError('Unsupported content texture header: '+name)
            width,height=struct.unpack_from('<HH',raw,4);kind,bits=raw[2:4]
            if kind==1 and bits==4:expected=8+64+(width*height+1)//2
            elif kind in (1,4) and bits==8:expected=8+(1024 if kind==1 else 512)+width*height
            elif kind in (0,1) and bits in (24,32):expected=8+width*height*(3 if kind==0 else 4)
            else:raise ValueError('Unsupported content texture format: '+name)
            if not 0<width<=8192 or not 0<height<=8192 or len(raw)!=expected:raise ValueError('Invalid content texture dimensions or byte count: '+name)
            self.asset_dimensions[name]=(width,height)
            self.assets[name]=raw
        self.sprite_descriptors={}
        for u in self.units:
            for name in u.get('textures',[u.get('texture')]):
                if name not in self.assets:raise ValueError('Unregistered unit texture')
            if 'unit_icon_02.obm' not in self.assets:raise ValueError('Missing community icon atlas')
            width,height=self.asset_dimensions['unit_icon_02.obm'];x,y,w,h=u['icon']['rect']
            if x+w>width or y+h>height:raise ValueError('Icon rectangle outside its atlas')
            filename=u.get('sprite_descriptor')
            if filename:
                if Path(filename).name!=filename or not filename.endswith('.json'):raise ValueError('Invalid sprite descriptor path')
                desc=json.loads((self.root/filename).read_text(encoding='utf-8'))
                rects=desc['rects'];frames=desc['frames'];textures=u.get('textures',[u.get('texture')])
                if not 1<=len(rects)<=8192 or not 1<=len(frames)<=65536 or not 1<=desc['script_count']<=256:raise ValueError('Invalid sprite descriptor capacity')
                for x,y,w,h,ax,ay,flags,page in rects:
                    if any(not isinstance(v,int) or not -32768<=v<=32767 for v in (x,y,w,h,ax,ay,flags,page)) or not 0<=page<len(textures):raise ValueError('Invalid sprite rectangle')
                    width,height=self.asset_dimensions[textures[page]]
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
                self.sprite_descriptors[u['key']]=desc
            flame=u.get('flame_interrupt')
            if flame and (flame['alternate_knockback_animation']+5>desc['script_count'] or any(v>=desc['script_count'] for v in flame['ending_bullet_animations'])):raise ValueError('Flame interruption animation outside sprite descriptor')
            if 'recovery_animation' in u:
                value=u['recovery_animation']
                if u['base_id']!=61 or not filename or not isinstance(value,int) or isinstance(value,bool) or not 0<=value<desc['script_count']:raise ValueError('Invalid mummy recovery animation')
        from campaign_catalog import merge_scenes
        merge_scenes(self)
        import community_maps
        community_maps.validate(self.manifest,self.assets)
        self.overridden_assets=set()
        self.path=p.saves/'community_progress.json'
        self.progress=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'schema':1,'units':{}}
        if self.progress.get('schema')!=1:raise ValueError('Unsupported community progress schema')
        self.legacy_ids={}
        for i,u in enumerate(self.units):
            saved=self.progress['units'].get(u['key'],{})
            previous=saved.get('id',u['id'])
            if previous!=u['id']:
                if previous!=400+i:raise ValueError('Unsupported legacy unit identity')
                self.legacy_ids[previous]=u['id']
        self.deck_migration_done=not self.legacy_ids
        self.original_filecall=p.filecall
        def filecall(name,args):
            leaf=Path(p.string(args[0])).name if name=='fopen' else None
            if leaf in self.assets and p.string(args[1]).startswith('r'):
                self.overridden_assets.add(leaf)
                handle=p.alloc(16);p.handles[handle]=io.BytesIO(self.assets[leaf]);return handle
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
        if any(u.get('ground_special_attack') for u in self.units) and (not hasattr(p.uc.lib,'msd_community_ground_special_version') or p.uc.lib.msd_community_ground_special_version()!=1):raise RuntimeError('Native core lacks grounded special attacks')
        p.uc.lib.msd_enable_community_content()
        self.ready=False

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
        p=self.p;n=len(self.units);info=p.call('_ZN10BattleInfo11getInstanceEv');db=p.word(info)
        if p.word(db+8)!=400:raise RuntimeError('Unexpected original unit table size')
        base=p.word(db+4);original=p.read(base,400*0x390);rows=bytearray(original)+bytearray((UNIT_ID_BASE-400)*0x390)
        self.original_rows=hashlib.sha256(original).hexdigest()
        table=0x10922f28;original_images=p.read(table,423*8);images=bytearray(original_images)
        actions_global=0x109373f4;actions=p.word(actions_global);action_rows=bytearray(p.read(actions,400*4))+bytearray((UNIT_ID_BASE-400)*4)
        menu=(p.word(0x101652d0)+0x101652b4+0x818)&0xffffffff
        shopbase=(p.word(0x101655d8)+0x101655ce+0x19c)&0xffffffff
        language_table=p.symbols['strMenuUnitInfoTbl']
        language_order={p.word(language_table+i*4):i for i in range(11)}
        records=bytearray(n*RECORD_SIZE)
        for i,u in enumerate(self.units):
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
                values=[v for cmd in commands for v in [cmd['opcode'],*cmd['values']]]
                scripts[int(key)]=self.alloc(struct.pack('<'+'i'*len(values),*values))
            struct.pack_into('<I',header,24,self.alloc(struct.pack('<'+'I'*count,*scripts)))
            images+=struct.pack('<II',self.alloc(header),p.word(table+bid*8+4))
            menu_bid=u.get('menu_reference_id',bid)
            menurow=next(p.read(menu+j*20,20) for j in range(320) if p.word(menu+j*20)==menu_bid)
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
        conv=p.symbols['ConvUnitIcon'];rects=bytearray(p.read(conv,340*16))
        battle_icons=bytearray()
        for u in self.units:
            ic=u['icon'];rect=struct.pack('<8h',*ic['rect'],*ic['anchor'],0,ic['page']);rects+=rect;battle_icons+=rect
        self.icon_references=self.replace_global(conv,self.alloc(rects))
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
        shop_ids=[512+i for i,u in enumerate(self.units) if not u.get('internal_only') and not u.get('world_clear_reward')]
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
        self.app=p.app_instance();self.custom_list=self.alloc(bytes(512*4));self.deck_list=self.alloc(bytes(512*4))
        import community_maps
        stage_pointer,stage_count,mission_count=community_maps.install(self,info,db)
        fields=(0x434f4d32,n,self.records,UNIT_ID_BASE+n,423+n,imageptr,0,self.app,self.custom_list,self.deck_list,512,self.shop_catalog,259+len(shop_ids),self.alloc(battle_icons),self.icon_offsets,self.icon_scripts,stage_pointer,stage_count,mission_count)
        profiles=bytearray()
        for u in self.units:
            values=[ratio(u['hp_multiplier']) if isinstance(u['hp_multiplier'],list) else (1,1)]
            values.extend(ratio(u.get(key,[1,1])) for key in ('damage_multiplier','move_speed_multiplier',
                'attack_range_multiplier','knockback_distance_multiplier','ballistic_range_multiplier'))
            profiles+=struct.pack('<12I',*(v for pair in values for v in pair))
        # 原生商城许可对参考值 >=512 返回关闭；免费通关奖励同时从商城目录排除。
        unlocks=struct.pack('<'+'I'*n,*(512 if u.get('world_clear_reward') else 0xffffffff if u['available_from_start'] else u['shop_unlock_reference_id'] for u in self.units))
        fields+= (self.alloc(profiles),1,p.symbols['_ZTV10BattleUnit']+8,p.symbols['_ZTV12BattleBullet']+8,self.alloc(unlocks))
        landing_ids={u['key']:u['id'] for u in self.units}
        landings=struct.pack('<'+'I'*n,*(landing_ids[u['landing_unit_key']] if u.get('landing_unit_key') else 0 for u in self.units))
        display_ids=struct.pack('<'+'I'*n,*(landing_ids[u['child_unit_key']] if u.get('child_unit_key') else u['id'] for u in self.units))
        fields+=(pack_pointer,self.alloc(landings),self.alloc(display_ids))
        recoveries=struct.pack('<'+'I'*n,*(u.get('recovery_animation',26) for u in self.units))
        fields+=(self.alloc(recoveries),)
        # 喷火受击收尾与单次击退限制：每单位 8 词（标记、喷火起点与时长 tick、收尾受击槽起点、四个收尾弹体动画）。
        flames=bytearray()
        for u in self.units:
            f=u.get('flame_interrupt')
            if f:flames+=struct.pack('<8I',1|(2 if f['knockback_limit_per_special'] else 0),f['flame_start_tick'],f['flame_ticks'],f['alternate_knockback_animation'],*f['ending_bullet_animations'])
            else:flames+=bytes(32)
        fields+=(self.alloc(flames),)
        # 头部偏移 116：逐单位地面绝招标记，复用原生冲刺单位的地形移动流程。
        grounded=struct.pack('<'+'I'*n,*(int(u.get('ground_special_attack',False)) for u in self.units))
        fields+=(self.alloc(grounded),)
        p.write(HEADER,struct.pack('<%dI'%len(fields),*fields));self.ready=True
        self.map_initial_choices_applied=not (self.manifest.get('missions') or self.manifest.get('campaign_choices'))
        assert p.read(p.word(db+4),400*0x390)==original
        p.log('COMMUNITY_REGISTERED',n,'unit IDs',[u['id'] for u in self.units])

    def grant_world_clear_rewards(self):
        p=self.p
        # 奖励在已加载进度的常规菜单中协调；LAB 隔离期间保留社区进度。
        if not self.ready or p.word(self.app+0x22bc)!=28 or getattr(getattr(p,'lab',None),'sandbox',False):return
        for i,u in enumerate(self.units):
            reward=u.get('world_clear_reward')
            if reward is None or struct.unpack('<i',p.read(self.records+i*RECORD_SIZE+24,4))[0]!=-1:continue
            if not p.call('_Z19IsAreaClearSaveDataii9WorldType',reward['world'],reward['area'],reward['world_type']):continue
            p.call('_ZN7AppMain20SetUnitLevelSaveDataE6UnitIDi',self.app,u['id'],0)
            # 既有开放阶段保留，等级上限及阵营核心权限由原生接口协调。
            p.call('_ZN7AppMain24GetUnitLevelOpenSaveDataE6UnitID',self.app,u['id'])
            p.call('_ZN7AppMain21AddUnitNewFlgSaveDataE6UnitID',self.app,u['id'])
            p.log('COMMUNITY_WORLD_CLEAR_REWARD',u['key'],reward['world'],reward['area'],reward['world_type'])

    def flush(self):
        p=self.p
        self.grant_world_clear_rewards()
        if self.ready and not self.deck_migration_done and p.word(self.app+0x22bc)==28:
            self.migrate_legacy_decks()
        if self.ready and not self.map_initial_choices_applied and p.word(self.app+0x22bc)==28:
            import community_maps
            community_maps.enable_initial_choices(self);self.map_initial_choices_applied=True
        if not self.ready or not p.word(HEADER+24):return
        for i,u in enumerate(self.units):
            values=struct.unpack('<5I',p.read(self.records+i*RECORD_SIZE+24,20))
            self.progress['units'][u['key']]={'id':u['id'],'level':struct.unpack('<i',struct.pack('<I',values[0]))[0],
             'level_open':values[1],'custom_time':values[2],'new':values[3],'shop_new':values[4],
             'deck_time':p.word(self.records+i*RECORD_SIZE+0x88)}
        temporary=self.path.with_suffix('.json.tmp')
        with temporary.open('w',encoding='utf-8') as stream:
            json.dump(self.progress,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,self.path);p.put(HEADER+24,0)

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
