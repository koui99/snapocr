"""OCR 引擎包:本地离线 RapidOCR 封装。"""
from src.core.ocr.engine import (
    LANG_OPTIONS,
    OcrEngine,
    OcrLine,
    OcrResult,
    average_confidence,
    format_confidence,
    format_elapsed,
    join_lines,
    lang_label,
)

__all__ = [
    "OcrEngine",
    "OcrResult",
    "OcrLine",
    "LANG_OPTIONS",
    "average_confidence",
    "join_lines",
    "format_elapsed",
    "format_confidence",
    "lang_label",
]
