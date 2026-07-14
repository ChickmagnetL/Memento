"""Tests for the vector retriever."""

import pytest

from core.rag.retrieval import HybridRetriever, SearchResult, VectorRetriever


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
            "platform": "youtube",
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
            video_id="v1", platform="youtube", document_id="d1", chunk_index=0,
            title_path="标题 > Transcript", text="chunk 0",
            start_timestamp="00:01", score=0.9,
        ),
        SearchResult(
            video_id="v1", platform="youtube", document_id="d1", chunk_index=1,
            title_path="标题 > Transcript", text="chunk 1",
            start_timestamp="00:01", score=0.5,
        ),
    ]


@pytest.mark.asyncio
async def test_search_keeps_legacy_payload_without_platform_compatible():
    hit = _qdrant_result(0, 0.9)
    hit["payload"].pop("platform")
    retriever = VectorRetriever(
        embedding_client=FakeEmbeddingClient(), qdrant=FakeQdrant([hit])
    )

    results = await retriever.search("查询内容", top_k=1)

    assert results[0].platform is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("video_id", "expected_platform"),
    [
        ("BV1234567890", "bilibili"),
        ("7123456789012345678", "douyin"),
    ],
)
async def test_search_recovers_platform_for_legacy_video_payloads(
    video_id: str, expected_platform: str
):
    hit = _qdrant_result(0, 0.9)
    hit["payload"].pop("platform")
    hit["payload"]["video_id"] = video_id
    retriever = VectorRetriever(
        embedding_client=FakeEmbeddingClient(), qdrant=FakeQdrant([hit])
    )

    results = await retriever.search("查询内容", top_k=1)

    assert results[0].platform == expected_platform


@pytest.mark.asyncio
async def test_search_blank_query_raises_value_error():
    retriever = VectorRetriever(
        embedding_client=FakeEmbeddingClient(), qdrant=FakeQdrant([])
    )
    with pytest.raises(ValueError):
        await retriever.search("   ", top_k=5)


def _chunk_payload(index: int, text: str) -> dict:
    return {
        "video_id": "v1",
        "platform": "bilibili",
        "document_id": "d1",
        "chunk_index": index,
        "title_path": "标题 > Transcript",
        "text": text,
        "start_timestamp": "00:01",
    }


class FakeHybridQdrant:
    """Vector search returns chunk 0 first; corpus contains keyword in chunk 1."""

    def __init__(self):
        self.payloads = [
            _chunk_payload(0, "向量召回的内容"),
            _chunk_payload(1, "唯一关键词青蒿素出现在这里"),
        ]

    def search_points(self, *, vector: list[float], top_k: int) -> list[dict]:
        return [
            {"score": 0.9, "payload": self.payloads[0]},
            {"score": 0.1, "payload": self.payloads[1]},
        ][:top_k]

    def scroll_all_points(self, *, batch_size: int = 256) -> list[dict]:
        return self.payloads


@pytest.mark.asyncio
async def test_hybrid_search_boosts_keyword_match():
    retriever = HybridRetriever(
        embedding_client=FakeEmbeddingClient(),
        qdrant=FakeHybridQdrant(),
        weights={"bm25": 1.0, "vector": 0.0},  # isolate the BM25 path
    )

    results = await retriever.search("青蒿素", top_k=2)

    # BM25 must rank the keyword-bearing chunk first when vector weight is 0.
    assert results[0].chunk_index == 1


@pytest.mark.asyncio
async def test_hybrid_search_returns_top_k_with_scores():
    retriever = HybridRetriever(
        embedding_client=FakeEmbeddingClient(),
        qdrant=FakeHybridQdrant(),
        weights={"bm25": 0.3, "vector": 0.7},
    )

    results = await retriever.search("向量", top_k=1)

    assert len(results) == 1
    assert results[0].score > 0
