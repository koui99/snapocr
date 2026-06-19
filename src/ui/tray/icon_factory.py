"""占位图标工厂:无图标资源时用 QPainter 内存自绘,避免托盘因缺图而异常。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

from src.ui.theme import tokens


def make_app_icon(size: int = 64) -> QIcon:
    """生成「主色圆角底 + 白色字母 S」的占位应用/托盘图标。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(tokens.COLORS["primary"]))
    radius = size * 0.25
    painter.drawRoundedRect(0, 0, size, size, radius, radius)

    painter.setPen(QColor("#FFFFFF"))
    font = QFont()
    font.setBold(True)
    font.setPixelSize(int(size * 0.6))
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "S")
    painter.end()

    return QIcon(pixmap)
