"""Tests for document API endpoints."""

from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api import documents
from main import app
from storage.sqlite_client import SQLiteClient
from storage.qdrant_client import QdrantStore

DRAFT = """# 示例视频

## Transcript

[00:01] 第一行内容
"""

CLEAN_REPLY = (
    "## 主题\n\n"
    "[00:01] 清洗后的第一行内容。\n"
    "<summary>这是关于示例视频的一段描述。</summary>\n"
    "<brief>示例视频的主题。</brief>\n"
)


class FakeEmbeddingClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]


def chat_client_reply(text: str) -> type:
    """Return a fake chat client class whose ``complete`` always returns ``text``."""

    class FakeChatClient:
        def complete(self, messages: list[dict]) -> str:
            return text

    return FakeChatClient


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
    monkeypatch.setattr(qdrant, "ensure_summary_collection", lambda vector_size: None)
    monkeypatch.setattr(qdrant, "upsert_summary", lambda **kwargs: None)
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
    assert records[0]["status"] == "raw"


@pytest.mark.asyncio
async def test_index_document_marks_indexed(client, tmp_path: Path):
    test_client, sqlite = client
    await _seed_document(sqlite, tmp_path)

    response = test_client.post("/api/documents/d1/index")

    assert response.status_code == 200
    record = response.json()
    assert record["status"] == "indexed"
    assert record["chunk_count"] == 1


@pytest.mark.asyncio
async def test_index_missing_document_returns_404(client):
    test_client, _sqlite = client
    response = test_client.post("/api/documents/missing/index")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_preview_chunks_returns_chunks_without_indexing(client, tmp_path: Path):
    test_client, sqlite = client
    await _seed_document(sqlite, tmp_path)

    response = test_client.get("/api/documents/d1/chunks")

    assert response.status_code == 200
    chunks = response.json()
    assert len(chunks) == 1
    assert chunks[0]["title_path"] == "示例视频 > Transcript"
    assert chunks[0]["chunk_index"] == 0
    assert "[00:01] 第一行内容" in chunks[0]["text"]
    # Preview must not mark the document as indexed.
    document = await sqlite.get_document("d1")
    assert document["status"] == "raw"


@pytest.mark.asyncio
async def test_preview_chunks_missing_document_returns_404(client):
    test_client, _sqlite = client
    response = test_client.get("/api/documents/missing/chunks")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_document_removes_record_and_points(client, tmp_path: Path):
    test_client, sqlite = client
    await _seed_document(sqlite, tmp_path)
    # Index first so Qdrant has points for this document.
    assert test_client.post("/api/documents/d1/index").status_code == 200

    response = test_client.delete("/api/documents/d1")

    assert response.status_code == 204
    assert await sqlite.get_document("d1") is None
    # The markdown file is intentionally preserved (user data).
    assert Path(tmp_path / "v1.md").exists()


@pytest.mark.asyncio
async def test_delete_missing_document_returns_404(client):
    test_client, _sqlite = client
    assert test_client.delete("/api/documents/missing").status_code == 404


@pytest.mark.asyncio
async def test_clean_document_updates_in_place_and_indexes(
    client, tmp_path: Path, monkeypatch
):
    test_client, sqlite = client
    await _seed_document(sqlite, tmp_path)

    monkeypatch.setattr(
        documents, "build_chat_completion_client", lambda: chat_client_reply(CLEAN_REPLY)()
    )

    response = test_client.post("/api/documents/d1/clean")

    assert response.status_code == 200
    record = response.json()
    assert record["id"] == "d1"
    assert record["video_id"] == "v1"
    assert record["file_path"].endswith("v1.clean.md")
    assert record["status"] == "indexed"
    cleaned_text = Path(record["file_path"]).read_text(encoding="utf-8")
    assert "## 主题" in cleaned_text
    assert cleaned_text.startswith("# 示例视频")
    # Raw draft file is untouched.
    raw = Path(tmp_path / "v1.md")
    assert "[00:01] 第一行内容" in raw.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_clean_missing_document_returns_404(client):
    test_client, _sqlite = client
    assert test_client.post("/api/documents/missing/clean").status_code == 404


