"""开机自启:Windows 写入注册表 Run 项;非 Windows 优雅降级(仅记录日志)。"""
from __future__ import annotations

import os
import sys

from src.core.logger import get_logger

log = get_logger("startup")

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "SnapOCR"


def _command() -> str:
    """开机启动命令:打包后指向 exe,开发期指向 python run.py(均带 --minimized)。"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return f'"{sys.executable}" "{os.path.join(root, "run.py")}" --minimized'


def is_enabled() -> bool:
    """查询是否已设置开机自启(仅 Windows;其它平台恒为 False)。"""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
            return True
    except FileNotFoundError:
        return False
    except OSError as e:
        log.warning("查询开机自启失败:%s", e)
        return False


def set_enabled(enabled: bool) -> bool:
    """设置/取消开机自启;非 Windows 平台仅记录日志并返回 False(降级)。"""
    if sys.platform != "win32":
        log.info("非 Windows 平台,跳过开机自启设置(降级):enabled=%s", enabled)
        return False
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, _command())
                log.info("已启用开机自启")
            else:
                try:
                    winreg.DeleteValue(key, _VALUE_NAME)
                    log.info("已取消开机自启")
                except FileNotFoundError:
                    pass
        return True
    except OSError as e:
        log.error("设置开机自启失败:%s", e)
        return False
