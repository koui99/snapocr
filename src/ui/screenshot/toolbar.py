"""截图工具栏:双排布局(上排 10 个标注工具 + 下排操作),还原 mockup 界面①。

作为截图窗口子控件浮于选区附近。工具按钮互斥可反选;操作按钮即时触发。
所有交互通过 sig_tool_selected / sig_action 上抛给标注控制器与窗口。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.ui.components.shadow_widget import apply_shadow
from src.ui.screenshot import icons
from src.ui.theme.tokens import COLORS, qss_replacements

# 上排标注工具:(标识, 中文提示)
_TOOLS = [
    ("rect", "矩形"), ("ellipse", "椭圆"), ("line", "直线"), ("arrow", "箭头"),
    ("pen", "画笔"), ("marker", "马克笔"), ("mosaic", "马赛克"), ("text", "文字"),
    ("sequence", "序号标记"), ("eraser", "橡皮擦"),
]

# 下排操作分区:每段为 (标识, 提示) 列表,段间插竖分隔线
_ACTION_GROUPS = [
    [("undo", "撤销 (Ctrl+Z)"), ("redo", "重做 (Ctrl+Y)")],
    [("picker", "取色")],
    [("pin", "钉图"), ("copy", "复制"), ("save", "保存"), ("ocr", "文字识别")],
    [("cancel", "取消 (Esc)"), ("confirm", "确认 (Enter)")],
]

_ICON_GRAY = COLORS["text_main"]
_ICON_WHITE = "#FFFFFF"

_QSS_TEMPLATE = """
#ToolbarContent {
    background-color: @bg_card;
    border: 1px solid @border;
    border-radius: @radius_lg;
}
QToolButton {
    background-color: transparent;
    border: none;
    border-radius: @radius_sm;
    padding: 5px;
}
QToolButton:hover {
    background-color: @primary_active_bg;
}
QToolButton:checked {
    background-color: @primary;
}
QToolButton#OcrButton {
    background-color: @primary;
    color: #FFFFFF;
    font-weight: bold;
    padding: 5px 10px;
}
QToolButton#OcrButton:hover {
    background-color: @primary_hover;
}
QFrame#VSep {
    color: @border;
}
"""


def _apply_tokens(qss: str) -> str:
    for ph, val in qss_replacements().items():
        qss = qss.replace(ph, val)
    return qss


class ScreenshotToolbar(QWidget):
    """双排截图工具栏。"""

    sig_tool_selected = Signal(str)   # 工具标识;空串表示取消选择(回到选区模式)
    sig_action = Signal(str)          # 操作标识(undo/redo/picker/pin/copy/save/ocr/cancel/confirm)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._tool_buttons: dict[str, QToolButton] = {}
        self._action_buttons: dict[str, QToolButton] = {}
        self._current_tool: str | None = None

        self._build_ui()

    # ---- 构建 ----
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)  # 留白给阴影
        outer.setSpacing(0)

        content = QWidget(self)
        content.setObjectName("ToolbarContent")
        content.setStyleSheet(_apply_tokens(_QSS_TEMPLATE))
        apply_shadow(content)
        outer.addWidget(content)

        v = QVBoxLayout(content)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(4)

        # 上排:标注工具
        tools_row = QHBoxLayout()
        tools_row.setSpacing(2)
        for name, tip in _TOOLS:
            btn = self._make_button(name, tip, checkable=True)
            btn.clicked.connect(lambda _=False, n=name: self._on_tool_clicked(n))
            self._tool_buttons[name] = btn
            tools_row.addWidget(btn)
        v.addLayout(tools_row)

        # 下排:操作
        actions_row = QHBoxLayout()
        actions_row.setSpacing(2)
        for gi, group in enumerate(_ACTION_GROUPS):
            if gi > 0:
                actions_row.addWidget(self._make_separator())
            for name, tip in group:
                btn = self._make_button(name, tip, checkable=False)
                if name == "ocr":
                    btn.setObjectName("OcrButton")
                    btn.setText("识别")
                    btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                btn.clicked.connect(lambda _=False, n=name: self.sig_action.emit(n))
                self._action_buttons[name] = btn
                actions_row.addWidget(btn)
        v.addLayout(actions_row)

        self.set_undo_enabled(False)
        self.set_redo_enabled(False)

    def _make_button(self, name: str, tip: str, checkable: bool) -> QToolButton:
        btn = QToolButton(self)
        btn.setToolTip(tip)
        btn.setCheckable(checkable)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setIconSize(self._icon_size())
        color = _ICON_WHITE if name == "ocr" else _ICON_GRAY
        btn.setIcon(icons.render_icon(name, color, 20))
        return btn

    @staticmethod
    def _icon_size():
        from PySide6.QtCore import QSize
        return QSize(20, 20)

    def _make_separator(self) -> QFrame:
        sep = QFrame(self)
        sep.setObjectName("VSep")
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"color:{COLORS['border']}; background:{COLORS['border']}; margin:4px 4px;")
        return sep

    # ---- 工具选择(互斥 + 可反选)----
    def _on_tool_clicked(self, name: str) -> None:
        if self._current_tool == name:
            # 再次点击当前工具 → 取消选择
            self._current_tool = None
        else:
            self._current_tool = name
        self._refresh_tool_state()
        self.sig_tool_selected.emit(self._current_tool or "")

    def _refresh_tool_state(self) -> None:
        for n, btn in self._tool_buttons.items():
            checked = (n == self._current_tool)
            btn.setChecked(checked)
            btn.setIcon(icons.render_icon(n, _ICON_WHITE if checked else _ICON_GRAY, 20))

    def clear_tool_selection(self) -> None:
        """外部强制清空工具选择(如完成一次绘制后回到选区模式)。"""
        self._current_tool = None
        self._refresh_tool_state()

    @property
    def current_tool(self) -> str | None:
        return self._current_tool

    # ---- 操作按钮可用态 ----
    def set_undo_enabled(self, enabled: bool) -> None:
        if "undo" in self._action_buttons:
            self._action_buttons["undo"].setEnabled(enabled)

    def set_redo_enabled(self, enabled: bool) -> None:
        if "redo" in self._action_buttons:
            self._action_buttons["redo"].setEnabled(enabled)
