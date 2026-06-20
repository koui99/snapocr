"""工具栏图标:Lucide 风格内联 SVG,经 QSvgRenderer 动态着色并渲染为 QIcon。

内联 SVG 而非 PNG → 高分屏锐利、可随状态(默认灰 / 选中白)改色、完全离线无资源文件。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# 各图标的 SVG 内部元素(统一 24x24 viewBox,stroke 由外层注入)
_ICON_BODIES: dict[str, str] = {
    # —— 上排标注工具 ——
    "rect": '<rect x="3" y="3" width="18" height="18" rx="2"/>',
    "ellipse": '<circle cx="12" cy="12" r="9"/>',
    "line": '<line x1="5" y1="19" x2="19" y2="5"/>',
    "arrow": '<path d="M7 7h10v10"/><path d="M7 17 17 7"/>',
    "pen": '<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z"/><path d="m15 5 4 4"/>',
    "marker": ('<path d="m9 11-6 6v3h9l3-3"/>'
               '<path d="m22 12-4.6 4.6a2 2 0 0 1-2.8 0l-5.2-5.2a2 2 0 0 1 0-2.8L14 4"/>'),
    "mosaic": ('<rect x="3" y="3" width="18" height="18" rx="2"/>'
               '<path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>'),
    "text": '<path d="M4 7V4h16v3"/><path d="M9 20h6"/><path d="M12 4v16"/>',
    "sequence": '<circle cx="12" cy="12" r="9"/><path d="M10.5 9 12 8v8"/>',
    "eraser": ('<path d="m7 21-4.3-4.3c-1-1-1-2.5 0-3.4l9.6-9.6c1-1 2.5-1 3.4 0'
               'l5.6 5.6c1 1 1 2.5 0 3.4L13 21"/><path d="M22 21H7"/><path d="m5 11 9 9"/>'),
    # —— 下排操作 ——
    "undo": '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
    "redo": '<path d="m15 14 5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/>',
    "picker": ('<path d="M2 22l4-1 11-11"/><path d="m14 7 3 3"/>'
               '<path d="M17 2.5a2.5 2.5 0 0 1 3.5 3.5L18 8.5 15.5 6z"/>'),
    "pin": ('<path d="M12 17v5"/><path d="M9 10.8a2 2 0 0 1-1.1 1.8l-1.8.9A2 2 0 0 0 5 15.2V16'
            'a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.8a2 2 0 0 0-1.1-1.8l-1.8-.9A2 2 0 0 1 15 10.8V7'
            'a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/>'),
    "copy": ('<rect width="14" height="14" x="8" y="8" rx="2"/>'
             '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>'),
    "save": ('<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5'
             'a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/>'
             '<path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"/>'
             '<path d="M7 3v4a1 1 0 0 0 1 1h7"/>'),
    "ocr": ('<path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/>'
            '<path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/>'
            '<path d="M7 8h8"/><path d="M7 12h10"/><path d="M7 16h6"/>'),
    "cancel": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "confirm": '<path d="M20 6 9 17l-5-5"/>',
}

_SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    "{body}</svg>"
)

_cache: dict[tuple[str, str, int], QIcon] = {}


def render_icon(name: str, color: str = "#333333", size: int = 20) -> QIcon:
    """渲染指定图标为 QIcon;按 (名称, 颜色, 尺寸) 缓存。未知名称返回空 QIcon。"""
    key = (name, color, size)
    if key in _cache:
        return _cache[key]

    body = _ICON_BODIES.get(name)
    if body is None:
        icon = QIcon()
        _cache[key] = icon
        return icon

    svg = _SVG_TEMPLATE.format(color=color, body=body).encode("utf-8")
    renderer = QSvgRenderer(svg)

    dpr = 2  # 2x 物理像素,保证高分屏锐利
    pixmap = QPixmap(size * dpr, size * dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(dpr)

    icon = QIcon(pixmap)
    _cache[key] = icon
    return icon


def available_icons() -> list[str]:
    """返回所有可用图标名称(便于自检 / 测试)。"""
    return list(_ICON_BODIES.keys())
