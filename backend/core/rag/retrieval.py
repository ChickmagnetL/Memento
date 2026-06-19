"""RAG retrieval: query embedding + vector search."""

import asyncio

from pydantic import BaseModel
from rank_bm25 import BM25Plus

from core.rag.fusion import rrf_fuse
from core.rag.tokenize import tokenize


class SearchResult(BaseModel):
    video_id: str | None
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


class HybridRetriever:
    """BM25 + vector search fused with weighted RRF.

    The BM25 corpus is rebuilt from a full Qdrant scroll per query.
    Acceptable for MVP-scale data; revisit in v0.2 performance work.
    """

    def __init__(self, *, embedding_client, qdrant, weights: dict[str, float]) -> None:
        self.embedding_client = embedding_client
        self.qdrant = qdrant
        self.weights = weights

    async def search(self, query: str, *, top_k: int) -> list[SearchResult]:
        if not query.strip():
            raise ValueError("empty query")
        return await asyncio.to_thread(self._search_sync, query, top_k)

    def _search_sync(self, query: str, top_k: int) -> list[SearchResult]:
        fetch_k = top_k * 2

        # SECTION 1: vector ranking
        vector = self.embedding_client.embed([query])[0]
        vector_hits = self.qdrant.search_points(vector=vector, top_k=fetch_k)
        payload_by_key: dict[tuple, dict] = {}
        vector_scores: dict[tuple, float] = {}
        vector_ranking: list[tuple] = []
        for hit in vector_hits:
            key = (hit["payload"]["document_id"], hit["payload"]["chunk_index"])
            payload_by_key[key] = hit["payload"]
            vector_scores[key] = hit["score"]
            vector_ranking.append(key)

        # SECTION 2: BM25 ranking over the full corpus
        corpus = self.qdrant.scroll_all_points()
        bm25_ranking: list[tuple] = []
        if corpus:
            tokenized = [tokenize(payload["text"]) for payload in corpus]
            bm25 = BM25Plus(tokenized)
            scores = bm25.get_scores(tokenize(query))
            scored = sorted(
                zip(scores, corpus), key=lambda pair: -pair[0]
            )[:fetch_k]
            for score, payload in scored:
                key = (payload["document_id"], payload["chunk_index"])
                payload_by_key.setdefault(key, payload)
                bm25_ranking.append(key)

        # SECTION 3: weighted RRF fusion
        fused_keys = rrf_fuse(
            rankings={"vector": vector_ranking, "bm25": bm25_ranking},
            weights=self.weights,
        )[:top_k]

        results = []
        for rank, key in enumerate(fused_keys, start=1):
            payload = payload_by_key[key]
            results.append(
                SearchResult(
                    video_id=payload["video_id"],
                    document_id=payload["document_id"],
                    chunk_index=payload["chunk_index"],
                    title_path=payload["title_path"],
                    text=payload["text"],
                    start_timestamp=payload.get("start_timestamp"),
                    # Expose vector similarity when available, else 1/rank.
                    score=vector_scores.get(key, 1.0 / rank),
                )
            )
        return results
