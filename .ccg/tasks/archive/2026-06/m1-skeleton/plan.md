# M1 项目骨架 — 实施计划(Phase 3)

> 任务: m1-skeleton · 策略: full-collaborate · 综合 analysis.md(双模型)+ 本机环境实测。

## 0. 关键约束(决定验证方式 —— 必读)

| 事实 | 影响 |
|------|------|
| 本机 Python **3.14.4** | PySide6 对 3.14 可能尚无 wheel(代差风险);requirements 建议 Python **3.11–3.13** |
| 本机**无 pip / ensurepip / uv / conda** | 本机**无法安装 PySide6** |
| 本机 **headless**(无 DISPLAY/Wayland) | 即便装上也**无法显示窗口** |

**结论**:M1 在本机只产出**代码 + 结构 + 语法检查(py_compile)**;一切运行验证(import / offscreen 冒烟 / 单测 / 托盘 / 热键 / 外观)在 **Windows 10** 完成。
**交付物定位**:一份「在 Windows 上 `pip install -r requirements.txt && python run.py` 即可运行」的完整 M1 代码 + Windows 验证清单。

## 1. 目录结构(方案 A,融合双模型裁决)

```
snipaste-ocr/
├── run.py                      # 便捷启动:python run.py → src.main:main()
├── requirements.txt            # PySide6(标注建议 Python 3.11-3.13)
├── README.md                   # 运行/打包说明 + Windows 验证清单
└── src/
    ├── __init__.py
    ├── main.py                 # 入口:High DPI 设置→QApplication→单实例→装配托盘/上下文
    ├── app_context.py          # 业务协调器(Presenter):UI 信号 ↔ core 服务
    ├── config/
    │   ├── paths.py            # 数据/日志/配置路径(便携模式 + _MEIPASS 兼容)
    │   └── settings.py         # ConfigManager:JSON 读写 + schema + 默认值 + 迁移
    ├── core/
    │   ├── logger.py           # 日志(文件 + 控制台)
    │   ├── single_instance.py  # QLocalServer/Socket 单实例 + 唤醒
    │   ├── startup.py          # Windows 开机自启(winreg);非 Win 优雅降级
    │   └── hotkey/
    │       ├── base.py         # HotkeyManager 门面 + Signal + 平台分发
    │       ├── win32.py        # ctypes RegisterHotKey + QAbstractNativeEventFilter
    │       └── linux.py        # Mock 降级(打日志,不崩)
    ├── ui/
    │   ├── theme/
    │   │   ├── tokens.py       # design token 字典(主色/圆角/阴影)
    │   │   ├── theme.qss       # QSS 模板(@占位符)
    │   │   └── theme_manager.py# 加载 qss + 占位符替换 + app.setStyleSheet
    │   ├── components/
    │   │   ├── title_bar.py    # 无边框标题栏(拖拽 + 关闭)
    │   │   ├── shadow_widget.py# 阴影容器(外补齐 + QGraphicsDropShadowEffect)
    │   │   └── hotkey_edit.py  # HotkeyLineEdit 录制控件(重写 keyPressEvent)
    │   ├── tray/
    │   │   ├── tray_icon.py    # QSystemTrayIcon + QMenu(对照 mockup ④)
    │   │   └── icon_factory.py # QPainter 自绘占位图标
    │   └── settings/
    │       ├── settings_dialog.py # 设置窗(QDialog + QListWidget 导航 + QStackedWidget)
    │       └── pages.py        # 各子页(常规/热键/截屏/贴图/输出/OCR/关于)
    └── assets/icons/           # 图标占位(SVG/png 后补)
└── tests/
    ├── test_config.py          # 配置默认值/读写/迁移(纯逻辑)
    └── test_hotkey_parse.py    # 热键字符串解析 + Linux 降级不崩
```
(各包补 `__init__.py`)

## 2. 分层实施(文件归属互不重叠 → 可并行)

| Layer | 内容 | 依赖 |
|-------|------|------|
| **L0 基础设施** | `core/logger.py`, `config/paths.py`, `ui/theme/tokens.py` | 无 |
| **L1 核心服务** | `config/settings.py`, `core/single_instance.py`, `core/startup.py`, `core/hotkey/{base,win32,linux}.py` | L0 |
| **L2 UI 基础** | `ui/theme/{theme.qss,theme_manager.py}`, `ui/components/{title_bar,shadow_widget,hotkey_edit}.py`, `ui/tray/{icon_factory,tray_icon}.py` | L0/L1 |
| **L3 页面+装配** | `ui/settings/{settings_dialog,pages}.py`, `app_context.py`, `main.py`, `run.py` | L0/L1/L2 |
| **L4 工程化** | `requirements.txt`, `tests/*`, `README.md` | 全部 |

## 3. 架构决策(摘要,详见 analysis.md)
热键 ctypes+Linux Mock · 自管 JSON 配置 · QLocalServer 单实例 · QDialog 无边框设置窗 · 信号驱动 UI/Core 解耦 · QSS token 占位符 · QRC+_MEIPASS 资源 · High DPI + SVG。

## 4. 测试与验证策略
- **本机(Linux)**:`python -m py_compile` 全量语法检查 + 代码结构审查(无法 import PySide6,故不能跑单测)。
- **Windows 10**(用户侧,验收主场):
  1. `py -3.12 -m venv .venv` → `pip install -r requirements.txt`
  2. `python run.py`:托盘出现 → 设置窗打开 → 热键页改键存盘 → 重启保留 → F1/F3/F4 触发占位日志
  3. `pytest tests/`:配置读写、热键解析、降级
- README 附**逐条 Windows 验证清单**(对照 requirements.md 验收标准)。

## 5. 风险与缓解
| # | 风险 | 缓解 |
|---|------|------|
| R1 | 本机不可运行,代码无法即时验证 | 代码靠审查 + py_compile;Windows 实测;每文件含可独立读懂的注释 |
| R2 | PySide6 对 Python 3.14 无 wheel | requirements.txt 标注建议 3.11–3.13;README 指导 Windows 用 3.12 |
| R3 | ctypes Win32 热键 API 细节(WM_HOTKEY=0x0312、nativeEventFilter 返回值签名) | 严格按 PySide6 6.x;Win32 与 Linux 分文件,Linux 纯降级 |
| R4 | PyInstaller 单 exe 资源寻址 | QRC 嵌入 + `_MEIPASS` 路径 helper,M1 先就位 |

## 6. 工作量
约 35 个文件(含 `__init__.py`/占位),核心逻辑文件约 14 个。
