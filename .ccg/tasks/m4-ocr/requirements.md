# M4 OCR 文字识别 — 需求规格

> 任务: m4-ocr · 策略: full-collaborate · Phase 1 研究与分析产物
> 对照 design/BRIEF.md 界面③、design/mockup.html(L581–622 OCR 结果窗)、design/PLAN.md 里程碑 M4。

## 目标
把「截图选区 / 贴图 / 剪贴板图片」交给**本地离线 RapidOCR(ONNX)**识别出文字,弹出
**OCR 结果窗(界面③)**:左原图缩略 + 右可编辑文本框,顶部语言下拉 + 重新识别,
底部复制全部 / 保存 txt / (翻译占位) + 耗时·置信度状态栏。替换 M1/M2/M3 中所有 OCR 占位逻辑。

## 范围(本轮 M4)

**IN(本轮交付):**
- **OCR 引擎封装 `core/ocr/engine.py`**:
  - 懒加载 RapidOCR(首次识别才初始化模型,避免启动卡顿);线程安全单例。
  - `recognize(image_bytes) -> OcrResult`:返回 `OcrResult(text, lines, avg_confidence, elapsed_ms, ok, error)`。
  - rapidocr 未安装 / 模型缺失 / 识别异常 → 返回 `ok=False` + 中文错误说明,**不崩**。
  - 引擎模块**不在顶层 import PySide6**(纯逻辑可单测);QImage→bytes 转换放在 UI/控制层。
- **后台识别 `ui/ocr/worker.py`**:QThread 包装,识别在子线程跑,完成经信号回主线程,UI 不冻结。
- **结果窗 `ui/ocr/result_window.py`(还原 mockup 界面③)**:
  - 标准窗口(标题「文字识别结果」+ 最小化/最大化/关闭)。
  - 顶部:识别语言下拉(简体中文+英文 / 仅英文 / 仅中文)、「重新识别」按钮。
  - 中部:左原图缩略(等比缩放),右**可编辑**文本框(填识别结果)。
  - 底部:状态栏(`识别耗时 0.8s · 置信度 96%`)+ 复制全部 / 保存 txt / 翻译(**占位,次要按钮**)。
  - 识别中显示「识别中…」态,失败显示错误文案。
- **OCR 控制器 `ui/ocr/ocr_controller.py`**:统一入口 `run_ocr(image)` —— QImage→bytes、起 worker、建/复用结果窗、回填文本与状态;管理结果窗生命周期。
- **接线**:
  - 截图工具栏「识别」→ `sig_result(image,"ocr")` → app_context 调 `ocr.run_ocr(image)`(替换占位)。
  - 贴图右键「文字识别」→ `PinWindow` 发信号 → app_context → `ocr.run_ocr`(替换 `_ocr_placeholder`)。
  - F4 / 托盘「文字识别」→ 有剪贴板图则直接识别,否则发起截图(选区后点识别)。
- **配置**:`config` 增 `ocr` 段(默认语言、是否自动复制结果);设置窗「文字识别(OCR)」页从占位升级为真实页(语言默认值 + 自动复制开关 + 模型说明)。
- **保存 txt**:写 UTF-8 文本文件(复用 config.screenshot.save_dir 或用户数据目录),返回路径。
- **纯逻辑单测 `tests/test_ocr.py`**:置信度求平均、行文本拼接、语言参数映射、耗时格式化、空结果处理(均不依赖模型/Qt)。

**OUT(后续里程碑 / 本轮占位):**
- **翻译**:按钮留位,点击提示「未接入」(PLAN 明确:在线翻译需单独商量)。
- 多模型/语言包热切换:当前内置中英混合模型,语言下拉传参但实际同一模型(英文本就支持);如实说明,不假装切模型。
- PyInstaller 打包内置模型 → M5。

## 约束
- 框架 **PySide6 (Qt6)**;OCR 引擎 **rapidocr-onnxruntime**(本地离线 ONNX,MIT)。
- 复用既有设施:`app_context` 协调器、`config.settings`、`theme/tokens`、`components/{title_bar,shadow_widget}`、`core/logger`;保存复用 paths/数据目录。
- 目标平台 **Windows 10**;开发机 **Linux + Python 3.14 + headless + 无 pip** → 本机仅 `py_compile` + 纯逻辑单测 + agy 审查;**真实识别 / 模型加载 / 准确率 / 结果窗外观必须 Windows 实测**(README 附 M4 清单)。
- **全中文 UI**(窗口/按钮/状态文案 + 注释中文)。
- 完全离线;模型**内置随包**(PLAN 定;M5 PyInstaller 带上模型目录)。
- 防御性:rapidocr 缺失 / 模型缺失 / 空图 / 识别 0 结果 → 不崩,给中文提示。
- 引擎与 UI 解耦:engine.py 不依赖 PySide6;rapidocr 仅在 recognize 内 import(延迟,缺失可降级)。

## 验收标准
1. 截图选区 → 点工具栏「识别」→ 弹出结果窗,文本框出现识别文字,状态栏显示耗时+置信度。
2. 贴图右键「文字识别」→ 对当前贴图识别并弹结果窗。
3. F4 / 托盘「文字识别」→ 剪贴板有图直接识别;无图则发起截图。
4. 结果窗:语言下拉可选、「重新识别」可重跑、文本框可编辑、左侧原图缩略正确。
5. 复制全部 → 文本进剪贴板;保存 txt → 按配置写 UTF-8 文件并提示路径。
6. 翻译按钮存在可点(占位提示,不报错)。
7. rapidocr 未安装时点识别 → 结果窗/提示给出「OCR 组件未安装」的中文说明,程序不崩。
8. 识别过程 UI 不冻结(后台线程);识别中有「识别中…」反馈。
9. 设置窗「文字识别(OCR)」页可设默认语言 + 自动复制,保存后生效。
10. 代码结构清晰、引擎与 UI 解耦、关键路径有日志;纯逻辑单测通过。

## 跨平台现实
真实 OCR 依赖 rapidocr-onnxruntime + onnxruntime + 模型文件,本机(headless/无 pip/3.14)装不了跑不了。
M4 在 Linux 侧验证「py_compile + 纯逻辑单测(置信度/拼接/语言映射/格式化)+ agy 审查」;
真实识别 / 模型加载 / 准确率 / 结果窗外观 / 线程不冻结留待 **Windows 10 实测**(README 附 M4 逐条清单)。

## 需求完整性评分
| 维度 | 满分 | 得分 | 依据 |
|------|------|------|------|
| 目标明确性 | 3 | 3 | M4 目标在 PLAN 里程碑 + BRIEF 界面③ + mockup 明确 |
| 预期结果 | 3 | 3 | 验收标准对应 mockup 每个控件;IN/OUT 清晰 |
| 边界范围 | 2 | 2 | 翻译占位、模型不热切换如实说明、打包归 M5 |
| 约束条件 | 2 | 2 | 技术栈 / 平台 / 离线 / 解耦 / 降级均已定 |
| **总分** | **10** | **10** | **≥7 → 通过,进入实现** |
