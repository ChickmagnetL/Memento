"""Tests for document API endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import documents
from main import app
from storage.sqlite_client import SQLiteClient
from storage.qdrant_client import QdrantStore

DRAFT = """# 示例视频

## Transcript

[00:01] 第一行内容
"""


class FakeEmbeddingClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]


@pytest.fixture
async def client(tmp_path: Path, monkeypatch):
    sqlite = SQLiteClient(tmp_path / "metadata.db")
    await sqlite.connect()
    qdrant = QdrantStore(tmp_path / "qdrant")
    qdrant.connect(vector_size=4)
    monkeypatch.setattr(
        documents, "build_embedding_client", lambda: FakeEmbeddingClient()
    )
    # Qdrant local mode uses SQLite internally, which is not thread-safe.
    # FastAPI's TestClient runs async handlers in a thread-pool, so we
    # replace the QdrantStore methods with thread-safe no-ops.
    monkeypatch.setattr(qdrant, "upsert_points", lambda **kwargs: None)
    monkeypatch.setattr(qdrant, "delete_for_document", lambda document_id: None)
    with TestClient(app) as test_client:
        # Override app.state after lifespan so endpoints use the temp DB.
        app.state.sqlite = sqlite
        app.state.qdrant = qdrant
        yield test_client, sqlite
    await sqlite.close()
    qdrant.close()


async def _seed_document(sqlite: SQLiteClient, tmp_path: Path) -> None:
    await sqlite.create_video(
        video_id="v1", platform="bilibili", title="示例视频",
        url="https://www.bilibili.com/video/BV1abc",
    )
    draft_path = tmp_path / "v1.md"
    draft_path.write_text(DRAFT, encoding="utf-8")
    await sqlite.create_document(
        document_id="d1", video_id="v1", file_path=str(draft_path)
    )


@pytest.mark.asyncio
async def test_list_documents_returns_records(client, tmp_path: Path):
    test_client, sqlite = client
    await _seed_document(sqlite, tmp_path)

    response = test_client.get("/api/documents")

    assert response.status_code == 200
    records = response.json()
    assert len(records) == 1
    assert records[0]["id"] == "d1"
    assert records[0]["is_indexed"] is False


@pytest.mark.asyncio
async def test_index_document_marks_indexed(client, tmp_path: Path):
    test_client, sqlite = client
    await _seed_document(sqlite, tmp_path)

    response = test_client.post("/api/documents/d1/index")

    assert response.status_code == 200
    record = response.json()
    assert record["is_indexed"] is True
    assert record["chunk_count"] == 1


@pytest.mark.asyncio
async def test_index_missing_document_returns_404(client):
    test_client, _sqlite = client
    response = test_client.post("/api/documents/missing/index")
    assert response.status_code == 404