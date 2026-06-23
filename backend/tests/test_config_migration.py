"""Tests for model preset and app config CRUD operations."""

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
        model_name="openai_compatible",
        config={"base_url": "http://localhost:8000", "model": "whisper-large-v3"},
    )

    assert preset["id"] is not None
    assert len(preset["id"]) == 36  # UUID4 format
    assert preset["name"] == "测试预设"
    assert preset["model_name"] == "openai_compatible"
    config = json.loads(preset["config"])
    assert config["base_url"] == "http://localhost:8000"
    assert config["model"] == "whisper-large-v3"
    assert preset["created_at"] is not None


@pytest.mark.asyncio
async def test_get_preset_returns_record(sqlite: SQLiteClient):
    created = await sqlite.create_preset(
        name="预设1", model_name="local_asr", config={"model": "moonshine-tiny"}
    )
    preset_id = created["id"]

    fetched = await sqlite.get_preset(preset_id)

    assert fetched is not None
    assert fetched["id"] == preset_id
    assert fetched["name"] == "预设1"


@pytest.mark.asyncio
async def test_get_preset_returns_none_for_missing(sqlite: SQLiteClient):
    assert await sqlite.get_preset("00000000-0000-0000-0000-000000000000") is None


@pytest.mark.asyncio
async def test_list_presets_returns_all_ordered_by_creation(sqlite: SQLiteClient):
    await sqlite.create_preset(name="A", model_name="openai", config={})
    await sqlite.create_preset(name="B", model_name="local_asr", config={})
    await sqlite.create_preset(name="C", model_name="openai_compatible", config={})

    presets = await sqlite.list_presets()

    assert len(presets) == 3
    # Newest first
    assert presets[0]["name"] == "C"
    assert presets[1]["name"] == "B"
    assert presets[2]["name"] == "A"


@pytest.mark.asyncio
async def test_list_presets_filters_by_model_name(sqlite: SQLiteClient):
    await sqlite.create_preset(name="A", model_name="openai", config={})
    await sqlite.create_preset(name="B", model_name="local_asr", config={})
    await sqlite.create_preset(name="C", model_name="openai", config={})

    openai_presets = await sqlite.list_presets(model_name="openai")

    assert len(openai_presets) == 2
    assert openai_presets[0]["name"] == "C"
    assert openai_presets[1]["name"] == "A"


@pytest.mark.asyncio
async def test_update_preset_modifies_fields(sqlite: SQLiteClient):
    created = await sqlite.create_preset(
        name="旧名称", model_name="openai", config={"key": "old"}
    )
    preset_id = created["id"]

    updated = await sqlite.update_preset(
        preset_id=preset_id,
        name="新名称",
        model_name="local_asr",
        config={"key": "new"},
    )

    assert updated is not None
    assert updated["name"] == "新名称"
    assert updated["model_name"] == "local_asr"
    config = json.loads(updated["config"])
    assert config["key"] == "new"


@pytest.mark.asyncio
async def test_update_preset_returns_none_for_missing(sqlite: SQLiteClient):
    result = await sqlite.update_preset(
        preset_id="00000000-0000-0000-0000-000000000000",
        name="不存在",
        model_name="openai",
        config={},
    )
    assert result is None


@pytest.mark.asyncio
async def test_delete_preset_removes_record(sqlite: SQLiteClient):
    created = await sqlite.create_preset(
        name="待删除", model_name="openai", config={}
    )
    preset_id = created["id"]

    deleted = await sqlite.delete_preset(preset_id)

    assert deleted is True
    assert await sqlite.get_preset(preset_id) is None


@pytest.mark.asyncio
async def test_delete_preset_returns_false_for_missing(sqlite: SQLiteClient):
    assert await sqlite.delete_preset("00000000-0000-0000-0000-000000000000") is False


@pytest.mark.asyncio
async def test_delete_preset_sets_active_to_null(sqlite: SQLiteClient):
    """When preset is deleted, active_preset.preset_id should be set to NULL."""
    created = await sqlite.create_preset(
        name="活跃预设", model_name="openai", config={}
    )
    preset_id = created["id"]
    await sqlite.set_active_preset("openai", preset_id)

    await sqlite.delete_preset(preset_id)

    active = await sqlite.get_active_preset("openai")
    assert active is not None  # 记录仍存在
    assert active["preset_id"] is None  # 但 preset_id 被设为 NULL


