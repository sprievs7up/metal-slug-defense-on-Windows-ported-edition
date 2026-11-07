"""里地图扩展页（里世界 4 起，2026-10-19）：世界目录中写 "ura_page" 的世界显示在原生里地图第 4 页之后。

原生里地图只有 3 页（里世界 1–3，世界号 9–11），每区域最多 5 关。核心钩子（src/ura_world_hooks.cpp，共享头 URA）对扩展世界号
返回宿主写入的区域、关卡与任务记录，开放 / 通关 / 新标记 / 用时 / 评级奖励读写宿主进度表；本模块负责：
- 依世界目录建立区域与关卡记录（原生布局，区域可有 6 关）、任务记录（关卡编号按原生规则 (世界号+1)×1000 + (区域+1)×10 + 关卡+1，
  名单、波次与触发由 community_campaign.mission_words 编译，BGM 写任务记录词 2，人质 0）；
- 区域名称：native_name 为原生区域名称表的编号；写 name（11 种语言）的区域由宿主把名称追加到原生表之后（编号 57 起，
  strAreaNameTbl 的各语言指针换为宿主副本，GetAreaName 按表读取）；
- 进度按关卡与区域稳定键保存于存档目录 campaign_progress.json（与扩展世界共用文件，字段 seen / wins / best_time、areas）；
- 主菜单背景：写 menu_background 的关卡编号表写入 URA+56 / +60，核心 menu_bg 钩子在 GetMainMenuBGStageID 洗牌前追加其中
  已通关者（2026-11-08）；
- 里地图背景：原生背景图案表 0x8fdb58（按页号取图案）第 4 页起写入未被里地图使用的图案（表世界 3、1、2 的 0x85、0x36、0x37；
  0x85 与里地图图案同在已载入的第 3 页图集），在里地图场景中以 drawConv 替换表把这些图案的转换项换为世界目录的 ura_background；
- 扩展世界的区域画面中，略缩图（转换表 28 的帧 0–5）换为关卡 thumbnail；关卡框标题为图案 0x3a + 序号（GT_StageIconDrawEx），
  第 6 关取到的 0x3f（第 62 项，别处的小图标）按标题位置换为“STAGE 6”整幅图（custom_content/stage_title_6.png，
  数字与原生同一字体，字形见 docs/ms6/MS6_STAGE_PORT_PLAN_2026-10-19.md 第 8.3.4 节）。
扩展世界的区域按原版里世界的做法整体开放：全部关卡可选，首次显示为 NEW。
"""
import json
import struct
from pathlib import Path

URA = 0x1ffe9000
URA_MAGIC = 0x34415255                     # 'URA4'
FIRST_WORLD = 12                           # 里世界 4 = 世界号 12（里地图页号 = 世界号 − 9）
SLOT_BASE = 0x40                           # 扩展页面任务的菜单槽（里地图场景用到 0x01–0x2e 与 0xdc 起的驾驶舱；0x29–0x2e 为进入演出所用）
BASE = 0x10000000
MENU_TABLE = BASE + 0x931950               # SC_StageInitMainEx 的菜单表（9 项，每项 0x38 字节）
BG_TABLE = BASE + 0x8fdb58                 # GT_StageSelectBGDrawEx：页号 → 背景图案（6 项）
BG_PICTS = [(0x85, 0x10306c64, 0x10306c74), (0x36, 0x10306a94, 0x10306aa4), (0x37, 0x10306ae4, 0x10306af4)]
THUMB_CONV_BASE = 0x10307bde               # 转换表 28：略缩图帧 0–7（128×56）
TITLE6_CONV = 0x10306654                   # 转换表 21 第 62 项（图案 0x3f）：第 6 关图标的标题取到此项
TITLE_X_OFFSET = 58.0                      # GT_StageIconDrawEx：标题绘制 x = 任务 x + 偏移 x − 58
AREA_THUMB = 9                             # 区域略缩图组（取里世界 1「中非」的原版值；帧由替换表换为关卡 thumbnail）
AREA_NAMES = BASE + 0x946b8c               # strAreaNameTbl：11 种语言各一个指针，指向 57 个区域名称（GetAreaName 每次按此表读取）
NATIVE_AREA_NAMES = 57
ARROW_PREV = 0x33cc
URA_SCENES = range(131, 137)
POPUP_SCENES = range(119, 123)
STAGE_STRIDE = 8


