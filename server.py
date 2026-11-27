"""ES-Share Server: captures local keyboard/mouse and streams to a connected client."""

from __future__ import annotations

import atexit
import platform
import socket
import threading
import time
from typing import Any, Callable

from clipboard_sync import ClipboardWatcher
from protocol import (
    DEFAULT_PORT,
    decode_messages,
    encode_message,
    save_incoming_file,
    serialize_key,
)


def check_accessibility_trusted(prompt: bool = False) -> bool:
    """Return True if macOS Accessibility permission is granted (always True on other OSes)."""
    if platform.system().lower() != "darwin":
        return True
    try:
        import ApplicationServices

        if prompt:
            opts = {ApplicationServices.kAXTrustedCheckOptionPrompt: True}
            return bool(ApplicationServices.AXIsProcessTrustedWithOptions(opts))
        return bool(ApplicationServices.AXIsProcessTrusted())
    except Exception:
        return True


def _get_screen_size() -> tuple[int, int]:
    """Return primary display dimensions using native OS APIs."""
    sys_name = platform.system().lower()
    if sys_name == "darwin":
        try:
            import Quartz

            main_id = Quartz.CGMainDisplayID()
            w = int(Quartz.CGDisplayPixelsWide(main_id))
            h = int(Quartz.CGDisplayPixelsHigh(main_id))
            if w > 0 and h > 0:
                return w, h
        except Exception:
            pass
    elif sys_name == "windows":
        try:
            import ctypes

            user32 = ctypes.windll.user32
            w = int(user32.GetSystemMetrics(0))
            h = int(user32.GetSystemMetrics(1))
            if w > 0 and h > 0:
                return w, h
        except Exception:
            pass

    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        w, h = root.winfo_screenwidth(), root.winfo_screenheight()
        root.destroy()
        return int(w), int(h)
    except Exception:
        return 1920, 1080


