"""OCR 后台识别线程 + QImage→字节转换。

识别在子线程跑,完成/失败经信号回主线程,避免 UI 冻结。
engine 层只认字节,这里负责把 QImage 编码成 PNG 字节(并在识别前做放大预处理)。
"""
from __future__ import annotations

import math

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt, QThread, Signal
from PySide6.QtGui import QImage

from src.core.logger import get_logger
from src.core.ocr.engine import OcrEngine, OcrResult

log = get_logger("ocr.worker")

# 识别前放大:屏幕文字普遍偏小,把最短边放大到约此值能显著提升检测/识别。
# 用整数倍 + 平滑插值,避免引入插值噪声;封顶倍数防巨图拖慢推理。
_OCR_TARGET_MIN_SIDE = 1200
_OCR_MAX_UPSCALE = 4


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


def prepare_ocr_bytes(image: QImage) -> bytes:
    """OCR 预处理:小图按整数倍放大(屏幕小字放大后识别更准),再编码 PNG。
    放大只影响识别质量,不影响呈现(面板只用 box 相对顺序排序,不做像素定位)。"""
    if image is None or image.isNull():
        return b""
    w, h = image.width(), image.height()
    side = min(w, h)
    if 0 < side < _OCR_TARGET_MIN_SIDE:
        factor = min(_OCR_MAX_UPSCALE, max(2, math.ceil(_OCR_TARGET_MIN_SIDE / side)))
        scaled = image.scaled(
            w * factor, h * factor,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if not scaled.isNull():
            log.info("OCR 预处理:放大 %dx(%dx%d → %dx%d)",
                     factor, w, h, scaled.width(), scaled.height())
            image = scaled
    return qimage_to_png_bytes(image)


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
