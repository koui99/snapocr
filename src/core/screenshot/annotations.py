"""标注对象数据模型:面向对象多态(BaseAnnotation + 各图形子类)。

每个标注对象自封装几何、自绘制(paint)、命中测试(hit_test)、整体位移(move_by)、
控制点(get_handles / update_by_handle)与状态快照(capture_state / restore_state,供撤销重做)。
仅依赖 QtCore / QtGui(图像与绘制),无 QtWidgets 依赖,符合「core 零 GUI 依赖」约束。
"""
from __future__ import annotations

import math
import uuid
from abc import ABC, abstractmethod

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPixmap,
    QPolygonF,
)

from src.core.screenshot import geometry as geo

# ---- 工具标识(与工具栏一一对应)----
TOOL_RECT = "rect"
TOOL_ELLIPSE = "ellipse"
TOOL_LINE = "line"
TOOL_ARROW = "arrow"
TOOL_PEN = "pen"
TOOL_MARKER = "marker"
TOOL_MOSAIC = "mosaic"
TOOL_TEXT = "text"
TOOL_SEQUENCE = "sequence"
TOOL_ERASER = "eraser"

# 绘图类工具(选中时弹出二级属性条)
DRAWING_TOOLS = {
    TOOL_RECT, TOOL_ELLIPSE, TOOL_LINE, TOOL_ARROW,
    TOOL_PEN, TOOL_MARKER, TOOL_MOSAIC, TOOL_TEXT, TOOL_SEQUENCE,
}

# 橡皮擦 hover 高亮色(半透明红)
_HOVER_COLOR = QColor(239, 68, 68, 150)


class BaseAnnotation(ABC):
    """所有标注图形的抽象基类。"""

    # 是否提供可缩放控制点(画笔/马克笔/马赛克为 False,仅可整体移动)
    has_handles: bool = False

    def __init__(self, pen_color: QColor, pen_width: int):
        self.id = uuid.uuid4()
        self.pen_color = QColor(pen_color)
        self.pen_width = int(pen_width)
        self.hovered = False  # 橡皮擦悬停高亮标记

    # ---- 抽象接口 ----
    @abstractmethod
    def paint(self, painter: QPainter) -> None:
        """把自身绘制到给定 painter(逻辑坐标系)。"""

    @abstractmethod
    def hit_test(self, pos: QPointF, tolerance: float = 8.0) -> bool:
        """命中测试:鼠标点是否落在图形上(供橡皮擦 / 选中)。"""

    @abstractmethod
    def move_by(self, dx: float, dy: float) -> None:
        """整体平移。"""

    @abstractmethod
    def get_handles(self) -> list[QPointF]:
        """返回控制点中心坐标列表(无控制点的图形返回空列表)。"""

    @abstractmethod
    def update_by_handle(self, index: int, pos: QPointF) -> None:
        """拖拽第 index 个控制点到 pos,更新几何。"""

    @abstractmethod
    def get_bounding_rect(self) -> QRectF:
        """包围盒(含画笔粗细外扩),用于脏区刷新与命中粗筛。"""

    # ---- 几何状态快照(撤销重做用,子类覆写 _geometry_state)----
    def _geometry_state(self) -> dict:
        return {}

    def _set_geometry_state(self, state: dict) -> None:
        pass

    def capture_state(self) -> dict:
        """捕获完整可恢复状态(颜色 + 粗细 + 几何)。"""
        state = {"pen_color": QColor(self.pen_color), "pen_width": self.pen_width}
        state.update(self._geometry_state())
        return state

    def restore_state(self, state: dict) -> None:
        """从快照恢复状态。"""
        if "pen_color" in state:
            self.pen_color = QColor(state["pen_color"])
        if "pen_width" in state:
            self.pen_width = state["pen_width"]
        self._set_geometry_state(state)

    # ---- 公共绘制辅助 ----
    def _draw_hover_outline(self, painter: QPainter) -> None:
        """橡皮擦悬停时,在包围盒上画半透明红框提示「将被删除」。"""
        if not self.hovered:
            return
        painter.save()
        pen = QPen(_HOVER_COLOR, 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.get_bounding_rect())
        painter.restore()


