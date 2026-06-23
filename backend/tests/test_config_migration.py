"""Tests for model preset and app config CRUD operations and migration."""

import json
from pathlib import Path

import pytest
import yaml

from storage.sqlite_client import SQLiteClient
from core.config_migration import migrate_config_to_db


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


# ===== Migration Tests =====


@pytest.fixture
def mock_project_root(tmp_path: Path, monkeypatch):
    """Mock project root to a temp directory."""
    monkeypatch.setenv("MEMENTO_PROJECT_ROOT", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_migration_skipped_when_presets_exist(sqlite: SQLiteClient, mock_project_root: Path):
    """Migration should skip if model_presets table already has records."""
    # Create a preset to make table non-empty
    await sqlite.create_preset(name="已有预设", model_name="asr", config={})

    # Create a config.local.yaml file
    config_file = mock_project_root / "config.local.yaml"
    config_file.write_text("models:\n  asr:\n    provider: local\n")

    # Run migration
    await migrate_config_to_db(sqlite)

    # Verify: only 1 preset (the one we created), file not renamed
    presets = await sqlite.list_presets()
    assert len(presets) == 1
    assert presets[0]["name"] == "已有预设"
    assert config_file.exists()  # Not renamed


@pytest.mark.asyncio
async def test_migration_skipped_when_no_config_file(sqlite: SQLiteClient, mock_project_root: Path):
    """Migration should skip if config.local.yaml doesn't exist."""
    await migrate_config_to_db(sqlite)

    # Verify: no presets, no app_config
    presets = await sqlite.list_presets()
    assert len(presets) == 0


@pytest.mark.asyncio
async def test_migration_skipped_when_config_empty(sqlite: SQLiteClient, mock_project_root: Path):
    """Migration should skip if config.local.yaml is empty."""
    config_file = mock_project_root / "config.local.yaml"
    config_file.write_text("")

    await migrate_config_to_db(sqlite)

    # Verify: no presets, file not renamed
    presets = await sqlite.list_presets()
    assert len(presets) == 0
    assert config_file.exists()


@pytest.mark.asyncio
async def test_migration_creates_presets_and_sets_active(sqlite: SQLiteClient, mock_project_root: Path):
    """Migration should create presets and set them as active."""
    # Create config.local.yaml with 3 model configs
    config_data = {
        "models": {
            "asr": {
                "provider": "local",
                "endpoint": "http://localhost:8001",
                "model": "whisper-large-v3",
                "protocol": "transcriptions",
            },
            "chat": {
                "provider": "cloud",
                "api_key": "sk-test123",
                "model": "gpt-4",
            },
            "embedding": {
                "provider": "ollama",
                "endpoint": "http://localhost:11434",
                "model": "qwen3-embedding:0.6b",
            },
        }
    }

    config_file = mock_project_root / "config.local.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    # Run migration
    await migrate_config_to_db(sqlite)

    # Verify: 3 presets created, all named "默认配置"
    presets = await sqlite.list_presets()
    assert len(presets) == 3

    asr_presets = await sqlite.list_presets(model_name="asr")
    assert len(asr_presets) == 1
    assert asr_presets[0]["name"] == "默认配置"
    asr_config = json.loads(asr_presets[0]["config"])
    assert asr_config["provider"] == "local"
    assert asr_config["model"] == "whisper-large-v3"

    # Verify: active presets set for all 3 models
    asr_active = await sqlite.get_active_preset("asr")
    assert asr_active is not None
    assert asr_active["preset_id"] == asr_presets[0]["id"]

    chat_active = await sqlite.get_active_preset("chat")
    assert chat_active is not None

    embedding_active = await sqlite.get_active_preset("embedding")
    assert embedding_active is not None


@pytest.mark.asyncio
async def test_migration_stores_app_config(sqlite: SQLiteClient, mock_project_root: Path):
    """Migration should store non-model sections in app_config."""
    config_data = {
        "storage": {
            "data_dir": "/custom/path",
            "keep_videos": True,
        },
        "video_processing": {
            "auto_clean": False,
            "preserve_timestamp": True,
            "bilibili_cookie": "cookie_value",
        },
        "rag": {
            "chunk_size": 1000,
            "overlap": 100,
            "top_k": 10,
        },
    }

    config_file = mock_project_root / "config.local.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    # Run migration
    await migrate_config_to_db(sqlite)

    # Verify: app_config entries created
    storage_value = await sqlite.get_app_config("storage")
    assert storage_value is not None
    storage_data = json.loads(storage_value)
    assert storage_data["data_dir"] == "/custom/path"
    assert storage_data["keep_videos"] is True

    video_value = await sqlite.get_app_config("video_processing")
    assert video_value is not None
    video_data = json.loads(video_value)
    assert video_data["auto_clean"] is False
    assert video_data["bilibili_cookie"] == "cookie_value"

    rag_value = await sqlite.get_app_config("rag")
    assert rag_value is not None
    rag_data = json.loads(rag_value)
    assert rag_data["chunk_size"] == 1000
    assert rag_data["top_k"] == 10


@pytest.mark.asyncio
async def test_migration_renames_config_file(sqlite: SQLiteClient, mock_project_root: Path):
    """Migration should rename config.local.yaml to .bak after success."""
    config_data = {
        "models": {
            "asr": {"provider": "local", "model": "whisper-base"},
        }
    }

    config_file = mock_project_root / "config.local.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    # Run migration
    await migrate_config_to_db(sqlite)

    # Verify: original file renamed
    assert not config_file.exists()
    backup_file = mock_project_root / "config.local.yaml.bak"
    assert backup_file.exists()

    # Verify: backup has original content
    with open(backup_file) as f:
        backup_data = yaml.safe_load(f)
    assert backup_data["models"]["asr"]["model"] == "whisper-base"


@pytest.mark.asyncio
async def test_migration_handles_partial_config(sqlite: SQLiteClient, mock_project_root: Path):
    """Migration should handle config with only some sections."""
    # Config with only 1 model and 1 app section
    config_data = {
        "models": {
            "chat": {"provider": "cloud", "model": "gpt-4"},
        },
        "storage": {"data_dir": "/data"},
    }

    config_file = mock_project_root / "config.local.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    # Run migration
    await migrate_config_to_db(sqlite)

    # Verify: only 1 preset created
    presets = await sqlite.list_presets()
    assert len(presets) == 1
    assert presets[0]["model_name"] == "chat"

    # Verify: only storage in app_config
    storage_value = await sqlite.get_app_config("storage")
    assert storage_value is not None

    video_value = await sqlite.get_app_config("video_processing")
    assert video_value is None

    rag_value = await sqlite.get_app_config("rag")
    assert rag_value is None


@pytest.mark.asyncio
async def test_migration_full_workflow(sqlite: SQLiteClient, mock_project_root: Path):
    """Test complete migration workflow from config file to DB."""
    # Create a config.local.yaml with test data
    config_data = {
        "models": {
            "asr": {
                "provider": "local",
                "endpoint": "http://localhost:8001",
                "model": "whisper-large-v3",
                "protocol": "transcriptions",
            },
            "chat": {
                "provider": "cloud",
                "api_key": "sk-test123",
                "model": "gpt-4",
            },
        },
        "storage": {
            "data_dir": "/test/path",
            "keep_videos": True,
        },
        "rag": {
            "chunk_size": 1000,
            "top_k": 10,
        },
    }

    config_file = mock_project_root / "config.local.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    # Run migration
    await migrate_config_to_db(sqlite)

    # Verify migration ran: presets created
    presets = await sqlite.list_presets()
    assert len(presets) == 2  # asr + chat

    asr_presets = await sqlite.list_presets(model_name="asr")
    assert len(asr_presets) == 1
    assert asr_presets[0]["name"] == "默认配置"
    asr_config = json.loads(asr_presets[0]["config"])
    assert asr_config["model"] == "whisper-large-v3"

    # Verify active presets set
    asr_active = await sqlite.get_active_preset("asr")
    assert asr_active is not None

    chat_active = await sqlite.get_active_preset("chat")
    assert chat_active is not None

    # Verify app_config stored
    storage_value = await sqlite.get_app_config("storage")
    assert storage_value is not None
    storage_data = json.loads(storage_value)
    assert storage_data["keep_videos"] is True

    rag_value = await sqlite.get_app_config("rag")
    assert rag_value is not None
    rag_data = json.loads(rag_value)
    assert rag_data["chunk_size"] == 1000

    # Verify config file was renamed
    assert not config_file.exists()
    backup_file = mock_project_root / "config.local.yaml.bak"
    assert backup_file.exists()


@pytest.mark.asyncio
async def test_migration_idempotent_on_repeated_runs(sqlite: SQLiteClient, mock_project_root: Path):
    """Test that migration is idempotent on repeated runs."""
    # Create initial preset directly in DB
    await sqlite.create_preset(
        name="手动预设", model_name="asr", config={"provider": "local"}
    )

    # Now create a config.local.yaml (should be ignored)
    config_data = {
        "models": {
            "chat": {"provider": "cloud", "model": "gpt-4"},
        }
    }

    config_file = mock_project_root / "config.local.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    # Run migration (should skip because presets exist)
    await migrate_config_to_db(sqlite)

    # Verify: still only 1 preset (migration skipped)
    presets = await sqlite.list_presets()
    assert len(presets) == 1
    assert presets[0]["name"] == "手动预设"

    # Verify: config file NOT renamed (migration was skipped)
    assert config_file.exists()
