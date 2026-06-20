"""贴图管理器 PinManager:统一创建、定位、跟踪所有贴图浮窗。

- pin_image:从 QImage/QPixmap 创建贴图,定位到光标处并 show。
- pin_from_clipboard:读系统剪贴板图片贴出(无图返回 None,由调用方提示)。
- toggle_all:Shift+F3 一键显隐全部贴图。
- 贴图关闭(closed 信号)自动从列表移除,避免引用泄漏。
"""
from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtGui import QCursor, QGuiApplication, QImage, QPixmap

from src.core.logger import get_logger
from src.ui.pin.pin_window import PinWindow

log = get_logger("pin.manager")


class PinManager:
    """贴图浮窗集合管理。"""

    def __init__(self, config) -> None:
        self._config = config
        self._pins: list[PinWindow] = []
        self._hidden = False

    # ---- 创建 ----
    def pin_image(self, image, at: QPoint | None = None) -> PinWindow | None:
        """把图片钉到桌面。image 可为 QImage 或 QPixmap;at 为期望中心点(默认光标处)。"""
        pixmap = image if isinstance(image, QPixmap) else QPixmap.fromImage(image)
        if pixmap is None or pixmap.isNull():
            log.warning("贴图失败:图片为空")
            return None

        win = PinWindow(pixmap, self._config)
        win.closed.connect(self._on_closed)

        center = at or QCursor.pos()
        win.move_center_to(center)
        self._clamp_to_screen(win, center)

        win.show()
        win.raise_()
        win.activateWindow()
        self._pins.append(win)
        self._hidden = False
        log.info("已创建贴图浮窗(当前共 %d 个)", len(self._pins))
        return win

    def pin_from_clipboard(self) -> PinWindow | None:
        """从系统剪贴板取图贴出;剪贴板无图返回 None。"""
        clipboard = QGuiApplication.clipboard()
        image = clipboard.image()
        if image is None or image.isNull():
            log.info("剪贴板没有图片,无法贴图")
            return None
        return self.pin_image(image)

    # ---- 显隐 / 关闭 ----
    def toggle_all(self) -> None:
        """Shift+F3:在「全部隐藏」与「全部显示」间切换。"""
        if not self._pins:
            return
        if self._hidden:
            for w in self._pins:
                w.show()
            self._hidden = False
            log.info("显示全部贴图(%d 个)", len(self._pins))
        else:
            for w in self._pins:
                w.hide()
            self._hidden = True
            log.info("隐藏全部贴图(%d 个)", len(self._pins))

    def close_all(self) -> None:
        for w in list(self._pins):
            try:
                w.close()
            except Exception:
                pass
        self._pins.clear()

    def count(self) -> int:
        return len(self._pins)

    # ---- 内部 ----
    def _on_closed(self, win: PinWindow) -> None:
        if win in self._pins:
            self._pins.remove(win)
            log.info("贴图已关闭(剩余 %d 个)", len(self._pins))

    def _clamp_to_screen(self, win: PinWindow, center: QPoint) -> None:
        """把贴图限制在光标所在屏幕的可用区域内,避免钉到屏幕外看不见。"""
        screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        w, h = win.width(), win.height()
        # 用 x()+width() 取右/下边界(QRect.right()/bottom() 会少 1 像素)
        max_x = max(geo.left(), geo.x() + geo.width() - w)
        max_y = max(geo.top(), geo.y() + geo.height() - h)
        x = min(max(win.x(), geo.left()), max_x)
        y = min(max(win.y(), geo.top()), max_y)
        win.move(x, y)
