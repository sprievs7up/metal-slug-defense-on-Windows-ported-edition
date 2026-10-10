// Native host imports retain the game's soft-float ABI and pointer checks.
#include "native_imports.h"
#include "netplay.h"
#include <memory>
#include <unordered_map>
struct Import {uint32_t kind=0;void* function=nullptr;};
struct NativeImports {
    Import entries[8192];uint64_t calls[128]={};
    uint32_t array_buffer=0,element_buffer=0;
    uint32_t decoder_plus=0,decoder_sync=0;
};
static std::unordered_map<Context*,std::unique_ptr<NativeImports>> bindings;
NativeImports* msd_imports(Context* c){auto i=bindings.find(c);return i==bindings.end()?nullptr:i->second.get();}
extern "C" __declspec(dllexport) uint32_t msd_bind_import(Context* c,uint32_t address,uint32_t kind,void* function){
    if(address<0x1f000000u||address>=0x1f010000u||(address&7u)||kind>=128u)return 0;
    auto& p=bindings[c];if(!p)p=std::make_unique<NativeImports>();
    p->entries[(address-0x1f000000u)/8u]={kind,function};return 1;
}
extern "C" __declspec(dllexport) void msd_release_imports(Context* c){bindings.erase(c);}
extern "C" __declspec(dllexport) void msd_bind_decoder(Context* c,uint32_t plus,uint32_t sync){
    auto& p=bindings[c];if(!p)p=std::make_unique<NativeImports>();
    p->decoder_plus=plus;p->decoder_sync=sync;
}
uint32_t msd_decoder_thunk(NativeImports* p,uint32_t pc){
    if(!p)return 0;
    return pc==0x1013e05du?p->decoder_plus:pc==0x1013dfcfu?p->decoder_sync:0;
}
extern "C" __declspec(dllexport) uint64_t msd_import_count(Context* c,uint32_t kind){
    auto p=msd_imports(c);return p&&kind<128u?p->calls[kind]:0;
}
extern "C" __declspec(dllexport) uint32_t msd_bound_buffer(Context* c,uint32_t target){
    auto p=msd_imports(c);return !p?0u:target==0x8892u?p->array_buffer:p->element_buffer;
}
extern "C" __declspec(dllexport) void msd_set_bound_buffer(Context* c,uint32_t target,uint32_t buffer){
    auto p=msd_imports(c);if(p){if(target==0x8892u)p->array_buffer=buffer;if(target==0x8893u)p->element_buffer=buffer;}
}
static void* pointer(Context& c,uint32_t a,uint64_t size){
    if(!a&&!size)return nullptr;
    if(a<0x10000000u||uint64_t(a)+size>0x20000000ull){c.error=3;c.error_address=a;return nullptr;}
    return c.memory+a-0x10000000u;
}
static uint32_t arg(Context& c,uint32_t n){return n<4u?c.r[n]:rd<uint32_t>(c,c.r[13]+4u*(n-4u));}
static float real(uint32_t u){float f;std::memcpy(&f,&u,4);return f;}
static uint32_t bits(float f){uint32_t u;std::memcpy(&u,&f,4);return u;}
static double dbl(uint32_t lo,uint32_t hi){uint64_t u=uint64_t(lo)|(uint64_t(hi)<<32);double d;std::memcpy(&d,&u,8);return d;}
static void return_double(Context& c,double d){uint64_t u;std::memcpy(&u,&d,8);c.r[0]=uint32_t(u);c.r[1]=uint32_t(u>>32);}
bool msd_native_import(Context& c,uint32_t address,NativeImports* host){
    if(!host)return false;
    auto& entry=host->entries[(address-0x1f000000u)/8u];
    auto kind=entry.kind;if(!kind)return false;
    host->calls[kind]++;
    uint32_t a=c.r[0],b=c.r[1],d=c.r[2],e=c.r[3];void* fn=entry.function;
    switch(kind){
        // 联机与回放（netplay.cpp 位 1）改用与 CPU 无关的软件实现；本地游戏保持原绑定。
        case 1:return_double(c,(msd_netplay_flags&NETPLAY_DETERMINISTIC_MATH)?msd_det_sin(dbl(a,b)):std::sin(dbl(a,b)));break;
        case 2:return_double(c,(msd_netplay_flags&NETPLAY_DETERMINISTIC_MATH)?msd_det_cos(dbl(a,b)):std::cos(dbl(a,b)));break;
        case 3:c.r[0]=bits(float((msd_netplay_flags&NETPLAY_DETERMINISTIC_MATH)?msd_det_sin(double(real(a))):std::sin(double(real(a)))));break;
        case 4:c.r[0]=bits(float((msd_netplay_flags&NETPLAY_DETERMINISTIC_MATH)?msd_det_cos(double(real(a))):std::cos(double(real(a)))));break;
        case 5:{auto dst=pointer(c,a,d);if(!c.error)std::memset(dst,b,d);c.r[0]=a;break;}
        case 6:case 7:{auto dst=pointer(c,a,d),src=pointer(c,b,d);if(!c.error)std::memmove(dst,src,d);c.r[0]=a;break;}
        case 8:c.r[0]=0;break; // Existing mutex/attribute host contracts.
        case 9:c.r[0]=reinterpret_cast<uint32_t(*)()>(fn)();break; // Host process clock, including synchronous LAB sound requests.
        case 32:case 33:case 34:case 35:case 36:case 37:case 38:
            reinterpret_cast<void(*)(uint32_t)>(fn)(a);break;
        case 39:case 40:case 41:
            reinterpret_cast<void(*)(uint32_t,uint32_t)>(fn)(a,b);break;
        case 42: // Buffer state remains native, including element-index offsets.
            if(a==0x8892u)host->array_buffer=b;if(a==0x8893u)host->element_buffer=b;
            reinterpret_cast<void(*)(uint32_t,uint32_t)>(fn)(a,b);break;
        case 43:reinterpret_cast<void(*)(uint8_t)>(fn)(uint8_t(a));break;
        // 联机重模拟帧（netplay.cpp 位 0）只跳过绘制调用；状态、纹理与缓冲调用照常，GL 状态与客体缓存保持一致。
        case 44:if(!(msd_netplay_flags&NETPLAY_SUPPRESS_DRAW))reinterpret_cast<void(*)(uint32_t,int32_t,int32_t)>(fn)(a,int32_t(b),int32_t(d));break;
        case 45:{void* p=host->element_buffer?reinterpret_cast<void*>(uintptr_t(e)):e?pointer(c,e,1):nullptr;
            if(!c.error&&!(msd_netplay_flags&NETPLAY_SUPPRESS_DRAW))reinterpret_cast<void(*)(uint32_t,int32_t,uint32_t,const void*)>(fn)(a,int32_t(b),d,p);break;}
        case 46:{auto offset=arg(c,5);void* p=host->array_buffer?reinterpret_cast<void*>(uintptr_t(offset)):offset?pointer(c,offset,1):nullptr;
            if(!c.error)reinterpret_cast<void(*)(uint32_t,int32_t,uint32_t,uint8_t,int32_t,const void*)>(fn)(a,int32_t(b),d,uint8_t(e),int32_t(arg(c,4)),p);break;}
        case 47:case 48:{auto p=pointer(c,d,uint64_t(b)*(kind==47?16u:12u));
            if(!c.error)reinterpret_cast<void(*)(int32_t,int32_t,const float*)>(fn)(int32_t(a),int32_t(b),static_cast<const float*>(p));break;}
        case 49:{auto p=pointer(c,e,uint64_t(b)*64u);
            if(!c.error)reinterpret_cast<void(*)(int32_t,int32_t,uint8_t,const float*)>(fn)(int32_t(a),int32_t(b),uint8_t(d),static_cast<const float*>(p));break;}
        case 50:reinterpret_cast<void(*)(int32_t,int32_t)>(fn)(int32_t(a),int32_t(b));break;
        case 51:reinterpret_cast<void(*)(int32_t,float)>(fn)(int32_t(a),real(b));break;
        case 52:reinterpret_cast<void(*)(int32_t,float,float,float,float)>(fn)(int32_t(a),real(b),real(d),real(e),real(arg(c,4)));break;
        case 53:reinterpret_cast<void(*)(float,float,float,float)>(fn)(real(a),real(b),real(d),real(e));break;
        case 54:reinterpret_cast<void(*)(uint32_t,uint32_t,float)>(fn)(a,b,real(d));break;
        case 55:{auto p=pointer(c,b,1);if(!c.error)c.r[0]=uint32_t(reinterpret_cast<int32_t(*)(uint32_t,const char*)>(fn)(a,static_cast<const char*>(p)));break;}
        default:return false;
    }
    if(kind>=32u&&kind!=55u)c.r[0]=0;
    c.pc=c.r[14];return true;
}
