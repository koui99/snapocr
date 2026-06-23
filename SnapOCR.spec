# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# 收集 OCR 模型和字典文件
ocr_datas = [
    ('src/core/ocr/models/*.onnx', 'src/core/ocr/models'),
    ('src/core/ocr/models/*.txt', 'src/core/ocr/models'),
]

# 收集主题文件
theme_datas = [
    ('src/ui/theme/*.qss', 'src/ui/theme'),
]

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=ocr_datas + theme_datas,
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'rapidocr_onnxruntime',
        'onnxruntime',
        'cv2',
        'numpy',
        'PIL',
        'shapely',
    ],
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
    exclude_binaries=True,
    name='SnapOCR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 无控制台窗口
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
