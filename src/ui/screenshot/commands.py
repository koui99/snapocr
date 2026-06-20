"""标注撤销/重做命令(命令模式)。

每个用户操作(新增 / 删除 / 编辑)封装为 QUndoCommand,压入 QUndoStack。
命令仅持有标注列表与控制器引用,通过控制器回调刷新视图,保持与渲染解耦。
"""
from __future__ import annotations

from PySide6.QtGui import QUndoCommand

from src.core.screenshot.annotations import BaseAnnotation


class AddAnnotationCommand(QUndoCommand):
    """新增一个标注对象。"""

    def __init__(self, controller, item: BaseAnnotation):
        super().__init__("添加标注")
        self._controller = controller
        self._item = item

    def redo(self) -> None:
        if self._item not in self._controller.annotations:
            self._controller.annotations.append(self._item)
        self._controller.set_active_item(self._item)
        self._controller.request_update()

    def undo(self) -> None:
        if self._item in self._controller.annotations:
            self._controller.annotations.remove(self._item)
        self._controller.clear_active()
        self._controller.request_update()


class DeleteAnnotationCommand(QUndoCommand):
    """删除 / 橡皮擦擦除一个标注对象。"""

    def __init__(self, controller, item: BaseAnnotation):
        super().__init__("删除标注")
        self._controller = controller
        self._item = item

    def redo(self) -> None:
        if self._item in self._controller.annotations:
            self._controller.annotations.remove(self._item)
        self._controller.clear_active()
        self._controller.request_update()

    def undo(self) -> None:
        self._controller.annotations.append(self._item)
        self._controller.request_update()


class EditAnnotationCommand(QUndoCommand):
    """编辑一个标注对象(移动 / 缩放 / 改色 / 改粗细)。

    before / after 为 annotation.capture_state() 快照。
    """

    def __init__(self, item: BaseAnnotation, before: dict, after: dict, controller):
        super().__init__("编辑标注")
        self._item = item
        self._before = before
        self._after = after
        self._controller = controller

    def redo(self) -> None:
        self._item.restore_state(self._after)
        self._controller.request_update()

    def undo(self) -> None:
        self._item.restore_state(self._before)
        self._controller.request_update()
