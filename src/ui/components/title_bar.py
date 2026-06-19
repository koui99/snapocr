"""无边框窗口的自定义标题栏:标题 + 关闭按钮,支持鼠标拖拽移动窗口。"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class TitleBar(QWidget):
    """简洁标题栏:左侧标题,右侧关闭按钮(点击关闭宿主窗口)。"""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(40)
        self._drag_offset: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)

        self._title = QLabel(title)
        self._title.setObjectName("titleBarText")

        self._close_btn = QPushButton("✕")  # ✕
        self._close_btn.setObjectName("winCloseBtn")
        self._close_btn.setFixedSize(28, 28)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self._on_close)

        layout.addWidget(self._title)
        layout.addStretch(1)
        layout.addWidget(self._close_btn)

    def _on_close(self) -> None:
        win = self.window()
        if win is not None:
            win.close()

    # ---- 拖拽移动宿主窗口 ----
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        event.accept()
