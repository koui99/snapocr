"""OCR 文字识别结果窗(界面③)。

布局(对照 design/mockup.html 界面③):
- 标题栏「文字识别结果」(复用 TitleBar,可拖拽 + 关闭)。
- 顶部工具行:语言下拉(中英混合/仅英文)+ 重新识别。
- 主体左右两栏:左=原图缩略,右=可编辑识别文本框。
- 底部状态栏:识别耗时 · 置信度;右侧操作:翻译(占位/禁用)、保存 txt、复制全部。

识别在 OcrWorker 子线程跑,期间禁用按钮 + 状态栏提示「识别中…」,避免 UI 冻结。
复用既有设施:TitleBar、apply_shadow、theme tokens、ScreenshotWriter(无)→ 文本另存自管。
"""
from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.config import paths
from src.core.logger import get_logger
from src.core.ocr.engine import (
    LANG_OPTIONS,
    OcrResult,
    format_confidence,
    format_elapsed,
)
from src.ui.components.shadow_widget import apply_shadow
from src.ui.components.title_bar import TitleBar
from src.ui.ocr.worker import OcrWorker, prepare_ocr_bytes

log = get_logger("ocr.window")

_THUMB_MAX = 280  # 缩略图最长边


class OcrResultWindow(QWidget):
    """OCR 识别结果窗口。create→show 后自动发起首次识别。"""

    closed = Signal(object)  # 关闭时发射自身,供 app_context 主动清理(不依赖 C++ destroyed)

    # 类级集合:持有正在运行的 worker,防止 Python GC 在线程跑完前回收
    _running_workers: set = set()

    def __init__(self, source_image: QImage, config=None, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self._source = QImage(source_image)  # 留存原图供重新识别
        self._worker: OcrWorker | None = None

        self.setWindowTitle("文字识别结果")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(640, 460)

        self._build_ui()

    # ---- UI 装配 ----
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)

        content = QWidget()
        content.setObjectName("ocrContent")
        apply_shadow(content, heavy=True)
        outer.addWidget(content)

        v = QVBoxLayout(content)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        v.addWidget(TitleBar("文字识别结果", content))
        v.addWidget(self._build_toolbar())
        v.addLayout(self._build_body(), 1)
        v.addWidget(self._build_footer())

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("ocrToolbar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 10, 16, 10)
        row.setSpacing(10)

        self._lang = QComboBox()
        for value, label in LANG_OPTIONS:
            self._lang.addItem(label, value)
        self._lang.setFixedWidth(160)
        # 应用配置里的默认识别语言
        if self.config is not None:
            default_lang = self.config.get("ocr", "default_lang", "mix")
            idx = self._lang.findData(default_lang)
            if idx >= 0:
                self._lang.setCurrentIndex(idx)
        # 切换语言即自动重新识别(免去再点「重新识别」)
        self._lang.currentIndexChanged.connect(self._start_recognize)

        self._btn_redo = QPushButton("重新识别")
        self._btn_redo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_redo.clicked.connect(self._start_recognize)

        row.addWidget(QLabel("识别语言"))
        row.addWidget(self._lang)
        row.addStretch(1)
        row.addWidget(self._btn_redo)
        return bar

    def _build_body(self) -> QHBoxLayout:
        body = QHBoxLayout()
        body.setContentsMargins(16, 8, 16, 8)
        body.setSpacing(12)

        # 左:原图缩略
        self._thumb = QLabel("原图缩略区")
        self._thumb.setObjectName("ocrThumb")
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setFixedWidth(_THUMB_MAX + 12)
        self._thumb.setMinimumHeight(200)
        self._refresh_thumb()

        # 右:可编辑识别文本
        self._text = QPlainTextEdit()
        self._text.setObjectName("ocrText")
        self._text.setPlaceholderText("识别结果将显示在此,可直接编辑。")

        body.addWidget(self._thumb)
        body.addWidget(self._text, 1)
        return body

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setObjectName("ocrFooter")
        row = QHBoxLayout(footer)
        row.setContentsMargins(16, 10, 16, 10)
        row.setSpacing(8)

        self._status = QLabel("")
        self._status.setObjectName("ocrStatus")

        # 翻译:PLAN 明确先留位,默认不接在线翻译 → 禁用 + 提示
        self._btn_translate = QPushButton("翻译")
        self._btn_translate.setEnabled(False)
        self._btn_translate.setToolTip("翻译为可选功能,默认不接在线翻译")

        self._btn_save = QPushButton("保存 txt")
        self._btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_save.clicked.connect(self._save_txt)

        self._btn_copy = QPushButton("复制全部")
        self._btn_copy.setProperty("primary", "true")
        self._btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_copy.clicked.connect(self._copy_all)

        self._btn_close = QPushButton("关闭")
        self._btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_close.clicked.connect(self.close)

        row.addWidget(self._status)
        row.addStretch(1)
        row.addWidget(self._btn_translate)
        row.addWidget(self._btn_save)
        row.addWidget(self._btn_copy)
        row.addWidget(self._btn_close)
        return footer

    def _refresh_thumb(self) -> None:
        if self._source.isNull():
            return
        # 先在 CPU 侧缩小 QImage 再转 QPixmap,避免把 4K 原图整张上传 GPU 造成卡顿
        scaled = self._source.scaled(
            _THUMB_MAX, _THUMB_MAX,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._thumb.setPixmap(QPixmap.fromImage(scaled))

    # ---- 识别流程 ----
    def showEvent(self, event) -> None:
        super().showEvent(event)
        # 首次显示后自动发起识别
        if self._worker is None:
            self._start_recognize()

    def _start_recognize(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return  # 正在识别,忽略重复触发
        image_bytes = prepare_ocr_bytes(self._source)
        if not image_bytes:
            self._status.setText("无法读取图片,识别已取消")
            return

        lang = self._lang.currentData() or "mix"
        self._set_busy(True)
        self._status.setText("识别中…")

        # worker 不挂 parent(避免窗口销毁时连带销毁运行中的 QThread 导致闪退);
        # 用类级集合持有引用防 GC,跑完自动 deleteLater + 移除。
        worker = OcrWorker(image_bytes, lang)
        self._worker = worker
        type(self)._running_workers.add(worker)
        worker.sig_done.connect(self._on_done)
        worker.finished.connect(lambda w=worker: type(self)._running_workers.discard(w))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_done(self, result: OcrResult) -> None:
        self._set_busy(False)
        if not result.ok:
            self._status.setText(result.error or "识别失败")
            log.warning("OCR 失败:%s", result.error)
            return

        self._text.setPlainText(result.text)
        if result.lines:
            self._status.setText(
                f"识别耗时 {format_elapsed(result.elapsed_ms)} · "
                f"置信度 {format_confidence(result.avg_confidence)} · "
                f"{len(result.lines)} 行"
            )
            # 配置开启时自动复制识别结果(不覆盖耗时/置信度状态)
            if self.config is not None and self.config.get("ocr", "auto_copy", False):
                from PySide6.QtGui import QGuiApplication
                QGuiApplication.clipboard().setText(result.text)
        else:
            self._status.setText("未识别到文字")

    def _set_busy(self, busy: bool) -> None:
        self._btn_redo.setEnabled(not busy)
        self._lang.setEnabled(not busy)
        self._btn_copy.setEnabled(not busy)
        self._btn_save.setEnabled(not busy)

    # ---- 输出 ----
    def _copy_all(self) -> None:
        from PySide6.QtGui import QGuiApplication

        text = self._text.toPlainText()
        QGuiApplication.clipboard().setText(text)
        self._status.setText(f"已复制全部文本({len(text)} 字)")

    def _save_txt(self) -> None:
        default_dir = ""
        if self.config is not None:
            default_dir = self.config.get("screenshot", "save_dir", "") or ""
        if not default_dir:
            default_dir = str(paths.data_dir())
        default_name = os.path.join(default_dir, f"OCR_{int(time.time())}.txt")

        path, _ = QFileDialog.getSaveFileName(
            self, "保存识别文本", default_name, "文本文件 (*.txt)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._text.toPlainText())
            self._status.setText(f"已保存:{os.path.basename(path)}")
            log.info("OCR 文本已保存:%s", path)
        except OSError as e:
            self._status.setText("保存失败,请检查路径")
            log.error("OCR 文本保存失败:%s", e)

    # ---- 生命周期 ----
    def closeEvent(self, event) -> None:
        # 断开回调:即便后台线程稍后跑完,也不再回调已销毁的控件(防 RuntimeError)。
        # worker 不挂 parent 且在 _running_workers 中持有,会自行 deleteLater,无需阻塞 wait。
        if self._worker is not None:
            try:
                self._worker.sig_done.disconnect(self._on_done)
            except (TypeError, RuntimeError):
                pass
            self._worker = None
        self.closed.emit(self)
        super().closeEvent(event)
