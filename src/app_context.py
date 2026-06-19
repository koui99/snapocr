"""应用业务协调器(Presenter):连接 UI 信号与 core 服务,持有共享状态。

托盘 / 设置窗 / 热键的交互在此汇聚,UI 与 core 互不直接依赖。
M1 阶段各功能动作(截屏/贴图/OCR)为占位:打日志 + 托盘提示。
"""
from __future__ import annotations

import copy

from PySide6.QtCore import QObject

from src.config.settings import ConfigManager
from src.core import startup
from src.core.hotkey.base import ACTION_LABELS, HotkeyManager
from src.core.logger import get_logger
from src.ui.settings.settings_dialog import SettingsDialog
from src.ui.tray.tray_icon import TrayIcon

log = get_logger("app_context")

_FEATURE_ACTIONS = {"screenshot", "pin", "pin_clipboard", "ocr"}
_ABOUT_PAGE_INDEX = 6


class AppContext(QObject):
    """应用级协调器。"""

    def __init__(self) -> None:
        super().__init__()
        self.config = ConfigManager()
        self.hotkeys = HotkeyManager()
        self.tray = TrayIcon()
        self._settings_dialog: SettingsDialog | None = None

        self._wire()
        self._apply_hotkeys()
        self._refresh_tray()

    # ---- 启动 ----
    def start(self) -> None:
        if not self.tray.is_available():
            log.warning("系统托盘不可用(常见于 headless / 无托盘的 Linux 桌面)")
        self.tray.show()
        log.info("SnapOCR 已启动并常驻托盘")

    # ---- 信号连线 ----
    def _wire(self) -> None:
        self.hotkeys.triggered.connect(self._on_hotkey)
        self.tray.action_triggered.connect(self._on_tray_action)
        self.tray.autostart_toggled.connect(self._on_autostart_toggled)
        self.tray.recent_file_triggered.connect(self._on_recent_file)

    def _apply_hotkeys(self) -> None:
        self.hotkeys.register_all(self.config.hotkeys())

    def _refresh_tray(self) -> None:
        self.tray.update_state(
            hotkeys=self.config.hotkeys(),
            recent_files=self.config.recent_files(),
            autostart=startup.is_enabled()
            or bool(self.config.get("general", "auto_start", False)),
        )

    # ---- 热键触发(占位) ----
    def _on_hotkey(self, action: str) -> None:
        self._placeholder_feature(action)

    # ---- 托盘动作 ----
    def _on_tray_action(self, action: str) -> None:
        if action in _FEATURE_ACTIONS:
            self._placeholder_feature(action)
        elif action == "settings":
            self.open_settings()
        elif action == "help":
            self._placeholder_feature("help")
        elif action == "about":
            self.open_settings(page_index=_ABOUT_PAGE_INDEX)
        elif action == "quit":
            self.quit()

    def _placeholder_feature(self, action: str) -> None:
        label = ACTION_LABELS.get(action, action)
        log.info("[占位] 触发功能:%s(%s)— M1 暂未实现具体逻辑", action, label)
        self.tray.show_message("SnapOCR", f"[占位] {label} 功能将在后续里程碑实现")

    def _on_autostart_toggled(self, enabled: bool) -> None:
        startup.set_enabled(enabled)
        self.config.set("general", "auto_start", enabled)
        self.config.save()

    def _on_recent_file(self, path: str) -> None:
        log.info("[占位] 打开最近文件:%s", path)

    # ---- 设置窗 ----
    def open_settings(self, page_index: int | None = None) -> None:
        if self._settings_dialog is None:
            # 传入深拷贝,避免设置窗在「取消」前 inplace 污染全局配置
            self._settings_dialog = SettingsDialog(copy.deepcopy(self.config.data))
            self._settings_dialog.sig_saved.connect(self._on_settings_saved)
            self._settings_dialog.sig_reset_defaults.connect(self._on_reset_defaults)
        if page_index is not None:
            self._settings_dialog.select_page(page_index)
        self._settings_dialog.show_and_raise()

    def _on_settings_saved(self, merged: dict) -> None:
        for section, payload in merged.items():
            for key, value in payload.items():
                self.config.set(section, key, value)
        self.config.save()
        # 应用副作用:热键热重载 + 开机自启 + 托盘刷新
        self._apply_hotkeys()
        startup.set_enabled(bool(self.config.get("general", "auto_start", False)))
        self._refresh_tray()
        log.info("设置已保存并应用")

    def _on_reset_defaults(self) -> None:
        self.config.reset_to_defaults()
        self.config.save()
        self._apply_hotkeys()
        self._refresh_tray()
        # 重建设置窗以反映默认值,并保留当前所在页(避免跳回热键页)
        page = 1
        if self._settings_dialog is not None:
            page = self._settings_dialog.current_page()
            self._settings_dialog.close()
            self._settings_dialog = None
        self.open_settings(page_index=page)
        log.info("已恢复默认设置")

    # ---- 退出 ----
    def quit(self) -> None:
        from PySide6.QtWidgets import QApplication

        log.info("退出 SnapOCR")
        self.hotkeys.unregister_all()
        self.config.save()
        self.tray.hide()
        QApplication.quit()
