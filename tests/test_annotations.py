"""标注子系统纯逻辑单元测试(几何 / 命中测试 / 撤销命令 / 序号自增 / 颜色解析)。

均为不依赖窗口显示的逻辑测试,可在装有 PySide6 的 headless 环境(offscreen)运行。
本机若无 PySide6 仅做 py_compile 语法校验,真实断言在 Windows / CI 执行。
"""
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QFont
import pytest

from src.core.screenshot import geometry as geo
from src.core.screenshot import annotations as ann
from src.ui.screenshot.commands import (
    AddAnnotationCommand, DeleteAnnotationCommand, EditAnnotationCommand,
)
from src.ui.screenshot.canvas import AnnotationController


# ---------------- 几何 ----------------
def test_point_to_segment_distance():
    a, b = QPointF(0, 0), QPointF(10, 0)
    assert geo.point_to_segment_distance(QPointF(5, 0), a, b) == pytest.approx(0.0)
    assert geo.point_to_segment_distance(QPointF(5, 3), a, b) == pytest.approx(3.0)
    # 投影落在端点外 → 取端点距离
    assert geo.point_to_segment_distance(QPointF(-4, 0), a, b) == pytest.approx(4.0)


def test_point_to_rect_border_distance():
    rect = QRectF(0, 0, 100, 100)
    # 点在边框上
    assert geo.point_to_rect_border_distance(QPointF(0, 50), rect) == pytest.approx(0.0)
    # 点在矩形中心 → 到最近边 50
    assert geo.point_to_rect_border_distance(QPointF(50, 50), rect) == pytest.approx(50.0)


def test_normalized_rect():
    r = geo.normalized_rect(QPointF(30, 40), QPointF(10, 20))
    assert (r.x(), r.y(), r.width(), r.height()) == (10, 20, 20, 20)


# ---------------- 命中测试 ----------------
def test_rect_annotation_border_hit():
    r = ann.RectAnnotation(QRectF(10, 10, 100, 60), QColor("#EF4444"), 4)
    assert r.hit_test(QPointF(10, 40))         # 左边框上
    assert not r.hit_test(QPointF(60, 40))     # 空心矩形内部不命中


def test_line_annotation_hit():
    line = ann.LineAnnotation(QPointF(0, 0), QPointF(100, 0), QColor("#000"), 3)
    assert line.hit_test(QPointF(50, 2))
    assert not line.hit_test(QPointF(50, 40))


def test_sequence_hit_and_state():
    s = ann.SequenceAnnotation(QPointF(50, 50), 1, QColor("#2D7FF9"), 4)
    assert s.hit_test(QPointF(50, 50))
    s.move_by(10, 0)
    assert s.center == QPointF(60, 50)


# ---------------- 状态快照(撤销基础)----------------
def test_capture_restore_roundtrip():
    r = ann.RectAnnotation(QRectF(0, 0, 50, 50), QColor("#EF4444"), 4)
    before = r.capture_state()
    r.move_by(20, 20)
    assert r.rect.topLeft() == QPointF(20, 20)
    r.restore_state(before)
    assert r.rect.topLeft() == QPointF(0, 0)


# ---------------- 撤销 / 重做命令 ----------------
class _FakeController:
    def __init__(self):
        self.annotations = []
        self.active = None

    def set_active_item(self, item):
        self.active = item

    def clear_active(self):
        self.active = None

    def request_update(self):
        pass


def test_add_delete_commands():
    c = _FakeController()
    item = ann.RectAnnotation(QRectF(0, 0, 10, 10), QColor("#000"), 2)

    add = AddAnnotationCommand(c, item)
    add.redo()
    assert item in c.annotations and c.active is item
    add.undo()
    assert item not in c.annotations and c.active is None

    add.redo()  # 放回
    delete = DeleteAnnotationCommand(c, item)
    delete.redo()
    assert item not in c.annotations
    delete.undo()
    assert item in c.annotations


def test_edit_command():
    c = _FakeController()
    item = ann.RectAnnotation(QRectF(0, 0, 10, 10), QColor("#000"), 2)
    before = item.capture_state()
    item.move_by(5, 5)
    after = item.capture_state()
    cmd = EditAnnotationCommand(item, before, after, c)
    cmd.undo()
    assert item.rect.topLeft() == QPointF(0, 0)
    cmd.redo()
    assert item.rect.topLeft() == QPointF(5, 5)


# ---------------- 控制器:序号自增 ----------------
class _FakeHost:
    def request_update(self):
        pass

    def selection_rect_f(self):
        return QRectF(0, 0, 1000, 1000)

    def start_text_input(self, pos):
        pass


def test_controller_sequence_increment():
    ctrl = AnnotationController(_FakeHost())
    ctrl.set_tool(ann.TOOL_SEQUENCE)
    for i in range(3):
        ctrl.on_mouse_press(QPointF(100 + i * 30, 100))
    numbers = [a.number for a in ctrl.annotations if isinstance(a, ann.SequenceAnnotation)]
    assert numbers == [1, 2, 3]


def test_controller_undo_after_draw():
    ctrl = AnnotationController(_FakeHost())
    ctrl.set_tool(ann.TOOL_RECT)
    ctrl.on_mouse_press(QPointF(10, 10))
    ctrl.on_mouse_move(QPointF(80, 60))
    ctrl.on_mouse_release(QPointF(80, 60))
    assert len(ctrl.annotations) == 1
    ctrl.undo()
    assert len(ctrl.annotations) == 0
    ctrl.redo()
    assert len(ctrl.annotations) == 1


# ---------------- 颜色解析 ----------------
def test_color_parse():
    assert QColor("#2D7FF9").name().lower() == "#2d7ff9"
    for hex_c in ["#EF4444", "#22C55E", "#FFFFFF", "#1F2937"]:
        assert QColor(hex_c).isValid()
