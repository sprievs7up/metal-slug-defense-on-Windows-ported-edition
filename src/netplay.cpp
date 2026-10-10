// 联机回滚（Rollback）的核心支持，见 docs/netcode/N1_N2_ROLLBACK_2026-10-10.md：
// 1. 渲染抑制（msd_netplay_flags 位 0）：重模拟帧跳过绘制调用，其余 GL 状态与资源调用照常执行，
//    使 GL 实际状态与客体内的绘制缓存保持一致（见 native_imports.cpp 第 44、45 类）。
// 2. 确定性数学（位 1）：游戏的 sin/cos/sinf/cosf 原绑定 MinGW 数学库（x87 fsin/fcos），不同厂商 CPU 可能有末位差异；
//    联机与回放改用下列软件实现（SSE2 双精度、-ffp-contract=off，结果与 CPU 型号无关）。本地游戏不受影响。
// 3. 核心静态状态：客体内存之外、参与战斗或 AI 决策的静态变量随快照保存、恢复（StateIO，见 netplay.h）。
// 4. 快照页复制（版本 2）：逐帧撤销记录的页复制在此完成，避免宿主逐段循环。
//
// 软件 sin/cos 移植自 musl libc（MIT）中的 fdlibm 实现：__sin、__cos 与 __rem_pio2 的中小参数路径。
// ====================================================
// Copyright (C) 1993 by Sun Microsystems, Inc. All rights reserved.
//
// Developed at SunPro, a Sun Microsystems, Inc. business.
// Permission to use, copy, modify, and distribute this
// software is freely granted, provided that this notice
// is preserved.
// ====================================================
// 与 musl 的差异：|x| ≥ 2^20·π/2 时不使用 __rem_pio2_large，先以 fmod(x, 2π)（IEEE 精确运算）缩小参数；
// 这类参数在游戏中不出现，结果仍与 CPU 无关。
#include "netplay.h"
#include <cmath>
#include <vector>
uint32_t msd_netplay_flags=0;

