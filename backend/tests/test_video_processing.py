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
        self.calls = 0

    def fetch(self, video: dict) -> list[SubtitleEntry]:
        self.calls += 1
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


def test_pipeline_passes_cookie_to_default_subtitle_client(
    tmp_path: Path,
    monkeypatch,
):
    seen_cookies = []

    class RecordingSubtitleClient:
        def __init__(self, *, cookie: str = "") -> None:
            seen_cookies.append(cookie)

    monkeypatch.setattr(
        "core.video.pipeline.BilibiliSubtitleClient",
        RecordingSubtitleClient,
    )

    VideoPipeline(
        sqlite=None,
        data_dir=tmp_path,
        cookie="SESSDATA=explicit",
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
    assert "douyin" in result.error.lower()


@pytest.mark.asyncio
async def test_process_empty_subtitles_without_fallback_returns_failed(
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
    assert "cookie" in result.error.lower()


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


class FakeAudioDownloader:
    def __init__(self, tmp_path: Path):
        self.wav_path = tmp_path / "v1.wav"
        self.cleaned_up: list[Path] = []

    def download(self, video: dict) -> Path:
        self.wav_path.write_bytes(b"RIFF")
        return self.wav_path

    def cleanup(self, wav_path: Path) -> None:
        self.cleaned_up.append(wav_path)


class FakeAsrClient:
    def __init__(self, entries, error: Exception | None = None):
        self.entries = entries
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def transcribe(self, audio_path: str, *, model: str):
        self.calls.append((audio_path, model))
        if self.error:
            raise self.error
        return self.entries


@pytest.mark.asyncio
async def test_no_subtitles_falls_back_to_asr(sqlite: SQLiteClient, tmp_path: Path):
    video = make_video("video-1", "bilibili")
    await sqlite.create_video(
        video_id=video["id"], platform=video["platform"],
        title=video["title"], url=video["url"],
    )
    downloader = FakeAudioDownloader(tmp_path)
    asr = FakeAsrClient([SubtitleEntry(start_seconds=0.0, text="ASR 第一段")])
    pipeline = VideoPipeline(
        sqlite=sqlite,
        data_dir=tmp_path,
        subtitle_client=FakeSubtitleClient([]),  # no soft subtitles
        audio_downloader=downloader,
        asr_client=asr,
        asr_model="custom/asr-model",
    )

    result = await pipeline.process_with_asr(video)

    assert result.status == "completed"
    assert asr.calls == [(str(downloader.wav_path), "custom/asr-model")]
    assert downloader.cleaned_up == [downloader.wav_path]
    assert "ASR 第一段" in Path(result.document_path).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_asr_failure_cleans_up_and_fails(sqlite: SQLiteClient, tmp_path: Path):
    from core.video.asr_client import AsrError

    video = make_video("video-1", "bilibili")
    downloader = FakeAudioDownloader(tmp_path)
    asr = FakeAsrClient([], error=AsrError("ASR service unreachable"))
    pipeline = VideoPipeline(
        sqlite=sqlite,
        data_dir=tmp_path,
        subtitle_client=FakeSubtitleClient([]),
        audio_downloader=downloader,
        asr_client=asr,
        asr_model="iic/SenseVoiceSmall",
    )

    result = await pipeline.process_with_asr(video)

    assert result.status == "failed"
    assert "ASR service unreachable" in result.error
    assert downloader.cleaned_up == [downloader.wav_path]


@pytest.mark.asyncio
async def test_douyin_video_goes_straight_to_asr(
    sqlite: SQLiteClient, tmp_path: Path
):
    video = make_video("douyin-1", "douyin")
    await sqlite.create_video(
        video_id=video["id"], platform=video["platform"],
        title=video["title"], url=video["url"],
    )
    downloader = FakeAudioDownloader(tmp_path)
    asr = FakeAsrClient([SubtitleEntry(start_seconds=0.0, text="抖音内容")])
    subtitle_client = FakeSubtitleClient(
        [SubtitleEntry(start_seconds=0.0, text="不应被调用")]
    )
    pipeline = VideoPipeline(
        sqlite=sqlite,
        data_dir=tmp_path,
        subtitle_client=subtitle_client,
        douyin_downloader=downloader,
        asr_client=asr,
        asr_model="custom/asr-model",
    )

    result = await pipeline.process(video)

    assert result.status == "completed"
    assert asr.calls == [(str(downloader.wav_path), "custom/asr-model")]
    # Bilibili subtitle client must not be touched for douyin.
    assert subtitle_client.calls == 0
    assert "抖音内容" in Path(result.document_path).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_douyin_without_downloader_fails_with_clear_error(
    sqlite: SQLiteClient, tmp_path: Path
):
    pipeline = VideoPipeline(
        sqlite=sqlite, data_dir=tmp_path, subtitle_client=FakeSubtitleClient([])
    )
    video = make_video("douyin-1", "douyin")

    result = await pipeline.process(video)

    assert result.status == "failed"
    assert "douyin" in result.error.lower()
