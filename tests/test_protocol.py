"""Unit tests for ES-Share protocol, key mapping, server hotkey, and Web UI state."""

from __future__ import annotations

import base64
from pathlib import Path
import tempfile
import time
import types
import unittest

from client import KVMClient
from clipboard_sync import ClipboardWatcher
from protocol import (
    decode_messages,
    encode_message,
    map_special_key_name,
    normalize_char_key,
    save_incoming_file,
    serialize_key,
)
from server import KVMServer
import web_ui
from web_ui import ControllerState


class TestProtocol(unittest.TestCase):
    def test_encode_decode_roundtrip_and_partial_buffer(self) -> None:
        m1 = {"type": "mouse_move", "dx": 12, "dy": -5}
        m2 = {"type": "mouse_click", "button": "left", "pressed": True}
        raw = encode_message(m1) + encode_message(m2)

        msgs1, rem1 = decode_messages(raw[:10])
        self.assertEqual(msgs1, [])

        msgs2, rem2 = decode_messages(rem1 + raw[10:])
        self.assertEqual(msgs2, [m1, m2])
        self.assertEqual(rem2, b"")

    def test_decode_ignores_invalid_json_lines(self) -> None:
        raw = b"not-json\n" + encode_message({"type": "switch", "active": True})
        msgs, rem = decode_messages(raw)
        self.assertEqual(msgs, [{"type": "switch", "active": True}])
        self.assertEqual(rem, b"")

    def test_map_special_key_name(self) -> None:
        self.assertEqual(map_special_key_name("cmd", "darwin", "windows", True), "ctrl")
        self.assertEqual(map_special_key_name("cmd_l", "darwin", "windows", True), "ctrl_l")
        self.assertEqual(map_special_key_name("ctrl", "windows", "darwin", True), "cmd")
        self.assertEqual(map_special_key_name("cmd", "darwin", "windows", False), "cmd")
        self.assertEqual(map_special_key_name("enter", "darwin", "windows", True), "enter")

    def test_normalize_char_key_and_serialize(self) -> None:
        self.assertEqual(normalize_char_key("\x03"), "c")
        self.assertEqual(normalize_char_key("\x13"), "s")
        self.assertEqual(normalize_char_key("x"), "x")

        special = types.SimpleNamespace(name="shift")
        self.assertEqual(serialize_key(special), {"kind": "special", "value": "shift"})

        char_key = types.SimpleNamespace(char="\x03", vk=8)
        self.assertEqual(serialize_key(char_key), {"kind": "char", "value": "c", "vk": 8})

        vk_only = types.SimpleNamespace(char=None, vk=123)
        self.assertEqual(serialize_key(vk_only), {"kind": "vk", "value": 123})


