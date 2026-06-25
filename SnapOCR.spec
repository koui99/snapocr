# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

block_cipher = None

# 当前目录
base_path = Path('.')

# 手动指定所有数据文件
datas = [
    # OCR 模型（最重要）:
    # engine.py 在 PyInstaller 环境下从 sys._MEIPASS/models 查找模型,
    # 因此这里必须收集到顶层 models/ 目录,避免打包后日语模型找不到而降级。
    ('src/core/ocr/models', 'models'),
    # 主题文件
    ('src/ui/theme', 'src/ui/theme'),
    # 应用图标资源（运行时窗口/托盘图标）
    ('src/assets/app_icon.ico', 'src/assets'),
    ('src/assets/app_icon.svg', 'src/assets'),
]

# 收集 RapidOCR 的配置文件
from PyInstaller.utils.hooks import collect_data_files
datas += collect_data_files('rapidocr_onnxruntime')

# 所有需要的隐藏导入
hiddenimports = [
    # PySide6 核心
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtNetwork',
    'PySide6.QtSvg',
    'shiboken6',
    # OCR 相关
    'rapidocr_onnxruntime',
    'rapidocr_onnxruntime.api',
    'onnxruntime',
    'onnxruntime.capi',
    'onnxruntime.capi.onnxruntime_pybind11_state',
    # 图像处理
    'cv2',
    'numpy',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'PIL.ImageFilter',
    # 其他
    'shapely',
    'shapely.geometry',
]

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # onedir 模式：不把二进制文件打包到 exe 里
    name='SnapOCR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # 改为 True 可以看到错误信息和调试日志
    icon='src/assets/app_icon.ico',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SnapOCR',
)
