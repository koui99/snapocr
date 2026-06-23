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

    def __init__(self, config, ocr_handler=None) -> None:
        self._config = config
        self._pins: list[PinWindow] = []
        self._hidden = False
        # OCR 请求回调:贴图右键「文字识别」时,把当前图像交给 app_context 弹结果窗
        self._ocr_handler = ocr_handler

    # ---- 创建 ----
    def pin_image(self, image, at: QPoint | None = None,
                  at_topleft: QPoint | None = None,
                  source_ratio: float = 1.0,
                  center_on_screen: bool = False,
                  then_ocr: bool = False) -> PinWindow | None:
        """把图片钉到桌面。image 可为 QImage 或 QPixmap。
        at_topleft:内容左上角对齐的全局坐标(截图「钉图」原位贴回时用);
        at:期望中心点(剪贴板贴图时用,默认光标处)。三者优先级:at_topleft > center_on_screen > at。
        source_ratio:截图来源屏的 DPI 缩放比,使贴图与原区域同尺寸;剪贴板贴图取目标屏 DPI。
        center_on_screen:贴到光标所在屏的正中(剪贴板贴图用)。
        then_ocr:钉出后立刻原地识别并叠加可选文字(截图「识别」用)。"""
        pixmap = image if isinstance(image, QPixmap) else QPixmap.fromImage(image)
        if pixmap is None or pixmap.isNull():
            log.warning("贴图失败:图片为空")
            return None

        win = PinWindow(pixmap, self._config, source_ratio=source_ratio)
        win.closed.connect(self._on_closed)
        if self._ocr_handler is not None:
            win.ocr_requested.connect(self._ocr_handler)

        if at_topleft is not None:
            # 原位贴回:坐标本就在屏内,不做 clamp(否则阴影留白会把贴图顶偏 16px)
            win.move_content_to(at_topleft)
        elif center_on_screen:
            anchor = at or QCursor.pos()
            screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
            geo = (screen.availableGeometry() if screen else None)
            center = geo.center() if geo else anchor
            win.move_center_to(center)
            self._clamp_to_screen(win, center)
        else:
            anchor = at or QCursor.pos()
            win.move_center_to(anchor)
            self._clamp_to_screen(win, anchor)

        win.show()
        win.raise_()
        win.activateWindow()
        if then_ocr:
            win.start_inplace_ocr()
        self._pins.append(win)
        self._hidden = False
        log.info("已创建贴图浮窗(当前共 %d 个)", len(self._pins))
        return win

    def pin_from_clipboard(self, then_ocr: bool = False) -> PinWindow | None:
        """从系统剪贴板取图贴出;剪贴板无图返回 None。
        尺寸校正:剪贴板图多为物理像素(如截图复制的),按光标所在屏 DPI 折算回逻辑尺寸,
        使其与「当初屏幕上看到的大小」一致,而非在高分屏上被放大。贴到屏幕正中。
        then_ocr:贴出后立刻在图下方展开 OCR 文字面板(F4 / 托盘「文字识别」用)。"""
        clipboard = QGuiApplication.clipboard()
        image = clipboard.image()
        if image is None or image.isNull():
            log.info("剪贴板没有图片,无法贴图")
            return None
        # 优先用图自带的 DPR;没有则取光标所在屏的 DPI
        ratio = float(image.devicePixelRatio() or 0.0)
        if ratio <= 1.0:
            screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
            ratio = float(screen.devicePixelRatio()) if screen else 1.0
        return self.pin_image(image, source_ratio=max(1.0, ratio),
                              center_on_screen=True, then_ocr=then_ocr)

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