class TestServerAndClient(unittest.TestCase):
    def test_check_hotkey_macos_and_windows(self) -> None:
        srv = KVMServer()
        srv._pressed_modifiers = {"ctrl_l", "alt_l"}

        srv._is_darwin = True
        self.assertTrue(srv._check_hotkey({"kind": "char", "value": "ß", "vk": 1}))
        self.assertTrue(srv._check_hotkey({"kind": "char", "value": "\x13", "vk": 1}))
        self.assertTrue(srv._check_hotkey({"kind": "vk", "value": 1}))
        self.assertFalse(srv._check_hotkey({"kind": "char", "value": "a", "vk": 0}))

        srv._is_darwin = False
        self.assertTrue(srv._check_hotkey({"kind": "char", "value": "s", "vk": 83}))
        self.assertTrue(srv._check_hotkey({"kind": "vk", "value": 83}))

        srv._pressed_modifiers = {"ctrl_l"}
        self.assertFalse(srv._check_hotkey({"kind": "char", "value": "s", "vk": 83}))

    def test_client_ignores_foreign_platform_vk(self) -> None:
        cli = KVMClient("127.0.0.1")
        cli._server_platform = "darwin"
        cli._local_platform = "windows"
        self.assertIsNone(cli._resolve_key({"kind": "vk", "value": 8}))

    def test_controller_state_status_fields(self) -> None:
        state = ControllerState()
        st = state.status()
        self.assertIn("accessibility_trusted", st)
        self.assertIn("platform", st)
        self.assertIn("screen_size", st)
        self.assertEqual(len(st["screen_size"]), 2)
        self.assertFalse(state.test_mouse())

    def test_triple_esc_exits_remote_mode(self) -> None:
        srv = KVMServer()
        srv._is_darwin = False
        srv._remote_active = True
        srv._send = lambda payload: None  # type: ignore[method-assign]

        esc = types.SimpleNamespace(name="esc")
        srv._on_key_press(esc)
        self.assertTrue(srv.remote_active)
        srv._on_key_press(esc)
        self.assertTrue(srv.remote_active)
        srv._on_key_press(esc)
        self.assertFalse(srv.remote_active)

    def test_cursor_lock_noop_on_non_darwin(self) -> None:
        srv = KVMServer()
        srv._is_darwin = False
        srv._set_darwin_cursor_locked(True)
        self.assertFalse(srv._cursor_locked)
        srv._set_darwin_cursor_locked(False)
        self.assertFalse(srv._cursor_locked)

    def test_virtual_edge_return_fallback(self) -> None:
        srv = KVMServer(edge_switch="right")
        srv._client_supports_edge_return = False
        srv._remote_screen_w = 1920
        srv._virtual_x = 120.0
        srv._last_switch_ts = time.monotonic() - 1.0

        self.assertFalse(srv._check_virtual_edge_return(2500))
        self.assertEqual(srv._virtual_x, 1920.0)

        self.assertFalse(srv._check_virtual_edge_return(-1000))
        self.assertTrue(srv._check_virtual_edge_return(-1000))

        srv.edge_switch = "left"
        srv._virtual_x = 1800.0
        self.assertFalse(srv._check_virtual_edge_return(-2000))
        self.assertEqual(srv._virtual_x, 0.0)
        self.assertTrue(srv._check_virtual_edge_return(2000))

        srv._last_switch_ts = time.monotonic()
        self.assertFalse(srv._check_virtual_edge_return(2000))
        srv._last_switch_ts = time.monotonic() - 1.0
        srv._client_supports_edge_return = True
        self.assertFalse(srv._check_virtual_edge_return(2000))

    def test_client_exact_edge_return_message(self) -> None:
        cli = KVMClient("127.0.0.1")
        cli._screen_w = 1920
        cli._screen_h = 1080
        sent: list[dict] = []
        cli._send = sent.append  # type: ignore[method-assign]

        class DummyMouse:
            def __init__(self) -> None:
                self.position = (100, 540)

            def move(self, dx: int, dy: int) -> None:
                x, y = self.position
                self.position = (max(0, x + dx), max(0, y + dy))

        cli._mouse_ctrl = DummyMouse()
        cli._handle_message({"type": "switch", "active": True, "edge": "right", "y_ratio": 0.5})
        self.assertEqual(cli._mouse_ctrl.position, (8, 540))

        cli._active_since = time.monotonic() - 1.0
        cli._handle_message({"type": "mouse_move", "dx": -15, "dy": 0})
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["type"], "return_to_server")
        self.assertAlmostEqual(sent[0]["y_ratio"], 0.5, places=2)
        self.assertFalse(cli._remote_active)

    def test_compiled_shadcn_ui_exists(self) -> None:
        self.assertTrue((web_ui.DIST_DIR / "index.html").is_file())

    def test_save_incoming_file_and_unique_naming(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest_dir = Path(tmp)
            payload = base64.b64encode(b"hello es-share").decode("ascii")
            p1 = save_incoming_file("../../secret.txt", payload, target_dir=dest_dir)
            p2 = save_incoming_file("secret.txt", payload, target_dir=dest_dir)
            self.assertEqual(p1.name, "secret.txt")
            self.assertEqual(p2.name, "secret (1).txt")
            self.assertEqual(p1.read_bytes(), b"hello es-share")
            self.assertEqual(p2.read_bytes(), b"hello es-share")

    def test_clipboard_watcher_apply_remote_prevents_echo(self) -> None:
        seen: list[str] = []
        watcher = ClipboardWatcher(on_change=seen.append)
        watcher._last_text = "abc"
        watcher.apply_remote("abc")
        self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main()
