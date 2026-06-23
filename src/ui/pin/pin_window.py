"""贴图浮窗 PinWindow:把一张图片钉在桌面上的无边框置顶浮窗。

结构沿用 M2 工具栏的「半透明顶层窗 + 内层内容控件 + 投影」模式(已在真机验证可行):
- 顶层窗透明、无边框、置顶、Tool(不进任务栏),四周留 MARGIN 给柔和阴影。
- 内层 _PinCanvas 绘制(缩放+旋转后的)图片 + 1px 细边框 + 右下角缩放徽标,并承接交互。
交互:拖动移动、滚轮缩放、右键菜单、键盘(Esc/Shift+Esc/Ctrl+C/Ctrl+S/±)。
复制/保存复用 core.screenshot.writer,不重复造轮子。
"""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QRect,
    QRectF,
    Qt,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import QMenu, QWidget

from src.core.logger import get_logger
from src.core.screenshot.writer import ScreenshotWriter
from src.ui.components.shadow_widget import apply_shadow
from src.ui.theme.tokens import COLORS

log = get_logger("pin.window")

_MARGIN = 16          # 阴影留白
_PANEL_GAP = 6        # 图与下方 OCR 文字面板的间距
_MIN_SCALE = 0.1
_MAX_SCALE = 8.0
_WHEEL_STEP = 1.1
_OPACITY_LEVELS = [100, 80, 60, 40, 20]

# 模块级集合:持有贴图原地 OCR 的后台线程,防止跑完前被 Python GC 回收
_PIN_OCR_WORKERS: set = set()


def clamp_scale(scale: float) -> float:
    """把缩放比例钳制到 [_MIN_SCALE, _MAX_SCALE]。"""
    return max(_MIN_SCALE, min(_MAX_SCALE, scale))


class _PinCanvas(QWidget):
    """贴图内容面:绘制图片 + 边框 + 徽标,事件转发给 owner(PinWindow)。"""

    def __init__(self, owner: "PinWindow"):
        super().__init__(owner)
        self._owner = owner
        self._flash = 0.0  # 创建时高亮强度 0~1,由 PinWindow 的入场动画驱动
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_flash(self, value: float) -> None:
        """设置入场高亮强度并重绘(0 = 无,1 = 最强)。"""
        self._flash = max(0.0, min(1.0, value))
        self.update()

    def paintEvent(self, event) -> None:
        owner = self._owner
        dp = owner.display_pixmap
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if dp is not None and not dp.isNull():
            painter.drawPixmap(0, 0, dp)

        # 彩色渐变边框(蓝→紫→橙):抗锯齿 + 半像素内缩,保证四边等粗、明显彩色
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0.0, QColor("#2D7FF9"))   # 蓝
        grad.setColorAt(0.5, QColor("#9B5DE5"))   # 紫
        grad.setColorAt(1.0, QColor("#FF7A45"))   # 橙
        pen = QPen(grad, 2)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(1, 1, self.width() - 2, self.height() - 2))

        # 入场高亮:创建瞬间叠一道暖橙描边并渐隐,强化「钉成功了」的反馈
        if self._flash > 0.0:
            accent = QColor("#FF5A36")
            accent.setAlpha(int(230 * self._flash))
            painter.setPen(QPen(accent, 2))
            painter.drawRect(QRectF(2, 2, self.width() - 4, self.height() - 4))

        # 右下角缩放徽标(rgba(0,0,0,0.6) 底 + 白字),还原 mockup
        text = f"{int(round(owner.scale * 100))}%"
        font = QFont()
        font.setPixelSize(11)
        painter.setFont(font)
        fm = QFontMetrics(font)
        bw = fm.horizontalAdvance(text) + 12
        bh = 18
        badge = QRect(self.width() - bw, self.height() - bh, bw, bh)
        painter.fillRect(badge, QColor(0, 0, 0, 153))
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(badge, int(Qt.AlignmentFlag.AlignCenter), text)
        painter.end()

    # 事件全部委托给 owner
    def mousePressEvent(self, e): self._owner.on_press(e)
    def mouseMoveEvent(self, e): self._owner.on_move(e)
    def mouseReleaseEvent(self, e): self._owner.on_release(e)
    def mouseDoubleClickEvent(self, e): self._owner.on_double_click(e)
    def wheelEvent(self, e): self._owner.on_wheel(e)
    def contextMenuEvent(self, e): self._owner.show_menu(e.globalPos())
    def keyPressEvent(self, e): self._owner.on_key(e)


