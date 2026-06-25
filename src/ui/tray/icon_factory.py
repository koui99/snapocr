"""应用图标工厂:优先加载正式图标资源,缺失时用 QPainter 内存自绘兜底。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

from src.config import paths
from src.ui.theme import tokens


def make_app_icon(size: int = 64) -> QIcon:
    """返回 SnapOCR 正式应用图标。

    打包/开发期均优先加载 src/assets/app_icon.ico;若资源缺失,再绘制一个
    「渐变圆角底 + 截图扫描框 + OCR 文本线」的兜底图标。
    """
    icon_path = paths.resource_path("src/assets/app_icon.ico")
    if icon_path.exists():
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            return icon

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(tokens.COLORS["primary"]))
    radius = size * 0.25
    painter.drawRoundedRect(0, 0, size, size, radius, radius)

    # 截图扫描四角
    pen = QPen(QColor("#FFFFFF"))
    pen.setWidth(max(2, int(size * 0.075)))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    left, top = int(size * 0.28), int(size * 0.28)
    right, bottom = int(size * 0.72), int(size * 0.72)
    seg = int(size * 0.14)
    for x, y, hx, vy in (
        (left, top, 1, 1),
        (right, top, -1, 1),
        (left, bottom, 1, -1),
        (right, bottom, -1, -1),
    ):
        painter.drawLine(x, y, x + hx * seg, y)
        painter.drawLine(x, y, x, y + vy * seg)

    # OCR 文本线
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#FFFFFF"))
    h = max(3, int(size * 0.065))
    painter.drawRoundedRect(int(size * 0.34), int(size * 0.40), int(size * 0.32), h, h / 2, h / 2)
    painter.drawRoundedRect(int(size * 0.34), int(size * 0.52), int(size * 0.27), h, h / 2, h / 2)
    painter.drawRoundedRect(int(size * 0.34), int(size * 0.64), int(size * 0.20), h, h / 2, h / 2)

    # 扫描光束
    painter.setBrush(QColor(184, 255, 245, 140))
    beam_h = max(2, int(size * 0.05))
    painter.drawRoundedRect(int(size * 0.27), int(size * 0.48), int(size * 0.46), beam_h, beam_h / 2, beam_h / 2)
    painter.end()

    return QIcon(pixmap)
