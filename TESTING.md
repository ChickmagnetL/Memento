# Manual E2E Testing - Phase 1

## Prerequisites

- Python 3.10+ installed
- Node.js 18+ installed
- Backend dependencies installed (`cd backend && pip install -r requirements.txt`)
- Frontend dependencies installed (`cd frontend && npm install`)

## Test Procedure

### 1. Start Backend

Terminal 1:
```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
uvicorn main:app --port 8000
```

Expected: Server starts with log message "Databases initialized at ..."

### 2. Start Frontend

Terminal 2:
```bash
cd frontend
npm run dev
```

Expected: Dev server starts on http://localhost:3000

### 3. Verify Frontend

Open browser: http://localhost:3000

Expected:
- Page displays "Memento" title
- Shows "Backend health: ok"

### 4. Verify Backend API Docs

Open browser: http://localhost:8000/docs

Expected:
- Swagger UI loads successfully
- Shows `/api/health` endpoint
- Can execute the endpoint and receive `{"status":"ok","service":"memento-backend"}`

## Phase 1 Acceptance Criteria

- [x] Frontend accessible at http://localhost:3000
- [x] Backend API docs at http://localhost:8000/docs
- [x] Health check endpoint returns 200
- [x] Configuration loads from YAML
- [x] Databases initialize without errors

All criteria verified ✓
