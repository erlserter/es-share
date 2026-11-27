"""Cross-platform clipboard read/write helpers without external dependencies."""

from __future__ import annotations

import platform
import subprocess
import threading
import time
from typing import Callable


def get_clipboard_text() -> str | None:
    """Read plain text from the OS clipboard, or return None if unavailable/empty."""
    sys_name = platform.system().lower()
    if sys_name == "darwin":
        try:
            res = subprocess.run(
                ["pbpaste"],
                capture_output=True,
                text=True,
                timeout=1.5,
                check=False,
            )
            if res.returncode == 0:
                return res.stdout
        except Exception:
            return None
    elif sys_name == "windows":
        return _win_get_clipboard()
    return None


def set_clipboard_text(text: str) -> bool:
    """Write plain text to the OS clipboard. Returns True on success."""
    sys_name = platform.system().lower()
    if sys_name == "darwin":
        try:
            res = subprocess.run(
                ["pbcopy"],
                input=text,
                text=True,
                timeout=1.5,
                check=False,
            )
            return res.returncode == 0
        except Exception:
            return False
    elif sys_name == "windows":
        return _win_set_clipboard(text)
    return False


def _win_get_clipboard() -> str | None:
    try:
        import ctypes
        from ctypes import wintypes

        CF_UNICODETEXT = 13
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = wintypes.HANDLE
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL

        if not user32.OpenClipboard(None):
            return None
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return None
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return None
            try:
                return ctypes.wstring_at(ptr)
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()
    except Exception:
        return None


def _win_set_clipboard(text: str) -> bool:
    try:
        import ctypes
        from ctypes import wintypes

        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.EmptyClipboard.argtypes = []
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL

        data = text.encode("utf-16-le") + b"\x00\x00"
        hmem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not hmem:
            return False
        ptr = kernel32.GlobalLock(hmem)
        if not ptr:
            return False
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(hmem)

        if not user32.OpenClipboard(None):
            return False
        try:
            user32.EmptyClipboard()
            return bool(user32.SetClipboardData(CF_UNICODETEXT, hmem))
        finally:
            user32.CloseClipboard()
    except Exception:
        return False


class ClipboardWatcher:
    """Polls local clipboard and invokes callback on text changes without echo loops."""

    def __init__(self, on_change: Callable[[str], None], interval: float = 0.6) -> None:
        self.on_change = on_change
        self.interval = interval
        self._lock = threading.Lock()
        self._last_text: str | None = get_clipboard_text()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def apply_remote(self, text: str) -> None:
        """Apply text received from peer and suppress echoing it back."""
        with self._lock:
            if text == self._last_text:
                return
            self._last_text = text
        set_clipboard_text(text)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            time.sleep(self.interval)
            if self._stop_event.is_set():
                break
            current = get_clipboard_text()
            if current is None or current == "":
                continue
            changed = False
            with self._lock:
                if current != self._last_text:
                    self._last_text = current
                    changed = True
            if changed:
                try:
                    self.on_change(current)
                except Exception:
                    pass

