"""联机回滚 N1：战斗状态的逐帧保存与恢复（docs/netcode/N1_N2_ROLLBACK_2026-10-10.md）。

客体内存（256 MiB 窗口）以 MEM_WRITE_WATCH 分配（probe.guest_ram）。开始时把迄今写过的全部页复制到影子副本；
此后每帧结束时以 GetWriteWatch 取得本帧改动的页，把这些页的帧前内容（影子副本）记入该帧的撤销记录，
再把影子副本更新为帧后内容。恢复到第 g 帧末时，先撤销上次提交后的写入，再按相反顺序写回 g 之后各帧的撤销记录，
客体内存与影子副本同时回到第 g 帧末。从未写过的页始终为零，无需记录。

宿主侧状态（分配器、宿主随机数、JNI 引用表、文件句柄、OpenSL 音频流、核心静态状态）在每帧末各复制一份，
恢复时一并还原。GL 对象由 GLLedger 管理：回滚窗口内的删除推迟到该帧确认之后执行，被回滚掉的帧中新建的对象在恢复时删除。
"""
import ctypes
from collections import deque

PAGE = 4096
MEM_COMMIT_RESERVE, PAGE_READWRITE, MEM_RELEASE = 0x3000, 0x04, 0x8000


class Record:
    __slots__ = ('frame', 'host', 'bytes', 'pages', 'count', 'undo', 'runs', 'chunks')

    def __init__(self, frame, host):
        self.frame, self.host = frame, host
        self.pages = self.undo = self.runs = self.chunks = None
        self.count = self.bytes = 0