class UraWorld:
    def __init__(self, p):
        self.p = p
        self.ready = False
        self.pages = []                    # [(页号, 世界号, 世界)]
        self.stage_keys = []               # 进度序号 → 稳定键
        self.area_keys = []
        self.images = {}
        self.written = None
        self.base_scene = 0
        self.counter = 0

    # ---------- 建立 ----------
    def install(self):
        p = self.p
        catalog = getattr(p.community, 'campaign_catalog', None)
        worlds = getattr(catalog, 'ura_worlds', {}) if catalog else {}
        self.ready = True
        if not worlds:
            return
        if not hasattr(p.uc.lib, 'msd_enable_ura_world_hooks'):
            raise RuntimeError('里地图扩展页需要与宿主匹配的原生核心（msd_enable_ura_world_hooks）')
        missing = p.uc.lib.msd_enable_ura_world_hooks()
        if missing:
            raise RuntimeError(f'里地图扩展页钩子有 {missing} 处未找到原生块')
        from community_campaign import mission_words
        self.catalog = catalog
        if getattr(p, 'campaign', None) is None:
            self.own_progress = self.load_progress()
        info = p.call('_ZN10BattleInfo11getInstanceEv')
        scene_ids = {s['key']: s['id'] for s in p.community.manifest.get('stages', [])}
        sound_ids = getattr(p.community, 'sound_ids', {})
        world_rows, missions, stages, areas, custom_names, menu_ids = [], [], [], [], [], []
        for k, page in enumerate(sorted(worlds)):
            world = worlds[page]
            number = FIRST_WORLD + k
            self.pages.append((page, number, world))
            area_ptrs = []
            for a, area in enumerate(world['areas']):
                stage_ptrs = []
                first = len(stages)
                for s, stage in enumerate(area['stages']):
                    music = stage.get('music', 100)
                    bgm = music if type(music) is int else sound_ids.get(music, 0)
                    dx, dy = stage['map_position']
                    rec = struct.pack('<iiIIbxhhh', 3 * dx, 3 * dy - 10, bgm, s, -1, 0, 0, 0)
                    stage_ptrs.append(self.blob(rec))
                    stage_number = (number + 1) * 1000 + (a + 1) * 10 + s + 1
                    words = mission_words(p, catalog, scene_ids, info, stage, stage_number, self.blob)
                    words[2] = bgm                     # 任务记录 +8：关卡 BGM（原生优先读取）
                    words[7] = 0                       # 人质上限
                    missions.append(struct.pack('<30I', *words))
                    stages.append(stage['key'])
                    if stage.get('menu_background'):
                        menu_ids.append(stage_number)
                x, y = area['map_position']
                if 'name' in area:                     # 自制区域名称：编号接在原生 57 项之后（extend_area_names）
                    name_index = NATIVE_AREA_NAMES + len(custom_names)
                    custom_names.append(area['name'])
                else:
                    name_index = area['native_name']
                head = struct.pack('<IiibxhhH', name_index, x, y, AREA_THUMB, -1, -1, len(stage_ptrs))
                body = b''.join(struct.pack('<I', ptr) for ptr in stage_ptrs)
                rec = (head + body).ljust(0x40, b'\0') + struct.pack('<II', first, len(areas))
                area_ptrs.append(self.blob(rec))
                areas.append(area['key'])
            world_rows.append(struct.pack('<I', len(area_ptrs)) + b''.join(struct.pack('<I', v) for v in area_ptrs).ljust(64, b'\0'))
        self.stage_keys, self.area_keys = stages, areas
        if custom_names:
            self.extend_area_names(custom_names)
        self.stage_table = self.blob(bytes(STAGE_STRIDE * len(stages)))
        self.area_table = self.blob(bytes(4 * len(areas)))
        self.write_progress()
        menu = bytearray(p.read(MENU_TABLE, 9 * 0x38))
        page_entry = bytearray(p.read(MENU_TABLE + 8 * 0x38, 0x38))
        if struct.unpack_from('<i', page_entry, 0)[0] != 0x1f or struct.unpack_from('<i', page_entry, 16)[0] != 2752:
            raise RuntimeError('里地图菜单表与预期不符（第 9 项应为里世界 3 的页面任务）')
        for k in range(len(self.pages)):
            struct.pack_into('<i', page_entry, 0, SLOT_BASE + k)
            struct.pack_into('<i', page_entry, 16, 2752 + 1136 * (k + 1))
            menu += page_entry
        menu_ptr = self.blob(bytes(menu))
        for k in range(len(self.pages)):
            p.put(BG_TABLE + 4 * (3 + k), BG_PICTS[k][0])
        p.write(URA + 4, struct.pack('<9I', len(self.pages), FIRST_WORLD, SLOT_BASE, self.blob(b''.join(world_rows)),
                                     self.blob(b''.join(missions)), len(missions), self.stage_table, self.area_table, 0))
        p.write(URA + 40, struct.pack('<4I', menu_ptr, 9 + len(self.pages), 0, 0))
        if menu_ids and p.uc.lib.msd_ura_world_version() < 2:
            raise RuntimeError('主菜单背景关卡（menu_background）需要核心 menu_bg 钩子（msd_ura_world_version 2）')
        menu_list = self.blob(struct.pack(f'<{len(menu_ids)}I', *menu_ids)) if menu_ids else 0
        p.write(URA + 56, struct.pack('<2I', menu_list, len(menu_ids)))
        p.put(URA, URA_MAGIC)
        self.counter = 0
        p.log('URA_WORLD_INSTALLED', [(page, number, w['key']) for page, number, w in self.pages], len(missions), menu_ids)

    @property
    def progress(self):
        # 与扩展世界共用 campaign_progress.json：每次取 CommunityCampaign 当前的进度对象（其事务失败时会换为回滚后的对象）。
        campaign = getattr(self.p, 'campaign', None)
        return campaign.progress if campaign is not None else self.own_progress

    def blob(self, raw):
        ptr = self.p.alloc(len(raw))
        self.p.write(ptr, raw)
        return ptr

    def extend_area_names(self, names):
        """区域名称表的每种语言换为宿主副本：原生 57 个指针之后接自制名称（UTF-8），编号 57 起依次对应 names。"""
        from campaign_catalog import AREA_NAME_LANGUAGES
        p = self.p
        for lang, code in enumerate(AREA_NAME_LANGUAGES):
            table = p.word(AREA_NAMES + 4 * lang)
            native = p.read(table, 4 * NATIVE_AREA_NAMES)
            extra = b''.join(struct.pack('<I', self.blob(name[code].encode('utf-8') + b'\0')) for name in names)
            p.put(AREA_NAMES + 4 * lang, self.blob(native + extra))

    def load_progress(self):
        path = self.p.saves / 'campaign_progress.json'
        progress = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'schema': 1, 'stages': {}}
        if progress.get('schema') != 1:
            raise ValueError('未知扩展世界存档版本')
        return progress

    # ---------- 进度 ----------
    def write_progress(self):
        p = self.p
        stages = self.progress.setdefault('stages', {})
        areas = self.progress.setdefault('areas', {})
        for i, key in enumerate(self.stage_keys):
            saved = stages.get(key, {})
            flags = 1 | (0 if saved.get('seen') else 4) | (2 if saved.get('wins', 0) > 0 else 0)
            p.write(self.stage_table + i * STAGE_STRIDE, struct.pack('<II', flags, saved.get('best_time', 0)))
        for i, key in enumerate(self.area_keys):
            saved = areas.get(key, {})
            flags = (0 if saved.get('seen') else 1) | (2 if saved.get('rank_reward') else 0)
            p.put(self.area_table + 4 * i, flags)

    def save_progress(self):
        p = self.p
        stages = self.progress.setdefault('stages', {})
        areas = self.progress.setdefault('areas', {})
        for i, key in enumerate(self.stage_keys):
            flags, best = struct.unpack('<II', p.read(self.stage_table + i * STAGE_STRIDE, 8))
            saved = stages.setdefault(key, {'attempts': 0, 'wins': 0, 'captures': 0, 'rank': 0})
            saved['seen'] = not flags & 4
            if flags & 2:
                saved['wins'] = max(saved.get('wins', 0), 1)
            if best:
                saved['best_time'] = best
        for i, key in enumerate(self.area_keys):
            flags = p.word(self.area_table + 4 * i)
            areas[key] = {'seen': not flags & 1, 'rank_reward': bool(flags & 2)}
        from event_trial import atomic_bytes
        atomic_bytes(p.saves / 'campaign_progress.json', json.dumps(self.progress, ensure_ascii=False, indent=2).encode())
        p.log('URA_WORLD_PROGRESS_SAVED', p.word(URA + 36))

    # ---------- 每帧 ----------
    def update(self):
        p = self.p
        app = p.app_instance()
        if not app:
            return
        scene = p.word(app + 0x22bc)
        if not self.ready:
            if scene < 27:                     # 主菜单之后建立（里地图只能经主菜单进入）
                return
            self.install()
        if not self.pages:
            return
        counter = p.word(URA + 36)
        if counter != self.counter:
            self.counter = counter
            self.save_progress()
        self.update_art(app, scene)

    def image(self, path):
        if path not in self.images:
            from PIL import Image
            from lab_versus import create_native_image
            with Image.open(path) as source:
                self.images[path] = create_native_image(self.p, source.convert('RGBA'))
        return self.images[path]

    def rows(self, app):
        p = self.p
        rows = []
        for k, (page, number, world) in enumerate(self.pages):
            image = self.image(self.catalog.ura_images[world['ura_background']])
            _, left, right = BG_PICTS[k]
            rows.append((left, 0, image, 0, (0, 0, 285, 320, 0, 0, 0, 0)))
            rows.append((right, 0, image, 0, (286, 0, 285, 320, -283, 0, 0, 0)))
        current = p.word(app + 0xb200) + p.word(app + 0xb204)
        if FIRST_WORLD <= current < FIRST_WORLD + len(self.pages):
            world = self.pages[current - FIRST_WORLD][2]
            area_index = p.word(app + 0xb208)
            areas = world['areas']
            if area_index < len(areas):
                for f, stage in enumerate(areas[area_index]['stages']):
                    if 'thumbnail' in stage:
                        rows.append((THUMB_CONV_BASE + 16 * f, 0, self.image(self.catalog.ura_images[stage['thumbnail']]),
                                     0, (0, 0, 128, 56, 0, 0, 0, 0)))
            if p.word(URA + 48):                    # 第 6 关图标位于槽 0x1b（箭头暂存期间）
                icon = p.word(app + ARROW_PREV)
                if icon:
                    x = struct.unpack('<f', p.read(icon + 0x84, 4))[0] + struct.unpack('<f', p.read(icon + 0x9c, 4))[0] - TITLE_X_OFFSET
                    title = Path(__file__).resolve().parent / 'custom_content' / 'stage_title_6.png'
                    rows.append((TITLE6_CONV, 1, self.image(title), struct.unpack('<I', struct.pack('<f', x))[0],
                                 (0, 0, 59, 10, 0, 0, 0, 0)))
        return rows

    def update_art(self, app, scene):
        p = self.p
        import lab
        header = lab.LAB_HEADER + 0xb40
        from event_content import REPLACE_MAGIC, MAX_REPLACEMENTS
        if scene not in POPUP_SCENES:
            self.base_scene = scene
        if self.base_scene not in URA_SCENES:
            if self.written is not None:
                if p.word(header) == REPLACE_MAGIC:
                    p.put(header, 0)
                self.written = None
            return
        rows = self.rows(app)[:MAX_REPLACEMENTS]
        if rows == self.written:
            return
        for i, (conv, mode, image, match, rect) in enumerate(rows):
            e = header + 0x10 + i * 32
            p.put(e, conv); p.put(e + 4, mode); p.put(e + 8, image); p.put(e + 12, match)
            p.write(e + 16, struct.pack('<8h', *rect))
        p.put(header + 4, len(rows))
        p.put(header, REPLACE_MAGIC)
        self.written = rows

    def close(self):
        if self.pages and self.counter != self.p.word(URA + 36):
            self.save_progress()
