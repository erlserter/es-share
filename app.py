"""ES-Share: Web UI & CLI launcher for Mac <-> Windows keyboard/mouse sharing."""

from __future__ import annotations

import argparse
import sys
import time

from client import KVMClient
from protocol import DEFAULT_PORT, get_local_ips
from server import KVMServer
from web_ui import serve_web_ui


def run_cli(args: argparse.Namespace) -> int:
    """Run in headless CLI mode."""
    if args.mode == "server":
        ips = ", ".join(get_local_ips())
        print(f"Yerel IP adresleri: {ips}")
        print(f"Geçiş kısayolu: Ctrl+Alt+S | Ekran kenarı: {args.edge}")
        srv = KVMServer(
            port=args.port,
            edge_switch=None if args.edge == "none" else args.edge,
            on_status=lambda msg: print(f"[SERVER] {msg}", flush=True),
        )
        srv.start()
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            srv.stop()
        return 0

    if args.mode == "client":
        if not args.host:
            print("Hata: İstemci modu için --host <SUNUCU_IP> gerekli.", file=sys.stderr)
            return 1
        cli = KVMClient(
            server_host=args.host,
            port=args.port,
            map_cmd_ctrl=not args.no_cmd_ctrl_map,
            on_status=lambda msg: print(f"[CLIENT] {msg}", flush=True),
        )
        cli.start()
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            cli.stop()
        return 0

    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ES-Share — Mac & Windows klavye/fare paylaşımı")
    parser.add_argument("--ui-port", type=int, default=8765, help="Web arayüz portu")
    parser.add_argument("--no-browser", action="store_true", help="Tarayıcıyı otomatik açma")
    sub = parser.add_subparsers(dest="mode")

    p_srv = sub.add_parser("server", help="Ana bilgisayar (klavye/fare bağlı)")
    p_srv.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_srv.add_argument("--edge", choices=["right", "left", "none"], default="right")

    p_cli = sub.add_parser("client", help="Diğer bilgisayar")
    p_cli.add_argument("--host", required=True, help="Sunucu IP adresi")
    p_cli.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_cli.add_argument("--no-cmd-ctrl-map", action="store_true")

    args = parser.parse_args()
    if args.mode in ("server", "client"):
        return run_cli(args)

    serve_web_ui(ui_port=args.ui_port, open_browser=not args.no_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
