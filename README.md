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

## Project Structure

- `backend/` - FastAPI backend server
- `frontend/` - Next.js frontend application
- `services/` - Independent model services (ASR, Ollama)
- `data/` - User data storage (knowledge base, databases)
