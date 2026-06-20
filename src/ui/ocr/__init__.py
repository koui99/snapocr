"""OCR UI 子系统:识别结果窗 + 后台识别线程。"""
from src.ui.ocr.result_window import OcrResultWindow
from src.ui.ocr.worker import OcrWorker, qimage_to_png_bytes

__all__ = ["OcrResultWindow", "OcrWorker", "qimage_to_png_bytes"]
