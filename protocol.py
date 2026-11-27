"""Network protocol, file saving, and cross-platform key mapping for ES-Share."""

from __future__ import annotations

import base64
import json
import socket
from pathlib import Path
from typing import Any


DEFAULT_PORT = 24800


def get_local_ips() -> list[str]:
    """Return non-loopback IPv4 addresses of this machine."""
    ips: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            primary = s.getsockname()[0]
            if primary and not primary.startswith("127."):
                ips.append(primary)
    except OSError:
        pass

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass

    return ips or ["127.0.0.1"]


def encode_message(payload: dict[str, Any]) -> bytes:
    """Serialize a message dict as newline-delimited UTF-8 JSON."""
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")


def decode_messages(buffer: bytes) -> tuple[list[dict[str, Any]], bytes]:
    """Split newline-delimited JSON messages from a byte buffer."""
    messages: list[dict[str, Any]] = []
    while b"\n" in buffer:
        line, buffer = buffer.split(b"\n", 1)
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line.decode("utf-8"))
            if isinstance(obj, dict):
                messages.append(obj)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return messages, buffer


MAC_TO_WIN_SPECIAL = {
    "cmd": "ctrl",
    "cmd_l": "ctrl_l",
    "cmd_r": "ctrl_r",
}

WIN_TO_MAC_SPECIAL = {
    "ctrl": "cmd",
    "ctrl_l": "cmd_l",
    "ctrl_r": "cmd_r",
}


def map_special_key_name(
    name: str,
    source_platform: str,
    target_platform: str,
    map_cmd_ctrl: bool = True,
) -> str:
    """Map special key names across platforms (e.g. Mac Cmd <-> Windows Ctrl)."""
    if not map_cmd_ctrl:
        return name
    src = source_platform.lower()
    dst = target_platform.lower()
    if src == "darwin" and dst == "windows":
        return MAC_TO_WIN_SPECIAL.get(name, name)
    if src == "windows" and dst == "darwin":
        return WIN_TO_MAC_SPECIAL.get(name, name)
    return name


def normalize_char_key(char: str) -> str:
    """Convert ASCII control characters (Ctrl+A..Z) back to lowercase letters."""
    if len(char) == 1:
        code = ord(char)
        if 1 <= code <= 26:
            return chr(code + 96)
    return char


def serialize_key(key: Any) -> dict[str, Any] | None:
    """Convert a pynput Key or KeyCode into a JSON-serializable dict."""
    name = getattr(key, "name", None)
    if name is not None:
        return {"kind": "special", "value": str(name)}

    char = getattr(key, "char", None)
    vk = getattr(key, "vk", None)
    if char is not None:
        return {"kind": "char", "value": normalize_char_key(str(char)), "vk": vk}
    if vk is not None:
        return {"kind": "vk", "value": int(vk)}
    return None


def save_incoming_file(
    name: str,
    data_b64: str,
    target_dir: Path | None = None,
) -> Path:
    """Decode a base64 file payload and save it safely into Downloads/ES-Share."""
    safe_name = Path(name or "dosya").name.strip() or "dosya"
    dest_dir = target_dir or (Path.home() / "Downloads" / "ES-Share")
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / safe_name
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        idx = 1
        while dest.exists():
            dest = dest_dir / f"{stem} ({idx}){suffix}"
            idx += 1

    raw = base64.b64decode(data_b64.encode("ascii"))
    dest.write_bytes(raw)
    return dest
