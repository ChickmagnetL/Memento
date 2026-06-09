# Memento

Video content to searchable knowledge base assistant.

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Run backend tests:

```bash
cd backend
source venv/bin/activate
pytest
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Run frontend lint:

```bash
cd frontend
npm run lint
```

Run the Phase 1 smoke test from the project root:

```bash
./scripts/smoke-test.sh
```

## Phase 2A: Video Intake

With backend and frontend running, open http://localhost:3000 and submit a
Bilibili or Douyin URL. The app creates a pending SQLite video record and
displays it in the video list.

## Phase 2B: Video Processing Workflow

After submitting a Bilibili or Douyin URL, use the processing action on the
saved video record. Phase 2B updates the record status to `completed`.

Real subtitle extraction, video download, ASR, and OCR are outside the Phase 2B
scope.

## Project Structure

- `backend/` - FastAPI backend server
- `frontend/` - Next.js frontend application
- `services/` - Independent model services (ASR, Ollama)
- `data/` - User data storage (knowledge base, databases)
