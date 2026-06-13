"""Tests for video record API endpoints."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api import videos
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


def test_process_video_passes_configured_bilibili_cookie_to_pipeline(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
):
    created = _create_video(client)
    seen_cookies = []

    def get_settings_spy():
        return SimpleNamespace(
            storage=SimpleNamespace(data_dir=tmp_path, keep_videos=False),
            video_processing=SimpleNamespace(
                bilibili_cookie="SESSDATA=explicit", asr_language="auto"
            ),
            models=SimpleNamespace(asr=SimpleNamespace(endpoint=None)),
        )

    def pipeline_init_spy(self, *, sqlite, data_dir, bilibili_cookie="", **kwargs):
        seen_cookies.append(bilibili_cookie)

    async def process_spy(self, video: dict) -> VideoProcessingResult:
        return VideoProcessingResult(video_id=video["id"], status="completed")

    monkeypatch.setattr(videos, "get_settings", get_settings_spy)
    monkeypatch.setattr(VideoPipeline, "__init__", pipeline_init_spy)
    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 200
    assert seen_cookies == ["SESSDATA=explicit"]


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


def test_process_completed_video_keeps_completed_status(client: TestClient, monkeypatch):
    created = _create_video(client)
    completed = _set_video_status(client, created["id"], "completed")
    process_called = False

    async def process_spy(self, video: dict) -> VideoProcessingResult:
        nonlocal process_called
        process_called = True
        return VideoProcessingResult(video_id=video["id"], status="completed")

    monkeypatch.setattr(VideoPipeline, "process", process_spy)

    resp = client.post(f"/api/videos/{created['id']}/process")

    assert resp.status_code == 200
    assert resp.json() == completed
    assert process_called is False


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
