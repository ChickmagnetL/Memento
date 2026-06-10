"""Tests for SQLite document metadata operations."""

from pathlib import Path

import pytest
import aiosqlite

from storage.sqlite_client import SQLiteClient


@pytest.fixture
async def sqlite(tmp_path: Path):
    client = SQLiteClient(tmp_path / "metadata.db")
    await client.connect()
    try:
        yield client
    finally:
        await client.close()


async def create_video(sqlite: SQLiteClient, video_id: str) -> None:
    await sqlite.create_video(
        video_id=video_id,
        platform="bilibili",
        title=f"Video {video_id}",
        url=f"https://www.bilibili.com/video/{video_id}",
    )


@pytest.mark.asyncio
async def test_create_and_get_document(sqlite: SQLiteClient):
    await create_video(sqlite, "video-1")

    created = await sqlite.create_document(
        document_id="doc-1",
        video_id="video-1",
        file_path="/tmp/doc-1.md",
    )

    loaded = await sqlite.get_document("doc-1")

    assert created["id"] == "doc-1"
    assert loaded is not None
    assert loaded["id"] == "doc-1"
    assert loaded["video_id"] == "video-1"
    assert loaded["file_path"] == "/tmp/doc-1.md"
    assert loaded["chunk_count"] == 0
    assert loaded["is_indexed"] == 0
    assert loaded["indexed_at"] is None


@pytest.mark.asyncio
async def test_list_documents_returns_newest_first(sqlite: SQLiteClient):
    await create_video(sqlite, "video-1")
    await create_video(sqlite, "video-2")

    await sqlite.create_document(
        document_id="doc-1",
        video_id="video-1",
        file_path="/tmp/doc-1.md",
    )
    await sqlite.create_document(
        document_id="doc-2",
        video_id="video-2",
        file_path="/tmp/doc-2.md",
    )

    documents = await sqlite.list_documents()

    assert [document["id"] for document in documents] == ["doc-2", "doc-1"]


@pytest.mark.asyncio
async def test_list_documents_for_video_filters_by_video_id(sqlite: SQLiteClient):
    await create_video(sqlite, "video-1")
    await create_video(sqlite, "video-2")

    await sqlite.create_document(
        document_id="doc-1",
        video_id="video-1",
        file_path="/tmp/doc-1.md",
    )
    await sqlite.create_document(
        document_id="doc-2",
        video_id="video-2",
        file_path="/tmp/doc-2.md",
    )

    documents = await sqlite.list_documents_for_video("video-1")

    assert [document["id"] for document in documents] == ["doc-1"]


@pytest.mark.asyncio
async def test_get_missing_document_returns_none(sqlite: SQLiteClient):
    document = await sqlite.get_document("missing")

    assert document is None


@pytest.mark.asyncio
async def test_create_document_rejects_missing_video(sqlite: SQLiteClient):
    with pytest.raises(aiosqlite.IntegrityError):
        await sqlite.create_document(
            document_id="doc-1",
            video_id="missing-video",
            file_path="/tmp/doc-1.md",
        )
