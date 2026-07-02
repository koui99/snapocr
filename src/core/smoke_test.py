"""打包冒烟测试(--smoke-test):在 CI 上验证瘦身后的 exe 功能完整。

覆盖打包最容易剔坏的链路,每项独立记录通过/失败:
1. qt-app      QApplication 创建(平台插件、Qt6Core/Gui/Widgets DLL)
2. theme       QSS 主题模板加载(datas 里的 theme.qss)
3. svg-icons   QtSvg 渲染内联工具栏图标(Qt6Svg DLL)
4. local-server QtNetwork 的 QLocalServer 监听(单实例机制)
5. ocr         QPainter 画文字 → RapidOCR 全链路识别
   (rapidocr / onnxruntime / cv2 / numpy / PIL / 内置模型)

结果写到 exe 同目录 smoke_result.json;全部通过退出码 0,否则 1。
GUI 子系统经 QT_QPA_PLATFORM=offscreen 在无桌面环境运行。
"""
from __future__ import annotations

import json
import os
import sys
import traceback

from src.core.logger import get_logger

log = get_logger("smoke")

# 数字比中文对字体渲染更鲁棒(CI 字体差异不影响判定)
_SMOKE_TEXT = "SnapOCR 12345"
_EXPECT_SUBSTR = "12345"


def _result_path() -> str:
    """结果文件放 exe 同目录(打包态)或仓库根(源码态)。"""
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "smoke_result.json")
    return os.path.join(os.getcwd(), "smoke_result.json")


def _paint_sample() -> bytes:
    """用 QPainter 画一张白底黑字测试图,返回 PNG 字节。"""
    from PySide6.QtCore import QBuffer, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter

    image = QImage(640, 140, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    font = QFont("Arial")
    font.setPixelSize(56)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("black"))
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, _SMOKE_TEXT)
    painter.end()

    buf = QBuffer()
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    return bytes(buf.data())


def run_smoke_test() -> int:
    checks: dict[str, str] = {}

    def record(name: str, fn) -> None:
        try:
            fn()
            checks[name] = "ok"
            log.info("冒烟 [%s] 通过", name)
        except Exception:
            checks[name] = traceback.format_exc(limit=3)
            log.error("冒烟 [%s] 失败:%s", name, checks[name])

    # 1. QApplication(offscreen 下也会加载平台插件与核心 DLL)
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    checks["qt-app"] = "ok"

    # 2. 主题 QSS
    def _theme() -> None:
        from src.ui.theme import theme_manager

        qss = theme_manager.build_stylesheet()
        assert qss.strip(), "主题样式表为空"

    record("theme", _theme)

    # 3. QtSvg 图标渲染
    def _svg() -> None:
        from src.ui.screenshot.icons import render_icon

        icon = render_icon("rect")
        assert not icon.isNull(), "SVG 图标渲染为空"

    record("svg-icons", _svg)

    # 4. QtNetwork 单实例服务
    def _server() -> None:
        from src.core.single_instance import SingleInstance

        guard = SingleInstance()
        guard.start_server()
        assert guard._server is not None and guard._server.isListening(), "QLocalServer 未监听"

    record("local-server", _server)

    # 5. OCR 全链路
    def _ocr() -> None:
        from src.core.ocr.engine import OcrEngine

        result = OcrEngine.recognize(_paint_sample())
        assert result.ok, f"OCR 失败:{result.error}"
        got = result.text.replace(" ", "")
        assert _EXPECT_SUBSTR in got, f"OCR 结果不含期望文本:{result.text!r}"

    record("ocr", _ocr)

    passed = all(v == "ok" for v in checks.values())
    payload = {"passed": passed, "checks": checks}
    try:
        with open(_result_path(), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except OSError:
        log.error("冒烟结果文件写入失败", exc_info=True)

    log.info("冒烟测试%s:%s", "通过" if passed else "未通过", checks)
    app.quit()
    return 0 if passed else 1
