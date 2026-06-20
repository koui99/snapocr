"""设置窗:无边框 QDialog + 左侧导航 + 右侧分页 + 底部操作栏。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.config.settings import DEFAULT_CONFIG
from src.ui.components.shadow_widget import apply_shadow
from src.ui.components.title_bar import TitleBar
from src.ui.settings.pages import (
    AboutPage,
    GeneralPage,
    HotkeyPage,
    OcrPage,
    PlaceholderPage,
)

# 导航项顺序需与 _build_body 中 _pages 构造顺序一一对应
_NAV = ["常规", "热键", "截屏", "贴图", "输出", "文字识别(OCR)", "关于"]


class SettingsDialog(QDialog):
    """设置对话框。点击「确定」发射 sig_saved(收集后的配置片段)。"""

    sig_saved = Signal(dict)
    sig_reset_defaults = Signal()

    def __init__(self, config: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(560, 420)

        self._pages: list = []
        self._build_ui(config)

    def _build_ui(self, config: dict) -> None:
        # 外层透明 + 边距,给阴影留出空间(外补齐法)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)

        content = QWidget()
        content.setObjectName("settingsContent")
        apply_shadow(content, heavy=True)
        outer.addWidget(content)

        v = QVBoxLayout(content)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(TitleBar("设置", content))
        v.addLayout(self._build_body(config), 1)
        v.addWidget(self._build_footer())

    def _build_body(self, config: dict) -> QHBoxLayout:
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._nav = QListWidget()
        self._nav.setObjectName("settingsNav")
        self._nav.setFixedWidth(130)
        self._nav.addItems(_NAV)

        self._stack = QStackedWidget()
        self._stack.setObjectName("settingsStack")

        hotkeys = config.get("hotkeys", DEFAULT_CONFIG["hotkeys"])
        general = config.get("general", DEFAULT_CONFIG["general"])
        ocr = config.get("ocr", DEFAULT_CONFIG["ocr"])
        self._pages = [
            GeneralPage(general),
            HotkeyPage(hotkeys),
            PlaceholderPage("截屏"),
            PlaceholderPage("贴图"),
            PlaceholderPage("输出"),
            OcrPage(ocr),
            AboutPage(),
        ]
        for p in self._pages:
            self._stack.addWidget(p)

        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._nav.setCurrentRow(1)  # 默认高亮「热键」(对照 mockup ④)

        body.addWidget(self._nav)
        body.addWidget(self._stack, 1)
        return body

    def _build_footer(self) -> QWidget:
        # 用 QWidget 容器(而非裸 Layout)承载,QSS 才能给底栏上背景色与分隔线
        footer_widget = QWidget()
        footer_widget.setObjectName("settingsFooter")
        footer = QHBoxLayout(footer_widget)
        footer.setContentsMargins(16, 10, 16, 12)

        btn_reset = QPushButton("恢复默认")
        btn_cancel = QPushButton("取消")
        btn_ok = QPushButton("确定")
        btn_ok.setProperty("primary", "true")
        btn_reset.clicked.connect(self.sig_reset_defaults.emit)
        btn_cancel.clicked.connect(self.reject)
        btn_ok.clicked.connect(self._on_ok)

        footer.addWidget(btn_reset)
        footer.addStretch(1)
        footer.addWidget(btn_cancel)
        footer.addWidget(btn_ok)
        return footer_widget

    def _on_ok(self) -> None:
        merged: dict = {}
        for page in self._pages:
            for section, payload in page.collect().items():
                merged.setdefault(section, {}).update(payload)
        self.sig_saved.emit(merged)
        self.accept()

    def current_page(self) -> int:
        return self._nav.currentRow()

    def select_page(self, index: int) -> None:
        if 0 <= index < self._nav.count():
            self._nav.setCurrentRow(index)

    def show_and_raise(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
