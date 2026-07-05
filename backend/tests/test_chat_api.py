"""Tests for the SSE chat API (TestModel, no real LLM)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import AgentRunResult
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    PartDeltaEvent,
    TextPartDelta,
    ToolCallPart,
)
from pydantic_ai.models.test import TestModel
from pydantic_ai.run import AgentRunResultEvent

from api import chat as chat_api
from core.rag.embedding import EmbeddingError
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
    # lookup_documents searches the summary collection; ensure it exists so
    # TestModel's tool call does not crash on a missing collection.
    qdrant.ensure_summary_collection(vector_size=4)
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


def test_chat_continues_when_embedding_client_build_fails(
    client: TestClient, monkeypatch
):
    def raise_embedding_error():
        raise EmbeddingError("embedding service unavailable")

    monkeypatch.setattr(chat_api, "build_embedding_client", raise_embedding_error)

    response = client.post("/api/chat", json={"message": "你好"})

    assert response.status_code == 200
    events = _parse_sse(response.text)
    text = "".join(e["delta"] for e in events if e["type"] == "text")
    assert "这是回答" in text
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["session_id"]
    assert not any(e["type"] == "error" for e in events)


class _FakeEventStream:
    """Async ctx + async iterator duck-type for agent.run_stream_events().

    After draining the scripted events, yields a terminal AgentRunResultEvent
    carrying final_output (the real stream emits one of these last)."""

    def __init__(self, events: list, final_output: str):
        self._events = list(events)
        self._terminal = AgentRunResultEvent(
            result=AgentRunResult(output=final_output)
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._events:
            return self._events.pop(0)
        if self._terminal is not None:
            terminal = self._terminal
            self._terminal = None
            return terminal
        raise StopAsyncIteration


class _FakeEventsAgent:
    """Agent whose run_stream_events() yields a scripted event list then a
    terminal AgentRunResultEvent carrying final_output."""

    def __init__(self, *, events: list, final_output: str):
        self._events = events
        self._final_output = final_output

    def run_stream_events(self, message, *, deps=None, message_history=None):
        return _FakeEventStream(self._events, self._final_output)


class _RaisingStreamAgent:
    """Agent whose run_stream_events() raises on __aenter__: simulates a
    streaming failure that exhausts all retries -> error event, no persist."""

    def __init__(self, exc: Exception):
        self._exc = exc

    def run_stream_events(self, message, *, deps=None, message_history=None):
        return self

    async def __aenter__(self):
        raise self._exc

    async def __aexit__(self, *exc):
        return False


class _MidStreamRaisingStream:
    """Async ctx + iterator: yields scripted events, then raises mid-stream
    (no terminal result). Simulates a failure after partial content has
    already reached the client."""

    def __init__(self, events: list, exc: Exception):
        self._events = list(events)
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._events:
            return self._events.pop(0)
        raise self._exc


class _MidStreamRaisingAgent:
    """Agent whose run_stream_events() yields some events then raises."""

    def __init__(self, *, events: list, exc: Exception):
        self._events = events
        self._exc = exc

    def run_stream_events(self, message, *, deps=None, message_history=None):
        return _MidStreamRaisingStream(self._events, self._exc)


def test_chat_errors_and_skips_persist_when_streaming_always_fails(
    client: TestClient, monkeypatch
):
    """When every streaming retry fails (before any content is sent), an error
    event is emitted and no assistant message is persisted."""
    monkeypatch.setattr(chat_api, "_RETRY_BACKOFF_S", 0)
    monkeypatch.setattr(
        chat_api, "build_agent",
        lambda model, system_prompt=None: _RaisingStreamAgent(RuntimeError("nope")),
    )
    # Pre-create the session so its id is known even when the turn fails.
    session_id = client.post(
        "/api/sessions", json={"title": "fails"}
    ).json()["id"]
    events = _parse_sse(
        client.post(
            "/api/chat", json={"message": "hi", "session_id": session_id}
        ).text
    )
    assert any(e["type"] == "error" for e in events)
    assert not any(e["type"] == "done" for e in events)
    # Strong DB assertion: only the up-front user message exists, no assistant.
    messages = client.get(f"/api/sessions/{session_id}/messages").json()
    roles = [m["role"] for m in messages]
    assert roles == ["user"]


def test_chat_emits_error_after_partial_stream_without_retry(
    client: TestClient, monkeypatch
):
    """A failure AFTER content has been streamed surfaces an error event with
    the partial text intact — no retry (which would duplicate text), no done."""
    monkeypatch.setattr(chat_api, "_RETRY_BACKOFF_S", 0)
    events_seq = [
        PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="部分")),
    ]
    monkeypatch.setattr(
        chat_api,
        "build_agent",
        lambda model, system_prompt=None: _MidStreamRaisingAgent(
            events=events_seq, exc=RuntimeError("mid-stream boom"),
        ),
    )
    events = _parse_sse(client.post("/api/chat", json={"message": "hi"}).text)
    text_events = [e for e in events if e["type"] == "text"]
    assert len(text_events) == 1, "partial delta must reach client exactly once (no retry)"
    assert text_events[0]["delta"] == "部分"
    assert any(e["type"] == "error" for e in events), "error must be surfaced"
    assert not any(e["type"] == "done" for e in events), "no done on mid-stream failure"


class _NonStreamingRunSpy:
    """Wraps a streaming agent and records whether the non-streaming
    ``agent.run()`` is ever invoked (it must not be on a streamed turn)."""

    def __init__(self, inner):
        self._inner = inner
        self.run_called = False

    def run_stream_events(self, message, *, deps=None, message_history=None):
        return self._inner.run_stream_events(
            message, deps=deps, message_history=message_history
        )

    def run(self, *args, **kwargs):
        self.run_called = True
        raise AssertionError("agent.run() must not be called on a streamed turn")


def test_chat_never_calls_non_streaming_agent_run(
    client: TestClient, monkeypatch
):
    """A successful streamed turn must never invoke the non-streaming
    agent.run() (the path that loses system messages on some OpenAI-compatible
    proxies). Replaces two tautological log-string assertions with a faithful
    spy on the agent instance."""
    spy_holder: dict = {}

    def build_spy(model, system_prompt=None):
        inner = _FakeEventsAgent(
            events=[PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="ok"))],
            final_output="ok",
        )
        spy = _NonStreamingRunSpy(inner)
        spy_holder["spy"] = spy
        return spy

    monkeypatch.setattr(chat_api, "build_agent", build_spy)
    events = _parse_sse(client.post("/api/chat", json={"message": "hi"}).text)
    assert any(e["type"] == "done" for e in events), "turn must complete via streaming"
    assert not spy_holder["spy"].run_called, "agent.run() must not be called"


def test_chat_streams_multiple_text_deltas(client: TestClient, monkeypatch):
    """Multiple text PartDeltaEvents yield multiple `text` SSE events (real
    streaming), not one aggregated blob."""
    events_seq = [
        PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="第一")),
        PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="第二")),
        PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="第三")),
    ]
    monkeypatch.setattr(
        chat_api,
        "build_agent",
        lambda model, system_prompt=None: _FakeEventsAgent(
            events=events_seq, final_output="第一第二第三",
        ),
    )
    events = _parse_sse(client.post("/api/chat", json={"message": "hi"}).text)
    text_events = [e for e in events if e["type"] == "text"]
    assert len(text_events) == 3, "expected one text event per delta"
    assert "".join(e["delta"] for e in text_events) == "第一第二第三"
    done = [e for e in events if e["type"] == "done"]
    assert len(done) == 1


def test_chat_emits_status_event_on_tool_call(client: TestClient, monkeypatch):
    """A FunctionToolCallEvent yields a `status` SSE event with state=tool_call
    and the raw tool name (no Chinese mapping)."""
    events_seq = [
        FunctionToolCallEvent(
            part=ToolCallPart(tool_name="search_knowledge", args={"query": "x"})
        ),
        PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="答案")),
    ]
    monkeypatch.setattr(
        chat_api,
        "build_agent",
        lambda model, system_prompt=None: _FakeEventsAgent(
            events=events_seq, final_output="答案",
        ),
    )
    events = _parse_sse(client.post("/api/chat", json={"message": "找一下"}).text)
    status_events = [e for e in events if e["type"] == "status"]
    assert status_events, "expected a status event when a tool is called"
    assert all(s["state"] == "tool_call" for s in status_events)
    assert status_events[0]["tool"] == "search_knowledge"  # raw name, no mapping


def test_chat_emits_text_replace_when_streamed_text_incomplete(
    client: TestClient, monkeypatch
):
    """If accumulated deltas differ from final_result.output, a `text_replace`
    event carries the authoritative full text."""
    # Deltas sum to "部分" but final_output is the fuller text.
    events_seq = [PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="部分"))]
    monkeypatch.setattr(
        chat_api,
        "build_agent",
        lambda model, system_prompt=None: _FakeEventsAgent(
            events=events_seq, final_output="部分回答完整版",
        ),
    )
    events = _parse_sse(client.post("/api/chat", json={"message": "hi"}).text)
    replace = [e for e in events if e["type"] == "text_replace"]
    assert replace, "expected text_replace when deltas != final output"
    assert replace[-1]["content"] == "部分回答完整版"
