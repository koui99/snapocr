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
    # 本项目只用 QtCore/QtGui/QtWidgets/QtNetwork/QtSvg 五个 Qt 模块,
    # 其余 Qt 生态(QML/Quick/Pdf/多媒体/虚拟键盘等)从依赖分析阶段就排除,
    # 避免 PyInstaller 的 Qt 钩子顺带收集它们的 DLL 与插件。
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuickWidgets',
    'PySide6.QtQuickControls2',
    'PySide6.QtPdf',
    'PySide6.QtPdfWidgets',
    'PySide6.QtOpenGL',
    'PySide6.QtOpenGLWidgets',
    'PySide6.QtVirtualKeyboard',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebChannel',
    'PySide6.QtWebSockets',
    'PySide6.QtSql',
    'PySide6.QtTest',
    'PySide6.QtDBus',
    'PySide6.Qt3DCore',
    'PySide6.QtCharts',
    'PySide6.QtDataVisualization',
    # PIL 与 GUI 框架的桥接模块用不到(还会把 PIL 和 Qt 钩在一起)
    'PIL.ImageQt',
    'PIL.ImageTk',
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


# ---------------------------------------------------------------------------
# 打包产物瘦身:从 a.binaries / a.datas 里剔除确定用不到的二进制与数据。
# 依据 2026-06-25 发布包的逐文件体积实测,合计可减约 100MB 解压体积。
# 剔除是否安全均已核对来源代码:
# - opencv_videoio_ffmpeg*.dll:cv2 视频编解码后端,OCR 流程只用 imdecode/
#   imgproc,videoio 按需 LoadLibrary,缺失不影响 import cv2。
# - PySide6/opengl32sw.dll + d3dcompiler*.dll:软件渲染 OpenGL 兜底,
#   纯 QWidget 应用不创建 GL 上下文。
# - Qt6Quick/Qml/Pdf/OpenGL/VirtualKeyboard 及配套插件:QML 生态,项目零使用;
#   它们经由 platforminputcontexts/imageformats(qpdf) 插件的依赖链被误收集。
# - PIL/_avif、_webp、_imagingft 等:Pillow 对这些扩展是 try/except 延迟导入,
#   缺失只在真正调用对应功能(AVIF 解码/字体绘制)时才报错,而 rapidocr 只在
#   可视化调试(VisRes)里用到,主流程不触达。
# - Qt 侧 OpenSSL(libcrypto-3-x64/libssl-3-x64)与 tls 插件:仅 QtNetwork 的
#   TLS 场景按需加载;本项目 QtNetwork 只用 QLocalServer/QLocalSocket(命名
#   管道),不走任何 TLS。注意 python 侧的 libcrypto-3.dll(无 -x64 后缀,
#   属 _ssl/_hashlib)不能删。
# - translations:应用界面文案全部自绘中文,只保留 Qt 内建控件的中文翻译。
# ---------------------------------------------------------------------------

# 子串匹配即剔除(统一小写、正斜杠比较)
_STRIP_PATTERNS = (
    # --- cv2 ---
    'opencv_videoio_ffmpeg',
    # --- PySide6 主 DLL ---
    'pyside6/opengl32sw.dll',
    'pyside6/d3dcompiler',
    'pyside6/qt6quick',
    'pyside6/qt6qml',
    'pyside6/qt6pdf',
    'pyside6/qt6opengl',
    'pyside6/qt6virtualkeyboard',
    'pyside6/qt6shadertools',
    # --- PySide6 插件目录 ---
    'pyside6/plugins/qmltooling/',
    'pyside6/plugins/platforminputcontexts/',
    'pyside6/plugins/virtualkeyboard/',
    'pyside6/plugins/tls/',
    'pyside6/plugins/networkinformation/',
    'pyside6/plugins/sqldrivers/',
    'pyside6/plugins/multimedia/',
    'pyside6/plugins/scenegraph/',
    'pyside6/plugins/renderers/',
    'pyside6/plugins/platforms/qdirect2d',   # 保留 qwindows/qoffscreen/qminimal
    # --- 图片格式插件:保留 qjpeg/qico/qsvg/qgif,剔除不会出现的格式 ---
    'pyside6/plugins/imageformats/qwebp',
    'pyside6/plugins/imageformats/qtiff',
    'pyside6/plugins/imageformats/qpdf',
    'pyside6/plugins/imageformats/qicns',
    'pyside6/plugins/imageformats/qtga',
    'pyside6/plugins/imageformats/qwbmp',
    # --- Qt 侧 OpenSSL(区别于 python 侧的 libcrypto-3.dll) ---
    'libcrypto-3-x64.dll',
    'libssl-3-x64.dll',
    # --- Pillow 可选编解码扩展 ---
    'pil/_avif',
    'pil/_webp',
    'pil/_imagingft',
    'pil/_imagingcms',
    'pil/_imagingmath',
    'pil/_imagingtk',
)


def _keep(entry) -> bool:
    name = entry[0].replace('\\', '/').lower()
    # Qt 翻译:只保留中文
    if '/translations/' in name and name.endswith('.qm'):
        return 'zh_cn' in name
    return not any(p in name for p in _STRIP_PATTERNS)


_before = len(a.binaries) + len(a.datas)
a.binaries = [e for e in a.binaries if _keep(e)]
a.datas = [e for e in a.datas if _keep(e)]
print(f'[SnapOCR.spec] 瘦身过滤:剔除 {_before - len(a.binaries) - len(a.datas)} 个文件')

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
