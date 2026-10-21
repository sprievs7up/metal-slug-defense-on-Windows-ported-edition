"""Host ABI facade for statically compiled x64 game blocks. No ARM engine.

Register identifiers preserve the existing bridge API; instruction execution
occurs exclusively in the build-time generated Windows DLL.
"""
import ctypes as C,time,json,hashlib
from pathlib import Path
UC_ARCH_ARM=1;UC_MODE_ARM=0;UC_PROT_ALL=7;UC_CPU_ARM_CORTEX_A15=17
UC_HOOK_INTR=1;UC_HOOK_MEM_INVALID=2
UC_ARM_REG_R0=66;UC_ARM_REG_R1=67;UC_ARM_REG_R2=68;UC_ARM_REG_R3=69
UC_ARM_REG_SP=12;UC_ARM_REG_LR=10;UC_ARM_REG_PC=11;UC_ARM_REG_CPSR=3
UC_ARM_REG_C1_C0_2=111;UC_ARM_REG_FPEXC=4;UC_ARM_REG_FPSCR=6
class Context(C.Structure):
    _fields_=[('r',C.c_uint32*16),('d',C.c_uint64*32),('n',C.c_uint32),('z',C.c_uint32),('c',C.c_uint32),('v',C.c_uint32),('fpscr',C.c_uint32),('pc',C.c_uint32),('error',C.c_uint32),('error_address',C.c_uint32),('memory',C.c_void_p),('blocks',C.c_uint64)]
class Uc:
    nested_error=None   # host exception from nested_import; class default also covers subclasses with their own __init__
    def __init__(self,*args):
        self.ctx=Context();self.callbacks={}
        root=Path(__file__).resolve().parent
        config_path=root/'core_runtime.json'
        config=json.loads(config_path.read_text(encoding='utf-8')) if config_path.is_file() else {'library':'msd_aot.dll'}
        name=config['library']
        if Path(name).name!=name or not name.lower().endswith('.dll'):
            raise RuntimeError('Invalid native core filename')
        self.library_path=root/'build'/name
        if config.get('sha256') and hashlib.sha256(self.library_path.read_bytes()).hexdigest()!=config['sha256']:
            raise RuntimeError('Native core differs from the installed release')
        self.lib=C.CDLL(str(self.library_path))
        self.lib.msd_context_size.restype=C.c_uint32
        if self.lib.msd_context_size()!=C.sizeof(Context):raise RuntimeError('AOT context ABI mismatch')
        self.lib.msd_runtime_kind.restype=C.c_uint32
        if self.lib.msd_runtime_kind()!=0x414f5431:raise RuntimeError('Unexpected AOT backend')
        self.lib.msd_run.argtypes=[C.POINTER(Context),C.c_uint32];self.lib.msd_run.restype=C.c_uint32
    def ctl_set_cpu_model(self,*args):pass
    def mem_map_ptr(self,base,size,perms,address):
        if (base,size)!=(0x10000000,0x10000000):raise ValueError('Unexpected memory layout')
        self.ctx.memory=address
    def hook_add(self,kind,callback):self.callbacks[kind]=callback;return kind
    def reg_read(self,r):
        c=self.ctx
        if 66<=r<=78:return c.r[r-66]
        if r in (12,10):return c.r[13 if r==12 else 14]
        if r==11:return c.pc&~1
        if r==3:return (c.n<<31)|(c.z<<30)|(c.c<<29)|(c.v<<28)|(32 if c.pc&1 else 0)|16
        if r==6:return c.fpscr
        if 14<=r<=45:return c.d[r-14]
        if 79<=r<=110:return (c.d[(r-79)//2]>>(((r-79)%2)*32))&0xffffffff
        if r in (4,111):return 0
        raise ValueError('Unknown register '+str(r))
    def reg_write(self,r,v):
        c=self.ctx;v=int(v)
        if 66<=r<=78:c.r[r-66]=v;return
        if r in (12,10):c.r[13 if r==12 else 14]=v;return
        if r==11:c.pc=v;return
        if r==3:
            c.n=(v>>31)&1;c.z=(v>>30)&1;c.c=(v>>29)&1;c.v=(v>>28)&1;c.pc=(c.pc&~1)|bool(v&32);return
        if r==6:c.fpscr=v;return
        if 14<=r<=45:c.d[r-14]=v;return
        if 79<=r<=110:
            n=r-79;s=(n%2)*32;c.d[n//2]=(c.d[n//2]&~(0xffffffff<<s))|((v&0xffffffff)<<s);return
        if r in (4,111):return
        raise ValueError('Unknown register '+str(r))
    def emu_start(self,address,stop,timeout=30000000,count=0):
        c=self.ctx;c.pc=address;c.error=0;deadline=time.monotonic()+timeout/1e6 if timeout else None
        began_blocks=c.blocks
        while True:
            budget=min(1000000,max(1,count-(c.blocks-began_blocks))) if count else 1000000
            result=self.lib.msd_run(C.byref(c),budget)
            if self.nested_error is not None:error,self.nested_error=self.nested_error,None;raise error
            if result==0:return
            if result==1:
                target=c.pc&~1;c.pc=target+4
                self.callbacks[UC_HOOK_INTR](self,2,None)
                c.pc=c.r[14]
            elif result==4:
                if (deadline is not None and time.monotonic()>deadline) or (count and c.blocks-began_blocks>=count):return
            else:
                raise RuntimeError(f'AOT stopped: reason={result} address=0x{c.error_address:08x} pc=0x{c.pc:08x} lr=0x{c.r[14]:08x}; no fallback engine')
    def nested_import(self,address):
        # Host import reached inside a core-side nested guest call (msd_bind_nested_host): handled exactly as
        # emu_start handles result 1 (pc = import + 4 for the thunk lookup); the core then returns to lr.
        # A host exception fails the import (reason 5) and is raised by the outer emu_start.
        try:
            self.ctx.pc=address+4;self.callbacks[UC_HOOK_INTR](self,2,None);return 1
        except BaseException as error:
            self.nested_error=error;return 0
