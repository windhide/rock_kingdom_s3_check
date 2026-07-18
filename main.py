from __future__ import annotations

import argparse
import ctypes
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, Signal, QThread, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from capture import capture_window, crop_region, find_window, is_window_valid, get_content_rect
from config_manager import ConfigManager
from matcher import Matcher
from ocr_engine import OCREngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")

# ---- debug switch: set to True to enable region overlays + OCR print ----
DEBUG = True


# ---------------------------------------------------------------------------
# debug region overlay — grey semi-transparent rectangle
# ---------------------------------------------------------------------------
class _DebugRegion(QWidget):
    """A frameless transparent window that paints a grey 30% rectangle."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_geo(self, x: int, y: int, w: int, h: int) -> None:
        hwnd = int(self.winId())
        ctypes.windll.user32.SetWindowPos(
            hwnd, 0, x, y, w, h, 0x0010,  # SWP_NOACTIVATE
        )
        dpr = self.devicePixelRatioF()
        self.move(int(x / dpr), int(y / dpr))
        self.resize(int(w / dpr), int(h / dpr))

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(128, 128, 128, 77))  # grey 30%
        painter.setPen(QPen(QColor(80, 80, 80, 120), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.end()


# ---------------------------------------------------------------------------
class ProcessWorker(QThread):
    results_ready = Signal(dict)
    status_update = Signal(str)
    debug_text = Signal(str, str)  # (region_type, ocr_text)

    def __init__(self, ocr: OCREngine, matcher: Matcher, config: ConfigManager, debug: bool = False) -> None:
        super().__init__()
        self._ocr = ocr
        self._matcher = matcher
        self._config = config
        self._images: dict[str, object] = {}
        self._running = True
        self._debug = debug
        self._lock = __import__("threading").Lock()
        self._event = __import__("threading").Event()

    def submit(self, images: dict[str, object]) -> None:
        with self._lock:
            self._images = images
            self._event.set()

    def stop(self) -> None:
        self._running = False
        self._event.set()

    def run(self) -> None:
        while self._running:
            self._event.wait()
            if not self._running:
                break
            with self._lock:
                images = self._images
                self._images = {}
                self._event.clear()

            if not images:
                continue

            all_results: dict[str, list[str]] = {}
            for region_type, img in images.items():
                if img is None:
                    continue
                text = self._ocr.recognize(img)

                if self._debug:
                    self.debug_text.emit(region_type, text if text.strip() else "(empty)")

                matched = self._matcher.match(region_type, text)
                if matched:
                    all_results[region_type] = matched

            # Always emit so _processing flag gets cleared in main thread
            if all_results:
                logger.debug("Detected: %s", all_results)
            self.results_ready.emit(all_results)
            self.status_update.emit("")


# ---------------------------------------------------------------------------
class App:
    REFRESH_MS = 300

    def __init__(self, config_path: str, debug: bool = False) -> None:
        self._config = ConfigManager(config_path)
        self._config.load()

        if not self._config.name:
            logger.error("name is empty in check.json — please set the window title first")
            sys.exit(1)

        self._debug = debug
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass

        self._ocr = OCREngine()
        self._matcher = Matcher(self._config, debounce_seconds=5.0)
        self._worker = ProcessWorker(self._ocr, self._matcher, self._config, debug=debug)
        self._worker.results_ready.connect(self._on_results)
        self._worker.status_update.connect(self._on_status)
        if debug:
            self._worker.debug_text.connect(self._on_debug_text)

        from overlay import Overlay, CenterOverlay
        self._overlay = Overlay(self._config)
        self._overlay.closed.connect(self._on_overlay_closed)
        self._overlay.set_ocr_ready(False)

        self._center = CenterOverlay()
        self._center.show()

        # Debug region overlays
        self._debug_regions: dict[str, _DebugRegion] = {}
        if debug:
            for rtype in ("dialog", "battle"):  # banner disabled
                w = _DebugRegion()
                w.show()
                self._debug_regions[rtype] = w

        self._hwnd: int | None = None
        self._processing = False
        self._overlay.show()

        self._overlay.set_status("正在初始化 OCR 引擎…")
        QTimer.singleShot(100, self._init_ocr)

    # ------------------------------------------------------------------
    def _init_ocr(self) -> None:
        ok = self._ocr.initialize()
        if not ok:
            self._overlay.set_status("OCR 初始化失败，请检查 rapidocr-onnxruntime 安装")
            return
        self._overlay.set_ocr_ready(True)
        self._worker.start()

        self._capture_timer = QTimer()
        self._capture_timer.timeout.connect(self._tick)
        self._capture_timer.start(self.REFRESH_MS)

        # Debug region z-order refresh — independent of capture loop
        if self._debug:
            self._debug_timer = QTimer()
            self._debug_timer.timeout.connect(self._update_debug_regions)
            self._debug_timer.start(200)

        self._find_target()

    # ------------------------------------------------------------------
    def _find_target(self) -> None:
        hwnd = find_window(self._config.name)
        if hwnd is not None and is_window_valid(hwnd):
            self._hwnd = hwnd
            self._overlay.set_target(hwnd)
            self._center.set_target(hwnd)
            self._overlay.set_status("")
            logger.info("Found target window: 0x%X", hwnd)
        else:
            self._hwnd = None
            self._overlay.set_target(None)
            self._overlay.set_status(f"未找到窗口: {self._config.name}")

    # ------------------------------------------------------------------
    def _tick(self) -> None:
        if self._hwnd is None or not is_window_valid(self._hwnd):
            self._find_target()
            if self._hwnd is None:
                return

        if self._processing:
            return

        img = capture_window(self._hwnd)
        if img is None:
            return

        crops: dict[str, object] = {}
        for rtype in ("dialog", "battle"):  # banner disabled
            rc = self._config.get_region(rtype)
            if rc is None:
                continue
            cropped = crop_region(img, rc)
            if cropped is not None:
                crops[rtype] = cropped

        if crops:
            self._processing = True
            self._worker.submit(crops)

        # Update debug region overlays (position + z-order every tick)
        if self._debug:
            self._update_debug_regions()

    def _update_debug_regions(self) -> None:
        rect = get_content_rect(self._hwnd)
        if rect is None:
            return
        c_left, c_top, c_right, c_bottom = rect
        cw, ch = c_right - c_left, c_bottom - c_top

        for rtype, widget in self._debug_regions.items():
            rc = self._config.get_region(rtype)
            if rc is None:
                continue
            l = [float(v) for v in rc["left"]]
            t = [float(v) for v in rc["top"]]
            x = c_left + int(cw * l[0] / 100)
            y = c_top + int(ch * t[0] / 100)
            w = int(cw * (l[1] - l[0]) / 100)
            h = int(ch * (t[1] - t[0]) / 100)
            if w > 0 and h > 0:
                # position + z-order above target
                hwnd_dbg = int(widget.winId())
                hwnd_above = ctypes.windll.user32.GetWindow(self._hwnd, 3)
                ctypes.windll.user32.SetWindowPos(
                    hwnd_dbg, hwnd_above or 0, x, y, w, h, 0x0010,
                )
                dpr = widget.devicePixelRatioF()
                widget.move(int(x / dpr), int(y / dpr))
                widget.resize(int(w / dpr), int(h / dpr))

    # ------------------------------------------------------------------
    def _on_results(self, results: dict[str, list[str]]) -> None:
        self._processing = False
        if results:
            self._overlay.update_results(results)

            # Update center overlay with current detections
            dialog_specs = results.get("dialog", [])
            battle_specs = results.get("battle", [])
            self._center.set_current(
                " ".join(dialog_specs) if dialog_specs else "",
                " ".join(battle_specs) if battle_specs else "",
            )

        self._overlay.update_stats(self._matcher.stats)

    def _on_status(self, text: str) -> None:
        if text:
            self._overlay.set_status(text)

    def _on_debug_text(self, region_type: str, text: str) -> None:
        print(f"[OCR] [{region_type}] {text}")

    def _on_overlay_closed(self) -> None:
        self._worker.stop()
        self._worker.wait(2000)

    # ------------------------------------------------------------------
    def run(self) -> int:
        return self._app.exec()


# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Rock Kingdom S3 Check")
    parser.add_argument(
        "-c", "--config", default="check.json",
        help="Path to check.json (default: check.json)",
    )
    parser.add_argument(
        "--debounce", type=float, default=5.0,
        help="Debounce seconds for repeated detections (default: 5.0)",
    )
    parser.add_argument(
        "--debug", action="store_true", default=None,
        help="Enable debug mode: show OCR region overlays and print OCR text",
    )
    args = parser.parse_args()

    # CLI flag overrides code constant
    debug = DEBUG if args.debug is None else args.debug

    if not Path(args.config).exists():
        logger.error("Config file not found: %s", args.config)
        sys.exit(1)

    app = App(args.config, debug=debug)
    sys.exit(app.run())


if __name__ == "__main__":
    main()
