// Additive native hooks; original game blocks remain the fallback for stock IDs.
#include "aot_runtime.h"
static constexpr uint32_t H=0x1ffee000u,MAGIC=0x434f4d32u,R=0x90u,U=1024u;
static uint32_t head(Context& c,uint32_t o){return rd<uint32_t>(c,H+o);}
static bool active(Context& c){return head(c,0)==MAGIC;}
static uint32_t record(Context& c,uint32_t uid){
 if(!active(c)||uid<U||uid>=head(c,12))return 0;
 return head(c,8)+(uid-U)*R;
}
static bool real_unit(Context& c,uint32_t uid){return uid<400u||record(c,uid)!=0;}
static uint32_t shop(Context& c,uint32_t sid){
 if(!active(c)||sid<512u||sid>=512u+head(c,4))return 0;
 return head(c,8)+(sid-512u)*R;
}
static uint32_t pack_record(Context& c){return active(c)?head(c,96):0u;}
static uint32_t pack_shop(Context& c,uint32_t sid){uint32_t p=pack_record(c);return p&&rd<uint16_t>(c,p)==sid?p:0u;}
static uint32_t pack_id(Context& c,uint32_t id){uint32_t p=pack_record(c);return p&&rd<uint32_t>(c,p+4u)==id?p:0u;}
static uint32_t pack_member(Context& c,uint32_t p,uint32_t index){
 return index<rd<uint32_t>(c,p+32u)?rd<uint32_t>(c,rd<uint32_t>(c,p+36u)+index*4u):0xffffffffu;
}
static bool pack_owned(Context& c,uint32_t p){
 for(uint32_t i=0;i<rd<uint32_t>(c,p+32u);++i){uint32_t r=record(c,pack_member(c,p,i));if(!r||rd<int32_t>(c,r+24u)<0)return false;}
 return true;
}
static void ret(Context& c,uint32_t v){c.r[0]=v;c.pc=c.r[14];}
static void dirty(Context& c){wr<uint32_t>(c,H+24,1u);}
static uint32_t total(Context& c){return active(c)?head(c,12):400u;}
static uint32_t images(Context& c){return active(c)?head(c,16):423u;}
static uint32_t stage_graphics(Context& c,uint32_t id,uint32_t original){
 if(!active(c)||id<138u||id>=138u+head(c,68))return original;
 return rd<uint32_t>(c,head(c,64)+(id-138u)*8u+4u);
}
static void extend_menu_icons(Context& c){
 // Menu initialization rebuilds these arrays when changing scenes.
 // Bind the additive action maps immediately before native menu drawing.
 if(!active(c)||!rd<uint32_t>(c,0x109600d4u+80u))return;
 wr<uint32_t>(c,0x1095fe9cu+80u,head(c,56));
 wr<uint32_t>(c,0x1095ffb8u+80u,head(c,60));
}
static uint32_t array_address(Context& c,uint32_t a,bool deck){
 if(!active(c))return a;uint32_t base=head(c,28)+(deck?0xb9d4u:0xb240u);
 if(a>=base&&a<base+head(c,40)*4u)return head(c,deck?36:32)+a-base;
 return a;
}
static uint32_t array_base(Context& c,uint32_t a,bool deck){
 if(active(c)&&a==head(c,28)+(deck?0xb9d4u:0xb240u))return head(c,deck?36:32);
 return a;
}
static uint32_t image_base(Context& c,uint32_t a){return active(c)&&a==0x10922f28u?head(c,20):a;}
// 有理数参数在原生等级插值完成后应用；既有单位的默认倍率为一。
static uint32_t combat_profile(Context& c,uint32_t uid){
 if(!record(c,uid)||head(c,80)!=1u||!head(c,76))return 0u;
 return head(c,76)+(uid-U)*48u;
}
static bool shop_unlocked(Context& c,uint32_t entry,uint32_t app){
 uint32_t table=head(c,92);if(!table)return true;
 uint32_t index=(entry-head(c,8))/R,reference=rd<uint32_t>(c,table+index*4u);
 if(reference==0xffffffffu)return true;
 if(reference>=512u)return false;
 return (rd<uint32_t>(c,app+0x4f20u+(reference/32u)*4u)&(1u<<(reference%32u)))!=0u;
}
static void scale_integer(Context& c,uint32_t address,uint32_t pair){
 uint32_t a=rd<uint32_t>(c,pair),b=rd<uint32_t>(c,pair+4u);if(a==b||!b)return;
 int64_t value=int64_t(rd<int32_t>(c,address))*a/b;
 wr<int32_t>(c,address,int32_t(std::max<int64_t>(INT32_MIN,std::min<int64_t>(INT32_MAX,value))));
}
static void apply_combat_status(Context& c,uint32_t out){
 uint32_t p=combat_profile(c,rd<uint32_t>(c,out));if(!p)return;
 scale_integer(c,out+0xcu,p);
 // 近距、普攻、绝招伤害分别为状态偏移 0x3c/0x58/0x74（词 15/22/29）；0x34（词 13）为被击毁时给予敌方的 AP，保持原值。
 for(uint32_t off:{0x3cu,0x58u,0x74u})scale_integer(c,out+off,p+8u);
 uint32_t a=rd<uint32_t>(c,p+16u),b=rd<uint32_t>(c,p+20u);
 if(a!=b&&b)wr<float>(c,out+0x14u,rd<float>(c,out+0x14u)*float(a)/float(b));
 // 近距、远距攻击判定与三类弹体的目的距离分别缩放。
 // 近距弹体目的距离为 0x4c（词 19）；0x40（词 16）为近距击退力，保持原值。
 for(uint32_t off:{0x18u,0x1cu,0x4cu,0x68u,0x84u})scale_integer(c,out+off,p+24u);
}
#define HOOK(NAME,PC,BODY) static Block old_##NAME;static void NAME(Context& c){BODY old_##NAME(c);}
// 抛物线弹体保持垂直轨迹，水平位移按射程倍率缩放。
// 受击滑行仅调整进入受击状态的载具水平位移。
static void scale_vehicle_motion(Context& c){
 uint32_t object=c.r[0],p=combat_profile(c,rd<uint32_t>(c,object+0x128u));if(!p)return;
 uint32_t type=rd<uint32_t>(c,object),pair=0u;
 if(type==head(c,84)&&rd<uint32_t>(c,object+0x7cu)==80u)pair=p+32u;
 else if(type==head(c,88))pair=p+40u;
 if(!pair)return;
 uint32_t a=rd<uint32_t>(c,pair),b=rd<uint32_t>(c,pair+4u);if(a==b||!b)return;
 for(uint32_t index:{1u,2u}){float x;std::memcpy(&x,&c.r[index],4);x=x*float(a)/float(b);std::memcpy(&c.r[index],&x,4);}
}
#include "unit_level_rules.inc"
HOOK(vehicle_motion,0x101dde11u, scale_vehicle_motion(c);)
HOOK(unitdata,0x101652a9u, uint32_t p=record(c,c.r[0]);if(p){ret(c,rd<uint32_t>(c,p+12));return;})
HOOK(unitname,0x101652d5u, uint32_t p=record(c,c.r[0]);if(p){ret(c,rd<uint32_t>(c,p+0x30u+std::min(c.r[1],10u)*4u));return;})
HOOK(unitinfo,0x101652e9u, uint32_t p=record(c,c.r[0]);if(p){ret(c,rd<uint32_t>(c,p+0x5cu+std::min(c.r[1],10u)*4u));return;})
HOOK(maxlevel,0x1016533bu, /* 原生世界开放数量与菜单数据共同决定免费基础上限。 */)
HOOK(getlevel,0x10167af1u, uint32_t p=record(c,c.r[1]);if(p){ret(c,rd<uint32_t>(c,p+0x8cu)?0xffffffffu:rd<uint32_t>(c,p+24));return;}if(active(c)&&c.r[1]>=400u){ret(c,0xffffffffu);return;})
HOOK(setlevel,0x10167b5bu, uint32_t p=record(c,c.r[1]);if(p){wr<uint32_t>(c,p+24,uint32_t(std::max(-1,std::min(39,int32_t(c.r[2])))));dirty(c);ret(c,0);return;}if(active(c)&&c.r[1]>=400u){ret(c,0u);return;})
HOOK(addlevel,0x10167b0fu, if(limit_player_increment(c))return;uint32_t p=record(c,c.r[1]);if(p){int v=std::max(-1,std::min(39,int32_t(rd<uint32_t>(c,p+24))+int32_t(c.r[2])));wr<uint32_t>(c,p+24,uint32_t(v));dirty(c);ret(c,uint32_t(v));return;}if(active(c)&&c.r[1]>=400u){ret(c,0xffffffffu);return;})
HOOK(getopen,0x10167ccbu, if(active(c)&&real_unit(c,c.r[1])){ret(c,reconcile_player_cap(c,c.r[0],c.r[1]));return;}if(active(c)&&c.r[1]>=400u){ret(c,40u);return;})
HOOK(isopen,0x10167cf3u, if(active(c)&&real_unit(c,c.r[1])){ret(c,reconcile_player_cap(c,c.r[0],c.r[1])<=39u);return;}if(active(c)&&c.r[1]>=400u){ret(c,0u);return;})
HOOK(setopen,0x10167d69u, if(active(c)&&real_unit(c,c.r[1]))c.r[2]=uint32_t(std::max(0,std::min(40,int32_t(c.r[2]))));uint32_t p=record(c,c.r[1]);if(p){wr<uint32_t>(c,p+28,c.r[2]);dirty(c);ret(c,0);return;}if(active(c)&&c.r[1]>=400u){ret(c,0u);return;})
HOOK(addopen,0x10167d1du, uint32_t p=record(c,c.r[1]);if(p){int32_t cap=std::max(0,std::min(40,int32_t(rd<uint32_t>(c,p+28u))+int32_t(c.r[2])));wr<uint32_t>(c,p+28u,uint32_t(cap));dirty(c);ret(c,uint32_t(cap));return;}if(active(c)&&c.r[1]>=400u){ret(c,40u);return;})
HOOK(gettime,0x10167bafu, uint32_t p=record(c,c.r[1]);if(p){ret(c,rd<uint32_t>(c,p+32));return;}if(active(c)&&c.r[1]>=400u){ret(c,0u);return;})
HOOK(settime,0x10167bcfu, uint32_t p=record(c,c.r[1]);if(p){wr<uint32_t>(c,p+32,c.r[2]);dirty(c);ret(c,0);return;}if(active(c)&&c.r[1]>=400u){ret(c,0u);return;})
HOOK(getdecktime,0x10167c0du, uint32_t p=record(c,c.r[1]);if(p){ret(c,rd<uint32_t>(c,p+0x88u));return;}if(active(c)&&c.r[1]>=400u){ret(c,0u);return;})
HOOK(setdecktime,0x10167c2bu, uint32_t p=record(c,c.r[1]);if(p){wr<uint32_t>(c,p+0x88u,c.r[2]);dirty(c);ret(c,0);return;}if(active(c)&&c.r[1]>=400u){ret(c,0u);return;})
HOOK(getnew,0x10167c67u, uint32_t p=record(c,c.r[1]);if(p){ret(c,rd<uint32_t>(c,p+36));return;}if(active(c)&&c.r[1]>=400u){ret(c,0u);return;})
HOOK(addnew,0x10167c7bu, uint32_t p=record(c,c.r[1]);if(p){wr<uint32_t>(c,p+36,1u);dirty(c);ret(c,0);return;}if(active(c)&&c.r[1]>=400u){ret(c,0u);return;})
HOOK(delnew,0x10167ca3u, uint32_t p=record(c,c.r[1]);if(p){wr<uint32_t>(c,p+36,0u);dirty(c);ret(c,0);return;}if(active(c)&&c.r[1]>=400u){ret(c,0u);return;})
HOOK(shopdata,0x101655c9u, uint32_t p=pack_shop(c,c.r[0]);if(p){ret(c,p);return;}p=shop(c,c.r[0]);if(p){ret(c,rd<uint32_t>(c,p+16));return;})
HOOK(shopprice,0x101656c5u, uint32_t p=pack_shop(c,c.r[0]);if(p){ret(c,uint32_t(rd<int16_t>(c,p+16u)));return;}p=shop(c,c.r[0]);if(p){ret(c,rd<uint32_t>(c,p+44));return;})
HOOK(shopmax,0x10165709u, if(shop(c,c.r[0])||pack_shop(c,c.r[0])){ret(c,1u);return;})
HOOK(shopstock,0x10165749u, uint32_t p=pack_shop(c,c.r[0]);if(p){ret(c,pack_owned(c,p));return;}p=shop(c,c.r[0]);if(p){ret(c,rd<uint32_t>(c,p+0x8cu)||int32_t(rd<uint32_t>(c,p+24))>=0?1u:0u);return;})
HOOK(soldout,0x10165835u, uint32_t p=pack_shop(c,c.r[0]);if(p){ret(c,pack_owned(c,p));return;}p=shop(c,c.r[0]);if(p){ret(c,rd<uint32_t>(c,p+0x8cu)||int32_t(rd<uint32_t>(c,p+24))>=0);return;})
HOOK(shopdisplay,0x1016595fu, if(shop(c,c.r[0])||pack_shop(c,c.r[0])){ret(c,0u);return;})
HOOK(shopdiscount,0x1016596bu, uint32_t p=pack_shop(c,c.r[0]);if(p){ret(c,uint32_t(rd<int16_t>(c,p+24u)));return;}if(shop(c,c.r[0])){ret(c,0u);return;})
HOOK(discount,0x1020b459u, if(record(c,c.r[1])){ret(c,0u);return;})
HOOK(shopavailable,0x102093f5u, if(pack_shop(c,c.r[1])){ret(c,rd<uint32_t>(c,c.r[0]+0xb890u)==2u);return;}uint32_t p=shop(c,c.r[1]);if(p){ret(c,!rd<uint32_t>(c,p+0x8cu)&&rd<uint32_t>(c,c.r[0]+0xb890u)==2u&&shop_unlocked(c,p,c.r[0]));return;})
HOOK(shopenable,0x10167d8du, if(pack_shop(c,c.r[1])){ret(c,1u);return;}uint32_t p=shop(c,c.r[1]);if(p){ret(c,!rd<uint32_t>(c,p+0x8cu)&&shop_unlocked(c,p,c.r[0]));return;})
HOOK(setshopenable,0x10167da1u, if(shop(c,c.r[1])||pack_shop(c,c.r[1])){ret(c,0u);return;})
HOOK(getshopnew,0x10167dc9u, if(pack_shop(c,c.r[1])){ret(c,0u);return;}uint32_t p=shop(c,c.r[1]);if(p){ret(c,rd<uint32_t>(c,p+40));return;})
HOOK(addshopnew,0x10167dddu, if(pack_shop(c,c.r[1])){ret(c,0u);return;}uint32_t p=shop(c,c.r[1]);if(p){wr<uint32_t>(c,p+40,1u);dirty(c);ret(c,0);return;})
HOOK(delshopnew,0x10167e05u, if(pack_shop(c,c.r[1])){ret(c,0u);return;}uint32_t p=shop(c,c.r[1]);if(p){wr<uint32_t>(c,p+40,0u);dirty(c);ret(c,0);return;})
HOOK(convertunit,0x101dc929u, uint32_t p=record(c,c.r[0]);if(p){ret(c,rd<uint32_t>(c,p+20));return;})
// Auxiliary sprites have image/sound resources and no BattleInfo unit row.
// Stop child traversal after preloading their resources, at the common path.
HOOK(aux_preload_status,0x101c945du, if(active(c)&&!real_unit(c,c.r[5])){c.pc=0x101c9483u;return;})
HOOK(image_index_boundary,0x101dcb09u, if(active(c)&&c.r[1]>=images(c)){ret(c,0u);return;})
HOOK(image_create_boundary,0x101dcbc5u, if(active(c)&&c.r[1]>=images(c)){ret(c,0u);return;})
HOOK(sound_read_boundary,0x101dcc65u, if(active(c)&&c.r[1]>=images(c)){ret(c,0u);return;})
HOOK(sound_release_boundary,0x101dccd9u, if(active(c)&&c.r[1]>=images(c)){ret(c,0u);return;})
HOOK(resource_uid_boundary,0x101dcba9u, if(active(c)&&c.r[1]>=423u&&!record(c,c.r[1])){ret(c,0u);return;})
HOOK(sound_uid_boundary,0x101dccc1u, if(active(c)&&c.r[1]>=423u&&!record(c,c.r[1])){ret(c,0u);return;})
HOOK(release_uid_boundary,0x101dcd31u, if(active(c)&&c.r[1]>=423u&&!record(c,c.r[1])){ret(c,0u);return;})
// Namespace gaps are excluded before table interpolation; empty statuses
// retain a -1 child sentinel and cannot become an accidental real unit.
HOOK(status_boundary,0x101cfbcdu, if(active(c)&&!real_unit(c,c.r[1])){uint32_t out=c.r[3];for(uint32_t i=0;i<0xecu;i+=4u)wr<uint32_t>(c,out+i,0u);wr<uint32_t>(c,out,c.r[1]);wr<uint32_t>(c,out+0xa0u,0xffffffffu);ret(c,0u);return;})
extern "C" __declspec(dllexport) uint32_t msd_community_unit_id_base(){return U;}
extern "C" __declspec(dllexport) uint32_t msd_community_combat_profile_version(){return 1u;}
extern "C" __declspec(dllexport) uint32_t msd_community_shop_gate_version(){return 1u;}
HOOK(create_params_boundary,0x101cfa99u, if(active(c)&&!real_unit(c,c.r[1])){for(uint32_t i=0;i<0x1cu;i+=4u)wr<uint32_t>(c,c.r[3]+i,0u);ret(c,0u);return;})
HOOK(real_unit_factory_boundary,0x101d1421u, if(active(c)&&!real_unit(c,c.r[2])){ret(c,0u);return;})
HOOK(pack_unit,0x101654b5u, uint32_t p=pack_id(c,c.r[0]);if(p){ret(c,pack_member(c,p,c.r[1]));return;})
static const int32_t pack_positions[7]={-50,0,50,-65,-25,15,55};
HOOK(pack_x,0x101654d1u, if(pack_id(c,c.r[0])){ret(c,c.r[1]<7u?uint32_t(pack_positions[c.r[1]]):0u);return;})
HOOK(pack_y,0x101654edu, if(pack_id(c,c.r[0])){ret(c,c.r[1]<3u?uint32_t(-30):0u);return;})
HOOK(pack_name,0x1016551du, uint32_t p=pack_id(c,c.r[0]);if(p){ret(c,rd<uint32_t>(c,p+40u+std::min(c.r[1],10u)*4u));return;})
HOOK(pack_info,0x10165509u, uint32_t p=pack_id(c,c.r[0]);if(p){ret(c,rd<uint32_t>(c,p+84u+std::min(c.r[1],10u)*4u));return;})
extern "C" __declspec(dllexport) uint32_t msd_community_unit_pack_version(){return 1u;}
// 伞兵落地时，原生动作固定生成 UnitID 45；社区映射保留其正规军身份。
HOOK(paratrooper_landing,0x101de225u, uint32_t uid=rd<uint32_t>(c,c.r[0]+0x128u);uint32_t p=record(c,uid);if(p&&rd<uint32_t>(c,p+4u)==160u&&c.r[1]==45u&&head(c,100)){uint32_t target=rd<uint32_t>(c,head(c,100)+(uid-U)*4u);if(target)c.r[1]=target;})
extern "C" __declspec(dllexport) uint32_t msd_community_paratrooper_landing_version(){return 1u;}
// 属性面板显示实际作战单位；其他调用保留购买与拥有状态的原生标识。
HOOK(menu_display_id,0x101652fdu, if(record(c,c.r[0])&&c.r[14]==0x101ecd31u&&head(c,104)){ret(c,rd<uint32_t>(c,head(c,104)+(c.r[0]-U)*4u));return;})
extern "C" __declspec(dllexport) uint32_t msd_community_display_status_version(){return 1u;}
// 地面木乃伊与虫群共享原生动画编号；本体击退恢复使用登记的独立槽。
HOOK(mummy_recovery,0x101de017u,
 if(active(c)&&c.r[1]==26u&&rd<uint32_t>(c,c.r[0])==head(c,84)&&head(c,108)){
  uint32_t uid=rd<uint32_t>(c,c.r[0]+0x128u);
  if(record(c,uid))c.r[1]=rd<uint32_t>(c,head(c,108)+(uid-U)*4u);
 })
