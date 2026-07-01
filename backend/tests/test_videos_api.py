"""Tests for video record API endpoints."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from api import videos
from core.video.bilibili import BilibiliSubtitleClient, BilibiliSubtitleError
from core.video.douyin import DouyinMetadata
from core.video.pipeline import VideoPipeline, VideoProcessingResult
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
        raise AssertionError("Bilibili metadata import should not read settings")

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
    assert resp.json()["detail"] == "Only Bilibili and Douyin URLs are supported"


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

    async def process_spy(self, video: dict) -> VideoProcessingResult:
        seen_statuses.append(video["status"])
        return VideoProcessingResult(video_id=video["id"], status="completed")

    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == created["id"]
    assert data["status"] == "completed"
    assert seen_statuses == ["processing"]


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

    async def process_spy(self, video: dict) -> VideoProcessingResult:
        return VideoProcessingResult(video_id=video["id"], status="completed")

    monkeypatch.setattr(videos, "get_settings", get_settings_spy)
    monkeypatch.setattr(VideoPipeline, "__init__", pipeline_init_spy)
    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 200
    assert seen_cookies == ["SESSDATA=explicit"]
    assert seen_asr_models == [expected_model]


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

    async def process_spy(self, video: dict) -> VideoProcessingResult:
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

    async def process_spy(self, video: dict) -> VideoProcessingResult:
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

    async def process_spy(self, video: dict) -> VideoProcessingResult:
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

    async def process_spy(self, video: dict) -> VideoProcessingResult:
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

    async def process_spy(self, video: dict) -> VideoProcessingResult:
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

    async def process_spy(self, video: dict) -> VideoProcessingResult:
        return VideoProcessingResult(video_id=video["id"], status="completed")

    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == created["id"]
    assert data["status"] == "completed"


def test_process_pipeline_failure_marks_video_failed(client: TestClient, monkeypatch):
    created = _create_video(client)

    async def process_spy(self, video: dict) -> VideoProcessingResult:
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

    async def process_spy(self, video: dict) -> VideoProcessingResult:
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


def test_check_subtitles_returns_false_for_bilibili_without_cookie(
    client: TestClient, monkeypatch
):
    created = _create_video(client)

    def fake_fetch(self, video):
        return []

    monkeypatch.setattr(BilibiliSubtitleClient, "fetch", fake_fetch)

    resp = client.get(f"/api/videos/{created['id']}/check-subtitles")

    assert resp.status_code == 200
    assert resp.json() == {"has_subtitles": False, "platform": "bilibili"}


def test_check_subtitles_true_for_non_bilibili(client: TestClient):
    created = client.post(
        "/api/videos",
        json={"url": "https://www.douyin.com/video/1234567890"},
    ).json()

    resp = client.get(f"/api/videos/{created['id']}/check-subtitles")

    assert resp.status_code == 200
    assert resp.json() == {"has_subtitles": True, "platform": "douyin"}


@pytest.mark.parametrize(
    "exc",
    [BilibiliSubtitleError("malformed"), OSError("network down")],
    ids=["subtitle-error", "network-error"],
)
def test_check_subtitles_returns_false_when_fetch_fails(
    client: TestClient, monkeypatch, exc
):
    created = _create_video(client)

    def fake_fetch(self, video):
        raise exc

    monkeypatch.setattr(BilibiliSubtitleClient, "fetch", fake_fetch)

    resp = client.get(f"/api/videos/{created['id']}/check-subtitles")

    assert resp.status_code == 200
    assert resp.json() == {"has_subtitles": False, "platform": "bilibili"}
