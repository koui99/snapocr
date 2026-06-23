"""贴图下方的 OCR 文字面板(就地呈现,不弹新窗,不遮挡原图)。

呈现:原图保持原样不被遮挡;识别出的文字接在图的**正下方**一条独立面板里。
- 展开态:深色圆角底 + 等宽排版可选文本 +「收起」按钮 → 任意底图(含纯白)都清晰;
- 收起态:整个深色框消失,只在图下方留一个小「显示文字」按钮(深色药丸,任意背景可见);
- 文字按 box 坐标**重建原图排版**(同一横排合到一行、保留左缩进、行间留空),等宽字体呈现;
- 整段是一个只读 QTextEdit → 可跨行框选 / Ctrl+A 全选 / Ctrl+C 一起复制;
- 面板是 PinWindow 的子控件(非独立窗口);右键「文字识别」可整体清除。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.logger import get_logger

log = get_logger("pin.ocr_panel")

_BG = QColor(22, 22, 26, 235)   # 深色圆角底(近不透明,保证白底图上文字也清晰)
_RADIUS = 8
_LINE_PX = 20                   # 估算每行高度,用于计算面板高
_HEADER_H = 26                  # 标题行(提示 + 按钮)估高
_MIN_H = 40
_MAX_H = 260
_COLLAPSED_H = 26               # 收起态:只剩小按钮的高度

# 小按钮深色药丸样式:收起态浮在桌面上也要看得见,故用近不透明深底
_BTN_QSS = (
    "QPushButton {"
    "  color: #FFFFFF; background: rgba(22,22,26,235);"
    "  border: none; border-radius: 4px; padding: 1px 12px; font-size: 11px;"
    "}"
    "QPushButton:hover { background: rgba(45,127,249,235); }"
)


class OcrTextPanel(QWidget):
    """接在贴图下方的 OCR 文字面板:展开=深色框+文字;收起=只留一个小按钮。"""

    toggled = Signal()  # 收起/展开后发射,供 PinWindow 重算窗口高度

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        # 收起态要露出桌面(只剩按钮),故面板自身透明,深色底仅在展开态由 paintEvent 画
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._has = False
        self._line_count = 0
        self._collapsed = False

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 7, 10, 9)
        self._layout.setSpacing(4)

        # 标题行:左「收起/显示文字」按钮 + 提示文字 + 右侧弹簧
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self._toggle_btn = QPushButton("收起", self)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setFixedHeight(20)
        self._toggle_btn.setStyleSheet(_BTN_QSS)
        self._toggle_btn.clicked.connect(self._on_toggle)
        header.addWidget(self._toggle_btn)

        self._hint = QLabel("识别文字 · Ctrl+A 全选 · Ctrl+C 复制", self)
        self._hint.setStyleSheet(
            "color: rgba(255,255,255,150); font-size: 11px; background: transparent;"
        )
        header.addWidget(self._hint)
        header.addStretch(1)
        self._layout.addLayout(header)

        self._edit = QTextEdit(self)
        self._edit.setReadOnly(True)
        self._edit.setFrameShape(QFrame.Shape.NoFrame)
        # 不自动换行:重建的排版靠空格对齐,自动换行会打乱列位
        self._edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self._edit.setStyleSheet(
            "QTextEdit {"
            "  background: transparent;"
            "  color: #F2F2F2;"
            "  border: none;"
            "  selection-background-color: rgba(45,127,249,220);"
            "  selection-color: #FFFFFF;"
            "}"
        )
        f = self._edit.font()
        # 等宽字体让按列对齐的空格缩进真正对齐(贴近原图版式)
        f.setFamily("Consolas")
        f.setStyleHint(f.StyleHint.Monospace)
        f.setFixedPitch(True)
        f.setPixelSize(14)
        self._edit.setFont(f)
        self._layout.addWidget(self._edit)

    # ---- 绘制深色圆角底(仅展开态)----
    def paintEvent(self, event) -> None:
        if self._collapsed:
            return  # 收起态:整框透明,只剩小按钮浮在图下方
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(_BG)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), _RADIUS, _RADIUS)
        painter.end()

    # ---- 收起 / 展开 ----
    def _on_toggle(self) -> None:
        self._set_collapsed(not self._collapsed)
        self.toggled.emit()  # 通知 PinWindow 重算高度

    def _set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._edit.setVisible(not collapsed)
        self._hint.setVisible(not collapsed)
        self._toggle_btn.setText("显示文字" if collapsed else "收起")
        # 收起态贴紧图下方(去掉给深色框留的内边距),展开态恢复
        if collapsed:
            self._layout.setContentsMargins(0, 0, 0, 0)
        else:
            self._layout.setContentsMargins(10, 7, 10, 9)
        self.update()

    def is_collapsed(self) -> bool:
        return self._collapsed

    # ---- 内容 ----
    def build(self, lines: list) -> int:
        """按 box 坐标重建原图排版,合成一段可选文本。返回重建后的文本行数。"""
        text = _reconstruct_text(lines)
        self._edit.setPlainText(text)
        self._line_count = text.count("\n") + 1 if text else 0
        self._has = bool(text)
        self._set_collapsed(False)
        self.show()
        self.raise_()
        # 默认全选,Ctrl+C 即可一次性复制全部;想要局部再自行框选
        self._edit.selectAll()
        self._edit.setFocus()
        return self._line_count

    def desired_height(self) -> int:
        """按状态/行数估算面板高度;收起态只留小按钮,展开态按行数(钳制区间)。"""
        if self._collapsed:
            return _COLLAPSED_H
        body = _HEADER_H + self._line_count * _LINE_PX + 18
        return max(_MIN_H, min(_MAX_H, body))

    def clear_fields(self) -> None:
        self._edit.clear()
        self._has = False
        self._line_count = 0
        self._set_collapsed(False)

    def has_fields(self) -> bool:
        return self._has


# ============== 排版重建(按 box 坐标还原原图版式) ==============

def _box_geom(box):
    """把四角 box → (left, top, right, bottom);非法返回 None。"""
    if not box:
        return None
    try:
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
    except (TypeError, ValueError, IndexError):
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _reconstruct_text(lines: list) -> str:
    """依据每行文字框坐标重建版式:
    - 纵向中心相近的合到同一文本行(原图横排);
    - 行内按左 x 排序,用空格按列位还原左缩进 / 间隔;
    - 行与行的较大纵向间隙补空行(还原段落间距)。
    任一行缺 box(无法定位)则退化为简单按序换行拼接。"""
    items = []  # (geom, text)
    for ln in lines:
        text = (getattr(ln, "text", "") or "")
        if not text.strip():
            continue
        geom = _box_geom(getattr(ln, "box", None))
        items.append((geom, text))

    if not items:
        return ""
    # 有任何一行拿不到坐标 → 无法可靠重排,退化为顺序拼接(不假装排版)
    if any(g is None for g, _ in items):
        return "\n".join(t for _, t in items)

    items.sort(key=lambda it: it[0][1])  # 按 top 升序
    heights = [g[3] - g[1] for g, _ in items]
    avg_h = (sum(heights) / len(heights)) if heights else 14.0
    avg_h = max(1.0, avg_h)

    # 分组成「行」:纵向中心相近视为同一横排
    rows = []
    cur = [items[0]]
    cur_top, cur_bottom = items[0][0][1], items[0][0][3]
    for geom, text in items[1:]:
        top, bottom = geom[1], geom[3]
        center = (top + bottom) / 2
        cur_center = (cur_top + cur_bottom) / 2
        if abs(center - cur_center) < avg_h * 0.6:
            cur.append((geom, text))
            cur_top, cur_bottom = min(cur_top, top), max(cur_bottom, bottom)
        else:
            rows.append((cur_top, cur_bottom, cur))
            cur = [(geom, text)]
            cur_top, cur_bottom = top, bottom
    rows.append((cur_top, cur_bottom, cur))

    # 以等宽字符列还原缩进:一列 ≈ 半个平均字高
    char_w = max(1.0, avg_h * 0.5)
    min_left = min(g[0] for g, _ in items)

    out: list[str] = []
    prev_bottom = None
    for rtop, rbottom, cells in rows:
        if prev_bottom is not None:
            gap = rtop - prev_bottom
            if gap > avg_h * 0.8:
                out.extend([""] * min(2, int(gap / avg_h)))
        cells.sort(key=lambda c: c[0][0])  # 行内按左 x
        line = ""
        for geom, text in cells:
            col = int((geom[0] - min_left) / char_w)
            if col > len(line):
                line += " " * (col - len(line))
            elif line and not line.endswith(" "):
                line += " "  # 同行相邻块至少留一个空格
            line += text
        out.append(line.rstrip())
        prev_bottom = rbottom
    return "\n".join(out)
