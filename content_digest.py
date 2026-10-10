"""内容资源摘要（BLAKE2b-256），按“文件大小 + 修改时间”缓存。

用于启动时核对本体与模组资源、以及以后的联机内容清单（模组规格第 6 节第 4 项）。缓存位于用户目录，
不在存档目录内，可随时删除；文件大小或修改时间变化时重新计算。
MSD_CONTENT_DIGEST_CACHE 可改变缓存文件路径，设为空值时停用缓存。
"""
from pathlib import Path
import hashlib
import json
import os


def blake2(raw):
    return hashlib.blake2b(raw, digest_size=32).hexdigest()


def cache_path():
    value = os.environ.get('MSD_CONTENT_DIGEST_CACHE')
    if value is not None:
        return Path(value) if value else None
    base = os.environ.get('LOCALAPPDATA')
    return Path(base) / 'MSD_WINDOWS_S1XLV' / 'content_digests.json' if base else None


class DigestCache:
    def __init__(self, path=None):
        self.path = cache_path() if path is None else path
        self.entries, self.dirty = {}, False
        if self.path is not None:
            try:
                data = json.loads(self.path.read_text(encoding='utf-8'))
                if data.get('schema') == 1 and isinstance(data.get('entries'), dict):
                    self.entries = data['entries']
            except (OSError, ValueError):
                self.entries = {}

    def digest(self, path, raw):
        """返回 raw（path 的当前内容）的摘要；缓存命中时不重新计算。"""
        stat = path.stat()
        key = str(path.resolve())
        entry = self.entries.get(key)
        if isinstance(entry, list) and len(entry) == 3 and entry[0] == stat.st_size == len(raw) and entry[1] == stat.st_mtime_ns:
            return entry[2]
        value = blake2(raw)
        self.entries[key] = [stat.st_size, stat.st_mtime_ns, value]
        self.dirty = True
        return value

    def save(self):
        if not self.dirty or self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.json.tmp')
            temporary.write_text(json.dumps({'schema': 1, 'entries': self.entries}), encoding='utf-8')
            os.replace(temporary, self.path)
            self.dirty = False
        except OSError:
            pass
