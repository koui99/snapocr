"""截图合成输出:把「选区底图 + 标注层」合成为最终位图,并分别提供复制 / 保存。

设计要点:
- compose_image():纯合成,返回 QImage,不产生任何副作用(便于复用与测试)。
- copy_to_clipboard():仅复制到系统剪贴板(对应「复制」按钮 / 确认 ✓)。
- save_to_file():仅按 config.screenshot 写盘(对应「保存」按钮),返回保存路径。
复制与保存彻底分离,杜绝 M1 遗留的「每次确认强制存盘」行为。
"""
from __future__ import annotations

import os
import time

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QPixmap

from src.config import paths
from src.core.logger import get_logger

log = get_logger("screenshot.writer")


class ScreenshotWriter:
    """截图合成与输出写入器(全部为无状态静态方法)。"""

    @staticmethod
    def compose_image(
        logical_rect: QRect,
        device_ratio: float,
        bg_pixmap: QPixmap,
        annotations_list: list,
    ) -> QImage | None:
        """把选区底图与标注合成为一张物理分辨率无损的 QImage。

        参数:
            logical_rect: 逻辑像素选区
            device_ratio: 选区所在屏幕的 DPI 缩放比
            bg_pixmap: 原始抓取的物理底图
            annotations_list: 标注对象列表(各自实现 paint(painter))
        返回:
            合成后的 QImage;选区无效时返回 None。
        """
        if logical_rect is None or logical_rect.isEmpty():
            log.warning("选区为空,取消合成")
            return None

        px = int(logical_rect.x() * device_ratio)
        py = int(logical_rect.y() * device_ratio)
        pw = int(logical_rect.width() * device_ratio)
        ph = int(logical_rect.height() * device_ratio)
        if pw <= 0 or ph <= 0:
            return None
        physical_rect = QRect(px, py, pw, ph)

        log.info("合成物理尺寸 %dx%d(逻辑 %dx%d @ %.2fx)",
                 pw, ph, logical_rect.width(), logical_rect.height(), device_ratio)

        output = QImage(pw, ph, QImage.Format.Format_ARGB32)
        output.fill(Qt.GlobalColor.transparent)

        painter = QPainter(output)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # 1. 底图裁剪块铺满输出
        cropped = bg_pixmap.copy(physical_rect).toImage()
        painter.drawImage(QRect(0, 0, pw, ph), cropped)

        # 2. 切换到逻辑坐标系并把原点移到选区左上角,使标注高分辨率无损渲染
        painter.scale(device_ratio, device_ratio)
        painter.translate(-logical_rect.topLeft())

        for anno in annotations_list:
            try:
                anno.paint(painter)
            except Exception as e:  # 单个标注绘制失败不影响整体
                log.error("标注绘制失败:%s", e)

        painter.end()
        return output

    @staticmethod
    def copy_to_clipboard(image: QImage) -> bool:
        """把合成图复制到系统剪贴板;成功返回 True。"""
        if image is None or image.isNull():
            return False
        try:
            # 转 RGB32,规避部分 Windows 软件粘贴透明背景变黑
            clip_img = image.convertToFormat(QImage.Format.Format_RGB32)
            QGuiApplication.clipboard().setImage(clip_img)
            log.info("已复制到剪贴板")
            return True
        except Exception as e:
            log.error("复制到剪贴板失败:%s", e)
            return False

    @staticmethod
    def save_to_file(image: QImage, config) -> str | None:
        """按 config.screenshot 配置写盘;返回绝对路径,失败返回 None。"""
        if image is None or image.isNull():
            return None

        save_dir = config.get("screenshot", "save_dir", "") or ""
        fmt = (config.get("screenshot", "format", "png") or "png").lower()
        quality = int(config.get("screenshot", "quality", 90) or 90)

        if not save_dir:
            # 未配置则落到用户数据目录下的 screenshots/
            save_dir = str(paths.data_dir() / "screenshots")

        try:
            os.makedirs(save_dir, exist_ok=True)
            filename = f"Screenshot_{int(time.time())}.{fmt}"
            fullpath = os.path.join(save_dir, filename)
            # JPG 无 alpha,统一转 RGB32 再写,避免黑底
            out = image.convertToFormat(QImage.Format.Format_RGB32)
            if out.save(fullpath, fmt.upper(), quality):
                log.info("截图已保存:%s", fullpath)
                return fullpath
            log.error("截图保存失败,QImage.save 返回 False")
        except Exception as e:
            log.error("截图保存异常:%s", e)
        return None
