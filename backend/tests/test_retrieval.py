"""Tests for the vector retriever."""

import pytest

from core.rag.retrieval import SearchResult, VectorRetriever


class FakeEmbeddingClient:
    def __init__(self):
        self.seen: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.seen.append(texts)
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]


class FakeQdrant:
    def __init__(self, results: list[dict]):
        self.results = results
        self.calls: list[dict] = []

    def search_points(self, *, vector: list[float], top_k: int) -> list[dict]:
        self.calls.append({"vector": vector, "top_k": top_k})
        return self.results


def _qdrant_result(index: int, score: float) -> dict:
    return {
        "score": score,
        "payload": {
            "video_id": "v1",
            "document_id": "d1",
            "chunk_index": index,
            "title_path": "标题 > Transcript",
            "text": f"chunk {index}",
            "start_timestamp": "00:01",
        },
    }


@pytest.mark.asyncio
async def test_search_embeds_query_and_maps_results():
    embedding = FakeEmbeddingClient()
    qdrant = FakeQdrant([_qdrant_result(0, 0.9), _qdrant_result(1, 0.5)])
    retriever = VectorRetriever(embedding_client=embedding, qdrant=qdrant)

    results = await retriever.search("查询内容", top_k=2)

    assert embedding.seen == [["查询内容"]]
    assert qdrant.calls == [{"vector": [0.1, 0.2, 0.3, 0.4], "top_k": 2}]
    assert results == [
        SearchResult(
            video_id="v1", document_id="d1", chunk_index=0,
            title_path="标题 > Transcript", text="chunk 0",
            start_timestamp="00:01", score=0.9,
        ),
        SearchResult(
            video_id="v1", document_id="d1", chunk_index=1,
            title_path="标题 > Transcript", text="chunk 1",
            start_timestamp="00:01", score=0.5,
        ),
    ]


@pytest.mark.asyncio
async def test_search_blank_query_raises_value_error():
    retriever = VectorRetriever(
        embedding_client=FakeEmbeddingClient(), qdrant=FakeQdrant([])
    )
    with pytest.raises(ValueError):
        await retriever.search("   ", top_k=5)