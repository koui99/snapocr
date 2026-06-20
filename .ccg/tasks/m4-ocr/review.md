# M4 OCR — Phase 4 审查与质量关卡

> 任务: m4-ocr · 策略: full-collaborate · Phase 4 产物
> 审查:CCG 质量/安全关卡 + agy(Gemini 3.5 Flash High)独立只读审查 + 本机 py_compile + 纯逻辑单测。

## 关卡结果

| 关卡 | 范围 | 结果 |
|------|------|------|
| `verify-security` | `src/core/ocr` + `src/ui/ocr` | ✓ 通过(严重/高/中/低 全 0) |
| `verify-quality` | `src/core/ocr` + `src/ui/ocr` | ✓ 通过(错误 0、警告 0;recognize 圈复杂度由 15 降到达标) |
| `py_compile` | 全量 `src/**.py` + `tests/**.py` | ✓ 全过 |
| 纯逻辑单测 `tests/test_ocr.py` | 置信度/拼接/格式化/语言映射/空结果 + 降级 | ✓ 10/10(本机经 pytest 桩跑过) |
| 引擎降级 | rapidocr 缺失 / 空字节 | ✓ 返回 ok=False + 中文说明,不崩 |

## agy 独立审查发现与处置(全部采纳)

### 严重
1. **关闭窗口时销毁运行中的 QThread → 闪退**(result_window)。原 worker 挂 `parent=self` + `closeEvent` 里 `wait(3000)` 阻塞:超时未完则销毁运行中的 QThread,Qt 抛 `QThread: Destroyed while thread is still running` 进程崩溃;且跑完回调已销毁控件抛 `RuntimeError`。
   **修复**:worker 不挂 parent;用类级 `_running_workers` 集合持有防 GC;`finished→deleteLater`+移除;`closeEvent` 不再阻塞 wait,改为 `disconnect(sig_done)` 切断回调。

### 重要
2. **推理并发无锁**(engine)。多窗口/快速重识别并发调用同一 RapidOCR 单例 → 数据污染或 ONNX C++ 段错误。**修复**:`recognize` 的推理调用包进类锁 `_lock` 串行化(单机低频瞬发,无感知开销)。
3. **VC++ 缺失误诊**(engine)。纯净 Windows 缺 VC++ 运行库时 `import rapidocr` 抛 `ImportError: DLL load failed`,原逻辑一律报「组件未安装」误导用户。**修复**:`ImportError` 按 `DLL load failed`/`找不到指定的` 特征分流,提示装 VC++ 运行库。
4. **重新识别 worker 内存泄漏**(result_window)。旧 worker 挂 parent 不释放,点 N 次累积 N-1 个僵尸对象。**修复**:同 #1 的 `finished→deleteLater`。

### 次要
5. **destroyed 信号悬空**(app_context)。原 `win.destroyed.connect(lambda: forget(win))` 在 C++ 析构期捕获 win 易抛 RuntimeError。**修复**:OcrResultWindow 仿 PinWindow 加 `closed = Signal(object)`,closeEvent 主动发射,app_context 连 `closed`。
6. **语言下拉无联动**(result_window)。**修复**:`currentIndexChanged → _start_recognize`,切语言即重识别。
7. **大图缩略主线程卡顿**(result_window)。**修复**:先在 CPU 侧 `QImage.scaled` 再转 QPixmap,避免整张 4K 上传 GPU。

### 部署踩坑(采纳)
- **ONNX 铺满 CPU 核心**:main 入口加 `OMP_NUM_THREADS=2`/`MKL_NUM_THREADS=2`(QApplication 前),避免识别时风扇暴转 + UI 卡。
- **PyInstaller 选型**(记入 M5):建议 `--onedir` + Inno/NSIS 而非 `--onefile`(后者每次解压 150MB+ 到 TEMP,启动慢 3-5s 且易被 Defender 误报)。模型走 `sys._MEIPASS`(engine 已预留 `_resource_base`)。

## 与需求差异说明
- 需求里写的 `ui/ocr/ocr_controller.py` 独立控制器,实现时合并进了 **app_context.open_ocr**(更简单、与 M2/M3 路由风格一致,职责单一)。worker + result_window 已覆盖控制逻辑,无需额外一层。
- 语言下拉「仅英文」:内置中英混合模型本就识别英文;仅当 `models/en_PP-OCRv3_rec_infer.onnx` 存在时才真正切纯英文模型,否则降级混合并打日志——**不假装切换**(如实)。

## 结论
M4 实现质量达标,关卡全过,agy 审查全部采纳并修复(尤其闪退级缺陷)。剩余为真机依赖项(真实识别/模型加载/准确率/线程不冻结/结果窗外观),按 README「M4 验证清单」在 Windows 10 逐条核对。
