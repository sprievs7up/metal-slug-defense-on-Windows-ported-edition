// Event preview intercepts only finalization and continuation writes.
// Original native blocks remain active outside a selected historical Event.
#include "aot_runtime.h"
#include "native_imports.h"
static constexpr uint32_t H=0x1ffed000u,MAGIC=0x45565431u;
static Block original_end,original_continue;
static bool active(Context& c){return rd<uint32_t>(c,H)==MAGIC;}
static bool eventmsd(Context& c);
static void event_end(Context& c){
    if(!active(c)||rd<uint32_t>(c,H+116)){original_end(c);return;}
    // 合作活动的原生合作战斗（模式 6，NPC/联机接口）由原生结算处理。
    uint32_t app=rd<uint32_t>(c,H+36);
    if(eventmsd(c)&&app&&rd<uint32_t>(c,app+0xc8c8)==6u){original_end(c);return;}
    wr<uint32_t>(c,H+4,1u);c.pc=c.r[14];
}
static void no_event_continuation(Context& c){
    if(active(c))c.r[1]=0u;
    original_continue(c);
}
static bool event_shop(Context& c){
    if(!active(c)||!rd<uint32_t>(c,H+16)||!rd<uint32_t>(c,H+24))return false;
    uint32_t app=rd<uint32_t>(c,H+36);
    uint32_t kind=rd<uint32_t>(c,H+8);
    return app&&((kind==1u&&rd<uint32_t>(c,app+0xb890)==6u)||
                 (kind==2u&&rd<uint32_t>(c,app+0xb890)==2u));
}
static bool medal_event_shop(Context& c){return event_shop(c)&&rd<uint32_t>(c,H+8)==2u;}
// 历史活动勋章单位仅在对应活动的独立商店出售：0x1ffef200 为 'EVSK' 时，+4 个数、+8 起 MenuShopID 列表，
// 在活动商店以外的原生商店中关闭（宿主于启动时写入，与活动选择状态无关）。
static constexpr uint32_t EVSK=0x1ffef200u,EVSK_MAGIC=0x4b535645u;
static bool event_exclusive_sku(Context& c,uint32_t sid){
    if(rd<uint32_t>(c,EVSK)!=EVSK_MAGIC||event_shop(c))return false;
    uint32_t n=rd<uint32_t>(c,EVSK+4u);if(n>64u)n=64u;
    for(uint32_t i=0;i<n;++i)if(rd<uint32_t>(c,EVSK+8u+i*4u)==sid)return true;
    return false;
}
static bool hidden_shop(Context& c){
    if(!active(c)||rd<uint32_t>(c,H+16))return false;
    uint32_t app=rd<uint32_t>(c,H+36);
    if(!app)return false;
    uint32_t scene=rd<uint32_t>(c,app+0x22bc);
    // H+48 为当前活动勋章单位商店的商品数；女教官基地底栏 SHOP 以其开放独立勋章店。
    return (scene==67u&&!rd<uint32_t>(c,H+48))||(scene==34u&&rd<uint32_t>(c,H+80)&&!rd<uint32_t>(c,H+84))||(scene==160u&&rd<uint32_t>(c,H+84));
}
static uint32_t shop_record(Context& c,uint32_t sid){
    if(!event_shop(c))return 0;
    uint32_t base=rd<uint32_t>(c,H+20),count=rd<uint32_t>(c,H+24);
    for(uint32_t i=0;i<count;i++)if(rd<uint32_t>(c,base+i*64)==sid)return base+i*64;
    return 0;
}
static void ret(Context& c,uint32_t value){c.r[0]=value;c.pc=c.r[14];}
#define SHOP_HOOK(NAME,PC,BODY) static Block old_##NAME;static void NAME(Context& c){BODY old_##NAME(c);}
// Clear native overrides before main-menu initialization can invoke another
// scene. The host restores the borrowed mission tables in the same frame.
SHOP_HOOK(main_menu_reset,0x10204051u,{
    uint32_t app=c.r[0];
    if(active(c)||rd<uint32_t>(c,H+80)||rd<uint32_t>(c,H+124)){
        for(uint32_t offset=0;offset<=212;offset+=4)wr<uint32_t>(c,H+offset,0u);
        wr<uint32_t>(c,H+200,1u);
    }
    wr<uint32_t>(c,app+0xb1ec,0u);wr<uint32_t>(c,app+0xb1f0,0u);wr<uint32_t>(c,app+0xb1f4,0u);
    wr<uint32_t>(c,app+0xc030,0u);wr<uint32_t>(c,app+0xc034,0u);
    wr<uint32_t>(c,app+0xc63c,0u);wr<uint32_t>(c,app+0xc06c,0u);wr<uint32_t>(c,app+0xc8c8,0u);
})
SHOP_HOOK(shop_data,0x101655c9u,uint32_t row=shop_record(c,c.r[0]);if(row){ret(c,rd<uint32_t>(c,row+4));return;})
SHOP_HOOK(shop_coin_price,0x10165977u,uint32_t row=shop_record(c,c.r[0]);if(row){ret(c,rd<uint32_t>(c,row+8));return;})
SHOP_HOOK(shop_standard_price,0x101656c5u,uint32_t row=shop_record(c,c.r[0]);if(row){ret(c,rd<uint32_t>(c,row+8));return;})
SHOP_HOOK(shop_discount,0x1016596bu,if(shop_record(c,c.r[0])){ret(c,0u);return;})
// 勋章目录的展示与开售权限仅作用于当前活动商店，不写入普通商店开放存档。
SHOP_HOOK(shop_display_type,0x1016595fu,if(medal_event_shop(c)&&shop_record(c,c.r[0])){ret(c,1u);return;})
SHOP_HOOK(shop_enable,0x102093f5u,if(event_exclusive_sku(c,c.r[1])){ret(c,0u);return;}
if(medal_event_shop(c)){
    uint32_t row=shop_record(c,c.r[1]);ret(c,row&&rd<uint32_t>(c,row+28)?1u:0u);return;
})
SHOP_HOOK(shop_enable2,0x10209469u,if(event_exclusive_sku(c,c.r[1])){ret(c,0u);return;}
if(medal_event_shop(c)){
    uint32_t row=shop_record(c,c.r[1]);ret(c,row&&rd<uint32_t>(c,row+28)?1u:0u);return;
})
// 价格与目录不受普通商店促销及阵营过滤状态影响；原有过滤设置保持。
SHOP_HOOK(shop_unit_discount,0x1020b459u,if(medal_event_shop(c)&&
    c.r[14]>=0x10208b00u&&c.r[14]<0x1020c600u){ret(c,0u);return;})
