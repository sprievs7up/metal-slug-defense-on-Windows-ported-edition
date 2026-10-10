// beta 设置页复用原生按钮；两个音频选项分别写入既有存档字段。
#include "aot_runtime.h"
namespace {
constexpr uint32_t H=0x1ffea000u,MAGIC=0x41554431u;
bool enabled(Context& c){return rd<uint32_t>(c,H)==MAGIC;}
bool menu_options(Context& c,uint32_t app){
    return rd<uint32_t>(c,app+0x22bcu)==28u && rd<uint32_t>(c,app+0x22dcu)==2u;
}
static Block old_title_music,old_title_effects,old_title_flags,old_title_layout,old_title_extra;
// 标题 OPTION 扩展（模组 M4）：H+0x10 为 'TOPT' 时启用。+0x14 MOD 页请求计数（第 6 个面板 0x33a4 按下时递增，
// 取代原生“再次取得追加資料”确认窗）；+0x18 宿主建立的额外面板（退出游戏）；+0x1c 面板文字重建计数。
constexpr uint32_t TOPT=H+0x10u,TOPT_MAGIC=0x54504f54u;
bool title_extension(Context& c){return rd<uint32_t>(c,TOPT)==TOPT_MAGIC;}
static Block old_menu_music,old_menu_effects,old_menu_music_animation,old_menu_effects_animation;
static Block old_pause_music,old_pause_effects,old_pause_flags;
void toggle(Context& c,uint32_t app,uint32_t offset){
    wr<uint32_t>(c,app+offset,rd<uint32_t>(c,app+offset)?0u:1u);
    wr<uint32_t>(c,H+4,rd<uint32_t>(c,H+4)+1u);
}
void title_music(Context& c){
    if(!enabled(c)){old_title_music(c);return;}
    toggle(c,c.r[4],0x3d5cu);c.r[3]=c.r[4]+0x3d40u;c.r[6]=1u;nz(c,1u);
    c.r[0]=c.r[4];c.r[14]=0x1021894fu;c.pc=0x101c6da5u;
}
void title_effects(Context& c){
    if(!enabled(c)){old_title_effects(c);return;}
    toggle(c,c.r[4],0x3d60u);c.r[3]=c.r[4]+0x3d40u;
    c.r[0]=c.r[4];c.r[14]=0x10218997u;c.pc=0x101c6da5u;
}
void title_flags(Context& c){
    if(!enabled(c)){old_title_flags(c);return;}
    for(uint32_t offset:{0x3394u,0x3398u}){
        uint32_t task=rd<uint32_t>(c,c.r[0]+offset);
        wr<uint32_t>(c,task+0x7cu,rd<uint32_t>(c,task+0x7cu)&~0x80u);
    }
    c.pc=c.r[14];
}
void title_layout(Context& c){
    uint32_t app=c.r[4];bool active=enabled(c);old_title_layout(c);
    if(title_extension(c)){
        // SetTitlePanelString 清空并重建了文字纹理：额外面板的文字索引失效，先隐藏，由宿主重新写入文字后恢复。
        uint32_t extra=rd<uint32_t>(c,TOPT+8u);
        if(extra)wr<uint32_t>(c,extra+0x7cu,rd<uint32_t>(c,extra+0x7cu)|0xa0u);
        wr<uint32_t>(c,TOPT+12u,rd<uint32_t>(c,TOPT+12u)+1u);
    }
    if(!active)return;
    // 六行控件保留 66 像素原生点击高度，行间距为 68 像素。
    const uint32_t offsets[]={0x3390u,0x3394u,0x3398u,0x339cu,0x33a0u,0x33a8u};
    for(uint32_t i=0;i<6u;i++)wr<float>(c,rd<uint32_t>(c,app+offsets[i])+0x88u,176.0f+68.0f*i);
}
void title_extra(Context& c){
    // SelectTitleOptionWindow：第 6 个面板（0x33a4）选中后（原生已播放确定音 13），改为发出 MOD 页请求，
    // 转入原生 ClearSelectPanel 收尾（0x218a82，r4 app、r5 app+0x3380、r7 为 0）。
    if(!title_extension(c)){old_title_extra(c);return;}
    wr<uint32_t>(c,TOPT+4u,rd<uint32_t>(c,TOPT+4u)+1u);
    c.pc=0x10218a83u;
}
void menu_music(Context& c){
    if(!enabled(c)){old_menu_music(c);return;}
    // 音频回调仅在主菜单设置页接受操作，其他页面沿用未选择分支。
    if(!menu_options(c,c.r[4])){c.r[10]=0u;c.pc=0x10201ea7u;return;}
    toggle(c,c.r[4],0x3d5cu);c.r[3]=c.r[4]+0x3d40u;
    c.r[0]=c.r[4];c.r[14]=0x10201e6fu;c.pc=0x101c6da5u;
}
void menu_effects(Context& c){
    if(!enabled(c)){old_menu_effects(c);return;}
    if(!menu_options(c,c.r[4])){c.r[11]=0u;c.pc=0x10201effu;return;}
    toggle(c,c.r[4],0x3d60u);c.r[3]=c.r[4]+0x3d40u;c.r[6]=1u;nz(c,1u);
    c.r[0]=c.r[4];c.r[14]=0x10201ec5u;c.pc=0x101c6da5u;
}
void menu_music_animation(Context& c){
    if(!enabled(c)){old_menu_music_animation(c);return;}
    // 两项设置各自保留控件，切换时继续执行原生选择状态清除。
    c.pc=0x10201e8fu;
}
void menu_effects_animation(Context& c){
    if(!enabled(c)){old_menu_effects_animation(c);return;}
    c.pc=0x10201ee5u;
}
void pause_music(Context& c){
    if(!enabled(c)){old_pause_music(c);return;}
    toggle(c,c.r[4],0x3d5cu);c.r[3]=c.r[4]+0x3d40u;
    c.r[0]=c.r[4];c.r[14]=0x10210357u;c.pc=0x101c6da5u;
}
void pause_effects(Context& c){
    if(!enabled(c)){old_pause_effects(c);return;}
    toggle(c,c.r[4],0x3d60u);c.r[3]=c.r[4]+0x3d40u;c.r[6]=1u;nz(c,1u);
    c.r[0]=c.r[4];c.r[14]=0x102103a1u;c.pc=0x101c6da5u;
}
void pause_flags(Context& c){
    if(!enabled(c)){old_pause_flags(c);return;}
    for(uint32_t offset:{0x3368u,0x336cu}){
        uint32_t task=rd<uint32_t>(c,c.r[0]+offset);
        wr<uint32_t>(c,task+0x7cu,rd<uint32_t>(c,task+0x7cu)&~0x80u);
    }
    c.pc=c.r[14];
}
}
extern "C" __declspec(dllexport) uint32_t msd_beta_audio_options_version(){return 1u;}
extern "C" __declspec(dllexport) uint32_t msd_title_option_extension_version(){return 1u;}
extern "C" __declspec(dllexport) void msd_enable_beta_audio_options(){
    static bool installed=false;if(installed)return;installed=true;
#define INSTALL(NAME,PC) old_##NAME=find_block(PC);register_block(PC,NAME)
    INSTALL(title_music,0x1021893fu);INSTALL(title_effects,0x10218989u);
    INSTALL(title_flags,0x10217c5bu);
    INSTALL(title_layout,0x10217d0bu);INSTALL(title_extra,0x10218a57u);
    INSTALL(menu_music,0x10201e61u);INSTALL(menu_effects,0x10201eb5u);
    INSTALL(menu_music_animation,0x10201e7du);INSTALL(menu_effects_animation,0x10201ed3u);
    INSTALL(pause_music,0x10210349u);INSTALL(pause_effects,0x10210391u);INSTALL(pause_flags,0x10210127u);
#undef INSTALL
}