// 修筑单位的浏览模式沿用原版初始化位置与完成箱体选择流程。
HOOK(mummy_viewer_setup,0x1020a665u,
 uint32_t p=record(c,c.r[4]);
 if(p&&rd<uint32_t>(c,p+4u)==77u&&head(c,104)&&rd<uint32_t>(c,head(c,104)+(c.r[4]-U)*4u)!=c.r[4]){
  wr<uint32_t>(c,c.r[5]+176u,300u);wr<uint32_t>(c,c.r[5]+180u,400u);
  c.pc=0x1020a9a7u;return;
 })
HOOK(mummy_viewer_child,0x1020a571u,
 uint32_t p=record(c,c.r[0]);if(p&&rd<uint32_t>(c,p+4u)==77u)c.r[0]=77u;
 )
HOOK(mummy_viewer_update,0x1020b0edu,
 uint32_t p=record(c,c.r[0]);if(p&&rd<uint32_t>(c,p+4u)==77u){
  uint32_t object=c.r[4];uint32_t state=rd<uint32_t>(c,object+0x7cu);
  if((state==10u||state==20u)&&rd<float>(c,object+0x8cu)<320.0f){
   wr<uint32_t>(c,object+0x80u,20u);wr<uint32_t>(c,object+0x84u,20u);
  }
  c.r[0]=77u;
 }
 )
