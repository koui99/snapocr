"""截图交互与引擎单元测试。

测试选区状态机、命中测试以及 headless 环境下的截图优雅降级。
"""
from PySide6.QtCore import QPoint, QRect, Qt
import pytest

from src.core.screenshot.capture import CaptureEngine
from src.ui.screenshot.selection import (
    SelectionTracker, SelectionState,
    HANDLE_TL, HANDLE_BR, HANDLE_TR, HANDLE_BL
)

def test_capture_engine_headless_fallback():
    """测试在没有运行中的 display server 或是 headless 模式下，截图引擎是否能优雅降级返回 Mock 数据而不是 Crash。"""
    screens_data = CaptureEngine.capture_all_screens()
    assert isinstance(screens_data, dict)
    assert len(screens_data) >= 1
    
    # 验证返回字段结构
    for idx, data in screens_data.items():
        assert "rect" in data
        assert "pixmap" in data
        assert "device_ratio" in data
        assert len(data["rect"]) == 4

def test_selection_tracker_initial_state():
    tracker = SelectionTracker()
    assert tracker.state == SelectionState.IDLE
    assert tracker.is_empty()
    assert tracker.rect.isEmpty()

def test_selection_tracker_creation():
    tracker = SelectionTracker()
    bounds = QRect(0, 0, 1000, 1000)
    
    tracker.start_creation(QPoint(100, 100))
    assert tracker.state == SelectionState.CREATING
    
    tracker.update_drag(QPoint(300, 400), bounds)
    assert tracker.rect == QRect(100, 100, 200, 300)
    
    tracker.end_drag()
    assert tracker.state == SelectionState.IDLE
    assert not tracker.is_empty()

def test_selection_tracker_hit_test():
    tracker = SelectionTracker(handle_size=8, hit_threshold=8)
    bounds = QRect(0, 0, 1000, 1000)
    
    tracker.start_creation(QPoint(100, 100))
    tracker.update_drag(QPoint(200, 200), bounds)
    tracker.end_drag()
    
    # 选区现在是 QRect(100, 100, 100, 100) -> corners at (100,100), (200,200)
    
    # 测试控制点命中
    assert tracker.hit_test(QPoint(100, 100)) == HANDLE_TL
    assert tracker.hit_test(QPoint(200, 200)) == HANDLE_BR
    assert tracker.hit_test(QPoint(200, 100)) == HANDLE_TR
    assert tracker.hit_test(QPoint(100, 200)) == HANDLE_BL
    
    # 测试内部命中
    assert tracker.hit_test(QPoint(150, 150)) == "inside"
    
    # 测试外部命中
    assert tracker.hit_test(QPoint(50, 50)) == "outside"
    assert tracker.hit_test(QPoint(250, 250)) == "outside"

def test_selection_tracker_moving():
    tracker = SelectionTracker()
    bounds = QRect(0, 0, 1000, 1000)
    
    # 创建 QRect(100, 100, 100, 100)
    tracker.start_creation(QPoint(100, 100))
    tracker.update_drag(QPoint(200, 200), bounds)
    tracker.end_drag()
    
    # 模拟在内部按下鼠标并拖动
    tracker.start_move(QPoint(150, 150))
    assert tracker.state == SelectionState.MOVING
    
    tracker.update_drag(QPoint(250, 250), bounds)
    # 平移向量是 (100, 100)，新坐标应该是 (200, 200, 100, 100)
    assert tracker.rect == QRect(200, 200, 100, 100)
    
    tracker.end_drag()
    assert tracker.state == SelectionState.IDLE

def test_selection_tracker_bounds_clamping():
    tracker = SelectionTracker()
    # 限制边界为 0, 0, 500, 500
    bounds = QRect(0, 0, 500, 500)
    
    tracker.start_creation(QPoint(400, 400))
    # 往边界外拖拽
    tracker.update_drag(QPoint(600, 600), bounds)
    tracker.end_drag()
    
    # 选区应该被限制在 bounds 内部
    assert tracker.rect.right() <= 500
    assert tracker.rect.bottom() <= 500
