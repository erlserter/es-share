#!/bin/bash
cd "$(dirname "$0")"
echo "ES-Share (Mac Ana Bilgisayar) baslatiliyor..."
exec .venv/bin/python app.py --ui-port 8765

