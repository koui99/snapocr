"""贴图浮窗 PinWindow:把一张图片钉在桌面上的无边框置顶浮窗。

结构沿用 M2 工具栏的「半透明顶层窗 + 内层内容控件 + 投影」模式(已在真机验证可行):
- 顶层窗透明、无边框、置顶、Tool(不进任务栏),四周留 MARGIN 给柔和阴影。
- 内层 _PinCanvas 绘制(缩放+旋转后的)图片 + 1px 细边框 + 右下角缩放徽标,并承接交互。
交互:拖动移动、滚轮缩放、右键菜单、键盘(Esc/Shift+Esc/Ctrl+C/Ctrl+S/±)。
复制/保存复用 core.screenshot.writer,不重复造轮子。
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPen,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import QMenu, QWidget

from src.core.logger import get_logger
from src.core.screenshot.writer import ScreenshotWriter
from src.ui.components.shadow_widget import apply_shadow
from src.ui.theme.tokens import COLORS

log = get_logger("pin.window")

_MARGIN = 16          # 阴影留白
_MIN_SCALE = 0.1
_MAX_SCALE = 8.0
_WHEEL_STEP = 1.1
_OPACITY_LEVELS = [100, 80, 60, 40, 20]


def clamp_scale(scale: float) -> float:
    """把缩放比例钳制到 [_MIN_SCALE, _MAX_SCALE]。"""
    return max(_MIN_SCALE, min(_MAX_SCALE, scale))


class _PinCanvas(QWidget):
    """贴图内容面:绘制图片 + 边框 + 徽标,事件转发给 owner(PinWindow)。"""

    def __init__(self, owner: "PinWindow"):
        super().__init__(owner)
        self._owner = owner
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def paintEvent(self, event) -> None:
        owner = self._owner
        dp = owner.display_pixmap
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if dp is not None and not dp.isNull():
            painter.drawPixmap(0, 0, dp)

        # 1px 细边框
        painter.setPen(QPen(QColor(0, 0, 0, 40), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)

        # 右下角缩放徽标(rgba(0,0,0,0.6) 底 + 白字),还原 mockup
        text = f"{int(round(owner.scale * 100))}%"
        font = QFont()
        font.setPixelSize(11)
        painter.setFont(font)
        fm = QFontMetrics(font)
        bw = fm.horizontalAdvance(text) + 12
        bh = 18
        badge = QRect(self.width() - bw, self.height() - bh, bw, bh)
        painter.fillRect(badge, QColor(0, 0, 0, 153))
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(badge, int(Qt.AlignmentFlag.AlignCenter), text)
        painter.end()

    # 事件全部委托给 owner
    def mousePressEvent(self, e): self._owner.on_press(e)
    def mouseMoveEvent(self, e): self._owner.on_move(e)
    def mouseReleaseEvent(self, e): self._owner.on_release(e)
    def mouseDoubleClickEvent(self, e): self._owner.on_double_click(e)
    def wheelEvent(self, e): self._owner.on_wheel(e)
    def contextMenuEvent(self, e): self._owner.show_menu(e.globalPos())
    def keyPressEvent(self, e): self._owner.on_key(e)


class PinWindow(QWidget):
    """单个贴图浮窗。"""

    closed = Signal(object)  # 关闭时发射自身,供 PinManager 清理引用
    ocr_requested = Signal(object)  # 请求 OCR,载荷为当前图像 QImage(交由 app_context 弹结果窗)

    def __init__(self, pixmap: QPixmap, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._orig = QPixmap(pixmap)
        self._scale = 1.0
        self._angle = 0
        self._opacity = 100
        self._on_top = True
        self._drag_offset: QPoint | None = None
        self._initialized = False  # 首次定位前不做「保持中心」的位移
        self.display_pixmap: QPixmap | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self._canvas = _PinCanvas(self)
        apply_shadow(self._canvas, heavy=True)

        self._refresh()

    # ---- 只读属性给 canvas 用 ----
    @property
    def scale(self) -> float:
        return self._scale

    # ---- 尺寸刷新(缩放/旋转后重算,保持窗口中心不动)----
    def _compute_display(self) -> QPixmap:
        if self._orig.isNull():
            return QPixmap()
        sw = max(1, int(self._orig.width() * self._scale))
        sh = max(1, int(self._orig.height() * self._scale))
        dp = self._orig.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        if self._angle % 360 != 0:
            dp = dp.transformed(QTransform().rotate(self._angle),
                                Qt.TransformationMode.SmoothTransformation)
        return dp

    def _refresh(self) -> None:
        self.display_pixmap = self._compute_display()
        cw = max(1, self.display_pixmap.width())
        ch = max(1, self.display_pixmap.height())
        new_w, new_h = cw + 2 * _MARGIN, ch + 2 * _MARGIN

        old_center = self.geometry().center()
        self.resize(new_w, new_h)
        if self._initialized:
            # 缩放/旋转后保持窗口中心不动(首次定位由 PinManager 负责)
            self.move(old_center.x() - new_w // 2, old_center.y() - new_h // 2)
        self._canvas.setGeometry(_MARGIN, _MARGIN, cw, ch)
        self._canvas.update()

    # ---- 定位(由 PinManager 调用)----
    def move_center_to(self, point: QPoint) -> None:
        self.move(point.x() - self.width() // 2, point.y() - self.height() // 2)
        self._initialized = True  # 已完成首次定位,后续缩放/旋转保持中心

    def move_content_to(self, global_topleft: QPoint) -> None:
        """把贴图内容(去掉阴影留白)的左上角对齐到指定全局坐标 → 原位贴回。"""
        self.move(global_topleft.x() - _MARGIN, global_topleft.y() - _MARGIN)
        self._initialized = True

    # ---- 缩放 / 旋转 / 不透明度 / 置顶 ----
    def set_scale(self, scale: float) -> None:
        self._scale = clamp_scale(scale)
        self._refresh()

    def zoom(self, factor: float) -> None:
        self.set_scale(self._scale * factor)

    def reset_scale(self) -> None:
        self.set_scale(1.0)

    def rotate(self, delta: int) -> None:
        self._angle = (self._angle + delta) % 360
        self._refresh()

    def set_opacity(self, percent: int) -> None:
        self._opacity = percent
        self.setWindowOpacity(max(0.05, percent / 100.0))

    def toggle_on_top(self, on: bool) -> None:
        self._on_top = on
        geom = self.geometry()  # 暂存位置/尺寸,防止 show() 后系统重置到原点
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on)
        self.show()             # 改 flag 后需重新 show 才生效
        self.setGeometry(geom)  # 恢复原位置/尺寸

    # ---- 复制 / 保存(复用 writer)----
    def _output_image(self):
        """复制/保存用的图像:保留原始分辨率,但体现用户的旋转(所见即所得)。"""
        src = self._orig
        if self._angle % 360 != 0:
            src = src.transformed(QTransform().rotate(self._angle),
                                  Qt.TransformationMode.SmoothTransformation)
        return src.toImage()

    def copy_image(self) -> None:
        ScreenshotWriter.copy_to_clipboard(self._output_image())

    def save_image(self) -> None:
        path = ScreenshotWriter.save_to_file(self._output_image(), self.config)
        if path:
            log.info("贴图已保存:%s", path)
        else:
            log.warning("贴图保存失败")

    # ---- 右键菜单 ----
    def _build_submenus(self, menu: QMenu) -> None:
        """装配缩放 / 不透明度 / 旋转三个二级子菜单。"""
        zoom_menu = menu.addMenu("缩放")
        zoom_menu.addAction("放大", lambda: self.zoom(1.25))
        zoom_menu.addAction("缩小", lambda: self.zoom(0.8))
        zoom_menu.addAction("恢复 100%", self.reset_scale)

        op_menu = menu.addMenu("不透明度")
        for level in _OPACITY_LEVELS:
            a = op_menu.addAction(f"{level}%")
            a.setCheckable(True)
            a.setChecked(level == self._opacity)
            a.triggered.connect(lambda _checked=False, lv=level: self.set_opacity(lv))

        rot_menu = menu.addMenu("旋转")
        rot_menu.addAction("向左旋转 90°", lambda: self.rotate(-90))
        rot_menu.addAction("向右旋转 90°", lambda: self.rotate(90))

    def show_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)

        act_copy = menu.addAction("复制")
        act_copy.setShortcut("Ctrl+C")
        act_copy.triggered.connect(self.copy_image)

        act_save = menu.addAction("保存图片")
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self.save_image)

        act_ocr = menu.addAction("文字识别 (OCR)")
        act_ocr.triggered.connect(self._request_ocr)

        menu.addSeparator()
        self._build_submenus(menu)
        menu.addSeparator()

        act_top = menu.addAction("置顶")
        act_top.setCheckable(True)
        act_top.setChecked(self._on_top)
        act_top.triggered.connect(lambda checked: self.toggle_on_top(checked))

        act_cancel = menu.addAction("取消贴图")
        act_cancel.setShortcut("Esc")
        act_cancel.triggered.connect(self.close)

        act_destroy = menu.addAction("销毁")
        act_destroy.setShortcut("Shift+Esc")
        act_destroy.triggered.connect(self.close)

        menu.exec(global_pos)
        menu.deleteLater()  # 显式回收,避免反复右键累积 QMenu 实例

    def _request_ocr(self) -> None:
        """请求对当前贴图做 OCR;发出体现旋转的图像,由 app_context 弹结果窗。"""
        self.ocr_requested.emit(self._output_image())

    # ---- 交互事件(由 _PinCanvas 转发)----
    def on_press(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            # 用 geometry().topLeft() 与 move() 保持同一坐标系,避免起拖瞬间跳动
            self._drag_offset = event.globalPosition().toPoint() - self.geometry().topLeft()
            self._canvas.setFocus()

    def on_move(self, event) -> None:
        if self._drag_offset is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def on_release(self, event) -> None:
        self._drag_offset = None

    def on_double_click(self, event) -> None:
        # 双击销毁贴图(「恢复100%」保留在右键菜单)
        if event.button() == Qt.MouseButton.LeftButton:
            self.close()

    def on_wheel(self, event) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        self.zoom(_WHEEL_STEP if delta > 0 else 1.0 / _WHEEL_STEP)

    def on_key(self, event) -> None:
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key.Key_Escape:
            self.close()  # 取消贴图 / 销毁均关闭
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom(_WHEEL_STEP)
        elif key == Qt.Key.Key_Minus:
            self.zoom(1.0 / _WHEEL_STEP)
        elif key == Qt.Key.Key_C and (mods & Qt.KeyboardModifier.ControlModifier):
            self.copy_image()
        elif key == Qt.Key.Key_S and (mods & Qt.KeyboardModifier.ControlModifier):
            self.save_image()

    # ---- 生命周期 ----
    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._canvas.setFocus()

    def closeEvent(self, event) -> None:
        self.closed.emit(self)
        super().closeEvent(event)