class GuestJournal:
    """客体内存的逐帧撤销记录。frame 为最近一次提交的帧号；records 中保存 (base_frame, frame] 各帧的撤销记录。
    核心有 msd_snap_*（联机接口版本 2，r44 起）时页复制在核心中完成；否则以宿主逐段复制（r43 验证过的实现）。"""

    def __init__(self, probe):
        if not getattr(probe, 'write_watch', False):
            raise RuntimeError('客体内存未以写入监视分配，无法建立回滚快照')
        import probe as probe_module
        self.p = probe
        self.base = probe.hostbase
        self.size = probe_module.SIZE
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self._get = kernel.GetWriteWatch
        self._get.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                              ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_uint32)]
        self._get.restype = ctypes.c_uint32
        self._reset = kernel.ResetWriteWatch
        self._reset.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        self._reset.restype = ctypes.c_uint32
        allocate = kernel.VirtualAlloc
        allocate.restype = ctypes.c_void_p
        allocate.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
        self.shadow = allocate(None, self.size, MEM_COMMIT_RESERVE, PAGE_READWRITE)
        if not self.shadow:
            raise MemoryError('无法分配回滚影子副本')
        self.capacity = self.size // PAGE
        self.addresses = (ctypes.c_uint64 * self.capacity)()
        # 本进程迄今写过的全部页（各次会话共用）。每次提交与恢复都会重置写入监视，同一进程的下一场会话（再战、回放）
        # 开始时 GetWriteWatch 只返回上次重置之后写过的页；其余页仍保存着有效内容，必须一并复制到新的影子副本（N5 修正）。
        self.seen = probe.__dict__.setdefault('journal_pages', set())
        lib = probe.uc.lib
        self.native = hasattr(lib, 'msd_snap_commit')
        if self.native:
            P, U = ctypes.c_void_p, ctypes.c_uint32
            for name, args in (('msd_snap_commit', [P, P, P, U, P]), ('msd_snap_restore', [P, P, P, U, P]),
                               ('msd_snap_copy', [P, P, P, P, U])):
                getattr(lib, name).argtypes = args
                getattr(lib, name).restype = U
            self.lib = lib
        self.records = deque()
        self.frame = self.base_frame = None
        self.base_host = None
        self.stats = {'commits': 0, 'restores': 0, 'pages_committed': 0, 'bytes_committed': 0,
                      'max_frame_bytes': 0, 'pages_restored': 0, 'shadow_bytes': 0, 'native_copy': self.native}

    def dirty_count(self, reset=True):
        """自上次重置以来写过的页数；页地址（升序）写入 self.addresses。"""
        count, granularity = ctypes.c_size_t(self.capacity), ctypes.c_uint32()
        if self._get(1 if reset else 0, self.base, self.size, self.addresses, ctypes.byref(count), ctypes.byref(granularity)):
            raise OSError(ctypes.get_last_error(), 'GetWriteWatch 失败')
        if count.value and granularity.value != PAGE:
            raise RuntimeError('意外的写入监视粒度 %d' % granularity.value)
        if reset and count.value:
            self.seen.update(self.addresses[:count.value])
        return count.value

    def dirty_runs(self, reset=True):
        """宿主逐段复制用：写过的页合并为 [(偏移, 字节数)]。"""
        n = self.dirty_count(reset)
        if not n:
            return []
        addresses = self.addresses[:n]
        runs = []
        start = previous = addresses[0]
        for address in addresses[1:]:
            if address == previous + PAGE:
                previous = address
                continue
            runs.append((start - self.base, previous + PAGE - start))
            start = previous = address
        runs.append((start - self.base, previous + PAGE - start))
        return runs

    def begin(self, frame, host):
        """以当前内存为第 frame 帧末的状态开始记录：本进程迄今写过的全部页（self.seen）复制到影子副本。"""
        self.dirty_count(reset=True)
        pages = sorted(self.seen)
        n = len(pages)
        self.addresses[:n] = pages
        if self.native:
            self.lib.msd_snap_copy(self.shadow, self.base, self.base, self.addresses, n)
        else:
            for address in pages:
                ctypes.memmove(self.shadow + (address - self.base), address, PAGE)
        total = n * PAGE
        self.stats['shadow_bytes'] = total
        self.records.clear()
        self.frame = self.base_frame = frame
        self.base_host = host

    def commit(self, frame, host):
        """第 frame 帧已模拟完毕：记录本帧改动页的帧前内容，影子副本更新为帧后内容。"""
        if frame != self.frame + 1:
            raise RuntimeError(f'回滚记录须逐帧提交：{self.frame} → {frame}')
        record = Record(frame, host)
        if self.native:
            n = self.dirty_count(reset=True)
            record.count, record.bytes = n, n * PAGE
            if n:
                record.pages = ctypes.string_at(self.addresses, n * 8)
                record.undo = ctypes.create_string_buffer(n * PAGE)
                self.lib.msd_snap_commit(self.base, self.shadow, record.pages, n, record.undo)
        else:
            memmove, string_at = ctypes.memmove, ctypes.string_at
            record.runs = self.dirty_runs(reset=True)
            record.chunks = []
            for offset, n in record.runs:
                record.chunks.append(string_at(self.shadow + offset, n))
                memmove(self.shadow + offset, self.base + offset, n)
            record.bytes = sum(n for _, n in record.runs)
        self.records.append(record)
        self.frame = frame
        s = self.stats
        s['commits'] += 1
        s['bytes_committed'] += record.bytes
        s['pages_committed'] += record.bytes // PAGE
        s['max_frame_bytes'] = max(s['max_frame_bytes'], record.bytes)
        return record

    def restore(self, frame):
        """客体内存回到第 frame 帧末（base_frame ≤ frame ≤ self.frame）；返回该帧末的宿主状态。"""
        if self.frame is None or not self.base_frame <= frame <= self.frame:
            raise RuntimeError(f'无法恢复到第 {frame} 帧（可恢复范围 {self.base_frame}–{self.frame}）')
        restored = 0
        if self.native:
            n = self.dirty_count(reset=True)                   # 上次提交后的写入：影子副本即为提交时的内容
            self.lib.msd_snap_copy(self.base, self.shadow, self.base, self.addresses, n)
            restored += n * PAGE
            while self.records and self.records[-1].frame > frame:
                record = self.records.pop()
                if record.count:
                    self.lib.msd_snap_restore(self.base, self.shadow, record.pages, record.count, record.undo)
                restored += record.bytes
        else:
            memmove = ctypes.memmove
            for offset, n in self.dirty_runs(reset=True):
                memmove(self.base + offset, self.shadow + offset, n)
                restored += n
            while self.records and self.records[-1].frame > frame:
                record = self.records.pop()
                for (offset, n), chunk in zip(record.runs, record.chunks):
                    memmove(self.base + offset, chunk, n)
                    memmove(self.shadow + offset, chunk, n)
                    restored += n
        if self._reset(self.base, self.size):                     # 本函数写回的页不计入下一帧的改动
            raise OSError(ctypes.get_last_error(), 'ResetWriteWatch 失败')
        self.frame = frame
        self.stats['restores'] += 1
        self.stats['pages_restored'] += restored // PAGE
        return self.records[-1].host if self.records else self.base_host

    def host_at(self, frame):
        if frame == self.base_frame:
            return self.base_host
        for record in self.records:
            if record.frame == frame:
                return record.host
        raise KeyError(frame)

    def confirm(self, frame):
        """第 frame 帧及之前已确认，不再恢复到更早的状态：丢弃不再需要的撤销记录。"""
        while self.records and self.records[0].frame <= frame:
            record = self.records.popleft()
            self.base_frame, self.base_host = record.frame, record.host

    def memory_bytes(self):
        return self.stats['shadow_bytes'] + sum(r.bytes for r in self.records)

    def close(self):
        """会话结束：释放影子副本（256 MiB 提交内存）与撤销记录，之后不能再提交或恢复。
        未释放时每场联机对战（含再战）各占 256 MiB 提交内存（N4 文档第 6.4 节）。"""
        if self.shadow:
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
            kernel.VirtualFree.restype = ctypes.c_int
            if not kernel.VirtualFree(ctypes.c_void_p(self.shadow), 0, MEM_RELEASE):
                raise OSError(ctypes.get_last_error(), 'VirtualFree 失败')
            self.shadow = None
        self.records.clear()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


