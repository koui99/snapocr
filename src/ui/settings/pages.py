"""设置窗的各子页面。M1 完整实现「常规」「热键」「关于」,其余页给出结构占位。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.hotkey.base import ACTIONS, ACTION_LABELS
from src.ui.components.hotkey_edit import HotkeyLineEdit


class BasePage(QWidget):
    """页面基类:统一顶部标题 + 内容垂直布局。"""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # 让自定义 QWidget 子类也能渲染 QSS 背景(否则 background-color 静默失效)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(20, 20, 20, 20)
        self._root.setSpacing(14)

        heading = QLabel(title)
        heading.setProperty("pageTitle", "true")
        self._root.addWidget(heading)

    def add_widget(self, w: QWidget) -> None:
        self._root.addWidget(w)

    def add_stretch(self) -> None:
        self._root.addStretch(1)

    def collect(self) -> dict:
        """返回本页配置片段(默认空,子类按需覆写)。"""
        return {}


class GeneralPage(BasePage):
    """常规页:界面语言 + 开机启动。"""

    def __init__(self, general: dict, parent=None) -> None:
        super().__init__("常规", parent)
        form = QFormLayout()
        form.setSpacing(12)

        self._language = QComboBox()
        self._language.addItem("简体中文", "zh_CN")
        form.addRow("界面语言", self._language)

        self._autostart = QCheckBox("开机时自动启动 SnapOCR")
        self._autostart.setChecked(bool(general.get("auto_start", False)))
        form.addRow("开机启动", self._autostart)

        container = QWidget()
        container.setLayout(form)
        self.add_widget(container)
        self.add_stretch()

    def collect(self) -> dict:
        return {
            "general": {
                "auto_start": self._autostart.isChecked(),
                "language": self._language.currentData(),
            }
        }


class HotkeyPage(BasePage):
    """热键页:每行「功能名 + 快捷键框 + 修改」,对照 mockup ④。"""

    def __init__(self, hotkeys: dict, parent=None) -> None:
        super().__init__("热键", parent)
        self._edits: dict[str, HotkeyLineEdit] = {}

        for action in ACTIONS:
            row = QHBoxLayout()
            label = QLabel(ACTION_LABELS[action])
            edit = HotkeyLineEdit(hotkeys.get(action, ""))
            edit.setFixedWidth(120)
            btn = QPushButton("修改")
            btn.setProperty("link", "true")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(edit.start_recording)

            row.addWidget(label)
            row.addStretch(1)
            row.addWidget(edit)
            row.addWidget(btn)

            wrapper = QWidget()
            wrapper.setLayout(row)
            self.add_widget(wrapper)
            self._edits[action] = edit

        hint = QLabel("点击「修改」后按下目标组合键;Esc 取消,Backspace 清空。")
        hint.setProperty("hint", "true")
        self.add_widget(hint)
        self.add_stretch()

    def collect(self) -> dict:
        return {"hotkeys": {a: e.sequence() for a, e in self._edits.items()}}


class PlaceholderPage(BasePage):
    """占位页:后续里程碑开放。"""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(title, parent)
        tip = QLabel("该模块将在后续里程碑中开放。")
        tip.setProperty("hint", "true")
        self.add_widget(tip)
        self.add_stretch()


class AboutPage(BasePage):
    """关于页:产品名 + 版本。"""

    def __init__(self, parent=None) -> None:
        super().__init__("关于", parent)
        from src import __app_name__, __app_name_cn__, __version__

        info = QLabel(
            f"{__app_name_cn__} / {__app_name__}\n"
            f"版本 {__version__}\n\n"
            "轻量级桌面截图与标注工具,内置本地 OCR。"
        )
        info.setProperty("hint", "true")
        self.add_widget(info)
        self.add_stretch()
