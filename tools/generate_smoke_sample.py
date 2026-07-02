#!/usr/bin/env python3
"""生成 OCR 冒烟测试样图(CI 构建后、冒烟前运行)。

在原生 windows 平台(字体完整)下用 QPainter 画 "SnapOCR 12345",
供打包后的 exe 在 offscreen 环境做 OCR 冒烟——offscreen 平台可能
没有可用字体渲染文字,故样图必须预先在此生成。

用法: python tools/generate_smoke_sample.py <输出.png>
"""
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

SMOKE_TEXT = "SnapOCR 12345"


def ink_count(image: QImage) -> int:
    """粗采样统计暗色像素数,用于断言文字确实画上去了。"""
    n = 0
    for y in range(0, image.height(), 3):
        for x in range(0, image.width(), 3):
            if QColor(image.pixel(x, y)).lightness() < 128:
                n += 1
    return n


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: generate_smoke_sample.py <输出.png>")
        return 2
    QApplication(sys.argv)

    image = QImage(640, 140, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    font = QFont("Arial")
    font.setPixelSize(56)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("black"))
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, SMOKE_TEXT)
    painter.end()

    ink = ink_count(image)
    if ink < 50:
        print(f"样图无笔迹(ink={ink}),字体渲染失败")
        return 1
    if not image.save(sys.argv[1], "PNG"):
        print("样图保存失败")
        return 1
    print(f"smoke sample ok: {sys.argv[1]} (ink={ink})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