class GLLedger:
    """回滚窗口内的 GL 对象管理（graphics.Graphics.ledger）。

    - 删除请求推迟到所在帧确认后执行：被回滚的帧中客体仍认为对象存在，名称不能先行释放。
    - 新建的对象按帧登记：恢复到更早的帧时，客体已不再持有这些名称，随即真正删除。"""
    CREATE = {'glGenTextures': 'texture', 'glGenFramebuffers': 'framebuffer',
              'glCreateShader': 'shader', 'glCreateProgram': 'program'}
    DELETE = {'glDeleteTextures': 'texture', 'glDeleteFramebuffers': 'framebuffer',
              'glDeleteShader': 'shader', 'glDeleteProgram': 'program'}

    def __init__(self, graphics):
        self.g = graphics
        self.frame = 0
        self.created = []           # [(帧, 类型, 名称)]
        self.deferred = []          # [(帧, 类型, 名称)]
        self.busy = False
        self.hooked = set(self.CREATE) | set(self.DELETE)
        self.stats = {'created': 0, 'deferred_deletes': 0, 'executed_deletes': 0, 'rollback_deletes': 0}

    def names(self, count, pointer):
        import struct
        p = self.g.p
        return list(struct.unpack('<%dI' % count, p.read(pointer, 4 * count))) if count > 0 and pointer else []

    def handle(self, name, args):
        if name in self.DELETE:
            kind = self.DELETE[name]
            if kind in ('texture', 'framebuffer'):
                for value in self.names(int(args[0]), args[1]):
                    if value:
                        self.deferred.append((self.frame, kind, value))
            elif args[0]:
                self.deferred.append((self.frame, kind, args[0]))
            self.stats['deferred_deletes'] += 1
            return 0
        self.busy = True
        try:
            result = self.g.call(name, args)
        finally:
            self.busy = False
        kind = self.CREATE[name]
        created = self.names(int(args[0]), args[1]) if kind in ('texture', 'framebuffer') else [result]
        for value in created:
            if value:
                self.created.append((self.frame, kind, value))
                self.stats['created'] += 1
        return result

    def delete(self, kind, value):
        import ctypes as C
        f = self.g.function
        if kind in ('texture', 'framebuffer'):
            array = (C.c_uint * 1)(value)
            f('glDeleteTextures' if kind == 'texture' else 'glDeleteFramebuffers', 'ip')(1, C.cast(array, C.c_void_p))
        elif kind == 'shader':
            f('glDeleteShader', 'u')(value)
        else:
            f('glDeleteProgram', 'u')(value)

    def rollback(self, frame):
        """恢复到第 frame 帧末：其后帧中的删除请求作废，其后帧中新建的对象真正删除。"""
        self.deferred = [entry for entry in self.deferred if entry[0] <= frame]
        keep = []
        for entry in self.created:
            if entry[0] > frame:
                self.delete(entry[1], entry[2])
                self.stats['rollback_deletes'] += 1
            else:
                keep.append(entry)
        self.created = keep

    def confirm(self, frame):
        keep = []
        for entry in self.deferred:
            if entry[0] <= frame:
                self.delete(entry[1], entry[2])
                self.stats['executed_deletes'] += 1
            else:
                keep.append(entry)
        self.deferred = keep
        self.created = [entry for entry in self.created if entry[0] > frame]

    def flush(self):
        """会话结束：执行全部推迟的删除。"""
        for entry in self.deferred:
            self.delete(entry[1], entry[2])
            self.stats['executed_deletes'] += 1
        self.deferred, self.created = [], []


