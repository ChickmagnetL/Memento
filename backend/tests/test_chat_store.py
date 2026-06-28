"""Tests for chat session/message CRUD on SQLiteClient."""

from pathlib import Path

import pytest

from storage.sqlite_client import SQLiteClient


@pytest.fixture
async def sqlite(tmp_path: Path):
    client = SQLiteClient(tmp_path / "test.db")
    await client.connect()
    try:
        yield client
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_create_and_get_session(sqlite: SQLiteClient):
    session = await sqlite.create_chat_session(title="hello")
    assert session["title"] == "hello"
    fetched = await sqlite.get_chat_session(session["id"])
    assert fetched is not None
    assert fetched["title"] == "hello"


@pytest.mark.asyncio
async def test_create_session_default_title(sqlite: SQLiteClient):
    session = await sqlite.create_chat_session()
    assert session["title"] == "New Chat"


@pytest.mark.asyncio
async def test_add_messages_and_list(sqlite: SQLiteClient):
    session = await sqlite.create_chat_session()
    await sqlite.add_chat_message(
        session_id=session["id"], role="user", content="hi"
    )
    await sqlite.add_chat_message(
        session_id=session["id"], role="assistant", content="hello"
    )
    msgs = await sqlite.list_chat_messages(session["id"])
    assert len(msgs) == 2
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert [m["content"] for m in msgs] == ["hi", "hello"]


@pytest.mark.asyncio
async def test_list_sessions_newest_first_and_updated_at(sqlite: SQLiteClient):
    s1 = await sqlite.create_chat_session(title="first")
    s2 = await sqlite.create_chat_session(title="second")
    # touch s1 after s2 created -> s1 should sort first by updated_at
    await sqlite.add_chat_message(session_id=s1["id"], role="user", content="bump")
    sessions = await sqlite.list_chat_sessions()
    assert sessions[0]["id"] == s1["id"]
    assert sessions[1]["id"] == s2["id"]


@pytest.mark.asyncio
async def test_rename_session(sqlite: SQLiteClient):
    session = await sqlite.create_chat_session()
    updated = await sqlite.rename_chat_session(session["id"], "new title")
    assert updated is not None
    assert updated["title"] == "new title"


@pytest.mark.asyncio
async def test_delete_session_cascades_messages(sqlite: SQLiteClient):
    session = await sqlite.create_chat_session()
    await sqlite.add_chat_message(session_id=session["id"], role="user", content="x")
    deleted = await sqlite.delete_chat_session(session["id"])
    assert deleted is True
    assert await sqlite.get_chat_session(session["id"]) is None
    assert await sqlite.list_chat_messages(session["id"]) == []


@pytest.mark.asyncio
async def test_history_for_agent(sqlite: SQLiteClient):
    """get_chat_history returns messages in agent-usable order."""
    session = await sqlite.create_chat_session()
    await sqlite.add_chat_message(session_id=session["id"], role="user", content="q")
    await sqlite.add_chat_message(
        session_id=session["id"], role="assistant", content="a"
    )
    history = await sqlite.get_chat_history(session["id"])
    assert history == [("user", "q"), ("assistant", "a")]


@pytest.mark.asyncio
async def test_get_session_missing_returns_none(sqlite: SQLiteClient):
    assert await sqlite.get_chat_session("does-not-exist") is None
