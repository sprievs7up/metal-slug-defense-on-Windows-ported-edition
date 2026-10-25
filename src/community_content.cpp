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
static bool wd_guard(Context& c,uint32_t s,uint32_t o);   // 钢铁死亡蠕虫（后文）：不击退（MSA 全部动作 EnableNockBack(false)）
HOOK(zombie_no_knockback,0x1016f485u, uint32_t s=zspec(c,c.r[4]);if(s&&((zw(c,s,0)&2u)||((zw(c,s,0)&2097152u)&&wd_guard(c,s,c.r[4])))){c.pc=0x1016f4a3u;return;})
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
// 建筑损毁效果（structure_death_effect，标记 65536；2026-10-22 能量核心，行为库 v13，基准 4 沙包类）。原生 BattleAction_Donou::update
// 在状态 100 / 110 / 120 播完槽 8（对象 +0xc9 为 0）后以尾调用 BattleObject::kill 移除单位（0x1016d324，r0 为对象）。带此标记的单位
// 在该处先经 BattleCommonActions::addEffect（is_effect，同钢铁哨兵）在原点放共用爆炸 0xff04，再继续原生的移除；MSA EnergyCore1800
// 同样在损毁槽播完后于 (0, 0) 放 0xff04 再移除。原版沙包与其他 Donou 单位不变。嵌套调用建立效果对象，依赖堆导入回调（核心 r77）。
static constexpr uint32_t Z_STRUCTURE_DEATH=65536u;
static Block old_donou_death_kill;static uint32_t structure_death_hooks=0u;
static void donou_death_kill(Context& c){
 uint32_t obj=c.r[0],s=zspec(c,obj);
 if(s&&(zw(c,s,0)&Z_STRUCTURE_DEATH))is_effect(c,rd<uint32_t>(c,obj+0x58u),obj,0,0,0xff04u);
 old_donou_death_kill(c);
}
extern "C" __declspec(dllexport) uint32_t msd_community_structure_death_version(){return structure_death_hooks==1u?1u:0u;}
// 建筑受击光束（structure_hit_attack，标记 524288；2026-10-22 能量核心，行为库 v16，基准 4 沙包类）。原生 BattleAction_Donou::update 的
// 状态 60（受击，槽 7）分支（0x1016d300，r0 为对象）。沙包的攻击组 +0x88 为 0，BattleUnit::attack 按 0 组结算为 0 伤害；带此标记的单位
// 在该处把 +0x88 设为 40（普通攻击组：伤害字 22、击退计量字 23、目标数字 24、属性字 28），并置身体状态 0x20（AttackIDReset，
// BattleObject::changeBodyState 只对 +0x6c 按位或），使槽 7 脚本中每条开启攻击框的 op4 都经 BattleUnit::initAttackStatus 建立新的攻击 ID，
// 框内各目标每次开启各受 1 次伤害。攻击框与伤害时刻由脚本决定，原生沙包与其他 Donou 单位不变。
static constexpr uint32_t Z_STRUCTURE_HIT_ATTACK=524288u;
static Block old_donou_hit;static uint32_t structure_hit_hooks=0u;
static void donou_hit(Context& c){
 uint32_t obj=c.r[0],s=zspec(c,obj);
 if(s&&(zw(c,s,0)&Z_STRUCTURE_HIT_ATTACK)){wr<uint32_t>(c,obj+0x88u,40u);wr<uint32_t>(c,obj+0x6cu,rd<uint32_t>(c,obj+0x6cu)|0x20u);}
 old_donou_hit(c);
}
extern "C" __declspec(dllexport) uint32_t msd_community_structure_hit_attack_version(){return structure_hit_hooks==1u?1u:0u;}
// 飞行护盾（flying_shell，标记 131072；2026-10-22，行为库 v14，基准 200 飞行侵略者类 BattleAction_WingedInvader）。按 MSA 7.13.0
// BattleAction_FlyingShell（UnitID 858 / 860）的做法在 MSD 原生 WingedInvader 上实现（verification/flying_shell_20261022）。
// ZSpec 字 43–52：飞行高度、下落 / 追踪动作、普攻陨石首槽与个数、绝招陨石首槽与个数、绝招落下的倒数、陨石存在 tick、陨石生命百分比、
// 每 tick 转向上限（4096 为一周）。
//  1 WingedInvader::update 首帧定高（0x1017d470，BattleStage::getInstance 返回后，r4 单位）：原生刚写入的飞行高度 +0x1c（30）改为字 43，
//    初始高度与行走中的高度保持随之按字 43 计算（MSA FlyingShell::getGroundHigh：860 / 1080 为 80，858 为 140）。
//  2 WingedInvader::update 入口（r1 单位、r2 状态、r3 为 0 时为该状态的首帧，同原生 setAnimationID 的条件）：状态 50 首帧取前方最近的敌方单位（远攻击距离字 7 + 半宽之内）为落点 x，
//    写入 +0x28（没有时取单位前方该距离处），+0x2c 为字 49 的倒数，之后状态 50 每帧减 1（MSA spAttack：+0x28 / +0x30 = 120）。
//    状态 100–120 首帧在 (−120,−60)、(0,−30)、(90,−100) 放共用爆炸 0xff04；100–140 的其余各帧在 x ∈ [−160,160)、y ∈ (−200,0] 的伪随机
//    位置放 0xff03（MSA FlyingShell::dead）。伪随机数由单位 x、UnitID 与 +0x30 的帧计数求出（不用对象地址：联机两端的地址可能不同），
//    回滚重算与两端的结果相同。
//  3 WingedInvader::shotBullet 中 addBulletNotAim 返回后（0x10180178，r0 弹体、r4 单位）：陨石记录 +0x28 阶段（普攻 1 弧线、绝招 3 升空）、
//    +0x2c 发射时 x、+0x30 存在 tick、+0x34 生命（单位最大生命 +0x304 × 字 51 %）、+0x38 绝招落点 x、+0x3c 落下倒数（单位 +0x2c）、
//    +0x40 投射距离（普攻字 26、绝招字 33；+0x20 由原生随后写入，不用）；目的点 +0x13c 改为 −9999（原生“无目的点”）：原生
//    BattleBullet::update 在弹体越过目的点（addBulletImpl 按单位前方求出）时调用 attackFailed，飞行侵略者类在此预约 60。绝招背面花瓣
//    （脚本 32）的陨石向后上方升起，一生成即越过目的点而爆炸（r79–r85 每次绝招实际只有正面 4 颗）；下落中的陨石越过目的点也会在空中
//    爆炸。陨石的距离与存在时间由本行为判断（核心 r86）。单位菜单的动作演示（z_viewer）中不记录，弹体保持原生处理：
//    演示切换动作时重建精灵，存在时间较长的陨石若留到下一个演示，绘制时取用已释放的图像（实测 drawImageS 访问 0x9 停止）。
//  4 BulletAction_WingedInvader::update 入口（r0 动作、r1 弹体、r2 状态）：陨石改由此处理——状态 60 / 200 放 0xff04 后移除；存在超过字 50 tick
//    预约 60。弧线（1）动画播完（+0xc9 为 0：onEventAnimationStart 置 1，脚本 op21 经 onEventAnimationFinished 置 0）换为字 44 的动作、
//    朝向前方（阶段 2）；追踪（2）每 tick 向最近的敌方单位中心转向（不超过字 52），以弹体速度
//    +0x138 飞行，横向离发射点超过投射距离时预约 60（MSA createMeteo 与其弹体 update）。升空（3）倒数结束时换为字 44 的动作（阶段 4），
//    按 MSA bulletSp_getStartPos 移到起点：bx = 目标 x（+0x38）− 朝向 × rnd(300)，gy = bx 处地面高，k = (gy + 80 + rnd(400)) × √2 / 2，
//    起点 (bx + 朝向 × (300 − k), gy − k)，多在画面上沿之外；之后每 tick 横向朝向 × 弹速、纵向弹速（MSA bulletSp_setFallSpeed），
//    落在 bx + 朝向 × 300 附近（目标前方 0–300）。伪随机数取弹体攻击 ID（+0x144，每颗不同）与发射时 x（核心 r86；r79–r85 取弹体
//    +0x44 的序号，该字段发射后被改写为 0，同一次绝招的陨石落在同一点、起点为落点后上方 200–400，多在画面内）。
//    原生 update 的越过舞台上沿与超出 +0x20 距离的处理不用于陨石。
//  5 BulletAction_WingedInvader::hitGround 入口（r1 弹体）：阶段 1、3 的陨石不处理落地（MSA 860 的陨石换为下落 / 追踪动作后才落地爆炸）。
//  6 BattleBullet::damage 入口（r0 弹体、r3 伤害）：陨石扣生命（阶段 3 不扣，同 MSA 绝招陨石只在下落中受伤），耗尽时预约 60；原生随后返回 1，
//    攻击陨石的敌方弹体按原生消失（陨石挡下攻击，受击框来自陨石脚本的 op3）。
// 陨石与单位的状态只在客体对象内存（动作参数区 +0x10–+0x53 由 clearActionParams 清零），无静态状态。
static constexpr uint32_t FS_FLAG=131072u,FS_BULLET_VPTR=0x1092f210u,FS_MANAGER=0x10977f50u;
static uint32_t flying_shell_hooks=0u;
// 绝招陨石的起点（MSA BattleAction_FlyingShell::bulletSp_getStartPos 与其调用的散布函数）：落点在目标前方 0–FS_RAIN_SPREAD（MSA 860
// 的攻击 4 投射距离 300），起点高出 FS_RAIN_LIFT 与 0–FS_RAIN_HEIGHT 的伪随机量，再向前 FS_RAIN_AHEAD
static constexpr int32_t FS_RAIN_SPREAD=300,FS_RAIN_AHEAD=300;static constexpr float FS_RAIN_LIFT=80.0f;static constexpr uint32_t FS_RAIN_HEIGHT=400u;
static constexpr int32_t FS_NO_DESTINATION=-9999;   // BattleBullet::initialize / update 的“无目的点”值（0xffffd8f1）
static uint32_t fs_unit(Context& c,uint32_t obj){uint32_t s=zspec(c,obj);return s&&(zw(c,s,0)&FS_FLAG)?s:0u;}
static uint32_t fs_bullet(Context& c,uint32_t b){
 if(!active(c)||!head(c,168u)||!b||rd<uint32_t>(c,b)!=FS_BULLET_VPTR)return 0u;
 uint32_t uid=rd<uint32_t>(c,b+0x128u);if(!record(c,uid))return 0u;
 uint32_t s=rd<uint32_t>(c,head(c,168u)+(uid-U)*4u);
 return s&&(zw(c,s,0)&FS_FLAG)?s:0u;
}
static uint32_t fs_hash(uint32_t a,uint32_t b){
 uint32_t h=a*0x9e3779b1u^(b+0x7f4a7c15u)*0x85ebca6bu;h^=h>>15;h*=0x2c1b3c6du;h^=h>>12;h*=0x297a2d39u;h^=h>>15;return h;
}
static void fs_effect(Context& c,uint32_t obj,int32_t x,int32_t y,uint32_t id){is_effect(c,rd<uint32_t>(c,obj+0x58u),obj,x,y,id);}
static void fs_move(Context& c,uint32_t b,float vx,float vy){
 msd_guest_call(c,IS_MOVE_X,b,l_bits(vx),0u,0xffffffffu,nullptr);
 msd_guest_call(c,IS_MOVE_Y,b,l_bits(vy),0u,0xffffffffu,nullptr);
}
static void fs_velocity(Context& c,uint32_t b,uint32_t a,float speed){
 fs_move(c,b,float(int32_t(is_call(c,IS_COS,a&0xfffu)))*(1.0f/4096.0f)*speed,float(int32_t(is_call(c,IS_SIN,a&0xfffu)))*(1.0f/4096.0f)*speed);
}
// 弹体所在位置最近的敌方单位（对方队伍链表，资格同 z_candidate：存活、可作为目标）。单位菜单的动作演示（z_viewer）中战斗管理器的
// 队伍链表不是当前战斗的内容，不查找（取不到目标，陨石保持方向；绝招落点取单位前方远攻击距离处）。
static uint32_t fs_nearest(Context& c,uint32_t b){
 if(z_viewer(c))return 0u;
 uint32_t team=rd<uint32_t>(c,b+0x70u)&1u,head0=rd<uint32_t>(c,FS_MANAGER+(team?0x18u:0x1cu));if(!head0)return 0u;
 float x=rd<float>(c,b+0x8cu),y=rd<float>(c,b+0x90u),bd=0.0f;uint32_t best=0u,e=head0;
 for(uint32_t n=0;n<8192u;++n){
  if(z_candidate(c,e,0x49u)){
   float dx=rd<float>(c,e+0x8cu)-x,dy=rd<float>(c,e+0x90u)-y,d=dx*dx+dy*dy;
   if(!best||d<bd){best=e;bd=d;}
  }
  uint32_t next=rd<uint32_t>(c,e+0x124u);if(!next)break;e=next-0x11cu;if(e==head0)break;
 }
 return best;
}
HOOK(flying_shell_height,0x1017d471u, {uint32_t s=fs_unit(c,c.r[4]);if(s)wr<uint32_t>(c,c.r[4]+0x1cu,zw(c,s,43));})
static void fs_update(Context& c){
 uint32_t obj=c.r[1],state=c.r[2],s=fs_unit(c,obj);bool first=c.r[3]==0u;if(!s)return;
 if(state==50u){
  if(first){
   uint32_t team=rd<uint32_t>(c,obj+0x70u)&1u;
   float ux=rd<float>(c,obj+0x8cu);int32_t dir=rd<uint32_t>(c,obj+0x78u)==0x5au?1:-1;
   int32_t reach=int32_t(is_status(c,obj,7u))+z_width(c,obj),tx=int32_t(ux)+dir*reach;
   uint32_t e=z_viewer(c)?0u:z_nearest_ahead(c,FS_MANAGER,obj,team,0x49u);
   if(e){float ex=rd<float>(c,e+0x8cu),d=ex-ux;if(d<0.0f)d=-d;if(d<=float(reach))tx=int32_t(ex);}
   wr<int32_t>(c,obj+0x28u,tx);wr<uint32_t>(c,obj+0x2cu,zw(c,s,49));
  }else if(rd<int32_t>(c,obj+0x2cu)>0)wr<int32_t>(c,obj+0x2cu,rd<int32_t>(c,obj+0x2cu)-1);
 }else if(state>=100u&&state<=140u){
  if(first&&state<=120u){
   fs_effect(c,obj,-120,-60,0xff04u);fs_effect(c,obj,0,-30,0xff04u);fs_effect(c,obj,90,-100,0xff04u);wr<uint32_t>(c,obj+0x30u,0u);
  }else{
   uint32_t n=rd<uint32_t>(c,obj+0x30u)+1u,h=fs_hash(uint32_t(int32_t(rd<float>(c,obj+0x8cu)))^(rd<uint32_t>(c,obj+0x128u)<<16),n);
   wr<uint32_t>(c,obj+0x30u,n);
   fs_effect(c,obj,int32_t(h%320u)-160,-int32_t((h>>16)%200u),0xff03u);
  }
 }
}
HOOK(flying_shell_update,0x1017d433u, fs_update(c);)
static void fs_shot(Context& c){
 uint32_t b=c.r[0],u=c.r[4],s=b&&!z_viewer(c)?fs_unit(c,u):0u;if(!s)return;
 int32_t anim=int32_t(rd<uint32_t>(c,b+0xc4u));uint32_t phase=0u,dist=0u;
 if(anim>=int32_t(zw(c,s,45))&&anim<int32_t(zw(c,s,45)+zw(c,s,46))){phase=1u;dist=is_status(c,u,26u);}
 else if(anim>=int32_t(zw(c,s,47))&&anim<int32_t(zw(c,s,47)+zw(c,s,48))){phase=3u;dist=is_status(c,u,33u);}
 if(!phase)return;
 wr<uint32_t>(c,b+0x28u,phase);wr<int32_t>(c,b+0x2cu,int32_t(rd<float>(c,b+0x8cu)));wr<uint32_t>(c,b+0x30u,0u);
 wr<int32_t>(c,b+0x34u,int32_t(int64_t(rd<int32_t>(c,u+0x304u))*int64_t(zw(c,s,51))/100));
 wr<int32_t>(c,b+0x38u,rd<int32_t>(c,u+0x28u));wr<int32_t>(c,b+0x3cu,rd<int32_t>(c,u+0x2cu));
 wr<uint32_t>(c,b+0x40u,int32_t(dist)>0?dist:900u);wr<int32_t>(c,b+0x13cu,FS_NO_DESTINATION);
}
HOOK(flying_shell_shot,0x10180179u, fs_shot(c);)
static bool fs_meteor(Context& c){
 uint32_t act=c.r[0],b=c.r[1],state=c.r[2],s=fs_bullet(c,b),phase=s?rd<uint32_t>(c,b+0x28u):0u;
 if(!phase||phase>4u)return false;
 if(state==60u||state==200u){is_effect(c,act,b,0,0,0xff04u);is_call(c,IS_KILL,b);c.pc=c.r[14];return true;}
 uint32_t age=rd<uint32_t>(c,b+0x30u)+1u;wr<uint32_t>(c,b+0x30u,age);
 if(age>zw(c,s,50)){is_call(c,IS_RESERVE,b,60u,0u);c.pc=c.r[14];return true;}
 bool right=rd<uint32_t>(c,b+0x78u)==0x5au;
 float x=rd<float>(c,b+0x8cu),y=rd<float>(c,b+0x90u),speed=rd<float>(c,b+0x138u);if(!(speed>0.0f))speed=6.0f;
 uint32_t homing=zw(c,s,44);
 if(phase==1u&&age>1u&&!rd<uint8_t>(c,b+0xc9u)){
  is_call(c,IS_SET_ANIM,b,homing,0u,1u);wr<uint32_t>(c,b+0x28u,2u);wr<uint32_t>(c,b+0x38u,right?0u:2048u);phase=2u;
 }
 if(phase==2u){
  int32_t gone=int32_t(x)-rd<int32_t>(c,b+0x2cu);if(gone<0)gone=-gone;
  if(gone>rd<int32_t>(c,b+0x40u)){is_call(c,IS_RESERVE,b,60u,0u);c.pc=c.r[14];return true;}
  uint32_t a=rd<uint32_t>(c,b+0x38u)&0xfffu,e=fs_nearest(c,b);
  if(e){
   float ex=rd<float>(c,e+0x8cu),ey=rd<float>(c,e+0x90u)-float(int32_t(is_call(c,IS_HEIGHT,e))>>1);
   uint32_t want=is_call(c,IS_ATAN,uint32_t(int32_t(ex-x)),uint32_t(int32_t(ey-y)))&0xfffu;
   int32_t d=int32_t((want-a)&0xfffu),lim=int32_t(zw(c,s,52));if(d>=2048)d-=4096;
   if(d>lim)d=lim;else if(d<-lim)d=-lim;
   a=uint32_t(int32_t(a)+d)&0xfffu;wr<uint32_t>(c,b+0x38u,a);
  }
  fs_velocity(c,b,a,speed);
 }else if(phase==3u){
  int32_t left=rd<int32_t>(c,b+0x3cu)-1;wr<int32_t>(c,b+0x3cu,left);
  if(left<=0){
   uint32_t h=fs_hash(rd<uint16_t>(c,b+0x144u),rd<uint32_t>(c,b+0x2cu));int32_t dir=right?1:-1;
   int32_t bx=rd<int32_t>(c,b+0x38u)-dir*int32_t(h%uint32_t(FS_RAIN_SPREAD));
   float gy=float(stage_altitude(c,bx)),k=(gy+FS_RAIN_LIFT+float((h>>16)%FS_RAIN_HEIGHT))*0.70710678f;
   float sx=float(bx)+float(dir)*(float(FS_RAIN_AHEAD)-k),sy=gy-k;
   wr<float>(c,b+0x8cu,sx);wr<float>(c,b+0x94u,sx);wr<float>(c,b+0x90u,sy);wr<float>(c,b+0x98u,sy);
   is_call(c,IS_SET_ANIM,b,homing,0u,1u);wr<uint32_t>(c,b+0x28u,4u);
   fs_move(c,b,right?speed:-speed,speed);
  }
 }else if(phase==4u)fs_move(c,b,right?speed:-speed,speed);
 c.pc=c.r[14];return true;
}
static Block old_flying_shell_meteor;static void flying_shell_meteor(Context& c){if(fs_meteor(c))return;old_flying_shell_meteor(c);}
static bool fs_ground(Context& c){
 uint32_t b=c.r[1],s=fs_bullet(c,b),phase=s?rd<uint32_t>(c,b+0x28u):0u;
 if(phase!=1u&&phase!=3u)return false;
 c.pc=c.r[14];return true;
}
static Block old_flying_shell_ground;static void flying_shell_ground(Context& c){if(fs_ground(c))return;old_flying_shell_ground(c);}
static void fs_damage(Context& c){
 uint32_t b=c.r[0],s=fs_bullet(c,b),phase=s?rd<uint32_t>(c,b+0x28u):0u;
 if(!phase||phase==3u||phase>4u)return;
 int32_t hp=rd<int32_t>(c,b+0x34u)-int32_t(c.r[3]);wr<int32_t>(c,b+0x34u,hp);
 if(hp<=0&&rd<uint32_t>(c,b+0x7cu)!=60u)is_call(c,IS_RESERVE,b,60u,0u);
}
HOOK(flying_shell_damage,0x101dcd9du, fs_damage(c);)
extern "C" __declspec(dllexport) uint32_t msd_community_flying_shell_version(){return flying_shell_hooks==6u?1u:0u;}
// ---------- 蜈蚣长老（2026-10-22，行为库 v15：elder_centipede，标记 262144；基准 192 BattleAction_Alien；核心 r80）----------
// MSA 7.13.0 BattleAction_Eldercentipedo（反汇编与对照 verification/elder_centipede_20261022/）在 MSD 原版侵略者类上的实现。
// 动作号为 MSA 脚本号，存于 ZSpec 字 53–76（community_content.py）：53 出土、54 由地下出土、55 待机、56 钻地、57 地下移动、58 喷酸、
// 59 喷酸收尾、60 绝招入地、61 大前行、62 / 63 受击与其循环、64 击退、65 损毁、66 尘土首槽（三槽轮换）、67 圆环节数、
// 68 / 69 地面攻击弹体、70 / 71 飞沫首槽与个数、72 飞沫溅射、73 / 74 绝招酸块与其命中、75 绝招泥土、76 地面尘土。
//  1 Alien::update 入口（0x1019b045，r0 动作、r1 单位、r2 状态、r3 本状态帧数，0 为首帧）：按 MSA update 处理，不进入原生。
//    出击后先出土（MSA startPosition 置状态 78），播完待机并预约状态 10；10 待机（在地下时先出土）；20 钻地后在地下移动（高度取
//    地形）；30 / 40 出土、喷酸、收尾后进入攻击等待；50 入地后大前行：每 tick 角度按朝向加 32（4096 为一周），圆环各节绕单位前方
//    280 处转动（MSA getSpAttackPartsPos：位置 = 单位 + 2 ×（±140 + 节偏移按角度旋转）），节越过地面处生成地面攻击弹体
//    （createSpAttackGroundEffect），头部在地面以上且未过半周时单位的攻击框跟随头部（spAttackHitRect，40×40 精灵单位），转满一周后
//    出土；80（MSD 击退）播放击退动作 70（MSA 状态 70）；70 播放受击动作 60 / 65（MSA 状态 80）；100–140 损毁（在地下时先出土），播完
//    移除。地面以上的状态每 10 tick 在脚下地面放一团尘土（MSA createSmoke）；钻地与出土期间不能发动绝招（MSA spAttackDisable）。
//    动作切换在本函数末尾以尾调用交给原生 setAnimationID：脚本第一 tick 的音效（动作 50 经泥土 132、70、75）在客体流程中照常播放
//    （嵌套调用遇到音效导入会中止）。
//    圆环各节为大前行动作的 op11 子层（MSA 不建立对象，由 drawSpAttack 绘制）：每 tick 按角度写入子层偏移 +0x20/+0x24（精灵单位，
//    原画坐标：原画朝左（精灵 +0x48 为 270）时前方为 −x，偏移为 −(140 + 旋转后的横向偏移)）、旋转 +0x2c（节脚本 op2 的角度减去
//    圆环角度）与缩放 +0x30/+0x34（隐藏的节为 0）；前 21 tick
//    只画头部一侧 13 节，过半周后不画最前的 7 节（同 MSA）。生成脚本把大前行动作中各节的 op11 横向偏移写为角度 0 时的原画坐标
//    （角度 0 时的位置，切换动作的那一 tick 已在正确位置），本函数据此还原 MSA 的节偏移表（MSA 0x467c474，26 项）。
//    攻击框：首次进入地面以上时以 onEventSetAttackRect 设定（其中 BattleUnit::initAttackStatus 重置命中记录），之后只改写矩形
//    字段 +0xdc–+0xe8，同一次大前行中头部对同一目标只结算一次（MSA 每 tick 重设，其命中记录的处理未能对应，按此实施）。
//  2 Alien::shotBullet 入口（0x1017f74d，r2 弹体脚本、r3 x、栈 [0] y）：地面攻击 18 / 20 以绝招组（MSA shotBullet 以 0x32）、飞沫
//    35–42 以普攻组（MSA 0x4c40430 以 0x28）经 addBulletNotAim 发射，弹体动作为原生侵略者弹体（BulletAction_Alien，0x109606b0）。
//    地面攻击贴地，动作号字段 +0xc4 写 20，使原生 attackAction 走“只结算伤害、不消失”的分支（范围内多个目标，同一弹体对同一目标一次）。
//    其余脚本不发射。
//  3 BulletAction_Alien::update 入口（0x1019afc3）：本单位的弹体（+0x28：1 地面攻击、2 飞沫、3 绝招酸块、4 酸块命中）：地面攻击播完移除；
//    飞沫命中（60）、落地（59）或贴地时在原处放溅射 43 后移除，动画结束移除；酸块命中或落地时停住并换为命中动作，播完移除。
//  4 BulletAction_Alien::attackAction 入口（0x1017747b）：飞沫与酸块改走 BattleBulletDefault::attackAction（结算伤害后预约 60）。
//  5 BattleUnitDefault::createObject 入口（0x10181ec5）：绝招泥土 132 的位置按圆环角度旋转并移到单位前方 280 处（改写参数后交给
//    原生，泥土的音效照常），同处发射一个酸块 116（绝招组），以 5 的速度飞向圆环中心（MSA createSpAttackBullet）；地面尘土 19 的高度
//    取地形（MSA createObject 19）。单位菜单的动作演示中不发射酸块。
//  6 BattleUnitDefault::draw 入口（0x1016f891）：本单位的绘制按地面裁切（MSA 0x10e0728 / 0x10e0838，原生 BattleAction_Daimanji::draw
//    同理）：当前裁切与地面以上（战斗中为地形高度，单位菜单的动作演示中为单位脚下）取交集 → 原生绘制 → 恢复原裁切。GL 调用须在
//    客体流程中执行，以三个延续块串接（7–9）：入口改为调用 GraphicsOpt::setClip、返回地址为延续块 1；延续块 1 恢复参数执行原生绘制、
//    返回地址为延续块 2；延续块 2 恢复原裁切（setClip 或 clearClip）、返回地址为延续块 3；延续块 3 返回原调用者。延续块地址为 Thumb 32 位指令的后半字
//    （0x1016f89f、0x101358c3、0x101358c9），原生代码不会跳到这些地址，登记前确认其上没有原生块。
// 单位与弹体的状态只在客体对象内存：单位 +0x24 圆环角度（按朝向累加）、+0x28 剩余角度、+0x2c 过半周、+0x30 尘土倒数、+0x34 尘土
// 序号、+0x38 标记（1 已出土、2 不能发动绝招）、+0x3c 大前行 tick（+0x1c–+0x43 不随状态切换清零，生成时由 clearActionParams 清零）；
// 弹体 +0x28 种类、+0x2c 存在 tick。绘制延续块的保存区为静态变量（只在一次绘制内使用，不属于对战模拟）。
static constexpr uint32_t EC_FLAG=262144u,EC_BULLET_ACTION=0x109606b0u,EC_MAX_PARTS=32u;
static constexpr uint32_t EC_START_WAIT=0x10179180u,EC_ACTION_MOVE=0x10178b40u,EC_DONT_SP=0x10177f68u,EC_SET_ATTACK=0x101ddaa6u,
 EC_DEFAULT_ATTACK=0x10175e05u,EC_ADJUST_GROUND=0x1019af50u,EC_GRAPHICS=0x1016c040u,EC_SET_CLIP=0x101358c1u,EC_CLEAR_CLIP=0x1013593fu;