class PinWindow(QWidget):
    """单个贴图浮窗。"""

    closed = Signal(object)  # 关闭时发射自身,供 PinManager 清理引用
    ocr_requested = Signal(object)  # 请求 OCR,载荷为当前图像 QImage(交由 app_context 弹结果窗)

    def __init__(self, pixmap: QPixmap, config, parent=None, source_ratio: float = 1.0):
        super().__init__(parent)
        self.config = config
        self._orig = QPixmap(pixmap)
        # 捕获时的 DPI 缩放比:截图来的贴图按此把物理像素折算回逻辑尺寸,
        # 使贴图与屏幕原区域「同样大小、同一位置」(剪贴板贴图无 DPI 信息,取 1.0)。
        self._base_dpr = max(0.1, float(source_ratio))
        self._scale = 1.0
        self._angle = 0
        self._opacity = 100
        self._on_top = True
        self._drag_offset: QPoint | None = None
        self._initialized = False  # 首次定位前不做「保持中心」的位移
        self.display_pixmap: QPixmap | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self._canvas = _PinCanvas(self)
        apply_shadow(self._canvas, heavy=True)
        self._ocr_panel = None     # 懒建:贴图下方的 OCR 文字面板
        self._ocr_worker = None    # 原地识别后台线程
        self._flash_anim = None    # 入场高亮动画
        self._flashed = False      # 入场高亮只播一次

        self._refresh()

    # ---- 只读属性给 canvas 用 ----
    @property
    def scale(self) -> float:
        return self._scale

    def _canvas_logical_size(self) -> tuple[int, int]:
        """当前显示图占用的逻辑尺寸(= 物理尺寸 ÷ DPI),即画布应占的逻辑像素。"""
        dp = self.display_pixmap
        if dp is not None and not dp.isNull():
            return (max(1, int(round(dp.width() / self._base_dpr))),
                    max(1, int(round(dp.height() / self._base_dpr))))
        return max(1, self._canvas.width()), max(1, self._canvas.height())

    # ---- 尺寸刷新(缩放/旋转后重算,保持窗口中心不动)----
    def _compute_display(self) -> QPixmap:
        if self._orig.isNull():
            return QPixmap()
        # 先按用户缩放重采样到物理目标尺寸
        sw = max(1, int(self._orig.width() * self._scale))
        sh = max(1, int(self._orig.height() * self._scale))
        dp = self._orig.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        if self._angle % 360 != 0:
            dp = dp.transformed(QTransform().rotate(self._angle),
                                Qt.TransformationMode.SmoothTransformation)
        # 关键:按捕获 DPI 标注,Qt 即以「逻辑尺寸 = 物理 ÷ DPI」绘制 →
        # 贴图与屏幕原区域同样大小,且高分屏下不糊(保留物理分辨率细节)。
        dp.setDevicePixelRatio(self._base_dpr)
        return dp

    def _refresh(self) -> None:
        self.display_pixmap = self._compute_display()
        cw, ch = self._canvas_logical_size()

        # OCR 文字面板(若有)接在图正下方,窗口向下加高;图本身位置不变
        panel_on = self._ocr_panel is not None and self._ocr_panel.has_fields()
        gap = _PANEL_GAP if panel_on else 0
        panel_h = self._ocr_panel.desired_height() if panel_on else 0

        new_w = cw + 2 * _MARGIN
        new_h = ch + gap + panel_h + 2 * _MARGIN

        old_center = self.geometry().center()
        self.resize(new_w, new_h)
        # 缩放/旋转时保持窗口中心不动(更顺手);但有文字面板时不挪窗,
        # 让图(canvas 恒在 _MARGIN,_MARGIN)留在原位、面板向下展开。
        if self._initialized and not panel_on:
            self.move(old_center.x() - new_w // 2, old_center.y() - new_h // 2)
        self._canvas.setGeometry(_MARGIN, _MARGIN, cw, ch)
        self._canvas.update()
        if panel_on:
            self._ocr_panel.setGeometry(_MARGIN, _MARGIN + ch + gap, cw, panel_h)

    # ---- 定位(由 PinManager 调用)----
    def move_center_to(self, point: QPoint) -> None:
        self.move(point.x() - self.width() // 2, point.y() - self.height() // 2)
        self._initialized = True  # 已完成首次定位,后续缩放/旋转保持中心

    def move_content_to(self, global_topleft: QPoint) -> None:
        """把贴图内容(去掉阴影留白)的左上角对齐到指定全局坐标 → 原位贴回。"""
        self.move(global_topleft.x() - _MARGIN, global_topleft.y() - _MARGIN)
        self._initialized = True

    # ---- 缩放 / 旋转 / 不透明度 / 置顶 ----
    def set_scale(self, scale: float) -> None:
        self._scale = clamp_scale(scale)
        self._refresh()

    def zoom(self, factor: float) -> None:
        self.set_scale(self._scale * factor)

    def reset_scale(self) -> None:
        self.set_scale(1.0)

    def rotate(self, delta: int) -> None:
        self._angle = (self._angle + delta) % 360
        # 旋转后清掉 OCR 文字面板(坐标/排序失效);需要可重新识别
        if self._ocr_panel is not None and self._ocr_panel.has_fields():
            self._ocr_panel.clear_fields()
            self._ocr_panel.hide()
        self._refresh()

    def set_opacity(self, percent: int) -> None:
        self._opacity = percent
        self.setWindowOpacity(max(0.05, percent / 100.0))

    def toggle_on_top(self, on: bool) -> None:
        self._on_top = on
        geom = self.geometry()  # 暂存位置/尺寸,防止 show() 后系统重置到原点
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on)
        self.show()             # 改 flag 后需重新 show 才生效
        self.setGeometry(geom)  # 恢复原位置/尺寸

    # ---- 复制 / 保存(复用 writer)----
    def _output_image(self):
        """复制/保存用的图像:保留原始分辨率,但体现用户的旋转(所见即所得)。"""
        src = self._orig
        if self._angle % 360 != 0:
            src = src.transformed(QTransform().rotate(self._angle),
                                  Qt.TransformationMode.SmoothTransformation)
        return src.toImage()

    def copy_image(self) -> None:
        ScreenshotWriter.copy_to_clipboard(self._output_image())

    def save_image(self) -> None:
        path = ScreenshotWriter.save_to_file(self._output_image(), self.config)
        if path:
            log.info("贴图已保存:%s", path)
        else:
            log.warning("贴图保存失败")

    # ---- 右键菜单 ----
    def _build_submenus(self, menu: QMenu) -> None:
        """装配缩放 / 不透明度 / 旋转三个二级子菜单。"""
        zoom_menu = menu.addMenu("缩放")
        zoom_menu.addAction("放大", lambda: self.zoom(1.25))
        zoom_menu.addAction("缩小", lambda: self.zoom(0.8))
        zoom_menu.addAction("恢复 100%", self.reset_scale)

        op_menu = menu.addMenu("不透明度")
        for level in _OPACITY_LEVELS:
            a = op_menu.addAction(f"{level}%")
            a.setCheckable(True)
            a.setChecked(level == self._opacity)
            a.triggered.connect(lambda _checked=False, lv=level: self.set_opacity(lv))

        rot_menu = menu.addMenu("旋转")
        rot_menu.addAction("向左旋转 90°", lambda: self.rotate(-90))
        rot_menu.addAction("向右旋转 90°", lambda: self.rotate(90))

    def show_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)

        act_copy = menu.addAction("复制")
        act_copy.setShortcut("Ctrl+C")
        act_copy.triggered.connect(self.copy_image)

        act_save = menu.addAction("保存图片")
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self.save_image)

        act_ocr = menu.addAction("文字识别 (OCR)")
        act_ocr.triggered.connect(self._request_ocr)

        menu.addSeparator()
        self._build_submenus(menu)
        menu.addSeparator()

        act_top = menu.addAction("置顶")
        act_top.setCheckable(True)
        act_top.setChecked(self._on_top)
        act_top.triggered.connect(lambda checked: self.toggle_on_top(checked))

        act_cancel = menu.addAction("取消贴图")
        act_cancel.setShortcut("Esc")
        act_cancel.triggered.connect(self.close)

        act_destroy = menu.addAction("销毁")
        act_destroy.setShortcut("Shift+Esc")
        act_destroy.triggered.connect(self.close)

        menu.exec(global_pos)
        menu.deleteLater()  # 显式回收,避免反复右键累积 QMenu 实例

    def _request_ocr(self) -> None:
        """贴图右键「文字识别」:在图下方展开可选文字面板;再点一次则收起(窗口高度还原)。
        旋转态(角度≠0)坐标排序无意义,降级为弹结果窗(发 ocr_requested)。"""
        # 已有面板 → 收起
        if self._ocr_panel is not None and self._ocr_panel.has_fields():
            self._ocr_panel.clear_fields()
            self._ocr_panel.hide()
            self._refresh()   # 收起后窗口高度还原
            return
        self._start_ocr()

    def start_inplace_ocr(self) -> None:
        """供外部(截图「识别」直接钉图)调用:钉出后立刻识别并在图下方展开文字面板。"""
        if self._ocr_panel is not None and self._ocr_panel.has_fields():
            return  # 已有结果,不重复识别
        self._start_ocr()

    def _start_ocr(self) -> None:
        """发起一次后台原地 OCR(图不动,识别完在图下方展开文字面板)。"""
        if self._angle % 360 != 0:
            # 旋转态退回独立结果窗
            self.ocr_requested.emit(self._output_image())
            return
        if self._ocr_worker is not None and self._ocr_worker.isRunning():
            return
        from src.ui.ocr.worker import OcrWorker, prepare_ocr_bytes

        image_bytes = prepare_ocr_bytes(self._orig.toImage())
        if not image_bytes:
            log.warning("贴图 OCR:图像为空")
            return
        lang = "mix"
        if self.config is not None:
            lang = self.config.get("ocr", "default_lang", "mix")
        worker = OcrWorker(image_bytes, lang)
        self._ocr_worker = worker
        _PIN_OCR_WORKERS.add(worker)
        worker.sig_done.connect(self._on_ocr_done)
        worker.finished.connect(lambda w=worker: _PIN_OCR_WORKERS.discard(w))
        worker.finished.connect(self._clear_ocr_worker_ref)
        worker.finished.connect(worker.deleteLater)
        worker.start()
        log.info("贴图原地 OCR 已发起")

    def _clear_ocr_worker_ref(self) -> None:
        # 线程结束后置空引用,避免下次 _request_ocr 误判 isRunning 或回调悬空对象
        self._ocr_worker = None

    def _on_ocr_done(self, result) -> None:
        if not result.ok:
            log.warning("贴图 OCR 失败:%s", result.error)
            return
        if not result.lines:
            log.info("贴图 OCR:未识别到文字")
            return
        if self._angle % 360 != 0:
            # 识别中途用户旋转了贴图 → 退回弹结果窗
            self.ocr_requested.emit(self._output_image())
            return
        from src.ui.pin.ocr_overlay import OcrTextPanel

        if self._ocr_panel is None:
            self._ocr_panel = OcrTextPanel(self)
            # 面板内「收起/展开」按钮 → 重算窗口高度
            self._ocr_panel.toggled.connect(self._refresh)
        placed = self._ocr_panel.build(result.lines)
        self._refresh()  # 在图下方展开面板,窗口随之加高
        log.info("贴图原地 OCR:图下方展开 %d 行可选文字", placed)

    # ---- 交互事件(由 _PinCanvas 转发)----
    def on_press(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            # 用 geometry().topLeft() 与 move() 保持同一坐标系,避免起拖瞬间跳动
            self._drag_offset = event.globalPosition().toPoint() - self.geometry().topLeft()
            self._canvas.setFocus()

    def on_move(self, event) -> None:
        if self._drag_offset is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def on_release(self, event) -> None:
        self._drag_offset = None

    def on_double_click(self, event) -> None:
        # 双击销毁贴图(「恢复100%」保留在右键菜单)
        if event.button() == Qt.MouseButton.LeftButton:
            self.close()

    def on_wheel(self, event) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        self.zoom(_WHEEL_STEP if delta > 0 else 1.0 / _WHEEL_STEP)

    def on_key(self, event) -> None:
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key.Key_Escape:
            self.close()  # 取消贴图 / 销毁均关闭
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom(_WHEEL_STEP)
        elif key == Qt.Key.Key_Minus:
            self.zoom(1.0 / _WHEEL_STEP)
        elif key == Qt.Key.Key_C and (mods & Qt.KeyboardModifier.ControlModifier):
            self.copy_image()
        elif key == Qt.Key.Key_S and (mods & Qt.KeyboardModifier.ControlModifier):
            self.save_image()

    # ---- 生命周期 ----
    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._canvas.setFocus()
        self._play_entrance_flash()

    def _play_entrance_flash(self) -> None:
        """首次显示时播放一段主题色描边渐隐(约 0.6s),让用户看清「这块被钉住了」。"""
        if self._flashed:
            return
        self._flashed = True
        anim = QVariantAnimation(self)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setDuration(600)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(lambda v: self._canvas.set_flash(float(v)))
        anim.finished.connect(lambda: self._canvas.set_flash(0.0))
        anim.start()
        self._flash_anim = anim  # 持引用防被 GC

    def closeEvent(self, event) -> None:
        # 断开原地 OCR 回调,避免后台线程稍后回调已销毁的窗口
        if self._ocr_worker is not None:
            try:
                self._ocr_worker.sig_done.disconnect(self._on_ocr_done)
            except (TypeError, RuntimeError):
                pass
            self._ocr_worker = None
        self.closed.emit(self)
        super().closeEvent(event)
