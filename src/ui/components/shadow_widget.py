"""阴影工具:用 QGraphicsDropShadowEffect 为内容控件渲染柔和投影。

无边框顶级窗口直接加阴影会被裁剪,故配合「外补齐」使用:外层透明窗口留出边距,
真正的内容放在 inner 容器上,对 inner 调用本函数。
"""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

from src.ui.theme import tokens


def apply_shadow(widget: QWidget, heavy: bool = False) -> None:
    """给指定控件施加 design token 定义的阴影。"""
    spec = tokens.SHADOW_HEAVY if heavy else tokens.SHADOW_SOFT
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(spec["blur"])
    effect.setXOffset(spec["x"])
    effect.setYOffset(spec["y"])
    effect.setColor(QColor(0, 0, 0, spec["alpha"]))
    widget.setGraphicsEffect(effect)
