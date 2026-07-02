"""Tests for memories CRUD on SQLiteClient."""

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
async def test_add_and_list_memory(sqlite: SQLiteClient):
    m = await sqlite.add_memory(content="在学 React", category="study")
    assert m["content"] == "在学 React"
    listed = await sqlite.list_memories()
    assert len(listed) == 1
    assert listed[0]["id"] == m["id"]


@pytest.mark.asyncio
async def test_add_memory_no_category(sqlite: SQLiteClient):
    m = await sqlite.add_memory(content="偏好简洁")
    assert m["category"] is None


@pytest.mark.asyncio
async def test_delete_memory(sqlite: SQLiteClient):
    m = await sqlite.add_memory(content="x")
    assert await sqlite.delete_memory(m["id"]) is True
    assert await sqlite.delete_memory(m["id"]) is False  # already gone
    assert await sqlite.list_memories() == []