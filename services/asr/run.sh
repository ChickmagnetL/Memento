#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ASR_HOST="${ASR_HOST:-0.0.0.0}"
export ASR_PORT="${ASR_PORT:-8001}"
export ASR_DEVICE="${ASR_DEVICE:-cpu}"

exec "$ROOT_DIR/.venv/bin/uvicorn" server:app --host "$ASR_HOST" --port "$ASR_PORT" --app-dir "$ROOT_DIR"
