"""SnapOCR 入口:High DPI 预设 → QApplication → 单实例 → 装配上下文。

注意:高 DPI 相关环境变量必须在创建 QApplication 之前设置,故部分 import 延后,
并以 noqa: E402 标注(这是 Qt 应用的常见且必要写法)。
"""
from __future__ import annotations

import os
import sys

# 高 DPI:在 QApplication 创建前设置(Qt6 默认已启用缩放,这里显式声明以防万一)。
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
# headless(无 DISPLAY)环境可用 offscreen 平台做冒烟验证:
#   QT_QPA_PLATFORM=offscreen python run.py

from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from src.app_context import AppContext  # noqa: E402
from src.core.logger import get_logger, setup_logging  # noqa: E402
from src.core.single_instance import SingleInstance  # noqa: E402
from src.ui.theme import theme_manager  # noqa: E402

log = get_logger("main")


def main() -> int:
    setup_logging()
    minimized = "--minimized" in sys.argv  # 开机自启时静默到托盘(预留)
    log.info("SnapOCR 启动(minimized=%s)", minimized)

    app = QApplication(sys.argv)
    app.setApplicationName("SnapOCR")
    app.setApplicationDisplayName("截图精灵")
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口不退出,常驻托盘
    app.setFont(QFont("Microsoft YaHei", 9))

    theme_manager.apply_theme(app)

    # 单实例:已有实例则唤醒它并退出
    guard = SingleInstance()
    if guard.is_running():
        log.info("检测到已有实例,发送唤醒后退出")
        guard.send_wake()
        return 0
    guard.start_server()  # 尽快抢占本地套接字,缩小与后续初始化间的竞态窗口

    context = AppContext()
    guard.activated.connect(context.open_settings)

    context.start()
    if not minimized:
        context.tray.show_message(
            "SnapOCR 截图精灵", "已在后台运行,右键托盘图标查看菜单"
        )

    return app.exec()
