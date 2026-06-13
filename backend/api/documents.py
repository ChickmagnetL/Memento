"""Document API endpoints (listing and RAG indexing)."""

import asyncio
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from config.settings import get_settings
from core.models.chat_completion import (
    ChatCompletionError,
    CloudChatCompletionClient,
)
from core.rag.chunking import chunk_markdown
from core.rag.embedding import CloudEmbeddingClient, EmbeddingError, post_json
from core.rag.indexer import DocumentIndexer
from core.video.cleaner import CleaningError, TranscriptCleaner
from schemas.document import DocumentRecord

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger(__name__)


class ChunkPreview(BaseModel):
    """A chunk preview entry (no persistence side effects)."""

    chunk_index: int
    title_path: str
    text: str
    start_timestamp: str | None


def build_embedding_client() -> CloudEmbeddingClient:
    """Build the embedding client from settings (overridable in tests)."""
    embedding = get_settings().models.embedding
    return CloudEmbeddingClient(
        endpoint=embedding.endpoint,
        api_key=embedding.api_key,
        model=embedding.model,
    )


def build_chat_completion_client() -> CloudChatCompletionClient:
    """Build the chat completion client from settings (overridable in tests)."""
    chat = get_settings().models.chat
    return CloudChatCompletionClient(
        endpoint=chat.endpoint,
        api_key=chat.api_key,
        model=chat.model,
        post_json=lambda url, payload, headers: post_json(
            url, payload, headers, timeout=300
        ),
    )


def get_state(request: Request):
    """Return (sqlite, qdrant) app state or raise 500."""
    sqlite = getattr(request.app.state, "sqlite", None)
    qdrant = getattr(request.app.state, "qdrant", None)
    if sqlite is None or qdrant is None:
        raise HTTPException(status_code=500, detail="Storage is not initialized")
    return sqlite, qdrant


@router.get("", response_model=list[DocumentRecord])
async def list_documents(request: Request) -> list[dict]:
    """List document records."""
    sqlite, _qdrant = get_state(request)
    return await sqlite.list_documents()


@router.post("/{document_id}/index", response_model=DocumentRecord)
async def index_document(document_id: str, request: Request) -> dict:
    """Chunk, embed, and index a document into Qdrant."""
    sqlite, qdrant = get_state(request)
    document = await sqlite.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    settings = get_settings()
    try:
        embedding_client = build_embedding_client()
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=500, detail=str(exc)
        ) from exc

    indexer = DocumentIndexer(
        sqlite=sqlite,
        qdrant=qdrant,
        embedding_client=embedding_client,
        chunk_size=settings.rag.chunk_size,
        overlap=settings.rag.overlap,
    )
    try:
        return await indexer.index(document)
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding API failed: {exc}",
        ) from exc
    except (OSError, ValueError, RuntimeError) as exc:
        logger.exception("Indexing failed for document %s", document_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/{document_id}/clean",
    response_model=DocumentRecord,
    status_code=status.HTTP_201_CREATED,
)
async def clean_document(document_id: str, request: Request) -> dict:
    """AI-clean a draft document into a new sibling document."""
    sqlite, _qdrant = get_state(request)
    document = await sqlite.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        chat_client = build_chat_completion_client()
    except ChatCompletionError as exc:
        raise HTTPException(
            status_code=500, detail=str(exc)
        ) from exc

    source_path = Path(document["file_path"])
    cleaner = TranscriptCleaner(chat_client=chat_client)
    try:
        draft = await asyncio.to_thread(source_path.read_text, encoding="utf-8")
        cleaned = await asyncio.to_thread(cleaner.clean, draft)
    except ChatCompletionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Chat API failed: {exc}",
        ) from exc
    except (CleaningError, OSError, ValueError) as exc:
        logger.exception("Cleaning failed for document %s", document_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    cleaned_path = source_path.parent / f"{source_path.stem}.clean.md"
    await asyncio.to_thread(
        cleaned_path.write_text, cleaned, encoding="utf-8"
    )
    return await sqlite.create_document(
        document_id=uuid4().hex,
        video_id=document["video_id"],
        file_path=str(cleaned_path),
    )


@router.get("/{document_id}/chunks", response_model=list[ChunkPreview])
async def preview_chunks(document_id: str, request: Request) -> list[ChunkPreview]:
    """Preview how a document would be chunked. Read-only."""
    sqlite, _qdrant = get_state(request)
    document = await sqlite.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    settings = get_settings()
    try:
        content = await asyncio.to_thread(
            Path(document["file_path"]).read_text, encoding="utf-8"
        )
        chunks = chunk_markdown(
            content,
            video_id=document["video_id"],
            document_id=document_id,
            chunk_size=settings.rag.chunk_size,
            overlap=settings.rag.overlap,
        )
    except (OSError, ValueError) as exc:
        logger.exception("Chunk preview failed for document %s", document_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return [
        ChunkPreview(
            chunk_index=chunk.chunk_index,
            title_path=chunk.title_path,
            text=chunk.text,
            start_timestamp=chunk.start_timestamp,
        )
        for chunk in chunks
    ]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str, request: Request) -> None:
    """Delete a document record and its Qdrant points.

    The markdown file on disk is preserved (user data).
    """
    sqlite, qdrant = get_state(request)
    document = await sqlite.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        qdrant.delete_for_document(document_id)
        await sqlite.delete_document(document_id)
    except (OSError, RuntimeError) as exc:
        logger.exception("Delete failed for document %s", document_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc