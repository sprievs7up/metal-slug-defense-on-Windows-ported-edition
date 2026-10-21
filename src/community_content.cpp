// Additive native hooks; original game blocks remain the fallback for stock IDs.
#include "aot_runtime.h"
#include "netplay.h"
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
// 已拥有单位紧凑列表的字节数（头部 +40 为单位个数，宿主取 8 的倍数，保持栈 8 字节对齐）。
// CreateUnitListCustum 与 InitDeckPanels 的栈上暂存表及列表清零、复制按此长度。
static uint32_t list_bytes(Context& c){return head(c,40)*4u;}
// BattleSpriteFactory::releaseUnusedResourcesAll 的栈上“使用中”标记表（每个图片索引 1 字节，清零长度为 images(c)）。
// 原覆盖块的帧固定为 516 字节（按 64 个社区单位）；帧长取不小于 images(c) 且 ≡4 mod 8（加 36 字节保存寄存器后 8 字节对齐）。
static uint32_t used_bytes(Context& c){return std::max(516u,(images(c)+3u)/8u*8u+4u);}
// 有理数参数在原生等级插值完成后应用；既有单位的默认倍率为一。
static uint32_t combat_profile(Context& c,uint32_t uid){
 // 原版单位（模组覆盖补丁，M3b）：头部 +148 为 400 个指针的表，被补丁修改的 UnitID 指向 48 字节倍率组，其余为 0。
 if(uid<400u){
  uint32_t table=active(c)&&head(c,80)==1u?head(c,148u):0u;
  return table?rd<uint32_t>(c,table+uid*4u):0u;
 }
 if(!record(c,uid)||head(c,80)!=1u||!head(c,76))return 0u;
 return head(c,76)+(uid-U)*48u;
}
extern "C" __declspec(dllexport) uint32_t msd_community_stock_profile_version(){return 1u;}
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
// 工兵生命（2026-10-20，用户设定）：头部 +176 为按生命计算的修筑类单位表（每项 3 个字：UnitID、百分比、下限），+180 为项数。
// 表中单位的生命 = max(下限, 修筑对象同等级生命 × 百分比 / 100)。修筑对象为状态 +0xa0（字 40；BattleAction_Kouhei::update 状态 50
// 以 getStatus(39) 调用 createChildObject，getStatus 的编号 n 对应字 n+1，如生命为编号 2、字 3），其生命经原生
// BattleInfo::getUnitStatus 取得（含该单位自身的倍率）。
// 不在表中的单位保持原生：生命 1，受击即撤退（“一击即跑”）。
bool msd_guest_call(Context& c,uint32_t fn,uint32_t a0,uint32_t a1,uint32_t a2,uint32_t a3,uint32_t* result);
static constexpr uint32_t ENG_INFO_INSTANCE=0x101cfa4du,ENG_UNIT_STATUS=0x101cfbcdu;
static uint32_t engineer_entry(Context& c,uint32_t uid){
 if(!active(c)||!head(c,176u))return 0u;
 uint32_t t=head(c,176u),n=head(c,180u);
 for(uint32_t i=0;i<n;++i)if(rd<uint32_t>(c,t+i*12u)==uid)return t+i*12u;
 return 0u;
}
static uint32_t engineer_depth=0u;   // 只在单次嵌套调用内非零
static void engineer_hp(Context& c,uint32_t out){
 uint32_t uid=rd<uint32_t>(c,out),e=engineer_entry(c,uid);if(!e||engineer_depth)return;
 uint32_t pct=rd<uint32_t>(c,e+4u),minimum=rd<uint32_t>(c,e+8u),child=rd<uint32_t>(c,out+0xa0u);int64_t hp=0;
 if(child&&child!=uid&&real_unit(c,child)){
  // 嵌套调用的状态缓冲区放在当前栈指针之下，调用期间栈指针移到缓冲区之下。
  uint32_t sp=c.r[13],buf=(sp-0x100u)&~7u,info=0u;++engineer_depth;c.r[13]=buf;
  if(msd_guest_call(c,ENG_INFO_INSTANCE,0u,0u,0u,0u,&info)&&info){
   for(uint32_t o=0;o<0xecu;o+=4u)wr<uint32_t>(c,buf+o,0u);
   if(msd_guest_call(c,ENG_UNIT_STATUS,info,child,rd<uint32_t>(c,out+8u),buf,nullptr))hp=int64_t(rd<int32_t>(c,buf+0xcu))*pct/100;
  }
  c.r[13]=sp;--engineer_depth;
 }
 wr<int32_t>(c,out+0xcu,int32_t(std::max<int64_t>(minimum,std::min<int64_t>(hp,INT32_MAX))));
}
static void apply_combat_status(Context& c,uint32_t out){
 uint32_t p=combat_profile(c,rd<uint32_t>(c,out));if(!p){engineer_hp(c,out);return;}
 scale_integer(c,out+0xcu,p);
 // 近距、普攻、绝招伤害分别为状态偏移 0x3c/0x58/0x74（词 15/22/29）；0x34（词 13）为被击毁时给予敌方的 AP，保持原值。
 for(uint32_t off:{0x3cu,0x58u,0x74u})scale_integer(c,out+off,p+8u);
 uint32_t a=rd<uint32_t>(c,p+16u),b=rd<uint32_t>(c,p+20u);
 if(a!=b&&b)wr<float>(c,out+0x14u,rd<float>(c,out+0x14u)*float(a)/float(b));
 // 近距、远距攻击判定与三类弹体的目的距离分别缩放。
 // 近距弹体目的距离为 0x4c（词 19）；0x40（词 16）为近距击退力，保持原值。
 for(uint32_t off:{0x18u,0x1cu,0x4cu,0x68u,0x84u})scale_integer(c,out+off,p+24u);
 engineer_hp(c,out);
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
// 获得时间（GetUnitGetTimeSaveData / SetUnitGetTimeSaveData，0x167b74 / 0x167b90）：原生对 UnitID ≥ 300 读写
// app+0x857c+4·uid，无上界（U1 开工说明附录 A.11）。社区单位改用头部 +160 的逐槽表（宿主随社区进度保存）。
static uint32_t get_time_slot(Context& c,uint32_t uid){uint32_t t=head(c,160);return t&&record(c,uid)?t+(uid-U)*4u:0u;}
HOOK(getgettime,0x10167b75u, uint32_t p=get_time_slot(c,c.r[1]);if(p){ret(c,rd<uint32_t>(c,p));return;}if(active(c)&&c.r[1]>=400u){ret(c,0u);return;})
HOOK(setgettime,0x10167b91u, uint32_t p=get_time_slot(c,c.r[1]);if(p){wr<uint32_t>(c,p,c.r[2]);dirty(c);ret(c,0);return;}if(active(c)&&c.r[1]>=400u){ret(c,0u);return;})
extern "C" __declspec(dllexport) uint32_t msd_community_get_time_version(){return 1u;}
// 原生单位商店勋章不足（PopupResultMenuShopBuyYes：0x20b686 起以 strShop 8 格式化“还差 %d 个 [deco0]\n是否前往购买画面”，
// 0x20b69a 起以 SetPopupYesNo 询问，“是”转勋章商店）。头部 +164 非零时（新单位界面的组合包页面，开工说明 D45）只保留第一行，
// 改走同函数模式 6 的 SetPopupOK 路径（0x20b66c：r4 为 AppMain、r5 为文字缓冲），不询问是否前往商店。
HOOK(shop_short_ok,0x1020b69bu, if(active(c)&&head(c,164u)){
 for(uint32_t i=0,s=c.r[5];i<512u;++i){uint8_t ch=rd<uint8_t>(c,s+i);if(!ch)break;
  if(ch=='\n'){uint32_t e=i;while(e&&rd<uint8_t>(c,s+e-1u)==' ')--e;wr<uint8_t>(c,s+e,0);break;}}
 c.pc=0x1020b66du;return;})
extern "C" __declspec(dllexport) uint32_t msd_community_shop_short_ok_version(){return 1u;}
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
// ---------- 生命分档单位（行为库 v3：hp_stage_animations 等，首批为 PVZ 僵尸；基准为原版 UnitID 313 BattleAction_ZombieBrain）----------
// 头部 +168：逐槽 ZSpec 指针表（0 为无，无此类单位时整表为 0）。ZSpec 为 33 个 32 位字（community_content.py zombie_spec；字 28–32 与标记 512–4096 见下文“2026-10-15 新 PvZ 单位”）：
//  0 标记（1 生命分档 2 无击退 4 防具受击音效 8 击毙音效 16 投出子单位 32 被投出的飞行单位 64 前方最近敌人 128 分档受击动作）；1 分档数 n（≤6）；
//  2..7 / 8..13 第 k 档阈值的分子 / 分母（生命 < 最大生命×分子/分母 时至少为第 k 档）；14 带过渡动作的档位位图；
//  15 狂暴档（0 为无）；16/17 狂暴移速倍率；18/19 狂暴伤害倍率；20/21 防具受击音效 SoundID；22 防具在第几档前存在；
//  23 击毙音效；24 投出子单位的档位；25 投出时刻（过渡动作的精灵帧计数）；26/27 被投出单位的起点前移与高度（世界坐标）。
// 第 k 档的动作槽为原生槽号 + 16k（只对槽 0–2、6、7、9–12、14；槽 14 为分档受击动作，原生 ZombieBrain 不使用）。逐实例状态只保存在客体对象中：当前动作号（+0xc4）、
// 状态副本序号（+0x300，狂暴为 1）与子对象指针（+0xfc，已投出），回滚快照随客体内存保存。
bool msd_guest_call(Context& c,uint32_t fn,uint32_t a0,uint32_t a1,uint32_t a2,uint32_t a3,uint32_t* result);
static constexpr uint32_t Z_STAGE_SLOTS=0x5ec7u;
static constexpr uint32_t Z_RESERVE_STATE=0x101dda28u,Z_PLAY_SE=0x101de1acu,Z_SUMMON_CHILD=0x101af74bu;
static const uint8_t Z_LEN[24]={2,2,2,2,2,1,3,5,2,2,3,5,5,2,3,1,1,2,2,3,3,1,5,2};
static uint32_t zspec(Context& c,uint32_t obj){
 if(!active(c)||!head(c,168u)||!obj||rd<uint32_t>(c,obj)!=head(c,84u))return 0u;
 uint32_t uid=rd<uint32_t>(c,obj+0x128u);if(!record(c,uid))return 0u;
 return rd<uint32_t>(c,head(c,168u)+(uid-U)*4u);
}
static uint32_t zw(Context& c,uint32_t s,uint32_t i){return rd<uint32_t>(c,s+i*4u);}
static int32_t z_stage_of_anim(Context& c,uint32_t s,int32_t anim){
 if(anim<0)return -1;uint32_t k=uint32_t(anim)/16u,slot=uint32_t(anim)%16u;
 if(k>zw(c,s,1)||!((Z_STAGE_SLOTS>>slot)&1u))return -1;return int32_t(k);
}
static uint32_t z_stage_of_hp(Context& c,uint32_t s,uint32_t obj){
 int64_t hp=int32_t(rd<uint32_t>(c,obj+0x308u)),mx=int32_t(rd<uint32_t>(c,obj+0x304u));uint32_t n=std::min(zw(c,s,1),6u),k=0u;
 for(uint32_t i=0;i<n;++i)if(hp*int64_t(zw(c,s,8u+i))<int64_t(zw(c,s,2u+i))*mx)k=i+1u;
 return k;
}
static uint32_t z_next_transition(Context& c,uint32_t s,uint32_t d){
 uint32_t n=std::min(zw(c,s,1),6u),m=zw(c,s,14);for(uint32_t k=d+1u;k<=n;++k)if((m>>k)&1u)return k;return n+1u;
}
// 动作请求的目标档位：不越过下一个带过渡动作的档位（过渡动作经状态 80 播放，槽 12 只由过渡请求）。
static uint32_t z_target(Context& c,uint32_t s,uint32_t obj,uint32_t slot){
 int32_t d=z_stage_of_anim(c,s,int32_t(rd<uint32_t>(c,obj+0xc4u)));if(d<0)d=0;
 uint32_t hp=z_stage_of_hp(c,s,obj),t=z_next_transition(c,s,uint32_t(d));
 if(slot==12u)return hp>=t?t:uint32_t(d);
 return std::min(hp,t-1u);
}
// 同一动作换到另一档：保留脚本位置与等待计数，显示帧取新脚本在该位置之前最后一条 op0（各档同一动作的命令结构相同）。
static void z_swap(Context& c,uint32_t obj,uint32_t anim,uint32_t target){
 uint32_t next=anim%16u+16u*target,sprite=rd<uint32_t>(c,obj+0x5cu);if(!sprite)return;
 uint32_t st=rd<uint32_t>(c,sprite+0x58u),desc=rd<uint32_t>(c,sprite+0x40u);if(!st||!desc)return;
 if(rd<uint32_t>(c,st+0xcu)!=anim||next>=rd<uint32_t>(c,desc+0x1cu))return;
 uint32_t script=rd<uint32_t>(c,rd<uint32_t>(c,desc+0x18u)+next*4u),index=rd<uint32_t>(c,st+0x10u),pos=0u;int32_t frame=-2;
 while(pos<index){uint32_t op=rd<uint32_t>(c,script+pos*4u);if(op>23u)return;if(op==0u)frame=int32_t(rd<uint32_t>(c,script+pos*4u+4u));pos+=Z_LEN[op];}
 if(pos!=index)return;
 wr<uint32_t>(c,st+0xcu,next);if(frame!=-2)wr<uint32_t>(c,st+8u,uint32_t(frame));wr<uint32_t>(c,obj+0xc4u,next);
}
// 狂暴：状态副本 1 复制副本 0，移速（词 5，浮点）与普攻、绝招伤害（词 22、29）按倍率缩放，切换序号（不改特殊攻击计量）。
static void z_apply_rage(Context& c,uint32_t s,uint32_t obj){
 for(uint32_t i=0;i<0xecu;i+=4u)wr<uint32_t>(c,obj+0x214u+i,rd<uint32_t>(c,obj+0x128u+i));
 uint32_t a=zw(c,s,16),b=zw(c,s,17);
 if(a&&b)wr<float>(c,obj+0x214u+0x14u,rd<float>(c,obj+0x214u+0x14u)*float(a)/float(b));
 a=zw(c,s,18);b=zw(c,s,19);
 if(a&&b)for(uint32_t w:{22u,29u}){int64_t v=int32_t(rd<uint32_t>(c,obj+0x214u+w*4u));wr<uint32_t>(c,obj+0x214u+w*4u,uint32_t(int32_t(v*a/b)));}
 wr<uint32_t>(c,obj+0x300u,1u);
}
// BattleAction_ZombieBrain::update 入口（r1 对象、r2 状态）：生命越过档位时，带过渡的档位预约状态 80，其余就地换档。
static void z_update(Context& c){
 uint32_t obj=c.r[1],state=c.r[2],s=zspec(c,obj);if(!s||!(zw(c,s,0)&1u))return;
 if(state>=100u||int32_t(rd<uint32_t>(c,obj+0x308u))<=0)return;
 int32_t anim=int32_t(rd<uint32_t>(c,obj+0xc4u)),d=z_stage_of_anim(c,s,anim);if(d<0)return;
 uint32_t rage=zw(c,s,15);
 if(rage&&uint32_t(d)>=rage&&!rd<uint32_t>(c,obj+0x300u))z_apply_rage(c,s,obj);
 if(state==80u)return;
 uint32_t hp=z_stage_of_hp(c,s,obj),t=z_next_transition(c,s,uint32_t(d));
 if(hp>=t){msd_guest_call(c,Z_RESERVE_STATE,obj,80u,0u,0u,nullptr);return;}
 uint32_t target=std::min(hp,t-1u);
 if(target!=uint32_t(d))z_swap(c,obj,uint32_t(anim),target);
}
// 分档受击动作（行为库 v5：stage_knockback_animation，标记 128）：ZombieBrain 只在进入状态 80 的第一帧请求槽 12
// （0x1017caaa）；此时没有待播的过渡（生命未越过下一个带过渡的档位）即为原生击退（BattleUnitDefault::damageAction
// 预约），改为当前档的槽 14 + 16d，过渡动作不因受击重播。没有此标记时槽 12 照旧。
static uint32_t z_remap(Context& c,uint32_t s,uint32_t obj,uint32_t slot){
 if(slot==12u&&(zw(c,s,0)&128u)){
  int32_t d=z_stage_of_anim(c,s,int32_t(rd<uint32_t>(c,obj+0xc4u)));if(d<0)d=0;
  if(z_stage_of_hp(c,s,obj)<z_next_transition(c,s,uint32_t(d)))return 14u+16u*uint32_t(d);
 }
 return slot+16u*z_target(c,s,obj,slot);
}
static bool z_self_destruct(Context& c,uint32_t s);static bool z_balloon(Context& c,uint32_t s);
// 入口：自爆单位（标记 512）的攻击状态与气球飞行段（标记 4096）先处理，其余照旧做生命分档。
HOOK(zombie_stage_update,0x1017ca15u, {uint32_t s=zspec(c,c.r[1]);if(s&&(z_self_destruct(c,s)||z_balloon(c,s)))return;} z_update(c);)
// 雪地步兵类（基准 182，BattleAction_ZakoSnow::update 入口 0x1018805c，参数与 ZombieBrain::update 相同：r1 对象、r2 状态）：
// 2026-10-13 冰车。宿主只允许不带过渡与狂暴的分档（behaviors.py），此处只会就地换档。
// 2026-10-15 冰车：ZakoSnow::update 的状态 110（爆炸属性死亡）与 100 都播放槽 13 并预约状态 140，110 另生成血色效果 0xff01。
// 带 no_death_splash（标记 256）的单位把传入的状态 110 按 100 处理。
static void z_snow_death(Context& c){
 if(c.r[2]!=110u)return;uint32_t s=zspec(c,c.r[1]);if(s&&(zw(c,s,0)&256u))c.r[2]=100u;
}
HOOK(zombie_stage_update_snow,0x1018805du, z_update(c);z_snow_death(c);)
HOOK(zombie_stage_remap,0x101de017u,
 uint32_t slot=c.r[1];
 if(slot<16u&&slot!=14u&&((Z_STAGE_SLOTS>>slot)&1u)){uint32_t s=zspec(c,c.r[0]);if(s&&(zw(c,s,0)&1u))c.r[1]=z_remap(c,s,c.r[0],slot);}
 )
// ZombieBrain 状态 80 的尾块（0x1017cac4：mov r0,r6; mov r1,r4; movs r2,#0 后出栈并尾调用 actionMove）。
// 投出子单位的档位过渡到达投出时刻且尚未投出时，按同一出栈改为尾调用 ParaTrooper::summonZakoBazooka(r1=对象)：
// 原生在对象位置以本单位等级生成固定 UnitID 45（落地映射改为登记的子单位）并记入 +0xfc。该帧不调用 actionMove(…,0)。
static bool z_throw(Context& c){
 uint32_t obj=c.r[4],s=zspec(c,obj);if(!s||!(zw(c,s,0)&16u))return false;
 if(rd<uint32_t>(c,obj+0xc4u)!=12u+16u*zw(c,s,24)||rd<uint32_t>(c,obj+0xfcu))return false;
 uint32_t sprite=rd<uint32_t>(c,obj+0x5cu);if(!sprite||rd<uint32_t>(c,sprite+0x3cu)<zw(c,s,25))return false;
 uint32_t sp=c.r[13];c.r[0]=c.r[6];c.r[1]=obj;
 c.r[4]=rd<uint32_t>(c,sp);c.r[5]=rd<uint32_t>(c,sp+4u);c.r[6]=rd<uint32_t>(c,sp+8u);c.r[14]=rd<uint32_t>(c,sp+12u);c.r[13]=sp+16u;
 c.pc=Z_SUMMON_CHILD;return true;
}
static Block old_zombie_throw;static void zombie_throw(Context& c){if(z_throw(c))return;old_zombie_throw(c);}
// 被投出的飞行单位（基准 160 BattleAction_ParaTrooper）首帧：原生把高度固定为 75（空降起点），改为从投出者手中出发，
// 并与原生空中单位一样不阻挡、不被选为目标。
// 0x101af7da 为非浏览模式的高度写入块，跳到 0x101af802 继续原生首帧流程。
static bool z_flight_start(Context& c){
 uint32_t obj=c.r[4],s=zspec(c,obj);if(!s||!(zw(c,s,0)&32u))return false;
 int32_t forward=int32_t(zw(c,s,26)),height=int32_t(zw(c,s,27));
 float x=rd<float>(c,obj+0x8cu)+float(rd<uint32_t>(c,obj+0x78u)==0x5au?forward:-forward),y=rd<float>(c,obj+0x90u)-float(height);
 wr<float>(c,obj+0x8cu,x);wr<float>(c,obj+0x94u,x);wr<float>(c,obj+0x90u,y);wr<float>(c,obj+0x98u,y);
 // 飞行段不阻挡、不受伤、穿越前线（身体状态 +0x6c：2 Guard、8 DontToche、0x10 AreaThrough、0x40 NoTarget，同原生空中单位）。
 wr<uint32_t>(c,obj+0x6cu,rd<uint32_t>(c,obj+0x6cu)|0x5au);
 c.pc=0x101af803u;return true;
}
static Block old_zombie_flight_start;static void zombie_flight_start(Context& c){if(z_flight_start(c))return;old_zombie_flight_start(c);}
// BattleUnitDefault::damageAction：0x1016f484 为受击后仍存活的分支（随后检查击退计量），0x1016f4a2 播放受击效果，
// 0x1016f44c 为生命归零的分支（栈 +8 为攻击方）。
static void z_armor_hit(Context& c){
 uint32_t obj=c.r[4],s=zspec(c,obj);
 if(!s||!(zw(c,s,0)&4u)||z_stage_of_hp(c,s,obj)>=zw(c,s,22))return;
 // 两个音效按当前生命的第 6 位交替（受击伤害多为 8 的倍数，低位不变）。
 uint32_t sid=zw(c,s,20u+((rd<uint32_t>(c,obj+0x308u)>>6)&1u));if(!sid)sid=zw(c,s,20);
 if(sid)msd_guest_call(c,Z_PLAY_SE,obj,sid,0u,0u,nullptr);
}
static void z_kill_sound(Context& c){
 uint32_t attacker=rd<uint32_t>(c,c.r[13]+8u),s=zspec(c,attacker);
 if(s&&(zw(c,s,0)&8u)&&zw(c,s,23))msd_guest_call(c,Z_PLAY_SE,attacker,zw(c,s,23),0u,0u,nullptr);
}
HOOK(zombie_no_knockback,0x1016f485u, uint32_t s=zspec(c,c.r[4]);if(s&&(zw(c,s,0)&2u)){c.pc=0x1016f4a3u;return;})
HOOK(zombie_armor_hit,0x1016f4a3u, z_armor_hit(c);)
HOOK(zombie_kill_sound,0x1016f44du, z_kill_sound(c);)
static bool z_throws(Context& c,uint32_t obj){uint32_t s=zspec(c,obj);return s&&(zw(c,s,0)&16u);}
// 前方最近敌人（行为库 v4：front_nearest_target，ZSpec 标记 64）。原生 setHeadPositionUnit 每帧按横坐标为两队各取最前单位
// （管理器 +0x30/+0x34 含 NoTarget，+0x38/+0x3c 不含；+0x30/+0x38 为队伍 0 的，+0x34/+0x3c 为队伍 1 的），
// getNearEnemyDistance、unitControlTypeNoukin 的阻挡判定与 isUnitMovePossible 的移动限制只看对方最前单位。单位落到对方最前单位之后
// （被投出的小鬼）时，距离为负，原生一直攻击而攻击框内没有敌人；与其重叠的对方单位也不能越过它移动，双方停在原地互相攻击不到。
// 本单位或对方最前单位带此标记、且对方最前单位的中心在本单位中心之后时，改取本单位前方（中心不在其后）的对方单位中前缘最近者：
// 资格同原生（存活，UnitID 0x8b/0x101/0x10c/0x10d 不检查；+0x64；身体状态非 Invisible 1、DontToche 8，攻击目标另排除 NoTarget 0x40），
// 前缘相同时取 +0xf0、再取 +0x60 较大者。前方没有对方单位时按原生的“无对方单位”处理。其余情形保持原生。
static constexpr uint32_t Z_AHEAD=64u;
static bool z_ahead(Context& c,uint32_t obj){uint32_t s=zspec(c,obj);return s&&(zw(c,s,0)&Z_AHEAD);}
// BattleObject::getWidthSize：精灵 +8（整数）乘 +0x28（浮点）后截断。
static int32_t z_width(Context& c,uint32_t obj){
 uint32_t sp=rd<uint32_t>(c,obj+0x5cu);
 return int32_t(float(int32_t(rd<uint32_t>(c,sp+8u)))*rd<float>(c,sp+0x28u));
}
static bool z_candidate(Context& c,uint32_t e,uint32_t excluded){
 if(!rd<uint8_t>(c,e+0x64u)||(rd<uint32_t>(c,e+0x6cu)&excluded))return false;
 uint32_t vt=rd<uint32_t>(c,e),uid=0u,alive=0u;
 msd_guest_call(c,rd<uint32_t>(c,vt+0x4cu),e,0u,0u,0u,&uid);
 if(uid==0x8bu||uid==0x101u||uid==0x10cu||uid==0x10du)return true;
 msd_guest_call(c,rd<uint32_t>(c,vt+0x5cu),e,0u,0u,0u,&alive);
 return alive!=0u;
}
// 单位 u（队伍 team）前方的对方单位中前缘最近者（对方队伍链表：队伍 0 的对方为 +0x1c，队伍 1 的对方为 +0x18，环形）。
static uint32_t z_nearest_ahead(Context& c,uint32_t manager,uint32_t u,uint32_t team,uint32_t excluded){
 uint32_t head=rd<uint32_t>(c,manager+(team?0x18u:0x1cu));if(!head)return 0u;
 float ux=rd<float>(c,u+0x8cu);uint32_t best=0u,bf=0u,bi=0u,e=head;int32_t bk=0;
 for(uint32_t n=0;n<8192u;++n){
  float ex=rd<float>(c,e+0x8cu);
  if((team?ex<=ux:ex>=ux)&&z_candidate(c,e,excluded)){
   float w=float(z_width(c,e));int32_t k=int32_t(team?ex+w:ex-w);
   uint32_t f=rd<uint32_t>(c,e+0xf0u),i=rd<uint16_t>(c,e+0x60u);
   if(!best||(team?k>bk:k<bk)||(k==bk&&(int32_t(f)>int32_t(bf)||(f==bf&&i>bi)))){best=e;bk=k;bf=f;bi=i;}
  }
  uint32_t next=rd<uint32_t>(c,e+0x124u);if(!next)break;e=next-0x11cu;if(e==head)break;
 }
 return best;
}
static bool z_front_behind(Context& c,uint32_t u,uint32_t f,uint32_t team){
 if(!f)return false;
 float ux=rd<float>(c,u+0x8cu),fx=rd<float>(c,f+0x8cu);
 if(team?!(fx>ux):!(fx<ux))return false;
 return z_ahead(c,u)||z_ahead(c,f);
}
// getNearEnemyDistance 入口（r0 管理器、r1 单位、r2 非 0 时扣除双方宽度）；计算次序同原生，结果截断为整数。
static bool z_balloon_flying(Context& c,uint32_t u);
static bool z_distance(Context& c){
 uint32_t m=c.r[0],u=c.r[1],team=rd<uint32_t>(c,u+0x70u);
 // 气球飞行段不以任何敌方单位为攻击目标（不在空中啃咬），飞到敌方据点前由 z_balloon 放手落地。
 if(z_balloon_flying(c,u)){ret(c,0x7fffffffu);return true;}
 if(!z_front_behind(c,u,rd<uint32_t>(c,m+(team?0x38u:0x3cu)),team))return false;
 uint32_t e=z_nearest_ahead(c,m,u,team,0x49u);
 if(!e){ret(c,0x7fffffffu);return true;}
 float ux=rd<float>(c,u+0x8cu),ex=rd<float>(c,e+0x8cu),d;
 if(c.r[2]){float wu=float(z_width(c,u)),we=float(z_width(c,e));d=team?((ux-wu)-we)-ex:((ex-we)-wu)-ux;}
 else d=team?ux-ex:ex-ux;
 ret(c,uint32_t(int32_t(d)));return true;
}
static Block old_zombie_ahead_distance;static void zombie_ahead_distance(Context& c){if(z_distance(c))return;old_zombie_ahead_distance(c);}
// unitControlTypeNoukin 的阻挡判定：0x1df780（队伍 0）与 0x1df7ea（队伍 1）入口处 r0 为管理器、r4 单位、
// r5 对方最前单位（含 NoTarget）、r7 队伍；r5 为 0 时原生按无对方单位前进至战场边界。
static void z_block_target(Context& c){
 uint32_t u=c.r[4],team=c.r[7];
 if(z_front_behind(c,u,c.r[5],team))c.r[5]=z_nearest_ahead(c,c.r[0],u,team,0x09u);
}
HOOK(zombie_ahead_block_p1,0x101df781u, z_block_target(c);)
HOOK(zombie_ahead_block_p2,0x101df7ebu, z_block_target(c);)
// BattleObjectManager::isUnitMovePossible（advanceFrame 移动后检查）：向前移动时不得越过对方最前单位（含 NoTarget）的后缘。
// 0x1df1fa（向右）与 0x1df23a（向左）入口处 r0 为管理器、r3 队伍、r4 单位、r5 对方最前单位；r5 为 0 时只受战场边界限制。
static void z_move_target(Context& c){
 uint32_t u=c.r[4],team=c.r[3];
 if(team<=1u&&z_front_behind(c,u,c.r[5],team))c.r[5]=z_nearest_ahead(c,c.r[0],u,team,0x09u);
}
HOOK(zombie_ahead_move_right,0x101df1fbu, z_move_target(c);)
HOOK(zombie_ahead_move_left,0x101df23bu, z_move_target(c);)
// ---------- 2026-10-15 新 PvZ 单位（行为库 v8：小丑、气球、机枪豌豆、辣椒、倭瓜；被投出的小鬼在敌方据点前落地）----------
// ZSpec 扩为 33 个字：28 行进射击的射程（walk_shoot），29 气球自动放手的距离，30 气球出场音效 SoundID，
// 31 被投出的飞行单位与敌方据点前缘的最小间距（thrown_flight.base_clearance，0 为不限制），32 自爆动作按素材原朝向绘制的起始 tick + 1。
bool msd_guest_call_stack(Context& c,uint32_t fn,uint32_t a0,uint32_t a1,uint32_t a2,uint32_t a3,
                          const uint32_t* stack,uint32_t stack_words,uint32_t* result);
static constexpr uint32_t Z_SELF_DESTRUCT=512u,Z_GROUND_ONLY=1024u,Z_WALK_SHOOT=2048u,Z_BALLOON=4096u;
// BattleObjectManager 单例（getInstance 0x1de618 返回 0x977f4c+4）；getKyotenUnitImpl 为 [管理器 + (队伍+6)×4]。
static constexpr uint32_t Z_MANAGER=0x10977f50u;
static constexpr uint32_t Z_HOPPER_UPDATE=0x101840ddu,Z_NEAR_DISTANCE=0x101ded90u,Z_ADD_BULLET=0x1017e3f0u;
// BattleGameMaster 单例（getInstance 0x1cdb48 返回 0x9606f8+4）；+0x4828 为 5 时为原生动作浏览（单位菜单 ACTION），场上没有敌人。
static constexpr uint32_t Z_GAME_MASTER=0x109606fcu;
static bool z_viewer(Context& c){return rd<uint32_t>(c,Z_GAME_MASTER+0x4828u)==5u;}
// 单位 u 前缘与敌方据点前缘的间距（与 getNearEnemyDistance 扣除双方宽度时的算法相同）。
static bool z_base_gap(Context& c,uint32_t u,float& gap){
 uint32_t team=rd<uint32_t>(c,u+0x70u);if(team>1u)return false;
 uint32_t b=rd<uint32_t>(c,Z_MANAGER+(7u-team)*4u);if(!b||!rd<uint32_t>(c,b+0x5cu)||!rd<uint32_t>(c,u+0x5cu))return false;
 float ux=rd<float>(c,u+0x8cu),bx=rd<float>(c,b+0x8cu),wu=float(z_width(c,u)),wb=float(z_width(c,b));
 gap=team?((ux-wu)-wb)-bx:((bx-wb)-wu)-ux;return true;
}
// 自爆（self_destruct_attack，标记 512）：状态 30/40/50/140 交给原版 HOPPER MECHA（UnitID 39）的
// BattleAction_Hoppermecha::update（0x1840dc）：30/40 播放槽 8、50 播放槽 9，并置 NoTarget、DontToche、DontSpAttack，
// 预约状态 140；140 在动画播完后 BattleObject::kill（不经死亡流程）。状态 140 的优先级高于受击（80）与死亡（100–130），
// 爆炸动作不会被打断。伤害取进入动作时的攻击组（setAnimationID 在状态 30/40/50 时写入对象 +0x88）。
// ZSpec 字 32（self_destruct_attack.unmirrored_from_tick + 1）：状态 140 中精灵帧计数（+0x3c）达到该值后，把精灵的当前朝向
// （+0x10）设为素材朝向（+0x48），图像不再随队伍镜像（BattleObject::isImageMirrorRendring 比较这两个字段）；单位朝向（+0x78）不变。
// 动作浏览中不移除：动作播完（对象 +0xc9 为 0）后恢复绘制朝向与身体状态（NoTarget、DontToche、DontSpAttack），强制回到待机，
// 由单位菜单重新演示（同其他单位）。
static bool z_self_destruct(Context& c,uint32_t s){
 uint32_t st=c.r[2],obj=c.r[1];
 if(!(zw(c,s,0)&Z_SELF_DESTRUCT)||(st!=30u&&st!=40u&&st!=50u&&st!=140u))return false;
 uint32_t sp=rd<uint32_t>(c,obj+0x5cu);
 if(st==140u&&zw(c,s,32)){
  if(sp&&rd<uint32_t>(c,sp+0x3cu)+1u>=zw(c,s,32))wr<uint32_t>(c,sp+0x10u,rd<uint32_t>(c,sp+0x48u));
 }
 if(st==140u&&z_viewer(c)&&!rd<uint8_t>(c,obj+0xc9u)){
  if(sp)wr<uint32_t>(c,sp+0x10u,rd<uint32_t>(c,obj+0x78u));
  wr<uint32_t>(c,obj+0x6cu,rd<uint32_t>(c,obj+0x6cu)&~0x4cu);
  msd_guest_call(c,Z_RESERVE_STATE,obj,10u,1u,0u,nullptr);
  c.pc=c.r[14];return true;
 }
 c.pc=Z_HOPPER_UPDATE;return true;
}
// 气球飞行（balloon_flight，标记 4096，须与生命分档同用）：第 0 档为飞行段，生命降到第 1 个档位（气球打破）、
// 前缘与敌方据点前缘的间距不超过 ZSpec 字 29、或发动绝招时放手，经状态 80 播放第 1 档的过渡动作（爆开与落下）。
// 飞行段置身体状态 DontToche 8、AreaThrough 0x10、NoTarget 0x40、NockbackGuard 0x80（同原生空中单位：不被选为目标、
// 不阻挡、不被阻挡、不被击退），高度由精灵描述符的受击框与帧位置表达；落地后清除这些状态，并置 DontSpAttack 4（不再有绝招）。
// 主动放手时生命截到第 1 个档位以下（气球部分的生命作废，同 PvZ 原作）。出场首帧播放 ZSpec 字 30 的音效。
// 飞行段的判定：身体状态已有 AreaThrough，或生命仍在第 0 档且未进入死亡状态（出场首帧尚未经过 z_balloon 设置身体状态，
// 原生行动控制在同一帧已查询攻击距离；2026-10-15 修正：敌人已在出生点附近时，气球在首帧进入攻击状态 40，
// 飞行段的攻击槽为循环动作，状态 40 不结束，气球停在出生点）。
static bool z_balloon_flying(Context& c,uint32_t u){
 uint32_t s=zspec(c,u);if(!s||!(zw(c,s,0)&Z_BALLOON))return false;
 if(rd<uint32_t>(c,u+0x6cu)&0x10u)return true;
 return rd<uint32_t>(c,u+0x7cu)<100u&&int32_t(rd<uint32_t>(c,u+0x308u))>0&&z_stage_of_hp(c,s,u)==0u;
}
static void z_balloon_pop(Context& c,uint32_t s,uint32_t obj){
 int64_t mx=int32_t(rd<uint32_t>(c,obj+0x304u)),cap=(int64_t(zw(c,s,2))*mx-1)/int64_t(zw(c,s,8));
 if(int32_t(rd<uint32_t>(c,obj+0x308u))>cap)wr<uint32_t>(c,obj+0x308u,uint32_t(int32_t(cap)));
}
static bool z_balloon(Context& c,uint32_t s){
 uint32_t obj=c.r[1],state=c.r[2];
 if(!(zw(c,s,0)&Z_BALLOON)||state>=100u||int32_t(rd<uint32_t>(c,obj+0x308u))<=0)return false;
 int32_t d=z_stage_of_anim(c,s,int32_t(rd<uint32_t>(c,obj+0xc4u)));
 uint32_t body=rd<uint32_t>(c,obj+0x6cu);
 if(d<=0&&state!=80u&&z_stage_of_hp(c,s,obj)==0u){
  if(!(body&0x10u)&&zw(c,s,30))msd_guest_call(c,Z_PLAY_SE,obj,zw(c,s,30),0u,0u,nullptr);
  wr<uint32_t>(c,obj+0x6cu,body|0xd8u);
  float gap=0.0f;
  // 动作浏览的近距离攻击演示（状态 30/40）：先放手落地，此后在地面上演示啃咬
  bool demo=z_viewer(c)&&(state==30u||state==40u);
  if(state==50u||demo||(z_base_gap(c,obj,gap)&&gap<=float(int32_t(zw(c,s,29))))){
   z_balloon_pop(c,s,obj);
   // 绝招：不播放原生的特殊攻击动作，直接经状态 80 放手
   if(state==50u||demo){msd_guest_call(c,Z_RESERVE_STATE,obj,80u,0u,0u,nullptr);c.pc=c.r[14];return true;}
   return false;
  }
  // 飞行段不攻击：已处于攻击状态（30/40）时强制回到行进（状态 20）。飞行段的攻击槽为循环动作，状态 40 不会自行结束。
  if(state==30u||state==40u){msd_guest_call(c,Z_RESERVE_STATE,obj,20u,1u,0u,nullptr);c.pc=c.r[14];return true;}
  return false;
 }
 wr<uint32_t>(c,obj+0x6cu,(body&~0xd8u)|4u);
 return false;
}
// 行进射击（walk_shoot，标记 2048）：动作脚本 op22[弹体槽, 命中槽, x, y]（x、y 为素材坐标，同原生）经 BattleObject::onEventBulletShot
// 调用 BattleAction_ZombieBrain::shotBullet（0x17e308：r1 对象，r2 弹体槽，r3 / 栈 [0] 为已换算朝向与比例的 x、y，栈 [4] 为命中槽）。
// 只在待机或行进（状态 10、20）且最近的敌方单位前缘距离不超过 ZSpec 字 28 时发射（动作浏览中没有敌人，不检查距离）；位置的取法同原生 shotBullet，
// 以近距参数组（状态 30：词 15–21，伤害、击退值、目标数、弹速、行程）调用
// addBullet(对象, x, y, 0, 弹体槽, 命中槽, 命中槽, 30)（0x17e3f0）。原版僵尸（青年）的吐出攻击仍走原生路径。
static bool z_walk_shot(Context& c){
 uint32_t obj=c.r[1],s=zspec(c,obj);if(!s||!(zw(c,s,0)&Z_WALK_SHOOT))return false;
 uint32_t state=rd<uint32_t>(c,obj+0x7cu),sp=c.r[13],action=c.r[0],anim=c.r[2],x=c.r[3];
 uint32_t y=rd<uint32_t>(c,sp),hit=rd<uint32_t>(c,sp+4u);
 c.pc=c.r[14];
 if(state!=10u&&state!=20u)return true;
 uint32_t d=0u;
 if(!z_viewer(c)&&(!msd_guest_call(c,Z_NEAR_DISTANCE,Z_MANAGER,obj,1u,0u,&d)||int32_t(d)>int32_t(zw(c,s,28))))return true;
 const uint32_t stack[5]={0u,anim,hit,hit,30u};
 msd_guest_call_stack(c,Z_ADD_BULLET,action,obj,x,y,stack,5u,nullptr);
 return true;
}
static Block old_zombie_walk_shot;static void zombie_walk_shot(Context& c){if(z_walk_shot(c))return;old_zombie_walk_shot(c);}
// 只打地面（ground_only_attack，标记 1024）：BattleUnit::attack 入口（r0 攻击方、r1 目标）。目标为空中单位
// （身体状态 NoTarget 0x40）或战场道具（UnitID 116/231/289/363）时不命中。
static bool z_ground_only(Context& c){
 uint32_t s=zspec(c,c.r[0]);if(!s||!(zw(c,s,0)&Z_GROUND_ONLY))return false;
 uint32_t t=c.r[1];bool skip=(rd<uint32_t>(c,t+0x6cu)&0x40u)!=0u;
 if(!skip){
  uint32_t uid=0u;msd_guest_call(c,rd<uint32_t>(c,rd<uint32_t>(c,t)+0x4cu),t,0u,0u,0u,&uid);
  skip=uid==0x74u||uid==0xe7u||uid==0x121u||uid==0x16bu;
 }
 if(!skip)return false;
 c.pc=c.r[14];return true;
}
static Block old_zombie_ground_only;static void zombie_ground_only(Context& c){if(z_ground_only(c))return;old_zombie_ground_only(c);}
// 被投出的飞行单位的据点前落地（thrown_flight.base_clearance，ZSpec 字 31）：BattleAction_ParaTrooper::update 入口
// （r1 对象、r2 状态）。首帧初始化（对象 +0x1c 非 0）之后的飞行状态 20–50 中，前缘与敌方据点前缘的间距小于该值时，
// 把位置退回到该间距处并清除水平运动（同 clearMoveActionParamsXOnly），随后垂直落下；落地后照常转为
// para_drop_transform 指定的单位。避免被投出的小鬼越过或嵌入敌方据点。
static void z_flight_clearance(Context& c){
 uint32_t obj=c.r[1],state=c.r[2],s=zspec(c,obj);
 if(!s||!(zw(c,s,0)&32u)||!zw(c,s,31)||!rd<uint32_t>(c,obj+0x1cu)||state<20u||state>50u)return;
 float gap=0.0f;if(!z_base_gap(c,obj,gap))return;
 float need=float(int32_t(zw(c,s,31)));if(gap>=need)return;
 float x=rd<float>(c,obj+0x8cu)+(rd<uint32_t>(c,obj+0x70u)?need-gap:gap-need);
 wr<float>(c,obj+0x8cu,x);wr<float>(c,obj+0x94u,x);
 wr<uint32_t>(c,obj+0x9cu,0u);wr<uint32_t>(c,obj+0xa4u,0u);wr<uint32_t>(c,obj+0xacu,0u);
}
HOOK(zombie_flight_clearance,0x101af795u, z_flight_clearance(c);)
// 原住民（鸟）类（基准 221，BattleAction_NativeBird）的两个行为（2026-10-18 Hunter，行为库 v9；ZSpec 字 33–38）。
// 炸药（lob_blast，标记 8192）：原生 BattleAction_NativeBird::shotBullet（0x17fdd8）以 addBulletNotAim 发射槽 26，
// 把状态参数 0x16 写入弹体 +0x34；BulletAction_NativeBird::update（0x19fc3c）首帧按发射高度求竖直初速（飞行时间固定）、
// 按 +0x34 求水平速度，使弹体落在该距离处；碰到敌人（BattleBulletDefault::attackAction 预约状态 60）或落地
// （adjustHitGround 后预约状态 60）后，状态 60 与 200 的下一帧直接移除，不爆炸。
// 带此标记的单位：
// - 绝招弹体：op22 的弹体槽在 [字 35, 字 35 + 字 36) 内时改由本钩子发射（弹体动画取 op22 的槽），第 i 颗（0 起）的
//   落点距离为 本单位当前状态词 33（绝招弹体目的距离）×(i+1)/字 36，即在射程内等距分布、最远一颗落在射程处，
//   射程随等级或倍率改变时落点随之改变。其余 op22（普通攻击）照旧走原生路径（落点为状态参数 0x16）。
// - 飞行：原生每帧以整数横移（水平速度定点数右移 8 位），各颗的落点只能是飞行帧数（约 37）的整数倍，5 颗不能等距。
//   原生首帧初始化并移动一次后（对象 +0x1c 非 0），本钩子接管飞行：按剩余距离（+0x34 的目的距离减去首帧已移动的整数步）
//   与按原生的竖直运动（actionMoveY(vy)、vy += 1.32）推算的剩余帧数求出浮点横移，记入 +0x30（原生的累加量，接管后不再使用），
//   +0x1c 记为 2；之后每帧 actionMoveX(横移)、actionMoveY(vy)、vy += 1.32，adjustHitGround 着地时预约状态 61。
//   落点距离（自投出点）因此等于目的距离（误差在 1 个世界单位内）。
//   剩余帧数只在下落段（本帧竖直位移大于 0）判定到达落点地面（2026-10-21 r75）：向高处投掷时（自制坡道战场，落点地面高于出手后的弹体），
//   上升段第 1 帧即满足 y 不小于落点地面，原先求得 1 帧，横移等于整段剩余距离，弹体此后每帧以该横移飞出战场。
// - 落地：弹体的框碰到地面时原生调用 BulletAction_NativeBird::hitGround（0x16d8e8，预约状态 60），本钩子改为预约状态 61；
//   弹体中心到达地面时 update 自身的 adjustHitGround 也预约 60（位置已贴地）。碰到敌人时 BattleBulletDefault::attackAction
//   （0x175e04）预约 60（位置在空中）。
// - 弹体进入状态 61、或进入状态 60 且位置在地面（y 不低于 BattleStage::getAltitude 减 1）的第一帧：位置贴到地面，播放字 34 的槽
//   （引信燃烧后爆炸）；进入其余状态 60 或 200 的第一帧：播放字 33 的槽（碰到敌人，立即爆炸）。之后不移动，动画播完
//   （对象 +0xc9 为 0）时 kill，同原生迫击炮弹 BulletAction_Mortar::update（0x185c5c）。爆炸的攻击框、目标数与音效写在这两个槽的脚本中。
// 按攻击属性区分死亡（death_by_attribute，标记 16384）：NativeBird::update 的死亡状态 100/110/120 都在第一帧请求槽 12
// （着地后槽 13，动画播完 kill）；状态 110（爆炸属性）改为字 37 的槽、120（火焰属性）改为字 38 的槽，100 照旧。
// 字 39–41（2026-10-18 R4）为状态 100/110/120 的另一版本（非 0 时）：死亡第一帧单位横坐标（+0x8c）取整为奇数时播放该版本。
// 只由当时的位置决定，不用随机数（不改变其他随机数的序列），回放与联机时双方相同。
static constexpr uint32_t L_BLAST=8192u,L_DEATH=16384u;
static constexpr uint32_t L_NOT_AIM=0x1017f728u,L_ACTION_GOT=0x10936b08u,L_SET_ANIM=0x101de016u,L_KILL=0x101dd86cu,
 L_STAGE=0x101e1ae0u,L_ALTITUDE=0x101e1c72u;
static uint32_t bspec(Context& c,uint32_t obj){
 if(!active(c)||!head(c,168u)||!obj)return 0u;
 uint32_t vt=rd<uint32_t>(c,obj);if(vt!=head(c,84u)&&vt!=head(c,88u))return 0u;
 uint32_t uid=rd<uint32_t>(c,obj+0x128u);if(!record(c,uid))return 0u;
 return rd<uint32_t>(c,head(c,168u)+(uid-U)*4u);
}
// shotBullet 入口：r0 动作、r1 对象、r2 弹体槽、r3 / 栈 [0] 为 x、y，栈 [4] 为命中槽。
static bool l_shot(Context& c){
 uint32_t obj=c.r[1],s=zspec(c,obj);if(!s||!(zw(c,s,0)&L_BLAST))return false;
 uint32_t slot=c.r[2],first=zw(c,s,35),count=zw(c,s,36);
 if(!count||slot<first||slot>=first+count)return false;
 uint32_t sp=c.r[13],bullet=0u;
 const uint32_t stack[4]={rd<uint32_t>(c,sp+4u),slot,rd<uint32_t>(c,L_ACTION_GOT),0u};
 // 嵌套调用未完成时 bullet 为中止时的 r0（不是弹体），不写入（2026-10-22 r77）。
 bool done=msd_guest_call_stack(c,L_NOT_AIM,c.r[0],obj,c.r[3],rd<uint32_t>(c,sp),stack,4u,&bullet);
 if(done&&bullet){
  uint32_t st=obj+0x128u+0xecu*rd<uint32_t>(c,obj+0x300u);
  int64_t range=int32_t(rd<uint32_t>(c,st+33u*4u));
  wr<uint32_t>(c,bullet+0x34u,uint32_t(int32_t(range*int64_t(slot-first+1u)/int64_t(count))));
 }
 c.pc=c.r[14];return true;
}
static Block old_hunter_shot;static void hunter_shot(Context& c){if(l_shot(c))return;old_hunter_shot(c);}
// BulletAction_NativeBird::update 入口：r1 弹体、r2 状态、r3 进入该状态后的帧数。
static bool l_blast_bullet(Context& c,uint32_t b){
 if(rd<uint32_t>(c,b)!=head(c,88u))return 0u;
 uint32_t s=bspec(c,b);return s&&(zw(c,s,0)&L_BLAST)?s:0u;
}
static constexpr uint32_t L_MOVE_X=0x101dde10u,L_MOVE_Y=0x101dde4eu,L_ADJUST_GROUND=0x1019af50u;
static constexpr float L_GRAVITY=1.32f;
static uint32_t l_bits(float f){uint32_t u;std::memcpy(&u,&f,4);return u;}
static int32_t l_altitude(Context& c,float x){
 uint32_t stage=0u,alt=0u;
 if(!msd_guest_call(c,L_STAGE,0u,0u,0u,0u,&stage)||!stage||!msd_guest_call(c,L_ALTITUDE,stage,uint32_t(int32_t(x)),1u,0u,&alt))return 0x7fffffff;
 return int32_t(alt);
}
static void l_flight(Context& c,uint32_t b){
 float dir=rd<uint32_t>(c,b+0x78u)==0x5au?1.0f:-1.0f;
 if(rd<uint32_t>(c,b+0x1cu)==1u){
  int32_t moved=int32_t(rd<uint32_t>(c,b+0x2cu))>>8;
  float rest=float(int32_t(rd<uint32_t>(c,b+0x34u))-moved),x=rd<float>(c,b+0x8cu),y=rd<float>(c,b+0x90u),vy=rd<float>(c,b+0x3cu);
  float ground=float(l_altitude(c,x+dir*rest));int n=0;
  while(n<600){float step=vy;y+=vy;vy+=L_GRAVITY;++n;if(step>0.0f&&y>=ground)break;}
  wr<float>(c,b+0x30u,rest>0.0f?rest/float(n):0.0f);wr<uint32_t>(c,b+0x1cu,2u);
 }
 msd_guest_call(c,L_MOVE_X,b,l_bits(dir*rd<float>(c,b+0x30u)),0u,0xffffffffu,nullptr);
 float vy=rd<float>(c,b+0x3cu);
 msd_guest_call(c,L_MOVE_Y,b,l_bits(vy),0u,0xffffffffu,nullptr);
 wr<float>(c,b+0x3cu,vy+L_GRAVITY);
 uint32_t landed=0u;
 if(msd_guest_call(c,L_ADJUST_GROUND,c.r[0],b,0u,0u,&landed)&&landed)msd_guest_call(c,Z_RESERVE_STATE,b,61u,0u,0u,nullptr);
}
static bool l_bullet(Context& c){
 uint32_t b=c.r[1],state=c.r[2];
 uint32_t s=l_blast_bullet(c,b)?bspec(c,b):0u;if(!s)return false;
 if(state!=60u&&state!=61u&&state!=200u){
  if(!rd<uint32_t>(c,b+0x1cu))return false;      // 原生首帧：初始化竖直初速与水平速度并移动一次
  l_flight(c,b);c.pc=c.r[14];return true;
 }
 if(c.r[3]==0u){
  uint32_t slot=zw(c,s,33),stage=0u,alt=0u;
  if(state!=200u&&msd_guest_call(c,L_STAGE,0u,0u,0u,0u,&stage)&&stage&&
     msd_guest_call(c,L_ALTITUDE,stage,uint32_t(int32_t(rd<float>(c,b+0x8cu))),1u,0u,&alt)&&
     (state==61u||rd<float>(c,b+0x90u)>=float(int32_t(alt))-1.0f)){
   slot=zw(c,s,34);
   wr<float>(c,b+0x90u,float(int32_t(alt)));wr<float>(c,b+0x98u,float(int32_t(alt)));
  }
  msd_guest_call(c,L_SET_ANIM,b,slot,0u,1u,nullptr);
 }else if(!rd<uint8_t>(c,b+0xc9u))msd_guest_call(c,L_KILL,b,0u,0u,0u,nullptr);
 c.pc=c.r[14];return true;
}
static Block old_hunter_bullet;static void hunter_bullet(Context& c){if(l_bullet(c))return;old_hunter_bullet(c);}
// BulletAction_NativeBird::hitGround 入口（r1 弹体）：带 lob_blast 的弹体改为预约状态 61（落地）。
static bool l_ground(Context& c){
 uint32_t b=c.r[1];if(!l_blast_bullet(c,b))return false;
 msd_guest_call(c,Z_RESERVE_STATE,b,61u,0u,0u,nullptr);c.pc=c.r[14];return true;
}
static Block old_hunter_ground;static void hunter_ground(Context& c){if(l_ground(c))return;old_hunter_ground(c);}
HOOK(hunter_death_slot,0x101de017u,
 if(c.r[1]==12u){uint32_t s=zspec(c,c.r[0]);
  if(s&&(zw(c,s,0)&L_DEATH)){uint32_t st=rd<uint32_t>(c,c.r[0]+0x7cu);
   bool odd=(int32_t(rd<float>(c,c.r[0]+0x8cu))&1)!=0;
   uint32_t base=st==110u?zw(c,s,37):st==120u?zw(c,s,38):st==100u?12u:0u;
   uint32_t alt=st==100u?zw(c,s,39):st==110u?zw(c,s,40):st==120u?zw(c,s,41):0u;
   if(odd&&alt)c.r[1]=alt;else if(base)c.r[1]=base;}}
 )
static uint32_t hunter_hooks=0u;
// 版本 1：炸药与按属性的死亡；版本 2（r66）：三种死亡的另一版本（ZSpec 字 39–41）。
extern "C" __declspec(dllexport) uint32_t msd_community_hunter_version(){return hunter_hooks==4u?2u:0u;}
// 已登记的钩子数：首批 7 个全部找到时版本 1，另含前方最近敌人的 5 个时版本 2；宿主据此确认核心支持。
static uint32_t zombie_hooks=0u;
// 3：分档受击动作（标记 128，钩子数同 2）。4：另含雪地步兵类的分档入口（2026-10-13 冰车，共 13 个钩子）。
// 5：雪地步兵类入口另处理 no_death_splash（标记 256，2026-10-15，钩子数同 4）。
// 6：2026-10-15 新单位（自爆 512、只打地面 1024、行进射击 2048、气球飞行 4096、被投出单位的据点前落地），
//    另含 ZombieBrain::shotBullet、BattleUnit::attack 与 ParaTrooper::update 入口 3 个钩子（共 16 个）；ZSpec 33 字。
extern "C" __declspec(dllexport) uint32_t msd_community_zombie_version(){return zombie_hooks==16u?6u:zombie_hooks==13u?5u:zombie_hooks==12u?3u:zombie_hooks==7u?1u:0u;}
// 战场道具（UnitID 116/231/289/363）：BattleUnit::attack（0x1e093c）对道具在 0x1e0a0c 起比较攻击方 getUnitID，
// 为 1、80、182（雪地步兵）时不造成命中；其他攻击方以当前状态的伤害组直接调用道具的 damage。社区单位的 UnitID 不在其中：
// 基准 182 的冰车在行走状态（伤害组为 0）以零伤害反复命中道具，道具每次进入状态 60 并生成效果 0xff15（黄色火光），不被拾取。
// 社区单位按其基准 UnitID（记录 +4）适用同一判断（2026-10-14）。
static bool item_hit_exempt(Context& c){
 uint32_t p=record(c,rd<uint32_t>(c,c.r[4]+0x128u));if(!p)return false;
 uint32_t base=rd<uint32_t>(c,p+4u);if(base!=1u&&base!=80u&&base!=182u)return false;
 c.pc=0x101e0a47u;return true;
}
static Block old_item_hit_base;static uint32_t item_hit_hooks=0u;
static void item_hit_base(Context& c){if(item_hit_exempt(c))return;old_item_hit_base(c);}
extern "C" __declspec(dllexport) uint32_t msd_community_item_exempt_version(){return item_hit_hooks==1u?1u:0u;}
// 工兵受击（2026-10-20）：BattleAction_Kouhei::damageAction（0x16d772）每次受击都预约状态 100（撤退），与生命无关。
// 按生命计算的单位（头部 +176 表）在原生扣血之后生命仍大于 0 时只播放受击闪光（同 BattleObject::playHitEffect 0x1de114：+0x110 写 4.0），
// 继续行进或修筑；生命耗尽时按原生撤退。不在表中的单位保持原生。
static Block old_engineer_damage;static uint32_t engineer_hooks=0u;
static void engineer_damage(Context& c){
 uint32_t o=c.r[1];
 if(o&&engineer_entry(c,rd<uint32_t>(c,o+0x128u))&&rd<int32_t>(c,o+0x308u)>0){wr<uint32_t>(c,o+0x110u,0x40800000u);c.pc=c.r[14];return;}
 old_engineer_damage(c);
}
extern "C" __declspec(dllexport) uint32_t msd_community_engineer_hp_version(){return engineer_hooks==1u?1u:0u;}
// ---------- IRON SENTINEL（钢铁哨兵，2026-10-21，行为库 v12：iron_slider / iron_slider_second_form）----------
// MSD 1.46 原生保留未发布的 IRON SLIDER（UnitID 394/395）的动作类 BattleAction_IronSlider / _2 与弹体类
// BulletAction_IronSlider_Atack_L/SP/S/S_SUB/2/2_SUB，是 MSA 7.13.0 同名类的较早版本。社区单位以这两个动作类运行
// （加载器以行为写入动作对象），脚本为 MSA 7.13 的动作记录（编号不变）。以下钩子把较早版本与 MSA 7.13 的差异按 MSA 处理：
//  1 setAnimationID：原生请求的槽号换成 MSA 槽号（第一形态 8→9；第二形态 94/95/96/97→17/18/19/21；主炮导弹 52→14；
//    巨型导弹 77→25、84→23；侧炮炮弹 43→共用爆炸 0xff03 + 槽 15）。
//  2 BattleAction_IronSlider::createObject：MSA 编号（侧炮 50/56/105/111/117/124/130/136、火箭 60、主炮导弹 64、残片 72/73），
//    其他编号不建立对象（同 MSA）。火箭另记录 VALS：+0x1c 发射时单位 x、+0x20 投射距离（字 26）、+0x24 攻击距离边缘的 x
//    （单位 x ± (半宽 + 字 7)）。
//  3 BattleAction_IronSlider_2::createObject：MSA 编号 24（巨型导弹，参数 40）。
//  4 summonUnit 调用 createChildObject 时（返回地址 0x101bdadd）：原生写死的 395 换成第一形态状态 +0xa0 的子单位（第二形态）。
//  5 两个 update 首次调用 setImageOffsetPosition 时：取消较早版本的 (0,30) 绘制偏移（MSA 无此偏移）。
//  6 BulletAction_IronSlider_Atack_L::update：状态 40 首帧按 MSA 重新进入（y = 舞台上沿 65 − 80，动作 61）并瞄准对方最前方单位
//    （BattleObjectManager +0x38/+0x3c，瞄准其中心，角度按 MSA 限定在朝下一侧）；目标超出攻击距离边缘时落向边缘的地面。
//    之后水平飞离发射点达投射距离即爆炸。命中 / 失效 / 落地（60/140/200）在 (20,20) 生成共用爆炸 0xff03。
//  7 BulletAction_IronSlider_Atack_SP::update：60/140/200 在 (0,20) 生成本单位的爆炸动作 103（带攻击框，同 MSA）后移除。
//  （以下 2026-10-21 R4，核心 r74）
//  8 summonUnit 中 createChildObject 返回后（0x101bdadc）：第一形态并非因生命耗尽而损毁（据点被毁时生命仍大于 0），或本方据点
//    生命已为 0（战斗结束后新单位不再由状态 0 进入待机），第二形态立即预约状态 100，播放其损毁动作后移除。
//  9 update 中 summonUnit 返回后（0x101bddc4）：第一形态不在召唤的同一帧移除，改预约状态 140（原生：动画结束即移除），于下一帧移除。
//    第二形态在被召唤的帧尚未更新、不绘制，原先这一帧画面中没有车体（闪现）。
// 10 BulletAction_IronSlider_Atack_2::update 状态 40（巨型导弹自舞台上方斜落；原生与 MSA 只在进入下落时按对方最前方单位的位置
//    定一次起点）：每 tick 按对方最前方单位当前的 x 重设水平速度，使导弹在该单位所在处落地（竖直速度不变，水平速度不超过竖直速度）。
// 只读写客体对象内存，无静态状态（回滚快照随客体内存保存）。
static constexpr uint32_t IS_VT1=0x1092db60u,IS_VT2=0x1092db90u;
static constexpr uint32_t IS_ACT_2=0x109601f8u,IS_ACT_SP=0x10960200u,IS_ACT_L=0x10960204u,IS_ACT_S=0x10960208u,IS_ACT_SSUB=0x1096020cu;
static constexpr uint32_t IS_ADD_EFFECT=0x10181cd4u,IS_FALLOUT=0x1018fd68u,IS_WIDTH=0x101ddb2eu,IS_HEIGHT=0x101ddb4au,
 IS_ATAN=0x1013fd60u,IS_COS=0x1013fc14u,IS_SIN=0x1013fc54u,IS_MOVE_X=0x101dde10u,IS_MOVE_Y=0x101dde4eu,
 IS_NOT_AIM=0x1017f728u,IS_SET_ANIM=0x101de016u,IS_KILL=0x101dd86cu,IS_STAGE=0x101e1ae0u,IS_ALTITUDE=0x101e1c72u,
 IS_MANAGER=0x10977f50u,IS_RESERVE=0x101dda28u,IS_TEAM_UNITS=0x101df318u;
static uint32_t iron_slider_hooks=0u;
static uint32_t is_class(Context& c,uint32_t obj){
 uint32_t act=obj?rd<uint32_t>(c,obj+0x58u):0u;   // BattleObject::initialize：+0x58 动作对象、+0x5c 精灵、+0x70 队伍
 return act>=0x10000000u&&act<0x20000000u?rd<uint32_t>(c,act):0u;
}
static uint32_t is_status(Context& c,uint32_t obj,uint32_t word){
 return rd<uint32_t>(c,obj+0x128u+0xecu*rd<uint32_t>(c,obj+0x300u)+word*4u);
}
static void is_effect(Context& c,uint32_t act,uint32_t obj,int32_t x,int32_t y,uint32_t id){
 const uint32_t stack[3]={0u,id,0xffffffffu};
 msd_guest_call_stack(c,IS_ADD_EFFECT,act,obj,uint32_t(x),uint32_t(y),stack,3u,nullptr);
}
static uint32_t is_call(Context& c,uint32_t fn,uint32_t a0,uint32_t a1=0u,uint32_t a2=0u,uint32_t a3=0u){
 uint32_t r=0u;msd_guest_call(c,fn,a0,a1,a2,a3,&r);return r;
}
static void is_anim(Context& c){
 if(!active(c))return;
 uint32_t obj=c.r[0],act=rd<uint32_t>(c,obj+0x58u),slot=c.r[1];
 if(act==IS_ACT_SP){if(slot==52u)c.r[1]=14u;return;}
 if(act==IS_ACT_2){if(slot==77u)c.r[1]=25u;else if(slot==84u)c.r[1]=23u;return;}
 if(act==IS_ACT_SSUB){if(slot==43u){is_effect(c,act,obj,0,0,0xff03u);c.r[1]=15u;}return;}
 uint32_t vt=is_class(c,obj);
 if(vt==IS_VT1){if(slot==8u)c.r[1]=9u;}
 else if(vt==IS_VT2&&slot>=94u&&slot<=97u){static const uint32_t form2[4]={17u,18u,19u,21u};c.r[1]=form2[slot-94u];}
}
HOOK(iron_slider_anim,0x101de017u, is_anim(c);)
// createObject(this, 对象, 编号, x, 栈 [0] y, 栈 [4] z) → addBulletNotAim(this, 对象, x, y, z, 编号, 弹体动作, 参数)。
static bool is_create1(Context& c){
 if(!active(c)||rd<uint32_t>(c,c.r[0])!=IS_VT1)return false;
 uint32_t act=c.r[0],obj=c.r[1],id=c.r[2],x=c.r[3],sp=c.r[13],y=rd<uint32_t>(c,sp),z=rd<uint32_t>(c,sp+4u);
 uint32_t bullet_action=0u,param=0u;
 switch(id){
  case 50u:case 56u:case 105u:case 111u:case 117u:case 124u:case 130u:case 136u:bullet_action=IS_ACT_S;param=30u;break;
  case 60u:bullet_action=IS_ACT_L;break;
  case 64u:bullet_action=IS_ACT_SP;break;
  case 72u:case 73u:{const uint32_t stack[4]={z,id,0xffffffffu,0xffffffffu};
   msd_guest_call_stack(c,IS_FALLOUT,act,obj,x,y,stack,4u,nullptr);break;}
  default:break;
 }
 if(bullet_action){
  const uint32_t stack[4]={z,id,bullet_action,param};uint32_t bullet=0u;
  bool done=msd_guest_call_stack(c,IS_NOT_AIM,act,obj,x,y,stack,4u,&bullet);   // 未完成时 bullet 不是弹体（同 l_shot）
  if(done&&bullet&&id==60u){
   int32_t ux=int32_t(rd<float>(c,obj+0x8cu)),half=int32_t(is_call(c,IS_WIDTH,obj));
   int32_t reach=half+int32_t(is_status(c,obj,7u)),dir=rd<uint32_t>(c,obj+0x78u)==0x5au?1:-1;
   wr<int32_t>(c,bullet+0x1cu,ux);wr<int32_t>(c,bullet+0x20u,int32_t(is_status(c,obj,26u)));wr<int32_t>(c,bullet+0x24u,ux+dir*reach);
  }
 }
 c.pc=c.r[14];return true;
}
static Block old_iron_slider_create1;static void iron_slider_create1(Context& c){if(is_create1(c))return;old_iron_slider_create1(c);}
static bool is_create2(Context& c){
 if(!active(c)||rd<uint32_t>(c,c.r[0])!=IS_VT2)return false;
 if(c.r[2]==24u){
  uint32_t sp=c.r[13];const uint32_t stack[4]={rd<uint32_t>(c,sp+4u),24u,IS_ACT_2,40u};
  msd_guest_call_stack(c,IS_NOT_AIM,c.r[0],c.r[1],c.r[3],rd<uint32_t>(c,sp),stack,4u,nullptr);
 }
 c.pc=c.r[14];return true;
}
static Block old_iron_slider_create2;static void iron_slider_create2(Context& c){if(is_create2(c))return;old_iron_slider_create2(c);}
HOOK(iron_slider_summon,0x101de225u,
 if(active(c)&&c.r[14]==0x101bdaddu){uint32_t child=is_status(c,c.r[0],40u);if(child>=U&&record(c,child))c.r[1]=child;})
HOOK(iron_slider_offset,0x101de193u, if(active(c)&&(c.r[14]==0x101bdb0bu||c.r[14]==0x101996a9u))c.r[2]=0u;)
static bool is_rocket(Context& c){
 if(!active(c)||c.r[0]!=IS_ACT_L)return false;
 uint32_t act=c.r[0],b=c.r[1],state=c.r[2];
 if(state==60u||state==140u||state==200u){is_effect(c,act,b,20,20,0xff03u);is_call(c,IS_KILL,b);c.pc=c.r[14];return true;}
 if(state!=40u)return false;   // 20：原生（升出舞台上沿后进入 40）
 if(c.r[3]==0u){
  const float top=-15.0f;   // MSA：舞台上沿 65 − 80
  float x=rd<float>(c,b+0x8cu);
  wr<float>(c,b+0x90u,top);wr<float>(c,b+0x98u,top);
  is_call(c,IS_SET_ANIM,b,61u,0u,1u);
  bool right=rd<uint32_t>(c,b+0x78u)==0x5au;
  int32_t limit=rd<int32_t>(c,b+0x24u);
  uint32_t team=rd<uint32_t>(c,b+0x70u)&1u,t=rd<uint32_t>(c,IS_MANAGER+0x38u+(team^1u)*4u);
  float tx=float(limit),ty=0.0f;bool aimed=false;
  if(t){
   float ex=rd<float>(c,t+0x8cu),half=float(int32_t(is_call(c,IS_WIDTH,t)));
   if(right?ex-half<=float(limit):ex+half>=float(limit)){
    tx=ex;ty=float(int32_t(rd<float>(c,t+0x90u))-(int32_t(is_call(c,IS_HEIGHT,t))>>1));aimed=true;
   }
  }
  if(!aimed){
   uint32_t stage=is_call(c,IS_STAGE,0u);
   ty=stage?float(int32_t(is_call(c,IS_ALTITUDE,stage,uint32_t(limit),1u))):0.0f;
  }
  uint32_t raw=is_call(c,IS_ATAN,uint32_t(int32_t(tx-x)),uint32_t(int32_t(ty-top))),a=raw&0xfffu;
  if(right)a=(raw&0xc00u)==0x800u?0xc00u:(a<0x400u?a:0x400u);
  else a=a>0xc00u?0xc00u:(a>0x400u?a:0x400u);
  float speed=rd<float>(c,b+0x138u);if(!(speed>0.0f))speed=20.0f;
  float vx=float(int32_t(is_call(c,IS_COS,a)))*(1.0f/4096.0f)*speed,vy=float(int32_t(is_call(c,IS_SIN,a)))*(1.0f/4096.0f)*speed;
  msd_guest_call(c,IS_MOVE_X,b,l_bits(vx),0u,0xffffffffu,nullptr);
  msd_guest_call(c,IS_MOVE_Y,b,l_bits(vy),0u,0xffffffffu,nullptr);
 }else{
  int32_t start=rd<int32_t>(c,b+0x1cu),dist=rd<int32_t>(c,b+0x20u),x=int32_t(rd<float>(c,b+0x8cu));
  if(std::abs(start-x)>=dist){is_effect(c,act,b,20,20,0xff03u);is_call(c,IS_KILL,b);}
 }
 c.pc=c.r[14];return true;
}
static Block old_iron_slider_rocket;static void iron_slider_rocket(Context& c){if(is_rocket(c))return;old_iron_slider_rocket(c);}
static bool is_missile(Context& c){
 if(!active(c)||c.r[0]!=IS_ACT_SP)return false;
 uint32_t state=c.r[2];if(state!=60u&&state!=140u&&state!=200u)return false;
 is_effect(c,c.r[0],c.r[1],0,20,103u);is_call(c,IS_KILL,c.r[1]);c.pc=c.r[14];return true;
}
static Block old_iron_slider_missile;static void iron_slider_missile(Context& c){if(is_missile(c))return;old_iron_slider_missile(c);}
static void is_spawn(Context& c,uint32_t child,uint32_t obj){
 uint32_t base=is_call(c,IS_TEAM_UNITS,IS_MANAGER,rd<uint32_t>(c,obj+0x70u),0u);   // 队伍单位链表首项为据点
 if(rd<int32_t>(c,obj+0x308u)>0||(base&&rd<int32_t>(c,base+0x308u)<=0))is_call(c,IS_RESERVE,child,100u,0u);
}
HOOK(iron_slider_spawn,0x101bdaddu, if(active(c)&&c.r[0]&&is_class(c,c.r[4])==IS_VT1)is_spawn(c,c.r[0],c.r[4]);)
HOOK(iron_slider_handoff,0x101bddc5u, if(active(c)&&is_class(c,c.r[4])==IS_VT1){is_call(c,IS_RESERVE,c.r[4],140u,0u);c.pc=0x101bddcbu;return;})
static void is_giant(Context& c){
 if(!active(c)||c.r[0]!=IS_ACT_2||c.r[2]!=40u)return;
 uint32_t b=c.r[1],t=rd<uint32_t>(c,IS_MANAGER+0x38u+((rd<uint32_t>(c,b+0x70u)&1u)^1u)*4u);
 float vy=rd<float>(c,b+0xa8u);
 if(!t||!(vy>0.0f))return;
 uint32_t stage=is_call(c,IS_STAGE,0u);
 float tx=rd<float>(c,t+0x8cu),x=rd<float>(c,b+0x8cu),y=rd<float>(c,b+0x90u);
 float ground=stage?float(int32_t(is_call(c,IS_ALTITUDE,stage,uint32_t(int32_t(tx)),1u))):rd<float>(c,t+0x90u),ticks=(ground-y)/vy;
 if(!(ticks>=1.0f))return;
 float vx=std::max(-vy,std::min(vy,(tx-x)/ticks));
 msd_guest_call(c,IS_MOVE_X,b,l_bits(vx),0u,0xffffffffu,nullptr);
}
HOOK(iron_slider_giant,0x10177b21u, is_giant(c);)
extern "C" __declspec(dllexport) uint32_t msd_community_iron_slider_version(){return iron_slider_hooks==10u?1u:0u;}
// 高分辨率战场（2026-10-19，MS6 关卡移植 S0）：头部 +172 为自制场景（ID ≥ 138）逐场景的标记字节表，位 0 表示图集按 2 倍精灵比例制作。
// BattleStageBase::drawBack / drawFront 的绘制块（0x1e147c / 0x1e1518）以 s16（BattleStageBase +0x10 的战斗缩放 2.0）作为 drawConv 的
// 横纵缩放，纵向基准 s18（缩放 ×32）与横向镜头偏移 r9 在此前已算好。带标记的场景只把图块缩放减半：1 个图集像素对应 1 个逻辑单位，
// 纵向基准仍为 64，镜头、边界、地形与据点坐标不变。原版场景与未标记的自制场景保持原路径。
static bool stage_hires(Context& c,uint32_t base){
 if(!active(c)||!head(c,172u))return false;
 uint32_t id=rd<uint32_t>(c,base+8u);
 if(id<138u||id>=138u+head(c,68))return false;
 return (rd<uint8_t>(c,head(c,172u)+id-138u)&1u)!=0u;
}
static Block old_stage_back_draw,old_stage_front_draw;static uint32_t stage_scale_hooks=0u;
static void stage_back_draw(Context& c){if(stage_hires(c,c.r[4]))setfs(c,16,fs(c,16)*0.5f);old_stage_back_draw(c);}
static void stage_front_draw(Context& c){if(stage_hires(c,c.r[4]))setfs(c,16,fs(c,16)*0.5f);old_stage_front_draw(c);}
extern "C" __declspec(dllexport) uint32_t msd_community_stage_scale_version(){return stage_scale_hooks==2u?1u:0u;}
// 自制战场的地形跟随（2026-10-20，里世界 4 实机反馈：坡道上被击退的单位只横向位移、偏离地形线，向上坡被推开后可能卡住）。
// 原生 BattleObject::update（0x1dd874）先把待定位置（+0x94 / +0x98）提交为当前位置（+0x8c / +0x90），再按动画脚本的移动参数（op7）
// 推进待定 x；待定 y 只在各单位动作类调用 BattleCommonActions::actionMove 时改为地形高度。多数动作类在受击击退（状态 80）等滑行中
// 不调用，单位在坡道上只横向位移：下坡时悬空，上坡时低于地形；低于地形超过 40 后 actionMove 把前方视为高台而清除移动，单位停在原地。
// 自制场景（ID ≥ 138）中，贴地的单位（当前 y 与所在 x 的地形相差不超过 2，未在下落）本帧有横向待定位移而没有纵向位移时，把待定 y
// 改为待定 x 处的地形高度；单步高差超过 40 时保持原生处理。空中单位、跳跃与下落不受影响，原版场景保持原路径。
static constexpr uint32_t BATTLE_STAGE=0x1097a714u;   // BattleStage::getInstance() 返回的静态对象
static bool custom_stage(Context& c){
 if(!active(c))return false;
 uint32_t base=rd<uint32_t>(c,BATTLE_STAGE+0xcu);if(!base)return false;
 uint32_t id=rd<uint32_t>(c,base+8u);
 return id>=138u&&id<138u+head(c,68);
}
// 与 BattleStage::getAltitude(x,true)（0x1e1c72）相同的计算：x 限制在 [0, +0x18]，按地形点（+0x14，每点 x、y）线性插值并向零取整。
static int32_t stage_altitude(Context& c,int32_t x){
 const uint32_t s=BATTLE_STAGE;
 if(x<0)x=0;
 int32_t w=int32_t(rd<uint32_t>(c,s+0x18u));if(x>=w)x=w;
 if(rd<uint32_t>(c,s+8u)==0x14u&&x>=int32_t(rd<uint32_t>(c,s+0x20u)))return 9999;
 uint32_t q=rd<uint32_t>(c,s+0x14u);
 for(uint32_t i=0;i<8192u;++i,q+=8u){
  int32_t x0=int32_t(rd<uint32_t>(c,q)),x1=int32_t(rd<uint32_t>(c,q+8u));
  if(x0<=x&&x<=x1){
   int32_t y0=int32_t(rd<uint32_t>(c,q+4u)),y1=int32_t(rd<uint32_t>(c,q+12u));
   if(y0==y1)return y0;
   return y0+int32_t(float(x-x0)/float(x1-x0)*float(y1-y0));
  }
 }
 return int32_t(rd<uint32_t>(c,rd<uint32_t>(c,s+0x14u)+4u));
}
static void ground_follow(Context& c){
 uint32_t o=c.r[0];
 if(rd<uint32_t>(c,o)!=head(c,84u)||!rd<uint8_t>(c,o+0x64u)||rd<uint8_t>(c,o+0x117u))return;
 float x0=rd<float>(c,o+0x8cu),x1=rd<float>(c,o+0x94u),y0=rd<float>(c,o+0x90u),y1=rd<float>(c,o+0x98u);
 if(x1==x0||y1!=y0||rd<float>(c,o+0x68u)!=0.0f||!custom_stage(c))return;
 float d=y0-float(stage_altitude(c,int32_t(x0)));if(d>2.0f||d<-2.0f)return;
 float there=float(stage_altitude(c,int32_t(x1)));d=there-y0;if(d>40.0f||d<-40.0f)return;
 wr<float>(c,o+0x98u,there);
}
// 出兵高度：原生 BattleObjectManager::createUnit（0x1df344）把新单位放在据点前缘（据点 x ± (据点宽 − 单位宽) ∓ 2），y 直接取据点的 y。
// 自制场景中，据点在地面且单位的起始处理没有另行设定高度时，y 改为出兵点的地形高度（据点前后不平坦的战场不再把单位放进地形之下）。
static void spawn_ground(Context& c){
 uint32_t u=c.r[4],k=c.r[7];
 if(!k||rd<uint32_t>(c,u)!=head(c,84u)||!custom_stage(c))return;
 float ky=rd<float>(c,k+0x90u);
 if(rd<float>(c,u+0x90u)!=ky||rd<float>(c,u+0x98u)!=ky)return;
 float d=ky-float(stage_altitude(c,int32_t(rd<float>(c,k+0x8cu))));if(d>2.0f||d<-2.0f)return;
 int32_t a=stage_altitude(c,int32_t(rd<float>(c,u+0x8cu)));
 wr<float>(c,u+0x90u,float(a));wr<float>(c,u+0x98u,float(a));
 if(int32_t(rd<uint32_t>(c,u+0x3e0u))==int32_t(ky))wr<uint32_t>(c,u+0x3e0u,uint32_t(a));
}
// 子单位高度：原生 BattleObject::createChildObject(UnitID,int,int,int,bool)（0x1de224）把子单位放在父对象 x ± dx、y + dy（dy 为
// 第 5 个参数，位于栈 +16）。正规军运兵车（UnitID 396，BattleAction_TruckSlug::update 0x194446）放兵时 dx 为车宽 + 45、dy 为 0，
// 步兵直接取车的高度；车在坡道上时放兵点的地形可能比车高出 40 以上，步兵此后每一步都被 actionMove 视为高台而停在原地。
// 自制场景中，父对象为该动作类（动作对象 +0x58 的虚表为 BattleAction_TruckSlug，0x1092dbc0）、在地面且 dy 为 0 时，把子单位的 y 改为
// 其所在 x 的地形高度。其他放兵单位的动作类自行处理（例如修筑类在创建后再移动子单位的 x），不经此改写。
// 原生写入位置与返回在同一块中（0x1de248 方向非 90、0x1de252 方向 90），此处在原块执行之后改写。
static constexpr uint32_t TRUCK_SLUG_VTABLE=0x1092dbc0u;
static void child_ground(Context& c,uint32_t child,uint32_t parent,uint32_t dy){
 if(!child||dy||rd<uint32_t>(c,child)!=head(c,84u)||!custom_stage(c))return;
 uint32_t action=rd<uint32_t>(c,parent+0x58u);if(!action||rd<uint32_t>(c,action)!=TRUCK_SLUG_VTABLE)return;
 float py=rd<float>(c,parent+0x90u);
 float d=py-float(stage_altitude(c,int32_t(rd<float>(c,parent+0x8cu))));if(d>2.0f||d<-2.0f)return;
 if(rd<float>(c,child+0x90u)!=py)return;
 float a=float(stage_altitude(c,int32_t(rd<float>(c,child+0x8cu))));
 wr<float>(c,child+0x90u,a);wr<float>(c,child+0x98u,a);
}
static Block old_ground_follow_update,old_spawn_ground_height,old_child_left,old_child_right;static uint32_t ground_follow_hooks=0u;
static void ground_follow_update(Context& c){ground_follow(c);old_ground_follow_update(c);}
static void spawn_ground_height(Context& c){spawn_ground(c);old_spawn_ground_height(c);}
static void child_left(Context& c){uint32_t ch=c.r[0],pa=c.r[4],dy=rd<uint32_t>(c,c.r[13]+16u);old_child_left(c);child_ground(c,ch,pa,dy);}
static void child_right(Context& c){uint32_t ch=c.r[0],pa=c.r[4],dy=rd<uint32_t>(c,c.r[13]+16u);old_child_right(c);child_ground(c,ch,pa,dy);}
extern "C" __declspec(dllexport) uint32_t msd_community_ground_follow_version(){return ground_follow_hooks==4u?1u:0u;}
// 效果贴地（ground_hugging_effect，标记 32768，ZSpec 字 42 = 效果动作号 + 1；2026-10-21 辣椒僵尸的火焰在坡道上穿地）。
// 原生 BattleCommonActions::addEffectImpl（0x181c1e）把脚本 op12 的效果放在单位 x ± dx、y + dy，横向排开的火焰带因此是一条
// 位于单位高度的水平线。绘制路径：BattleObject::draw（0x1ddd00）→ 效果默认动作 BattleEffectDefault::draw（0x16f990：r1 对象、
// r2 精灵、r3 世界 x，栈 [0] 世界 y、[4] / [8] 镜头 x / y）→ BattleSprite::drawImpl（0x1db920）逐分件调用 GraphicsOpt::drawConv
// （0x1dbab6 起的块设置参数：r2 / r3 为分件原点的屏幕 x / y 浮点位，栈 [0] 为 C_CONV（短整数：矩形 x、y、宽、高，锚点 x、y，
// 翻转标志，图像号），[4] 为横向比例，[16] 为翻转方式）。带此标记的单位所生成、当前动作号为该槽的效果，在 drawConv 之前把各分件的
// y 平移 地形高度（分件中心的世界 x 处，BattleStage::getAltitude 同算法）− 效果的世界 y，分件铺在所在位置的地表上。
// 只改绘制，不写客体内存（对象坐标、攻击框、回滚快照不变）；动作浏览中按原样绘制。
static constexpr uint32_t Z_GROUND_EFFECT=32768u;
static uint32_t hug_sprite=0u;static int32_t hug_y=0,hug_camera=0;
static void hug_effect_begin(Context& c){
 hug_sprite=0u;
 uint32_t obj=c.r[1];
 if(!active(c)||!head(c,168u)||!obj||z_viewer(c))return;
 uint32_t uid=rd<uint32_t>(c,obj+0x128u);if(!record(c,uid))return;
 uint32_t s=rd<uint32_t>(c,head(c,168u)+(uid-U)*4u);
 if(!s||!(zw(c,s,0)&Z_GROUND_EFFECT)||rd<uint32_t>(c,obj+0xc4u)+1u!=zw(c,s,42))return;
 if(!rd<uint32_t>(c,BATTLE_STAGE+0x14u)||!rd<uint32_t>(c,BATTLE_STAGE+0x18u))return;
 hug_sprite=c.r[2];hug_y=int32_t(rd<uint32_t>(c,c.r[13]));hug_camera=int32_t(rd<uint32_t>(c,c.r[13]+4u));
}
static void hug_effect_part(Context& c){
 if(!hug_sprite||c.r[4]!=hug_sprite)return;
 uint32_t sp=c.r[13],conv=rd<uint32_t>(c,sp);
 uint32_t flip=rd<uint32_t>(c,sp+16u)^uint32_t(int32_t(rd<int16_t>(c,conv+12u)));
 float sx=rd<float>(c,sp+4u);if(flip&1u)sx=-sx;if(flip&8u)sx=-sx;
 float x,y;std::memcpy(&x,&c.r[2],4);std::memcpy(&y,&c.r[3],4);
 float cx=x+sx*(float(rd<int16_t>(c,conv+4u))*0.5f-float(rd<int16_t>(c,conv+8u)));
 int32_t a=stage_altitude(c,int32_t(std::floor(cx))+hug_camera);if(a==9999)return;
 y+=float(a-hug_y);std::memcpy(&c.r[3],&y,4);
}
static Block old_hug_effect_draw,old_hug_effect_conv,old_hug_effect_done;static uint32_t hug_effect_hooks=0u;
static void hug_effect_draw(Context& c){hug_effect_begin(c);old_hug_effect_draw(c);}
static void hug_effect_conv(Context& c){old_hug_effect_conv(c);hug_effect_part(c);}
static void hug_effect_done(Context& c){hug_sprite=0u;old_hug_effect_done(c);}
extern "C" __declspec(dllexport) uint32_t msd_community_ground_effect_version(){return hug_effect_hooks==3u?1u:0u;}
// 伞兵落地时，原生动作固定生成 UnitID 45；社区映射保留其正规军身份。投出子单位的生命分档单位同样经此映射（落地映射表登记子单位）。
HOOK(paratrooper_landing,0x101de225u, uint32_t uid=rd<uint32_t>(c,c.r[0]+0x128u);uint32_t p=record(c,uid);if(p&&(rd<uint32_t>(c,p+4u)==160u||z_throws(c,c.r[0]))&&c.r[1]==45u&&head(c,100)){uint32_t target=rd<uint32_t>(c,head(c,100)+(uid-U)*4u);if(target)c.r[1]=target;})
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
// 自定义音效（M6）：头部 +152 为 1032 项的 SoundID → 24 字节音效记录指针表（宿主只为原生表中不存在的 SoundID 写入），
// +156 为登记数。原生音效缓存与引用计数数组（app+0x9b30、app+0xab54）按 SoundID 0..1031 定址，扩展 ID 位于该范围内。
HOOK(extension_music,0x101c6625u,
 if(c.r[1]==1031u&&rd<uint32_t>(c,0x1ffec000u)==0x45585431u){
  uint32_t bank=rd<uint32_t>(c,0x1ffec004u);if(bank){ret(c,bank);return;}
 }
 if(active(c)&&head(c,152)&&c.r[1]<1032u){
  uint32_t entry=rd<uint32_t>(c,head(c,152)+c.r[1]*4u);if(entry){ret(c,entry);return;}
 })
extern "C" __declspec(dllexport) uint32_t msd_community_sound_version(){return 1u;}
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
void msd_flame_netplay_state(StateIO& io){         // 联机回滚：喷火击退记录属于战斗状态（netplay.h）
 io.field(flame_marks);io.field(flame_mark_count);io.field(flame_owners);io.field(flame_owner_count);
}
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
// 多页单位图标（M1b）：页 0/1 为原版 unit_icon_01/02（菜单图像 33/34），页 2 起为社区图标页。
// 头部 +120 为页表、+124 为页数、+128 为扩展 ConvUnitIcon 地址；每页 16 字节：+0 文件名、+4 菜单纹理 Image*（宿主创建与释放）、
// +8 保留、+12 标记（位 0 菜单请求）。头部 +132 为战斗面板共用的页 ImageDesc，+136 为其中当前载入的页号（无为 0xffffffff）。
static uint32_t icon_page_entry(Context& c,int32_t page){
 if(!active(c)||page<2||uint32_t(page-2)>=head(c,124u)||!head(c,120u))return 0u;
 return head(c,120u)+uint32_t(page-2)*16u;
}
// GraphicsOpt::drawConv(Image**,…,const C_CONV*,…)：任务绘制共用的单矩形入口，按矩形 +0xe 的页号取 images[page]。
// 各场景把 unit_icon_01/02 载入不同的菜单图像槽（主菜单 33/34、编队 25/26），故以矩形本身判定：
// 矩形位于扩展 ConvUnitIcon（头部 +128）的社区段且页号 ≥2 时，把基址改到页表，使 images[page] 取得该页纹理。
// 纹理尚未创建时登记请求并跳过本次绘制，宿主在下一帧前创建。
static void icon_page_draw(Context& c){
 uint32_t conv=rd<uint32_t>(c,c.r[13]),table=head(c,128u);
 if(!active(c)||!table||conv<table+340u*16u||conv>=table+(340u+head(c,4u))*16u)return;
 int32_t page=rd<int16_t>(c,conv+14u);
 uint32_t e=icon_page_entry(c,page);
 if(!e)return;
 if(rd<uint32_t>(c,e+4u)){c.r[1]=e+4u-uint32_t(page)*4u;return;}
 wr<uint32_t>(c,e+12u,rd<uint32_t>(c,e+12u)|1u);
 c.pc=c.r[14];
}
static Block old_icon_page_draw_hook;
static void icon_page_draw_hook(Context& c){
 icon_page_draw(c);
 if(c.pc==c.r[14])return;
 old_icon_page_draw_hook(c);
}
// BattlePlayerOperator::createGrahics 的出兵格头像循环（块 0x101dacbc）：源图为 unit_icon_02 的 ImageDesc（fp）。
// 页号 ≥2 的社区单位改用共用的页 ImageDesc（头部 +132），+136 记录其中当前载入的页号。所需页未载入时调用
// ImageDesc::readFileFromOBM（其内部 create 先释放上一页像素，同一时刻只占一页内存）并返回循环头 0x101dacaa
// 重新取同一格（循环头只依赖被调用者保存的寄存器）。页图集在加载时已校验存在与格式。宿主在下一帧释放该 ImageDesc。
static bool battle_icon_source(Context& c,uint32_t rect){
 int32_t page=rd<int16_t>(c,rect+14u);
 uint32_t e=icon_page_entry(c,page),desc=head(c,132u);if(!e||!desc)return false;
 if(head(c,136u)==uint32_t(page)){if(rd<uint32_t>(c,desc))c.r[11]=desc;return false;}
 wr<uint32_t>(c,H+136u,uint32_t(page));
 c.r[0]=desc;c.r[1]=rd<uint32_t>(c,e);c.r[14]=0x101dacabu;c.pc=0x101c3badu;
 return true;
}
extern "C" __declspec(dllexport) uint32_t msd_community_icon_pages_version(){return 1u;}
// 保留强化武器（行为 retained_special_weapon）：返回 UnitID 对应的角色类（原版十类角色为其自身 UnitID）；
// 社区单位在逐单位行为标记（头部 +116）位 1 置位时取其基准 UnitID（行为库限定为这十类）；其他单位返回 0。
uint32_t msd_retained_class(Context& c,uint32_t uid){
 switch(uid){
  case 16u:case 17u:case 18u:case 19u:case 96u:case 97u:case 98u:case 99u:case 344u:case 362u:return uid;
  default:break;
 }
 uint32_t p=record(c,uid);
 if(p&&head(c,116u)&&(rd<uint32_t>(c,head(c,116u)+(uid-U)*4u)&2u))return rd<uint32_t>(c,p+4u);
 return 0u;
}
// 诊断计数：保留武器参数组替换次数，头部 +140 社区单位、+144 原版角色（只计数，不影响行为）。
void msd_retained_count(Context& c,uint32_t uid){
 if(!active(c))return;
 uint32_t field=H+(uid>=U?140u:144u);wr<uint32_t>(c,field,rd<uint32_t>(c,field)+1u);
}
extern "C" __declspec(dllexport) uint32_t msd_community_retained_weapon_version(){return 1u;}
// ---------- 自制场景的水花与子弹墙（2026-10-22，MS6 任务 3；核心 r76）----------
// 头部 +184：自制场景（ID 138 起，manifest['stages'] 顺序）逐场景的效果记录指针表（宿主 install_scene_fx），无此类场景时为 0。记录 20 个字：
//  0 标记（位 0 水花，位 1 子弹墙）；1–4 水花左界、右界、起水高度、画线；5–8 水花颜色 r、g、b 与染色强度（float）；
//  9 已建立 WaterFunc 的场景对象；10–17 WaterFunc 存储（0x20 字节）；18 子弹墙多边形数；19 多边形数据（每个：点数 n，再 n 对 x、y）。
// 水花：原生水面场景（BattleStage1_3、2_4、3_1、5_1_2 等）在构造时建 WaterFunc（共用效果 402 的精灵），setup 中 waterSetup(2.0, 左界, 右界,
// 起水高度, 画线)，drawFront 末尾 waterDraw(镜头 x, 帧)：按每个地面单位的 x 画 7 帧水花（宽单位画多处），只画 y 不小于起水高度的单位，纵向
// 位置固定为画线。自制场景为通用 BattleStageBase（update 0x1e13c2，drawFront 0x1e14c4，析构 0x1e1398）。setup 时 BattleSpriteFactory
// 尚不能分配精灵（create 返回 0，waterDraw 不检查而访问空指针），因此在场景第一次 update（对战模拟的一部分，联机双方与回滚重算都会执行）
// 建 WaterFunc 并 waterSetup；在 drawFront 收尾块（0x1e1552）以 GraphicsOpt::setSpriteFog（原生受击闪光所用的精灵染色）把水花染成
// 场景指定的颜色后调用 waterDraw（精灵为 0 时不画），绘制后 resetFog；析构时释放精灵。只改绘制。
// 子弹墙：原生 BattleBullet::update（0x1dd16c）在子弹的待定 y 低于所在 x 的地形时调用弹体动作的 hitGround（虚表 +0x18，参数为地形高度）：
// 多数弹体进入命中 / 落地状态（60 / 61，播放命中或爆炸动画后移除）并停止移动。attackFailed（+0x10）有的弹体为空函数（例：ZombieBrain
// 系的抛射弹），不能用作统一的拦截。带子弹墙的自制场景中，子弹当前位置（+0x8c / +0x90）在墙外而本帧的待定位置（+0x94 / +0x98）进入
// 任一多边形时，同样调用 hitGround，高度取待定 y（子弹停在墙面处）；从墙内发射的子弹不拦截；已移除的子弹（存活标记 +0x64 为 0）跳过。
// 墙不改地形，地面、空降、飞行与产兵单位的移动不受影响；双方子弹同样处理。
static constexpr uint32_t FX_WATER_CTOR=0x101e1708u,FX_WATER_SETUP=0x101e1730u,FX_WATER_DRAW=0x101e1748u,FX_WATER_DTOR=0x101e1580u;
static constexpr uint32_t FX_SET_FOG=0x10137750u,FX_RESET_FOG=0x10137768u;
static uint32_t scene_fx_hooks=0u;
static uint32_t scene_fx(Context& c,uint32_t stage){
 if(!active(c)||!stage||!head(c,184u))return 0u;
 uint32_t id=rd<uint32_t>(c,stage+8u);
 if(id<138u||id>=138u+head(c,68))return 0u;
 return rd<uint32_t>(c,head(c,184u)+4u*(id-138u));
}
static void fx_water_release(Context& c,uint32_t r){
 if(rd<uint32_t>(c,r+36u)){msd_guest_call(c,FX_WATER_DTOR,r+40u,0u,0u,0u,nullptr);wr<uint32_t>(c,r+36u,0u);}
}
static void fx_update_begin(Context& c){
 uint32_t st=c.r[0],r=scene_fx(c,st);
 if(!r||!(rd<uint32_t>(c,r)&1u)||(rd<uint32_t>(c,r+36u)==st&&rd<uint32_t>(c,r+44u)))return;
 if(rd<uint32_t>(c,r+36u)==st)fx_water_release(c,r);    // 同一场景对象而精灵未建成（工厂分配失败）时重试；他局遗留的指针不释放
 msd_guest_call(c,FX_WATER_CTOR,r+40u,0u,0u,0u,nullptr);
 const uint32_t stack[2]={rd<uint32_t>(c,r+12u),rd<uint32_t>(c,r+16u)};
 msd_guest_call_stack(c,FX_WATER_SETUP,r+40u,0x40000000u,rd<uint32_t>(c,r+4u),rd<uint32_t>(c,r+8u),stack,2u,nullptr);
 wr<uint32_t>(c,r+36u,st);
}
static Block old_fx_update;static void fx_update(Context& c){fx_update_begin(c);old_fx_update(c);}
static void fx_draw_end(Context& c){
 uint32_t st=c.r[4],g=c.r[7],r=scene_fx(c,st);
 if(!r||!(rd<uint32_t>(c,r)&1u)||rd<uint32_t>(c,r+36u)!=st||!rd<uint32_t>(c,r+44u)||!g)return;
 // 收尾块中 sb = −(镜头 x + 2 × [场景 +0x14])（0x1e14ee、0x1e14f8），由此还原 drawFront 的参数
 uint32_t cam=uint32_t(-int32_t(c.r[9])-int32_t(rd<uint32_t>(c,st+0x14u)<<1));
 const uint32_t alpha[1]={rd<uint32_t>(c,r+32u)};
 msd_guest_call_stack(c,FX_SET_FOG,g,rd<uint32_t>(c,r+20u),rd<uint32_t>(c,r+24u),rd<uint32_t>(c,r+28u),alpha,1u,nullptr);
 msd_guest_call(c,FX_WATER_DRAW,r+40u,cam,rd<uint32_t>(c,st+0x1cu),0u,nullptr);
 msd_guest_call(c,FX_RESET_FOG,g,0u,0u,0u,nullptr);
}
static Block old_fx_draw;static void fx_draw(Context& c){fx_draw_end(c);old_fx_draw(c);}
static void fx_dtor_begin(Context& c){
 uint32_t st=c.r[0],r=scene_fx(c,st);
 if(r&&rd<uint32_t>(c,r+36u)==st)fx_water_release(c,r);
}
static Block old_fx_dtor;static void fx_dtor(Context& c){fx_dtor_begin(c);old_fx_dtor(c);}
static bool fx_inside(Context& c,uint32_t q,uint32_t n,float x,float y){
 bool in=false;
 for(uint32_t i=0,j=n-1u;i<n;j=i++){
  float xi=float(rd<int32_t>(c,q+8u*i)),yi=float(rd<int32_t>(c,q+8u*i+4u)),xj=float(rd<int32_t>(c,q+8u*j)),yj=float(rd<int32_t>(c,q+8u*j+4u));
  if((yi>y)!=(yj>y)&&x<(xj-xi)*(y-yi)/(yj-yi)+xi)in=!in;
 }
 return in;
}
static void fx_bullet_begin(Context& c){
 uint32_t b=c.r[0];
 if(!rd<uint8_t>(c,b+0x64u))return;
 uint32_t r=scene_fx(c,rd<uint32_t>(c,BATTLE_STAGE+0xcu));
 if(!r||!(rd<uint32_t>(c,r)&2u))return;
 float x=rd<float>(c,b+0x94u),y=rd<float>(c,b+0x98u),x0=rd<float>(c,b+0x8cu),y0=rd<float>(c,b+0x90u);
 uint32_t q=rd<uint32_t>(c,r+76u);
 for(uint32_t k=0,count=rd<uint32_t>(c,r+72u);k<count;++k){
  uint32_t n=rd<uint32_t>(c,q);
  if(fx_inside(c,q+4u,n,x,y)&&!fx_inside(c,q+4u,n,x0,y0)){
   uint32_t act=rd<uint32_t>(c,b+0x58u);
   if(act)msd_guest_call(c,rd<uint32_t>(c,rd<uint32_t>(c,act)+0x18u),act,b,0u,uint32_t(int32_t(y)),nullptr);
   return;
  }
  q+=4u+8u*n;
 }
}
static Block old_fx_bullet;static void fx_bullet(Context& c){fx_bullet_begin(c);old_fx_bullet(c);}
extern "C" __declspec(dllexport) uint32_t msd_community_scene_fx_version(){return scene_fx_hooks==4u?1u:0u;}
// 行为库清单（模组 M2）：behavior_library.json 原文，由构建脚本生成 behavior_manifest.inc 嵌入。
#include "behavior_manifest.inc"
extern "C" __declspec(dllexport) const char* msd_behavior_manifest(){return BEHAVIOR_MANIFEST;}
// Generated block overrides and registration are emitted by the build script.
#include "community_blocks.inc"
