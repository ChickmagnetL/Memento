#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_PID=""
TEMP_HOME=""

cleanup() {
    if [ -n "$SERVER_PID" ]; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
    if [ -n "$TEMP_HOME" ]; then
        rm -rf "$TEMP_HOME"
    fi
}

trap cleanup EXIT

echo "=== Phase 1 Integration Smoke Test ==="
echo

# Start backend
TEMP_HOME="$(mktemp -d)"
cd "$ROOT_DIR/backend"
source venv/bin/activate
export HOME="$TEMP_HOME"

python - <<'PY'
import socket
import sys

sock = socket.socket()
try:
    sock.bind(("127.0.0.1", 8000))
except OSError as exc:
    print(f"Cannot bind port 8000: {exc}", file=sys.stderr)
    sys.exit(1)
finally:
    sock.close()
PY

uvicorn main:app --port 8000 &
SERVER_PID=$!
cd "$ROOT_DIR"

# Wait for backend to start
echo "Starting backend..."
sleep 5

# Test backend health endpoint directly
echo "1. Testing backend health endpoint..."
HEALTH_RESPONSE=$(curl -s http://localhost:8000/api/health)
echo "   Response: $HEALTH_RESPONSE"

if echo "$HEALTH_RESPONSE" | grep -q '"status":"ok"'; then
    echo "   ✓ Backend health check passed"
else
    echo "   ✗ Backend health check failed"
    exit 1
fi

# Test backend API docs
echo
echo "2. Testing backend API docs..."
DOCS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs)
echo "   Status: $DOCS_STATUS"

if [ "$DOCS_STATUS" = "200" ]; then
    echo "   ✓ Backend API docs reachable"
else
    echo "   ✗ Backend API docs unreachable"
    exit 1
fi

# Test frontend API client can reach backend
echo
echo "3. Testing frontend API client..."
cd "$ROOT_DIR/frontend"
node -e "
fetch('http://localhost:8000/api/health')
  .then(r => r.json())
  .then(d => {
    console.log('   Response:', JSON.stringify(d));
    if (d.status === 'ok') {
      console.log('   ✓ Frontend API client can reach backend');
      process.exit(0);
    } else {
      console.log('   ✗ Unexpected response');
      process.exit(1);
    }
  })
  .catch(e => {
    console.error('   ✗ Error:', e.message);
    process.exit(1);
  });
"
FRONTEND_TEST_EXIT=$?

if [ $FRONTEND_TEST_EXIT -eq 0 ]; then
    echo
    echo "=== Smoke Test Passed ==="
    exit 0
else
    echo
    echo "=== Smoke Test Failed ==="
    exit 1
fi
