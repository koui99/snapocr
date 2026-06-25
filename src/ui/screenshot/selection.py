"""选区交互追踪器:维护选区状态机、8 控制点坐标及命中测试(Hit Test)。
"""
from __future__ import annotations

from enum import Enum, auto
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QCursor

class SelectionState(Enum):
    IDLE = auto()          # 无选区
    CREATING = auto()      # 正在拖拽新建选区
    MOVING = auto()        # 正在拖动平移选区
    RESIZING = auto()      # 正在拖拽控制点缩放选区

# 控制点标识
HANDLE_TL = "tl"
HANDLE_T  = "t"
HANDLE_TR = "tr"
HANDLE_R  = "r"
HANDLE_BR = "br"
HANDLE_B  = "b"
HANDLE_BL = "bl"
HANDLE_L  = "l"

class SelectionTracker:
    """负责选区几何位置与状态维护的轻量类 (全部使用逻辑坐标)。"""

    def __init__(self, handle_size: int = 8, hit_threshold: int = 8):
        self.rect = QRect()  # 逻辑坐标选区
        self.state = SelectionState.IDLE
        self.active_handle: str | None = None
        
        self.handle_size = handle_size
        self.hit_threshold = hit_threshold
        
        # 拖拽临时变量
        self.drag_start_pos = QPoint()
        self.drag_start_rect = QRect()

    def is_empty(self) -> bool:
        return self.rect.isEmpty() or self.rect.width() <= 2 or self.rect.height() <= 2

    def reset(self):
        self.rect = QRect()
        self.state = SelectionState.IDLE
        self.active_handle = None

    def get_handles(self) -> dict[str, QPoint]:
        """计算当前 8 个控制点中心的逻辑位置。"""
        if self.rect.isEmpty():
            return {}

        r = self.rect
        c_x = r.x() + r.width() // 2
        c_y = r.y() + r.height() // 2

        # 使用明确的坐标计算，避免 topRight()/bottomRight() 的坐标偏差
        return {
            HANDLE_TL: QPoint(r.left(), r.top()),
            HANDLE_T: QPoint(c_x, r.top()),
            HANDLE_TR: QPoint(r.right(), r.top()),
            HANDLE_R: QPoint(r.right(), c_y),
            HANDLE_BR: QPoint(r.right(), r.bottom()),
            HANDLE_B: QPoint(c_x, r.bottom()),
            HANDLE_BL: QPoint(r.left(), r.bottom()),
            HANDLE_L: QPoint(r.left(), c_y),
        }

    def hit_test(self, pos: QPoint) -> str:
        """测试给定点所在的交互区域。

        返回:
            HANDLE_* 标识、'inside'、或 'outside'
        """
        from src.core.logger import get_logger
        log = get_logger("selection.hit_test")

        if self.is_empty():
            return "outside"

        # 1. 优先进行 8 控制点碰撞检测
        handles = self.get_handles()

        # 输出所有控制点位置
        log.debug(f"选区rect={self.rect}, 控制点数量={len(handles)}, 阈值={self.hit_threshold}")

        for name, pt in handles.items():
            # 距离检测
            dist = (pos - pt).manhattanLength()
            log.debug(f"  控制点 {name}: pt={pt}, 鼠标pos={pos}, 距离={dist}")
            if dist <= self.hit_threshold:
                log.info(f"✓ 命中控制点 {name}, 距离={dist}")
                return name

        # 2. 检测是否在选区内
        if self.rect.contains(pos):
            log.debug(f"在选区内 pos={pos}")
            return "inside"

        log.debug(f"在选区外 pos={pos}")
        return "outside"

    def start_creation(self, start_pos: QPoint):
        """开始创建新选区。"""
        self.state = SelectionState.CREATING
        self.drag_start_pos = start_pos
        self.rect = QRect(start_pos, start_pos)

    def start_move(self, start_pos: QPoint):
        """开始移动现有选区。"""
        self.state = SelectionState.MOVING
        self.drag_start_pos = start_pos
        self.drag_start_rect = QRect(self.rect)

    def start_resize(self, start_pos: QPoint, handle: str):
        """开始缩放现有选区。"""
        self.state = SelectionState.RESIZING
        self.active_handle = handle
        self.drag_start_pos = start_pos
        self.drag_start_rect = QRect(self.rect)

    def update_drag(self, pos: QPoint, bounds: QRect):
        """处理鼠标拖拽更新事件，传入边界限制 bounds。"""
        if self.state == SelectionState.CREATING:
            # 拖拽对角线创建，并限制在边界内
            x = max(bounds.left(), min(pos.x(), bounds.right()))
            y = max(bounds.top(), min(pos.y(), bounds.bottom()))
            self.rect = QRect(self.drag_start_pos, QPoint(x, y)).normalized()

        elif self.state == SelectionState.MOVING:
            # 整体平移选区
            delta = pos - self.drag_start_pos
            new_rect = self.drag_start_rect.translated(delta)
            
            # 贴边碰撞约束
            if new_rect.left() < bounds.left():
                new_rect.moveLeft(bounds.left())
            if new_rect.right() > bounds.right():
                new_rect.moveRight(bounds.right())
            if new_rect.top() < bounds.top():
                new_rect.moveTop(bounds.top())
            if new_rect.bottom() > bounds.bottom():
                new_rect.moveBottom(bounds.bottom())
                
            self.rect = new_rect

        elif self.state == SelectionState.RESIZING:
            # 根据激活的控制点更新矩形边缘
            r = QRect(self.drag_start_rect)
            h = self.active_handle
            
            # 限制坐标在当前屏幕范围内
            pos_x = max(bounds.left(), min(pos.x(), bounds.right()))
            pos_y = max(bounds.top(), min(pos.y(), bounds.bottom()))

            if h == HANDLE_TL:
                r.setTopLeft(QPoint(pos_x, pos_y))
            elif h == HANDLE_TR:
                r.setTopRight(QPoint(pos_x, pos_y))
            elif h == HANDLE_BL:
                r.setBottomLeft(QPoint(pos_x, pos_y))
            elif h == HANDLE_BR:
                r.setBottomRight(QPoint(pos_x, pos_y))
            elif h == HANDLE_T:
                r.setTop(pos_y)
            elif h == HANDLE_B:
                r.setBottom(pos_y)
            elif h == HANDLE_L:
                r.setLeft(pos_x)
            elif h == HANDLE_R:
                r.setRight(pos_x)
                
            self.rect = r.normalized()

    def end_drag(self):
        """拖拽结束，固化状态。"""
        if self.state == SelectionState.CREATING and self.is_empty():
            self.reset()
        else:
            self.state = SelectionState.IDLE
        self.active_handle = None

    def get_cursor_shape(self, hover_target: str) -> Qt.CursorShape:
        """根据当前鼠标命中的区域返回适当的鼠标光标类型。"""
        cursor_map = {
            HANDLE_TL: Qt.CursorShape.SizeFDiagCursor,
            HANDLE_BR: Qt.CursorShape.SizeFDiagCursor,
            HANDLE_TR: Qt.CursorShape.SizeBDiagCursor,
            HANDLE_BL: Qt.CursorShape.SizeBDiagCursor,
            HANDLE_T: Qt.CursorShape.SizeVerCursor,
            HANDLE_B: Qt.CursorShape.SizeVerCursor,
            HANDLE_L: Qt.CursorShape.SizeHorCursor,
            HANDLE_R: Qt.CursorShape.SizeHorCursor,
            "inside": Qt.CursorShape.SizeAllCursor,
            "outside": Qt.CursorShape.CrossCursor
        }
        return cursor_map.get(hover_target, Qt.CursorShape.ArrowCursor)
