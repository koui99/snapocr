"""标注控制器:截图窗口的标注交互大脑(数据 + 状态机,不直接持有 Qt 窗口绘制)。

职责:
- 持有标注列表、撤销栈(QUndoStack)、当前工具 / 颜色 / 粗细、当前选中对象。
- 接收窗口转发的鼠标事件,按工具分发:绘制新标注 / 编辑选中对象 / 橡皮擦删除。
- 提供 paint() 把所有标注 + 草稿 + 选中控制点画到窗口给定的 painter。
窗口(host)只需实现 request_update() / selection_rect_f() / start_text_input(pos) 三个回调。
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QUndoStack

from src.core.screenshot import annotations as ann
from src.ui.screenshot.commands import (
    AddAnnotationCommand,
    DeleteAnnotationCommand,
    EditAnnotationCommand,
)

# 交互子状态
_IDLE = "idle"
_DRAWING = "drawing"
_MOVING = "moving"
_RESIZING = "resizing"

_HANDLE_HIT = 12.0   # 控制点命中半径(逻辑像素)
_HANDLE_DRAW_R = 4   # 控制点绘制半径

# 控制点序号 → 光标(矩形 8 点:TL,T,TR,R,BR,B,BL,L)
_HANDLE_CURSORS = [
    Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeVerCursor,
    Qt.CursorShape.SizeBDiagCursor, Qt.CursorShape.SizeHorCursor,
    Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeVerCursor,
    Qt.CursorShape.SizeBDiagCursor, Qt.CursorShape.SizeHorCursor,
]


def _dist(a: QPointF, b: QPointF) -> float:
    return math.hypot(a.x() - b.x(), a.y() - b.y())


class AnnotationController:
    """标注交互控制器。"""

    def __init__(self, host):
        self.host = host
        self.annotations: list[ann.BaseAnnotation] = []
        self.undo_stack = QUndoStack()

        self.current_tool: str | None = None
        self.active_color = QColor("#EF4444")
        self.active_width = 4
        self.mosaic_pixmap: QPixmap | None = None

        self.active_item: ann.BaseAnnotation | None = None
        self._draft: ann.BaseAnnotation | None = None
        self._mode = _IDLE
        self._handle_index = -1
        self._drag_last = QPointF()
        self._edit_before: dict | None = None
        self._seq_counter = 1

    # ===== 命令回调(供 commands.py 调用)=====
    def set_active_item(self, item: ann.BaseAnnotation) -> None:
        self.active_item = item

    def clear_active(self) -> None:
        self.active_item = None

    def request_update(self) -> None:
        self.host.request_update()

    # ===== 工具 / 属性 =====
    def set_tool(self, tool: str | None) -> None:
        self.current_tool = tool or None
        # 切换工具时结束当前编辑选中态
        self.active_item = None
        self._draft = None
        self._mode = _IDLE
        if self.current_tool == ann.TOOL_SEQUENCE:
            # 序号计数从 1 重新开始(每次进入序号工具复位,符合 Snipaste 习惯)
            self._seq_counter = 1
        self.request_update()

    def set_color(self, color: QColor) -> None:
        self.active_color = QColor(color)
        if self.active_item is not None and not isinstance(self.active_item, ann.MosaicAnnotation):
            if self.active_item.pen_color.name() == QColor(color).name():
                self.request_update()
                return
            before = self.active_item.capture_state()
            self.active_item.pen_color = QColor(color)
            after = self.active_item.capture_state()
            self.undo_stack.push(EditAnnotationCommand(self.active_item, before, after, self))
        self.request_update()

    def set_width(self, width: int) -> None:
        self.active_width = int(width)
        if self.active_item is not None and not isinstance(
            self.active_item, (ann.MosaicAnnotation, ann.TextAnnotation)
        ):
            if self.active_item.pen_width == int(width):
                self.request_update()
                return
            before = self.active_item.capture_state()
            self.active_item.pen_width = int(width)
            after = self.active_item.capture_state()
            self.undo_stack.push(EditAnnotationCommand(self.active_item, before, after, self))
        self.request_update()

    # ===== 撤销 / 重做 / 删除 =====
    def undo(self) -> None:
        self.undo_stack.undo()
        self.request_update()

    def redo(self) -> None:
        self.undo_stack.redo()
        self.request_update()

    def delete_active(self) -> None:
        if self.active_item is not None and self.active_item in self.annotations:
            self.undo_stack.push(DeleteAnnotationCommand(self, self.active_item))

    def has_content(self) -> bool:
        return bool(self.annotations)

    # ===== 鼠标事件 =====
    def on_mouse_press(self, pos: QPointF) -> None:
        tool = self.current_tool
        if tool is None:
            return

        if tool == ann.TOOL_ERASER:
            target = self._hit_topmost(pos)
            if target is not None:
                self.undo_stack.push(DeleteAnnotationCommand(self, target))
            return

        if tool == ann.TOOL_TEXT:
            self.host.start_text_input(pos)
            return

        if tool == ann.TOOL_SEQUENCE:
            item = ann.SequenceAnnotation(pos, self._seq_counter, self.active_color, self.active_width)
            self._seq_counter += 1
            self.undo_stack.push(AddAnnotationCommand(self, item))
            return

        # 其余绘图工具:优先判断是否在编辑已选中对象
        if self.active_item is not None:
            idx = self._handle_at(self.active_item, pos)
            if idx >= 0:
                self._mode = _RESIZING
                self._handle_index = idx
                self._edit_before = self.active_item.capture_state()
                return
            if self.active_item.hit_test(pos, tolerance=10.0):
                self._mode = _MOVING
                self._drag_last = QPointF(pos)
                self._edit_before = self.active_item.capture_state()
                return

        # 开始绘制新草稿
        self._draft = self._create_draft(tool, pos)
        self._mode = _DRAWING

    def on_mouse_move(self, pos: QPointF) -> None:
        tool = self.current_tool
        if tool == ann.TOOL_ERASER:
            self._update_hover(pos)
            return

        if self._mode == _DRAWING and self._draft is not None:
            self._update_draft(self._draft, pos)
            self.request_update()
        elif self._mode == _MOVING and self.active_item is not None:
            dx = pos.x() - self._drag_last.x()
            dy = pos.y() - self._drag_last.y()
            self.active_item.move_by(dx, dy)
            self._drag_last = QPointF(pos)
            self.request_update()
        elif self._mode == _RESIZING and self.active_item is not None:
            self.active_item.update_by_handle(self._handle_index, pos)
            self.request_update()

    def on_mouse_release(self, pos: QPointF) -> None:
        if self._mode == _DRAWING and self._draft is not None:
            if self._draft_is_valid(self._draft):
                self.undo_stack.push(AddAnnotationCommand(self, self._draft))
            self._draft = None
        elif self._mode in (_MOVING, _RESIZING) and self.active_item is not None and self._edit_before is not None:
            after = self.active_item.capture_state()
            self.undo_stack.push(
                EditAnnotationCommand(self.active_item, self._edit_before, after, self)
            )
            self._edit_before = None
        self._mode = _IDLE
        self._handle_index = -1
        self.request_update()

    def commit_text(self, pos: QPointF, text: str) -> None:
        """文字浮层提交后,由窗口回调本方法生成文字标注。"""
        if not text:
            return
        font = QFont()
        font.setPixelSize(max(14, self.active_width * 5))
        item = ann.TextAnnotation(pos, text, self.active_color, font)
        self.undo_stack.push(AddAnnotationCommand(self, item))

    # ===== 草稿创建 / 更新 / 校验 =====
    def _create_draft(self, tool: str, pos: QPointF) -> ann.BaseAnnotation | None:
        if tool == ann.TOOL_RECT:
            item = ann.RectAnnotation(QRectF(pos, pos), self.active_color, self.active_width)
            item._origin = QPointF(pos)
            return item
        if tool == ann.TOOL_ELLIPSE:
            item = ann.EllipseAnnotation(QRectF(pos, pos), self.active_color, self.active_width)
            item._origin = QPointF(pos)
            return item
        if tool == ann.TOOL_LINE:
            return ann.LineAnnotation(pos, pos, self.active_color, self.active_width)
        if tool == ann.TOOL_ARROW:
            return ann.ArrowAnnotation(pos, pos, self.active_color, self.active_width)
        if tool == ann.TOOL_PEN:
            item = ann.PathAnnotation(self.active_color, self.active_width, is_highlighter=False)
            item.add_point(pos)
            return item
        if tool == ann.TOOL_MARKER:
            item = ann.PathAnnotation(self.active_color, self.active_width, is_highlighter=True)
            item.add_point(pos)
            return item
        if tool == ann.TOOL_MOSAIC:
            brush = max(16, self.active_width * 6)
            item = ann.MosaicAnnotation(self.mosaic_pixmap, brush)
            item.add_point(pos)
            return item
        return None

    def _update_draft(self, draft: ann.BaseAnnotation, pos: QPointF) -> None:
        if isinstance(draft, ann._RectBasedAnnotation):
            origin = getattr(draft, "_origin", draft.rect.topLeft())
            draft.set_corner(origin, pos)
        elif isinstance(draft, ann.LineAnnotation):
            draft.p2 = QPointF(pos)
        elif isinstance(draft, (ann.PathAnnotation, ann.MosaicAnnotation)):
            draft.add_point(pos)

    def _draft_is_valid(self, draft: ann.BaseAnnotation) -> bool:
        if isinstance(draft, ann._RectBasedAnnotation):
            return draft.rect.width() > 3 and draft.rect.height() > 3
        if isinstance(draft, ann.LineAnnotation):
            return _dist(draft.p1, draft.p2) > 3
        if isinstance(draft, (ann.PathAnnotation, ann.MosaicAnnotation)):
            return len(draft.points) >= 2
        return True

    # ===== 命中辅助 =====
    def _hit_topmost(self, pos: QPointF) -> ann.BaseAnnotation | None:
        for item in reversed(self.annotations):
            if item.hit_test(pos):
                return item
        return None

    def _handle_at(self, item: ann.BaseAnnotation, pos: QPointF) -> int:
        if not item.has_handles:
            return -1
        for i, h in enumerate(item.get_handles()):
            if _dist(h, pos) <= _HANDLE_HIT:
                return i
        return -1

    def _update_hover(self, pos: QPointF) -> None:
        target = self._hit_topmost(pos)
        changed = False
        for item in self.annotations:
            new_state = (item is target)
            if item.hovered != new_state:
                item.hovered = new_state
                changed = True
        if changed:
            self.request_update()

    # ===== 光标 =====
    def cursor_for(self, pos: QPointF) -> Qt.CursorShape:
        tool = self.current_tool
        if tool == ann.TOOL_ERASER:
            return Qt.CursorShape.PointingHandCursor
        if self.active_item is not None:
            idx = self._handle_at(self.active_item, pos)
            if idx >= 0:
                if self.active_item.has_handles and len(self.active_item.get_handles()) == 2:
                    return Qt.CursorShape.SizeAllCursor
                return _HANDLE_CURSORS[idx % len(_HANDLE_CURSORS)]
            if self.active_item.hit_test(pos, tolerance=10.0):
                return Qt.CursorShape.SizeAllCursor
        return Qt.CursorShape.CrossCursor

    # ===== 绘制 =====
    def paint(self, painter: QPainter) -> None:
        """绘制全部标注 + 草稿 + 选中对象控制点(painter 已由窗口裁剪到选区)。"""
        for item in self.annotations:
            item.paint(painter)
        if self._draft is not None:
            self._draft.paint(painter)
        if self.active_item is not None and self.active_item.has_handles and self._mode != _DRAWING:
            self._paint_handles(painter, self.active_item)

    def _paint_handles(self, painter: QPainter, item: ann.BaseAnnotation) -> None:
        handles = item.get_handles()
        if not handles:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
        painter.setBrush(QColor("#2D7FF9"))
        for h in handles:
            painter.drawEllipse(h, _HANDLE_DRAW_R, _HANDLE_DRAW_R)
        painter.restore()
