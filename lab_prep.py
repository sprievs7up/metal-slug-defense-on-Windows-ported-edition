"""LAB 准备界面（T8）：宿主自绘的独立全屏界面（砖墙背景、MISSION BGM），F7 经闸门进入，
开始战斗时经闸门进入战斗，战斗结束后经原生闸门回到本界面；退出时回到原生主菜单（出击 / 强化 / Wi-Fi 对战）。

内容：我方/敌方牌组（各 10 格，点格子选单位，±调整等级，一括等级、据点初始等级、复制对方、随机编队、清空）、
地图（原生地图 1–3 与里地图 1–3 的全部小关，按世界与小关选择，上方为原生缩略图，见 lab_stages.py）、
完全控制与四个 AI 开关、优势设定（原生关卡强化级数，生命/攻击各 +20%/级）、预设 A/B/C（lab_presets/）
与战斗履历（lab_presets/history.jsonl）。全部设定保存到 lab_config.json；战斗使用的牌组与等级直接交给
BattleController::entryUnit，不写存档。界面文字随游戏语言（lab_ui.TEXT）。
"""
import random

from lab_ui import (W, H, WHITE, GOLD, GRAY, DARK, BLUE, RED, BRICK, CELLS, TAB_ON, TAB_OFF, ROW_STYLES, HEADER_H,
                    BUTTONS, ICON_SCALE, HEADER_DARK, TIER_COLORS, SE_DECIDE, SE_CLOSE, BGM_MISSION, BGM_MENU, T, current_bgm,
                    Canvas, Skin, Shutter, fonts, icon_press_image, readable, play_se, play_bgm)

CELL, CELL_GAP = 100, 10                          # 编组格（unit.obm 50×50 原图 2 倍）
DECK_W = 10 * CELL + 9 * CELL_GAP
DECK_X = (W - DECK_W) // 2
DECK_TOP, DECK_PITCH = HEADER_H + 8, 160          # 每行：标题与按钮 26、格子 100、等级 28
PANEL_TOP = DECK_TOP + 2 * DECK_PITCH + 6
PANEL_H = H - PANEL_TOP - 24
PICK_CELL, PICK_PITCH, PICK_COLS, PICK_ROWS = 75, 100, 12, 4
KEY_LABELS = {'LEFT': '←', 'RIGHT': '→', 'UP': '↑', 'DOWN': '↓', 'COMMA': ',', 'PERIOD': '.', 'SLASH': '/',
              'SEMICOLON': ';', 'APOSTROPHE': "'", 'LEFT_BRACKET': '[', 'RIGHT_BRACKET': ']', 'BACKSLASH': '\\',
              'MINUS': '-', 'EQUAL': '=', 'GRAVE_ACCENT': '`', 'SPACE': 'SPACE', 'ENTER': 'ENTER',
              'LEFT_SHIFT': 'L SHIFT', 'RIGHT_SHIFT': 'R SHIFT', 'LEFT_CONTROL': 'L CTRL', 'RIGHT_CONTROL': 'R CTRL',
              'LEFT_ALT': 'L ALT', 'RIGHT_ALT': 'R ALT', 'LEFT_SUPER': 'WIN', 'RIGHT_SUPER': 'WIN', 'PRINT_SCREEN': 'PRTSC',
              'CAPS_LOCK': 'CAPS', 'BACKSPACE': 'BKSP', 'PAGE_UP': 'PGUP', 'PAGE_DOWN': 'PGDN'}


def key_label(name):
    """GLFW 键名（KEY_ 之后部分）的显示文字。"""
    name = str(name).upper()
    if name in KEY_LABELS:
        return KEY_LABELS[name]
    if name.startswith('KP_'):
        return 'NUM' + key_label(name[3:])
    return name
PICK_X = (W - PICK_COLS * PICK_PITCH) // 2 + (PICK_PITCH - PICK_CELL) // 2
PICK_TABS_Y = HEADER_H + 8
FALLBACK_LANGUAGE = 3
ADVANTAGE_MAX = 10                                # 原生强化级数：每级生命/攻击 +20%
THUMB_SCALE = 2                                   # 原生缩略图 128×56，整数倍最近邻放大
SCENE_MAIN_MENU, SCENE_MAIN_MENU_INIT, MAIN_MENU_IDLE = 28, 27, 1
MENU_RETURN_PANEL = 0xb168                        # 主菜单返回时进入的子画面
# GetUnitAffiliation：0 正规军 1 叛军 2 普特曼军 3 火星人与僵尸 4 其他 5 联动（依各阵营成员核对）
TABS = (('tab_all', None), ('tab_community', 'community'), ('f0', 0), ('f1', 1), ('f2', 2),
        ('f3', 3), ('f4', 4), ('f5', 5))
BACK_COMMANDS = ('close', 'back')
ICON_W, ICON_H = round(60 * ICON_SCALE), round(48 * ICON_SCALE)     # 顶栏图标按钮 90×72
# 青色框（66×54，锚点 3,3）在顶栏深色区内垂直居中，按钮随之定位。
ICON_FRAME_H = round(54 * ICON_SCALE)
ICON_Y = HEADER_DARK[0] + (HEADER_DARK[1] - HEADER_DARK[0] - ICON_FRAME_H) // 2 + round(3 * ICON_SCALE)
TIER_PLATE = BUTTONS['normal']                                      # 段位名底板：原生棕色按钮压暗
TIER_PLATE_DIM = 0.45


def desaturate(rgb, keep=0.15, dim=0.55):
    """保留 15% 饱和度并压暗至 55% 亮度的段位色（AI 关闭时的色带）。"""
    grey = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    return tuple(round((grey + (c - grey) * keep) * dim) for c in rgb)


