"""LAB 战斗中菜单（T6）：游戏样式的宿主面板，打开期间暂停战斗。

GameMode 1 中原生暂停页不可用；打开菜单时置 BattleGameMaster+0x1c（暂停标记，战斗模拟随之停止，
原生不显示暂停界面），关闭时还原。面板使用原生素材（pause_window.obm 米色面板、menuparts.obm 标题栏与按钮），
打开时自上方滑入、关闭时滑出（8 帧），打开/选择播放原生确定音，关闭播放原生关闭音。
鼠标点击行或 ↑/↓ + Enter 选择，Esc 打开/关闭。文字随游戏语言（lab_ui.TEXT）。
LAB 与双人对战均提供音乐、音效开关（与原生暂停页相同的存档字 app+0x3d5c / app+0x3d60，由 audio_options 应用音量与保存）。
"""
from lab_ui import (W, H, WHITE, GOLD, GRAY, HEADER, BOARD, SE_DECIDE, SE_CLOSE, T, Canvas, Skin, fonts, play_se)

PANEL_W = 500
ROW_H, ROW_TOP = 44, 92
AUDIO_ROWS = (('menu_music', 0x3d5c), ('menu_effects', 0x3d60))   # app 偏移（audio_options.MUSIC / EFFECTS）
SLIDE_FRAMES = 8


