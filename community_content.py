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


# 修筑类单位（原生动作类 BattleAction_Kouhei）的生命方式（2026-10-20，用户设定；核心导出 msd_community_engineer_hp_version）：
#   "hp"：生命 = max(minimum, 修筑对象同等级生命 × percent / 100)，受击后生命仍大于 0 时继续行进或修筑，耗尽时撤退；
#   "hit_and_run"：原生（生命 1，受击即撤退）。
# content.json 的 engineer_hp 为缺省方式与原版 UnitID 的单独设定（units，键为 UnitID 字符串）；单位文件可写同格式的 engineer_hp。
KOUHEI_VTABLE=0x10929950
# 原生保留、无原版单位使用的动作类（行为 iron_slider / iron_slider_second_form，2026-10-21）：内部字段 native_action → 虚表符号。
NATIVE_ACTIONS={'IronSlider':'_ZTV23BattleAction_IronSlider','IronSlider_2':'_ZTV25BattleAction_IronSlider_2'}
# 浮点状态词：移速 5（另有倍率字段）以外的第二参数 16/23/30 与弹速 18/25/32。
FLOAT_WORDS=frozenset((16,18,23,25,30,32))
# 动作类为 BattleAction_Kouhei 的原版单位（1.46.0 动作表，安装时另按动作表核对）；迫击炮兵类（163、171）不在其中。
KOUHEI_IDS=frozenset((5,73,74,75,76,77,95,108,155,184,244,246,264,282,306,346,348,350,352,355,357,367,369,392))
ENGINEER_MODES=('hp','hit_and_run')
def check_engineer_hp(spec,where,mode_required=False):
    # 单独设定（units 中的项与单位文件）可只写 percent / minimum，方式沿用缺省。
    if not isinstance(spec,dict) or ('mode' in spec or mode_required) and spec.get('mode') not in ENGINEER_MODES or set(spec)-{'mode','percent','minimum','units'}:raise ValueError('Invalid engineer HP setting: '+where)
    for name,low,high in (('percent',1,100),('minimum',1,1000000)):
        v=spec.get(name)
        if v is not None and (not isinstance(v,int) or isinstance(v,bool) or not low<=v<=high):raise ValueError('Invalid engineer HP '+name+': '+where)
def engineer_setting(default,spec):
    """合并缺省与单独设定，返回 (方式, 百分比, 下限)。"""
    merged=dict(mode='hit_and_run',percent=5,minimum=300)
    for part in (default or {},spec or {}):merged.update((k,v) for k,v in part.items() if k!='units')
    return merged['mode'],merged['percent'],merged['minimum']
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

def load_stock_sprites(root,value):
    """content.json 的 stock_sprites（原版单位外观替换，2026-10-23）：{"原版 UnitID": "替换文件.json"}。
    替换文件含 textures（原版图集名或本体资源名）、sprite_descriptor（以原版描述符为底本、在后面追加矩形与帧）
    与 animations（改写的脚本，其余脚本沿用原版）。返回 {UnitID: 替换定义}。"""
    if not isinstance(value,dict):raise ValueError('Invalid stock sprite table')
    result={}
    for key,filename in value.items():
        if not isinstance(key,str) or not key.isdigit() or not 1<=int(key)<ORIGINAL_UNITS:raise ValueError('Invalid stock sprite unit: '+str(key))
        if not isinstance(filename,str) or Path(filename).name!=filename or not filename.endswith('.json'):raise ValueError('Invalid stock sprite file: '+str(filename))
        spec=json.loads((root/filename).read_text(encoding='utf-8'))
        if not isinstance(spec,dict) or set(spec)!={'textures','sprite_descriptor','animations'} or not isinstance(spec['textures'],list) or not isinstance(spec['sprite_descriptor'],str) or not isinstance(spec['animations'],dict):raise ValueError('Invalid stock sprite definition: '+filename)
        result[int(key)]=spec
    return result

