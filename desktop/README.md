# Memento Desktop Shell

## Dev Mode Quick Start

1. Build backend: `./scripts/build-backend.sh`
   Or use venv uvicorn: `export MEMENTO_BACKEND_CMD="../backend/venv/bin/uvicorn main:app --port 8000"`
2. Start frontend: `cd frontend && npm run dev`
3. Start desktop: `cd desktop && npm start`
