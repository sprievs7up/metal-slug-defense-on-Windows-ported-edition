"""标题画面 OPTION 的整理与 MOD 页（模组 M4）。

- 标题画面（场景 20）原生 OPTION 面板改为六行，全部使用原生面板（GT_PausePanel：原生按钮框、按下高亮、原生文字与字形、
  原生喇叭图标与确定音）：
    1 語言設定
    2 音樂 | 音效（原生面板 0x3394、0x3398 各占半行，开关状态由原生喇叭图标表示，文字改为短名）
    3 開頭動畫 | 結尾動畫（0x339c、0x33a0；未通关第二世界时原生不显示结尾动画，右半行留空）
    4 MOD 設定（原“再次取得追加資料”面板 0x33a4，原生建好后改为 GT_Blank；本模块恢复为 GT_PausePanel 并改写文字，
      核心钩子把它的选中结果改为 MOD 页请求）
    5 結束遊戲（以“關閉”行的原生表项另建一个面板，存于 app+0x3360 第 255 槽，场景结束时由 deleteMenuTask 一并释放）
    6 關閉
- 半宽按钮：每半各为独立原生面板（按下高亮、点击区域、图标与文字互不影响）。按钮框与按下高亮图块经 drawConv 替换表
  （LAB 头部 +0xb40）按 x 坐标换为 92 像素宽的合成框（原生框左 80 像素 + 右端 12 像素），面板入场纵向滑动时不受影响；
  左右点击区域之间留 8 像素空隙，避免误触。
- MOD 页：宿主绘制的全屏页面（原生砖墙背景、顶栏、BACK 图标按钮、米色面板与按钮），列出 mods/ 下的模组与启用列表中
  未安装的模组；可启用/停用、调整加载顺序、查看详情（作者、许可、内容、依赖、冲突、校验错误、被覆盖的字段）、全部停用。
- 生效时机（用户确认）：选择即写入启用列表（mod_loader.write_enabled），重启游戏后生效；页面显示提示。
  运行中不卸载或重装已安装内容。
- 界面文字随游戏语言（MOD 页为繁体 / 简体 / 日语 / 英语，同 lab_ui；OPTION 面板文字为原生 11 种语言）。
"""
import struct

from lab_ui import (W, H, WHITE, GOLD, GRAY, BLUE, RED, BRICK, SE_DECIDE, SE_CLOSE,
                    Canvas, Skin, T, fonts, icon_press_image, lang, play_se)

AUDIO_HEADER = 0x1ffea000
TOPT, TOPT_MAGIC = AUDIO_HEADER + 0x10, 0x54504f54          # 核心 audio_options.cpp：+4 MOD 请求、+8 额外面板、+0xc 文字重建计数
VS_TABLE, VS_MAGIC = 0x1ffeb000 + 0xb40, 0x47505356          # drawConv 替换表（lab_hooks.cpp）
FRAME_CONV, PRESS_CONV = 0x1031c940, 0x1031c950             # 原生 OPTION 行按钮框与按下高亮（menuparts.obm 191,144 / 191,120，190×23）
FRAME_RECT, PRESS_RECT = (191, 144, 190, 23), (191, 120, 190, 23)
HALF_W, CAP = 92, 12                                        # 半宽框（原生 2 倍绘制）：左 80 像素 + 右端 12 像素
FULL_X, LEFT_X, RIGHT_X = 290.0, 192.0, 388.0               # 文字中心为任务 x + 190：半宽框中心 382 / 578
ROW_Y = (176.0, 244.0, 312.0, 380.0, 448.0, 516.0)
HIT_FULL, HIT_LEFT, HIT_RIGHT = (-10.0, -10.0, 400.0, 66.0), (92.0, -10.0, 192.0, 66.0), (96.0, -10.0, 190.0, 66.0)
EXIT_SLOT = 255                                             # app+0x3360 起的任务槽（标题场景未使用）
CLOSE_ENTRY = 20                                            # 标题菜单任务表中“關閉”行（槽 18）的表项
# 面板：(app 偏移 或 None=退出面板, x, 行号, 点击区域)
LAYOUT = ((0x3390, FULL_X, 0, HIT_FULL), (0x3394, LEFT_X, 1, HIT_LEFT), (0x3398, RIGHT_X, 1, HIT_RIGHT),
          (0x339c, LEFT_X, 2, HIT_LEFT), (0x33a0, RIGHT_X, 2, HIT_RIGHT), (0x33a4, FULL_X, 3, HIT_FULL),
          (None, FULL_X, 4, HIT_FULL), (0x33a8, FULL_X, 5, HIT_FULL))
