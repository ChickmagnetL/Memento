#!/usr/bin/env bash
# One-command dev launcher for the Memento desktop app.
#
# Starts the frontend (Next dev server) and the Electron shell. Electron's
# main.js spawns the backend (from the venv) and the Douyin fetcher itself;
# the ASR service is NOT started here — the backend lazily spawns it on first
# use (see backend/core/video/asr_supervisor.py).
#
# Ctrl-C (or closing the window) tears down the frontend; Electron tears down
# the backend and Douyin fetcher on exit.
set -euo pipefail
set -m  # job control: each background job gets its own process group, so the
        # trap below can kill the whole frontend tree (npm + next + workers).

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# 1. Ensure desktop dependencies are installed (one-time).
if [ ! -d "$ROOT/desktop/node_modules" ]; then
  echo "==> installing desktop dependencies (one-time)"
  (cd "$ROOT/desktop" && npm install)
fi

# 2. Start the frontend dev server in the background.
echo "==> starting frontend (next dev)"
(cd "$ROOT/frontend" && npm run dev) &
FRONTEND_PID=$!

cleanup() {
  # Kill the frontend's entire process group (negative PID) so the next dev
  # worker spawned under npm is reaped too, not just the subshell.
  kill -- -"$FRONTEND_PID" 2>/dev/null || true
  wait "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# 3. Start Electron. It spawns the backend + Douyin fetcher and waits for the
#    backend health endpoint before opening the window.
echo "==> starting desktop (Electron spawns backend + douyin fetcher; ASR is lazy)"
cd "$ROOT/desktop"
MEMENTO_BACKEND_CMD="../backend/venv/bin/uvicorn main:app --port 8000" npm start
