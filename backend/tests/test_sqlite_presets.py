"""Tests for transcription preset and app config CRUD operations."""

import json
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


# ===== Preset CRUD Tests =====


@pytest.mark.asyncio
async def test_create_preset_generates_uuid(sqlite: SQLiteClient):
    preset = await sqlite.create_preset(
        name="测试预设",
        provider="openai_compatible",
        config={"base_url": "http://localhost:8000", "model": "whisper-large-v3"},
    )

    assert preset["preset_id"] is not None
    assert len(preset["preset_id"]) == 36  # UUID4 format
    assert preset["name"] == "测试预设"
    assert preset["provider"] == "openai_compatible"
    config = json.loads(preset["config"])
    assert config["base_url"] == "http://localhost:8000"
    assert config["model"] == "whisper-large-v3"
    assert preset["created_at"] is not None


@pytest.mark.asyncio
async def test_get_preset_returns_record(sqlite: SQLiteClient):
    created = await sqlite.create_preset(
        name="预设1", provider="local_asr", config={"model": "moonshine-tiny"}
    )
    preset_id = created["preset_id"]

    fetched = await sqlite.get_preset(preset_id)

    assert fetched is not None
    assert fetched["preset_id"] == preset_id
    assert fetched["name"] == "预设1"


@pytest.mark.asyncio
async def test_get_preset_returns_none_for_missing(sqlite: SQLiteClient):
    assert await sqlite.get_preset("00000000-0000-0000-0000-000000000000") is None


@pytest.mark.asyncio
async def test_list_presets_returns_all_ordered_by_creation(sqlite: SQLiteClient):
    await sqlite.create_preset(name="A", provider="openai", config={})
    await sqlite.create_preset(name="B", provider="local_asr", config={})
    await sqlite.create_preset(name="C", provider="openai_compatible", config={})

    presets = await sqlite.list_presets()

    assert len(presets) == 3
    # Newest first
    assert presets[0]["name"] == "C"
    assert presets[1]["name"] == "B"
    assert presets[2]["name"] == "A"


@pytest.mark.asyncio
async def test_update_preset_modifies_fields(sqlite: SQLiteClient):
    created = await sqlite.create_preset(
        name="旧名称", provider="openai", config={"key": "old"}
    )
    preset_id = created["preset_id"]

    updated = await sqlite.update_preset(
        preset_id=preset_id,
        name="新名称",
        provider="local_asr",
        config={"key": "new"},
    )

    assert updated is not None
    assert updated["name"] == "新名称"
    assert updated["provider"] == "local_asr"
    config = json.loads(updated["config"])
    assert config["key"] == "new"


@pytest.mark.asyncio
async def test_update_preset_returns_none_for_missing(sqlite: SQLiteClient):
    result = await sqlite.update_preset(
        preset_id="00000000-0000-0000-0000-000000000000",
        name="不存在",
        provider="openai",
        config={},
    )
    assert result is None


@pytest.mark.asyncio
async def test_delete_preset_removes_record(sqlite: SQLiteClient):
    created = await sqlite.create_preset(
        name="待删除", provider="openai", config={}
    )
    preset_id = created["preset_id"]

    deleted = await sqlite.delete_preset(preset_id)

    assert deleted is True
    assert await sqlite.get_preset(preset_id) is None


@pytest.mark.asyncio
async def test_delete_preset_returns_false_for_missing(sqlite: SQLiteClient):
    assert await sqlite.delete_preset("00000000-0000-0000-0000-000000000000") is False


@pytest.mark.asyncio
async def test_delete_preset_clears_active_preset_reference(sqlite: SQLiteClient):
    """When preset is deleted, active_preset.preset_id should be set to NULL."""
    created = await sqlite.create_preset(
        name="活跃预设", provider="openai", config={}
    )
    preset_id = created["preset_id"]
    await sqlite.set_active_preset(preset_id)

    await sqlite.delete_preset(preset_id)

    active = await sqlite.get_active_preset()
    assert active is None


# ===== Active Preset Tests =====


@pytest.mark.asyncio
async def test_set_active_preset_creates_record(sqlite: SQLiteClient):
    preset = await sqlite.create_preset(
        name="活跃预设", provider="openai", config={}
    )
    preset_id = preset["preset_id"]

    await sqlite.set_active_preset(preset_id)

    active = await sqlite.get_active_preset()
    assert active is not None
    assert active["preset_id"] == preset_id
    assert active["updated_at"] is not None


@pytest.mark.asyncio
async def test_set_active_preset_updates_existing_record(sqlite: SQLiteClient):
    preset1 = await sqlite.create_preset(name="预设1", provider="openai", config={})
    preset2 = await sqlite.create_preset(name="预设2", provider="local_asr", config={})

    await sqlite.set_active_preset(preset1["preset_id"])
    await sqlite.set_active_preset(preset2["preset_id"])

    active = await sqlite.get_active_preset()
    assert active["preset_id"] == preset2["preset_id"]


@pytest.mark.asyncio
async def test_get_active_preset_returns_none_when_empty(sqlite: SQLiteClient):
    assert await sqlite.get_active_preset() is None


@pytest.mark.asyncio
async def test_clear_active_preset_sets_null(sqlite: SQLiteClient):
    preset = await sqlite.create_preset(name="预设", provider="openai", config={})
    await sqlite.set_active_preset(preset["preset_id"])

    await sqlite.clear_active_preset()

    active = await sqlite.get_active_preset()
    assert active is None


# ===== App Config Tests =====


@pytest.mark.asyncio
async def test_set_app_config_stores_json_value(sqlite: SQLiteClient):
    await sqlite.set_app_config(
        "embedding", {"provider": "openai", "model": "text-embedding-3-small"}
    )

    value = await sqlite.get_app_config("embedding")
    assert value == {"provider": "openai", "model": "text-embedding-3-small"}


@pytest.mark.asyncio
async def test_set_app_config_updates_existing_key(sqlite: SQLiteClient):
    await sqlite.set_app_config("rerank", {"enabled": False})
    await sqlite.set_app_config("rerank", {"enabled": True, "model": "bge-reranker"})

    value = await sqlite.get_app_config("rerank")
    assert value == {"enabled": True, "model": "bge-reranker"}


@pytest.mark.asyncio
async def test_get_app_config_returns_none_for_missing(sqlite: SQLiteClient):
    assert await sqlite.get_app_config("nonexistent") is None


@pytest.mark.asyncio
async def test_delete_app_config_removes_key(sqlite: SQLiteClient):
    await sqlite.set_app_config("temp_key", {"data": "value"})

    deleted = await sqlite.delete_app_config("temp_key")

    assert deleted is True
    assert await sqlite.get_app_config("temp_key") is None


@pytest.mark.asyncio
async def test_delete_app_config_returns_false_for_missing(sqlite: SQLiteClient):
    assert await sqlite.delete_app_config("nonexistent") is False
