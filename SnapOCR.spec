# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

block_cipher = None

# 当前目录
base_path = Path('.')

# 手动指定所有数据文件
datas = [
    # 运行时只需要 QSS 模板;theme_manager/tokens 作为 Python 模块会进 PYZ,
    # 不需要把整个目录(含 __pycache__)再作为 data 打包一份。
    ('src/ui/theme/theme.qss', 'src/ui/theme'),
]

# OCR 可选模型:
# RapidOCR 自带中英混合默认模型;项目内 models/ 只放可选扩展模型。
# 日语模型已移除以减小安装包体积,因此这里仅在目录内确有文件时才收集。
_model_dir = base_path / 'src/core/ocr/models'
if _model_dir.exists() and any(path.is_file() for path in _model_dir.rglob('*')):
    datas.append((str(_model_dir), 'models'))

# 应用图标资源（运行时窗口/托盘图标）:
# exe 文件图标由 EXE(icon=...) 写入 PE 资源;运行时 Qt 托盘/窗口图标从
# src/assets/app_icon_<size>.png 加载,这些资源与 app_icon.ico 同源生成。
datas += [
    (str(path), 'src/assets')
    for path in sorted((base_path / 'src/assets').glob('app_icon*'))
    if path.is_file()
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
    # OCR 图像处理依赖(由 rapidocr 间接使用,保留核心项)
    'cv2',
    'numpy',
    'PIL',
    'PIL.Image',
]

# 排除常见“可选但很重”的生态包,避免依赖链中的 optional import 被误收集。
# 不排除 cv2/numpy/PIL/onnxruntime/rapidocr/PySide6 核心模块,保证现有功能不变。
excludes = [
    'IPython',
    'jupyter',
    'matplotlib',
    'notebook',
    'pandas',
    'pytest',
    'scipy',
    'sklearn',
    'tensorflow',
    'tkinter',
    'torch',
    'PyQt5',
    'PyQt6',
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
    excludes=excludes,
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
    console=False,  # 正式版本不显示控制台窗口
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
