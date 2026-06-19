# M1 项目骨架 — 多模型分析综合(Phase 2)

> 双模型并行分析(均 Gemini 3.5 Flash High via Antigravity):**架构视角** + **UI 还原视角**。
> 本文综合两份输出并加入 Claude 的编排裁决与本机环境实测,作为 Phase 3 规划的输入。

## 一、核心技术结论(两份分析一致)

| # | 决策点 | 结论 | 理由 |
|---|--------|------|------|
| 1 | 全局热键 | **Windows: ctypes 直调 Win32 `RegisterHotKey`**;Linux: Mock 降级(只打日志) | 零外部依赖、打包最可靠;否决 `keyboard`(需 root + 与 PySide6 在 Linux 下 X11 冲突) |
| 2 | 配置持久化 | **自管 JSON**(`%APPDATA%/SnapOCR` 或便携目录) | 绿色便携、跨平台调试友好;否决 `QSettings`(写注册表不便携) |
| 3 | 单实例 | **QLocalServer / QLocalSocket**(可唤醒旧实例) | 否决 `QSharedMemory`(进程被杀残留锁段,导致再也打不开) |
| 4 | 设置窗 | **QDialog + Frameless + 圆角阴影**;左 `QListWidget` 导航 + 右 `QStackedWidget` | 设置窗是辅助窗,不需要 QMainWindow 的菜单/状态栏 |
| 5 | 阴影 | **QGraphicsDropShadowEffect + 外补齐法**(透明背景 + 16px 边距) | QSS 不支持 CSS box-shadow |
| 6 | Design token → QSS | **Python 字典存 token + 占位符正则替换** | 原生 QSS 无 `var()` 变量,硬编码难维护 |
| 7 | UI/Core 解耦 | **信号驱动(MVP)**,`app_context` 作为协调器(Presenter) | core 层零 GUI 依赖,可脱离界面单测 |
| 8 | 高分屏 | **SVG 图标 + 布局管理器**(禁 `setGeometry` 绝对坐标);main.py 顶部设 High DPI | 适配 Win10 125%/150% 缩放 |
| 9 | 打包资源 | **QRC 嵌入**(`:/icons/...`)+ `_MEIPASS` 路径辅助函数 | 防 PyInstaller 单 exe 解压后 `FileNotFoundError` |
| 10 | 托盘图标 | **QPainter 内存自绘占位**(加载失败时回退) | 无设计图标 / Linux 下不因图标缺失崩溃 |

## 二、架构方案对比(架构分析产出)

| 维度 | 方案 A:轻量解耦 + ctypes + JSON(推荐) | 方案 B:富层级 + pyqtkeybind + QSettings |
|------|------|------|
| 热键 | ctypes Win32 + Linux Mock,零依赖 | pyqtkeybind/QHotkey,C++ 扩展,打包易丢 dll |
| Linux 开发 | 静默降级,100% 不崩 | 无 X11/Wayland 下初始化即崩 |
| 配置 | 自管 JSON,便携 | QSettings,注册表不便携 |
| 单实例 | QLocalServer,可唤醒 | QSharedMemory,易残留锁 |
| 解耦 | 扁平 App→UI→Core→Config | EventBus/ServiceLocator,过重 |

**采用方案 A。**

## 三、两份分析的分歧 → 统一裁决

| 分歧点 | 架构版 | UI 版 | 统一采用(Claude 裁决) |
|--------|--------|-------|------------------------|
| 入口位置 | 根 `main.py` + `src/app.py` | `src/main.py` | `src/main.py` 为入口 + 根 `run.py` 便捷启动 |
| Linux 降级文件名 | `hotkey/mock.py` | `hotkey/linux.py` | **`hotkey/linux.py`**(语义清晰) |
| 协调器 | `app.py`(QApplication 子类) | `app_context.py`(Presenter) | 拆分:`main.py` 管启动/生命周期,`app_context.py` 管业务协调 |
| 主题目录 | `ui/common/style.py` | `ui/theme/{tokens,theme.qss,theme_manager}` | 采用 **`ui/theme/`** 三件套(更清晰) |

## 四、本机环境现实约束(Claude 实测补充)

- **Python 3.14.4**(很新),**PySide6 及相关库均未安装** → 见 plan.md 风险:需先验证 PySide6 在 3.14 是否有 wheel。
- **本机 headless**:`DISPLAY` / `WAYLAND_DISPLAY` 均为空 → Qt **无法显示真实窗口**。Linux 侧验证须用 `QT_QPA_PLATFORM=offscreen`(看不到界面,只验证"导入不报错 / 启动不崩 / 配置读写 / 逻辑单测")。
- **真实托盘 / 全局热键 / 窗口外观** → 必须在 **Windows 实测**(M1 收尾或 M5 打包后)。
- 因此 M1 在 Linux 的"可见进展"有限,**验收标准对应调整**:以 offscreen 冒烟 + 单元测试 + 代码结构为准,真实交互留待 Windows。
