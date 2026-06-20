"""标注几何工具:点到线段 / 点到矩形边框的距离等纯几何运算。

仅依赖 QtCore(QPointF / QRectF),无任何 GUI 依赖,供标注对象的命中测试(橡皮擦、
鼠标再选中)复用,也便于在 headless 环境做纯逻辑单元测试。
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF


def point_to_segment_distance(p: QPointF, a: QPointF, b: QPointF) -> float:
    """点 p 到线段 ab 的最短欧氏距离(用于直线 / 箭头 / 画笔笔迹命中)。"""
    abx = b.x() - a.x()
    aby = b.y() - a.y()
    apx = p.x() - a.x()
    apy = p.y() - a.y()

    ab_len_sq = abx * abx + aby * aby
    if ab_len_sq == 0.0:
        # a、b 重合,退化为点到点距离
        return math.hypot(apx, apy)

    # 投影系数 t,限制在 [0,1] 之间(超出则取端点)
    t = (apx * abx + apy * aby) / ab_len_sq
    t = max(0.0, min(1.0, t))

    cx = a.x() + t * abx
    cy = a.y() + t * aby
    return math.hypot(p.x() - cx, p.y() - cy)


def point_to_polyline_distance(p: QPointF, points: list[QPointF]) -> float:
    """点 p 到折线(多段线)的最短距离;少于 2 点时退化为点距。"""
    if not points:
        return float("inf")
    if len(points) == 1:
        return math.hypot(p.x() - points[0].x(), p.y() - points[0].y())
    best = float("inf")
    for i in range(len(points) - 1):
        d = point_to_segment_distance(p, points[i], points[i + 1])
        if d < best:
            best = d
    return best


def point_to_rect_border_distance(p: QPointF, rect: QRectF) -> float:
    """点 p 到矩形四条边框的最短距离(用于无填充矩形 / 椭圆的描边命中)。"""
    tl = QPointF(rect.left(), rect.top())
    tr = QPointF(rect.right(), rect.top())
    br = QPointF(rect.right(), rect.bottom())
    bl = QPointF(rect.left(), rect.bottom())
    return min(
        point_to_segment_distance(p, tl, tr),
        point_to_segment_distance(p, tr, br),
        point_to_segment_distance(p, br, bl),
        point_to_segment_distance(p, bl, tl),
    )


def normalized_rect(p1: QPointF, p2: QPointF) -> QRectF:
    """由两个对角点构造左上原点、正宽高的规整矩形。"""
    x = min(p1.x(), p2.x())
    y = min(p1.y(), p2.y())
    w = abs(p2.x() - p1.x())
    h = abs(p2.y() - p1.y())
    return QRectF(x, y, w, h)
