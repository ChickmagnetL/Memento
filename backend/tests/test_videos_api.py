"""Tests for video record API endpoints."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from api import videos
from core.video.bilibili import BilibiliSubtitleClient, BilibiliSubtitleError
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
    canonical_path = tmp_path / "knowledge" / "bilibili" / f"{created['id']}.md"
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_path.write_text("# draft\n", encoding="utf-8")
    cleaned_path = canonical_path.parent / f"{created['id']}.clean.md"
    cleaned_path.write_text("# cleaned\n", encoding="utf-8")

    async def seed_documents() -> None:
        await sqlite.create_document(
            document_id="raw-doc",
            video_id=created["id"],
            file_path=str(canonical_path),
            chunk_count=3,
            is_indexed=True,
        )
        await sqlite.mark_document_indexed("raw-doc", chunk_count=3)
        await sqlite.create_document(
            document_id="clean-doc",
            video_id=created["id"],
            file_path=str(cleaned_path),
            chunk_count=7,
            is_indexed=True,
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
    assert raw_document["is_indexed"] == 0
    assert raw_document["indexed_at"] is None

    clean_document = asyncio.run(sqlite.get_document("clean-doc"))
    assert clean_document is not None
    assert clean_document["chunk_count"] == 7
    assert clean_document["is_indexed"] == 1
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
    canonical_path = tmp_path / "knowledge" / "bilibili" / f"{created['id']}.md"
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_path.write_text("# draft\n", encoding="utf-8")

    import asyncio

    asyncio.run(
        sqlite.create_document(
            document_id="raw-doc",
            video_id=created["id"],
            file_path=str(canonical_path),
            chunk_count=3,
            is_indexed=True,
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
