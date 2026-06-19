"""热键测试:Linux 降级后端(任意平台)+ Win32 快捷键解析(仅 Windows)。"""
import sys

import pytest


def test_mock_backend_never_crashes():
    """降级后端在任意平台都不应报错,且能转发触发回调。"""
    from src.core.hotkey.linux import MockHotkeyBackend

    triggered = []
    be = MockHotkeyBackend(on_trigger=triggered.append)
    assert be.register("screenshot", "F1") is True
    be.unregister_all()
    be.trigger_for_test("screenshot")
    assert triggered == ["screenshot"]


@pytest.mark.skipif(sys.platform != "win32", reason="win32 后端仅在 Windows 导入")
def test_parse_simple_function_key():
    from src.core.hotkey.win32 import _MOD_NOREPEAT, parse_sequence

    mods, vk = parse_sequence("F1")
    assert vk == 0x70             # VK_F1
    assert mods == _MOD_NOREPEAT  # 无修饰键,仅 NOREPEAT


@pytest.mark.skipif(sys.platform != "win32", reason="win32 后端仅在 Windows 导入")
def test_parse_with_modifier():
    from src.core.hotkey.win32 import parse_sequence

    result = parse_sequence("Shift+F3")
    assert result is not None
    mods, vk = result
    assert vk == 0x72       # VK_F3
    assert mods & 0x0004    # MOD_SHIFT


@pytest.mark.skipif(sys.platform != "win32", reason="win32 后端仅在 Windows 导入")
def test_parse_invalid():
    from src.core.hotkey.win32 import parse_sequence

    assert parse_sequence("") is None
    assert parse_sequence("Ctrl+") is None  # 只有修饰键,无主键
