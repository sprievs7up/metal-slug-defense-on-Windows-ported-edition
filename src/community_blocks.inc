static Block old_block_101c9abc;
static void cc_101c9abc(Context& c){if(!active(c)){old_block_101c9abc(c);return;}
{uint32_t v=add(c,real_unit(c,c.r[4])?0u:1u,~(1u),1,true);}
{}
{if(cond(c,3)){uint32_t v=0u;c.r[0]=v;}}
{if(cond(c,4)){uint32_t v=1u;c.r[0]=v;}}
{uint32_t a=c.r[13];c.r[4]=rd<uint32_t>(c,a+0u);uint32_t newpc=rd<uint32_t>(c,a+4u);c.r[13]=a+8u;c.pc=newpc;return;}
c.pc=270310089u;}
static Block old_block_101d09b4;
static void cc_101d09b4(Context& c){if(!active(c)){old_block_101d09b4(c);return;}
{uint32_t a=(c.r[5]+0u+132u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[3],~(0u),1,true);}
{}
{if(cond(c,14)){uint32_t a=(c.r[5]+0u+28u);c.r[3]=rd<uint32_t>(c,a+0u);}}
{uint32_t a=(c.r[5]+0u+208u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+888u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[5]+0u+212u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+892u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[5]+0u+216u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+896u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[5]+0u+220u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+900u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[5]+0u+224u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+904u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[5]+0u+228u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+908u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[5]+0u+232u);wr<uint32_t>(c,a+0u,c.r[3]);}
apply_combat_status(c,c.r[5]);
{uint32_t v=add(c,c.r[13],32u,0,false);c.r[13]=v;}
{uint32_t a=c.r[13];c.d[8]=rd<uint64_t>(c,a+0u);c.r[13]=a+8u;}
{uint32_t a=c.r[13];c.r[4]=rd<uint32_t>(c,a+0u);c.r[5]=rd<uint32_t>(c,a+4u);c.r[6]=rd<uint32_t>(c,a+8u);uint32_t newpc=rd<uint32_t>(c,a+12u);c.r[13]=a+16u;c.pc=newpc;return;}
c.pc=270338555u;}
static Block old_block_101d09c2;
static void cc_101d09c2(Context& c){if(!active(c)){old_block_101d09c2(c);return;}
{uint32_t a=(c.r[4]+0u+888u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[5]+0u+212u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+892u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[5]+0u+216u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+896u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[5]+0u+220u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+900u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[5]+0u+224u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+904u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[5]+0u+228u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+908u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[5]+0u+232u);wr<uint32_t>(c,a+0u,c.r[3]);}
apply_combat_status(c,c.r[5]);
{uint32_t v=add(c,c.r[13],32u,0,false);c.r[13]=v;}
{uint32_t a=c.r[13];c.d[8]=rd<uint64_t>(c,a+0u);c.r[13]=a+8u;}
{uint32_t a=c.r[13];c.r[4]=rd<uint32_t>(c,a+0u);c.r[5]=rd<uint32_t>(c,a+4u);c.r[6]=rd<uint32_t>(c,a+8u);uint32_t newpc=rd<uint32_t>(c,a+12u);c.r[13]=a+16u;c.pc=newpc;return;}
c.pc=270338555u;}
static Block old_block_101dacbc;
static void cc_101dacbc(Context& c){if(!active(c)){old_block_101dacbc(c);return;}
{uint32_t a=(c.r[0]+0u+16u);c.r[5]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[7],56u,0,false);c.r[12]=v;}
{uint32_t a=(c.r[13]+0u+28u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[13],104u,0,false);c.r[11]=v;}
{uint32_t a=(c.r[4]+0u+200u);c.r[0]=rd<uint32_t>(c,a+0u);}
{uint32_t v=shift(c,c.r[12],4u,1,false);c.r[12]=v;}
{uint32_t v=(record(c,c.r[5])?head(c,52)+(c.r[5]-U)*16u:add(c,c.r[2],shift(c,c.r[5],4,1,false),0,false));c.r[5]=v;}
{uint32_t v=c.r[6];c.r[1]=v;}
{uint32_t v=add(c,c.r[0],c.r[12],0,false);c.r[0]=v;}
{uint32_t a=(c.r[5]+0u+6u);c.r[2]=uint32_t(rd<int16_t>(c,a+0u));}
{uint32_t a=(c.r[5]+0u+4u);c.r[3]=uint32_t(rd<int16_t>(c,a+0u));}
{uint32_t a=(c.r[13]+0u+0u);wr<uint32_t>(c,a+0u,c.r[2]);}
{uint32_t a=(c.r[5]+0u+8u);c.r[2]=uint32_t(rd<int16_t>(c,a+0u));}
{uint32_t a=(c.r[13]+0u+4u);wr<uint32_t>(c,a+0u,c.r[2]);}
{uint32_t a=(c.r[5]+0u+10u);c.r[2]=uint32_t(rd<int16_t>(c,a+0u));}
{uint32_t a=(c.r[13]+0u+20u);wr<uint32_t>(c,a+0u,c.r[12]);}
{uint32_t a=(c.r[13]+0u+8u);wr<uint32_t>(c,a+0u,c.r[2]);}
{uint32_t v=c.r[8];c.r[2]=v;}
{c.r[14]=270380281u;c.pc=(270361786u|1u);return;}
c.pc=270380281u;}
static Block old_block_101dc844;
static void cc_101dc844(Context& c){if(!active(c)){old_block_101dc844(c);return;}
{uint32_t a=c.r[13]-24u;wr<uint32_t>(c,a+0u,c.r[4]);wr<uint32_t>(c,a+4u,c.r[5]);wr<uint32_t>(c,a+8u,c.r[6]);wr<uint32_t>(c,a+12u,c.r[7]);wr<uint32_t>(c,a+16u,c.r[8]);wr<uint32_t>(c,a+20u,c.r[14]);c.r[13]=a;}
{uint32_t v=image_base(c,add(c,c.r[0],57600u,0,false));c.r[0]=v;}
{uint32_t a=((270387280u&~3u)+0u+60u);c.r[8]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[0],8u,0,false));c.r[6]=v;}
{uint32_t v=0u;nz(c,v);c.r[4]=v;}
{uint32_t v=image_base(c,add(c,c.r[8],270387290u,0,false));c.r[8]=v;}
{uint32_t a=(c.r[6]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+c.r[4]+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{if(c.r[3] != 0){c.pc=(270387308u|1u);return;}}
c.pc=270387295u;}
static Block old_block_101dc85e;
static void cc_101dc85e(Context& c){if(!active(c)){old_block_101dc85e(c);return;}
{uint32_t v=image_base(c,add(c,c.r[4],4u,0,true));c.r[4]=v;}
{uint32_t v=(4u*images(c));c.r[3]=v;}
{uint32_t v=image_base(c,add(c,c.r[4],~(c.r[3]),1,true));}
{if(cond(c,2)){c.pc=(270387288u|1u);return;}}
c.pc=270387305u;}
static Block old_block_101dc86c;
static void cc_101dc86c(Context& c){if(!active(c)){old_block_101dc86c(c);return;}
{uint32_t a=(c.r[8]+shift(c,c.r[4],1,1,false)+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=0u;nz(c,v);c.r[5]=v;}
{uint32_t a=(c.r[3]+0u+0u);c.r[7]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[5],~(c.r[7]),1,true));}
{if(cond(c,11)){c.pc=(270387294u|1u);return;}}
c.pc=270387321u;}
static Block old_block_101dc874;
static void cc_101dc874(Context& c){if(!active(c)){old_block_101dc874(c);return;}
{uint32_t v=image_base(c,add(c,c.r[5],~(c.r[7]),1,true));}
{if(cond(c,11)){c.pc=(270387294u|1u);return;}}
c.pc=270387321u;}
static Block old_block_101dc886;
static void cc_101dc886(Context& c){if(!active(c)){old_block_101dc886(c);return;}
{uint32_t v=image_base(c,add(c,c.r[5],1u,0,true));c.r[5]=v;}
{c.pc=(270387316u|1u);return;}
c.pc=270387339u;}
static Block old_block_101dc890;
static void cc_101dc890(Context& c){if(!active(c)){old_block_101dc890(c);return;}
{uint32_t a=c.r[13]-24u;wr<uint32_t>(c,a+0u,c.r[4]);wr<uint32_t>(c,a+4u,c.r[5]);wr<uint32_t>(c,a+8u,c.r[6]);wr<uint32_t>(c,a+12u,c.r[7]);wr<uint32_t>(c,a+16u,c.r[8]);wr<uint32_t>(c,a+20u,c.r[14]);c.r[13]=a;}
{uint32_t v=image_base(c,add(c,c.r[0],57600u,0,false));c.r[0]=v;}
{uint32_t a=((270387356u&~3u)+0u+60u);c.r[8]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[0],8u,0,false));c.r[6]=v;}
{uint32_t v=0u;nz(c,v);c.r[4]=v;}
{uint32_t v=image_base(c,add(c,c.r[8],270387366u,0,false));c.r[8]=v;}
{uint32_t a=(c.r[6]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+c.r[4]+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{if(c.r[3] != 0){c.pc=(270387384u|1u);return;}}
c.pc=270387371u;}
static Block old_block_101dc8aa;
static void cc_101dc8aa(Context& c){if(!active(c)){old_block_101dc8aa(c);return;}
{uint32_t v=image_base(c,add(c,c.r[4],4u,0,true));c.r[4]=v;}
{uint32_t v=(4u*images(c));c.r[3]=v;}
{uint32_t v=image_base(c,add(c,c.r[4],~(c.r[3]),1,true));}
{if(cond(c,2)){c.pc=(270387364u|1u);return;}}
c.pc=270387381u;}
static Block old_block_101dc8b8;
static void cc_101dc8b8(Context& c){if(!active(c)){old_block_101dc8b8(c);return;}
{uint32_t a=(c.r[8]+shift(c,c.r[4],1,1,false)+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=0u;nz(c,v);c.r[5]=v;}
{uint32_t a=(c.r[3]+0u+0u);c.r[7]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[5],~(c.r[7]),1,true));}
{if(cond(c,11)){c.pc=(270387370u|1u);return;}}
c.pc=270387397u;}
static Block old_block_101dc8c0;
static void cc_101dc8c0(Context& c){if(!active(c)){old_block_101dc8c0(c);return;}
{uint32_t v=image_base(c,add(c,c.r[5],~(c.r[7]),1,true));}
{if(cond(c,11)){c.pc=(270387370u|1u);return;}}
c.pc=270387397u;}
static Block old_block_101dc8d2;
static void cc_101dc8d2(Context& c){if(!active(c)){old_block_101dc8d2(c);return;}
{uint32_t v=image_base(c,add(c,c.r[5],1u,0,true));c.r[5]=v;}
{c.pc=(270387392u|1u);return;}
c.pc=270387415u;}
static Block old_block_101dc8dc;
static void cc_101dc8dc(Context& c){if(!active(c)){old_block_101dc8dc(c);return;}
{uint32_t a=c.r[13]-24u;wr<uint32_t>(c,a+0u,c.r[4]);wr<uint32_t>(c,a+4u,c.r[5]);wr<uint32_t>(c,a+8u,c.r[6]);wr<uint32_t>(c,a+12u,c.r[7]);wr<uint32_t>(c,a+16u,c.r[8]);wr<uint32_t>(c,a+20u,c.r[14]);c.r[13]=a;}
{uint32_t v=image_base(c,add(c,c.r[0],57600u,0,false));c.r[0]=v;}
{uint32_t a=((270387432u&~3u)+0u+60u);c.r[8]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[0],8u,0,false));c.r[6]=v;}
{uint32_t v=0u;nz(c,v);c.r[4]=v;}
{uint32_t v=image_base(c,add(c,c.r[8],270387442u,0,false));c.r[8]=v;}
{uint32_t a=(c.r[6]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+c.r[4]+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{if(c.r[3] != 0){c.pc=(270387460u|1u);return;}}
c.pc=270387447u;}
static Block old_block_101dc8f6;
static void cc_101dc8f6(Context& c){if(!active(c)){old_block_101dc8f6(c);return;}
{uint32_t v=image_base(c,add(c,c.r[4],4u,0,true));c.r[4]=v;}
{uint32_t v=(4u*images(c));c.r[3]=v;}
{uint32_t v=image_base(c,add(c,c.r[4],~(c.r[3]),1,true));}
{if(cond(c,2)){c.pc=(270387440u|1u);return;}}
c.pc=270387457u;}
static Block old_block_101dc904;
static void cc_101dc904(Context& c){if(!active(c)){old_block_101dc904(c);return;}
{uint32_t a=(c.r[8]+shift(c,c.r[4],1,1,false)+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=0u;nz(c,v);c.r[5]=v;}
{uint32_t a=(c.r[3]+0u+0u);c.r[7]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[5],~(c.r[7]),1,true));}
{if(cond(c,11)){c.pc=(270387446u|1u);return;}}
c.pc=270387473u;}
static Block old_block_101dc90c;
static void cc_101dc90c(Context& c){if(!active(c)){old_block_101dc90c(c);return;}
{uint32_t v=image_base(c,add(c,c.r[5],~(c.r[7]),1,true));}
{if(cond(c,11)){c.pc=(270387446u|1u);return;}}
c.pc=270387473u;}
static Block old_block_101dc91e;
static void cc_101dc91e(Context& c){if(!active(c)){old_block_101dc91e(c);return;}
{uint32_t v=image_base(c,add(c,c.r[5],1u,0,true));c.r[5]=v;}
{c.pc=(270387468u|1u);return;}
c.pc=270387491u;}
static Block old_block_101dc92a;
static void cc_101dc92a(Context& c){if(!active(c)){old_block_101dc92a(c);return;}
{uint32_t v=image_base(c,add(c,c.r[0],404u,0,false));c.r[0]=v;}
{c.pc=c.r[14];return;}
c.pc=270387505u;}
static Block old_block_101dc938;
static void cc_101dc938(Context& c){if(!active(c)){old_block_101dc938(c);return;}
{uint32_t a=((270387516u&~3u)+0u+68u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=c.r[5];c.r[4]=v;}
{uint32_t v=image_base(c,add(c,c.r[3],270387520u,0,false));c.r[3]=v;}
{uint32_t a=(c.r[3]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[3],8u,0,true));c.r[3]=v;}
{uint32_t a=(c.r[4]+0u+0u);uint32_t wb=c.r[4]+4u;wr<uint32_t>(c,a+0u,c.r[3]);c.r[4]=wb;}
{uint32_t v=image_base(c,add(c,c.r[4],57600u,0,false));c.r[6]=v;}
{uint32_t v=c.r[4];c.r[0]=v;}
{uint32_t v=image_base(c,add(c,c.r[4],96u,0,true));c.r[4]=v;}
{c.r[14]=270387539u;c.pc=(270382792u|1u);return;}
c.pc=270387539u;}
static Block old_block_101dc94a;
static void cc_101dc94a(Context& c){if(!active(c)){old_block_101dc94a(c);return;}
{uint32_t v=c.r[4];c.r[0]=v;}
{uint32_t v=image_base(c,add(c,c.r[4],96u,0,true));c.r[4]=v;}
{c.r[14]=270387539u;c.pc=(270382792u|1u);return;}
c.pc=270387539u;}
static Block old_block_101dc952;
static void cc_101dc952(Context& c){if(!active(c)){old_block_101dc952(c);return;}
{uint32_t v=image_base(c,add(c,c.r[4],~(c.r[6]),1,true));}
{if(cond(c,2)){c.pc=(270387530u|1u);return;}}
c.pc=270387543u;}
static Block old_block_101dc956;
static void cc_101dc956(Context& c){if(!active(c)){old_block_101dc956(c);return;}
{uint32_t v=(4u*images(c));c.r[0]=v;}
{c.r[14]=270387551u;c.pc=(270690404u|1u);return;}
c.pc=270387551u;}
static Block old_block_101dc95e;
static void cc_101dc95e(Context& c){if(!active(c)){old_block_101dc95e(c);return;}
{uint32_t v=image_base(c,add(c,c.r[5],57600u,0,false));c.r[2]=v;}
{uint32_t v=0u;nz(c,v);c.r[3]=v;}
{uint32_t v=c.r[3];c.r[4]=v;}
{uint32_t a=(c.r[2]+0u+8u);wr<uint32_t>(c,a+0u,c.r[0]);}
{uint32_t v=(4u*images(c));c.r[0]=v;}
{uint32_t a=(c.r[2]+0u+8u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[1]+c.r[3]+0u);wr<uint32_t>(c,a+0u,c.r[4]);}
{uint32_t v=image_base(c,add(c,c.r[3],4u,0,true));c.r[3]=v;}
{uint32_t v=image_base(c,add(c,c.r[3],~(c.r[0]),1,true));}
{if(cond(c,2)){c.pc=(270387564u|1u);return;}}
c.pc=270387575u;}
static Block old_block_101dc96c;
static void cc_101dc96c(Context& c){if(!active(c)){old_block_101dc96c(c);return;}
{uint32_t a=(c.r[2]+0u+8u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[1]+c.r[3]+0u);wr<uint32_t>(c,a+0u,c.r[4]);}
{uint32_t v=image_base(c,add(c,c.r[3],4u,0,true));c.r[3]=v;}
{uint32_t v=image_base(c,add(c,c.r[3],~(c.r[0]),1,true));}
{if(cond(c,2)){c.pc=(270387564u|1u);return;}}
c.pc=270387575u;}
static Block old_block_101dc984;
static void cc_101dc984(Context& c){if(!active(c)){old_block_101dc984(c);return;}
{uint32_t a=c.r[13]-16u;wr<uint32_t>(c,a+0u,c.r[3]);wr<uint32_t>(c,a+4u,c.r[4]);wr<uint32_t>(c,a+8u,c.r[5]);wr<uint32_t>(c,a+12u,c.r[14]);c.r[13]=a;}
{uint32_t a=((270387594u&~3u)+0u+56u);c.r[4]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[4],270387596u,0,false));c.r[4]=v;}
{uint32_t a=(c.r[4]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=shift(c,c.r[3],31u,1,true);nz(c,v);c.r[3]=v;}
{if(cond(c,5)){c.pc=(270387638u|1u);return;}}
c.pc=270387601u;}
static Block old_block_101dc998;
static void cc_101dc998(Context& c){if(!active(c)){old_block_101dc998(c);return;}
{uint32_t v=image_base(c,add(c,c.r[4],4u,0,true));c.r[5]=v;}
{uint32_t v=c.r[5];c.r[0]=v;}
{c.r[14]=270387617u;c.pc=(270387504u|1u);return;}
c.pc=270387617u;}
static Block old_block_101dc9a6;
static void cc_101dc9a6(Context& c){if(!active(c)){old_block_101dc9a6(c);return;}
{uint32_t a=((270387626u&~3u)+0u+28u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=((270387628u&~3u)+0u+28u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=c.r[5];c.r[0]=v;}
{uint32_t v=image_base(c,add(c,c.r[1],270387632u,0,false));c.r[1]=v;}
{uint32_t a=(c.r[1]+0u+0u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[2],270387636u,0,false));c.r[2]=v;}
{c.r[14]=270387639u;c.pc=(269636940u|0u);return;}
c.pc=270387639u;}
static Block old_block_101dc9b6;
static void cc_101dc9b6(Context& c){if(!active(c)){old_block_101dc9b6(c);return;}
{uint32_t a=((270387642u&~3u)+0u+20u);c.r[0]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[0],270387644u,0,false));c.r[0]=v;}
{uint32_t v=image_base(c,add(c,c.r[0],4u,0,true));c.r[0]=v;}
{uint32_t a=c.r[13];c.r[3]=rd<uint32_t>(c,a+0u);c.r[4]=rd<uint32_t>(c,a+4u);c.r[5]=rd<uint32_t>(c,a+8u);uint32_t newpc=rd<uint32_t>(c,a+12u);c.r[13]=a+16u;c.pc=newpc;return;}
c.pc=270387647u;}
static Block old_block_101dc9d4;
static void cc_101dc9d4(Context& c){if(!active(c)){old_block_101dc9d4(c);return;}
{uint32_t a=((270387672u&~3u)+0u+52u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=c.r[13]-16u;wr<uint32_t>(c,a+0u,c.r[4]);wr<uint32_t>(c,a+4u,c.r[5]);wr<uint32_t>(c,a+8u,c.r[6]);wr<uint32_t>(c,a+12u,c.r[14]);c.r[13]=a;}
{uint32_t v=image_base(c,add(c,c.r[3],270387676u,0,false));c.r[3]=v;}
{uint32_t a=(c.r[3]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=c.r[0];c.r[6]=v;}
{uint32_t v=image_base(c,add(c,c.r[3],8u,0,true));c.r[3]=v;}
{uint32_t a=(c.r[6]+0u+0u);uint32_t wb=c.r[6]+4u;wr<uint32_t>(c,a+0u,c.r[3]);c.r[6]=wb;}
{uint32_t v=c.r[0];c.r[4]=v;}
{c.r[14]=270387691u;c.pc=(270387666u|1u);return;}
c.pc=270387691u;}
static Block old_block_101dc9ea;
static void cc_101dc9ea(Context& c){if(!active(c)){old_block_101dc9ea(c);return;}
{uint32_t v=image_base(c,add(c,c.r[4],57600u,0,false));c.r[5]=v;}
{uint32_t v=image_base(c,add(c,c.r[5],4u,0,true));c.r[5]=v;}
{uint32_t v=image_base(c,add(c,c.r[5],~(c.r[6]),1,true));}
{if(cond(c,1)){c.pc=(270387712u|1u);return;}}
c.pc=270387701u;}
static Block old_block_101dc9f0;
static void cc_101dc9f0(Context& c){if(!active(c)){old_block_101dc9f0(c);return;}
{uint32_t v=image_base(c,add(c,c.r[5],~(c.r[6]),1,true));}
{if(cond(c,1)){c.pc=(270387712u|1u);return;}}
c.pc=270387701u;}
static Block old_block_101dca24;
static void cc_101dca24(Context& c){if(!active(c)){old_block_101dca24(c);return;}
{uint32_t a=c.r[13]-36u;wr<uint32_t>(c,a+0u,c.r[4]);wr<uint32_t>(c,a+4u,c.r[5]);wr<uint32_t>(c,a+8u,c.r[6]);wr<uint32_t>(c,a+12u,c.r[7]);wr<uint32_t>(c,a+16u,c.r[8]);wr<uint32_t>(c,a+20u,c.r[9]);wr<uint32_t>(c,a+24u,c.r[10]);wr<uint32_t>(c,a+28u,c.r[11]);wr<uint32_t>(c,a+32u,c.r[14]);c.r[13]=a;}
{uint32_t v=image_base(c,add(c,c.r[13],~(516u),1,false));c.r[13]=v;}
{uint32_t v=0u;nz(c,v);c.r[1]=v;}
{uint32_t v=c.r[0];c.r[6]=v;}
{uint32_t v=images(c);c.r[2]=v;}
{uint32_t v=c.r[13];c.r[0]=v;}
{c.r[14]=270387769u;c.pc=(269634900u|0u);return;}
c.pc=270387769u;}
static Block old_block_101dca38;
static void cc_101dca38(Context& c){if(!active(c)){old_block_101dca38(c);return;}
{uint32_t v=c.r[13];c.r[8]=v;}
{uint32_t v=0u;nz(c,v);c.r[3]=v;}
{uint32_t v=1u;nz(c,v);c.r[1]=v;}
{uint32_t v=image_base(c,add(c,c.r[6],c.r[3],0,true));c.r[2]=v;}
{uint32_t v=image_base(c,add(c,c.r[3],96u,0,true));c.r[3]=v;}
{uint32_t a=(c.r[2]+0u+8u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[2],~(0u),1,true));}
{}
{if(cond(c,11)){uint32_t a=(c.r[8]+c.r[2]+0u);wr<uint8_t>(c,a+0u,c.r[1]);}}
{uint32_t v=image_base(c,add(c,c.r[3],~(57600u),1,true));}
{if(cond(c,2)){c.pc=(270387774u|1u);return;}}
c.pc=270387795u;}
static Block old_block_101dca3e;
static void cc_101dca3e(Context& c){if(!active(c)){old_block_101dca3e(c);return;}
{uint32_t v=image_base(c,add(c,c.r[6],c.r[3],0,true));c.r[2]=v;}
{uint32_t v=image_base(c,add(c,c.r[3],96u,0,true));c.r[3]=v;}
{uint32_t a=(c.r[2]+0u+8u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[2],~(0u),1,true));}
{}
{if(cond(c,11)){uint32_t a=(c.r[8]+c.r[2]+0u);wr<uint8_t>(c,a+0u,c.r[1]);}}
{uint32_t v=image_base(c,add(c,c.r[3],~(57600u),1,true));}
{if(cond(c,2)){c.pc=(270387774u|1u);return;}}
c.pc=270387795u;}
static Block old_block_101dca52;
static void cc_101dca52(Context& c){if(!active(c)){old_block_101dca52(c);return;}
{uint32_t a=((270387798u&~3u)+0u+100u);c.r[9]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[6],57600u,0,false));c.r[6]=v;}
{uint32_t v=image_base(c,add(c,c.r[6],8u,0,true));c.r[6]=v;}
{uint32_t v=0u;nz(c,v);c.r[4]=v;}
{uint32_t v=image_base(c,add(c,c.r[9],270387810u,0,false));c.r[9]=v;}
{uint32_t a=(c.r[6]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=shift(c,c.r[4],2u,1,true);nz(c,v);c.r[7]=v;}
{uint32_t a=(c.r[3]+shift(c,c.r[4],2,1,false)+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{if(c.r[3] == 0){c.pc=(270387880u|1u);return;}}
c.pc=270387819u;}
static Block old_block_101dca70;
static void cc_101dca70(Context& c){if(!active(c)){old_block_101dca70(c);return;}
{uint32_t a=(c.r[9]+shift(c,c.r[4],3,1,false)+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=c.r[5];c.r[11]=v;}
{uint32_t a=(c.r[3]+0u+0u);c.r[10]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[5],~(c.r[10]),1,true));}
{uint32_t a=(c.r[6]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{if(cond(c,11)){c.pc=(270387866u|1u);return;}}
c.pc=270387841u;}
static Block old_block_101dca7a;
static void cc_101dca7a(Context& c){if(!active(c)){old_block_101dca7a(c);return;}
{uint32_t v=image_base(c,add(c,c.r[5],~(c.r[10]),1,true));}
{uint32_t a=(c.r[6]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{if(cond(c,11)){c.pc=(270387866u|1u);return;}}
c.pc=270387841u;}
static Block old_block_101dca8e;
static void cc_101dca8e(Context& c){if(!active(c)){old_block_101dca8e(c);return;}
{uint32_t a=(c.r[6]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+c.r[7]+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+shift(c,c.r[5],2,1,false)+0u);wr<uint32_t>(c,a+0u,c.r[11]);}
{uint32_t v=image_base(c,add(c,c.r[5],1u,0,true));c.r[5]=v;}
{c.pc=(270387834u|1u);return;}
c.pc=270387867u;}
static Block old_block_101dca96;
static void cc_101dca96(Context& c){if(!active(c)){old_block_101dca96(c);return;}
{uint32_t v=image_base(c,add(c,c.r[5],1u,0,true));c.r[5]=v;}
{c.pc=(270387834u|1u);return;}
c.pc=270387867u;}
static Block old_block_101dcaa2;
static void cc_101dcaa2(Context& c){if(!active(c)){old_block_101dcaa2(c);return;}
{uint32_t a=(c.r[6]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=0u;nz(c,v);c.r[2]=v;}
{uint32_t a=(c.r[3]+c.r[7]+0u);wr<uint32_t>(c,a+0u,c.r[2]);}
{uint32_t v=image_base(c,add(c,c.r[4],1u,0,true));c.r[4]=v;}
{uint32_t v=images(c);c.r[3]=v;}
{uint32_t v=image_base(c,add(c,c.r[4],~(c.r[3]),1,true));}
{if(cond(c,2)){c.pc=(270387808u|1u);return;}}
c.pc=270387891u;}
static Block old_block_101dcaa8;
static void cc_101dcaa8(Context& c){if(!active(c)){old_block_101dcaa8(c);return;}
{uint32_t v=image_base(c,add(c,c.r[4],1u,0,true));c.r[4]=v;}
{uint32_t v=images(c);c.r[3]=v;}
{uint32_t v=image_base(c,add(c,c.r[4],~(c.r[3]),1,true));}
{if(cond(c,2)){c.pc=(270387808u|1u);return;}}
c.pc=270387891u;}
static Block old_block_101dcab2;
static void cc_101dcab2(Context& c){if(!active(c)){old_block_101dcab2(c);return;}
{uint32_t v=image_base(c,add(c,c.r[13],516u,0,false));c.r[13]=v;}
{uint32_t a=c.r[13];c.r[4]=rd<uint32_t>(c,a+0u);c.r[5]=rd<uint32_t>(c,a+4u);c.r[6]=rd<uint32_t>(c,a+8u);c.r[7]=rd<uint32_t>(c,a+12u);c.r[8]=rd<uint32_t>(c,a+16u);c.r[9]=rd<uint32_t>(c,a+20u);c.r[10]=rd<uint32_t>(c,a+24u);c.r[11]=rd<uint32_t>(c,a+28u);uint32_t newpc=rd<uint32_t>(c,a+32u);c.r[13]=a+36u;c.pc=newpc;return;}
c.pc=270387897u;}
static Block old_block_101dcabc;
static void cc_101dcabc(Context& c){if(!active(c)){old_block_101dcabc(c);return;}
{uint32_t v=image_base(c,add(c,c.r[0],57600u,0,false));c.r[3]=v;}
{uint32_t v=c.r[0];c.r[1]=v;}
{uint32_t a=c.r[13]-20u;wr<uint32_t>(c,a+0u,c.r[4]);wr<uint32_t>(c,a+4u,c.r[5]);wr<uint32_t>(c,a+8u,c.r[6]);wr<uint32_t>(c,a+12u,c.r[7]);wr<uint32_t>(c,a+16u,c.r[14]);c.r[13]=a;}
{uint32_t v=599u;c.r[6]=v;}
{uint32_t a=(c.r[3]+0u+4u);uint32_t wb=a;c.r[5]=rd<uint32_t>(c,a+0u);c.r[3]=wb;}
{uint32_t v=96u;nz(c,v);c.r[7]=v;}
{uint32_t a=(c.r[3]+0u+0u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[2],~(c.r[6]),1,true));}
{if(cond(c,13)){c.pc=(270387942u|1u);return;}}
c.pc=270387925u;}
static Block old_block_101dcace;
static void cc_101dcace(Context& c){if(!active(c)){old_block_101dcace(c);return;}
{uint32_t a=(c.r[3]+0u+0u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[2],~(c.r[6]),1,true));}
{if(cond(c,13)){c.pc=(270387942u|1u);return;}}
c.pc=270387925u;}
static Block old_block_101dcad4;
static void cc_101dcad4(Context& c){if(!active(c)){old_block_101dcad4(c);return;}
{uint32_t v=(c.r[7])*(c.r[2])+c.r[1];c.r[0]=v;}
{uint32_t v=image_base(c,add(c,c.r[0],4u,0,true));c.r[0]=v;}
{uint32_t a=(c.r[0]+0u+4u);c.r[4]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[4],~(0u),1,true));}
{if(cond(c,12)){c.pc=(270387974u|1u);return;}}
c.pc=270387937u;}
static Block old_block_101dcae0;
static void cc_101dcae0(Context& c){if(!active(c)){old_block_101dcae0(c);return;}
{uint32_t v=image_base(c,add(c,c.r[2],1u,0,true));c.r[2]=v;}
{uint32_t a=(c.r[3]+0u+0u);wr<uint32_t>(c,a+0u,c.r[2]);}
{c.pc=(270387918u|1u);return;}
c.pc=270387943u;}
static Block old_block_101dcae6;
static void cc_101dcae6(Context& c){if(!active(c)){old_block_101dcae6(c);return;}
{uint32_t v=96u;nz(c,v);c.r[6]=v;}
{uint32_t v=0u;nz(c,v);c.r[2]=v;}
{uint32_t a=(c.r[3]+0u+0u);wr<uint32_t>(c,a+0u,c.r[2]);}
{uint32_t a=(c.r[3]+0u+0u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[2],~(c.r[5]),1,true));}
{if(cond(c,11)){c.pc=(270387972u|1u);return;}}
c.pc=270387955u;}
static Block old_block_101dcaec;
static void cc_101dcaec(Context& c){if(!active(c)){old_block_101dcaec(c);return;}
{uint32_t a=(c.r[3]+0u+0u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[2],~(c.r[5]),1,true));}
{if(cond(c,11)){c.pc=(270387972u|1u);return;}}
c.pc=270387955u;}
static Block old_block_101dcaf2;
static void cc_101dcaf2(Context& c){if(!active(c)){old_block_101dcaf2(c);return;}
{uint32_t v=(c.r[6])*(c.r[2])+c.r[1];c.r[0]=v;}
{uint32_t v=image_base(c,add(c,c.r[0],4u,0,true));c.r[0]=v;}
{uint32_t a=(c.r[0]+0u+4u);c.r[4]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[4],~(0u),1,true));}
{if(cond(c,12)){c.pc=(270387974u|1u);return;}}
c.pc=270387967u;}
static Block old_block_101dcafe;
static void cc_101dcafe(Context& c){if(!active(c)){old_block_101dcafe(c);return;}
{uint32_t v=image_base(c,add(c,c.r[2],1u,0,true));c.r[2]=v;}
{uint32_t a=(c.r[3]+0u+0u);wr<uint32_t>(c,a+0u,c.r[2]);}
{c.pc=(270387948u|1u);return;}
c.pc=270387973u;}
static Block old_block_101dcb08;
static void cc_101dcb08(Context& c){if(!active(c)){old_block_101dcb08(c);return;}
{uint32_t a=c.r[13]-48u;wr<uint32_t>(c,a+0u,c.r[0]);wr<uint32_t>(c,a+4u,c.r[1]);wr<uint32_t>(c,a+8u,c.r[2]);wr<uint32_t>(c,a+12u,c.r[4]);wr<uint32_t>(c,a+16u,c.r[5]);wr<uint32_t>(c,a+20u,c.r[6]);wr<uint32_t>(c,a+24u,c.r[7]);wr<uint32_t>(c,a+28u,c.r[8]);wr<uint32_t>(c,a+32u,c.r[9]);wr<uint32_t>(c,a+36u,c.r[10]);wr<uint32_t>(c,a+40u,c.r[11]);wr<uint32_t>(c,a+44u,c.r[14]);c.r[13]=a;}
{uint32_t v=image_base(c,add(c,c.r[0],57600u,0,false));c.r[5]=v;}
{uint32_t v=c.r[1];c.r[4]=v;}
{uint32_t v=shift(c,c.r[1],2u,1,false);c.r[11]=v;}
{uint32_t a=(c.r[5]+0u+8u);c.r[8]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[8]+shift(c,c.r[1],2,1,false)+0u);c.r[6]=rd<uint32_t>(c,a+0u);}
{if(c.r[6] == 0){c.pc=(270388008u|1u);return;}}
c.pc=270388001u;}
static Block old_block_101dcb28;
static void cc_101dcb28(Context& c){if(!active(c)){old_block_101dcb28(c);return;}
{uint32_t a=((270388012u&~3u)+0u+120u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[3],270388014u,0,false));c.r[3]=v;}
{uint32_t a=(c.r[3]+shift(c,c.r[1],3,1,false)+0u);c.r[7]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[7]+0u+0u);c.r[0]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[0],~(532676608u),1,true));}
{}
{if(cond(c,10)){uint32_t v=shift(c,c.r[0],2u,1,false);c.r[0]=v;}}
{if(cond(c,9)){uint32_t v=4294967295u;c.r[0]=v;}}
{c.r[14]=270388035u;c.pc=(270690404u|1u);return;}
c.pc=270388035u;}
static Block old_block_101dcb4e;
static void cc_101dcb4e(Context& c){if(!active(c)){old_block_101dcb4e(c);return;}
{uint32_t v=0u;c.r[10]=v;}
{uint32_t a=(c.r[7]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[10],~(c.r[3]),1,true));}
{if(cond(c,11)){c.pc=(270388000u|1u);return;}}
c.pc=270388057u;}
static Block old_block_101dcb52;
static void cc_101dcb52(Context& c){if(!active(c)){old_block_101dcb52(c);return;}
{uint32_t a=(c.r[7]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[10],~(c.r[3]),1,true));}
{if(cond(c,11)){c.pc=(270388000u|1u);return;}}
c.pc=270388057u;}
static Block old_block_101dcb8c;
static void cc_101dcb8c(Context& c){if(!active(c)){old_block_101dcb8c(c);return;}
{uint32_t a=(c.r[5]+0u+8u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+c.r[11]+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+shift(c,c.r[10],2,1,false)+0u);wr<uint32_t>(c,a+0u,c.r[8]);}
{uint32_t v=image_base(c,add(c,c.r[10],1u,0,false));c.r[10]=v;}
{c.pc=(270388050u|1u);return;}
c.pc=270388125u;}
static Block old_block_101dcb9c;
static void cc_101dcb9c(Context& c){if(!active(c)){old_block_101dcb9c(c);return;}
{uint32_t v=c.r[6];c.r[0]=v;}
{uint32_t v=image_base(c,add(c,c.r[13],12u,0,false));c.r[13]=v;}
{uint32_t a=c.r[13];c.r[4]=rd<uint32_t>(c,a+0u);c.r[5]=rd<uint32_t>(c,a+4u);c.r[6]=rd<uint32_t>(c,a+8u);c.r[7]=rd<uint32_t>(c,a+12u);c.r[8]=rd<uint32_t>(c,a+16u);c.r[9]=rd<uint32_t>(c,a+20u);c.r[10]=rd<uint32_t>(c,a+24u);c.r[11]=rd<uint32_t>(c,a+28u);uint32_t newpc=rd<uint32_t>(c,a+32u);c.r[13]=a+36u;c.pc=newpc;return;}
c.pc=270388133u;}
static Block old_block_101dcbba;
static void cc_101dcbba(Context& c){if(!active(c)){old_block_101dcbba(c);return;}
{uint32_t v=image_base(c,add(c,c.r[0],0u,0,true));c.r[0]=v;}
{}
{if(cond(c,2)){uint32_t v=1u;c.r[0]=v;}}
{uint32_t a=c.r[13];c.r[4]=rd<uint32_t>(c,a+0u);uint32_t newpc=rd<uint32_t>(c,a+4u);c.r[13]=a+8u;c.pc=newpc;return;}
c.pc=270388163u;}
static Block old_block_101dcbe8;
static void cc_101dcbe8(Context& c){if(!active(c)){old_block_101dcbe8(c);return;}
{uint32_t v=c.r[6];c.r[3]=v;}
{uint32_t a=((270388206u&~3u)+0u+28u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=c.r[4];c.r[0]=v;}
{uint32_t v=image_base(c,add(c,c.r[2],270388210u,0,false));c.r[2]=v;}
{uint32_t v=image_base(c,add(c,c.r[2],shift(c,c.r[5],3,1,false),0,false));c.r[1]=v;}
{uint32_t a=(c.r[1]+0u+4u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[13]+0u+0u);wr<uint32_t>(c,a+0u,c.r[1]);}
{uint32_t v=c.r[5];c.r[1]=v;}
{uint32_t a=(c.r[2]+shift(c,c.r[5],3,1,false)+0u);c.r[2]=rd<uint32_t>(c,a+0u);}
c.pc=270388223u;}
static Block old_block_101dcbea;
static void cc_101dcbea(Context& c){if(!active(c)){old_block_101dcbea(c);return;}
{uint32_t a=((270388206u&~3u)+0u+28u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=c.r[4];c.r[0]=v;}
{uint32_t v=image_base(c,add(c,c.r[2],270388210u,0,false));c.r[2]=v;}
{uint32_t v=image_base(c,add(c,c.r[2],shift(c,c.r[5],3,1,false),0,false));c.r[1]=v;}
{uint32_t a=(c.r[1]+0u+4u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[13]+0u+0u);wr<uint32_t>(c,a+0u,c.r[1]);}
{uint32_t v=c.r[5];c.r[1]=v;}
{uint32_t a=(c.r[2]+shift(c,c.r[5],3,1,false)+0u);c.r[2]=rd<uint32_t>(c,a+0u);}
c.pc=270388223u;}
static Block old_block_101dcc02;
static void cc_101dcc02(Context& c){if(!active(c)){old_block_101dcc02(c);return;}
{uint32_t v=c.r[4];c.r[0]=v;}
{uint32_t v=image_base(c,add(c,c.r[13],12u,0,false));c.r[13]=v;}
{uint32_t a=c.r[13];c.r[4]=rd<uint32_t>(c,a+0u);c.r[5]=rd<uint32_t>(c,a+4u);c.r[6]=rd<uint32_t>(c,a+8u);c.r[7]=rd<uint32_t>(c,a+12u);uint32_t newpc=rd<uint32_t>(c,a+16u);c.r[13]=a+20u;c.pc=newpc;return;}
c.pc=270388233u;}
static Block old_block_101dcc04;
static void cc_101dcc04(Context& c){if(!active(c)){old_block_101dcc04(c);return;}
{uint32_t v=image_base(c,add(c,c.r[13],12u,0,false));c.r[13]=v;}
{uint32_t a=c.r[13];c.r[4]=rd<uint32_t>(c,a+0u);c.r[5]=rd<uint32_t>(c,a+4u);c.r[6]=rd<uint32_t>(c,a+8u);c.r[7]=rd<uint32_t>(c,a+12u);uint32_t newpc=rd<uint32_t>(c,a+16u);c.r[13]=a+20u;c.pc=newpc;return;}
c.pc=270388233u;}
static Block old_block_101dcc26;
static void cc_101dcc26(Context& c){if(!active(c)){old_block_101dcc26(c);return;}
{uint32_t v=image_base(c,add(c,real_unit(c,c.r[4])?0u:1u,~(1u),1,true));}
{if(cond(c,11)){c.pc=(270388272u|1u);return;}}
c.pc=270388269u;}
static Block old_block_101dcc64;
static void cc_101dcc64(Context& c){if(!active(c)){old_block_101dcc64(c);return;}
{uint32_t a=c.r[13]-32u;wr<uint32_t>(c,a+0u,c.r[3]);wr<uint32_t>(c,a+4u,c.r[4]);wr<uint32_t>(c,a+8u,c.r[5]);wr<uint32_t>(c,a+12u,c.r[6]);wr<uint32_t>(c,a+16u,c.r[7]);wr<uint32_t>(c,a+20u,c.r[8]);wr<uint32_t>(c,a+24u,c.r[9]);wr<uint32_t>(c,a+28u,c.r[14]);c.r[13]=a;}
{uint32_t v=0u;nz(c,v);c.r[5]=v;}
{uint32_t a=((270388334u&~3u)+0u+76u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=((270388336u&~3u)+0u+76u);c.r[9]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[3],270388340u,0,false));c.r[3]=v;}
{uint32_t v=image_base(c,add(c,c.r[9],270388342u,0,false));c.r[9]=v;}
{uint32_t a=(c.r[3]+shift(c,c.r[1],3,1,false)+0u);c.r[6]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[6]+0u+28u);c.r[7]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[5],~(c.r[7]),1,true));}
{if(cond(c,11)){c.pc=(270388400u|1u);return;}}
c.pc=270388351u;}
static Block old_block_101dcc7a;
static void cc_101dcc7a(Context& c){if(!active(c)){old_block_101dcc7a(c);return;}
{uint32_t v=image_base(c,add(c,c.r[5],~(c.r[7]),1,true));}
{if(cond(c,11)){c.pc=(270388400u|1u);return;}}
c.pc=270388351u;}
static Block old_block_101dcc7e;
static void cc_101dcc7e(Context& c){if(!active(c)){old_block_101dcc7e(c);return;}
{uint32_t v=shift(c,c.r[5],2u,1,false);c.r[8]=v;}
{uint32_t v=0u;nz(c,v);c.r[4]=v;}
{uint32_t a=(c.r[6]+0u+24u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+c.r[8]+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[3],shift(c,c.r[4],2,1,false),0,false));c.r[1]=v;}
{uint32_t a=(c.r[3]+shift(c,c.r[4],2,1,false)+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[9]+shift(c,c.r[3],2,1,false)+0u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[4],c.r[2],0,false));c.r[4]=v;}
{uint32_t v=(c.r[3])&(~(16u));c.r[2]=v;}
{uint32_t v=image_base(c,add(c,c.r[2],~(5u),1,true));}
{if(cond(c,1)){c.pc=(270388396u|1u);return;}}
c.pc=270388385u;}
static Block old_block_101dcc84;
static void cc_101dcc84(Context& c){if(!active(c)){old_block_101dcc84(c);return;}
{uint32_t a=(c.r[6]+0u+24u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+c.r[8]+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[3],shift(c,c.r[4],2,1,false),0,false));c.r[1]=v;}
{uint32_t a=(c.r[3]+shift(c,c.r[4],2,1,false)+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[9]+shift(c,c.r[3],2,1,false)+0u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[4],c.r[2],0,false));c.r[4]=v;}
{uint32_t v=(c.r[3])&(~(16u));c.r[2]=v;}
{uint32_t v=image_base(c,add(c,c.r[2],~(5u),1,true));}
{if(cond(c,1)){c.pc=(270388396u|1u);return;}}
c.pc=270388385u;}
static Block old_block_101dcca0;
static void cc_101dcca0(Context& c){if(!active(c)){old_block_101dcca0(c);return;}
{uint32_t v=image_base(c,add(c,c.r[3],~(23u),1,true));}
{if(cond(c,2)){c.pc=(270388356u|1u);return;}}
c.pc=270388389u;}
static Block old_block_101dccac;
static void cc_101dccac(Context& c){if(!active(c)){old_block_101dccac(c);return;}
{uint32_t v=image_base(c,add(c,c.r[5],1u,0,true));c.r[5]=v;}
{c.pc=(270388346u|1u);return;}
c.pc=270388401u;}
static Block old_block_101dccd8;
static void cc_101dccd8(Context& c){if(!active(c)){old_block_101dccd8(c);return;}
{uint32_t a=c.r[13]-32u;wr<uint32_t>(c,a+0u,c.r[3]);wr<uint32_t>(c,a+4u,c.r[4]);wr<uint32_t>(c,a+8u,c.r[5]);wr<uint32_t>(c,a+12u,c.r[6]);wr<uint32_t>(c,a+16u,c.r[7]);wr<uint32_t>(c,a+20u,c.r[8]);wr<uint32_t>(c,a+24u,c.r[9]);wr<uint32_t>(c,a+28u,c.r[14]);c.r[13]=a;}
{uint32_t v=0u;nz(c,v);c.r[5]=v;}
{uint32_t a=((270388450u&~3u)+0u+72u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=((270388452u&~3u)+0u+72u);c.r[9]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[3],270388456u,0,false));c.r[3]=v;}
{uint32_t v=image_base(c,add(c,c.r[9],270388458u,0,false));c.r[9]=v;}
{uint32_t a=(c.r[3]+shift(c,c.r[1],3,1,false)+0u);c.r[6]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[6]+0u+28u);c.r[7]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[5],~(c.r[7]),1,true));}
{if(cond(c,11)){c.pc=(270388516u|1u);return;}}
c.pc=270388467u;}
static Block old_block_101dccee;
static void cc_101dccee(Context& c){if(!active(c)){old_block_101dccee(c);return;}
{uint32_t v=image_base(c,add(c,c.r[5],~(c.r[7]),1,true));}
{if(cond(c,11)){c.pc=(270388516u|1u);return;}}
c.pc=270388467u;}
static Block old_block_101dccf2;
static void cc_101dccf2(Context& c){if(!active(c)){old_block_101dccf2(c);return;}
{uint32_t v=shift(c,c.r[5],2u,1,false);c.r[8]=v;}
{uint32_t v=0u;nz(c,v);c.r[4]=v;}
{uint32_t a=(c.r[6]+0u+24u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+c.r[8]+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[3],shift(c,c.r[4],2,1,false),0,false));c.r[1]=v;}
{uint32_t a=(c.r[3]+shift(c,c.r[4],2,1,false)+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[9]+shift(c,c.r[3],2,1,false)+0u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[4],c.r[2],0,false));c.r[4]=v;}
{uint32_t v=(c.r[3])&(~(16u));c.r[2]=v;}
{uint32_t v=image_base(c,add(c,c.r[2],~(5u),1,true));}
{if(cond(c,1)){c.pc=(270388512u|1u);return;}}
c.pc=270388501u;}
static Block old_block_101dccf8;
static void cc_101dccf8(Context& c){if(!active(c)){old_block_101dccf8(c);return;}
{uint32_t a=(c.r[6]+0u+24u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+c.r[8]+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[3],shift(c,c.r[4],2,1,false),0,false));c.r[1]=v;}
{uint32_t a=(c.r[3]+shift(c,c.r[4],2,1,false)+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[9]+shift(c,c.r[3],2,1,false)+0u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[4],c.r[2],0,false));c.r[4]=v;}
{uint32_t v=(c.r[3])&(~(16u));c.r[2]=v;}
{uint32_t v=image_base(c,add(c,c.r[2],~(5u),1,true));}
{if(cond(c,1)){c.pc=(270388512u|1u);return;}}
c.pc=270388501u;}
static Block old_block_101dcd14;
static void cc_101dcd14(Context& c){if(!active(c)){old_block_101dcd14(c);return;}
{uint32_t v=image_base(c,add(c,c.r[3],~(23u),1,true));}
{if(cond(c,2)){c.pc=(270388472u|1u);return;}}
c.pc=270388505u;}
static Block old_block_101dcd20;
static void cc_101dcd20(Context& c){if(!active(c)){old_block_101dcd20(c);return;}
{uint32_t v=image_base(c,add(c,c.r[5],1u,0,true));c.r[5]=v;}
{c.pc=(270388462u|1u);return;}
c.pc=270388517u;}
static Block old_block_101dcd50;
static void cc_101dcd50(Context& c){if(!active(c)){old_block_101dcd50(c);return;}
{uint32_t a=((270388564u&~3u)+0u+8u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=image_base(c,add(c,c.r[3],270388566u,0,false));c.r[3]=v;}
{uint32_t a=(c.r[3]+shift(c,c.r[0],3,1,false)+0u);c.r[0]=rd<uint32_t>(c,a+0u);}
{uint32_t a=c.r[13];c.r[3]=rd<uint32_t>(c,a+0u);uint32_t newpc=rd<uint32_t>(c,a+4u);c.r[13]=a+8u;c.pc=newpc;return;}
c.pc=270388571u;}
static Block old_block_101dcdb6;
static void cc_101dcdb6(Context& c){if(!active(c)){old_block_101dcdb6(c);return;}
{uint32_t v=image_base(c,add(c,c.r[1],~(41u),1,true));}
{if(cond(c,1)){c.pc=(270388728u|1u);return;}}
c.pc=270388667u;}
static Block old_block_101dcdbc;
static void cc_101dcdbc(Context& c){if(!active(c)){old_block_101dcdbc(c);return;}
{uint32_t v=image_base(c,add(c,c.r[1],~(5u),1,true));}
{if(cond(c,1)){c.pc=(270388740u|1u);return;}}
c.pc=270388673u;}
static Block old_block_101dcdc2;
static void cc_101dcdc2(Context& c){if(!active(c)){old_block_101dcdc2(c);return;}
{uint32_t v=image_base(c,add(c,c.r[1],~(1u),1,true));}
{if(cond(c,1)){c.pc=(270388760u|1u);return;}}
c.pc=270388679u;}
static Block old_block_101dcdc8;
static void cc_101dcdc8(Context& c){if(!active(c)){old_block_101dcdc8(c);return;}
{uint32_t v=image_base(c,add(c,c.r[1],~(10u),1,true));}
{if(cond(c,1)){c.pc=(270388760u|1u);return;}}
c.pc=270388685u;}
static Block old_block_101dcdcc;
static void cc_101dcdcc(Context& c){if(!active(c)){old_block_101dcdcc(c);return;}
{uint32_t v=image_base(c,add(c,c.r[1],~(40u),1,true));}
{if(cond(c,2)){c.pc=(270388768u|1u);return;}}
c.pc=270388689u;}
static Block old_block_101dcdd6;
static void cc_101dcdd6(Context& c){if(!active(c)){old_block_101dcdd6(c);return;}
{uint32_t v=image_base(c,add(c,c.r[1],~(45u),1,true));}
{if(cond(c,1)){c.pc=(270388740u|1u);return;}}
c.pc=270388699u;}
static Block old_block_101dcddc;
static void cc_101dcddc(Context& c){if(!active(c)){old_block_101dcddc(c);return;}
{uint32_t v=image_base(c,add(c,c.r[1],~(42u),1,true));}
{if(cond(c,1)){c.pc=(270388734u|1u);return;}}
c.pc=270388705u;}
static Block old_block_101dcde0;
static void cc_101dcde0(Context& c){if(!active(c)){old_block_101dcde0(c);return;}
{uint32_t v=image_base(c,add(c,c.r[1],~(43u),1,true));}
{if(cond(c,2)){c.pc=(270388768u|1u);return;}}
c.pc=270388709u;}
static Block old_block_101dcdea;
static void cc_101dcdea(Context& c){if(!active(c)){old_block_101dcdea(c);return;}
{uint32_t v=image_base(c,add(c,c.r[1],~(46u),1,true));}
{if(cond(c,1)){c.pc=(270388754u|1u);return;}}
c.pc=270388719u;}
static Block old_block_101dcdee;
static void cc_101dcdee(Context& c){if(!active(c)){old_block_101dcdee(c);return;}
{uint32_t v=image_base(c,add(c,c.r[1],~(47u),1,true));}
{if(cond(c,2)){c.pc=(270388768u|1u);return;}}
c.pc=270388723u;}
static Block old_block_101dce24;
static void cc_101dce24(Context& c){if(!active(c)){old_block_101dce24(c);return;}
{uint32_t v=image_base(c,add(c,c.r[1],~(41u),1,true));}
{if(cond(c,1)){c.pc=(270388824u|1u);return;}}
c.pc=270388777u;}
static Block old_block_101dce2a;
static void cc_101dce2a(Context& c){if(!active(c)){old_block_101dce2a(c);return;}
{uint32_t v=image_base(c,add(c,c.r[1],~(5u),1,true));}
{if(cond(c,1)){c.pc=(270388846u|1u);return;}}
c.pc=270388783u;}
static Block old_block_101dce30;
static void cc_101dce30(Context& c){if(!active(c)){old_block_101dce30(c);return;}
{uint32_t v=image_base(c,add(c,c.r[1],~(1u),1,true));}
{if(cond(c,1)){c.pc=(270388862u|1u);return;}}
c.pc=270388789u;}
static Block old_block_101dce36;
static void cc_101dce36(Context& c){if(!active(c)){old_block_101dce36(c);return;}
{uint32_t v=image_base(c,add(c,c.r[1],~(10u),1,true));}
{if(cond(c,1)){c.pc=(270388862u|1u);return;}}
c.pc=270388795u;}
static Block old_block_101dce3a;
static void cc_101dce3a(Context& c){if(!active(c)){old_block_101dce3a(c);return;}
{uint32_t v=image_base(c,add(c,c.r[1],~(40u),1,true));}
{if(cond(c,2)){c.pc=(270388872u|1u);return;}}
c.pc=270388799u;}
static Block old_block_101e1be2;
static void cc_101e1be2(Context& c){if(!active(c)){old_block_101e1be2(c);return;}
{uint32_t a=(c.r[4]+0u+4u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=12u;nz(c,v);c.r[5]=v;}
{uint32_t a=(c.r[4]+0u+8u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+0u+12u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[13]+0u+0u);wr<uint32_t>(c,a+0u,c.r[2]);}
{uint32_t a=(c.r[3]+0u+4u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[13]+0u+4u);wr<uint32_t>(c,a+0u,c.r[2]);}
{uint32_t a=((270408692u&~3u)+0u+32u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+0u+8u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[2],270408696u,0,false);c.r[2]=v;}
{uint32_t v=stage_graphics(c,c.r[1],(c.r[5])*(c.r[1])+c.r[2]);c.r[2]=v;}
{c.r[14]=270408703u;c.pc=(270407150u|1u);return;}
c.pc=270408703u;}
static Block old_block_101ed5e4;
static void cc_101ed5e4(Context& c){if(!active(c)){old_block_101ed5e4(c);return;}
{uint32_t v=add(c,c.r[10],shift(c,c.r[5],2,1,false),0,false);c.r[3]=v;}
{uint32_t v=add(c,c.r[3],45568u,0,false);c.r[3]=v;}
{uint32_t a=(c.r[3]+0u+64u);a=array_address(c,a,false);c.r[8]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[8],~(0u),1,true);}
{if(cond(c,14)){c.pc=(270456476u|1u);return;}}
c.pc=270456311u;}
static Block old_block_101ed6ac;
static void cc_101ed6ac(Context& c){if(!active(c)){old_block_101ed6ac(c);return;}
{uint32_t v=add(c,c.r[4],47104u,0,false);c.r[3]=v;}
{uint32_t a=(c.r[3]+0u+128u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[5]+c.r[9],~(c.r[3]),1,true);}
{if(cond(c,11)){c.pc=(270456530u|1u);return;}}
c.pc=270456505u;}
static Block old_block_101ed6f4;
static void cc_101ed6f4(Context& c){if(!active(c)){old_block_101ed6f4(c);return;}
{uint32_t a=(c.r[6]+0u+60u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=4294967295u;c.r[2]=v;}
{uint32_t a=(c.r[3]+0u+544u);wr<uint32_t>(c,a+0u,c.r[2]);}
{uint32_t a=((270456578u&~3u)+0u+40u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[13]+0u+8u);wr<uint32_t>(c,a+0u,c.r[5]);}
{uint32_t v=add(c,c.r[3],270456582u,0,false);c.r[3]=v;}
{uint32_t v=add(c,c.r[3],72u,0,false);c.r[2]=v;}
{uint32_t v=array_base(c,add(c,c.r[3],64u,0,true),false);c.r[3]=v;}
{uint32_t a=c.r[2];c.r[0]=rd<uint32_t>(c,a+0u);c.r[1]=rd<uint32_t>(c,a+4u);}
{uint32_t a=c.r[3];c.r[2]=rd<uint32_t>(c,a+0u);c.r[3]=rd<uint32_t>(c,a+4u);}
{uint32_t a=c.r[13];wr<uint32_t>(c,a+0u,c.r[0]);wr<uint32_t>(c,a+4u,c.r[1]);}
{uint32_t v=c.r[4];c.r[0]=v;}
{uint32_t a=(c.r[6]+0u+60u);c.r[1]=rd<uint32_t>(c,a+0u);}
{c.r[14]=270456605u;c.pc=(270629428u|1u);return;}
c.pc=270456605u;}
static Block old_block_101edaaa;
static void cc_101edaaa(Context& c){if(!active(c)){old_block_101edaaa(c);return;}
{uint32_t v=array_base(c,add(c,c.r[1],64u,0,true),false);c.r[1]=v;}
{uint32_t v=255u;nz(c,v);c.r[0]=v;}
{c.r[14]=270457523u;c.pc=(269745118u|1u);return;}
c.pc=270457523u;}
static Block old_block_101edb68;
static void cc_101edb68(Context& c){if(!active(c)){old_block_101edb68(c);return;}
{uint32_t a=(c.r[5]+0u+124u);c.r[0]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+208u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);c.r[2]=rd<uint32_t>(c,a+0u);}
{c.r[14]=270457719u;c.pc=(269711120u|1u);return;}
c.pc=270457719u;}
static Block old_block_101ee836;
static void cc_101ee836(Context& c){if(!active(c)){old_block_101ee836(c);return;}
{uint32_t a=(c.r[5]+0u+124u);c.r[0]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+208u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);c.r[2]=rd<uint32_t>(c,a+0u);}
{c.r[14]=270460997u;c.pc=(269711120u|1u);return;}
c.pc=270460997u;}
static Block old_block_101eef84;
static void cc_101eef84(Context& c){if(!active(c)){old_block_101eef84(c);return;}
{uint32_t a=c.r[13]-32u;wr<uint32_t>(c,a+0u,c.r[4]);wr<uint32_t>(c,a+4u,c.r[5]);wr<uint32_t>(c,a+8u,c.r[6]);wr<uint32_t>(c,a+12u,c.r[7]);wr<uint32_t>(c,a+16u,c.r[8]);wr<uint32_t>(c,a+20u,c.r[9]);wr<uint32_t>(c,a+24u,c.r[10]);wr<uint32_t>(c,a+28u,c.r[14]);c.r[13]=a;}
{uint32_t v=add(c,c.r[13],~(2048u),1,false);c.r[13]=v;}
{uint32_t v=c.r[0];c.r[4]=v;}
{uint32_t v=0u;nz(c,v);c.r[1]=v;}
{uint32_t v=2048u;c.r[2]=v;}
{uint32_t v=0u;nz(c,v);c.r[5]=v;}
{uint32_t v=c.r[13];c.r[0]=v;}
{uint32_t v=add(c,c.r[4],45568u,0,false);c.r[9]=v;}
{uint32_t v=add(c,c.r[4],47104u,0,false);c.r[8]=v;}
{c.r[14]=270462885u;c.pc=(269634900u|0u);return;}
c.pc=270462885u;}
static Block old_block_101eefa4;
static void cc_101eefa4(Context& c){if(!active(c)){old_block_101eefa4(c);return;}
{uint32_t v=c.r[13];c.r[7]=v;}
{uint32_t v=array_base(c,add(c,c.r[9],64u,0,false),false);c.r[0]=v;}
{uint32_t v=0u;nz(c,v);c.r[1]=v;}
{uint32_t v=2048u;c.r[2]=v;}
{uint32_t v=c.r[5];c.r[6]=v;}
{c.r[14]=270462903u;c.pc=(269634900u|0u);return;}
c.pc=270462903u;}
static Block old_block_101eefde;
static void cc_101eefde(Context& c){if(!active(c)){old_block_101eefde(c);return;}
{uint32_t v=(c.r[0])&(c.r[10]);nz(c,v);}
{}
{if(cond(c,1)){uint32_t a=(c.r[7]+shift(c,c.r[6],2,1,false)+0u);wr<uint32_t>(c,a+0u,c.r[5]);}}
{if(cond(c,1)){uint32_t v=add(c,c.r[6],1u,0,false);c.r[6]=v;}}
{uint32_t v=add(c,c.r[5],1u,0,true);c.r[5]=v;}
{uint32_t v=add(c,c.r[5],~(total(c)),1,true);}
{if(cond(c,2)){c.pc=(270462906u|1u);return;}}
c.pc=270462963u;}
static Block old_block_101eefea;
static void cc_101eefea(Context& c){if(!active(c)){old_block_101eefea(c);return;}
{uint32_t v=add(c,c.r[5],1u,0,true);c.r[5]=v;}
{uint32_t v=add(c,c.r[5],~(total(c)),1,true);}
{if(cond(c,2)){c.pc=(270462906u|1u);return;}}
c.pc=270462963u;}
static Block old_block_101ef012;
static void cc_101ef012(Context& c){if(!active(c)){old_block_101ef012(c);return;}
{uint32_t v=add(c,c.r[4],shift(c,c.r[3],2,1,false),0,false);c.r[1]=v;}
{uint32_t a=(c.r[7]+shift(c,c.r[3],2,1,false)+0u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[1],45568u,0,false);c.r[1]=v;}
{uint32_t v=add(c,c.r[3],1u,0,true);c.r[3]=v;}
{uint32_t a=(c.r[1]+0u+64u);a=array_address(c,a,false);wr<uint32_t>(c,a+0u,c.r[2]);}
{c.pc=(270462990u|1u);return;}
c.pc=270463013u;}
static Block old_block_101ef024;
static void cc_101ef024(Context& c){if(!active(c)){old_block_101ef024(c);return;}
{uint32_t a=(c.r[8]+0u+128u);wr<uint32_t>(c,a+0u,c.r[6]);}
{uint32_t v=add(c,c.r[13],2048u,0,false);c.r[13]=v;}
{uint32_t a=c.r[13];c.r[4]=rd<uint32_t>(c,a+0u);c.r[5]=rd<uint32_t>(c,a+4u);c.r[6]=rd<uint32_t>(c,a+8u);c.r[7]=rd<uint32_t>(c,a+12u);c.r[8]=rd<uint32_t>(c,a+16u);c.r[9]=rd<uint32_t>(c,a+20u);c.r[10]=rd<uint32_t>(c,a+24u);uint32_t newpc=rd<uint32_t>(c,a+28u);c.r[13]=a+32u;c.pc=newpc;return;}
c.pc=270463025u;}
static Block old_block_101ef3bc;
static void cc_101ef3bc(Context& c){if(!active(c)){old_block_101ef3bc(c);return;}
{uint32_t v=array_base(c,add(c,c.r[1],64u,0,true),false);c.r[1]=v;}
{uint32_t v=255u;nz(c,v);c.r[0]=v;}
{c.r[14]=270463941u;c.pc=(269745118u|1u);return;}
c.pc=270463941u;}
static Block old_block_101ef468;
static void cc_101ef468(Context& c){if(!active(c)){old_block_101ef468(c);return;}
{uint32_t a=(c.r[5]+0u+124u);c.r[0]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+208u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);c.r[2]=rd<uint32_t>(c,a+0u);}
{c.r[14]=270464119u;c.pc=(269711120u|1u);return;}
c.pc=270464119u;}
static Block old_block_101ef6fc;
static void cc_101ef6fc(Context& c){if(!active(c)){old_block_101ef6fc(c);return;}
{uint32_t a=((270464768u&~3u)+0u+212u);a=array_address(c,a,true);setsbits(c,14,rd<uint32_t>(c,a+0u));}
{uint32_t a=((270464772u&~3u)+0u+212u);a=array_address(c,a,true);setsbits(c,15,rd<uint32_t>(c,a+0u));}
{setfs(c,14,(fs(c,16))+(fs(c,14)));}
{uint32_t v=add(c,c.r[6],~(c.r[7]),1,true);}
{uint32_t a=((270464782u&~3u)+0u+208u);c.r[2]=rd<uint32_t>(c,a+0u);}
{}
{if(cond(c,11)){uint32_t v=3u;c.r[3]=v;}}
{if(cond(c,12)){uint32_t v=2u;c.r[3]=v;}}
{uint32_t a=(c.r[13]+0u+8u);wr<uint32_t>(c,a+0u,c.r[11]);}
{uint32_t v=add(c,c.r[3],126u,0,false);c.r[3]=v;}
{}
{if(cond(c,12)){uint32_t v=4294967295u;c.r[2]=v;}}
{uint32_t a=(c.r[13]+0u+0u);wr<uint32_t>(c,a+0u,c.r[2]);}
{uint32_t v=65u;nz(c,v);c.r[2]=v;}
{uint32_t a=(c.r[4]+shift(c,c.r[3],2,1,false)+0u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[13]+0u+4u);wr<uint32_t>(c,a+0u,c.r[2]);}
{uint32_t a=(c.r[9]+0u+56u);c.r[0]=rd<uint32_t>(c,a+0u);}
{setfs(c,15,(fs(c,17))+(fs(c,15)));}
{setsbits(c,14,cvti(fs(c,14),true));}
{setsbits(c,15,cvti(fs(c,15),true));}
{c.r[2]=sbits(c,14);}
{c.r[3]=sbits(c,15);}
{c.r[14]=270464839u;c.pc=(269788668u|1u);return;}
c.pc=270464839u;}
static Block old_block_101ef87a;
static void cc_101ef87a(Context& c){if(!active(c)){old_block_101ef87a(c);return;}
{uint32_t a=(c.r[4]+0u+132u);setsbits(c,15,rd<uint32_t>(c,a+0u));}
{uint32_t a=(c.r[4]+0u+156u);setsbits(c,17,rd<uint32_t>(c,a+0u));}
{uint32_t a=(c.r[4]+0u+160u);setsbits(c,16,rd<uint32_t>(c,a+0u));}
{setfs(c,17,(fs(c,17))+(fs(c,15)));}
{uint32_t a=(c.r[4]+0u+136u);setsbits(c,15,rd<uint32_t>(c,a+0u));}
{uint32_t a=(c.r[4]+0u+208u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);c.r[2]=rd<uint32_t>(c,a+0u);}
{setfs(c,16,(fs(c,16))+(fs(c,15)));}
{uint32_t v=c.r[0];c.r[5]=v;}
{uint32_t a=(c.r[0]+0u+124u);c.r[0]=rd<uint32_t>(c,a+0u);}
{c.r[14]=270465187u;c.pc=(269711120u|1u);return;}
c.pc=270465187u;}
static Block old_block_101f007e;
static void cc_101f007e(Context& c){if(!active(c)){old_block_101f007e(c);return;}
{uint32_t a=(c.r[4]+0u+208u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+132u);setsbits(c,15,rd<uint32_t>(c,a+0u));}
{uint32_t a=(c.r[5]+0u+124u);c.r[0]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+156u);setsbits(c,17,rd<uint32_t>(c,a+0u));}
{uint32_t a=(c.r[4]+0u+160u);setsbits(c,16,rd<uint32_t>(c,a+0u));}
{setfs(c,17,(fs(c,17))+(fs(c,15)));}
{uint32_t a=(c.r[4]+0u+136u);setsbits(c,15,rd<uint32_t>(c,a+0u));}
{setfs(c,16,(fs(c,16))+(fs(c,15)));}
{c.r[14]=270467237u;c.pc=(269711120u|1u);return;}
c.pc=270467237u;}
static Block old_block_101f022a;
static void cc_101f022a(Context& c){if(!active(c)){old_block_101f022a(c);return;}
{uint32_t v=add(c,c.r[4],50688u,0,false);c.r[3]=v;}
{uint32_t v=add(c,c.r[7],270467634u,0,false);c.r[7]=v;}
{uint32_t a=(c.r[7]+0u+0u);c.r[7]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[6],270467638u,0,false);c.r[6]=v;}
{uint32_t a=(c.r[6]+0u+0u);c.r[6]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+0u+64u);a=array_address(c,a,false);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[3],~(1u),1,true);}
{if(cond(c,2)){c.pc=(270467672u|1u);return;}}
c.pc=270467645u;}
static Block old_block_101f02da;
static void cc_101f02da(Context& c){if(!active(c)){old_block_101f02da(c);return;}
{uint32_t a=((270467806u&~3u)+0u+64u);a=array_address(c,a,false);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[3],270467808u,0,false);c.r[3]=v;}
{uint32_t a=(c.r[3]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+0u+0u);c.r[0]=rd<uint32_t>(c,a+0u);}
{uint32_t v=c.r[3];c.r[6]=v;}
{if(c.r[0] == 0){c.pc=(270467818u|1u);return;}}
c.pc=270467815u;}
static Block old_block_101f0536;
static void cc_101f0536(Context& c){if(!active(c)){old_block_101f0536(c);return;}
{uint32_t a=(c.r[4]+0u+548u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=c.r[4];c.r[1]=v;}
{uint32_t a=((270468416u&~3u)+0u+24u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[2],270468418u,0,false);c.r[2]=v;}
{uint32_t a=(c.r[2]+0u+0u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[0],~(c.r[3]),1,true);}
{uint32_t v=c.r[5];c.r[0]=v;}
{}
{if(cond(c,2)){uint32_t v=122u;c.r[3]=v;}}
{if(cond(c,1)){uint32_t v=255u;c.r[3]=v;}}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);wr<uint32_t>(c,a+0u,c.r[3]);}
{c.r[14]=270468437u;c.pc=(269926188u|1u);return;}
c.pc=270468437u;}
static Block old_block_101f0706;
static void cc_101f0706(Context& c){if(!active(c)){old_block_101f0706(c);return;}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);c.r[1]=rd<uint32_t>(c,a+0u);}
{c.r[14]=270468879u;c.pc=(270383294u|1u);return;}
c.pc=270468879u;}
static Block old_block_101f083e;
static void cc_101f083e(Context& c){if(!active(c)){old_block_101f083e(c);return;}
{uint32_t a=(c.r[4]+0u+208u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=c.r[0];c.r[5]=v;}
{uint32_t a=(c.r[0]+0u+124u);c.r[0]=rd<uint32_t>(c,a+0u);}
{c.r[14]=270469199u;c.pc=(269711120u|1u);return;}
c.pc=270469199u;}
static Block old_block_101f08fa;
static void cc_101f08fa(Context& c){if(!active(c)){old_block_101f08fa(c);return;}
{uint32_t a=(c.r[4]+0u+208u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=c.r[0];c.r[5]=v;}
{uint32_t a=(c.r[0]+0u+124u);c.r[0]=rd<uint32_t>(c,a+0u);}
{c.r[14]=270469387u;c.pc=(269711120u|1u);return;}
c.pc=270469387u;}
static Block old_block_101f0a42;
static void cc_101f0a42(Context& c){if(!active(c)){old_block_101f0a42(c);return;}
{uint32_t a=(c.r[4]+0u+208u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=c.r[0];c.r[5]=v;}
{uint32_t a=(c.r[0]+0u+124u);c.r[0]=rd<uint32_t>(c,a+0u);}
{c.r[14]=270469715u;c.pc=(269711120u|1u);return;}
c.pc=270469715u;}
static Block old_block_101f0b08;
static void cc_101f0b08(Context& c){if(!active(c)){old_block_101f0b08(c);return;}
{uint32_t a=(c.r[4]+0u+132u);setsbits(c,15,rd<uint32_t>(c,a+0u));}
{uint32_t a=(c.r[4]+0u+156u);setsbits(c,17,rd<uint32_t>(c,a+0u));}
{uint32_t a=(c.r[4]+0u+160u);setsbits(c,16,rd<uint32_t>(c,a+0u));}
{setfs(c,17,(fs(c,17))+(fs(c,15)));}
{uint32_t a=(c.r[4]+0u+136u);setsbits(c,15,rd<uint32_t>(c,a+0u));}
{uint32_t a=(c.r[4]+0u+208u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);c.r[2]=rd<uint32_t>(c,a+0u);}
{setfs(c,16,(fs(c,16))+(fs(c,15)));}
{uint32_t v=c.r[0];c.r[5]=v;}
{uint32_t a=(c.r[0]+0u+124u);c.r[0]=rd<uint32_t>(c,a+0u);}
{c.r[14]=270469937u;c.pc=(269711120u|1u);return;}
c.pc=270469937u;}
static Block old_block_101f0c28;
static void cc_101f0c28(Context& c){if(!active(c)){old_block_101f0c28(c);return;}
{uint32_t a=((270470188u&~3u)+0u+216u);setsbits(c,15,rd<uint32_t>(c,a+0u));}
{setfs(c,15,(fs(c,17))+(fs(c,15)));}
{uint32_t a=((270470196u&~3u)+0u+212u);a=array_address(c,a,true);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[13]+0u+8u);wr<uint32_t>(c,a+0u,c.r[8]);}
{uint32_t a=(c.r[4]+0u+504u);c.r[1]=rd<uint32_t>(c,a+0u);}
{setsbits(c,15,cvti(fs(c,15),true));}
{c.r[7]=sbits(c,15);}
{setfs(c,15,12.0);}
{setfs(c,15,(fs(c,16))-(fs(c,15)));}
{uint32_t v=add(c,c.r[0],~(0u),1,true);}
{}
{if(cond(c,2)){uint32_t v=c.r[3];c.r[0]=v;}}
{if(cond(c,1)){uint32_t v=4294967295u;c.r[0]=v;}}
{uint32_t v=65u;nz(c,v);c.r[3]=v;}
{uint32_t a=(c.r[13]+0u+0u);wr<uint32_t>(c,a+0u,c.r[0]);}
{uint32_t a=(c.r[13]+0u+4u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[6]+0u+56u);c.r[0]=rd<uint32_t>(c,a+0u);}
{uint32_t v=c.r[7];c.r[2]=v;}
{setsbits(c,15,cvti(fs(c,15),true));}
{c.r[3]=sbits(c,15);}
{c.r[14]=270470251u;c.pc=(269788668u|1u);return;}
c.pc=270470251u;}
static Block old_block_101f11b6;
static void cc_101f11b6(Context& c){if(!active(c)){old_block_101f11b6(c);return;}
{uint32_t v=96u;nz(c,v);c.r[3]=v;}
{uint32_t v=(c.r[3])*(c.r[5])+c.r[10];c.r[2]=v;}
{uint32_t v=24u;nz(c,v);c.r[1]=v;}
{uint32_t v=19u;nz(c,v);c.r[3]=v;}
{uint32_t a=c.r[13];wr<uint32_t>(c,a+0u,c.r[1]);wr<uint32_t>(c,a+4u,c.r[3]);}
{uint32_t a=(c.r[13]+0u+64u);a=array_address(c,a,false);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[13]+0u+20u);wr<uint32_t>(c,a+0u,c.r[7]);}
{setsbits(c,15,c.r[2]);}
{uint32_t a=(c.r[13]+0u+8u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t v=4294967295u;c.r[3]=v;}
{uint32_t a=(c.r[13]+0u+12u);wr<uint32_t>(c,a+0u,c.r[3]);}
{setfs(c,15,int32_t(sbits(c,15)));}
{uint32_t v=1u;nz(c,v);c.r[3]=v;}
{uint32_t a=(c.r[13]+0u+16u);wr<uint32_t>(c,a+0u,c.r[3]);}
{c.r[2]=sbits(c,15);}
{setfs(c,15,int32_t(sbits(c,17)));}
{c.r[3]=sbits(c,15);}
{uint32_t v=c.r[0];c.r[6]=v;}
{uint32_t v=c.r[4];c.r[0]=v;}
{uint32_t v=c.r[6];c.r[1]=v;}
{c.r[14]=270471667u;c.pc=(270272006u|1u);return;}
c.pc=270471667u;}
static Block old_block_101f12d4;
static void cc_101f12d4(Context& c){if(!active(c)){old_block_101f12d4(c);return;}
{uint32_t a=((270471896u&~3u)+0u+64u);a=array_address(c,a,false);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[7],244u,0,false);c.r[14]=v;}
{uint32_t a=(c.r[7]+0u+544u);wr<uint32_t>(c,a+0u,c.r[4]);}
{uint32_t v=add(c,c.r[3],270471906u,0,false);c.r[3]=v;}
{uint32_t a=(c.r[7]+0u+548u);wr<uint32_t>(c,a+0u,c.r[6]);}
{uint32_t a=c.r[3];c.r[0]=rd<uint32_t>(c,a+0u);c.r[1]=rd<uint32_t>(c,a+4u);c.r[2]=rd<uint32_t>(c,a+8u);c.r[3]=rd<uint32_t>(c,a+12u);}
{uint32_t a=c.r[14];wr<uint32_t>(c,a+0u,c.r[0]);wr<uint32_t>(c,a+4u,c.r[1]);wr<uint32_t>(c,a+8u,c.r[2]);wr<uint32_t>(c,a+12u,c.r[3]);}
{uint32_t v=c.r[6];c.r[0]=v;}
{c.r[14]=270471921u;c.pc=(269898508u|1u);return;}
c.pc=270471921u;}
static Block old_block_101f1650;
static void cc_101f1650(Context& c){if(!active(c)){old_block_101f1650(c);return;}
{uint32_t a=c.r[13]-36u;wr<uint32_t>(c,a+0u,c.r[4]);wr<uint32_t>(c,a+4u,c.r[5]);wr<uint32_t>(c,a+8u,c.r[6]);wr<uint32_t>(c,a+12u,c.r[7]);wr<uint32_t>(c,a+16u,c.r[8]);wr<uint32_t>(c,a+20u,c.r[9]);wr<uint32_t>(c,a+24u,c.r[10]);wr<uint32_t>(c,a+28u,c.r[11]);wr<uint32_t>(c,a+32u,c.r[14]);c.r[13]=a;}
{uint32_t v=add(c,c.r[13],~(2108u),1,false);c.r[13]=v;}
{uint32_t v=add(c,c.r[13],56u,0,false);c.r[8]=v;}
{uint32_t v=c.r[0];c.r[4]=v;}
{uint32_t v=0u;nz(c,v);c.r[1]=v;}
{uint32_t v=2048u;c.r[2]=v;}
{uint32_t v=c.r[8];c.r[0]=v;}
{uint32_t v=0u;nz(c,v);c.r[6]=v;}
{c.r[14]=270472813u;c.pc=(269634900u|0u);return;}
c.pc=270472813u;}
static Block old_block_101f1694;
static void cc_101f1694(Context& c){if(!active(c)){old_block_101f1694(c);return;}
{uint32_t v=(c.r[0])&(c.r[7]);nz(c,v);}
{}
{if(cond(c,1)){uint32_t a=(c.r[8]+shift(c,c.r[5],2,1,false)+0u);wr<uint32_t>(c,a+0u,c.r[6]);}}
{if(cond(c,1)){uint32_t v=add(c,c.r[5],1u,0,false);c.r[5]=v;}}
{uint32_t v=add(c,c.r[6],1u,0,true);c.r[6]=v;}
{uint32_t v=add(c,c.r[6],~(total(c)),1,true);}
{if(cond(c,2)){c.pc=(270472814u|1u);return;}}
c.pc=270472871u;}
static Block old_block_101f169e;
static void cc_101f169e(Context& c){if(!active(c)){old_block_101f169e(c);return;}
{uint32_t v=add(c,c.r[6],1u,0,true);c.r[6]=v;}
{uint32_t v=add(c,c.r[6],~(total(c)),1,true);}
{if(cond(c,2)){c.pc=(270472814u|1u);return;}}
c.pc=270472871u;}
static Block old_block_101f16c2;
static void cc_101f16c2(Context& c){if(!active(c)){old_block_101f16c2(c);return;}
{uint32_t v=0u;nz(c,v);c.r[3]=v;}
{uint32_t v=add(c,c.r[4],c.r[3],0,true);c.r[1]=v;}
{uint32_t a=(c.r[8]+c.r[3]+0u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[3],4u,0,true);c.r[3]=v;}
{uint32_t v=add(c,c.r[1],47360u,0,false);c.r[1]=v;}
{uint32_t v=add(c,c.r[3],~(2048u),1,true);}
{uint32_t a=(c.r[1]+0u+212u);a=array_address(c,a,true);wr<uint32_t>(c,a+0u,c.r[2]);}
{if(cond(c,2)){c.pc=(270472900u|1u);return;}}
c.pc=270472923u;}
static Block old_block_101f16c4;
static void cc_101f16c4(Context& c){if(!active(c)){old_block_101f16c4(c);return;}
{uint32_t v=add(c,c.r[4],c.r[3],0,true);c.r[1]=v;}
{uint32_t a=(c.r[8]+c.r[3]+0u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[3],4u,0,true);c.r[3]=v;}
{uint32_t v=add(c,c.r[1],47360u,0,false);c.r[1]=v;}
{uint32_t v=add(c,c.r[3],~(2048u),1,true);}
{uint32_t a=(c.r[1]+0u+212u);a=array_address(c,a,true);wr<uint32_t>(c,a+0u,c.r[2]);}
{if(cond(c,2)){c.pc=(270472900u|1u);return;}}
c.pc=270472923u;}
static Block old_block_101f17a4;
static void cc_101f17a4(Context& c){if(!active(c)){old_block_101f17a4(c);return;}
{uint32_t v=add(c,c.r[13],2108u,0,false);c.r[13]=v;}
{uint32_t a=c.r[13];c.r[4]=rd<uint32_t>(c,a+0u);c.r[5]=rd<uint32_t>(c,a+4u);c.r[6]=rd<uint32_t>(c,a+8u);c.r[7]=rd<uint32_t>(c,a+12u);c.r[8]=rd<uint32_t>(c,a+16u);c.r[9]=rd<uint32_t>(c,a+20u);c.r[10]=rd<uint32_t>(c,a+24u);c.r[11]=rd<uint32_t>(c,a+28u);uint32_t newpc=rd<uint32_t>(c,a+32u);c.r[13]=a+36u;c.pc=newpc;return;}
c.pc=270473133u;}
static Block old_block_101f1a7a;
static void cc_101f1a7a(Context& c){if(!active(c)){old_block_101f1a7a(c);return;}
{uint32_t v=add(c,c.r[12],shift(c,c.r[5],2,1,false),0,false);c.r[3]=v;}
{uint32_t v=add(c,c.r[3],47360u,0,false);c.r[3]=v;}
{uint32_t a=(c.r[3]+0u+212u);a=array_address(c,a,true);c.r[6]=rd<uint32_t>(c,a+0u);}
{if(c.r[6] == 0){c.pc=(270473924u|1u);return;}}
c.pc=270473865u;}
static Block old_block_101f1b28;
static void cc_101f1b28(Context& c){if(!active(c)){old_block_101f1b28(c);return;}
{uint32_t a=c.r[13]-36u;wr<uint32_t>(c,a+0u,c.r[4]);wr<uint32_t>(c,a+4u,c.r[5]);wr<uint32_t>(c,a+8u,c.r[6]);wr<uint32_t>(c,a+12u,c.r[7]);wr<uint32_t>(c,a+16u,c.r[8]);wr<uint32_t>(c,a+20u,c.r[9]);wr<uint32_t>(c,a+24u,c.r[10]);wr<uint32_t>(c,a+28u,c.r[11]);wr<uint32_t>(c,a+32u,c.r[14]);c.r[13]=a;}
{uint32_t v=add(c,c.r[13],~(60u),1,false);c.r[13]=v;}
{uint32_t v=c.r[0];c.r[4]=v;}
{uint32_t v=0u;nz(c,v);c.r[6]=v;}
{uint32_t v=add(c,c.r[4],shift(c,c.r[6],2,1,false),0,false);c.r[3]=v;}
{uint32_t v=add(c,c.r[3],47360u,0,false);c.r[3]=v;}
{uint32_t a=(c.r[3]+0u+212u);a=array_address(c,a,true);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[1],~(c.r[3]),1,true);}
{if(cond(c,2)){c.pc=(270474092u|1u);return;}}
c.pc=270474051u;}
static Block old_block_101f1b32;
static void cc_101f1b32(Context& c){if(!active(c)){old_block_101f1b32(c);return;}
{uint32_t v=add(c,c.r[4],shift(c,c.r[6],2,1,false),0,false);c.r[3]=v;}
{uint32_t v=add(c,c.r[3],47360u,0,false);c.r[3]=v;}
{uint32_t a=(c.r[3]+0u+212u);a=array_address(c,a,true);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[1],~(c.r[3]),1,true);}
{if(cond(c,2)){c.pc=(270474092u|1u);return;}}
c.pc=270474051u;}
static Block old_block_101f1b6c;
static void cc_101f1b6c(Context& c){if(!active(c)){old_block_101f1b6c(c);return;}
{uint32_t v=add(c,c.r[6],1u,0,true);c.r[6]=v;}
{uint32_t v=add(c,c.r[6],~(head(c,40)),1,true);}
{if(cond(c,2)){c.pc=(270474034u|1u);return;}}
c.pc=270474101u;}
static Block old_block_101f1bae;
static void cc_101f1bae(Context& c){if(!active(c)){old_block_101f1bae(c);return;}
{uint32_t v=add(c,c.r[12],shift(c,c.r[5],2,1,false),0,false);c.r[3]=v;}
{uint32_t v=c.r[4];c.r[0]=v;}
{uint32_t v=add(c,c.r[3],47360u,0,false);c.r[3]=v;}
{uint32_t a=(c.r[3]+0u+212u);a=array_address(c,a,true);c.r[7]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[13]+0u+16u);wr<uint32_t>(c,a+0u,c.r[12]);}
{uint32_t v=c.r[7];c.r[1]=v;}
{c.r[14]=270474183u;c.pc=(269908720u|1u);return;}
c.pc=270474183u;}
static Block old_block_101f1c62;
static void cc_101f1c62(Context& c){if(!active(c)){old_block_101f1c62(c);return;}
{uint32_t v=add(c,c.r[4],1u,0,true);c.r[4]=v;}
{uint32_t v=add(c,c.r[0],1u,0,true);c.r[0]=v;}
{}
{if(cond(c,2)){uint32_t v=add(c,c.r[5],1u,0,false);c.r[5]=v;}}
{uint32_t v=add(c,c.r[4],~(total(c)),1,true);}
{if(cond(c,2)){c.pc=(270474330u|1u);return;}}
c.pc=270474353u;}
static Block old_block_101f1fc0;
static void cc_101f1fc0(Context& c){if(!active(c)){old_block_101f1fc0(c);return;}
{uint32_t v=0u;nz(c,v);c.r[3]=v;}
{uint32_t a=(c.r[5]+0u+144u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[5]+0u+148u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t v=255u;nz(c,v);c.r[3]=v;}
{uint32_t a=(c.r[5]+0u+212u);a=array_address(c,a,true);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[5]+0u+128u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=c.r[6];c.r[0]=v;}
{uint32_t v=(c.r[3])&(~(4194304u));c.r[3]=v;}
{uint32_t a=(c.r[5]+0u+128u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+132u);setsbits(c,14,rd<uint32_t>(c,a+0u));}
{uint32_t a=(c.r[4]+0u+136u);setsbits(c,15,rd<uint32_t>(c,a+0u));}
{setsbits(c,14,cvti(fs(c,14),true));}
{setsbits(c,15,cvti(fs(c,15),true));}
{c.r[1]=sbits(c,14);}
{c.r[2]=sbits(c,15);}
{c.r[14]=270475259u;c.pc=(270474952u|1u);return;}
c.pc=270475259u;}
static Block old_block_101f1fca;
static void cc_101f1fca(Context& c){if(!active(c)){old_block_101f1fca(c);return;}
{uint32_t v=255u;nz(c,v);c.r[3]=v;}
{uint32_t a=(c.r[5]+0u+212u);a=array_address(c,a,true);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[5]+0u+128u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=c.r[6];c.r[0]=v;}
{uint32_t v=(c.r[3])&(~(4194304u));c.r[3]=v;}
{uint32_t a=(c.r[5]+0u+128u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+132u);setsbits(c,14,rd<uint32_t>(c,a+0u));}
{uint32_t a=(c.r[4]+0u+136u);setsbits(c,15,rd<uint32_t>(c,a+0u));}
{setsbits(c,14,cvti(fs(c,14),true));}
{setsbits(c,15,cvti(fs(c,15),true));}
{c.r[1]=sbits(c,14);}
{c.r[2]=sbits(c,15);}
{c.r[14]=270475259u;c.pc=(270474952u|1u);return;}
c.pc=270475259u;}
static Block old_block_101f2034;
static void cc_101f2034(Context& c){if(!active(c)){old_block_101f2034(c);return;}
{uint32_t v=0u;nz(c,v);c.r[3]=v;}
{uint32_t a=(c.r[4]+0u+144u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+148u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t v=255u;nz(c,v);c.r[3]=v;}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+128u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=0u;nz(c,v);c.r[2]=v;}
{uint32_t v=c.r[6];c.r[0]=v;}
{uint32_t a=(c.r[13]+0u+0u);wr<uint32_t>(c,a+0u,c.r[2]);}
{uint32_t v=(c.r[3])&(~(4194304u));c.r[3]=v;}
{uint32_t v=72u;nz(c,v);c.r[1]=v;}
{uint32_t a=(c.r[4]+0u+128u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t v=c.r[2];c.r[3]=v;}
{c.r[14]=270475359u;c.pc=(270287196u|1u);return;}
c.pc=270475359u;}
static Block old_block_101f203e;
static void cc_101f203e(Context& c){if(!active(c)){old_block_101f203e(c);return;}
{uint32_t v=255u;nz(c,v);c.r[3]=v;}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+128u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=0u;nz(c,v);c.r[2]=v;}
{uint32_t v=c.r[6];c.r[0]=v;}
{uint32_t a=(c.r[13]+0u+0u);wr<uint32_t>(c,a+0u,c.r[2]);}
{uint32_t v=(c.r[3])&(~(4194304u));c.r[3]=v;}
{uint32_t v=72u;nz(c,v);c.r[1]=v;}
{uint32_t a=(c.r[4]+0u+128u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t v=c.r[2];c.r[3]=v;}
{c.r[14]=270475359u;c.pc=(270287196u|1u);return;}
c.pc=270475359u;}
static Block old_block_101f228e;
static void cc_101f228e(Context& c){if(!active(c)){old_block_101f228e(c);return;}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[3],~(16u),1,true);c.r[3]=v;}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t v=add(c,c.r[3],~(0u),1,true);}
{if(cond(c,13)){c.pc=(270476078u|1u);return;}}
c.pc=270475933u;}
static Block old_block_101f229c;
static void cc_101f229c(Context& c){if(!active(c)){old_block_101f229c(c);return;}
{uint32_t a=(c.r[4]+0u+132u);setsbits(c,14,rd<uint32_t>(c,a+0u));}
{uint32_t a=(c.r[4]+0u+136u);setsbits(c,15,rd<uint32_t>(c,a+0u));}
{setsbits(c,14,cvti(fs(c,14),true));}
{uint32_t v=255u;nz(c,v);c.r[3]=v;}
{uint32_t v=c.r[5];c.r[0]=v;}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);wr<uint32_t>(c,a+0u,c.r[3]);}
{setsbits(c,15,cvti(fs(c,15),true));}
{c.r[1]=sbits(c,14);}
{c.r[2]=sbits(c,15);}
{c.r[14]=270475969u;c.pc=(270474952u|1u);return;}
c.pc=270475969u;}
static Block old_block_101f2720;
static void cc_101f2720(Context& c){if(!active(c)){old_block_101f2720(c);return;}
{uint32_t v=add(c,c.r[0],2397u,0,false);c.r[0]=v;}
{uint32_t a=(c.r[7]+0u+0u);wr<uint32_t>(c,a+0u,c.r[0]);}
{uint32_t v=0u;nz(c,v);c.r[1]=v;}
{uint32_t a=(c.r[8]+0u+0u);wr<uint32_t>(c,a+0u,c.r[0]);}
{uint32_t v=c.r[4];c.r[0]=v;}
{uint32_t a=(c.r[13]+0u+12u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+0u+64u);a=array_address(c,a,false);wr<uint32_t>(c,a+0u,c.r[1]);}
{uint32_t a=(c.r[3]+0u+80u);wr<uint32_t>(c,a+0u,c.r[1]);}
{uint32_t a=(c.r[3]+0u+86u);wr<uint8_t>(c,a+0u,c.r[1]);}
{uint32_t a=(c.r[13]+0u+12u);wr<uint32_t>(c,a+0u,c.r[1]);}
{c.r[14]=270477119u;c.pc=(269889944u|1u);return;}
c.pc=270477119u;}
static Block old_block_101f2724;
static void cc_101f2724(Context& c){if(!active(c)){old_block_101f2724(c);return;}
{uint32_t a=(c.r[7]+0u+0u);wr<uint32_t>(c,a+0u,c.r[0]);}
{uint32_t v=0u;nz(c,v);c.r[1]=v;}
{uint32_t a=(c.r[8]+0u+0u);wr<uint32_t>(c,a+0u,c.r[0]);}
{uint32_t v=c.r[4];c.r[0]=v;}
{uint32_t a=(c.r[13]+0u+12u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+0u+64u);a=array_address(c,a,false);wr<uint32_t>(c,a+0u,c.r[1]);}
{uint32_t a=(c.r[3]+0u+80u);wr<uint32_t>(c,a+0u,c.r[1]);}
{uint32_t a=(c.r[3]+0u+86u);wr<uint8_t>(c,a+0u,c.r[1]);}
{uint32_t a=(c.r[13]+0u+12u);wr<uint32_t>(c,a+0u,c.r[1]);}
{c.r[14]=270477119u;c.pc=(269889944u|1u);return;}
c.pc=270477119u;}
static Block old_block_101f2e54;
static void cc_101f2e54(Context& c){if(!active(c)){old_block_101f2e54(c);return;}
{uint32_t a=(c.r[0]+0u+124u);c.r[0]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+208u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);c.r[2]=rd<uint32_t>(c,a+0u);}
{c.r[14]=270478947u;c.pc=(269711120u|1u);return;}
c.pc=270478947u;}
static Block old_block_101f2e80;
static void cc_101f2e80(Context& c){if(!active(c)){old_block_101f2e80(c);return;}
{uint32_t a=((270478980u&~3u)+0u+124u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+156u);setsbits(c,12,rd<uint32_t>(c,a+0u));}
{uint32_t a=(c.r[4]+0u+60u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+132u);setsbits(c,13,rd<uint32_t>(c,a+0u));}
{uint32_t v=add(c,c.r[3],270478992u,0,false);c.r[3]=v;}
{uint32_t a=(c.r[3]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+80u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+160u);setsbits(c,14,rd<uint32_t>(c,a+0u));}
{uint32_t a=(c.r[4]+0u+136u);setsbits(c,15,rd<uint32_t>(c,a+0u));}
{uint32_t a=(c.r[3]+shift(c,c.r[2],2,1,false)+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{setfs(c,13,(fs(c,12))+(fs(c,13)));}
{uint32_t a=(c.r[3]+shift(c,c.r[1],1,1,false)+0u);c.r[0]=rd<uint16_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+92u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[3],11200u,0,false);c.r[3]=v;}
{c.r[0]=uint32_t(int16_t(c.r[0]));}
{uint32_t v=add(c,c.r[3],32u,0,false);c.r[1]=v;}
{uint32_t a=((270479030u&~3u)+0u+80u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[3],270479032u,0,false);c.r[3]=v;}
{uint32_t a=(c.r[3]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[5],shift(c,c.r[1],2,1,false),0,false);c.r[1]=v;}
{setfs(c,15,(fs(c,14))+(fs(c,15)));}
{uint32_t a=(c.r[3]+shift(c,c.r[2],2,1,false)+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[13]+0u+0u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=((270479050u&~3u)+0u+64u);a=array_address(c,a,false);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[3],270479052u,0,false);c.r[3]=v;}
{uint32_t a=(c.r[3]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[3]+shift(c,c.r[2],2,1,false)+0u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[2],shift(c,c.r[0],1,1,false),0,false);c.r[3]=v;}
{uint32_t a=(c.r[13]+0u+4u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+168u);c.r[3]=rd<uint32_t>(c,a+0u);}
{c.r[2]=sbits(c,13);}
{uint32_t a=(c.r[13]+0u+8u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+172u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[13]+0u+12u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[4]+0u+236u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[13]+0u+16u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t v=0u;nz(c,v);c.r[3]=v;}
{uint32_t a=(c.r[13]+0u+20u);wr<uint32_t>(c,a+0u,c.r[3]);}
{c.r[3]=sbits(c,15);}
{uint32_t a=(c.r[5]+0u+124u);c.r[0]=rd<uint32_t>(c,a+0u);}
{c.r[14]=270479099u;c.pc=(269708822u|1u);return;}
c.pc=270479099u;}
static Block old_block_101f2f28;
static void cc_101f2f28(Context& c){if(!active(c)){old_block_101f2f28(c);return;}
{uint32_t a=(c.r[4]+0u+212u);a=array_address(c,a,true);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[0]+0u+124u);c.r[0]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[4]+0u+208u);c.r[1]=rd<uint32_t>(c,a+0u);}
{c.r[14]=270479159u;c.pc=(269711120u|1u);return;}
c.pc=270479159u;}
static Block old_block_10200160;
static void cc_10200160(Context& c){if(!active(c)){old_block_10200160(c);return;}extend_menu_icons(c);
{uint32_t a=c.r[13]-20u;wr<uint32_t>(c,a+0u,c.r[4]);wr<uint32_t>(c,a+4u,c.r[5]);wr<uint32_t>(c,a+8u,c.r[6]);wr<uint32_t>(c,a+12u,c.r[7]);wr<uint32_t>(c,a+16u,c.r[14]);c.r[13]=a;}
{uint32_t v=add(c,c.r[13],~(28u),1,false);c.r[13]=v;}
{uint32_t v=c.r[0];c.r[6]=v;}
{uint32_t a=(c.r[13]+0u+48u);c.r[0]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[0],~(0u),1,true);}
{if(cond(c,12)){c.pc=(270533062u|1u);return;}}
c.pc=270532973u;}
static Block old_block_102005dc;
static void cc_102005dc(Context& c){if(!active(c)){old_block_102005dc(c);return;}extend_menu_icons(c);
{uint32_t a=c.r[13]-20u;wr<uint32_t>(c,a+0u,c.r[4]);wr<uint32_t>(c,a+4u,c.r[5]);wr<uint32_t>(c,a+8u,c.r[6]);wr<uint32_t>(c,a+12u,c.r[7]);wr<uint32_t>(c,a+16u,c.r[14]);c.r[13]=a;}
{uint32_t v=add(c,c.r[13],~(28u),1,false);c.r[13]=v;}
{uint32_t v=c.r[0];c.r[6]=v;}
{uint32_t a=(c.r[13]+0u+56u);c.r[0]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[13]+0u+52u);c.r[4]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[0],~(0u),1,true);}
{if(cond(c,12)){c.pc=(270534210u|1u);return;}}
c.pc=270534123u;}
static Block old_block_102010a4;
static void cc_102010a4(Context& c){if(!active(c)){old_block_102010a4(c);return;}extend_menu_icons(c);
{uint32_t a=c.r[13]-28u;wr<uint32_t>(c,a+0u,c.r[4]);wr<uint32_t>(c,a+4u,c.r[5]);wr<uint32_t>(c,a+8u,c.r[6]);wr<uint32_t>(c,a+12u,c.r[7]);wr<uint32_t>(c,a+16u,c.r[8]);wr<uint32_t>(c,a+20u,c.r[9]);wr<uint32_t>(c,a+24u,c.r[14]);c.r[13]=a;}
{uint32_t v=c.r[0];c.r[6]=v;}
{uint32_t a=(c.r[13]+0u+36u);c.r[1]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[13]+0u+28u);c.r[0]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[1],~(0u),1,true);}
{uint32_t a=(c.r[13]+0u+32u);c.r[5]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[13]+0u+40u);c.r[9]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[13]+0u+44u);c.r[8]=rd<uint32_t>(c,a+0u);}
{uint32_t a=(c.r[13]+0u+48u);c.r[12]=rd<uint32_t>(c,a+0u);}
{if(cond(c,12)){c.pc=(270536976u|1u);return;}}
c.pc=270536897u;}
static Block old_block_102022fa;
static void cc_102022fa(Context& c){if(!active(c)){old_block_102022fa(c);return;}
{uint32_t a=((270541566u&~3u)+0u+644u);c.r[6]=rd<uint32_t>(c,a+0u);}
{uint32_t v=c.r[0];c.r[7]=v;}
{uint32_t v=add(c,c.r[6],270541570u,0,false);c.r[6]=v;}
{uint32_t a=(c.r[6]+0u+0u);c.r[6]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[6],~(4u),1,true);c.r[5]=v;}
{uint32_t v=add(c,c.r[6],(4u*total(c)-4u),0,false);c.r[8]=v;}
{uint32_t a=(c.r[5]+0u+4u);c.r[0]=rd<uint32_t>(c,a+0u);}
{if(c.r[0] == 0){c.pc=(270541584u|1u);return;}}
c.pc=270541581u;}
static Block old_block_10202f0e;
static void cc_10202f0e(Context& c){if(!active(c)){old_block_10202f0e(c);return;}
{uint32_t a=((270544658u&~3u)+0u+76u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[3],270544660u,0,false);c.r[3]=v;}
{uint32_t a=(c.r[3]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[3],~(4u),1,true);c.r[5]=v;}
{uint32_t v=add(c,c.r[3],(4u*total(c)-4u),0,false);c.r[7]=v;}
{uint32_t a=(c.r[5]+0u+4u);c.r[0]=rd<uint32_t>(c,a+0u);}
{if(c.r[0] == 0){c.pc=(270544674u|1u);return;}}
c.pc=270544671u;}
static Block old_block_10209826;
static void cc_10209826(Context& c){if(!active(c)){old_block_10209826(c);return;}
{uint32_t v=0u;nz(c,v);c.r[3]=v;}
{uint32_t a=(c.r[5]+0u+12u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=((270571566u&~3u)+0u+52u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=0u;nz(c,v);c.r[6]=v;}
{uint32_t v=add(c,c.r[3],270571570u,0,false);c.r[3]=v;}
{uint32_t a=(c.r[3]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[3],~(4u),1,true);c.r[5]=v;}
{uint32_t v=add(c,c.r[3],(4u*total(c)-4u),0,false);c.r[7]=v;}
{uint32_t a=(c.r[5]+0u+4u);c.r[0]=rd<uint32_t>(c,a+0u);}
{if(c.r[0] == 0){c.pc=(270571584u|1u);return;}}
c.pc=270571581u;}
static Block old_block_1020982a;
static void cc_1020982a(Context& c){if(!active(c)){old_block_1020982a(c);return;}
{uint32_t a=((270571566u&~3u)+0u+52u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=0u;nz(c,v);c.r[6]=v;}
{uint32_t v=add(c,c.r[3],270571570u,0,false);c.r[3]=v;}
{uint32_t a=(c.r[3]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[3],~(4u),1,true);c.r[5]=v;}
{uint32_t v=add(c,c.r[3],(4u*total(c)-4u),0,false);c.r[7]=v;}
{uint32_t a=(c.r[5]+0u+4u);c.r[0]=rd<uint32_t>(c,a+0u);}
{if(c.r[0] == 0){c.pc=(270571584u|1u);return;}}
c.pc=270571581u;}
static Block old_block_1020a3cc;
static void cc_1020a3cc(Context& c){if(!active(c)){old_block_1020a3cc(c);return;}
{uint32_t a=((270574544u&~3u)+0u+56u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[3],270574546u,0,false);c.r[3]=v;}
{uint32_t a=(c.r[3]+0u+0u);c.r[3]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[3],~(4u),1,true);c.r[5]=v;}
{uint32_t v=add(c,c.r[3],(4u*total(c)-4u),0,false);c.r[7]=v;}
{uint32_t a=(c.r[5]+0u+4u);c.r[0]=rd<uint32_t>(c,a+0u);}
{if(c.r[0] == 0){c.pc=(270574560u|1u);return;}}
c.pc=270574557u;}
static Block old_block_1020baa8;
static void cc_1020baa8(Context& c){if(!active(c)){old_block_1020baa8(c);return;}
{uint32_t a=c.r[13]-36u;wr<uint32_t>(c,a+0u,c.r[4]);wr<uint32_t>(c,a+4u,c.r[5]);wr<uint32_t>(c,a+8u,c.r[6]);wr<uint32_t>(c,a+12u,c.r[7]);wr<uint32_t>(c,a+16u,c.r[8]);wr<uint32_t>(c,a+20u,c.r[9]);wr<uint32_t>(c,a+24u,c.r[10]);wr<uint32_t>(c,a+28u,c.r[11]);wr<uint32_t>(c,a+32u,c.r[14]);c.r[13]=a;}
{uint32_t a=c.r[13]-8u;wr<uint64_t>(c,a+0u,c.d[8]);c.r[13]=a;}
{uint32_t v=shift(c,c.r[1],2u,1,true);nz(c,v);c.r[3]=v;}
{uint32_t a=((270580406u&~3u)+0u+1052u);c.r[7]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[0],47104u,0,false);c.r[6]=v;}
{uint32_t v=add(c,c.r[13],~(292u),1,false);c.r[13]=v;}
{uint32_t v=add(c,c.r[1],~(1u),1,true);c.r[2]=v;}
{uint32_t v=add(c,c.r[7],270580418u,0,false);c.r[7]=v;}
{uint32_t v=c.r[0];c.r[4]=v;}
{uint32_t v=add(c,c.r[7],1168u,0,false);c.r[9]=v;}
{uint32_t v=add(c,c.r[7],32u,0,false);c.r[10]=v;}
{uint32_t v=add(c,c.r[7],96u,0,false);c.r[8]=v;}
{uint32_t v=(active(c)?head(c,44):add(c,c.r[7],116u,0,true));c.r[7]=v;}
{uint32_t v=add(c,c.r[9],c.r[3],0,false);c.r[9]=v;}
{uint32_t v=add(c,c.r[10],c.r[3],0,false);c.r[10]=v;}
{uint32_t v=add(c,c.r[8],c.r[3],0,false);c.r[8]=v;}
{uint32_t v=add(c,c.r[7],c.r[3],0,false);c.r[7]=v;}
{uint32_t v=c.r[1];c.r[11]=v;}
{uint32_t v=0u;nz(c,v);c.r[5]=v;}
{uint32_t a=(c.r[6]+0u+164u);wr<uint32_t>(c,a+0u,c.r[5]);}
{uint32_t v=add(c,c.r[2],~(0u),1,true);}
{if(cond(c,12)){c.pc=(270580552u|1u);return;}}
c.pc=270580453u;}
static Block old_block_1020bb9a;
static void cc_1020bb9a(Context& c){if(!active(c)){old_block_1020bb9a(c);return;}
{uint32_t a=((270580638u&~3u)+0u+840u);c.r[2]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[2],270580640u,0,false);c.r[2]=v;}
{uint32_t v=(active(c)?head(c,44):add(c,c.r[2],116u,0,true));c.r[2]=v;}
{uint32_t a=(c.r[2]+c.r[3]+0u);c.r[5]=rd<uint32_t>(c,a+0u);}
{uint32_t v=c.r[5];c.r[0]=v;}
{c.r[14]=270580649u;c.pc=(269899408u|1u);return;}
c.pc=270580649u;}
static Block old_block_1020be14;
static void cc_1020be14(Context& c){if(!active(c)){old_block_1020be14(c);return;}
{uint32_t v=add(c,c.r[2],~(1u),1,true);}
{}
{if(cond(c,1)){uint32_t v=add(c,c.r[8],96u,0,false);c.r[2]=v;}}
{if(cond(c,2)){uint32_t v=(active(c)?head(c,44):add(c,c.r[5],116u,0,false));c.r[2]=v;}}
{uint32_t a=(c.r[2]+c.r[3]+0u);c.r[11]=rd<uint32_t>(c,a+0u);}
{uint32_t v=c.r[4];c.r[0]=v;}
{uint32_t v=c.r[11];c.r[1]=v;}
{c.r[14]=270581293u;c.pc=(270570484u|1u);return;}
c.pc=270581293u;}
static Block old_block_1020c0c4;
static void cc_1020c0c4(Context& c){if(!active(c)){old_block_1020c0c4(c);return;}
{uint32_t v=(259u+head(c,4));c.r[3]=v;}
{uint32_t a=(c.r[5]+0u+160u);wr<uint32_t>(c,a+0u,c.r[3]);}
{uint32_t a=(c.r[5]+0u+156u);c.r[3]=rd<uint32_t>(c,a+0u);}
{if(c.r[3] == 0){c.pc=(270582012u|1u);return;}}
c.pc=270581971u;}
static Block old_block_1020c0e8;
static void cc_1020c0e8(Context& c){if(!active(c)){old_block_1020c0e8(c);return;}
{uint32_t v=(active(c)?head(c,44):add(c,c.r[0],116u,0,false));c.r[7]=v;}
{uint32_t a=(c.r[7]+shift(c,c.r[1],2,1,false)+0u);c.r[7]=rd<uint32_t>(c,a+0u);}
{uint32_t v=add(c,c.r[3],~(c.r[7]),1,true);}
{if(cond(c,2)){c.pc=(270582008u|1u);return;}}
c.pc=270582005u;}
static Block old_block_1020dc74;
static void cc_1020dc74(Context& c){if(!active(c)){old_block_1020dc74(c);return;}
{uint32_t v=add(c,c.r[7],~((head(c,72)-1u)),1,true);}
{if(cond(c,13)){c.pc=(270589256u|1u);return;}}
c.pc=270589049u;}
extern "C" __declspec(dllexport) void msd_enable_community_content(){static bool done=false;if(done)return;find_block(0x101652a9u);done=true;
old_block_101c9abc=find_block(270310077u);register_block(270310077u,cc_101c9abc);
old_block_101d09b4=find_block(270338485u);register_block(270338485u,cc_101d09b4);
old_block_101d09c2=find_block(270338499u);register_block(270338499u,cc_101d09c2);
old_block_101dacbc=find_block(270380221u);register_block(270380221u,cc_101dacbc);
old_block_101dc844=find_block(270387269u);register_block(270387269u,cc_101dc844);
old_block_101dc85e=find_block(270387295u);register_block(270387295u,cc_101dc85e);
old_block_101dc86c=find_block(270387309u);register_block(270387309u,cc_101dc86c);
old_block_101dc874=find_block(270387317u);register_block(270387317u,cc_101dc874);
old_block_101dc886=find_block(270387335u);register_block(270387335u,cc_101dc886);
old_block_101dc890=find_block(270387345u);register_block(270387345u,cc_101dc890);
old_block_101dc8aa=find_block(270387371u);register_block(270387371u,cc_101dc8aa);
old_block_101dc8b8=find_block(270387385u);register_block(270387385u,cc_101dc8b8);
old_block_101dc8c0=find_block(270387393u);register_block(270387393u,cc_101dc8c0);
old_block_101dc8d2=find_block(270387411u);register_block(270387411u,cc_101dc8d2);
old_block_101dc8dc=find_block(270387421u);register_block(270387421u,cc_101dc8dc);
old_block_101dc8f6=find_block(270387447u);register_block(270387447u,cc_101dc8f6);
old_block_101dc904=find_block(270387461u);register_block(270387461u,cc_101dc904);
old_block_101dc90c=find_block(270387469u);register_block(270387469u,cc_101dc90c);
old_block_101dc91e=find_block(270387487u);register_block(270387487u,cc_101dc91e);
old_block_101dc92a=find_block(270387499u);register_block(270387499u,cc_101dc92a);
old_block_101dc938=find_block(270387513u);register_block(270387513u,cc_101dc938);
old_block_101dc94a=find_block(270387531u);register_block(270387531u,cc_101dc94a);
old_block_101dc952=find_block(270387539u);register_block(270387539u,cc_101dc952);
old_block_101dc956=find_block(270387543u);register_block(270387543u,cc_101dc956);
old_block_101dc95e=find_block(270387551u);register_block(270387551u,cc_101dc95e);
old_block_101dc96c=find_block(270387565u);register_block(270387565u,cc_101dc96c);
old_block_101dc984=find_block(270387589u);register_block(270387589u,cc_101dc984);
old_block_101dc998=find_block(270387609u);register_block(270387609u,cc_101dc998);
old_block_101dc9a6=find_block(270387623u);register_block(270387623u,cc_101dc9a6);
old_block_101dc9b6=find_block(270387639u);register_block(270387639u,cc_101dc9b6);
old_block_101dc9d4=find_block(270387669u);register_block(270387669u,cc_101dc9d4);
old_block_101dc9ea=find_block(270387691u);register_block(270387691u,cc_101dc9ea);
old_block_101dc9f0=find_block(270387697u);register_block(270387697u,cc_101dc9f0);
old_block_101dca24=find_block(270387749u);register_block(270387749u,cc_101dca24);
old_block_101dca38=find_block(270387769u);register_block(270387769u,cc_101dca38);
old_block_101dca3e=find_block(270387775u);register_block(270387775u,cc_101dca3e);
old_block_101dca52=find_block(270387795u);register_block(270387795u,cc_101dca52);
old_block_101dca70=find_block(270387825u);register_block(270387825u,cc_101dca70);
old_block_101dca7a=find_block(270387835u);register_block(270387835u,cc_101dca7a);
old_block_101dca8e=find_block(270387855u);register_block(270387855u,cc_101dca8e);
old_block_101dca96=find_block(270387863u);register_block(270387863u,cc_101dca96);
old_block_101dcaa2=find_block(270387875u);register_block(270387875u,cc_101dcaa2);
old_block_101dcaa8=find_block(270387881u);register_block(270387881u,cc_101dcaa8);
old_block_101dcab2=find_block(270387891u);register_block(270387891u,cc_101dcab2);
old_block_101dcabc=find_block(270387901u);register_block(270387901u,cc_101dcabc);
old_block_101dcace=find_block(270387919u);register_block(270387919u,cc_101dcace);
old_block_101dcad4=find_block(270387925u);register_block(270387925u,cc_101dcad4);
old_block_101dcae0=find_block(270387937u);register_block(270387937u,cc_101dcae0);
old_block_101dcae6=find_block(270387943u);register_block(270387943u,cc_101dcae6);
old_block_101dcaec=find_block(270387949u);register_block(270387949u,cc_101dcaec);
old_block_101dcaf2=find_block(270387955u);register_block(270387955u,cc_101dcaf2);
old_block_101dcafe=find_block(270387967u);register_block(270387967u,cc_101dcafe);
old_block_101dcb08=find_block(270387977u);register_block(270387977u,cc_101dcb08);
old_block_101dcb28=find_block(270388009u);register_block(270388009u,cc_101dcb28);
old_block_101dcb4e=find_block(270388047u);register_block(270388047u,cc_101dcb4e);
old_block_101dcb52=find_block(270388051u);register_block(270388051u,cc_101dcb52);
old_block_101dcb8c=find_block(270388109u);register_block(270388109u,cc_101dcb8c);
old_block_101dcb9c=find_block(270388125u);register_block(270388125u,cc_101dcb9c);
old_block_101dcbba=find_block(270388155u);register_block(270388155u,cc_101dcbba);
old_block_101dcbe8=find_block(270388201u);register_block(270388201u,cc_101dcbe8);
old_block_101dcbea=find_block(270388203u);register_block(270388203u,cc_101dcbea);
old_block_101dcc02=find_block(270388227u);register_block(270388227u,cc_101dcc02);
old_block_101dcc04=find_block(270388229u);register_block(270388229u,cc_101dcc04);
old_block_101dcc26=find_block(270388263u);register_block(270388263u,cc_101dcc26);
old_block_101dcc64=find_block(270388325u);register_block(270388325u,cc_101dcc64);
old_block_101dcc7a=find_block(270388347u);register_block(270388347u,cc_101dcc7a);
old_block_101dcc7e=find_block(270388351u);register_block(270388351u,cc_101dcc7e);
old_block_101dcc84=find_block(270388357u);register_block(270388357u,cc_101dcc84);
old_block_101dcca0=find_block(270388385u);register_block(270388385u,cc_101dcca0);
old_block_101dccac=find_block(270388397u);register_block(270388397u,cc_101dccac);
old_block_101dccd8=find_block(270388441u);register_block(270388441u,cc_101dccd8);
old_block_101dccee=find_block(270388463u);register_block(270388463u,cc_101dccee);
old_block_101dccf2=find_block(270388467u);register_block(270388467u,cc_101dccf2);
old_block_101dccf8=find_block(270388473u);register_block(270388473u,cc_101dccf8);
old_block_101dcd14=find_block(270388501u);register_block(270388501u,cc_101dcd14);
old_block_101dcd20=find_block(270388513u);register_block(270388513u,cc_101dcd20);
old_block_101dcd50=find_block(270388561u);register_block(270388561u,cc_101dcd50);
old_block_101dcdb6=find_block(270388663u);register_block(270388663u,cc_101dcdb6);
old_block_101dcdbc=find_block(270388669u);register_block(270388669u,cc_101dcdbc);
old_block_101dcdc2=find_block(270388675u);register_block(270388675u,cc_101dcdc2);
old_block_101dcdc8=find_block(270388681u);register_block(270388681u,cc_101dcdc8);
old_block_101dcdcc=find_block(270388685u);register_block(270388685u,cc_101dcdcc);
old_block_101dcdd6=find_block(270388695u);register_block(270388695u,cc_101dcdd6);
old_block_101dcddc=find_block(270388701u);register_block(270388701u,cc_101dcddc);
old_block_101dcde0=find_block(270388705u);register_block(270388705u,cc_101dcde0);
old_block_101dcdea=find_block(270388715u);register_block(270388715u,cc_101dcdea);
old_block_101dcdee=find_block(270388719u);register_block(270388719u,cc_101dcdee);
old_block_101dce24=find_block(270388773u);register_block(270388773u,cc_101dce24);
old_block_101dce2a=find_block(270388779u);register_block(270388779u,cc_101dce2a);
old_block_101dce30=find_block(270388785u);register_block(270388785u,cc_101dce30);
old_block_101dce36=find_block(270388791u);register_block(270388791u,cc_101dce36);
old_block_101dce3a=find_block(270388795u);register_block(270388795u,cc_101dce3a);
old_block_101e1be2=find_block(270408675u);register_block(270408675u,cc_101e1be2);
old_block_101ed5e4=find_block(270456293u);register_block(270456293u,cc_101ed5e4);
old_block_101ed6ac=find_block(270456493u);register_block(270456493u,cc_101ed6ac);
old_block_101ed6f4=find_block(270456565u);register_block(270456565u,cc_101ed6f4);
old_block_101edaaa=find_block(270457515u);register_block(270457515u,cc_101edaaa);
old_block_101edb68=find_block(270457705u);register_block(270457705u,cc_101edb68);
old_block_101ee836=find_block(270460983u);register_block(270460983u,cc_101ee836);
old_block_101eef84=find_block(270462853u);register_block(270462853u,cc_101eef84);
old_block_101eefa4=find_block(270462885u);register_block(270462885u,cc_101eefa4);
old_block_101eefde=find_block(270462943u);register_block(270462943u,cc_101eefde);
old_block_101eefea=find_block(270462955u);register_block(270462955u,cc_101eefea);
old_block_101ef012=find_block(270462995u);register_block(270462995u,cc_101ef012);
old_block_101ef024=find_block(270463013u);register_block(270463013u,cc_101ef024);
old_block_101ef3bc=find_block(270463933u);register_block(270463933u,cc_101ef3bc);
old_block_101ef468=find_block(270464105u);register_block(270464105u,cc_101ef468);
old_block_101ef6fc=find_block(270464765u);register_block(270464765u,cc_101ef6fc);
old_block_101ef87a=find_block(270465147u);register_block(270465147u,cc_101ef87a);
old_block_101f007e=find_block(270467199u);register_block(270467199u,cc_101f007e);
old_block_101f022a=find_block(270467627u);register_block(270467627u,cc_101f022a);
old_block_101f02da=find_block(270467803u);register_block(270467803u,cc_101f02da);
old_block_101f0536=find_block(270468407u);register_block(270468407u,cc_101f0536);
old_block_101f0706=find_block(270468871u);register_block(270468871u,cc_101f0706);
old_block_101f083e=find_block(270469183u);register_block(270469183u,cc_101f083e);
old_block_101f08fa=find_block(270469371u);register_block(270469371u,cc_101f08fa);
old_block_101f0a42=find_block(270469699u);register_block(270469699u,cc_101f0a42);
old_block_101f0b08=find_block(270469897u);register_block(270469897u,cc_101f0b08);
old_block_101f0c28=find_block(270470185u);register_block(270470185u,cc_101f0c28);
old_block_101f11b6=find_block(270471607u);register_block(270471607u,cc_101f11b6);
old_block_101f12d4=find_block(270471893u);register_block(270471893u,cc_101f12d4);
old_block_101f1650=find_block(270472785u);register_block(270472785u,cc_101f1650);
old_block_101f1694=find_block(270472853u);register_block(270472853u,cc_101f1694);
old_block_101f169e=find_block(270472863u);register_block(270472863u,cc_101f169e);
old_block_101f16c2=find_block(270472899u);register_block(270472899u,cc_101f16c2);
old_block_101f16c4=find_block(270472901u);register_block(270472901u,cc_101f16c4);
old_block_101f17a4=find_block(270473125u);register_block(270473125u,cc_101f17a4);
old_block_101f1a7a=find_block(270473851u);register_block(270473851u,cc_101f1a7a);
old_block_101f1b28=find_block(270474025u);register_block(270474025u,cc_101f1b28);
old_block_101f1b32=find_block(270474035u);register_block(270474035u,cc_101f1b32);
old_block_101f1b6c=find_block(270474093u);register_block(270474093u,cc_101f1b6c);
old_block_101f1bae=find_block(270474159u);register_block(270474159u,cc_101f1bae);
old_block_101f1c62=find_block(270474339u);register_block(270474339u,cc_101f1c62);
old_block_101f1fc0=find_block(270475201u);register_block(270475201u,cc_101f1fc0);
old_block_101f1fca=find_block(270475211u);register_block(270475211u,cc_101f1fca);
old_block_101f2034=find_block(270475317u);register_block(270475317u,cc_101f2034);
old_block_101f203e=find_block(270475327u);register_block(270475327u,cc_101f203e);
old_block_101f228e=find_block(270475919u);register_block(270475919u,cc_101f228e);
old_block_101f229c=find_block(270475933u);register_block(270475933u,cc_101f229c);
old_block_101f2720=find_block(270477089u);register_block(270477089u,cc_101f2720);
old_block_101f2724=find_block(270477093u);register_block(270477093u,cc_101f2724);
old_block_101f2e54=find_block(270478933u);register_block(270478933u,cc_101f2e54);
old_block_101f2e80=find_block(270478977u);register_block(270478977u,cc_101f2e80);
old_block_101f2f28=find_block(270479145u);register_block(270479145u,cc_101f2f28);
old_block_10200160=find_block(270532961u);register_block(270532961u,cc_10200160);
old_block_102005dc=find_block(270534109u);register_block(270534109u,cc_102005dc);
old_block_102010a4=find_block(270536869u);register_block(270536869u,cc_102010a4);
old_block_102022fa=find_block(270541563u);register_block(270541563u,cc_102022fa);
old_block_10202f0e=find_block(270544655u);register_block(270544655u,cc_10202f0e);
old_block_10209826=find_block(270571559u);register_block(270571559u,cc_10209826);
old_block_1020982a=find_block(270571563u);register_block(270571563u,cc_1020982a);
old_block_1020a3cc=find_block(270574541u);register_block(270574541u,cc_1020a3cc);
old_block_1020baa8=find_block(270580393u);register_block(270580393u,cc_1020baa8);
old_block_1020bb9a=find_block(270580635u);register_block(270580635u,cc_1020bb9a);
old_block_1020be14=find_block(270581269u);register_block(270581269u,cc_1020be14);
old_block_1020c0c4=find_block(270581957u);register_block(270581957u,cc_1020c0c4);
old_block_1020c0e8=find_block(270581993u);register_block(270581993u,cc_1020c0e8);
old_block_1020dc74=find_block(270589045u);register_block(270589045u,cc_1020dc74);
old_vehicle_motion=find_block(0x101dde11u);register_block(0x101dde11u,vehicle_motion);
old_unitdata=find_block(0x101652a9u);register_block(0x101652a9u,unitdata);
old_unitname=find_block(0x101652d5u);register_block(0x101652d5u,unitname);
old_unitinfo=find_block(0x101652e9u);register_block(0x101652e9u,unitinfo);
old_maxlevel=find_block(0x1016533bu);register_block(0x1016533bu,maxlevel);
old_getlevel=find_block(0x10167af1u);register_block(0x10167af1u,getlevel);
old_setlevel=find_block(0x10167b5bu);register_block(0x10167b5bu,setlevel);
old_addlevel=find_block(0x10167b0fu);register_block(0x10167b0fu,addlevel);
old_getopen=find_block(0x10167ccbu);register_block(0x10167ccbu,getopen);
old_isopen=find_block(0x10167cf3u);register_block(0x10167cf3u,isopen);
old_setopen=find_block(0x10167d69u);register_block(0x10167d69u,setopen);
old_addopen=find_block(0x10167d1du);register_block(0x10167d1du,addopen);
old_gettime=find_block(0x10167bafu);register_block(0x10167bafu,gettime);
old_settime=find_block(0x10167bcfu);register_block(0x10167bcfu,settime);
old_getdecktime=find_block(0x10167c0du);register_block(0x10167c0du,getdecktime);
old_setdecktime=find_block(0x10167c2bu);register_block(0x10167c2bu,setdecktime);
old_getnew=find_block(0x10167c67u);register_block(0x10167c67u,getnew);
old_addnew=find_block(0x10167c7bu);register_block(0x10167c7bu,addnew);
old_delnew=find_block(0x10167ca3u);register_block(0x10167ca3u,delnew);
old_shopdata=find_block(0x101655c9u);register_block(0x101655c9u,shopdata);
old_shopprice=find_block(0x101656c5u);register_block(0x101656c5u,shopprice);
old_shopmax=find_block(0x10165709u);register_block(0x10165709u,shopmax);
old_shopstock=find_block(0x10165749u);register_block(0x10165749u,shopstock);
old_soldout=find_block(0x10165835u);register_block(0x10165835u,soldout);
old_shopdisplay=find_block(0x1016595fu);register_block(0x1016595fu,shopdisplay);
old_shopdiscount=find_block(0x1016596bu);register_block(0x1016596bu,shopdiscount);
old_discount=find_block(0x1020b459u);register_block(0x1020b459u,discount);
old_shopavailable=find_block(0x102093f5u);register_block(0x102093f5u,shopavailable);
old_shopenable=find_block(0x10167d8du);register_block(0x10167d8du,shopenable);
old_setshopenable=find_block(0x10167da1u);register_block(0x10167da1u,setshopenable);
old_getshopnew=find_block(0x10167dc9u);register_block(0x10167dc9u,getshopnew);
old_addshopnew=find_block(0x10167dddu);register_block(0x10167dddu,addshopnew);
old_delshopnew=find_block(0x10167e05u);register_block(0x10167e05u,delshopnew);
old_convertunit=find_block(0x101dc929u);register_block(0x101dc929u,convertunit);
old_aux_preload_status=find_block(0x101c945du);register_block(0x101c945du,aux_preload_status);
old_image_index_boundary=find_block(0x101dcb09u);register_block(0x101dcb09u,image_index_boundary);
old_image_create_boundary=find_block(0x101dcbc5u);register_block(0x101dcbc5u,image_create_boundary);
old_sound_read_boundary=find_block(0x101dcc65u);register_block(0x101dcc65u,sound_read_boundary);
old_sound_release_boundary=find_block(0x101dccd9u);register_block(0x101dccd9u,sound_release_boundary);
old_resource_uid_boundary=find_block(0x101dcba9u);register_block(0x101dcba9u,resource_uid_boundary);
old_sound_uid_boundary=find_block(0x101dccc1u);register_block(0x101dccc1u,sound_uid_boundary);
old_release_uid_boundary=find_block(0x101dcd31u);register_block(0x101dcd31u,release_uid_boundary);
old_status_boundary=find_block(0x101cfbcdu);register_block(0x101cfbcdu,status_boundary);
old_create_params_boundary=find_block(0x101cfa99u);register_block(0x101cfa99u,create_params_boundary);
old_real_unit_factory_boundary=find_block(0x101d1421u);register_block(0x101d1421u,real_unit_factory_boundary);
old_pack_unit=find_block(0x101654b5u);register_block(0x101654b5u,pack_unit);
old_pack_x=find_block(0x101654d1u);register_block(0x101654d1u,pack_x);
old_pack_y=find_block(0x101654edu);register_block(0x101654edu,pack_y);
old_pack_name=find_block(0x1016551du);register_block(0x1016551du,pack_name);
old_pack_info=find_block(0x10165509u);register_block(0x10165509u,pack_info);
old_paratrooper_landing=find_block(0x101de225u);register_block(0x101de225u,paratrooper_landing);
old_menu_display_id=find_block(0x101652fdu);register_block(0x101652fdu,menu_display_id);
old_mummy_recovery=find_block(0x101de017u);register_block(0x101de017u,mummy_recovery);
old_mummy_viewer_setup=find_block(0x1020a665u);register_block(0x1020a665u,mummy_viewer_setup);
old_mummy_viewer_child=find_block(0x1020a571u);register_block(0x1020a571u,mummy_viewer_child);
old_mummy_viewer_update=find_block(0x1020b0edu);register_block(0x1020b0edu,mummy_viewer_update);
old_mummy_viewer_initial_state=find_block(0x1020ab2du);register_block(0x1020ab2du,mummy_viewer_initial_state);
old_enemy_roster=find_block(0x101c9d07u);register_block(0x101c9d07u,enemy_roster);
old_enemy_unit_enable=find_block(0x101c98fbu);register_block(0x101c98fbu,enemy_unit_enable);
old_enemy_special_policy=find_block(0x101c9da3u);register_block(0x101c9da3u,enemy_special_policy);
old_extension_music=find_block(0x101c6625u);register_block(0x101c6625u,extension_music);
old_extension_mission=find_block(0x101d09fdu);register_block(0x101d09fdu,extension_mission);
old_kt21_flame_interrupt=find_block(0x101de017u);register_block(0x101de017u,kt21_flame_interrupt);
old_kt21_flame_ending_bullet=find_block(0x1017d7fdu);register_block(0x1017d7fdu,kt21_flame_ending_bullet);
old_kt21_flame_knockback_limit=find_block(0x101e0b5du);register_block(0x101e0b5du,kt21_flame_knockback_limit);
old_kt21_flame_battle_reset=find_block(0x101e019du);register_block(0x101e019du,kt21_flame_battle_reset);
old_ground_special_update=find_block(0x10192571u);register_block(0x10192571u,ground_special_update);
}