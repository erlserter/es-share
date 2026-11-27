"""Local Web Dashboard UI server for ES-Share (Mac Main PC <-> Windows)."""

from __future__ import annotations

import json
import mimetypes
import platform
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from client import KVMClient
from protocol import DEFAULT_PORT, get_local_ips
from server import KVMServer, _get_screen_size, check_accessibility_trusted

_BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
DIST_DIR = _BASE_DIR / "ui" / "dist"


FALLBACK_HTML = """<!DOCTYPE html>
<html lang="tr">
<head><meta charset="UTF-8" /><title>ES-Share — Mac &amp; Windows</title></head>
<body style="font-family:sans-serif;background:#0b0f19;color:#e5e7eb;padding:32px">
  <h1>ES-Share</h1>
  <p>Derlenmiş UI bulunamadı (<code>ui/dist</code>). Lütfen <code>ui/</code> içinde <code>npm run build</code> çalıştırın.</p>
</body>
</html>
"""


class ControllerState:
    """Thread-safe controller managing the active KVMServer or KVMClient."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.mode: str | None = None
        self.instance: KVMServer | KVMClient | None = None
        self.logs: list[str] = ["Arayüz hazır. Mac ana bilgisayar olarak seçili."]

    def add_log(self, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        with self._lock:
            self.logs.append(f"[{ts}] {msg}")
            if len(self.logs) > 80:
                self.logs = self.logs[-80:]

    def start(self, data: dict[str, Any]) -> dict[str, Any]:
        self.stop()
        mode = data.get("mode", "server")
        port = int(data.get("port", DEFAULT_PORT))

        with self._lock:
            try:
                if mode == "server":
                    edge = data.get("edge", "right")
                    srv = KVMServer(
                        port=port,
                        edge_switch=None if edge == "none" else edge,
                        on_status=self.add_log,
                    )
                    srv.start()
                    self.instance = srv
                    self.mode = "server"
                else:
                    host = str(data.get("host", "")).strip()
                    cli = KVMClient(
                        server_host=host,
                        port=port,
                        map_cmd_ctrl=bool(data.get("map_cmd_ctrl", True)),
                        on_status=self.add_log,
                    )
                    cli.start()
                    self.instance = cli
                    self.mode = "client"
            except Exception as exc:
                self.add_log(f"HATA: Başlatılamadı ({exc})")
                self.instance = None
                self.mode = None

        return self.status()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if self.instance is not None:
                try:
                    self.instance.stop()
                except Exception:
                    pass
                self.instance = None
            self.mode = None
        return self.status()

    def toggle(self) -> dict[str, Any]:
        with self._lock:
            if isinstance(self.instance, KVMServer):
                self.instance.toggle_mode()
        return self.status()

    def set_edge(self, edge: str | None) -> dict[str, Any]:
        with self._lock:
            if isinstance(self.instance, KVMServer):
                self.instance.edge_switch = None if edge == "none" else edge
                self.add_log(f"Ekran kenarı güncellendi: {edge or 'none'}")
        return self.status()

    def test_mouse(self) -> bool:
        with self._lock:
            if isinstance(self.instance, KVMServer):
                return self.instance.send_test_mouse()
        return False

    def send_file(self, name: str, data_b64: str) -> bool:
        with self._lock:
            if isinstance(self.instance, (KVMServer, KVMClient)):
                return self.instance.send_file(name, data_b64)
        return False

    def open_accessibility(self) -> None:
        if platform.system().lower() == "darwin":
            check_accessibility_trusted(prompt=True)
            try:
                subprocess.Popen(
                    [
                        "open",
                        "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
                    ]
                )
            except Exception:
                pass
            self.add_log("macOS Erişilebilirlik ayarları açıldı.")

    def status(self) -> dict[str, Any]:
        with self._lock:
            running = self.instance is not None
            remote_active = (
                self.instance.remote_active
                if isinstance(self.instance, KVMServer)
                else False
            )
            client_connected = (
                self.instance._has_client()
                if isinstance(self.instance, KVMServer)
                else False
            )
            screen_size = (
                list(self.instance.screen_size)
                if isinstance(self.instance, KVMServer)
                else list(_get_screen_size())
            )
            return {
                "running": running,
                "mode": self.mode,
                "remote_active": remote_active,
                "client_connected": client_connected,
                "local_ips": get_local_ips(),
                "accessibility_trusted": check_accessibility_trusted(False),
                "platform": platform.system().lower(),
                "screen_size": screen_size,
                "logs": list(self.logs),
            }


def serve_web_ui(ui_port: int = 8765, open_browser: bool = True) -> None:
    """Start the local HTTP dashboard server."""
    state = ControllerState()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_json(self, payload: dict[str, Any], code: int = 200) -> None:
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            req_path = urlsplit(self.path).path
            if req_path == "/api/status":
                self._send_json(state.status())
                return

            dist_index = DIST_DIR / "index.html"
            if DIST_DIR.is_dir() and dist_index.is_file():
                dist_root = DIST_DIR.resolve()
                if req_path in ("", "/"):
                    target = dist_index
                else:
                    candidate = (DIST_DIR / req_path.lstrip("/")).resolve()
                    if candidate.is_relative_to(dist_root) and candidate.is_file():
                        target = candidate
                    elif not req_path.startswith("/assets/"):
                        target = dist_index
                    else:
                        self._send_json({"error": "Not found"}, code=404)
                        return

                raw = target.read_bytes()
                ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
                if ctype.startswith("text/") or ctype == "application/javascript":
                    ctype = f"{ctype}; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return

            raw = FALLBACK_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                data = {}

            if self.path == "/api/start":
                self._send_json(state.start(data))
            elif self.path == "/api/stop":
                self._send_json(state.stop())
            elif self.path == "/api/toggle":
                self._send_json(state.toggle())
            elif self.path == "/api/edge":
                state.set_edge(data.get("edge"))
                self._send_json(state.status())
            elif self.path == "/api/test-mouse":
                ok = state.test_mouse()
                st = state.status()
                st["test_sent"] = ok
                self._send_json(st)
            elif self.path == "/api/send-file":
                name = str(data.get("name", "dosya"))
                data_b64 = str(data.get("data", ""))
                ok = state.send_file(name, data_b64) if data_b64 else False
                st = state.status()
                st["file_sent"] = ok
                self._send_json(st)
            elif self.path == "/api/open-accessibility":
                state.open_accessibility()
                self._send_json(state.status())
            else:
                self._send_json({"error": "Not found"}, code=404)

    httpd = ThreadingHTTPServer(("127.0.0.1", ui_port), Handler)
    url = f"http://127.0.0.1:{ui_port}"
    print(f"ES-Share Arayüzü çalışıyor: {url}", flush=True)

    if open_browser:
        import webbrowser

        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        state.stop()
        httpd.server_close()