SHOP_HOOK(shop_filter_state,0x10168d6fu,if(medal_event_shop(c)&&
    c.r[14]>=0x1020baa8u&&c.r[14]<0x1020bef9u){ret(c,0u);return;})
SHOP_HOOK(shop_maximum,0x10165709u,uint32_t row=shop_record(c,c.r[0]);if(row){ret(c,rd<uint32_t>(c,row+12));return;})
SHOP_HOOK(shop_stock,0x10165749u,uint32_t row=shop_record(c,c.r[0]);if(row&&rd<uint32_t>(c,row+20)==3){ret(c,rd<uint32_t>(c,row+16));return;})
// Medal packs listed in an Event catalog have an Event-local one-time stock.
// Native sold-out checks read global item stock directly; use the Event-local
// purchase count for these packs so another Event remains independent.
SHOP_HOOK(shop_medal_sold_out,0x10165835u,uint32_t row=shop_record(c,c.r[0]);if(row&&rd<uint32_t>(c,row+20)==3){ret(c,rd<uint32_t>(c,row+16)>=rd<uint32_t>(c,row+12));return;})
SHOP_HOOK(shop_catalog_forward,0x1020bb6bu,if(event_shop(c)){
    c.r[2]=rd<uint32_t>(c,H+12);c.r[3]=c.r[9]*4;c.pc=0x1020bba1u;return;
})
SHOP_HOOK(shop_catalog_previous,0x1020bae5u,if(event_shop(c)){
    c.r[3]=rd<uint32_t>(c,H+12)+c.r[11]*4+c.r[5];c.pc=0x1020bb05u;return;
})
SHOP_HOOK(shop_catalog_count,0x1020c087u,if(event_shop(c)){
    c.r[2]=0;wr<uint32_t>(c,c.r[5]+0x84,0u);
    wr<uint32_t>(c,c.r[5]+0x9c,0u);wr<uint32_t>(c,c.r[5]+0xa0,rd<uint32_t>(c,H+16));
    if(rd<uint32_t>(c,H+8)==1u){
        c.r[2]=0x22;c.r[3]=rd<uint32_t>(c,c.r[6]+0x24);wr<uint32_t>(c,c.r[3]+0x50,c.r[2]);
    }
    c.pc=0x1020c0cdu;return;
})
SHOP_HOOK(shop_catalog_update,0x1020c41fu,if(event_shop(c)){
    c.r[3]=rd<uint32_t>(c,rd<uint32_t>(c,H+12)+(c.r[7]-c.r[6])*4);
    c.pc=0x1020c2b3u;return;
})
// 活动勋章店（模式 2）使用活动底栏（BACK/OPTION/SHOP/MEDAL），不建立主菜单底栏与筛选/排序按钮。
SHOP_HOOK(shop_cockpit,0x1020bffbu,if(medal_event_shop(c)){c.r[0]=c.r[4];c.pc=0x1020c005u;return;})
SHOP_HOOK(shop_filter_cockpit,0x1020c00fu,if(medal_event_shop(c)){c.pc=0x1020c027u;return;})
SHOP_HOOK(shop_buy_request,0x1020b475u,if(event_shop(c)){
    uint32_t app=rd<uint32_t>(c,H+36);uint32_t index=rd<uint32_t>(c,app+0xb894);
    uint32_t panel=rd<uint32_t>(c,app+0x3380+index*4);
    if(!panel){ret(c,0u);return;}
    uint32_t sid=rd<uint32_t>(c,panel+0x224);
    uint32_t row=shop_record(c,sid);uint32_t authorization=rd<uint32_t>(c,H+44);
    if(!row||(medal_event_shop(c)&&!rd<uint32_t>(c,row+28))){ret(c,0u);return;}
    // 勋章店沿用原生勋章扣除与单位发放；开售权限由记录 +28 决定。
    if(medal_event_shop(c)){old_shop_buy_request(c);return;}
    if(!authorization){wr<uint32_t>(c,H+28,sid+1);ret(c,0u);return;}
    if(authorization!=sid+1){ret(c,0u);return;}
})
SHOP_HOOK(shop_medal_counter,0x10167ac5u,if(active(c)&&rd<uint32_t>(c,H+8)&&rd<uint32_t>(c,H+44)){
    uint32_t row=shop_record(c,rd<uint32_t>(c,H+44)-1);
    if(row&&rd<uint32_t>(c,row+20)==3&&c.r[1]==rd<uint32_t>(c,row+24))
        wr<uint32_t>(c,row+16,rd<uint32_t>(c,row+16)+c.r[2]);
})
// Offline cooperation reuses the Survival controller. Cooperative ex-data
// contains no frozen-POW drop mapping; the original zero-count fallback reads
// dummy float data as an animation ID. A declared empty mapping has no drop.
SHOP_HOOK(empty_frozen_drop_map,0x101bcbf9u,if(active(c)&&!rd<uint32_t>(c,c.r[0]+0x3c)){
    c.pc=0x101bcca5u;return;
})
SHOP_HOOK(empty_enemy_drop_map,0x101d5489u,if(active(c)&&!rd<uint32_t>(c,c.r[0]+0x3c)){
    c.pc=0x101d5503u;return;
})
SHOP_HOOK(trace_drop_creation,0x101df345u,if(active(c)&&c.r[2]==327u){wr<uint32_t>(c,H+68,c.r[14]);})
SHOP_HOOK(trace_drop_animation,0x101de017u,if(active(c)&&rd<uint32_t>(c,c.r[0]+0x78)==327u&&c.r[1]>=32u){
    wr<uint32_t>(c,H+56,c.r[14]);wr<uint32_t>(c,H+60,c.r[0]);wr<uint32_t>(c,H+64,c.r[1]);
})
static bool event_map(Context& c){return active(c)&&rd<uint32_t>(c,H+80);}
// H+84=1：历史活动经原生 EventMSD 场景运行，数据钩子仅回应该活动的 WorldType（H+72），
// 模式写入 H+76。H+84=0 保留扩展世界借用普通世界地图的既有行为。
static bool eventmsd(Context& c){return event_map(c)&&rd<uint32_t>(c,H+84);}
static bool legacy_map(Context& c){return event_map(c)&&!rd<uint32_t>(c,H+84);}
static bool map_wt(Context& c,uint32_t wt,bool legacy){return eventmsd(c)?wt==rd<uint32_t>(c,H+72):(event_map(c)&&legacy);}
static uint32_t stack_arg(Context& c){return rd<uint32_t>(c,c.r[13]);}
SHOP_HOOK(map_campaign_bonus,0x101669fdu,if(event_map(c)&&c.r[14]>=0x10100000u&&c.r[14]<0x10200000u){
    uint32_t base=rd<uint32_t>(c,H+140);uint32_t count=rd<uint32_t>(c,H+144);
    for(uint32_t i=0;i<count;i++){
        uint32_t row=base+i*16;
        if(rd<uint32_t>(c,row)==c.r[0]&&rd<uint32_t>(c,row+4)==c.r[1]&&rd<uint32_t>(c,row+8)==c.r[2]){
            ret(c,rd<uint32_t>(c,row+12));return;
        }
    }
})
static uint32_t map_record(Context& c,uint32_t id){
    if(!event_map(c))return 0;
    uint32_t base=rd<uint32_t>(c,H+92);uint32_t count=rd<uint32_t>(c,H+96);
    for(uint32_t i=0;i<count;i++)if(rd<uint32_t>(c,base+i*64)==id)return base+i*64;
    return 0;
}
static uint32_t map_slot(Context& c,uint32_t w,uint32_t a,uint32_t s){
    if(!event_map(c))return 0;
    uint32_t base=rd<uint32_t>(c,H+92);uint32_t count=rd<uint32_t>(c,H+96);
    for(uint32_t i=0;i<count;i++){uint32_t row=base+i*64;
        if(rd<uint32_t>(c,row+32)==w&&rd<uint32_t>(c,row+20)==a&&rd<uint32_t>(c,row+24)==s)return row;}
    return 0;
}
static uint32_t map_stage(Context& c,bool method){
    uint32_t w=c.r[method?1:0];uint32_t a=c.r[method?2:1];uint32_t s=c.r[method?3:2];
    return map_slot(c,w,a,s);
}
static bool stage_wt(Context& c,bool method){return map_wt(c,method?stack_arg(c):c.r[3],true);}
static uint32_t map_world(Context& c,uint32_t w){
    return w<rd<uint32_t>(c,H+148)?rd<uint32_t>(c,H+152)+w*12:0;
}
static bool map_has_area(Context& c,uint32_t w,uint32_t a){uint32_t row=map_world(c,w);return row&&a<rd<uint32_t>(c,row+4);}
// 猫咪活动保留原生 EventMSD 单关确认路径；主世界任务仍采用 GT_WorldMap。
// 场景、WorldType、宿主身份与当前槽位共同限定几何读取，避免复用任务地址跨页生效。
static bool cat_event_scene(Context& c,uint32_t app){
    return eventmsd(c)&&rd<uint32_t>(c,H+156)&&rd<uint32_t>(c,H+72)==2u&&
           app&&app==rd<uint32_t>(c,H+36)&&rd<uint32_t>(c,app+0x22bcu)==160u&&
           rd<uint32_t>(c,app+0xc63cu)==2u;
}
static bool cat_event_geometry(Context& c,uint32_t app,uint32_t task){
    if(!cat_event_scene(c,app)||!task||task!=rd<uint32_t>(c,app+0x33d0u)||
       rd<uint32_t>(c,task+0x1b4u)!=28u)return false;
    uint32_t function=rd<uint32_t>(c,task);
    return function==0x10213a6du||function==0x101f6b69u;
}
static float cat_page_width(Context& c,uint32_t app){
    uint32_t manager=app?rd<uint32_t>(c,app+0x98u):0u;
    int32_t width=manager?int32_t(rd<uint32_t>(c,manager+0x18u)):0;
    return width>0&&width<=4096?float(width):1136.0f;
}
// 初始化时 AppMain 尚处于 158/159。原生 setParam 前的已生成块保留页宽、
// 惯性及触点矩形，只依据当前分期的世界表扩展最大页索引。
SHOP_HOOK(cat_event_paging_init,0x101f739du,{
    uint32_t app=c.r[4];uint32_t count=rd<uint32_t>(c,H+148);
    uint32_t scene=app?rd<uint32_t>(c,app+0x22bcu):0u;
    if(eventmsd(c)&&rd<uint32_t>(c,H+156)&&rd<uint32_t>(c,H+72)==2u&&
       app&&app==rd<uint32_t>(c,H+36)&&rd<uint32_t>(c,app+0xc63cu)==2u&&
       (scene==158u||scene==159u||scene==160u)&&count>=1u&&count<=2u){
        wr<uint32_t>(c,app+0xc630u,count-1u);
    }
})
// 区域坐标属于单页。真实世界任务采用当前页起点，使 world1 的原生
// scroll=-pageWidth 与 originX=480+pageWidth 抵消，绘制和触点保持同源。
SHOP_HOOK(cat_event_world_origin,0x10213a6du,{
    uint32_t app=rd<uint32_t>(c,H+36);uint32_t task=c.r[0];
    if(cat_event_geometry(c,app,task)){
        uint32_t world=rd<uint32_t>(c,app+0xc624u);
        if(world<rd<uint32_t>(c,H+148))wr<float>(c,task+0x84u,480.0f+float(world)*cat_page_width(c,app));
    }
})
static uint32_t cat_draw_copy(Context& c,uint32_t geometry,uint32_t destination,float page_offset){
    for(uint32_t offset=0;offset<0x228u;offset+=4)wr<uint32_t>(c,destination+offset,rd<uint32_t>(c,geometry+offset));
    constexpr float overview=0.6529411673545837f;
    float sx=rd<float>(c,geometry+0xa8u),sy=rd<float>(c,geometry+0xacu);
    float ox=rd<float>(c,geometry+0x84u)+rd<float>(c,geometry+0x9cu)+page_offset;
    float oy=rd<float>(c,geometry+0x88u)+rd<float>(c,geometry+0xa0u);
    wr<float>(c,destination+0x84u,ox+(-88.0f-(480.0f-720.0f*overview))*sx/overview);
    wr<float>(c,destination+0x88u,oy+(60.0f-(304.0f-356.0f*overview))*sy/overview);
    wr<float>(c,destination+0x9cu,0.0f);wr<float>(c,destination+0xa0u,0.0f);
    wr<float>(c,destination+0xa8u,2.0f*sx/overview);wr<float>(c,destination+0xacu,1.5f*sy/overview);
    wr<uint32_t>(c,destination+0x3cu,57u);wr<uint32_t>(c,destination+0x5cu,65u);wr<uint32_t>(c,destination+0x50u,0u);
    return destination;
}
// 相邻页只在总览/水平滚动期间绘制。嵌套调用沿用现有 LAB 的原生分派，
// 保留外层寄存器与栈，并使用 H196 中独立的相邻页任务副本。
static bool cat_draw_neighbor(Context& c,uint32_t task){
    uint32_t saved_r[16];std::memcpy(saved_r,c.r,sizeof saved_r);
    uint64_t saved_d[32];std::memcpy(saved_d,c.d,sizeof saved_d);
    uint32_t n=c.n,z=c.z,cf=c.c,v=c.v,fpscr=c.fpscr,pc=c.pc;
    constexpr uint32_t sentinel=0x1fff0000u;
    c.r[13]=(c.r[13]-96u)&~7u;c.r[0]=task;c.r[14]=sentinel;c.pc=0x10213b35u;
    NativeImports* host=msd_imports(&c);bool ok=false;
    for(uint32_t i=0;i<100000u;++i){
        uint32_t address=c.pc&~1u;
        if(address==sentinel){ok=true;break;}
        if(address>=0x1f000000u&&address<0x1f010000u){
            if(!msd_native_import(c,address,host))break;
            c.blocks++;if(c.error)break;continue;
        }
        if(uint32_t thunk=msd_decoder_thunk(host,c.pc)){c.pc=thunk;continue;}
        Block function=find_block(c.pc);
        if(!function){missing(c,c.pc);break;}
        function(c);c.blocks++;if(c.error)break;
    }
    std::memcpy(c.r,saved_r,sizeof saved_r);std::memcpy(c.d,saved_d,sizeof saved_d);
    c.n=n;c.z=z;c.c=cf;c.v=v;c.fpscr=fpscr;c.pc=pc;
    if(!ok&&!c.error)missing(c,0x10213b35u);
    return ok;
}
SHOP_HOOK(map_area_count,0x10165efdu,if(map_wt(c,c.r[1],true)){uint32_t row=map_world(c,c.r[0]);ret(c,row?rd<uint32_t>(c,row+4):0);return;})
SHOP_HOOK(map_area_data,0x10165f49u,if(map_wt(c,c.r[2],c.r[2]==0)){
    uint32_t row=map_world(c,c.r[0]);ret(c,map_has_area(c,c.r[0],c.r[1])?rd<uint32_t>(c,rd<uint32_t>(c,row)+c.r[1]*4):0);return;
})
SHOP_HOOK(map_area_name,0x10166085u,if(map_wt(c,c.r[3],c.r[3]==0)){
    uint32_t row=map_slot(c,c.r[0],c.r[1],0);
    if(row){uint32_t i=(row-rd<uint32_t>(c,H+92))/64;ret(c,rd<uint32_t>(c,rd<uint32_t>(c,H+100)+i*4));return;}
})
SHOP_HOOK(map_mission,0x101d09fdu,uint32_t row=map_record(c,c.r[1]);if(row){ret(c,rd<uint32_t>(c,row+8));return;})
SHOP_HOOK(map_world_enable,0x101664adu,if(map_wt(c,c.r[1],true)){ret(c,map_world(c,c.r[0])!=0);return;})
SHOP_HOOK(map_area_enable,0x10166471u,if(map_wt(c,c.r[2],true)){ret(c,map_has_area(c,c.r[0],c.r[1]));return;})
SHOP_HOOK(map_area_open,0x10166597u,if(map_wt(c,c.r[2],true)){ret(c,map_has_area(c,c.r[0],c.r[1]));return;})
SHOP_HOOK(map_world_init,0x10215009u,if(legacy_map(c)){
    uint32_t task=rd<uint32_t>(c,c.r[0]+0x3360+c.r[1]*4);
    if(task){bool cats=rd<uint32_t>(c,H+156)!=0;
        wr<uint32_t>(c,task+0x3c,21u);wr<uint32_t>(c,task+0x40,0xffffffffu);
        // The original Event task table also uses world picture 56 above
        // its gray grid. Keep that map layer for every non-Neko Event.
        wr<uint32_t>(c,task+0x50,cats?0xffffffffu:56u);wr<uint32_t>(c,task+0x54,cats?0xffffffffu:56u);
        wr<uint32_t>(c,task+0x5c,27u);
        wr<uint32_t>(c,H+188,0u);
    }
})
// Battle resource initialization can occur after the map UI is suspended.
// Retain the selected Event track throughout that initialization as well.
SHOP_HOOK(map_bgm,0x101663c1u,if(active(c)&&rd<uint32_t>(c,H+164)){ret(c,rd<uint32_t>(c,H+164));return;})
// BattleScene::sceneActivate starts a stage track through FrameworkInstance.
// Victory (104) and defeat (105) effects request their own music during the
// same battle scene. Restrict substitution to the stage activation callsite.
SHOP_HOOK(map_music_request,0x101c677du,if(active(c)&&rd<uint32_t>(c,H+164)&&c.r[14]==0x101d52cbu){
    uint32_t scene=rd<uint32_t>(c,c.r[0]+0x22bc);
    if(scene==99u||scene==100u)c.r[1]=rd<uint32_t>(c,H+164);
})
// 猫咪共享图集经独立绘制任务映射到原生世界几何。旧普通地图使用槽 29–31；
// EventMSD 使用槽 28。真实任务的中心、比例、父链及触点矩形保持原生状态。
SHOP_HOOK(cat_world_draw,0x10213b35u,if(event_map(c)&&rd<uint32_t>(c,H+156)){
    uint32_t geometry=c.r[0];uint32_t task=rd<uint32_t>(c,H+196);uint32_t slot=rd<uint32_t>(c,geometry+0x1b4);
    bool native=eventmsd(c);
    uint32_t app=rd<uint32_t>(c,H+36);
    if(task&&((!native&&slot>=29u&&slot<32u)||(native&&cat_event_geometry(c,app,geometry)))){
        if(native&&rd<uint32_t>(c,H+148)>1u&&rd<float>(c,geometry+0x1e0u)<1.0f&&rd<float>(c,geometry+0xa8u)<1.0f){
            uint32_t world=rd<uint32_t>(c,app+0xc624u);uint32_t neighbor=0u;
            for(uint32_t page=0;page<rd<uint32_t>(c,H+148)&&neighbor<2u;++page){
                if(page==world)continue;
                uint32_t copy=cat_draw_copy(c,geometry,task+(++neighbor)*0x228u,
                                           float(int32_t(page)-int32_t(world))*cat_page_width(c,app));
                if(!cat_draw_neighbor(c,copy))return;
            }
        }
        c.r[0]=cat_draw_copy(c,geometry,task+(native?0u:slot-29u)*0x228u,0.0f);
    }
})
// EventMSD 猫咪背景原先以固定 (-88,60)、(2,1.5) 绘制；纹理已在世界几何
// 的同层绘制路径重排，停用固定副本以保持缩放及返回期间的单一图层。
SHOP_HOOK(cat_event_background,0x101f56f5u,{
    uint32_t app=rd<uint32_t>(c,H+36);
    if(cat_event_scene(c,app)&&rd<uint32_t>(c,H+196)&&c.r[0]==rd<uint32_t>(c,app+0x3364u)){
        ret(c,0u);return;
    }
})
// 猫咪每区域一关，原生 WT2 选择区域后直接进入 InfoInit/state19，跳过
// 通常区域的 StageWorldMapInit。依据当前分期区域表设置同一几何任务的
// 中心目标，并使用原生标准比例 3.0；每帧 1/4 插值与 BACK 的复原沿用原生。
SHOP_HOOK(cat_event_info_zoom,0x101f778du,{
    uint32_t app=c.r[0];uint32_t task=app?rd<uint32_t>(c,app+0x33d0u):0u;
    if(cat_event_geometry(c,app,task)){
        uint32_t world=rd<uint32_t>(c,app+0xc624u);uint32_t area=rd<uint32_t>(c,app+0xc628u);
        uint32_t row=map_world(c,world);
        if(map_has_area(c,world,area)){
            uint32_t record=rd<uint32_t>(c,rd<uint32_t>(c,row)+area*4u);
            wr<float>(c,task+0x1ecu,float(int32_t(rd<uint32_t>(c,record+4u))));
            wr<float>(c,task+0x1f0u,float(int32_t(rd<uint32_t>(c,record+8u))));
            wr<float>(c,task+0x1e0u,3.0f);wr<float>(c,task+0x1e4u,3.0f);
        }
    }
})
SHOP_HOOK(map_background,0x102146cdu,if(legacy_map(c)){
    // Keep the native task's animated position and scale between draws.
    uint32_t task=c.r[0];
    if(rd<uint32_t>(c,H+156)){ret(c,0u);return;}
    wr<uint32_t>(c,task+0x3c,21u);wr<uint32_t>(c,task+0x5c,27u);
    wr<uint32_t>(c,task+0x50,147u);wr<uint32_t>(c,task+0x54,147u);
    if(rd<uint32_t>(c,H+188)!=task){
        wr<uint32_t>(c,H+188,task);
        wr<uint32_t>(c,task+0x84,0xc2b00000u);wr<uint32_t>(c,task+0x88,0u);
    }
    c.pc=0x101f56f5u;return;
})
// The Neko map numbers only ordinary regions. Boss regions do not consume a
// number; campaign area indices otherwise select unrelated picture frames.
SHOP_HOOK(cat_area_labels,0x10200161u,if(legacy_map(c)&&rd<uint32_t>(c,H+156)&&c.r[14]==0x10213f13u){
    uint32_t w=rd<uint32_t>(c,c.r[0]+0xb1ec);uint32_t a=rd<uint32_t>(c,c.r[1]+0x224);uint32_t world=map_world(c,w);
    if(world&&a<rd<uint32_t>(c,world+4)){
        uint32_t areas=rd<uint32_t>(c,world);uint32_t area=rd<uint32_t>(c,areas+a*4);
        if(rd<uint16_t>(c,area+14)==0xffffu){
            uint32_t label=0;
            for(uint32_t i=0;i<a;i++)if(rd<uint16_t>(c,rd<uint32_t>(c,areas+i*4)+14)==0xffffu)label++;
            wr<uint32_t>(c,c.r[13],105u+label);
        }
    }
})
SHOP_HOOK(map_stage_enable,0x10166411u,if(stage_wt(c,false)){ret(c,map_stage(c,false)!=0);return;})
SHOP_HOOK(map_stage_save_enable,0x10167f0du,if(stage_wt(c,true)){ret(c,map_stage(c,true)!=0);return;})
SHOP_HOOK(map_stage_clear,0x101680cdu,if(stage_wt(c,true)){uint32_t row=map_stage(c,true);ret(c,row?rd<uint32_t>(c,row+12):0);return;})
SHOP_HOOK(map_stage_time,0x101681afu,if(stage_wt(c,true)){uint32_t row=map_stage(c,true);ret(c,row?rd<uint32_t>(c,row+16):0);return;})
SHOP_HOOK(map_stage_prisoner,0x1016830fu,if(stage_wt(c,true)){uint32_t row=map_stage(c,true);ret(c,row?rd<uint32_t>(c,row+44):0);return;})
SHOP_HOOK(map_stage_prisoner_max,0x10166165u,if(stage_wt(c,false)){uint32_t row=map_stage(c,false);ret(c,row?rd<uint32_t>(c,row+40):0);return;})
static uint32_t prisoner_total(Context& c,uint32_t w,uint32_t a,bool saved){
    uint32_t result=0,base=rd<uint32_t>(c,H+92),count=rd<uint32_t>(c,H+96);bool parts=rd<uint32_t>(c,H+184)!=0;
    for(uint32_t i=0;i<count;i++){
        uint32_t row=base+i*64;
        if(rd<uint32_t>(c,row+32)==w&&rd<uint32_t>(c,row+20)==a){
            uint32_t value=rd<uint32_t>(c,row+(saved?44:40));
            if(parts){if(value>result)result=value;}else result+=value;
        }
    }
    return result;
}
SHOP_HOOK(map_area_prisoner_max,0x101661b5u,if(map_wt(c,c.r[2],true)){ret(c,prisoner_total(c,c.r[0],c.r[1],false));return;})
static Block old_map_prisoner_rate;
static void map_prisoner_rate(Context& c){
    if(map_wt(c,c.r[2],c.r[14]<0x10100000u||c.r[14]>=0x10200000u)){
        uint32_t maximum=prisoner_total(c,c.r[0],c.r[1],false),saved=prisoner_total(c,c.r[0],c.r[1],true);
        ret(c,maximum?(saved>=maximum?100u:saved*100u/maximum):0u);return;
    }
    old_map_prisoner_rate(c);
}
static uint32_t prisoner_row(Context& c,uint32_t pid){
    if(!event_map(c))return 0;
    uint32_t base=rd<uint32_t>(c,H+168),count=rd<uint32_t>(c,H+172);
    for(uint32_t i=0;i<count;i++)if(rd<uint32_t>(c,base+i*20)==pid)return base+i*20;
    return 0;
}
SHOP_HOOK(map_prisoner_data,0x101668a9u,uint32_t row=prisoner_row(c,c.r[0]);if(row){ret(c,rd<uint32_t>(c,row+4));return;})
static uint32_t prisoner_text(Context& c,uint32_t field){
    uint32_t row=prisoner_row(c,c.r[0]);
    return row&&c.r[1]<11?rd<uint32_t>(c,rd<uint32_t>(c,row+field)+c.r[1]*4):0;
}
SHOP_HOOK(map_prisoner_name,0x10166911u,uint32_t text=prisoner_text(c,8);if(text){ret(c,text);return;})
SHOP_HOOK(map_prisoner_info1,0x10166925u,uint32_t text=prisoner_text(c,12);if(text){ret(c,text);return;})
SHOP_HOOK(map_prisoner_info2,0x10166939u,uint32_t text=prisoner_text(c,16);if(text){ret(c,text);return;})
SHOP_HOOK(map_prisoner_init,0x102130e1u,if(legacy_map(c)){
    if(!rd<uint32_t>(c,H+176)){wr<uint32_t>(c,H+180,1u);ret(c,0);return;}
    uint32_t app=c.r[0];
    wr<uint32_t>(c,app+0xc624,rd<uint32_t>(c,app+0xb1ec));
    wr<uint32_t>(c,app+0xc628,rd<uint32_t>(c,app+0xb1f0));wr<uint32_t>(c,app+0xc63c,0u);
})
// The POW cockpit button uses picture 117. Disable its native input callback
// and drawing when the selected Event world has no POW rewards.
// 无商店活动的 SHOP 图标 33 与基地面板 4 同时停用绘制及输入。
SHOP_HOOK(map_prisoner_button_input,0x101ff4e9u,{
    uint32_t task=c.r[0];uint32_t id=rd<uint32_t>(c,task+0x50);
    if(id==33u&&hidden_shop(c)){wr<uint32_t>(c,task+0x7c,rd<uint32_t>(c,task+0x7c)|0xa0u);ret(c,0u);return;}
    if(event_map(c)&&!rd<uint32_t>(c,H+176)&&id==117u){ret(c,0u);return;}
})
SHOP_HOOK(map_prisoner_button_draw,0x102003bdu,{
    uint32_t id=rd<uint32_t>(c,c.r[0]+0x50);
    if((id==33u&&hidden_shop(c))||(event_map(c)&&!rd<uint32_t>(c,H+176)&&id==117u)){ret(c,0u);return;}
})
SHOP_HOOK(base_shop_panel,0x1021d63du,{
    uint32_t task=c.r[0];
    // 基地“商店”面板仅对应活动代币兑换店。
    uint32_t app=active(c)?rd<uint32_t>(c,H+36):0u;
    bool hidden=hidden_shop(c)||(app&&!rd<uint32_t>(c,H+16)&&rd<uint32_t>(c,app+0x22bc)==67u);
    if(hidden&&rd<uint32_t>(c,task+0x50)==4u){
        wr<uint32_t>(c,task+0x7c,rd<uint32_t>(c,task+0x7c)|0xa0u);ret(c,0u);return;
    }
})
// 活动拾取物计数（战斗左下 HUD）：1.46 BattlePlayerOperator::createGrahics 以 1.39 版 event_otakara_ui.obm 的坐标
// （内嵌星形 9 帧、数字 10 项与 "x"）裁切 1.46 重排后的图集，得到错位图块。H+216 非零时为宿主提供的 1.39 布局
// 图集文件名，仅替换该调用点（返回地址 0x101dadc2）的 readFileFromOBM 参数；H+220 非零时指向 9 项转换表，
// 于首次循环前覆盖栈上的星形帧副本（秘宝活动以金币代替）。
SHOP_HOOK(hud_item_atlas,0x101c3badu,{
    if(active(c)&&(c.r[14]&~1u)==0x101dadc2u&&rd<uint32_t>(c,H+216))c.r[1]=rd<uint32_t>(c,H+216);
})
SHOP_HOOK(hud_item_frames,0x101dade5u,{
    uint32_t table=active(c)?rd<uint32_t>(c,H+220):0u;
    if(table&&c.r[8]==c.r[13]+0xb0u)for(uint32_t i=0;i<9u*16u;i+=4u)wr<uint32_t>(c,c.r[8]+i,rd<uint32_t>(c,table+i));
})
SHOP_HOOK(map_stage_new,0x10167ff1u,if(stage_wt(c,true)){ret(c,0);return;})
SHOP_HOOK(map_stage_new_delete,0x1016807du,if(stage_wt(c,true)){ret(c,0);return;})
SHOP_HOOK(map_area_new,0x10168659u,if(map_wt(c,c.r[3],true)){ret(c,0);return;})
SHOP_HOOK(map_area_new_delete,0x10168705u,if(map_wt(c,c.r[3],true)){ret(c,0);return;})
SHOP_HOOK(map_start_battle,0x101e5b99u,uint32_t row=map_record(c,c.r[1]);if(row){
    wr<uint32_t>(c,H+112,rd<uint32_t>(c,row+28)+1);wr<uint32_t>(c,H+164,rd<uint32_t>(c,row+36));c.r[1]=rd<uint32_t>(c,row+4);
    if(rd<uint32_t>(c,H+108)){c.pc=0x101e5cffu;return;}
})
// 历史活动进入原生 EventMSD 场景（初始化与战后返回）时写入该活动的 WorldType 与模式；
// 女教官基地出击按原生 1.46 写入合作活动值，此处按所选历史活动覆盖。
SHOP_HOOK(eventmsd_init,0x101f7709u,if(eventmsd(c)){
    uint32_t app=c.r[0];wr<uint32_t>(c,app+0xc63c,rd<uint32_t>(c,H+72));wr<uint32_t>(c,app+0xc8c8,rd<uint32_t>(c,H+76));
    // 首次进入时置于该活动的原生世界号（H+192），区域与关卡归零；战后返回经 Init2 保留当前位置。
    wr<uint32_t>(c,app+0xc624,rd<uint32_t>(c,H+192));wr<uint32_t>(c,app+0xc628,0u);wr<uint32_t>(c,app+0xc62c,0u);
})
SHOP_HOOK(eventmsd_init2,0x101f772fu,if(eventmsd(c)){
    uint32_t app=c.r[0];wr<uint32_t>(c,app+0xc63c,rd<uint32_t>(c,H+72));wr<uint32_t>(c,app+0xc8c8,rd<uint32_t>(c,H+76));
})
// 1.46 中 WorldType 2 专用于猫咪联动地图；经典活动以 WorldType 1 运行并保留原生世界号，
// EventAreaCheck 对 WorldType≠2 的非零世界会转回主菜单，历史活动中放行。
SHOP_HOOK(eventmsd_area_check,0x101f6f19u,if(eventmsd(c)){ret(c,0u);return;})
// 1.37/1.38 的 Survival BASE 原生菜单任务位于 (300,200)。1.39/1.46 为
// (603,553)，与历史阿玛迪斯母舰区域的原生坐标重叠。H+204/+208 为宿主
// 按活动来源登记的 BASE 坐标，H+212 为有效标记；未登记的活动沿用原生布局。
// 绘制与 PushPanel 共用当前 BASE 任务，动作初始坐标同步保持。
SHOP_HOOK(eventmsd_survival_base,0x101f4ef9u,if(eventmsd(c)&&rd<uint32_t>(c,H+72)==3u&&rd<uint32_t>(c,H+212)){
    uint32_t app=rd<uint32_t>(c,H+36);uint32_t task=c.r[0];
    float x=rd<float>(c,H+204);float y=rd<float>(c,H+208);
    if(app&&task==rd<uint32_t>(c,app+0x340cu)&&rd<uint32_t>(c,task)==0x101f4ef9u&&
       rd<uint32_t>(c,app+0xc63cu)==3u&&x>=0.0f&&x<=1500.0f&&y>=0.0f&&y<=700.0f){
        wr<float>(c,task+0x84u,x);wr<float>(c,task+0x88u,y);
        wr<float>(c,task+0x90u,x);wr<float>(c,task+0x94u,y);
    }
})
// Survival 类活动（模式 5）经 BattleInit_SurvivalMode 开战，登记所选关卡供宿主结算。
SHOP_HOOK(eventmsd_survival_battle,0x101e5cffu,if(eventmsd(c)){
    uint32_t base=rd<uint32_t>(c,H+92);uint32_t count=rd<uint32_t>(c,H+96);
    for(uint32_t i=0;i<count;i++){uint32_t row=base+i*64;
        if(rd<uint32_t>(c,row+4)==c.r[1]){wr<uint32_t>(c,H+112,rd<uint32_t>(c,row+28)+1);wr<uint32_t>(c,H+164,rd<uint32_t>(c,row+36));break;}}
})
// 巨灵战车零件奖励（人质 61–66）为单位类型而奖励 ID 无效。UpdateScrollPrisoner 以
// GetUnitLevelSaveData(ID)==-1 判定未拥有并写入、弹窗；无效 ID 写入不生效而反复弹出。
// 活动中对无效 ID 按已拥有回应，人质页保留原生“達成”显示，零件奖励由宿主按活动进度发放。
SHOP_HOOK(prisoner_invalid_unit,0x10167af1u,if(event_map(c)&&c.r[1]==0xffffffffu){ret(c,0u);return;})
SHOP_HOOK(selector_mission,0x101d0a0fu,if(rd<uint32_t>(c,H+124)){
    ret(c,c.r[1]<rd<uint32_t>(c,H+132)?rd<uint32_t>(c,H+128)+c.r[1]*112:0);return;
})
SHOP_HOOK(selector_enabled,0x10168b5du,if(rd<uint32_t>(c,H+124)&&c.r[14]>=0x1020d000u&&c.r[14]<0x1020eb00u){ret(c,c.r[1]<rd<uint32_t>(c,H+132));return;})
SHOP_HOOK(selector_cleared,0x10168bc1u,if(rd<uint32_t>(c,H+124)&&c.r[14]>=0x1020d000u&&c.r[14]<0x1020eb00u){ret(c,0);return;})
SHOP_HOOK(selector_chosen,0x1020e805u,if(rd<uint32_t>(c,H+124)){
    wr<uint32_t>(c,H+136,c.r[11]+1);c.pc=0x1020e7f5u;return;
})
// Selecting an Event has no stamina charge. Its stages retain their own costs.
SHOP_HOOK(selector_cost_icon,0x102005ddu,if(rd<uint32_t>(c,H+124)&&c.r[14]==0x1020e9c5u){ret(c,0);return;})
SHOP_HOOK(selector_cost_number,0x101c4935u,if(rd<uint32_t>(c,H+124)&&c.r[14]==0x1020ea05u){ret(c,0);return;})
extern "C" __declspec(dllexport) void msd_enable_historical_event_hooks(){
    static bool done=false;if(done)return;done=true;
    original_end=find_block(0x101ea099u);
    original_continue=find_block(0x10168a03u);
    register_block(0x101ea099u,event_end);
    register_block(0x10168a03u,no_event_continuation);
#define INSTALL(NAME,PC) old_##NAME=find_block(PC);register_block(PC,NAME)
    INSTALL(main_menu_reset,0x10204051u);
    INSTALL(shop_data,0x101655c9u);INSTALL(shop_coin_price,0x10165977u);
    INSTALL(shop_standard_price,0x101656c5u);
    INSTALL(shop_discount,0x1016596bu);
    INSTALL(shop_display_type,0x1016595fu);INSTALL(shop_enable,0x102093f5u);
    INSTALL(shop_enable2,0x10209469u);INSTALL(shop_unit_discount,0x1020b459u);
    INSTALL(shop_filter_state,0x10168d6fu);
    INSTALL(shop_maximum,0x10165709u);INSTALL(shop_stock,0x10165749u);
    INSTALL(shop_medal_sold_out,0x10165835u);
    INSTALL(shop_catalog_forward,0x1020bb6bu);INSTALL(shop_catalog_previous,0x1020bae5u);
    INSTALL(shop_catalog_count,0x1020c087u);INSTALL(shop_catalog_update,0x1020c41fu);
    INSTALL(shop_buy_request,0x1020b475u);
    INSTALL(shop_cockpit,0x1020bffbu);INSTALL(shop_filter_cockpit,0x1020c00fu);
    INSTALL(shop_medal_counter,0x10167ac5u);
    INSTALL(empty_frozen_drop_map,0x101bcbf9u);
    INSTALL(empty_enemy_drop_map,0x101d5489u);
    INSTALL(trace_drop_creation,0x101df345u);INSTALL(trace_drop_animation,0x101de017u);
    INSTALL(map_area_count,0x10165efdu);INSTALL(map_area_data,0x10165f49u);INSTALL(map_area_name,0x10166085u);
    INSTALL(map_campaign_bonus,0x101669fdu);
    old_map_prisoner_rate=find_block(0x101669fdu);register_block(0x101669fdu,map_prisoner_rate);
    INSTALL(map_stage_prisoner_max,0x10166165u);INSTALL(map_area_prisoner_max,0x101661b5u);
    INSTALL(map_prisoner_data,0x101668a9u);INSTALL(map_prisoner_name,0x10166911u);
    INSTALL(map_prisoner_info1,0x10166925u);INSTALL(map_prisoner_info2,0x10166939u);
    INSTALL(map_prisoner_init,0x102130e1u);
    INSTALL(map_prisoner_button_input,0x101ff4e9u);
    INSTALL(map_prisoner_button_draw,0x102003bdu);
    INSTALL(base_shop_panel,0x1021d63du);
    INSTALL(hud_item_atlas,0x101c3badu);INSTALL(hud_item_frames,0x101dade5u);
    INSTALL(map_world_init,0x10215009u);INSTALL(map_bgm,0x101663c1u);
    INSTALL(map_background,0x102146cdu);
    INSTALL(cat_world_draw,0x10213b35u);
    INSTALL(cat_event_background,0x101f56f5u);INSTALL(cat_event_info_zoom,0x101f778du);
    INSTALL(cat_event_paging_init,0x101f739du);INSTALL(cat_event_world_origin,0x10213a6du);
    INSTALL(map_music_request,0x101c677du);
    INSTALL(cat_area_labels,0x10200161u);
    INSTALL(map_mission,0x101d09fdu);INSTALL(map_world_enable,0x101664adu);
    INSTALL(map_area_enable,0x10166471u);INSTALL(map_area_open,0x10166597u);
    INSTALL(map_stage_enable,0x10166411u);INSTALL(map_stage_save_enable,0x10167f0du);
    INSTALL(map_stage_clear,0x101680cdu);INSTALL(map_stage_time,0x101681afu);INSTALL(map_stage_prisoner,0x1016830fu);
    INSTALL(map_stage_new,0x10167ff1u);INSTALL(map_stage_new_delete,0x1016807du);
    INSTALL(map_area_new,0x10168659u);INSTALL(map_area_new_delete,0x10168705u);
    INSTALL(map_start_battle,0x101e5b99u);
    INSTALL(eventmsd_init,0x101f7709u);INSTALL(eventmsd_area_check,0x101f6f19u);INSTALL(eventmsd_init2,0x101f772fu);
    INSTALL(eventmsd_survival_base,0x101f4ef9u);
    INSTALL(eventmsd_survival_battle,0x101e5cffu);INSTALL(prisoner_invalid_unit,0x10167af1u);
    INSTALL(selector_mission,0x101d0a0fu);INSTALL(selector_enabled,0x10168b5du);
    INSTALL(selector_cleared,0x10168bc1u);INSTALL(selector_chosen,0x1020e805u);
    INSTALL(selector_cost_icon,0x102005ddu);INSTALL(selector_cost_number,0x101c4935u);
}