static constexpr uint32_t EC_V1=0x1016f89fu,EC_V2=0x101358c3u,EC_V3=0x101358c9u;
static uint32_t elder_centipede_hooks=0u;
static uint32_t ec_unit(Context& c,uint32_t o){uint32_t s=o?zspec(c,o):0u;return s&&(zw(c,s,0)&EC_FLAG)?s:0u;}
static uint32_t ec_bullet_spec(Context& c,uint32_t b){
 if(!active(c)||!head(c,168u)||!b||rd<uint32_t>(c,b)!=FS_BULLET_VPTR)return 0u;
 uint32_t uid=rd<uint32_t>(c,b+0x128u);if(!record(c,uid))return 0u;
 uint32_t s=rd<uint32_t>(c,head(c,168u)+(uid-U)*4u),k=rd<uint32_t>(c,b+0x28u);
 return s&&(zw(c,s,0)&EC_FLAG)&&k>=1u&&k<=4u?s:0u;
}
static int32_t ec_sign(Context& c,uint32_t o){return rd<uint32_t>(c,o+0x78u)==0x10eu?-1:1;}
static int32_t ec_ground(Context& c,uint32_t o,int32_t x){return z_viewer(c)?int32_t(rd<float>(c,o+0x90u)):stage_altitude(c,x);}
struct EcTrig{float co,si;};
static EcTrig ec_trig(Context& c,uint32_t a){return {float(int32_t(is_call(c,IS_COS,a&0xfffu))),float(int32_t(is_call(c,IS_SIN,a&0xfffu)))};}
// btl::Vector2f::rotate（MSA 0xd6a7dc）：(x cos − y sin, x sin + y cos) / 4096，角度 4096 为一周
static void ec_rotate(const EcTrig& t,float x,float y,float& rx,float& ry){rx=(x*t.co-y*t.si)*(1.0f/4096.0f);ry=(x*t.si+y*t.co)*(1.0f/4096.0f);}
struct EcPart{uint32_t script;int32_t prio,x,y;};
static int32_t ec_art(Context& c,uint32_t sprite){return rd<uint32_t>(c,sprite+0x48u)==0x10eu?-1:1;}   // 原画朝向（精灵 +0x48；+0x10 为当前朝向）：朝左 −1
// 大前行动作脚本中前 n 条 op11（圆环各节，横向偏移为角度 0 时的原画坐标 ±(140 − 节偏移)）：返回 MSA 节偏移表
static uint32_t ec_parts(Context& c,uint32_t o,uint32_t s,EcPart* out){
 uint32_t sprite=rd<uint32_t>(c,o+0x5cu),desc=sprite?rd<uint32_t>(c,sprite+0x40u):0u,anim=zw(c,s,61);
 if(!desc||anim>=rd<uint32_t>(c,desc+0x1cu))return 0u;
 uint32_t sc=rd<uint32_t>(c,rd<uint32_t>(c,desc+0x18u)+anim*4u),want=std::min(zw(c,s,67),EC_MAX_PARTS),n=0u,pos=0u;
 for(uint32_t k=0;k<1024u&&n<want;++k){
  uint32_t op=rd<uint32_t>(c,sc+pos*4u);if(op>23u||op==5u||op==21u)break;
  if(op==11u)out[n++]={rd<uint32_t>(c,sc+pos*4u+4u),rd<int32_t>(c,sc+pos*4u+8u),140-ec_art(c,sprite)*rd<int32_t>(c,sc+pos*4u+12u),rd<int32_t>(c,sc+pos*4u+16u)};
  pos+=Z_LEN[op];
 }
 return n;
}
// MSA getSpAttackPartsPos：单位 + 2 ×（±140 + 旋转((∓x), y)），a 为按朝向累加的角度
static void ec_part_pos(Context& c,uint32_t o,const EcPart& p,const EcTrig& t,float& wx,float& wy){
 int32_t sg=ec_sign(c,o);float rx,ry;ec_rotate(t,float(-sg*p.x),float(p.y),rx,ry);
 wx=rd<float>(c,o+0x8cu)+2.0f*(float(sg*140)+rx);wy=rd<float>(c,o+0x90u)+2.0f*ry;
}
// addBulletNotAim / addEffect / createObject 的横向参数为朝向坐标（前方为正，放置时乘单位朝向）
static uint32_t ec_fire(Context& c,uint32_t act,uint32_t o,uint32_t script,uint32_t kind,uint32_t state,int32_t x,int32_t y){
 const uint32_t stack[4]={state,script,EC_BULLET_ACTION,0u};uint32_t b=0u;
 if(!msd_guest_call_stack(c,IS_NOT_AIM,act,o,uint32_t(x),uint32_t(y),stack,4u,&b)||!b)return 0u;   // 未完成时 b 不是弹体
 wr<uint32_t>(c,b+0x28u,kind);wr<uint32_t>(c,b+0x2cu,0u);
 if(kind==1u)wr<uint32_t>(c,b+0xc4u,20u);
 return b;
}
// 节脚本第一 tick 的旋转（op2，角度）与缩放（op19，%）
static void ec_part_pose(Context& c,uint32_t desc,uint32_t script,float& rot,float& sx,float& sy){
 rot=0.0f;sx=sy=1.0f;if(script>=rd<uint32_t>(c,desc+0x1cu))return;
 uint32_t sc=rd<uint32_t>(c,rd<uint32_t>(c,desc+0x18u)+script*4u),pos=0u;bool gr=false,gs=false;
 for(uint32_t k=0;k<64u;++k){
  uint32_t op=rd<uint32_t>(c,sc+pos*4u);if(op>23u||op==1u||op==5u||op==21u)break;
  if(op==2u&&!gr){rot=float(rd<int32_t>(c,sc+pos*4u+4u))*0.087890625f;gr=true;}
  if(op==19u&&!gs){sx=float(rd<int32_t>(c,sc+pos*4u+4u))*0.01f;sy=float(rd<int32_t>(c,sc+pos*4u+8u))*0.01f;gs=true;}
  pos+=Z_LEN[op];
 }
}
static void ec_wheel(Context& c,uint32_t o,const EcPart* parts,uint32_t n,uint32_t a,uint32_t t,bool half){
 uint32_t sprite=rd<uint32_t>(c,o+0x5cu);if(!sprite)return;
 uint32_t root=rd<uint32_t>(c,sprite+0x58u),desc=rd<uint32_t>(c,sprite+0x40u);
 uint32_t ar=(ec_sign(c,o)>0?a:0u-a)&0xfffu;EcTrig tr=ec_trig(c,ar);
 float scale=rd<float>(c,sprite+0x28u),deg=float(ar)*0.087890625f;
 uint32_t first=(t<21u?std::min(n,13u):n)-1u;
 for(uint32_t i=0;i<n;++i){
  uint32_t key=uint32_t(parts[i].prio+0x64)|(parts[i].script<<8),st=rd<uint32_t>(c,sprite+0x54u);
  for(uint32_t k=0;st&&k<1024u;++k){if(rd<uint32_t>(c,st+4u)==key&&rd<uint32_t>(c,st+0x4cu)==root)break;st=rd<uint32_t>(c,st+0x50u);}
  if(!st)continue;
  if(i>first||((first-i)>=19u&&half)){wr<float>(c,st+0x30u,0.0f);wr<float>(c,st+0x34u,0.0f);continue;}
  float rot,sx,sy,rx,ry;ec_part_pose(c,desc,parts[i].script,rot,sx,sy);
  ec_rotate(tr,float(-parts[i].x),float(parts[i].y),rx,ry);
  rot-=deg;while(rot<0.0f)rot+=360.0f;while(rot>=360.0f)rot-=360.0f;
  wr<float>(c,st+0x20u,float(ec_art(c,sprite))*(140.0f+rx));wr<float>(c,st+0x24u,ry);wr<float>(c,st+0x2cu,rot);
  wr<float>(c,st+0x30u,scale*sx);wr<float>(c,st+0x34u,scale*sy);
 }
}
// MSA createSpAttackGroundEffect：节由地下越过地面（未过半周）或由地面以上进入地下时，在该处地面生成地面攻击弹体
static void ec_ground_hits(Context& c,uint32_t act,uint32_t o,uint32_t s,const EcPart* parts,uint32_t n,uint32_t a,uint32_t t,bool half){
 uint32_t prev=(a-uint32_t(ec_sign(c,o)*32))&0xfffu,m=t<21u?std::min(n,13u):n;
 EcTrig tc=ec_trig(c,a),tp=ec_trig(c,prev);
 float ox=rd<float>(c,o+0x8cu),oy=rd<float>(c,o+0x90u);
 for(uint32_t i=0;i<m;++i){
  float cx,cy,px,py;ec_part_pos(c,o,parts[i],tc,cx,cy);ec_part_pos(c,o,parts[i],tp,px,py);
  float g=float(ec_ground(c,o,int32_t(cx)));
  if(cy<g?(!half&&py>g):(py<g))ec_fire(c,act,o,zw(c,s,68),1u,50u,ec_sign(c,o)*int32_t(cx-ox),int32_t(g-oy));
 }
}
static void ec_head_rect(Context& c,uint32_t o,const EcPart& p,uint32_t a,bool half){
 float hx,hy;EcTrig t=ec_trig(c,a);ec_part_pos(c,o,p,t,hx,hy);
 bool on=rd<uint8_t>(c,o+0xecu)!=0;
 if(hy<float(ec_ground(c,o,int32_t(hx)))&&!half){
  int32_t dx=int32_t(hx-rd<float>(c,o+0x8cu)),dy=int32_t(hy-rd<float>(c,o+0x90u)),x=(dx>>1)-20,y=(dy>>1)-20;
  if(!on){const uint32_t st[1]={40u};msd_guest_call_stack(c,EC_SET_ATTACK,o,uint32_t(x),uint32_t(y),40u,st,1u,nullptr);}
  else{wr<int32_t>(c,o+0xdcu,2*x);wr<int32_t>(c,o+0xe0u,2*y);wr<int32_t>(c,o+0xe4u,2*(x+40));wr<int32_t>(c,o+0xe8u,2*(y+40));}
 }else if(on){const uint32_t st[1]={0u};msd_guest_call_stack(c,EC_SET_ATTACK,o,0u,0u,0u,st,1u,nullptr);}
}
// MSA createSmoke：每 10 tick 在脚下地面放一团尘土（三个动作轮换）
static void ec_smoke(Context& c,uint32_t act,uint32_t o,uint32_t s){
 int32_t n=rd<int32_t>(c,o+0x30u)-1;
 if(n>0){wr<int32_t>(c,o+0x30u,n);return;}
 uint32_t idx=rd<uint32_t>(c,o+0x34u);if(idx>2u)idx=0u;
 wr<int32_t>(c,o+0x30u,10);
 float g=float(ec_ground(c,o,int32_t(rd<float>(c,o+0x94u))));
 const uint32_t stack[3]={1u,zw(c,s,66)+idx,0xffffffffu};
 msd_guest_call_stack(c,IS_ADD_EFFECT,act,o,0u,uint32_t(int32_t(g-rd<float>(c,o+0x90u))),stack,3u,nullptr);
 wr<uint32_t>(c,o+0x34u,idx>=2u?0u:idx+1u);
}
static bool ec_update(Context& c){
 uint32_t act=c.r[0],o=c.r[1],state=c.r[2],frame=c.r[3],s=ec_unit(c,o);if(!s)return false;
 const int32_t APPEAR=int32_t(zw(c,s,53)),EMERGE=int32_t(zw(c,s,54)),NEUTRAL=int32_t(zw(c,s,55)),BURROW=int32_t(zw(c,s,56)),
  UNDER=int32_t(zw(c,s,57)),LONG=int32_t(zw(c,s,58)),LONG_END=int32_t(zw(c,s,59)),DIVE=int32_t(zw(c,s,60)),MARCH=int32_t(zw(c,s,61)),
  FLINCH=int32_t(zw(c,s,62)),FLINCH_LOOP=int32_t(zw(c,s,63)),KNOCK=int32_t(zw(c,s,64)),DEATH=int32_t(zw(c,s,65));
 int32_t anim=int32_t(rd<uint32_t>(c,o+0xc4u)),pend=-1;     // pend：末尾尾调用 setAnimationID 的动作号
 auto cur=[&]{return pend>=0?pend:anim;};
 auto run=[&]{return pend>=0||rd<uint8_t>(c,o+0xc9u)!=0;};
 auto set=[&](int32_t a){pend=a;};
 auto finish=[&]{is_call(c,EC_START_WAIT,act,o,state);set(NEUTRAL);};
 bool viewer=z_viewer(c),first=frame==0u,smoke=true,disable=true;
 uint32_t fl=rd<uint32_t>(c,o+0x38u);
 if(state>=100u&&state<=140u){
  // MSA dead：在地下时先出土，再播放损毁动作，播完移除
  if(cur()==UNDER)set(EMERGE);
  if(cur()==EMERGE){if(!run())set(DEATH);}
  else if(first)set(DEATH);
  else if(!run())is_call(c,IS_KILL,o);
  smoke=frame<71u;disable=false;
 }else if(!viewer&&!(fl&1u)){
  // MSA 状态 78（startPosition）：出土，播完待机
  if(cur()!=APPEAR)set(APPEAR);
  else if(!run()){wr<uint32_t>(c,o+0x38u,fl|1u);set(NEUTRAL);wr<uint32_t>(c,o+0x84u,10u);is_call(c,IS_RESERVE,o,10u,0u);}
 }else switch(state){
  case 10u:
   if(cur()==UNDER)set(EMERGE);
   else if(cur()==EMERGE){if(!run())set(NEUTRAL);}
   else if(first)set(NEUTRAL);
   break;
  case 20u:
   if(cur()!=BURROW&&cur()!=UNDER){set(BURROW);wr<uint32_t>(c,o+0x84u,10u);}
   else if(cur()==BURROW){if(!run())set(UNDER);}
   else{
    msd_guest_call(c,EC_ACTION_MOVE,act,o,l_bits(-1.0f),0u,nullptr);
    float g=float(ec_ground(c,o,int32_t(rd<float>(c,o+0x94u))));wr<float>(c,o+0x90u,g);wr<float>(c,o+0x98u,g);
    smoke=false;
   }
   break;
  case 30u:case 40u:
   if(first){if(cur()==UNDER)set(EMERGE);else if(cur()!=BURROW)set(LONG);}
   if(cur()==EMERGE){if(!run())set(LONG);}
   else if(cur()==BURROW){if(!run())set(EMERGE);}
   else if(cur()==LONG){if(!run())set(LONG_END);}
   else if(cur()==LONG_END){if(!run())finish();}
   else finish();
   break;
  case 50u:
   if(first){set(cur()==UNDER?EMERGE:DIVE);wr<uint32_t>(c,o+0x24u,0u);wr<int32_t>(c,o+0x28u,4096);wr<uint32_t>(c,o+0x2cu,0u);}
   if(cur()==MARCH){
    int32_t left=rd<int32_t>(c,o+0x28u)-32;wr<int32_t>(c,o+0x28u,left);if(left<=2048)wr<uint32_t>(c,o+0x2cu,1u);
    uint32_t t=rd<uint32_t>(c,o+0x3cu);wr<uint32_t>(c,o+0x3cu,t+1u);
    if(left<=0)set(APPEAR);
    else{
     uint32_t a=(rd<uint32_t>(c,o+0x24u)+uint32_t(ec_sign(c,o)*32))&0xfffu;wr<uint32_t>(c,o+0x24u,a);
     bool half=rd<uint32_t>(c,o+0x2cu)!=0u;EcPart parts[EC_MAX_PARTS];uint32_t n=ec_parts(c,o,s,parts);
     if(n){ec_ground_hits(c,act,o,s,parts,n,a,t,half);ec_head_rect(c,o,parts[0],a,half);ec_wheel(c,o,parts,n,a,t,half);}
     smoke=t<23u;
    }
   }else if(cur()==DIVE){
    if(!run()){set(MARCH);wr<uint32_t>(c,o+0x3cu,0u);const uint32_t st[1]={0u};msd_guest_call_stack(c,EC_SET_ATTACK,o,0u,0u,0u,st,1u,nullptr);}
   }else if(cur()==APPEAR){if(!run())finish();}
   else if(cur()==EMERGE){if(!run())set(DIVE);}
   else finish();
   break;
  case 80u:   // MSD 击退（MSA 状态 70）
   if(first)set(KNOCK);else if(!run())wr<uint32_t>(c,o+0x84u,10u);
   break;
  case 70u:   // MSA 状态 80：受击
   if(cur()==UNDER)set(EMERGE);
   else if(cur()==EMERGE){if(!run())set(FLINCH);}
   else if(cur()==FLINCH){if(!run()){set(FLINCH_LOOP);wr<uint32_t>(c,o+0x84u,10u);}}
   else if(cur()!=FLINCH_LOOP)set(FLINCH);
   disable=false;
   break;
  default:break;
 }
 if(smoke&&!viewer)ec_smoke(c,act,o,s);
 if(disable){
  bool want=cur()==BURROW||cur()==EMERGE;fl=rd<uint32_t>(c,o+0x38u);
  if(want!=((fl&2u)!=0u)){is_call(c,EC_DONT_SP,o,want?1u:0u);wr<uint32_t>(c,o+0x38u,want?fl|2u:fl&~2u);}
 }
 if(pend>=0){c.r[0]=o;c.r[1]=uint32_t(pend);c.r[2]=0u;c.r[3]=1u;c.pc=IS_SET_ANIM|1u;}   // 返回地址不变
 else c.pc=c.r[14];
 return true;
}
static bool ik_update(Context& c);static bool ik_shot(Context& c);static bool ik_bullet_update(Context& c);static bool ik_create(Context& c);
static uint32_t ik_bullet_spec(Context& c,uint32_t b);static bool ik_beam_hits(Context& c,uint32_t b,uint32_t t);   // 侵略者之王（后文）
static bool wd_update(Context& c);static bool wd_shot(Context& c);static bool wd_bullet_update(Context& c);static bool wd_create(Context& c);static uint32_t wd_unit(Context& c,uint32_t o);static bool wd_debris(Context& c,uint32_t b);   // 钢铁死亡蠕虫（后文）
static Block old_elder_update;static void elder_update(Context& c){if(ec_update(c)||ik_update(c)||wd_update(c))return;old_elder_update(c);}
static bool ec_shot(Context& c){
 uint32_t act=c.r[0],o=c.r[1],script=c.r[2],s=ec_unit(c,o);if(!s)return false;
 int32_t x=int32_t(c.r[3]),y=rd<int32_t>(c,c.r[13]);
 if(script==zw(c,s,68)||script==zw(c,s,69)){
  uint32_t b=ec_fire(c,act,o,script,1u,50u,x,y);
  if(b){float g=float(ec_ground(c,b,int32_t(rd<float>(c,b+0x8cu))));wr<float>(c,b+0x90u,g);wr<float>(c,b+0x98u,g);}
 }else if(script>=zw(c,s,70)&&script<zw(c,s,70)+zw(c,s,71))ec_fire(c,act,o,script,2u,40u,x,y);
 c.pc=c.r[14];return true;
}
static Block old_elder_shot;static void elder_shot(Context& c){if(ec_shot(c)||ik_shot(c)||wd_shot(c))return;old_elder_shot(c);}
static bool ec_bullet_update(Context& c){
 uint32_t act=c.r[0],b=c.r[1],state=c.r[2],s=ec_bullet_spec(c,b);if(!s)return false;
 uint32_t kind=rd<uint32_t>(c,b+0x28u),age=rd<uint32_t>(c,b+0x2cu)+1u;wr<uint32_t>(c,b+0x2cu,age);
 bool run=rd<uint8_t>(c,b+0xc9u)!=0;
 if(kind==1u||kind==4u){if(age>1u&&!run)is_call(c,IS_KILL,b);}
 else{
  bool hit=state==60u||state==59u||(state!=200u&&is_call(c,EC_ADJUST_GROUND,act,b)!=0u);
  if(kind==2u){
   if(hit){is_effect(c,act,b,0,0,zw(c,s,72));is_call(c,IS_KILL,b);}
   else if(age>1u&&!run)is_call(c,IS_KILL,b);
  }else if(hit){
   msd_guest_call(c,IS_MOVE_X,b,0u,0u,0xffffffffu,nullptr);msd_guest_call(c,IS_MOVE_Y,b,0u,0u,0xffffffffu,nullptr);
   wr<uint32_t>(c,b+0x28u,4u);wr<uint32_t>(c,b+0x2cu,0u);is_call(c,IS_SET_ANIM,b,zw(c,s,74),0u,1u);
  }
 }
 c.pc=c.r[14];return true;
}
static Block old_elder_bullet;static void elder_bullet(Context& c){if(ec_bullet_update(c)||ik_bullet_update(c)||wd_bullet_update(c))return;old_elder_bullet(c);}
static Block old_elder_attack;static void elder_attack(Context& c){
 uint32_t b=c.r[1],k=ec_bullet_spec(c,b)?rd<uint32_t>(c,b+0x28u):0u;
 if(k>=2u||wd_debris(c,b)){c.pc=EC_DEFAULT_ATTACK;return;}   // 钢铁死亡蠕虫的掘削碎块：结算后消失（MSA 默认弹体 attackAction 0x10e54b8）
 if(ik_bullet_spec(c,b)&&!ik_beam_hits(c,b,c.r[2])){c.r[0]=0u;c.pc=c.r[14];return;}   // 侵略者之王的激光：先按光束判定
 old_elder_attack(c);
}
static void ec_create(Context& c){
 uint32_t act=c.r[0],o=c.r[1],script=c.r[2],s=ec_unit(c,o),sp=c.r[13];if(!s)return;
 if(script==zw(c,s,75)){
  // MSA createSpAttackBullet：世界偏移 = ±280 + 旋转((±x), y)；换回朝向坐标交给原生
  int32_t sg=ec_sign(c,o);EcTrig t=ec_trig(c,rd<uint32_t>(c,o+0x24u)&0xfffu);float rx,ry;
  ec_rotate(t,float(sg*int32_t(c.r[3])),float(rd<int32_t>(c,sp)),rx,ry);
  int32_t dx=sg*int32_t(float(sg*280)+rx),dy=int32_t(ry);
  c.r[3]=uint32_t(dx);wr<uint32_t>(c,sp,uint32_t(dy));
  if(!z_viewer(c)){
   uint32_t b=ec_fire(c,act,o,zw(c,s,73),3u,50u,dx,dy);
   if(b){
    float cx=rd<float>(c,o+0x8cu)+float(sg*280),cy=rd<float>(c,o+0x90u);
    uint32_t a=is_call(c,IS_ATAN,uint32_t(int32_t(cx-rd<float>(c,b+0x8cu))),uint32_t(int32_t(cy-rd<float>(c,b+0x90u))))&0xfffu;
    fs_velocity(c,b,a,5.0f);
   }
  }
 }else if(script==zw(c,s,76)){
  int32_t g=ec_ground(c,o,int32_t(rd<float>(c,o+0x8cu))+ec_sign(c,o)*int32_t(c.r[3]));
  wr<uint32_t>(c,sp,uint32_t(g-int32_t(rd<float>(c,o+0x90u))));
 }
}
static Block old_elder_create;static void elder_create(Context& c){if(ik_create(c)||wd_create(c))return;ec_create(c);old_elder_create(c);}
// 当前裁切（Graphics +0x14–+0x20，像素；+4/+8 原点、+0xc/+0x10 全屏、+0x38 缩放）换回逻辑坐标，与“地面以上”取交集；
// 绘制后恢复：原为全屏（clearClip 后的状态）时 clearClip，否则按换回的逻辑坐标 setClip。
// r87：战斗中（非动作演示）原生绘制单位时不留裁切（BattleAction_Daimanji 等绘制后以覆盖全屏的矩形 setClip），本次启动若从未调用
// setClip / clearClip，裁切字段全为 0；r80–r86 把全 0 当作 0×0 裁切并在绘制后“恢复”，此后剪裁一直为 0×0（界面与单位不再绘制、
// 清屏无效）。战斗中改为以全屏为底、绘制后 clearClip；动作演示中取演示画框的裁切，字段无效（宽或高 ≤ 0）时同样按全屏处理。
// r91 钢铁死亡蠕虫：MSA draw（0xef2fb4）以 BattleSprite 0xd4fe10 分两遍绘制：优先级 < 6 的层按地面裁切，≥ 6 的层（地面土环与空中碎屑）
// 不裁切、后绘制。隐藏的层把帧号（动画层 +8）减 2000（原生 drawImpl 跳过帧号 < 0 的层，MSA 同法），绘制后加回；层的优先级为
// BattleSprite::getObjectPriority（自身 +0x28 沿父层 +0x4c 累加）。第二遍以延续块 3 调用原生绘制、返回地址为延续块 4
// （GraphicsOpt::setClip 中 str.w 指令的后半字 0x101358d9）。
static constexpr int32_t WD_HIDE=2000,WD_PRIO=6;
static constexpr uint32_t EC_V4=0x101358d9u;
static void wd_mark(Context& c,uint32_t o,bool high,int32_t delta){
 uint32_t sprite=rd<uint32_t>(c,o+0x5cu),st=sprite?rd<uint32_t>(c,sprite+0x54u):0u;
 for(uint32_t k=0;st&&k<1024u;++k){
  int32_t pr=0;for(uint32_t q=st,n=0;q&&n<16u;q=rd<uint32_t>(c,q+0x4cu),++n)pr+=rd<int32_t>(c,q+0x28u);
  if((pr>=WD_PRIO)==high)wr<int32_t>(c,st+8u,rd<int32_t>(c,st+8u)+delta);
  st=rd<uint32_t>(c,st+0x50u);
 }
}
static struct{uint32_t busy,lr,sp,r[4],ret,go,cleared,split;int32_t x,y,w,h;} ec_paint;
static bool ec_draw_begin(Context& c){
 uint32_t o=c.r[1];bool worm=wd_unit(c,o)!=0u;if(ec_paint.busy||(!worm&&!ec_unit(c,o)))return false;
 uint32_t go=is_call(c,EC_GRAPHICS,0u),sp=c.r[13],g=go?rd<uint32_t>(c,go):0u;if(!g)return false;
 float s=rd<float>(c,g+0x38u);if(!(s>0.0f))return false;
 int32_t px=rd<int32_t>(c,g+0x14u),py=rd<int32_t>(c,g+0x18u),pw=rd<int32_t>(c,g+0x1cu),ph=rd<int32_t>(c,g+0x20u);
 if(!z_viewer(c)||pw<=0||ph<=0){px=0;py=0;pw=rd<int32_t>(c,g+0xcu);ph=rd<int32_t>(c,g+0x10u);}
 ec_paint.cleared=px==0&&py==0&&pw==rd<int32_t>(c,g+0xcu)&&ph==rd<int32_t>(c,g+0x10u);
 ec_paint.x=int32_t(float(px)/s)-rd<int32_t>(c,g+4u);ec_paint.y=int32_t(float(py)/s)-rd<int32_t>(c,g+8u);
 ec_paint.w=int32_t(float(pw)/s+0.5f);ec_paint.h=int32_t(float(ph)/s+0.5f);
 // 地面：战斗中为地形高度，单位菜单的动作演示中为单位脚下（栈 [0] 绘制 y、[8] 镜头 y）
 int32_t ground=z_viewer(c)?rd<int32_t>(c,sp):stage_altitude(c,int32_t(rd<float>(c,o+0x8cu)));
 int32_t h=std::min(ec_paint.y+ec_paint.h,ground-rd<int32_t>(c,sp+8u))-ec_paint.y;if(h<0)h=0;
 ec_paint.busy=1u;ec_paint.lr=c.r[14];ec_paint.sp=sp;for(int i=0;i<4;++i)ec_paint.r[i]=c.r[i];ec_paint.go=go;
 ec_paint.split=worm?1u:0u;if(worm)wd_mark(c,o,true,-WD_HIDE);   // 第一遍（裁切）只画优先级 < 6 的层
 wr<uint32_t>(c,sp-8u,uint32_t(h));c.r[13]=sp-8u;
 c.r[0]=go;c.r[1]=uint32_t(ec_paint.x);c.r[2]=uint32_t(ec_paint.y);c.r[3]=uint32_t(ec_paint.w);c.r[14]=EC_V1;c.pc=EC_SET_CLIP;
 return true;
}
static Block old_elder_draw;static void elder_draw(Context& c){if(ec_draw_begin(c))return;old_elder_draw(c);}
static void elder_draw_v1(Context& c){c.r[13]=ec_paint.sp;for(int i=0;i<4;++i)c.r[i]=ec_paint.r[i];c.r[14]=EC_V2;old_elder_draw(c);}
static void elder_draw_v2(Context& c){
 ec_paint.ret=c.r[0];c.r[0]=ec_paint.go;c.r[14]=EC_V3;
 if(ec_paint.cleared){c.r[13]=ec_paint.sp;c.pc=EC_CLEAR_CLIP;return;}
 wr<uint32_t>(c,ec_paint.sp-8u,uint32_t(ec_paint.h));c.r[13]=ec_paint.sp-8u;
 c.r[1]=uint32_t(ec_paint.x);c.r[2]=uint32_t(ec_paint.y);c.r[3]=uint32_t(ec_paint.w);c.pc=EC_SET_CLIP;
}
static void elder_draw_v3(Context& c){
 if(ec_paint.split==1u){   // 钢铁死亡蠕虫的第二遍（裁切已恢复）：只画优先级 ≥ 6 的层
  uint32_t o=ec_paint.r[1];wd_mark(c,o,true,WD_HIDE);wd_mark(c,o,false,-WD_HIDE);ec_paint.split=2u;
  c.r[13]=ec_paint.sp;for(int i=0;i<4;++i)c.r[i]=ec_paint.r[i];c.r[14]=EC_V4;old_elder_draw(c);return;
 }
 c.r[13]=ec_paint.sp;c.r[0]=ec_paint.ret;ec_paint.busy=0u;c.pc=ec_paint.lr;
}
static void elder_draw_v4(Context& c){wd_mark(c,ec_paint.r[1],false,WD_HIDE);ec_paint.split=0u;c.r[13]=ec_paint.sp;c.r[0]=ec_paint.ret;ec_paint.busy=0u;c.pc=ec_paint.lr;}
extern "C" __declspec(dllexport) uint32_t msd_community_elder_centipede_version(){return elder_centipede_hooks==10u?1u:0u;}
// ---------- 侵略者之王（2026-10-22，行为库 v17：invader_king，标记 1048576；基准 192 BattleAction_Alien；核心 r83）----------
// MSA 7.13.0 BattleAction_InvaderKing 与其两个无符号激光弹体类（虚表 0x4a73e40 反击激光、0x4a73f08 绝招激光；反汇编与对照
// verification/invader_king_20261022/）在 MSD 原版侵略者类上的实现。与蜈蚣长老共用同 5 个块（Alien::update / shotBullet、
// BulletAction_Alien::update / attackAction、BattleUnitDefault::createObject）。r83–r92 另在 BattleUnitDefault::damageAction 的击退
// 判定（zombie_no_knockback 同一块）中，落下、着地、跃起与绝招动作期间与空中不击退（MSA 这些动作以 EnableNockBack(false) 关闭击退）；
// r93（社区意见，用户 2026-10-25：去掉 MSA 的不击退段）起这些动作中同样按原生计量击退，见 update 中跃起、落下、着地一段。
// 动作号为 MSA 脚本号，存于 ZSpec 字 77–100（community_content.py）：待机、落下、着地、近距、跃起、绝招开始 / 绝招 / 收尾、击退、
// 损毁、受击与其循环、菜单待机 / 远距 / 绝招演示、反击激光与其身体段、反击激光落点爆炸、天空激光首槽 / 个数 / 身体段、地面激光
// 首槽 / 个数、地面落点。
//  1 Alien::update：按 MSA update 处理，不进入原生。出场（MSA startPosition 置状态 78）：核心 r88 起出击的单位与关卡预置的单位
//    均在原处（出击的单位即本方据点旁）落下，出击的单位着地后先等待一次跃起间隔（远距攻击等待，词 27）；没有攻击距离内的目标时
//    （原生进入移动状态 20，本单位不步行）跃起并落到敌方最前线，每次跃起落地后等待跃起间隔（用户 2026-10-22；r87 及以前出击的单位
//    直接移到敌方最前方单位前缘之后（近攻击距离 − 2）处，即 MSA getAppearPos，夹在本方据点与敌方据点前缘之间）。均自地面以上 400 落下（落下
//    动作 7，速度 12、每 tick 加 2，MSA op45 [0,600,0,100] 乘精灵缩放），到地面时着地踏击（8，攻击框 10，按远距攻击组结算，MSA
//    appear 以 0x28），播完待机并预约状态 10。10 / 20 待机（MSA 状态 20 立即回 10，本单位不步行）；30 近距攻击；40 跃起（11，第
//    10 tick 起以速度 −24、每 tick −4 上升，MSA op45 [0,−1200,0,−200]）→ 移到出场位置 → 落下 → 着地踏击；50 绝招 12 → 13 → 15；
//    80（MSD 击退，MSA 状态 70）击退动作 16，前 15 tick 后滑（速度 2、每 tick 减 0.1，MSA op45 [−100,0,5,0] 与 op16），第 37 tick
//    的反击激光由 2 发射；70（MSA 状态 80）受击 19 → 20；100–140 损毁 18：在空中时先落到地面，播完移除；损毁动作第 95 tick 的
//    攻击框 11（MSA 攻击 4）按远距攻击组结算，伤害为远距攻击的 2/3（MSA 攻击 4 = 攻击 2 × 2/3，各等级相同），属性爆炸、第二参数 1、
//    目标数 999（损毁开始时改写本单位当前等级的数据行副本，单位即将移除）。动作切换在末尾以尾调用交给原生 setAnimationID。
//    单位菜单的动作演示中：10 / 20 菜单待机 0、30 近距 10、40 菜单远距演示 1（原地跃起与踏击）、50 菜单绝招演示 2，不出场、不发射弹体。
//    攻击 ID（核心 r84，2026-10-22 用户：一次攻击对同一目标整次只结算一次）：每个状态的第一 tick 清空攻击 ID（+0x314）与剩余目标数
//    （+0x318）；近距攻击中原生在攻击框关闭时把 ID 清零、重开（爪击、吐息各次）时再建新 ID，这里记下本次第一次建立的 ID（单位
//    +0x38）并每 tick 写回，目标的受击 ID 环（+0x328，80 项）中已有该 ID 时原生不再结算，整次近距攻击对每个目标只结算一次。
//    r83 及以前对本单位置身体状态 0x20（AttackIDReset），吐息每次重开都建新 ID，同一目标一次近距攻击受 7 次。
//  2 Alien::shotBullet：天空激光 35–40、地面激光 49–54 与反击激光 34 以绝招组经 addBulletNotAim 发射（MSA shotBullet 的
//    0x23–0x28、0x31–0x36、0x22）。每道激光取原生 BattleBullet::initialize 建立的攻击 ID，同一目标可受多道、每道各自结算（核心 r89，
//    用户 2026-10-23：激光分段结算；r84–r88 一次绝招的全部天空 / 地面激光共用绝招开始时取的 ID（单位 +0x3c），r85–r88 一次击退的
//    2 道反击激光共用击退开始时取的 ID（单位 +0x40），同一目标整次只结算一次）；反击激光每道伤害为绝招组伤害 × 9/2（r89）。原注：
//    0x23–0x28、0x31–0x36、0x22；弹体伤害由 addBulletImpl 按单位当前攻击组取，反击激光发射前把攻击组设为 50，MSA 以 0x32），动作号字段 +0xc4 写 20，使原生 attackAction 走“只结算伤害、不消失”的
//    分支。地面激光：MSA 在落点效果 55 之后的第一条跳过（单位 +0x28 由 0 置 1）、第二条以落点地面高度建立。其余脚本不发射（MSA 同）。
//  3 BulletAction_Alien::update：激光（弹体 +0x28：10 天空、11 地面、12 反击）动画播完移除；每 tick 拉伸身体段（天空 / 反击：
//    op11 子层，偏移为头部长度；地面：根层）到激光长度，攻击框开启时改为激光起点与终点的外接矩形（MSA 弹体 update）。
//    天空与地面激光的方向为脚本 op2 的角度 + 90°（敌方镜像），向上到 y = 40 为止（MSA 0xef180c）；反击激光自发射点射向前方最近的
//    敌方单位所在处的地面（远攻击距离之内，没有时为前方远攻击距离处），落点放爆炸 17（MSA shotBullet 0x22 与 createObject 0x11，
//    MSA 以最后一次击退本单位的攻击者为目标，本实施以敌方最前方单位代替）。
//  4 BulletAction_Alien::attackAction：激光先按 MSA 的光束判定（btl::beamContactPosition：以激光方向为轴、半宽 16 的长条，天空与
//    地面激光长 600，反击激光为其长度）检查目标受击框，不相交时不结算。
//  5 BattleUnitDefault::createObject：地面落点效果 55 的高度取该处地形（高于 600 时不建立），单位 +0x28 置 0、+0x2c 记地面高度
//    （MSA createObject 0x37）。
// 单位的状态只在客体对象内存：+0x24 标记（1 已出场、2 在空中；8 为 r83 及以前已置身体状态 0x20）、+0x28 / +0x2c 地面激光（MSA 同位置）、
// +0x30 竖直速度、+0x34 本动作 tick、+0x38 本次近距攻击的攻击 ID（+0x3c / +0x40 为 r84–r88 绝招与击退的攻击 ID，r89 不再使用）。弹体：+0x28 种类、+0x2c 存在 tick、+0x30 方向（4096 为一周，已按队伍镜像）、+0x34 / +0x38 终点、
// +0x3c 绘制长度、+0x40 判定长度、+0x1c 精灵旋转（4096 为一周，原画坐标）。
#include <cmath>
#include <initializer_list>
static constexpr uint32_t IK_FLAG=1048576u,IK_W=77u;
enum:uint32_t{IK_NEUTRAL,IK_FALL,IK_LAND,IK_NEAR,IK_JUMP,IK_SP0,IK_SP,IK_SP1,IK_KNOCK,IK_DEATH,IK_FLINCH,IK_FLINCH2,IK_M0,IK_M1,IK_M2,
 IK_COUNTER,IK_COUNTER_BODY,IK_BURST,IK_SKY,IK_SKY_N,IK_SKY_BODY,IK_GROUND,IK_GROUND_N,IK_IMPACT};
