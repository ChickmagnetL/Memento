"""Tests for the SSE chat API (TestModel, no real LLM)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

from api import chat as chat_api
from main import app
from storage.sqlite_client import SQLiteClient
from storage.qdrant_client import QdrantStore


class FakeEmbeddingClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]


@pytest.fixture
async def client(tmp_path: Path, monkeypatch):
    sqlite = SQLiteClient(tmp_path / "metadata.db")
    await sqlite.connect()
    qdrant = QdrantStore(tmp_path / "qdrant")
    qdrant.connect(vector_size=4)
    monkeypatch.setattr(
        chat_api,
        "build_chat_model",
        lambda: TestModel(custom_output_text="这是回答"),
    )
    monkeypatch.setattr(
        chat_api, "build_embedding_client", lambda: FakeEmbeddingClient()
    )
    with TestClient(app) as test_client:
        # Override lifespan's state with our test stores.
        app.state.sqlite = sqlite
        app.state.qdrant = qdrant
        yield test_client
    await sqlite.close()
    qdrant.close()


def _parse_sse(body: str) -> list[dict]:
    events = []
    for line in body.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))
    return events


def test_chat_streams_text_and_done(client: TestClient):
    response = client.post("/api/chat", json={"message": "你好"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)
    text = "".join(e["delta"] for e in events if e["type"] == "text")
    assert "这是回答" in text
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["session_id"]


def test_chat_session_persists_history(client: TestClient):
    """Conversation persists to SQLite; two turns leave four messages."""
    first = _parse_sse(client.post("/api/chat", json={"message": "第一句"}).text)
    session_id = next(e for e in first if e["type"] == "done")["session_id"]

    client.post("/api/chat", json={"message": "第二句", "session_id": session_id})

    # Messages persisted in DB (queried via the sessions REST API).
    messages = client.get(f"/api/sessions/{session_id}/messages").json()
    # Two turns of user + assistant messages accumulated.
    assert len(messages) >= 4
    roles = [m["role"] for m in messages]
    assert roles.count("user") >= 2
    assert roles.count("assistant") >= 2

    # Session title = first user message (set at create time, truncated).
    sessions = client.get("/api/sessions").json()
    target = next(s for s in sessions if s["id"] == session_id)
    assert target["title"] == "第一句"


def test_chat_404_on_unknown_session(client: TestClient):
    response = client.post(
        "/api/chat", json={"message": "hi", "session_id": "does-not-exist"}
    )
    assert response.status_code == 404


def test_chat_rejects_blank_message(client: TestClient):
    assert (
        client.post("/api/chat", json={"message": "   "}).status_code == 422
    )
