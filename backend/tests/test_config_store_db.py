"""Tests for DB-based config persistence."""

import json
import sqlite3
from pathlib import Path

import pytest

from core.config_store import ConfigStore


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Create a test database with schema."""
    db = tmp_path / "memento.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE model_presets (
            id TEXT PRIMARY KEY,
            model_name TEXT NOT NULL,
            name TEXT NOT NULL,
            config TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(model_name, name)
        );
        CREATE TABLE active_preset (
            model_name TEXT PRIMARY KEY,
            preset_id TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (preset_id) REFERENCES model_presets(id) ON DELETE SET NULL
        );
        CREATE TABLE app_config (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    # Create initial presets for all models
    for model_name in ["chat", "embedding", "asr"]:
        preset_id = f"{model_name}_default"
        config = {
            "provider": "cloud",
            "model": f"{model_name}-model-v1",
            "api_key": "test_key",
        }
        conn.execute(
            "INSERT INTO model_presets (id, model_name, name, config) VALUES (?, ?, ?, ?)",
            (preset_id, model_name, "默认配置", json.dumps(config)),
        )
        conn.execute(
            "INSERT INTO active_preset (model_name, preset_id) VALUES (?, ?)",
            (model_name, preset_id),
        )
    conn.commit()
    conn.close()
    return db


def test_update_models_modifies_active_preset(db_path: Path):
    """Test that update_models modifies the active preset in DB."""
    store = ConfigStore(db_path)

    store.update_models({"chat": {"model": "gpt-4", "api_key": "new_key"}})

    # Check DB directly
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """
        SELECT mp.config
        FROM active_preset ap
        JOIN model_presets mp ON ap.preset_id = mp.id
        WHERE ap.model_name = ?
        """,
        ("chat",),
    )
    row = cursor.fetchone()
    conn.close()

    config = json.loads(row["config"])
    assert config["model"] == "gpt-4"
    assert config["api_key"] == "new_key"
    assert config["provider"] == "cloud"  # preserved


def test_update_models_ignores_none_values(db_path: Path):
    """Test that None values preserve existing config."""
    store = ConfigStore(db_path)

    store.update_models({"chat": {"model": "gpt-4", "api_key": None}})

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """
        SELECT mp.config
        FROM active_preset ap
        JOIN model_presets mp ON ap.preset_id = mp.id
        WHERE ap.model_name = ?
        """,
        ("chat",),
    )
    row = cursor.fetchone()
    conn.close()

    config = json.loads(row["config"])
    assert config["model"] == "gpt-4"
    assert config["api_key"] == "test_key"  # preserved


def test_update_models_handles_multiple_models(db_path: Path):
    """Test updating multiple models at once."""
    store = ConfigStore(db_path)

    store.update_models(
        {
            "chat": {"model": "gpt-4"},
            "embedding": {"provider": "ollama", "endpoint": "http://localhost:11434"},
        }
    )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Check chat
    cursor = conn.execute(
        """
        SELECT mp.config
        FROM active_preset ap
        JOIN model_presets mp ON ap.preset_id = mp.id
        WHERE ap.model_name = ?
        """,
        ("chat",),
    )
    chat_config = json.loads(cursor.fetchone()["config"])
    assert chat_config["model"] == "gpt-4"

    # Check embedding
    cursor = conn.execute(
        """
        SELECT mp.config
        FROM active_preset ap
        JOIN model_presets mp ON ap.preset_id = mp.id
        WHERE ap.model_name = ?
        """,
        ("embedding",),
    )
    embedding_config = json.loads(cursor.fetchone()["config"])
    assert embedding_config["provider"] == "ollama"
    assert embedding_config["endpoint"] == "http://localhost:11434"

    # Check asr unchanged
    cursor = conn.execute(
        """
        SELECT mp.config
        FROM active_preset ap
        JOIN model_presets mp ON ap.preset_id = mp.id
        WHERE ap.model_name = ?
        """,
        ("asr",),
    )
    asr_config = json.loads(cursor.fetchone()["config"])
    assert asr_config["model"] == "asr-model-v1"  # unchanged

    conn.close()


def test_update_models_only_modifies_active_preset(db_path: Path):
    """Test that update_models only modifies the active preset, not others."""
    # Create a second preset for chat
    conn = sqlite3.connect(db_path)
    other_config = {"provider": "openai", "model": "gpt-3.5", "api_key": "other_key"}
    conn.execute(
        "INSERT INTO model_presets (id, model_name, name, config) VALUES (?, ?, ?, ?)",
        ("chat_other", "chat", "Other Preset", json.dumps(other_config)),
    )
    conn.commit()
    conn.close()

    store = ConfigStore(db_path)
    store.update_models({"chat": {"model": "gpt-4"}})

    # Check that the inactive preset is unchanged
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT config FROM model_presets WHERE id = ?",
        ("chat_other",),
    )
    row = cursor.fetchone()
    conn.close()

    config = json.loads(row["config"])
    assert config["model"] == "gpt-3.5"  # unchanged


def test_update_models_handles_missing_active_preset(db_path: Path):
    """Test that update_models handles missing active preset gracefully."""
    # Remove active preset for chat
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM active_preset WHERE model_name = ?", ("chat",))
    conn.commit()
    conn.close()

    store = ConfigStore(db_path)
    # Should not crash, just skip the update
    store.update_models({"chat": {"model": "gpt-4"}})

    # Verify other models still work
    store.update_models({"embedding": {"model": "new-embedding"}})

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """
        SELECT mp.config
        FROM active_preset ap
        JOIN model_presets mp ON ap.preset_id = mp.id
        WHERE ap.model_name = ?
        """,
        ("embedding",),
    )
    row = cursor.fetchone()
    conn.close()

    config = json.loads(row["config"])
    assert config["model"] == "new-embedding"