# 原生语言编号（app+0x3d64，GetStringTitle 核对）：0 英 1 日 2 韩 3 西 4 葡 5 法 7 意 9 繁中 10 俄；6、8 无原生文字（按英语）。
TITLE_LABELS = {
    'mod': ('MODS', 'MOD設定', 'MOD 설정', 'MODS', 'MODS', 'MODS', 'MODS', 'MOD', 'MODS', 'MOD 設定', 'МОДЫ'),
    'exit': ('QUIT GAME', 'ゲーム終了', '게임 종료', 'SALIR', 'SAIR', 'QUITTER', 'BEENDEN', 'ESCI', 'QUIT GAME', '結束遊戲', 'ВЫХОД'),
}
PAGE_ROWS = 9
LIST_X, LIST_Y, LIST_W, ROW_PITCH = 20, 132, 760, 56
DETAIL_X, DETAIL_W = 792, 468

TEXT = {
    'row': ('MOD 設定', 'MOD 设置', 'MOD設定', 'MODS'),
    'title': ('MOD 管理', 'MOD 管理', 'MOD 管理', 'MOD MANAGER'),
    'on': ('啟用', '启用', 'ON', 'ON'), 'off': ('停用', '停用', 'OFF', 'OFF'),
    'loaded': ('已載入', '已载入', '読込済み', 'LOADED'),
    'skipped': ('已跳過', '已跳过', 'スキップ', 'SKIPPED'),
    'disabled': ('未啟用', '未启用', '無効', 'DISABLED'),
    'missing': ('未安裝', '未安装', '未インストール', 'NOT INSTALLED'),
    'invalid': ('格式錯誤', '格式错误', '形式エラー', 'INVALID'),
    'pending_on': ('重新啟動後啟用', '重启后启用', '再起動後に有効', 'ON AFTER RESTART'),
    'pending_off': ('重新啟動後停用', '重启后停用', '再起動後に無効', 'OFF AFTER RESTART'),
    'restart_notice': ('變更將在重新啟動遊戲後生效', '更改将在重新启动游戏后生效', '変更はゲームの再起動後に反映されます',
                       'Changes take effect after restarting the game'),
    'disable_all': ('全部停用', '全部停用', 'すべて無効', 'DISABLE ALL'),
    'empty': ('尚未安裝任何 MOD。把 MOD 資料夾放入下列位置後重新啟動遊戲：',
              '尚未安装任何 MOD。将 MOD 文件夹放入以下位置后重新启动游戏：',
              'MOD がインストールされていません。次のフォルダーに入れてゲームを再起動してください：',
              'No mods installed. Put mod folders here and restart the game:'),
    'order': ('載入順序 {}', '加载顺序 {}', '読込順 {}', 'LOAD ORDER {}'),
    'page': ('{} / {}', '{} / {}', '{} / {}', '{} / {}'),
    'version': ('版本', '版本', 'バージョン', 'Version'),
    'author': ('作者', '作者', '作者', 'Author'),
    'license': ('授權', '许可', 'ライセンス', 'License'),
    'folder': ('資料夾', '文件夹', 'フォルダー', 'Folder'),
    'content': ('內容', '内容', '内容', 'Content'),
    'content_value': ('單位 {} 個・數值修改 {} 項', '单位 {} 个 · 数值修改 {} 项', 'ユニット {}・数値変更 {}',
                      '{} units · {} value patches'),
    'campaign_value': ('世界 {} 個・關卡 {} 個・戰場 {} 個・音樂 {} 首', '世界 {} 个 · 关卡 {} 个 · 战场 {} 个 · 音乐 {} 首',
                       'ワールド {}・ステージ {}・戦場 {}・音楽 {}', '{} worlds · {} stages · {} battlefields · {} music'),
    'sounds_value': ('音效 {} 個', '音效 {} 个', '効果音 {}', '{} sounds'),
    'events_value': ('EVENT {} 個', 'EVENT {} 个', 'EVENT {}', '{} events'),
    'game_version': ('需要遊戲版本', '需要游戏版本', '必要なゲームバージョン', 'Game version'),
    'depends': ('依賴', '依赖', '依存', 'Requires'),
    'conflicts': ('衝突', '冲突', '競合', 'Conflicts'),
    'none': ('無', '无', 'なし', 'none'),
    'description': ('說明', '说明', '説明', 'Description'),
    'problems': ('問題', '问题', '問題', 'Problems'),
    'warn_dep_off': ('依賴的 MOD「{}」未啟用', '依赖的 MOD“{}”未启用', '依存 MOD「{}」が無効です', 'Required mod "{}" is not enabled'),
    'warn_dep_order': ('依賴的 MOD「{}」須排在本 MOD 之前', '依赖的 MOD“{}”须排在本 MOD 之前',
                       '依存 MOD「{}」を先に読み込む必要があります', 'Required mod "{}" must load earlier'),
    'warn_conflict': ('與已啟用的 MOD「{}」衝突', '与已启用的 MOD“{}”冲突', '有効な MOD「{}」と競合します',
                      'Conflicts with enabled mod "{}"'),
    'overridden': ('{} 項數值被後載入的 MOD 改寫', '{} 项数值被后加载的 MOD 改写', '{} 件の数値が後の MOD に上書きされています',
                   '{} values overridden by later mods'),
    'hint': ('點擊名稱查看詳情・▲▼ 調整載入順序（後載入者的數值修改優先）・Esc 返回',
             '点击名称查看详情 · ▲▼ 调整加载顺序（后加载者的数值修改优先）· Esc 返回',
             '名前をクリックで詳細・▲▼ で読込順を変更（後に読み込んだ MOD の数値が優先）・Esc で戻る',
             'Click a name for details · ▲▼ load order (later mods win value conflicts) · Esc to return'),
}
STATE_COLORS = {'loaded': (140, 230, 140, 255), 'skipped': RED, 'invalid': RED, 'missing': RED,
                'disabled': GRAY, 'pending_on': GOLD, 'pending_off': GOLD}