class LabPrep:
    def __init__(self, lab):
        self.lab = lab
        self.open = False
        self.page = 'main'               # main / picker / history / keys / help
        self.capture = None              # 按键设定等待中的 (玩家 'p1'/'p2', 'key'/'pad', 动作)
        self.picker = None               # (side, slot)
        self.tab = 0
        self.picker_page = 0
        self.level_all = {'player': 40, 'enemy': 40}
        self.revision = 0
        self.overlay = None
        self.font = None
        self.skin = Skin(lab)
        self.shutter = Shutter(lab)
        self.hitboxes = []
        self.units = None
        self.units_language = None
        self.thumbs = {}
        self.pressed = None
        self.pressed_rect = None
        self.pointer_inside = False
        self.lit = None                  # 抬起后保持青色框的图标按钮命令（闸门合拢期间）
        self.icons = {}
        self.press_overlay = None
        self.tier_colors = {}
        self.message = ''
        self.warm_steps = None

    # ---------- 数据 ----------
    def t(self, key, *args):
        """双人对战中“我方 / 敌方”类文字改用 vs_ 前缀的“玩家1 / 玩家2”版本（lab_ui.TEXT）。"""
        from lab_ui import TEXT
        p = self.lab.p
        return T(p, 'vs_' + key, *args) if self.lab.versus and 'vs_' + key in TEXT else T(p, key, *args)

    def unit_list(self):
        """全部可选单位：原版 1–399 与社区可选单位。原生名称带括号或为“-”的条目是内部子单位
        （投放体、箱体、弹头车攻击等，如“(沙包)”“(伞兵)”），与社区 internal_only 一样排除。
        名称取 GetMenuUnitName(uid, 游戏语言)。(uid, 名称, 阵营, 是否社区)
        条目来自单位目录 unit_catalog（按当前游戏语言 app+0x3d64 缓存，语言切换后重新取名）。"""
        p, app = self.lab.p, self.lab.app()
        current = p.word(app + 0x3d64)
        if self.units is None or self.units_language != current:
            self.units_language = current
            from unit_catalog import catalog
            self.units = [(e['uid'], e['name'], e['faction'], e['source'] != 'original') for e in catalog(p).index()]
        return self.units

    def random_pool(self):
        """随机编队的候选：可选单位中具有原生头像的单位（无头像的空单位，如 UID 256、259、265，不进入候选）。"""
        return [u[0] for u in self.unit_list() if self.skin.icon(u[0], 1) is not None]

    def names(self):
        return {uid: name for uid, name, _, _ in self.unit_list()}

    def deck(self, side):
        lab = self.lab
        key = side + '_deck'
        deck = lab.config.get(key)
        if deck is None:
            deck = self.default_deck(side)
            lab.config[key] = deck
        deck = list(deck) + [None] * (10 - len(deck))
        return deck[:10]

    def default_deck(self, side):
        """我方：当前原生牌组；敌方：沿用我方牌组。等级默认 Lv40。"""
        lab = self.lab
        p, app = lab.p, lab.app()
        deck = []
        for slot in range(10):
            uid = p.call('_ZN7AppMain19GetDeckUnitSaveDataEii', app, slot, 0xffffffff)
            deck.append(None if uid in (0, 0xffffffff) or uid & 0x80000000 else [uid, 40])
        return deck

    def resolved(self, side):
        """[(UnitID, 存档等级 0–39) 或 None] × 10，供 Lab.start 使用。"""
        return self.lab.resolve_deck(self.deck(side))

    def uid(self, unit):
        return unit if isinstance(unit, int) else self.lab.community_uid(unit)

    def set_deck(self, side, deck):
        self.lab.config[side + '_deck'] = deck
        self.changed()

    def changed(self):
        self.lab.save_config()
        self.revision += 1

    def stage_position(self):
        """(世界列表, 世界序号, 小关序号)；配置中的 StageID 不在目录内时取地图 1 第一关。"""
        catalog = self.lab.stage_catalog()
        worlds = catalog.load()
        wi, si = catalog.locate(int(self.lab.config.get('stage_id', 0)))
        return worlds, wi, si

    def set_stage(self, world_index, stage_index):
        worlds, _, _ = self.stage_position()
        if not worlds:
            return
        world_index %= len(worlds)
        stages = worlds[world_index][1]
        self.lab.config['stage_id'] = stages[stage_index % len(stages)]['id']
        self.changed()

    def thumbnail(self, entry):
        key = (self.lab.stages.language, entry['id'])    # 缩略图文件按语言取自 ImageDataInfo 表
        if key not in self.thumbs:
            from PIL import Image
            image = self.lab.stages.thumbnail(self.skin, entry)
            if image is not None:
                image = image.resize((image.width * THUMB_SCALE, image.height * THUMB_SCALE), Image.NEAREST)
            self.thumbs[key] = image
        return self.thumbs[key]

    def warm(self):
        """主菜单空闲时每次调用预热一项首次打开所需的缓存（与打开时调用相同的函数，结果相同），
        把首次打开的一次性开销分散到多个空闲帧。语言改变后各缓存仍按原规则重新读取。"""
        if self.warm_steps is None:
            def thumb():
                worlds, wi, si = self.stage_position()
                if worlds:
                    self.thumbnail(worlds[wi][1][si])
            self.warm_steps = [lambda: self.skin.tiled(BRICK, W, H), self.unit_list,
                               lambda: self.lab.stage_catalog().load(), thumb]
        if self.warm_steps:
            step = self.warm_steps.pop(0)
            try:
                step()
            except Exception as error:
                self.lab.p.log('LAB_PREP_WARM_SKIPPED', type(error).__name__, str(error))

    # ---------- 打开与关闭（闸门） ----------
    def show(self, from_closed=False):
        """显示准备界面并播放 MISSION BGM。from_closed：画面已被闸门遮住（原生战斗结束闸门），直接开闸。"""
        def reveal():
            self.open, self.page, self.pressed, self.lit = True, 'main', None, None
            self.revision += 1
            play_bgm(self.lab.p, BGM_MISSION)
            self.shutter.open()
        if from_closed:
            reveal()                     # 原生闸门已合拢：直接以原生开闸任务打开
        else:
            self.shutter.close(reveal)

    def hide(self):
        """退出 LAB：闸门合拢后关闭准备界面并回到原生主菜单（出击 / 强化 / Wi-Fi 对战）。
        已在主菜单稳态（场景 28、子状态 1）时直接恢复主菜单 BGM 并开闸；其他界面（CUSTOMIZE、SHOP、OPTION、
        地图等）按 lab.leave 的方式结束当前场景并进入主菜单初始化（场景 27），由 SC_MainMenuInit 的
        SetShutterOpen 开闸，SC_MainMenuLoop 在闸门结束后请求主菜单 BGM。"""
        def leave():
            lab = self.lab
            p, app = lab.p, lab.app()
            self.open = False
            self.revision += 1
            scene, state = p.word(app + 0x22bc), p.word(app + 0x22dc)
            lab.record('prep_exit', scene=scene, state=state)
            if scene == SCENE_MAIN_MENU and state == MAIN_MENU_IDLE:
                play_bgm(p, BGM_MENU)
                self.shutter.open()
                return
            # SC_MainMenuLoop 状态 0 按 app+0xb168 决定初始子画面（1 OPTION、3 CUSTOMIZE、4 SHOP，其余为主菜单），
            # 清零后主菜单初始化进入出击 / 强化 / Wi-Fi 对战的主画面。
            p.put(app + MENU_RETURN_PANEL, 0)
            p.call('_ZN7AppMain12SceneEndFuncEi', app, scene)
            p.call('_ZN7AppMain11ChangeExeSTEi', app, SCENE_MAIN_MENU_INIT)
            self.shutter.release()
        self.shutter.close(leave)

    def set_open(self, value):
        """无动画的开关（启动战斗、测试脚本使用）。"""
        self.open = bool(value)
        self.page, self.pressed, self.lit = 'main', None, None
        self.revision += 1

    def busy(self):
        return self.shutter.state != 'open'

    def hold_bgm(self):
        """准备界面打开期间保持 MISSION BGM。战斗结束后 LAB 回到原生主菜单场景（27→28），
        SC_MainMenuLoop 状态 0 在闸门结束时请求一次主菜单 BGM 101，此处在其后改回 135。
        只在主菜单场景（27/28，准备界面所覆盖的场景）中保持，其他场景的 BGM 由其自身流程决定。"""
        p = self.lab.p
        if p.word(self.lab.app() + 0x22bc) not in (SCENE_MAIN_MENU, SCENE_MAIN_MENU_INIT):
            return
        if current_bgm(p) != BGM_MISSION:
            play_bgm(p, BGM_MISSION)
            self.lab.record('prep_bgm_restore')

    # ---------- 指令 ----------
    def command(self, name, *args):
        lab = self.lab
        if name == 'start':
            try:
                self.resolved('player')
                self.resolved('enemy')
            except ValueError as error:
                self.message = str(error)
                self.revision += 1
                return
            def begin():
                self.set_open(False)
                lab.commands.append(('start',))
                lab.release_shutter_on_battle = True   # 场景进入战斗初始化后交给 SC_BattleInit 的原生开闸
            self.shutter.close(begin)
        elif name == 'close':
            self.hide()
        elif name == 'slot':
            side, slot = args
            self.page, self.picker, self.picker_page = 'picker', (side, slot), 0
        elif name == 'level':
            side, slot, step = args
            deck = self.deck(side)
            if deck[slot] is not None:
                deck[slot] = [deck[slot][0], max(1, min(40, int(deck[slot][1]) + step))]
                self.set_deck(side, deck)
        elif name == 'level_all':
            side, step = args
            self.level_all[side] = max(1, min(40, self.level_all[side] + step))
        elif name == 'apply_all':
            side = args[0]
            self.set_deck(side, [None if e is None else [e[0], self.level_all[side]] for e in self.deck(side)])
        elif name == 'random':
            side = args[0]
            pool = self.random_pool()
            self.set_deck(side, [[uid, self.level_all[side]] for uid in random.sample(pool, min(10, len(pool)))])
        elif name == 'clear':
            self.set_deck(args[0], [None] * 10)
        elif name == 'copy':
            # 复制对方牌组（单位、格位与各格等级）到本方。
            side = args[0]
            other = 'enemy' if side == 'player' else 'player'
            self.set_deck(side, [None if e is None else [e[0], int(e[1])] for e in self.deck(other)])
        elif name == 'base':
            side, step = args
            key = side + '_base_level'
            lab.config[key] = max(0, min(10, int(lab.config.get(key, 0)) + step))
            self.changed()
        elif name == 'advantage':
            key, step = args
            lab.config[key] = max(0, min(ADVANTAGE_MAX, int(lab.config.get(key, 0)) + step))
            self.changed()
        elif name == 'world':
            # 换世界时保留同一区域与小关序号（新世界没有该关时取其第一关）。
            worlds, wi, si = self.stage_position()
            if worlds:
                current = worlds[wi][1][si]
                target = (wi + args[0]) % len(worlds)
                stages = worlds[target][1]
                match = next((i for i, e in enumerate(stages)
                              if (e['area'], e['stage']) == (current['area'], current['stage'])), 0)
                self.set_stage(target, match)
        elif name == 'stage':
            worlds, wi, si = self.stage_position()
            if worlds:
                self.set_stage(wi, si + args[0])
        elif name == 'tier':
            # AI 段位：ROOKIE … PREDATOR，两端不循环（按到底停止）。
            from lab import AI_TIER_NAMES
            side, step = args
            key = side + '_ai_tier'
            current = lab.config.get(key, 'SILVER')
            index = AI_TIER_NAMES.index(current) if current in AI_TIER_NAMES else AI_TIER_NAMES.index('SILVER')
            lab.config[key] = AI_TIER_NAMES[max(0, min(len(AI_TIER_NAMES) - 1, index + step))]
            self.changed()
        elif name == 'cpu_side':
            lab.config['cpu_side'] = args[0] if args[0] in ('p1', 'p2') else 'p1'
            self.changed()
        elif name == 'toggle':
            setattr(lab, args[0], not getattr(lab, args[0]))
            lab.config[args[0]] = getattr(lab, args[0])
            self.changed()
        elif name == 'pick':
            side, slot = self.picker
            uid = args[0]
            deck = self.deck(side)
            if uid is None:
                deck[slot] = None
            else:
                # 同一牌组不能重复编入（原生 entryUnit 会略过重复单位）：已在其他格时两格互换。
                old = deck[slot]
                for other, entry in enumerate(deck):
                    if other != slot and entry is not None and self.uid(entry[0]) == uid:
                        deck[other] = old
                deck[slot] = [uid, old[1] if old else self.level_all[side]]
            self.set_deck(side, deck)
            self.page = 'main'
        elif name == 'tab':
            self.tab, self.picker_page = args[0], 0
        elif name == 'picker_page':
            self.picker_page = max(0, self.picker_page + args[0])
        elif name == 'back':
            self.page, self.capture = 'main', None
        elif name == 'vs_page':
            self.page, self.capture, self.message = args[0], None, ''
        elif name == 'capture':
            side, device, action = args
            self.capture = (side, device, action)
            self.message = T(lab.p, 'vs_capture_' + device, side.upper(), T(lab.p, 'vs_act_' + action))
        elif name == 'keys_reset':
            lab.config['versus_keys'] = None
            lab.config['versus_pad'] = None
            self.capture = None
            self.message = T(lab.p, 'vs_reset_done')
            lab.save_config()
        elif name == 'pad_single':
            lab.config['versus_pad_single'] = 'p1' if lab.config.get('versus_pad_single', 'p2') == 'p2' else 'p2'
            lab.save_config()
        elif name == 'history':
            self.page = 'history'
        elif name == 'preset_save':
            lab.save_preset(args[0])
            self.message = T(lab.p, 'saved', args[0])
        elif name == 'preset_load':
            self.message = T(lab.p, 'loaded' if lab.load_preset(args[0]) else 'preset_empty', args[0])
        self.revision += 1

    def key(self, name, *args):
        if name == 'pads':
            if self.page in ('keys', 'help'):
                self.revision += 1                     # 手柄连接状态变化
            return
        if name in ('bind', 'pad_bind'):
            self.bind(name, args[0])
            return
        if name == 'escape' and not self.busy():
            play_se(self.lab.p, SE_CLOSE)
            if self.capture is not None:
                self.capture, self.message = None, ''
                self.revision += 1
            elif self.page != 'main':
                self.page = 'main'
                self.revision += 1
            else:
                self.hide()

    def bind(self, kind, value):
        """按键设定：校验并保存一次指定（同一玩家内已占用时两项互换，保留键拒绝并保持等待）。"""
        from lab_versus_input import glfw_key_names, key_banned, bind
        lab, p = self.lab, self.lab.p
        if self.capture is None or (kind == 'bind') != (self.capture[1] == 'key'):
            return
        side, device, action = self.capture
        if device == 'key':
            name = glfw_key_names().get(value)
            if name is None or key_banned(name):
                play_se(p, SE_CLOSE)
                self.message = T(p, 'vs_banned', key_label(name) if name else '?')
                self.revision += 1
                return
            table, store, label = lab.versus_keys(), 'versus_keys', key_label(name)
        else:
            name, table, store, label = value, lab.versus_pad(), 'versus_pad', value
        swapped = bind(table[side], action, name)
        lab.config[store] = table
        lab.save_config()
        play_se(p, SE_DECIDE)
        self.capture = None
        act = T(p, 'vs_act_' + action)
        self.message = (T(p, 'vs_swapped', side.upper(), act, label, T(p, 'vs_act_' + swapped)) if swapped
                        else T(p, 'vs_bound', side.upper(), act, label))
        self.revision += 1

    def touch(self, action, x, y):
        """按下：按钮显示按下状态；在同一按钮上抬起：播放原生确定（返回类为关闭）音效并执行。"""
        if not self.open and self.shutter.state == 'open':
            return False
        if self.busy():
            return True
        hit = rect = None
        for box, command in reversed(self.hitboxes):
            left, top, w, h = box
            if left <= x < left + w and top <= y < top + h:
                hit, rect = command, box
                break
        if action == 1:
            # 按下反馈只叠加该按钮区域的小图（draw 中绘制），不重绘整个界面。
            self.pressed, self.pressed_rect, self.pointer_inside = hit, rect, hit is not None
        elif action == 5:
            self.pointer_inside = self.pressed is not None and hit == self.pressed
        elif action == 3:
            pressed, self.pressed = self.pressed, None
            if hit is not None and hit == pressed:
                play_se(self.lab.p, SE_CLOSE if hit[0] in BACK_COMMANDS else SE_DECIDE)
                if hit in self.icons and hit[0] in ('start', 'close'):
                    self.lit = hit       # 与原生选单按钮相同：选中后青色框保持到画面切换
                self.command(*hit)
        return True

    # ---------- 绘制 ----------
    def draw(self):
        """每帧调用：准备界面（打开时）在下，宿主闸门在上。"""
        if self.open:
            if not self.busy():
                self.hold_bgm()
            if self.overlay is None:
                from trial_overlay import SurfaceOverlay
                self.overlay = SurfaceOverlay(self.lab.p.graphics)
                self.font = fonts()
            key = ('lab_prep', self.revision)
            image = None
            if self.overlay.cached != key:
                image = self.skin.tiled(BRICK, W, H).copy()
                self.c = Canvas(image, self.skin, self.font, None)
                {'main': self.draw_main, 'picker': self.draw_picker, 'history': self.draw_history,
                 'keys': self.draw_keys, 'help': self.draw_help}[self.page]()
                self.hitboxes = self.c.hitboxes
                self.icons = self.c.icons
                self.rendered = image
            self.overlay.draw_image(image, key, (0, 0, W, H))
            self.draw_press()
        self.shutter.update_and_draw(self.skin)

    def draw_press(self):
        """按下反馈：原生图标按钮叠加青色框与三灯（按住且指针在按钮上，或抬起后至闸门合拢）；
        其他按钮叠加该区域的压暗小图并下移 2 像素。"""
        if getattr(self, 'rendered', None) is None:
            return
        command = self.lit if self.lit in self.icons else (self.pressed if self.pointer_inside else None)
        if command is None or (command not in self.icons and not self.pressed_rect):
            return
        if self.press_overlay is None:
            from trial_overlay import SurfaceOverlay
            self.press_overlay = SurfaceOverlay(self.lab.p.graphics)
        if command in self.icons:
            x, y, name = self.icons[command]
            press_key = ('lab_prep_icon', self.revision, command)
            part = None
            if self.press_overlay.cached != press_key:
                part, (left, top) = icon_press_image(self.skin, self.rendered, x, y, name)
                self.icon_rect = (left, top, part.width, part.height)
            self.press_overlay.draw_image(part, press_key, self.icon_rect)
            return
        x, y, w, h = self.pressed_rect
        press_key = ('lab_prep_press', self.revision, self.pressed_rect)
        part = None
        if self.press_overlay.cached != press_key:
            part = self.skin.darken(self.rendered.crop((x, y, x + w, y + h)), cache=False)
        self.press_overlay.draw_image(part, press_key, (x, y + 2, w, h))

    def cell(self, rect, uid, side, label=None):
        """原生编组格（unit.obm 绿/红/空格 50×50）+ 原生单位头像（与格子同倍率）。"""
        c = self.c
        x, y, size = rect
        style = 'empty' if uid is None else ('player' if side == 'player' else 'enemy')
        part = self.skin.scaled(CELLS[style], size, size)
        down = c.is_pressed(('slot', side, label and int(label) - 1)) if label else False
        c.paste(self.skin.darken(part) if down else part, (x, y))
        if uid is not None:
            icon = self.skin.icon(uid, size / 50)
            if icon is not None:
                c.paste(icon, (x + (size - icon.width) // 2, y + (size - icon.height) // 2))
        if label is not None:
            c.text((x + 6, y + 3), label, 14, WHITE)

    def header_buttons(self, start=True):
        """顶栏右侧的原生 OK / BACK 图标按钮（60×48 × 1.5，等比缩小），按钮与按下青色框均在顶栏深色区内。"""
        c, p = self.c, self.lab.p
        back_x = W - 12 - ICON_W
        if start:
            ok_x = back_x - 14 - ICON_W
            c.icon_button((ok_x, ICON_Y), 'ok', ('start',))
            c.text((ok_x - 12, ICON_Y + ICON_H // 2), T(p, 'start'), 18, GOLD, 'rm', 2, 260)
        c.icon_button((back_x, ICON_Y), 'back', ('close',) if start else ('back',))

    def draw_main(self):
        lab, c, p = self.lab, self.c, self.lab.p
        names = self.names()
        c.header(T(p, 'cpu_prep_title' if lab.cpu else 'vs_prep_title' if lab.versus else 'prep_title'))
        self.header_buttons()
        if lab.versus:
            # 双人对战：顶栏增加按键设定与操作说明两个入口页（位于标题与“开始战斗”之间，顶栏深色区内）。
            for index, page in enumerate(('keys', 'help')):
                c.button((420 + index * 176, ICON_Y + (ICON_H - 40) // 2, 164, 40), T(p, f'vs_{page}_title'),
                         ('vs_page', page), 16)
        for row, side in enumerate(('player', 'enemy')):
            top = DECK_TOP + row * DECK_PITCH
            c.text((DECK_X, top + 13), self.deck_label(side), 18, BLUE if side == 'player' else RED, 'lm', 2, 140)
            x = DECK_X + 150
            c.text((x, top + 13), T(p, 'all_level'), 14, WHITE, 'lm', 2, 80)
            c.button((x + 84, top, 28, 26), '-', ('level_all', side, -1))
            c.text((x + 146, top + 13), f'Lv{self.level_all[side]}', 16, WHITE, 'mm')
            c.button((x + 180, top, 28, 26), '+', ('level_all', side, 1))
            c.button((x + 218, top, 80, 26), T(p, 'apply'), ('apply_all', side), 14, 'light')
            # 据点初始等级（0–10，10 为 MAX；完全控制开启时开战即 MAX）
            bx = DECK_X + 470
            value = int(lab.config.get(side + '_base_level', 0))
            shown = 'MAX' if lab.full_control or value >= 10 else f'Lv{value}'
            c.text((bx, top + 13), T(p, 'base_short'), 14, WHITE, 'lm', 2, 50)
            c.button((bx + 54, top, 28, 26), '<', ('base', side, -1))
            c.text((bx + 54 + 28 + 38, top + 13), shown, 16, GRAY if lab.full_control else GOLD, 'mm', 2, 70)
            c.button((bx + 54 + 28 + 76, top, 28, 26), '>', ('base', side, 1))
            right = DECK_X + DECK_W
            c.button((right - 292, top, 100, 26), T(p, 'cpu_copy') if lab.cpu else
                     self.t('copy_enemy' if side == 'player' else 'copy_player'), ('copy', side), 14, 'light')
            c.button((right - 186, top, 90, 26), T(p, 'random'), ('random', side), 14)
            c.button((right - 90, top, 90, 26), T(p, 'clear'), ('clear', side), 14, 'off')
            for slot, entry in enumerate(self.deck(side)):
                x, y = DECK_X + slot * (CELL + CELL_GAP), top + 30
                uid = None if entry is None else self.uid(entry[0])
                unavailable = entry is not None and (uid is None or (uid >= 1024 and uid not in names))
                self.cell((x, y, CELL), None if unavailable else uid, side, str(slot + 1))
                c.hitboxes.append(((x, y, CELL, CELL), ('slot', side, slot)))
                if entry is None:
                    c.text((x + CELL // 2, y + CELL // 2), T(p, 'empty'), 18, GRAY, 'mm', 2, CELL - 10)
                    continue
                if unavailable:
                    # 设定中的模组单位当前未载入：显示“未启用”，开战时按空格处理。
                    c.text((x + CELL // 2, y + CELL // 2), T(p, 'unit_unavailable'), 15, GRAY, 'mm', 2, CELL - 10)
                    continue
                c.text((x + CELL // 2, y + CELL - 11), names.get(uid, str(uid)), 13, WHITE, 'mm', 2, CELL - 8)
                c.button((x, y + CELL + 4, 28, 24), '-', ('level', side, slot, -1))
                c.text((x + CELL // 2, y + CELL + 16), f'Lv{entry[1]}', 16, GOLD, 'mm', 2, CELL - 58)
                c.button((x + CELL - 28, y + CELL + 4, 28, 24), '+', ('level', side, slot, 1))
        # 下方四块面板：地图、控制、优势、预设；左右边距与牌组对齐。
        widths = (290, 300, 230)
        gap = 10
        xs = [DECK_X]
        for w in widths:
            xs.append(xs[-1] + w + gap)
        boxes = list(zip(xs, list(widths) + [DECK_X + DECK_W - xs[-1]]))
        self.draw_map(boxes[0], PANEL_TOP, PANEL_H)
        self.draw_control(boxes[1], PANEL_TOP, PANEL_H)
        self.draw_advantage(boxes[2], PANEL_TOP, PANEL_H)
        self.draw_presets(boxes[3], PANEL_TOP, PANEL_H)
        c.text((W // 2, H - 12), T(p, 'hint'), 12, GRAY, 'mm', 1, W - 40)

    def stepper(self, x, y, w, value, minus, plus):
        c = self.c
        c.button((x, y, 30, 28), '<', minus)
        c.text((x + w / 2, y + 14), value, 15, GOLD, 'mm', 2, w - 68)
        c.button((x + w - 30, y, 30, 28), '>', plus)

    def draw_map(self, box, top, height):
        """地图：原生缩略图（区域缩略图文件中的小关图块，2 倍）、区域名与小关编号、世界与小关两个选择器。"""
        lab, c, p = self.lab, self.c, self.lab.p
        x, w = box
        c.panel((x, top, w, height), T(p, 'map'))
        worlds, wi, si = self.stage_position()
        tw, th = 128 * THUMB_SCALE, 56 * THUMB_SCALE
        tx, ty = x + (w - tw) // 2, top + 36
        c.draw.rectangle((tx - 3, ty - 3, tx + tw + 2, ty + th + 2), fill=(12, 12, 12, 255), outline=(150, 135, 100, 255),
                         width=2)
        if not worlds:
            c.text((x + w / 2, ty + th / 2), str(lab.config.get('stage_id')), 16, GRAY, 'mm')
            return
        world, stages = worlds[wi]
        entry = stages[si]
        image = self.thumbnail(entry)
        if image is not None:
            c.paste(image, (tx + (tw - image.width) // 2, ty + (th - image.height) // 2))
        c.text((x + w / 2, ty + th + 14), f"{entry['area_name']}  {entry['area'] + 1}-{entry['stage'] + 1}",
               15, WHITE, 'mm', 2, w - 20)
        self.stepper(x + 14, ty + th + 28, w - 28, T(p, f'world_{world}'), ('world', -1), ('world', 1))
        self.stepper(x + 14, ty + th + 60, w - 28, f"{entry['area'] + 1}-{entry['stage'] + 1}   ({si + 1}/{len(stages)})",
                     ('stage', -1), ('stage', 1))

    def human_side(self):
        """VS CPU：玩家所在的一行（'player' 为 P1，'enemy' 为 P2）。"""
        return 'enemy' if self.lab.config.get('cpu_side') == 'p2' else 'player'

    def deck_label(self, side):
        if not self.lab.cpu:
            return self.t(side + '_deck')
        p = self.lab.p
        slot = 'P1' if side == 'player' else 'P2'
        return T(p, 'cpu_you_deck' if side == self.human_side() else 'cpu_cpu_deck', slot)

    def draw_control(self, box, top, height):
        """控制：LAB 为完全控制、双方 AI（开/关 + 段位选择器）、双方自动绝招；双人对战显示双方键位与对战规则
        （完全控制、AI 与自动绝招在对战中关闭，设定保留）。两种模式由入口决定，此处不提供切换。"""
        lab, c, p = self.lab, self.c, self.lab.p
        x, w = box
        c.panel((x, top, w, height), T(p, 'control'))
        y = top + 26
        if lab.cpu:
            # VS CPU：玩家所在一边（P1 左 / P2 右，CPU 在另一边）与 CPU 段位；完全控制与玩家方 AI 不在本模式中使用。
            side = lab.config.get('cpu_side', 'p1')
            c.text((x + 14, top + 58), T(p, 'cpu_side'), 15, WHITE, 'lm', 2, 90)
            for index, value in enumerate(('p1', 'p2')):
                c.button((x + 110 + index * ((w - 124) // 2 + 4), top + 44, (w - 124) // 2 - 4, 28),
                         T(p, 'cpu_side_' + value), ('cpu_side', value), 14, 'on' if side == value else 'light')
            c.text((x + 14, top + 102), T(p, 'cpu_tier'), 15, WHITE, 'lm', 2, 90)
            self.tier_selector((x + 110, top + 88, w - 124, 28), 'cpu', True)
            c.text((x + 14, top + 150), T(p, 'cpu_rules'), 12, GRAY, 'lm', 2, w - 28)
            return
        if lab.versus:
            keys = lab.versus_keys()
            for row, (side, color) in enumerate((('p1', BLUE), ('p2', RED))):
                k = {a: key_label(n) for a, n in keys[side].items()}
                c.text((x + 14, y + 52 + row * 40), T(p, 'vs_keys', side.upper(), k['left'], k['right'], k['ap'],
                                                     k['deploy'], k['special'], k['slug']), 13, color, 'lm', 2, w - 28)
            c.text((x + 14, y + 134), T(p, 'vs_rules'), 12, GRAY, 'lm', 2, w - 28)
            return
        for index, attr in enumerate(('full_control', 'player_ai', 'player_auto_special', 'enemy_ai',
                                      'enemy_auto_special')):
            y = top + 44 + index * 34
            on = getattr(lab, attr)
            if attr in ('player_ai', 'enemy_ai'):
                side = attr[:-3]
                c.text((x + 14, y + 15), T(p, side + '_ai_short'), 15, WHITE, 'lm', 2, 64)
                c.button((x + 82, y, 52, 28), T(p, 'on' if on else 'off'), ('toggle', attr), 16, 'on' if on else 'off')
                self.tier_selector((x + 142, y, w - 156, 28), side, on)
                continue
            c.text((x + 14, y + 14), T(p, attr), 15, WHITE, 'lm', 2, w - 110)
            c.button((x + w - 86, y, 72, 28), T(p, 'on' if on else 'off'), ('toggle', attr), 16, 'on' if on else 'off')

    def tier_color(self, name, plate):
        if name not in self.tier_colors:
            self.tier_colors[name] = readable(TIER_COLORS[name], plate)
        return self.tier_colors[name]

    def tier_selector(self, rect, side, active):
        """AI 段位选择器：原生左右按钮与压暗的原生按钮底板，段位名为英文大写、段位色加黑色描边；
        底板下沿以段位原色画细色带。AI 关闭时文字为灰色（段位保留，不生效）。"""
        from PIL import ImageEnhance
        c, lab = self.c, self.lab
        x, y, w, h = rect
        name = lab.ai_tier(side)[0]
        c.button((x, y, 24, h), '<', ('tier', side, -1))
        c.button((x + w - 24, y, 24, h), '>', ('tier', side, 1))
        px, pw = x + 27, w - 54
        plate = ImageEnhance.Brightness(self.skin.nine(TIER_PLATE, pw, h, 6)).enhance(TIER_PLATE_DIM)
        c.paste(plate, (px, y))
        color = self.tier_color(name, plate.convert('RGB').resize((1, 1)).getpixel((0, 0)))
        # AI 关闭时色带降低饱和度并压暗（与灰色文字一致），避免仅凭色带误判 AI 已开启。
        band = TIER_COLORS[name] if active else desaturate(TIER_COLORS[name])
        c.draw.rectangle((px + 4, y + h - 4, px + pw - 5, y + h - 3), fill=band + (255,))
        c.text((px + pw / 2, y + h / 2 - 1), name, 15, color if active else GRAY, 'mm', 2, pw - 8)

    def draw_advantage(self, box, top, height):
        """优势设定：原生关卡强化级数（BattleObjectManager+72 起每队两个浮点数，生命/攻击各 ×(1+0.2×级数)）。"""
        lab, c, p = self.lab, self.c, self.lab.p
        x, w = box
        c.panel((x, top, w, height), T(p, 'advantage'))
        y = top + 42
        for side in ('player', 'enemy'):
            label = self.deck_label(side) if lab.cpu else self.t('adv_' + side)
            c.text((x + 14, y + 10), label, 15, BLUE if side == 'player' else RED, 'lm', 2, w - 28)
            y += 24
            for stat in ('hp', 'atk'):
                key = f'{side}_{stat}_boost'
                steps = int(lab.config.get(key, 0))
                c.text((x + 14, y + 14), T(p, 'adv_' + stat), 15, WHITE, 'lm', 2, 54)
                self.stepper(x + 70, y, w - 84, f'+{steps * 20}%', ('advantage', key, -1), ('advantage', key, 1))
                y += 34
            y += 4

    def draw_presets(self, box, top, height):
        c, p = self.c, self.lab.p
        x, w = box
        c.panel((x, top, w, height), T(p, 'presets'))
        bw = (w - 28 - 70 - 8) // 2
        for index, name in enumerate('ABC'):
            y = top + 42 + index * 40
            c.text((x + 14, y + 15), T(p, 'preset', name), 15, WHITE, 'lm', 2, 66)
            c.button((x + 84, y, bw, 30), T(p, 'save'), ('preset_save', name), 14)
            c.button((x + 84 + bw + 8, y, bw, 30), T(p, 'load'), ('preset_load', name), 14, 'light')
        c.button((x + 14, top + 42 + 3 * 40, w - 28, 30), T(p, 'history'), ('history',), 15)
        if self.message:
            c.text((x + w / 2, top + 42 + 4 * 40 + 16), self.message, 14, GOLD, 'mm', 2, w - 28)

    def filtered(self):
        tab = TABS[self.tab][1]
        units = self.unit_list()
        if tab == 'community':
            return [u for u in units if u[3]]
        if tab is None:
            return units
        return [u for u in units if u[2] == tab]

    def draw_picker(self):
        c, p = self.c, self.lab.p
        side, slot = self.picker
        c.header(T(p, 'picker_title', self.t('side_' + side), slot + 1))
        self.header_buttons(start=False)
        c.button((W - 10 - ICON_W - 14 - 140, ICON_Y + (ICON_H - 32) // 2, 140, 32), T(p, 'set_empty'),
                 ('pick', None), 16, 'light')
        tab_w = (W - 48 - 7 * 8) // 8
        for index, (label, _) in enumerate(TABS):
            x = 24 + index * (tab_w + 8)
            down = c.is_pressed(('tab', index))
            part = self.skin.nine(TAB_ON if index == self.tab else TAB_OFF, tab_w, 33, 6)
            c.paste(self.skin.darken(part) if down else part, (x, PICK_TABS_Y + (2 if down else 0)))
            active = index == self.tab
            c.text((x + tab_w / 2, PICK_TABS_Y + 17 + (2 if down else 0)), T(p, label), 16, DARK if active else WHITE,
                   'mm', 0 if active else 2, tab_w - 10)
            c.hitboxes.append(((x, PICK_TABS_Y, tab_w, 33), ('tab', index)))
        units = self.filtered()
        per_page = PICK_COLS * PICK_ROWS
        pages = max(1, (len(units) + per_page - 1) // per_page)
        self.picker_page = min(self.picker_page, pages - 1)
        for index, (uid, name, faction, community) in enumerate(units[self.picker_page * per_page:][:per_page]):
            col, row = index % PICK_COLS, index // PICK_COLS
            x, y = PICK_X + col * PICK_PITCH, PICK_TABS_Y + 45 + row * (PICK_CELL + 32)
            self.cell((x, y, PICK_CELL), uid, side)
            if c.is_pressed(('pick', uid)):
                c.paste(self.skin.darken(self.skin.scaled(CELLS['player' if side == 'player' else 'enemy'],
                                                          PICK_CELL, PICK_CELL)), (x, y))
                icon = self.skin.icon(uid, PICK_CELL / 50)
                if icon is not None:
                    c.paste(icon, (x + (PICK_CELL - icon.width) // 2, y + (PICK_CELL - icon.height) // 2))
            if community:
                c.text((x + PICK_CELL - 4, y + 3), T(p, 'community_mark'), 12, GOLD, 'ra', 2)
            c.text((x + PICK_CELL / 2, y + PICK_CELL + 13), name, 13, WHITE, 'mm', 2, PICK_PITCH - 6)
            c.hitboxes.append(((x, y, PICK_CELL, PICK_CELL + 26), ('pick', uid)))
        c.button((24, H - 54, 140, 38), T(p, 'prev'), ('picker_page', -1), 16)
        c.text((W / 2, H - 35), T(p, 'page', self.picker_page + 1, pages, len(units)), 16, WHITE, 'mm', 2, 600)
        c.button((W - 164, H - 54, 140, 38), T(p, 'next'), ('picker_page', 1), 16)

    def pad_lines(self):
        """已连接手柄的显示行：(序号, 名称, 玩家)。"""
        return [(index + 1, name or f'#{jid}', '-' if side is None else ('P1', 'P2')[side])
                for index, (jid, side, name) in enumerate(self.lab.pad_status)]

    def draw_keys(self):
        """按键设定：每名玩家 6 项键盘键与 4 项手柄功能键（点击后按下新键；同一玩家内重复时互换）。"""
        lab, c, p = self.lab, self.c, self.lab.p
        from lab_versus_input import ACTIONS
        c.header(T(p, 'vs_keys_title'))
        self.header_buttons(start=False)
        keys, pads = lab.versus_keys(), lab.versus_pad()
        top, height = HEADER_H + 10, 400
        for index, (side, color) in enumerate((('p1', BLUE), ('p2', RED))):
            x, w = 24 + index * 626, 606
            c.panel((x, top, w, height), None)
            c.text((x + 18, top + 22), T(p, 'vs_side_' + side), 20, color, 'lm', 2, w - 36)
            for label, cx in (('vs_col_action', x + 22), ('vs_col_key', x + 210), ('vs_col_pad', x + 410)):
                c.text((cx, top + 60), T(p, label), 14, GRAY, 'lm', 2, 180)
            for row, action in enumerate(ACTIONS):
                y = top + 80 + row * 50
                c.text((x + 22, y + 19), T(p, 'vs_act_' + action), 17, WHITE, 'lm', 2, 176)
                waiting = self.capture == (side, 'key', action)
                c.button((x + 200, y, 180, 38), '…' if waiting else key_label(keys[side][action]),
                         ('capture', side, 'key', action), 18, 'on' if waiting else 'normal')
                if action in pads[side]:
                    waiting = self.capture == (side, 'pad', action)
                    c.button((x + 400, y, 180, 38), '…' if waiting else pads[side][action],
                             ('capture', side, 'pad', action), 18, 'on' if waiting else 'normal')
                else:
                    c.text((x + 490, y + 19), T(p, 'vs_pad_fixed'), 14, GRAY, 'mm', 2, 180)
        y = top + height + 10
        c.panel((24, y, W - 48, 120), T(p, 'vs_pads'))
        lines = self.pad_lines()
        if not lines:
            c.text((42, y + 64), T(p, 'vs_pad_none'), 16, GRAY, 'lm', 2, 760)
        for row, (number, name, side) in enumerate(lines[:3]):
            c.text((42, y + 52 + row * 24), T(p, 'vs_pad_row', number, name, side), 15, WHITE, 'lm', 2, 760)
        single = lab.config.get('versus_pad_single', 'p2').upper()
        c.button((W - 48 - 400, y + 46, 220, 36), T(p, 'vs_pad_single', single), ('pad_single',), 15)
        c.button((W - 48 - 168, y + 46, 150, 36), T(p, 'vs_reset'), ('keys_reset',), 15, 'off')
        if self.message:
            c.text((W // 2, H - 20), self.message, 16, GOLD, 'mm', 2, W - 60)

    def draw_help(self):
        """操作说明：双方当前键位与手柄按键（随自定义实时显示）与对战规则。"""
        lab, c, p = self.lab, self.c, self.lab.p
        c.header(T(p, 'vs_help_title'))
        self.header_buttons(start=False)
        keys, pads = lab.versus_keys(), lab.versus_pad()
        top, height = HEADER_H + 10, 262
        for index, (side, color) in enumerate((('p1', BLUE), ('p2', RED))):
            x, w = 24 + index * 626, 606
            k, g = keys[side], pads[side]
            rows = (('select', f"{key_label(k['left'])} / {key_label(k['right'])}", T(p, 'vs_pad_fixed')),
                    ('ap', key_label(k['ap']), g['ap']), ('deploy', key_label(k['deploy']), g['deploy']),
                    ('special', key_label(k['special']), g['special']), ('slug', key_label(k['slug']), g['slug']),
                    ('menu', 'Esc', 'START'),
                    ('camera', T(p, 'vs_cam_' + side), None))
            c.panel((x, top, w, height), None)
            c.text((x + 18, top + 22), T(p, 'vs_side_' + side), 20, color, 'lm', 2, w - 36)
            for label, cx in (('vs_col_action', x + 22), ('vs_col_key', x + 230), ('vs_col_pad', x + 420)):
                c.text((cx, top + 54), T(p, label), 14, GRAY, 'lm', 2, 180)
            for row, (action, key, pad) in enumerate(rows):
                y = top + 80 + row * 26
                c.text((x + 22, y), T(p, 'vs_act_' + action), 16, WHITE, 'lm', 2, 200)
                if pad is None:
                    c.text((x + 230, y), key, 16, GOLD, 'lm', 2, w - 250)
                    continue
                c.text((x + 230, y), key, 16, GOLD, 'lm', 2, 180)
                c.text((x + 420, y), pad, 16, GOLD, 'lm', 2, 170)
        y = top + height + 10
        c.panel((24, y, W - 48, H - y - 14), None)
        for row, line in enumerate(T(p, 'vs_rule_lines')):
            c.text((44, y + 24 + row * 30), '・' + line, 16, WHITE, 'lm', 2, W - 100)

    def draw_history(self):
        c, p = self.c, self.lab.p
        c.header(T(p, 'history_title'))
        self.header_buttons(start=False)
        entries = self.lab.read_history()[-12:][::-1]
        if not entries:
            c.text((W / 2, H / 2), T(p, 'no_history'), 20, GRAY, 'mm')
        for index, entry in enumerate(entries):
            y = HEADER_H + 10 + index * 49
            winner = entry.get('winner')
            c.paste(self.skin.nine(ROW_STYLES.get(winner, ROW_STYLES[None]), W - 48, 45, 8), (24, y))
            key = {'player': 'win_player', 'enemy': 'win_enemy'}.get(winner, 'aborted')
            if entry.get('cpu') and winner:
                human = 'enemy' if entry.get('cpu_side') == 'p2' else 'player'
                result = T(p, 'cpu_win_you' if winner == human else 'cpu_win_cpu') + ' · ' + str(entry.get('cpu_tier', ''))
            else:
                result = T(p, 'vs_' + key if entry.get('versus') and winner else key)
            c.text((40, y + 22), T(p, 'history_row', entry.get('time', ''), result, entry.get('seconds', 0),
                                   self.lab.stage_label(entry.get('stage_id'))), 16, WHITE, 'lm', 2, 380)
            for side_index, key in enumerate(('player_units', 'enemy_units')):
                for i, uid in enumerate([u for u in entry.get(key, []) if u][:10]):
                    icon = self.skin.icon(uid, 36 / 50)
                    if icon is not None:
                        c.paste(icon, (430 + side_index * 410 + i * 38 + (36 - icon.width) // 2,
                                       y + 4 + (36 - icon.height) // 2))

    def close_resources(self):
        for overlay in (self.overlay, self.press_overlay):
            if overlay is not None:
                overlay.close()
        self.overlay = self.press_overlay = None
        self.shutter.close_resources()
