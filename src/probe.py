"""Windows x64 static-recompilation host. Never accesses the live AVD.

Experimental implementation: unresolved host calls stop execution and are logged.
ELF bytes supply data/relocations. Game execution uses precompiled x64 blocks.
"""
from pathlib import Path
import bisect, sys, io, json, struct, zipfile, tarfile, ctypes, math, time, os, re, collections
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='backslashreplace')
if hasattr(sys.stderr,'reconfigure'):sys.stderr.reconfigure(encoding='utf-8',errors='backslashreplace')
ROOT = Path(__file__).resolve().parent
RUNTIME_PACKAGES = Path(sys.executable).resolve().parent / 'packages'
sys.path.insert(0, str(RUNTIME_PACKAGES if RUNTIME_PACKAGES.is_dir() else ROOT.parent / 'windows_probe/deps'))
from elftools.elf.elffile import ELFFile
from static_cpu import *


DATA_ROOT = ROOT/'game_data'
APK = DATA_ROOT/'original.apk' if (DATA_ROOT/'original.apk').is_file() else ROOT.parent / 'zero_progress/downloads/MSD_No_Progress_All_Units_Mod_Support_By_lXBloodShootXl.apk'
RESOURCE_ROOT = DATA_ROOT/'assets' if (DATA_ROOT/'assets').is_dir() else ROOT.parent/'zero_progress/game_assets'
PKG = 'com.snkplaymore.android003'
REGS = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3]
BASE, SIZE = 0x10000000, 0x10000000
STOP, THUNKS, STACK = 0x1fff0000, 0x1f000000, 0x1efe0000
f32 = lambda n: struct.unpack('<f', struct.pack('<I', n & 0xffffffff))[0]
u32f = lambda f: struct.unpack('<I', struct.pack('<f', f))[0]
i32 = lambda n: ctypes.c_int32(n).value

class ProbeCancelled(Exception):
    """A local host requested that the current experiment stop."""

def guest_ram(size):
    """客体内存。优先以 MEM_WRITE_WATCH 分配（按需清零页，与普通缓冲同为全零初值），
    联机回滚快照（netplay_state.py）以 GetWriteWatch 取得逐帧改动页；不可用时退回普通缓冲。
    返回 (地址或缓冲对象, 是否启用写入监视)。"""
    if os.environ.get('MSD_GUEST_WRITE_WATCH','1')=='0':return ctypes.create_string_buffer(size),False
    try:
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        allocate=kernel.VirtualAlloc
        allocate.restype=ctypes.c_void_p
        allocate.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_uint32]
        address=allocate(None,size,0x1000|0x2000|0x200000,0x04)   # MEM_COMMIT|MEM_RESERVE|MEM_WRITE_WATCH, PAGE_READWRITE
        if address:return address,True
    except (AttributeError,OSError):pass
    return ctypes.create_string_buffer(size),False

