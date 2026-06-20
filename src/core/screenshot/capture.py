"""截图引擎核心:利用 mss 或 QScreen 抓取全屏图像。

支持多显示器、DPI 比率探测以及优雅降级(在 headless/Linux 下降级为 Mock 位图)。
"""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPixmap, QGuiApplication
from src.core.logger import get_logger

log = get_logger("screenshot.capture")

class CaptureEngine:
    """截图抓帧引擎。"""

    @staticmethod
    def capture_all_screens() -> dict[int, dict]:
        """抓取所有屏幕的物理像素，并返回包含位置、物理大小、DPI比率和QPixmap的字典。
        
        返回字典结构:
        {
            screen_index: {
                "rect": (left, top, width, height),  # 物理坐标
                "pixmap": QPixmap,                   # 物理像素位图
                "device_ratio": float                # 该屏幕的 DPI 缩放比
            }
        }
        """
        screens_data = {}
        
        # 优先尝试 mss 抓取
        try:
            import mss
            with mss.mss() as sct:
                # sct.monitors[0] 是整个虚拟屏幕，sct.monitors[1:] 是各个独立物理屏幕
                monitors = sct.monitors
                if len(monitors) > 1:
                    # 匹配 Qt 中的 screens，建立对应映射
                    qt_screens = QGuiApplication.screens()
                    for idx, monitor in enumerate(monitors[1:]):
                        # 获取对应的 Qt QScreen，以读取设备缩放比 (DPI)
                        ratio = 1.0
                        if idx < len(qt_screens):
                            ratio = qt_screens[idx].devicePixelRatio()
                        
                        sct_img = sct.grab(monitor)
                        width, height = sct_img.size
                        raw_bytes = sct_img.bgra
                        
                        # 核心转换：传入 raw 字节，然后调用 .copy() 使其在 C++ 堆中深拷贝，规避悬垂指针风险
                        qimg = QImage(
                            raw_bytes,
                            width,
                            height,
                            width * 4,
                            QImage.Format.Format_ARGB32
                        ).copy()
                        
                        pixmap = QPixmap.fromImage(qimg)
                        screens_data[idx] = {
                            "rect": (monitor["left"], monitor["top"], monitor["width"], monitor["height"]),
                            "pixmap": pixmap,
                            "device_ratio": ratio
                        }
                    log.info("成功使用 mss 抓取 %d 个屏幕", len(screens_data))
                    return screens_data
        except Exception as e:
            log.warning("mss 截屏失败，尝试使用 QScreen 降级。错误原因: %s", e)

        # 降级方案一：QScreen
        try:
            qt_screens = QGuiApplication.screens()
            if qt_screens:
                for idx, screen in enumerate(qt_screens):
                    ratio = screen.devicePixelRatio()
                    geom = screen.geometry()
                    
                    # 使用 QScreen.grabWindow 截取该屏幕
                    # grabWindow 在部分系统/无头模式下可能返回空，故做防护
                    pixmap = screen.grabWindow(0)
                    if not pixmap or pixmap.isNull():
                        raise RuntimeError(f"屏幕 {idx} grabWindow 返回空")
                        
                    # 物理大小 = 逻辑大小 * 缩放比
                    px_w = int(geom.width() * ratio)
                    px_h = int(geom.height() * ratio)
                    
                    screens_data[idx] = {
                        "rect": (int(geom.x() * ratio), int(geom.y() * ratio), px_w, px_h),
                        "pixmap": pixmap,
                        "device_ratio": ratio
                    }
                log.info("成功使用 QScreen.grabWindow 抓取 %d 个屏幕", len(screens_data))
                return screens_data
        except Exception as e:
            log.warning("QScreen 降级捕获也失败(可能处于 Headless 模式)。启用 Mock 降级。错误: %s", e)

        # 降级方案二：纯本地离线 Mock 数据（Headless 环境专属，如 Linux CI）
        return CaptureEngine._generate_mock_screens()

    @staticmethod
    def _generate_mock_screens() -> dict[int, dict]:
        """生成模拟的多屏渐变位图，防止 headless 环境下程序崩溃。"""
        from PySide6.QtGui import QPainter, QColor, QLinearGradient
        screens_data = {}
        
        # 模拟双屏配置
        qt_screens = QGuiApplication.screens()
        if qt_screens:
            # 如果有虚拟屏幕实例，遵循其实际 geometry
            for idx, screen in enumerate(qt_screens):
                geom = screen.geometry()
                ratio = screen.devicePixelRatio()
                pw = int(geom.width() * ratio)
                ph = int(geom.height() * ratio)
                
                qimg = QImage(pw, ph, QImage.Format.Format_ARGB32)
                qimg.fill(QColor(40, 40, 40))
                
                # 绘制华丽的渐变色底图
                painter = QPainter(qimg)
                gradient = QLinearGradient(0, 0, pw, ph)
                gradient.setColorAt(0.0, QColor(45, 127, 249, 100))  # SnapOCR 品牌主色带透明度
                gradient.setColorAt(1.0, QColor(20, 20, 20, 255))
                painter.fillRect(qimg.rect(), gradient)
                
                # 画一些文字提示
                painter.setPen(QColor(255, 255, 255))
                font = painter.font()
                font.setPointSize(20)
                painter.setFont(font)
                painter.drawText(qimg.rect(), Qt.AlignmentFlag.AlignCenter, f"Mock Monitor {idx}\n{pw}x{ph} @ {ratio}x")
                painter.end()
                
                screens_data[idx] = {
                    "rect": (int(geom.x() * ratio), int(geom.y() * ratio), pw, ph),
                    "pixmap": QPixmap.fromImage(qimg),
                    "device_ratio": ratio
                }
        else:
            # 彻底的无屏幕 headless (例如 CI 容器)
            mock_configs = [
                (0, 0, 1920, 1080, 1.0),
                (1920, 0, 1280, 720, 1.25)
            ]
            for idx, (x, y, w, h, ratio) in enumerate(mock_configs):
                pw = int(w * ratio)
                ph = int(h * ratio)
                
                qimg = QImage(pw, ph, QImage.Format.Format_ARGB32)
                qimg.fill(QColor(45, 127, 249, 80))
                
                painter = QPainter(qimg)
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(qimg.rect(), Qt.AlignmentFlag.AlignCenter, f"Mock Headless Screen {idx}\n{pw}x{ph}")
                painter.end()
                
                screens_data[idx] = {
                    "rect": (int(x * ratio), int(y * ratio), pw, ph),
                    "pixmap": QPixmap.fromImage(qimg),
                    "device_ratio": ratio
                }
                
        log.info("已生成 %d 个模拟屏幕背景", len(screens_data))
        return screens_data
