#!/bin/bash
set -e

echo "=== Phase 1 Integration Smoke Test ==="
echo

# Start backend
cd /Users/leo/development/memento/backend
source venv/bin/activate
uvicorn main:app --port 8000 &
SERVER_PID=$!
cd /Users/leo/development/memento

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
    kill $SERVER_PID 2>/dev/null || true
    exit 1
fi

# Test frontend API client can reach backend
echo
echo "2. Testing frontend API client..."
cd /Users/leo/development/memento/frontend
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
cd /Users/leo/development/memento

# Cleanup
kill $SERVER_PID 2>/dev/null || true
wait $SERVER_PID 2>/dev/null || true

if [ $FRONTEND_TEST_EXIT -eq 0 ]; then
    echo
    echo "=== Smoke Test Passed ==="
    exit 0
else
    echo
    echo "=== Smoke Test Failed ==="
    exit 1
fi
