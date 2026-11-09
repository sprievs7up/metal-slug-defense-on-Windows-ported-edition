"""主菜单底栏的 LAB 图标；保留原始 PNG 并共用原生六项布局。"""
from pathlib import Path

MENU_HEADER = 0x1ffef000
MENU_MAGIC = 0x4c41424d
ICON_SIZE = (60, 48)
MENU_INPUT_STATES = (1, 2, 3, 4)  # MENU、OPTION、CUSTOMIZE、SHOP 的稳定子状态。


class LabMenuEntry:
    def __init__(self, probe, lab, root):
        self.p, self.lab = probe, lab
        self.path = Path(root) / 'custom_content/lab.png'
        self.image = None
        self.native_image = None
        self.pressed = False
        self.pointer_inside = False
        self.p.write(MENU_HEADER, bytes(64))
        if lab.native_hooks < 8:
            return
        from PIL import Image
        with Image.open(self.path) as source:
            if source.format != 'PNG' or source.size != ICON_SIZE:
                raise ValueError('LAB 图标需要原尺寸 60×48 PNG')
            self.image = source.convert('RGBA')
        import struct
        raw = b'OI\x01\x20' + struct.pack('<HH', *ICON_SIZE) + self.image.tobytes()
        buffer = self.p.alloc(len(raw))
        self.p.write(buffer, raw)
        try:
            self.native_image = self.p.call('_ZN5Image14createImageBufEPhiiS0_i', buffer, len(raw), 0, 0, 0)
        finally:
            self.p.free(buffer)
        if not self.native_image or self.p.word(self.native_image + 4) != 60 or self.p.word(self.native_image + 8) != 48:
            raise RuntimeError('LAB 原生图像创建失败或尺寸发生变化')
        # 60×48 原尺寸纹理采用 GLES2 的非二次幂完整采样条件。
        # 仅配置寻址及最近邻采样，像素、尺寸及原生 60×48 矩形保持。
        import ctypes
        saved_texture = ctypes.c_int()
        graphics = self.p.graphics
        graphics.function('glGetIntegerv', 'up')(0x8069, ctypes.byref(saved_texture))
        graphics.function('glBindTexture', 'uu')(0x0de1, self.p.word(self.native_image + 12))
        try:
            for parameter, value in ((0x2801, 0x2600), (0x2800, 0x2600), (0x2802, 0x812f), (0x2803, 0x812f)):
                graphics.function('glTexParameteri', 'uui')(0x0de1, parameter, value)
        finally:
            graphics.function('glBindTexture', 'uu')(0x0de1, saved_texture.value)
        self.p.put(MENU_HEADER + 48, self.native_image)
        self.p.put(MENU_HEADER + 56, 1)
        self.p.put(MENU_HEADER, MENU_MAGIC)
        self.p.log('LAB_MENU_ICON', str(self.path), *self.image.size)

    def prepare_frame(self):
        self.p.put(MENU_HEADER + 4, 0)
        app = self.p.app_instance()
        # 闸门开合期间图标与其他原生底栏按钮一同绘制于闸门之下；准备界面打开或 LAB 战斗时停绘。
        visible = bool(app and self.p.word(app + 0x22bc) in (27, 28)
                       and not (self.lab.active or self.lab.prep.open))
        if not visible:
            self.pressed = self.pointer_inside = False
            self.p.put(MENU_HEADER + 36, 0)
        self.p.put(MENU_HEADER + 56, int(visible))
        # 青色框只在按住且指针在图标内时显示，释放即消失（与原生底栏按钮相同：PushPanel 在释放的一帧清除按压字段）。
        self.p.put(MENU_HEADER + 52, int(self.pressed and self.pointer_inside))

    def visible(self):
        p, lab = self.p, self.lab
        if self.image is None or lab.active or lab.prep.open:
            return False
        app = p.app_instance()
        return (p.word(MENU_HEADER) == MENU_MAGIC and p.word(MENU_HEADER + 4) == 1
                and p.word(app + 0x22bc) in (27, 28))

    def ready(self):
        app = self.p.app_instance()
        return (self.visible() and not self.lab.prep.busy() and self.p.word(app + 0x22bc) == 28
                and self.p.word(app + 0x22dc) in MENU_INPUT_STATES
                and self.p.word(MENU_HEADER + 36) == 1)

    def rectangle(self):
        """绘制与输入共用宿主逻辑坐标，原生边距及统一缩放共同作用。"""
        from probe import f32, i32
        p, app = self.p, self.p.app_instance()
        x, y, sx, sy = (f32(p.word(MENU_HEADER + offset)) for offset in (8, 12, 16, 20))
        width, height = p.window_size
        scale = min(width / 960, height / 640)
        return ((x + i32(p.word(app + 0x3c))) * scale,
                (y + i32(p.word(app + 0x40))) * scale,
                ICON_SIZE[0] * sx * scale, ICON_SIZE[1] * sy * scale)

    def inside(self, x, y):
        bx, by, width, height = self.rectangle()
        return bx <= x < bx + width and by <= y < by + height

    def touch(self, action, x, y):
        ready = self.ready()
        inside = ready and self.inside(x, y)
        if action == 1:
            self.pressed = self.pointer_inside = bool(inside)
            return self.pressed
        if not self.pressed:
            return False
        self.pointer_inside = bool(inside)
        if action == 3:
            self.pressed = False
            if inside:
                from lab_ui import play_se, SE_DECIDE
                play_se(self.p, SE_DECIDE)
                self.lab.commands.append(('prep', 'lab'))
                self.p.log('LAB_MENU_OPEN', self.p.frame)
        return True

    def draw(self):
        """图像及按压装饰已在原生按钮任务层绘制。"""
        if not self.ready():
            self.pressed = self.pointer_inside = False

    def close(self):
        self.p.write(MENU_HEADER, bytes(64))
        if self.native_image is not None:
            if self.p.stop_event is None or not self.p.stop_event.is_set():
                self.p.call('_ZN5ImageD1Ev', self.native_image)
            self.p.free(self.native_image)
            self.native_image = None
