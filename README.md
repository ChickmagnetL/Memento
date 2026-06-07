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

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Project Structure

- `backend/` - FastAPI backend server
- `frontend/` - Next.js frontend application  
- `services/` - Independent model services (ASR, Ollama)
- `data/` - User data storage (knowledge base, databases)
