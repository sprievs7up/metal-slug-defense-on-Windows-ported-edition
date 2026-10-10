"""主菜单“對戰”入口与 VERSUS 子页面（钩子版本 16）。

- 主菜单第三个按钮的文字由宿主光栅化（probe.draw_text）。各语言的 Wi-Fi 对战按钮文字（libAppMain.so 字符串表中的
  独立字符串）整串替换为“对战”，Wi-Fi 模式因 Google Play 登录判断不可用。
- 点击该按钮时保留原生按压白光，由宿主调用原生布局切换函数进入 SHOP 子页面（scene28/state4），底栏 SHOP 不接收按压触点。
  页面打开期间，src/lab_hooks.cpp 的 drawConv 替换表（头部 +0xb40，'VSPG'）把 SHOP 标题字换为原生 VERSUS 整词，
  三张卡的插画与标签图块换为本地对战 / 局域网对战 / 远程对战，并跳过底栏 SHOP 的 LOCK 叠层；位置、缩放与入场动画
  沿用原生调用。原生 BACK 返回 MENU 时页面关闭；在页面中点击底栏 SHOP 时解除原生“当前页”标记，由原生切换动画进入商店（场景离开 28 时页面关闭）。
- 卡片点击由宿主拦截：本地对战以双人模式打开 LAB 准备界面；局域网（N6a）与远程（N6b：按地址与房间码直连）经原生闸门进入
  同一联机大厅（netplay_lobby，原版 Wi-Fi VERSUS 菜单改造）。离开大厅回到主菜单时重新显示本页（follow_lobby_return）。
卡片图块为 98×123（与原生卡片插画加标签的转换项相同）：上 98×102 为插画，下方为 12 行原生标题字体的标签
（artwork/title_font_20261008/titles/*_12.png）。存在 custom_content/versus_card_{local,lan,online}.png（98×102）时采用用户插画，
否则使用占位插画（原生叛军普通兵头像相对）。三张卡的 VS 字样均由程序以原始像素尺寸固定叠加，用户插画仅包含人物图标。
用户人物插画以原尺寸统一向下绘制 16 px，避让固定 VS，PNG 文件内的像素与坐标保持。
"""
from pathlib import Path
import struct

VS_PAGE = 0xb40
VS_PAGE_MAGIC = 0x47505356
# 原生只读数据中的转换项（verification/lab_versus_20261008/driver_menu_log.py 记录，shop 页）
TITLE_CONV = 0x108fdd58                     # menu.obm 的 SHOP 标题字（64×18，锚点 0,9）
CARD_CONVS = (0x10304fe2, 0x10304ff2, 0x10305002)   # ITEM、MSP、UNIT 的插画加标签（98×123，锚点 -7,-7）
LOCK_CONV = 0x1031cf70                      # 底栏 SHOP 的 LOCK 叠层
CARDS = ('local', 'lan', 'online')
CARD_NATIVE_X = (86, 370, 654)              # 卡框的原生参考坐标 x（y 160），尺寸 112×144，绘制 2 倍
WIFI_BUTTON = (708, 410, 424, 74)           # 1280×720 逻辑坐标：主菜单第三个按钮
SHOP_BUTTON = (532, 650)                    # 底栏 SHOP
SHOP_TASK = 0x36e0                          # app 偏移：底栏 SHOP 按钮任务
WIFI_TASK = 0x3384                          # 主菜单第三项（原生 panel index 9）
CARD_TASKS = (0x33a4, 0x33a8, 0x33ac)       # 三张原生卡片任务
WIFI_LABELS = {'Wi-Fi對戰': '對戰', 'Wi-Fi対戦': '対戦', 'Wi-Fi 대전': '대전', 'Wi-Fi VS': 'VERSUS',
               'Wi-Fi V/S': 'VERSUS', 'Wi-Fi ВЕР': 'ВЕРСУС'}