namespace {
inline uint64_t bits_of(double x){uint64_t u;std::memcpy(&u,&x,8);return u;}
const double S1=-1.66666666666666324348e-01,S2=8.33333333332248946124e-03,S3=-1.98412698298579493134e-04,
             S4=2.75573137070700676789e-06,S5=-2.50507602534068634195e-08,S6=1.58969099521155010221e-10;
const double C1=4.16666666666666019037e-02,C2=-1.38888888888741095749e-03,C3=2.48015872894767294178e-05,
             C4=-2.75573143513906633035e-07,C5=2.08757232129817482790e-09,C6=-1.13596475577881948265e-11;
double k_sin(double x,double y,int iy){
    double z=x*x,w=z*z;
    double r=S2+z*(S3+z*S4)+z*w*(S5+z*S6);
    double v=z*x;
    if(iy==0)return x+v*(S1+z*r);
    return x-((z*(0.5*y-v*r)-y)-v*S1);
}
double k_cos(double x,double y){
    double z=x*x,w=z*z;
    double r=z*(C1+z*(C2+z*C3))+w*w*(C4+z*(C5+z*C6));
    double hz=0.5*z;
    w=1.0-hz;
    return w+(((1.0-w)-hz)+(z*r-x*y));
}
const double toint=1.5/2.220446049250313080847e-16,pio4=0.78539816339744827900,invpio2=6.36619772367581382433e-01,
             pio2_1=1.57079632673412561417e+00,pio2_1t=6.07710050650619224932e-11,
             pio2_2=6.07710050630396597660e-11,pio2_2t=2.02226624879595063154e-21,
             pio2_3=2.02226624871116645580e-21,pio2_3t=8.47842766036889956997e-32,
             two_pi=6.28318530717958647692;
int rem_pio2_medium(double x,uint32_t ix,double* y){
    double fn=x*invpio2+toint-toint;
    int n=int(int32_t(fn));
    double r=x-fn*pio2_1,w=fn*pio2_1t;
    if(r-w< -pio4){n--;fn--;r=x-fn*pio2_1;w=fn*pio2_1t;}
    else if(r-w>pio4){n++;fn++;r=x-fn*pio2_1;w=fn*pio2_1t;}
    y[0]=r-w;
    int ey=int(bits_of(y[0])>>52&0x7ff),ex=int(ix>>20);
    if(ex-ey>16){
        double t=r;w=fn*pio2_2;r=t-w;w=fn*pio2_2t-((t-r)-w);y[0]=r-w;
        ey=int(bits_of(y[0])>>52&0x7ff);
        if(ex-ey>49){t=r;w=fn*pio2_3;r=t-w;w=fn*pio2_3t-((t-r)-w);y[0]=r-w;}
    }
    y[1]=(r-y[0])-w;
    return n;
}
int rem_pio2(double x,double* y){
    uint64_t u=bits_of(x);
    bool sign=u>>63;
    uint32_t ix=uint32_t(u>>32)&0x7fffffffu;
    if(ix<=0x400f6a7au){                                   // |x| ~<= 5π/4
        if((ix&0xfffffu)==0x921fbu)return rem_pio2_medium(x,ix,y);
        if(ix<=0x4002d97cu){                               // |x| ~<= 3π/4
            if(!sign){double z=x-pio2_1;y[0]=z-pio2_1t;y[1]=(z-y[0])-pio2_1t;return 1;}
            double z=x+pio2_1;y[0]=z+pio2_1t;y[1]=(z-y[0])+pio2_1t;return -1;
        }
        if(!sign){double z=x-2*pio2_1;y[0]=z-2*pio2_1t;y[1]=(z-y[0])-2*pio2_1t;return 2;}
        double z=x+2*pio2_1;y[0]=z+2*pio2_1t;y[1]=(z-y[0])+2*pio2_1t;return -2;
    }
    if(ix<=0x401c463bu){                                   // |x| ~<= 9π/4
        if(ix<=0x4015fdbcu){                               // |x| ~<= 7π/4
            if(ix==0x4012d97cu)return rem_pio2_medium(x,ix,y);
            if(!sign){double z=x-3*pio2_1;y[0]=z-3*pio2_1t;y[1]=(z-y[0])-3*pio2_1t;return 3;}
            double z=x+3*pio2_1;y[0]=z+3*pio2_1t;y[1]=(z-y[0])+3*pio2_1t;return -3;
        }
        if(ix==0x401921fbu)return rem_pio2_medium(x,ix,y);
        if(!sign){double z=x-4*pio2_1;y[0]=z-4*pio2_1t;y[1]=(z-y[0])-4*pio2_1t;return 4;}
        double z=x+4*pio2_1;y[0]=z+4*pio2_1t;y[1]=(z-y[0])+4*pio2_1t;return -4;
    }
    if(ix<0x413921fbu)return rem_pio2_medium(x,ix,y);     // |x| ~< 2^20·π/2
    double r=std::fmod(x,two_pi);                          // 见文件首说明（与 musl 的唯一差异）
    return rem_pio2_medium(r,uint32_t(bits_of(r)>>32)&0x7fffffffu,y);
}
}

double msd_det_sin(double x){
    uint32_t ix=uint32_t(bits_of(x)>>32)&0x7fffffffu;
    if(ix<=0x3fe921fbu){
        if(ix<0x3e500000u)return x;
        return k_sin(x,0.0,0);
    }
    if(ix>=0x7ff00000u)return x-x;
    double y[2];
    switch(unsigned(rem_pio2(x,y))&3u){
        case 0:return k_sin(y[0],y[1],1);
        case 1:return k_cos(y[0],y[1]);
        case 2:return -k_sin(y[0],y[1],1);
        default:return -k_cos(y[0],y[1]);
    }
}
double msd_det_cos(double x){
    uint32_t ix=uint32_t(bits_of(x)>>32)&0x7fffffffu;
    if(ix<=0x3fe921fbu){
        if(ix<0x3e46a09eu)return 1.0;
        return k_cos(x,0.0);
    }
    if(ix>=0x7ff00000u)return x-x;
    double y[2];
    switch(unsigned(rem_pio2(x,y))&3u){
        case 0:return k_cos(y[0],y[1]);
        case 1:return -k_sin(y[0],y[1],1);
        case 2:return -k_cos(y[0],y[1]);
        default:return k_sin(y[0],y[1],1);
    }
}

