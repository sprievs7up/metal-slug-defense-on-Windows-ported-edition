// 玩家沿用原版世界开放判定及 20/25/30/35 级的持久化解锁阶段。
static uint32_t player_level_address(uint32_t app,uint32_t uid){
 return app+(uid<300u?0x3e28u:0x86a8u)+uid*2u;
}
static uint32_t player_cap_address(uint32_t app,uint32_t uid){
 return app+(uid<300u?0x68ccu:0x8edcu)+uid*2u;
}
static int32_t player_saved_level(Context& c,uint32_t app,uint32_t uid){
 uint32_t entry=record(c,uid);
 return entry?rd<int32_t>(c,entry+24u):rd<int16_t>(c,player_level_address(app,uid));
}
static uint32_t player_saved_cap(Context& c,uint32_t app,uint32_t uid){
 uint32_t entry=record(c,uid);
 int32_t value=entry?rd<int32_t>(c,entry+28u):rd<int16_t>(c,player_cap_address(app,uid));
 return uint32_t(std::max(20,std::min(40,value)));
}
static bool player_has_faction_core(Context& c,uint32_t app,uint32_t uid){
 // 运行数据库包含当前及后续有效登记单位的阵营。
 uint32_t info=rd<uint32_t>(c,0x101cfa94u)+0x101cfa84u+4u;
 uint32_t db=rd<uint32_t>(c,info),rows=rd<uint32_t>(c,db+4u);
 if(uid>=rd<uint32_t>(c,db+8u))return false;
 int32_t faction=rd<int32_t>(c,rows+uid*0x390u+0x378u);
 if(faction<0||faction>5)return false;
 uint32_t shops=rd<uint32_t>(c,0x101655d8u)+0x101655ceu+0x19cu;
 uint32_t item=rd<uint32_t>(c,shops+(289u+uint32_t(faction))*32u+4u);
 return rd<int16_t>(c,app+0x3decu+item*2u)>0;
}
static uint32_t player_open_cap(Context& c,uint32_t app,uint32_t uid){
 uint32_t cap=player_saved_cap(c,app,uid);
 // 核心提前或延后购买均适用；前置付费阶段继续保留。
 if(cap>=35u)return player_has_faction_core(c,app,uid)?40u:35u;
 return cap;
}
static uint32_t native_player_base_cap(Context& c,uint32_t uid){
 // 在独立寄存器上下文中执行原生只读查询，保留调用方寄存器及标志。
 Context query=c;
 constexpr uint32_t done=0x10000001u;
 query.r[0]=uid;query.r[14]=done;query.pc=0x1016533bu;query.error=0u;
 for(uint32_t i=0;i<20000u&&query.pc!=done&&!query.error;i++){
  Block block=find_block(query.pc);
  if(!block){query.error=2u;query.error_address=query.pc;break;}
  block(query);
 }
 if(query.error||query.pc!=done){c.error=query.error?query.error:2u;c.error_address=query.error_address;return 0u;}
 return query.r[0];
}
static uint32_t player_level_cap(Context& c,uint32_t app,uint32_t uid){
 uint32_t base=native_player_base_cap(c,uid);
 return base<=10u?base:std::max(base,player_open_cap(c,app,uid));
}
static uint32_t reconcile_player_cap(Context& c,uint32_t app,uint32_t uid){
 uint32_t cap=player_open_cap(c,app,uid),entry=record(c,uid);
 // 社区核心权限按登记身份协调，覆盖原生购买回调的 400 条记录边界。
 if(entry&&cap==40u&&rd<uint32_t>(c,entry+28u)!=40u){wr<uint32_t>(c,entry+28u,40u);dirty(c);}
 return cap;
}
static bool limit_player_increment(Context& c){
 if(!active(c)||!real_unit(c,c.r[1])||int32_t(c.r[2])<=0)return false;
 int32_t current=player_saved_level(c,c.r[0],c.r[1]);
 int32_t limit=int32_t(player_level_cap(c,c.r[0],c.r[1]))-1;
 if(current>=limit){ret(c,uint32_t(current));return true;}
 c.r[2]=uint32_t(std::min(int32_t(c.r[2]),limit-current));return false;
}
extern "C" __declspec(dllexport) uint32_t msd_player_level_rules_version(){return 1u;}
extern "C" __declspec(dllexport) uint32_t msd_world_level_rules_version(){return 1u;}
extern "C" __declspec(dllexport) uint32_t msd_native_level_rules_version(){return 1u;}
static Block old_world_upgrade,old_limit_break;
static void world_upgrade(Context& c){
 if(active(c)){
  uint32_t uid=rd<uint32_t>(c,c.r[5]+0x224u);
  if(real_unit(c,uid)){
   uint32_t limit=player_level_cap(c,c.r[4],uid);
   // 世界初期、无核心 Lv35 及最终 Lv40 边界均结束本次操作。
   if((limit<=10u||limit>=35u)&&int32_t(c.r[7])>=int32_t(limit)-1){c.pc=0x101ed2d1u;return;}
  }
 }
 old_world_upgrade(c);
}
static void limit_break(Context& c){
 if(active(c)&&real_unit(c,c.r[1])){
  uint32_t target=c.r[2]+5u;
  if(target>40u||(target>35u&&!player_has_faction_core(c,c.r[0],c.r[1]))){ret(c,0u);return;}
  c.r[2]=target;c.pc=0x10167d69u;return;
 }
 old_limit_break(c);
}
// 头目区域（世界 1–3 区域 12–15）救出率达到 100% 时，战斗结算 BattleEndGetPrisoner 在有头目、俘虏星期为 −1 时
// 调用 SetAreaEnableSaveData(世界, 区域, false) 写入全部关卡开放位，此后不依赖头目出现时段。
// RAID（raidInit，S 评级关卡不经战斗通关，雷達救出 1 名）在同一情形只置结果状态，头目转到下一区域后
// 该区域在地图上不再显示（AGENTS 第 300 节）。块 0x216cf2 只在救出率由未满变为 100% 时进入，r0–r3 在块内重新赋值：
// 条件成立时经 lr 进入原生 SetAreaEnableSaveData（含存档写入，不作嵌套调用），返回本块后继续原生流程。
static Block old_raid_complete;
static bool raid_enable_pending=false;
static void raid_complete(Context& c){
 if(raid_enable_pending){raid_enable_pending=false;old_raid_complete(c);return;}
 uint32_t app=c.r[5],world=rd<uint32_t>(c,app+0xb1ecu),area=rd<uint32_t>(c,app+0xb1f0u),boss=0u,prisoner=0u,weekday=0u;
 if(msd_guest_call(c,0x10165fe7u,world,area,0u,0u,&boss)&&boss!=0xffffffffu
  &&msd_guest_call(c,0x10165ffbu,world,area,0u,0u,&prisoner)
  &&msd_guest_call(c,0x10166905u,prisoner,0u,0u,0u,&weekday)&&weekday==0xffffffffu){
  raid_enable_pending=true;
  c.r[0]=world;c.r[1]=area;c.r[2]=0u;c.r[3]=0u;c.r[14]=0x10216cf3u;c.pc=0x10166545u;return;
 }
 old_raid_complete(c);
}
extern "C" __declspec(dllexport) uint32_t msd_raid_boss_area_rules_version(){return 1u;}
extern "C" __declspec(dllexport) void msd_enable_world_level_rules(){
 static bool installed=false;if(installed)return;installed=true;
 old_world_upgrade=find_block(0x101ed29fu);register_block(0x101ed29fu,world_upgrade);
 old_limit_break=find_block(0x101eeae5u);register_block(0x101eeae5u,limit_break);
 old_raid_complete=find_block(0x10216cf3u);register_block(0x10216cf3u,raid_complete);
}
