"""快捷键录制输入框:点击「修改」进入录制态,捕获组合键并以标准文本显示。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QLineEdit

_MODIFIER_KEYS = {
    Qt.Key.Key_Control,
    Qt.Key.Key_Shift,
    Qt.Key.Key_Alt,
    Qt.Key.Key_Meta,
}


class HotkeyLineEdit(QLineEdit):
    """只读输入框,重写键盘事件以录制快捷键。

    sequence_changed(str) 在录制到有效快捷键或被清空时发射(空串表示「无」)。
    """

    sequence_changed = Signal(str)

    def __init__(self, sequence: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sequence = sequence
        self._recording = False
        self.setText(sequence if sequence else "无")

    def sequence(self) -> str:
        return self._sequence

    def set_sequence(self, sequence: str) -> None:
        self._sequence = sequence
        self.setText(sequence if sequence else "无")

    def start_recording(self) -> None:
        """进入录制状态(由外部「修改」按钮调用)。"""
        self._recording = True
        self._set_recording_style(True)
        self.setText("请按下快捷键…")
        self.setFocus()

    def _set_recording_style(self, on: bool) -> None:
        # 通过动态属性驱动 QSS([recording="true"]),需 unpolish/polish 刷新样式
        self.setProperty("recording", "true" if on else "false")
        style = self.style()
        style.unpolish(self)
        style.polish(self)

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt 接口命名)
        if not self._recording:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key.Key_Escape:                       # 取消录制,恢复原值
            self._finish(self._sequence)
            return
        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):  # 清空绑定
            self._finish("")
            return
        if key in _MODIFIER_KEYS:                          # 仅修饰键:继续等待主键
            event.accept()
            return
        seq = QKeySequence(event.keyCombination()).toString()
        if seq:
            self._finish(seq)
        else:
            event.accept()

    def _finish(self, sequence: str) -> None:
        self._recording = False
        self._set_recording_style(False)
        self._sequence = sequence
        self.setText(sequence if sequence else "无")
        if self.hasFocus():  # 失焦流程中再调 clearFocus 多余,加判断避免焦点链问题
            self.clearFocus()
        self.sequence_changed.emit(sequence)

    def focusOutEvent(self, event) -> None:  # noqa: N802 (Qt 接口命名)
        if self._recording:
            # 失焦视为放弃本次录制,恢复原值
            self._finish(self._sequence)
        super().focusOutEvent(event)