static void state_io(StateIO& io){msd_lab_netplay_state(io);msd_flame_netplay_state(io);}
extern "C" __declspec(dllexport) uint32_t msd_netplay_version(){return 2u;}   // 2：快照页复制
extern "C" __declspec(dllexport) void msd_netplay_set_flags(uint32_t flags){msd_netplay_flags=flags;}
extern "C" __declspec(dllexport) uint32_t msd_netplay_get_flags(){return msd_netplay_flags;}
extern "C" __declspec(dllexport) uint32_t msd_netplay_state_size(){StateIO io;state_io(io);return uint32_t(io.size);}
extern "C" __declspec(dllexport) uint32_t msd_netplay_state_save(uint8_t* out,uint32_t capacity){
    StateIO io;state_io(io);
    if(io.size>capacity)return 0u;
    StateIO w;w.out=out;state_io(w);return uint32_t(w.size);
}
extern "C" __declspec(dllexport) uint32_t msd_netplay_state_load(const uint8_t* in,uint32_t size){
    StateIO io;state_io(io);
    if(io.size!=size)return 0u;
    StateIO r;r.in=in;state_io(r);return 1u;
}
// 每场联机或回放对战开始前：静态状态清零（等同进程启动时的初值），AI 随机数由比赛种子决定。
extern "C" __declspec(dllexport) void msd_netplay_reset(uint32_t seed){
    StateIO io;state_io(io);
    std::vector<uint8_t> zero(io.size,0u);
    StateIO r;r.in=zero.data();state_io(r);
    msd_lab_netplay_defaults(seed);
}
// 4. 快照页复制（netplay_state.GuestJournal）：pages 为 GetWriteWatch 返回的页地址（宿主地址，4 KiB 对齐），undo 依次存放各页内容。
//    提交：undo ← 影子副本（帧前内容），影子副本 ← 客体内存；恢复：客体内存与影子副本 ← undo；撤销未提交写入：客体内存 ← 影子副本。
constexpr size_t SNAP_PAGE=4096;
extern "C" __declspec(dllexport) uint32_t msd_snap_commit(uint8_t* guest,uint8_t* shadow,const uint64_t* pages,uint32_t count,uint8_t* undo){
    for(uint32_t i=0;i<count;++i){
        size_t offset=size_t(pages[i]-uint64_t(reinterpret_cast<uintptr_t>(guest)));
        std::memcpy(undo+size_t(i)*SNAP_PAGE,shadow+offset,SNAP_PAGE);
        std::memcpy(shadow+offset,guest+offset,SNAP_PAGE);
    }
    return count;
}
extern "C" __declspec(dllexport) uint32_t msd_snap_restore(uint8_t* guest,uint8_t* shadow,const uint64_t* pages,uint32_t count,const uint8_t* undo){
    for(uint32_t i=0;i<count;++i){
        size_t offset=size_t(pages[i]-uint64_t(reinterpret_cast<uintptr_t>(guest)));
        std::memcpy(guest+offset,undo+size_t(i)*SNAP_PAGE,SNAP_PAGE);
        std::memcpy(shadow+offset,undo+size_t(i)*SNAP_PAGE,SNAP_PAGE);
    }
    return count;
}
extern "C" __declspec(dllexport) uint32_t msd_snap_copy(uint8_t* to,const uint8_t* from,uint8_t* guest,const uint64_t* pages,uint32_t count){
    for(uint32_t i=0;i<count;++i){
        size_t offset=size_t(pages[i]-uint64_t(reinterpret_cast<uintptr_t>(guest)));
        std::memcpy(to+offset,from+offset,SNAP_PAGE);
    }
    return count;
}
extern "C" __declspec(dllexport) double msd_netplay_sin(double x){return msd_det_sin(x);}
extern "C" __declspec(dllexport) double msd_netplay_cos(double x){return msd_det_cos(x);}
