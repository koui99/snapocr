"""贴图上的 OCR 文字浮层:在识别出的每行文字原位叠一个只读可选文本框。

用途:贴图右键「文字识别」后,不弹新窗,直接在图上原位置叠加可选中、可复制的文字
(图不动)。每行一个透明只读 QLineEdit,鼠标划选即可复制;再次点「文字识别」可隐藏。

坐标:box 为识别图(原始分辨率 _orig)的像素坐标;浮层覆盖 canvas,按当前缩放 scale 映射。
旋转态(angle≠0)下不叠加(坐标无法简单映射),给提示。
"""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import QLineEdit, QWidget

from src.core.logger import get_logger

log = get_logger("pin.ocr_overlay")


class _SelectableLine(QLineEdit):
    """单行只读可选文本:透明底 + 浅高亮,鼠标划选可 Ctrl+C 复制。"""

    def __init__(self, text: str, parent: QWidget) -> None:
        super().__init__(text, parent)
        self.setReadOnly(True)
        self.setFrame(False)
        self.setTextMargins(0, 0, 0, 0)  # 清默认边距,防窄框文字被上下裁剪
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.setStyleSheet(
            "QLineEdit {"
            "  background-color: rgba(255,255,255,180);"
            "  color: #111111;"
            "  border: none;"
            "  padding: 0px 1px;"
            "}"
            "QLineEdit:focus { background-color: rgba(255,255,80,200); }"
        )


class OcrTextOverlay(QWidget):
    """覆盖在 canvas 上的文字浮层。build(lines, scale) 摆放,reposition(scale) 跟随缩放。"""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._lines: list = []          # 缓存 (text, box)
        self._fields: list[_SelectableLine] = []

    @staticmethod
    def _box_rect(box, scale: float) -> QRect | None:
        """把四角 box 映射成缩放后的外接矩形;box 不合法返回 None。"""
        try:
            xs = [float(p[0]) for p in box]
            ys = [float(p[1]) for p in box]
        except (TypeError, ValueError, IndexError):
            return None
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        # 两端点分别缩放再相减,避免「左上角缩放 + 宽高缩放」各自截断累积 1px 漂移
        x = int(x0 * scale)
        y = int(y0 * scale)
        w = max(1, int(x1 * scale) - x)
        h = max(1, int(y1 * scale) - y)
        return QRect(x, y, w, h)

    def build(self, lines: list, scale: float) -> int:
        """按识别结果创建可选文本框。返回成功摆放的行数。"""
        self.clear_fields()
        self._lines = [(ln.text, ln.box) for ln in lines if ln.box]
        placed = 0
        for text, box in self._lines:
            rect = self._box_rect(box, scale)
            if rect is None:
                continue
            field = _SelectableLine(text, self)
            field.setGeometry(rect)
            # 字号按框高自适应,贴近原图观感
            f = field.font()
            f.setPixelSize(max(8, int(rect.height() * 0.72)))
            field.setFont(f)
            field.show()
            self._fields.append(field)
            placed += 1
        self.show()
        self.raise_()
        return placed

    def reposition(self, scale: float) -> None:
        """缩放变化时按新比例重排各文本框。"""
        for field, (_text, box) in zip(self._fields, self._lines):
            rect = self._box_rect(box, scale)
            if rect is None:
                continue
            field.setGeometry(rect)
            f = field.font()
            f.setPixelSize(max(8, int(rect.height() * 0.72)))
            field.setFont(f)

    def clear_fields(self) -> None:
        for field in self._fields:
            field.deleteLater()
        self._fields.clear()
        self._lines.clear()

    def has_fields(self) -> bool:
        return bool(self._fields)
