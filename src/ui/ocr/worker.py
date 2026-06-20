"""OCR 后台识别线程 + QImage→字节转换。

识别在子线程跑,完成/失败经信号回主线程,避免 UI 冻结。
engine 层只认字节,这里负责把 QImage 编码成 PNG 字节。
"""
from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QThread, Signal
from PySide6.QtGui import QImage

from src.core.logger import get_logger
from src.core.ocr.engine import OcrEngine, OcrResult

log = get_logger("ocr.worker")


def qimage_to_png_bytes(image: QImage) -> bytes:
    """把 QImage 编码为 PNG 字节;失败返回空字节。"""
    if image is None or image.isNull():
        return b""
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    ok = image.save(buf, "PNG")
    buf.close()
    if not ok:
        log.warning("QImage 编码 PNG 失败")
        return b""
    return bytes(ba)


class OcrWorker(QThread):
    """单次识别任务线程。完成发 sig_done(OcrResult)。"""

    sig_done = Signal(object)  # OcrResult

    def __init__(self, image_bytes: bytes, lang: str, parent=None) -> None:
        super().__init__(parent)
        self._bytes = image_bytes
        self._lang = lang

    def run(self) -> None:
        try:
            result = OcrEngine.recognize(self._bytes, self._lang)
        except Exception as e:  # 兜底:线程内绝不抛出
            log.error("OCR worker 异常:%s", e)
            result = OcrResult(ok=False, error=f"文字识别失败:{e}")
        self.sig_done.emit(result)