class HostState:
    """宿主侧随帧变化、且与客体内存一致性相关的状态。"""

    def __init__(self, probe):
        self.p = probe
        lib = probe.uc.lib
        self.core_size = 0
        if hasattr(lib, 'msd_netplay_state_size'):
            lib.msd_netplay_state_size.restype = ctypes.c_uint32
            lib.msd_netplay_state_save.restype = ctypes.c_uint32
            lib.msd_netplay_state_save.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            lib.msd_netplay_state_load.restype = ctypes.c_uint32
            lib.msd_netplay_state_load.argtypes = [ctypes.c_char_p, ctypes.c_uint32]
            self.core_size = lib.msd_netplay_state_size()
            self.core_buffer = ctypes.create_string_buffer(self.core_size)
        self.extra = []             # [(capture(), apply(value))]：会话附加的宿主状态
        self.heap_seen = None       # 分配器版本（Probe.heap_version）未变时复用上一份分配表副本
        self.heap_copy = None

    def capture(self):
        p = self.p
        core = None
        if self.core_size:
            if p.uc.lib.msd_netplay_state_save(self.core_buffer, self.core_size) != self.core_size:
                raise RuntimeError('核心静态状态保存失败')
            core = self.core_buffer.raw
        audio = None
        bridge = getattr(p, 'audio_bridge', None)
        if bridge is not None:
            audio = {obj: (tuple(s.queue), s.index, s.generated_bytes, s.callbacks, s.state, s.last_frame,
                           s.capture_seconds, s.volume_mb, s.mute)
                     for obj, s in bridge.streams.items()}
        version = p.heap_version
        if version != self.heap_seen:
            self.heap_seen, self.heap_copy = version, (dict(p.allocations), list(p.free_blocks))
        allocations, free_blocks = self.heap_copy
        return (p.heap, allocations, free_blocks, getattr(p, 'rng48', None),
                dict(p.objects), {k: dict(v) for k, v in p.jni_refs.items()}, dict(p.jni_utf_chars),
                dict(p.handles), core, audio, [capture() for capture, _ in self.extra])

    def apply(self, state):
        p = self.p
        heap, allocations, free_blocks, rng48, objects, jni_refs, utf, handles, core, audio, extra = state
        if set(handles) != set(p.handles):
            raise RuntimeError('回滚窗口内存在跨帧打开的文件句柄，无法恢复')
        p.heap = heap
        p.allocations = dict(allocations)
        p.free_blocks = list(free_blocks)
        p.heap_version += 1                  # 分配表已替换：下一次保存重新复制
        self.heap_seen = None
        if rng48 is None:
            if hasattr(p, 'rng48'):
                del p.rng48
        else:
            p.rng48 = rng48
        p.objects = dict(objects)
        p.jni_refs = {k: dict(v) for k, v in jni_refs.items()}
        p.jni_utf_chars = dict(utf)
        if core is not None and not p.uc.lib.msd_netplay_state_load(core, len(core)):
            raise RuntimeError('核心静态状态恢复失败')
        bridge = getattr(p, 'audio_bridge', None)
        if bridge is not None and audio is not None:
            for obj, value in audio.items():
                stream = bridge.streams.get(obj)
                if stream is None:
                    continue
                (queue, stream.index, stream.generated_bytes, stream.callbacks, stream.state, stream.last_frame,
                 stream.capture_seconds, stream.volume_mb, stream.mute) = value
                stream.queue = deque(queue)
        for (_, apply), value in zip(self.extra, extra):
            apply(value)
