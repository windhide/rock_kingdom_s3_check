from __future__ import annotations

import ctypes
from ctypes import wintypes

import win32con
import win32gui
import win32ui
from PIL import Image


def find_window(name: str) -> int | None:
    """Find a top-level window whose title *contains* `name` (case-insensitive).
    Falls back to matching by window class name.
    """

    def _callback(hwnd: int, windows: list[int]) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            cls_name = win32gui.GetClassName(hwnd)
            needle = name.lower()
            if needle in title.lower() or needle in cls_name.lower():
                windows.append(hwnd)
        return True

    windows: list[int] = []
    win32gui.EnumWindows(_callback, windows)
    return windows[0] if windows else None


def is_window_valid(hwnd: int) -> bool:
    return bool(win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd))


def get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """Get the true visible bounds of a window (excludes DWM invisible shadows).
    Uses DwmGetWindowAttribute on Windows 10+ for pixel-accurate bounds.
    """
    try:
        rect = wintypes.RECT()
        hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)  # DWMWA_EXTENDED_FRAME_BOUNDS
        )
        if hr == 0:  # S_OK
            return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception:
        pass
    try:
        return win32gui.GetWindowRect(hwnd)
    except Exception:
        return None


def get_client_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """Get the client area in **physical** screen coordinates."""
    try:
        c_rect = win32gui.GetClientRect(hwnd)
        cw_logical, ch_logical = c_rect[2], c_rect[3]

        # Convert logical → physical for DPI-unaware windows
        try:
            dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
        except Exception:
            dpi = 96
        scale = dpi / 96.0

        wr = get_window_rect(hwnd)
        if wr:
            dwm_w = wr[2] - wr[0]
            if abs(cw_logical * scale - dwm_w) < abs(cw_logical - dwm_w):
                cw_logical = int(cw_logical * scale)
                ch_logical = int(ch_logical * scale)

        pt = wintypes.POINT(0, 0)
        ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))
        return (pt.x, pt.y, pt.x + cw_logical, pt.y + ch_logical)
    except Exception:
        return None


def get_content_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """Get the game-content bounds in physical screen pixels.
    - Fullscreen / borderless → full window rect (no title bar).
    - Windowed → client area only (excludes title bar / borders).
    """
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    has_caption = bool(style & win32con.WS_CAPTION)
    if has_caption:
        return get_client_rect(hwnd)
    return get_window_rect(hwnd)


def capture_window(hwnd: int) -> Image.Image | None:
    """Capture game content, auto-detecting fullscreen vs windowed, DPI-safe.

    All coordinates are in **physical screen pixels** so Windows DPI scaling
    does not affect region percentages — the game renders at native resolution.
    """
    try:
        # Accurate visible bounds (no DWM shadows)
        wr = get_window_rect(hwnd)
        if wr is None:
            return None
        w_left, w_top, w_right, w_bottom = wr

        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        has_caption = bool(style & win32con.WS_CAPTION)

        if has_caption:
            # Windowed: capture ONLY the client (content) area.
            # GetClientRect gives logical dimensions; may need DPI scaling.
            c_rect = win32gui.GetClientRect(hwnd)
            cw_logical, ch_logical = c_rect[2], c_rect[3]

            # Physical client origin on screen
            pt = wintypes.POINT(0, 0)
            ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))
            left, top = pt.x, pt.y

            # Detect if the window is DPI-unaware (GetClientRect gives logical px)
            try:
                dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
            except Exception:
                dpi = 96
            scale = dpi / 96.0

            # Heuristic: if logical size × scale is close to DWM physical width,
            # the window is DPI-unaware and needs scaling.
            dwm_w = w_right - w_left
            if abs(cw_logical * scale - dwm_w) < abs(cw_logical - dwm_w):
                w = int(cw_logical * scale)
                h = int(ch_logical * scale)
            else:
                w, h = cw_logical, ch_logical
        else:
            # Fullscreen / borderless — no title bar, capture entire window
            left, top = w_left, w_top
            w = w_right - w_left
            h = w_bottom - w_top

        if w <= 0 or h <= 0:
            return None

        screen_dc = win32gui.GetDC(0)
        mfc_dc = win32ui.CreateDCFromHandle(screen_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mfc_dc, w, h)
        save_dc.SelectObject(bmp)

        save_dc.BitBlt((0, 0), (w, h), mfc_dc, (left, top), win32con.SRCCOPY)

        bmp_bits = bmp.GetBitmapBits(True)
        img = Image.frombuffer("RGB", (w, h), bmp_bits, "raw", "BGRX", 0, 1)

        win32gui.DeleteObject(bmp.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(0, screen_dc)
        return img
    except Exception:
        return None


def crop_region(img: Image.Image, region_config: dict) -> Image.Image | None:
    """Crop image by percentage-based top/left config.
    region_config = {"top": ["start%", "end%"], "left": ["start%", "end%"]}
    """
    try:
        w, h = img.size
        top_pcts = [float(v) for v in region_config["top"]]
        left_pcts = [float(v) for v in region_config["left"]]
        x1 = int(w * left_pcts[0] / 100)
        y1 = int(h * top_pcts[0] / 100)
        x2 = int(w * left_pcts[1] / 100)
        y2 = int(h * top_pcts[1] / 100)
        if x2 <= x1 or y2 <= y1:
            return None
        return img.crop((x1, y1, x2, y2))
    except Exception:
        return None