HOOK(mummy_viewer_initial_state,0x1020ab2du,
 uint32_t object=rd<uint32_t>(c,c.r[7]+24u);
 if(object){uint32_t p=record(c,rd<uint32_t>(c,object+0x128u));
  if(p&&rd<uint32_t>(c,p+4u)==77u){wr<uint32_t>(c,object+0x80u,20u);wr<uint32_t>(c,object+0x84u,20u);}
 }
 )
extern "C" __declspec(dllexport) uint32_t msd_community_mummy_variant_version(){return 1u;}
// 敌军名单沿用原生等级与标志计算，社区身份由运行注册表确认。
HOOK(enemy_roster,0x101c9d07u,
 uint32_t row=rd<uint32_t>(c,c.r[3]+68u)+c.r[6]*c.r[5];
 uint32_t uid=rd<uint32_t>(c,row+4u);
 if(record(c,uid)){
  c.r[0]=c.r[4];c.r[3]=row;c.r[5]=add(c,c.r[5],1u,0u,true);
  c.r[1]=uid;c.r[2]=rd<uint32_t>(c,row+8u);c.r[3]=1u;nz(c,1u);
  c.r[2]=add(c,c.r[2],~1u,1u,true);c.r[14]=0x101c9d23u;c.pc=0x101c9b91u;return;
 })
