"""全屏截图窗口:单屏遮罩 + 选区交互 + 标注画布 + 工具栏整合。

两种交互模式:
- 选区模式(未选工具):拖拽创建/调整选区,放大镜取色,选区 8 控制点。
- 标注模式(选中工具):鼠标事件转发标注控制器绘制/编辑,选区锁定。
确认/复制/保存/钉图/识别由窗口合成位图后,经信号上抛给 app_context 路由处理。
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QWidget

from src.core.logger import get_logger
from src.core.screenshot import annotations as ann
from src.core.screenshot.annotations import generate_full_mosaic
from src.core.screenshot.writer import ScreenshotWriter
from src.ui.screenshot.canvas import AnnotationController
from src.ui.screenshot.magnifier import MagnifierRenderer
from src.ui.screenshot.property_bar import PropertyBar
from src.ui.screenshot.selection import SelectionState, SelectionTracker
from src.ui.screenshot.text_overlay import OverlayTextEdit
from src.ui.screenshot.toolbar import ScreenshotToolbar
from src.ui.theme.tokens import COLORS

log = get_logger("screenshot.window")


class ScreenshotWindow(QWidget):
    """单显示器全屏遮罩 + 选区 + 标注窗体。"""

    # 信号契约
    sig_canceled = Signal()
    # 合成结果上抛:(合成图, 动作, 选区左上角全局坐标, 来源屏 DPI)  动作 ∈ {"copy","save","pin","ocr"}
    sig_result = Signal(QImage, str, QPoint, float)

    def __init__(self, screen, cap_data: dict, config, parent=None, default_action: str = "copy"):
        super().__init__(parent)
        self.screen_obj = screen
        self.config = config
        self.device_ratio = screen.devicePixelRatio()
        # 「确认」(Enter / 双击 / ✓)默认执行的动作:普通截图=copy;「贴图」发起的截图=pin
        self._default_action = default_action if default_action in ("copy", "save", "pin", "ocr") else "copy"

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setGeometry(screen.geometry())

        # 物理底图
        self.bg_pixmap = cap_data["pixmap"]
        self.bg_pixmap.setDevicePixelRatio(self.device_ratio)
        self.bg_image = self.bg_pixmap.toImage()

        # 选区 / 放大镜
        self.tracker = SelectionTracker(handle_size=10, hit_threshold=16)
        self.magnifier = MagnifierRenderer(size=135, zoom_factor=9, border_color=COLORS["primary"])
        self.last_mouse_pos = QPoint()
        self.show_magnifier = True
        self.last_magnifier_dirty_rect = QRect()

        # 标注控制器
        self.controller = AnnotationController(self)
        self._mosaic_ready = False  # 马赛克底图惰性生成标记
        self._picking = False        # 取色模式
        self._text_editor: OverlayTextEdit | None = None

        # 工具栏 / 属性条(子控件,选区完成后显示)
        self.toolbar = ScreenshotToolbar(self)
        self.toolbar.hide()
        self.toolbar.sig_tool_selected.connect(self._on_tool_selected)
        self.toolbar.sig_action.connect(self._on_toolbar_action)

        self.property_bar = PropertyBar(self)
        self.property_bar.hide()
        self.property_bar.set_active(self.controller.active_width, self.controller.active_color)
        self.property_bar.sig_width_changed.connect(self.controller.set_width)
        self.property_bar.sig_color_changed.connect(self.controller.set_color)

        # 撤销栈可用态 → 工具栏按钮
        self.controller.undo_stack.canUndoChanged.connect(self.toolbar.set_undo_enabled)
        self.controller.undo_stack.canRedoChanged.connect(self.toolbar.set_redo_enabled)

    # ================= host 回调(供控制器使用)=================
    def request_update(self, rect: QRect | None = None) -> None:
        self.update() if rect is None else self.update(rect)

    def selection_rect_f(self) -> QRectF:
        return QRectF(self.tracker.rect)

    def start_text_input(self, pos: QPointF) -> None:
        """在 pos 处唤起就地文字编辑浮层。"""
        if self._text_editor is not None:
            self._text_editor.clearFocus()  # 触发提交
        px = max(14, self.controller.active_width * 5)
        editor = OverlayTextEdit(self.controller.active_color, px, self)
        editor.move(int(pos.x()), int(pos.y()))
        editor.sig_commit.connect(lambda text, p=pos: self._commit_text(p, text))
        editor.sig_cancel.connect(self._discard_text_editor)
        editor.show()
        editor.setFocus()
        self._text_editor = editor

    def _commit_text(self, pos: QPointF, text: str) -> None:
        self.controller.commit_text(pos, text)
        self._discard_text_editor()

    def _discard_text_editor(self) -> None:
        if self._text_editor is not None:
            self._text_editor.deleteLater()
            self._text_editor = None
        self.update()

    @property
    def annotation_mode(self) -> bool:
        return self.controller.current_tool is not None

    # ================= 绘制 =================
    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)

        # 1. 底图
        painter.drawPixmap(0, 0, self.bg_pixmap)
        # 2. 暗色遮罩(选区外)
        self._draw_overlay_mask(painter)

        # 3. 标注层(裁剪到选区内)
        if not self.tracker.rect.isEmpty():
            painter.save()
            painter.setClipRect(self.tracker.rect)
            self.controller.paint(painter)
            painter.restore()

        # 4. 选区边框 +(选区模式下)8 控制点
        if not self.tracker.rect.isEmpty():
            self._draw_selection_border(painter, handles=not self.annotation_mode)

        # 5. 放大镜(仅选区模式 / 取色模式,且未拖拽中)
        if self.show_magnifier and (not self.annotation_mode or self._picking) and \
                self.tracker.state in (SelectionState.IDLE, SelectionState.CREATING):
            dirty = self.magnifier.draw(painter, self.last_mouse_pos, self.bg_image, self.device_ratio)
            self.last_magnifier_dirty_rect = dirty

        painter.end()

    def _draw_overlay_mask(self, painter: QPainter):
        w, h = self.width(), self.height()
        mask = QColor(0, 0, 0, 110)
        if self.tracker.is_empty():
            painter.fillRect(0, 0, w, h, mask)
            return
        r = self.tracker.rect
        painter.fillRect(0, 0, w, r.top(), mask)
        painter.fillRect(0, r.bottom(), w, h - r.bottom(), mask)
        painter.fillRect(0, r.top(), r.left(), r.height(), mask)
        painter.fillRect(r.right(), r.top(), w - r.right(), r.height(), mask)

    def _draw_selection_border(self, painter: QPainter, handles: bool):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.tracker.rect
        painter.setPen(QPen(QColor(COLORS["primary"]), 1.5, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(r)

        if handles:
            hs = self.tracker.handle_size
            painter.setPen(QPen(QColor(COLORS["primary"]), 2))
            painter.setBrush(QColor("#FFFFFF"))  # 白色填充更醒目
            for _name, center in self.tracker.get_handles().items():
                painter.drawRect(QRect(center.x() - hs // 2, center.y() - hs // 2, hs, hs))
        painter.restore()

    # ================= 鼠标事件 =================
    def mousePressEvent(self, event: QMouseEvent):
        pos = event.position().toPoint()
        posf = QPointF(pos)

        if event.button() == Qt.MouseButton.RightButton:
            # 右键:标注模式下取消工具回选区;选区模式下重置/取消
            if self.annotation_mode:
                self._select_tool(None)
            elif not self.tracker.is_empty():
                self.tracker.reset()
                self._hide_overlays()
                self.update()
            else:
                self.sig_canceled.emit()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        # 取色模式优先
        if self._picking:
            self._pick_color_at(pos)
            return

        if self.annotation_mode:
            self.controller.on_mouse_press(posf)
            self.update()
            return

        # —— 选区模式 ——
        target = self.tracker.hit_test(pos)
        log.debug(f"鼠标按下 pos={pos}, target={target}, state={self.tracker.state}")

        # 修复逻辑：优先判断 target，而非 state
        if target == "outside":
            # 点击选区外 → 重新创建选区
            self.tracker.start_creation(pos)
        elif target == "inside":
            # 点击选区内 → 移动选区
            self.tracker.start_move(pos)
        else:
            # 点击控制点 → 调整大小
            self.tracker.start_resize(pos, target)

        self.last_mouse_pos = pos
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.position().toPoint()
        posf = QPointF(pos)
        self.last_mouse_pos = pos

        if self._picking:
            self.show_magnifier = True
            self.update()
            return

        if self.annotation_mode:
            if event.buttons() & Qt.MouseButton.LeftButton:
                self.controller.on_mouse_move(posf)
            else:
                self.setCursor(self.controller.cursor_for(posf))
                self.controller.on_mouse_move(posf)  # 橡皮擦 hover
            return

        # —— 选区模式 ——
        bounds = QRect(0, 0, self.width(), self.height())
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.tracker.update_drag(pos, bounds)
            self.show_magnifier = False
            self._hide_overlays()
            self.update()
        else:
            self.show_magnifier = True
            target = self.tracker.hit_test(pos)
            cursor = self.tracker.get_cursor_shape(target)
            log.debug(f"鼠标悬停 pos={pos}, target={target}, cursor={cursor}")
            self.setCursor(cursor)
            if not self.last_magnifier_dirty_rect.isEmpty():
                self.update(self.last_magnifier_dirty_rect)
            self.update(QRect(pos.x() - 160, pos.y() - 160, 320, 320))

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        posf = QPointF(event.position().toPoint())

        if self.annotation_mode:
            self.controller.on_mouse_release(posf)
            self.update()
            return

        # —— 选区模式 —— 完成后显示工具栏
        self.tracker.end_drag()
        self.show_magnifier = True
        if not self.tracker.is_empty():
            self._show_toolbar()
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        if not self.annotation_mode and self.tracker.hit_test(pos) == "inside":
            # 选区内双击 = 确认(默认动作:普通截图=复制;贴图发起=钉图)
            self._emit_result(self._default_action)

    # ================= 键盘 =================
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key.Key_Escape:
            if self.annotation_mode:
                self._select_tool(None)
            else:
                self.sig_canceled.emit()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._emit_result(self._default_action)
            return
        if mods & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_Z and (mods & Qt.KeyboardModifier.ShiftModifier):
                self.controller.redo()
                return
            if key == Qt.Key.Key_Z:
                self.controller.undo()
                return
            if key == Qt.Key.Key_Y:
                self.controller.redo()
                return
            if key == Qt.Key.Key_C:
                self._emit_result("copy")
                return
            if key == Qt.Key.Key_S:
                self._emit_result("save")
                return
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.controller.delete_active()
            return
        super().keyPressEvent(event)

    # ================= 工具栏 / 属性条 =================
    def _on_tool_selected(self, tool: str):
        self.controller.set_tool(tool or None)
        if tool == ann.TOOL_MOSAIC:
            self._ensure_mosaic()
        # 绘图类工具显示属性条;橡皮擦 / 无工具隐藏
        if tool in ann.DRAWING_TOOLS:
            self._show_property_bar()
        else:
            self.property_bar.hide()
        self.setCursor(Qt.CursorShape.CrossCursor if tool else Qt.CursorShape.ArrowCursor)
        self.update()

    def _select_tool(self, tool: str | None):
        """程序化清除工具选择(右键/Esc),同步工具栏按钮态。"""
        self.toolbar.clear_tool_selection()
        self.controller.set_tool(tool)
        self.property_bar.hide()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def _on_toolbar_action(self, action: str):
        if action == "undo":
            self.controller.undo()
        elif action == "redo":
            self.controller.redo()
        elif action == "picker":
            self._picking = True
            self.show_magnifier = True
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.update()
        elif action == "copy":
            self._emit_result("copy")
        elif action == "save":
            self._emit_result("save")
        elif action == "pin":
            self._emit_result("pin")
        elif action == "ocr":
            self._emit_result("ocr")
        elif action == "cancel":
            self.sig_canceled.emit()
        elif action == "confirm":
            self._emit_result(self._default_action)

    def _show_toolbar(self):
        self.toolbar.adjustSize()
        tw, th = self.toolbar.width(), self.toolbar.height()
        r = self.tracker.rect
        # 工具栏居中对齐选区底部,而非右对齐,避免遮挡右下控制点
        x = r.x() + (r.width() - tw) // 2
        y = r.bottom() + 10  # 距离选区底部 10 像素
        if y + th > self.height():           # 下方放不下 → 选区上方
            y = r.top() - th - 10
        if y < 0:                            # 仍放不下 → 选区内底部(远离控制点)
            y = max(4, r.bottom() - th - 20)
        # 确保不超出屏幕边界
        x = max(4, min(x, self.width() - tw - 4))
        self.toolbar.move(x, y)
        self.toolbar.show()
        self.toolbar.raise_()
        self._reposition_property_bar()

    def _show_property_bar(self):
        self.property_bar.set_active(self.controller.active_width, self.controller.active_color)
        self._reposition_property_bar()
        self.property_bar.show()
        self.property_bar.raise_()

    def _reposition_property_bar(self):
        if not self.toolbar.isVisible():
            return
        pw, ph = self.property_bar.width(), self.property_bar.height()
        tb = self.toolbar.geometry()
        x = max(4, min(tb.left(), self.width() - pw - 4))
        y = tb.bottom() + 2
        if y + ph > self.height():
            y = max(4, tb.top() - ph - 2)
        self.property_bar.move(x, y)

    def _hide_overlays(self):
        """选区被重新拖拽时,隐藏工具栏/属性条并清空标注上下文。"""
        self.toolbar.hide()
        self.property_bar.hide()

    # ================= 取色 =================
    def _pick_color_at(self, pos: QPoint):
        px = int(pos.x() * self.device_ratio)
        py = int(pos.y() * self.device_ratio)
        if 0 <= px < self.bg_image.width() and 0 <= py < self.bg_image.height():
            color = QColor(self.bg_image.pixel(px, py))
            self.controller.active_color = color
            self.property_bar.set_active(self.controller.active_width, color)
            hex_str = color.name().upper()
            QGuiApplication.clipboard().setText(hex_str)
            log.info("取色:%s 已复制到剪贴板", hex_str)
        self._picking = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    # ================= 马赛克底图 =================
    def _ensure_mosaic(self):
        if self._mosaic_ready:
            return
        try:
            self.controller.mosaic_pixmap = generate_full_mosaic(
                self.bg_image, self.device_ratio, block_size=12
            )
            self._mosaic_ready = True
        except Exception as e:
            log.error("马赛克底图生成失败:%s", e)

    # ================= 合成输出 =================
    def _current_selection(self) -> QRect:
        if self.tracker.is_empty():
            return QRect(0, 0, self.width(), self.height())
        return self.tracker.rect

    def _emit_result(self, action: str):
        # 提交未完成的文字输入
        if self._text_editor is not None:
            self._text_editor.clearFocus()
        rect = self._current_selection()
        image = ScreenshotWriter.compose_image(
            rect, self.device_ratio, self.bg_pixmap, self.controller.annotations
        )
        if image is None:
            log.warning("合成失败,选区无效")
            return
        # 选区左上角的全局屏幕坐标(窗口覆盖本屏,窗口左上=屏幕左上)→ 供「钉图」原位贴回;
        # 连同来源屏 DPI 一起上抛,使贴图按逻辑尺寸还原,与屏幕原区域严丝合缝。
        origin = self.mapToGlobal(rect.topLeft())
        self.sig_result.emit(image, action, origin, float(self.device_ratio))
