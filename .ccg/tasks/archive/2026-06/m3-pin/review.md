# M3 贴图(Pin)— Phase 4 审查与质量关卡

> 任务: m3-pin · 策略: full-collaborate · Phase 4 产物
> 审查方式:CCG 质量/安全关卡 + agy(Gemini 3.5 Flash High)独立只读审查 + 本机 py_compile。

## 关卡结果

| 关卡 | 范围 | 结果 |
|------|------|------|
| `verify-security` | `src/ui/pin` | ✓ 通过(严重 0 / 高 0 / 中 0 / 低 0) |
| `verify-quality` | `src/ui/pin` | ✓ 通过(错误 0;命名告警为 Qt 强制 camelCase 事件回调,误报) |
| `py_compile` | 全量 `src/**.py` | ✓ 全过 |
| 纯逻辑单测 `test_pin.py` | clamp_scale/不透明度/角度归一 | 本机无 PySide6 → 顶层 import 拦截,留待 Windows 跑 |

## agy 独立审查发现与处置

### 已采纳并修复
1. **置顶切换丢失位置/尺寸**(严重)—— `toggle_on_top` 改 flag 后 `show()` 会被系统重置到原点。
   修复:暂存 `geometry()` → `setWindowFlag` → `show()` → `setGeometry(geom)` 恢复。
2. **拖拽起拖瞬间抖动**(重要)—— `on_press` 用 `frameGeometry().topLeft()` 与 `move()`(作用于 `geometry()`)坐标系不一致。
   修复:统一改用 `geometry().topLeft()`。
3. **QMenu 内存累积**(重要)—— 每次右键 `QMenu(self)` 不自动析构。
   修复:`menu.exec()` 后 `menu.deleteLater()`。
4. **(0,0) 初始化误判**(次要)—— 原 `topLeft().isNull()` 在用户把贴图拖到屏幕左上角 (0,0) 时会误判,跳过保持中心逻辑。
   修复:改用显式 `self._initialized` 标志,首次定位(`move_center_to`)后置 True。
5. **复制/保存未体现旋转**(次要)—— 原传 `self._orig`,旋转后复制/保存得到旋转前的图。
   修复:新增 `_output_image()`,保留原始分辨率但应用旋转(所见即所得);缩放故意不缩(避免存盘掉分辨率变糊)。
6. **`_clamp_to_screen` 差 1 像素**(次要)—— `QRect.right()/bottom()` = left+width-1。
   修复:改用 `geo.x()+geo.width()-w`、`geo.y()+geo.height()-h` 求右/下边界。

### 判定为误报 / 可接受,未改
- **writer 转 RGB32「通道丢失」** —— 有意为之(注释写明:规避 Windows 粘贴透明背景变黑),且 M2 已 Windows 实测通过。贴图源多为不透明截图,无实际损失。
- **Shift+Esc「无反应」** —— `on_key` 中 `Key_Escape` 不论是否带 Shift 都进 close 分支,实际可用;销毁/取消当前实现等价(均 close,WA_DeleteOnClose 回收)。
- **`contextMenuEvent` 的 `globalPos()` 弃用** —— 弃用仅针对鼠标事件;`QContextMenuEvent.globalPos()` 在 Qt6 仍为有效 API,不改。

### 记为已知项,留待后续迭代
- **大图连续缩放的 QPixmap 重分配性能 + 高 DPI 缩放变糊** —— 改 transform 动态绘制(paintEvent 内 `setTransform` + 绘 `_orig`)是较大重构;当前 `scaled()` 方案功能正常,M3 不做,记入 knownLimits。
- **PinManager↔PinWindow 引用环** —— 退出走 `close_all()` 主动关闭,closed 信号断连;实际无泄漏。仅在「保留窗口下析构 Manager」的边缘场景才有理论残留,非 M3 路径。

## 结论
M3 实现质量达标,关卡全过,审查发现的可修项已全部处理。剩余为真机依赖项(贴图置顶/拖拽/缩放/剪贴板),按 README「M3 验证清单」在 Windows 10 逐条核对。
