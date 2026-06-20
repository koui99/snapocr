"""Windows 全局热键后端:独立线程内注册 + 自跑 GetMessage 消息循环。

为什么不用 Qt 的 nativeEventFilter:
RegisterHotKey 的 WM_HOTKEY(无论绑定 NULL 还是真实 HWND)在 PySide6 下并不能
可靠地经 QAbstractNativeEventFilter 投递(实测:注册成功但按键收不到)。因此改用
最稳妥的方案——开一个专用线程,在该线程内 RegisterHotKey(NULL) 并自己跑
GetMessage 循环;WM_HOTKEY 一定回到本线程队列,被我们直接取到,再回调上抛
(经 Qt 信号的跨线程队列连接安全切回主线程)。零第三方依赖,打包单 exe 稳妥。
"""
from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable

from src.core.logger import get_logger

log = get_logger("hotkey.win32")

_WM_HOTKEY = 0x0312
_WM_APP_SYNC = 0x8000   # 自定义:请求(重新)同步注册
_PM_REMOVE = 0x0001
_ERROR_HOTKEY_ALREADY_REGISTERED = 1409

_MOD = {
    "ALT": 0x0001, "CTRL": 0x0002, "CONTROL": 0x0002,
    "SHIFT": 0x0004, "WIN": 0x0008, "META": 0x0008,
}
_MOD_NOREPEAT = 0x4000

if hasattr(ctypes, "WinDLL"):
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
else:  # 非 Windows(理论上不会走到,linux 用 Mock 后端)
    _user32 = _kernel32 = None

if _user32 is not None:
    _LPMSG = ctypes.POINTER(wintypes.MSG)
    _user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    _user32.RegisterHotKey.restype = wintypes.BOOL
    _user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.UnregisterHotKey.restype = wintypes.BOOL
    _user32.GetMessageW.argtypes = [_LPMSG, wintypes.HWND, wintypes.UINT, wintypes.UINT]
    _user32.GetMessageW.restype = ctypes.c_int  # 可能返回 -1
    _user32.PeekMessageW.argtypes = [_LPMSG, wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
    _user32.PeekMessageW.restype = wintypes.BOOL
    _user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    _user32.PostThreadMessageW.restype = wintypes.BOOL
    _kernel32.GetCurrentThreadId.restype = wintypes.DWORD

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
    if key.startswith("F") and key[1:].isdigit():
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


class Win32HotkeyBackend:
    """专用线程承载 RegisterHotKey + GetMessage 循环的全局热键后端。"""

    def __init__(self, on_trigger: Callable[[str], None]) -> None:
        self._on_trigger = on_trigger
        self._desired: dict[str, tuple[int, int, str]] = {}  # action -> (mods, vk, sequence)
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._tid: int | None = None
        self._ready = threading.Event()

    # ---- 对外接口(主线程调用)----
    def register(self, action: str, sequence: str) -> bool:
        if _user32 is None:
            return False
        parsed = parse_sequence(sequence)
        if parsed is None:
            log.warning("无法解析快捷键:%s", sequence)
            return False
        mods, vk = parsed
        with self._lock:
            self._desired[action] = (mods, vk, sequence)
        self._ensure_thread()
        self._post_sync()
        return True

    def unregister_all(self) -> None:
        with self._lock:
            self._desired.clear()
        self._post_sync()

    # ---- 线程与消息 ----
    def _ensure_thread(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="SnapOCRHotkey", daemon=True)
        self._thread.start()
        self._ready.wait(2.0)  # 等 worker 建好消息队列并拿到 tid

    def _post_sync(self) -> None:
        if self._tid and _user32 is not None:
            _user32.PostThreadMessageW(self._tid, _WM_APP_SYNC, 0, 0)

    def _run(self) -> None:
        if _user32 is None or _kernel32 is None:
            return
        self._tid = int(_kernel32.GetCurrentThreadId())
        msg = wintypes.MSG()
        # 主动 PeekMessage 触发本线程消息队列的创建,确保 PostThreadMessage 能投进来
        _user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, _PM_REMOVE)
        self._ready.set()
        log.info("全局热键线程已启动(tid=%s)", self._tid)

        id_to_action: dict[int, str] = {}
        next_id = 1

        def _resync() -> None:
            for hid in list(id_to_action):
                _user32.UnregisterHotKey(None, hid)
            id_to_action.clear()
            with self._lock:
                desired = dict(self._desired)
            nonlocal next_id
            for action, (mods, vk, seq) in desired.items():
                hid = next_id
                next_id += 1
                if _user32.RegisterHotKey(None, hid, mods, vk):
                    id_to_action[hid] = action
                    log.info("已注册全局热键:%s=%s(id=%d)", action, seq, hid)
                else:
                    err = ctypes.get_last_error()
                    if err == _ERROR_HOTKEY_ALREADY_REGISTERED:
                        log.warning("热键被其他程序占用:%s=%s(请换组合键)", action, seq)
                    else:
                        log.warning("RegisterHotKey 失败:%s=%s(错误码=%s)", action, seq, err)

        _resync()  # 线程启动即应用一次当前期望集
        try:
            while True:
                ret = _user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret in (0, -1):  # WM_QUIT 或错误
                    break
                if msg.message == _WM_HOTKEY:
                    action = id_to_action.get(int(msg.wParam))
                    if action:
                        log.info("热键消息收到:%s", action)
                        try:
                            self._on_trigger(action)
                        except Exception as e:
                            log.error("热键回调异常:%s", e)
                elif msg.message == _WM_APP_SYNC:
                    # 合并连续的同步请求,只 resync 一次
                    drain = wintypes.MSG()
                    while _user32.PeekMessageW(ctypes.byref(drain), None,
                                               _WM_APP_SYNC, _WM_APP_SYNC, _PM_REMOVE):
                        pass
                    _resync()
        finally:
            for hid in list(id_to_action):
                _user32.UnregisterHotKey(None, hid)
            id_to_action.clear()
