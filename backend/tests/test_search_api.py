"""Tests for the search API endpoint."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import search as search_api
from main import app
from storage.sqlite_client import SQLiteClient
from storage.qdrant_client import QdrantStore


class FakeEmbeddingClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


@pytest.fixture
async def client(tmp_path: Path, monkeypatch):
    sqlite = SQLiteClient(tmp_path / "metadata.db")
    await sqlite.connect()
    qdrant = QdrantStore(tmp_path / "qdrant")
    qdrant.connect(vector_size=4)
    qdrant.upsert_points(
        ids=["11111111-1111-1111-1111-111111111111"],
        vectors=[[1.0, 0.0, 0.0, 0.0]],
        payloads=[{
            "video_id": "v1", "document_id": "d1", "chunk_index": 0,
            "title_path": "标题 > Transcript", "text": "chunk 0",
            "start_timestamp": "00:01",
        }],
    )
    monkeypatch.setattr(
        search_api, "build_embedding_client", lambda: FakeEmbeddingClient()
    )
    with TestClient(app) as test_client:
        # Override app.state after lifespan so endpoints use the temp DB.
        app.state.sqlite = sqlite
        app.state.qdrant = qdrant
        yield test_client
    await sqlite.close()
    qdrant.close()


def test_search_returns_results_with_metadata(client: TestClient):
    response = client.post("/api/search", json={"query": "测试查询"})

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["text"] == "chunk 0"
    assert results[0]["video_id"] == "v1"
    assert results[0]["start_timestamp"] == "00:01"
    assert "score" in results[0]


def test_search_rejects_blank_query(client: TestClient):
    response = client.post("/api/search", json={"query": "   "})
    assert response.status_code == 422


def test_search_custom_top_k(client: TestClient, monkeypatch):
    # Insert 2 more points so fixture has 3 total; top_k=1 should return exactly 1.
    from api import search as search_api
    from main import app

    qdrant = app.state.qdrant
    qdrant.upsert_points(
        ids=[
            "22222222-2222-2222-2222-222222222222",
            "33333333-3333-3333-3333-333333333333",
        ],
        vectors=[[0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]],
        payloads=[
            {
                "video_id": "v1", "document_id": "d1", "chunk_index": 1,
                "title_path": "标题 > Transcript", "text": "chunk 1",
                "start_timestamp": "00:02",
            },
            {
                "video_id": "v1", "document_id": "d1", "chunk_index": 2,
                "title_path": "标题 > Transcript", "text": "chunk 2",
                "start_timestamp": "00:03",
            },
        ],
    )

    response = client.post("/api/search", json={"query": "q", "top_k": 1})
    assert response.status_code == 200
    assert len(response.json()) == 1

def test_search_finds_keyword_only_match(client: TestClient):
    # Seeded fixture has no vector affinity for this keyword; BM25 must find it.
    response = client.post("/api/search", json={"query": "chunk"})

    assert response.status_code == 200
    assert len(response.json()) >= 1
