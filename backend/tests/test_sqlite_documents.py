"""Tests for document indexing metadata updates."""

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
    assert updated["is_indexed"] == 1
    assert updated["indexed_at"] is not None


@pytest.mark.asyncio
async def test_mark_document_indexed_returns_none_for_missing(sqlite: SQLiteClient):
    assert await sqlite.mark_document_indexed("missing", chunk_count=1) is None