def card_rect(index):
    """卡框在 1280×720 逻辑画布上的矩形（原生参考坐标 → L=(D+88.9)×1.125，菜单 2 倍绘制）。"""
    x = (CARD_NATIVE_X[index] + 88.9) * 1.125
    return (x, 160 * 1.125, 112 * 2 * 1.125, 144 * 2 * 1.125)


def inside(rect, x, y):
    return rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]


class VersusPage:
    def __init__(self, probe, lab, root, native_touch):
        self.p, self.lab, self.root = probe, lab, Path(root)
        self.native_touch = native_touch        # 未经 LAB 拦截的原生触点入口
        self.state = 'closed'                   # closed / opening / open
        self.left_menu = False
        self.unlocked = False                   # 已清除底栏 SHOP 的当前页标记
        self.leaving = 0                        # 离开 VERSUS 页后的帧数
        self.pressed = None
        self.press_cancelled = False
        self.images = {}                        # 语言 → 已建立的原生图像
        self.error = None
        self.lobby = None                       # 联机大厅（netplay_lobby.NetplayLobby，lab_runtime 建立）
        self.lobby_return = None                # 离开联机大厅回到主菜单时重开本页：None / 'lobby' / 'armed'

    # ---------- 文字 ----------
    def rename_strings(self, a):
        """在 probe.draw_text 光栅化前替换 Wi-Fi 对战按钮文字（整串相等时）。"""
        try:
            p = self.p
            cursor = a[3]
            cursor = (cursor + 4 + 7) & ~7
            cursor += 8
            refs = [p.word(cursor + 4 * i) for i in range(6)]
            for item in p.objects[refs[5]]['items']:
                text = p.objects.get(item)
                if isinstance(text, str) and text in WIFI_LABELS:
                    p.objects[item] = WIFI_LABELS[text]
        except Exception as error:
            p.log('VERSUS_RENAME_ERROR', type(error).__name__, str(error))

    # ---------- 图块 ----------
    def card_image(self, index, lang):
        from PIL import Image
        name = CARDS[index]
        art_path = self.root / 'custom_content' / f'versus_card_{name}.png'
        art_y = 0
        if art_path.is_file():
            art = Image.open(art_path).convert('RGBA')
            if art.size != (98, 102):
                raise ValueError(f'{art_path.name} 须为 98×102')
            art_y = 16                         # 用户人物图统一下移，原图像素与尺寸保持。
        else:
            art = self.placeholder_art()
        card = Image.new('RGBA', (98, 123), (0, 0, 0, 0))
        card.alpha_composite(art, (0, art_y))
        vs = self.versus_mark()
        # 内容距卡框上沿 7 px，VS 顶端透明 2 px；可见像素与底部标签均距相应卡框外沿 14 px。
        card.alpha_composite(vs, ((98 - vs.width) // 2, 5))
        label = Image.open(self.root / f'artwork/title_font_20261008/titles/{name.upper()}_12.png').convert('RGBA')
        bbox = label.getchannel('A').getbbox()
        label = label.crop(bbox)
        card.alpha_composite(label, ((98 - label.width) // 2, 123 - label.height))
        return card

    def placeholder_art(self):
        from PIL import Image
        soldier = self.lab.prep.skin.icon(2, 1)                       # UnitID 2 原生头像（ConvUnitIcon，原尺寸）
        art = Image.new('RGBA', (98, 102), (0, 0, 0, 0))
        art.alpha_composite(soldier, (2, 40))
        art.alpha_composite(soldier.transpose(Image.FLIP_LEFT_RIGHT), (54, 40))
        return art

    def versus_mark(self):
        """以原生像素拼接 34×20 的 VS 字样，在各卡片插画上独立叠加。"""
        from PIL import Image
        versus = Image.open(self.root / 'artwork/title_font_20261008/titles/VERSUS_16_native.png').convert('RGBA')
        vs = Image.new('RGBA', (34, versus.height), (0, 0, 0, 0))
        vs.alpha_composite(versus.crop((0, 0, 17, versus.height)), (0, 0))          # V
        vs.alpha_composite(versus.crop((versus.width - 17, 0, versus.width, versus.height)), (17, 0))  # S
        return vs

    def native_images(self, lang):
        if lang not in self.images:
            from PIL import Image
            from lab_versus import create_native_image
            title = Image.open(self.root / 'artwork/title_font_20261008/titles/VERSUS_16_native.png').convert('RGBA')
            entries = [(TITLE_CONV, create_native_image(self.p, title), (0, 0, title.width, title.height, 0, title.height // 2, 0, 0))]
            for index, conv in enumerate(CARD_CONVS):
                card = self.card_image(index, lang)
                entries.append((conv, create_native_image(self.p, card), (0, 0, 98, 123, -7, -7, 0, 0)))
            entries.append((LOCK_CONV, 0, (0,) * 8))
            self.images[lang] = entries
        return self.images[lang]

    def write_header(self, enable):
        import lab as labmod
        from lab_ui import lang
        p = self.p
        header = labmod.LAB_HEADER + VS_PAGE
        if not enable:
            p.put(header, 0)
            return
        entries = self.native_images(lang(p))
        for i, (conv, image, rect) in enumerate(entries):
            e = header + 0x10 + i * 32
            p.put(e, conv)
            p.put(e + 4, 0)
            p.put(e + 8, image)
            p.put(e + 12, 0)
            p.write(e + 16, struct.pack('<8h', *rect))
        p.put(header + 4, len(entries))
        p.put(header, VS_PAGE_MAGIC)

    # ---------- 状态 ----------
    def menu_state(self):
        app = self.p.app_instance()
        return self.p.word(app + 0x22bc), self.p.word(app + 0x22dc)

    def panel_ready(self, offset, symbol):
        """按压仅在原生入场任务切换至稳态控件后受理，白光与业务点击使用相同就绪时机。"""
        p = self.p
        task = p.word(p.app_instance() + offset)
        return bool(task and (p.word(task) & ~1) == (p.symbols[symbol] & ~1))

    def can_open(self):
        scene, state = self.menu_state()
        lab = self.lab
        return (scene == 28 and state == 1 and not lab.active and not lab.prep.open and not lab.prep.busy()
                and self.state == 'closed' and self.lab.native_hooks >= 16
                and self.panel_ready(WIFI_TASK, '_ZN7AppMain12GT_MenuPanelEP17GENERAL_TASK_BASE'))

    def open(self):
        p = self.p
        try:
            self.write_header(True)
            app = p.app_instance()
            task = p.word(app + SHOP_TASK)
            if not task:
                raise RuntimeError('原生 SHOP 布局任务未就绪')
            # 仅登记布局选择；原生切换函数保留入场、单次确定音与标记清理，SHOP 不进入按压状态。
            try:
                p.put(task + 0x194, 1)
                p.call('_ZN7AppMain21SelectCockpitMainMenuEv', app)
            finally:
                p.call('_ZN7AppMain16ClearSelectPanelEP17GENERAL_TASK_BASEi', app, task, 0)
            if p.word(app + 0xb168) != 4:
                raise RuntimeError('原生对战卡片布局切换未完成')
        except Exception as error:
            self.write_header(False)
            self.error = f'{type(error).__name__}: {error}'
            p.log('VERSUS_PAGE_ERROR', self.error)
            return
        self.state, self.left_menu, self.unlocked, self.leaving = 'opening', False, False, 0
        self.error = None
        p.log('VERSUS_PAGE_OPEN', p.frame)

    def close(self, reason):
        self.end_press()
        if self.state != 'closed':
            self.write_header(False)
            self.p.log('VERSUS_PAGE_CLOSE', reason, self.p.frame)
        self.state, self.pressed = 'closed', None

    def follow_lobby_return(self):
        """离开联机大厅（大厅 BACK，或经编队页进入的勋章商店、单位改造等页面返回）回到主菜单时显示本页。
        原生按 app+0xb168 选择回到主菜单后的子页；大厅打开后该值置 0（原版从 MENU 进入 Wi-Fi 菜单时的状态），
        途中在原生底栏另选 OPTION / SHOP 时由原生改写，按原生前往。主菜单初始化（场景 27）时仍为 0 则改为 4（SHOP 子页），
        场景 28 起以 VERSUS 替换表打开本页，入场动画沿用原生。"""
        p = self.p
        app = p.app_instance()
        scene, _ = self.menu_state()
        if scene == 27 and self.lobby_return == 'lobby':
            if p.word(app + 0xb168) == 0:
                p.put(app + 0xb168, 4)
                self.lobby_return = 'armed'
            else:
                self.lobby_return = None
        elif scene == 28:
            if self.lobby_return == 'armed' and self.state == 'closed':
                self.write_header(True)
                self.state, self.left_menu, self.unlocked, self.leaving = 'opening', False, False, 0
                p.log('VERSUS_PAGE_RETURN', p.frame)
            self.lobby_return = None

    def prepare_frame(self):
        if self.lobby_return is not None:
            self.follow_lobby_return()
        if self.state == 'closed':
            return
        scene, state = self.menu_state()
        if self.state == 'local_transition':
            # 准备界面 reveal() 在闸门完全闭合后置 open；此前继续显示 VERSUS 的标题与卡片。
            if self.lab.prep.open or self.lab.active or scene != 28:
                self.close('local')
            return
        if self.state == 'lan_transition':
            # 原生闸门合拢、进入联机大厅（场景 66）之前继续显示 VERSUS 的标题与卡片。
            if scene != 28 or self.lobby is None or not self.lobby.active():
                if scene != 28 and self.lobby is not None and self.lobby.active():
                    self.lobby_return = 'lobby'
                    self.p.put(self.p.app_instance() + 0xb168, 0)
                self.close('lan')
            return
        if scene != 28 or self.lab.active or self.lab.prep.open:
            self.close('left_menu')
            return
        if self.state == 'open' and state != 4:
            # 离开 VERSUS 页（BACK、OPTION、MEDAL 等原生切换）：卡片淡出期间保留替换，三张卡透明度归零
            # （或任务结束、至多 30 帧）后关闭，使其后原生再次进入的商店为原生内容。
            self.leaving = (self.leaving or 0) + 1
            app = self.p.app_instance()
            alphas = [self.p.word(self.p.word(app + o) + 212) & 0xff if self.p.word(app + o) else 0
                      for o in (0x33a4, 0x33a8, 0x33ac)]
            if not any(alphas) or self.leaving > 30:
                self.close('left_page')
            return
        if state == 4:
            self.state = 'open'
            # 原生 SHOP 子页面把底栏 SHOP 按钮任务 +0x80 第 0 位置 1（当前页，按下不受理）。VERSUS 页清除该位，
            # 点击 SHOP 时原生 SelectCockpitMainMenu 受理并重新进入商店（再次置位）；此时宿主关闭替换，
            # 并以原生进入商店时的卡片动作（CTaskSystem2D::Change，见 shop_card_entry）重放三张卡的入场。
            task = self.p.word(self.p.app_instance() + SHOP_TASK)
            if task and self.p.word(task + 0x80) & 1:
                if self.unlocked:
                    self.shop_card_entry()
                    self.close('shop')
                    return
                self.p.put(task + 0x80, self.p.word(task + 0x80) & ~1)
                self.unlocked = True

    def shop_card_entry(self):
        """原生 SelectCockpitMainMenu 进入商店的共同段（0x10205516 起）对三张卡任务（app+0x33a4/0x33a8/0x33ac）
        把透明度归零并调用 CTaskSystem2D::Change(GT_MenuGenrePanelIn, 任务)；入场动作取自该函数的 GOT 偏移（字面量 0x102058e8，基址
        字面量 0x102058d0 + 0x1020529a）。"""
        p = self.p
        app = p.app_instance()
        got = (p.word(0x102058d0) + 0x1020529a) & 0xffffffff
        action = p.word((got + p.word(0x102058e8)) & 0xffffffff)
        for offset in (0x33a4, 0x33a8, 0x33ac):
            task = p.word(app + offset)
            if task and action:
                p.put(task + 212, 0)                # GT_MenuGenrePanelIn：+212 透明度每帧 +32 至 255（淡入）
                p.call('_ZN13CTaskSystem2D6ChangeEPFiP17GENERAL_TASK_BASEES1_', action, task)
        p.log('VERSUS_PAGE_TO_SHOP', hex(action), p.frame)

    # ---------- 输入 ----------
    def clear_press(self):
        """清除当前原生控件的按压与点击完成字，白光由其原生任务继续淡出。"""
        offset = WIFI_TASK if self.pressed == 'wifi' else CARD_TASKS[self.pressed]
        p, app = self.p, self.p.app_instance()
        task = p.word(app + offset)
        if task:
            p.call('_ZN7AppMain16ClearSelectPanelEP17GENERAL_TASK_BASEi', app, task, 0)

    def end_press(self):
        if self.pressed is None:
            return
        # 框外释放结束原生触点；业务点击由宿主处理，原 Wi-Fi 与商店卡片的选择动作保持未触发。
        try:
            self.native_touch(self.p, 3, -1000, -1000)
        finally:
            try:
                self.clear_press()
            finally:
                self.pressed, self.press_cancelled = None, False

    def move_press(self, rect, x, y):
        if self.press_cancelled:
            self.native_touch(self.p, 5, -1000, -1000)
            self.clear_press()
            return
        self.native_touch(self.p, 5, x, y)
        if not inside(rect, x, y):
            self.press_cancelled = True
            self.clear_press()

    def touch(self, action, x, y):
        """返回 True 表示已处理（不送入原生）。"""
        trial = getattr(self.p, 'event_trial', None)
        if trial is not None and trial.browser.active:
            return False                                    # 历史活动浏览页借用主菜单，第三行由浏览页处理
        if self.state == 'closed':
            if action == 1 and self.can_open() and inside(WIFI_BUTTON, x, y):
                self.end_press()
                self.pressed = 'wifi'
                self.press_cancelled = False
                self.native_touch(self.p, action, x, y)
                return True
            if self.pressed == 'wifi':
                if action == 5:
                    self.move_press(WIFI_BUTTON, x, y)
                if action == 3:
                    activate = not self.press_cancelled and inside(WIFI_BUTTON, x, y) and self.can_open()
                    self.end_press()
                    if activate:
                        self.open()
                return True
            return False
        if self.state != 'open':
            return True                                     # 入场过程中不接受输入
        if action == 1:
            self.end_press()
            self.pressed = next((i for i in range(3) if inside(card_rect(i), x, y)
                                 and self.panel_ready(CARD_TASKS[i], '_ZN7AppMain17GT_MenuGenrePanelEP17GENERAL_TASK_BASE')), None)
            if self.pressed is not None:
                self.press_cancelled = False
                self.native_touch(self.p, action, x, y)
                return True
            return False                                    # 底栏按钮（含 SHOP）由原生处理
        if self.pressed is None:
            return False
        if action == 5:
            self.move_press(card_rect(self.pressed), x, y)
        if action == 3:
            index = self.pressed
            activate = not self.press_cancelled and inside(card_rect(index), x, y)
            self.end_press()
            if activate:
                self.activate(index)
        return True

    def activate(self, index):
        from lab_ui import play_se, SE_DECIDE, SE_CLOSE, T
        if index == 0:
            play_se(self.p, SE_DECIDE)
            self.state = 'local_transition'
            self.lab.commands.append(('prep', 'versus'))
            return
        if index in (1, 2) and self.lobby is not None:
            play_se(self.p, SE_DECIDE)
            self.state = 'lan_transition'                 # 局域网与远程（N6b）进入同一大厅
            self.lobby.open('lan' if index == 1 else 'remote')
            return
        play_se(self.p, SE_CLOSE)
        self.lab.feedback(T(self.p, 'vs_soon'), False)

    def shutdown(self):
        self.write_header(False)
