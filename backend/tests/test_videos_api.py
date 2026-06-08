"""Tests for video record API endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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
