"""放大镜与取色渲染器:在指定位置绘制缩放像素和 RGB 颜色详情。
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

class MagnifierRenderer:
    """负责将截图底图的局部像素放大并标注取色值的渲染组件。"""

    def __init__(self, size: int = 135, zoom_factor: int = 9, border_color: str = "#2D7FF9"):
        """
        参数:
            size: 放大镜视窗的逻辑大小 (必须能整除 zoom_factor 得到奇数网格为佳)
            zoom_factor: 放大倍率(推荐 9 或 11，单数使中心像素对齐)
            border_color: 镜框描边色 (来自 design token @primary)
        """
        self.size = size
        self.zoom_factor = zoom_factor
        self.border_color = border_color
        
        # 网格边数 (表示取样多少个物理像素)
        self.sampling_radius = (size // zoom_factor) // 2

    def draw(self, painter: QPainter, mouse_pos: QPoint, bg_image: QImage, device_ratio: float) -> QRect:
        """在全屏窗口上绘制放大镜。
        
        参数:
            painter: 目标窗口的当前 QPainter 实例
            mouse_pos: 鼠标所在的当前逻辑位置
            bg_image: 初始化时拷贝的物理像素 QImage (通常是底图)
            device_ratio: 当前屏幕缩放比
            
        返回:
            放大镜绘制占用的逻辑 QRect (用于主窗体做局部 dirty update)
        """
        # 1. 获取鼠标在物理底图上的像素点坐标
        center_x = int(mouse_pos.x() * device_ratio)
        center_y = int(mouse_pos.y() * device_ratio)

        # 越界防错
        if center_x < 0 or center_y < 0 or center_x >= bg_image.width() or center_y >= bg_image.height():
            return QRect()

        # 2. 避免放大镜直接遮挡鼠标准星，做合理的偏移与屏幕边缘翻转
        offset_x = 20
        offset_y = 20
        
        # 边界检测翻转 (在逻辑坐标系上计算)
        screen_w = bg_image.width() / device_ratio
        screen_h = bg_image.height() / device_ratio
        
        if mouse_pos.x() + self.size + offset_x > screen_w:
            offset_x = -self.size - 20
        if mouse_pos.y() + self.size + offset_y > screen_h:
            offset_y = -self.size - 20

        # 放大镜的绘制逻辑矩形
        mag_rect = QRect(mouse_pos.x() + offset_x, mouse_pos.y() + offset_y, self.size, self.size)

        # 3. 绘制镜框外壳
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        # 外描边框与圆角阴影背景
        painter.setBrush(QColor(30, 30, 30, 220))
        painter.setPen(QPen(QColor(self.border_color), 2))
        painter.drawRoundedRect(mag_rect.adjusted(-1, -1, 1, 1), 6, 6)

        # 4. 像素切片采样与平铺放大绘制
        # 采样源物理像素包围盒
        src_rect = QRect(
            center_x - self.sampling_radius,
            center_y - self.sampling_radius,
            self.sampling_radius * 2 + 1,
            self.sampling_radius * 2 + 1
        )
        
        # 平铺渲染 (通过 drawImage 缩放插值)
        # 注意: 截图放大镜需要硬边锯齿样式，故关闭平滑 Pixmap 过滤以保持真实像素颗粒
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        
        # 裁剪出中间采样图画入放大镜上半部 (底部留 40 逻辑像素显示 RGB)
        pixel_draw_height = self.size - 40
        pixel_draw_rect = QRect(mag_rect.left(), mag_rect.top(), self.size, pixel_draw_height)
        
        # 画像素格
        painter.drawImage(pixel_draw_rect, bg_image, src_rect)

        # 5. 绘制中心准星红框
        # 计算出中心那个物理像素在逻辑放大镜中的相对位置
        center_cell_offset_x = (self.size - self.zoom_factor) // 2
        center_cell_offset_y = (pixel_draw_height - self.zoom_factor) // 2
        
        center_pixel_rect = QRect(
            mag_rect.left() + center_cell_offset_x,
            mag_rect.top() + center_cell_offset_y,
            self.zoom_factor,
            self.zoom_factor
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(239, 68, 68, 220), 1.5)) # 亮红准星
        painter.drawRect(center_pixel_rect)

        # 6. 获取当前中心点的颜色并展示
        center_color = QColor(bg_image.pixel(center_x, center_y))
        hex_str = f"#{center_color.red():02X}{center_color.green():02X}{center_color.blue():02X}"
        rgb_str = f"RGB: ({center_color.red()}, {center_color.green()}, {center_color.blue()})"

        # 绘制底部背景信息条
        info_rect = QRect(mag_rect.left(), mag_rect.bottom() - 40, self.size, 40)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(info_rect, QColor(20, 20, 20, 240))

        # 绘制一个小小的色块
        swatch_rect = QRect(info_rect.left() + 8, info_rect.top() + 10, 20, 20)
        painter.setPen(QPen(QColor(128, 128, 128, 100), 1))
        painter.setBrush(center_color)
        painter.drawRect(swatch_rect)

        # 绘制文本信息
        text_rect = QRect(swatch_rect.right() + 8, info_rect.top() + 4, info_rect.width() - swatch_rect.width() - 20, 32)
        painter.setPen(Qt.GlobalColor.white)
        
        font = QFont("Microsoft YaHei")
        font.setPixelSize(10)
        painter.setFont(font)
        
        # 换行绘制
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            f"{hex_str}\n{rgb_str}"
        )

        painter.restore()
        
        # 返回包括外部描边的完整更新脏区，以备局部重绘刷新缓存
        return mag_rect.adjusted(-6, -6, 6, 6)
