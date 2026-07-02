# SnapOCR 截图精灵

**Windows 截图 + 贴图 + 标注 + OCR 工具**，全中文界面，本地离线识别，无需联网。

![](https://img.shields.io/badge/platform-Windows%2010%2B-blue) ![](https://img.shields.io/badge/Python-3.11%7C3.12%7C3.13-green) ![](https://img.shields.io/badge/license-MIT-brightgreen)

---

## ✨ 功能特性

### 📸 截图标注
- **全屏截图**：F1 快捷键，支持多显示器
- **实时标注**：矩形、椭圆、箭头、直线、画笔、马克笔、马赛克、文字、序号
- **属性调整**：粗细（细/中/粗）+ 8 色调色板
- **取色器**：屏幕取色 + 自动复制 HEX 值
- **撤销重做**：Ctrl+Z / Ctrl+Y

### 📌 贴图
- **桌面贴图**：F3 快捷键，将图片钉在桌面
- **置顶浮窗**：始终显示在最前端
- **自由缩放**：滚轮缩放，双击恢复 100%
- **旋转调整**：向左/向右 90° 旋转
- **透明度**：100% / 80% / 60% / 40% / 20% 五档
- **批量管理**：Shift+F3 一键显隐所有贴图

### 🔤 文字识别（OCR）
- **本地离线**：基于 RapidOCR，无需联网
- **多语言支持**：中文（简/繁）、英语
- **识别模式**：
  - 截图后点击「文字识别」按钮
  - 贴图右键菜单「文字识别 (OCR)」
- **结果展示**：可折叠面板，支持一键复制

---

## 📥 下载安装

### 方式一：下载 exe 版本（推荐）

1. 前往 [Releases](https://github.com/koui99/snapocr/releases) 页面
2. 下载最新版本的 `SnapOCR-vX.X.X.zip`
3. 解压到任意目录（如 `C:\SnapOCR\`）
4. 运行 `SnapOCR.exe` 即可使用

> **注意**：首次运行可能被 Windows Defender 拦截，点击「更多信息」→「仍要运行」即可。

### 方式二：从源码运行

**环境要求**：
- Windows 10 / 11
- Python 3.11 / 3.12 / 3.13

**安装步骤**：
```bat
# 1. 克隆仓库
git clone https://github.com/koui99/snapocr.git
cd snapocr

# 2. 创建虚拟环境
py -3.12 -m venv .venv
.venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行
python run.py
```

---

## 🎮 使用指南

### 启动与托盘

运行后，程序常驻系统托盘（右下角 **SnapOCR** 图标），右键托盘菜单：

- **截屏**：启动截图
- **贴图**：从剪贴板贴图
- **设置**：热键配置、保存路径、开机启动
- **退出**：关闭程序

### 截图流程

1. **按 F1** 或托盘「截屏」→ 全屏变暗
2. **拖拽选区**：鼠标拖拽矩形，8 个控制点调整大小
3. **标注工具**：上方工具栏选择矩形/箭头/画笔/文字等
4. **完成操作**：
   - **复制**：✓ 按钮 / 双击选区 / Enter / Ctrl+C
   - **保存**：💾 按钮 / Ctrl+S
   - **钉图**：📌 按钮
   - **识别**：🔤 按钮（OCR）
   - **取消**：Esc / 右键

### 贴图操作

- **创建贴图**：截图后点「钉图」，或 F3 从剪贴板贴图
- **移动**：鼠标拖拽
- **缩放**：滚轮上下 / 双击恢复 100%
- **右键菜单**：
  - 复制 (Ctrl+C)
  - 保存图片 (Ctrl+S)
  - 文字识别 (OCR)
  - 缩放（放大/缩小/恢复 100%）
  - 不透明度（100% ~ 20%）
  - 旋转（向左/向右 90°）
  - 置顶（可切换）
  - 取消贴图 (Esc)
- **全局热键**：Shift+F3 显隐所有贴图

### OCR 文字识别

#### 从截图识别
1. 按 F1 截图
2. 选中文字区域
3. 点击工具栏「🔤 文字识别」按钮
4. 下方面板显示识别结果
5. 点击「复制」按钮复制文字

#### 从贴图识别
1. 贴图右键菜单 →「文字识别 (OCR)」
2. 下方面板显示结果

#### 切换语言
- 打开「设置」→「OCR」页
- 选择识别语言：中英混合 / 仅英文

---

## ⚙️ 设置说明

打开「设置」窗口（托盘右键 →「设置」）：

### 热键页
- **截屏**：默认 F1
- **贴图**：默认 F3（从剪贴板）
- **显隐贴图**：默认 Shift+F3
- 点击「修改」→ 按下新组合键（如 Ctrl+Alt+A）→「确定」

### 保存页
- **保存路径**：默认 `%APPDATA%\SnapOCR\screenshots\`
- **文件格式**：PNG / JPG / BMP
- **文件名模板**：支持时间戳变量 `{timestamp}`

### OCR 页
- **识别语言**：选择默认语言
- **识别引擎**：RapidOCR（离线）

### 通用页
- **开机启动**：勾选后自动注册到注册表
- **主题**：浅色 / 深色（开发中）

---

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| 界面框架 | PySide6 (Qt6) |
| 截图引擎 | MSS (Multi-Screen Screenshot) |
| OCR 引擎 | RapidOCR (ONNX Runtime) |
| 全局热键 | Windows `RegisterHotKey` API |
| 打包工具 | PyInstaller |

---

## 📋 常见问题

**Q: 为什么 exe 文件这么大（100+ MB）？**  
A: 包含了完整的 Python 运行时 + PySide6 GUI 库 + ONNX Runtime + OCR 模型，保证离线可用。打包配置已做过瘦身（剔除未用的 Qt 模块、视频编解码器、非中文翻译等，压缩包约减少 30%），剩余体积主要来自 OpenCV 与 ONNX 推理引擎，是本地离线 OCR 的必要成本。

**Q: 杀毒软件报毒？**  
A: PyInstaller 打包的 exe 可能被误报，属于正常现象。可查看源码自行打包，或添加信任白名单。

**Q: 更新后文件管理器里还是旧图标？**  
A: Windows 可能缓存 exe 图标。请先确认重新打包后的 `dist\SnapOCR\SnapOCR.exe`，必要时重启资源管理器或清理 Windows 图标缓存。

**Q: 多显示器支持？**  
A: 支持。截图时每个屏幕独立遮罩，标注在任意屏操作均可。

**Q: 支持 macOS / Linux 吗？**  
A: 目前仅支持 Windows 10/11。跨平台版本计划中。

**Q: OCR 识别不准确？**  
A: 
- 确保文字区域清晰、对比度高
- 切换到对应语言（中文/英语）
- 避免倾斜、模糊、过小的文字

---

## 📜 开源协议

MIT License © 2024

---

## 🤝 反馈与贡献

- **问题反馈**：[提交 Issue](https://github.com/koui99/snapocr/issues)
- **功能建议**：欢迎在 Issue 中讨论
- **代码贡献**：欢迎 Pull Request

---

## 🙏 致谢

- [RapidOCR](https://github.com/RapidAI/RapidOCR) - 高性能离线 OCR 引擎
- [PySide6](https://wiki.qt.io/Qt_for_Python) - Qt6 Python 绑定
- [MSS](https://github.com/BoboTiG/python-mss) - 跨平台截图库
