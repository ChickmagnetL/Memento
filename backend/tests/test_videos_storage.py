"""Tests for SQLite video metadata operations."""

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
async def test_create_and_get_video(sqlite: SQLiteClient):
    created = await sqlite.create_video(
        video_id="video-1",
        platform="bilibili",
        title="Example video",
        url="https://www.bilibili.com/video/BV123",
        author_id="12345",
    )

    loaded = await sqlite.get_video("video-1")

    assert created["id"] == "video-1"
    assert loaded is not None
    assert loaded["platform"] == "bilibili"
    assert loaded["title"] == "Example video"
    assert loaded["url"] == "https://www.bilibili.com/video/BV123"
    assert loaded["status"] == "pending"
    assert loaded["author_id"] == "12345"


@pytest.mark.asyncio
async def test_list_videos_returns_newest_first(sqlite: SQLiteClient):
    await sqlite.create_video(
        video_id="video-1",
        platform="bilibili",
        title="First",
        url="https://www.bilibili.com/video/BV111",
    )
    await sqlite.create_video(
        video_id="video-2",
        platform="douyin",
        title="Second",
        url="https://www.douyin.com/video/222",
    )

    videos = await sqlite.list_videos()

    assert [video["id"] for video in videos] == ["video-2", "video-1"]


@pytest.mark.asyncio
async def test_update_video_status(sqlite: SQLiteClient):
    await sqlite.create_video(
        video_id="video-1",
        platform="bilibili",
        title="Example video",
        url="https://www.bilibili.com/video/BV123",
    )

    updated = await sqlite.update_video_status("video-1", "processing")

    assert updated is not None
    assert updated["status"] == "processing"


@pytest.mark.asyncio
async def test_update_missing_video_returns_none(sqlite: SQLiteClient):
    updated = await sqlite.update_video_status("missing", "failed")

    assert updated is None


@pytest.mark.asyncio
async def test_claim_video_for_processing_from_pending(sqlite: SQLiteClient):
    await sqlite.create_video(
        video_id="video-1",
        platform="bilibili",
        title="Example video",
        url="https://www.bilibili.com/video/BV123",
    )

    claimed = await sqlite.claim_video_for_processing("video-1")

    assert claimed is not None
    assert claimed["status"] == "processing"


@pytest.mark.asyncio
async def test_claim_video_for_processing_from_failed(sqlite: SQLiteClient):
    await sqlite.create_video(
        video_id="video-1",
        platform="bilibili",
        title="Example video",
        url="https://www.bilibili.com/video/BV123",
    )
    await sqlite.update_video_status("video-1", "failed")

    claimed = await sqlite.claim_video_for_processing("video-1")

    assert claimed is not None
    assert claimed["status"] == "processing"


@pytest.mark.asyncio
async def test_claim_video_for_processing_from_completed(sqlite: SQLiteClient):
    await sqlite.create_video(
        video_id="video-1",
        platform="bilibili",
        title="Example video",
        url="https://www.bilibili.com/video/BV123",
    )
    await sqlite.update_video_status("video-1", "completed")

    claimed = await sqlite.claim_video_for_processing("video-1")

    assert claimed is not None
    assert claimed["status"] == "processing"


@pytest.mark.asyncio
@pytest.mark.parametrize("video_status", ["processing"])
async def test_claim_video_for_processing_rejects_unclaimable_status(
    sqlite: SQLiteClient,
    video_status: str,
):
    await sqlite.create_video(
        video_id="video-1",
        platform="bilibili",
        title="Example video",
        url="https://www.bilibili.com/video/BV123",
    )
    await sqlite.update_video_status("video-1", video_status)

    claimed = await sqlite.claim_video_for_processing("video-1")

    assert claimed is None
    current = await sqlite.get_video("video-1")
    assert current is not None
    assert current["status"] == video_status


@pytest.mark.asyncio
async def test_claim_missing_video_for_processing_returns_none(sqlite: SQLiteClient):
    claimed = await sqlite.claim_video_for_processing("missing")

    assert claimed is None


@pytest.mark.asyncio
async def test_claim_video_for_processing_only_succeeds_once(sqlite: SQLiteClient):
    await sqlite.create_video(
        video_id="video-1",
        platform="bilibili",
        title="Example video",
        url="https://www.bilibili.com/video/BV123",
    )

    first_claim = await sqlite.claim_video_for_processing("video-1")
    second_claim = await sqlite.claim_video_for_processing("video-1")

    assert first_claim is not None
    assert first_claim["status"] == "processing"
    assert second_claim is None


@pytest.mark.asyncio
async def test_delete_video_removes_record_and_nulls_documents(sqlite: SQLiteClient):
    await sqlite.create_video(
        video_id="v1", platform="bilibili", title="t", url="https://example.com"
    )
    await sqlite.create_document(
        document_id="d1", video_id="v1", file_path="/tmp/d1.md"
    )

    deleted = await sqlite.delete_video("v1")

    assert deleted is True
    assert await sqlite.get_video("v1") is None
    # document survives, video_id nulled (FK ON DELETE SET NULL)
    surviving = await sqlite.get_document("d1")
    assert surviving is not None
    assert surviving["video_id"] is None


@pytest.mark.asyncio
async def test_delete_missing_video_returns_false(sqlite: SQLiteClient):
    assert await sqlite.delete_video("missing") is False
