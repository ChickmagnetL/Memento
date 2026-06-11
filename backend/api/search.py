"""Knowledge base search API."""

from fastapi import APIRouter, HTTPException, Request, status

from config.settings import get_settings
from core.rag.embedding import CloudEmbeddingClient, EmbeddingError
from core.rag.retrieval import HybridRetriever, SearchResult
from schemas.search import SearchRequest

router = APIRouter(prefix="/api/search", tags=["search"])


def build_embedding_client() -> CloudEmbeddingClient:
    """Build the embedding client from settings (overridable in tests)."""
    embedding = get_settings().models.embedding
    return CloudEmbeddingClient(
        endpoint=embedding.endpoint,
        api_key=embedding.api_key,
        model=embedding.model,
    )


@router.post("", response_model=list[SearchResult])
async def search(payload: SearchRequest, request: Request) -> list[SearchResult]:
    """Search indexed chunks by semantic similarity."""
    qdrant = getattr(request.app.state, "qdrant", None)
    if qdrant is None:
        raise HTTPException(status_code=500, detail="Qdrant is not initialized")

    try:
        embedding_client = build_embedding_client()
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    settings = get_settings()
    retriever = HybridRetriever(
        embedding_client=embedding_client,
        qdrant=qdrant,
        weights=settings.rag.hybrid_weights,
    )
    top_k = payload.top_k or settings.rag.top_k
    try:
        return await retriever.search(payload.query, top_k=top_k)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding API failed: {exc}",
        ) from exc