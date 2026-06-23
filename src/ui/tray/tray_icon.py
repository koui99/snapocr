"""系统托盘:QSystemTrayIcon + 右键菜单(对照 mockup ④)。

只负责把菜单点击转成信号转发给上层(app_context),自身不含业务逻辑。
"""
from __future__ import annotations

import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from src.core.logger import get_logger
from src.ui.tray.icon_factory import make_app_icon

log = get_logger("tray")


class TrayIcon(QObject):
    """托盘图标与右键菜单封装。"""

    # 通用动作:screenshot / pin(钉剪贴板) / ocr / settings / help / about / quit
    action_triggered = Signal(str)
    recent_file_triggered = Signal(str)  # 最近文件路径
    autostart_toggled = Signal(bool)     # 开机启动勾选状态

    def __init__(self, icon: QIcon | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(icon or make_app_icon(), self)
        self._tray.setToolTip("SnapOCR 截图精灵")
        self._menu = QMenu()
        self._autostart_action: QAction | None = None
        self._build_menu({}, [], False)
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_activated)

    # ---- 对外 ----
    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    @staticmethod
    def is_available() -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def show_message(self, title: str, text: str) -> None:
        # 不用 supportsMessages() 拦截(部分环境会误报 False);直接弹,用标准信息图标。
        # 打一条日志便于排查:若日志出现此行但屏幕无气泡,基本可判定是 Windows
        # 通知设置(专注助手 / 已关闭通知)拦截,而非程序逻辑问题。
        log.info(
            "弹出托盘通知: %s(supportsMessages=%s)",
            title,
            self._tray.supportsMessages(),
        )
        self._tray.showMessage(
            title, text, QSystemTrayIcon.MessageIcon.Information, 3000
        )

    def update_state(self, hotkeys: dict, recent_files: list, autostart: bool) -> None:
        """根据最新配置重建菜单(热键文本 / 最近文件 / 自启勾选)。"""
        self._build_menu(hotkeys, recent_files, autostart)

    # ---- 菜单构建 ----
    def _build_menu(self, hotkeys: dict, recent_files: list, autostart: bool) -> None:
        self._menu.clear()

        def add(text: str, action_name: str, shortcut: str = "") -> None:
            # 菜单文本中 \t 之后的内容会作为快捷键提示右对齐显示(仅展示,不绑定)
            label = f"{text}\t{shortcut}" if shortcut else text
            act = self._menu.addAction(label)
            act.triggered.connect(
                lambda checked=False, n=action_name: self.action_triggered.emit(n)
            )

        add("截屏", "screenshot", hotkeys.get("screenshot", ""))
        add("贴图(钉剪贴板的图)", "pin", hotkeys.get("pin", ""))
        add("文字识别", "ocr", hotkeys.get("ocr", ""))

        # 最近文件子菜单
        recent_menu = self._menu.addMenu("最近文件")
        if recent_files:
            for path in recent_files[:5]:
                # 菜单只显示文件名,完整路径放 tooltip,避免长路径撑宽菜单
                act = recent_menu.addAction(os.path.basename(path) or path)
                act.setToolTip(path)
                act.triggered.connect(
                    lambda checked=False, p=path: self.recent_file_triggered.emit(p)
                )
        else:
            empty = recent_menu.addAction("(暂无)")
            empty.setEnabled(False)

        self._menu.addSeparator()
        add("设置", "settings")

        self._autostart_action = self._menu.addAction("开机启动")
        self._autostart_action.setCheckable(True)
        self._autostart_action.setChecked(autostart)
        self._autostart_action.toggled.connect(self.autostart_toggled.emit)

        self._menu.addSeparator()
        add("帮助", "help")
        add("关于", "about")
        self._menu.addSeparator()
        add("退出", "quit")

    def _on_activated(self, reason) -> None:
        # 双击托盘图标 → 触发截屏(与 Snipaste 习惯一致)
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.action_triggered.emit("screenshot")
