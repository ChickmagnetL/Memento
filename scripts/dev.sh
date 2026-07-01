#!/usr/bin/env bash
# One-command dev launcher for the Memento desktop app.
#
# Starts the frontend (Next dev server) and the Electron shell. Electron's
# main.js spawns the backend (from the venv) and the Douyin fetcher itself;
# the ASR service is NOT started here — the backend lazily spawns it on first
# use (see backend/core/video/asr_supervisor.py).
#
# Ctrl-C (or closing the window) tears down both the frontend and Electron
# process groups so backend sidecars do not linger between runs.
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

echo "==> starting desktop (Electron spawns backend + douyin fetcher; ASR is lazy)"
(cd "$ROOT/desktop" && MEMENTO_BACKEND_CMD="../backend/venv/bin/uvicorn main:app --port 8000" npm start) &
DESKTOP_PID=$!

stop_job() {
  local pid="$1"
  kill -- -"$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
}

cleanup() {
  # Kill each job's entire process group (negative PID) so npm/electron/uvicorn
  # children are reaped too, not just the shell subshell.
  stop_job "$DESKTOP_PID"
  stop_job "$FRONTEND_PID"
}
trap cleanup EXIT INT TERM

wait "$DESKTOP_PID"