@pytest.mark.asyncio
async def test_unique_constraint_model_name_and_name(sqlite: SQLiteClient):
    """UNIQUE(model_name, name) constraint should prevent duplicate names per model."""
    await sqlite.create_preset(
        name="重复预设", model_name="openai", config={"key": "value1"}
    )

    # Same model_name and name should fail
    with pytest.raises(Exception):  # aiosqlite.IntegrityError
        await sqlite.create_preset(
            name="重复预设", model_name="openai", config={"key": "value2"}
        )

    # Different model_name should succeed
    preset = await sqlite.create_preset(
        name="重复预设", model_name="local_asr", config={"key": "value3"}
    )
    assert preset["name"] == "重复预设"
    assert preset["model_name"] == "local_asr"


# ===== Active Preset Tests =====


@pytest.mark.asyncio
async def test_set_active_preset_creates_record(sqlite: SQLiteClient):
    preset = await sqlite.create_preset(
        name="活跃预设", model_name="openai", config={}
    )
    preset_id = preset["id"]

    await sqlite.set_active_preset("openai", preset_id)

    active = await sqlite.get_active_preset("openai")
    assert active is not None
    assert active["model_name"] == "openai"
    assert active["preset_id"] == preset_id
    assert active["updated_at"] is not None


@pytest.mark.asyncio
async def test_set_active_preset_updates_existing_record(sqlite: SQLiteClient):
    preset1 = await sqlite.create_preset(name="预设1", model_name="openai", config={})
    preset2 = await sqlite.create_preset(name="预设2", model_name="openai", config={})

    await sqlite.set_active_preset("openai", preset1["id"])
    await sqlite.set_active_preset("openai", preset2["id"])

    active = await sqlite.get_active_preset("openai")
    assert active["preset_id"] == preset2["id"]


@pytest.mark.asyncio
async def test_set_active_preset_per_model(sqlite: SQLiteClient):
    """Each model can have its own active preset."""
    openai_preset = await sqlite.create_preset(
        name="OpenAI预设", model_name="openai", config={}
    )
    local_preset = await sqlite.create_preset(
        name="本地预设", model_name="local_asr", config={}
    )

    await sqlite.set_active_preset("openai", openai_preset["id"])
    await sqlite.set_active_preset("local_asr", local_preset["id"])

    openai_active = await sqlite.get_active_preset("openai")
    local_active = await sqlite.get_active_preset("local_asr")

    assert openai_active["preset_id"] == openai_preset["id"]
    assert local_active["preset_id"] == local_preset["id"]


@pytest.mark.asyncio
async def test_get_active_preset_returns_none_when_empty(sqlite: SQLiteClient):
    assert await sqlite.get_active_preset("nonexistent_model") is None


@pytest.mark.asyncio
async def test_clear_active_preset_removes_entry(sqlite: SQLiteClient):
    preset = await sqlite.create_preset(name="预设", model_name="openai", config={})
    await sqlite.set_active_preset("openai", preset["id"])

    await sqlite.clear_active_preset("openai")

    active = await sqlite.get_active_preset("openai")
    assert active is None


# ===== App Config Tests =====


@pytest.mark.asyncio
async def test_set_app_config_stores_text_value(sqlite: SQLiteClient):
    await sqlite.set_app_config("embedding", '{"provider": "openai", "model": "text-embedding-3-small"}')

    value = await sqlite.get_app_config("embedding")
    assert value == '{"provider": "openai", "model": "text-embedding-3-small"}'


@pytest.mark.asyncio
async def test_set_app_config_allows_null_value(sqlite: SQLiteClient):
    await sqlite.set_app_config("nullable_key", None)

    value = await sqlite.get_app_config("nullable_key")
    assert value is None


@pytest.mark.asyncio
async def test_set_app_config_updates_existing_key(sqlite: SQLiteClient):
    await sqlite.set_app_config("rerank", '{"enabled": false}')
    await sqlite.set_app_config("rerank", '{"enabled": true, "model": "bge-reranker"}')

    value = await sqlite.get_app_config("rerank")
    assert value == '{"enabled": true, "model": "bge-reranker"}'


@pytest.mark.asyncio
async def test_get_app_config_returns_none_for_missing(sqlite: SQLiteClient):
    assert await sqlite.get_app_config("nonexistent") is None


@pytest.mark.asyncio
async def test_delete_app_config_removes_key(sqlite: SQLiteClient):
    await sqlite.set_app_config("temp_key", '{"data": "value"}')

    deleted = await sqlite.delete_app_config("temp_key")

    assert deleted is True
    assert await sqlite.get_app_config("temp_key") is None


@pytest.mark.asyncio
async def test_delete_app_config_returns_false_for_missing(sqlite: SQLiteClient):
    assert await sqlite.delete_app_config("nonexistent") is False
