// LAB 原生钩子（第 1 批）：敌方单位绝招等待条。
// 战斗钩子在宿主写入 LAB 共享头（0x1ffeb000，魔数 LAB1）且对应功能位开启时生效；
// 主菜单六项布局使用独立共享头 0x1ffef000。未启用相应共享头时回落至原生块。
//
// 原生结构（BattlePlayerOperator::drawUI，0x1d7ca8 起）：
//   0x1d8d26  BattleObjectManager::getInstance → 0x1d8d2a getTeamUnitList(r7=本方队伍, 0)
//   0x1d8d90… 逐单位循环：0x1d8da0 起按 getSpAttackCooldownRate 绘制绝招等待条（drawConv + fillRect），
//             0x1d8e48 起绘制小地图点；0x1d8ef6 取下一单位；循环结束跳至 0x1d8f0a。
//   0x1d8f0a  第二个循环：getTeamUnitList([sp+56]=敌方队伍, 0)，只绘制敌方小地图点。
// 做法：第一个循环结束到达 0x1d8f0a 时，以敌方队伍再执行一遍第一个循环（状态 1），
//       该遍在 0x1d8e48 直接跳到下一单位，只画等待条、不重复画小地图点；
//       第二次到达 0x1d8f0a 时状态复位，继续原生的敌方小地图循环。
//
// 第 2 批（T1）：点击敌方单位释放其绝招。BattlePlayerOperator::onGameScreenTouchEnded（0x1d74a8）：
//   0x1d7642  getTeamUnitList(r1=r5 本方队伍, r2=r6=0) → 逐单位：isSpAttack、成员 [u+116]==r9、
//             [u+980]==0、|触点世界 x−[u+140]|≤99、|触点 y−[u+144]|<常数，按 [u+240] 与横距择优，结果 r6。
//   0x1d76c8  遍历结束：r6==0 退出；0x1d76cc 成员复核；0x1d76d2 以 [r4+24]（本方控制器）vtable+0x98 发动。
// 做法：本方未命中时置状态 1，r5/r9 换成敌方队伍与成员，r7 恢复触点世界 x（遍历中保存在 s16），
//       模拟调用 BattleObjectManager::getInstance 并返回 0x1d7642 再遍历一遍；命中则在 0x1d76d2 改用
//       敌方控制器（宿主写入 +16）发动。头部字段：+16 敌方控制器，+20 敌方成员，+24 点击补遍状态。
//
// 第 3 批（T2）：底栏左右分栏（功能位 4）。drawUI 作为嵌套调用每帧执行多遍，各遍以裁剪框与仿射变换
// 把底栏片段排成 [我方 AP][我方弹头车]▌我方 3 格▐敌方 3 格▐[敌方弹头车][敌方 AP]；敌方各遍换入敌方
// 控制器、出兵栏状态（头部 +0x70）与出兵格图集（头部 +0x40，宿主以敌方控制器调用 createGrahics 生成）。
// 触点在 onUITouchBegan/Moved/Ended 入口按片段换回原生坐标，敌方片段在处理期间换入敌方状态。
#include "aot_runtime.h"
#include "native_imports.h"
#include <utility>
namespace {
constexpr uint32_t H=0x1ffeb000u,MAGIC=0x4c414231u;   // "LAB1"
constexpr uint32_t FLAGS=H+4u,ENEMY_TEAM=H+8u,GAUGE_PASS=H+12u;
constexpr uint32_t ENEMY_CONTROLLER=H+16u,ENEMY_MEMBER=H+20u,TOUCH_PASS=H+24u;
constexpr uint32_t FLAG_ENEMY_GAUGE=1u,FLAG_ENEMY_TOUCH=2u;
constexpr uint32_t OBJECT_MANAGER_GET_INSTANCE=0x101de618u;
bool enabled(Context& c,uint32_t flag){
    return rd<uint32_t>(c,H)==MAGIC && (rd<uint32_t>(c,FLAGS)&flag);
}
Block old_gauge_loop_exit,old_gauge_minimap;
void gauge_loop_exit(Context& c){
    if(enabled(c,FLAG_ENEMY_GAUGE)){
        if(rd<uint32_t>(c,GAUGE_PASS)==0u){
            wr<uint32_t>(c,GAUGE_PASS,1u);
            c.r[7]=rd<uint32_t>(c,c.r[13]+56u);   // 原生第二循环所用的敌方队伍
            c.pc=0x101d8d27u;                      // 重新进入：getInstance → getTeamUnitList(r7,0)
            return;
        }
        wr<uint32_t>(c,GAUGE_PASS,0u);
    }else if(rd<uint32_t>(c,GAUGE_PASS)){
        wr<uint32_t>(c,GAUGE_PASS,0u);
    }
    old_gauge_loop_exit(c);
}
void gauge_minimap(Context& c){
    if(rd<uint32_t>(c,H)==MAGIC && rd<uint32_t>(c,GAUGE_PASS)==1u){
        c.pc=0x101d8ef7u;                          // 敌方补画遍：跳过小地图点，取下一单位
        return;
    }
    old_gauge_minimap(c);
}
Block old_touch_entry,old_touch_list,old_touch_loop_exit,old_touch_activate;
void touch_entry(Context& c){
    if(rd<uint32_t>(c,TOUCH_PASS))wr<uint32_t>(c,TOUCH_PASS,0u);
    old_touch_entry(c);
}
bool start_enemy_touch_pass(Context& c,uint32_t world_x){
    if(!rd<uint32_t>(c,ENEMY_CONTROLLER))return false;
    wr<uint32_t>(c,TOUCH_PASS,1u);
    c.r[5]=rd<uint32_t>(c,ENEMY_TEAM);
    c.r[6]=0u;
    c.r[9]=rd<uint32_t>(c,ENEMY_MEMBER);
    c.r[7]=world_x;                                // 0x1d764a 由 r7 重新得到 s16
    c.r[14]=0x101d7643u;                           // getInstance 返回后进入 getTeamUnitList(r5,r6=0)
    c.pc=OBJECT_MANAGER_GET_INSTANCE|1u;
    return true;
}
void touch_list(Context& c){
    // 0x1d764a：列表为空时原生直接退出，不经过 0x1d76c8。
    if(c.r[0]==0u && enabled(c,FLAG_ENEMY_TOUCH)){
        uint32_t pass=rd<uint32_t>(c,TOUCH_PASS);
        if(pass==0u && start_enemy_touch_pass(c,c.r[7]))return;
        if(pass)wr<uint32_t>(c,TOUCH_PASS,0u);
    }
    old_touch_list(c);
}
void touch_loop_exit(Context& c){
    if(enabled(c,FLAG_ENEMY_TOUCH)){
        uint32_t pass=rd<uint32_t>(c,TOUCH_PASS);
        if(pass==0u && c.r[6]==0u && start_enemy_touch_pass(c,uint32_t(int32_t(fs(c,16)))))return;
        if(pass==1u)wr<uint32_t>(c,TOUCH_PASS,c.r[6]?2u:0u);
    }else if(rd<uint32_t>(c,TOUCH_PASS)){
        wr<uint32_t>(c,TOUCH_PASS,0u);
    }
    old_touch_loop_exit(c);
}
void touch_activate(Context& c){
    if(rd<uint32_t>(c,TOUCH_PASS)==2u){
        wr<uint32_t>(c,TOUCH_PASS,0u);
        if(enabled(c,FLAG_ENEMY_TOUCH)){
            uint32_t controller=rd<uint32_t>(c,ENEMY_CONTROLLER);
            c.r[0]=controller;
            c.r[1]=rd<uint16_t>(c,c.r[6]+98u);
            c.r[3]=rd<uint32_t>(c,rd<uint32_t>(c,controller)+152u);   // actionUnitSpAttack
            c.r[14]=0x101d76e1u;
            c.pc=c.r[3];
            return;
        }
    }
    old_touch_activate(c);
}
// ---------- 嵌套调用：在钩子内同步执行一段客体函数（与 msd_run 相同的分派，返回哨兵 0x1fff0000） ----------
constexpr uint32_t RETURN_SENTINEL=0x1fff0000u;
bool guest_call(Context& c,uint32_t fn,uint32_t a0,uint32_t a1=0,uint32_t a2=0,uint32_t a3=0,
                const uint32_t* stack=nullptr,uint32_t stack_words=0,uint32_t* result=nullptr){
    uint32_t saved_r[16];std::memcpy(saved_r,c.r,sizeof saved_r);
    uint64_t saved_d[32];std::memcpy(saved_d,c.d,sizeof saved_d);
    uint32_t n=c.n,z=c.z,cf=c.c,v=c.v,fpscr=c.fpscr,pc=c.pc;
    uint32_t sp=(c.r[13]-96u)&~7u;
    for(uint32_t i=0;i<stack_words;++i)wr<uint32_t>(c,sp+i*4u,stack[i]);
    c.r[13]=sp;c.r[0]=a0;c.r[1]=a1;c.r[2]=a2;c.r[3]=a3;c.r[14]=RETURN_SENTINEL;c.pc=fn|1u;
    NativeImports* host=msd_imports(&c);
    bool ok=false;
    for(uint32_t i=0;i<50000000u;++i){
        uint32_t a=c.pc&~1u;
        if(a==RETURN_SENTINEL){ok=true;break;}
        if(a>=0x1f000000u&&a<0x1f010000u){
            if(!msd_native_import(c,a,host))break;        // 需要宿主处理的导入：嵌套调用无法让出，放弃
            c.blocks++;if(c.error)break;continue;
        }
        if(uint32_t thunk=msd_decoder_thunk(host,c.pc)){c.pc=thunk;continue;}
        Block f=find_block(c.pc);
        if(!f){missing(c,c.pc);break;}
        f(c);c.blocks++;
        if(c.error)break;
    }
    if(result)*result=c.r[0];
    std::memcpy(c.r,saved_r,sizeof saved_r);std::memcpy(c.d,saved_d,sizeof saved_d);
    c.n=n;c.z=z;c.c=cf;c.v=v;c.fpscr=fpscr;c.pc=pc;
    return ok;
}
uint32_t fbits(float f){uint32_t x;std::memcpy(&x,&f,4);return x;}
float bitsf(uint32_t x){float f;std::memcpy(&f,&x,4);return f;}

// ---------- 主菜单 LAB 入口：共享头提供位置，原生底栏保留其按钮任务与输入流程 ----------
// 宿主在每帧 step 前清除 +4；原生按钮绘制时发布同帧父任务位移及透明度。
// +8/+12 为 LAB 左上角原生坐标，+16/+20 为缩放，+24/+28 为相邻按钮任务，
// +32 为透明度（0..255），+36 为输入就绪标记；入场、退场及稳定态共用六槽分配。
// 主菜单 scene 28 的稳定子状态：1 MENU、2 OPTION、3 CUSTOMIZE、4 SHOP。
// state 0 为入场等待，5/6 为离场闸门；上述过渡状态保持输入关闭。
constexpr uint32_t MENU_H=0x1ffef000u,MENU_MAGIC=0x4c41424du;   // "LABM"
constexpr uint32_t MENU_LAYOUT=0x101ff3fdu,MENU_BUTTON=0x101ff4e9u;
constexpr uint32_t MENU_SLOTS[]={0x36d8u,0x36dcu,0x36e0u,0x36e4u,0x3718u};
constexpr uint32_t MENU_IMAGES[]={30u,32u,33u,34u,119u};
constexpr uint32_t MENU_INDICES[]={0u,1u,2u,3u,5u};
Block old_menu_layout,old_menu_button_draw,old_menu_button_tail;
bool menu_pointer(uint32_t p,uint32_t size){
    return p>=0x10000000u && uint64_t(p)+size<=0x20000000ull;
}
// 主菜单离场后，底栏任务地址可被其他场景重新分配。绘制时同时核验当前场景、
// 当前 MEDAL 槽位及任务身份，避免旧地址在 EVENT 基地或选关页继续承载 LAB 图像。
bool current_menu_medal(Context& c,uint32_t t){
    uint32_t app=rd<uint32_t>(c,MENU_H+44u);
    if(!menu_pointer(app,0xc21eu) || !menu_pointer(t,0x1bcu))return false;
    uint32_t scene=rd<uint32_t>(c,app+0x22bcu);
    return (scene==27u || scene==28u) && rd<uint32_t>(c,app+MENU_SLOTS[3])==t &&
           rd<uint32_t>(c,t)==MENU_BUTTON && rd<uint32_t>(c,t+0x50u)==MENU_IMAGES[3] &&
           rd<float>(c,t+0xfcu)==140.0f;
}
// 宿主受理的原生底栏按钮（GT_CockpitButton）：原生 PushPanel 每帧依触点重算 +0x174/+0x194，
// 宿主拦截触点时反馈只能维持一帧。头部 +0x40 为 'HOLD' 时，+0x44 起四个任务指针跳过 PushPanel，
// 保持按压（+0x174=1）且不产生原生选择（+0x194=0），由宿主在取消或场景切换后清除。
constexpr uint32_t HOLD_H=MENU_H+0x40u,HOLD_MAGIC=0x444c4f48u;
Block old_cockpit_push;
void cockpit_push(Context& c){
    uint32_t t=c.r[4];
    if(rd<uint32_t>(c,HOLD_H)==HOLD_MAGIC && menu_pointer(t,0x198u)){
        for(uint32_t i=0;i<4;++i)if(rd<uint32_t>(c,HOLD_H+4u+i*4u)==t){
            wr<uint32_t>(c,t+0x174u,1u);wr<uint32_t>(c,t+0x194u,0u);c.pc=0x101ff525u;return;
        }
    }
    old_cockpit_push(c);
}
void menu_layout(Context& c){
    uint32_t app=c.r[0];
    old_menu_layout(c);                                    // 保留原块的分配、寄存器与后续控制流
    if(rd<uint32_t>(c,MENU_H)!=MENU_MAGIC)return;
    wr<uint32_t>(c,MENU_H+4u,0u);
    if(!menu_pointer(app,0xc21eu))return;
    uint32_t scene=rd<uint32_t>(c,app+0x22bcu);
    if(scene!=27u && scene!=28u)return;
    uint32_t panels[5];
    for(uint32_t i=0;i<5u;++i){
        uint32_t t=rd<uint32_t>(c,app+MENU_SLOTS[i]);
        if(!menu_pointer(t,0x1bcu) || rd<uint32_t>(c,t)!=MENU_BUTTON ||
           rd<uint32_t>(c,t+0x50u)!=MENU_IMAGES[i] || rd<float>(c,t+0xfcu)!=140.0f)return;
        panels[i]=t;
    }
    float margin=float(int32_t(rd<uint32_t>(c,app+0x3cu)));
    float left=40.0f-margin;
    float step=(float(rd<uint32_t>(c,app+0x34u))+2.0f*margin-200.0f)/5.0f;
    float x=left+step*4.0f+rd<float>(c,panels[3]+0x9cu);
    float y=rd<float>(c,panels[3]+0x88u)+rd<float>(c,panels[3]+0xa0u);
    float sx=rd<float>(c,panels[3]+0xa8u),sy=rd<float>(c,panels[3]+0xacu);
    if(!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(step) || step<=0.0f ||
       !std::isfinite(sx) || !std::isfinite(sy) || sx<=0.0f || sy<=0.0f)return;
    for(uint32_t i=0;i<5u;++i)wr<float>(c,panels[i]+0x84u,left+step*float(MENU_INDICES[i]));
    wr<float>(c,MENU_H+8u,x);wr<float>(c,MENU_H+12u,y);
    wr<float>(c,MENU_H+16u,sx);wr<float>(c,MENU_H+20u,sy);
    wr<uint32_t>(c,MENU_H+24u,panels[3]);wr<uint32_t>(c,MENU_H+28u,panels[4]);
    wr<float>(c,MENU_H+40u,left+step*4.0f);wr<uint32_t>(c,MENU_H+44u,app);
}
void menu_button_draw(Context& c){
    uint32_t t=c.r[0];
    if(rd<uint32_t>(c,MENU_H)==MENU_MAGIC && t==rd<uint32_t>(c,MENU_H+24u) &&
       current_menu_medal(c,t) && !(rd<uint32_t>(c,t+0x80u)&2u) &&
       !(rd<uint32_t>(c,t+0x7cu)&0x80u)){
        uint32_t parent=rd<uint32_t>(c,t+0x1b8u);
        if(menu_pointer(parent,0xd8u)){
            // GT_CockpitButton 在更新时把父任务位移及 alpha 写入此任务。
            // 绘制钩子读取该最终状态，使 LAB 与 MEDAL 的显示在同一帧一致。
            float x=rd<float>(c,MENU_H+40u)+rd<float>(c,t+0x9cu);
            float y=rd<float>(c,t+0x88u)+rd<float>(c,t+0xa0u);
            wr<float>(c,MENU_H+8u,x);wr<float>(c,MENU_H+12u,y);
            wr<uint32_t>(c,MENU_H+32u,rd<uint32_t>(c,t+0xd4u));
            uint32_t app=rd<uint32_t>(c,MENU_H+44u);
            uint32_t state=menu_pointer(app,0xc21eu)?rd<uint32_t>(c,app+0x22dcu):0u;
            bool ready=menu_pointer(app,0xc21eu) && rd<uint32_t>(c,app+0x22bcu)==28u &&
                       state>=1u && state<=4u && rd<uint8_t>(c,app+0xb178u) &&
                       !rd<uint8_t>(c,app+0xc21du) && !(rd<uint32_t>(c,t+0x80u)&3u) &&
                       !(rd<uint32_t>(c,t+0x7cu)&0xa0u);
            wr<uint32_t>(c,MENU_H+36u,ready?1u:0u);
            wr<uint32_t>(c,MENU_H+4u,1u);
        }
    }
    old_menu_button_draw(c);
}
void menu_button_tail(Context& c){
    uint32_t t=c.r[4],image=rd<uint32_t>(c,MENU_H+48u),app=rd<uint32_t>(c,MENU_H+44u);
    if(rd<uint32_t>(c,MENU_H)==MENU_MAGIC && rd<uint32_t>(c,MENU_H+4u) &&
       rd<uint32_t>(c,MENU_H+56u) && t==rd<uint32_t>(c,MENU_H+24u) &&
       current_menu_medal(c,t) && menu_pointer(image,56u) && menu_pointer(app,0x80u)){
        uint32_t graphics=rd<uint32_t>(c,app+0x7cu);
        // +52：1 为按住且指针在图标内（需输入许可），2 为确认后保持至 LAB 闸门合拢。
        uint32_t press=rd<uint32_t>(c,MENU_H+52u);
        bool pressed=press==2u || (press && rd<uint32_t>(c,MENU_H+36u));
        uint32_t x=rd<uint32_t>(c,MENU_H+8u),y=rd<uint32_t>(c,MENU_H+12u);
        guest_call(c,0x10137711u,graphics,rd<uint32_t>(c,t+0xd0u),rd<uint32_t>(c,t+0xd4u));
        uint32_t item=79u;
        if(pressed)guest_call(c,0x10200161u,app,t,x,y,&item,1u);
        // 独立矩形在原生队列中与 MEDAL 同层。后续闸门绘制按原任务顺序覆盖底栏。
        uint32_t rect=MENU_H+0x100u;
        wr<int16_t>(c,rect+0u,0);wr<int16_t>(c,rect+2u,0);
        wr<int16_t>(c,rect+4u,60);wr<int16_t>(c,rect+6u,48);
        for(uint32_t o=8u;o<16u;o+=2u)wr<int16_t>(c,rect+o,0);
        uint32_t stack[]={rect,rd<uint32_t>(c,t+0xa8u),rd<uint32_t>(c,t+0xacu),0u,0u};
        guest_call(c,0x10136985u,graphics,image,x,y,stack,5u);
        item=37u;
        if(pressed)guest_call(c,0x10200161u,app,t,x,y,&item,1u);
    }
    old_menu_button_tail(c);
}

// ---------- 底栏分栏（T2，功能位 4） ----------
// drawUI 的全部底栏绘制最终经由 Graphics::drawImageS(Image*, float m[6]{a,b,tx,c,d,ty}, u,v,w,h,…)、
// Graphics::fillRect 与 Graphics::setClip/clearClip，坐标为原生参考坐标 D（逻辑 1280×720 下 L=(D+88.9)×1.125）。
// LAB 中每帧把 drawUI 作为嵌套调用执行多遍：第 0 遍只画底栏以外（裁剪 y<498）；其余各遍各负责一个底栏片段，
// 以裁剪框限定片段、以仿射变换（统一缩放 s、以底栏上沿为基准）移到新位置；敌方各遍临时换入敌方控制器与敌方滚动状态。
constexpr uint32_t FLAG_SPLIT_BAR=4u;
constexpr uint32_t G_DRAW_S=0x10143cddu,G_DRAW=0x10141b11u,G_FILL=0x1014311du,G_SETCLIP=0x101423ddu,G_CLEARCLIP=0x10142615u;
constexpr uint32_t DRAWUI=0x101d7ca8u,G_DRAWSTACK=0x10143a48u;
constexpr float BAR_TOP=498.0f,BAR_BOTTOM=640.0f,SCREEN_LEFT=-88.89f,SCREEN_RIGHT=1048.89f;
float SCALE=0.88f;                                             // layout() 按片段总宽占满屏幕计算（约 0.863）
// filter：0 全部，1 只画底栏背景。mirror：片段内容绕片段中心水平翻转。
// 两端的边缘块取自底栏背景最左端（源 x −88.89…−70，含 AP 框下方与底栏相接的圆角），右端为其镜像。
struct Segment{float src0,src1;bool enemy;int filter;bool mirror;};
constexpr Segment SEGMENTS[]={
    {-88.89f,-70,false,1,false},
    {18,140,false,0,false},{812,948,false,0,false},{155,177,false,1,false},{184,532,false,0,false},     // 我方：AP 升级、弹头车、左警示条、3 格
    {155,177,true,1,false},{184,532,true,0,false},{776,800,true,1,false},{812,948,true,0,true},{18,140,true,0,false},  // 敌方：中间分隔、3 格、右警示条、弹头车（翻转）、AP 升级
    {-88.89f,-70,true,1,true}};
constexpr int SEGMENT_COUNT=int(sizeof SEGMENTS/sizeof SEGMENTS[0]);
constexpr float ARROW_SHIFT=-246.0f;                           // 滚动箭头（源 x 742）移到 3 格窗口右端
struct Pass{bool active=false;float s=1,offx=0,offy=0;int clip[4]={0,0,0,0};int filter=0;bool cells=false;bool tinted=false;bool rotate=false;bool ap_button=false;bool apbar=false;bool no_apbar=false;bool mirror=false;bool mirror_sprite=false;bool coin_overlay=false;bool banner_overlay=false;float mirror_center=0;uint32_t atlas=0;};
Pass pass;
bool enemy_pass=false,drawing_banner=false;
float seg_dest[SEGMENT_COUNT];
bool laid_out_once=false;
void layout(){
    float total=0;for(const Segment& g:SEGMENTS)total+=g.src1-g.src0;
    SCALE=(SCREEN_RIGHT-SCREEN_LEFT)/total;
    float x=SCREEN_LEFT;
    for(int i=0;i<SEGMENT_COUNT;++i){seg_dest[i]=x;x+=SCALE*(SEGMENTS[i].src1-SEGMENTS[i].src0);}
}
bool split_enabled(Context& c){return enabled(c,FLAG_SPLIT_BAR) && rd<uint32_t>(c,ENEMY_CONTROLLER);}
uint32_t graphics_ptr=0;
uint32_t& scratch_matrix_slot(){static uint32_t slot=H+0x800u;return slot;}

bool pass_filter(Context& c,uint32_t u_bits){
    if(pass.filter==1)return u_bits==0u && rd<uint32_t>(c,c.r[13])==fbits(32.0f);   // 底栏背景图块 (0,32,568,71)
    return true;
}
bool is_arrow(Context& c){
    float u=bitsf(c.r[3]),v=bitsf(rd<uint32_t>(c,c.r[13]));
    return v==234.0f && (u==686.0f||u==706.0f);
}
// 裁剪改为软件实现：glScissor/glEnable 由 Python 宿主处理，嵌套调用中无法执行。
// 各遍中原生 setClip/clearClip 只更新 cur_clip（D 坐标），绘制钩子按 cur_clip 裁切每个图块的源矩形与位移。
int cur_clip[4]={0,0,0,0};
bool clip_range(float o,float k,float lo,float hi,float len,float& t0,float& t1){
    if(k==0.0f){t0=0;t1=len;return o>=lo && o<hi;}
    float p=(lo-o)/k,q=(hi-o)/k;if(p>q)std::swap(p,q);
    t0=std::max(0.0f,p);t1=std::min(len,q);return t1>t0;
}
// drawImageS(Image*, float m[6], u, v, w, h, …)：目标 x = tx + a·t（t∈[0,w]），y = ty + d·t（t∈[0,h]）。
bool clip_quad(Context& c,uint32_t m){
    float a=bitsf(rd<uint32_t>(c,m)),b=bitsf(rd<uint32_t>(c,m+4u)),tx=bitsf(rd<uint32_t>(c,m+8u));
    float cc=bitsf(rd<uint32_t>(c,m+12u)),d=bitsf(rd<uint32_t>(c,m+16u)),ty=bitsf(rd<uint32_t>(c,m+20u));
    uint32_t sp=c.r[13];
    float u=bitsf(c.r[3]),v=bitsf(rd<uint32_t>(c,sp)),w=bitsf(rd<uint32_t>(c,sp+4u)),h=bitsf(rd<uint32_t>(c,sp+8u));
    float L=float(cur_clip[0]),T=float(cur_clip[1]),R=L+float(cur_clip[2]),B=T+float(cur_clip[3]);
    if(b!=0.0f || cc!=0.0f){                                    // 旋转图块：只按外接框整体取舍
        float xs[4]={tx,tx+a*w,tx+b*h,tx+a*w+b*h},ys[4]={ty,ty+cc*w,ty+d*h,ty+cc*w+d*h};
        float x0=*std::min_element(xs,xs+4),x1=*std::max_element(xs,xs+4);
        float y0=*std::min_element(ys,ys+4),y1=*std::max_element(ys,ys+4);
        return x1>L && x0<R && y1>T && y0<B;
    }
    float x0,x1,y0,y1;
    if(!clip_range(tx,a,L,R,w,x0,x1) || !clip_range(ty,d,T,B,h,y0,y1))return false;
    if(x0>0.0f || x1<w){c.r[3]=fbits(u+x0);wr<uint32_t>(c,sp+4u,fbits(x1-x0));wr<uint32_t>(c,m+8u,fbits(tx+a*x0));}
    if(y0>0.0f || y1<h){wr<uint32_t>(c,sp,fbits(v+y0));wr<uint32_t>(c,sp+8u,fbits(y1-y0));wr<uint32_t>(c,m+20u,fbits(ty+d*y0));}
    return true;
}
// T5 AP 数值框：drawApBar 从第 0 遍中排除，我方、敌方各单独执行一遍，裁剪到框体真实下沿（D 520），
// 由随后绘制的底栏照原版压住下沿。敌方以敌方控制器执行，框体水平翻转到右下，不加底色（用户 2026-10-06 确认）。
// 框体图块含文字带（源 x 22…100：“AP:”、暗色占位数字与 “/”）：翻转后以无字底纹（源 x 100…122）平铺盖住
// 镜像的文字带，再把文字带不翻转地画到平移后的位置；当前值数字与 “/上限” 由原生平移绘制。
constexpr float AP_BOX_LEFT=-88.0f,AP_BOX_RIGHT=174.0f,AP_BOX_TOP=442.0f,AP_BOX_BOTTOM=520.0f;
constexpr float AP_TEXT0=22.0f,AP_TEXT1=100.0f,AP_PLAIN=100.0f,AP_PLAIN_W=22.0f;
constexpr uint32_t DRAW_AP_BAR=0x101d7ac4u;
constexpr uint32_t G_SETCOLOR=0x101417deu,G_GETCOLOR=0x1014398au;
// AP 升级按钮内的成本数字缩放后偏左约 2 像素（实测）；向右补正使其在数字框内居中（“MAX” 字样原本居中，不补正）。
constexpr float AP_DIGIT_SHIFT=2.0f;
// 缩放后底栏背景的上沿边框（目标 D 498…513，实测）；警示条条纹与骨架区为 513…底栏下沿。
constexpr float BAR_BORDER_SRC=17.0f;
void draw_quad(Context& c,uint32_t matrix,float a,float d,float tx,float ty,float u,float w,const uint32_t* tail){
    wr<uint32_t>(c,matrix,fbits(a));wr<uint32_t>(c,matrix+4u,0u);wr<uint32_t>(c,matrix+8u,fbits(tx));
    wr<uint32_t>(c,matrix+12u,0u);wr<uint32_t>(c,matrix+16u,fbits(d));wr<uint32_t>(c,matrix+20u,fbits(ty));
    uint32_t stack[6]={tail[0],fbits(w),tail[2],tail[3],tail[4],tail[5]};
    guest_call(c,G_DRAW_S-1u,c.r[0],c.r[1],matrix,fbits(u),stack,6);
}
void draw_enemy_ap_frame(Context& c,float a,float d,float tx,float ty){
    uint32_t tail[6];
    for(uint32_t i=0;i<6u;++i)tail[i]=rd<uint32_t>(c,c.r[13]+i*4u);   // v, w, h 及其余参数
    float w=bitsf(tail[1]),mirror_tx=SCREEN_LEFT+SCREEN_RIGHT-tx;
    pass.active=false;
    uint32_t m=H+0x820u;
    draw_quad(c,m,-a,d,mirror_tx,ty,0.0f,w,tail);                                      // 翻转的框体
    for(float x=mirror_tx-a*AP_TEXT1;x<mirror_tx-a*AP_TEXT0;x+=a*AP_PLAIN_W){        // 盖住镜像的文字带
        float tile=std::min(AP_PLAIN_W,(mirror_tx-a*AP_TEXT0-x)/a);
        draw_quad(c,m,a,d,x,ty,AP_PLAIN,tile,tail);
    }
    draw_quad(c,m,a,d,tx+pass.offx+a*AP_TEXT0,ty,AP_TEXT0,AP_TEXT1-AP_TEXT0,tail);     // 不翻转的文字带
    pass.active=true;
}
// 诊断：头部 +0xb10 为 'SLOG' 时，把翻转片段（敌方弹头车）中的 drawImageS 调用记入宿主缓冲区（+0xb18 地址、+0xb1c 容量），
// 计数在 +0xb14；每条 32 字节：Image*、u、v、w、h、tx、ty、是否翻转 | 片段裁剪 x<<8 | 宽<<24（同一 Image/u/v/片段只记一次）。不改变绘制。
constexpr uint32_t SEG_LOG=H+0xb10u,SEG_LOG_MAGIC=0x474f4c53u;
// 敌方弹头车按钮框：底栏图集中 73×71、源 v 103 的按钮框图块（u 343/417 等各状态），底部含 “MAX” 字样。
// 整块翻转会显示为 “XAM”（第 34 版诊断 SLOG 实测：绘制 tx 808、ty 496）。
bool is_slug_max_text(Context& c){
    uint32_t sp=c.r[13];
    return c.r[1]==pass.atlas && rd<uint32_t>(c,sp)==fbits(103.0f) &&
           rd<uint32_t>(c,sp+4u)==fbits(73.0f) && rd<uint32_t>(c,sp+8u)==fbits(71.0f);
}
template<uint32_t ENTRY> struct DrawHook{static Block old;static void run(Context& c);};
template<uint32_t ENTRY> Block DrawHook<ENTRY>::old;
template<uint32_t ENTRY> void DrawHook<ENTRY>::run(Context& c){
    graphics_ptr=c.r[0];
    if(pass.active){
        if(pass.banner_overlay && !drawing_banner){c.pc=c.r[14];return;}
        if(!pass_filter(c,c.r[3])){c.pc=c.r[14];return;}
        float extra=(pass.cells && is_arrow(c))?ARROW_SHIFT*pass.s:0.0f;
        uint32_t m=c.r[2],dst=H+0x800u;
        float a=bitsf(rd<uint32_t>(c,m)),b=bitsf(rd<uint32_t>(c,m+4u)),tx=bitsf(rd<uint32_t>(c,m+8u));
        float cc=bitsf(rd<uint32_t>(c,m+12u)),d=bitsf(rd<uint32_t>(c,m+16u)),ty=bitsf(rd<uint32_t>(c,m+20u));
        float s=pass.s;
        wr<uint32_t>(c,dst,fbits(a*s));wr<uint32_t>(c,dst+4u,fbits(b*s));wr<uint32_t>(c,dst+8u,fbits(tx*s+pass.offx+extra));
        wr<uint32_t>(c,dst+12u,fbits(cc*s));wr<uint32_t>(c,dst+16u,fbits(d*s));wr<uint32_t>(c,dst+20u,fbits(ty*s+pass.offy));
        if(pass.apbar && c.r[3]==0u && rd<uint32_t>(c,c.r[13])==fbits(174.0f)){
            draw_enemy_ap_frame(c,a,d,tx,ty);c.pc=c.r[14];return;
        }
        if(pass.ap_button && ty>=590.0f && ty<625.0f && c.r[3]!=fbits(210.0f))
            wr<uint32_t>(c,dst+8u,fbits(bitsf(rd<uint32_t>(c,dst+8u))+AP_DIGIT_SHIFT));
        // 敌方弹头车片段整体翻转（底部 “MAX” 字样除外）；敌方 AP 升级片段只翻转人物精灵（图集以外的图像）。
        bool flip=(pass.coin_overlay || pass.banner_overlay)?pass.mirror:
                  (pass.mirror && !(ty>=590.0f && c.r[3]!=0u)) || (pass.mirror_sprite && c.r[1]!=pass.atlas);
        if(pass.mirror && !pass.coin_overlay && !pass.banner_overlay && rd<uint32_t>(c,SEG_LOG)==SEG_LOG_MAGIC){
            uint32_t n=rd<uint32_t>(c,SEG_LOG+4u),buf=rd<uint32_t>(c,SEG_LOG+8u),cap=rd<uint32_t>(c,SEG_LOG+12u);
            uint32_t row[8]={c.r[1],c.r[3],rd<uint32_t>(c,c.r[13]),rd<uint32_t>(c,c.r[13]+4u),rd<uint32_t>(c,c.r[13]+8u),fbits(tx),fbits(ty),(flip?1u:0u)|(uint32_t(pass.clip[0]&0xffff)<<8)|(uint32_t(pass.clip[2]&0xff)<<24)};
            bool seen=false;
            for(uint32_t i=0;i<n && !seen;++i)seen=rd<uint32_t>(c,buf+i*32u)==row[0] && rd<uint32_t>(c,buf+i*32u+4u)==row[1] && rd<uint32_t>(c,buf+i*32u+8u)==row[2] && rd<uint32_t>(c,buf+i*32u+28u)==row[7];
            if(buf && n<cap && !seen){for(uint32_t k=0;k<8u;++k)wr<uint32_t>(c,buf+n*32u+k*4u,row[k]);wr<uint32_t>(c,SEG_LOG+4u,n+1u);}
        }
        if(flip){
            float cx=(pass.coin_overlay || pass.banner_overlay)?pass.mirror_center:float(pass.clip[0])+float(pass.clip[2])*0.5f;
            wr<uint32_t>(c,dst,fbits(-bitsf(rd<uint32_t>(c,dst))));
            wr<uint32_t>(c,dst+4u,fbits(-bitsf(rd<uint32_t>(c,dst+4u))));
            wr<uint32_t>(c,dst+8u,fbits(2.0f*cx-bitsf(rd<uint32_t>(c,dst+8u))));
            if(pass.mirror && !pass.coin_overlay && !pass.banner_overlay && is_slug_max_text(c)){
                // 弹头车按钮框（含 “MAX” 字样，不受 ty≥590 例外覆盖）：保留翻转后的位置，
                // 图像恢复正向（x 范围不变：tx' = tx + a'·w，a' < 0），避免显示为 “XAM”；按钮内的弹头车图像仍翻转。
                float fa=bitsf(rd<uint32_t>(c,dst)),fb=bitsf(rd<uint32_t>(c,dst+4u)),w=bitsf(rd<uint32_t>(c,c.r[13]+4u));
                wr<uint32_t>(c,dst,fbits(-fa));wr<uint32_t>(c,dst+4u,fbits(-fb));
                wr<uint32_t>(c,dst+8u,fbits(bitsf(rd<uint32_t>(c,dst+8u))+fa*w));
            }
        }
        if(pass.rotate){                                   // 中间分隔条：绕片段中心旋转 180°
            float px=float(pass.clip[0])+float(pass.clip[2])*0.5f,py=float(pass.clip[1])+float(pass.clip[3])*0.5f;
            for(uint32_t k=0;k<6u;k+=3u){
                wr<uint32_t>(c,dst+k*4u,fbits(-bitsf(rd<uint32_t>(c,dst+k*4u))));
                wr<uint32_t>(c,dst+k*4u+4u,fbits(-bitsf(rd<uint32_t>(c,dst+k*4u+4u))));
            }
            wr<uint32_t>(c,dst+8u,fbits(2.0f*px-bitsf(rd<uint32_t>(c,dst+8u))));
            wr<uint32_t>(c,dst+20u,fbits(2.0f*py-bitsf(rd<uint32_t>(c,dst+20u))));
        }
        c.r[2]=dst;
        if(!clip_quad(c,dst)){c.pc=c.r[14];return;}
    }
    old(c);
}
Block old_fill;
void fill_hook(Context& c){
    if(pass.active){
        if(pass.banner_overlay && !drawing_banner){c.pc=c.r[14];return;}
        if(pass.filter==1){c.pc=c.r[14];return;}
        float s=pass.s;
        int x=int(std::lround(int32_t(c.r[1])*s+pass.offx)),y=int(std::lround(int32_t(c.r[2])*s+pass.offy));
        int w=int(std::lround(int32_t(c.r[3])*s)),h=int(std::lround(int32_t(rd<uint32_t>(c,c.r[13]))*s));
        if(pass.mirror)x=(pass.banner_overlay?int(2.0f*pass.mirror_center):pass.clip[0]*2+pass.clip[2])-(x+w);
        int x0=std::max(x,cur_clip[0]),y0=std::max(y,cur_clip[1]);
        int x1=std::min(x+w,cur_clip[0]+cur_clip[2]),y1=std::min(y+h,cur_clip[1]+cur_clip[3]);
        if(x1<=x0 || y1<=y0){c.pc=c.r[14];return;}
        c.r[1]=uint32_t(x0);c.r[2]=uint32_t(y0);c.r[3]=uint32_t(x1-x0);wr<uint32_t>(c,c.r[13],uint32_t(y1-y0));
    }
    old_fill(c);
}
Block old_setclip,old_clearclip;
// T3 敌我滤镜：出兵格循环的 setClip 之前（GraphicsOpt::setClip 已提交背景批次），在本遍 3 格窗口上叠半透明色块，
// 随后绘制的格子、头像、数字不受影响；警示条属于独立片段，不染色。
constexpr uint32_t TINT_MINE=0x462860ffu,TINT_ENEMY=0x46ff3030u;   // 约 27% 不透明
void draw_tint(Context& c,uint32_t g){
    uint32_t previous=0xffffffffu;
    pass.active=false;
    guest_call(c,G_GETCOLOR,g,0,0,0,nullptr,0,&previous);
    guest_call(c,G_SETCOLOR,g,enemy_pass?TINT_ENEMY:TINT_MINE);
    int top=int(BAR_TOP+BAR_BORDER_SRC*pass.s);                // 避开底栏上沿边框
    uint32_t stack[1]={uint32_t(pass.clip[1]+pass.clip[3]-top)};
    guest_call(c,G_FILL-1u,g,uint32_t(pass.clip[0]),uint32_t(top),uint32_t(pass.clip[2]),stack,1);
    guest_call(c,G_SETCOLOR,g,previous);
    pass.active=true;
}
void setclip_hook(Context& c){
    if(pass.active){
        if(pass.cells && !pass.tinted){pass.tinted=true;draw_tint(c,c.r[0]);}
        float s=pass.s;
        int x=int(std::floor(int32_t(c.r[1])*s+pass.offx)),y=int(std::floor(int32_t(c.r[2])*s+pass.offy));
        int w=int(std::ceil(int32_t(c.r[3])*s)),h=int(std::ceil(int32_t(rd<uint32_t>(c,c.r[13]))*s));
        int x0=std::max(x,pass.clip[0]),y0=std::max(y,pass.clip[1]);
        int x1=std::min(x+w,pass.clip[0]+pass.clip[2]),y1=std::min(y+h,pass.clip[1]+pass.clip[3]);
        cur_clip[0]=x0;cur_clip[1]=y0;cur_clip[2]=std::max(0,x1-x0);cur_clip[3]=std::max(0,y1-y0);
        c.pc=c.r[14];
        return;
    }
    old_setclip(c);
}
void clearclip_hook(Context& c){
    if(pass.active){
        std::memcpy(cur_clip,pass.clip,sizeof cur_clip);
        c.pc=c.r[14];
        return;
    }
    old_clearclip(c);
}

// 出兵栏状态（operator 偏移）：+24 控制器，+32 按下的格，+96 拖动状态，+100 滚动值，+104 最大滚动，+108 格距，+112 拖动中位置，+116 拖动标记。
constexpr uint32_t PANEL_WORDS[]={24,32,96,100,104,112,116};
// 敌方出兵栏状态存放在头部 +0x70 起 7 字（与 PANEL_WORDS 对应），+0x6c 为已初始化标记（宿主开战时清零），
// 宿主可直接改写 +0x7c（滚动值）实现按键自动滚动。
constexpr uint32_t ENEMY_PANEL_READY=H+0x6cu,ENEMY_PANEL=H+0x70u;
void swap_panel(Context& c,uint32_t op){
    for(int i=0;i<7;++i){
        uint32_t a=op+PANEL_WORDS[i],b=ENEMY_PANEL+uint32_t(i)*4u,t=rd<uint32_t>(c,a);
        wr<uint32_t>(c,a,rd<uint32_t>(c,b));wr<uint32_t>(c,b,t);
    }
}
void ensure_enemy_panel(Context& c,uint32_t op){
    if(rd<uint32_t>(c,ENEMY_PANEL_READY)!=1u){
        for(int i=0;i<7;++i)wr<uint32_t>(c,ENEMY_PANEL+uint32_t(i)*4u,rd<uint32_t>(c,op+PANEL_WORDS[i]));
        wr<uint32_t>(c,ENEMY_PANEL+4u,0xffffffffu);wr<uint32_t>(c,ENEMY_PANEL+8u,0u);wr<uint32_t>(c,ENEMY_PANEL+12u,0u);
        wr<uint32_t>(c,ENEMY_PANEL+20u,0u);wr<uint32_t>(c,ENEMY_PANEL+24u,rd<uint32_t>(c,op+116u)&~0xffu);
        wr<uint32_t>(c,ENEMY_PANEL_READY,1u);
    }
    wr<uint32_t>(c,ENEMY_PANEL,rd<uint32_t>(c,ENEMY_CONTROLLER));
}
// 3 格窗口：最大滚动 =（槽位数 − 3）× 格距。
uint32_t max_scroll(Context& c,uint32_t op,uint32_t controller){
    float pitch=bitsf(rd<uint32_t>(c,op+108u));
    int count=int32_t(rd<uint32_t>(c,controller+912u));
    return uint32_t(std::max(0,count-3)*int(pitch+0.5f));
}
// 敌方出兵格图集：宿主在战斗开始后以敌方控制器调用 BattlePlayerOperator::createGrahics（含 OBM 读取，须在顶层执行），
// 把生成的 operator+188…+220 九个字写入头部 +0x40 起，+0x3c 置 1。敌方各遍与 operator 原值互换。
constexpr uint32_t GFX_READY=H+0x3cu,GFX_BASE=H+0x40u,GFX_FIRST=188u,GFX_WORDS=9u;
void swap_gfx(Context& c,uint32_t op){
    if(rd<uint32_t>(c,GFX_READY)!=1u)return;
    for(uint32_t i=0;i<GFX_WORDS;++i){
        uint32_t a=op+GFX_FIRST+i*4u,b=GFX_BASE+i*4u,t=rd<uint32_t>(c,a);
        wr<uint32_t>(c,a,rd<uint32_t>(c,b));wr<uint32_t>(c,b,t);
    }
}
// 敌方横幅：十个交换字段保存六个槽指针、显示/滚入状态及优先标记，六个槽各 28 字节。
// 原生 playTargetAction 分配槽内 +4 的 BattleSprite；宿主结束 LAB 时 release 后清除此区（hooks 9）。
constexpr uint32_t BANNER_BASE=H+0x100u,BANNER_READY=H+0x128u,BANNER_SLOTS=H+0x140u;
constexpr uint32_t BANNER_WORDS[]={120u,124u,128u,132u,136u,140u,144u,148u,152u,224u};
constexpr uint32_t TARGET_ACTION=0x101d6fdcu,TARGET_UPDATE=0x101d6c48u;
void ensure_enemy_banner(Context& c){
    if(rd<uint32_t>(c,BANNER_READY)==1u)return;
    for(uint32_t i=0;i<6u;++i){
        uint32_t slot=BANNER_SLOTS+i*28u;
        for(uint32_t j=0;j<28u;j+=4u)wr<uint32_t>(c,slot+j,0u);
        wr<uint32_t>(c,BANNER_BASE+i*4u,slot);
    }
    for(uint32_t i=6u;i<10u;++i)wr<uint32_t>(c,BANNER_BASE+i*4u,0u);
    wr<uint32_t>(c,BANNER_READY,1u);
}
void swap_banner(Context& c,uint32_t op){
    for(uint32_t i=0;i<10u;++i){
        uint32_t a=op+BANNER_WORDS[i],b=BANNER_BASE+i*4u,t=rd<uint32_t>(c,a);
        wr<uint32_t>(c,a,rd<uint32_t>(c,b));wr<uint32_t>(c,b,t);
    }
}
// 与 BattlePlayerOperator::update（0x1d6ae4…0x1d6b3c）一致：动画 1 的第 36 帧播放敬礼声音 7，
// 升级动作播完且据点未满级时回到动画 0；随后依次推进人物和金币。敌方图集换入期间每帧执行一次。
constexpr uint32_t SPRITE_GET_ANIMATION=0x101db8eau,SPRITE_GET_FRAME=0x101dbc0cu,SPRITE_IS_PLAYING=0x101db8f0u;
constexpr uint32_t SPRITE_CHANGE=0x101dc3eau,SPRITE_UPDATE=0x101dc4a6u;
constexpr uint32_t COIN_UPDATE=0x101d678cu,COIN_DRAW=0x101d6880u,SOUND_PLAY=0x1016c17au;
constexpr uint32_t KYOTEN_LEVEL_MAX=0x101cbd78u;
void tick_enemy_sprite(Context& c,uint32_t op){
    uint32_t sprite=rd<uint32_t>(c,op+204u),value=0;
    if(!sprite)return;
    guest_call(c,SPRITE_GET_ANIMATION,sprite,0,0,0,nullptr,0,&value);
    if(value==1u){
        guest_call(c,SPRITE_GET_FRAME,sprite,0,0,0,nullptr,0,&value);
        if(value==36u)guest_call(c,SOUND_PLAY,0u,7u,0u);
        guest_call(c,SPRITE_IS_PLAYING,sprite,0,0,0,nullptr,0,&value);
        if(!value){
            guest_call(c,KYOTEN_LEVEL_MAX,rd<uint32_t>(c,op+24u),0,0,0,nullptr,0,&value);
            if(!value)guest_call(c,SPRITE_CHANGE,sprite,0,0);
        }
    }
    guest_call(c,SPRITE_UPDATE,sprite);
    uint32_t coin=rd<uint32_t>(c,op+208u);
    if(coin)guest_call(c,COIN_UPDATE,coin);
}
void run_pass(Context& c,uint32_t op,const Pass& p,uint32_t fn=DRAWUI){
    pass=p;
    drawing_banner=false;
    std::memcpy(cur_clip,p.clip,sizeof cur_clip);
    guest_call(c,fn,op);
    pass.active=false;
    drawing_banner=false;
}

Block old_drawui_entry;
bool in_ui=false;
void drawui_entry(Context& c){
    // graphics_ptr 在首次 Graphics 绘制时取得；取得之前按原生流程绘制一帧。
    if(in_ui || !split_enabled(c) || !graphics_ptr){old_drawui_entry(c);return;}
    uint32_t ret=c.r[14],op=c.r[0];
    in_ui=true;
    if(!laid_out_once){layout();laid_out_once=true;}
    ensure_enemy_panel(c,op);
    ensure_enemy_banner(c);
    uint32_t mine=rd<uint32_t>(c,op+24u);
    wr<uint32_t>(c,op+104u,max_scroll(c,op,mine));
    wr<uint32_t>(c,ENEMY_PANEL+16u,max_scroll(c,op,rd<uint32_t>(c,ENEMY_PANEL)));
    // 第 0 遍：底栏以外。
    Pass base;base.active=true;base.s=1.0f;base.no_apbar=true;
    base.clip[0]=int(SCREEN_LEFT)-1;base.clip[1]=0;base.clip[2]=int(SCREEN_RIGHT-SCREEN_LEFT)+2;base.clip[3]=int(BAR_TOP);
    run_pass(c,op,base);
    // AP 数值框（T5）：我方原位，敌方翻转到右下；下沿由随后绘制的底栏压住，与原版一致。
    Pass apm;apm.active=true;apm.s=1.0f;
    apm.clip[0]=int(AP_BOX_LEFT)-2;apm.clip[1]=int(AP_BOX_TOP)-8;
    apm.clip[2]=int(AP_BOX_RIGHT-AP_BOX_LEFT)+4;apm.clip[3]=int(AP_BOX_BOTTOM)+2-apm.clip[1];
    run_pass(c,op,apm,DRAW_AP_BAR);
    Pass apb=apm;apb.apbar=true;
    apb.offx=(SCREEN_LEFT+SCREEN_RIGHT-AP_BOX_RIGHT)-AP_BOX_LEFT;
    apb.clip[0]=int(SCREEN_LEFT+SCREEN_RIGHT-AP_BOX_RIGHT)-2;
    swap_panel(c,op);
    enemy_pass=true;
    run_pass(c,op,apb,DRAW_AP_BAR);
    enemy_pass=false;
    swap_panel(c,op);
    for(int i=0;i<SEGMENT_COUNT;++i){
        const Segment& g=SEGMENTS[i];
        Pass p;p.active=true;p.s=SCALE;p.filter=g.filter;p.cells=(g.src0==184.0f);
        p.ap_button=(g.src0==18.0f);
        p.mirror=g.mirror;
        p.mirror_sprite=g.enemy && g.src0==18.0f;
        p.offx=seg_dest[i]-SCALE*g.src0;
        p.offy=BAR_TOP*(1.0f-SCALE);                       // 以底栏上沿为基准缩放
        p.clip[0]=int(std::floor(seg_dest[i]));p.clip[1]=int(BAR_TOP);
        p.clip[2]=int(std::ceil(SCALE*(g.src1-g.src0)))+1;p.clip[3]=int(std::ceil((BAR_BOTTOM-BAR_TOP)*SCALE));
        if(g.enemy){swap_panel(c,op);swap_gfx(c,op);}
        p.atlas=rd<uint32_t>(c,op+188u);
        enemy_pass=g.enemy;
        if(g.enemy && g.src0==155.0f){
            // 中间分隔条（取自敌方左警示条）：上沿边框不动，条纹段绕自身中心旋转 180°，避免与两侧重复。
            int border=int(BAR_TOP+BAR_BORDER_SRC*SCALE),bottom=p.clip[1]+p.clip[3];
            Pass top=p;top.clip[3]=border-p.clip[1];
            run_pass(c,op,top);
            p.rotate=true;p.clip[1]=border;p.clip[3]=bottom-border;
        }
        run_pass(c,op,p);
        enemy_pass=false;
        if(g.enemy){swap_gfx(c,op);swap_panel(c,op);}
    }
    // 缩放后底栏下方留出的带状区域：以底栏底色填充。
    if(graphics_ptr){
        float bottom=BAR_TOP+(BAR_BOTTOM-BAR_TOP)*SCALE;
        uint32_t stack[1]={uint32_t(int(BAR_BOTTOM-bottom)+2)};
        guest_call(c,0x101417dfu-1u,graphics_ptr,0xff1c1c1cu);                 // Graphics::setColor
        guest_call(c,G_FILL-1u,graphics_ptr,uint32_t(int(SCREEN_LEFT)-1),uint32_t(int(bottom)),uint32_t(int(SCREEN_RIGHT-SCREEN_LEFT)+2),stack,1);
        guest_call(c,0x101417dfu-1u,graphics_ptr,0xffffffffu);
    }
    // 原生 drawUI 在人物之后绘制金币（0x1d92f6）。分栏金币统一置于 AP 框及底栏之上，
    // 使用对应 AP 按钮的变换并允许越过框体；各侧金币对象独立，敌方镜像中心采用其按钮中心。
    for(int i=0;i<SEGMENT_COUNT;++i){
        const Segment& g=SEGMENTS[i];
        if(g.src0!=18.0f || (g.enemy && rd<uint32_t>(c,GFX_READY)!=1u))continue;
        uint32_t coin=rd<uint32_t>(c,g.enemy?GFX_BASE+20u:op+208u);
        if(!coin)continue;
        Pass p;p.active=true;p.coin_overlay=true;p.s=SCALE;p.mirror=g.enemy;
        p.offx=seg_dest[i]-SCALE*g.src0;p.offy=BAR_TOP*(1.0f-SCALE);
        p.mirror_center=seg_dest[i]+SCALE*(g.src1-g.src0)*0.5f;
        p.clip[0]=int(SCREEN_LEFT)-1;p.clip[1]=0;
        p.clip[2]=int(SCREEN_RIGHT-SCREEN_LEFT)+2;p.clip[3]=int(BAR_BOTTOM);
        run_pass(c,coin,p,COIN_DRAW);
    }
    if(rd<uint32_t>(c,GFX_READY)==1u){
        Pass p;p.active=true;p.banner_overlay=true;p.mirror=true;
        p.mirror_center=(SCREEN_LEFT+SCREEN_RIGHT)*0.5f;
        p.clip[0]=int(SCREEN_LEFT)-1;p.clip[1]=0;
        p.clip[2]=int(SCREEN_RIGHT-SCREEN_LEFT)+2;p.clip[3]=int(BAR_BOTTOM);
        swap_panel(c,op);swap_gfx(c,op);swap_banner(c,op);
        run_pass(c,op,p);
        swap_banner(c,op);swap_gfx(c,op);swap_panel(c,op);
    }
    in_ui=false;
    c.pc=ret;
}
// ---------- 底栏分栏的触点换算 ----------
// onTouchBegan/Moved/Ended 在 y≥512 时尾调用 onUITouchBegan/Moved/Ended(op,x,y,…)。入口处按按下时所在的片段
// 把新布局坐标换回原生坐标（x=(x−offx)/s，y=(y−offy)/s），敌方片段临时换入敌方出兵栏状态，出口块执行后换回。
int touch_segment=-1;bool touch_swapped=false;uint32_t touch_op=0;
int segment_at(float x,float y){
    if(y<BAR_TOP)return -1;
    for(int i=0;i<SEGMENT_COUNT;++i){
        float w=SCALE*(SEGMENTS[i].src1-SEGMENTS[i].src0);
        if(x>=seg_dest[i] && x<seg_dest[i]+w)return i;
    }
    return -1;
}
float to_src_x(int i,float x){return i<0?-10000.0f:(x-(seg_dest[i]-SCALE*SEGMENTS[i].src0))/SCALE;}
float to_src_y(float y){return (y-BAR_TOP*(1.0f-SCALE))/SCALE;}
bool touch_enter(Context& c,bool began,bool has_prev){
    if(!split_enabled(c) || !laid_out_once)return true;
    uint32_t op=c.r[0];
    if(began)touch_segment=segment_at(float(int32_t(c.r[1])),float(int32_t(c.r[2])));
    int i=touch_segment;
    bool enemy=i>=0 && SEGMENTS[i].enemy;
    c.r[1]=uint32_t(int32_t(std::lround(to_src_x(i,float(int32_t(c.r[1]))))));
    c.r[2]=uint32_t(int32_t(std::lround(to_src_y(float(int32_t(c.r[2]))))));
    if(has_prev){                                              // onUITouchMoved(op,x,y,上一 x,上一 y)
        c.r[3]=uint32_t(int32_t(std::lround(to_src_x(i,float(int32_t(c.r[3]))))));
        uint32_t py=rd<uint32_t>(c,c.r[13]);
        wr<uint32_t>(c,c.r[13],uint32_t(int32_t(std::lround(to_src_y(float(int32_t(py)))))));
    }
    if(enemy){swap_panel(c,op);touch_swapped=true;touch_op=op;}
    return true;
}
Block old_ui_began,old_ui_moved,old_ui_ended;
void ui_began(Context& c){if(touch_enter(c,true,false))old_ui_began(c);}
void ui_moved(Context& c){if(touch_enter(c,false,true))old_ui_moved(c);}
void ui_ended(Context& c){if(touch_enter(c,false,false))old_ui_ended(c);}
// 三个处理函数的全部出口块（均以出栈返回结束）：先执行原块，再换回我方状态。
constexpr uint32_t UI_EXITS[]={0x101d725du,0x101d7263u,0x101d72c1u,0x101d72c9u,0x101d72cfu,0x101d7311u,0x101d73d3u,0x101d73d7u,0x101d7411u};
constexpr int UI_EXIT_COUNT=int(sizeof UI_EXITS/sizeof UI_EXITS[0]);
Block old_ui_exit[UI_EXIT_COUNT];
template<int K> void ui_exit(Context& c){
    old_ui_exit[K](c);
    if(touch_swapped){
        touch_swapped=false;
        // 拖动结束时（+96==2）原生 update 只为我方逐帧收敛滚动；敌方直接定位到吸附后的滚动值。
        if(rd<uint32_t>(c,touch_op+96u)==2u){wr<uint32_t>(c,touch_op+96u,0u);wr<uint32_t>(c,touch_op+112u,fbits(float(int32_t(rd<uint32_t>(c,touch_op+100u)))));}
        swap_panel(c,touch_op);
    }
}
template<int... K> void install_ui_exits(std::integer_sequence<int,K...>){
    ((old_ui_exit[K]=find_block(UI_EXITS[K]),register_block(UI_EXITS[K],ui_exit<K>)),...);
}
// onUITouchMoved 的拖动条件（0x1d7282 / 0x1d728c 两个入口块内）：槽位数（controller+912）不超过可见格数
// （operator+12 为 0 时 5，否则 6）即放弃拖动。分栏每侧只显示 3 格，4–6 个单位同样需要拖动；
// 分栏时在这两个块执行期间把计数临时视为 7，块返回后立即还原。实际滚动范围由 operator+104（max_scroll）限定。
Block old_drag_check_a,old_drag_check_b;
template<Block* Old> void drag_check(Context& c){
    uint32_t controller=split_enabled(c)?rd<uint32_t>(c,c.r[4]+24u):0u;
    uint32_t count=controller?rd<uint32_t>(c,controller+912u):0u;
    bool widen=controller && int32_t(count)>3 && int32_t(count)<=6;
    if(widen)wr<uint32_t>(c,controller+912u,7u);
    (*Old)(c);
    if(widen)wr<uint32_t>(c,controller+912u,count);
}
void install_touch_hooks(){
    old_drag_check_a=find_block(0x101d7283u);register_block(0x101d7283u,drag_check<&old_drag_check_a>);
    old_drag_check_b=find_block(0x101d728du);register_block(0x101d728du,drag_check<&old_drag_check_b>);
    old_ui_began=find_block(0x101d7209u);register_block(0x101d7209u,ui_began);
    old_ui_moved=find_block(0x101d7265u);register_block(0x101d7265u,ui_moved);
    old_ui_ended=find_block(0x101d7315u);register_block(0x101d7315u,ui_ended);
    install_ui_exits(std::make_integer_sequence<int,UI_EXIT_COUNT>{});
}
// 分栏常规各遍统一跳过金币；两侧最后各执行一次金币覆盖层，保持原生框体与动效绘制顺序。
Block old_coin_draw;
void coin_draw(Context& c){
    if(pass.active && !pass.coin_overlay){c.pc=c.r[14];return;}
    old_coin_draw(c);
}
// ---------- 敌方 AP 按钮人物的动画（与我方相同的逻辑） ----------
// 我方：BattlePlayerOperator::update 每帧推进 operator+204；BattleScene 的事件切换动画——
//   onEventBaseLevelup（本方）→ playBaseLevelupAction（动画 1），onEventFeverTimeStart（本方）→ changeRumiAnimationLevelMAX，
//   onEventBaseUnitDead → battleFinish 后本方据点被毁为 Escape，否则（本方未满级时）为 Win。
// 敌方：在上述函数入口以敌方图集与出兵栏状态执行对应动作（敌方据点被毁 → Escape，我方据点被毁 → Win）。
bool enemy_sprite_ready(Context& c){return split_enabled(c) && rd<uint32_t>(c,GFX_READY)==1u && rd<uint32_t>(c,ENEMY_PANEL_READY)==1u;}
template<class F> void with_enemy(Context& c,uint32_t op,F action){
    // 敌方鼠标输入处理期间已换入该控制器，升级事件可在其返回前同步到达。
    bool panel_swapped=rd<uint32_t>(c,op+24u)!=rd<uint32_t>(c,ENEMY_CONTROLLER);
    if(panel_swapped)swap_panel(c,op);
    ensure_enemy_banner(c);
    swap_gfx(c,op);swap_banner(c,op);action();swap_banner(c,op);swap_gfx(c,op);
    if(panel_swapped)swap_panel(c,op);
}
void origin_observe(Context& c);                                // 第 13 版：单位来源记录（定义见 ai_invest 前）
void front_observe(Context& c);                                 // 第 18 版：相持判定（定义见 ai_front_ratio 后）
Block old_operator_update;
void operator_update(Context& c){
    uint32_t op=c.r[0];
    if(enemy_sprite_ready(c))with_enemy(c,op,[&]{tick_enemy_sprite(c,op);});
    origin_observe(c);
    front_observe(c);
    old_operator_update(c);
}
// BattleScene 逐帧调用 update_TargetAction；双方独立使用原生入场、45 tick 等待及退场状态机。
Block old_target_update,old_banner_begin,old_banner_end,old_scene_slug;
bool in_target_update=false;
void target_update(Context& c){
    uint32_t op=c.r[0];
    if(!in_target_update && enemy_sprite_ready(c)){
        in_target_update=true;
        with_enemy(c,op,[&]{guest_call(c,TARGET_UPDATE,op);});
        in_target_update=false;
    }
    old_target_update(c);
}
void banner_begin(Context& c){drawing_banner=true;old_banner_begin(c);}
void banner_end(Context& c){drawing_banner=false;old_banner_end(c);}
void scene_slug(Context& c){                                  // onEventMetasuraHou(scene, charge, team, member, bool)
    uint32_t op=rd<uint32_t>(c,c.r[0]+60u);
    if(enemy_sprite_ready(c) && c.r[2]==rd<uint32_t>(c,ENEMY_TEAM))
        with_enemy(c,op,[&]{guest_call(c,TARGET_ACTION,op,7u,0u);}); // 原生 ATTACK 横幅
    old_scene_slug(c);
}
constexpr uint32_t BASE_LEVELUP_ACTION=0x101d711cu,RUMI_LEVEL_MAX=0x101d7196u,RUMI_ESCAPE=0x101d71b2u,RUMI_WIN=0x101d71ceu;
Block old_fever,old_levelup,old_base_dead;
void scene_fever(Context& c){                                  // onEventFeverTimeStart(scene, team)
    uint32_t scene=c.r[0],op=rd<uint32_t>(c,scene+60u);
    if(enemy_sprite_ready(c) && c.r[1]==rd<uint32_t>(c,ENEMY_TEAM))
        with_enemy(c,op,[&]{guest_call(c,RUMI_LEVEL_MAX,op);});
    old_fever(c);
}
void scene_levelup(Context& c){                                // onEventBaseLevelup(scene, team, level, member, bool)
    uint32_t scene=c.r[0],op=rd<uint32_t>(c,scene+60u);
    if(enemy_sprite_ready(c) && c.r[1]==rd<uint32_t>(c,ENEMY_TEAM) && c.r[3]==rd<uint32_t>(c,ENEMY_MEMBER))
        // 完整原生动作包含通知、人物动画 1、金币初始化和同 tick 的 OKAY 声音 26。
        with_enemy(c,op,[&]{guest_call(c,BASE_LEVELUP_ACTION,op);});
    old_levelup(c);
}
void scene_base_dead(Context& c){                              // onEventBaseUnitDead(scene, ?, team)
    uint32_t scene=c.r[0],op=rd<uint32_t>(c,scene+60u),team=c.r[2];
    if(enemy_sprite_ready(c)){
        with_enemy(c,op,[&]{
            uint32_t max=0;
            if(team==rd<uint32_t>(c,ENEMY_TEAM))guest_call(c,RUMI_ESCAPE,op);
            else{
                guest_call(c,KYOTEN_LEVEL_MAX,rd<uint32_t>(c,op+24u),0,0,0,nullptr,0,&max);
                if(!max)guest_call(c,RUMI_WIN,op);
            }
        });
    }
    old_base_dead(c);
}
// ---------- T7：AI 自动出兵与自动绝招拆分（功能位 16） ----------
// BattleControllerPlayerBase::noukinAutoPlay（0x1cbfe0，原生 AUTO 每帧一步）：等待计时 → 弹头车（0x1cc018）→
// 逐个本方单位检查绝招（0x1cc04e isSpAttack，就绪则 0x1cc426 发动）→ 0x1cc070 起为出兵等决策。
// 宿主在任一开关开启时对该方 startAutoPlay；头部 +0x30 的禁用位决定跳过哪一部分：
//   位 0/1：我方 自动出兵/自动绝招 关闭；位 2/3：敌方 自动出兵/自动绝招 关闭。“自动出兵”含弹头车与出兵决策。
constexpr uint32_t FLAG_AUTO_SPLIT=16u,AUTO_DISABLE=H+0x30u;
uint32_t auto_disabled(Context& c,uint32_t controller){
    uint32_t bits=rd<uint32_t>(c,AUTO_DISABLE);
    return controller==rd<uint32_t>(c,ENEMY_CONTROLLER)?(bits>>2)&3u:bits&3u;   // 位 0 出兵，位 1 绝招
}
// getAutoPlay 的返回值参与底栏的手动出兵许可与格子显示。自动绝招单独开启时，
// 底层 controller+1052 仍驱动 update 中的 noukinAutoPlay；对手动输入与 UI 返回关闭出兵 AUTO。
// 自动出兵禁用位仅改变该查询结果，AP、生产冷却与人数上限继续由原生函数核查。
Block old_auto_query,old_auto_slug,old_auto_special,old_auto_deploy;
void auto_query(Context& c){                                  // 0x1cba34：r0=控制器
    if(enabled(c,FLAG_AUTO_SPLIT) && (auto_disabled(c,c.r[0])&1u)){
        c.r[0]=0u;c.pc=c.r[14];return;
    }
    old_auto_query(c);
}
void auto_slug(Context& c){                                    // 0x1cc018：r0=isUseMetasuraHou，r4=控制器
    if(enabled(c,FLAG_AUTO_SPLIT) && (auto_disabled(c,c.r[4])&1u)){c.pc=0x101cc02bu;return;}
    old_auto_slug(c);
}
void auto_special(Context& c){                                 // 0x1cc04e：r5=单位
    if(enabled(c,FLAG_AUTO_SPLIT) && (auto_disabled(c,c.r[4])&2u)){c.pc=0x101cc061u;return;}
    old_auto_special(c);
}
// ---------- 第 11 版：AI 段位（功能位 128） ----------
// noukinAutoPlay（0x1cbfe0）每次出兵、弹头车或绝招后调用 setAutoPlayWaitTimer（0x1cbfca），等待 rand() & mask 帧
// （mask = controller+0x420，startAutoPlay 以 rand()%240 抽取）。段位启用时改为 [下限, 上限] 内均匀随机。
// 据点：原生在未处于劣势时只要 AP 够就升据点直至满级。段位的“开局据点目标”：低于目标且敌方前线未推进到
// 己方 60% 以内（原生 r7≥2 的同一判据）时优先升级，AP 不足则保留 AP；达到目标后，AI 自身对 isKyotenLevelup
// （0x1cbd48）的调用只在 AP 已满且没有可出单位时放行。紧急阈值（controller+0x424）由宿主写入。
// 头部 +0x500 我方、+0x520 敌方：+0 启用、+4 等待下限、+8 等待上限（帧）、+12 据点目标（负数为原生）。
constexpr uint32_t FLAG_AI_TIER=128u,AI_TIER_BASE=H+0x500u;
constexpr uint32_t NOUKIN_BEGIN=0x101cbfe0u,NOUKIN_END=0x101cc534u,DECISION_EXIT=0x101cc52fu;
constexpr uint32_t P_IS_LEVELUP=0x101cbd49u,P_MAX_AP=0x101cbdf5u,P_IS_UNIT_CREATE=0x101cbd87u;
constexpr uint32_t P_STAGE_INSTANCE=0x101e1ae1u,P_BASE_X=0x101e1cf3u;
uint32_t ai_rng=0x9e3779b9u;
uint32_t ai_random(){ai_rng^=ai_rng<<13;ai_rng^=ai_rng>>17;ai_rng^=ai_rng<<5;return ai_rng;}
uint32_t ai_tier(Context& c,uint32_t controller){              // 该控制器的段位块地址；未启用为 0
    if(!enabled(c,FLAG_AI_TIER))return 0u;
    uint32_t block=AI_TIER_BASE+(controller==rd<uint32_t>(c,ENEMY_CONTROLLER)?0x20u:0u);
    return rd<uint32_t>(c,block)?block:0u;
}
Block old_ai_wait,old_ai_levelup_query;
void ai_wait(Context& c){                                      // setAutoPlayWaitTimer(controller)
    if(uint32_t tier=ai_tier(c,c.r[0])){
        uint32_t low=rd<uint32_t>(c,tier+4u),high=rd<uint32_t>(c,tier+8u);
        if(high<low)high=low;
        wr<uint32_t>(c,c.r[0]+0x428u,low+ai_random()%(high-low+1u));
        c.pc=c.r[14];return;
    }
    old_ai_wait(c);
}
bool ai_ap_full(Context& c,uint32_t controller){                // AP 已满（≥98% 上限）。第 18 版起不再要求无可出单位：
    uint32_t level=rd<uint32_t>(c,controller+0x3fcu),max_ap=0;      // AP 满档轮流出兵会使“无可出单位”几乎不成立
    guest_call(c,P_MAX_AP,controller,level,0,0,nullptr,0,&max_ap);
    return rd<float>(c,controller+0x404u)>=float(int32_t(max_ap))*0.98f;
}
void ai_levelup_query(Context& c){                             // isKyotenLevelup(controller)
    uint32_t controller=c.r[0],lr=c.r[14]&~1u;
    if(lr>=NOUKIN_BEGIN && lr<NOUKIN_END)
        if(uint32_t tier=ai_tier(c,controller)){
            int32_t target=int32_t(rd<uint32_t>(c,tier+12u));
            if(target>=0 && int32_t(rd<uint32_t>(c,controller+0x3fcu))>=target && !ai_ap_full(c,controller)){
                c.r[0]=0u;c.pc=c.r[14];return;
            }
        }
    old_ai_levelup_query(c);
}
bool ai_enemy_near(Context& c,uint32_t controller){            // 原生 r7≥2：对方最前单位推进到距己方据点 60% 以内
    uint32_t manager=0,stage=0,base0=0,base1=0;
    guest_call(c,OBJECT_MANAGER_GET_INSTANCE,0,0,0,0,nullptr,0,&manager);
    guest_call(c,P_STAGE_INSTANCE,0,0,0,0,nullptr,0,&stage);
    uint32_t team=rd<uint32_t>(c,controller+0x38cu)&1u;
    uint32_t front=rd<uint32_t>(c,manager+(12u+(team^1u))*4u);
    if(!front)return false;
    guest_call(c,P_BASE_X,stage,0,0,0,nullptr,0,&base0);
    guest_call(c,P_BASE_X,stage,1,0,0,nullptr,0,&base1);
    float width=float(int32_t(base1)-int32_t(base0));
    float d=rd<float>(c,front+0x8cu)-float(int32_t(base0));
    if(team==1u)d=width-d;
    return d<=width*0.6f;
}
bool ai_opening(Context& c,uint32_t controller){               // true：本帧已处理（升级或保留 AP），退出决策
    uint32_t tier=ai_tier(c,controller);
    if(!tier)return false;
    int32_t target=int32_t(rd<uint32_t>(c,tier+12u));
    if(target<0 || int32_t(rd<uint32_t>(c,controller+0x3fcu))>=target || ai_enemy_near(c,controller))return false;
    uint32_t can=0;guest_call(c,P_IS_LEVELUP,controller,0,0,0,nullptr,0,&can);
    if(can&0xffu)guest_call(c,rd<uint32_t>(c,rd<uint32_t>(c,controller)+0xa8u),controller);   // 与原生 0x1cc464 相同的虚函数
    return true;
}
// ---------- 第 12 版：AI 段位的出兵选择（单位价值、积累 AP、建筑类单位） ----------
// noukinAutoPlay 在 0x1cc40e 以 r5 槽位调用 vtable+0x94 出兵。段位块 +20 的“理解度”s（0–100，0 为原生选择）
// 大于 0 时在此改由下列规则选择或暂不出兵（暂不出兵时不设等待，下一帧重新判断）：
//   单位价值 S = √(HP × 每秒伤害) × (1 + min(击退门槛, 40)/40)，按 BattleInfo::getUnitStatus 的等级状态计算：
//   +0xc HP、+0x10 击退门槛×100（≤0 为每次受击均击退）、+0x58 普攻伤害、+0x6c 普攻等待、+0x74 绝招伤害、+0x8c 绝招冷却；
//   每秒伤害 = 普攻伤害×30/(普攻等待+30) + 绝招伤害×30/max(绝招冷却,30)。建筑类（行动类为 Kouhei 系或 Donou，
//   本体 HP 1、无伤害）以原生 AI 战力（状态 +0xc8）×12 估计其建成后的价值（按基寇卡、士兵的 S/战力比校准）。
//   排序值 = S / AP^(1−0.75s) × (1 + 0.6(1−s)·u)，u 为 [−1,1] 随机（理解度越低越看重性价比、越容易误判；越高越看重单位本身强度）。
//   目标为当前据点 AP 上限内、冷却完毕或在 3s 秒内完毕的排序最高者；目标暂不能出时积累 AP，出其他单位后余下的 AP
//   仍不少于目标 AP×(1+s) 时才出其他单位；已积累超过 s×450 帧，或处于压力
//   （对方前线推进到距己方据点 (0.4−0.2s)×场宽以内，或对方场上战力比己方高 400+1200s 以上），此时改出能买得起的最高者。
//   建筑类只在对方有单位在场、且对方前线位于己方半场（≤0.5 场宽）时出击，使其在己方一侧建成。
//   积累方式在策略 A（填补）与 B（囤积）之间随机切换，见 ai_hoard。
constexpr uint32_t P_INFO_INSTANCE=0x101cfa4du,P_UNIT_STATUS=0x101cfbcdu,ACTION_TABLE_GOT=0x109373f4u;
constexpr uint32_t STATUS_SCRATCH=H+0x600u,AI_STATS_BASE=H+0x540u;
constexpr uint32_t BUILDER_VTABLES[]={0x10929950u,0x10929980u,0x1092b600u,0x1092b750u};   // Kouhei、Donou、Mortar_Kouhei、GuerrillaMortar_Kouhei
struct UnitValue{uint32_t uid,level;float value;bool builder;};
UnitValue unit_values[96];uint32_t unit_value_count;
uint32_t ai_saving[2],ai_saving_controller[2];
// 出兵策略（用户要求随机切换）：每次出兵后以各 50% 重新抽取。
//   A 填补：积累目标只看 3s 秒内冷却结束的单位；余下 AP 不少于目标 AP×(1+s) 时出其他单位；最长积累 s×450 帧。
//   B 囤积：积累目标看 30s 秒内冷却结束的单位（等待高价值单位冷却）；期间不出其他单位；最长积累 s×900 帧。
//   两种策略下，压力（据点受威胁或场上战力明显落后）都改为出能买得起的最高者。
uint32_t ai_hoard[2];
bool ai_is_builder(Context& c,uint32_t uid){
    uint32_t table=rd<uint32_t>(c,ACTION_TABLE_GOT);
    uint32_t action=table?rd<uint32_t>(c,table+uid*4u):0u;
    if(!action)return false;
    uint32_t vt=rd<uint32_t>(c,action);
    for(uint32_t v:BUILDER_VTABLES)if(vt==v)return true;
    return false;
}
const UnitValue& ai_unit_value(Context& c,uint32_t uid,uint32_t level){
    for(uint32_t i=0;i<unit_value_count;++i)if(unit_values[i].uid==uid && unit_values[i].level==level)return unit_values[i];
    if(unit_value_count>=96)unit_value_count=0;
    uint32_t info=0;guest_call(c,P_INFO_INSTANCE,0,0,0,0,nullptr,0,&info);
    for(uint32_t o=0;o<0xecu;o+=4u)wr<uint32_t>(c,STATUS_SCRATCH+o,0u);
    guest_call(c,P_UNIT_STATUS,info,uid,level,STATUS_SCRATCH);
    auto si=[&](uint32_t o){return float(int32_t(rd<uint32_t>(c,STATUS_SCRATCH+o)));};
    UnitValue v{uid,level,0.0f,ai_is_builder(c,uid)};
    if(v.builder){
        v.value=std::max(si(0xc8u),1.0f)*12.0f;
    }else{
        float hp=std::max(si(0xcu),1.0f),threshold=std::max(si(0x10u)/100.0f,0.0f);
        float dps=std::max(si(0x58u),0.0f)*30.0f/(std::max(si(0x6cu),0.0f)+30.0f);
        if(si(0x74u)>0.0f)dps+=si(0x74u)*30.0f/std::max(si(0x8cu),30.0f);
        v.value=std::sqrt(hp*std::max(dps,1.0f))*(1.0f+std::min(threshold,40.0f)/40.0f);
    }
    unit_values[unit_value_count++]=v;
    return unit_values[unit_value_count-1];
}
float ai_front_ratio_team(Context& c,uint32_t team,bool& present){   // 对方最前单位距 team 据点的场宽比例
    uint32_t manager=0,stage=0,base0=0,base1=0;
    guest_call(c,OBJECT_MANAGER_GET_INSTANCE,0,0,0,0,nullptr,0,&manager);
    present=false;
    if(!manager)return 1.0f;
    guest_call(c,P_STAGE_INSTANCE,0,0,0,0,nullptr,0,&stage);
    uint32_t front=rd<uint32_t>(c,manager+(12u+(team^1u))*4u);
    present=front!=0u;
    if(!front)return 1.0f;
    guest_call(c,P_BASE_X,stage,0,0,0,nullptr,0,&base0);
    guest_call(c,P_BASE_X,stage,1,0,0,nullptr,0,&base1);
    float width=float(int32_t(base1)-int32_t(base0));
    float d=rd<float>(c,front+0x8cu)-float(int32_t(base0));
    if(team==1u)d=width-d;
    return width>0.0f?d/width:1.0f;
}
float ai_front_ratio(Context& c,uint32_t controller,bool& present){
    return ai_front_ratio_team(c,rd<uint32_t>(c,controller+0x38cu)&1u,present);
}
// ---------- 第 18 版：相持判定（建筑类单位的出击时机） ----------
// 每帧记录每队所面对的对方前线位置（场宽比例）。对方有单位在场、且前线位置连续 STABLE_FRAMES 帧的波动
// （最大值 − 最小值）不超过 STABLE_SPAN 时视为相持（用户确认：5 秒、6% 场宽）。出建筑类后该队计时重新开始。
constexpr uint32_t STABLE_FRAMES=150u;constexpr float STABLE_SPAN=0.06f;
struct FrontTrack{float lo,hi;uint32_t since;bool present;};
FrontTrack front_track[2];uint32_t lab_frame;
void front_observe(Context& c){                                 // operator_update 每帧调用
    ++lab_frame;
    if(!enabled(c,FLAG_AI_TIER))return;
    for(uint32_t team=0;team<2u;++team){
        bool present=false;
        float v=ai_front_ratio_team(c,team,present);
        FrontTrack& t=front_track[team];
        if(!present){t=FrontTrack{v,v,lab_frame,false};continue;}
        float lo=std::min(t.lo,v),hi=std::max(t.hi,v);
        if(!t.present || hi-lo>STABLE_SPAN)t=FrontTrack{v,v,lab_frame,true};
        else{t.lo=lo;t.hi=hi;}
    }
}
bool front_stable(uint32_t team,uint32_t extra){               // extra：段位反应延迟（帧）
    const FrontTrack& t=front_track[team&1u];
    return t.present && lab_frame-t.since>=STABLE_FRAMES+extra;
}
float ai_field_power(Context& c,uint32_t team){
    // 队伍单位状态 +0xc8（AI 战力）之和，不含据点。原生的同类合计包含据点，据点战力随据点等级大幅变化，
    // 双方据点等级不同时（LAB 常见）合计差额由据点主导，因此此处排除 getKyotenUnit。
    uint32_t manager=0,unit=0,base=0;float sum=0.0f;
    guest_call(c,OBJECT_MANAGER_GET_INSTANCE,0,0,0,0,nullptr,0,&manager);
    guest_call(c,0x101df341u,manager,team,0,0,nullptr,0,&base);   // getKyotenUnit(team, 0)
    guest_call(c,0x101df318u,manager,team,0,0,nullptr,0,&unit);   // getTeamUnitList(team, 0)
    uint32_t first=unit;
    for(int guard=0;unit && guard<4096;++guard){
        uint32_t status=unit+0x128u+rd<uint32_t>(c,unit+0x300u)*0xecu;
        if(unit!=base)sum+=float(int32_t(rd<uint32_t>(c,status+0xc8u)));
        uint32_t link=rd<uint32_t>(c,unit+0x120u);
        unit=link?link-0x11cu:0u;
        if(unit==first)break;                                    // 队伍单位链表为环形（原生遍历回到首个单位即结束）
    }
    return sum;
}
// 第 20 版：统一压力判定（出兵选择、AP 饱和出兵、场上投资共用）。对方前线推进到距己方据点 ALERT_BASE+ALERT_SPAN·s
// 场宽以内（段位越高越早察觉：SILVER 0.35、GOLD 约 0.39、PREDATOR 0.45；0.45+0.15s 的试验值使 PREDATOR 在敌方越过中线时即判定压力，投资据点受阻），或对方不含据点的场上战力高出 PRESSURE_DEFICIT。
// 第 12–19 版为 front ≤ 0.4−0.2s、deficit > 400+1200s，高段位警戒距离反而更短（PREDATOR 0.2 场宽），敌方压到据点前仍在积累 AP。
constexpr float ALERT_BASE=0.35f,ALERT_SPAN=0.10f,PRESSURE_DEFICIT=400.0f;
bool ai_pressure(Context& c,uint32_t controller,float s){
    bool present=false;
    float front=ai_front_ratio(c,controller,present);
    if(present && front<=ALERT_BASE+ALERT_SPAN*s)return true;
    uint32_t team=rd<uint32_t>(c,controller+0x38cu)&1u;
    return ai_field_power(c,team^1u)-ai_field_power(c,team)>PRESSURE_DEFICIT;
}
void ai_stat(Context& c,uint32_t side,uint32_t field,uint32_t value,bool add=true){
    uint32_t a=AI_STATS_BASE+side*0x20u+field*4u;wr<uint32_t>(c,a,add?rd<uint32_t>(c,a)+value:value);
}
// 统计（每方 +0x540/+0x560，8 字）：0 出兵、1 积累帧、2 建筑类暂缓、3 改选、4 压力出兵、5 最近出兵 UnitID、
// 6 出兵 AP 合计、7 建筑类出兵；+0x580/+0x584 建筑类出兵时对方前线比例的最大值（×1000），+0x588/+0x58c 对方无单位时的建筑类出兵；
// +0x5a0 起每方 10 字：各槽出兵次数（我方 +0x5a0、敌方 +0x5c8）；+0x5f0 起每方 2 字：进入策略 B 的次数、B 下出兵次数。
void ai_record_deploy(Context& c,uint32_t controller,uint32_t slot){
    uint32_t side=controller==rd<uint32_t>(c,ENEMY_CONTROLLER)?1u:0u;
    uint32_t info=controller+0xcu+slot*0x1cu,uid=rd<uint32_t>(c,info+0x10u);
    ai_stat(c,side,0,1);
    ai_stat(c,side,5,uid,false);
    if(slot<10u){uint32_t a=AI_STATS_BASE+0x60u+side*0x28u+slot*4u;wr<uint32_t>(c,a,rd<uint32_t>(c,a)+1u);}   // 各槽出兵次数
    ai_stat(c,side,6,rd<uint32_t>(c,info));
    if(ai_is_builder(c,uid)){
        ai_stat(c,side,7,1);
        front_track[rd<uint32_t>(c,controller+0x38cu)&1u].since=lab_frame;   // 相持计时重新开始
        bool present=false;
        uint32_t ratio=uint32_t(std::max(ai_front_ratio(c,controller,present),0.0f)*1000.0f);
        uint32_t a=AI_STATS_BASE+0x40u+side*4u;
        if(ratio>rd<uint32_t>(c,a))wr<uint32_t>(c,a,ratio);
        if(!present)wr<uint32_t>(c,a+8u,rd<uint32_t>(c,a+8u)+1u);
    }
}
// ---------- 第 18 版：AP 饱和时按 AP 从高到低轮流出兵（全部段位，含 SILVER） ----------
// 用户要求：据点等级 9–10 时不再等待最高 AP 单位的冷却，以最高 AP 单位为主，其冷却中则出第二高、第三高……，
// 使 AP 接近饱和时持续输出；任何等级 AP 已满（≥98% 上限）时同样如此，避免 AP 回复浪费。
// 候选为已冷却、AP 足够、非建筑类的单位，按出兵 AP 从高到低（同 AP 按单位价值）。最高 AP 单位冷却中时，出次一级
// 单位后余下的 AP 须仍够买最高 AP 单位，否则等待；AP 已满时直接出，且可升据点时优先升据点。
// 返回槽位；−2 为等待；−1 为不适用（交由后续逻辑）。
// 段位差异（用户要求：不同段位的反应时刻不同）：各规则的反应延迟从该段位的反应等待区间（块 +4/+8）随机抽取，
// AP 已满须持续该延迟后才开始轮流出兵（低段位察觉更慢，AP 浪费更多）。
constexpr uint32_t SAT_LEVEL=9u;
uint32_t ai_react(Context& c,uint32_t tier){
    uint32_t low=rd<uint32_t>(c,tier+4u),high=rd<uint32_t>(c,tier+8u);
    if(high<low)high=low;
    return low+ai_random()%(high-low+1u);
}
struct Saturation{uint32_t controller,full_since,full_react;};
Saturation sat_state[2];
constexpr uint32_t TACTIC_STATS=H+0x6f0u;                         // 每方 2 字：前置规则出兵（压前线、骚扰、相持建筑）、饱和出兵
bool forced_deploy;
int32_t ai_saturated_pick(Context& c,uint32_t controller,uint32_t tier){
    uint32_t level=rd<uint32_t>(c,controller+0x3fcu),max_ap=0;
    guest_call(c,P_MAX_AP,controller,level,0,0,nullptr,0,&max_ap);
    float ap=rd<float>(c,controller+0x404u);
    bool full=ap>=float(int32_t(max_ap))*0.98f;
    Saturation& st=sat_state[controller==rd<uint32_t>(c,ENEMY_CONTROLLER)?1u:0u];
    if(st.controller!=controller)st=Saturation{controller,0u,0u};
    if(!full)st.full_since=0u;
    else if(!st.full_since){st.full_since=lab_frame?lab_frame:1u;st.full_react=ai_react(c,tier);}
    bool full_seen=full && lab_frame-st.full_since>=st.full_react;   // 察觉 AP 已满需要反应时间
    if(level<SAT_LEVEL && !full_seen)return -1;
    int32_t best=-1,best_cost=-1,top=-1,top_cost=-1;float best_value=-1.0f;
    uint32_t slots=rd<uint32_t>(c,controller+0x390u);
    for(uint32_t slot=0;slot<slots && slot<32u;++slot){
        uint32_t info=controller+0xcu+slot*0x1cu;
        int32_t cost=int32_t(rd<uint32_t>(c,info));
        if(!rd<uint8_t>(c,info+0xcu) || cost<=0 || cost>int32_t(max_ap))continue;
        const UnitValue& v=ai_unit_value(c,rd<uint32_t>(c,info+0x10u),rd<uint32_t>(c,info+0x14u));
        if(v.builder)continue;
        if(cost>top_cost){top_cost=cost;top=int32_t(slot);}
        uint32_t ready=0;guest_call(c,P_IS_UNIT_CREATE,controller,slot,0,0,nullptr,0,&ready);
        if((ready&0xffu) && (cost>best_cost || (cost==best_cost && v.value>best_value))){best=int32_t(slot);best_cost=cost;best_value=v.value;}
    }
    if(best<0)return -1;
    if(full_seen){
        uint32_t maxed=0,can=0;guest_call(c,KYOTEN_LEVEL_MAX,controller,0,0,0,nullptr,0,&maxed);
        if(!(maxed&0xffu))guest_call(c,P_IS_LEVELUP,controller,0,0,0,nullptr,0,&can);
        return (can&0xffu)?-1:best;                              // AP 已满且可升据点：交由据点升级（ai_levelup_query 放行）
    }
    if(best_cost>=top_cost)return best;                          // 最高 AP 单位可出
    // 最高 AP 单位冷却中：只用超出其价格的 AP 出次一级单位，保留够买它的 AP（第 18 版测试：不保留时满级后
    // 反复出最便宜单位，AP 攒不起来）；余量不足时等待 AP 回复。
    // 压力下（第 20 版）不再保留 AP，直接出已就绪单位中 AP 最高者。
    if(ai_pressure(c,controller,float(std::min(rd<uint32_t>(c,tier+20u),100u))/100.0f))return best;
    return ap-float(best_cost)>=float(top_cost)?best:-2;
}
void tactic_stat(Context& c,uint32_t controller,uint32_t field){
    uint32_t a=TACTIC_STATS+(controller==rd<uint32_t>(c,ENEMY_CONTROLLER)?8u:0u)+field*4u;wr<uint32_t>(c,a,rd<uint32_t>(c,a)+1u);
}
Block old_ai_choose;
void ai_choose(Context& c){                                    // 0x1cc40e：r4 控制器，r5 原生选择的槽位
    uint32_t controller=c.r[4],tier=ai_tier(c,controller);
    if(forced_deploy){                                           // auto_deploy 的前置规则已选定槽位
        forced_deploy=false;
        if(tier)ai_record_deploy(c,controller,c.r[5]);
        old_ai_choose(c);return;
    }
    uint32_t smart=tier?rd<uint32_t>(c,tier+20u):0u;
    if(tier){
        int32_t sat=ai_saturated_pick(c,controller,tier);
        if(sat==-2){c.pc=DECISION_EXIT;return;}
        if(sat>=0){
            uint32_t side=controller==rd<uint32_t>(c,ENEMY_CONTROLLER)?1u:0u;
            ai_saving[side]=0;
            if(uint32_t(sat)!=c.r[5])ai_stat(c,side,3,1);
            tactic_stat(c,controller,1);
            ai_record_deploy(c,controller,uint32_t(sat));
            c.r[5]=uint32_t(sat);
            old_ai_choose(c);return;
        }
    }
    if(!smart){
        if(tier)ai_record_deploy(c,controller,c.r[5]);           // 原生选择（理解度 0）同样统计，供对照
        old_ai_choose(c);return;
    }
    float s=std::min(float(smart),100.0f)/100.0f;
    uint32_t side=controller==rd<uint32_t>(c,ENEMY_CONTROLLER)?1u:0u;
    if(ai_saving_controller[side]!=controller){ai_saving_controller[side]=controller;ai_saving[side]=0;ai_hoard[side]=ai_random()&1u;}   // 新的一场
    bool hoard=ai_hoard[side]!=0u;
    uint32_t level=rd<uint32_t>(c,controller+0x3fcu),max_ap=0;
    guest_call(c,P_MAX_AP,controller,level,0,0,nullptr,0,&max_ap);
    bool present=false;
    float front=ai_front_ratio(c,controller,present);
    uint32_t team=rd<uint32_t>(c,controller+0x38cu)&1u;
    bool pressure=ai_pressure(c,controller,s);
    bool builders_ok=present && front<=0.5f;
    int32_t target=-1,affordable=-1;float best_target=-1.0f,best_affordable=-1.0f;
    int32_t target_cost=0,affordable_cost=0;
    int32_t lookahead=int32_t((hoard?900.0f:90.0f)*s);           // 冷却在 3s（B：30s）秒内结束的单位也作为积累目标
    float ap=rd<float>(c,controller+0x404u);
    uint32_t slots=rd<uint32_t>(c,controller+0x390u);
    for(uint32_t slot=0;slot<slots && slot<32u;++slot){
        uint32_t info=controller+0xcu+slot*0x1cu;
        int32_t cost=int32_t(rd<uint32_t>(c,info));
        if(!rd<uint8_t>(c,info+0xcu) || int32_t(rd<uint32_t>(c,info+0x18u))>lookahead || cost<=0 || cost>int32_t(max_ap))continue;
        const UnitValue& v=ai_unit_value(c,rd<uint32_t>(c,info+0x10u),rd<uint32_t>(c,info+0x14u));
        if(v.builder && !builders_ok){ai_stat(c,side,2,1);continue;}
        float u=float(int32_t(ai_random()%2001u)-1000)/1000.0f;
        float rank=v.value/std::pow(float(cost),1.0f-0.75f*s)*(1.0f+0.6f*(1.0f-s)*u);
        if(rank>best_target){best_target=rank;target=int32_t(slot);target_cost=cost;}
        uint32_t ready=0;guest_call(c,P_IS_UNIT_CREATE,controller,slot,0,0,nullptr,0,&ready);
        if((ready&0xffu) && rank>best_affordable){best_affordable=rank;affordable=int32_t(slot);affordable_cost=cost;}
    }
    int32_t chosen=-1;
    if(target>=0){
        uint32_t ready=0;guest_call(c,P_IS_UNIT_CREATE,controller,uint32_t(target),0,0,nullptr,0,&ready);
        if(ready&0xffu)chosen=target;
        else if(pressure || ai_saving[side]>=uint32_t((hoard?900.0f:450.0f)*s))chosen=affordable;
        else if(!hoard && affordable>=0 && affordable!=target && ap-float(affordable_cost)>=float(target_cost)*(1.0f+s))chosen=affordable;   // A：余量足够时动用
    }else chosen=affordable;
    if(chosen<0){                                                // 积累 AP：本帧不出兵，也不设等待
        ++ai_saving[side];ai_stat(c,side,1,1);
        c.pc=DECISION_EXIT;return;
    }
    ai_saving[side]=0;
    if(uint32_t(chosen)!=c.r[5])ai_stat(c,side,3,1);
    if(pressure)ai_stat(c,side,4,1);
    ai_record_deploy(c,controller,uint32_t(chosen));
    if(hoard){uint32_t a=AI_STATS_BASE+0xb0u+side*8u;wr<uint32_t>(c,a+4u,rd<uint32_t>(c,a+4u)+1u);}   // B 下出兵
    ai_hoard[side]=ai_random()&1u;                                // 下一阶段重新抽取策略
    if(ai_hoard[side]){uint32_t a=AI_STATS_BASE+0xb0u+side*8u;wr<uint32_t>(c,a,rd<uint32_t>(c,a)+1u);}   // 进入 B 的次数
    c.r[5]=uint32_t(chosen);
    old_ai_choose(c);
}
// ---------- 第 13 版：场上投资升级据点 ----------
// 达到开局据点目标后，r20 只在“AP 已满且无可出单位”时放行 AI 的据点升级，积累与冷却使两者几乎不同时成立，
// AI 停在目标等级。第 13 版：己方场上存活单位（不含据点与召唤单位）的 AP 价格合计 F ≥ k × 本级升级费用
// （controller+1024）连续 D 帧后，AP 足够即升级据点，不足时暂停出兵保留 AP，最长 L 帧；压力下照常出兵。
// 超时后须再出一次兵才重新触发；F < 0.7 × 阈值时退出。
// 停滞兜底（用户要求：不得因等待触发而停滞）：达到开局目标后据点等级 S 帧未变化时，不论 F 均进入投资，
// 且不设暂停上限，保留 AP 直至可升级（压力下照常出兵）；本级升级费用超过 AP 上限时不触发。
// 段位块 +24 为 k×100（0 关闭），+28 为 L（位 0–11）| D（位 12–19）| S/10（位 20–31）。停滞触发次数：+0x770 起每方 1 字。
// 单位来源：BattleObjectManager::createUnit 成功出口（0x1df440，r4 新单位）按调用者区分：返回地址（sp+52）为
// 0x1c9683（BattleController::onEventUnitCreate，卡组出兵）或 0x1de213（BattleObject::createChildObject，召唤与变身，
// 父对象为调用者的 r4，保存在 sp+24）；其他来源（弹头车等）不计入。AP 取己方卡组中同一 UnitID（单位 +0x128）的出兵费用。
// 子单位在 300 帧内父单位消失、
// 且父单位只生成过这一个子单位时视为变身（伞兵落地、工兵建成等），继承父单位的出兵 AP；其余为召唤，不计入。
// 宿主每场开战时递增头部 +0x700，钩子据此清空记录。统计：+0x710 起每方 8 字（触发、投资升级、超时、
// 暂停帧、最近 F、最近阈值、压力跳过、据点等级），+0x750 起每方 4 字（出兵记录、变身继承、召唤、当前计入单位数）。
constexpr uint32_t INVEST_SERIAL=H+0x700u,INVEST_STATS=H+0x710u,ORIGIN_STATS=H+0x750u;
enum:uint8_t{ORIGIN_DEPLOY=1,ORIGIN_PENDING=2,ORIGIN_INHERIT=3,ORIGIN_SUMMON=4};
// 单位对象来自原生对象池，指针会被后续单位复用；记录以指针 + 生成序号区分，新单位生成时同一指针的旧记录失效。
// uid 为计价用的 UnitID：出兵单位为自身（生成时 +0x62 尚未写入，首次使用时读取），变身后的单位为最初出兵单位；
// AP 已转给变身后单位的父记录置为 UID_TRANSFERRED。
struct Origin{uint32_t unit,gen,parent_gen,born,dead_since,uid;uint16_t children;uint8_t team,kind,alive;};
Origin origins[512];uint32_t origin_count,origin_serial=0xffffffffu,origin_gen,ai_frame;
struct Invest{uint32_t controller,since,hold_start,level,level_since;bool active,need_deploy,forced;};
Invest invest_state[2];
constexpr uint32_t UID_TRANSFERRED=0xffffffffu;
uint32_t origin_uid(Context& c,Origin& o){
    if(!o.uid && o.kind==ORIGIN_DEPLOY && o.unit)o.uid=rd<uint32_t>(c,o.unit+0x128u);
    return o.uid;
}
Origin* origin_of(uint32_t unit){
    if(!unit)return nullptr;
    for(uint32_t i=origin_count;i-->0;)if(origins[i].unit==unit)return &origins[i];
    return nullptr;
}
Origin* origin_gen_find(uint32_t gen){
    for(uint32_t i=origin_count;i-->0;)if(origins[i].gen==gen)return &origins[i];
    return nullptr;
}
bool origin_tracking(Context& c){
    return enabled(c,FLAG_AI_TIER) && (rd<uint32_t>(c,AI_TIER_BASE+24u) || rd<uint32_t>(c,AI_TIER_BASE+0x20u+24u));
}
void origin_reset(Context& c){
    uint32_t serial=rd<uint32_t>(c,INVEST_SERIAL);
    if(serial==origin_serial)return;
    origin_serial=serial;origin_count=0;ai_frame=0;
    for(Invest& s:invest_state)s=Invest{};
}
void origin_retire(uint32_t unit){                              // 该指针上的旧单位已不存在
    for(uint32_t i=0;i<origin_count;++i)if(origins[i].unit==unit){
        origins[i].unit=0;origins[i].alive=0;
        if(!origins[i].dead_since)origins[i].dead_since=ai_frame?ai_frame:1u;
    }
}
Origin* origin_add(Context& c,uint32_t unit,uint32_t team,uint8_t kind,uint32_t uid){
    if(origin_count>=512u){                                       // 移除已消失较久的记录；仍满时丢弃最旧的
        uint32_t n=0;
        for(uint32_t i=0;i<origin_count;++i)if(origins[i].alive || ai_frame-origins[i].dead_since<=400u)origins[n++]=origins[i];
        if(n>=512u){for(uint32_t i=1;i<n;++i)origins[i-1]=origins[i];n=511u;}
        origin_count=n;
    }
    origin_retire(unit);
    Origin& o=origins[origin_count++];
    o=Origin{unit,++origin_gen,0u,ai_frame,0u,uid,0,uint8_t(team&1u),kind,1};
    if(kind==ORIGIN_DEPLOY || kind==ORIGIN_SUMMON){uint32_t a=ORIGIN_STATS+o.team*0x10u+(kind==ORIGIN_DEPLOY?0u:8u);wr<uint32_t>(c,a,rd<uint32_t>(c,a)+1u);}
    return &o;
}
Block old_unit_created;
void unit_created(Context& c){                                 // BattleObjectManager::createUnit 成功出口：r4 新单位，r6 队伍
    if(origin_tracking(c)){
        origin_reset(c);
        uint32_t unit=c.r[4],team=c.r[6]&1u;
        uint32_t ret=rd<uint32_t>(c,c.r[13]+52u)&~1u,caller_r4=rd<uint32_t>(c,c.r[13]+24u);
        origin_retire(unit);
        if(ret==0x101c9682u){
            origin_add(c,unit,team,ORIGIN_DEPLOY,0u);
            invest_state[team==(rd<uint32_t>(c,ENEMY_TEAM)&1u)?1u:0u].need_deploy=false;   // 手动或 AI 出兵后可再次触发
        }else if(ret==0x101de212u){
            Origin* p=origin_of(caller_r4);
            bool counted=p && (p->kind==ORIGIN_DEPLOY || p->kind==ORIGIN_INHERIT);
            uint32_t parent_gen=p?p->gen:0u,uid=p?origin_uid(c,*p):0u;
            Origin* o=origin_add(c,unit,team,counted?ORIGIN_PENDING:ORIGIN_SUMMON,counted?uid:0u);
            if(counted){
                o->parent_gen=parent_gen;
                if(Origin* q=origin_gen_find(parent_gen))++q->children;   // origin_add 可能整理了数组，按序号重新查找
                else o->kind=ORIGIN_SUMMON;
            }
        }
    }
    old_unit_created(c);
}
template<class F> void team_units(Context& c,uint32_t team,F visit){
    uint32_t manager=0,unit=0,base=0;
    guest_call(c,OBJECT_MANAGER_GET_INSTANCE,0,0,0,0,nullptr,0,&manager);
    guest_call(c,0x101df341u,manager,team,0,0,nullptr,0,&base);
    guest_call(c,0x101df318u,manager,team,0,0,nullptr,0,&unit);
    uint32_t first=unit;
    for(int guard=0;unit && guard<4096;++guard){
        if(unit!=base)visit(unit);
        uint32_t link=rd<uint32_t>(c,unit+0x120u);
        unit=link?link-0x11cu:0u;
        if(unit==first)break;
    }
}
void origin_observe(Context& c){                               // 每帧：标记存活并判定子单位为变身或召唤
    if(!origin_tracking(c))return;
    origin_reset(c);
    ++ai_frame;
    for(uint32_t i=0;i<origin_count;++i)origins[i].alive=0;
    for(uint32_t team=0;team<2u;++team)
        team_units(c,team,[&](uint32_t unit){if(Origin* o=origin_of(unit))o->alive=1;});
    for(uint32_t i=0;i<origin_count;++i){
        Origin& o=origins[i];
        if(!o.alive && !o.dead_since)o.dead_since=ai_frame;
        if(o.kind!=ORIGIN_PENDING)continue;
        Origin* p=origin_gen_find(o.parent_gen);
        if(!(p && p->alive)){
            o.kind=(p && p->children==1u)?ORIGIN_INHERIT:ORIGIN_SUMMON;
            if(o.kind==ORIGIN_INHERIT)p->uid=UID_TRANSFERRED;     // 投入的 AP 只由变身后的单位计入一次
        }else if(ai_frame-o.born>300u)o.kind=ORIGIN_SUMMON;
        if(o.kind!=ORIGIN_PENDING){uint32_t a=ORIGIN_STATS+o.team*0x10u+(o.kind==ORIGIN_INHERIT?4u:8u);wr<uint32_t>(c,a,rd<uint32_t>(c,a)+1u);}
    }
}
uint32_t field_invested_ap(Context& c,uint32_t controller,uint32_t team){   // 场上存活、计入的单位的出兵 AP 合计
    uint32_t sum=0,count=0,slots=rd<uint32_t>(c,controller+0x390u);
    team_units(c,team,[&](uint32_t unit){
        if(int32_t(rd<uint32_t>(c,unit+776u))<=0)return;
        Origin* o=origin_of(unit);
        if(!o || !(o->kind==ORIGIN_DEPLOY || o->kind==ORIGIN_INHERIT))return;
        uint32_t uid=origin_uid(c,*o);
        if(!uid || uid==UID_TRANSFERRED)return;
        for(uint32_t slot=0;slot<slots && slot<32u;++slot){
            uint32_t info=controller+0xcu+slot*0x1cu;
            if(rd<uint32_t>(c,info+0x10u)==uid){sum+=rd<uint32_t>(c,info);++count;break;}
        }
    });
    wr<uint32_t>(c,ORIGIN_STATS+team*0x10u+12u,count);
    return sum;
}
bool ai_invest(Context& c,uint32_t controller){                // true：本帧已处理（升级或保留 AP），退出决策
    uint32_t tier=ai_tier(c,controller);
    if(!tier)return false;
    uint32_t k=rd<uint32_t>(c,tier+24u),timing=rd<uint32_t>(c,tier+28u);
    int32_t target=int32_t(rd<uint32_t>(c,tier+12u));
    if(!k || target<0)return false;
    uint32_t side=controller==rd<uint32_t>(c,ENEMY_CONTROLLER)?1u:0u;
    Invest& st=invest_state[side];
    if(st.controller!=controller)st=Invest{controller,0u,0u,0xffffffffu,0u,false,false,false};
    uint32_t level=rd<uint32_t>(c,controller+0x3fcu);
    uint32_t stats=INVEST_STATS+side*0x20u;
    wr<uint32_t>(c,stats+28u,level);
    if(level!=st.level){st.level=level;st.level_since=ai_frame;st.forced=false;}
    if(int32_t(level)<target){st.active=false;st.since=0;return false;}
    uint32_t maxed=0;guest_call(c,KYOTEN_LEVEL_MAX,controller,0,0,0,nullptr,0,&maxed);
    if(maxed&0xffu){st.active=false;return false;}
    uint32_t team=rd<uint32_t>(c,controller+0x38cu)&1u;
    float field=float(field_invested_ap(c,controller,team));
    float threshold=float(int32_t(rd<uint32_t>(c,controller+1024u)))*float(k)/100.0f;
    wr<uint32_t>(c,stats+16u,uint32_t(field));wr<uint32_t>(c,stats+20u,uint32_t(threshold));
    uint32_t hold=timing&0xfffu,delay=(timing>>12)&0xffu,stall=(timing>>20)*10u;
    if(!st.forced && stall && ai_frame-st.level_since>=stall){
        uint32_t max_ap=0;guest_call(c,P_MAX_AP,controller,level,0,0,nullptr,0,&max_ap);
        if(int32_t(rd<uint32_t>(c,controller+1024u))<=int32_t(max_ap)){
            st.forced=true;st.active=true;st.hold_start=ai_frame;st.need_deploy=false;
            uint32_t a=INVEST_SERIAL+0x70u+side*4u;wr<uint32_t>(c,a,rd<uint32_t>(c,a)+1u);
        }
    }
    if(st.forced){
        st.active=true;                                            // 停滞兜底：保持投资直至升级
    }else if(st.active){
        if(field<threshold*0.7f){st.active=false;st.since=0;}
    }else{
        if(st.need_deploy || field<threshold){st.since=0;return false;}
        if(!st.since)st.since=ai_frame;
        if(ai_frame-st.since<delay)return false;                  // 反应延迟：低段位“慢半拍”
        st.active=true;st.hold_start=ai_frame;
        wr<uint32_t>(c,stats,rd<uint32_t>(c,stats)+1u);
    }
    if(!st.active)return false;
    float s=float(std::min(rd<uint32_t>(c,tier+20u),100u))/100.0f;
    bool present=false;
    float front=ai_front_ratio(c,controller,present);
    if(ai_pressure(c,controller,s)){                              // 压力：照常出兵，暂停计时不累计
        st.hold_start=ai_frame;wr<uint32_t>(c,stats+24u,rd<uint32_t>(c,stats+24u)+1u);
        return false;
    }
    uint32_t can=0;guest_call(c,P_IS_LEVELUP,controller,0,0,0,nullptr,0,&can);
    if(can&0xffu){
        guest_call(c,rd<uint32_t>(c,rd<uint32_t>(c,controller)+0xa8u),controller);   // 与原生 0x1cc464 相同的虚函数
        wr<uint32_t>(c,stats+4u,rd<uint32_t>(c,stats+4u)+1u);
        st.active=false;st.since=0;st.forced=false;
        return true;
    }
    if(!st.forced && ai_frame-st.hold_start>=hold){                             // 超时：恢复出兵，出兵后才可再次触发
        st.active=false;st.since=0;st.need_deploy=true;
        wr<uint32_t>(c,stats+8u,rd<uint32_t>(c,stats+8u)+1u);
        return false;
    }
    wr<uint32_t>(c,stats+12u,rd<uint32_t>(c,stats+12u)+1u);
    return true;
}
// ---------- 第 14 版：本地双人对战的结束演出（功能位 256） ----------
// BattleMain::changeScene（0x1d0b57，r1 = SceneType）在已建立的场景中按类型切换：1 MISSION START、
// 3 MISSION COMPLETE（BattleStartAndCompleteEffectScene，效果类型非 0）、4 MISSION FAILED（BattleFailedEffectScene）。
// 原生演出以 P1（本地队伍）视角选择 3 或 4。双人对战中双方胜利都播放 MISSION COMPLETE（用户要求：动画与音效相同），
// 因此功能位开启时把 4 改为 3。替换次数记于头部 +0x780。
constexpr uint32_t FLAG_VERSUS=256u,VERSUS_COMPLETE_COUNT=H+0x780u;
Block old_change_scene;
void change_scene(Context& c){
    if(enabled(c,FLAG_VERSUS) && c.r[1]==4u){
        c.r[1]=3u;
        wr<uint32_t>(c,VERSUS_COMPLETE_COUNT,rd<uint32_t>(c,VERSUS_COMPLETE_COUNT)+1u);
    }
    old_change_scene(c);
}
// ---------- 第 15 版：双人对战选中格光标（原生绘制顺序，功能位 512） ----------
// drawUI 的出兵格循环（0x1d8700–0x1d8a80）以 GraphicsOpt::drawConv（0x10136985：r0 graphics、r1 Image、r2/r3 x/y、
// 栈 [转换项, 3 个浮点, 整数]）绘制格子：底板为 operator+200 转换表项 53/54/55（50×50），其后为单位头像（项 56–74），
// 费用牌为 createGrahics 按槽位预先画好价格数字的项 78–97（绿/红）及 77（OK!）、98（MAX）、107。
// r6 为槽位序号（drawUI 0x1d88b0 以其与按下格 operator+32 比较）。敌方半区绘制时 operator+188/+200 换入敌方图集与
// 转换表（swap_gfx），因此转换表基址按调用时的 operator+200 实时读取。
// 功能位开启时，若当前片段为出兵格（pass.cells）且该槽为本侧光标所在格，先画原生图块，再以相同位置与参数画
// 宿主建立的光标图块（头部 +0xa00）：底板后画光标框、费用牌后画光标费用牌，单位头像与数字随后由原生画在其上。
// 头部 +0xa00：+0 启用，+4/+8 P1/P2 光标槽，+0x10 起每侧 4 个 Image*（0 框、1 费用牌），
// +0x30 起每侧 4 个转换项（16 字节，至 +0xaf），+0xc0 BattlePlayerOperator 指针，+0xd0/+0xd4 命中计数（框、费用牌）。
constexpr uint32_t FLAG_VS_CURSOR=512u,VS_CUR=H+0xa00u,VS_CUR_HITS=H+0xad0u,G_DRAW_CONV=0x10136985u;
constexpr uint32_t SLOT_LOOP_BEGIN=0x101d8700u,SLOT_LOOP_END=0x101d8a80u;
// 诊断：头部 +0xb00 为 'DLOG' 时，把 drawConv 调用记入宿主分配的缓冲区（+0xb08 地址、+0xb0c 容量条数），
// 计数在 +0xb04；同一转换项指针只记一次。每条 32 字节：返回地址、Image*、x、y 位、转换项 16 字节。不改变绘制。
constexpr uint32_t DRAW_LOG=H+0xb00u,DRAW_LOG_MAGIC=0x474f4c44u;
// ---------- 第 16 版：VERSUS 子页面（借用原生 SHOP 子页面 scene28/state4 的图块替换） ----------
// 头部 +0xb40 为 'VSPG' 时启用（与 LAB 战斗头部无关，主菜单中由宿主写入）：+4 条目数（≤8），+0x10 起每条 32 字节：
// [匹配的转换项指针, 匹配的 Image*（0 为任意）, 新 Image*（0 为跳过绘制）, 匹配的 y 坐标位（0 为任意）, 新转换项 16 字节]。
// 历史活动浏览页（event_browser.py）在主菜单中使用同一表，以 y 坐标区分共用图块的第二、三行按钮。
// drawConv 的转换项为原生只读数据中的固定地址（SHOP 标题字、三张卡的插画与标签、底栏 LOCK），位置与参数沿用原生调用。
constexpr uint32_t VS_PAGE=H+0xb40u,VS_PAGE_MAGIC=0x47505356u;
Block old_draw_conv;
bool in_vs_cursor=false;
void draw_conv(Context& c){
    uint32_t lr=c.r[14]&~1u;
    if(rd<uint32_t>(c,VS_PAGE)==VS_PAGE_MAGIC){
        uint32_t conv=rd<uint32_t>(c,c.r[13]),n=std::min(rd<uint32_t>(c,VS_PAGE+4u),8u);
        for(uint32_t i=0;i<n;++i){
            uint32_t e=VS_PAGE+0x10u+i*32u,want=rd<uint32_t>(c,e+4u),wanty=rd<uint32_t>(c,e+12u);
            if(rd<uint32_t>(c,e)!=conv || (want && want!=c.r[1]) || (wanty && wanty!=c.r[3]))continue;
            uint32_t image=rd<uint32_t>(c,e+8u);
            if(!image){c.pc=c.r[14];return;}                        // 跳过绘制（底栏 LOCK）
            c.r[1]=image;wr<uint32_t>(c,c.r[13],e+16u);              // 新图像与新转换项（沿用原生位置与缩放）
            break;
        }
    }
    if(rd<uint32_t>(c,DRAW_LOG)==DRAW_LOG_MAGIC){
        uint32_t n=rd<uint32_t>(c,DRAW_LOG+4u),buf=rd<uint32_t>(c,DRAW_LOG+8u),cap=rd<uint32_t>(c,DRAW_LOG+12u);
        uint32_t conv=rd<uint32_t>(c,c.r[13]);
        bool seen=false;
        for(uint32_t i=0;i<n && !seen;++i)seen=rd<uint32_t>(c,buf+i*32u+28u)==conv && rd<uint32_t>(c,buf+i*32u+4u)==c.r[1];
        if(buf && n<cap && !seen){
            uint32_t e=buf+n*32u;
            wr<uint32_t>(c,e,lr);wr<uint32_t>(c,e+4u,c.r[1]);wr<uint32_t>(c,e+8u,c.r[2]);wr<uint32_t>(c,e+12u,c.r[3]);
            for(uint32_t k=0;k<12u;k+=4u)wr<uint32_t>(c,e+16u+k,conv?rd<uint32_t>(c,conv+k):0u);
            wr<uint32_t>(c,e+28u,conv);                                  // 转换项前 12 字节（矩形 x,y,w,h,锚点 x,y）与指针
            wr<uint32_t>(c,DRAW_LOG+4u,n+1u);
        }
    }
    if(!in_vs_cursor && lr>=SLOT_LOOP_BEGIN && lr<SLOT_LOOP_END && pass.active && pass.cells &&
       enabled(c,FLAG_VS_CURSOR) && rd<uint32_t>(c,VS_CUR)){
        uint32_t conv=rd<uint32_t>(c,c.r[13]);
        int part=-1;
        uint32_t op=rd<uint32_t>(c,VS_CUR+0xc0u);
        uint32_t base=op?rd<uint32_t>(c,op+200u):0u;                 // 当前（含敌方换入）转换表基址，项号 = 偏移/16
        if(base && conv>=base && (conv-base)%16u==0u){
            uint32_t index=(conv-base)/16u;
            if(index==53u||index==54u||index==55u)part=0;
            else if((index>=77u && index<=98u)||index==107u)part=1;
        }
        uint32_t side=enemy_pass?1u:0u;
        if(part>=0 && c.r[6]==rd<uint32_t>(c,VS_CUR+4u+side*4u)){
            uint32_t image=rd<uint32_t>(c,VS_CUR+0x10u+side*0x10u+uint32_t(part)*4u);
            uint32_t stack[5];
            for(uint32_t i=0;i<5u;++i)stack[i]=rd<uint32_t>(c,c.r[13]+i*4u);
            uint32_t r0=c.r[0],r1=c.r[1],r2=c.r[2],r3=c.r[3];
            in_vs_cursor=true;
            guest_call(c,G_DRAW_CONV,r0,r1,r2,r3,stack,5u);              // 原生图块
            if(image){
                stack[0]=VS_CUR+0x30u+side*0x40u+uint32_t(part)*16u;
                guest_call(c,G_DRAW_CONV,r0,image,r2,r3,stack,5u);       // 光标图块（同位置、同缩放）
                uint32_t a=VS_CUR_HITS+(part?4u:0u);wr<uint32_t>(c,a,rd<uint32_t>(c,a)+1u);
            }
            in_vs_cursor=false;
            c.pc=c.r[14];return;
        }
    }
    old_draw_conv(c);
}
// ---------- 第 18 版：出兵决策的前置规则（全部段位，含 SILVER；在开局据点目标与场上投资之前） ----------
// 1 相持建筑：对方前线相持（front_stable）时，有已冷却且 AP 足够的建筑类单位即先出（按单位价值最高者）。
// 2 压前线（据点等级 0–1）：己方场上单位（不含据点）少于 SCREEN_UNITS 时，随机出一个 CHEAP_AP 以内的单位，
//   先在前线建立屏障，使 AP 能稳定积累（用户要求）。
// 3 骚扰（据点等级 2–5）：每隔 HARASS_MIN–HARASS_MAX 帧随机出 1–2 个 CHEAP_AP 以内的单位（用户要求）。
// 第 20 版在 1 与 2 之间加入受压出兵（见函数内说明）。
// 选定后跳转原生出兵调用点 0x1cc40e（与本入口同一栈帧，r4 控制器、r5 槽位），出兵后原生设定反应等待。
constexpr int32_t CHEAP_AP=100;constexpr uint32_t SCREEN_UNITS=2u,HARASS_MIN=300u,HARASS_MAX=600u,P_DEPLOY_POINT=0x101cc40fu;
struct Tactic{uint32_t controller,next_harass,burst,stable_seen,stable_react;};
Tactic tactic_state[2];
int32_t ai_pre_rules(Context& c,uint32_t controller){
    uint32_t tier=ai_tier(c,controller);
    if(!tier)return -1;
    uint32_t side=controller==rd<uint32_t>(c,ENEMY_CONTROLLER)?1u:0u,team=rd<uint32_t>(c,controller+0x38cu)&1u;
    Tactic& st=tactic_state[side];
    if(st.controller!=controller)st=Tactic{controller,lab_frame+HARASS_MIN+ai_random()%(HARASS_MAX-HARASS_MIN+1u)+ai_react(c,tier),0u,0xffffffffu,0u};
    if(front_track[team].since!=st.stable_seen){st.stable_seen=front_track[team].since;st.stable_react=ai_react(c,tier);}   // 每段相持重新抽取反应延迟
    uint32_t level=rd<uint32_t>(c,controller+0x3fcu),slots=rd<uint32_t>(c,controller+0x390u);
    int32_t builder=-1,cheap[32],strongest=-1,strongest_cost=-1;uint32_t cheap_count=0;float builder_value=-1.0f;
    for(uint32_t slot=0;slot<slots && slot<32u;++slot){
        uint32_t info=controller+0xcu+slot*0x1cu;
        int32_t cost=int32_t(rd<uint32_t>(c,info));
        if(!rd<uint8_t>(c,info+0xcu) || cost<=0)continue;
        uint32_t ready=0;guest_call(c,P_IS_UNIT_CREATE,controller,slot,0,0,nullptr,0,&ready);
        if(!(ready&0xffu))continue;
        const UnitValue& v=ai_unit_value(c,rd<uint32_t>(c,info+0x10u),rd<uint32_t>(c,info+0x14u));
        if(v.builder){if(v.value>builder_value){builder_value=v.value;builder=int32_t(slot);}}
        else{
            if(cost>strongest_cost){strongest_cost=cost;strongest=int32_t(slot);}
            if(cost<=CHEAP_AP)cheap[cheap_count++]=int32_t(slot);
        }
    }
    if(builder>=0 && front_stable(team,st.stable_react))return builder;
    // 第 20 版受压出兵：压力下直接出已就绪单位中 AP 最高者，优先于积累 AP、开局据点目标与场上投资。
    // 依据：原生“己方场上不足 4 个单位时不出远程单位”使受压时就绪的远程单位全部被跳过，AP 积累至数千而不出兵，
    // 最终最高 AP 单位单独出场被围杀（第 20 版隔离测试：GOLD 受压 49 秒未出兵，期间 6–9 个槽位已就绪）。
    if(strongest>=0 && ai_pressure(c,controller,float(std::min(rd<uint32_t>(c,tier+20u),100u))/100.0f)){
        return strongest;
    }
    if(!cheap_count)return -1;
    int32_t pick=cheap[ai_random()%cheap_count];
    if(level<=1u){
        uint32_t units=0;
        team_units(c,team,[&](uint32_t unit){if(int32_t(rd<uint32_t>(c,unit+776u))>0)++units;});
        return units<SCREEN_UNITS?pick:-1;
    }
    if(level<=5u && (st.burst || lab_frame>=st.next_harass)){
        if(!st.burst)st.burst=1u+(ai_random()&1u);
        if(!--st.burst)st.next_harass=lab_frame+HARASS_MIN+ai_random()%(HARASS_MAX-HARASS_MIN+1u)+ai_react(c,tier);
        return pick;
    }
    return -1;
}
void auto_deploy(Context& c){                                  // 0x1cc070：绝招检查结束，进入出兵决策
    if(enabled(c,FLAG_AUTO_SPLIT) && (auto_disabled(c,c.r[4])&1u)){c.pc=DECISION_EXIT;return;}
    int32_t pre=ai_pre_rules(c,c.r[4]);
    if(pre>=0){
        tactic_stat(c,c.r[4],0);
        forced_deploy=true;c.r[5]=uint32_t(pre);c.pc=P_DEPLOY_POINT;return;
    }
    if(ai_opening(c,c.r[4])){c.pc=DECISION_EXIT;return;}
    if(ai_invest(c,c.r[4])){c.pc=DECISION_EXIT;return;}
    old_auto_deploy(c);
}
// ---------- T8 支援：弹头车出击按钮的可选效果（功能位 32） ----------
// BattleControllerPlayerBase::actionMetasuraHou（0x1cc760）：充能（控制器+1036）满时清零并调用
// BattleController::actionMetasuraHou 发射弹头车。按钮、按键与 AI 均经此入口。头部 +0x34：低字节我方、次字节敌方
// 的支援选项；0 为原版弹头车，其余选项在充能满时同样清零充能，执行效果后不发射弹头车。新增选项在 apply_support 中扩展。
//   1：本方除据点外所有存活单位 HP 回满（当前 HP 单位+776 ← 最大 HP 单位+772）。
//   2：本方所有单位绝招立即可再次释放（绝招倒计时 单位+800 大于 0 时置 0；isSpAttack 在其为 0 时成立）。
constexpr uint32_t FLAG_SUPPORT=32u,SUPPORT_OPTIONS=H+0x34u,SUPPORT_LAST=H+0x38u;
constexpr uint32_t IS_USE_SLUG=0x101cbdc0u,GET_TEAM_UNITS=0x101df318u,GET_BASE_UNIT=0x101c9764u;
void apply_support(Context& c,uint32_t controller,uint32_t option){
    uint32_t manager=0,unit=0,base=0;
    guest_call(c,OBJECT_MANAGER_GET_INSTANCE,0,0,0,0,nullptr,0,&manager);
    guest_call(c,GET_BASE_UNIT,controller,0,0,0,nullptr,0,&base);
    guest_call(c,GET_TEAM_UNITS,manager,rd<uint32_t>(c,controller+908u),0,0,nullptr,0,&unit);
    uint32_t first=unit;
    for(int guard=0;unit && guard<4096;++guard){
        if(unit!=base){
            if(option==1u && int32_t(rd<uint32_t>(c,unit+776u))>0)wr<uint32_t>(c,unit+776u,rd<uint32_t>(c,unit+772u));
            if(option==2u && int32_t(rd<uint32_t>(c,unit+800u))>0)wr<uint32_t>(c,unit+800u,0u);
        }
        uint32_t link=rd<uint32_t>(c,unit+0x120u);
        unit=link?link-0x11cu:0u;
        if(unit==first)break;                                    // 队伍单位链表为环形（原生遍历回到首个单位即结束）
    }
}
Block old_slug_action;
void slug_action(Context& c){
    if(enabled(c,FLAG_SUPPORT)){
        uint32_t controller=c.r[0];
        uint32_t options=rd<uint32_t>(c,SUPPORT_OPTIONS);
        uint32_t option=controller==rd<uint32_t>(c,ENEMY_CONTROLLER)?(options>>8)&0xffu:options&0xffu;
        if(option){
            uint32_t ready=0;
            guest_call(c,IS_USE_SLUG,controller,0,0,0,nullptr,0,&ready);
            if(ready){
                wr<uint32_t>(c,controller+1036u,0u);
                apply_support(c,controller,option);
                wr<uint32_t>(c,SUPPORT_LAST,rd<uint32_t>(c,SUPPORT_LAST)+1u);   // 宿主据此给出提示
            }
            c.pc=c.r[14];return;
        }
    }
    old_slug_action(c);
}
Block old_ap_bar;
void ap_bar_entry(Context& c){
    if(pass.active && pass.no_apbar){c.pc=c.r[14];return;}
    old_ap_bar(c);
}
void install_ui_hooks(){
    old_slug_action=find_block(0x101cc761u);register_block(0x101cc761u,slug_action);
    old_auto_query=find_block(0x101cba35u);register_block(0x101cba35u,auto_query);
    old_auto_slug=find_block(0x101cc019u);register_block(0x101cc019u,auto_slug);
    old_auto_special=find_block(0x101cc04fu);register_block(0x101cc04fu,auto_special);
    old_auto_deploy=find_block(0x101cc071u);register_block(0x101cc071u,auto_deploy);
    old_unit_created=find_block(0x101df441u);register_block(0x101df441u,unit_created);
    old_change_scene=find_block(0x101d0b57u);register_block(0x101d0b57u,change_scene);
    old_draw_conv=find_block(0x10136985u);register_block(0x10136985u,draw_conv);
    old_operator_update=find_block(0x101d6ae5u);register_block(0x101d6ae5u,operator_update);
    old_target_update=find_block(TARGET_UPDATE|1u);register_block(TARGET_UPDATE|1u,target_update);
    old_banner_begin=find_block(0x101d932fu);register_block(0x101d932fu,banner_begin);
    old_banner_end=find_block(0x101d950fu);register_block(0x101d950fu,banner_end);
    old_scene_slug=find_block(0x101d502fu);register_block(0x101d502fu,scene_slug);
    old_fever=find_block(0x101d5063u);register_block(0x101d5063u,scene_fever);
    old_levelup=find_block(0x101d5173u);register_block(0x101d5173u,scene_levelup);
    old_base_dead=find_block(0x101d5dfdu);register_block(0x101d5dfdu,scene_base_dead);
    old_ap_bar=find_block(DRAW_AP_BAR|1u);register_block(DRAW_AP_BAR|1u,ap_bar_entry);
    old_coin_draw=find_block(0x101d6881u);register_block(0x101d6881u,coin_draw);
    old_drawui_entry=find_block(0x101d7ca9u);register_block(0x101d7ca9u,drawui_entry);
    DrawHook<G_DRAW_S>::old=find_block(G_DRAW_S);register_block(G_DRAW_S,DrawHook<G_DRAW_S>::run);
    DrawHook<G_DRAW>::old=find_block(G_DRAW);register_block(G_DRAW,DrawHook<G_DRAW>::run);
    old_fill=find_block(G_FILL);register_block(G_FILL,fill_hook);
    old_setclip=find_block(G_SETCLIP);register_block(G_SETCLIP,setclip_hook);
    old_clearclip=find_block(G_CLEARCLIP);register_block(G_CLEARCLIP,clearclip_hook);
    install_touch_hooks();
}
// ---------- 第 10 版：LAB 音效通道扩展（功能位 64） ----------
// 原生音效（AppMain::Sound_RequestPlaySE 0x1c67e8 / Sound_PlaySE 0x1c7538 / Sound_PlaySE_2P 0x1c778c）每个端口
// 每帧只收 3 条请求（第 4 条按优先级淘汰），播放时在 3 个 CAudioPresenter（1P app+0x9b00、2P app+0x9b18）间
// 轮换，3 个都在播放时停止最早开始的一个。BattleObject::playSE 以对象 +0x70 选端口，双方各用一组。
// LAB 战斗中改为：每端口每帧最多 SE_QUEUE 条请求（同帧同 SoundID 合并），通道为原生 3 个加宿主建立的
// 宿主建立的扩展通道（每端口至多 SE_EXTRA 个，头部 +0x304 个数、+0x310/+0x330 指针），优先使用空闲通道，
// 全部占用时停止最早开始者。CMediaManager 有 32 个播放槽，通道只在播放期间登记（play/stop）；槽满时
// setAudioPresenter 不登记，该声音不混音，不影响其他通道。播放、音量、停止、缓冲释放沿用原生函数，扩展通道在
// Sound_Stop（标志 2）、Sound_ChangeVolumeSE、bufferReleaseCheck 中与原生通道同样处理。
constexpr uint32_t FLAG_SE_EXTEND=64u,SE_MAGIC_ADDR=H+0x300u,SE_MAGIC=0x4c534531u,SE_COUNT=H+0x304u;
constexpr uint32_t SE_EXTRA_BASE=H+0x310u,SE_STATS=H+0x380u;   // 统计：每端口 8 字（请求/合并/满队/播放/抢占/最大并发/当前并发/播放后未登记）
                                                                // +0x40 起每端口 6 字诊断（调用/有请求/未启用/音效关闭/设声失败/播放失败）
constexpr uint32_t SE_EXTRA=8u,SE_QUEUE=24u,SE_NATIVE=3u;
constexpr uint32_t P_PLAY=0x101382b8u,P_STOP=0x101383c4u,P_IS_PLAYEND=0x10138242u,P_SET_SOUND=0x10137fdcu;
constexpr uint32_t P_SET_PAUSE=0x10138176u,P_RELEASE=0x1013847au,P_SET_ATTRIBUTE=0x101381a4u;
struct SeRequest{uint32_t id,priority,value,pause;};
SeRequest se_queue[2][SE_QUEUE];uint32_t se_queued[2];
uint32_t se_seq_counter;
struct SeSeq{uint32_t presenter,seq;};SeSeq se_seq[2][SE_NATIVE+SE_EXTRA];
bool se_ready(Context& c){return rd<uint32_t>(c,SE_MAGIC_ADDR)==SE_MAGIC;}
bool se_active(Context& c){return se_ready(c) && enabled(c,FLAG_SE_EXTEND);}
uint32_t se_extra_count(Context& c){uint32_t n=rd<uint32_t>(c,SE_COUNT);return n<SE_EXTRA?n:SE_EXTRA;}
uint32_t se_extra(Context& c,uint32_t port,uint32_t i){return rd<uint32_t>(c,SE_EXTRA_BASE+port*0x20u+i*4u);}
void se_stat(Context& c,uint32_t port,uint32_t field,uint32_t add){
    uint32_t a=SE_STATS+port*0x20u+field*4u;wr<uint32_t>(c,a,rd<uint32_t>(c,a)+add);
}
Block old_se_request,old_se_play_1p,old_se_play_2p,old_se_stop,old_se_volume,old_se_release;
void se_request(Context& c){                                   // r0=app r1=SoundID r2=端口 r3=优先级，栈：值、暂停字节、可屏蔽
    uint32_t port=c.r[2];
    if(port>1u || !se_active(c)){old_se_request(c);return;}
    uint32_t app=c.r[0],id=c.r[1];
    c.pc=c.r[14];
    if(!id)return;
    if(rd<uint8_t>(c,c.r[13]+8u) && (rd<uint32_t>(c,app+0x97d8u)&1u))return;   // 原生请求屏蔽（胜负演出）
    se_stat(c,port,0,1);
    for(uint32_t i=0;i<se_queued[port];++i)if(se_queue[port][i].id==id){se_stat(c,port,1,1);return;}
    if(se_queued[port]>=SE_QUEUE){se_stat(c,port,2,1);return;}
    se_queue[port][se_queued[port]++]={id,c.r[3],rd<uint32_t>(c,c.r[13]),rd<uint32_t>(c,c.r[13]+4u)};
}
// CMediaManager 播放槽（manager+0x20 起 32 个，manager 为 presenter+0x78）：play 经 setAudioPresenter 追加一项
// 且不查重；stop 经 delAudioPresenter 只在找不到时才进入清除循环（0x138b10 找到即返回），实际不注销；
// 槽位由混音回调（0x138584）在通道已结束（+0）或已停止（+0x60）时清空。同一回调间隔内对同一通道
// stop 再 play 会留下重复项（该通道被混音两次），重复项累积占满 32 槽后，新 play 不再登记而无声。
// 每次 play 前按混音回调的同一规则清除已结束、已停止及重复的项（头部 +0x308 非 0 时跳过，供诊断对照）。
constexpr uint32_t SE_KEEP_SLOTS=H+0x308u,SLOT_COUNT=32u;
uint32_t se_slot_table(Context& c,uint32_t presenter){
    uint32_t manager=rd<uint32_t>(c,presenter+0x78u);
    return manager>=0x10000000u && manager<0x1ffff000u ? manager+0x20u : 0u;
}
void se_compact_slots(Context& c,uint32_t table){
    for(uint32_t i=0;i<SLOT_COUNT;++i){
        uint32_t p=rd<uint32_t>(c,table+i*4u);
        if(!p)continue;
        bool duplicate=false;
        for(uint32_t j=0;j<i && !duplicate;++j)duplicate=rd<uint32_t>(c,table+j*4u)==p;
        if(duplicate || rd<uint8_t>(c,p) || rd<uint8_t>(c,p+0x60u))wr<uint32_t>(c,table+i*4u,0u);
    }
}
bool se_slot_registered(Context& c,uint32_t table,uint32_t presenter){
    for(uint32_t i=0;i<SLOT_COUNT;++i)if(rd<uint32_t>(c,table+i*4u)==presenter)return true;
    return false;
}
uint32_t& se_seq_of(uint32_t port,uint32_t presenter){
    for(auto& s:se_seq[port])if(s.presenter==presenter)return s.seq;
    for(auto& s:se_seq[port])if(!s.presenter){s.presenter=presenter;s.seq=0;return s.seq;}
    static uint32_t spare;spare=0;return spare;
}
void se_debug(Context& c,uint32_t port,uint32_t field){
    uint32_t a=SE_STATS+0x40u+port*0x20u+field*4u;wr<uint32_t>(c,a,rd<uint32_t>(c,a)+1u);
}
void se_dispatch(Context& c,uint32_t port){
    uint32_t app=c.r[0],count=se_queued[port];se_queued[port]=0;
    se_debug(c,port,0);
    if(!count)return;
    se_debug(c,port,1);
    if(!se_active(c)){se_debug(c,port,2);return;}
    if(!rd<uint32_t>(c,app+0x3d60u)){se_debug(c,port,3);return;}   // 音效关闭：原生同样清空请求
    uint32_t pool[SE_NATIVE+SE_EXTRA],n=0;
    for(uint32_t i=0;i<SE_NATIVE;++i)pool[n++]=rd<uint32_t>(c,app+(port?0x9b18u:0x9b00u)+i*4u);
    for(uint32_t i=0,k=se_extra_count(c);i<k;++i)if(uint32_t p=se_extra(c,port,i))pool[n++]=p;
    // play(float) 的音量：原生两支都在 0x1c76f0 以 vcvt.f32.s32 把整数音量转为浮点。
    // 普通支为 app+0x9ae8（Sound_ChangeVolumeSE 写入的整数），淡出支（标志 0x40）为 (app+0x9ae8 × app+0xaf5c)>>8。
    uint32_t flags=rd<uint32_t>(c,app+0x9ae0u);
    int32_t level=int32_t(rd<uint32_t>(c,app+0x9ae8u));
    if(flags&0x40u)level=(level*int32_t(rd<uint32_t>(c,app+0xaf5cu)))>>8;
    uint32_t volume=fbits(float(level));
    for(uint32_t r=0;r<count;++r){
        const SeRequest& q=se_queue[port][r];
        uint32_t chosen=0,chosen_index=0,oldest=0xffffffffu;
        for(uint32_t i=0;i<n && !chosen;++i){
            if(!pool[i])continue;
            uint32_t ended=0;guest_call(c,P_IS_PLAYEND,pool[i],0,0,0,nullptr,0,&ended);
            if(ended&0xffu){chosen=pool[i];chosen_index=i;}
        }
        if(!chosen){
            for(uint32_t i=0;i<n;++i){
                uint32_t s=se_seq_of(port,pool[i]);
                if(pool[i] && s<oldest){oldest=s;chosen=pool[i];chosen_index=i;}
            }
            if(!chosen)continue;
            guest_call(c,P_STOP,chosen);
            se_stat(c,port,4,1);
        }
        uint32_t sound=rd<uint32_t>(c,app+(0x26ccu+q.id)*4u),ok=0;
        guest_call(c,P_SET_SOUND,chosen,sound,0,0,nullptr,0,&ok);
        if(!(ok&0xffu)){se_debug(c,port,4);continue;}
        float pause;std::memcpy(&pause,&q.pause,4);
        if(pause>0.0f)guest_call(c,P_SET_PAUSE,chosen,q.pause);
        uint32_t table=se_slot_table(c,chosen);
        if(table && !rd<uint32_t>(c,SE_KEEP_SLOTS))se_compact_slots(c,table);
        guest_call(c,P_PLAY,chosen,volume,0,0,nullptr,0,&ok);
        if(!(ok&0xffu)){se_debug(c,port,5);continue;}
        if(table && !se_slot_registered(c,table,chosen))se_stat(c,port,7,1);   // 统计第 8 字：播放后未登记（无声）
        se_seq_of(port,chosen)=++se_seq_counter;
        se_stat(c,port,3,1);
        if(chosen_index<SE_NATIVE){                            // 原生通道状态记录（与 Sound_PlaySE 写入的字段相同）
            uint32_t state=app+(port?0x9944u:0x982cu)+chosen_index*0x14u;
            wr<uint32_t>(c,state,q.id);wr<uint32_t>(c,state+4u,q.priority);wr<uint32_t>(c,state+8u,0xffffffffu);
            wr<uint32_t>(c,state+12u,q.pause);wr<uint32_t>(c,state+16u,se_seq_counter);
        }
    }
    uint32_t playing=0;
    for(uint32_t i=0;i<n;++i){
        uint32_t ended=1;if(pool[i])guest_call(c,P_IS_PLAYEND,pool[i],0,0,0,nullptr,0,&ended);
        if(!(ended&0xffu))++playing;
    }
    wr<uint32_t>(c,SE_STATS+port*0x20u+24u,playing);
    if(playing>rd<uint32_t>(c,SE_STATS+port*0x20u+20u))wr<uint32_t>(c,SE_STATS+port*0x20u+20u,playing);
}
void se_play_1p(Context& c){se_dispatch(c,0);old_se_play_1p(c);}
void se_play_2p(Context& c){se_dispatch(c,1);old_se_play_2p(c);}
template<typename F> void se_each_extra(Context& c,F f){
    if(!se_ready(c))return;
    for(uint32_t port=0;port<2;++port)for(uint32_t i=0,k=se_extra_count(c);i<k;++i)
        if(uint32_t p=se_extra(c,port,i))f(port,p);
}
void se_stop(Context& c){
    // Sound_Stop（0x1c7e08）：标志 2 停止 1P 音效通道并清空其请求（0x1c7ee6 起）。原生 Sound_Stop 没有处理
    // Sound_StopSE_2P 置的 0x200（该位置位后一直保留），2P 音效通道不经此处停止；扩展通道与原生一致。
    uint32_t flags=rd<uint32_t>(c,c.r[0]+0x9a0cu);
    if(flags&2u){
        se_queued[0]=0;
        se_each_extra(c,[&](uint32_t port,uint32_t p){if(!port)guest_call(c,P_STOP,p);});
    }
    old_se_stop(c);
}
void se_volume(Context& c){                                    // Sound_ChangeVolumeSE(app, 音量)：原生对 6 个音效通道设属性 4
    uint32_t value=c.r[1];
    se_each_extra(c,[&](uint32_t,uint32_t p){guest_call(c,P_SET_ATTRIBUTE,p,4u,value);});
    old_se_volume(c);
}
void se_release(Context& c){                                   // bufferReleaseCheck(app, CMediaSound)：释放前停止仍在使用该声音的通道
    uint32_t sound=c.r[1];
    if(sound)se_each_extra(c,[&](uint32_t,uint32_t p){guest_call(c,P_RELEASE,p,sound);});
    old_se_release(c);
}
void install_se_hooks(){
    old_se_request=find_block(0x101c67e9u);register_block(0x101c67e9u,se_request);
    old_se_play_1p=find_block(0x101c7539u);register_block(0x101c7539u,se_play_1p);
    old_se_play_2p=find_block(0x101c778du);register_block(0x101c778du,se_play_2p);
    old_se_stop=find_block(0x101c7e09u);register_block(0x101c7e09u,se_stop);
    old_se_volume=find_block(0x101c6d05u);register_block(0x101c6d05u,se_volume);
    old_se_release=find_block(0x101c833du);register_block(0x101c833du,se_release);
}
}
extern "C" __declspec(dllexport) uint32_t msd_lab_hooks_version(){return 20u;}
extern "C" __declspec(dllexport) void msd_enable_lab_hooks(){
    static bool installed=false;
    if(installed)return;
    installed=true;
    old_gauge_loop_exit=find_block(0x101d8f0bu);register_block(0x101d8f0bu,gauge_loop_exit);
    old_gauge_minimap=find_block(0x101d8e49u);register_block(0x101d8e49u,gauge_minimap);
    old_touch_entry=find_block(0x101d74a9u);register_block(0x101d74a9u,touch_entry);
    old_touch_list=find_block(0x101d764bu);register_block(0x101d764bu,touch_list);
    old_touch_loop_exit=find_block(0x101d76c9u);register_block(0x101d76c9u,touch_loop_exit);
    old_touch_activate=find_block(0x101d76d3u);register_block(0x101d76d3u,touch_activate);
    old_menu_layout=find_block(MENU_LAYOUT);register_block(MENU_LAYOUT,menu_layout);
    old_cockpit_push=find_block(0x101ff51bu);register_block(0x101ff51bu,cockpit_push);
    old_menu_button_draw=find_block(0x102003bdu);register_block(0x102003bdu,menu_button_draw);
    old_menu_button_tail=find_block(0x1020047bu);register_block(0x1020047bu,menu_button_tail);
    install_ui_hooks();
    install_se_hooks();
    old_ai_wait=find_block(0x101cbfcbu);register_block(0x101cbfcbu,ai_wait);
    old_ai_levelup_query=find_block(0x101cbd49u);register_block(0x101cbd49u,ai_levelup_query);
    old_ai_choose=find_block(0x101cc40fu);register_block(0x101cc40fu,ai_choose);
}
