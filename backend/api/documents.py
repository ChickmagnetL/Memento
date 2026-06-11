"""Document API endpoints (listing and RAG indexing)."""

import logging

from fastapi import APIRouter, HTTPException, Request, status

from config.settings import get_settings
from core.rag.embedding import CloudEmbeddingClient, EmbeddingError
from core.rag.indexer import DocumentIndexer
from schemas.document import DocumentRecord

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger(__name__)


def build_embedding_client() -> CloudEmbeddingClient:
    """Build the embedding client from settings (overridable in tests)."""
    embedding = get_settings().models.embedding
    return CloudEmbeddingClient(
        endpoint=embedding.endpoint,
        api_key=embedding.api_key,
        model=embedding.model,
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