@pytest.mark.asyncio
async def test_clean_document_file_missing_returns_500(
    client, tmp_path: Path, monkeypatch
):
    test_client, sqlite = client
    await _seed_document(sqlite, tmp_path)

    monkeypatch.setattr(
        documents, "build_chat_completion_client", lambda: chat_client_reply(CLEAN_REPLY)()
    )

    (tmp_path / "v1.md").unlink()
    response = test_client.post("/api/documents/d1/clean")
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_clean_document_persists_summary_and_vector(
    tmp_path: Path, monkeypatch
):
    """Cleaning persists L2/L3 in SQLite and the L3 vector in Qdrant."""
    # DocumentSummaryStore.save_summary routes the Qdrant upsert through
    # asyncio.to_thread. Qdrant local mode stores points in SQLite, which on
    # macOS (THREADSAFE=2) refuses cross-thread access. Production runs on
    # Linux (THREADSAFE=1, check_same_thread=False); mirror that here so the
    # real upsert/search can run from the worker thread.
    from qdrant_client.local.persistence import CollectionPersistence

    monkeypatch.setattr(CollectionPersistence, "CHECK_SAME_THREAD", False)

    sqlite = SQLiteClient(tmp_path / "metadata.db")
    await sqlite.connect()
    qdrant = QdrantStore(tmp_path / "qdrant")
    qdrant.connect(vector_size=4)
    qdrant.ensure_summary_collection(vector_size=4)

    try:
        await sqlite.create_video(
            video_id="v1",
            platform="bilibili",
            title="示例视频",
            url="https://www.bilibili.com/video/BV1abc",
        )
        draft_path = tmp_path / "v1.md"
        draft_path.write_text(DRAFT, encoding="utf-8")
        await sqlite.create_document(
            document_id="d1", video_id="v1", file_path=str(draft_path)
        )

        monkeypatch.setattr(
            documents,
            "build_chat_completion_client",
            lambda: chat_client_reply(CLEAN_REPLY)(),
        )
        monkeypatch.setattr(
            documents, "build_embedding_client", lambda: FakeEmbeddingClient()
        )

        # We call the endpoint directly because the shared client fixture
        # monkeypatches Qdrant upsert_summary, making it impossible to verify
        # the real summary vector was persisted.
        test_app = FastAPI()
        test_app.state.sqlite = sqlite
        test_app.state.qdrant = qdrant
        request = Request(
            scope={
                "type": "http",
                "method": "POST",
                "path": "/api/documents/d1/clean",
                "headers": [],
                "query_string": b"",
                "app": test_app,
            }
        )

        record = await documents.clean_document("d1", request)

        assert record["id"] == "d1"
        assert record["summary"] == "这是关于示例视频的一段描述。"
        assert record["brief"] == "示例视频的主题。"

        results = qdrant.search_summaries(
            vector=[0.1, 0.2, 0.3, 0.4], top_k=5
        )
        assert any(r["payload"].get("document_id") == "d1" for r in results)
        match = next(r for r in results if r["payload"].get("document_id") == "d1")
        assert match["payload"]["title"] == "示例视频"
        assert match["payload"]["brief"] == "示例视频的主题。"
    finally:
        await sqlite.close()
        qdrant.close()


@pytest.mark.asyncio
async def test_delete_document_preserves_source_file_by_default(client, tmp_path: Path):
    test_client, sqlite = client
    await _seed_document(sqlite, tmp_path)
    draft_path = tmp_path / "v1.md"
    assert draft_path.exists()

    resp = test_client.delete("/api/documents/d1")

    assert resp.status_code == 204
    assert draft_path.exists()  # source file preserved
    assert await sqlite.get_document("d1") is None


@pytest.mark.asyncio
async def test_delete_document_removes_source_file_when_requested(
    client, tmp_path: Path
):
    test_client, sqlite = client
    await _seed_document(sqlite, tmp_path)
    draft_path = tmp_path / "v1.md"
    assert draft_path.exists()

    resp = test_client.delete("/api/documents/d1?delete_source_file=true")

    assert resp.status_code == 204
    assert not draft_path.exists()  # source file deleted
    assert await sqlite.get_document("d1") is None


@pytest.mark.asyncio
async def test_delete_document_with_missing_source_file_does_not_error(
    client, tmp_path: Path
):
    test_client, sqlite = client
    await _seed_document(sqlite, tmp_path)
    (tmp_path / "v1.md").unlink()  # file already gone

    resp = test_client.delete("/api/documents/d1?delete_source_file=true")

    assert resp.status_code == 204