HOOK(enemy_unit_enable,0x101c98fbu, if(record(c,c.r[1])){ret(c,1u);return;})
HOOK(enemy_special_policy,0x101c9da3u,
 uint32_t mission=rd<uint32_t>(c,c.r[4]+0x3acu);
 if(rd<uint32_t>(c,0x1ffec000u)==0x45585431u&&mission&&rd<uint32_t>(c,mission)>=1000000u)
  c.r[3]=rd<uint32_t>(c,0x1ffec014u)?1u:0u;
 )
// 独立音乐复用已核验的空闲音频槽，保持原生缓存边界。
HOOK(extension_music,0x101c6625u,
 if(c.r[1]==1031u&&rd<uint32_t>(c,0x1ffec000u)==0x45585431u){
  uint32_t bank=rd<uint32_t>(c,0x1ffec004u);if(bank){ret(c,bank);return;}
 })
HOOK(extension_mission,0x101d09fdu,
 if(rd<uint32_t>(c,0x1ffec000u)==0x45585431u&&c.r[1]>=1000000u){
  uint32_t base=rd<uint32_t>(c,0x1ffec00cu);uint32_t count=rd<uint32_t>(c,0x1ffec010u);
  uint32_t i=c.r[1]-1000000u;
  if(i<count&&rd<uint32_t>(c,base+i*120u)==c.r[1]){ret(c,base+i*120u);return;}
  ret(c,0u);return;
 })
