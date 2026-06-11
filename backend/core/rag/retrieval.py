"""RAG retrieval: query embedding + vector search."""

import asyncio

from pydantic import BaseModel


class SearchResult(BaseModel):
    video_id: str
    document_id: str
    chunk_index: int
    title_path: str
    text: str
    start_timestamp: str | None
    score: float


class VectorRetriever:
    def __init__(self, *, embedding_client, qdrant) -> None:
        self.embedding_client = embedding_client
        self.qdrant = qdrant

    async def search(self, query: str, *, top_k: int) -> list[SearchResult]:
        """Embed the query and return top-k chunks with metadata."""
        if not query.strip():
            raise ValueError("empty query")

        vectors = await asyncio.to_thread(self.embedding_client.embed, [query])
        hits = await asyncio.to_thread(
            lambda: self.qdrant.search_points(vector=vectors[0], top_k=top_k)
        )
        return [
            SearchResult(
                video_id=hit["payload"]["video_id"],
                document_id=hit["payload"]["document_id"],
                chunk_index=hit["payload"]["chunk_index"],
                title_path=hit["payload"]["title_path"],
                text=hit["payload"]["text"],
                start_timestamp=hit["payload"].get("start_timestamp"),
                score=hit["score"],
            )
            for hit in hits
        ]