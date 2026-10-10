#pragma once
// 联机回滚（docs/netcode/N1_N2_ROLLBACK_2026-10-10.md）：核心中客体内存之外的静态状态，以 StateIO 统一保存、恢复与计量。
#include <cstdint>
#include <cstring>
#include <cstddef>
struct StateIO{
    uint8_t* out=nullptr;const uint8_t* in=nullptr;size_t size=0;
    template<class T> void field(T& v){
        if(out)std::memcpy(out+size,&v,sizeof v);
        if(in)std::memcpy(&v,in+size,sizeof v);
        size+=sizeof v;
    }
};
void msd_lab_netplay_state(StateIO& io);          // lab_hooks.cpp：AI 段位、单位来源、相持判定、LAB 音效队列、底栏触点
void msd_lab_netplay_defaults(uint32_t seed);     // 清零后需要非零初值的字段（AI 随机数、单位来源序号、触点片段）
void msd_flame_netplay_state(StateIO& io);        // community_content.cpp：KT-21 喷火单次击退记录
// 位 0：渲染抑制（重模拟帧跳过 glDrawArrays/glDrawElements）；位 1：确定性数学（sin/cos/sinf/cosf 软件实现）。
extern uint32_t msd_netplay_flags;
constexpr uint32_t NETPLAY_SUPPRESS_DRAW=1u,NETPLAY_DETERMINISTIC_MATH=2u;
double msd_det_sin(double x);
double msd_det_cos(double x);