class LabMenu:
    def __init__(self, lab):
        self.lab = lab
        self.open = False
        self.closing = False
        self.frame = 0
        self.selected = 0
        self.paused_by_menu = False
        self.overlay = self.dim = None
        self.skin = Skin(lab)
        self.font = None
        self.rect = None
        self.revision = 0
        self.pressed = None
        self.hitboxes = []

    # ---------- 行 ----------
    def rows(self):
        lab, p = self.lab, self.lab.p
        rows = [] if lab.vs_battle() or lab.cpu_battle() else [(T(p, name), getattr(lab, name), ('toggle', name)) for name in
                ('full_control', 'player_ai', 'player_auto_special', 'enemy_ai', 'enemy_auto_special')]
        app = p.app_instance()
        rows += [(T(p, name), bool(p.word(app + offset)), ('audio', offset)) for name, offset in AUDIO_ROWS]
        return rows + [(T(p, 'restart'), None, ('restart',)), (T(p, 'exit_lab'), None, ('exit',)),
                       (T(p, 'resume'), None, ('close',))]

    # ---------- 打开与关闭 ----------
    def set_open(self, value, animate=True):
        p = self.lab.p
        master = p.call('_ZN16BattleGameMaster11getInstanceEv')
        if value and not self.open:
            self.open, self.closing, self.frame, self.selected = True, False, 0, 0
            play_se(p, SE_DECIDE)
            if master and not p.read(master + 0x1c, 1)[0]:
                p.write(master + 0x1c, b'\x01')
                self.paused_by_menu = True
        elif not value and self.open:
            if animate and not self.closing:
                self.closing, self.frame = True, 0
                play_se(p, SE_CLOSE)
                return
            self.open = self.closing = False
            if self.paused_by_menu and master:
                p.write(master + 0x1c, b'\x00')
            self.paused_by_menu = False
        self.revision += 1

    # ---------- 输入 ----------
    def move(self, step):
        self.selected = (self.selected + step) % len(self.rows())
        self.revision += 1

    def activate(self, index=None):
        index = self.selected if index is None else index
        command = self.rows()[index][2]
        if command[0] == 'close':
            self.set_open(False)
        else:
            play_se(self.lab.p, SE_DECIDE)
            self.lab.menu_command(command)
        self.revision += 1

    def touch(self, action, x, y):
        """返回 True 表示触点已由菜单处理（菜单打开期间一律拦截）。按下显示按下状态，同一行上抬起执行。"""
        if not self.open:
            return False
        if self.closing or not self.rect:
            return True
        hit = None
        for (left, top, w, h), index in self.hitboxes:
            if left <= x < left + w and top <= y < top + h:
                hit = index
        if action == 1:
            self.pressed = hit
            self.revision += 1
        elif action == 3:
            pressed, self.pressed = self.pressed, None
            self.revision += 1
            if hit is not None and hit == pressed:
                self.selected = hit
                self.activate(hit)
        return True

    # ---------- 绘制 ----------
    def draw(self):
        if not self.open:
            return
        if self.overlay is None:
            from PIL import Image
            from trial_overlay import SurfaceOverlay
            self.overlay, self.dim = SurfaceOverlay(self.lab.p.graphics), SurfaceOverlay(self.lab.p.graphics)
            self.font = fonts()
            self.dim_image = Image.new('RGBA', (16, 16), (0, 0, 0, 150))
        self.frame += 1
        t = min(1.0, self.frame / SLIDE_FRAMES)
        if self.closing:
            t = 1 - t
        t = t * t * (3 - 2 * t)
        rows = self.rows()
        panel_h = self.panel_h(rows)
        left, top = (W - PANEL_W) // 2, (H - panel_h) // 2
        y = int(-panel_h + (top + panel_h) * t)
        self.rect = (left, top, PANEL_W, panel_h)
        self.dim.draw_image(self.dim_image, ('lab_menu_dim',), (0, 0, W, H))
        key = ('lab_menu', self.revision, tuple(r[1] for r in rows), self.selected, self.pressed)
        image = None
        if self.overlay.cached != key:
            image = self.render(rows)
        self.overlay.draw_image(image, key, (left, y, PANEL_W, panel_h))
        if self.closing and self.frame >= SLIDE_FRAMES:
            self.set_open(False, animate=False)

    @staticmethod
    def panel_h(rows):
        """面板高度随行数（LAB 10 行、双人对战 5 行）。"""
        return ROW_TOP + len(rows) * ROW_H + 40

    def render(self, rows):
        from PIL import Image
        p = self.lab.p
        panel_h = self.panel_h(rows)
        image = Image.new('RGBA', (PANEL_W, panel_h), (0, 0, 0, 0))
        c = Canvas(image, self.skin, self.font, None)
        c.paste(self.skin.nine(BOARD, PANEL_W, panel_h - 30, 26), (0, 30))
        c.paste(self.skin.nine(HEADER, PANEL_W - 40, 58, 20), (20, 0))
        c.text((PANEL_W / 2, 24), T(p, 'vs_menu_title' if self.lab.versus else 'menu_title'), 22, GOLD, 'mm', 3, PANEL_W - 80)
        c.text((PANEL_W / 2, 46), T(p, 'menu_paused'), 13, WHITE, 'mm', 2, PANEL_W - 80)
        left, top = self.rect[:2]
        self.hitboxes = []
        for index, (label, state, _) in enumerate(rows):
            y = ROW_TOP + index * ROW_H
            style = 'light' if index == self.selected else 'normal'
            c.pressed = ('row', index) if self.pressed == index else None
            if state is None:
                c.button((40, y, PANEL_W - 80, ROW_H - 8), label, ('row', index), 17, style)
            else:
                c.button((40, y, PANEL_W - 170, ROW_H - 8), label, ('row', index), 15, style)
                c.button((PANEL_W - 122, y, 82, ROW_H - 8), T(p, 'on' if state else 'off'), ('row', index), 16,
                         'on' if state else 'off')
            self.hitboxes.append(((left + 40, top + y, PANEL_W - 80, ROW_H - 8), index))
        c.text((PANEL_W / 2, panel_h - 22), T(p, 'menu_hint'), 13, GRAY, 'mm', 1, PANEL_W - 60)
        return image

    def close_resources(self):
        for overlay in (self.overlay, self.dim):
            if overlay is not None:
                overlay.close()
        self.overlay = self.dim = None