static constexpr float IK_DROP=400.0f,IK_FALL_V=12.0f,IK_FALL_A=2.0f,IK_JUMP_V=-24.0f,IK_JUMP_A=-4.0f,IK_BEAM_TOP=40.0f,IK_BEAM_HALF=16.0f;
static constexpr uint32_t IK_JUMP_T=10u,IK_SLIDE_T=15u,IK_HEAD=41u;
static constexpr float IK_SPAWN_NEAR=160.0f;   // 出击单位在本方据点 x 附近生成
static constexpr int32_t IK_COUNTER_NUM=9,IK_COUNTER_DEN=2;   // 反击激光每道伤害 = 绝招组伤害 × 9/2（r89）
static uint32_t ik_w(Context& c,uint32_t s,uint32_t i){return zw(c,s,IK_W+i);}
static uint32_t ik_unit(Context& c,uint32_t o){uint32_t s=o?zspec(c,o):0u;return s&&(zw(c,s,0)&IK_FLAG)?s:0u;}
static uint32_t ik_bullet_spec(Context& c,uint32_t b){
 if(!active(c)||!head(c,168u)||!b||rd<uint32_t>(c,b)!=FS_BULLET_VPTR)return 0u;
 uint32_t uid=rd<uint32_t>(c,b+0x128u);if(!record(c,uid))return 0u;
 uint32_t s=rd<uint32_t>(c,head(c,168u)+(uid-U)*4u),k=rd<uint32_t>(c,b+0x28u);
 return s&&(zw(c,s,0)&IK_FLAG)&&k>=10u&&k<=12u?s:0u;
}
static int32_t ik_dir(Context& c,uint32_t o){return rd<uint32_t>(c,o+0x78u)==0x10eu?-1:1;}
static float ik_ground(Context& c,uint32_t o,float x){
 if(z_viewer(c))return rd<float>(c,o+0x90u);
 int32_t g=stage_altitude(c,int32_t(x));return g==9999?rd<float>(c,o+0x90u):float(g);
}
static uint32_t ik_base(Context& c,uint32_t team){return is_call(c,IS_TEAM_UNITS,IS_MANAGER,team,0u);}   // 队伍单位链表首项为据点
static void ik_place(Context& c,uint32_t o,float x,float y){wr<float>(c,o+0x8cu,x);wr<float>(c,o+0x94u,x);wr<float>(c,o+0x90u,y);wr<float>(c,o+0x98u,y);}
// MSA getAppearPos：敌方最前方单位的前缘之后（近攻击距离 − 2）处，夹在本方据点与敌方据点前缘之间
static float ik_appear_x(Context& c,uint32_t o){
 uint32_t team=rd<uint32_t>(c,o+0x70u)&1u;int32_t d=ik_dir(c,o);float x=rd<float>(c,o+0x8cu);
 uint32_t t=rd<uint32_t>(c,IS_MANAGER+0x38u+(team^1u)*4u);
 if(t){float ex=rd<float>(c,t+0x8cu),ew=float(int32_t(is_call(c,IS_WIDTH,t)));x=ex+float(ik_dir(c,t))*ew-float(d)*float(int32_t(is_status(c,o,6u))-2);}
 uint32_t own=ik_base(c,team),foe=ik_base(c,team^1u);
 if(foe){float fx=rd<float>(c,foe+0x8cu),fw=float(int32_t(is_call(c,IS_WIDTH,foe)));x=d>0?std::min(x,fx-fw):std::max(x,fx+fw);}
 if(own){float ox=rd<float>(c,own+0x8cu);x=d>0?std::max(x,ox):std::min(x,ox);}
 return x;
}
// 出击的单位由本方据点处生成；关卡预置的单位不在据点处（在原处落下）
static bool ik_deployed(Context& c,uint32_t o){
 uint32_t own=ik_base(c,rd<uint32_t>(c,o+0x70u)&1u);
 return own&&std::fabs(rd<float>(c,o+0x8cu)-rd<float>(c,own+0x8cu))<=IK_SPAWN_NEAR;
}
// MSA 攻击 4（损毁爆炸）= 攻击 2 × 2/3：改写本单位当前等级数据行副本的远距攻击组（单位即将移除）
static void ik_death_blast(Context& c,uint32_t o){
 uint32_t row=o+0x128u+0xecu*rd<uint32_t>(c,o+0x300u);
 wr<uint32_t>(c,row+22u*4u,rd<uint32_t>(c,row+22u*4u)*2u/3u);wr<float>(c,row+23u*4u,1.0f);
 wr<uint32_t>(c,row+24u*4u,999u);wr<uint32_t>(c,row+28u*4u,2u);wr<uint32_t>(c,o+0x88u,40u);
}
static bool ik_update(Context& c){
 uint32_t act=c.r[0],o=c.r[1],state=c.r[2],frame=c.r[3],s=ik_unit(c,o);if(!s)return false;
 int32_t anim=int32_t(rd<uint32_t>(c,o+0xc4u)),pend=-1;
 auto A=[&](uint32_t i){return int32_t(ik_w(c,s,i));};
 auto cur=[&]{return pend>=0?pend:anim;};
 auto run=[&]{return pend>=0||rd<uint8_t>(c,o+0xc9u)!=0;};
 auto set=[&](int32_t a){pend=a;wr<uint32_t>(c,o+0x34u,0u);};
 auto finish=[&]{is_call(c,EC_START_WAIT,act,o,state);set(A(IK_NEUTRAL));};
 auto is_any=[&](std::initializer_list<uint32_t> l){for(uint32_t i:l)if(cur()==A(i))return true;return false;};
 bool viewer=z_viewer(c),first=frame==0u;
 uint32_t fl=rd<uint32_t>(c,o+0x24u),tick=rd<uint32_t>(c,o+0x34u)+1u;wr<uint32_t>(c,o+0x34u,tick);
 // 攻击 ID（r84）：状态第一 tick 清空；近距攻击整次保持第一次建立的 ID（激光各自结算，r89）
 if(first){wr<uint16_t>(c,o+0x314u,0u);wr<uint32_t>(c,o+0x318u,0u);wr<uint32_t>(c,o+0x38u,0u);}
 if(!viewer&&state==30u){
  uint32_t id=rd<uint16_t>(c,o+0x314u),keep=rd<uint32_t>(c,o+0x38u);
  if(!keep){if(id)wr<uint32_t>(c,o+0x38u,id);}
  else if(id!=keep){wr<uint16_t>(c,o+0x314u,uint16_t(keep));if(rd<int32_t>(c,o+0x318u)<=0)wr<uint32_t>(c,o+0x318u,is_status(c,o,17u));}
 }
 auto drop=[&](float x){float g=ik_ground(c,o,x);ik_place(c,o,x,g-IK_DROP);wr<float>(c,o+0x30u,IK_FALL_V);fl|=2u;set(A(IK_FALL));};
 if(state>=100u&&state<=140u){
  if(first){
   if(fl&2u){float x=rd<float>(c,o+0x8cu);ik_place(c,o,x,ik_ground(c,o,x));fl&=~2u;}
   ik_death_blast(c,o);set(A(IK_DEATH));
  }else if(!run())is_call(c,IS_KILL,o);
 }else if(!viewer&&(!(fl&1u)||is_any({IK_JUMP,IK_FALL,IK_LAND}))){
  // 出场与远距攻击的跃起、落下、着地（其间不切换到其他状态的动作）
  bool appear=!(fl&1u);
  // r93（社区意见，用户 2026-10-25：去掉 MSA 的不击退段）：跃起、落下与着地中原生计量耗尽时同样预约击退（状态 80）。在地面（起跳前、
  // 着地踏击）立即播放击退；在空中原地落下（不移到前线、不踏击；高于地面 400 时自 400 处落下），到地面时播放击退。出场途中视为已出场。
  if(state==80u&&is_any({IK_JUMP,IK_FALL,IK_LAND})){
   if(fl&2u){
    float x=rd<float>(c,o+0x8cu),y=rd<float>(c,o+0x90u),g=ik_ground(c,o,x),v=rd<float>(c,o+0x30u);
    if(cur()!=A(IK_FALL)){v=0.0f;y=std::max(y,g-IK_DROP);set(A(IK_FALL));}
    y+=v;wr<float>(c,o+0x30u,v+IK_FALL_A);
    if(y>=g){y=g;fl&=~2u;set(A(IK_KNOCK));}
    wr<float>(c,o+0x90u,y);wr<float>(c,o+0x98u,y);
   }else set(A(IK_KNOCK));
   fl|=1u;
  }
  // r88（用户 2026-10-22）：出击的单位也在原处（本方据点旁）落下，不再直接落到敌方最前线；着地后等待一次跃起间隔再行动
  else if(appear&&!is_any({IK_FALL,IK_LAND}))drop(rd<float>(c,o+0x8cu));
  else if(cur()==A(IK_JUMP)){
   if(tick>=IK_JUMP_T){
    float v=tick==IK_JUMP_T?IK_JUMP_V:rd<float>(c,o+0x30u),x=rd<float>(c,o+0x8cu);
    ik_place(c,o,x,rd<float>(c,o+0x90u)+v);wr<float>(c,o+0x30u,v+IK_JUMP_A);fl|=2u;
   }
   if(!run())drop(ik_appear_x(c,o));
  }else if(cur()==A(IK_FALL)){
   float x=rd<float>(c,o+0x8cu),y=rd<float>(c,o+0x90u),v=rd<float>(c,o+0x30u),g=ik_ground(c,o,x);
   y+=v;wr<float>(c,o+0x30u,v+IK_FALL_A);
   if(y>=g){y=g;fl&=~2u;wr<uint32_t>(c,o+0x88u,40u);set(A(IK_LAND));}
   wr<float>(c,o+0x90u,y);wr<float>(c,o+0x98u,y);
  }else if(!run()){
   if(appear){
    fl|=1u;set(A(IK_NEUTRAL));
    if(ik_deployed(c,o))is_call(c,EC_START_WAIT,act,o,40u);   // r88：出击后先等待一次跃起间隔（远距攻击等待，词 27）
    else{wr<uint32_t>(c,o+0x84u,10u);is_call(c,IS_RESERVE,o,10u,0u);}
   }
   // r88：每次跃起落地后等待跃起间隔（下落中原生改为近距攻击状态 30 时同样）
   else if(state==40u||state==20u||state==30u){is_call(c,EC_START_WAIT,act,o,40u);set(A(IK_NEUTRAL));}
   else set(A(IK_NEUTRAL));
  }
 }else switch(state){
  case 10u:case 20u:{
   // r88：本单位不步行；没有攻击距离内的目标（原生进入移动状态 20）时跃起，落到敌方最前线（出击后由本方据点出发时的情形）
   if(!viewer&&state==20u){if(first)set(A(IK_JUMP));break;}
   int32_t want=viewer?A(IK_M0):A(IK_NEUTRAL);if(cur()!=want)set(want);break;}
  case 30u:
   if(cur()!=A(IK_NEAR)){if(first)set(A(IK_NEAR));else finish();}
   else if(!run())finish();
   break;
  case 40u:
   if(viewer){if(cur()!=A(IK_M1)){if(first)set(A(IK_M1));else finish();}else if(!run())finish();}
   else if(first)set(A(IK_JUMP));
   else finish();
   break;
  case 50u:
   if(viewer){if(cur()!=A(IK_M2)){if(first)set(A(IK_M2));else finish();}else if(!run())finish();}
   else if(!is_any({IK_SP0,IK_SP,IK_SP1})){if(first)set(A(IK_SP0));else finish();}
   else if(!run()){if(cur()==A(IK_SP0))set(A(IK_SP));else if(cur()==A(IK_SP))set(A(IK_SP1));else finish();}
   break;
  case 80u:   // MSD 击退（MSA 状态 70）
   if(first||cur()!=A(IK_KNOCK)){if(cur()!=A(IK_KNOCK))set(A(IK_KNOCK));}
   else{
    if(tick<=IK_SLIDE_T){
     int32_t d=ik_dir(c,o);float x=rd<float>(c,o+0x8cu)-float(d)*(2.0f-0.1f*float(tick-1u));
     uint32_t own=ik_base(c,rd<uint32_t>(c,o+0x70u)&1u);
     if(own){float ox=rd<float>(c,own+0x8cu);x=d>0?std::max(x,ox):std::min(x,ox);}
     wr<float>(c,o+0x8cu,x);wr<float>(c,o+0x94u,x);
    }
    if(!run())wr<uint32_t>(c,o+0x84u,10u);
   }
   break;
  case 70u:   // MSA 状态 80：受击
   if(!is_any({IK_FLINCH,IK_FLINCH2}))set(A(IK_FLINCH));
   else if(cur()==A(IK_FLINCH)&&!run()){set(A(IK_FLINCH2));wr<uint32_t>(c,o+0x84u,10u);}
   break;
  default:break;
 }
 wr<uint32_t>(c,o+0x24u,fl);
 if(pend>=0){c.r[0]=o;c.r[1]=uint32_t(pend);c.r[2]=0u;c.r[3]=1u;c.pc=IS_SET_ANIM|1u;}
 else c.pc=c.r[14];
 return true;
}
// 描述符（+8 矩形表 8 × int16、+0xc 帧表 u32 流、+0x18 脚本表、+0x1c 脚本数）中脚本第一帧的矩形高度（原画像素）
static float ik_frame_h(Context& c,uint32_t desc,uint32_t script){
 if(!desc||script>=rd<uint32_t>(c,desc+0x1cu))return 0.0f;
 uint32_t sc=rd<uint32_t>(c,rd<uint32_t>(c,desc+0x18u)+script*4u),pos=0u;
 for(uint32_t k=0;k<64u;++k){
  uint32_t op=rd<uint32_t>(c,sc+pos*4u);if(op>23u||op==5u||op==21u)break;
  if(op==0u){
   uint32_t f=rd<uint32_t>(c,sc+pos*4u+4u),r=rd<uint32_t>(c,rd<uint32_t>(c,desc+0xcu)+(f+1u)*4u);
   return float(rd<int16_t>(c,rd<uint32_t>(c,desc+8u)+r*16u+6u));
  }
  pos+=Z_LEN[op];
 }
 return 0.0f;
}
// 脚本第一 tick 的 op2 角度值（4096 为一周）
static uint32_t ik_script_rot(Context& c,uint32_t desc,uint32_t script){
 if(!desc||script>=rd<uint32_t>(c,desc+0x1cu))return 0u;
 uint32_t sc=rd<uint32_t>(c,rd<uint32_t>(c,desc+0x18u)+script*4u),pos=0u;
 for(uint32_t k=0;k<64u;++k){
  uint32_t op=rd<uint32_t>(c,sc+pos*4u);if(op>23u||op==1u||op==5u||op==21u)break;
  if(op==2u)return rd<uint32_t>(c,sc+pos*4u+4u)&0xfffu;
  pos+=Z_LEN[op];
 }
 return 0u;
}
// addBulletNotAim 的栈参数 0 为绘制优先级（取 op22 的第 2 个值，同 MSA）；弹体的伤害、第二参数与属性由 addBulletImpl 按单位当前的
// 攻击组 +0x88 取数据行（激光在绝招中发射时为 50；反击激光在击退中发射，先把 +0x88 设为 50，MSA 以 0x32 建立）
static uint32_t ik_fire(Context& c,uint32_t act,uint32_t o,uint32_t script,uint32_t kind,int32_t x,int32_t y,uint32_t z){
 uint32_t b=ec_fire(c,act,o,script,kind,z,x,y);if(b)wr<uint32_t>(c,b+0xc4u,20u);
 // r89（用户 2026-10-23）：激光各取原生 BattleBullet::initialize 建立的攻击 ID，每道各自结算（r84–r88 一次绝招 / 一次击退共用一个 ID）；
 // 反击激光每道为绝招组伤害（弹体 +0x12c，BattleBullet::attack 以此结算）× 9/2（Lv40 绝招每道 1000、反击激光每道 4500）
 if(b&&kind==12u)wr<int32_t>(c,b+0x12cu,rd<int32_t>(c,b+0x12cu)*IK_COUNTER_NUM/IK_COUNTER_DEN);
 return b;
}
// 激光的方向与终点：天空 / 地面为 op2 角度 + 90°（敌方镜像），向上到 y = 40（MSA 0xef180c）；判定长度 600（MSA 0xef19d8）
static void ik_beam_up(Context& c,uint32_t o,uint32_t b,uint32_t script){
 uint32_t sprite=rd<uint32_t>(c,b+0x5cu),desc=sprite?rd<uint32_t>(c,sprite+0x40u):0u;
 uint32_t a=(ik_script_rot(c,desc,script)+1024u)&0xfffu;if(rd<uint32_t>(c,o+0x70u)&1u)a=(2048u-a)&0xfffu;
 float dx=float(int32_t(is_call(c,IS_COS,a)))*(1.0f/4096.0f),dy=float(int32_t(is_call(c,IS_SIN,a)))*(1.0f/4096.0f);
 float bx=rd<float>(c,b+0x8cu),by=rd<float>(c,b+0x90u),ex=bx+dx*600.0f,ey=by+dy*600.0f;
 if(dy<-0.001f){float t=(IK_BEAM_TOP-by)/dy;ex=bx+dx*t;ey=IK_BEAM_TOP;}
 wr<uint32_t>(c,b+0x30u,a);wr<float>(c,b+0x34u,ex);wr<float>(c,b+0x38u,ey);
 wr<float>(c,b+0x3cu,std::sqrt((ex-bx)*(ex-bx)+(ey-by)*(ey-by)));wr<float>(c,b+0x40u,600.0f);
 wr<uint32_t>(c,b+0x1cu,ik_script_rot(c,desc,script));
}
// 反击激光：射向前方最近的敌方单位所在处的地面（远攻击距离之内，没有时为前方远攻击距离处），落点放爆炸
static void ik_beam_counter(Context& c,uint32_t act,uint32_t o,uint32_t s,uint32_t b){
 uint32_t team=rd<uint32_t>(c,o+0x70u)&1u,t=rd<uint32_t>(c,IS_MANAGER+0x38u+(team^1u)*4u);
 int32_t d=ik_dir(c,o);float bx=rd<float>(c,b+0x8cu),by=rd<float>(c,b+0x90u),reach=float(int32_t(is_status(c,o,7u)));
 float tx=bx+float(d)*reach;
 if(t){float ex=rd<float>(c,t+0x8cu),gap=(ex-bx)*float(d);if(gap>=0.0f&&gap<=reach)tx=ex;}
 float ty=ik_ground(c,o,tx);
 uint32_t a=is_call(c,IS_ATAN,uint32_t(int32_t(tx-bx)),uint32_t(int32_t(ty-by)))&0xfffu;
 uint32_t rot=team?(1024u-a)&0xfffu:(a-1024u)&0xfffu;   // MSA：精灵旋转 = 方向 − 90°（敌方 mirrorAngle(方向 − 270°)）
 uint32_t sprite=rd<uint32_t>(c,b+0x5cu),root=sprite?rd<uint32_t>(c,sprite+0x58u):0u;
 wr<uint32_t>(c,b+0x1cu,rot);if(root)wr<float>(c,root+0x2cu,float(rot)*0.087890625f);
 float len=std::sqrt((tx-bx)*(tx-bx)+(ty-by)*(ty-by));
 wr<uint32_t>(c,b+0x30u,a);wr<float>(c,b+0x34u,tx);wr<float>(c,b+0x38u,ty);wr<float>(c,b+0x3cu,len);wr<float>(c,b+0x40u,len);
 is_effect(c,act,o,d*int32_t(tx-rd<float>(c,o+0x8cu)),int32_t(ty-rd<float>(c,o+0x90u)),ik_w(c,s,IK_BURST));
}
static bool ik_shot(Context& c){
 uint32_t act=c.r[0],o=c.r[1],script=c.r[2],s=ik_unit(c,o);if(!s)return false;
 int32_t x=int32_t(c.r[3]),y=rd<int32_t>(c,c.r[13]);uint32_t z=rd<uint32_t>(c,c.r[13]+4u);
 if(!z_viewer(c)){
  uint32_t sky=ik_w(c,s,IK_SKY),gr=ik_w(c,s,IK_GROUND);
  if(script>=sky&&script<sky+ik_w(c,s,IK_SKY_N)){uint32_t b=ik_fire(c,act,o,script,10u,x,y,z);if(b)ik_beam_up(c,o,b,script);}
  else if(script>=gr&&script<gr+ik_w(c,s,IK_GROUND_N)){
   if(!rd<uint32_t>(c,o+0x28u))wr<uint32_t>(c,o+0x28u,1u);   // MSA：落点之后的第一条跳过
   else{
    uint32_t b=ik_fire(c,act,o,script,11u,x,y+rd<int32_t>(c,o+0x2cu)-int32_t(rd<float>(c,o+0x90u)),z);
    if(b)ik_beam_up(c,o,b,script);
   }
  }else if(script==ik_w(c,s,IK_COUNTER)){wr<uint32_t>(c,o+0x88u,50u);uint32_t b=ik_fire(c,act,o,script,12u,x,y,z);if(b)ik_beam_counter(c,act,o,s,b);}
 }
 c.pc=c.r[14];return true;
}
static bool ik_bullet_update(Context& c){
 uint32_t b=c.r[1],s=ik_bullet_spec(c,b);if(!s)return false;
 uint32_t kind=rd<uint32_t>(c,b+0x28u),age=rd<uint32_t>(c,b+0x2cu)+1u;wr<uint32_t>(c,b+0x2cu,age);
 if(age>1u&&rd<uint8_t>(c,b+0xc9u)==0u){is_call(c,IS_KILL,b);c.pc=c.r[14];return true;}
 float bx=rd<float>(c,b+0x8cu),by=rd<float>(c,b+0x90u),ex=rd<float>(c,b+0x34u),ey=rd<float>(c,b+0x38u),len=rd<float>(c,b+0x3cu);
 uint32_t sprite=rd<uint32_t>(c,b+0x5cu),root=sprite?rd<uint32_t>(c,sprite+0x58u):0u,desc=sprite?rd<uint32_t>(c,sprite+0x40u):0u;
 if(root&&desc){
  if(kind==11u){float h=ik_frame_h(c,desc,rd<uint32_t>(c,root+0xcu));if(h>0.0f)wr<float>(c,root+0x34u,len/h);}
  else{
   uint32_t body=ik_w(c,s,kind==12u?IK_COUNTER_BODY:IK_SKY_BODY),key=(1u+0x64u)|(body<<8),st=rd<uint32_t>(c,sprite+0x54u);
   for(uint32_t k=0;st&&k<256u;++k){if(rd<uint32_t>(c,st+4u)==key&&rd<uint32_t>(c,st+0x4cu)==root)break;st=rd<uint32_t>(c,st+0x50u);}
   // 子层不随根层旋转：身体段的旋转取根层的精灵旋转，偏移为头部长度按该旋转转向（原画坐标，敌方由原生镜像绘制）
   uint32_t rot=rd<uint32_t>(c,b+0x1cu)&0xfffu;float h=ik_frame_h(c,desc,body),deg=float(rot)*0.087890625f;
   if(kind==12u)wr<float>(c,root+0x2cu,deg);
   if(st&&h>0.0f){
    float si=float(int32_t(is_call(c,IS_SIN,rot)))*(1.0f/4096.0f),co=float(int32_t(is_call(c,IS_COS,rot)))*(1.0f/4096.0f);
    wr<float>(c,st+0x20u,-float(IK_HEAD)*si);wr<float>(c,st+0x24u,float(IK_HEAD)*co);wr<float>(c,st+0x2cu,deg);
    wr<float>(c,st+0x34u,std::max(0.0f,len-2.0f*float(IK_HEAD))/h);
   }
  }
 }
 if(rd<uint8_t>(c,b+0xecu)){
  wr<int32_t>(c,b+0xdcu,int32_t(std::min(0.0f,ex-bx)));wr<int32_t>(c,b+0xe0u,int32_t(std::min(0.0f,ey-by)));
  wr<int32_t>(c,b+0xe4u,int32_t(std::max(0.0f,ex-bx)));wr<int32_t>(c,b+0xe8u,int32_t(std::max(0.0f,ey-by)));
 }
 c.pc=c.r[14];return true;
}
// MSA btl::beamContactPosition：激光（起点、方向、长度、半宽 16 的长条）与目标受击框（BattleObject::getHitRect）是否相交（分离轴）
static bool ik_beam_hits(Context& c,uint32_t b,uint32_t t){
 int32_t hx=int32_t(rd<float>(c,t+0x8cu)),hy=int32_t(rd<float>(c,t+0x90u));
 if(!rd<int32_t>(c,t+0xd4u)&&!rd<int32_t>(c,t+0xd8u))return false;
 float x1=float(hx+rd<int32_t>(c,t+0xccu)),y1=float(hy+rd<int32_t>(c,t+0xd0u)),x2=float(hx+rd<int32_t>(c,t+0xd4u)),y2=float(hy+rd<int32_t>(c,t+0xd8u));
 uint32_t a=rd<uint32_t>(c,b+0x30u);
 float dx=float(int32_t(is_call(c,IS_COS,a)))*(1.0f/4096.0f),dy=float(int32_t(is_call(c,IS_SIN,a)))*(1.0f/4096.0f);
 float bx=rd<float>(c,b+0x8cu),by=rd<float>(c,b+0x90u),len=rd<float>(c,b+0x40u),nx=-dy,ny=dx;
 float qx[4]={bx+nx*IK_BEAM_HALF,bx-nx*IK_BEAM_HALF,bx+dx*len+nx*IK_BEAM_HALF,bx+dx*len-nx*IK_BEAM_HALF};
 float qy[4]={by+ny*IK_BEAM_HALF,by-ny*IK_BEAM_HALF,by+dy*len+ny*IK_BEAM_HALF,by+dy*len-ny*IK_BEAM_HALF};
 float rx[4]={x1,x2,x1,x2},ry[4]={y1,y1,y2,y2};
 const float ax[4]={1.0f,0.0f,dx,nx},ay[4]={0.0f,1.0f,dy,ny};
 for(int k=0;k<4;++k){
  float qa=1e30f,qb=-1e30f,ra=1e30f,rb=-1e30f;
  for(int i=0;i<4;++i){float p=qx[i]*ax[k]+qy[i]*ay[k];qa=std::min(qa,p);qb=std::max(qb,p);float r=rx[i]*ax[k]+ry[i]*ay[k];ra=std::min(ra,r);rb=std::max(rb,r);}
  if(qb<ra||rb<qa)return false;
 }
 return true;
}
// 地面落点效果 55：高度取该处地形（高于 600 时不建立），单位 +0x28 置 0、+0x2c 记地面高度（MSA createObject 0x37）
static bool ik_create(Context& c){
 uint32_t o=c.r[1],script=c.r[2],s=ik_unit(c,o),sp=c.r[13];if(!s||script!=ik_w(c,s,IK_IMPACT))return false;
 float x=rd<float>(c,o+0x8cu)+float(ik_dir(c,o)*int32_t(c.r[3]));
 int32_t g=z_viewer(c)?int32_t(rd<float>(c,o+0x90u)):stage_altitude(c,int32_t(x));
 wr<uint32_t>(c,o+0x28u,0u);wr<int32_t>(c,o+0x2cu,std::min(g,600));
 if(g>600){c.pc=c.r[14];return true;}
 wr<uint32_t>(c,sp,uint32_t(g-int32_t(rd<float>(c,o+0x90u))));
 return false;
}
extern "C" __declspec(dllexport) uint32_t msd_community_invader_king_version(){return elder_centipede_hooks==10u?1u:0u;}
// ---------- 钢铁死亡蠕虫（2026-10-25，行为库 v19：iron_death_worm v2，标记 2097152；基准 192 BattleAction_Alien；核心 r92，R3 r94；R4 行为库 v20 / 行为 v3，核心 r95；R5 行为库 v21 / 行为 v4，核心 r96）----------
// MSA 7.13.0 匿名命名空间 BattleAction_IronDeathWarm（虚表 0x4a742f0：update 0xef25d8、createObject 0xef2e38、shotBullet 0xef2f30、
// draw 0xef2fb4、startPosition 0xef304c、actionViewPosition 0xef30cc）与 EffectAction_DeadBody（虚表 0x4a743b0：update 0xef3134、
// createObject 0xef3208）在 MSD 原版侵略者类上的实现。r92 按 MSA 底层代码逐条核对（verification/iron_death_worm_20261025/msa_r2/
// FINDINGS_R2.md）。与蜈蚣长老、侵略者之王共用侵略者类的块与地面裁切绘制（按优先级分两遍，见 ec_draw_begin 之前的说明）。动作号为
// MSA 脚本号，存于 ZSpec 字 104–116（community_content.py）：待机、钻入、钻出、掘削、绝招钻入（兼损毁钻入）、地下钻击、损毁横穿、
// 爆炸、地下行进、碎块首槽与个数、损毁碎块首槽与个数（步长 2，落地动作为其后一个）。
// MSA 脚本指令 24–35、47–58（BattleSprite::EventCallback；MSD runScript 不识别，生成脚本已删）的作用由本段实现：全部动作的 op26
// EnableNockBack(false)（MSA 的击退为状态 70，changeState 0x10eb570 拒绝）→ 不击退（zombie_no_knockback 中 wd_guard 恒真；MSD 状态 80
// 若仍进入则预约状态 10、不切换动作）；掘削 17 的 op35 / op34 EveryTimeAtk（攻击框存在期间每 tick 重置攻击 ID，对象 update 0x10ec334 →
// BattleUnit 虚表 +0x160）→ 掘削动作中每 tick 以 BattleUnit::refreshAttackStatus 换新攻击 ID（攻击框已清除时 ID 为 0，不换），同一目标
// 每 tick 可再次受击；op54 / op56 攻击结算组 → 掘削 30、绝招钻入与钻击 50（单位 +0x88，每 tick 按当前动作写入）。
//  1 Alien::update（MSA update 0xef25d8），不进入原生；动作切换在末尾以尾调用交给原生 setAnimationID（参数同 MSA：动作、强制、清除移动）。
//    出场（MSA startPosition 置状态 78）：钻出，其间不近距攻击、不发动绝招（MSA +0x184 位 0x400 / 4），播完待机并预约状态 10；
//    单位菜单的动作演示中不出场。
//    10（MSA 通用待机 0x10d7b1c）：状态第一 tick 强制重播待机；
//    20：钻入（期间不近距攻击）→ 地下行进（用户 2026-10-25 要求；MSA 为钻入后移到敌方最前方单位前缘之前再钻出）：原生 actionMove 按
//        移速前进，高度取地形，不设受击框（R3）；转入 10 / 30 / 50 时在原处钻出，为近距攻击钻出后接着掘削、为绝招钻出后接着绝招钻入；
//    30（MSA 通用攻击 0x10d8e94）：掘削，播完进入攻击等待并待机；
//    50（MSA 绝招）：记下当前位置；钻入进行中先播完并在原处钻出，之后绝招钻入 25 → 选目标（前线 F 至 F + 朝向 × 绝招投射距离（词 33）
//        之间生命最低的敌方单位，不含战场道具 116，同生命取较靠前者；没有时为 F；动作演示中为原处前方 250）→ 移到其 x → 地下钻击 33 →
//        回到“F − 朝向 × 本单位宽度”与原处中较靠后者（动作演示中为原处）→ 钻出 → 待机并进入绝招等待。MSA 在钻击中置不可接触 /
//        不可选为目标 / 穿过，按用户要求不置（保持受击框）。攻击（R3，核心 r94，用户 2026-10-25：分段输出，范围跟随可见钻身）：25 与 33
//        在 MSA 的攻击时段（25 第 0–60 tick、33 第 0–59 tick）内由生成脚本每 4 tick 写一条 op4（攻击框为该段地面以上可见身体的外接矩形，
//        没有可见部分时为 0）；这两个动作中置身体状态 0x20（BattleObject::changeStateAttackIDReset），每条 op4 经 initAttackStatus 建立
//        新的攻击 ID，框内各目标每段各受 1 次（r92 / r93 为 MSA 原样的固定攻击框 3，每个动作对同一目标只结算一次）；
//    100–140 损毁（MSA 0xef263c）：开始时播放 25 → 播完移到本方舞台外侧（我方 −220、敌方舞台宽度 + 220，MSA 0x10df5b0）、置不可接触 /
//        穿过 / 不可选为目标（MSA 0x10ee200 / 0x10ee5a8 / 0x10ee630）→ 横穿 44（脚本 op7 的速度；高度随地形，第 6.2 节）越过舞台中央
//        （MSA 0x10df9ac）→ 爆炸 49 → 移除；
//    其余状态（含 MSD 70 胜利动作）：MSA 为默认分支（0x10dafd4，空），不切换动作。
//    钻入、钻出与绝招一经开始即按动作顺序进行到底（状态在其间改变时不打断）。
//    R5（用户 2026-10-25：钻入 / 钻出速度 200%，不影响大招的速度）：生成脚本把移动的钻入与平常的钻出换为 2 倍速的副本（字 105 / 106），
//    绝招中的钻出（绝招开始时在地下先于原处钻出、钻击后回原处钻出）改用字 120（原速的钻出）。
//  2 Alien::shotBullet（MSA 0xef2f30）：掘削的碎块（字 113 起字 114 个弹体脚本）经 addBulletNotAim 发射，攻击 ID（+0x144）新建
//    （MSA 碎块由自身的 op4 建立）；BulletAction_Alien::attackAction 改走 BattleBulletDefault::attackAction，结算后转入状态 60 消失（同 MSA
//    默认弹体 attackAction 0x10e54b8；原生侵略者弹体只在动作号为 20 时结算）。单位菜单的动作演示中不发射。
//  3 BattleUnitDefault::createObject（MSA createObject 0xef2e38）：损毁碎块（字 115 起每隔 1 共字 116 个）改以弹体建立（+0x28 为 21、
//    +0x24 记落地动作），按 MSA EffectAction_DeadBody 运动。
//  4 BulletAction_Alien::update：掘削碎块命中（状态 60）或落地（待定位置已到地形高度）时移除，脚本播完不移除（MSA 0x10e5304）；
//    R4（用户 2026-10-25：同 MS7 / MSXX，落地后随惯性弹跳、滚动，过 0.5 秒爆炸，碰到敌军立即爆炸，无索敌）：落地时以本 tick 的位移为速度，
//    横向乘 WD_BOUNCE_KEEP、纵向反向乘 WD_BOUNCE，改播滚动动作（字 117 起与碎块对应，种类 22，攻击 ID 保留）；此后每 tick 纵向加
//    WD_GRAVITY（碎块脚本 op45 的加速度 80 × 2 / 100），落到地形高度 − 落地时帧高的一半时再弹起，纵向速度不大于 WD_BOUNCE_MIN 时贴地
//    滚动、横向乘 WD_ROLL_FRICTION；落地后字 119 tick 或碰到敌方单位（状态 60，伤害由 BattleBulletDefault::attackAction 结算）时改播
//    爆炸（字 118，种类 23，攻击 ID 保留，碰到的目标不重复结算；爆炸攻击框伤害同碎块），播完移除；状态 200 时移除。
//    损毁碎块（MSA 0xef3134）：落地动作播完移除；否则向下运动且 y ≥ 地形高度（按待定 x）− 当前帧第一个矩形高 × 精灵缩放 / 2 时，
//    y 置为该值、改播落地动作并清除移动。
// 单位的状态只在客体对象内存：+0x24 记下的位置 x（整数）、+0x28 本次绝招已钻击、+0x2c 标记（1 已出场、2 已置不近距攻击、4 已置不发动
// 绝招、8 绝招进行中、16 已置攻击 ID 重置、32 损毁已开始）、+0x34 本动作 tick、+0x38 损毁时的舞台中央 x。弹体：+0x24 落地动作、
// +0x28 种类、+0x2c 存在 tick；R4 掘削碎块：+0x24 落地时的存在 tick、+0x30 / +0x34 横纵速度、+0x38 落地时帧高的一半。
// R4 部件判定（用户 2026-10-25：判定框贴合贴图）：生成脚本在描述符受击框 / 攻击框表中每个框之后接部件（第 5 值 WD_PART_MARK）。
//  5 BattleSprite::runScript 的 op3 / op4（0x101dbde6 / 0x101dbe2e，回调与命令已确认后）：本单位的框号记在 +0x3c / +0x40。
//  6 BattleObject::hitTest（0x101ddbca，this 为受击方、参数为攻击方攻击框的世界坐标；BattleObjectManager::advanceFrame 的全部命中判定
//    经此）：受击方为本单位且当前受击框有部件时，按各部件判定（按 op3 的换算：朝向与原画朝向不同时 x 取 −(x + w)，加精灵偏移
//    +0x34 / +0x38，× 2 加单位位置取整）；单位攻击单位的判定（返回地址 WD_UNIT_ATTACK_SITE，攻击方 r5）中攻击方为本单位且当前攻击框
//    有部件时，按攻击部件判定；两者都有时任一对相交即命中。外框（+0xcc–+0xd8、+0xdc–+0xe8）不变，供原生的其他用途。
static constexpr uint32_t WD_FLAG=2097152u,WD_W=104u,WD_DEBRIS=20u,WD_BODY=21u,WD_ROLL=22u,WD_BURST=23u;
static constexpr float WD_GRAVITY=1.6f,WD_BOUNCE=0.25f,WD_BOUNCE_KEEP=0.7f,WD_BOUNCE_MIN=3.0f,WD_ROLL_FRICTION=0.85f;
static constexpr uint32_t WD_DEBRIS_LIFE=600u;   // 碎块存在上限（tick）
static constexpr int32_t WD_PART_MARK=0x57445054,WD_MAX_PARTS=16;   // 'WDPT'
static constexpr uint32_t WD_HIT_INDEX=0x3cu,WD_ATTACK_INDEX=0x40u,WD_UNIT_ATTACK_SITE=0x101dfb75u;
static constexpr uint32_t WD_DONT_SHORT=0x1017859au,WD_STAGE_SIZE=0x101e1c20u;   // changeStateDontShortAttack、BattleStage::getStageSize
// BattleObject::changeStateDontToche / AreaThrough / NoTarget（MSA +0x184 位 8 / 0x10 / 0x40）、BattleUnit::refreshAttackStatus
static constexpr uint32_t WD_DONT_TOCHE=0x10177f76u,WD_AREA_THROUGH=0x10177f7eu,WD_NO_TARGET=0x101780d8u,WD_REFRESH_ID=0x101e0bd0u,
 WD_NEW_ID=0x101dfeecu,   // BattleObjectManager::createAttackID
 WD_ID_RESET=0x101780acu;   // BattleObject::changeStateAttackIDReset（身体状态 0x20）
