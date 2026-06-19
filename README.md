# 截图精灵 / SnapOCR

Windows 10 桌面**截图 / 贴图 / 标注 + 本地离线 OCR** 工具,全中文界面,基于 PySide6 实现,最终以 PyInstaller 打包为单个 `.exe`。

> **当前进度:M1 项目骨架** —— 系统托盘常驻 + 全局热键框架 + 设置窗。
> 截图选区/标注(M2)、贴图浮窗(M3)、OCR(M4)、打包(M5)为后续里程碑。

## 技术栈

| 部分 | 选用 |
|------|------|
| 界面 | PySide6 (Qt6) |
| 全局热键 | Windows: `ctypes` 直调 Win32 `RegisterHotKey`;非 Windows:自动降级(仅记录,不崩) |
| 配置持久化 | 自管 JSON(`%APPDATA%/SnapOCR/config.json`) |
| 单实例 | QLocalServer / QLocalSocket(可唤醒已有实例) |
| 打包(M5) | PyInstaller 单 exe |

## 运行(Windows 10)

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

> ⚠️ PySide6 不一定支持最新的 Python 3.14,建议使用 **Python 3.11–3.13**(本项目用 3.12 验证)。

## M1 验证清单(在 Windows 上逐条核对)

- [ ] 启动后系统托盘出现「S」图标,并弹出"已在后台运行"气泡
- [ ] 右键托盘 → 菜单项齐全:截屏 / 贴图 / 从剪贴板贴图 / 文字识别 / 最近文件 | 设置 / 开机启动 | 帮助 / 关于 | 退出
- [ ] 点「截屏 / 贴图 / 文字识别」→ 弹占位提示气泡 + 写日志(M1 为占位逻辑)
- [ ] 双击托盘图标 → 触发"截屏"占位
- [ ] 打开「设置」→ 默认停在「热键」页(对照 mockup ④)
- [ ] 热键页点「修改」→ 按下组合键(如 `Ctrl+Alt+A`)→ 输入框显示新键;Esc 取消、Backspace 清空
- [ ] 点「确定」→ 重新打开设置,新热键保留(配置已落盘 `%APPDATA%/SnapOCR/config.json`)
- [ ] 勾选「开机启动」→ 注册表 `HKCU\...\Run` 出现 `SnapOCR`(regedit 核对)
- [ ] 再次运行 `python run.py` → 不产生第二个实例,而是唤醒已有实例
- [ ] 点「退出」→ 程序结束,托盘图标消失

## 测试

```bat
pip install pytest
pytest tests/
```

- `test_config.py`:配置默认值/合并/回退/往返/重置 —— 任意平台可跑
- `test_hotkey_parse.py`:降级后端任意平台可跑;Win32 解析用例仅 Windows 执行

## 目录结构

```
run.py                  便捷启动入口
requirements.txt
src/
  main.py               入口:High DPI → QApplication → 单实例 → 装配
  app_context.py        业务协调器(UI 信号 ↔ core 服务)
  config/               路径管理 + JSON 配置
  core/                 日志、单实例、开机自启、跨平台全局热键(零 GUI 依赖)
  ui/                   theme(token+QSS) / components / tray / settings
tests/                  单元测试
```

## 开发说明(Linux / headless)

- 开发机为 Linux 且无显示环境时,无法显示真实窗口。可用 offscreen 平台做导入/启动冒烟:
  ```bash
  QT_QPA_PLATFORM=offscreen python run.py
  ```
- `core` 层除热键门面借用 Qt 信号外,不依赖任何窗口控件,可独立单测。
- 视觉规范(主色 `#2D7FF9`、圆角、阴影、字体)集中在 `src/ui/theme/tokens.py`,改样式只改这一处。
- 真实的托盘行为、全局热键、窗口外观需在 **Windows 实测**。
