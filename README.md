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
pip install -r requirements-dev.txt
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

## Phase 2C: Bilibili Subtitle Drafts

Phase 2C supports the first real processing slice for saved Bilibili videos.
When a Bilibili record has available soft subtitles, clicking `Process` writes a
Markdown draft to `~/memento_data/knowledge/bilibili/<video_id>.md`, creates a
document metadata row, and marks the video as `completed`.

Old or public Bilibili subtitles may work without a cookie. Bilibili AI
subtitles often require an explicit local cookie. Prefer setting it with an
environment variable for manual testing, then restart the backend:

```bash
export VIDEO_PROCESSING__BILIBILI_COOKIE='SESSDATA=your-cookie; bili_jct=...'
```

Do not commit real cookie values. Cookies carry account privileges; do not
share them, and rotate or invalidate them if leaked. `config.local.yaml` is
acceptable for local overrides, but environment variables are safer for
sensitive cookies.

Unsupported records and Bilibili records without soft subtitles are marked as
`failed` in this phase. Douyin, ASR, OCR, AI cleanup, chunking, and Qdrant
indexing are not part of Phase 2C.

## Project Structure

- `backend/` - FastAPI backend server
- `frontend/` - Next.js frontend application
- `services/` - Independent model services (ASR, Ollama)
- `data/` - User data storage (knowledge base, databases)
