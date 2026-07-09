#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export EMBEDDING_HOST="${EMBEDDING_HOST:-0.0.0.0}"
export EMBEDDING_PORT="${EMBEDDING_PORT:-8003}"
export EMBEDDING_DEVICE="${EMBEDDING_DEVICE:-cpu}"

exec "$ROOT_DIR/.venv/bin/uvicorn" server:app --host "$EMBEDDING_HOST" --port "$EMBEDDING_PORT" --app-dir "$ROOT_DIR"