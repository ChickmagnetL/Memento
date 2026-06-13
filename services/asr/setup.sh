#!/usr/bin/env bash
# Create the isolated ASR service environment (mirrors phase0 setup_asr_env.sh).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements.txt"

echo "ASR service env ready. Start with:"
echo "  $VENV_DIR/bin/uvicorn server:app --port 8001 --app-dir $ROOT_DIR"
