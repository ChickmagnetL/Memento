"""Tests for memories REST API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app
from storage.sqlite_client import SQLiteClient


@pytest.fixture
async def client(tmp_path: Path):
    """Isolated TestClient with a fresh per-test SQLite database.

    Mirrors the test_sessions_api.py pattern: open the app lifespan via
    TestClient(app), then override app.state.sqlite with our tmp database so
    the routes under test read/write the isolated store.
    """
    sqlite = SQLiteClient(tmp_path / "metadata.db")
    await sqlite.connect()
    with TestClient(app) as test_client:
        app.state.sqlite = sqlite
        yield test_client
    await sqlite.close()


def test_list_memories_empty(client: TestClient):
    resp = client.get("/api/memories")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_memory(client: TestClient):
    resp = client.post("/api/memories", json={"content": "在学 React", "category": "study"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["content"] == "在学 React"
    assert body["category"] == "study"


def test_delete_memory_returns_404_for_missing(client: TestClient):
    resp = client.delete("/api/memories/does-not-exist")
    assert resp.status_code == 404


def test_create_and_delete_memory(client: TestClient):
    created = client.post("/api/memories", json={"content": "x"}).json()
    resp = client.delete(f"/api/memories/{created['id']}")
    assert resp.status_code == 204
    # gone from list
    body = client.get("/api/memories").json()
    assert all(m["id"] != created["id"] for m in body)
    # subsequent delete is now 404
    assert client.delete(f"/api/memories/{created['id']}").status_code == 404