# M1 项目骨架 — 审查报告(Phase 5 · Round 1)

## 审查方式
- **agy 双模型交叉**(均 Gemini 3.5 Flash High):正确性/PySide6 API + UI 还原/QSS
- **CCG 关卡**:verify-security、verify-quality

## 关卡结果
| 关卡 | 结果 |
|------|------|
| verify-security | ✓ 0 问题(29 文件) |
| verify-quality | ✓ 0 错 0 警(修复后);6 个"命名"Info 为 Qt 重写方法(keyPressEvent 等),框架强制驼峰,误报保留 |
| py_compile | ✓ 33 文件全过 |

## 审查发现与处置

### Critical(9,全部修复)
1. **全局热键 eventType 漏 `windows_dispatcher_MSG`**(真功能 bug:RegisterHotKey(NULL) 的 WM_HOTKEY 走线程消息)→ 已修 `win32.py`
2–9. **PySide6 枚举 scoped 化**:`QSystemTrayIcon.ActivationReason.DoubleClick`、`QPainter.RenderHint.Antialiasing`、`Qt.MouseButton.LeftButton`、`Qt.AlignmentFlag.AlignCenter`、`Qt.WindowType.*`、`Qt.WidgetAttribute.WA_*`、`Qt.Key.Key_*`、`Qt.GlobalColor.transparent`、`Qt.PenStyle.NoPen`、`Qt.CursorShape.PointingHandCursor` → 全部改 scoped
   > 说明:这些在 PySide6 实际多半仍可用(审查员套用了更严格的 PyQt6 规则),但本机无法运行验证,改 scoped 是最稳、面向未来、消除版本差异的写法。

### Warning(全部修复)
- **ctypes 未声明 argtypes/restype**(64 位 HWND 指针截断风险)→ 已声明 `win32.py`
- **import 期 `mkdir` 副作用**(只读环境会在 import 阶段崩)→ `paths.py` 改纯路径计算 + `ensure_parent()` 延迟创建,`logger.py`/`settings.py` 写入前建目录
- **单实例竞态**(probe 与 start_server 间窗口过大)→ `main.py` 把 `start_server()` 提前到耗时初始化之前
- **footer 背景丢失**(Layout 无法上背景)→ 改用 `#settingsFooter` QWidget 容器 + QSS
- **恢复默认丢页面记忆** → `current_page()` 保存并恢复当前页

### Info(已修)
- 配置深拷贝传入设置窗(防"取消"前污染)、`focusOutEvent` 冗余 `clearFocus` 加 `hasFocus` 判断、最近文件用 basename+tooltip 防长路径撑宽、`BasePage` 启用 `WA_StyledBackground`

### 已知保留(低优先,留待 Windows 实测)
- `QListWidget::item` 选中右边框可能轻微晃动(Qt 支持该属性,属视觉细节)
- 单键热键合法性校验(默认热键均为功能键,当前无影响)

## 结论
**Critical 全部清零,质量/安全关卡通过。** 代码达到 M1 可交付质量;真实运行/托盘/热键/外观验证待 Windows 实测(README 附清单)。
