"""非 Windows 平台的全局热键降级后端:只记录日志,绝不报错或崩溃。

开发机为 Linux 时使用。真实的系统级热键捕获留待 Windows;此处保证 UI 与配置
流程在 Linux 上能完整跑通而不因热键不可用而中断。
"""
from __future__ import annotations

from typing import Callable

from src.core.logger import get_logger

log = get_logger("hotkey.linux")


class MockHotkeyBackend:
    """降级实现:记录“注册成功”,但不真正挂接系统钩子。"""

    def __init__(self, on_trigger: Callable[[str], None]) -> None:
        self._on_trigger = on_trigger
        self._registered: dict[str, str] = {}

    def register(self, action: str, sequence: str) -> bool:
        self._registered[action] = sequence
        log.info("降级注册热键(占位,不挂系统钩子):%s -> %s", action, sequence)
        return True

    def unregister_all(self) -> None:
        if self._registered:
            log.info("降级注销全部热键:%s", list(self._registered))
        self._registered.clear()

    def trigger_for_test(self, action: str) -> None:
        """供调试/测试主动触发某热键回调(真实运行不会调用)。"""
        self._on_trigger(action)
