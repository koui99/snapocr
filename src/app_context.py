"""应用业务协调器(Presenter):连接 UI 信号与 core 服务,持有共享状态。

托盘 / 设置窗 / 热键 / 截图 / 贴图的交互在此汇聚,UI 与 core 互不直接依赖。
截屏(M2)与贴图(M3)已接入真实流程;OCR(M4)仍为占位。
"""
from __future__ import annotations

import copy
import os

from PySide6.QtCore import QObject
from PySide6.QtGui import QImage

from src.config.settings import ConfigManager
from src.core import startup
from src.core.hotkey.base import ACTION_LABELS, HotkeyManager
from src.core.logger import get_logger
from src.ui.pin import PinManager
from src.ui.settings.settings_dialog import SettingsDialog
from src.ui.tray.tray_icon import TrayIcon

log = get_logger("app_context")

_ABOUT_PAGE_INDEX = 6


class AppContext(QObject):
    """应用级协调器。"""

    def __init__(self) -> None:
        super().__init__()
        self.config = ConfigManager()
        self.hotkeys = HotkeyManager()
        self.tray = TrayIcon()
        self.pins = PinManager(self.config, ocr_handler=self.open_ocr)
        self._settings_dialog: SettingsDialog | None = None
        self._screenshot_windows: list = []
        self._ocr_windows: list = []

        self._wire()
        self._apply_hotkeys()
        self._refresh_tray()

    # ---- 启动 ----
    def start(self) -> None:
        if not self.tray.is_available():
            log.warning("系统托盘不可用(常见于 headless / 无托盘的 Linux 桌面)")
        self.tray.show()
        log.info("SnapOCR 已启动并常驻托盘")

    # ---- 用户反馈 ----
    def notify(self, text: str) -> None:
        """统一的即时反馈:优先自绘 Toast 浮层(不会被 Windows 专注助手拦截),
        Toast 不可用时回退托盘气泡。"""
        try:
            from src.ui.components.toast import Toast
            Toast.show_text(text)
        except Exception as e:
            log.warning("Toast 失败,回退托盘气泡:%s", e)
            self.tray.show_message("SnapOCR", text)

    # ---- 信号连线 ----
    def _wire(self) -> None:
        self.hotkeys.triggered.connect(self._on_hotkey)
        self.tray.action_triggered.connect(self._on_tray_action)
        self.tray.autostart_toggled.connect(self._on_autostart_toggled)
        self.tray.recent_file_triggered.connect(self._on_recent_file)

    def _apply_hotkeys(self) -> None:
        self.hotkeys.register_all(self.config.hotkeys())

    def _refresh_tray(self) -> None:
        self.tray.update_state(
            hotkeys=self.config.hotkeys(),
            recent_files=self.config.recent_files(),
            autostart=startup.is_enabled()
            or bool(self.config.get("general", "auto_start", False)),
        )

    # ---- 热键触发 ----
    def _on_hotkey(self, action: str) -> None:
        if action == "screenshot":
            self.start_screenshot()
        elif action == "pin":
            self._pin_clipboard()
        elif action == "toggle_pin":
            self.pins.toggle_all()
        elif action == "ocr":
            self._ocr_from_clipboard()
        else:
            self._placeholder_feature(action)

    # ---- 托盘动作 ----
    def _on_tray_action(self, action: str) -> None:
        if action == "screenshot":
            self.start_screenshot()
        elif action == "pin":
            self._pin_clipboard()
        elif action == "ocr":
            self._ocr_from_clipboard()
        elif action == "settings":
            self.open_settings()
        elif action == "help":
            self._placeholder_feature("help")
        elif action == "about":
            self.open_settings(page_index=_ABOUT_PAGE_INDEX)
        elif action == "quit":
            self.quit()

    # ---- 贴图(M3)----
    def _pin_clipboard(self) -> None:
        """「贴图」(F3 / 托盘):把剪贴板里的图直接钉成置顶浮窗(同 Snipaste,不截图);
        剪贴板没图时轻提示。要把屏幕某块原位钉住,请用「截图」后点工具栏的「钉图」。"""
        if self.pins.pin_from_clipboard() is None:
            self.notify("剪贴板没有图片,无法贴图(可先截图或复制一张图再按贴图)")

    # ---- 文字识别(M4)----
    def _ocr_from_clipboard(self) -> None:
        """F4 / 托盘「文字识别」:把剪贴板图钉成浮窗 + 图下方原地展开文字面板,不弹独立窗。"""
        if self.pins.pin_from_clipboard(then_ocr=True) is None:
            self.notify("剪贴板没有图片,无法识别文字(可先截图或复制一张图)")

    def open_ocr(self, image: QImage) -> None:
        """弹独立 OCR 结果窗。现仅作降级出口:贴图处于旋转态、坐标排序失效时,
        由 pin_window 的 ocr_requested 信号兜底走这里(正常路径均已改为图下方面板)。"""
        if image is None or image.isNull():
            log.warning("OCR 请求收到空图,忽略")
            return
        from src.ui.ocr import OcrResultWindow

        win = OcrResultWindow(image, self.config)
        win.closed.connect(self._forget_ocr_window)
        self._ocr_windows.append(win)
        win.show()
        win.raise_()
        win.activateWindow()
        log.info("已打开 OCR 结果窗(当前共 %d 个)", len(self._ocr_windows))

    def _forget_ocr_window(self, win) -> None:
        if win in self._ocr_windows:
            self._ocr_windows.remove(win)

    def start_screenshot(self, default_action: str = "copy") -> None:
        log.info("触发截图流程(默认动作=%s)", default_action)
        self._cleanup_screenshot_windows()

        from src.core.screenshot.capture import CaptureEngine
        screens_data = CaptureEngine.capture_all_screens()

        from PySide6.QtWidgets import QApplication
        from src.ui.screenshot.screenshot_window import ScreenshotWindow

        qt_screens = QApplication.screens()
        for idx, screen in enumerate(qt_screens):
            cap_data = screens_data.get(idx, screens_data.get(0))
            if not cap_data:
                log.error("无法获取屏幕 %d 的抓帧数据", idx)
                continue

            win = ScreenshotWindow(screen, cap_data, self.config, default_action=default_action)
            win.sig_canceled.connect(self._on_screenshot_canceled)
            win.sig_result.connect(self._on_screenshot_result)

            self._screenshot_windows.append(win)

        for win in self._screenshot_windows:
            win.show()
            win.raise_()
            win.activateWindow()

    def _on_screenshot_canceled(self) -> None:
        log.info("用户取消了截图")
        self._cleanup_screenshot_windows()

    def _on_screenshot_result(self, image: QImage, action: str, origin=None,
                              ratio: float = 1.0) -> None:
        """截图窗口合成完成后的统一出口:按动作路由复制 / 保存 / 钉图 / OCR。
        origin 为选区左上角全局坐标、ratio 为来源屏 DPI,均用于「钉图」原位且同尺寸贴回。"""
        from src.core.screenshot.writer import ScreenshotWriter

        if image is None or image.isNull():
            log.warning("收到空的合成图,忽略")
            self._cleanup_screenshot_windows()
            return

        if action == "copy":
            ScreenshotWriter.copy_to_clipboard(image)
            self.notify("截图已复制到剪贴板")
        elif action == "save":
            path = ScreenshotWriter.save_to_file(image, self.config)
            if path:
                self._remember_recent(path)
                self.notify(f"截图已保存:{os.path.basename(path)}")
            else:
                self.notify("截图保存失败,请检查保存目录")
        elif action == "pin":
            # M3:把合成图原位、同尺寸钉到桌面(贴在选区原来的位置,体验同 Snipaste)
            self.pins.pin_image(image, at_topleft=origin, source_ratio=ratio)
            log.info("已将截图原位钉到桌面")
        elif action == "ocr":
            # M4:截图「识别」→ 原位钉成浮窗并立刻原地叠可选文字(不跳窗,图不动)
            self.pins.pin_image(image, at_topleft=origin, source_ratio=ratio, then_ocr=True)
            log.info("已将截图原位钉图并原地识别")
        else:
            log.warning("未知截图动作:%s", action)

        self._cleanup_screenshot_windows()

    def _remember_recent(self, path: str) -> None:
        recents = self.config.data.setdefault("recent_files", [])
        if path not in recents:
            recents.insert(0, path)
            self.config.data["recent_files"] = recents[:10]
            self.config.save()
            self._refresh_tray()

    def _cleanup_screenshot_windows(self) -> None:
        for win in self._screenshot_windows:
            try:
                win.close()
            except Exception:
                pass
        self._screenshot_windows.clear()

    def _placeholder_feature(self, action: str) -> None:
        label = ACTION_LABELS.get(action, action)
        log.info("[占位] 触发功能:%s(%s)— M1 暂未实现具体逻辑", action, label)
        self.tray.show_message("SnapOCR", f"[占位] {label} 功能将在后续里程碑实现")

    def _on_autostart_toggled(self, enabled: bool) -> None:
        startup.set_enabled(enabled)
        self.config.set("general", "auto_start", enabled)
        self.config.save()

    def _on_recent_file(self, path: str) -> None:
        log.info("[占位] 打开最近文件:%s", path)

    # ---- 设置窗 ----
    def open_settings(self, page_index: int | None = None) -> None:
        if self._settings_dialog is None:
            # 传入深拷贝,避免设置窗在「取消」前 inplace 污染全局配置
            self._settings_dialog = SettingsDialog(copy.deepcopy(self.config.data))
            self._settings_dialog.sig_saved.connect(self._on_settings_saved)
            self._settings_dialog.sig_reset_defaults.connect(self._on_reset_defaults)
        if page_index is not None:
            self._settings_dialog.select_page(page_index)
        self._settings_dialog.show_and_raise()

    def _on_settings_saved(self, merged: dict) -> None:
        for section, payload in merged.items():
            for key, value in payload.items():
                self.config.set(section, key, value)
        self.config.save()
        # 应用副作用:热键热重载 + 开机自启 + 托盘刷新
        self._apply_hotkeys()
        startup.set_enabled(bool(self.config.get("general", "auto_start", False)))
        self._refresh_tray()
        log.info("设置已保存并应用")

    def _on_reset_defaults(self) -> None:
        self.config.reset_to_defaults()
        self.config.save()
        self._apply_hotkeys()
        self._refresh_tray()
        # 重建设置窗以反映默认值,并保留当前所在页(避免跳回热键页)
        page = 1
        if self._settings_dialog is not None:
            page = self._settings_dialog.current_page()
            self._settings_dialog.close()
            self._settings_dialog = None
        self.open_settings(page_index=page)
        log.info("已恢复默认设置")

    # ---- 退出 ----
    def quit(self) -> None:
        from PySide6.QtWidgets import QApplication

        log.info("退出 SnapOCR")
        self.hotkeys.unregister_all()
        self.pins.close_all()
        for win in list(self._ocr_windows):
            try:
                win.close()
            except Exception:
                pass
        self._ocr_windows.clear()
        self.config.save()
        self.tray.hide()
        QApplication.quit()
