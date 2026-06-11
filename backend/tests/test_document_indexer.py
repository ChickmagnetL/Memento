"""Tests for the document indexing orchestrator."""

from pathlib import Path

import pytest

from core.rag.indexer import DocumentIndexer
from storage.sqlite_client import SQLiteClient
from storage.qdrant_client import QdrantStore

DRAFT = """# 示例视频

## Transcript

[00:01] 第一行内容
[00:05] 第二行内容
"""


class FakeEmbeddingClient:
    def __init__(self, dimension: int = 4):
        self.dimension = dimension
        self.seen_texts: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.seen_texts.append(texts)
        return [[0.1] * self.dimension for _ in texts]


@pytest.fixture
async def sqlite(tmp_path: Path):
    client = SQLiteClient(tmp_path / "metadata.db")
    await client.connect()
    try:
        yield client
    finally:
        await client.close()


@pytest.fixture
def qdrant(tmp_path: Path):
    store = QdrantStore(tmp_path / "qdrant")
    store.connect(vector_size=4)
    try:
        yield store
    finally:
        store.close()


async def _create_document(sqlite: SQLiteClient, tmp_path: Path) -> dict:
    await sqlite.create_video(
        video_id="v1", platform="bilibili", title="示例视频",
        url="https://www.bilibili.com/video/BV1abc",
    )
    draft_path = tmp_path / "v1.md"
    draft_path.write_text(DRAFT, encoding="utf-8")
    return await sqlite.create_document(
        document_id="d1", video_id="v1", file_path=str(draft_path)
    )


@pytest.mark.asyncio
async def test_index_writes_points_and_marks_document(
    sqlite: SQLiteClient, qdrant: QdrantStore, tmp_path: Path
):
    document = await _create_document(sqlite, tmp_path)
    embedding = FakeEmbeddingClient()
    indexer = DocumentIndexer(
        sqlite=sqlite, qdrant=qdrant, embedding_client=embedding,
        chunk_size=800, overlap=80,
    )

    updated = await indexer.index(document)

    assert updated["is_indexed"] == 1
    assert updated["chunk_count"] == 1
    assert qdrant.count_for_document("d1") == 1
    # Embedded texts are the chunk texts (title path + body).
    assert embedding.seen_texts[0][0].startswith("示例视频 > Transcript")


@pytest.mark.asyncio
async def test_reindex_is_idempotent(
    sqlite: SQLiteClient, qdrant: QdrantStore, tmp_path: Path
):
    document = await _create_document(sqlite, tmp_path)
    indexer = DocumentIndexer(
        sqlite=sqlite, qdrant=qdrant, embedding_client=FakeEmbeddingClient(),
        chunk_size=800, overlap=80,
    )

    await indexer.index(document)
    await indexer.index(document)

    assert qdrant.count_for_document("d1") == 1


@pytest.mark.asyncio
async def test_index_missing_file_raises_oserror(
    sqlite: SQLiteClient, qdrant: QdrantStore, tmp_path: Path
):
    document = await _create_document(sqlite, tmp_path)
    Path(document["file_path"]).unlink()
    indexer = DocumentIndexer(
        sqlite=sqlite, qdrant=qdrant, embedding_client=FakeEmbeddingClient(),
        chunk_size=800, overlap=80,
    )

    with pytest.raises(OSError):
        await indexer.index(document)
    refreshed = await sqlite.get_document("d1")
    assert refreshed["is_indexed"] == 0