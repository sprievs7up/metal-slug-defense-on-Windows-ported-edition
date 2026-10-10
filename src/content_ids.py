"""社区单位的运行时 UnitID 分配。

本体单位的 ID 写在 community_content/content.json 的 unit_ids 中，只追加、不重排。
模组单位的 ID 由 ModIdMap 在模组区段内分配，并持久化“稳定键 → ID”映射：同一模组跨启动保持相同 ID，
停用后映射保留，重新启用时恢复原 ID（模组规格第 2.1 节）。映射文件位于用户目录，不在存档目录内。
MSD_MOD_ID_MAP 可改变映射文件路径。
"""
from pathlib import Path
import json
import os

UNIT_ID_BASE = 1024
# 槽位编号同时用于商店 ID 512+槽位、图片索引 423+槽位与图标索引 340+槽位，均按 int16 写入原生表。
SLOT_LIMIT = 32000


def check_ranges(ranges):
    """content.json 的 unit_id_ranges：body 自 1024 起，mods 紧接其后；上限受槽位编号的 int16 范围约束。"""
    if not isinstance(ranges, dict) or set(ranges) != {'body', 'mods'}:
        raise ValueError('unit_id_ranges requires body and mods ranges')
    body, mods = ranges['body'], ranges['mods']
    values = [*body, *mods] if isinstance(body, list) and isinstance(mods, list) else []
    if (len(values) != 4 or any(not isinstance(v, int) or isinstance(v, bool) for v in values)
            or body[0] != UNIT_ID_BASE or not body[0] < body[1] == mods[0] < mods[1] <= UNIT_ID_BASE + SLOT_LIMIT):
        raise ValueError('Invalid community unit ID ranges')
    return tuple(body), tuple(mods)


def check_body_ids(unit_ids, body):
    if not isinstance(unit_ids, dict) or not unit_ids:
        raise ValueError('content.json requires unit_ids')
    seen = set()
    for key, uid in unit_ids.items():
        if not isinstance(key, str) or not key or '\0' in key:
            raise ValueError('Invalid stable unit key')
        if not isinstance(uid, int) or isinstance(uid, bool) or not body[0] <= uid < body[1] or uid in seen:
            raise ValueError('Body unit ID outside its range or duplicated: ' + key)
        seen.add(uid)


def default_map_path():
    value = os.environ.get('MSD_MOD_ID_MAP')
    if value:
        return Path(value)
    base = os.environ.get('LOCALAPPDATA')
    return Path(base) / 'MSD_WINDOWS_S1XLV' / 'mods_ids.json' if base else None


class ModIdMap:
    """模组单位的持久化 ID 映射；映射只增不删。"""

    def __init__(self, path, mods_range):
        self.path, self.range = path, tuple(mods_range)
        self.ids, self.dirty = {}, False
        if path is not None and path.is_file():
            data = json.loads(path.read_text(encoding='utf-8'))
            if data.get('schema') != 1:
                raise ValueError('Unsupported mod ID map schema')
            for key, uid in data['ids'].items():
                if not isinstance(uid, int) or not self.range[0] <= uid < self.range[1] or uid in self.ids.values():
                    raise ValueError('Invalid mod ID map entry: ' + key)
                self.ids[key] = uid

    def assign(self, keys, preferred=None):
        """为已启用模组的单位键返回 ID。已有映射保持；新键优先采用 preferred（例如存档进度记录的 ID）中
        仍空闲的值，否则取区段内最小的空闲 ID。"""
        preferred = preferred or {}
        result = {}
        for key in keys:
            if key in result:
                raise ValueError('Duplicate mod unit key: ' + key)
            uid = self.ids.get(key)
            if uid is None:
                used = set(self.ids.values())
                wish = preferred.get(key)
                if isinstance(wish, int) and self.range[0] <= wish < self.range[1] and wish not in used:
                    uid = wish
                else:
                    uid = next((v for v in range(*self.range) if v not in used), None)
                    if uid is None:
                        raise ValueError('Mod unit ID range exhausted')
                self.ids[key] = uid
                self.dirty = True
            result[key] = uid
        return result

    def save(self):
        if not self.dirty or self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps({'schema': 1, 'ids': self.ids}, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporary, self.path)
        self.dirty = False
