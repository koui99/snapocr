"""屏幕轻提示浮层(Toast):程序自绘的短暂提示,替代会被 Windows 专注助手拦截的托盘气泡。

无边框 + 置顶 + 半透明圆角胶囊,显示在主屏底部中央,定时淡出自动销毁。
用于「剪贴板没图」「已复制」「已保存」等即时反馈,保证用户一定看得到。
"""
from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGuiApplication,
    QLabel,
    QWidget,
)

# 同一时刻只保留一个 toast,避免叠在一起
_current: "Toast | None" = None


class Toast(QWidget):
    """一次性轻提示浮层。用 Toast.show_text(...) 弹出,不要直接实例化保存。"""

    def __init__(self, text: str, duration_ms: int = 2200) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput  # 不拦截鼠标
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self._label = QLabel(text, self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            "QLabel {"
            "  background-color: rgba(33,33,33,230);"
            "  color: #FFFFFF;"
            "  font-size: 13px;"
            "  padding: 10px 18px;"
            "  border-radius: 8px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect(self._label)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 120))
        self._label.setGraphicsEffect(shadow)

        self._label.adjustSize()
        self.resize(self._label.size())

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self._duration = duration_ms
        self._fade: QPropertyAnimation | None = None

    def _place(self) -> None:
        screen = QGuiApplication.screenAt(self.cursor().pos()) \
            or QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.center().x() - self.width() // 2
        y = geo.bottom() - self.height() - 80  # 离底部留点距离
        self.move(x, y)

    def _show(self) -> None:
        self._place()
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(160)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()
        self._timer.start(self._duration)

    def _fade_out(self) -> None:
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(260)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self.close)
        self._fade.start()

    @classmethod
    def show_text(cls, text: str, duration_ms: int = 2200) -> "Toast":
        """弹出一条轻提示;会先关掉上一条(避免重叠)。"""
        global _current
        if _current is not None:
            try:
                _current.close()
            except Exception:
                pass
        toast = cls(text, duration_ms)
        _current = toast
        toast._show()
        return toast
