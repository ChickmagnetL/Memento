"""
Memento backend application entry point.

Creates the FastAPI app, configures CORS and logging, initializes database
clients on startup (lifespan), and mounts the health router.

Author: Memento Team
Last Updated: 2026-06-07
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from storage.sqlite_client import SQLiteClient
from storage.qdrant_client import QdrantStore
from api.health import router as health_router
from api.videos import router as videos_router
from api.documents import router as documents_router
from api.search import router as search_router
from api.chat import router as chat_router
from api.settings import router as settings_router

settings = get_settings()

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("memento")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and tear down database clients with the app lifecycle."""
    data_dir = settings.storage.data_dir.expanduser()

    sqlite = SQLiteClient(data_dir / "metadata.db")
    await sqlite.connect()
    app.state.sqlite = sqlite

    qdrant = QdrantStore(data_dir / "qdrant")
    qdrant.connect(vector_size=settings.rag.vector_size)
    app.state.qdrant = qdrant

    app.state.chat_sessions = {}

    logger.info("Databases initialized at %s", data_dir)
    yield

    await sqlite.close()
    qdrant.close()
    logger.info("Databases closed")


app = FastAPI(title="Memento API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(videos_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(chat_router)
app.include_router(settings_router)