extern "C" __declspec(dllexport) uint32_t msd_content_interface_version(){return 1u;}
// KT-21 喷火受击收尾与单次击退限制（第 112 字节头字段：每单位 8 词）。
// 词 0 标记（1 启用收尾，2 启用击退限制）；词 1 喷火在槽 10 内的起点 tick，词 2 喷火时长；词 3 收尾受击槽起点；词 4..7 收尾弹体动画。
static uint32_t flame_entry(Context& c,uint32_t uid){
 if(!record(c,uid)||!head(c,112))return 0u;
 uint32_t e=head(c,112)+(uid-U)*32u;return rd<uint32_t>(c,e)?e:0u;
}
struct FlameMark{uint32_t target,target_id,owner,count;};
static FlameMark flame_marks[1024];static uint32_t flame_mark_count=0;
struct FlameOwner{uint32_t owner,count;};
static FlameOwner flame_owners[128];static uint32_t flame_owner_count=0;
static uint32_t flame_owner_key(Context& c,uint32_t object){return uint32_t(rd<uint16_t>(c,object+0x62u))|((rd<uint32_t>(c,object+0x70u)&0xffu)<<16);}
static void flame_owner_store(uint32_t owner,uint32_t count){
 for(uint32_t i=0;i<flame_owner_count;++i)if(flame_owners[i].owner==owner){flame_owners[i].count=count;return;}
 if(flame_owner_count<128u)flame_owners[flame_owner_count++]={owner,count};
}
static bool flame_owner_count_of(uint32_t owner,uint32_t& count){
 for(uint32_t i=0;i<flame_owner_count;++i)if(flame_owners[i].owner==owner){count=flame_owners[i].count;return true;}
 return false;
}
// 原生 setAnimationID：喷火阶段转入受击动画 11 时，按已执行的喷火 tick 选择含收尾的受击槽。
static void flame_interrupt_select(Context& c){
 if(active(c)&&c.r[1]==11u&&rd<uint32_t>(c,c.r[0])==head(c,84)){
  uint32_t object=c.r[0],e=flame_entry(c,rd<uint32_t>(c,object+0x128u));
  if(e&&rd<uint32_t>(c,object+0x7cu)==80u&&rd<uint32_t>(c,object+0xc4u)==10u){
   uint32_t frames=rd<uint32_t>(c,rd<uint32_t>(c,object+0x5cu)+0x3cu);
   int32_t k=int32_t(frames)-1-int32_t(rd<uint32_t>(c,e+4u));
   int32_t span=int32_t(rd<uint32_t>(c,e+8u));
   if(k>=1&&k<span){uint32_t variant=k<=4?0u:k<=8?1u:k<=12?2u:k<span-5?3u:4u;c.r[1]=rd<uint32_t>(c,e+12u)+variant;}
  }
 }
}
HOOK(kt21_flame_interrupt,0x101de017u, flame_interrupt_select(c);)
// addBulletImpl：受击收尾槽发射的弹体改用登记的收尾动画、绝招参数组，命中与落地不切换动画（贯穿，动画结束后消失）。
static void flame_ending_bullet(Context& c){
 uint32_t owner=c.r[1];
 if(active(c)&&rd<uint32_t>(c,owner)==head(c,84)){
  uint32_t e=flame_entry(c,rd<uint32_t>(c,owner+0x128u));
  if(e){uint32_t animation=rd<uint32_t>(c,owner+0xc4u),base=rd<uint32_t>(c,e+12u);
   if(animation>=base&&animation<base+4u){
    uint32_t sp=c.r[13];
    wr<uint32_t>(c,sp+8u,50u);wr<uint32_t>(c,sp+0xcu,rd<uint32_t>(c,e+16u+(animation-base)*4u));
    wr<uint32_t>(c,sp+0x10u,0xfffffffeu);wr<uint32_t>(c,sp+0x14u,0xfffffffeu);
    flame_owner_store(flame_owner_key(c,owner),rd<uint32_t>(c,owner+0x324u));
   }
  }
 }
}
HOOK(kt21_flame_ending_bullet,0x1017d7fdu, flame_ending_bullet(c);)
// BattleUnit::damage 击退计量扣除处：同一次绝招的喷火对同一目标最多造成一次击退。
static void flame_knockback_limit(Context& c){
 if(active(c)){
  uint32_t attacker=c.r[5],target=c.r[4],vt=rd<uint32_t>(c,attacker);
  uint32_t e=flame_entry(c,rd<uint32_t>(c,attacker+0x128u));
  if(e&&(rd<uint32_t>(c,e)&2u)){
   uint32_t owner=flame_owner_key(c,attacker),count=0u;bool flame=false;
   if(vt==head(c,84)&&rd<uint32_t>(c,attacker+0x7cu)==50u){count=rd<uint32_t>(c,attacker+0x324u);flame_owner_store(owner,count);flame=true;}
   else if(vt==head(c,88)){
    uint32_t animation=rd<uint32_t>(c,attacker+0xc4u);
    for(uint32_t i=0;i<4u;++i)if(animation==rd<uint32_t>(c,e+16u+i*4u))flame=flame_owner_count_of(owner,count);
   }
   if(flame){
    uint32_t sp=c.r[13],target_id=flame_owner_key(c,target);bool seen=false;
    for(uint32_t i=0;i<flame_mark_count&&!seen;++i){const FlameMark& m=flame_marks[i];seen=m.target==target&&m.target_id==target_id&&m.owner==owner&&m.count==count;}
    int32_t gauge=int32_t(rd<uint32_t>(c,target+0x310u));
    // 已被本次绝招击退的目标：计量为正时不扣除；计量非正（原生每次受击均击退的单位）时保持计量为 1。
    if(seen)wr<int32_t>(c,sp+0x48u,gauge>0?0:gauge-1);
    else if(gauge-int32_t(rd<uint32_t>(c,sp+0x48u))<=0){
     if(flame_mark_count>=1024u)flame_mark_count=0u;
     flame_marks[flame_mark_count++]={target,target_id,owner,count};
    }
   }
  }
 }
}
HOOK(kt21_flame_knockback_limit,0x101e0b5du, flame_knockback_limit(c);)
// BattleObjectManager::initialize：战斗开始时清除上述记录。
HOOK(kt21_flame_battle_reset,0x101e019du, flame_mark_count=0u;flame_owner_count=0u;)
extern "C" __declspec(dllexport) uint32_t msd_community_flame_interrupt_version(){return 1u;}
// 地面绝招沿用 HeavyB 状态 50 的更新：动画与攻击等待后，每帧调用 actionMove(object,0)。
// 该流程保留脚本水平速度，并按原生规则处理坡地高度、阶差阻挡与下落。
HOOK(ground_special_update,0x10192571u,
 if(active(c)&&c.r[2]==50u&&head(c,116u)){
  uint32_t object=c.r[1];uint32_t uid=rd<uint32_t>(c,object+0x128u);
  if(record(c,uid)&&rd<uint32_t>(c,object)==head(c,84u)&&
     (rd<uint32_t>(c,head(c,116u)+(uid-U)*4u)&1u)){
   c.pc=0x1017a0adu;return;
  }
 }
)
extern "C" __declspec(dllexport) uint32_t msd_community_ground_special_version(){return 1u;}
// Generated block overrides and registration are emitted by the build script.
#include "community_blocks.inc"
