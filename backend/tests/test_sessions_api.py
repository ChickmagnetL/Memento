"""Tests for the chat sessions REST API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app
from storage.sqlite_client import SQLiteClient


@pytest.fixture
async def client(tmp_path: Path):
    """Isolated TestClient with a fresh per-test SQLite database.

    Mirrors the test_chat_api.py pattern: open the app lifespan via
    TestClient(app), then override app.state.sqlite with our tmp database so
    the routes under test read/write the isolated store.
    """
    sqlite = SQLiteClient(tmp_path / "metadata.db")
    await sqlite.connect()
    with TestClient(app) as test_client:
        app.state.sqlite = sqlite
        yield test_client
    await sqlite.close()


def test_list_sessions_empty(client: TestClient):
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_session_returns_id_and_title(client: TestClient):
    resp = client.post("/api/sessions", json={"title": "hello"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "hello"
    assert isinstance(body["id"], str) and body["id"]


def test_list_sessions_returns_created(client: TestClient):
    created = client.post("/api/sessions", json={"title": "x"}).json()
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == created["id"]
    assert body[0]["title"] == "x"


def test_get_messages_empty_for_new_session(client: TestClient):
    created = client.post("/api/sessions", json={"title": "x"}).json()
    resp = client.get(f"/api/sessions/{created['id']}/messages")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_messages_returns_404_for_missing_session(client: TestClient):
    resp = client.get("/api/sessions/does-not-exist/messages")
    assert resp.status_code == 404


def test_delete_session_returns_404_for_missing(client: TestClient):
    resp = client.delete("/api/sessions/does-not-exist")
    assert resp.status_code == 404


def test_delete_session_removes_it(client: TestClient):
    created = client.post("/api/sessions", json={"title": "x"}).json()
    resp = client.delete(f"/api/sessions/{created['id']}")
    assert resp.status_code == 204
    # gone from list
    body = client.get("/api/sessions").json()
    assert all(s["id"] != created["id"] for s in body)
    # subsequent delete is now 404
    assert client.delete(f"/api/sessions/{created['id']}").status_code == 404
