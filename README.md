# ES-Share

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-6-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vite.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-v4-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![shadcn/ui](https://img.shields.io/badge/shadcn%2Fui-Components-000000?style=for-the-badge&logo=shadcnui&logoColor=white)](https://ui.shadcn.com/)
[![macOS & Windows](https://img.shields.io/badge/Platform-macOS%20%E2%86%94%20Windows-10B981?style=for-the-badge)](https://github.com/erlserter/es-share)

A lightweight software KVM with a modern web dashboard that lets you share a single keyboard and mouse between **Mac (Main PC) ↔ Windows** over your local network (Wi-Fi / Ethernet).

## Features

- **Single Keyboard & Mouse Sharing:** Low-latency TCP (`TCP_NODELAY`) input streaming with resolution-independent relative mouse deltas.
- **Smart Edge Switching & Cursor Lock:** Move your cursor across the shared screen edge to switch between Mac and Windows automatically; the Mac cursor stays locked in place while controlling Windows.
- **Instant Return Shortcuts:** Press `Ctrl + Alt + S` or tap `Esc` 3 times within 1 second (`3× Esc`) to jump back to Mac anytime.
- **Automatic Key Mapping:** Maps Mac `Cmd` ↔ Windows `Ctrl` shortcuts automatically and releases held keys when switching or disconnecting.
- **Bidirectional Clipboard Sync (Copy–Paste):** Zero-dependency plain-text clipboard sync between Mac (`pbcopy`/`pbpaste`) and Windows (`ctypes` Win32 Clipboard API).
- **Drag-and-Drop File Transfer:** Drop files or images directly onto the monitor cards in the web UI to send them to `~/Downloads/ES-Share` on the target computer.
- **Modern `shadcn/ui` Dashboard:** Visual dual-display desk canvas with live status badges, theme toggle (`light`/`dark`), and real-time activity logs.

---

## Requirements

- **Python 3.10+** (on both Mac and Windows)
- **Node.js 20+** *(only needed if rebuilding the `ui/` frontend)*

---

## Quick Start

### 1. Mac (Main PC / Server)

```bash
git clone https://github.com/erlserter/es-share.git
cd es-share

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Build the web dashboard
cd ui && npm install && npm run build && cd ..
```

Start the server:
- Double-click **`Mac_Baslat.command`** *(recommended on macOS — launches inside `Terminal.app` so Accessibility permissions are inherited cleanly)*, or
- Run from Terminal:
  ```bash
  .venv/bin/python app.py
  ```

Open **`http://127.0.0.1:8765`**, click **Sunucuyu Başlat** (Start Server), and note your Mac's local IP address.

### 2. Windows (Connected Device / Client)

Copy the repository to your Windows machine and install the Python dependency:

```bat
pip install -r requirements.txt
```

- **With Web Dashboard:**
  ```bat
  python app.py
  ```
  Switch to the **Windows (Client)** tab, enter your Mac's IP address, and click **Mac'e Bağlan**. You can also drag and drop files/images in this tab to send them to your Mac.

- **Direct CLI Mode:**
  ```bat
  python app.py client --host <MAC_IP_ADDRESS>
  ```

### Building a Standalone Windows `.exe` (Optional)

On a Windows machine with Python installed, double-click `build_windows.bat` or run:

```bat
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --onefile --name ES-Share --add-data "ui\dist;ui\dist" --hidden-import=pynput.keyboard._win32 --hidden-import=pynput.mouse._win32 app.py
```

The standalone executable will be generated at `dist\ES-Share.exe`.

---

## Permissions & Security

- **macOS Accessibility:** On first run, grant permission under **System Settings > Privacy & Security > Accessibility** for **Terminal** (and **Python.app** if using Homebrew Python).
- **Windows Firewall:** Allow access on **Private networks** when prompted (default port: `24800`).
- **Network Security:** ES-Share is designed for trusted local networks (home/office Wi-Fi) and uses unencrypted TCP sockets. Do not expose port `24800` to the public internet.

---

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```
