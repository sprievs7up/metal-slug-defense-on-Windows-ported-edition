// 里地图扩展页（里世界 4 起，2026-10-19）：世界目录中写 "ura_page" 的世界显示在原生里地图的第 4 页之后。
// 原生里地图只有 3 页（世界号 9–11，页号 = 世界号 − 9，页面任务在菜单槽 0x1d–0x1f），每个区域最多 5 关
// （区域记录 5 个关卡指针、关卡图标任务槽 0x16–0x1a、存档按“世界号×80 + 区域×5 + 关卡”编排）。
// 宿主在共享头 H 写入魔数后，下列钩子对扩展世界号返回宿主数据，其余世界号沿用原生路径：
//   区域与关卡数据（可超过 5 关）、任务记录（关卡编号按原生规则 (世界号+1)×1000 + (区域+1)×10 + 关卡+1）、
//   开放 / 通关 / 新标记 / 用时 / 评级奖励（宿主进度表，按稳定键保存于 campaign_progress.json）、人质（恒为 0）、
//   区域通关奖励（区域记录 +0x48 的奖励表，H+64 为 1 时有效；2026-11-10，版本 3）；
//   里地图场景：菜单表副本加入扩展页的页面任务（槽 base+k），页数上限 b210 = 2 + 扩展页数，
//   页面任务槽号 0x1d+页号 ≥ 0x20 时换为扩展槽；第 6 关起的关卡图标占用上一区域箭头的槽 0x1b，
//   区域画面期间箭头任务暂存于 H+52，信息窗与区域画面结束时按原生顺序复原。
// H：+0 魔数 'URA4'，+4 扩展页数 N，+8 首个扩展世界号 W0（12），+12 扩展页面任务槽基址，
//    +16 区域表（每个扩展世界 0x44 字节：区域数 + 16 个区域记录指针），+20 任务记录表（每条 120 字节），+24 记录数，
//    +28 关卡进度表（每关 8 字节：+0 标志 1 开放 / 2 通关 / 4 新，+4 用时），+32 区域进度表（每区域 4 字节：1 新 / 2 评级奖励已领取），
//    +36 写入计数（宿主据此保存），+40 菜单表副本，+44 副本项数，+48 箭头暂存标志，+52 暂存的上一区域箭头任务，
//    +56 主菜单背景关卡表（关卡编号，int32），+60 表项数（2026-11-08，menu_bg），
//    +64 区域记录含通关奖励表指针的标志（2026-11-10）。
// 区域记录：原生布局（+0 名称编号，+4/+8 地图坐标，+0xc 略缩图，+0xe 头目 −1，+0x10 人质 −1，+0x12 关卡数，+0x14 起关卡指针，
//    可多于 5 个），+0x40 关卡进度起始序号，+0x44 区域进度序号，+0x48 通关奖励表指针（每项 12 字节：类型、编号、数量，
//    类型 −1 结束；类型 11 为勋章；0 为无奖励）。关卡记录为原生 0x18 字节布局。
#include "aot_runtime.h"
namespace {
constexpr uint32_t H=0x1ffe9000u,MAGIC=0x34415255u;
constexpr uint32_t PAGE_SLOT0=0x1du,ARROW_PREV=0x33ccu;
bool active(Context& c){return rd<uint32_t>(c,H)==MAGIC;}
bool extra(Context& c,uint32_t world,uint32_t wt){
    if(!active(c)||wt!=0u)return false;
    uint32_t w0=rd<uint32_t>(c,H+8u),n=rd<uint32_t>(c,H+4u);
    return world>=w0&&world<w0+n;
}
uint32_t area_rec(Context& c,uint32_t world,uint32_t area){
    uint32_t row=rd<uint32_t>(c,H+16u)+(world-rd<uint32_t>(c,H+8u))*0x44u;
    return area<rd<uint32_t>(c,row)&&area<16u?rd<uint32_t>(c,row+4u+area*4u):0u;
}
uint32_t stage_count(Context& c,uint32_t rec){return rec?uint32_t(rd<int16_t>(c,rec+0x12u)):0u;}
uint32_t stage_slot(Context& c,uint32_t world,uint32_t area,uint32_t stage){
    uint32_t rec=area_rec(c,world,area);
    if(!rec||stage>=stage_count(c,rec))return 0u;
    return rd<uint32_t>(c,H+28u)+(rd<uint32_t>(c,rec+0x40u)+stage)*8u;
}
uint32_t area_slot(Context& c,uint32_t world,uint32_t area){
    uint32_t rec=area_rec(c,world,area);
    return rec?rd<uint32_t>(c,H+32u)+rd<uint32_t>(c,rec+0x44u)*4u:0u;
}
void bump(Context& c){wr<uint32_t>(c,H+36u,rd<uint32_t>(c,H+36u)+1u);}
void ret(Context& c,uint32_t value){c.r[0]=value;c.pc=c.r[14];}
uint32_t arg(Context& c,uint32_t i){return rd<uint32_t>(c,c.r[13]+i*4u);}
bool ura_scene(Context& c,uint32_t app){uint32_t s=rd<uint32_t>(c,app+0x22bcu);return s>=131u&&s<=136u;}
// 标志位读写：this, 世界, 区域, 关卡, [sp] WorldType
void stage_flag(Context& c,uint32_t bit,int op){
    uint32_t slot=stage_slot(c,c.r[1],c.r[2],c.r[3]);
    uint32_t flags=slot?rd<uint32_t>(c,slot):0u;
    if(op==0){ret(c,(flags&bit)?1u:0u);return;}
    if(slot){wr<uint32_t>(c,slot,op>0?(flags|bit):(flags&~bit));bump(c);}
    c.pc=c.r[14];
}
void area_flag(Context& c,uint32_t bit,int op){
    uint32_t slot=area_slot(c,c.r[1],c.r[2]);
    uint32_t flags=slot?rd<uint32_t>(c,slot):0u;
    if(op==0){ret(c,(flags&bit)?1u:0u);return;}
    if(slot){wr<uint32_t>(c,slot,op>0?(flags|bit):(flags&~bit));bump(c);}
    c.pc=c.r[14];
}
// 区域通关奖励表第 r2 项的字段（原生 GetAreaResultType / ID / Num：世界, 区域, 序号, WorldType；BattleEndGetAreaResult
// 自序号 0 起逐项读取，类型为 −1 时结束）。
uint32_t area_result(Context& c,uint32_t field){
    uint32_t rec=rd<uint32_t>(c,H+64u)?area_rec(c,c.r[0],c.r[1]):0u;
    uint32_t list=rec?rd<uint32_t>(c,rec+0x48u):0u;
    return list?rd<uint32_t>(c,list+c.r[2]*12u+field):0xffffffffu;
}
uint32_t missing_blocks=0u;
}
#define URA_HOOK(NAME,...) static Block old_##NAME;static void NAME(Context& c){__VA_ARGS__ old_##NAME(c);}
// ---------- 区域与关卡数据 ----------
URA_HOOK(area_num,if(extra(c,c.r[0],c.r[1])){ret(c,rd<uint32_t>(c,rd<uint32_t>(c,H+16u)+(c.r[0]-rd<uint32_t>(c,H+8u))*0x44u));return;})
URA_HOOK(area_data,if(extra(c,c.r[0],c.r[2])){ret(c,area_rec(c,c.r[0],c.r[1]));return;})
URA_HOOK(stage_data,if(extra(c,c.r[0],c.r[3])){
    uint32_t rec=area_rec(c,c.r[0],c.r[1]);
    ret(c,rec&&c.r[2]<stage_count(c,rec)?rd<uint32_t>(c,rec+0x14u+c.r[2]*4u):0u);return;
})
URA_HOOK(stage_enable,if(extra(c,c.r[0],c.r[3])){
    uint32_t slot=stage_slot(c,c.r[0],c.r[1],c.r[2]);ret(c,slot&&(rd<uint32_t>(c,slot)&1u)?1u:0u);return;
})
URA_HOOK(area_result_type,if(extra(c,c.r[0],c.r[3])){ret(c,area_result(c,0u));return;})
URA_HOOK(area_result_id,if(extra(c,c.r[0],c.r[3])){ret(c,area_result(c,4u));return;})
URA_HOOK(area_result_num,if(extra(c,c.r[0],c.r[3])){ret(c,area_result(c,8u));return;})
URA_HOOK(stage_prisoner_rate,if(extra(c,c.r[0],c.r[3])){ret(c,0u);return;})
URA_HOOK(area_prisoner_rate,if(extra(c,c.r[0],c.r[2])){ret(c,0u);return;})
URA_HOOK(mission,if(active(c)){
    uint32_t base=rd<uint32_t>(c,H+20u),n=rd<uint32_t>(c,H+24u);
    for(uint32_t i=0;i<n;++i)if(rd<uint32_t>(c,base+i*120u)==c.r[1]){ret(c,base+i*120u);return;}
})
// 续关存档的关卡编号：扩展世界的关卡不写入（重启后不续接，同历史活动）。
URA_HOOK(continue_stage,if(active(c)&&c.r[1]){
    uint32_t base=rd<uint32_t>(c,H+20u),n=rd<uint32_t>(c,H+24u);
    for(uint32_t i=0;i<n;++i)if(rd<uint32_t>(c,base+i*120u)==c.r[1]){c.r[1]=0u;break;}
})
// ---------- 进度（存档函数：this, 世界, 区域, 关卡, [sp]…） ----------
#define URA_STAGE_FLAG(NAME,BIT,OP) URA_HOOK(NAME,if(extra(c,c.r[1],arg(c,0))){stage_flag(c,BIT,OP);return;})
URA_STAGE_FLAG(stage_enable_save,1u,0) URA_STAGE_FLAG(stage_enable_add,1u,1) URA_STAGE_FLAG(stage_enable_del,1u,-1)
URA_STAGE_FLAG(stage_clear_save,2u,0) URA_STAGE_FLAG(stage_clear_add,2u,1) URA_STAGE_FLAG(stage_clear_del,2u,-1)
URA_STAGE_FLAG(stage_new_save,4u,0) URA_STAGE_FLAG(stage_new_add,4u,1) URA_STAGE_FLAG(stage_new_del,4u,-1)
URA_HOOK(stage_time_get,if(extra(c,c.r[1],arg(c,0))){
    uint32_t slot=stage_slot(c,c.r[1],c.r[2],c.r[3]);ret(c,slot?rd<uint32_t>(c,slot+4u):0u);return;
})
URA_HOOK(stage_time_set,if(extra(c,c.r[1],arg(c,1))){
    uint32_t slot=stage_slot(c,c.r[1],c.r[2],c.r[3]);
    if(slot){wr<uint32_t>(c,slot+4u,arg(c,0));bump(c);}
    c.pc=c.r[14];return;
})
// 原生 UpdateStageClearTimeSaveData：用时为 0 不记录；已有记录且短于本次时不更新。
URA_HOOK(stage_time_update,if(extra(c,c.r[1],arg(c,1))){
    uint32_t slot=stage_slot(c,c.r[1],c.r[2],c.r[3]),t=arg(c,0);
    if(slot&&t){uint32_t old=rd<uint32_t>(c,slot+4u);if(!old||old>=t){wr<uint32_t>(c,slot+4u,t);bump(c);}}
    c.pc=c.r[14];return;
})
URA_HOOK(prisoner_get,if(extra(c,c.r[1],arg(c,0))){ret(c,0u);return;})
URA_HOOK(prisoner_add,if(extra(c,c.r[1],arg(c,1))){c.pc=c.r[14];return;})
URA_HOOK(prisoner_set,if(extra(c,c.r[1],arg(c,1))){c.pc=c.r[14];return;})
#define URA_AREA_FLAG(NAME,BIT,OP) URA_HOOK(NAME,if(extra(c,c.r[1],c.r[3])){area_flag(c,BIT,OP);return;})
URA_AREA_FLAG(area_new_save,1u,0) URA_AREA_FLAG(area_new_add,1u,1) URA_AREA_FLAG(area_new_del,1u,-1)
URA_AREA_FLAG(area_reward_save,2u,0) URA_AREA_FLAG(area_reward_add,2u,1) URA_AREA_FLAG(area_reward_del,2u,-1)
// ---------- 里地图扩展页 ----------
// SC_StageInitMainEx 建立里地图菜单任务（原生表 9 项）：换为宿主副本（加入扩展页的页面任务）。
URA_HOOK(menu_table,{
    old_menu_table(c);
    if(active(c)&&rd<uint32_t>(c,H+40u)){c.r[2]=rd<uint32_t>(c,H+40u);c.r[3]=rd<uint32_t>(c,H+44u);}
    return;
})
// 页面任务建立之后：页数上限 b210 = 2 + 扩展页数；扩展页面任务按原生 WorlMapInit 初始化并显示；箭头暂存复位。
URA_HOOK(menu_pages,{
    uint32_t app=c.r[4];
    old_menu_pages(c);
    if(!active(c))return;
    uint32_t n=rd<uint32_t>(c,H+4u),base=rd<uint32_t>(c,H+12u);
    wr<uint32_t>(c,app+0xb210u,2u+n);
    for(uint32_t k=0;k<n;++k){
        uint32_t t=rd<uint32_t>(c,app+0x3360u+(base+k)*4u);
        if(!t)continue;
        wr<uint32_t>(c,t+0x7cu,rd<uint32_t>(c,t+0x7cu)&~0x80u);
        wr<float>(c,t+0x1d4u,720.0f);wr<float>(c,t+0x1d8u,356.0f);
        wr<uint32_t>(c,t+0x1ecu,rd<uint32_t>(c,t+0x1d4u));wr<uint32_t>(c,t+0x1f0u,rd<uint32_t>(c,t+0x1d8u));
        wr<uint32_t>(c,t+0x1e0u,rd<uint32_t>(c,t+0xa8u));wr<uint32_t>(c,t+0x1e4u,rd<uint32_t>(c,t+0xacu));
        wr<uint32_t>(c,t+0xa8u,0u);wr<uint32_t>(c,t+0xacu,0u);
    }
    wr<uint32_t>(c,H+48u,0u);wr<uint32_t>(c,H+52u,0u);
    return;
})
URA_HOOK(stage_world_map,if(extra(c,c.r[2],0u)&&c.r[1]==PAGE_SLOT0+(c.r[2]-9u))c.r[1]=rd<uint32_t>(c,H+12u)+(c.r[2]-rd<uint32_t>(c,H+8u));)
URA_HOOK(area_world_map,if(active(c)&&ura_scene(c,c.r[0])&&c.r[1]>=PAGE_SLOT0+3u){
    uint32_t world=9u+(c.r[1]-PAGE_SLOT0);
    if(extra(c,world,0u))c.r[1]=rd<uint32_t>(c,H+12u)+(world-rd<uint32_t>(c,H+8u));
})
URA_HOOK(area_icon,if(extra(c,c.r[1],0u))c.r[3]=rd<uint32_t>(c,c.r[0]+0x3360u+(rd<uint32_t>(c,H+12u)+(c.r[1]-rd<uint32_t>(c,H+8u)))*4u);)
// 第 6 关起的图标：区域画面建立前暂存上一区域箭头（单区域的扩展世界不显示箭头）。
URA_HOOK(stage_init,{
    uint32_t app=c.r[0];
    uint32_t world=rd<uint32_t>(c,app+0xb200u)+rd<uint32_t>(c,app+0xb204u);
    if(extra(c,world,0u)&&!rd<uint32_t>(c,H+48u)&&stage_count(c,area_rec(c,world,rd<uint32_t>(c,app+0xb208u)))>5u){
        wr<uint32_t>(c,H+52u,rd<uint32_t>(c,app+ARROW_PREV));wr<uint32_t>(c,H+48u,1u);
    }
})
// GT_StageIconEx 每帧按页号取页面任务（app+0x33d4+4×页号，即槽 0x1d+页号）定位关卡图标：扩展页期间该槽在此块内暂时指向
// 扩展页面任务（槽 0x20 在区域画面中为区域名称任务，块结束后复原）。区域图标经 CreateAreaIconEx（area_icon）处理。
URA_HOOK(stage_icon_page,{
    uint32_t app=c.r[0],page=rd<uint32_t>(c,app+0xb200u),n=active(c)?rd<uint32_t>(c,H+4u):0u;
    if(page>=3u&&page<3u+n){
        uint32_t a=app+0x3360u+(PAGE_SLOT0+page)*4u,saved=rd<uint32_t>(c,a);
        wr<uint32_t>(c,a,rd<uint32_t>(c,app+0x3360u+(rd<uint32_t>(c,H+12u)+page-3u)*4u));
        old_stage_icon_page(c);
        wr<uint32_t>(c,a,saved);
        return;
    }
})
// 信息窗打开（InfoInitEx 末尾隐藏两个箭头）：箭头暂存期间对真实箭头执行，第 6 关图标保持。
URA_HOOK(info_arrows,{
    uint32_t app=c.r[6]-0x33c0u;
    if(active(c)&&rd<uint32_t>(c,H+48u)){
        uint32_t icon=rd<uint32_t>(c,app+ARROW_PREV);
        wr<uint32_t>(c,app+ARROW_PREV,rd<uint32_t>(c,H+52u));
        old_info_arrows(c);
        wr<uint32_t>(c,app+ARROW_PREV,icon);
        return;
    }
})
// 区域画面结束（StageEndEx 已移除全部关卡图标）：复原箭头任务，再按原生隐藏两个箭头。
URA_HOOK(stage_end_arrows,{
    uint32_t app=c.r[6]-0x33c0u;
    if(active(c)&&rd<uint32_t>(c,H+48u)){
        wr<uint32_t>(c,app+ARROW_PREV,rd<uint32_t>(c,H+52u));wr<uint32_t>(c,H+48u,0u);wr<uint32_t>(c,H+52u,0u);
    }
})
// ---------- 主菜单背景（2026-11-08） ----------
// GetMainMenuBGStageID（0x201988）把表世界 1–3 已通关的小关编号收集到栈上数组（r7，256 项，原生至多 195 项）、个数在 r8，
// 再于 0x201a0c 调用 ShuffleCGStack（r9 为 AppMain）并取第一项（与上次相同时取第二项）。此块之前追加 H+56 表中扩展世界的
// 已通关关卡（通关标志同 IsStageClearSaveData），数组满 256 项即停止。原生东南亚第 1 关未通关时直接返回 1011，不经此块。
URA_HOOK(menu_bg,if(active(c)){
    uint32_t list=rd<uint32_t>(c,H+56u),n=rd<uint32_t>(c,H+60u);
    for(uint32_t i=0;list&&i<n&&c.r[8]<256u;++i){
        uint32_t id=rd<uint32_t>(c,list+i*4u),w=id/1000u-1u,a=(id%1000u)/10u-1u,s=id%10u-1u;
        uint32_t slot=extra(c,w,0u)?stage_slot(c,w,a,s):0u;
        if(slot&&(rd<uint32_t>(c,slot)&2u)){wr<uint32_t>(c,c.r[7]+c.r[8]*4u,id);++c.r[8];}
    }
})
extern "C" __declspec(dllexport) uint32_t msd_ura_world_version(){return missing_blocks?0u:3u;}
extern "C" __declspec(dllexport) uint32_t msd_enable_ura_world_hooks(){
    static bool installed=false;if(installed)return missing_blocks;installed=true;
#define INSTALL(NAME,PC) old_##NAME=find_block(PC);if(!old_##NAME)++missing_blocks;else register_block(PC,NAME)
    INSTALL(area_num,0x10165efdu);INSTALL(area_data,0x10165f49u);INSTALL(stage_data,0x10165fb3u);
    INSTALL(stage_enable,0x10166411u);INSTALL(area_result_type,0x101660a9u);
    INSTALL(area_result_id,0x101660e5u);INSTALL(area_result_num,0x10166125u);
    INSTALL(stage_prisoner_rate,0x10166951u);INSTALL(area_prisoner_rate,0x101669fdu);
    INSTALL(mission,0x101d09fdu);INSTALL(continue_stage,0x10168a03u);
    INSTALL(stage_enable_save,0x10167f0du);INSTALL(stage_enable_add,0x10167f4du);INSTALL(stage_enable_del,0x10167f9fu);
    INSTALL(stage_clear_save,0x101680cdu);INSTALL(stage_clear_add,0x1016810bu);INSTALL(stage_clear_del,0x1016815du);
    INSTALL(stage_new_save,0x10167ff1u);INSTALL(stage_new_add,0x1016802du);INSTALL(stage_new_del,0x1016807du);
    INSTALL(stage_time_get,0x101681afu);INSTALL(stage_time_set,0x1016820fu);INSTALL(stage_time_update,0x10168277u);
    INSTALL(prisoner_get,0x1016830fu);INSTALL(prisoner_add,0x10168395u);INSTALL(prisoner_set,0x10168461u);
    INSTALL(area_new_save,0x10168659u);INSTALL(area_new_add,0x101686a3u);INSTALL(area_new_del,0x10168705u);
    INSTALL(area_reward_save,0x10168c25u);INSTALL(area_reward_add,0x10168c59u);INSTALL(area_reward_del,0x10168c9bu);
    INSTALL(menu_table,0x101fb41bu);INSTALL(menu_pages,0x101fb42du);
    INSTALL(stage_world_map,0x10215095u);INSTALL(area_world_map,0x10215061u);INSTALL(area_icon,0x101fb7e9u);
    INSTALL(stage_init,0x101fca35u);INSTALL(stage_icon_page,0x101fa225u);INSTALL(info_arrows,0x101fbdedu);INSTALL(stage_end_arrows,0x101fbb99u);
    INSTALL(menu_bg,0x10201a0du);
#undef INSTALL
    return missing_blocks;
}
