"""二级属性条(上下文浮层):选中绘图工具时弹出,提供线条粗细(细/中/粗)与 8 色色板。

作为截图窗口的子控件,自绘圆角气泡(顶部小尖角)+ 自命中点击,无子控件依赖。
变更通过 sig_width_changed / sig_color_changed 上抛给标注控制器。
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from src.ui.theme.tokens import COLORS

# 三档粗细(像素)与对应展示半径
WIDTH_OPTIONS = [2, 4, 6]
_WIDTH_DOT_RADIUS = {2: 3, 4: 5, 6: 7}

# 8 色色板
PALETTE = [
    "#EF4444",  # 红
    "#F97316",  # 橙
    "#FACC15",  # 黄
    "#22C55E",  # 绿
    "#2D7FF9",  # 蓝(主色)
    "#A855F7",  # 紫
    "#1F2937",  # 近黑
    "#FFFFFF",  # 白
]

_ARROW_H = 7
_PAD = 12
_CELL_W = 26
_SWATCH = 18
_SWATCH_GAP = 6
_SEP_W = 13
_CONTENT_H = 38


class PropertyBar(QWidget):
    """绘图属性上下文浮层。"""

    sig_width_changed = Signal(int)
    sig_color_changed = Signal(QColor)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self._active_width = WIDTH_OPTIONS[0]
        self._active_color = QColor(COLORS["primary"])

        # 预计算各命中区域(局部坐标)
        self._width_rects: list[tuple[int, QRect]] = []
        self._color_rects: list[tuple[str, QRect]] = []
        self._build_layout()

    def _build_layout(self) -> None:
        top = _ARROW_H
        x = _PAD
        for w in WIDTH_OPTIONS:
            self._width_rects.append((w, QRect(x, top, _CELL_W, _CONTENT_H)))
            x += _CELL_W
        x += _SEP_W  # 分隔线区
        cy = top + (_CONTENT_H - _SWATCH) // 2
        for hex_color in PALETTE:
            self._color_rects.append((hex_color, QRect(x, cy, _SWATCH, _SWATCH)))
            x += _SWATCH + _SWATCH_GAP
        total_w = x - _SWATCH_GAP + _PAD
        self.setFixedSize(total_w, top + _CONTENT_H + _PAD // 2)

    # ---- 外部状态同步 ----
    def set_active(self, width: int, color: QColor) -> None:
        """同步当前激活的粗细与颜色(用于高亮显示)。"""
        self._active_width = width
        self._active_color = QColor(color)
        self.update()

    # ---- 绘制 ----
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 气泡主体(白底圆角 + 边框)
        body = QRect(0, _ARROW_H, self.width(), self.height() - _ARROW_H - _PAD // 2)
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.setBrush(QColor(COLORS["bg_card"]))
        painter.drawRoundedRect(body, 10, 10)

        # 顶部小尖角(指向上方工具栏)
        cx = self.width() // 2
        painter.setPen(Qt.PenStyle.NoPen)
        from PySide6.QtGui import QPolygon
        arrow = QPolygon([
            QPoint(cx - 7, _ARROW_H + 1),
            QPoint(cx + 7, _ARROW_H + 1),
            QPoint(cx, 0),
        ])
        painter.setBrush(QColor(COLORS["bg_card"]))
        painter.drawPolygon(arrow)
        # 尖角描边(两斜边)
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawLine(QPoint(cx - 7, _ARROW_H + 1), QPoint(cx, 0))
        painter.drawLine(QPoint(cx, 0), QPoint(cx + 7, _ARROW_H + 1))

        # 三档粗细圆点
        for w, rect in self._width_rects:
            selected = (w == self._active_width)
            if selected:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(COLORS["primary_active_bg"]))
                painter.drawRoundedRect(rect.adjusted(2, 4, -2, -4), 6, 6)
            r = _WIDTH_DOT_RADIUS[w]
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(COLORS["primary"] if selected else COLORS["text_secondary"]))
            painter.drawEllipse(rect.center(), r, r)

        # 分隔线
        sep_x = self._width_rects[-1][1].right() + _SEP_W // 2
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawLine(sep_x, _ARROW_H + 8, sep_x, _ARROW_H + _CONTENT_H - 8)

        # 8 色板
        for hex_color, rect in self._color_rects:
            painter.setPen(QPen(QColor(COLORS["border"]), 1))
            painter.setBrush(QColor(hex_color))
            painter.drawRoundedRect(rect, 4, 4)
            if QColor(hex_color).name().lower() == self._active_color.name().lower():
                # 选中:外描主色环
                painter.setPen(QPen(QColor(COLORS["primary"]), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), 6, 6)
        painter.end()

    # ---- 命中点击 ----
    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        for w, rect in self._width_rects:
            if rect.contains(pos):
                self._active_width = w
                self.sig_width_changed.emit(w)
                self.update()
                return
        for hex_color, rect in self._color_rects:
            if rect.contains(pos):
                self._active_color = QColor(hex_color)
                self.sig_color_changed.emit(QColor(hex_color))
                self.update()
                return
