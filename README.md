# Memento

Video content to searchable knowledge base assistant.

## Quick Start

### Prerequisites

- Python 3.10+
- Node 18+
- [ffmpeg](https://ffmpeg.org) — required for audio extraction (`brew install ffmpeg` on macOS)
- `jq` — optional, used by the smoke-test script

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Audio extraction requires [ffmpeg](https://ffmpeg.org) (`brew install ffmpeg` on macOS).

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 once both servers are running.

### 3. ASR Service (optional)

Only needed for videos that have no subtitles. See
[`services/asr/README.md`](services/asr/README.md) for install and startup
instructions. Videos with soft subtitles skip ASR entirely.

### 4. Model Configuration

Copy the example config and edit it:

```bash
cp config.example.yaml config.local.yaml
```

Configure both a **chat** model and an **embedding** model — both are required.
Alternatively, use the in-app **Settings** page to configure them at runtime.
See [Ollama (Local Models)](#ollama-local-models) below to use local models.

### 5. First Video

1. Open **Video Intake**, paste a Bilibili or Douyin URL, click *Add video*.
2. Click *Process* to extract subtitles (or ASR-transcribe audio).
3. Go to **Knowledge Base**, select the generated document, click *Index* to
   vectorize it.
4. Go to **Chat** and ask questions about the indexed content.

### 6. Test & Smoke

Backend tests:

```bash
cd backend
source venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Frontend lint:

```bash
cd frontend
npm run lint
```

Phase 1 smoke test from the project root:

```bash
./scripts/smoke-test.sh
```

> Tip: an in-app tutorial is available at **Help** in the sidebar (or `/help`).

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

## Ollama (Local Models)

Set `provider: "ollama"` in `config.local.yaml` under `models.chat` and/or
`models.embedding` to use local Ollama models instead of cloud APIs.

Example `config.local.yaml`:

```yaml
models:
  chat:
    endpoint: "http://localhost:11434/v1"
    api_key: "ollama"
    model: "qwen3"
  embedding:
    provider: "ollama"
    model: "qwen3-embedding:0.6b"
```

Pull the models first:

```bash
ollama pull qwen3
ollama pull qwen3-embedding:0.6b
```

**Switching embedding models:** Different embedding models output different
vector dimensions. When switching models, you MUST update `rag.vector_size` in
`config.local.yaml` to match (e.g. `qwen3-embedding:0.6b` outputs 1024-dim
vectors), then delete `data/qdrant/` and re-index all documents. Restart the
backend after making these changes.
