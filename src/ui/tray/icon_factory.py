"""应用图标工厂:优先加载正式图标资源,缺失时用 QPainter 内存自绘兜底。

注意:
- Windows 文件管理器里的 exe 图标来自 PyInstaller 写入 PE 资源的 app_icon.ico。
- 运行时窗口/托盘图标来自 Qt(QApplication/QSystemTrayIcon)加载的 QIcon。

为避免 PyInstaller 包内 Qt 缺少 qico 插件时 .ico 加载失败,运行时优先加载
由 tools/generate_app_icon.py 从同一设计生成的 PNG 多尺寸变体。这样托盘图标
和 exe 图标使用同一套源图,不会再落到旧的自绘占位图。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

from src.config import paths
from src.ui.theme import tokens

_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
_APP_ICON: QIcon | None = None


def _load_runtime_png_icon() -> QIcon | None:
    """加载运行时 PNG 多尺寸图标。

    QSystemTrayIcon 会按系统托盘尺寸选择 16/24/32 等小图;文件管理器会按视图
    使用 ico 中的大图。PNG 变体和 ico 由同一脚本生成,视觉保持一致。
    """
    icon = QIcon()
    for size in _ICON_SIZES:
        path = paths.resource_path(f"src/assets/app_icon_{size}.png")
        if not path.exists():
            continue
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            icon.addPixmap(pixmap)
    return None if icon.isNull() else icon


def make_app_icon(size: int = 64) -> QIcon:
    """返回 SnapOCR 正式应用图标。

    打包/开发期优先加载 src/assets/app_icon_<size>.png 多尺寸变体;若旧包未
    带 PNG,再回退 src/assets/app_icon.ico;若资源缺失,最后绘制一个「渐变
    圆角底 + 截图扫描框 + OCR 文本线」的兜底图标。
    """
    global _APP_ICON
    if _APP_ICON is not None:
        return _APP_ICON

    runtime_icon = _load_runtime_png_icon()
    if runtime_icon is not None:
        _APP_ICON = runtime_icon
        return _APP_ICON

    icon_path = paths.resource_path("src/assets/app_icon.ico")
    if icon_path.exists():
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            _APP_ICON = icon
            return _APP_ICON

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

    _APP_ICON = QIcon(pixmap)
    return _APP_ICON