class KVMServer:
    """TCP server that forwards keyboard & mouse events when Remote mode is active."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = DEFAULT_PORT,
        edge_switch: str | None = "right",
        on_status: Callable[[str], None] | None = None,
        on_mode_change: Callable[[bool], None] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.edge_switch = edge_switch
        self.on_status = on_status or (lambda msg: None)
        self.on_mode_change = on_mode_change or (lambda active: None)

        self._is_darwin = platform.system().lower() == "darwin"
        self._stop_event = threading.Event()
        self._server_sock: socket.socket | None = None
        self._client_sock: socket.socket | None = None
        self._client_lock = threading.Lock()
        self._client_platform = "windows"
        self._client_supports_edge_return = False
        self._remote_screen_w = 1920
        self._virtual_x = 0.0
        self._switch_y_ratio = 0.5

        self._remote_active = False
        self._mode_lock = threading.Lock()
        self._last_switch_ts = 0.0

        self._screen_w, self._screen_h = _get_screen_size()
        self._last_pos: tuple[int, int] | None = None
        self._warping = False
        self._suppress_current_key_event = False
        self._cursor_locked = False
        self._park_pos: tuple[int, int] | None = None
        self._esc_times: list[float] = []
        self._atexit_registered = False

        self._pressed_modifiers: set[str] = set()
        self._mouse_listener = None
        self._key_listener = None
        self._mouse_ctrl = None
        self._clipboard: ClipboardWatcher | None = None

    @property
    def remote_active(self) -> bool:
        return self._remote_active

    @property
    def accessibility_trusted(self) -> bool:
        return check_accessibility_trusted(False)

    @property
    def screen_size(self) -> tuple[int, int]:
        return (self._screen_w, self._screen_h)

    def start(self) -> None:
        """Start the TCP accept loop and input listeners."""
        from pynput import mouse

        self._mouse_ctrl = mouse.Controller()
        self._stop_event.clear()

        if self._is_darwin and not self._atexit_registered:
            atexit.register(self._unlock_cursor_safe)
            self._atexit_registered = True

        if self._is_darwin and not self.accessibility_trusted:
            self.on_status(
                "UYARI: macOS Erişilebilirlik izni yok! İzin verilmeden klavye/fare yakalanamaz."
            )

        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(1)
        self._server_sock.settimeout(0.5)

        self.on_status(f"Sunucu dinleniyor: {self.host}:{self.port}")
        self._start_listeners(suppress=False)

        self._clipboard = ClipboardWatcher(self._on_local_clipboard)
        self._clipboard.start()

        accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        accept_thread.start()

    def stop(self) -> None:
        """Stop server, listeners, and client connection."""
        self._stop_event.set()
        if self._clipboard is not None:
            self._clipboard.stop()
            self._clipboard = None
        self._set_remote_active(False, restart_listeners=False)
        self._unlock_cursor_safe()
        self._stop_listeners()

        with self._client_lock:
            if self._client_sock:
                try:
                    self._client_sock.close()
                except OSError:
                    pass
                self._client_sock = None

        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None

        self.on_status("Sunucu durduruldu.")

    def toggle_mode(self) -> None:
        """Toggle between Local and Remote control."""
        self._set_remote_active(not self._remote_active)

    def send_test_mouse(self) -> bool:
        """Send a small square mouse wiggle to the connected client for testing."""
        if not self._has_client():
            return False

        def _wiggle() -> None:
            for dx, dy in ((35, 0), (0, 35), (-35, 0), (0, -35)):
                if self._stop_event.is_set() or not self._has_client():
                    return
                self._send({"type": "mouse_move", "dx": dx, "dy": dy})
                time.sleep(0.06)
            self.on_status("Test sinyali Windows'a gönderildi (fare hareket etmeli).")

        threading.Thread(target=_wiggle, daemon=True).start()
        return True

    def _on_local_clipboard(self, text: str) -> None:
        if self._has_client():
            self._send({"type": "clipboard", "text": text})

    def send_file(self, name: str, data_b64: str) -> bool:
        """Send a base64-encoded file to the connected client."""
        if not self._has_client():
            return False
        self._send({"type": "file", "name": name, "data": data_b64})
        self.on_status(f"Dosya Windows'a gönderildi: {name}")
        return True

    def _set_darwin_cursor_locked(
        self,
        locked: bool,
        return_y_ratio: float | None = None,
    ) -> None:
        """Freeze or unfreeze macOS on-screen cursor without blocking relative deltas."""
        if not self._is_darwin:
            return
        try:
            import Quartz

            if locked and not self._cursor_locked:
                if self.edge_switch == "right":
                    park = (self._screen_w - 1, self._screen_h // 2)
                elif self.edge_switch == "left":
                    park = (0, self._screen_h // 2)
                else:
                    park = (self._screen_w // 2, self._screen_h // 2)
                self._park_pos = park
                Quartz.CGWarpMouseCursorPosition(park)
                Quartz.CGAssociateMouseAndMouseCursorPosition(False)
                self._cursor_locked = True
            elif not locked:
                Quartz.CGAssociateMouseAndMouseCursorPosition(True)
                if self._cursor_locked:
                    if return_y_ratio is not None:
                        clamped_y = max(0.0, min(1.0, float(return_y_ratio)))
                        target_y = int(clamped_y * self._screen_h)
                    else:
                        target_y = self._screen_h // 2
                    if self.edge_switch == "right":
                        Quartz.CGWarpMouseCursorPosition(
                            (max(0, self._screen_w - 40), target_y)
                        )
                    elif self.edge_switch == "left":
                        Quartz.CGWarpMouseCursorPosition(
                            (min(self._screen_w - 1, 40), target_y)
                        )
                    self._cursor_locked = False
                self._park_pos = None
        except Exception:
            self._cursor_locked = False
            self._park_pos = None

    def _unlock_cursor_safe(self) -> None:
        """Best-effort cursor unlock on shutdown/exit."""
        try:
            self._set_darwin_cursor_locked(False)
        except Exception:
            pass

    def _set_remote_active(
        self,
        active: bool,
        restart_listeners: bool = True,
        return_y_ratio: float | None = None,
    ) -> None:
        with self._mode_lock:
            if self._remote_active == active:
                return
            if active and not self._has_client():
                self.on_status("Bağlı istemci yok; uzak moda geçilemedi.")
                return

            self._remote_active = active
            self._last_switch_ts = time.monotonic()
            self._last_pos = None

            if active:
                if self.edge_switch == "right":
                    self._virtual_x = 120.0
                elif self.edge_switch == "left":
                    self._virtual_x = float(max(120, self._remote_screen_w - 120))
                else:
                    self._virtual_x = self._remote_screen_w / 2.0

                if self._is_darwin:
                    self._set_darwin_cursor_locked(True)
                else:
                    cx, cy = self._screen_w // 2, self._screen_h // 2
                    if self._mouse_ctrl is not None:
                        self._warping = True
                        self._mouse_ctrl.position = (cx, cy)
                        self._last_pos = (cx, cy)
                        self._warping = False
                self._send(
                    {
                        "type": "switch",
                        "active": True,
                        "edge": self.edge_switch,
                        "y_ratio": self._switch_y_ratio,
                    }
                )
                self.on_status("MOD: UZAK BİLGİSAYAR (Geri dönmek için Ctrl+Alt+S veya 3× Esc)")
            else:
                if self._is_darwin:
                    self._set_darwin_cursor_locked(False, return_y_ratio=return_y_ratio)
                self._send({"type": "switch", "active": False})
                self.on_status("MOD: YEREL BİLGİSAYAR (Geçiş: Ctrl+Alt+S veya ekran kenarı)")

            self.on_mode_change(active)

        if restart_listeners and not self._is_darwin and not self._stop_event.is_set():
            threading.Thread(
                target=self._restart_listeners,
                args=(active,),
                daemon=True,
            ).start()

    def _has_client(self) -> bool:
        with self._client_lock:
            return self._client_sock is not None

    def _send(self, payload: dict) -> None:
        data = encode_message(payload)
        with self._client_lock:
            if self._client_sock is None:
                return
            try:
                self._client_sock.sendall(data)
            except OSError:
                self._close_client_locked()

    def _close_client_locked(self) -> None:
        if self._client_sock is not None:
            try:
                self._client_sock.close()
            except OSError:
                pass
            self._client_sock = None
            self._client_supports_edge_return = False
            self.on_status("İstemci bağlantısı kesildi.")
            if self._remote_active:
                threading.Thread(
                    target=self._set_remote_active,
                    args=(False,),
                    daemon=True,
                ).start()

    def _accept_loop(self) -> None:
        while not self._stop_event.is_set():
            assert self._server_sock is not None
            try:
                conn, addr = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            with self._client_lock:
                if self._client_sock is not None:
                    try:
                        self._client_sock.close()
                    except OSError:
                        pass
                self._client_sock = conn

            self.on_status(f"İstemci bağlandı: {addr[0]}:{addr[1]}")
            self._send(
                {
                    "type": "handshake",
                    "platform": platform.system().lower(),
                    "screen_w": self._screen_w,
                    "screen_h": self._screen_h,
                }
            )
            self._read_client_loop(conn)

    def _read_client_loop(self, conn: socket.socket) -> None:
        buf = b""
        conn.settimeout(0.5)
        while not self._stop_event.is_set():
            try:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
                msgs, buf = decode_messages(buf)
                for msg in msgs:
                    mtype = msg.get("type")
                    if mtype == "handshake":
                        self._client_platform = str(msg.get("platform", "windows"))
                        self._client_supports_edge_return = bool(
                            msg.get("supports_edge_return", False)
                        )
                        sw = int(msg.get("screen_w", 0) or 0)
                        if sw > 0:
                            self._remote_screen_w = sw
                    elif mtype == "return_to_server":
                        if self._remote_active:
                            self._set_remote_active(
                                False,
                                return_y_ratio=msg.get("y_ratio"),
                            )
                    elif mtype == "clipboard":
                        text = msg.get("text")
                        if isinstance(text, str) and self._clipboard is not None:
                            self._clipboard.apply_remote(text)
                    elif mtype == "file":
                        name = str(msg.get("name", "dosya"))
                        data_b64 = str(msg.get("data", ""))
                        if data_b64:
                            try:
                                saved = save_incoming_file(name, data_b64)
                                self.on_status(f"Dosya alındı: {saved}")
                            except Exception as exc:
                                self.on_status(f"Dosya kaydetme hatası: {exc}")
            except socket.timeout:
                continue
            except OSError:
                break

        with self._client_lock:
            if self._client_sock is conn:
                self._close_client_locked()

    def _restart_listeners(self, suppress: bool) -> None:
        self._stop_listeners()
        if not self._stop_event.is_set():
            self._start_listeners(suppress=suppress)

    def _stop_listeners(self) -> None:
        if self._mouse_listener is not None:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass
            self._mouse_listener = None
        if self._key_listener is not None:
            try:
                self._key_listener.stop()
            except Exception:
                pass
            self._key_listener = None

    def _start_listeners(self, suppress: bool) -> None:
        from pynput import keyboard, mouse

        if self._is_darwin:
            self._mouse_listener = mouse.Listener(
                on_move=self._on_move,
                on_click=self._on_click,
                on_scroll=self._on_scroll,
                suppress=False,
                darwin_intercept=self._darwin_mouse_intercept,
            )
            self._key_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
                suppress=False,
                darwin_intercept=self._darwin_key_intercept,
            )
        else:
            self._mouse_listener = mouse.Listener(
                on_move=self._on_move,
                on_click=self._on_click,
                on_scroll=self._on_scroll,
                suppress=suppress,
            )
            self._key_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
                suppress=suppress,
            )
        self._mouse_listener.start()
        self._key_listener.start()

    def _check_virtual_edge_return(self, dx: int) -> bool:
        """Fallback edge return using virtual X tracking when client lacks edge-return."""
        if self._client_supports_edge_return or not self.edge_switch:
            return False
        if time.monotonic() - self._last_switch_ts <= 0.4:
            return False
        if self.edge_switch == "right":
            self._virtual_x = min(float(self._remote_screen_w), self._virtual_x + dx)
            if dx < 0 and self._virtual_x <= 0.0:
                return True
        elif self.edge_switch == "left":
            self._virtual_x = max(0.0, self._virtual_x + dx)
            if dx > 0 and self._virtual_x >= float(self._remote_screen_w):
                return True
        return False

    def _darwin_mouse_intercept(self, event_type: int, event: Any) -> Any:
        """Stream true hardware relative mouse deltas and suppress locally when remote."""
        if not self._remote_active:
            return event

        import Quartz

        if event_type in (
            Quartz.kCGEventMouseMoved,
            Quartz.kCGEventLeftMouseDragged,
            Quartz.kCGEventRightMouseDragged,
            Quartz.kCGEventOtherMouseDragged,
        ):
            dx = int(Quartz.CGEventGetIntegerValueField(event, Quartz.kCGMouseEventDeltaX))
            dy = int(Quartz.CGEventGetIntegerValueField(event, Quartz.kCGMouseEventDeltaY))
            if dx != 0 and self._check_virtual_edge_return(dx):
                self._set_remote_active(False)
                return None
            if dx != 0 or dy != 0:
                self._send({"type": "mouse_move", "dx": dx, "dy": dy})
            if self._park_pos is not None:
                loc = Quartz.CGEventGetLocation(event)
                if (
                    abs(loc.x - self._park_pos[0]) > 1
                    or abs(loc.y - self._park_pos[1]) > 1
                ):
                    Quartz.CGWarpMouseCursorPosition(self._park_pos)
        return None

    def _darwin_key_intercept(self, event_type: int, event: Any) -> Any:
        """Suppress keyboard events locally when remote or when hotkey just triggered."""
        if self._suppress_current_key_event:
            self._suppress_current_key_event = False
            return None
        if self._remote_active:
            return None
        return event

    def _on_move(self, x: int, y: int) -> None:
        if self._warping:
            return

        if not self._remote_active:
            if (
                self.edge_switch
                and self._has_client()
                and time.monotonic() - self._last_switch_ts > 0.5
            ):
                if self.edge_switch == "right" and x >= self._screen_w - 2:
                    self._switch_y_ratio = max(0.0, min(1.0, y / max(1, self._screen_h)))
                    self._set_remote_active(True)
                elif self.edge_switch == "left" and x <= 1:
                    self._switch_y_ratio = max(0.0, min(1.0, y / max(1, self._screen_h)))
                    self._set_remote_active(True)
            return

        if self._is_darwin:
            return

        if self._last_pos is None:
            self._last_pos = (x, y)
            return

        dx = int(x - self._last_pos[0])
        dy = int(y - self._last_pos[1])
        self._last_pos = (x, y)

        if dx != 0 and self._check_virtual_edge_return(dx):
            self._set_remote_active(False)
            return

        if dx != 0 or dy != 0:
            self._send({"type": "mouse_move", "dx": dx, "dy": dy})

        margin = 80
        if (
            x < margin
            or x > self._screen_w - margin
            or y < margin
            or y > self._screen_h - margin
        ):
            cx, cy = self._screen_w // 2, self._screen_h // 2
            if self._mouse_ctrl is not None:
                self._warping = True
                self._mouse_ctrl.position = (cx, cy)
                self._last_pos = (cx, cy)
                self._warping = False

    def _on_click(self, x: int, y: int, button: Any, pressed: bool) -> None:
        if not self._remote_active:
            return
        btn_name = getattr(button, "name", "left")
        self._send({"type": "mouse_click", "button": btn_name, "pressed": pressed})

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        if not self._remote_active:
            return
        self._send({"type": "mouse_scroll", "dx": int(dx), "dy": int(dy)})

    def _check_hotkey(self, key_info: dict) -> bool:
        """Detect Ctrl+Alt+S toggle hotkey across macOS/Windows/Turkish layouts."""
        has_ctrl = any(m.startswith("ctrl") for m in self._pressed_modifiers)
        has_alt = any(m.startswith("alt") for m in self._pressed_modifiers)
        if not (has_ctrl and has_alt):
            return False

        kind = key_info.get("kind")
        if kind == "char":
            val = str(key_info.get("value", "")).lower()
            if val in ("s", "\x13", "ß", "∑"):
                return True

        vk = key_info.get("vk") if kind != "vk" else key_info.get("value")
        if (self._is_darwin and vk == 1) or (not self._is_darwin and vk == 83):
            return True
        return False

    def _on_key_press(self, key: Any) -> None:
        info = serialize_key(key)
        if info is None:
            return

        if info["kind"] == "special":
            val = info["value"]
            if val.startswith(("ctrl", "alt", "shift", "cmd")):
                self._pressed_modifiers.add(val)

        if self._check_hotkey(info):
            self._suppress_current_key_event = True
            self.toggle_mode()
            return

        if (
            self._remote_active
            and info.get("kind") == "special"
            and info.get("value") == "esc"
        ):
            now = time.monotonic()
            self._esc_times = [t for t in self._esc_times if now - t <= 1.0]
            self._esc_times.append(now)
            if len(self._esc_times) >= 3:
                self._esc_times.clear()
                self._suppress_current_key_event = True
                self._set_remote_active(False)
                return

        if self._remote_active:
            self._send({"type": "key", "key": info, "pressed": True})

    def _on_key_release(self, key: Any) -> None:
        info = serialize_key(key)
        if info is None:
            return

        if info["kind"] == "special":
            self._pressed_modifiers.discard(info["value"])

        if self._remote_active:
            self._send({"type": "key", "key": info, "pressed": False})
