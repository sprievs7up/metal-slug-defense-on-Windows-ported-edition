#include "aot_runtime.h"
#include "native_imports.h"

// Retention follows each original BattleUnit instance, including truck
// passengers. No new save fields, global unit-ID flags or frame polling.
// 角色类：原版十类角色为自身 UnitID；带 retained_special_weapon 行为的社区单位为其基准 UnitID（community_content.cpp）。
uint32_t msd_retained_class(Context& c,uint32_t uid);
void msd_retained_count(Context& c,uint32_t uid);
static uint32_t retained_unit(Context& c){
    uint32_t sprite=c.r[4],animation=c.r[5];
    // BattleSpriteFactory owns a static ELF-data pool; the sprite can reside
    // below the dynamic heap. The callback and BattleUnit checks identify it.
    if(sprite<0x10000000u||sprite>=0x1e000000u||
       rd<uint32_t>(c,sprite+0x58u)!=animation)return 0u;
    uint32_t callback=rd<uint32_t>(c,sprite+0x50u);
    if(callback<0x12000008u||callback>=0x1e000000u)return 0u;
    uint32_t unit=callback-8u;
    // BattleUnit's primary vtable, plus the callback's owning sprite.
    if(rd<uint32_t>(c,unit)!=0x1092f710u||
       rd<uint32_t>(c,unit+0x5cu)!=sprite||
       !rd<uint32_t>(c,unit+0x324u))return 0u;
    return msd_retained_class(c,rd<uint32_t>(c,unit+0x128u))?unit:0u;
}
void msd_retained_weapon_script(Context& c){
    if(rd<uint32_t>(c,c.r[5]+0xcu)!=9u)return;
    if(retained_unit(c))c.r[2]=rd<uint32_t>(c,c.r[1]+10u*4u);
}
bool msd_retained_weapon_discard(Context& c){
    uint32_t script=rd<uint32_t>(c,c.r[5]+0xcu);
    if(script!=9u&&script!=10u)return false;
    uint32_t unit=retained_unit(c);
    if(!unit)return false;
    uint32_t id=msd_retained_class(c,rd<uint32_t>(c,unit+0x128u)),effect=rd<uint32_t>(c,c.r[6]+4u);
    // These effects depict discarding the equipped gun. Other script-12
    // operations include muzzle flashes and laser cleanup and remain active.
    return ((id==16u||id==17u)&&effect==23u)||
           ((id==18u||id==19u||id==344u||id==362u)&&effect==28u);
}
void msd_retained_weapon_frame(Context& c){
    uint32_t script=rd<uint32_t>(c,c.r[5]+0xcu);
    if(script!=9u&&script!=10u)return;
    uint32_t unit=retained_unit(c);
    if(!unit)return;
    uint32_t id=msd_retained_class(c,rd<uint32_t>(c,unit+0x128u));
    // The fat variants finish their gun burst with unarmed body frames.
    // Retain the matching gun pose while preserving every script timer.
    if(id==96u&&c.r[3]==0u)c.r[3]=198u;
    if(id==98u&&(c.r[3]==0u||c.r[3]==2u||c.r[3]==4u||c.r[3]==6u))c.r[3]=256u;
}
void msd_retained_fat_eri_laser(Context& c){
    // 胖子英里保留的大激光使用原生激光参数组，涵盖伤害、间隔、射程和速度。
    // 参数组仅作用于本次弹体生成；单位攻击状态、冷却及绝招计数保持原值。
    uint32_t unit=c.r[4];
    if(unit<0x12000000u||unit>=0x1e000000u||
       rd<uint32_t>(c,unit)!=0x1092f710u||
       msd_retained_class(c,rd<uint32_t>(c,unit+0x128u))!=98u||
       rd<uint32_t>(c,unit+0x88u)!=40u||
       !rd<uint32_t>(c,unit+0x324u))return;
    wr<uint32_t>(c,c.r[13]+12u,50u);
}
void msd_retained_weapon_params(Context& c){
    // 公共弹体入口的第三个栈参数指定参数组；0 表示读取单位当前状态。
    // 首次特攻后的远程普攻引用原生武器参数，保留近战与单位状态语义。
    uint32_t unit=c.r[1];
    if(unit<0x12000000u||unit>=0x1e000000u||
       rd<uint32_t>(c,unit)!=0x1092f710u||
       rd<uint32_t>(c,unit+0x88u)!=40u||
       !rd<uint32_t>(c,unit+0x324u)||
       rd<uint32_t>(c,c.r[13]+8u)!=0u)return;
    if(!msd_retained_class(c,rd<uint32_t>(c,unit+0x128u)))return;
    msd_retained_count(c,rd<uint32_t>(c,unit+0x128u));
    wr<uint32_t>(c,c.r[13]+8u,50u);
}
// Recovered CLZSS::Decode algorithm, verified against the original function.
// Keeping the dictionary loop in C++ avoids a block dispatch for every byte.
static void native_lzss(Context& c){
    uint32_t src=c.r[0],dst=c.r[1],remaining=c.r[2];
    if(!src||!dst||!remaining){c.r[0]=0;c.pc=c.r[14];return;}
    uint8_t dictionary[4096]={};uint32_t write=0xfee,flags=0;
    while(remaining&&!c.error){
        flags>>=1;if(!(flags&0x100))flags=rd<uint8_t>(c,src++)|0xff00;
        uint32_t lo=rd<uint8_t>(c,src++);
        if(flags&1){
            wr<uint8_t>(c,dst++,lo);remaining--;
            dictionary[write]=uint8_t(lo);write=(write+1)&4095;
        }else{
            uint32_t hi=rd<uint8_t>(c,src++),pos=lo|((hi&0xf0)<<4),length=(hi&15)+3;
            for(uint32_t j=0;j<length&&remaining;j++){
                uint8_t b=dictionary[(pos+j)&4095];wr<uint8_t>(c,dst++,b);remaining--;
                dictionary[write]=b;write=(write+1)&4095;
            }
        }
    }
    c.r[0]=c.error?0:1;c.pc=c.r[14];
}
static void native_decrypt(Context& c){
    uint32_t dst=c.r[0],offset=c.r[1]&63,n=c.r[2],last=0;
    uint8_t key[64];for(uint32_t j=0;j<64;j++)key[j]=rd<uint8_t>(c,0x102384b5u+j);
    for(uint32_t j=0;j<n&&!c.error;j++){
        last=rd<uint8_t>(c,dst+j);wr<uint8_t>(c,dst+j,last^key[(offset+j)&63]);
    }
    c.r[0]=last;c.pc=c.r[14];
}
// The original wrapper has already validated palette format, dimensions and
// allocation here. Expand identical pixels in one native loop, then resume
// its original upload/free path. No texture size, filtering or color changes.
template<uint32_t Bytes> static void expand_palette(const uint8_t* colors,const uint8_t* indices,
        uint8_t* out,uint32_t width,uint32_t height,uint32_t depth,uint64_t stride){
    for(uint32_t y=0;y<height;y++){
        const uint8_t* row=indices+y*stride;
        for(uint32_t x=0;x<width;x++){
            uint32_t index=depth==8u?row[x]:((row[x/2u]>>(x&1u?0u:4u))&15u);
            std::memcpy(out,colors+index*Bytes,Bytes);out+=Bytes;
        }
    }
}
static void native_palette(Context& c){
    uint32_t width=c.r[6],height=c.r[9],bytes=c.r[4],depth=c.r[10];
    uint32_t src=rd<uint32_t>(c,c.r[13]+0x28u),dst=c.r[8];
    uint64_t palette=uint64_t(bytes)<<depth;
    uint64_t stride=(uint64_t(width)*depth+7u)/8u;
    uint64_t input=palette+stride*height,output=uint64_t(width)*height*bytes;
    if(src<0x10000000u||dst<0x10000000u||uint64_t(src)+input>0x20000000ull||
       uint64_t(dst)+output>0x20000000ull||bytes<2u||bytes>4u||(depth!=4u&&depth!=8u)){
        c.error=3;c.error_address=src;return;
    }
    const uint8_t* colors=c.memory+src-0x10000000u;
    const uint8_t* indices=colors+palette;
    uint8_t* out=c.memory+dst-0x10000000u;
    if(bytes==2u)expand_palette<2>(colors,indices,out,width,height,depth,stride);
    else if(bytes==3u)expand_palette<3>(colors,indices,out,width,height,depth,stride);
    else expand_palette<4>(colors,indices,out,width,height,depth,stride);
    c.pc=0x1015fd63u;
}
extern "C" __declspec(dllexport) uint32_t msd_run(Context* cp,uint32_t budget){
    Context& c=*cp;
    auto host=msd_imports(cp);
    for(uint32_t i=0;i<budget;i++){
        uint32_t a=c.pc&~1u;
        if(a==0x1fff0000)return 0;
        if(a>=0x1f000000&&a<0x1f010000){
            if(msd_native_import(c,a,host)){c.blocks++;if(c.error)return c.error;continue;}
            return 1;
        }
        if(auto thunk=msd_decoder_thunk(host,c.pc)){c.pc=thunk;continue;}
        if(c.pc==0x1015fc23u){native_palette(c);c.blocks++;if(c.error)return c.error;continue;}
        if(c.pc==0x101c39fdu){
            uint32_t dst=c.r[0];uint64_t bytes=uint64_t(c.r[5])*4u;
            if(dst<0x10000000u||uint64_t(dst)+bytes>0x20000000ull){c.error=3;c.error_address=dst;return 3;}
            std::memset(c.memory+dst-0x10000000u,0,bytes);c.pc=0x101c3a09u;c.blocks++;continue;
        }
        if(c.pc==0x101c3ad9u&&c.r[1]==1u){
            uint32_t desc=c.r[0],dst=rd<uint32_t>(c,desc),src=c.r[2];
            uint64_t bytes=uint64_t(rd<uint32_t>(c,desc+4u))*rd<uint32_t>(c,desc+8u)*4u;
            if(src<0x10000000u||dst<0x10000000u||uint64_t(src)+bytes>0x20000000ull||uint64_t(dst)+bytes>0x20000000ull){c.error=3;c.error_address=src;return 3;}
            std::memcpy(c.memory+dst-0x10000000u,c.memory+src-0x10000000u,bytes);c.r[0]=1;c.pc=c.r[14];c.blocks++;continue;
        }
        if(c.pc==0x1013faa1){native_lzss(c);c.blocks++;if(c.error)return c.error;continue;}
        if(c.pc==0x10146645&&int32_t(c.r[1])>=0&&int32_t(c.r[2])>0){native_decrypt(c);c.blocks++;if(c.error)return c.error;continue;}
        auto f=find_block(c.pc);
        if(!f){missing(c,c.pc);return 2;}
        f(c);c.blocks++;
        if(c.error)return c.error;
    }
    return 4;
}
extern "C" __declspec(dllexport) uint32_t msd_context_size(){return sizeof(Context);}
extern "C" __declspec(dllexport) uint32_t msd_runtime_kind(){return 0x414f5431;}
