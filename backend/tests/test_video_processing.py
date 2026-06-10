"""Tests for the video processing pipeline."""

from pathlib import Path
import threading

import pytest

from core.video.bilibili import SubtitleEntry
from core.video.pipeline import VideoPipeline
from storage.sqlite_client import SQLiteClient


@pytest.fixture
async def sqlite(tmp_path: Path):
    client = SQLiteClient(tmp_path / "metadata.db")
    await client.connect()
    try:
        yield client
    finally:
        await client.close()


class FakeSubtitleClient:
    def __init__(self, entries: list[SubtitleEntry]) -> None:
        self.entries = entries

    def fetch(self, video: dict) -> list[SubtitleEntry]:
        return self.entries


class UnavailableDraftWriter:
    def write(self, video: dict, entries: list[SubtitleEntry]) -> Path:
        raise RuntimeError("document writer unavailable")


class ThreadRecordingSubtitleClient:
    def __init__(self) -> None:
        self.thread_id: int | None = None

    def fetch(self, video: dict) -> list[SubtitleEntry]:
        self.thread_id = threading.get_ident()
        return [SubtitleEntry(start_seconds=1.0, text="第一行")]


class ThreadRecordingDraftWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.thread_id: int | None = None

    def write(self, video: dict, entries: list[SubtitleEntry]) -> Path:
        self.thread_id = threading.get_ident()
        self.path.write_text("[00:01] 第一行\n", encoding="utf-8")
        return self.path


def make_video(video_id: str, platform: str) -> dict:
    return {
        "id": video_id,
        "platform": platform,
        "title": "Example video",
        "url": f"https://example.com/{video_id}",
        "status": "pending",
    }


def test_pipeline_passes_bilibili_cookie_to_default_subtitle_client(
    tmp_path: Path,
    monkeypatch,
):
    seen_cookies = []

    class RecordingSubtitleClient:
        def __init__(self, *, bilibili_cookie: str = "") -> None:
            seen_cookies.append(bilibili_cookie)

    monkeypatch.setattr(
        "core.video.pipeline.BilibiliSubtitleClient",
        RecordingSubtitleClient,
    )

    VideoPipeline(
        sqlite=None,
        data_dir=tmp_path,
        bilibili_cookie="SESSDATA=explicit",
    )

    assert seen_cookies == ["SESSDATA=explicit"]


@pytest.mark.asyncio
async def test_process_bilibili_video_writes_document(
    sqlite: SQLiteClient, tmp_path: Path
):
    video = make_video("video-1", "bilibili")
    await sqlite.create_video(
        video_id=video["id"],
        platform=video["platform"],
        title=video["title"],
        url=video["url"],
    )
    pipeline = VideoPipeline(
        sqlite=sqlite,
        data_dir=tmp_path,
        subtitle_client=FakeSubtitleClient(
            [SubtitleEntry(start_seconds=1.0, text="第一行")]
        ),
    )

    result = await pipeline.process(video)

    assert result.video_id == "video-1"
    assert result.status == "completed"
    assert result.document_id is not None
    assert result.document_path is not None
    assert Path(result.document_path).read_text(encoding="utf-8").endswith(
        "[00:01] 第一行\n"
    )
    documents = await sqlite.list_documents_for_video("video-1")
    assert len(documents) == 1
    assert documents[0]["id"] == result.document_id
    assert documents[0]["file_path"] == result.document_path


@pytest.mark.asyncio
async def test_process_runs_subtitle_fetch_and_draft_write_in_worker_threads(
    sqlite: SQLiteClient, tmp_path: Path
):
    video = make_video("video-1", "bilibili")
    await sqlite.create_video(
        video_id=video["id"],
        platform=video["platform"],
        title=video["title"],
        url=video["url"],
    )
    subtitle_client = ThreadRecordingSubtitleClient()
    draft_writer = ThreadRecordingDraftWriter(tmp_path / "draft.md")
    pipeline = VideoPipeline(
        sqlite=sqlite,
        data_dir=tmp_path,
        subtitle_client=subtitle_client,
        draft_writer=draft_writer,
    )
    event_loop_thread_id = threading.get_ident()

    result = await pipeline.process(video)

    assert result.status == "completed"
    assert subtitle_client.thread_id is not None
    assert draft_writer.thread_id is not None
    assert subtitle_client.thread_id != event_loop_thread_id
    assert draft_writer.thread_id != event_loop_thread_id


@pytest.mark.asyncio
async def test_process_douyin_video_returns_failed(
    sqlite: SQLiteClient, tmp_path: Path
):
    pipeline = VideoPipeline(
        sqlite=sqlite,
        data_dir=tmp_path,
        subtitle_client=FakeSubtitleClient([]),
    )
    video = make_video("douyin-1", "douyin")

    result = await pipeline.process(video)

    assert result.video_id == "douyin-1"
    assert result.status == "failed"
    assert result.document_id is None
    assert result.document_path is None
    assert result.error is not None
    assert "unsupported platform" in result.error


@pytest.mark.asyncio
async def test_process_empty_subtitles_returns_failed(
    sqlite: SQLiteClient, tmp_path: Path
):
    pipeline = VideoPipeline(
        sqlite=sqlite,
        data_dir=tmp_path,
        subtitle_client=FakeSubtitleClient([]),
    )
    video = make_video("video-1", "bilibili")

    result = await pipeline.process(video)

    assert result.video_id == "video-1"
    assert result.status == "failed"
    assert result.document_id is None
    assert result.document_path is None
    assert result.error == "No soft subtitles found"


@pytest.mark.asyncio
async def test_process_document_writer_runtime_error_returns_failed(
    sqlite: SQLiteClient, tmp_path: Path
):
    pipeline = VideoPipeline(
        sqlite=sqlite,
        data_dir=tmp_path,
        subtitle_client=FakeSubtitleClient(
            [SubtitleEntry(start_seconds=1.0, text="第一行")]
        ),
        draft_writer=UnavailableDraftWriter(),
    )
    video = make_video("video-1", "bilibili")

    result = await pipeline.process(video)

    assert result.video_id == "video-1"
    assert result.status == "failed"
    assert result.document_id is None
    assert result.document_path is None
    assert result.error == "document writer unavailable"