def tr(p, key, *args):
    text = TEXT[key][('ZT', 'ZS', 'JP', 'EN').index(lang(p))]
    return text.format(*args) if args else text


def localized(p, value, fallback=''):
    """模组清单的多语言文字（语言代码 → 文字）；按游戏语言、英语、首项依次选取。"""
    if isinstance(value, str):
        return value
    if not isinstance(value, dict) or not value:
        return fallback
    for code in (lang(p), 'EN'):
        if value.get(code):
            return value[code]
    return next(iter(value.values()))


class ModPage:
    def __init__(self, p, lab, root):
        import mod_loader
        self.p, self.lab, self.root = p, lab, root
        self.skin = Skin(lab)
        self.open = False
        self.revision = 0
        self.page = 0
        self.selected = None
        self.pressed = self.pressed_rect = None
        self.pointer_inside = False
        self.hitboxes, self.icons = [], {}
        self.overlay = self.press_overlay = None
        self.font = None
        self.rendered = None
        self.half_images, self.strings = {}, {}
        self.table_written = False
        self.exit_task = self.exit_entry = 0
        self.exit_text_language = self.exit_text_generation = None
        # 标题 OPTION 扩展需要核心 r40（audio_options.cpp 的 MOD 请求与文字重建计数，lab_hooks.cpp 的按 x 匹配替换）。
        version = getattr(p.uc.lib, 'msd_title_option_extension_version', None)
        self.extension = bool(version and version() == 1)
        if self.extension:
            p.put(TOPT, TOPT_MAGIC)
        self.mod_request = p.word(TOPT + 4)
        # 启动时生效的启用列表（社区内容已按它加载）；与当前选择不同时提示重启。
        try:
            self.startup = mod_loader.read_enabled()
        except (OSError, ValueError):
            self.startup = []
        self.pending = list(self.startup)

    # ---------- 标题 OPTION 面板（原生面板） ----------
    def title_label(self, name, language):
        labels = TITLE_LABELS[name]
        return labels[language] if 0 <= language < len(labels) else labels[0]

    def title_scene(self):
        """标题画面上下文：标题 OPTION 图标任务（app+0x336c，GT_TitleOption）存在。语言窗口等弹窗（场景 120）
        覆盖在标题画面上时同样成立，OPTION 面板仍在后面绘制，需继续维持布局与半宽框。"""
        p = self.p
        app = p.app_instance()
        if not app:
            return 0
        icon = p.word(app + 0x336c)
        return app if icon and p.word(icon) == p.symbols['_ZN7AppMain14GT_TitleOptionEP17GENERAL_TASK_BASE'] else 0

    def title_option(self):
        app = self.title_scene()
        if not app or self.p.word(app + 0x22bc) != 20:
            return 0
        task = self.p.word(app + 0x3388)
        if task and self.p.word(task) == self.p.symbols['_ZN7AppMain14GT_TitleOptionEP17GENERAL_TASK_BASE']:
            return app
        return 0

    def half_image(self, rect):
        """半宽按钮框：原生框左 80 像素 + 右端 12 像素，转为原生 Image（缓存）。"""
        if rect not in self.half_images:
            import probe as probe_module
            from pathlib import Path
            from PIL import Image
            from lab_versus import create_native_image
            raw = (Path(probe_module.RESOURCE_ROOT) / 'com.snkplaymore.android003' / 'menuparts.obm').read_bytes()
            w, h = struct.unpack_from('<HH', raw, 4)
            atlas = Image.frombytes('RGBA', (w, h), raw[8:8 + w * h * 4])
            x, y, fw, fh = rect
            src = atlas.crop((x, y, x + fw, y + fh))
            half = Image.new('RGBA', (HALF_W, fh), (0, 0, 0, 0))
            half.paste(src.crop((0, 0, HALF_W - CAP, fh)), (0, 0))
            half.paste(src.crop((fw - CAP, 0, fw, fh)), (HALF_W - CAP, 0))
            self.half_images[rect] = create_native_image(self.p, half)
        return self.half_images[rect]

    def write_table(self, enable):
        """半宽按钮框的 drawConv 替换（按 x 匹配，匹配图像写 1）；标题场景中保持，离开时清除。"""
        p = self.p
        if not enable:
            if self.table_written:
                p.put(VS_TABLE, 0)
                self.table_written = False
            return
        if self.table_written and p.word(VS_TABLE) == VS_MAGIC:
            return
        entries = []
        for conv, rect in ((FRAME_CONV, FRAME_RECT), (PRESS_CONV, PRESS_RECT)):
            image = self.half_image(rect)
            for x in (LEFT_X, RIGHT_X):
                # 新转换项：92×23，锚点 x −49（2 倍绘制即向右 98 像素），纵向锚点沿用原生 0。
                entries.append((conv, 1, image, struct.unpack('<I', struct.pack('<f', x))[0],
                                (0, 0, HALF_W, rect[3], -(190 - HALF_W) // 2, 0, 0, 0)))
        for i, (conv, want, image, xbits, rect) in enumerate(entries):
            e = VS_TABLE + 0x10 + i * 32
            p.put(e, conv)
            p.put(e + 4, want)
            p.put(e + 8, image)
            p.put(e + 12, xbits)
            p.write(e + 16, struct.pack('<8h', *rect))
        p.put(VS_TABLE + 4, len(entries))
        p.put(VS_TABLE, VS_MAGIC)
        self.table_written = True

    def ensure_exit_panel(self, app):
        """以“關閉”行的原生表项另建一个面板（退出游戏）。返回任务地址或 0。"""
        p = self.p
        slot = app + 0x3360 + EXIT_SLOT * 4
        task = p.word(slot)
        if self.exit_task and task == self.exit_task:
            return task
        if self.exit_task:                                     # 场景结束时已被 deleteMenuTask 释放
            self.exit_task = 0
            p.put(TOPT + 8, 0)
        close = p.word(app + 0x33a8)
        if task or not close or p.word(close) != p.symbols['_ZN7AppMain13GT_PausePanelEP17GENERAL_TASK_BASE']:
            return 0
        table = (p.word(0x10218738) + 0x102184a0) & 0xffffffff  # SC_TitleInit 传给 createMenuTask 的表（28 项，每项 0x38 字节）
        entry = bytearray(p.read(table + CLOSE_ENTRY * 0x38, 0x38))
        if struct.unpack_from('<I', entry, 0)[0] != 18:
            p.log('MOD_TITLE_TABLE_UNEXPECTED', entry.hex())
            return 0
        struct.pack_into('<I', entry, 0, EXIT_SLOT)
        struct.pack_into('<ii', entry, 0x10, int(FULL_X), int(ROW_Y[4]))
        if not self.exit_entry:
            self.exit_entry = p.alloc(0x38)
        p.write(self.exit_entry, bytes(entry))
        p.call('_ZN7AppMain14createMenuTaskEPP17GENERAL_TASK_BASEPNS_10_MENU_TASKEi', app, app + 0x3360, self.exit_entry, 1)
        task = p.word(slot)
        if not task:
            return 0
        p.put(task + 0x1b8, p.word(app + 0x338c))           # 与其他面板同一父容器（入场位移与输入许可）
        self.exit_task = task
        p.put(TOPT + 8, task)
        self.exit_text_language = None
        p.log('MOD_TITLE_EXIT_PANEL', hex(task))
        return task

    def set_exit_text(self, app, task):
        """退出面板文字：原生 TexString（app+0x3238）追加字符串，字形与其他面板相同。原生重建文字后（计数变化）重新追加。"""
        p = self.p
        language = p.word(app + 0x3d64)
        generation = p.word(TOPT + 12)
        if self.exit_text_language == language and self.exit_text_generation == generation:
            return
        text = self.title_label('exit', language)
        if text not in self.strings:
            self.strings[text] = p.cstr(text)
        p.call('_ZN9TexString13setStringCharEPKcPiP4Fontb', p.word(app + 0x3238), self.strings[text], task + 0x1f8,
               p.word(app + 0x60), 0)
        p.put(task + 0x7c, p.word(task + 0x7c) & ~0xa0)
        self.exit_text_language, self.exit_text_generation = language, generation

    def layout(self, app):
        """六行布局：位置、点击区域；第 4 行面板恢复为原生 GT_PausePanel。"""
        from probe import u32f
        p = self.p
        panel = p.symbols['_ZN7AppMain13GT_PausePanelEP17GENERAL_TASK_BASE']
        blank = p.symbols['_ZN7AppMain8GT_BlankEP17GENERAL_TASK_BASE']
        mod_task = p.word(app + 0x33a4)
        if mod_task and p.word(mod_task) == blank:
            p.call('_ZN13CTaskSystem2D6ChangeEPFiP17GENERAL_TASK_BASEES1_', panel, mod_task)
        for offset, x, row, hit in LAYOUT:
            task = self.exit_task if offset is None else p.word(app + offset)
            if not task:
                continue
            p.put(task + 0x84, u32f(x))
            p.put(task + 0x88, u32f(ROW_Y[row]))
            for i, v in enumerate(hit):
                p.put(task + 0xf4 + i * 4, u32f(v))

    def title_frame(self):
        """每帧（原生步进前后各一次）：标题场景中维护六行原生面板；处理 MOD 请求与退出。"""
        p = self.p
        app = self.title_scene()
        if not app or not self.extension:
            self.write_table(False)
            if self.exit_task and (not app or p.word(app + 0x3360 + EXIT_SLOT * 4) != self.exit_task):
                self.exit_task = 0                             # 面板已随场景结束释放
                p.put(TOPT + 8, 0)
            return
        if not p.word(app + 0x33a8):
            return                                             # 面板尚未建立（标题初始化中）
        task = self.ensure_exit_panel(app)
        self.layout(app)
        self.write_table(True)
        if task:
            self.set_exit_text(app, task)
            if p.word(task + 0x194):                           # 原生 PushPanel 的选中结果（抬起于面板内）
                p.call('_ZN7AppMain16ClearSelectPanelEP17GENERAL_TASK_BASEi', app, task, 0)
                play_se(p, SE_DECIDE)
                p.log('MOD_TITLE_EXIT', p.frame)
                if p.stop_event is not None:
                    p.stop_event.set()                         # 与标题 Esc（showEndDialogView）相同：按关闭窗口流程结束
        request = p.word(TOPT + 4)
        if request != self.mod_request:
            self.mod_request = request
            if self.title_option():
                self.set_open(True)

    # ---------- 数据 ----------
    def entries(self):
        """[(模组 id, 信息)]：已安装的模组（重新读取清单）与启用列表中未安装的模组；启用者按加载顺序在前。"""
        import mod_loader
        import behaviors
        import branding
        p = self.p
        game_root = self.root
        startup = {s['id']: s for s in getattr(getattr(p, 'community', None), 'mod_status', []) if s.get('id')}
        found = {}
        folder_root = mod_loader.mods_dir(game_root)
        if folder_root.is_dir():
            version = branding.load(game_root)['display_version']
            library = behaviors.load_library()[0]['library_version']
            for folder in sorted(f for f in folder_root.iterdir() if f.is_dir() and (f / 'mod.json').is_file()):
                mod = mod_loader.read_mod(folder, version, library)
                info = mod.status()
                key = mod.id or ('?' + folder.name)
                if key in found:
                    continue
                found[key] = info
        result = []
        for mod_id in self.pending:
            info = found.pop(mod_id, None)
            result.append((mod_id, info, startup.get(mod_id)))
        for mod_id in sorted(found):
            result.append((mod_id, found[mod_id], startup.get(mod_id)))
        return result

    def state(self, mod_id, info, startup):
        enabled = mod_id in self.pending
        if info is None:
            return 'missing'
        if info['state'] == 'skipped':
            return 'invalid'
        was = startup['state'] if startup else 'disabled'
        if enabled and was == 'loaded':
            return 'loaded'
        if enabled and was == 'skipped' and mod_id in self.startup:
            return 'skipped'
        if enabled:
            return 'pending_on'
        if was == 'loaded':
            return 'pending_off'
        return 'disabled'

    def warnings(self, mod_id, info):
        """按当前选择预判的依赖与冲突问题（重启后加载器会据此跳过模组）。"""
        if info is None or mod_id not in self.pending:
            return []
        out = []
        for dep in info.get('depends') or []:
            if dep not in self.pending:
                out.append(tr(self.p, 'warn_dep_off', dep))
            elif self.pending.index(dep) > self.pending.index(mod_id):
                out.append(tr(self.p, 'warn_dep_order', dep))
        for other in info.get('conflicts') or []:
            if other in self.pending:
                out.append(tr(self.p, 'warn_conflict', other))
        return out

    def overridden(self, mod_id):
        """该模组的数值修改中，被后加载模组改写的字段数（按启动时已加载的补丁记录）。"""
        patches = getattr(getattr(self.p, 'community', None), 'mod_patches', [])
        count = 0
        for index, entry in enumerate(patches):
            if entry['mod'] == mod_id and any(e['target'] == entry['target'] and e['field'] == entry['field']
                                              and e['mod'] != mod_id for e in patches[index + 1:]):
                count += 1
        return count

    def save(self):
        import mod_loader
        try:
            mod_loader.write_enabled(self.pending)
            self.p.log('MOD_PAGE_ENABLED', self.pending)
        except (OSError, RuntimeError) as error:
            self.p.log('MOD_PAGE_WRITE_ERROR', type(error).__name__, str(error))

    # ---------- 打开、关闭与命令 ----------
    def set_open(self, value):
        import mod_loader
        if value and not self.open:
            try:
                self.pending = mod_loader.read_enabled()
            except (OSError, ValueError):
                self.pending = []
            self.open, self.page, self.selected = True, 0, None
        elif not value:
            self.open = False
        self.pressed = None
        self.revision += 1

    def command(self, name, *args):
        if name == 'close':
            self.set_open(False)
            return
        if name == 'select':
            self.selected = args[0]
        elif name == 'toggle':
            mod_id = args[0]
            if mod_id in self.pending:
                self.pending.remove(mod_id)
            else:
                self.pending.append(mod_id)
            self.selected = mod_id
            self.save()
        elif name in ('up', 'down'):
            mod_id = args[0]
            i = self.pending.index(mod_id)
            j = i - 1 if name == 'up' else i + 1
            if 0 <= j < len(self.pending):
                self.pending[i], self.pending[j] = self.pending[j], self.pending[i]
                self.save()
            self.selected = mod_id
        elif name == 'disable_all':
            if self.pending:
                self.pending = []
                self.save()
        elif name == 'page':
            self.page += args[0]
        self.revision += 1

    # ---------- 输入 ----------
    def touch(self, action, x, y):
        """返回 True 表示触点已由本模块处理。页面打开时拦截全部触点；其余（含 OPTION 面板）交给原生。"""
        if self.open:
            hit = rect = None
            for box, command in reversed(self.hitboxes):
                left, top, w, h = box
                if left <= x < left + w and top <= y < top + h:
                    hit, rect = command, box
                    break
            if action == 1:
                self.pressed, self.pressed_rect, self.pointer_inside = hit, rect, hit is not None
            elif action == 5:
                self.pointer_inside = self.pressed is not None and hit == self.pressed
            elif action == 3:
                pressed, self.pressed = self.pressed, None
                if hit is not None and hit == pressed:
                    play_se(self.p, SE_CLOSE if hit[0] == 'close' else SE_DECIDE)
                    self.command(*hit)
            return True
        return False

    def back(self):
        if not self.open:
            return False
        play_se(self.p, SE_CLOSE)
        self.set_open(False)
        return True

    # ---------- 帧 ----------
    def prepare_frame(self):
        self.title_frame()

    def draw(self):
        self.title_frame()
        if not self.open:
            return
        if self.title_option() == 0:
            self.set_open(False)            # 离开标题 OPTION（例如画面切换）时关闭
            return
        if self.overlay is None:
            from trial_overlay import SurfaceOverlay
            self.overlay = SurfaceOverlay(self.p.graphics)
            self.font = self.font or fonts()
        key = ('mod_page', self.revision, lang(self.p))
        image = None
        if self.overlay.cached != key:
            image = self.skin.tiled(BRICK, W, H).copy()
            self.c = Canvas(image, self.skin, self.font, None)
            self.render()
            self.hitboxes, self.icons, self.rendered = self.c.hitboxes, self.c.icons, image
        self.overlay.draw_image(image, key, (0, 0, W, H))
        self.draw_press()

    def draw_press(self):
        command = self.pressed if self.pointer_inside else None
        if command is None or self.rendered is None:
            return
        if self.press_overlay is None:
            from trial_overlay import SurfaceOverlay
            self.press_overlay = SurfaceOverlay(self.p.graphics)
        if command in self.icons:
            x, y, name = self.icons[command]
            press_key = ('mod_icon', self.revision, command)
            part = None
            if self.press_overlay.cached != press_key:
                part, (left, top) = icon_press_image(self.skin, self.rendered, x, y, name)
                self.icon_rect = (left, top, part.width, part.height)
            self.press_overlay.draw_image(part, press_key, self.icon_rect)
            return
        x, y, w, h = self.pressed_rect
        press_key = ('mod_press', self.revision, self.pressed_rect)
        part = None
        if self.press_overlay.cached != press_key:
            part = self.skin.darken(self.rendered.crop((x, y, x + w, y + h)), cache=False)
        self.press_overlay.draw_image(part, press_key, (x, y + 2, w, h))

    # ---------- 绘制 ----------
    def wrap(self, text, size, width):
        face = self.c.face(text)(size)
        lines, line = [], ''
        for ch in text:
            if ch == '\n' or face.getlength(line + ch) > width:
                lines.append(line)
                line = '' if ch == '\n' else ch
            else:
                line += ch
        if line:
            lines.append(line)
        return lines

    def render(self):
        from lab_prep import ICON_W, ICON_Y
        p, c = self.p, self.c
        c.header(tr(p, 'title'))
        c.icon_button((W - 12 - ICON_W, ICON_Y), 'back', ('close',))
        entries = self.entries()
        if self.pending != self.startup:
            c.text((W - 24 - ICON_W - 12, ICON_Y + 36), tr(p, 'restart_notice'), 18, GOLD, 'rm', 2, 600)
        if not entries:
            import mod_loader
            c.panel((LIST_X, LIST_Y, W - 2 * LIST_X, 160))
            c.text((LIST_X + 24, LIST_Y + 50), tr(p, 'empty'), 18, WHITE, 'lm', 2, W - 2 * LIST_X - 48)
            c.text((LIST_X + 24, LIST_Y + 96), str(mod_loader.mods_dir(self.root)), 16, GOLD, 'lm', 2, W - 2 * LIST_X - 48)
            return
        pages = max(1, (len(entries) + PAGE_ROWS - 1) // PAGE_ROWS)
        self.page = min(max(self.page, 0), pages - 1)
        if self.selected is None or all(e[0] != self.selected for e in entries):
            self.selected = entries[0][0]
        c.panel((LIST_X - 6, LIST_Y - 6, LIST_W + 12, PAGE_ROWS * ROW_PITCH + 12))
        for row, (mod_id, info, startup) in enumerate(entries[self.page * PAGE_ROWS:(self.page + 1) * PAGE_ROWS]):
            self.draw_entry(row, mod_id, info, startup)
        bottom = LIST_Y + PAGE_ROWS * ROW_PITCH + 14
        c.button((LIST_X, bottom, 160, 34), tr(p, 'disable_all'), ('disable_all',), 16, 'off')
        if pages > 1:
            if self.page > 0:
                c.button((LIST_X + LIST_W - 300, bottom, 100, 34), T(p, 'prev'), ('page', -1), 16)
            c.text((LIST_X + LIST_W - 150, bottom + 17), tr(p, 'page', self.page + 1, pages), 16, WHITE, 'mm', 2, 90)
            if self.page < pages - 1:
                c.button((LIST_X + LIST_W - 100, bottom, 100, 34), T(p, 'next'), ('page', 1), 16)
        c.text((W // 2, H - 12), tr(p, 'hint'), 12, GRAY, 'mm', 1, W - 40)
        selected = next(e for e in entries if e[0] == self.selected)
        self.draw_detail(*selected)

    def draw_entry(self, row, mod_id, info, startup):
        p, c = self.p, self.c
        x, y = LIST_X, LIST_Y + row * ROW_PITCH
        enabled = mod_id in self.pending
        selected = mod_id == self.selected
        c.button((x, y + 4, LIST_W, ROW_PITCH - 8), '', ('select', mod_id), 16, 'light' if selected else 'normal')
        c.button((x + 8, y + 10, 78, ROW_PITCH - 20), tr(p, 'on' if enabled else 'off'), ('toggle', mod_id), 15,
                 'on' if enabled else 'off')
        name = localized(p, (info or {}).get('name'), mod_id)
        ink = (40, 30, 20, 255) if selected else WHITE
        c.text((x + 100, y + 20), name, 18, ink, 'lm', 0 if selected else 2, 330)
        sub = ' · '.join(v for v in ((('v' + info['version']) if info and info.get('version') else ''),
                                     (info or {}).get('author') or '', mod_id) if v)
        c.text((x + 100, y + 40), sub, 12, (90, 70, 50, 255) if selected else GRAY, 'lm', 0 if selected else 1, 330)
        state = self.state(mod_id, info, startup)
        c.text((x + 560, y + ROW_PITCH / 2), tr(p, state), 15, STATE_COLORS[state], 'mm', 2, 170)
        if enabled:
            order = self.pending.index(mod_id)
            if order > 0:
                c.button((x + LIST_W - 84, y + 10, 36, ROW_PITCH - 20), '▲', ('up', mod_id), 14)
            if order < len(self.pending) - 1:
                c.button((x + LIST_W - 44, y + 10, 36, ROW_PITCH - 20), '▼', ('down', mod_id), 14)

    def draw_detail(self, mod_id, info, startup):
        p, c = self.p, self.c
        x, y, w = DETAIL_X, LIST_Y - 6, DETAIL_W
        height = PAGE_ROWS * ROW_PITCH + 12
        name = localized(p, (info or {}).get('name'), mod_id)
        c.panel((x, y, w, height), name)
        info = info or {}
        lines = []
        if mod_id in self.pending:
            lines.append((tr(p, 'order', self.pending.index(mod_id) + 1), BLUE))
        for label, value in (('version', info.get('version')), ('author', info.get('author')),
                             ('license', info.get('license')), ('folder', info.get('folder'))):
            if value:
                lines.append((f'{tr(p, label)}：{value}', WHITE))
        if info:
            lines.append((f"{tr(p, 'content')}：{tr(p, 'content_value', len(info.get('units') or []), info.get('patches') or 0)}", WHITE))
            campaign = info.get('campaign')
            if campaign:
                lines.append((f"{tr(p, 'content')}：{tr(p, 'campaign_value', campaign['worlds'], campaign['stages'], campaign['scenes'], campaign['music'])}", WHITE))
            if info.get('sounds'):
                lines.append((f"{tr(p, 'content')}：{tr(p, 'sounds_value', info['sounds'])}", WHITE))
            if info.get('events'):
                lines.append((f"{tr(p, 'content')}：{tr(p, 'events_value', info['events'])}", WHITE))
        if info.get('game_version'):
            lines.append((f"{tr(p, 'game_version')}：{info['game_version']}", WHITE))
        lines.append((f"{tr(p, 'depends')}：{', '.join(info.get('depends') or []) or tr(p, 'none')}", WHITE))
        lines.append((f"{tr(p, 'conflicts')}：{', '.join(info.get('conflicts') or []) or tr(p, 'none')}", WHITE))
        overridden = self.overridden(mod_id)
        if overridden:
            lines.append((tr(p, 'overridden', overridden), GOLD))
        problems = list(info.get('reasons') or [])
        if startup and startup.get('reasons') and mod_id in self.startup:
            problems += [r for r in startup['reasons'] if r not in problems]
        if info is None or not info:
            problems.append('enabled but not installed')
        problems += self.warnings(mod_id, info or None)
        cy = y + 44
        for text, color in lines:
            for line in self.wrap(text, 15, w - 32):
                c.text((x + 16, cy), line, 15, color, 'lm', 2, w - 32)
                cy += 22
        description = localized(p, info.get('description'))
        if description:
            cy += 6
            c.text((x + 16, cy), tr(p, 'description'), 15, GOLD, 'lm', 2, w - 32)
            cy += 22
            for line in self.wrap(description, 14, w - 32)[:8]:
                c.text((x + 16, cy), line, 14, WHITE, 'lm', 2, w - 32)
                cy += 20
        if problems:
            cy += 6
            c.text((x + 16, cy), tr(p, 'problems'), 15, RED, 'lm', 2, w - 32)
            cy += 22
            for problem in problems:
                for line in self.wrap(problem, 13, w - 32):
                    if cy > y + height - 14:
                        return
                    c.text((x + 16, cy), line, 13, RED, 'lm', 1, w - 32)
                    cy += 19

    def close(self):
        for overlay in (self.overlay, self.press_overlay):
            if overlay is not None:
                overlay.close()
        self.overlay = self.press_overlay = None
