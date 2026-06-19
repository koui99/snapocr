"""日志:文件(轮转)+ 控制台双输出,统一挂在 "snapocr" 命名空间下。"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from src.config import paths

_INITED = False
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """初始化根日志(幂等;重复调用不会重复添加 handler)。"""
    global _INITED
    if _INITED:
        return

    root = logging.getLogger("snapocr")
    root.setLevel(level)
    root.propagate = False

    fmt = logging.Formatter(_LOG_FORMAT, _DATE_FORMAT)

    # 文件 handler:轮转,最多保留 3 个 1MB 文件;不可写时静默跳过(只读环境不阻断启动)
    try:
        log_path = paths.log_file()
        paths.ensure_parent(log_path)
        fh = RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass

    # 控制台 handler
    ch = logging.StreamHandler(sys.stderr)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    _INITED = True


def get_logger(name: str) -> logging.Logger:
    """获取子 logger;首次使用时自动完成日志初始化。"""
    if not _INITED:
        setup_logging()
    return logging.getLogger(f"snapocr.{name}")
