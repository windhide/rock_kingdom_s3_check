from __future__ import annotations

import ctypes
from typing import Any

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from config_manager import ConfigManager
from matcher import MatchStats


def _scale_font(base: int, ratio: float) -> QFont:
    size = max(7, int(base * ratio))
    return QFont("Microsoft YaHei", size)


class _SectionCard(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(6, 2, 6, 2)
        self._layout.setSpacing(1)

        self._title = QLabel(title)
        self._title.setStyleSheet("color: #8b949e; font-weight: bold;")
        self._layout.addWidget(self._title)

        self._grid = QGridLayout()
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(2)
        self._grid.setColumnStretch(1, 1)
        self._layout.addLayout(self._grid)

    def add_row(self, label: str, value: str) -> None:
        row = self._grid.rowCount()
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #c9d1d9;")
        val = QLabel(value)
        val.setStyleSheet("color: #58a6ff; font-weight: bold;")
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._grid.addWidget(lbl, row, 0)
        self._grid.addWidget(val, row, 1)

    def clear_rows(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def set_fonts(self, ratio: float) -> None:
        self._title.setFont(_scale_font(12, ratio))
        for i in range(self._grid.count()):
            w = self._grid.itemAt(i)
            if w and w.widget():
                w.widget().setFont(_scale_font(11, ratio))


class Overlay(QWidget):
    closed = Signal()

    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self._config = config
        self._target_hwnd: int | None = None
        self._drag_pos: QPoint | None = None
        self._stats: MatchStats = MatchStats()
        self._specialty: dict[str, list[str]] = {}
        self._info_region = config.get_region("info")
        self._last_geo: tuple[int, int, int, int] = (-1, -1, -1, -1)
        self._last_w: int = 200

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._build_ui()
        self._build_tray()

        self._pos_timer = QTimer(self)
        self._pos_timer.timeout.connect(self._track_position)
        self._pos_timer.start(200)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- top bar: 重置 + ✕ ---
        self._top_bar = QWidget()
        bar_lay = QHBoxLayout(self._top_bar)
        bar_lay.setContentsMargins(6, 4, 4, 2)
        bar_lay.setSpacing(6)

        self._btn_reset = QPushButton("重置")
        self._btn_reset.setFlat(True)
        self._btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_reset.clicked.connect(self._on_reset)
        bar_lay.addWidget(self._btn_reset)

        bar_lay.addStretch()

        self._btn_exit = QPushButton("✕")
        self._btn_exit.setFlat(True)
        self._btn_exit.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_exit.clicked.connect(self._on_quit)
        bar_lay.addWidget(self._btn_exit)

        self._top_bar.setStyleSheet("""
            QPushButton {
                color: #8b949e; background: transparent; border: none;
                padding: 1px 6px; font-weight: bold;
            }
            QPushButton:hover {
                color: #f0f6fc; background: rgba(48, 54, 61, 180);
                border-radius: 4px;
            }
        """)
        outer.addWidget(self._top_bar)

        # Scroll area — keeps content within the percentage bounds
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: rgba(48, 54, 61, 120); width: 5px; border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: rgba(88, 166, 255, 100); border-radius: 2px; min-height: 24px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        self._inner_layout = QVBoxLayout(inner)
        self._inner_layout.setContentsMargins(6, 6, 6, 6)
        self._inner_layout.setSpacing(2)

        # 精灵种类 — battle counts
        self._battle_card = _SectionCard("精灵种类")
        self._inner_layout.addWidget(self._battle_card)

        # Status
        self._status_lbl = QLabel("等待窗口…")
        self._status_lbl.setAlignment(Qt.AlignCenter)
        self._status_lbl.setStyleSheet("color: #8b949e;")
        self._inner_layout.addWidget(self._status_lbl)

        self._inner_layout.addStretch()

        self._scroll.setWidget(inner)
        outer.addWidget(self._scroll)

    def _build_tray(self) -> None:
        self._tray = QSystemTrayIcon(self)
        self._tray.setToolTip("Rock Kingdom S3 Check")
        self._tray.setIcon(self.style().standardIcon(
            self.style().StandardPixmap.SP_ComputerIcon
        ))
        menu = QMenu()
        show_act = QAction("显示 / 隐藏", self)
        show_act.triggered.connect(self._toggle_visible)
        menu.addAction(show_act)
        reset_act = QAction("重置统计", self)
        reset_act.triggered.connect(self._on_reset)
        menu.addAction(reset_act)
        menu.addSeparator()
        quit_act = QAction("退出", self)
        quit_act.triggered.connect(self._on_quit)
        menu.addAction(quit_act)
        self._tray.setContextMenu(menu)
        self._tray.show()

    # ------------------------------------------------------------------
    # Position & size — strictly within info percentages
    # ------------------------------------------------------------------
    def set_target(self, hwnd: int | None) -> None:
        self._target_hwnd = hwnd
        if hwnd is None:
            self._status_lbl.setText("未找到目标窗口")

    def _track_position(self) -> None:
        if self._target_hwnd is None or self._info_region is None:
            return
        from capture import get_content_rect

        rect = get_content_rect(self._target_hwnd)
        if rect is None:
            self._status_lbl.setText("窗口已关闭")
            return

        t_left, t_top, t_right, t_bottom = rect
        t_w = t_right - t_left
        t_h = t_bottom - t_top

        left_pcts = [float(v) for v in self._info_region["left"]]
        top_pcts = [float(v) for v in self._info_region["top"]]

        ov_x = t_left + int(t_w * left_pcts[0] / 100)
        ov_y = t_top + int(t_h * top_pcts[0] / 100)
        ov_w = int(t_w * (left_pcts[1] - left_pcts[0]) / 100)
        ov_h = int(t_h * (top_pcts[1] - top_pcts[0]) / 100)

        if ov_w < 80 or ov_h < 80:
            return

        hwnd_ov = int(self.winId())
        hwnd_above = ctypes.windll.user32.GetWindow(self._target_hwnd, 3)

        # Always refresh z-order so overlay reappears after Alt+Tab
        ctypes.windll.user32.SetWindowPos(
            hwnd_ov, hwnd_above or 0, 0, 0, 0, 0,
            0x0001 | 0x0002 | 0x0010,  # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
        )

        # Only update geometry when it actually changes
        geo = (ov_x, ov_y, ov_w, ov_h)
        if geo != self._last_geo:
            self._last_geo = geo

            ctypes.windll.user32.SetWindowPos(
                hwnd_ov, hwnd_above or 0, ov_x, ov_y, ov_w, ov_h,
                0x0010,  # SWP_NOACTIVATE
            )
            dpr = self.devicePixelRatioF()
            self.move(int(ov_x / dpr), int(ov_y / dpr))
            self.resize(int(ov_w / dpr), int(ov_h / dpr))
            self._last_w = ov_w
            self._apply_scale(ov_w)

        self._status_lbl.setText("")

    def _apply_scale(self, w: int) -> None:
        ratio = min(w / 220.0, 1.6)
        f = _scale_font(11, ratio)
        self._btn_reset.setFont(f)
        self._btn_exit.setFont(_scale_font(12, ratio))
        self._battle_card.set_fonts(ratio)
        self._status_lbl.setFont(_scale_font(9, ratio))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def update_results(self, results: dict[str, list[str]]) -> None:
        self._specialty = results

    def update_stats(self, stats: MatchStats) -> None:
        self._stats = stats
        self._refresh_display()

    def set_status(self, text: str) -> None:
        self._status_lbl.setText(text)

    def set_ocr_ready(self, ready: bool) -> None:
        if not ready:
            self._status_lbl.setText("正在初始化 OCR…")

    # ------------------------------------------------------------------
    def _refresh_display(self) -> None:
        s = self._stats

        # 精灵种类 (battle counts)
        self._battle_card.clear_rows()
        for key in ("奇异精灵_✔️", "混乱精灵_❌", "污染精灵_✔️", "异色精灵_✔️"):
            count = s.battle.get(key, 0)
            self._battle_card.add_row(key.replace("_✔️", "").replace("_❌", ""), f"×{count}")

        if self._last_w > 0:
            self._apply_scale(self._last_w)

    # ------------------------------------------------------------------
    # Paint — background strictly within geometry
    # ------------------------------------------------------------------
    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(13, 17, 23, 220)
        painter.setBrush(bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 8, 8)
        border = QColor(48, 54, 61, 180)
        pen = QPen(border, 1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)
        painter.end()

    # ------------------------------------------------------------------
    # Mouse drag
    # ------------------------------------------------------------------
    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: Any) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event: Any) -> None:
        self._drag_pos = None

    # ------------------------------------------------------------------
    def _toggle_visible(self) -> None:
        self.setVisible(not self.isVisible())

    def _on_reset(self) -> None:
        self._stats = MatchStats()
        self._specialty = {}
        self._refresh_display()

    def _on_quit(self) -> None:
        self._tray.hide()
        self.closed.emit()
        QApplication.quit()

    def closeEvent(self, event: Any) -> None:
        self._tray.hide()
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Center overlay — current detections in the middle of the game window
# ---------------------------------------------------------------------------
class CenterOverlay(QWidget):
    """Shows 当前特性 and 当前正战斗精灵种类 at the center of the game window."""

    def __init__(self) -> None:
        super().__init__()
        self._target_hwnd: int | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(4)

        self._dialog_lbl = QLabel()
        self._dialog_lbl.setAlignment(Qt.AlignCenter)
        self._dialog_lbl.setStyleSheet("color: #f0f6fc; font-weight: bold;")
        layout.addWidget(self._dialog_lbl)

        self._battle_lbl = QLabel()
        self._battle_lbl.setAlignment(Qt.AlignCenter)
        self._battle_lbl.setStyleSheet("color: #ffa657; font-weight: bold;")
        layout.addWidget(self._battle_lbl)

        self._pos_timer = QTimer(self)
        self._pos_timer.timeout.connect(self._track)
        self._pos_timer.start(200)

    def set_target(self, hwnd: int | None) -> None:
        self._target_hwnd = hwnd

    def set_current(self, dialog_text: str, battle_text: str) -> None:
        self._dialog_lbl.setText(f"当前特性：{dialog_text}" if dialog_text else "")
        self._battle_lbl.setText(f"当前正战斗精灵种类：{battle_text}" if battle_text else "")
        self._apply_size()

    def _apply_size(self) -> None:
        if self._target_hwnd is None:
            return
        from capture import get_content_rect
        rect = get_content_rect(self._target_hwnd)
        if rect is None:
            return
        cw = rect[2] - rect[0]
        ch = rect[3] - rect[1]

        ratio = min(cw / 1920.0, 1.5)
        f = QFont("Microsoft YaHei", max(12, int(18 * ratio)))
        self._dialog_lbl.setFont(f)
        self._battle_lbl.setFont(f)

    def _track(self) -> None:
        if self._target_hwnd is None:
            return
        from capture import get_content_rect
        rect = get_content_rect(self._target_hwnd)
        if rect is None:
            return
        c_left, c_top, c_right, c_bottom = rect
        cw, ch = c_right - c_left, c_bottom - c_top

        # Center horizontally, ~52% from top vertically
        x = c_left + int(cw * 0.25)
        y = c_top + int(ch * 0.50)
        w = int(cw * 0.50)
        h = int(ch * 0.12)

        hwnd_ov = int(self.winId())
        hwnd_above = ctypes.windll.user32.GetWindow(self._target_hwnd, 3)
        ctypes.windll.user32.SetWindowPos(
            hwnd_ov, hwnd_above or 0, x, y, w, h,
            0x0010,
        )
        dpr = self.devicePixelRatioF()
        self.move(int(x / dpr), int(y / dpr))
        self.resize(int(w / dpr), int(h / dpr))

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(13, 17, 23, 200)
        painter.setBrush(bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)
        painter.end()