class Probe:
    # 联机与回放（netplay_session.NetplayMode）：新分配的块清零（calloc 语义），使对象内的填充字节与复用块残留不随进程而异；
    # virtual_clock 为时钟函数的替代（时间由比赛种子与模拟帧号推导），None 时使用真实时钟。
    zero_fill = False
    virtual_clock = None
    heap_version = 0          # 每次分配或释放递增（联机回滚快照据此判断分配表是否变化）

    def __init__(self, guest_root=None, log_name='probe.log', window_handle=None,
                 window_size=(960,640), stop_event=None, on_progress=None,
                 audio_mode='silent', audio_capture=None):
        self.guest_root=Path(guest_root or ROOT/'guest').resolve()
        if not self.guest_root.is_relative_to(ROOT):raise ValueError('Save directory must remain inside the prototype folder')
        self.window_handle=window_handle
        self.window_size=window_size
        self.stop_event=stop_event
        self.on_progress=on_progress
        self.audio_mode=audio_mode
        self.audio_capture=audio_capture
        from branding import load as load_branding
        self.branding=load_branding(ROOT)
        from asset_cache import AssetCache
        self.asset_cache=AssetCache(RESOURCE_ROOT/PKG)
        self.file_commits={}
        self.logfile = open(ROOT / log_name, 'w', encoding='utf-8', buffering=1)
        self.zip = zipfile.ZipFile(APK)
        library = self.zip.read('lib/armeabi-v7a/libAppMain.so')
        if __import__('hashlib').sha256(library).hexdigest() != '91f34f3cf1645842bc0c547431f584ddca3374690c7b541b1bdf7ee93a031c7c':
            raise RuntimeError('This APK does not match the statically compiled game library')
        self.elf = ELFFile(io.BytesIO(library))
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A15)
        self.ram, self.write_watch = guest_ram(SIZE)
        self.hostbase = self.ram if self.write_watch else ctypes.addressof(self.ram)
        self.uc.mem_map_ptr(BASE, SIZE, UC_PROT_ALL, self.hostbase)
        self.uc.reg_write(UC_ARM_REG_C1_C0_2, 0xf << 20)
        self.uc.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
        self.heap = 0x12000000
        self.allocations = {}
        self.free_blocks = []
        self.thunks, self.thunk_names, self.objects, self.handles = {}, {}, {}, {}
        self.jni_refs, self.jni_utf_chars = {}, {}
        self.calls = collections.Counter()
        self.symbols = {}
        self.pending = []
        self.phase = 'loading'
        self.frame = 0
        self.errno = self.alloc(4)
        self.saves = self.guest_root / 'data/data' / PKG
        self.saves.mkdir(parents=True, exist_ok=True)
        # Resource overrides are discovered at launch; absent local textures
        # can fall through to the bundled assets without repeated failed opens.
        self.local_asset_names={q.name for q in self.saves.iterdir()}
        initial = self.saves / 'test.dat'
        if not initial.exists():
            verified=ROOT/'guest/data/data'/PKG/'test.dat'
            if verified.exists() and verified!=initial:initial.write_bytes(verified.read_bytes())
            elif (DATA_ROOT/'seed.dat').is_file():initial.write_bytes((DATA_ROOT/'seed.dat').read_bytes())
            else:
                with tarfile.open(ROOT.parent / 'zero_progress/validation/msd-zero-progress.tar') as tar:
                    initial.write_bytes(tar.extractfile(PKG + '/test.dat').read())
        if window_handle:
            backup=self.saves/'launch_backups';backup.mkdir(exist_ok=True)
            (backup/(time.strftime('%Y%m%d_%H%M%S')+f'_{os.getpid()}.dat')).write_bytes(initial.read_bytes())
        self.log('HOST_PROCESS',os.getpid(),'SAVE_SHA256_INITIAL',__import__('hashlib').sha256(initial.read_bytes()).hexdigest())
        self.uc.hook_add(UC_HOOK_INTR, self.interrupt)
        self.uc.hook_add(UC_HOOK_MEM_INVALID, self.invalid_memory)
        self.load()
        self.make_jni()
        from native_imports import bind
        bind(self)
        from native_audio import bind as bind_audio
        bind_audio(self)

    def log(self, *values):
        if self.on_progress:self.on_progress(values)
        if values and values[0] in ('JNI_LOOKUP','JAVA_CALL'):
            if not hasattr(self,'seen_logs'):self.seen_logs=set()
            key=repr(values)
            if key in self.seen_logs:return
            self.seen_logs.add(key)
        line = ' '.join(map(str, values))
        if sys.stdout is not None:print(line, flush=True)
        self.logfile.write(line + '\n')

    def host(self, p, size=1):
        if not p:
            return 0
        if not BASE <= p < BASE + SIZE or p + size > BASE + SIZE:
            raise RuntimeError(f'Guest pointer outside RAM: {p:08x}, length {size}')
        return self.hostbase + p - BASE

    def read(self, p, n):
        return ctypes.string_at(self.host(p, n), n)

    def write(self, p, data):
        ctypes.memmove(self.host(p, len(data)), data, len(data))

    def word(self, p):
        return struct.unpack('<I', self.read(p, 4))[0]

    def put(self, p, v):
        self.write(p, struct.pack('<I', v & 0xffffffff))

    def string(self, p):
        if not p: return ''
        return ctypes.string_at(self.host(p)).decode('utf-8', 'replace')

    def alloc(self, n):
        n = (max(int(n), 16)+15)&~15
        for i,(p,size) in enumerate(self.free_blocks):
            if size>=n:
                self.free_blocks.pop(i)
                if size>n:self.free_blocks.insert(i,(p+n,size-n))
                self.allocations[p]=n
                self.heap_version+=1
                if self.zero_fill:ctypes.memset(self.hostbase+p-BASE,0,n)
                return p
        p = self.heap
        self.heap += n
        if self.heap >= 0x1e000000: raise MemoryError('Guest heap exhausted')
        self.allocations[p] = n
        self.heap_version += 1
        if self.zero_fill:ctypes.memset(self.hostbase+p-BASE,0,n)
        return p

    def free(self,p):
        if not p:return
        guard=getattr(self,'decoder_worker_guard',None)
        if guard and p in guard['owned']:
            raise RuntimeError('Decoder worker unexpectedly released a guarded allocation')
        size=self.allocations.pop(p,None)
        if size is None:raise RuntimeError(f'Unknown or duplicate free: {p:08x}')
        self.heap_version+=1
        # free_blocks stays sorted by address with adjacent blocks merged, so the
        # released block only joins its immediate neighbours (same result as a
        # full sort and merge, without rescanning the whole list).
        blocks=self.free_blocks;i=bisect.bisect_left(blocks,(p,0))
        if i<len(blocks) and p+size==blocks[i][0]:size+=blocks.pop(i)[1]
        if i and blocks[i-1][0]+blocks[i-1][1]==p:
            q,n=blocks[i-1];blocks[i-1]=(q,n+size)
        else:blocks.insert(i,(p,size))

    def cstr(self, s):
        data = s.encode() + b'\0'
        p = self.alloc(len(data)); self.write(p, data)
        return p

    def obj(self, value):
        p = self.alloc(16); self.objects[p] = value
        return p

    def managed_obj(self, value):
        """Own a JNI local reference; cached classes/method IDs use obj instead."""
        p = self.obj(value)
        self.jni_refs[p] = {'local': 1, 'global': 0, 'array': 0, 'pin': 0}
        if isinstance(value, dict) and value.get('kind') == 'objects':
            for child in value['items']: self.jni_retain(child, 'array')
        return p

    def jni_retain(self, ref, kind='local'):
        counts = self.jni_refs.get(ref)
        if counts is not None: counts[kind] += 1
        return ref

    def jni_release(self, ref, kind='local'):
        counts = self.jni_refs.get(ref)
        if counts is None: return
        if counts[kind] <= 0: raise RuntimeError(f'JNI reference released twice: {ref:08x} ({kind})')
        counts[kind] -= 1
        if any(counts.values()): return
        del self.jni_refs[ref]
        value = self.objects.pop(ref)
        if isinstance(value, dict):
            if value.get('kind') == 'objects':
                for child in value['items']: self.jni_release(child, 'array')
            elif value.get('kind') == 'primitive': self.free(value['data'])
        self.free(ref)

    def thunk(self, name):
        if name in self.thunks: return self.thunks[name]
        if name == 'qsort':
            p=THUNKS+0x10000; self.thunks[name]=p
            return p
        p = THUNKS + len(self.thunks) * 8
        self.write(p, struct.pack('<II', 0xef000000, 0xe12fff1e))
        self.thunks[name] = p; self.thunk_names[p] = name
        return p

    def arg(self, i):
        return self.uc.reg_read(REGS[i]) if i < 4 else self.word(self.uc.reg_read(UC_ARM_REG_SP) + (i - 4) * 4)

    def args(self, n=16):
        # ARM soft-float ABI: r0-r3, then contiguous 32-bit stack words.
        # Read SP and the stack once instead of crossing the FFI for each word.
        if n <= 0:
            return []
        values = [self.uc.reg_read(reg) for reg in REGS[:n]]
        if n > 4:
            sp = self.uc.reg_read(UC_ARM_REG_SP)
            values.extend(struct.unpack('<' + 'I' * (n - 4), self.read(sp, (n - 4) * 4)))
        return values

    def invalid_memory(self, uc, access, address, size, value, _):
        self.log('INVALID_MEMORY', self.phase, hex(address), size, 'PC', hex(uc.reg_read(UC_ARM_REG_PC)), 'LR', hex(uc.reg_read(UC_ARM_REG_LR)))
        return False

    def load(self):
        for seg in self.elf.iter_segments():
            if seg['p_type'] == 'PT_LOAD':
                self.write(BASE + seg['p_vaddr'], seg.data())
        dynsym = self.elf.get_section_by_name('.dynsym')
        for s in dynsym.iter_symbols():
            if s['st_shndx'] != 'SHN_UNDEF': self.symbols[s.name] = BASE + s['st_value']
        special = {}
        for name in ['__stack_chk_guard','__sF','_tolower_tab_']:
            special[name] = self.alloc(2048)
        self.put(special['__stack_chk_guard'], 0x724ed902)
        for name in ['SL_IID_ENGINE','SL_IID_ANDROIDSIMPLEBUFFERQUEUE','SL_IID_VOLUME','SL_IID_PLAYBACKRATE','SL_IID_PLAY']:
            p = self.alloc(16); special[name] = self.alloc(4); self.put(special[name], p)
        self.slids = {self.word(v): k for k, v in special.items() if k.startswith('SL_')}
        counts = collections.Counter()
        for sec in self.elf.iter_sections():
            if sec['sh_type'] not in ('SHT_REL', 'SHT_RELA'): continue
            for rel in sec.iter_relocations():
                p = BASE + rel['r_offset']; typ = rel['r_info_type']; counts[typ] += 1
                sym = dynsym.get_symbol(rel['r_info_sym'])
                s = self.symbols.get(sym.name)
                if s is None and sym.name:
                    s = special.get(sym.name) or self.thunk(sym.name)
                a = self.word(p)
                if typ == 23: self.put(p, BASE + a)  # R_ARM_RELATIVE
                elif typ in (21, 22): self.put(p, s or 0)
                elif typ == 2: self.put(p, (s or 0) + a)
                elif typ == 0: pass
                else: raise RuntimeError(f'Unsupported relocation {typ}')
        self.log('ELF_LOADED', len(self.symbols), 'defined symbols;', dict(counts), 'relocations')
        self.log('IMPORTS', len(self.thunks))

    def make_jni(self):
        self.jni_table = self.alloc(240 * 4)
        for idx in range(240): self.put(self.jni_table + idx * 4, self.thunk(f'jni_{idx}'))
        self.env = self.alloc(4); self.put(self.env, self.jni_table)
        self.main_class = self.obj(('class', 'com/snkplaymore/android003/MainActivity'))
        self.vm_table = self.alloc(8 * 4)
        for idx in range(8): self.put(self.vm_table + idx * 4, self.thunk(f'jvm_{idx}'))
        self.vm = self.alloc(4); self.put(self.vm, self.vm_table)

    def decoder_worker_begin(self,args):
        # Specific to the SHA-256-verified libAppMain.so loaded in __init__.
        # decode_memory_plus already allocated this decoder before pthread_create.
        if len(args)!=1 or getattr(self,'decoder_worker_guard',None):
            raise RuntimeError('Unexpected Vorbis worker invocation')
        packet=args[0]
        if self.allocations.get(packet)!=32:
            raise RuntimeError('Invalid Vorbis worker packet ownership')
        decoder=self.word(packet)
        if self.allocations.get(decoder)!=1536 or self.word(decoder+0x60)!=0:
            raise RuntimeError('Invalid Vorbis heap decoder ownership')
        owned={decoder:1536};tables=[]
        for block_offset,table_offset in ((0x80,0x45c),(0x84,0x460)):
            blocksize=self.word(decoder+block_offset)
            table=self.word(decoder+table_offset)
            if not(64<=blocksize<=8192 and blocksize&(blocksize-1)==0):
                raise RuntimeError('Invalid Vorbis block size')
            size=blocksize//4  # uint16 bit-reversal table with blocksize/8 entries.
            if table in owned or self.allocations.get(table)!=size:
                raise RuntimeError('Invalid Vorbis bit-reversal table ownership')
            owned[table]=size;tables.append((table_offset,table))
        if packet in owned or any(self.word(packet+offset) in owned for offset in (4,8,12,16,20)):
            raise RuntimeError('Vorbis private storage aliases its published output')
        guard={'packet':packet,'decoder':decoder,'owned':owned,'tables':tables}
        self.decoder_worker_guard=guard
        return guard

    def decoder_worker_finish(self,guard,result):
        # All exits of 0x13dc60 converge on deleting packet, vorbis_deinit, then
        # return 0. PCM is separately owned by CMediaSound. Never call deinit twice.
        # The original deinit omits both bit-reversal tables; this worker also
        # omits freeing its decoder body. Other deinit/close paths are untouched.
        if result!=0 or guard['packet'] in self.allocations:
            raise RuntimeError('Vorbis worker did not complete its native cleanup')
        if any(self.allocations.get(ptr)!=size for ptr,size in guard['owned'].items()):
            raise RuntimeError('Vorbis ownership changed during decode')
        if any(self.word(guard['decoder']+offset)!=table for offset,table in guard['tables']):
            raise RuntimeError('Vorbis private table pointers changed during decode')
        # free() rejects native free/reuse of any guarded block while this worker
        # is active. Remove that guard only after a full, successful native return.
        self.decoder_worker_guard=None
        for _,table in guard['tables']:self.free(table)
        self.free(guard['decoder'])
        self.decoder_cleanup_workers=getattr(self,'decoder_cleanup_workers',0)+1
        self.decoder_cleanup_bytes=getattr(self,'decoder_cleanup_bytes',0)+sum(guard['owned'].values())

    def call(self, symbol, *args, count=0, timeout=30000000):
        if self.stop_event is not None and self.stop_event.is_set() and not self.file_commits:
            raise ProbeCancelled()
        addr = self.symbols[symbol] if isinstance(symbol, str) else symbol
        guard=self.decoder_worker_begin(args) if addr==BASE+0x13dc61 else None
        try:
            self.phase = symbol if isinstance(symbol, str) else hex(symbol)
            self.uc.reg_write(UC_ARM_REG_SP, STACK)
            for i, arg in enumerate(args):
                if i < 4: self.uc.reg_write(REGS[i], arg & 0xffffffff)
                else: self.put(STACK + 4 * (i - 4), arg)
            self.uc.reg_write(UC_ARM_REG_LR, STOP)
            for slice_no in range(4):
                self.uc.emu_start(addr, STOP, timeout=timeout, count=count)
                pc = self.uc.reg_read(UC_ARM_REG_PC)
                if pc==STOP:break
                self.log('EXECUTION_SLICE',self.phase,slice_no,hex(pc))
                addr=pc | (1 if self.uc.reg_read(UC_ARM_REG_CPSR)&0x20 else 0)
            if pc != STOP: raise RuntimeError(f'Execution budget exhausted in {self.phase}: PC={pc:08x}')
            result=self.uc.reg_read(UC_ARM_REG_R0)
            if guard:self.decoder_worker_finish(guard,result)
            return result

        finally:
            if guard:self.decoder_worker_guard=None

    def native(self, name, *args):
        # JNI native entry owns temporary parameter/local references. Host roots
        # (including the reused touch arrays) must survive DeleteLocalRef in it.
        locals_before = {ref: counts['local'] for ref, counts in self.jni_refs.items()}
        for arg in args: self.jni_retain(arg)
        try:
            return self.call('Java_com_snkplaymore_android003_MainActivity_' + name, self.env, self.main_class, *args)
        finally:
            for ref in list(self.jni_refs):
                while self.jni_refs.get(ref, {}).get('local', 0) > locals_before.get(ref, 0):
                    self.jni_release(ref)

    def interrupt(self, uc, number, _):
        if self.stop_event is not None and self.stop_event.is_set() and not self.file_commits:
            raise ProbeCancelled()
        pc = uc.reg_read(UC_ARM_REG_PC)
        name = self.thunk_names.get(pc - 4)
        if name is None: raise RuntimeError(f'Unexpected ARM interrupt {number} at {pc:08x}')
        self.calls[name] += 1
        if self.calls[name] <= 2: self.log('HOSTCALL', name, [hex(a) for a in self.args(4)])
        while True:
            try:value = self.dispatch(name);break
            except (RuntimeError,KeyError) as error:
                if '--live' not in sys.argv:raise
                version=(ROOT/'probe.py').stat().st_mtime_ns
                self.log('CALLBACK_PAUSED',name,str(error))
                if hasattr(self,'graphics'):self.graphics.capture(ROOT/'last_frame.png')
                while (ROOT/'probe.py').stat().st_mtime_ns==version:time.sleep(0.2)
                import importlib.util
                spec=importlib.util.spec_from_file_location('probe_reload',ROOT/'probe.py')
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                for key,value in module.Probe.__dict__.items():
                    if callable(value):setattr(type(self),key,value)
                self.log('HOST_IMPLEMENTATION_RELOADED')
        if value is not None: uc.reg_write(UC_ARM_REG_R0, int(value) & 0xffffffff)

    def dispatch(self, name):
        # These two-argument-word imports dominate the recorded host calls.
        # Their double return still uses r0/r1, exactly like the generic path.
        if name in ('sin', 'cos'):
            a = self.args(2)
            x = struct.unpack('<d', struct.pack('<II', *a))[0]
            lo, hi = struct.unpack('<II', struct.pack('<d', getattr(math, name)(x)))
            self.uc.reg_write(UC_ARM_REG_R1, hi)
            return lo
        a = self.args()
        if name in ('windows_vorbis_plus','windows_vorbis_sync'):
            from native_audio import decode
            return decode(self,name,a)
        if name.startswith('jni_'): return self.jni(int(name[4:]), a)
        if name.startswith('jvm_'):
            idx = int(name[4:])
            if idx in (4, 6, 7): self.put(a[1], self.env); return 0
            if idx == 5: return 0
        if name == 'slCreateEngine': self.put(a[0],self.slobject('engine')); return 0
        if name.startswith('sl_'): return self.slcall(name,a)
        if name in ('malloc',): return self.alloc(a[0])
        if name == 'free': self.free(a[0]);return 0
        if name == 'realloc':
            p = self.alloc(a[1]); n = min(self.allocations.get(a[0], 0), a[1])
            if n: self.write(p, self.read(a[0], n))
            self.free(a[0])
            return p
        if name == 'memset': ctypes.memset(self.host(a[0],a[2]), a[1], a[2]); return a[0]
        if name in ('memcpy','memmove','bcopy'):
            dst, src = (a[1],a[0]) if name == 'bcopy' else (a[0],a[1])
            ctypes.memmove(self.host(dst,a[2]), self.host(src,a[2]), a[2]); return dst
        if name == 'memcmp':
            x,y = self.read(a[0],a[2]),self.read(a[1],a[2]); return (x > y) - (x < y)
        if name in ('strlen','atoi'): return len(self.string(a[0]).encode()) if name == 'strlen' else int(self.string(a[0]) or '0')
        if name == 'strtod':
            # Preserve the C parser's end pointer and the guest soft-float ABI.
            fn = ctypes.CDLL('msvcrt').strtod
            fn.argtypes = (ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p))
            fn.restype = ctypes.c_double
            buffer = ctypes.create_string_buffer(self.string(a[0]).encode())
            end = ctypes.c_void_p()
            value = fn(buffer, ctypes.byref(end))
            if a[1]: self.put(a[1], a[0] + end.value - ctypes.addressof(buffer))
            lo, hi = struct.unpack('<II', struct.pack('<d', value))
            self.uc.reg_write(UC_ARM_REG_R1, hi)
            return lo
        if name in ('strcmp','strcasecmp','strncmp'):
            x,y=self.string(a[0]),self.string(a[1])
            if name=='strcasecmp': x,y=x.lower(),y.lower()
            if name=='strncmp': x,y=x[:a[2]],y[:a[2]]
            return (x>y)-(x<y)
        if name in ('strcpy','strncpy'):
            b=self.string(a[1]).encode()+b'\0'
            if name=='strncpy': b=b[:a[2]].ljust(a[2],b'\0')
            self.write(a[0],b); return a[0]
        if name in ('strchr','strrchr','strstr'):
            x=self.string(a[0]); y=self.string(a[1]) if name=='strstr' else chr(a[1]&255)
            i=x.rfind(y) if name=='strrchr' else x.find(y)
            return a[0]+i if i>=0 else 0
        if name in ('__cxa_atexit','__aeabi_atexit','__cxa_finalize'): return 0
        if name == '__errno': return self.errno
        if name in ('puts',): self.log('GUEST', self.string(a[0])); return 0
        if name in ('sprintf','fprintf','sscanf','scanf'): return self.formatted(name, a)
        if name in ('clock_gettime','clock','time','usleep','srand48','lrand48','localtime','gmtime','mktime'): return self.clock(name,a)
        if name in ('sinf','cosf','tanf','acosf','atan2f','ceilf'):
            fn=getattr(math, {'sinf':'sin','cosf':'cos','tanf':'tan','acosf':'acos','atan2f':'atan2','ceilf':'ceil'}[name])
            return u32f(fn(f32(a[0]),f32(a[1])) if name=='atan2f' else fn(f32(a[0])))
        if name in ('sin','cos','tan','atan2','pow','exp','log','floor','ldexp'):
            x=struct.unpack('<d',struct.pack('<II',a[0],a[1]))[0]
            y=struct.unpack('<d',struct.pack('<II',a[2],a[3]))[0]
            fn=getattr(math,name); result=fn(x,y) if name in ('atan2','pow') else fn(x,i32(a[2])) if name=='ldexp' else fn(x)
            lo,hi=struct.unpack('<II',struct.pack('<d',result)); self.uc.reg_write(UC_ARM_REG_R1,hi); return lo
        if name.startswith('pthread_'): return self.pthread(name,a)
        if name.startswith('AAsset'): return self.asset(name,a)
        if name.startswith('gl'): return self.glcall(name,a)
        if name in ('fopen','fclose','fread','fwrite','fseek','ftell','fgetc','fgets','fputs','setvbuf','mkdir','chmod','rename','remove','close'): return self.filecall(name,a)
        if name in ('ALooper_forThread','ALooper_prepare','ASensorManager_getInstance','AStorageManager_new'): return self.alloc(16)
        if name == 'ASensorManager_getDefaultSensor': return 0  # No accelerometer in this host.
        if name == 'dlopen': self.log('DLOPEN',self.string(a[0])); return 0
        if name == 'dlclose': return 0
        if name in ('socket','connect','gethostbyname','getservbyname'): self.put(self.errno,101); return 0 if name.startswith('get') else -1
        raise RuntimeError(f'Unimplemented host function {name}: {list(map(hex,a))}')

    def jni(self, idx, a):
        if idx == 4: return 0x10006
        if idx == 6:
            if not hasattr(self,'class_cache'):self.class_cache={}
            name=self.string(a[1])
            if name not in self.class_cache:self.class_cache[name]=self.obj(('class',name))
            return self.class_cache[name]
        if idx in (21,25): return self.jni_retain(a[1], 'global' if idx == 21 else 'local')
        if idx in (22,23):
            self.jni_release(a[1], 'global' if idx == 22 else 'local'); return 0
        if idx == 24: return int(a[1]==a[2])
        if idx == 31: return self.main_class
        if idx in (33,94,113,144):
            value=('method' if idx in(33,113) else 'field',self.string(a[2]),self.string(a[3]))
            self.log('JNI_LOOKUP',value)
            if not hasattr(self,'method_cache'):self.method_cache={}
            if value not in self.method_cache:self.method_cache[value]=self.obj(value)
            return self.method_cache[value]
        if idx in (167,169,170):
            if idx == 167: return self.managed_obj(self.string(a[1]))
            if idx == 169:
                p = self.cstr(self.objects[a[1]])
                self.jni_utf_chars[p] = a[1]
                self.jni_retain(a[1], 'pin')
                if a[2]: self.write(a[2], b'\1')
                return p
            if self.jni_utf_chars.get(a[2]) != a[1]:
                raise RuntimeError('ReleaseStringUTFChars does not match an acquired buffer')
            del self.jni_utf_chars[a[2]]
            self.free(a[2]); self.jni_release(a[1], 'pin'); return 0
        if idx == 168: return len(self.objects[a[1]].encode())
        if idx==171:return self.objects[a[1]]['length']
        if idx==172:return self.managed_obj({'kind':'objects','length':a[1],'items':[a[3]]*a[1]})
        if idx in (173,174):
            items = self.objects[a[1]]['items']
            if not 0 <= a[2] < len(items): raise RuntimeError('JNI object array bounds')
            if idx == 173: return self.jni_retain(items[a[2]])
            old = items[a[2]]
            self.jni_retain(a[3], 'array'); items[a[2]] = a[3]
            self.jni_release(old, 'array'); return 0
        if 175<=idx<=182:
            size=(1,1,2,2,4,8,4,8)[idx-175]
            data=self.alloc(a[1]*size);self.write(data,bytes(a[1]*size))
            return self.managed_obj({'kind':'primitive','length':a[1],'size':size,'data':data})
        if 183<=idx<=190:
            if a[2]:self.write(a[2],b'\0')
            self.jni_retain(a[1], 'pin')
            return self.objects[a[1]]['data']
        if 191<=idx<=198:
            if self.objects[a[1]]['data'] != a[2]: raise RuntimeError('JNI array buffer mismatch')
            if a[3] != 1: self.jni_release(a[1], 'pin')
            return 0
        if 199<=idx<=214:
            arr=self.objects[a[1]];start=a[2]*arr['size'];n=a[3]*arr['size']
            if a[2]+a[3]>arr['length']:raise RuntimeError('JNI array bounds')
            if idx>=207:self.write(arr['data']+start,self.read(a[4],n))
            else:self.write(a[4],self.read(arr['data']+start,n))
            return 0
        if idx == 219: self.put(a[1],self.vm); return 0
        if idx in (15,17,228): return 0
        if 114 <= idx <= 143:
            return self.java_call(self.objects.get(a[2]), a, idx)
        raise RuntimeError(f'Unimplemented JNI index {idx}: {list(map(hex,a))}')

    def java_call(self, method, a, idx):
        self.log('JAVA_CALL',method)
        def arg(i):return self.word(a[3]+i*4) if (idx-114)%3==1 else a[3+i]
        if method[1].startswith('getFont') and method[1].endswith('Java'):
            size=max(arg(0),1)
            font=self.font(size)
            ascent,descent=font.getmetrics()
            if method[1]=='getFontWidthJava':value=font.getlength(self.objects[arg(1)])
            elif method[1]=='getFontAscentJava':value=-ascent
            elif method[1]=='getFontDescentJava':value=descent
            else:value=ascent+descent
            return u32f(value)
        if method[1]=='setAnimationInterval':
            self.frame_interval=self.word(a[3]) if idx in (115,118,130,142) else a[3]
            self.log('FRAME_INTERVAL',self.frame_interval)
            return 0
        if method[1]=='isMediaMounted': return 1
        if method[1]=='screenMeasurement': self.log('ANALYTICS_DISABLED');return 0
        if method[1]=='unlockAchievemnt':self.log('ONLINE_ACHIEVEMENT_UNAVAILABLE');return 0
        if method[1]=='sendScore':self.log('ONLINE_LEADERBOARD_UNAVAILABLE');return 0
        if method[1]=='checkApplicationNewVersion': return 0  # Exact body of this APK's Java method.
        if method[1]=='isBlackRabel': return 0  # No Android su executable exists in this host.
        if method[1]=='getDeviceName': return self.managed_obj('MSD Windows compatibility probe')
        if method[1] in ('tapjoyRequestRewardInterstitial','tapjoyGetTapPoints','AL_CreateInterstitial','chartboostCacheRewordedVideo','chartboostCacheMoreApps','AdMobSetInterstitial','InMobiSetInterstitial','AdMobRemoveBanner','AdMobShowBanner','chartboostShowInterstitial','chartboostShowMoreApps','chartboostShowRewordedVideo','AL_ShowInterstitial','AdMobShowInterstitial','InMobiShowInterstitial','tapjoyShowRewardInterstitial'):
            self.log('AD_SERVICE_UNAVAILABLE',method[1]); return 0
        if method[1] in ('AL_GetContensFlag','TJ_GetContentsFlag','TJ_IsConnecting','AdMobIsLoadedBanner','AdMobIsLoadedInterstitial'): return 0
        if method[1]=='startLoadTask': self.pending.append(('loadTask',())); return 0
        if method[1]=='getDefaultLanguageNo': return 0  # English, matching Java locale mapping.
        if method[1]=='GetWeekDay':
            # APK: Calendar.getInstance().get(Calendar.DAY_OF_WEEK).
            # Local time; Java numbers Sunday=1 through Saturday=7.
            return (time.localtime().tm_wday+1)%7+1
        if method[1] in ('getInternalUseableMem','getExternalUseableMem','getInternalTotalMem','getExternalTotalMem'):
            usage=__import__('shutil').disk_usage(ROOT)
            value=usage.total if 'Total' in method[1] else usage.free
            if method[2]=='()J': self.uc.reg_write(UC_ARM_REG_R1,value>>32);return value&0xffffffff
            return min(value,0x7fffffff)
        if method[1]=='getAppVersionName': return self.managed_obj(self.branding['display_version'])
        if method[1]=='onTextDraw':return self.draw_text(a,idx)
        from local_platform import handle_java_call
        handled,value=handle_java_call(self,method,arg)
        if handled:return value
        raise RuntimeError(f'Java callback requires implementation: {method}')

    def font(self, size):
        from text_render import font_for
        app = self.app_instance()
        language = self.word(app + 0x3d64) if app else 0
        return font_for(self, size, language)

    def app_instance(self):
        # Original getInstance reads this relocated singleton slot. Reading it
        # directly avoids re-entering native execution from a JNI font callback.
        if not hasattr(self, 'app_instance_slot'):
            self.app_instance_slot = self.word(BASE + 0x161f4a + self.word(BASE + 0x161f50))
        return self.word(self.app_instance_slot)

    def activate_unit_slot(self, slot):
        result={'slot':slot+1,'key':'1234567890'[slot] if 0<=slot<10 else '?'}
        def report(reason, **values):
            result.update(reason=reason,**values)
            self.last_unit_result=result
            self.log('KEY_UNIT_RESULT',json.dumps(result,ensure_ascii=False))
            messages={'created':'已出击','not_playing':'战斗尚未开始或已经结束','paused':'战斗已暂停',
                      'empty':'空槽位','disabled':'当前单位不可生产','unit_limit':'已达到单位数量上限',
                      'cooldown':'生产冷却中','controller':'当前战斗控制器不支持出击',
                      'native_blocked':'当前单位暂时无法生产','not_battle':'当前界面无法出击',
                      'invalid_slot':'无效槽位'}
            message=(f"AP 不足：{result['ap']} / {result['cost']}" if reason=='insufficient_ap'
                     else messages.get(reason,reason))
            self.unit_feedback={'text':f"{result['key']} · {message}",
                                'until':time.perf_counter()+2.5,'success':reason=='created',
                                'visible':result.get('scene')==100}
            return reason=='created'
        if not 0 <= slot < 10:
            return report('invalid_slot')
        from battle_controls import context
        controller,blocked,scene=context(self)
        result['scene']=scene
        if blocked:return report(blocked)
        action = self.word(self.word(controller) + 0x94)
        info=self.call('_ZNK16BattleController11getUnitInfoEi',controller,slot)
        if not info:return report('empty')
        result.update(unit_id=self.word(info+0x10),cost=self.word(info),
                      ap=self.call('_ZN26BattleControllerPlayerBase5getAPEv',controller),
                      cooldown=i32(self.word(info+0x18)))
        if self.call('_ZNK16BattleController15isUnitCountOverEv', controller):
            return report('unit_limit')
        if not self.call('_ZN26BattleControllerPlayerBase12isUnitCreateEi', controller, slot):
            self.log('KEY_UNIT_BLOCKED', slot + 1)
            if not self.read(info+0xc,1)[0]:return report('disabled')
            if result['ap']<result['cost']:return report('insufficient_ap')
            if result['cooldown']>0:return report('cooldown')
            return report('native_blocked')
        created = self.call(action, controller, slot)
        if created:
            self.call('_ZN17FrameworkInstance6playSEENS_9SoundTypeE7SoundIDi', 0, 8, 0)
        self.log('KEY_UNIT_ACTIVATED', slot + 1, bool(created))
        return report('created' if created else 'native_blocked',
                      ap_after=self.call('_ZN26BattleControllerPlayerBase5getAPEv',controller))

    def battle_key_action(self, action):
        from battle_controls import perform
        return perform(self,action)

    def draw_text(self,a,idx):
        from PIL import Image, ImageDraw, ImageFont
        assert idx==115,idx
        cursor=a[3]
        ref=self.word(cursor);cursor=(cursor+4+7)&~7
        scale=struct.unpack('<d',self.read(cursor,8))[0];cursor+=8
        refs=[self.word(cursor+4*i) for i in range(6)]
        def ints(ref):
            obj=self.objects[ref]
            return struct.unpack('<'+'i'*obj['length'],self.read(obj['data'],obj['length']*4))
        count,width,height,border=ints(ref)[:4]
        sizes,colors,xs,ys=map(ints,refs[:4])
        bolds=self.read(self.objects[refs[4]]['data'],count)
        strings=self.objects[refs[5]]['items']
        def extent(n):return min(1024,max(32,1<<(max(1,int(n*scale))-1).bit_length()))
        w,h=extent(width),extent(height)
        canvas=Image.new('RGBA',(w,h));draw=ImageDraw.Draw(canvas)
        for i in range(count):
            s=self.objects.get(strings[i],'')
            if not s:continue
            font=self.font(max(1,round(sizes[i]*scale)))
            asc=font.getmetrics()[0]
            col=colors[i]&0xffffffff
            color=(col&255,(col>>8)&255,(col>>16)&255,(col>>24)&255)
            font.draw(draw,(xs[i]*scale,ys[i]*scale+asc),s,fill=color,stroke_width=round(scale) if border else 0,stroke_fill=(0,0,0,255))
        # Android Bitmap.getPixels exposes ARGB int values (little endian BGRA).
        data=canvas.tobytes('raw','BGRA');p=self.alloc(len(data));self.write(p,data)
        self.log('TEXT_RASTER',w,h,count,scale,[self.objects.get(x,'') for x in strings[:count]])
        return self.managed_obj({'kind':'primitive','length':w*h,'size':4,'data':p})

    def formatted(self,name,a):
        if name=='sscanf':
            fmt=self.string(a[1]); specs=re.findall(r'%(?!%)(\*?)(?:\d+)?(?:hh|ll|[hlLjzt])?(?:\[[^]]*\]|[a-zA-Z])',fmt)
            fn=ctypes.CDLL('msvcrt').sscanf; fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p];fn.restype=ctypes.c_int
            ptrs=[ctypes.c_void_p(self.host(a[2+i],4)) for i in range(sum(s!='*' for s in specs))]
            return fn(self.string(a[0]).encode(),fmt.encode(),*ptrs)
        if name not in ('sprintf','fprintf'): raise RuntimeError(f'Unimplemented format function {name}')
        fmt=self.string(a[1]); cursor=2
        def sub(m):
            nonlocal cursor
            if m.group()=='%%': return '%'
            spec=m['spec']; length=m['length'] or ''
            if length and (spec not in 'diuoxX' or length=='L'):
                raise RuntimeError(f'Unsupported printf format {m.group()}')
            bits=64 if length in ('ll','j') else 8 if length=='hh' else 16 if length=='h' else 32
            if spec in 'diuoxX' and bits==64:
                # AAPCS32 variadic double-words start at an even register or
                # an 8-byte-aligned stack slot. The low word precedes the high.
                cursor=(cursor+1)&~1
                value=self.arg(cursor)|(self.arg(cursor+1)<<32);cursor+=2
            else:value=self.arg(cursor);cursor+=1
            if spec=='s': return self.string(value)
            if spec=='c': return chr(value&255)
            if spec in 'diuoxX':
                value&=(1<<bits)-1
                signed=spec in 'di'
                if signed and value&(1<<(bits-1)):value-=1<<bits
                flags=m['flags']; precision=m['precision']; width=int(m['width'] or 0)
                negative=value<0; magnitude=abs(value)
                digits=format(magnitude,{'i':'d','u':'d'}.get(spec,spec))
                if precision is not None:
                    places=int(precision or 0)
                    digits='' if magnitude==0 and places==0 else digits.rjust(places,'0')
                prefix=''
                if '#' in flags:
                    if spec=='o' and not digits.startswith('0'):prefix='0'
                    elif spec in 'xX' and magnitude:prefix='0x' if spec=='x' else '0X'
                sign='-' if negative else '+' if signed and '+' in flags else ' ' if signed and ' ' in flags else ''
                text=sign+prefix+digits
                if '-' in flags:return text.ljust(width)
                if '0' in flags and precision is None:return sign+prefix+digits.rjust(max(0,width-len(sign)-len(prefix)),'0')
                return text.rjust(width)
            if spec=='p': return hex(value)
            raise RuntimeError(f'Unsupported printf format {m.group()}')
        text=re.sub(r'%%|%(?P<flags>[-+ #0]*)(?P<width>\d*)(?:\.(?P<precision>\d*))?(?P<length>hh|ll|[hlLjzt])?(?P<spec>[a-zA-Z])',sub,fmt)
        if name=='sprintf': self.write(a[0],text.encode()+b'\0')
        else: self.log('GUEST_PRINT',text)
        return len(text.encode())

    def clock(self,name,a):
        if self.virtual_clock is not None and name in ('clock_gettime','time','clock'):return self.virtual_clock(name,a)
        if name=='clock_gettime':
            ns=time.monotonic_ns() if a[0] else time.time_ns(); self.write(a[1],struct.pack('<II',ns//10**9 & 0xffffffff,ns%10**9)); return 0
        if name=='time':
            t=int(time.time())
            if a[0]: self.put(a[0],t)
            return t
        if name=='clock': return int(time.process_time()*1000000)
        if name=='usleep': return 0
        if name=='srand48': self.rng48=((a[0]&0xffffffff)<<16)|0x330e; return 0
        if name=='lrand48':
            self.rng48=(0x5deece66d*getattr(self,'rng48',0x1234abcd330e)+0xb)&((1<<48)-1)
            return self.rng48>>17
        if name in ('localtime','gmtime'):
            # C returns borrowed static storage. Preserve the existing UTC mapping.
            if not getattr(self, 'tm_buffer', 0): self.tm_buffer = self.alloc(44)
            t=time.gmtime(self.word(a[0])); p=self.tm_buffer
            self.write(p,struct.pack('<11i',t.tm_sec,t.tm_min,t.tm_hour,t.tm_mday,t.tm_mon-1,t.tm_year-1900,(t.tm_wday+1)%7,t.tm_yday-1,0,0,0)); return p
        if name=='mktime':
            t=struct.unpack('<9i',self.read(a[0],36)); return int(__import__('calendar').timegm((t[5]+1900,t[4]+1,t[3],t[2],t[1],t[0])))

    def pthread(self,name,a):
        if name in ('pthread_mutex_init','pthread_mutex_lock','pthread_mutex_unlock','pthread_mutex_destroy','pthread_attr_init','pthread_attr_setdetachstate','pthread_attr_destroy','pthread_setname_np','pthread_detach','pthread_key_delete'): return 0
        if name=='pthread_key_create': self.put(a[0],len(self.handles)+1); return 0
        if name=='pthread_getspecific': return self.handles.get(('tls',a[0]),0)
        if name=='pthread_setspecific': self.handles[('tls',a[0])]=a[1]; return 0
        if name=='pthread_create':
            self.log('THREAD_REQUEST',hex(a[2]),hex(a[3])); self.put(a[0],1)
            self.pending.append((a[2],(a[3],))); return 0
        raise RuntimeError(name)

    def path(self,s):
        asset_path=PKG in s and ('.obm' in s or '.msdf' in s)
        if asset_path:
            cache=getattr(self,'asset_paths',None)
            if cache is None:self.asset_paths=cache={}
            if s in cache:return cache[s]
        if s.startswith('/data/data/'+PKG): p=self.saves/s.removeprefix('/data/data/'+PKG).lstrip('/')
        elif PKG in s and ('.obm' in s or '.msdf' in s):
            p=RESOURCE_ROOT/PKG/s.split(PKG,1)[1].lstrip('/')
        else: p=self.guest_root/s.lstrip('/').replace(':','_')
        if asset_path and p.parent==self.asset_cache.root and p.name in self.asset_cache.safe_names:
            pass  # A single basename under the canonical asset directory.
        else:p=p.resolve()
        permitted=self.guest_root
        assets=self.asset_cache.root
        if not(p.is_relative_to(permitted) or p.is_relative_to(assets)): raise RuntimeError('Path escape: '+s)
        if asset_path:cache[s]=p
        return p

    def filecall(self,name,a):
        if name=='fopen':
            requested=self.string(a[0]);mode=self.string(a[1])
            prefix='/data/data/'+PKG+'/'
            if mode.startswith('r') and requested.startswith(prefix):
                leaf=requested[len(prefix):]
                if Path(leaf).name==leaf and leaf.endswith(('.obm','.msdf')) and leaf not in self.local_asset_names:
                    self.put(self.errno,2);return 0
            path=self.path(requested); self.log('FILE_OPEN',str(path),mode)
            if any(k in mode for k in 'wa+') and not path.is_relative_to(self.guest_root): raise RuntimeError('Original asset write blocked')
            if path.name=='title01.obm' and mode.startswith('r'):
                from title_visuals import TitleVisuals
                if not hasattr(self,'title_visuals'):
                    self.title_visuals=TitleVisuals(self,getattr(self,'custom_content_root',ROOT/'custom_content'))
                replacement=self.title_visuals.read_asset(path,mode,(RESOURCE_ROOT/PKG).resolve())
                if replacement is not None:
                    handle=self.alloc(16);self.handles[handle]=io.BytesIO(replacement);return handle
            if path.name.startswith('menu_news00') and mode.startswith('r'):
                from custom_menu import MenuScreenOverride
                if not hasattr(self,'menu_screen_override'):
                    self.menu_screen_override=MenuScreenOverride(
                        getattr(self,'custom_content_root',ROOT/'custom_content'),self.log,
                        filename=self.branding['menu_image'])
                replacement=self.menu_screen_override.read_asset(
                    path,mode,(RESOURCE_ROOT/PKG).resolve())
                if replacement is not None:
                    handle=self.alloc(16);self.handles[handle]=io.BytesIO(replacement);return handle
            pending=None
            try:
                if any(k in mode for k in 'wa'): path.parent.mkdir(parents=True,exist_ok=True)
                binary=mode.replace('t','') if 'b' in mode else mode+'b'
                if mode.startswith('w'):
                    import tempfile
                    fd,tmp=tempfile.mkstemp(prefix=path.name+'.',suffix='.pending',dir=path.parent)
                    f=os.fdopen(fd,binary);pending=(Path(tmp),path)
                elif mode.startswith('r') and '+' not in mode and path.is_relative_to(self.asset_cache.root):
                    f=self.asset_cache.open(path)
                else:f=open(path,binary)
            except FileNotFoundError: self.put(self.errno,2); return 0
            handle=self.alloc(16); self.handles[handle]=f
            if pending:self.file_commits[handle]=pending
            return handle
        if name in ('mkdir','chmod'): return 0
        if name=='fclose':
            f=self.handles[a[0]]
            if a[0] in self.file_commits:
                f.flush();os.fsync(f.fileno());f.close()
                pending,target=self.file_commits[a[0]];os.replace(pending,target)
                del self.file_commits[a[0]]
                self.log('SAVE_COMMITTED',target.name)
            else:f.close()
            del self.handles[a[0]];self.free(a[0])
            return 0
        if name=='setvbuf': return 0
        if name=='fread':
            data=self.handles[a[3]].read(a[1]*a[2]); self.write(a[0],data); return len(data)//a[1] if a[1] else 0
        if name=='fwrite':
            n=self.handles[a[3]].write(self.read(a[0],a[1]*a[2])); return n//a[1] if a[1] else 0
        if name=='fseek': self.handles[a[0]].seek(i32(a[1]),a[2]); return 0
        if name=='ftell': return self.handles[a[0]].tell()
        if name=='fgetc':
            b=self.handles[a[0]].read(1); return b[0] if b else -1
        if name=='fputs': return self.handles[a[1]].write(self.string(a[0]).encode())
        raise RuntimeError(name)

    def asset(self,name,a):
        if name=='AAssetManager_fromJava':
            if not getattr(self, 'asset_manager', 0): self.asset_manager = self.alloc(16)
            return self.asset_manager
        if name=='AAssetManager_open':
            path='assets/'+self.string(a[1]); self.log('ASSET_OPEN',path)
            try: data=self.zip.read(path)
            except KeyError: return 0
            p=self.alloc(16); self.handles[p]=io.BytesIO(data); return p
        if name=='AAsset_getLength': return len(self.handles[a[0]].getbuffer())
        if name=='AAsset_read': data=self.handles[a[0]].read(a[2]);self.write(a[1],data);return len(data)
        if name=='AAsset_seek': return self.handles[a[0]].seek(i32(a[1]),a[2])
        if name=='AAsset_close':
            self.handles.pop(a[0]).close();self.free(a[0]);return 0
        raise RuntimeError(name)

    def glcall(self,name,a):
        if not hasattr(self,'graphics'):
            from graphics import Graphics
            self.graphics=Graphics(self,*self.window_size)
        return self.graphics.call(name,a)

    def get_audio(self):
        if not hasattr(self,'audio_bridge'):
            from audio_bridge import OpenSLAudio
            self.audio_bridge=OpenSLAudio(self,self.audio_mode,self.audio_capture)
        return self.audio_bridge

    def slobject(self,kind):
        return self.get_audio().object(kind)

    def slcall(self,name,a):
        return self.get_audio().dispatch(name,a)

    def initialize(self):
        registry=ROOT/'community_content/content.json'
        if registry.is_file() and not hasattr(self,'community'):
            from community_content import CommunityContent
            self.community=CommunityContent(self,registry.parent)
        section=self.elf.get_section_by_name('.init_array')
        constructors=[self.word(BASE+section['sh_addr']+i) for i in range(0,section['sh_size'],4)]
        for p in constructors:
            if p and p!=0xffffffff: self.log('CONSTRUCTOR',hex(p));self.call(p)
        self.log('CONSTRUCTORS_COMPLETE')
        self.native('ApplicationInit',self.obj('asset_manager'),self.obj(PKG),self.obj('/sdcard'),self.obj('msd-windows-probe'))
        self.log('APPLICATION_INIT_COMPLETE')
        width,height=self.window_size
        # The original engine extends its background and battle view through
        # screen margins. A shared scale preserves every sprite's aspect and
        # the complete 960x640 reference view at wider surface proportions.
        scale=min(width/960,height/640)
        self.native('init',width,height,width,height,u32f(scale),u32f(scale))
        self.log('SURFACE_INIT_COMPLETE')
        if hasattr(self,'community') and not self.community.ready:self.community.install()

    def start(self):
        self.initialize()
        self.frames(140)
        self.log('FRAMES_COMPLETE')
        if '--live' in sys.argv:self.control_loop()

    def frames(self,n):
        start=time.perf_counter()
        calls_before=dict(self.calls)
        for _ in range(n):
            self.step_frame()
        elapsed=time.perf_counter()-start
        self.graphics.capture(ROOT/'last_frame.png')
        self.log('FRAME_BATCH',self.frame,n,round(elapsed,3),'seconds')
        with open(ROOT/'frame_batches.jsonl','a',encoding='utf-8') as stream:
            stream.write(json.dumps({'last_frame':self.frame,'frames':n,'seconds':elapsed,'step_calls_per_second':n/elapsed,'draw_calls':sum(self.calls[k]-calls_before.get(k,0) for k in ('glDrawArrays','glDrawElements')),'resource_opens':self.calls['fopen']-calls_before.get('fopen',0)})+'\n')

    def step_frame(self):
        self.frame+=1;self.native('step')
        while self.pending:
            name,args=self.pending.pop(0)
            if isinstance(name,int):self.call(name,*args)
            else:self.native(name,*args)
            if hasattr(self,'audio_bridge'):self.audio_bridge.pump()
        from local_platform import pump
        pump(self)
        if hasattr(self,'audio_bridge'):self.audio_bridge.pump()

        if hasattr(self,'community'):self.community.flush()

    def control_loop(self):
        self.log('CONTROL_READY')
        folder=ROOT/'commands';folder.mkdir(exist_ok=True)
        while True:
            queued=sorted(folder.glob('*.json'))
            if not queued:time.sleep(0.1);continue
            file=queued[0];cmd=json.loads(file.read_text(encoding='utf-8-sig'))
            self.log('CONTROL_COMMAND',file.name,cmd)
            if cmd.get('quit'):
                file.rename(file.with_suffix('.done'));return
            if cmd.get('reload'):
                import importlib.util
                spec=importlib.util.spec_from_file_location('probe_reload',ROOT/'probe.py')
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                for key,value in module.Probe.__dict__.items():
                    if callable(value):setattr(type(self),key,value)
                self.log('HOST_IMPLEMENTATION_RELOADED')
            if 'tap' in cmd:self.tap(*cmd['tap'])
            if 'frames' in cmd:self.frames(cmd['frames'])
            self.graphics.capture(ROOT/('capture_'+file.stem+'.png'))
            file.rename(file.with_suffix('.done'))
            (ROOT/'host_calls.json').write_text(json.dumps(self.calls,indent=2))
            self.log('CONTROL_COMPLETE',file.stem,self.frame)

    def tap(self,x,y):
        # This game's Java switch maps DOWN/UP to 1/3, followed by index, count, ID.
        for action in (1,3):
            self.touch_event(action,x,y);self.frames(2)

    def back(self):
        """将返回请求提交至原生按键触发入口，由当前场景处理。"""
        app=self.app_instance()
        if not app:return False
        self.call('_ZN7AppMain13SetKeyTriggerEi',app,0x1000)
        return True

    def touch_event(self,action,x,y):
        # GLFW supplies positions on the full logical render surface. Native
        # TouchEvent subtracts its screen margin in reference-game units.
        # Convert the uniformly scaled surface coordinate to those units.
        scale=min(self.window_size[0]/960,self.window_size[1]/640)
        x,y=x/scale,y/scale
        if not hasattr(self,'touch_arrays'):
            ids=self.jni(179,[self.env,16]);coords=self.jni(181,[self.env,32])
            self.touch_arrays=ids,coords
        ids,coords=self.touch_arrays
        self.write(self.objects[coords]['data'],struct.pack('<ff',float(x),float(y)))
        self.write(self.objects[ids]['data'],struct.pack('<4i',action,0,1,0))
        self.native('onTouchEvent',ids,coords)

    def close(self):
        if hasattr(self,'community'):self.community.flush()
        if hasattr(self,'native_audio_cache'):self.native_audio_cache.close()
        if hasattr(self,'asset_cache'):self.asset_cache.close()
        if hasattr(self,'audio_bridge') and not self.audio_bridge.closed:
            self.log('AUDIO_SUMMARY',json.dumps(self.audio_bridge.stats()))
            self.audio_bridge.close()
        for value in list(self.handles.values()):
            if hasattr(value,'close'):
                try:value.close()
                except Exception:pass
        if hasattr(self,'graphics'):self.graphics.close()
        from native_imports import release
        release(self)
        self.zip.close();self.logfile.close()

if __name__ == '__main__':
    probe=None
    try:
        probe=Probe(); probe.start()
    except Exception as e:
        if probe:
            probe.log('PROBE_STOP',type(e).__name__,str(e))
            if hasattr(probe,'graphics'):
                probe.graphics.capture(ROOT/'last_frame.png')
            regs={f'r{i}':hex(probe.uc.reg_read(UC_ARM_REG_R0+i)) for i in range(13)}
            probe.log('REGISTERS',regs)
            (ROOT/'host_calls.json').write_text(json.dumps(probe.calls,indent=2))
        import traceback; traceback.print_exc()
        sys.exit(1)
