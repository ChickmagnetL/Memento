# Manual E2E Testing - Phase 1

## Prerequisites

- Python 3.10+ installed
- Node.js 18+ installed
- Backend dependencies installed (`cd backend && pip install -r requirements-dev.txt`)
- Frontend dependencies installed (`cd frontend && npm install`)

## Automated Checks

From the project root:

```bash
cd backend
source venv/bin/activate
pytest

cd ../frontend
npm run lint

cd ..
./scripts/smoke-test.sh
```

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

All criteria should be verified with the automated checks above plus the manual browser checks.

## Phase 2A Checks

1. Start backend: `cd backend && source venv/bin/activate && uvicorn main:app --port 8000`
2. Start frontend: `cd frontend && npm run dev`
3. Open http://localhost:3000
4. Submit `https://www.bilibili.com/video/BV1234567890`
5. Expected: a pending Bilibili record appears and remains after refresh.
6. Submit `https://example.com/video/1`
7. Expected: unsupported URL error appears.

## Phase 2B Checks

Run automated checks from the project root:

```bash
cd backend
source venv/bin/activate
pytest

cd ../frontend
npm run lint
```

1. Start backend: `cd backend && source venv/bin/activate && uvicorn main:app --port 8000`
2. Start frontend: `cd frontend && npm run dev`
3. Open http://localhost:3000
4. Submit `https://www.bilibili.com/video/BV1234567890`
5. Use the processing action on the saved record.
6. Expected: the record status changes to `completed`.
7. Expected: real subtitle extraction, video download, ASR, and OCR are not required for Phase 2B.