static constexpr float WD_DEATH_FROM=220.0f,WD_VIEW_DRILL=250.0f;
enum:uint32_t{WD_NEUTRAL,WD_BURROW,WD_EMERGE,WD_NEAR,WD_DIVE,WD_DRILL,WD_DEATH_MOVE,WD_DEATH_BURST,WD_UNDER,
 WD_DEBRIS_FIRST,WD_DEBRIS_N,WD_BODY_FIRST,WD_BODY_N,WD_DEBRIS_ROLL,WD_DEBRIS_BURST,WD_DEBRIS_FUSE,WD_SP_EMERGE};
static uint32_t wd_w(Context& c,uint32_t s,uint32_t i){return zw(c,s,WD_W+i);}
static uint32_t wd_unit(Context& c,uint32_t o){uint32_t s=o?zspec(c,o):0u;return s&&(zw(c,s,0)&WD_FLAG)?s:0u;}
static uint32_t wd_bullet_spec(Context& c,uint32_t b){
 if(!active(c)||!head(c,168u)||!b||rd<uint32_t>(c,b)!=FS_BULLET_VPTR)return 0u;
 uint32_t uid=rd<uint32_t>(c,b+0x128u);if(!record(c,uid))return 0u;
 uint32_t s=rd<uint32_t>(c,head(c,168u)+(uid-U)*4u),kind=rd<uint32_t>(c,b+0x28u);
 return s&&(zw(c,s,0)&WD_FLAG)&&(kind==WD_DEBRIS||kind==WD_BODY||kind==WD_ROLL||kind==WD_BURST)?s:0u;
}
static bool wd_debris(Context& c,uint32_t b){return wd_bullet_spec(c,b)&&rd<uint32_t>(c,b+0x28u)!=WD_BODY;}
static float wd_width(Context& c,uint32_t u){return float(int32_t(is_call(c,IS_WIDTH,u)));}
static float wd_edge(Context& c,uint32_t u){return rd<float>(c,u+0x8cu)+float(ik_dir(c,u))*wd_width(c,u);}   // 单位前缘
static uint32_t wd_front(Context& c,uint32_t o){return rd<uint32_t>(c,IS_MANAGER+0x38u+((rd<uint32_t>(c,o+0x70u)&1u)^1u)*4u);}
// MSA 0x10dae34：限在本方据点与“敌方据点前缘 − 朝向 × 本单位宽度”之间
static float wd_clamp(Context& c,uint32_t o,float x){
 uint32_t team=rd<uint32_t>(c,o+0x70u)&1u,own=ik_base(c,team),foe=ik_base(c,team^1u);int32_t d=ik_dir(c,o);
 if(foe){float f=wd_edge(c,foe)-float(d)*wd_width(c,o);x=d>0?std::min(x,f):std::max(x,f);}
 if(own){float ox=rd<float>(c,own+0x8cu);x=d>0?std::max(x,ox):std::min(x,ox);}
 return x;
}
// MSA 0x10f9bfc：前线 = 敌方最前方单位的前缘，不越过敌方据点前缘（没有敌方单位时为敌方据点前缘）
static float wd_line(Context& c,uint32_t o){
 uint32_t foe=ik_base(c,(rd<uint32_t>(c,o+0x70u)&1u)^1u),t=wd_front(c,o);int32_t d=ik_dir(c,o);
 float lim=foe?wd_edge(c,foe):rd<float>(c,o+0x8cu);
 if(!t)return lim;
 float v=wd_edge(c,t);return d>0?std::min(lim,v):std::max(lim,v);
}
// MSA 0xef2af4：前线至前线 + 朝向 × 绝招投射距离（词 33）之间生命最低的敌方单位（整数 x；同生命取较靠前者），没有时为前线
static float wd_target(Context& c,uint32_t o){
 int32_t d=ik_dir(c,o),line=int32_t(wd_line(c,o)),reach=int32_t(is_status(c,o,33u)),best=line,hp=INT32_MAX,near=INT32_MAX;
 uint32_t u=is_call(c,IS_TEAM_UNITS,IS_MANAGER,(rd<uint32_t>(c,o+0x70u)&1u)^1u,0u);
 for(uint32_t k=0;u&&k<1024u;++k){
  int32_t h=rd<int32_t>(c,u+0x308u),ux=int32_t(rd<float>(c,u+0x8cu)),gap=(ux-line)*d;
  if(h>0&&rd<uint32_t>(c,u+0x7cu)<100u&&rd<uint32_t>(c,u+0x128u)!=116u&&gap>=0&&gap<=reach&&(h<hp||(h==hp&&gap<near))){hp=h;near=gap;best=ux;}
  uint32_t link=rd<uint32_t>(c,u+0x120u);u=link?link-0x11cu:0u;
 }
 return float(best);
}
// MSA 全部动作 op26 EnableNockBack(false)：不击退
static bool wd_guard(Context&,uint32_t,uint32_t){return true;}
static bool wd_update(Context& c){
 uint32_t act=c.r[0],o=c.r[1],state=c.r[2],frame=c.r[3],s=wd_unit(c,o);if(!s)return false;
 int32_t anim=int32_t(rd<uint32_t>(c,o+0xc4u)),pend=-1,d=ik_dir(c,o);uint32_t force=0u;
 auto A=[&](uint32_t i){return int32_t(wd_w(c,s,i));};
 auto emerge=[&](bool sp){return A(sp?WD_SP_EMERGE:WD_EMERGE);};   // R5：绝招中的钻出为原速
 auto cur=[&]{return pend>=0?pend:anim;};
 auto run=[&]{return pend>=0||rd<uint8_t>(c,o+0xc9u)!=0;};
 auto set=[&](int32_t a){pend=a;wr<uint32_t>(c,o+0x34u,0u);};
 auto is_any=[&](std::initializer_list<uint32_t> l){for(uint32_t i:l)if(cur()==A(i))return true;return false;};
 bool viewer=z_viewer(c),first=frame==0u;
 uint32_t fl=rd<uint32_t>(c,o+0x2cu),tick=rd<uint32_t>(c,o+0x34u)+1u;wr<uint32_t>(c,o+0x34u,tick);
 auto flag=[&](uint32_t bit,uint32_t fn,bool on){if(on!=((fl&bit)!=0u)){is_call(c,fn,o,on?1u:0u);fl=on?fl|bit:fl&~bit;}};
 auto place=[&](float x){ik_place(c,o,x,ik_ground(c,o,x));};
 auto special=[&]{fl|=8u;wr<int32_t>(c,o+0x24u,int32_t(rd<float>(c,o+0x8cu)));wr<uint32_t>(c,o+0x28u,0u);flag(2u,WD_DONT_SHORT,false);};
 if(state>=100u&&state<=140u){
  if(!(fl&32u)){fl|=32u;set(A(WD_DIVE));}
  else if(cur()==A(WD_DIVE)){
   if(!run()){
    uint32_t stage=viewer?0u:is_call(c,IS_STAGE,0u);
    if(!stage)is_call(c,IS_KILL,o);
    else{
     float size=float(int32_t(is_call(c,WD_STAGE_SIZE,stage)));
     wr<float>(c,o+0x38u,float(int32_t(size)/2));
     place((rd<uint32_t>(c,o+0x70u)&1u)?size+WD_DEATH_FROM:-WD_DEATH_FROM);set(A(WD_DEATH_MOVE));
     for(uint32_t fn:{WD_DONT_TOCHE,WD_AREA_THROUGH,WD_NO_TARGET})is_call(c,fn,o,1u);
    }
   }
  }else if(cur()==A(WD_DEATH_MOVE)){
   float x=rd<float>(c,o+0x8cu),half=rd<float>(c,o+0x38u),g=ik_ground(c,o,x);wr<float>(c,o+0x90u,g);wr<float>(c,o+0x98u,g);
   if((rd<uint32_t>(c,o+0x70u)&1u)?int32_t(x)<=int32_t(half):int32_t(half)<=int32_t(x))set(A(WD_DEATH_BURST));
  }else if(cur()==A(WD_DEATH_BURST)&&!run())is_call(c,IS_KILL,o);
 }else if(!viewer&&!(fl&1u)){
  // MSA 状态 78（startPosition 0xef304c / update 0xef2960）：钻出，播完待机并预约状态 10
  if(cur()!=A(WD_EMERGE)){set(A(WD_EMERGE));flag(2u,WD_DONT_SHORT,true);flag(4u,EC_DONT_SP,true);}
  else if(!run()){
   fl|=1u;flag(2u,WD_DONT_SHORT,false);flag(4u,EC_DONT_SP,false);set(A(WD_NEUTRAL));
   wr<uint32_t>(c,o+0x84u,10u);is_call(c,IS_RESERVE,o,10u,0u);
  }
 }else if(cur()==A(WD_UNDER)&&state!=20u){
  // 地下行进中转入 10 / 30 / 50：在原处钻出（绝招记下位置）；80（不应出现）预约回到移动；其余状态不切换动作
  if(state==80u)wr<uint32_t>(c,o+0x84u,20u);
  else if(state==10u||state==30u||state==50u){if(state==50u)special();set(emerge(state==50u));}
 }else if(is_any({WD_BURROW,WD_EMERGE,WD_SP_EMERGE,WD_DIVE,WD_DRILL})){
  // 移动与绝招的动作顺序（MSA update 状态 20 与 50 的分支；其间状态改变时不打断）
  bool sp=(fl&8u)!=0u;
  if(state==50u&&first&&!sp){special();sp=true;}
  if(run()){}
  else if(cur()==A(WD_BURROW)){
   if(sp||viewer)set(emerge(sp));                                      // MSA 状态 50 分支：钻入 7 播完在原处钻出 12
   else{flag(2u,WD_DONT_SHORT,false);set(A(WD_UNDER));}                // 地下行进（用户要求）
  }else if(cur()==A(WD_EMERGE)||cur()==A(WD_SP_EMERGE)){
   if(sp&&!rd<uint32_t>(c,o+0x28u))set(A(WD_DIVE));
   else if(sp){fl&=~8u;is_call(c,EC_START_WAIT,act,o,50u);set(A(WD_NEUTRAL));}
   else if(state==30u){flag(2u,WD_DONT_SHORT,false);set(A(WD_NEAR));}  // 为近距攻击钻出：接着掘削
   else{flag(2u,WD_DONT_SHORT,false);set(A(WD_NEUTRAL));wr<uint32_t>(c,o+0x84u,10u);is_call(c,IS_RESERVE,o,10u,0u);}
  }else if(cur()==A(WD_DIVE)){
   place(viewer?float(rd<int32_t>(c,o+0x24u))+float(d)*WD_VIEW_DRILL:wd_target(c,o));set(A(WD_DRILL));
  }else{   // 地下钻击结束：回到原处（敌方前线已越过原处时为前线之后）
   wr<uint32_t>(c,o+0x28u,1u);
   float back=float(rd<int32_t>(c,o+0x24u));
   if(!viewer){float f=wd_line(c,o)-float(d)*wd_width(c,o);back=wd_clamp(c,o,d>0?std::min(f,back):std::max(f,back));}
   place(back);set(emerge(true));
  }
 }else switch(state){
  case 10u:
   if(first){set(A(WD_NEUTRAL));force=1u;}
   break;
  case 20u:
   if(viewer){if(cur()!=A(WD_NEUTRAL))set(A(WD_NEUTRAL));break;}
   if(cur()==A(WD_UNDER)){   // 地下行进：原生 actionMove 按移速前进（遇敌方单位停住，由原生 AI 转入攻击），高度取地形（同蜈蚣长老）
    msd_guest_call(c,EC_ACTION_MOVE,act,o,l_bits(-1.0f),0u,nullptr);
    float g=ik_ground(c,o,rd<float>(c,o+0x94u));wr<float>(c,o+0x90u,g);wr<float>(c,o+0x98u,g);
   }else{set(A(WD_BURROW));flag(2u,WD_DONT_SHORT,true);}
   break;
  case 30u:
   if(first)set(A(WD_NEAR));
   else if(!run()){is_call(c,EC_START_WAIT,act,o,30u);set(A(WD_NEUTRAL));}
   break;
  case 50u:
   if(first){special();set(A(WD_DIVE));}
   break;
  case 80u:   // MSD 击退（本单位不击退，不应出现）：MSA changeState 拒绝，预约状态 10、不切换动作
   wr<uint32_t>(c,o+0x84u,10u);
   break;
  default:
   break;
 }
 // MSA op54 / op56：攻击结算组随动作；op35 / op34 EveryTimeAtk：掘削的攻击框存在期间每 tick 换新攻击 ID
 int32_t a=cur();
 if(a==A(WD_NEAR))wr<uint32_t>(c,o+0x88u,30u);else if(a==A(WD_DIVE)||a==A(WD_DRILL))wr<uint32_t>(c,o+0x88u,50u);
 if(!viewer&&pend<0&&anim==A(WD_NEAR))is_call(c,WD_REFRESH_ID,o);
 flag(16u,WD_ID_RESET,!viewer&&(a==A(WD_DIVE)||a==A(WD_DRILL)));   // R3：钻离与钻击每段（op4）新建攻击 ID
 wr<uint32_t>(c,o+0x2cu,fl);
 if(pend>=0){c.r[0]=o;c.r[1]=uint32_t(pend);c.r[2]=force;c.r[3]=1u;c.pc=IS_SET_ANIM|1u;}
 else c.pc=c.r[14];
 return true;
}
static bool wd_shot(Context& c){
 uint32_t act=c.r[0],o=c.r[1],script=c.r[2],s=wd_unit(c,o);if(!s)return false;
 int32_t x=int32_t(c.r[3]),y=rd<int32_t>(c,c.r[13]);uint32_t z=rd<uint32_t>(c,c.r[13]+4u),first=wd_w(c,s,WD_DEBRIS_FIRST);
 if(!z_viewer(c)&&script>=first&&script<first+wd_w(c,s,WD_DEBRIS_N)){
  uint32_t b=ec_fire(c,act,o,script,WD_DEBRIS,z,x,y);
  if(b)wr<uint16_t>(c,b+0x144u,uint16_t(is_call(c,WD_NEW_ID,IS_MANAGER,rd<uint32_t>(c,o+0x70u),0u)));
 }
 c.pc=c.r[14];return true;
}
// MSA createObject 0xef2e38：损毁碎块以 EffectAction_DeadBody 建立（落地动作 = 脚本 + 1）
static bool wd_create(Context& c){
 uint32_t act=c.r[0],o=c.r[1],script=c.r[2],s=wd_unit(c,o),sp=c.r[13];if(!s)return false;
 uint32_t first=wd_w(c,s,WD_BODY_FIRST),n=wd_w(c,s,WD_BODY_N);
 if(script<first||script>=first+2u*n||((script-first)&1u))return false;
 if(!z_viewer(c)){uint32_t b=ec_fire(c,act,o,script,WD_BODY,rd<uint32_t>(c,sp+4u),int32_t(c.r[3]),rd<int32_t>(c,sp));if(b)wr<uint32_t>(c,b+0x24u,script+1u);}
 c.pc=c.r[14];return true;
}
// 当前帧第一个矩形的高 × 精灵缩放（MSA 0xd4e9f8）
static float wd_frame_h(Context& c,uint32_t b){
 uint32_t sprite=rd<uint32_t>(c,b+0x5cu),root=sprite?rd<uint32_t>(c,sprite+0x58u):0u,desc=sprite?rd<uint32_t>(c,sprite+0x40u):0u;
 if(!root||!desc)return 0.0f;
 int32_t f=rd<int32_t>(c,root+8u);if(f<0)return 0.0f;
 uint32_t r=rd<uint32_t>(c,rd<uint32_t>(c,desc+12u)+uint32_t(f+1)*4u);
 return float(rd<int16_t>(c,rd<uint32_t>(c,desc+8u)+r*16u+6u))*rd<float>(c,sprite+0x28u);
}
// 掘削碎块（R4）：改播动作并保留攻击 ID（setAnimationID 清空攻击 ID）、放到 (x, y)
static void wd_debris_anim(Context& c,uint32_t b,uint32_t anim,uint32_t kind){
 uint16_t id=rd<uint16_t>(c,b+0x144u);is_call(c,IS_SET_ANIM,b,anim,0u,1u);wr<uint16_t>(c,b+0x144u,id);wr<uint32_t>(c,b+0x28u,kind);
}
static void wd_debris_place(Context& c,uint32_t b,float x,float y){wr<float>(c,b+0x8cu,x);wr<float>(c,b+0x94u,x);wr<float>(c,b+0x90u,y);wr<float>(c,b+0x98u,y);}
static bool wd_bullet_update(Context& c){
 uint32_t act=c.r[0],b=c.r[1],state=c.r[2],s=wd_bullet_spec(c,b);if(!s)return false;
 uint32_t age=rd<uint32_t>(c,b+0x2cu)+1u;wr<uint32_t>(c,b+0x2cu,age);
 if(rd<uint32_t>(c,b+0x28u)==WD_BODY){
  uint32_t land=rd<uint32_t>(c,b+0x24u);
  if(rd<uint32_t>(c,b+0xc4u)==land){if(rd<uint8_t>(c,b+0xc9u)==0u)is_call(c,IS_KILL,b);}
  else if(rd<float>(c,b+0xa8u)>0.0f){
   float g=float(stage_altitude(c,int32_t(rd<float>(c,b+0x94u))))-wd_frame_h(c,b)*0.5f;
   if(rd<float>(c,b+0x90u)>=g){wr<float>(c,b+0x90u,g);wr<float>(c,b+0x98u,g);is_call(c,IS_SET_ANIM,b,land,0u,1u);}
  }
 }else{
  uint32_t kind=rd<uint32_t>(c,b+0x28u);
  if(kind==WD_BURST){if(rd<uint8_t>(c,b+0xc9u)==0u)is_call(c,IS_KILL,b);}
  else if(state==200u||age>WD_DEBRIS_LIFE)is_call(c,IS_KILL,b);
  else if(state==60u){wd_debris_anim(c,b,wd_w(c,s,WD_DEBRIS_BURST),WD_BURST);wd_debris_place(c,b,rd<float>(c,b+0x8cu),rd<float>(c,b+0x90u));}
  else if(kind==WD_ROLL){
   float x=rd<float>(c,b+0x8cu),y=rd<float>(c,b+0x90u),vx=rd<float>(c,b+0x30u),vy=rd<float>(c,b+0x34u)+WD_GRAVITY;
   x+=vx;y+=vy;float g=float(stage_altitude(c,int32_t(x)))-rd<float>(c,b+0x38u);
   if(y>=g){y=g;if(vy>WD_BOUNCE_MIN){vy=-vy*WD_BOUNCE;vx*=WD_BOUNCE_KEEP;}else{vy=0.0f;vx*=WD_ROLL_FRICTION;}}
   wd_debris_place(c,b,x,y);wr<float>(c,b+0x30u,vx);wr<float>(c,b+0x34u,vy);
   if(age-rd<uint32_t>(c,b+0x24u)>=wd_w(c,s,WD_DEBRIS_FUSE))wd_debris_anim(c,b,wd_w(c,s,WD_DEBRIS_BURST),WD_BURST);
  }else if(state==59u||rd<float>(c,b+0x98u)>=float(stage_altitude(c,int32_t(rd<float>(c,b+0x94u))))||is_call(c,EC_ADJUST_GROUND,act,b)!=0u){
   // 落地（待定位置 +0x94 / +0x98 已到地形高度）：本 tick 的位移为速度，改播滚动动作并贴到地形
   float x0=rd<float>(c,b+0x8cu),y0=rd<float>(c,b+0x90u),x1=rd<float>(c,b+0x94u),y1=rd<float>(c,b+0x98u),half=wd_frame_h(c,b)*0.5f;
   uint32_t roll=wd_w(c,s,WD_DEBRIS_ROLL)+rd<uint32_t>(c,b+0xc4u)-wd_w(c,s,WD_DEBRIS_FIRST);
   wd_debris_anim(c,b,roll,WD_ROLL);wd_debris_place(c,b,x1,float(stage_altitude(c,int32_t(x1)))-half);
   wr<float>(c,b+0x30u,(x1-x0)*WD_BOUNCE_KEEP);wr<float>(c,b+0x34u,-(y1-y0)*WD_BOUNCE);wr<float>(c,b+0x38u,half);wr<uint32_t>(c,b+0x24u,age);
  }
 }
 c.pc=c.r[14];return true;
}
// R4 部件判定：框表 idx 之后的部件条目换为世界坐标（同 runScript op3 / op4 与 onEventSetHitRect / onEventSetAttackRect 的换算）
struct WdBox{int32_t l,t,r,b;};
static int32_t wd_parts(Context& c,uint32_t o,bool attack,WdBox* out){
 uint32_t sprite=rd<uint32_t>(c,o+0x5cu),desc=sprite?rd<uint32_t>(c,sprite+0x40u):0u;if(!desc)return 0;
 uint32_t table=rd<uint32_t>(c,desc+(attack?0x14u:0x10u)),idx=rd<uint32_t>(c,o+(attack?WD_ATTACK_INDEX:WD_HIT_INDEX));
 if(!table||!idx||idx>=4096u)return 0;
 bool same=rd<uint32_t>(c,sprite+0x48u)==rd<uint32_t>(c,sprite+0x10u);
 int32_t offx=rd<int32_t>(c,sprite+0x34u),offy=rd<int32_t>(c,sprite+0x38u),ox=int32_t(rd<float>(c,o+0x8cu)),oy=int32_t(rd<float>(c,o+0x90u)),n=0;
 for(uint32_t e=table+(idx+1u)*20u;n<WD_MAX_PARTS&&rd<int32_t>(c,e+16u)==WD_PART_MARK;e+=20u,++n){
  int32_t x=rd<int32_t>(c,e),y=rd<int32_t>(c,e+4u),w=rd<int32_t>(c,e+8u),h=rd<int32_t>(c,e+12u),lx=same?x+offx:-(x+w)-offx,ly=y+offy;
  out[n]={ox+2*lx,oy+2*ly,ox+2*(lx+w),oy+2*(ly+h)};
 }
 return n;
}
static uint32_t wd_part_hooks=0u;
static Block old_wd_op3;static void wd_op3(Context& c){uint32_t o=c.r[0]-8u;if(wd_unit(c,o))wr<uint32_t>(c,o+WD_HIT_INDEX,rd<uint32_t>(c,c.r[6]+4u));old_wd_op3(c);}
static Block old_wd_op4;static void wd_op4(Context& c){uint32_t o=c.r[0]-8u;if(wd_unit(c,o))wr<uint32_t>(c,o+WD_ATTACK_INDEX,rd<uint32_t>(c,c.r[6]+4u));old_wd_op4(c);}
static Block old_wd_hit_test;static void wd_hit_test(Context& c){
 uint32_t o=c.r[0],a=c.r[14]==WD_UNIT_ATTACK_SITE?c.r[5]:0u;
 bool empty=!rd<int32_t>(c,o+0xd4u)&&!rd<int32_t>(c,o+0xd8u);
 WdBox h[WD_MAX_PARTS],k[WD_MAX_PARTS];
 int32_t nh=!empty&&wd_unit(c,o)?wd_parts(c,o,false,h):0,na=a&&wd_unit(c,a)?wd_parts(c,a,true,k):0;
 if(!nh&&!na){old_wd_hit_test(c);return;}
 if(empty){ret(c,0u);return;}
 if(!nh){int32_t ox=int32_t(rd<float>(c,o+0x8cu)),oy=int32_t(rd<float>(c,o+0x90u));
  h[0]={ox+rd<int32_t>(c,o+0xccu),oy+rd<int32_t>(c,o+0xd0u),ox+rd<int32_t>(c,o+0xd4u),oy+rd<int32_t>(c,o+0xd8u)};nh=1;}
 if(!na){uint32_t r=c.r[1];k[0]={rd<int32_t>(c,r),rd<int32_t>(c,r+4u),rd<int32_t>(c,r+8u),rd<int32_t>(c,r+12u)};na=1;}
 for(int32_t i=0;i<na;++i)for(int32_t j=0;j<nh;++j)if(k[i].l<h[j].r&&k[i].r>h[j].l&&k[i].t<h[j].b&&k[i].b>h[j].t){ret(c,1u);return;}
 ret(c,0u);
}
// 版本 2（r92）：按 MSA 底层代码核对后的流程、地下行进与损毁碎块；3（r94）：绝招分段；4（r95）：部件判定、碎块弹跳滚动后爆炸；
// 5（r96）：绝招中的钻出用字 120
extern "C" __declspec(dllexport) uint32_t msd_community_iron_death_worm_version(){return elder_centipede_hooks==10u&&wd_part_hooks==3u?5u:0u;}
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
// 修筑单位的浏览模式沿用原版初始化位置与完成箱体选择流程。基准 77（木乃伊生成器）与基准 5（工兵，核心 r82 起）的
// 社区单位在原生浏览的 UnitID 判定中按基准单位处理。
static uint32_t viewer_builder(Context& c,uint32_t uid){uint32_t p=record(c,uid),b=p?rd<uint32_t>(c,p+4u):0u;return b==77u||b==5u?b:0u;}
HOOK(mummy_viewer_setup,0x1020a665u,
 if(viewer_builder(c,c.r[4])&&head(c,104)&&rd<uint32_t>(c,head(c,104)+(c.r[4]-U)*4u)!=c.r[4]){
  wr<uint32_t>(c,c.r[5]+176u,300u);wr<uint32_t>(c,c.r[5]+180u,400u);
  c.pc=0x1020a9a7u;return;
 })
HOOK(mummy_viewer_child,0x1020a571u,
 uint32_t b=viewer_builder(c,c.r[0]);if(b)c.r[0]=b;
 )
HOOK(mummy_viewer_update,0x1020b0edu,
 uint32_t b=viewer_builder(c,c.r[0]);if(b){
  uint32_t object=c.r[4];uint32_t state=rd<uint32_t>(c,object+0x7cu);
  if((state==10u||state==20u)&&rd<float>(c,object+0x8cu)<320.0f){
   wr<uint32_t>(c,object+0x80u,20u);wr<uint32_t>(c,object+0x84u,20u);
  }
  c.r[0]=b;
 }
 )
HOOK(mummy_viewer_initial_state,0x1020ab2du,
 uint32_t object=rd<uint32_t>(c,c.r[7]+24u);
 if(object&&viewer_builder(c,rd<uint32_t>(c,object+0x128u))){wr<uint32_t>(c,object+0x80u,20u);wr<uint32_t>(c,object+0x84u,20u);}
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
