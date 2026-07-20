"""Tests for the chat sessions REST API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from main import app
from schemas.sessions import (
    MessageEditRequest,
    MessageResponse,
    SessionUpdateRequest,
)
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


def test_message_edit_request_strips_and_rejects_blank():
    msg = MessageEditRequest(content="  hi  ")
    assert msg.content == "  hi  "
    with pytest.raises(ValidationError):
        MessageEditRequest(content="   ")


def test_message_edit_request_rejects_missing_field():
    with pytest.raises(ValidationError):
        MessageEditRequest()


def test_session_update_request_allows_empty_body():
    payload = SessionUpdateRequest()
    assert payload.title is None


def test_session_update_request_accepts_title():
    payload = SessionUpdateRequest(title="new title")
    assert payload.title == "new title"


def test_patch_session_rename(client: TestClient):
    created = client.post("/api/sessions", json={"title": "old"}).json()
    resp = client.patch(
        f"/api/sessions/{created['id']}", json={"title": "new title"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    assert body["title"] == "new title"
    sessions = client.get("/api/sessions").json()
    assert next(s for s in sessions if s["id"] == created["id"])["title"] == "new title"


def test_patch_session_returns_404_for_missing(client: TestClient):
    resp = client.patch(
        f"/api/sessions/does-not-exist", json={"title": "x"}
    )
    assert resp.status_code == 404


def test_patch_session_no_op_when_body_empty(client: TestClient):
    created = client.post("/api/sessions", json={"title": "keep"}).json()
    resp = client.patch(f"/api/sessions/{created['id']}", json={})
    assert resp.status_code == 200
    assert resp.json()["title"] == "keep"


def test_patch_message_edits_content_and_truncates_after(client: TestClient):
    created = client.post("/api/sessions", json={"title": "t"}).json()
    sid = created["id"]
    sqlite = client.app.state.sqlite
    import asyncio
    async def seed():
        u = await sqlite.add_chat_message(session_id=sid, role="user", content="old q")
        a = await sqlite.add_chat_message(session_id=sid, role="assistant", content="old a")
        u2 = await sqlite.add_chat_message(session_id=sid, role="user", content="second q")
        a2 = await sqlite.add_chat_message(session_id=sid, role="assistant", content="second a")
        return u, a, u2, a2
    u1, a1, u2, a2 = asyncio.run(seed())

    resp = client.patch(
        f"/api/sessions/{sid}/messages/{u1['id']}",
        json={"content": "edited question"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == u1["id"]
    assert body["content"] == "edited question"
    assert body["role"] == "user"

    msgs = client.get(f"/api/sessions/{sid}/messages").json()
    assert [m["id"] for m in msgs] == [u1["id"]]
    assert msgs[0]["content"] == "edited question"


def test_patch_message_first_user_also_renames_session(client: TestClient):
    created = client.post("/api/sessions", json={"title": "first q"}).json()
    sid = created["id"]
    sqlite = client.app.state.sqlite
    import asyncio
    async def seed():
        return await sqlite.add_chat_message(session_id=sid, role="user", content="first q")
    u1 = asyncio.run(seed())
    async def seed_more():
        await sqlite.add_chat_message(session_id=sid, role="assistant", content="a")
        return await sqlite.add_chat_message(session_id=sid, role="user", content="second")
    asyncio.run(seed_more())

    resp = client.patch(
        f"/api/sessions/{sid}/messages/{u1['id']}",
        json={"content": "completely different question"},
    )
    assert resp.status_code == 200
    sessions = client.get("/api/sessions").json()
    target = next(s for s in sessions if s["id"] == sid)
    assert target["title"] == "completely different question"


def test_patch_message_rejects_assistant_role(client: TestClient):
    created = client.post("/api/sessions", json={"title": "t"}).json()
    sid = created["id"]
    sqlite = client.app.state.sqlite
    import asyncio
    async def seed():
        await sqlite.add_chat_message(session_id=sid, role="user", content="q")
        return await sqlite.add_chat_message(session_id=sid, role="assistant", content="a")
    a1 = asyncio.run(seed())

    resp = client.patch(
        f"/api/sessions/{sid}/messages/{a1['id']}",
        json={"content": "try edit assistant"},
    )
    assert resp.status_code == 400


def test_patch_message_404_when_session_missing(client: TestClient):
    resp = client.patch(
        "/api/sessions/does-not-exist/messages/whatever",
        json={"content": "x"},
    )
    assert resp.status_code == 404


def test_patch_message_404_when_message_missing(client: TestClient):
    created = client.post("/api/sessions", json={"title": "t"}).json()
    resp = client.patch(
        f"/api/sessions/{created['id']}/messages/does-not-exist",
        json={"content": "x"},
    )
    assert resp.status_code == 404


def test_patch_message_404_when_message_belongs_to_other_session(client: TestClient):
    s1 = client.post("/api/sessions", json={"title": "t1"}).json()
    s2 = client.post("/api/sessions", json={"title": "t2"}).json()
    sqlite = client.app.state.sqlite
    import asyncio
    async def seed():
        return await sqlite.add_chat_message(session_id=s2["id"], role="user", content="x")
    u = asyncio.run(seed())

    resp = client.patch(
        f"/api/sessions/{s1['id']}/messages/{u['id']}",
        json={"content": "edited"},
    )
    assert resp.status_code == 404


def test_patch_message_rejects_blank_content(client: TestClient):
    created = client.post("/api/sessions", json={"title": "t"}).json()
    sid = created["id"]
    sqlite = client.app.state.sqlite
    import asyncio
    async def seed():
        return await sqlite.add_chat_message(session_id=sid, role="user", content="x")
    u = asyncio.run(seed())

    resp = client.patch(
        f"/api/sessions/{sid}/messages/{u['id']}",
        json={"content": "   "},
    )
    assert resp.status_code == 422


def test_delete_message_pair_removes_user_and_assistant(client: TestClient):
    created = client.post("/api/sessions", json={"title": "t"}).json()
    sid = created["id"]
    sqlite = client.app.state.sqlite
    import asyncio
    async def seed():
        u = await sqlite.add_chat_message(session_id=sid, role="user", content="q")
        a = await sqlite.add_chat_message(session_id=sid, role="assistant", content="a")
        return u, a
    u, a = asyncio.run(seed())

    resp = client.delete(f"/api/sessions/{sid}/messages/{u['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert sorted(body["deleted"]) == sorted([u["id"], a["id"]])

    msgs = client.get(f"/api/sessions/{sid}/messages").json()
    assert msgs == []


def test_delete_message_only_user_when_no_assistant_follows(client: TestClient):
    created = client.post("/api/sessions", json={"title": "t"}).json()
    sid = created["id"]
    sqlite = client.app.state.sqlite
    import asyncio
    async def seed():
        u1 = await sqlite.add_chat_message(session_id=sid, role="user", content="q1")
        u2 = await sqlite.add_chat_message(session_id=sid, role="user", content="q2")
        return u1, u2
    u1, u2 = asyncio.run(seed())

    resp = client.delete(f"/api/sessions/{sid}/messages/{u1['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] == [u1["id"]]

    msgs = client.get(f"/api/sessions/{sid}/messages").json()
    assert [m["id"] for m in msgs] == [u2["id"]]


def test_delete_message_rejects_assistant_role(client: TestClient):
    created = client.post("/api/sessions", json={"title": "t"}).json()
    sid = created["id"]
    sqlite = client.app.state.sqlite
    import asyncio
    async def seed():
        await sqlite.add_chat_message(session_id=sid, role="user", content="q")
        return await sqlite.add_chat_message(session_id=sid, role="assistant", content="a")
    a = asyncio.run(seed())

    resp = client.delete(f"/api/sessions/{sid}/messages/{a['id']}")
    assert resp.status_code == 400


def test_delete_message_404_when_session_missing(client: TestClient):
    resp = client.delete("/api/sessions/does-not-exist/messages/whatever")
    assert resp.status_code == 404


def test_delete_message_404_when_message_missing(client: TestClient):
    created = client.post("/api/sessions", json={"title": "t"}).json()
    resp = client.delete(
        f"/api/sessions/{created['id']}/messages/does-not-exist"
    )
    assert resp.status_code == 404


def test_delete_message_404_when_message_in_other_session(client: TestClient):
    s1 = client.post("/api/sessions", json={"title": "t1"}).json()
    s2 = client.post("/api/sessions", json={"title": "t2"}).json()
    sqlite = client.app.state.sqlite
    import asyncio
    async def seed():
        return await sqlite.add_chat_message(session_id=s2["id"], role="user", content="x")
    u = asyncio.run(seed())

    resp = client.delete(f"/api/sessions/{s1['id']}/messages/{u['id']}")
    assert resp.status_code == 404
