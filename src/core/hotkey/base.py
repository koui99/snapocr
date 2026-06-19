"""全局热键门面:对外提供统一注册接口与触发信号,内部按平台分发后端。

core 层零 GUI 依赖原则的例外说明:本类继承 QObject 仅为使用 Qt 的信号机制
(triggered),不涉及任何窗口/控件,仍可在无显示环境(offscreen)下实例化。
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QObject, Signal

from src.core.logger import get_logger

log = get_logger("hotkey")

# M1 支持的四个热键动作(与 config.settings.DEFAULT_CONFIG["hotkeys"] 对应)
ACTIONS = ("screenshot", "pin", "toggle_pin", "ocr")
ACTION_LABELS = {
    "screenshot": "截屏",
    "pin": "贴图",
    "toggle_pin": "隐藏/显示贴图",
    "ocr": "文字识别",
}


class HotkeyManager(QObject):
    """跨平台全局热键管理器。

    triggered(str) 在某热键被按下时发射,参数为动作名(如 "screenshot")。
    Windows 走 win32 后端(ctypes RegisterHotKey);其它平台走 linux 降级后端。
    """

    triggered = Signal(str)  # 参数:动作名

    def __init__(self) -> None:
        super().__init__()
        self._backend = self._make_backend()
        self._current: dict[str, str] = {}

    def _make_backend(self):
        """按平台惰性导入对应后端(避免在 Linux 导入 win32 模块)。"""
        if sys.platform == "win32":
            from src.core.hotkey.win32 import Win32HotkeyBackend
            log.info("加载 Win32 全局热键后端")
            return Win32HotkeyBackend(on_trigger=self._on_trigger)
        from src.core.hotkey.linux import MockHotkeyBackend
        log.info("非 Windows 平台,加载降级热键后端(Mock)")
        return MockHotkeyBackend(on_trigger=self._on_trigger)

    def _on_trigger(self, action: str) -> None:
        """后端回调 → 转成 Qt 信号。"""
        log.info("热键触发:%s(%s)", action, ACTION_LABELS.get(action, action))
        self.triggered.emit(action)

    def register_all(self, mapping: dict) -> None:
        """按 {动作: 快捷键字符串} 重新注册全部热键(支持热重载)。"""
        self.unregister_all()
        for action, sequence in mapping.items():
            if action not in ACTIONS or not sequence:
                continue
            if self._backend.register(action, sequence):
                self._current[action] = sequence
            else:
                log.warning("热键注册失败:%s=%s", action, sequence)

    def unregister_all(self) -> None:
        self._backend.unregister_all()
        self._current.clear()

    def active_hotkeys(self) -> dict:
        return dict(self._current)
