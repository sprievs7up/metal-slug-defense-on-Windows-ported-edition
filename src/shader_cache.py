"""Persistent ANGLE program cache through EGL_ANDROID_blob_cache.

ANGLE hands linked programs (including the compiled D3D shaders) to these
callbacks and asks for them again on the next launch, which skips the shader
compilation that otherwise stalls the first frames. The cache lives outside
the save folders and may be deleted at any time; one file per renderer string
(GPU and driver), so a driver change starts a fresh file.
MSD_SHADER_CACHE_DIR overrides the folder; an empty value disables the cache.
"""
import ctypes as C
import os
import struct
import zlib
from pathlib import Path

LIMIT = 64 << 20
MAGIC = b'MSDSHC1\0'
SIZE = C.c_ssize_t
SET = C.CFUNCTYPE(None, C.c_void_p, SIZE, C.c_void_p, SIZE)
GET = C.CFUNCTYPE(SIZE, C.c_void_p, SIZE, C.c_void_p, SIZE)


def folder():
    value = os.environ.get('MSD_SHADER_CACHE_DIR')
    if value is not None:
        return Path(value) if value else None
    base = os.environ.get('LOCALAPPDATA')
    return Path(base) / 'MSD_WINDOWS_S1XLV' / 'shader_cache' if base else None


class ShaderCache:
    def __init__(self, egl, display, log):
        self.log, self.entries, self.size, self.dirty, self.path = log, {}, 0, False, None
        self.hits = self.misses = self.stores = 0
        self.directory = folder()
        if self.directory is None:
            return
        egl.eglGetProcAddress.argtypes = [C.c_char_p]
        egl.eglGetProcAddress.restype = C.c_void_p
        proc = egl.eglGetProcAddress(b'eglSetBlobCacheFuncsANDROID')
        if not proc:
            log('SHADER_CACHE_UNAVAILABLE')
            return
        self.set_cb, self.get_cb = SET(self.store), GET(self.fetch)
        C.CFUNCTYPE(None, C.c_void_p, SET, GET)(proc)(display, self.set_cb, self.get_cb)

    def bind(self, renderer):
        """Select the file for this renderer; called once the context exists."""
        if self.directory is None:
            return
        self.path = self.directory / f'{zlib.crc32(renderer.encode()):08x}.bin'
        try:
            data = self.path.read_bytes()
        except OSError:
            data = b''
        if data[:8] == MAGIC:
            at = 8
            try:
                while at < len(data):
                    k, v = struct.unpack_from('<II', data, at)
                    at += 8
                    key, value = data[at:at + k], data[at + k:at + k + v]
                    if len(value) != v:
                        break
                    at += k + v
                    self.entries[key] = value
                    self.size += k + v
            except struct.error:
                pass
        self.log('SHADER_CACHE_LOADED', str(self.path), len(self.entries))

    def store(self, key, key_size, value, value_size):
        k = C.string_at(key, key_size)
        if self.size + key_size + value_size > LIMIT or k in self.entries:
            return
        self.entries[k] = C.string_at(value, value_size)
        self.size += key_size + value_size
        self.dirty = True
        self.stores += 1

    def fetch(self, key, key_size, value, value_size):
        found = self.entries.get(C.string_at(key, key_size))
        if found is None:
            self.misses += 1
            return 0
        if value and value_size >= len(found):
            C.memmove(value, found, len(found))
            self.hits += 1
        return len(found)

    def save(self):
        self.log('SHADER_CACHE_STATS', self.hits, self.misses, self.stores)
        if not (self.dirty and self.path):
            return
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(f'.{os.getpid()}.tmp')
            with temp.open('wb') as stream:
                stream.write(MAGIC)
                for k, v in self.entries.items():
                    stream.write(struct.pack('<II', len(k), len(v)) + k + v)
            os.replace(temp, self.path)
            self.dirty = False
        except OSError as error:
            self.log('SHADER_CACHE_SAVE_FAILED', str(error))
