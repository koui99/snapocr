"""路径管理:统一配置/日志/资源路径,兼容便携模式与 PyInstaller 打包。

- 普通安装:Windows 用 %APPDATA%/SnapOCR,其它系统用 ~/.config/snapocr
- 便携模式:exe 同级存在 portable.flag 时,数据写在 exe 同级 data/ 目录
- 打包资源:通过 resource_path() 兼容 PyInstaller 的 _MEIPASS 临时解压目录
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "SnapOCR"
_PORTABLE_FLAG = "portable.flag"


def _is_frozen() -> bool:
    """是否运行在 PyInstaller 打包环境。"""
    return getattr(sys, "frozen", False)


def _executable_dir() -> Path:
    """可执行文件所在目录:打包后为 exe 目录,开发期为项目根。"""
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    # 开发期:本文件位于 src/config/paths.py,上溯两级即项目根
    return Path(__file__).resolve().parents[2]


def is_portable() -> bool:
    """便携模式判定:exe 同级存在 portable.flag。"""
    return (_executable_dir() / _PORTABLE_FLAG).exists()


def data_dir() -> Path:
    """用户数据根目录(纯路径计算,不创建目录,避免 import 期副作用)。"""
    if is_portable():
        return _executable_dir() / "data"
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / APP_DIR_NAME
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_DIR_NAME.lower()


def config_file() -> Path:
    """配置文件路径 config.json。"""
    return data_dir() / "config.json"


def log_dir() -> Path:
    """日志目录(纯路径,不创建)。"""
    return data_dir() / "logs"


def log_file() -> Path:
    """主日志文件路径 snapocr.log。"""
    return log_dir() / "snapocr.log"


def ensure_parent(path: Path) -> None:
    """确保某文件的父目录存在(写入前调用);失败抛 OSError,由调用方处理。"""
    path.parent.mkdir(parents=True, exist_ok=True)


def resource_path(relative: str) -> Path:
    """打包资源寻址:兼容 PyInstaller 的 _MEIPASS;开发期回落到项目根。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / relative
    return Path(__file__).resolve().parents[2] / relative
