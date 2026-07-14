#!/usr/bin/env bash
# Package the Douyin fetcher as an independent desktop sidecar.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/services/douyin_fetcher"

PYTHON="$ROOT/backend/venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python"
fi
if [ ! -d .packaging-venv ]; then
  "$PYTHON" -m venv .packaging-venv
fi
.packaging-venv/bin/pip install -r requirements.txt pyinstaller
.packaging-venv/bin/pyinstaller --noconfirm --onedir --name memento-douyin-fetcher \
  --paths . \
  --collect-all f2 \
  desktop_entry.py

echo "Built: services/douyin_fetcher/dist/memento-douyin-fetcher/"