# ======================================================================
# 矩形 / 椭圆(共用包围盒控制点逻辑)
# ======================================================================
class _RectBasedAnnotation(BaseAnnotation):
    """以 QRectF 为几何的标注基类(矩形 / 椭圆),提供 8 控制点。"""

    has_handles = True

    def __init__(self, rect: QRectF, pen_color: QColor, pen_width: int):
        super().__init__(pen_color, pen_width)
        self.rect = QRectF(rect).normalized()

    def set_corner(self, p1: QPointF, p2: QPointF) -> None:
        """由两个对角点设定矩形(创建拖拽时调用)。"""
        self.rect = geo.normalized_rect(p1, p2)

    def move_by(self, dx: float, dy: float) -> None:
        self.rect.translate(dx, dy)

    def get_handles(self) -> list[QPointF]:
        r = self.rect
        cx = r.center().x()
        cy = r.center().y()
        # 顺序: TL, T, TR, R, BR, B, BL, L
        return [
            QPointF(r.left(), r.top()),
            QPointF(cx, r.top()),
            QPointF(r.right(), r.top()),
            QPointF(r.right(), cy),
            QPointF(r.right(), r.bottom()),
            QPointF(cx, r.bottom()),
            QPointF(r.left(), r.bottom()),
            QPointF(r.left(), cy),
        ]

    def update_by_handle(self, index: int, pos: QPointF) -> None:
        left, top, right, bottom = (
            self.rect.left(), self.rect.top(), self.rect.right(), self.rect.bottom(),
        )
        if index == 0:      # TL
            left, top = pos.x(), pos.y()
        elif index == 1:    # T
            top = pos.y()
        elif index == 2:    # TR
            right, top = pos.x(), pos.y()
        elif index == 3:    # R
            right = pos.x()
        elif index == 4:    # BR
            right, bottom = pos.x(), pos.y()
        elif index == 5:    # B
            bottom = pos.y()
        elif index == 6:    # BL
            left, bottom = pos.x(), pos.y()
        elif index == 7:    # L
            left = pos.x()
        self.rect = QRectF(QPointF(left, top), QPointF(right, bottom)).normalized()

    def get_bounding_rect(self) -> QRectF:
        m = self.pen_width / 2.0 + 8.0
        return self.rect.adjusted(-m, -m, m, m)

    def _geometry_state(self) -> dict:
        return {"rect": QRectF(self.rect)}

    def _set_geometry_state(self, state: dict) -> None:
        if "rect" in state:
            self.rect = QRectF(state["rect"])


