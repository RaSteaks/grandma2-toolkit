"""Optional Windows-only MA3D window capture, without UI input or desktop fallback."""

import ctypes
from ctypes import wintypes
from pathlib import Path
import sys


def capture_window(output: Path, title: str | None = None) -> dict:
    if sys.platform != "win32":
        raise RuntimeError("MA3D window capture requires Windows")
    from PIL import ImageGrab, ImageStat

    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    candidates = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def visit(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        text = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, text, len(text))
        if not text.value or (title is not None and text.value != title):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(0x1000, False, pid.value)
        if handle:
            try:
                path, size = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
                if kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
                    if Path(path.value).name.lower() == "ma3d.exe":
                        candidates.append((hwnd, text.value, path.value))
            finally:
                kernel32.CloseHandle(handle)
        return True

    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows(visit, 0)
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one visible, non-minimized MA3D window; found {[c[1] for c in candidates]}. Supply an exact window_title if needed.")
    hwnd, name, exe = candidates[0]
    # Pillow uses the selected HWND. Never fall back to a full-desktop capture.
    shot = ImageGrab.grab(window=hwnd)
    if shot.width < 100 or shot.height < 100 or max(ImageStat.Stat(shot.convert("RGB")).stddev) < 1:
        raise RuntimeError("MA3D capture is empty/blank; restore the window and inspect through computer use")
    shot.save(output)
    return {"file": str(output), "window_title": name, "process": exe, "width": shot.width, "height": shot.height}