def load_manifest(root):
    """读取内容索引 content.json（schema 3）与 units/ 逐单位文件，组装为既有 schema 2 结构的内存清单。

    单位按 UnitID 排序；加载器补回 id（content.json 的 unit_ids）与 icon.index（340+槽位，槽位为 UnitID−1024）；
    组合包补回 shop_id。单位文件不得自行写定这两项。返回 (清单, 本体区段, 模组区段)。
    content.json 的 disabled_units（可选，本体稳定键列表）暂不载入的本体单位：UnitID 保留，单位文件不读取，
    社区进度与编队按停用模组的方式保留（编队格按稳定键暂存，重新载入后恢复）。"""
    index=json.loads((root/CONTENT_INDEX).read_text(encoding='utf-8'))
    if index.get('schema')!=3:raise ValueError('Unsupported community content index schema')
    if index.get('asset_digest')!='blake2b-256':raise ValueError('Unsupported community asset digest')
    body,mods=content_ids.check_ranges(index.get('unit_id_ranges'))
    unit_ids=index.get('unit_ids');content_ids.check_body_ids(unit_ids,body)
    folder=index.get('units_dir')
    if not isinstance(folder,str) or Path(folder).name!=folder:raise ValueError('Invalid unit folder')
    disabled=index.get('disabled_units',[])
    if not isinstance(disabled,list) or any(k not in unit_ids for k in disabled) or len(set(disabled))!=len(disabled):raise ValueError('Invalid disabled body units')
    engineer=index.get('engineer_hp')
    if engineer is not None:
        check_engineer_hp(engineer,'content.json',True)
        for uid,spec in engineer.get('units',{}).items():
            if not uid.isdigit() or int(uid) not in KOUHEI_IDS:raise ValueError('Invalid engineer HP unit: '+uid)
            check_engineer_hp(spec,uid)
            if 'units' in spec:raise ValueError('Invalid engineer HP setting: '+uid)
    units={};skipped=set()
    for path in sorted((root/folder).glob('*.json')):
        data=json.loads(path.read_text(encoding='utf-8'))
        key=data.get('key') if isinstance(data,dict) else None
        if key not in unit_ids or key in units or key in skipped:raise ValueError('Unregistered or duplicate body unit file: '+path.name)
        if key in disabled:
            skipped.add(key);continue
        if 'id' in data or not isinstance(data.get('icon'),dict) or 'index' in data['icon']:raise ValueError('Unit files must not fix runtime identities: '+path.name)
        uid=unit_ids[key]
        unit={'key':key,'id':uid}
        unit.update((name,value) for name,value in data.items() if name!='key')
        unit['icon']=dict(index=340+uid-UNIT_ID_BASE,**data['icon'])
        if isinstance(unit.get('localization'),dict):unit['localization']=content_locale.fill(unit['localization'],'unit text')
        if ('atlas' in data['icon'])==('page' in data['icon']):raise ValueError('Unit icon requires either page 1 or an atlas: '+path.name)
        units[key]=unit
    if set(units)!=set(unit_ids)-set(disabled):raise ValueError('Missing body unit files: '+', '.join(sorted(set(unit_ids)-set(disabled)-set(units))))
    # 特殊行为（M2）：按行为库校验 behaviors 并转换为原生安装使用的内部字段。
    behaviors.apply(units,behaviors.load_library())
    manifest={'schema':2,'original_android_version':index.get('original_android_version'),
              'units':sorted(units.values(),key=lambda u:u['id']),'assets':index['assets'],'unit_id_base':UNIT_ID_BASE}
    assign_icon_pages(manifest['units'])
    for name,value in index.items():
        if name in manifest or name in ('unit_id_ranges','unit_ids','units_dir','asset_digest','disabled_units'):continue
        if name=='unit_pack' and value:
            if 'shop_id' in value:raise ValueError('The unit pack shop ID is assigned by the loader')
            if isinstance(value.get('localization'),dict):value=dict(value,localization=content_locale.fill(value['localization'],'pack text'))
            slots=manifest['units'][-1]['id']-UNIT_ID_BASE+1
            value=dict(value,shop_id=LEGACY_PACK_SHOP_ID if slots<=64 else 512+slots)
        if name=='stock_sprites':value=load_stock_sprites(root,value)
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
    cost=u.get('upgrade_cost_base')
    if cost is not None and (not isinstance(cost,int) or isinstance(cost,bool) or not 0<cost<=100000):raise ValueError('Invalid upgrade cost base')
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
                'construction_time_multiplier','summon_interval_additional_multiplier','near_damage_multiplier',
                'normal_damage_multiplier'):
        ratio(u.get(key,[1,1]))
    ratio(u.get('special_cooldown_multiplier',[1,1]))
    # 浮点状态词的绝对值（2026-10-21）：第二参数 16/23/30 与弹速 18/25/32 为浮点数，写入六个等级锚点。
    for word,value in u.get('status_float_values',{}).items():
        if not word.isdigit() or int(word) not in FLOAT_WORDS or isinstance(value,bool) or not isinstance(value,(int,float)) or not 0<=value<=10000:raise ValueError('Invalid float status word')
    for word,value in u.get('status_word_values',{}).items():
        # 单个整数写入六个等级锚点；也可写六个整数的列表，依次为 Lv1、Lv10、Lv20、Lv30、Lv40、Lv50 锚点（2026-10-15）。
        values=value if isinstance(value,list) and len(value)==6 else [value]
        if not word.isdigit() or int(word) not in ANCHOR_INDEX or int(word) in (1,2,3,4,5,13,14) or any(not isinstance(v,int) or isinstance(v,bool) or not -2147483648<=v<=2147483647 for v in values):raise ValueError('Invalid absolute status word')
    # 小地图标记的宽与高（数据行 +0x34c / +0x350，即 BattleUnitStatus 字 45 / 46；原生 BattlePlayerOperator::drawUI 按此画实心矩形）。
    # 原版大多为 4×4，大型单位为 10×10 至 20×20（2026-10-20）。
    if 'engineer_hp' in u:
        check_engineer_hp(u['engineer_hp'],u['key'])
        if u['base_id'] not in KOUHEI_IDS:raise ValueError('Engineer HP setting for a non-engineer unit: '+u['key'])
        if 'units' in u['engineer_hp']:raise ValueError('Invalid engineer HP setting: '+u['key'])
    if u.get('image_direction',90) not in (90,270):raise ValueError('Invalid image direction')
    marker=u.get('minimap_marker')
    if marker is not None and (not isinstance(marker,list) or len(marker)!=2 or any(not isinstance(v,int) or isinstance(v,bool) or not 1<=v<=64 for v in marker)):raise ValueError('Invalid minimap marker')
    # 绝招可发动时的蓝光宽与高（数据行 +0x344 / +0x348，即 BattleUnitStatus 字 43 / 44；原生 BattleUnit::draw 按两倍值绘制，
    # 为 0 时取当前帧第一个矩形的尺寸）。
    glow=u.get('special_effect_size')
    if glow is not None and (not isinstance(glow,list) or len(glow)!=2 or any(not isinstance(v,int) or isinstance(v,bool) or not 0<=v<=1000 for v in glow)):raise ValueError('Invalid special effect size')
    # 绘制优先级（数据行 +0x340，即 BattleUnitStatus 字 42；2026-10-25）：BattleObject::initialize 写入对象 +0xf0，BattleObjectManager::draw
    # 按其升序（相同时按建立次序）绘制，值小者先画、在下层。原版多数单位为 0，大型单位为负值（BIG SHIEE −90、REBEL GIGANT −78）。
    prio=u.get('draw_priority')
    if prio is not None and (not isinstance(prio,int) or isinstance(prio,bool) or not -1000<=prio<=1000):raise ValueError('Invalid draw priority')
    flame=u.get('flame_interrupt')
    if flame is not None:
        bullets=flame.get('ending_bullet_animations')
        values=[flame.get('flame_start_tick'),flame.get('flame_ticks'),flame.get('alternate_knockback_animation'),flame.get('knockback_limit_per_special')]
        if u['base_id']!=3 or not u.get('sprite_descriptor') or not isinstance(bullets,list) or len(bullets)!=4 or any(not isinstance(v,int) or isinstance(v,bool) or not 0<=v<256 for v in values+bullets) or not 6<=values[1]<=200 or values[3] not in (0,1):raise ValueError('Invalid flame interruption adapter')
    for group,reference in u.get('attack_parameter_references',{}).items():
        if group not in ('normal','special') or reference.get('group') not in ('normal','special') or not isinstance(reference.get('unit_id'),int) or not 0<reference['unit_id']<400:raise ValueError('Invalid attack parameter reference')
    for group,attribute in u.get('attack_attributes',{}).items():
        if group not in ('melee','normal','special') or not isinstance(attribute,int) or isinstance(attribute,bool) or attribute not in range(5):raise ValueError('Invalid native attack attribute')
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
    form=u.get('second_form_key')
    if form is not None and (form not in by_key or not by_key[form].get('internal_only') or form==u['key'] or by_key[form].get('native_action')!='IronSlider_2'):raise ValueError('Invalid second form reference')
    if 'native_action' in u and u['native_action'] not in NATIVE_ACTIONS:raise ValueError('Invalid native action class')
    landing=u.get('landing_unit_key')
    if landing is not None and (u['base_id']!=160 or landing not in by_key or by_key[landing].get('internal_only')):raise ValueError('Invalid paratrooper landing reference')
    summoned=u.get('summoned_unit_key')
    if summoned is not None and (u['base_id']!=64 or summoned not in by_key or summoned==u['key'] or by_key[summoned].get('internal_only')):raise ValueError('Invalid mummy gate summon reference')
    preview=u.get('preview_unit_key')
    if preview is not None and (preview!=child or preview not in by_key):raise ValueError('Invalid unit preview reference')
    thrown=u.get('throw_child_key')
    if thrown is not None and (thrown not in by_key or not by_key[thrown].get('internal_only') or by_key[thrown]['base_id']!=160 or thrown==u['key']):raise ValueError('Invalid thrown child reference')
    # 2026-10-27 5 连发马克斯奈尔的僚机（行为 formation_wingmen，核心 r99）：领队与僚机的基准均为 187，僚机为内部单位。
    wingman=u.get('formation_unit_key')
    if wingman is not None and (u['base_id']!=187 or wingman not in by_key or not by_key[wingman].get('internal_only') or by_key[wingman]['base_id']!=187 or wingman==u['key']):raise ValueError('Invalid formation wingman reference')

