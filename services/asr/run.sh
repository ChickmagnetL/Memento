#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST="${ASR_HOST:-0.0.0.0}"
PORT="${ASR_PORT:-8001}"

exec "$ROOT_DIR/.venv/bin/uvicorn" server:app --host "$HOST" --port "$PORT" --app-dir "$ROOT_DIR"
