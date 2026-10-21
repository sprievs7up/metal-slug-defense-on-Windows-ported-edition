#pragma once
#include "aot_runtime.h"
struct NativeImports;
NativeImports* msd_imports(Context*);
bool msd_native_import(Context&,uint32_t,NativeImports*);
// 嵌套调用（钩子内的同步客体调用）遇到核心未处理、但登记为可回调的宿主导入（堆分配）时，经宿主回调执行并返回调用方。
bool msd_nested_host_import(Context&,uint32_t,NativeImports*);
uint32_t msd_decoder_thunk(NativeImports*,uint32_t);
