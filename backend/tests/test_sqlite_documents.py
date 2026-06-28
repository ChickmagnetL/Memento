"""Tests for document CRUD and metadata updates (status, indexing, summary/brief)."""

from pathlib import Path

import pytest

from storage.sqlite_client import SQLiteClient


@pytest.fixture
async def sqlite(tmp_path: Path):
    client = SQLiteClient(tmp_path / "metadata.db")
    await client.connect()
    try:
        yield client
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_mark_document_indexed_updates_metadata(sqlite: SQLiteClient):
    await sqlite.create_video(
        video_id="v1", platform="bilibili", title="t", url="https://example.com"
    )
    await sqlite.create_document(
        document_id="d1", video_id="v1", file_path="/tmp/d1.md"
    )

    updated = await sqlite.mark_document_indexed("d1", chunk_count=7)

    assert updated is not None
    assert updated["chunk_count"] == 7
    assert updated["status"] == "indexed"
    assert updated["indexed_at"] is not None


@pytest.mark.asyncio
async def test_mark_document_indexed_returns_none_for_missing(sqlite: SQLiteClient):
    assert await sqlite.mark_document_indexed("missing", chunk_count=1) is None


@pytest.mark.asyncio
async def test_delete_document_removes_record(sqlite: SQLiteClient):
    await sqlite.create_video(
        video_id="v1", platform="bilibili", title="t", url="https://example.com"
    )
    await sqlite.create_document(
        document_id="d1", video_id="v1", file_path="/tmp/d1.md"
    )

    deleted = await sqlite.delete_document("d1")

    assert deleted is True
    assert await sqlite.get_document("d1") is None


@pytest.mark.asyncio
async def test_delete_missing_document_returns_false(sqlite: SQLiteClient):
    assert await sqlite.delete_document("missing") is False


@pytest.mark.asyncio
async def test_create_document_allows_null_video_id(sqlite: SQLiteClient):
    doc = await sqlite.create_document(
        document_id="d9", video_id=None, file_path="/tmp/d9.md"
    )
    assert doc["video_id"] is None
    assert doc["status"] == "raw"


@pytest.mark.asyncio
async def test_set_and_get_document_summary(sqlite: SQLiteClient):
    doc = await sqlite.create_document(document_id="d1", file_path="/tmp/d1.md")
    updated = await sqlite.set_document_summary(doc["id"], l2="Paragraph summary", l3="One-sentence brief")
    assert updated is not None
    assert updated["id"] == doc["id"]
    fetched = await sqlite.get_document_summary(doc["id"])
    assert fetched == ("Paragraph summary", "One-sentence brief")


@pytest.mark.asyncio
async def test_get_document_summary_none_when_not_generated(sqlite: SQLiteClient):
    doc = await sqlite.create_document(document_id="d1", file_path="/tmp/d1.md")
    assert await sqlite.get_document_summary(doc["id"]) is None