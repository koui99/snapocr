#!/usr/bin/env python3
"""SnapOCR(截图精灵)便捷启动入口。

用法:
    python run.py            # 正常启动(显示设置窗 + 托盘常驻)
    python run.py --minimized  # 仅托盘启动(供开机自启使用)
"""
import sys

from src.main import main

if __name__ == "__main__":
    sys.exit(main())