class RectAnnotation(_RectBasedAnnotation):
    """空心矩形。"""

    def paint(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(self.pen_color, self.pen_width, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect)
        painter.restore()
        self._draw_hover_outline(painter)

    def hit_test(self, pos: QPointF, tolerance: float = 8.0) -> bool:
        return geo.point_to_rect_border_distance(pos, self.rect) <= tolerance + self.pen_width / 2.0


class EllipseAnnotation(_RectBasedAnnotation):
    """空心椭圆。"""

    def paint(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(self.pen_color, self.pen_width, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(self.rect)
        painter.restore()
        self._draw_hover_outline(painter)

    def hit_test(self, pos: QPointF, tolerance: float = 8.0) -> bool:
        # 用椭圆参数方程判定:点到椭圆边的近似距离
        rx = self.rect.width() / 2.0
        ry = self.rect.height() / 2.0
        if rx <= 0 or ry <= 0:
            return False
        c = self.rect.center()
        # 归一化半径值:=1 在椭圆上,<1 在内,>1 在外
        nx = (pos.x() - c.x()) / rx
        ny = (pos.y() - c.y()) / ry
        val = math.hypot(nx, ny)
        # 把容差换算到归一化尺度
        tol_norm = (tolerance + self.pen_width / 2.0) / min(rx, ry)
        return abs(val - 1.0) <= tol_norm


# ======================================================================
# 直线 / 箭头(两端控制点)
# ======================================================================
class LineAnnotation(BaseAnnotation):
    """直线。"""

    has_handles = True

    def __init__(self, p1: QPointF, p2: QPointF, pen_color: QColor, pen_width: int):
        super().__init__(pen_color, pen_width)
        self.p1 = QPointF(p1)
        self.p2 = QPointF(p2)

    def paint(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(self.pen_color, self.pen_width, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawLine(self.p1, self.p2)
        painter.restore()
        self._draw_hover_outline(painter)

    def hit_test(self, pos: QPointF, tolerance: float = 8.0) -> bool:
        return geo.point_to_segment_distance(pos, self.p1, self.p2) <= tolerance + self.pen_width / 2.0

    def move_by(self, dx: float, dy: float) -> None:
        self.p1 += QPointF(dx, dy)
        self.p2 += QPointF(dx, dy)

    def get_handles(self) -> list[QPointF]:
        return [QPointF(self.p1), QPointF(self.p2)]

    def update_by_handle(self, index: int, pos: QPointF) -> None:
        if index == 0:
            self.p1 = QPointF(pos)
        else:
            self.p2 = QPointF(pos)

    def get_bounding_rect(self) -> QRectF:
        m = self.pen_width / 2.0 + 8.0
        return geo.normalized_rect(self.p1, self.p2).adjusted(-m, -m, m, m)

    def _geometry_state(self) -> dict:
        return {"p1": QPointF(self.p1), "p2": QPointF(self.p2)}

    def _set_geometry_state(self, state: dict) -> None:
        if "p1" in state:
            self.p1 = QPointF(state["p1"])
        if "p2" in state:
            self.p2 = QPointF(state["p2"])


class ArrowAnnotation(LineAnnotation):
    """箭头(直线 + 实心箭头头部)。"""

    def paint(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(self.pen_color, self.pen_width, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(self.p1, self.p2)

        # 箭头头部:依据线段角度计算两翼
        angle = math.atan2(self.p2.y() - self.p1.y(), self.p2.x() - self.p1.x())
        head_len = max(12.0, self.pen_width * 3.5)
        spread = math.radians(26)
        left = QPointF(
            self.p2.x() - head_len * math.cos(angle - spread),
            self.p2.y() - head_len * math.sin(angle - spread),
        )
        right = QPointF(
            self.p2.x() - head_len * math.cos(angle + spread),
            self.p2.y() - head_len * math.sin(angle + spread),
        )
        painter.setBrush(self.pen_color)
        painter.setPen(QPen(self.pen_color, 1))
        painter.drawPolygon(QPolygonF([self.p2, left, right]))
        painter.restore()
        self._draw_hover_outline(painter)


# ======================================================================
# 画笔 / 马克笔(自由曲线)
# ======================================================================
class PathAnnotation(BaseAnnotation):
    """自由曲线:画笔(实色)或马克笔(半透明荧光,正片叠底)。"""

    has_handles = False

    def __init__(self, pen_color: QColor, pen_width: int, is_highlighter: bool = False):
        super().__init__(pen_color, pen_width)
        self.is_highlighter = is_highlighter
        self.points: list[QPointF] = []
        self.path = QPainterPath()

    def add_point(self, pt: QPointF) -> None:
        """追加采样点并以二次贝塞尔中点法重建平滑曲线。"""
        self.points.append(QPointF(pt))
        self._rebuild_path()

    def _rebuild_path(self) -> None:
        self.path = QPainterPath()
        n = len(self.points)
        if n == 0:
            return
        self.path.moveTo(self.points[0])
        if n == 1:
            # 单点:画一个极小线段,保证可见(点击成点)
            self.path.lineTo(self.points[0] + QPointF(0.01, 0.01))
            return
        if n == 2:
            self.path.lineTo(self.points[1])
            return
        # 用相邻点中点作为锚,当前点作为控制点,生成平滑曲线
        for i in range(1, n - 1):
            mid = (self.points[i] + self.points[i + 1]) / 2.0
            self.path.quadTo(self.points[i], mid)
        self.path.lineTo(self.points[-1])

    def paint(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.is_highlighter:
            # 单路径一次性绘制 + 正片叠底,避免自相交处叠色发暗
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
            color = QColor(self.pen_color)
            color.setAlpha(110)
            pen = QPen(color, self.pen_width * 3, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        else:
            pen = QPen(self.pen_color, self.pen_width, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path)
        painter.restore()
        self._draw_hover_outline(painter)

    def hit_test(self, pos: QPointF, tolerance: float = 8.0) -> bool:
        width = self.pen_width * (3 if self.is_highlighter else 1)
        return geo.point_to_polyline_distance(pos, self.points) <= tolerance + width / 2.0

    def move_by(self, dx: float, dy: float) -> None:
        delta = QPointF(dx, dy)
        self.points = [p + delta for p in self.points]
        self._rebuild_path()

    def get_handles(self) -> list[QPointF]:
        return []

    def update_by_handle(self, index: int, pos: QPointF) -> None:
        pass

    def get_bounding_rect(self) -> QRectF:
        if not self.points:
            return QRectF()
        m = (self.pen_width * (3 if self.is_highlighter else 1)) / 2.0 + 8.0
        return self.path.boundingRect().adjusted(-m, -m, m, m)

    def _geometry_state(self) -> dict:
        return {"points": [QPointF(p) for p in self.points]}

    def _set_geometry_state(self, state: dict) -> None:
        if "points" in state:
            self.points = [QPointF(p) for p in state["points"]]
            self._rebuild_path()


# ======================================================================
# 马赛克(沿笔迹裁剪预生成的像素化底图)
# ======================================================================
class MosaicAnnotation(BaseAnnotation):
    """马赛克笔刷:把预生成的全屏像素化图,沿笔迹描边区域裁剪显示。"""

    has_handles = False

    def __init__(self, mosaic_pixmap: QPixmap, brush_width: int):
        # 马赛克自身无颜色概念,占位用透明黑
        super().__init__(QColor(0, 0, 0), brush_width)
        self.mosaic_pixmap = mosaic_pixmap
        self.brush_width = brush_width
        self.points: list[QPointF] = []
        self._stroke = QPainterPath()

    def add_point(self, pt: QPointF) -> None:
        self.points.append(QPointF(pt))
        self._rebuild()

    def _rebuild(self) -> None:
        line = QPainterPath()
        if not self.points:
            self._stroke = line
            return
        line.moveTo(self.points[0])
        if len(self.points) == 1:
            line.lineTo(self.points[0] + QPointF(0.01, 0.01))
        else:
            for p in self.points[1:]:
                line.lineTo(p)
        stroker = QPainterPathStroker()
        stroker.setWidth(max(8, self.brush_width))
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self._stroke = stroker.createStroke(line)

    def paint(self, painter: QPainter) -> None:
        if self._stroke.isEmpty() or self.mosaic_pixmap is None or self.mosaic_pixmap.isNull():
            return
        painter.save()
        painter.setClipPath(self._stroke)
        # 像素化底图按其 devicePixelRatio 对齐逻辑坐标,绘制在窗口原点
        painter.drawPixmap(0, 0, self.mosaic_pixmap)
        painter.restore()
        self._draw_hover_outline(painter)

    def hit_test(self, pos: QPointF, tolerance: float = 8.0) -> bool:
        return geo.point_to_polyline_distance(pos, self.points) <= tolerance + self.brush_width / 2.0

    def move_by(self, dx: float, dy: float) -> None:
        # 马赛克与底图像素绑定,移动会露馅,M2 不支持移动(整删重画)
        pass

    def get_handles(self) -> list[QPointF]:
        return []

    def update_by_handle(self, index: int, pos: QPointF) -> None:
        pass

    def get_bounding_rect(self) -> QRectF:
        if self._stroke.isEmpty():
            return QRectF()
        m = 8.0
        return self._stroke.boundingRect().adjusted(-m, -m, m, m)


# ======================================================================
# 文字
# ======================================================================
class TextAnnotation(BaseAnnotation):
    """自由文字。pos 为文字基线左上角(逻辑坐标)。"""

    has_handles = False

    def __init__(self, pos: QPointF, text: str, pen_color: QColor, font: QFont):
        super().__init__(pen_color, font.pixelSize() if font.pixelSize() > 0 else 18)
        self.pos = QPointF(pos)
        self.text = text
        self.font = QFont(font)

    def _bounding(self) -> QRectF:
        fm = QFontMetricsF(self.font)
        rect = fm.boundingRect(QRectF(0, 0, 4000, 4000),
                               int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
                               self.text or " ")
        rect.moveTopLeft(self.pos)
        return rect

    def paint(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setFont(self.font)
        painter.setPen(QPen(self.pen_color))
        rect = self._bounding()
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
                         self.text)
        painter.restore()
        self._draw_hover_outline(painter)

    def hit_test(self, pos: QPointF, tolerance: float = 8.0) -> bool:
        return self._bounding().adjusted(-tolerance, -tolerance, tolerance, tolerance).contains(pos)

    def move_by(self, dx: float, dy: float) -> None:
        self.pos += QPointF(dx, dy)

    def get_handles(self) -> list[QPointF]:
        return []

    def update_by_handle(self, index: int, pos: QPointF) -> None:
        pass

    def get_bounding_rect(self) -> QRectF:
        return self._bounding().adjusted(-4, -4, 4, 4)

    def _geometry_state(self) -> dict:
        return {"pos": QPointF(self.pos), "text": self.text}

    def _set_geometry_state(self, state: dict) -> None:
        if "pos" in state:
            self.pos = QPointF(state["pos"])
        if "text" in state:
            self.text = state["text"]


# ======================================================================
# 序号标记(自动递增的数字圆圈)
# ======================================================================
class SequenceAnnotation(BaseAnnotation):
    """序号标记:实心圆 + 白色数字,点击放置、自动递增。"""

    has_handles = False

    def __init__(self, center: QPointF, number: int, pen_color: QColor, pen_width: int):
        super().__init__(pen_color, pen_width)
        self.center = QPointF(center)
        self.number = number
        self.radius = max(11.0, pen_width * 3.0)

    def paint(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
        painter.setBrush(self.pen_color)
        painter.drawEllipse(self.center, self.radius, self.radius)

        painter.setPen(QPen(QColor("#FFFFFF")))
        font = QFont()
        font.setBold(True)
        font.setPixelSize(int(self.radius * 1.1))
        painter.setFont(font)
        rect = QRectF(self.center.x() - self.radius, self.center.y() - self.radius,
                      self.radius * 2, self.radius * 2)
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), str(self.number))
        painter.restore()
        self._draw_hover_outline(painter)

    def hit_test(self, pos: QPointF, tolerance: float = 8.0) -> bool:
        return math.hypot(pos.x() - self.center.x(), pos.y() - self.center.y()) <= self.radius + tolerance

    def move_by(self, dx: float, dy: float) -> None:
        self.center += QPointF(dx, dy)

    def get_handles(self) -> list[QPointF]:
        return []

    def update_by_handle(self, index: int, pos: QPointF) -> None:
        pass

    def get_bounding_rect(self) -> QRectF:
        r = self.radius + 8
        return QRectF(self.center.x() - r, self.center.y() - r, r * 2, r * 2)

    def _geometry_state(self) -> dict:
        return {"center": QPointF(self.center)}

    def _set_geometry_state(self, state: dict) -> None:
        if "center" in state:
            self.center = QPointF(state["center"])


# ======================================================================
# 马赛克底图生成
# ======================================================================
def generate_full_mosaic(base_image: QImage, device_ratio: float = 1.0,
                         block_size: int = 12) -> QPixmap:
    """对整张底图做「先降采样再放大」生成像素化马赛克图。

    返回的 QPixmap 已设置 devicePixelRatio,使其在逻辑坐标系下与底图等大对齐。
    block_size 为物理像素块大小。
    """
    w = base_image.width()
    h = base_image.height()
    if w <= 0 or h <= 0:
        return QPixmap()
    block = max(2, int(block_size * device_ratio))
    small = base_image.scaled(
        max(1, w // block), max(1, h // block),
        Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation,
    )
    pixelated = small.scaled(
        w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation,
    )
    pixmap = QPixmap.fromImage(pixelated)
    pixmap.setDevicePixelRatio(device_ratio)
    return pixmap
