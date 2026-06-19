"""ConfigManager 单元测试:默认值、深合并、损坏回退、保存/加载往返、重置。

纯逻辑测试,不依赖 PySide6;需在已安装 pytest 的环境运行。
"""
import json

import pytest

from src.config import paths
from src.config import settings as settings_mod


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """把配置文件重定向到临时目录,避免污染真实配置。"""
    cfg = tmp_path / "config.json"
    monkeypatch.setattr(paths, "config_file", lambda: cfg)
    return cfg


def test_defaults_when_missing(tmp_config):
    cm = settings_mod.ConfigManager()
    assert cm.get("hotkeys", "screenshot") == "F1"
    assert cm.hotkeys()["ocr"] == "F4"


def test_save_load_roundtrip(tmp_config):
    cm = settings_mod.ConfigManager()
    cm.set_hotkey("screenshot", "Ctrl+Alt+A")
    assert cm.save()
    cm2 = settings_mod.ConfigManager()
    assert cm2.get("hotkeys", "screenshot") == "Ctrl+Alt+A"


def test_deep_merge_fills_missing(tmp_config):
    # 只写部分字段,缺失项应由默认值补全
    tmp_config.write_text(
        json.dumps({"hotkeys": {"screenshot": "F2"}}), encoding="utf-8"
    )
    cm = settings_mod.ConfigManager()
    assert cm.get("hotkeys", "screenshot") == "F2"   # 保留用户值
    assert cm.get("hotkeys", "ocr") == "F4"          # 默认补全
    assert "general" in cm.data


def test_corrupted_falls_back(tmp_config):
    tmp_config.write_text("{ this is not json", encoding="utf-8")
    cm = settings_mod.ConfigManager()
    assert cm.get("hotkeys", "screenshot") == "F1"   # 回退默认


def test_reset_to_defaults(tmp_config):
    cm = settings_mod.ConfigManager()
    cm.set_hotkey("ocr", "F9")
    cm.reset_to_defaults()
    assert cm.get("hotkeys", "ocr") == "F4"
