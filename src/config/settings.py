"""配置管理:自管 JSON 读写 + 默认值深合并 + schema 版本迁移。

内存持有当前配置,显式 save() 落盘。读取损坏/缺失时回退默认值,保证不崩。
"""
from __future__ import annotations

import copy
import json
from typing import Any

from src.config import paths
from src.core.logger import get_logger

log = get_logger("config")

SCHEMA_VERSION = 1

# 默认配置(热键定义与 design/BRIEF.md 一致:F1 截屏 / F3 贴图 / Shift+F3 显隐 / F4 OCR)
DEFAULT_CONFIG: dict = {
    "schema_version": SCHEMA_VERSION,
    "general": {
        "auto_start": False,
        "language": "zh_CN",
    },
    "hotkeys": {
        "screenshot": "F1",
        "pin": "F3",
        "toggle_pin": "Shift+F3",
        "ocr": "F4",
    },
    "screenshot": {
        "save_dir": "",
        "format": "png",
        "quality": 90,
    },
    "ocr": {
        "default_lang": "mix",   # mix=中英混合(内置) / en=仅英文
        "auto_copy": False,      # 识别完成后自动把文本复制到剪贴板
    },
    "recent_files": [],
}


def _deep_merge(base: dict, override: dict) -> dict:
    """以 base 为模板深合并 override:override 缺失的键用 base 补全。"""
    result = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


class ConfigManager:
    """配置读写门面。"""

    def __init__(self) -> None:
        self._data: dict = copy.deepcopy(DEFAULT_CONFIG)
        self.load()

    # ---- 持久化 ----
    def load(self) -> None:
        """从磁盘加载配置;不存在或损坏时回退默认值。"""
        path = paths.config_file()
        if not path.exists():
            log.info("配置文件不存在,使用默认配置:%s", path)
            self._data = copy.deepcopy(DEFAULT_CONFIG)
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            log.warning("配置读取失败,回退默认值:%s", e)
            self._data = copy.deepcopy(DEFAULT_CONFIG)
            return
        merged = _deep_merge(DEFAULT_CONFIG, loaded if isinstance(loaded, dict) else {})
        self._data = self._migrate(merged)

    def save(self) -> bool:
        """落盘;成功返回 True。"""
        path = paths.config_file()
        try:
            paths.ensure_parent(path)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            log.info("配置已保存:%s", path)
            return True
        except OSError as e:
            log.error("配置保存失败:%s", e)
            return False

    def reset_to_defaults(self) -> None:
        """把内存配置重置为默认值(不自动落盘,由调用方决定 save)。"""
        self._data = copy.deepcopy(DEFAULT_CONFIG)

    def _migrate(self, data: dict) -> dict:
        """schema 版本迁移占位:当前仅纠正版本号,未来在此累加迁移步骤。"""
        ver = data.get("schema_version", 1)
        if ver != SCHEMA_VERSION:
            log.info("配置版本 %s → %s 迁移", ver, SCHEMA_VERSION)
            data["schema_version"] = SCHEMA_VERSION
        return data

    # ---- 通用访问 ----
    @property
    def data(self) -> dict:
        return self._data

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self._data.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any) -> None:
        self._data.setdefault(section, {})[key] = value

    # ---- 热键便捷访问 ----
    def hotkeys(self) -> dict:
        return dict(self._data.get("hotkeys", {}))

    def set_hotkey(self, action: str, sequence: str) -> None:
        self._data.setdefault("hotkeys", {})[action] = sequence

    def recent_files(self) -> list:
        return list(self._data.get("recent_files", []))
