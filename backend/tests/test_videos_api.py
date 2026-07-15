"""Tests for video record API endpoints."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from api import videos
from core.video.bilibili import (
    BilibiliSubtitleClient,
    REASON_NO_SUBTITLES,
    REASON_NON_CHINESE_SUBTITLES,
    outcome_for,
)
from core.video.douyin import DouyinMetadata
from core.video.pipeline import VideoPipeline, VideoProcessingResult
from core.video.youtube import (
    YouTubeError,
    YouTubeSubtitleClient,
    youtube_outcome,
)
from main import app
from storage.sqlite_client import SQLiteClient


@pytest.fixture
async def sqlite(tmp_path: Path):
    client = SQLiteClient(tmp_path / "metadata.db")
    await client.connect()
    try:
        yield client
    finally:
        await client.close()


@pytest.fixture(autouse=True)
def isolate_video_import_dependencies(monkeypatch, tmp_path: Path):
    def default_get_settings():
        return SimpleNamespace(
            storage=SimpleNamespace(data_dir=tmp_path, keep_videos=False),
            video_processing=SimpleNamespace(
                bilibili_cookie="",
                douyin_cookie="",
                douyin_fetcher_endpoint="",
            ),
            models=SimpleNamespace(
                asr=SimpleNamespace(endpoint=None, model="iic/SenseVoiceSmall")
            ),
    )

    monkeypatch.setattr(videos, "get_settings", default_get_settings)
    monkeypatch.setattr(
        BilibiliSubtitleClient, "fetch_metadata", lambda self, bvid: None
    )


@pytest.fixture
def client(sqlite: SQLiteClient):
    app.state.sqlite = sqlite
    app.state.qdrant = SimpleNamespace(delete_for_document=lambda document_id: None)
    return TestClient(app)


def test_create_video_from_bilibili_url(client: TestClient):
    resp = client.post(
        "/api/videos",
        json={"url": "https://www.bilibili.com/video/BV1234567890", "title": "Bili video"},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["platform"] == "bilibili"
    assert data["title"] == "Bili video"
    assert data["url"] == "https://www.bilibili.com/video/BV1234567890"
    assert data["status"] == "pending"


def test_create_bilibili_video_uses_fetched_metadata(client: TestClient, monkeypatch):
    seen_cookies = []

    def get_settings_spy():
        return SimpleNamespace(
            video_processing=SimpleNamespace(bilibili_cookie=""),
        )

    def fetch_metadata(self, bvid: str):
        assert bvid == "BV1234567890"
        seen_cookies.append(self.cookie)
        return {
            "title": "真实标题",
            "author": "作者名",
            "author_id": "456789",
            "duration": 123,
        }

    monkeypatch.setattr(videos, "get_settings", get_settings_spy)
    monkeypatch.setattr(BilibiliSubtitleClient, "fetch_metadata", fetch_metadata)

    resp = client.post(
        "/api/videos",
        json={"url": "https://www.bilibili.com/video/BV1234567890"},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "真实标题"
    assert data["author"] == "作者名"
    assert data["author_id"] == "456789"
    assert data["duration"] == 123
    assert seen_cookies == [""]


def test_create_bilibili_video_falls_back_when_metadata_fetch_fails(
    client: TestClient, monkeypatch
):
    def fetch_metadata(self, bvid: str):
        raise OSError("network down")

    monkeypatch.setattr(BilibiliSubtitleClient, "fetch_metadata", fetch_metadata)

    url = "https://www.bilibili.com/video/BV1234567890"
    resp = client.post("/api/videos", json={"url": url})

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == url
    assert data["author"] is None
    assert data["author_id"] is None
    assert data["duration"] is None


def test_create_bilibili_page_uses_distinct_video_id(client: TestClient, monkeypatch):
    monkeypatch.setattr(BilibiliSubtitleClient, "fetch_metadata", lambda self, bvid: None)

    first = client.post(
        "/api/videos",
        json={"url": "https://www.bilibili.com/video/BV1234567890?p=1"},
    )
    second = client.post(
        "/api/videos",
        json={"url": "https://www.bilibili.com/video/BV1234567890?p=2"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == "BV1234567890"
    assert second.json()["id"] == "BV1234567890-p2"


def test_create_video_from_douyin_url(client: TestClient):
    resp = client.post(
        "/api/videos",
        json={"url": "https://www.douyin.com/video/1234567890"},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["platform"] == "douyin"
    assert data["title"] == "https://www.douyin.com/video/1234567890"
    assert data["status"] == "pending"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123",
        "https://youtu.be/dQw4w9WgXcQ?t=10",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
    ],
)
def test_create_youtube_video_uses_probed_metadata(
    client: TestClient, monkeypatch, url: str
):
    seen_urls = []

    def fetch_metadata(self, source_url: str):
        seen_urls.append(source_url)
        return {
            "id": "dQw4w9WgXcQ",
            "title": "YouTube title",
            "author": "Channel name",
            "author_id": "UC-stable-id",
            "duration": 213,
        }

    monkeypatch.setattr(YouTubeSubtitleClient, "fetch_metadata", fetch_metadata)

    resp = client.post("/api/videos", json={"url": url})

    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == "dQw4w9WgXcQ"
    assert data["platform"] == "youtube"
    assert data["title"] == "YouTube title"
    assert data["author"] == "Channel name"
    assert data["author_id"] == "UC-stable-id"
    assert data["duration"] == 213
    assert data["url"] == url
    assert seen_urls == [url]


def test_create_youtube_video_rejects_metadata_failure_before_persistence(
    client: TestClient, monkeypatch
):
    def fetch_metadata(self, source_url: str):
        raise YouTubeError("Could not fetch YouTube video metadata")

    monkeypatch.setattr(YouTubeSubtitleClient, "fetch_metadata", fetch_metadata)

    resp = client.post(
        "/api/videos",
        json={"url": "https://youtu.be/dQw4w9WgXcQ"},
    )

    assert resp.status_code == 422
    assert "Could not import this YouTube video" in resp.json()["detail"]
    assert client.get("/api/videos").json() == []


def test_create_youtube_video_rejects_playlist_only_url(client: TestClient):
    resp = client.post(
        "/api/videos",
        json={"url": "https://www.youtube.com/playlist?list=PL123"},
    )

    assert resp.status_code == 422
    assert "single YouTube" in resp.json()["detail"]
    assert client.get("/api/videos").json() == []


def test_create_douyin_video_uses_fetched_metadata(client: TestClient, monkeypatch):
    def get_settings_spy():
        return SimpleNamespace(
            video_processing=SimpleNamespace(
                douyin_cookie="msToken=explicit",
                douyin_fetcher_endpoint="http://metadata-fetcher.test",
            )
        )

    def fake_build_http_resolver(endpoint: str):
        assert endpoint == "http://metadata-fetcher.test"

        def resolve(aweme_id: str, cookie: str):
            assert aweme_id == "1234567890"
            assert cookie == "msToken=explicit"
            return DouyinMetadata(
                video_url="https://cdn.example.com/video.mp4",
                title="抖音标题",
                author="抖音作者",
                author_id="sec-user",
                duration=42,
            )

        return resolve

    monkeypatch.setattr(videos, "get_settings", get_settings_spy)
    monkeypatch.setattr(videos, "build_douyin_http_resolver", fake_build_http_resolver)

    url = "https://www.douyin.com/video/1234567890"
    resp = client.post(
        "/api/videos",
        json={"url": url},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "抖音标题"
    assert data["author"] == "抖音作者"
    assert data["author_id"] == "sec-user"
    assert data["duration"] == 42
    assert data["url"] == url
    assert "video_url" not in data


def test_create_video_rejects_unknown_platform(client: TestClient):
    resp = client.post("/api/videos", json={"url": "https://example.com/video/1"})

    assert resp.status_code == 422
    assert resp.json()["detail"] == "Only Bilibili, Douyin, and YouTube URLs are supported"


def test_list_and_get_videos(client: TestClient):
    created = client.post(
        "/api/videos",
        json={"url": "https://www.bilibili.com/video/BV1234567890", "title": "Bili video"},
    ).json()

    list_resp = client.get("/api/videos")
    get_resp = client.get(f"/api/videos/{created['id']}")

    assert list_resp.status_code == 200
    assert [video["id"] for video in list_resp.json()] == [created["id"]]
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == created["id"]


def test_get_missing_video_returns_404(client: TestClient):
    resp = client.get("/api/videos/missing")

    assert resp.status_code == 404


def test_update_video_status(client: TestClient):
    created = client.post(
        "/api/videos",
        json={"url": "https://www.bilibili.com/video/BV1234567890"},
    ).json()

    resp = client.patch(f"/api/videos/{created['id']}/status", json={"status": "processing"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "processing"


def _create_video(client: TestClient) -> dict:
    return client.post(
        "/api/videos",
        json={"url": "https://www.bilibili.com/video/BV1234567890"},
    ).json()


def _set_video_status(client: TestClient, video_id: str, video_status: str) -> dict:
    return client.patch(
        f"/api/videos/{video_id}/status",
        json={"status": video_status},
    ).json()


def test_process_pending_video_completes_record(client: TestClient, monkeypatch):
    created = _create_video(client)
    seen_statuses = []

    async def process_spy(self, video: dict, *, allow_non_chinese: bool = False) -> VideoProcessingResult:
        seen_statuses.append(video["status"])
        return VideoProcessingResult(video_id=video["id"], status="completed")

    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == created["id"]
    assert data["status"] == "completed"
    assert seen_statuses == ["processing"]


def test_process_asr_choice_uses_forced_asr_path(client: TestClient, monkeypatch):
    created = _create_video(client)
    seen_video_ids = []

    async def process_with_asr_spy(
        self, video: dict, *, allow_non_chinese: bool = False
    ) -> VideoProcessingResult:
        seen_video_ids.append(video["id"])
        return VideoProcessingResult(video_id=video["id"], status="completed")

    async def process_unexpected(self, video: dict, **kwargs):
        raise AssertionError("subtitle path must not run after the ASR choice")

    monkeypatch.setattr(VideoPipeline, "process_with_asr", process_with_asr_spy)
    monkeypatch.setattr(VideoPipeline, "process", process_unexpected)

    resp = client.post(
        f"/api/videos/{created['id']}/process?subtitle_fallback=asr"
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert seen_video_ids == [created["id"]]


def test_check_subtitles_treats_bilibili_automatic_track_as_no_official_subtitles(
    client: TestClient, monkeypatch
):
    created = _create_video(client)

    def fetch_outcome(self, video, *, allow_non_chinese: bool = False):
        return SimpleNamespace(
            has_subtitles=True,
            reason="ok",
            message="Subtitles available.",
            source="automatic",
            available_languages=(),
        )

    monkeypatch.setattr(BilibiliSubtitleClient, "fetch_outcome", fetch_outcome)

    resp = client.get(f"/api/videos/{created['id']}/check-subtitles")

    assert resp.status_code == 200
    assert resp.json()["has_subtitles"] is False
    assert resp.json()["reason"] == "no_subtitles"


@pytest.mark.parametrize(
    ("configured_model", "expected_model"),
    [
        ("custom/asr-model", "custom/asr-model"),
        (None, "iic/SenseVoiceSmall"),
    ],
    ids=["configured-asr-model", "default-asr-model"],
)
def test_process_video_passes_configured_cookie_and_asr_model_to_pipeline(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
    configured_model: str | None,
    expected_model: str,
):
    created = _create_video(client)
    seen_cookies = []
    seen_asr_models = []

    def get_settings_spy():
        return SimpleNamespace(
            storage=SimpleNamespace(data_dir=tmp_path, keep_videos=False),
            video_processing=SimpleNamespace(
                bilibili_cookie="SESSDATA=explicit",
                douyin_cookie="", douyin_fetcher_endpoint="http://localhost:8002"
            ),
            models=SimpleNamespace(
                asr=SimpleNamespace(
                    endpoint=None,
                    model=configured_model,
                )
            ),
        )

    def pipeline_init_spy(self, *, sqlite, data_dir, cookie="", **kwargs):
        seen_cookies.append(cookie)
        seen_asr_models.append(kwargs["asr_model"])

    async def process_spy(self, video: dict, *, allow_non_chinese: bool = False) -> VideoProcessingResult:
        return VideoProcessingResult(video_id=video["id"], status="completed")

    monkeypatch.setattr(videos, "get_settings", get_settings_spy)
    monkeypatch.setattr(VideoPipeline, "__init__", pipeline_init_spy)
    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 200
    assert seen_cookies == ["SESSDATA=explicit"]
    assert seen_asr_models == [expected_model]


def test_process_video_builds_separate_cookie_free_youtube_downloader(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
):
    created = _create_video(client)
    seen_downloader_options = []

    def get_settings_spy():
        return SimpleNamespace(
            storage=SimpleNamespace(data_dir=tmp_path, keep_videos=False),
            video_processing=SimpleNamespace(
                bilibili_cookie="SESSDATA=explicit",
                douyin_cookie="",
                douyin_fetcher_endpoint="",
            ),
            models=SimpleNamespace(
                asr=SimpleNamespace(endpoint=None, model="iic/SenseVoiceSmall")
            ),
        )

    class RecordingAudioDownloader:
        def __init__(self, **kwargs):
            seen_downloader_options.append(
                (kwargs.get("cookie_str"), kwargs.get("no_playlist"))
            )

    def pipeline_init_spy(self, **kwargs):
        assert kwargs["audio_downloader"] is not kwargs["youtube_audio_downloader"]

    async def process_spy(
        self, video: dict, *, allow_non_chinese: bool = False
    ) -> VideoProcessingResult:
        return VideoProcessingResult(video_id=video["id"], status="completed")

    monkeypatch.setattr(videos, "get_settings", get_settings_spy)
    monkeypatch.setattr(videos, "AudioDownloader", RecordingAudioDownloader)
    monkeypatch.setattr(VideoPipeline, "__init__", pipeline_init_spy)
    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 200
    assert seen_downloader_options == [
        ("SESSDATA=explicit", None),
        (None, True),
    ]


def test_process_video_passes_asr_protocol_and_api_key_to_client(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
):
    created = _create_video(client)
    seen_client_kwargs = []

    def get_settings_spy():
        return SimpleNamespace(
            storage=SimpleNamespace(data_dir=tmp_path, keep_videos=False),
            video_processing=SimpleNamespace(
                bilibili_cookie="",
                douyin_cookie="",
                douyin_fetcher_endpoint="http://localhost:8002",
            ),
            models=SimpleNamespace(
                asr=SimpleNamespace(
                    endpoint="https://api.xiaomimimo.com/v1",
                    model="mimo-v2.5-asr",
                    protocol="chat_audio",
                    api_key="sk-asr",
                )
            ),
        )

    class FakeAsrServiceClient:
        def __init__(self, **kwargs):
            seen_client_kwargs.append(kwargs)

    def pipeline_init_spy(self, *, sqlite, data_dir, cookie="", **kwargs):
        pass

    async def process_spy(self, video: dict, *, allow_non_chinese: bool = False) -> VideoProcessingResult:
        return VideoProcessingResult(video_id=video["id"], status="completed")

    monkeypatch.setattr(videos, "get_settings", get_settings_spy)
    monkeypatch.setattr(videos, "AsrServiceClient", FakeAsrServiceClient)
    monkeypatch.setattr(VideoPipeline, "__init__", pipeline_init_spy)
    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 200
    assert seen_client_kwargs == [
        {
            "endpoint": "https://api.xiaomimimo.com/v1",
            "protocol": "chat_audio",
            "api_key": "sk-asr",
        }
    ]


def test_process_missing_video_returns_404(client: TestClient):
    resp = client.post("/api/videos/missing/process")

    assert resp.status_code == 404


def test_process_processing_video_returns_409(client: TestClient):
    created = _create_video(client)
    _set_video_status(client, created["id"], "processing")

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 409
    assert "processing" in resp.json()["detail"]


def test_process_video_does_not_run_pipeline_when_claim_fails(
    client: TestClient,
    sqlite: SQLiteClient,
    monkeypatch,
):
    created = _create_video(client)
    process_called = False

    async def claim_spy(video_id: str) -> None:
        await sqlite.update_video_status(video_id, "processing")
        return None

    async def process_spy(self, video: dict, *, allow_non_chinese: bool = False) -> VideoProcessingResult:
        nonlocal process_called
        process_called = True
        return VideoProcessingResult(video_id=video["id"], status="completed")

    monkeypatch.setattr(sqlite, "claim_video_for_processing", claim_spy, raising=False)
    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 409
    assert "processing" in resp.json()["detail"]
    assert process_called is False


def test_process_completed_video_reprocesses_and_keeps_completed_status(
    client: TestClient,
    sqlite: SQLiteClient,
    monkeypatch,
    tmp_path: Path,
):
    created = _create_video(client)
    _set_video_status(client, created["id"], "completed")
    canonical_path = (
        tmp_path / "knowledge" / "bilibili" / "raw" / f"{created['id']}.md"
    )
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_path.write_text("# draft\n", encoding="utf-8")
    cleaned_path = (
        tmp_path / "knowledge" / "bilibili" / "cleaned" / f"{created['id']}.md"
    )
    cleaned_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned_path.write_text("# cleaned\n", encoding="utf-8")

    async def seed_documents() -> None:
        await sqlite.create_document(
            document_id="raw-doc",
            video_id=created["id"],
            file_path=str(canonical_path),
            chunk_count=3,
            status='indexed',
        )
        await sqlite.mark_document_indexed("raw-doc", chunk_count=3)
        await sqlite.create_document(
            document_id="clean-doc",
            video_id=created["id"],
            file_path=str(cleaned_path),
            chunk_count=7,
            status='indexed',
        )
        await sqlite.mark_document_indexed("clean-doc", chunk_count=7)

    import asyncio

    asyncio.run(seed_documents())

    monkeypatch.setattr(
        videos,
        "get_settings",
        lambda: SimpleNamespace(
            storage=SimpleNamespace(data_dir=tmp_path, keep_videos=False),
            video_processing=SimpleNamespace(
                bilibili_cookie="",
                douyin_cookie="",
                douyin_fetcher_endpoint="http://localhost:8002",
            ),
            models=SimpleNamespace(
                asr=SimpleNamespace(endpoint=None, model="iic/SenseVoiceSmall")
            ),
        ),
    )
    delete_mock = Mock()
    monkeypatch.setattr(app.state.qdrant, "delete_for_document", delete_mock)
    seen_statuses = []

    async def process_spy(self, video: dict, *, allow_non_chinese: bool = False) -> VideoProcessingResult:
        seen_statuses.append(video["status"])
        return VideoProcessingResult(video_id=video["id"], status="completed")

    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert seen_statuses == ["processing"]
    delete_mock.assert_called_once_with("raw-doc")

    raw_document = asyncio.run(sqlite.get_document("raw-doc"))
    assert raw_document is not None
    assert raw_document["chunk_count"] == 0
    assert raw_document["status"] == "raw"
    assert raw_document["indexed_at"] is None

    clean_document = asyncio.run(sqlite.get_document("clean-doc"))
    assert clean_document is not None
    assert clean_document["chunk_count"] == 7
    assert clean_document["status"] == "indexed"
    assert clean_document["indexed_at"] is not None


def test_process_completed_video_without_canonical_document_does_not_fail(
    client: TestClient,
    monkeypatch,
):
    created = _create_video(client)
    _set_video_status(client, created["id"], "completed")

    async def process_spy(self, video: dict, *, allow_non_chinese: bool = False) -> VideoProcessingResult:
        return VideoProcessingResult(video_id=video["id"], status="completed")

    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_process_completed_video_reset_failure_restores_completed_status(
    client: TestClient,
    sqlite: SQLiteClient,
    monkeypatch,
    tmp_path: Path,
):
    created = _create_video(client)
    _set_video_status(client, created["id"], "completed")
    canonical_path = (
        tmp_path / "knowledge" / "bilibili" / "raw" / f"{created['id']}.md"
    )
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_path.write_text("# draft\n", encoding="utf-8")

    import asyncio

    asyncio.run(
        sqlite.create_document(
            document_id="raw-doc",
            video_id=created["id"],
            file_path=str(canonical_path),
            chunk_count=3,
            status='indexed',
        )
    )
    asyncio.run(sqlite.mark_document_indexed("raw-doc", chunk_count=3))

    monkeypatch.setattr(
        videos,
        "get_settings",
        lambda: SimpleNamespace(
            storage=SimpleNamespace(data_dir=tmp_path, keep_videos=False),
            video_processing=SimpleNamespace(
                bilibili_cookie="",
                douyin_cookie="",
                douyin_fetcher_endpoint="http://localhost:8002",
            ),
            models=SimpleNamespace(
                asr=SimpleNamespace(endpoint=None, model="iic/SenseVoiceSmall")
            ),
        ),
    )

    def delete_raises(document_id: str) -> None:
        raise RuntimeError("qdrant delete failed")

    monkeypatch.setattr(app.state.qdrant, "delete_for_document", delete_raises)
    process_called = False

    async def process_spy(self, video: dict, *, allow_non_chinese: bool = False) -> VideoProcessingResult:
        nonlocal process_called
        process_called = True
        return VideoProcessingResult(video_id=video["id"], status="completed")

    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 500
    assert process_called is False
    current = asyncio.run(sqlite.get_video(created["id"]))
    assert current is not None
    assert current["status"] == "completed"


def test_process_failed_video_completes_record(client: TestClient, monkeypatch):
    created = _create_video(client)
    _set_video_status(client, created["id"], "failed")

    async def process_spy(self, video: dict, *, allow_non_chinese: bool = False) -> VideoProcessingResult:
        return VideoProcessingResult(video_id=video["id"], status="completed")

    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == created["id"]
    assert data["status"] == "completed"


def test_process_pipeline_failure_marks_video_failed(client: TestClient, monkeypatch):
    created = _create_video(client)

    async def process_spy(self, video: dict, *, allow_non_chinese: bool = False) -> VideoProcessingResult:
        return VideoProcessingResult(
            video_id=video["id"],
            status="failed",
            error="No soft subtitles found",
        )

    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == created["id"]
    assert data["status"] == "failed"


def test_process_pipeline_exception_marks_video_failed(client: TestClient, monkeypatch):
    created = _create_video(client)

    async def process_spy(self, video: dict, *, allow_non_chinese: bool = False) -> VideoProcessingResult:
        raise KeyError("boom")

    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == created["id"]
    assert data["status"] == "failed"

    stored = client.get(f"/api/videos/{created['id']}")
    assert stored.status_code == 200
    assert stored.json()["status"] == "failed"


def test_delete_video_removes_record(client: TestClient):
    created = client.post(
        "/api/videos",
        json={"url": "https://www.bilibili.com/video/BV1234567890", "title": "Bili"},
    ).json()

    resp = client.delete(f"/api/videos/{created['id']}")

    assert resp.status_code == 204
    assert client.get(f"/api/videos/{created['id']}").status_code == 404


def test_delete_missing_video_returns_404(client: TestClient):
    resp = client.delete("/api/videos/missing")

    assert resp.status_code == 404


def test_check_subtitles_not_logged_in_without_usable_cookie(client: TestClient):
    created = _create_video(client)

    resp = client.get(f"/api/videos/{created['id']}/check-subtitles")

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_subtitles"] is False
    assert data["platform"] == "bilibili"
    assert data["reason"] == "not_logged_in"
    assert "Login" in data["message"] or "login" in data["message"]
    assert data["login_path"] == "/login"


def test_check_subtitles_true_for_non_bilibili(client: TestClient):
    created = client.post(
        "/api/videos",
        json={"url": "https://www.douyin.com/video/1234567890"},
    ).json()

    resp = client.get(f"/api/videos/{created['id']}/check-subtitles")

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_subtitles"] is True
    assert data["platform"] == "douyin"
    assert data["reason"] == "ok"
    assert "available" in data["message"].lower()
    assert "login_path" not in data


def test_check_subtitles_maps_youtube_outcome(
    client: TestClient, monkeypatch
):
    monkeypatch.setattr(
        YouTubeSubtitleClient,
        "fetch_metadata",
        lambda self, url: {
            "id": "dQw4w9WgXcQ",
            "title": "YouTube title",
            "author": "Channel name",
            "author_id": "UC-stable-id",
            "duration": 213,
        },
    )
    outcome = youtube_outcome(
        REASON_NON_CHINESE_SUBTITLES,
        available_languages=("en", "ja"),
    )
    monkeypatch.setattr(
        YouTubeSubtitleClient,
        "fetch_outcome",
        lambda self, video: outcome,
    )
    created = client.post(
        "/api/videos",
        json={"url": "https://youtu.be/dQw4w9WgXcQ"},
    ).json()

    resp = client.get(f"/api/videos/{created['id']}/check-subtitles")

    assert resp.status_code == 200
    assert resp.json() == {
        "has_subtitles": False,
        "platform": "youtube",
        "reason": REASON_NON_CHINESE_SUBTITLES,
        "message": outcome.message,
        "available_languages": ["en", "ja"],
    }


def test_check_subtitles_maps_fetch_outcome(
    client: TestClient, monkeypatch, tmp_path: Path
):
    created = _create_video(client)

    def get_settings_with_cookie():
        return SimpleNamespace(
            storage=SimpleNamespace(data_dir=tmp_path, keep_videos=False),
            video_processing=SimpleNamespace(
                bilibili_cookie="SESSDATA=alive",
                douyin_cookie="",
                douyin_fetcher_endpoint="",
            ),
            models=SimpleNamespace(
                asr=SimpleNamespace(endpoint=None, model="iic/SenseVoiceSmall")
            ),
        )

    outcome = outcome_for(REASON_NO_SUBTITLES)

    def fake_fetch_outcome(self, video):
        return outcome

    monkeypatch.setattr(videos, "get_settings", get_settings_with_cookie)
    monkeypatch.setattr(BilibiliSubtitleClient, "fetch_outcome", fake_fetch_outcome)

    resp = client.get(f"/api/videos/{created['id']}/check-subtitles")

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_subtitles"] is False
    assert data["platform"] == "bilibili"
    assert data["reason"] == REASON_NO_SUBTITLES
    assert data["message"] == outcome.message
    assert "login_path" not in data


def test_check_subtitles_maps_non_chinese_available_languages(
    client: TestClient, monkeypatch, tmp_path: Path
):
    created = _create_video(client)

    def get_settings_with_cookie():
        return SimpleNamespace(
            storage=SimpleNamespace(data_dir=tmp_path, keep_videos=False),
            video_processing=SimpleNamespace(
                bilibili_cookie="SESSDATA=alive",
                douyin_cookie="",
                douyin_fetcher_endpoint="",
            ),
            models=SimpleNamespace(
                asr=SimpleNamespace(endpoint=None, model="iic/SenseVoiceSmall")
            ),
        )

    outcome = outcome_for(
        REASON_NON_CHINESE_SUBTITLES,
        available_languages=("ai-en", "ai-ja"),
    )

    def fake_fetch_outcome(self, video, *, allow_non_chinese: bool = False):
        return outcome

    monkeypatch.setattr(videos, "get_settings", get_settings_with_cookie)
    monkeypatch.setattr(BilibiliSubtitleClient, "fetch_outcome", fake_fetch_outcome)

    resp = client.get(f"/api/videos/{created['id']}/check-subtitles")

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_subtitles"] is False
    assert data["platform"] == "bilibili"
    assert data["reason"] == REASON_NON_CHINESE_SUBTITLES
    assert data["message"] == outcome.message
    assert data["available_languages"] == ["ai-en", "ai-ja"]
    assert "login_path" not in data


def test_process_video_passes_allow_non_chinese(
    client: TestClient, monkeypatch
):
    created = _create_video(client)
    seen = {}

    async def process_spy(
        self, video: dict, *, allow_non_chinese: bool = False
    ) -> VideoProcessingResult:
        seen["allow_non_chinese"] = allow_non_chinese
        return VideoProcessingResult(
            video_id=video["id"],
            status="completed",
            document_id="d1",
            document_path="x",
        )

    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(
        f"/api/videos/{created['id']}/process?allow_non_chinese=true"
    )

    assert resp.status_code == 200
    assert seen.get("allow_non_chinese") is True


def test_process_video_defaults_allow_non_chinese_false(
    client: TestClient, monkeypatch
):
    created = _create_video(client)
    seen = {}

    async def process_spy(
        self, video: dict, *, allow_non_chinese: bool = False
    ) -> VideoProcessingResult:
        seen["allow_non_chinese"] = allow_non_chinese
        return VideoProcessingResult(video_id=video["id"], status="completed")

    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 200
    assert seen.get("allow_non_chinese") is False