def check_sprite_descriptor(u,dims,descriptor_path):
    """精灵描述符与动作脚本的检查（社区单位与原版单位外观替换共用）；u 含 textures、sprite_descriptor、animations；无描述符时返回 None。"""
    filename=u.get('sprite_descriptor')
    if not filename:return None
    if Path(filename).name!=filename or not filename.endswith('.json'):raise ValueError('Invalid sprite descriptor path')
    desc=json.loads(descriptor_path(filename).read_text(encoding='utf-8'))
    rects=desc['rects'];frames=desc['frames'];textures=u.get('textures',[u.get('texture')])
    # 脚本数上限 1024（2026-10-22 蜈蚣长老 284 个；原生描述符中 BrainRobot 为 261 个，原生不按字节存放脚本号）
    if not 1<=len(rects)<=8192 or not 1<=len(frames)<=65536 or not 1<=desc['script_count']<=1024:raise ValueError('Invalid sprite descriptor capacity')
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
            # op12 也可写共用效果编号 0xff00–0xfffe（原生 addEffectImpl：编号 ≥ 0xff00 时取共用效果 UnitID 402，动画为低 8 位；2026-10-20）。
            if op==12 and 0xff00<=values[0]<=0xfffe:continue
            if op in (10,11,12,22) and not 0<=values[0]<desc['script_count']:raise ValueError('Animation references invalid child script')
            if op in (3,4) and not -1<=values[0]<len(desc['hit_bounds' if op==3 else 'attack_bounds']):raise ValueError('Animation references invalid collision rectangle')
    for field in ('hit_bounds','attack_bounds'):
        # 上限 2048（2026-10-25 钢铁死亡蠕虫 R4：受击 / 攻击框之后的部件条目；原生按序号 × 20 字节定址，无数量限制）
        if not 1<=len(desc[field])<=2048 or any(len(r)!=5 or any(not isinstance(v,int) or not -2147483648<=v<=2147483647 for v in r) for r in desc[field]):raise ValueError('Invalid sprite collision bounds')
    return desc

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
    desc=check_sprite_descriptor(u,dims,descriptor_path)
    flame=u.get('flame_interrupt')
    if flame and (flame['alternate_knockback_animation']+5>desc['script_count'] or any(v>=desc['script_count'] for v in flame['ending_bullet_animations'])):raise ValueError('Flame interruption animation outside sprite descriptor')
    zombie=u.get('zombie_spec') or {}
    if zombie.get('thresholds') and (not filename or 16*(len(zombie['thresholds'])+1)>desc['script_count']):raise ValueError('HP stage animations outside sprite descriptor')
    # 2026-10-18 炸药与按属性的死亡（基准 221）：登记的动作槽须在描述符内；绝招等距落点的弹体槽同样。
    slots=[zombie.get(k) for k in ('blast_slot','fuse_slot','death_explosion','death_fire','death_normal_variant','death_explosion_variant','death_fire_variant') if k in zombie]
    if zombie.get('spread_count'):slots+=[zombie['spread_first']+i for i in range(zombie['spread_count'])]
    # 2026-10-22 飞行护盾：下落 / 追踪动作与两组陨石弹体槽
    if zombie.get('shell'):
        h=zombie['shell'];slots+=[h[1]]+[h[2]+i for i in range(h[3])]+[h[4]+i for i in range(h[5])]
    # 2026-10-22 蜈蚣长老：各动作、三个尘土槽、飞沫弹体槽
    if zombie.get('centipede'):
        e=zombie['centipede'];slots+=[e[i] for i in range(24) if i not in (13,14,17,18)]+[e[13]+i for i in range(3)]+[e[17]+i for i in range(e[18])]
    # 2026-10-22 侵略者之王：各动作、两组激光弹体槽
    if zombie.get('king'):
        k=zombie['king'];slots+=[k[i] for i in range(24) if i not in (18,19,21,22)]+[k[18]+i for i in range(k[19])]+[k[21]+i for i in range(k[22])]
    # 2026-10-25 钢铁死亡蠕虫：各动作与碎块弹体槽
    if zombie.get('worm'):
        m=zombie['worm'];slots+=m[:9]+[m[9]+i for i in range(m[10])]+[m[11]+2*i+k for i in range(m[12]) for k in (0,1)]
    if slots and (not filename or any(not 0<=v<desc['script_count'] for v in slots)):raise ValueError('Behavior animation outside sprite descriptor')
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
        # 原版单位外观替换（2026-10-23）：图集须为原版资源或本体资源，描述符为必需项。
        self.stock_sprites={}
        for uid,spec in self.manifest.get('stock_sprites',{}).items():
            for name in spec['textures']:
                if name not in self.asset_dimensions and not stock_asset_exists(name):raise ValueError('Unregistered stock sprite texture: '+str(name))
            desc=check_sprite_descriptor(spec,self.asset_dimensions,self.descriptor_path)
            if not desc:raise ValueError('Stock sprite requires a sprite descriptor')
            self.stock_sprites[uid]=(spec,desc)
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
                raw=self.assets[leaf]
                # 场景图像源（content_assets.ImageTexture）在原生打开时解码为直接 RGBA 的 OBM。
                if not isinstance(raw,(bytes,bytearray)):raw=raw.obm();p.log('SCENE_IMAGE_TEXTURE',leaf,len(raw))
                handle=p.alloc(16);p.handles[handle]=io.BytesIO(raw);return handle
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
        # 2026-10-27 僚机映射（formation_unit_key）：领队生成 UnitID 187 时经落地映射表换为登记的单位（核心 r99）。
        if any(u.get('formation_unit_key') for u in self.units) and (not hasattr(p.uc.lib,'msd_community_formation_version') or p.uc.lib.msd_community_formation_version()<1):raise RuntimeError('Native core lacks formation wingman references')
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
        # 钢铁哨兵（行为 iron_slider）的 7 个钩子同样在启用社区内容时登记。
        if any(u.get('native_action') for u in self.units) and (not hasattr(p.uc.lib,'msd_community_iron_slider_version') or p.uc.lib.msd_community_iron_slider_version()!=1):raise RuntimeError('Native core lacks the Iron Slider adaptation')
        # 生命分档单位的钩子在启用社区内容时登记，版本函数在全部找到原生块后返回 1。
        # 生命分档单位：核心版本 1 为首批 7 个钩子，2 另含前方最近敌人（front_nearest_target，标记 64）的 5 个钩子，
        # 3 另含分档受击动作（stage_knockback_animation，标记 128），4 另含雪地步兵类（基准 182）的分档入口，
        # 5 另含雪地步兵类爆炸死亡不生成血色效果（no_death_splash，标记 256，钩子数不变）。
        # 6 另含 2026-10-15 新单位的行为（自爆 512、只打地面 1024、行进射击 2048、气球飞行 4096、被投出单位的据点前落地）与 33 字 ZSpec。
        need=max([6 if u['zombie_spec']['flags']&(512|1024|2048|4096) or u['zombie_spec'].get('base_clearance') else 5 if u['zombie_spec']['flags']&256 else 4 if u['base_id']==182 else 3 if u['zombie_spec']['flags']&128 else 2 if u['zombie_spec']['flags']&64 else 1 for u in self.units if u.get('zombie_spec')] or [0])
        if need and (not hasattr(p.uc.lib,'msd_community_zombie_version') or p.uc.lib.msd_community_zombie_version()<need):raise RuntimeError('Native core lacks HP stage units')
        # 2026-10-18 炸药（lob_blast，标记 8192）与按攻击属性的死亡（death_by_attribute，标记 16384）：基准 221 的 3 个钩子。
        if any(u['zombie_spec']['flags']&(8192|16384) for u in self.units if u.get('zombie_spec')) and (not hasattr(p.uc.lib,'msd_community_hunter_version') or p.uc.lib.msd_community_hunter_version()<1):raise RuntimeError('Native core lacks dynamite and attribute deaths')
        if any(u['zombie_spec'].get(k) for u in self.units if u.get('zombie_spec') for k in ('death_normal_variant','death_explosion_variant','death_fire_variant')) and p.uc.lib.msd_community_hunter_version()<2:raise RuntimeError('Native core lacks death animation variants')
        # 2026-10-21 效果贴地（ground_hugging_effect，标记 32768）：效果默认绘制与逐分件绘制的 3 个钩子。
        if any(u['zombie_spec']['flags']&32768 for u in self.units if u.get('zombie_spec')) and (not hasattr(p.uc.lib,'msd_community_ground_effect_version') or p.uc.lib.msd_community_ground_effect_version()<1):raise RuntimeError('Native core lacks ground-hugging effects')
        # 2026-10-22 建筑损毁效果（structure_death_effect，标记 65536）：沙包类损毁后移除前的 1 个钩子。
        if any(u['zombie_spec']['flags']&65536 for u in self.units if u.get('zombie_spec')) and (not hasattr(p.uc.lib,'msd_community_structure_death_version') or p.uc.lib.msd_community_structure_death_version()<1):raise RuntimeError('Native core lacks structure destruction effects')
        # 2026-10-22 飞行护盾（flying_shell，标记 131072）：飞行高度、绝招落点、损毁爆炸与陨石的 6 个钩子。
        if any(u['zombie_spec']['flags']&131072 for u in self.units if u.get('zombie_spec')) and (not hasattr(p.uc.lib,'msd_community_flying_shell_version') or p.uc.lib.msd_community_flying_shell_version()<1):raise RuntimeError('Native core lacks flying shell behavior')
        # 2026-10-22 蜈蚣长老（elder_centipede，标记 262144）：侵略者类 update / shotBullet、其弹体 update / attackAction、createObject 与按地面裁切绘制的 9 个块。
        if any(u['zombie_spec']['flags']&262144 for u in self.units if u.get('zombie_spec')) and (not hasattr(p.uc.lib,'msd_community_elder_centipede_version') or p.uc.lib.msd_community_elder_centipede_version()<1):raise RuntimeError('Native core lacks elder centipede behavior')
        # 2026-10-22 建筑受击光束（structure_hit_attack，标记 524288）：沙包类受击动作按普攻组结算的 1 个钩子。
        if any(u['zombie_spec']['flags']&524288 for u in self.units if u.get('zombie_spec')) and (not hasattr(p.uc.lib,'msd_community_structure_hit_attack_version') or p.uc.lib.msd_community_structure_hit_attack_version()<1):raise RuntimeError('Native core lacks structure hit attacks')
        # 2026-10-22 侵略者之王（invader_king，标记 1048576）：与蜈蚣长老共用侵略者类 update / shotBullet、其弹体 update / attackAction、createObject 的块，另在击退判定中不击退。
        if any(u['zombie_spec']['flags']&1048576 for u in self.units if u.get('zombie_spec')) and (not hasattr(p.uc.lib,'msd_community_invader_king_version') or p.uc.lib.msd_community_invader_king_version()<1):raise RuntimeError('Native core lacks invader king behavior')
        # 2026-10-25 钢铁死亡蠕虫（iron_death_worm，标记 2097152）：与蜈蚣长老共用侵略者类的块与地面裁切绘制，另加分层绘制的第 4 个延续块（核心 r91）；
        # 行为 v2（按 MSA 底层代码核对的流程、地下行进、损毁碎块）需核心 r92（版本 2）。
        if any(u['zombie_spec']['flags']&2097152 for u in self.units if u.get('zombie_spec')) and (not hasattr(p.uc.lib,'msd_community_iron_death_worm_version') or p.uc.lib.msd_community_iron_death_worm_version()<5):raise RuntimeError('Native core lacks iron death worm behavior')
        # 2026-10-26 鼹鼠弹（mole_missile，标记 4194304）：Bike_P 类 update / attackAction 的 2 个块（核心 r97）；钻出时借用蜈蚣长老的地面裁切绘制。
        # R1 行为 v2（悬停点与追踪俯冲）需核心 r98（版本 2）。
        # 2026-10-27 贯穿子弹（piercing_shots，标记 8388608）：BattleBulletDefault::attackAction 的 2 个块（核心 r100）。
        if any(u['zombie_spec']['flags']&8388608 for u in self.units if u.get('zombie_spec')) and (not hasattr(p.uc.lib,'msd_community_piercing_shots_version') or p.uc.lib.msd_community_piercing_shots_version()<1):raise RuntimeError('Native core lacks piercing shots')
        if any(u['zombie_spec']['flags']&4194304 for u in self.units if u.get('zombie_spec')) and (not hasattr(p.uc.lib,'msd_community_mole_missile_version') or p.uc.lib.msd_community_mole_missile_version()<2 or not hasattr(p.uc.lib,'msd_community_elder_centipede_version') or p.uc.lib.msd_community_elder_centipede_version()<1):raise RuntimeError('Native core lacks mole missile behavior')
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
        # 条目 gain：宿主解码时按文件内容查表乘到采样上（native_audio.AudioCache，核心 msd_pcm_gain）。
        self.p.sound_gains={Path(e['source']).read_bytes():float(e['gain']) for e in entries if e.get('gain',1)!=1}
        cache=getattr(self.p,'native_audio_cache',None)
        if cache is not None and entries:cache.prefetch([e['source'] for e in entries])   # 后台预先解码（同原版音效）
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

    def sprite_header(self,descriptor,textures,desc,animations):
        """以原生描述符 descriptor 为底本建立精灵描述符头（社区单位与原版单位外观替换共用），返回头地址。
        desc 为精灵描述符（无则沿用原生矩形、帧与脚本数，textures 须与原生图集数相同）；animations 为改写的脚本。"""
        p=self.p;header=bytearray(p.read(descriptor,32))
        image_count=len(textures) if desc else p.word(descriptor)
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
        for key,commands in animations.items():
            if not 0<=int(key)<count:raise ValueError('Animation index outside base unit descriptor')
            values=[v for cmd in content_sounds.resolve_animation(commands,self.sound_ids) for v in [cmd['opcode'],*cmd['values']]]
            scripts[int(key)]=self.alloc(struct.pack('<'+'i'*len(values),*values))
        struct.pack_into('<I',header,24,self.alloc(struct.pack('<'+'I'*count,*scripts)))
        return self.alloc(header)

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
        # 原版单位外观替换（stock_sprites）：以原生描述符为底本追加矩形与帧、改写指定脚本，写入该 UnitID 的图像表项（朝向不变）。
        for uid,(spec,desc) in self.stock_sprites.items():
            struct.pack_into('<I',images,uid*8,self.sprite_header(p.word(table+uid*8),spec['textures'],desc,spec['animations']))
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
            # 强化费用基数 P（数据行 +0x354，非等级字段）：单次强化 MSP = P×(3L+5)；原生 AI 也以此值计单位战力。
            if 'upgrade_cost_base' in u:struct.pack_into('<i',row,0x354,u['upgrade_cost_base'])
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
            # 原生攻击属性为非等级字段：近距词 21、普攻词 28、绝招词 37；1 表示火焰，2 表示爆炸（决定被击杀单位的死亡状态 120 / 110）。
            for group,attribute in u.get('attack_attributes',{}).items():
                struct.pack_into('<i',row,{'melee':21,'normal':28,'special':37}[group]*4,attribute)
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
            # 近距伤害（词 15）的追加倍率（2026-10-21）：与绝招追加倍率相同，作用于数据行锚点并向下取整，再经 damage_multiplier。
            a,b=ratio(u.get('near_damage_multiplier',[1,1]))
            for off in anchor_offsets(15):struct.pack_into('<i',row,off,struct.unpack_from('<i',row,off)[0]*a//b)
            # 远距伤害（词 22）的追加倍率（2026-10-22）：同近距，作用于数据行锚点并向下取整，再经 damage_multiplier。
            a,b=ratio(u.get('normal_damage_multiplier',[1,1]))
            for off in anchor_offsets(22):struct.pack_into('<i',row,off,struct.unpack_from('<i',row,off)[0]*a//b)
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
                values=value if isinstance(value,list) else [value]*6
                for off,v in zip(anchor_offsets(int(word)),values):struct.pack_into('<i',row,off,v)
            for word,value in u.get('status_float_values',{}).items():
                for off in anchor_offsets(int(word)):struct.pack_into('<f',row,off,float(value))
            # 普通、特殊弹体的目的距离以绝对值登记时，原生距离元数据随之更新（同 normal_attack_range_from_projectile）。
            if '26' in u.get('status_word_values',{}):row[0x370:0x374]=row[26*4:27*4]
            if '33' in u.get('status_word_values',{}):row[0x374:0x378]=row[33*4:34*4]
            if 'minimap_marker' in u:struct.pack_into('<2i',row,0x34c,*u['minimap_marker'])
            if 'special_effect_size' in u:struct.pack_into('<2i',row,0x344,*u['special_effect_size'])
            if 'draw_priority' in u:struct.pack_into('<i',row,0x340,u['draw_priority'])
            # 击退门槛为状态词 4（原生插值后乘 100 作为击退计量）；六个等级锚点按倍率四舍五入。
            # 非正值（原版 -1）表示每次受击均击退，计量不回填，该标记保持原值。
            a,b=u.get('knockback_threshold_multiplier',[1,1])
            for off in (0x10,0xb4,0x138,0x1bc,0x240,0x2c4):
                value=struct.unpack_from('<i',row,off)[0]
                if value>0:struct.pack_into('<i',row,off,(2*value*a+b)//(2*b))
            struct.pack_into('<i',row,0x378,u['faction']);rows+=row
            child_key=u.get('child_unit_key') or u.get('summoned_unit_key') or u.get('throw_child_key') or u.get('second_form_key')
            if child_key:
                child=next(entry['id'] for entry in self.units if entry['key']==child_key)
                struct.pack_into('<I',rows,len(rows)-0x390+0xa4,child)
            action=p.word(actions+bid*4)
            if 'shot_action_reference_id' in u:
                reference=p.word(actions+u['shot_action_reference_id']*4)
                methods=bytearray(p.read(p.word(action),40))
                methods[8:12]=p.read(p.word(reference)+8,4)
                action=self.alloc(struct.pack('<I',self.alloc(methods)))
            if 'native_action' in u:
                # 原生保留、无原版单位使用的动作类（钢铁哨兵）：动作对象只含虚表指针。
                action=self.alloc(struct.pack('<I',p.symbols[NATIVE_ACTIONS[u['native_action']]]+8))
            action_rows+=struct.pack('<I',action)
            header=self.sprite_header(p.word(table+bid*8),u.get('textures',[u.get('texture')]),self.sprite_descriptors.get(u['key']),u['animations'])
            # 图像表第 2 字为原画朝向（90 朝右、270 朝左，原生按此决定是否镜像）；默认取基准单位，单位文件可用 image_direction 指定。
            images+=struct.pack('<II',header,u.get('image_direction',p.word(table+bid*8+4)))
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
        # 落地映射：空降单位登记落地后的单位；投出子单位的生命分档单位登记被投出的飞行单位（原生均以固定 UnitID 45 生成）；
        # 基准 187 的编队领队登记僚机单位（原生以固定 UnitID 187 生成，2026-10-27）。
        landings=struct.pack('<'+'I'*n,*(landing_ids[u.get('landing_unit_key') or u.get('throw_child_key') or u.get('formation_unit_key')] if u and (u.get('landing_unit_key') or u.get('throw_child_key') or u.get('formation_unit_key')) else 0 for u in units))
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
        # 头部偏移 160：逐槽获得时间（原生 Get/SetUnitGetTimeSaveData 对 UnitID ≥ 300 无上界，核心钩子改读写此表；U1c）。
        get_times=[int((self.progress['units'].get(u['key'],{}) if u else {}).get('get_time',0))&0xffffffff for u in units]
        self.get_time_table=self.alloc(struct.pack('<'+'I'*n,*get_times))
        fields+=(self.get_time_table,)
        # 头部偏移 164：原生单位商店勋章不足时只提示、不询问前往商店（新单位界面的组合包页面期间由宿主置 1，U1c D45）。
        fields+=(0,)
        # 头部偏移 168：生命分档等行为（行为库 v3 起，src/community_content.cpp 的 ZSpec，39 个字）的逐槽指针表；无此类单位时为 0。
        fields+=(self.install_zombie_specs(units),)
        # 头部偏移 172：自制场景（ID 138 起，manifest['stages'] 顺序）逐场景标记字节表，位 0 为 2 倍素材（resolution 2，绘制时图块缩放减半）；无此类场景时为 0。
        stage_rows=self.manifest.get('stages',[])
        flags=bytes(1 if s.get('resolution',1)==2 else 0 for s in stage_rows)
        if any(flags):
            if not hasattr(p.uc.lib,'msd_community_stage_scale_version') or p.uc.lib.msd_community_stage_scale_version()!=1:
                raise RuntimeError('Native core lacks high-resolution scene drawing (stage_scale hooks)')
            fields+=(self.alloc(flags+b'\0'*(-len(flags)%4)),)
        else:fields+=(0,)
        # 头部偏移 176/180：按生命计算的修筑类单位表（每项 UnitID、百分比、下限）与项数；无此类单位时为 0。
        fields+=self.install_engineer_hp(action_rows,units)
        # 头部偏移 184：自制场景（ID 138 起，manifest['stages'] 顺序）逐场景的效果记录指针表（水花 water、子弹墙 bullet_walls、背景图层视差 parallax）；无此类场景时为 0。
        fields+=(self.install_scene_fx(stage_rows),)
        p.write(HEADER,struct.pack('<%dI'%len(fields),*fields));self.ready=True
        self.map_initial_choices_applied=not (self.manifest.get('missions') or self.manifest.get('campaign_choices'))
        assert p.read(p.word(db+4),400*0x390)==bytes(rows[:400*0x390])
        p.log('COMMUNITY_REGISTERED',n,'unit IDs',[u['id'] for u in self.units])

    def install_scene_fx(self,stage_rows):
        """场景效果记录（src/community_content.cpp 的 scene_fx 钩子），每个 22 个字：0 标记（位 0 水花，位 1 子弹墙，位 2 背景图层视差）；
        1–4 水花左界、右界、起水高度、画线（同原生 WaterFunc::waterSetup 的四个整数，逻辑坐标）；5–8 水花颜色 r、g、b 与染色强度（float，0–1，
        GraphicsOpt::setSpriteFog）；9 已建立 WaterFunc 的场景对象（核心写入）；10–17 WaterFunc 存储（核心使用）；18 子弹墙多边形数；
        19 多边形数据（每个多边形：点数 n，再 n 对 x、y，int32）；20 视差表的背景层数；21 视差表（逐背景层的卷动比例，int32 千分比，
        1000 为与镜头同速；2026-10-28 起，核心 stage_parallax）。"""
        p=self.p
        if not any('water' in s or 'bullet_walls' in s or 'parallax' in s for s in stage_rows):return 0
        if not hasattr(p.uc.lib,'msd_community_scene_fx_version') or p.uc.lib.msd_community_scene_fx_version()!=1:
            raise RuntimeError('Native core lacks scene water / bullet wall hooks (scene_fx)')
        if any('parallax' in s for s in stage_rows) and (not hasattr(p.uc.lib,'msd_community_stage_parallax_version')
                                                        or p.uc.lib.msd_community_stage_parallax_version()!=1):
            raise RuntimeError('Native core lacks scene layer parallax (stage_parallax)')
        f32=lambda v:struct.unpack('<I',struct.pack('<f',v))[0]
        pointers=[]
        for s in stage_rows:
            water,walls,parallax=s.get('water'),s.get('bullet_walls'),s.get('parallax')
            if not water and not walls and not parallax:pointers.append(0);continue
            words=[0]*22
            if water:
                words[0]|=1;words[1:5]=[*water['range'],water['min_y'],water['draw_y']]
                words[5:9]=[f32(v/255) for v in (*water['color'],water.get('strength',230))]
            if walls:
                words[0]|=2;words[18]=len(walls)
                words[19]=self.alloc(b''.join(struct.pack('<I',len(poly))+b''.join(struct.pack('<ii',x,y) for x,y in poly) for poly in walls))
            if parallax:
                words[0]|=4;words[20]=len(parallax)
                words[21]=self.alloc(struct.pack('<%di'%len(parallax),*parallax))
            pointers.append(self.alloc(struct.pack('<22I',*(w&0xffffffff for w in words))))
        return self.alloc(struct.pack('<%dI'%len(pointers),*pointers))

    def install_engineer_hp(self,action_rows,units):
        p=self.p;default=self.manifest.get('engineer_hp');stock=(default or {}).get('units',{})
        def kouhei(uid):
            action=struct.unpack_from('<I',action_rows,uid*4)[0]
            return bool(action) and p.word(action)==KOUHEI_VTABLE
        entries=[]
        for uid in range(1,400):
            if not kouhei(uid):
                if str(uid) in stock:raise ValueError('Engineer HP setting for a non-engineer unit: %d'%uid)
                continue
            mode,percent,minimum=engineer_setting(default,stock.get(str(uid)))
            if mode=='hp':entries.append((uid,percent,minimum))
        for i,u in enumerate(units):
            if not u:continue
            if not kouhei(UNIT_ID_BASE+i):
                if 'engineer_hp' in u:raise ValueError('Engineer HP setting for a non-engineer unit: '+u['key'])
                continue
            mode,percent,minimum=engineer_setting(default,u.get('engineer_hp'))
            if mode=='hp':entries.append((UNIT_ID_BASE+i,percent,minimum))
        self.engineer_hp_units=[e[0] for e in entries]
        if not entries:return (0,0)
        if not hasattr(p.uc.lib,'msd_community_engineer_hp_version') or p.uc.lib.msd_community_engineer_hp_version()!=1:
            raise RuntimeError('Native core lacks engineer HP hooks')
        return (self.alloc(b''.join(struct.pack('<3I',*e) for e in entries)),len(entries))

    def install_zombie_specs(self,units):
        specs=[(u or {}).get('zombie_spec') for u in units]
        if not any(specs):return 0
        pointers=[]
        for spec in specs:
            if not spec:pointers.append(0);continue
            words=[0]*136;words[0]=spec['flags']
            thresholds=spec.get('thresholds',[]);words[1]=len(thresholds)
            for i,(a,b) in enumerate(thresholds):words[2+i]=a;words[8+i]=b
            words[14]=sum(1<<(i+1) for i,flag in enumerate(spec.get('transitions',[])) if flag)
            words[15]=spec.get('rage_stage',0)
            words[16],words[17]=spec.get('rage_speed',[1,1]);words[18],words[19]=spec.get('rage_damage',[1,1])
            armor=[self.sound_ids[k] for k in spec.get('armor_sounds',[])]
            words[20]=armor[0] if armor else 0;words[21]=armor[1] if len(armor)>1 else words[20]
            words[22]=spec.get('armor_until',0)
            words[23]=self.sound_ids[spec['kill_sound']] if spec.get('kill_sound') else 0
            words[24]=spec.get('throw_stage',0);words[25]=spec.get('release_tick',0)
            words[26]=spec.get('flight_forward',0)&0xffffffff;words[27]=spec.get('flight_height',0)
            # 2026-10-15：28 行进射击的射程，29 气球放手距离，30 气球出场音效，31 被投出单位与敌方据点前缘的最小间距
            words[28]=spec.get('walk_range',0);words[29]=spec.get('pop_distance',0)
            words[30]=self.sound_ids[spec['launch_sound']] if spec.get('launch_sound') else 0
            words[31]=spec.get('base_clearance',0)
            # 32：自爆动作开始后按素材原朝向绘制的起始 tick + 1（0 为不改变）
            words[32]=spec['unmirror_tick']+1 if 'unmirror_tick' in spec else 0
            # 2026-10-18（基准 221）：33 碰到敌人时的爆炸槽，34 落地后的引信与爆炸槽，35/36 绝招等距落点的首个弹体槽与颗数，
            # 37/38 爆炸属性与火焰属性击杀时的死亡槽
            words[33]=spec.get('blast_slot',0);words[34]=spec.get('fuse_slot',0)
            words[35]=spec.get('spread_first',0);words[36]=spec.get('spread_count',0)
            words[37]=spec.get('death_explosion',0);words[38]=spec.get('death_fire',0)
            # 39–41：普通、爆炸、火焰死亡的另一版本（死亡时横坐标取整为奇数时播放；0 为不使用）
            words[39]=spec.get('death_normal_variant',0);words[40]=spec.get('death_explosion_variant',0)
            words[41]=spec.get('death_fire_variant',0)
            # 2026-10-21：42 贴地绘制的效果动作号 + 1（ground_hugging_effect，0 为不使用）
            words[42]=spec['hug_animation']+1 if 'hug_animation' in spec else 0
            # 2026-10-22：43–52 飞行护盾（flying_shell）：飞行高度、下落 / 追踪动作、普攻陨石首槽与个数、绝招陨石首槽与个数、
            # 绝招落下的倒数、陨石存在 tick、陨石生命百分比、每 tick 转向上限
            for i,v in enumerate(spec.get('shell',[])):words[43+i]=v
            # 2026-10-22：53–76 蜈蚣长老（elder_centipede）：出土、由地下出土、待机、钻地、地下移动、喷酸与收尾、绝招入地、大前行、受击与其循环、
            # 击退、损毁、尘土首槽、圆环节数、两种地面攻击、飞沫首槽与个数、溅射、绝招酸块与其命中、绝招泥土、地面尘土（80 字，77–79 保留）
            for i,v in enumerate(spec.get('centipede',[])):words[53+i]=v
            # 2026-10-22：77–100 侵略者之王（invader_king）：待机、落下、着地、近距、跃起、绝招开始 / 绝招 / 收尾、击退、损毁、受击与其循环、
            # 菜单待机 / 远距 / 绝招演示、反击激光与其身体段、反击激光落点爆炸、天空激光首槽 / 个数 / 身体段、地面激光首槽 / 个数、地面落点（104 字）
            for i,v in enumerate(spec.get('king',[])):words[77+i]=v
            # 2026-10-25：104–116 钢铁死亡蠕虫（iron_death_worm v2，核心 r92）：待机、钻入、钻出、掘削、绝招钻入（兼损毁钻入）、
            # 地下钻击、损毁横穿、爆炸、地下行进、掘削碎块首槽与个数、损毁碎块首槽与个数；117–119（v3，核心 r95）：碎块滚动首槽、
            # 碎块爆炸、碎块引信 tick；120（v4，核心 r96）：绝招中的钻出
            for i,v in enumerate(spec.get('worm',[])):words[104+i]=v
            # 2026-10-26：121–131 鼹鼠弹（mole_missile v1，核心 r97）：悬停、钻入、地下潜行、钻出、冲刺、爆炸、绝招爆炸、损毁动作，
            # 冲刺速度（世界单位 × 10 / tick）、悬停点的前方距离与离地高度（R1，核心 r98；136 字，132–135 保留）
            for i,v in enumerate(spec.get('mole',[])):words[121+i]=v
            pointers.append(self.alloc(struct.pack('<136I',*words)))
        return self.alloc(struct.pack('<'+'I'*len(pointers),*pointers))

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
             'deck_time':p.word(self.records+i*RECORD_SIZE+0x88),'get_time':p.word(self.get_time_table+i*4)}
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
