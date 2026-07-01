"""Document API endpoints (listing and RAG indexing)."""

import asyncio
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from config.settings import get_settings
from core.documents.paths import (
    cleaned_document_path_for_source,
    preferred_clean_source_path,
)
from core.models.chat_completion import ChatCompletionError
from core.models.factory import (
    build_chat_completion_client as factory_build_chat_completion_client,
    build_embedding_client,
)
from core.documents.metadata import parse_markdown_metadata
from core.rag.chunking import chunk_markdown
from core.rag.document_summary_store import DocumentSummaryStore
from core.rag.embedding import EmbeddingError
from core.rag.indexer import DocumentIndexer
from core.video.cleaner import CleaningError, TranscriptCleaner
from schemas.document import DocumentRecord, UnimportedDocument

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger(__name__)


class ChunkPreview(BaseModel):
    """A chunk preview entry (no persistence side effects)."""

    chunk_index: int
    title_path: str
    text: str
    start_timestamp: str | None


class ImportUnimportedRequest(BaseModel):
    """Request body for importing unimported markdown files."""

    file_paths: list[str]


def build_chat_completion_client():
    """Build the chat completion client from settings (overridable in tests)."""
    return factory_build_chat_completion_client()


def get_state(request: Request):
    """Return (sqlite, qdrant) app state or raise 500."""
    sqlite = getattr(request.app.state, "sqlite", None)
    qdrant = getattr(request.app.state, "qdrant", None)
    if sqlite is None or qdrant is None:
        raise HTTPException(status_code=500, detail="Storage is not initialized")
    return sqlite, qdrant


async def _persist_summary(
    sqlite,
    qdrant,
    document: dict,
    l2_summary: str,
    l3_brief: str,
    embedding_client,
) -> None:
    """Persist L2/L3 summaries in SQLite and the L3 vector in Qdrant.

    Delegates to DocumentSummaryStore so the clean-time path and the
    on-demand backfill path share one persistence implementation.
    """
    summary_store = DocumentSummaryStore(
        sqlite=sqlite, qdrant=qdrant, embedding=embedding_client
    )
    l3_vector = await asyncio.to_thread(embedding_client.embed, [l3_brief])
    title = await summary_store._resolve_title(document)
    await summary_store.save_summary(
        document_id=document["id"],
        title=title,
        l2=l2_summary,
        l3=l3_brief,
        l3_vector=l3_vector[0],
    )


async def _index_cleaned_document(
    sqlite,
    qdrant,
    document: dict,
    settings,
    embedding_client,
) -> dict:
    """Index a cleaned document and return the updated record."""
    indexer = DocumentIndexer(
        sqlite=sqlite,
        qdrant=qdrant,
        embedding_client=embedding_client,
        chunk_size=settings.rag.chunk_size,
        overlap=settings.rag.overlap,
    )
    return await indexer.index(document)


@router.get("", response_model=list[DocumentRecord])
async def list_documents(request: Request) -> list[dict]:
    """List document records."""
    sqlite, _qdrant = get_state(request)
    return await sqlite.list_documents()


@router.get("/unimported", response_model=list[UnimportedDocument])
async def list_unimported_documents(request: Request) -> list[dict]:
    """List markdown files under the knowledge dir with no KB document record."""
    sqlite, _qdrant = get_state(request)
    settings = get_settings()
    knowledge_dir = Path(settings.storage.data_dir) / "knowledge"

    existing = {doc["file_path"] for doc in await sqlite.list_documents()}
    results: list[dict] = []
    if knowledge_dir.exists():
        for raw_dir in sorted(knowledge_dir.glob("*/raw")):
            for path in sorted(raw_dir.glob("*.md")):
                abs_path = str(path)
                if abs_path in existing:
                    continue
                results.append({"file_path": abs_path, **parse_markdown_metadata(path)})
    return results


@router.post(
    "/unimported/import",
    response_model=list[DocumentRecord],
    status_code=status.HTTP_201_CREATED,
)
async def import_unimported_documents(
    payload: ImportUnimportedRequest, request: Request
) -> list[dict]:
    """Create KB document records for the given markdown files.

    Already-imported or missing files are skipped silently.
    """
    sqlite, _qdrant = get_state(request)
    existing = {doc["file_path"] for doc in await sqlite.list_documents()}
    created: list[dict] = []
    for file_path in payload.file_paths:
        if file_path in existing or not Path(file_path).exists():
            continue
        meta = parse_markdown_metadata(Path(file_path))

        # Link to existing video when metadata has video_id that matches
        video_id = None
        if meta["video_id"]:
            video = await sqlite.get_video(meta["video_id"])
            if video:
                video_id = meta["video_id"]

        document = await sqlite.create_document(
            document_id=uuid4().hex,
            video_id=video_id,
            file_path=file_path,
            title=meta["title"] if not video_id else None,
            author=meta["author"] if not video_id else None,
        )
        existing.add(file_path)
        created.append(document)
    return created


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
)
async def clean_document(document_id: str, request: Request) -> dict:
    """AI-clean a draft document, persist the cleaned copy, and auto-index."""
    sqlite, qdrant = get_state(request)
    document = await sqlite.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    settings = get_settings()

    try:
        chat_client = build_chat_completion_client()
    except ChatCompletionError as exc:
        raise HTTPException(
            status_code=500, detail=str(exc)
        ) from exc

    source_path = preferred_clean_source_path(
        document["file_path"], video_id=document["video_id"]
    )
    cleaner = TranscriptCleaner(
        chat_client=chat_client,
        diagnostic_context={
            "document_id": document_id,
            "source_path": str(source_path),
            "chat_provider": settings.models.chat.provider,
            "chat_endpoint": settings.models.chat.endpoint,
            "chat_model": settings.models.chat.model,
        },
    )
    try:
        draft = await asyncio.to_thread(source_path.read_text, encoding="utf-8")
        cleaned_md, l2_summary, l3_brief = await asyncio.to_thread(
            cleaner.clean_with_summary, draft
        )
    except ChatCompletionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Chat API failed: {exc}",
        ) from exc
    except CleaningError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        logger.exception(
            "document_clean_failure %s",
            {
                "document_id": document_id,
                "source_path": str(source_path),
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    cleaned_path = cleaned_document_path_for_source(
        source_path, video_id=document["video_id"]
    )
    cleaned_path.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(
        cleaned_path.write_text, cleaned_md, encoding="utf-8"
    )

    try:
        embedding_client = build_embedding_client()
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=500, detail=str(exc)
        ) from exc

    try:
        document = await sqlite.update_document_path(document_id, str(cleaned_path))
        await _persist_summary(
            sqlite, qdrant, document, l2_summary, l3_brief, embedding_client
        )
        return await _index_cleaned_document(
            sqlite, qdrant, document, settings, embedding_client
        )
    except EmbeddingError as exc:
        logger.exception("Embedding failed for document %s", document_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding API failed: {exc}",
        ) from exc
    except (OSError, ValueError, RuntimeError) as exc:
        logger.exception("Storage/indexing failed for document %s", document_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
async def delete_document(
    document_id: str, request: Request, delete_source_file: bool = False
) -> None:
    """Delete a document record and its Qdrant points.

    The markdown file on disk is preserved unless delete_source_file=true.
    """
    sqlite, qdrant = get_state(request)
    document = await sqlite.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        qdrant.delete_for_document(document_id)
        if delete_source_file:
            Path(document["file_path"]).unlink(missing_ok=True)
        await sqlite.delete_document(document_id)
    except (OSError, RuntimeError) as exc:
        logger.exception("Delete failed for document %s", document_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
