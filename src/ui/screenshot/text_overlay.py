"""文字工具就地输入浮层:无边框透明 QTextEdit,贴合画布编辑,完成后由控制器烘焙为标注。

提交时机:失去焦点 / Ctrl+Enter;取消:Esc。高度随内容自适应,避免内部滚动条。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeyEvent
from PySide6.QtWidgets import QFrame, QTextEdit, QWidget


class OverlayTextEdit(QTextEdit):
    """就地文字编辑浮层。"""

    sig_commit = Signal(str)   # 提交文本(非空)
    sig_cancel = Signal()      # 取消编辑

    def __init__(self, color: QColor, pixel_size: int, parent: QWidget | None = None):
        super().__init__(parent)
        self._committed = False

        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(
            f"background: transparent; border: 1px dashed {color.name()}; "
            f"color: {color.name()}; padding: 2px;"
        )
        font = QFont()
        font.setPixelSize(pixel_size)
        self.setFont(font)
        self.setMinimumWidth(80)

        self.textChanged.connect(self._auto_resize)

    def _auto_resize(self) -> None:
        doc = self.document()
        doc.setTextWidth(-1)
        h = int(doc.size().height()) + 12
        w = max(80, int(doc.idealWidth()) + 24)
        self.setFixedSize(w, h)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key.Key_Escape:
            self.sig_cancel.emit()
            return
        # Ctrl+Enter 提交
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (mods & Qt.KeyboardModifier.ControlModifier):
            self._commit()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:
        self._commit()
        super().focusOutEvent(event)

    def _commit(self) -> None:
        if self._committed:
            return
        self._committed = True
        text = self.toPlainText().strip()
        if text:
            self.sig_commit.emit(text)
        else:
            self.sig_cancel.emit()
