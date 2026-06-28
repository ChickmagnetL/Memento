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


class _RunResult:
    """Minimal stand-in for a pydantic-ai agent run result."""

    def __init__(self, output: str):
        self.output = output


class _FakeAgent:
    """Duck-typed agent: run_stream raises (forces fallback); run succeeds.

    Mirrors how chat.py uses the agent: ``async with agent.run_stream(...)``
    then ``result.stream_text(delta=True)``, and the non-streaming
    ``agent.run(...).output``.
    """

    def __init__(self, *, stream_error: Exception, run_output: str | None):
        self._stream_error = stream_error
        self._run_output = run_output

    async def run_stream(self, *args, **kwargs):
        raise self._stream_error

    async def run(self, *args, **kwargs):
        if self._run_output is None:
            raise self._stream_error
        return _RunResult(self._run_output)


def test_chat_falls_back_to_non_streaming_run(client: TestClient, monkeypatch):
    """run_stream raising falls back to agent.run; output is still persisted."""
    monkeypatch.setattr(
        chat_api,
        "build_agent",
        lambda model: _FakeAgent(
            stream_error=RuntimeError("stream blew up"),
            run_output="fallback reply",
        ),
    )

    events = _parse_sse(
        client.post("/api/chat", json={"message": "hi"}).text
    )

    text = "".join(e["delta"] for e in events if e["type"] == "text")
    assert text == "fallback reply"
    done = [e for e in events if e["type"] == "done"]
    assert len(done) == 1
    session_id = done[0]["session_id"]

    # The fallback output IS persisted as the assistant message.
    messages = client.get(f"/api/sessions/{session_id}/messages").json()
    assert any(m["role"] == "assistant" and m["content"] == "fallback reply"
               for m in messages)


def test_chat_does_not_persist_assistant_on_failure(client: TestClient, monkeypatch):
    """When generation fully fails, no assistant message is written."""
    monkeypatch.setattr(chat_api, "_RETRY_BACKOFF_S", 0)
    monkeypatch.setattr(
        chat_api,
        "build_agent",
        lambda model: _FakeAgent(
            stream_error=RuntimeError("generation unavailable"),
            run_output=None,
        ),
    )

    # Pre-create the session so we know its id even though streaming fails
    # (the error event carries no session_id).
    session_id = client.post(
        "/api/sessions", json={"title": "failed turn"}
    ).json()["id"]

    events = _parse_sse(
        client.post(
            "/api/chat", json={"message": "hi", "session_id": session_id}
        ).text
    )

    assert any(e["type"] == "error" for e in events)
    assert not any(e["type"] in ("text", "done") for e in events)

    # Only the user message exists; the assistant was NOT persisted.
    messages = client.get(f"/api/sessions/{session_id}/messages").json()
    assert [m["role"] for m in messages] == ["user"]
