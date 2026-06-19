"""Windows 全局热键后端:ctypes 直调 user32.RegisterHotKey + Qt 原生事件过滤。

仅在 sys.platform == "win32" 时由 base.HotkeyManager 惰性导入。零第三方依赖,
打包成单 exe 时不引入额外 dll,最稳妥。
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication

from src.core.logger import get_logger

log = get_logger("hotkey.win32")

_WM_HOTKEY = 0x0312
_MOD = {
    "ALT": 0x0001,
    "CTRL": 0x0002,
    "CONTROL": 0x0002,
    "SHIFT": 0x0004,
    "WIN": 0x0008,
    "META": 0x0008,
}
_MOD_NOREPEAT = 0x4000  # 防止长按重复触发(Win7+)

_user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None

# 显式声明 argtypes/restype:64 位 Windows 下 HWND 是 64 位指针,
# 不声明时 ctypes 默认按 c_int 处理会截断指针,可能偶发崩溃。
if _user32 is not None:
    _user32.RegisterHotKey.argtypes = [
        wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT
    ]
    _user32.RegisterHotKey.restype = wintypes.BOOL
    _user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.UnregisterHotKey.restype = wintypes.BOOL

_SPECIAL_VK = {
    "ESC": 0x1B, "ESCAPE": 0x1B, "SPACE": 0x20, "TAB": 0x09,
    "ENTER": 0x0D, "RETURN": 0x0D, "INSERT": 0x2D, "INS": 0x2D,
    "DELETE": 0x2E, "DEL": 0x2E, "HOME": 0x24, "END": 0x23,
    "PAGEUP": 0x21, "PAGEDOWN": 0x22,
}


def _vk_from_key(key: str) -> int | None:
    """把单个主键名转成 Windows 虚拟键码 VK;无法识别返回 None。"""
    key = key.strip().upper()
    if not key:
        return None
    if key.startswith("F") and key[1:].isdigit():  # 功能键 F1-F24
        n = int(key[1:])
        if 1 <= n <= 24:
            return 0x70 + (n - 1)  # VK_F1 = 0x70
    if len(key) == 1 and ("A" <= key <= "Z" or "0" <= key <= "9"):
        return ord(key)
    return _SPECIAL_VK.get(key)


def parse_sequence(sequence: str) -> tuple[int, int] | None:
    """解析快捷键字符串(如 "Shift+F3")→ (modifiers, vk);失败返回 None。"""
    parts = [p for p in sequence.replace(" ", "").split("+") if p]
    if not parts:
        return None
    mods = 0
    vk: int | None = None
    for part in parts:
        up = part.upper()
        if up in _MOD:
            mods |= _MOD[up]
        else:
            vk = _vk_from_key(part)
    if vk is None:
        return None
    return mods | _MOD_NOREPEAT, vk


class Win32HotkeyBackend(QAbstractNativeEventFilter):
    """通过 RegisterHotKey 注册系统级热键,经 Qt 原生事件过滤器接收 WM_HOTKEY。"""

    def __init__(self, on_trigger: Callable[[str], None]) -> None:
        super().__init__()
        self._on_trigger = on_trigger
        self._id_to_action: dict[int, str] = {}
        self._next_id = 1
        self._installed = False

    def _ensure_installed(self) -> None:
        if not self._installed:
            app = QCoreApplication.instance()
            if app is not None:
                app.installNativeEventFilter(self)
                self._installed = True

    def register(self, action: str, sequence: str) -> bool:
        if _user32 is None:
            return False
        parsed = parse_sequence(sequence)
        if parsed is None:
            log.warning("无法解析快捷键:%s", sequence)
            return False
        mods, vk = parsed
        self._ensure_installed()
        hotkey_id = self._next_id
        self._next_id += 1
        ok = bool(_user32.RegisterHotKey(None, hotkey_id, mods, vk))
        if ok:
            self._id_to_action[hotkey_id] = action
        else:
            log.warning("RegisterHotKey 失败(可能被占用):%s=%s", action, sequence)
        return ok

    def unregister_all(self) -> None:
        if _user32 is None:
            return
        for hotkey_id in list(self._id_to_action):
            _user32.UnregisterHotKey(None, hotkey_id)
        self._id_to_action.clear()

    def nativeEventFilter(self, eventType, message):  # noqa: N802 (Qt 接口命名)
        # RegisterHotKey(NULL,...) 的 WM_HOTKEY 是线程消息,经 Qt 分发为
        # b"windows_dispatcher_MSG";普通窗口消息才是 b"windows_generic_MSG"。
        # 两者都需检查,否则全局热键收不到。
        if eventType in (b"windows_generic_MSG", b"windows_dispatcher_MSG") and message:
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == _WM_HOTKEY:
                action = self._id_to_action.get(int(msg.wParam))
                if action:
                    self._on_trigger(action)
        # 不拦截消息,交还给 Qt 继续处理
        return False, 0
