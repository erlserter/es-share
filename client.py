"""ES-Share Client: connects to a KVMServer and replays input events locally."""

from __future__ import annotations

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
    map_special_key_name,
    save_incoming_file,
)


def _get_client_screen_size() -> tuple[int, int]:
    """Return primary display dimensions on the client machine."""
    sys_name = platform.system().lower()
    if sys_name == "windows":
        try:
            import ctypes

            user32 = ctypes.windll.user32
            w = int(user32.GetSystemMetrics(0))
            h = int(user32.GetSystemMetrics(1))
            if w > 0 and h > 0:
                return w, h
        except Exception:
            pass
    elif sys_name == "darwin":
        try:
            import Quartz

            main_id = Quartz.CGMainDisplayID()
            w = int(Quartz.CGDisplayPixelsWide(main_id))
            h = int(Quartz.CGDisplayPixelsHigh(main_id))
            if w > 0 and h > 0:
                return w, h
        except Exception:
            pass
    return 1920, 1080


class KVMClient:
    """TCP client that receives keyboard & mouse events from a KVMServer."""

    def __init__(
        self,
        server_host: str,
        port: int = DEFAULT_PORT,
        map_cmd_ctrl: bool = True,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        self.server_host = server_host
        self.port = port
        self.map_cmd_ctrl = map_cmd_ctrl
        self.on_status = on_status or (lambda msg: None)

        self._stop_event = threading.Event()
        self._sock: socket.socket | None = None
        self._sock_lock = threading.Lock()
        self._thread: threading.Thread | None = None

        self._server_platform = "darwin"
        self._local_platform = platform.system().lower()
        self._screen_w, self._screen_h = _get_client_screen_size()
        self._entry_edge: str | None = None
        self._remote_active = False
        self._active_since = 0.0
        self._pressed_keys: list[Any] = []

        self._mouse_ctrl = None
        self._key_ctrl = None
        self._button_map: dict[str, Any] = {}
        self._special_keys: dict[str, Any] = {}
        self._clipboard: ClipboardWatcher | None = None

    def start(self) -> None:
        """Start client connection loop in a background thread."""
        from pynput import keyboard, mouse

        self._mouse_ctrl = mouse.Controller()
        self._key_ctrl = keyboard.Controller()
        self._button_map = {
            "left": mouse.Button.left,
            "right": mouse.Button.right,
            "middle": mouse.Button.middle,
        }
        self._special_keys = {k.name: k for k in keyboard.Key}

        self._stop_event.clear()
        self._clipboard = ClipboardWatcher(self._on_local_clipboard)
        self._clipboard.start()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Disconnect and stop the client."""
        self._stop_event.set()
        if self._clipboard is not None:
            self._clipboard.stop()
            self._clipboard = None
        self._remote_active = False
        self._release_all_keys()
        with self._sock_lock:
            if self._sock is not None:
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None
        self.on_status("İstemci durduruldu.")

    def _send(self, payload: dict[str, Any]) -> None:
        data = encode_message(payload)
        with self._sock_lock:
            if self._sock is None:
                return
            try:
                self._sock.sendall(data)
            except OSError:
                pass

    def _on_local_clipboard(self, text: str) -> None:
        self._send({"type": "clipboard", "text": text})

    def send_file(self, name: str, data_b64: str) -> bool:
        """Send a base64-encoded file to the server."""
        with self._sock_lock:
            connected = self._sock is not None
        if not connected:
            return False
        self._send({"type": "file", "name": name, "data": data_b64})
        self.on_status(f"Dosya Mac'e gönderildi: {name}")
        return True

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.on_status(f"Bağlanılıyor: {self.server_host}:{self.port}...")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect((self.server_host, self.port))
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                sock.settimeout(0.5)
                with self._sock_lock:
                    self._sock = sock

                self.on_status(f"Bağlandı: {self.server_host}:{self.port}")
                self._send(
                    {
                        "type": "handshake",
                        "platform": self._local_platform,
                        "screen_w": self._screen_w,
                        "screen_h": self._screen_h,
                        "supports_edge_return": True,
                    }
                )
                self._read_loop(sock)
            except OSError as exc:
                if not self._stop_event.is_set():
                    self.on_status(f"Bağlantı hatası ({exc}); 2 sn içinde yeniden deneniyor...")
                    time.sleep(2.0)
            finally:
                self._remote_active = False
                self._release_all_keys()
                with self._sock_lock:
                    if self._sock is not None:
                        try:
                            self._sock.close()
                        except OSError:
                            pass
                        self._sock = None

    def _read_loop(self, sock: socket.socket) -> None:
        buf = b""
        while not self._stop_event.is_set():
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    self.on_status("Sunucu bağlantıyı kapattı.")
                    break
                buf += chunk
                msgs, buf = decode_messages(buf)
                for msg in msgs:
                    self._handle_message(msg)
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_message(self, msg: dict[str, Any]) -> None:
        mtype = msg.get("type")
        if mtype == "handshake":
            self._server_platform = str(msg.get("platform", "darwin"))
        elif mtype == "switch":
            active = bool(msg.get("active", False))
            self._remote_active = active
            if active:
                self._entry_edge = msg.get("edge")
                self._active_since = time.monotonic()
                if self._mouse_ctrl is not None and self._entry_edge in ("right", "left"):
                    try:
                        y_ratio = float(msg.get("y_ratio", 0.5))
                        ty = int(max(0.0, min(1.0, y_ratio)) * self._screen_h)
                        tx = 8 if self._entry_edge == "right" else max(0, self._screen_w - 9)
                        self._mouse_ctrl.position = (tx, ty)
                    except Exception:
                        pass
                self.on_status("Kontrol AKTİF (Mac üzerinden yönetiliyor)")
            else:
                self._release_all_keys()
                self.on_status("Kontrol Mac'e geri döndü")
        elif mtype == "mouse_move":
            if self._mouse_ctrl is not None:
                dx = int(msg.get("dx", 0))
                dy = int(msg.get("dy", 0))
                self._mouse_ctrl.move(dx, dy)
                if (
                    self._remote_active
                    and self._entry_edge in ("right", "left")
                    and time.monotonic() - self._active_since > 0.4
                ):
                    try:
                        cx, cy = self._mouse_ctrl.position
                        if (self._entry_edge == "right" and dx < 0 and cx <= 2) or (
                            self._entry_edge == "left" and dx > 0 and cx >= self._screen_w - 3
                        ):
                            self._remote_active = False
                            y_ratio = max(0.0, min(1.0, cy / max(1, self._screen_h)))
                            self._send({"type": "return_to_server", "y_ratio": y_ratio})
                    except Exception:
                        pass
        elif mtype == "mouse_click":
            if self._mouse_ctrl is not None:
                btn = self._button_map.get(msg.get("button", "left"), self._button_map["left"])
                if msg.get("pressed", True):
                    self._mouse_ctrl.press(btn)
                else:
                    self._mouse_ctrl.release(btn)
        elif mtype == "mouse_scroll":
            if self._mouse_ctrl is not None:
                self._mouse_ctrl.scroll(int(msg.get("dx", 0)), int(msg.get("dy", 0)))
        elif mtype == "key":
            self._handle_key(msg.get("key", {}), bool(msg.get("pressed", True)))
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

    def _resolve_key(self, key_info: dict[str, Any]) -> Any:
        from pynput import keyboard

        kind = key_info.get("kind")
        val = key_info.get("value")
        if kind == "special" and isinstance(val, str):
            mapped = map_special_key_name(
                val,
                self._server_platform,
                self._local_platform,
                map_cmd_ctrl=self.map_cmd_ctrl,
            )
            return self._special_keys.get(mapped)
        if kind == "char" and isinstance(val, str):
            return val
        if kind == "vk" and isinstance(val, int):
            if self._server_platform != self._local_platform:
                return None
            return keyboard.KeyCode.from_vk(val)
        return None

    def _handle_key(self, key_info: dict[str, Any], pressed: bool) -> None:
        if self._key_ctrl is None:
            return
        target = self._resolve_key(key_info)
        if target is None:
            return
        try:
            if pressed:
                self._key_ctrl.press(target)
                if target not in self._pressed_keys:
                    self._pressed_keys.append(target)
            else:
                self._key_ctrl.release(target)
                if target in self._pressed_keys:
                    self._pressed_keys.remove(target)
        except Exception:
            pass

    def _release_all_keys(self) -> None:
        if self._key_ctrl is None:
            return
        for k in list(self._pressed_keys):
            try:
                self._key_ctrl.release(k)
            except Exception:
                pass
        self._pressed_keys.clear()
