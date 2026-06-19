"""主题管理:加载 QSS 模板,用 design token 替换占位符,应用到 QApplication。"""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from src.config import paths
from src.core.logger import get_logger
from src.ui.theme import tokens

log = get_logger("theme")

_QSS_REL = "src/ui/theme/theme.qss"


def _load_qss_template() -> str:
    """读取 QSS 模板文本;失败返回空串(不阻断启动)。"""
    qss_path = paths.resource_path(_QSS_REL)
    try:
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        log.warning("QSS 模板读取失败:%s", e)
        return ""


def build_stylesheet() -> str:
    """生成最终 QSS:用 token 值替换模板占位符。

    占位符按长度降序替换,避免 @primary 抢先吃掉 @primary_hover 这类前缀冲突。
    """
    template = _load_qss_template()
    if not template:
        return ""
    items = sorted(
        tokens.qss_replacements().items(), key=lambda kv: len(kv[0]), reverse=True
    )
    for placeholder, value in items:
        template = template.replace(placeholder, value)
    return template


def apply_theme(app: QApplication) -> None:
    """把主题应用到整个应用。"""
    qss = build_stylesheet()
    if qss:
        app.setStyleSheet(qss)
        log.info("已应用全局主题样式")
