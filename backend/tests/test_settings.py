"""Tests for application settings loading."""

import json
import os
import sqlite3

import pytest

import config.settings as settings_module
from config.settings import ModelConfig, Settings, get_settings


SETTINGS_ENV_VARS = (
    "API_HOST",
    "API_PORT",
    "API_RELOAD",
    "CORS_ORIGINS",
    "LOG_LEVEL",
    "STORAGE",
    "STORAGE__DATA_DIR",
    "STORAGE__KEEP_VIDEOS",
    "MODELS",
    "MODELS__ASR__ENDPOINT",
    "MODELS__ASR__API_KEY",
    "MODELS__ASR__MODEL",
    "MODELS__ASR__PROTOCOL",
    "MODELS__EMBEDDING__ENDPOINT",
    "MODELS__EMBEDDING__API_KEY",
    "MODELS__EMBEDDING__MODEL",
    "MODELS__EMBEDDING__PROTOCOL",
    "MODELS__CHAT__ENDPOINT",
    "MODELS__CHAT__API_KEY",
    "MODELS__CHAT__MODEL",
    "MODELS__CHAT__PROTOCOL",
    "VIDEO_PROCESSING",
    "VIDEO_PROCESSING__AUTO_CLEAN",
    "VIDEO_PROCESSING__PRESERVE_TIMESTAMP",
    "VIDEO_PROCESSING__BILIBILI_COOKIE",
    "VIDEO_PROCESSING__OCR_REGION",
    "RAG",
    "RAG__CHUNK_SIZE",
    "RAG__OVERLAP",
    "RAG__TOP_K",
    "RAG__HYBRID_WEIGHTS",
)


@pytest.fixture(autouse=True)
def isolate_settings_env(monkeypatch):
    target_env_vars = {env_var.lower() for env_var in SETTINGS_ENV_VARS}
    for env_var in tuple(os.environ):
        if env_var.lower() in target_env_vars:
            monkeypatch.delenv(env_var, raising=False)


def _isolate_project_config(tmp_path, monkeypatch):
    backend_config_dir = tmp_path / "backend" / "config"
    backend_config_dir.mkdir(parents=True)
    monkeypatch.setattr(
        settings_module,
        "__file__",
        str(backend_config_dir / "settings.py"),
    )
    monkeypatch.chdir(tmp_path)
    # conftest.py sets MEMENTO_PROJECT_ROOT for global test isolation;
    # this test helper manages its own project root via __file__ + chdir,
    # so clear the env var to avoid interference.
    monkeypatch.delenv("MEMENTO_PROJECT_ROOT", raising=False)
    return backend_config_dir


def test_bilibili_cookie_env_overrides_yaml_empty_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "default.yaml"
    config_path.write_text(
        """
video_processing:
  bilibili_cookie: ""
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("VIDEO_PROCESSING__BILIBILI_COOKIE", "SESSDATA=example")

    settings = Settings.load_from_yaml(config_path)

    assert settings.video_processing.bilibili_cookie == "SESSDATA=example"


def test_model_protocol_defaults():
    config = ModelConfig()

    assert config.protocol is None


def test_default_asr_protocol_is_transcriptions():
    settings = Settings.load_from_yaml(settings_module.resolve_backend_dir() / "config" / "default.yaml")

    assert settings.models.asr.protocol == "transcriptions"
    assert settings.models.embedding.protocol is None
    assert settings.models.chat.protocol is None


def test_config_local_partial_override_preserves_config_yaml_nested_values(tmp_path, monkeypatch):
    backend_config_dir = _isolate_project_config(tmp_path, monkeypatch)
    (backend_config_dir / "default.yaml").write_text(
        """
storage:
  data_dir: "/default/data"
models:
  embedding:
    endpoint: "http://default-embedding:11434"
video_processing:
  bilibili_cookie: ""
""",
        encoding="utf-8",
    )
    (tmp_path / "config.yaml").write_text(
        """
storage:
  data_dir: "/user/data"
models:
  embedding:
    endpoint: "http://user-embedding:11434"
video_processing:
  auto_clean: false
""",
        encoding="utf-8",
    )
    (tmp_path / "config.local.yaml").write_text(
        """
video_processing:
  bilibili_cookie: "SESSDATA=local"
""",
        encoding="utf-8",
    )

    settings = get_settings()

    assert settings.storage.data_dir.as_posix() == "/user/data"
    assert settings.models.embedding.endpoint == "http://user-embedding:11434"
    assert settings.video_processing.auto_clean is False
    assert settings.video_processing.bilibili_cookie == "SESSDATA=local"


def test_relative_data_dir_resolved_against_project_root(tmp_path, monkeypatch):
    backend_config_dir = _isolate_project_config(tmp_path, monkeypatch)
    (backend_config_dir / "default.yaml").write_text(
        """
storage:
  data_dir: "./data"
""",
        encoding="utf-8",
    )

    settings = get_settings()

    assert settings.storage.data_dir == tmp_path / "data"


def test_absolute_data_dir_not_changed(tmp_path, monkeypatch):
    backend_config_dir = _isolate_project_config(tmp_path, monkeypatch)
    (backend_config_dir / "default.yaml").write_text(
        """
storage:
  data_dir: "/absolute/data"
""",
        encoding="utf-8",
    )

    settings = get_settings()

    assert settings.storage.data_dir.as_posix() == "/absolute/data"


def test_bilibili_cookie_env_overrides_config_local_value(tmp_path, monkeypatch):
    backend_config_dir = _isolate_project_config(tmp_path, monkeypatch)
    (backend_config_dir / "default.yaml").write_text("", encoding="utf-8")
    (tmp_path / "config.local.yaml").write_text(
        """
video_processing:
  bilibili_cookie: "SESSDATA=local"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("VIDEO_PROCESSING__BILIBILI_COOKIE", "SESSDATA=env")

    settings = get_settings()

    assert settings.video_processing.bilibili_cookie == "SESSDATA=env"


def test_tilde_data_dir_expanded_to_home(tmp_path, monkeypatch):
    """Test that ~ in data_dir is expanded to user home directory."""
    backend_config_dir = _isolate_project_config(tmp_path, monkeypatch)
    (backend_config_dir / "default.yaml").write_text(
        """
storage:
  data_dir: "~/memento_data"
""",
        encoding="utf-8",
    )

    settings = get_settings()

    assert settings.storage.data_dir.is_absolute()
    assert "~" not in str(settings.storage.data_dir)
    assert str(settings.storage.data_dir).startswith(str(settings_module.Path.home()))


def test_db_overrides_yaml_model_config(tmp_path, monkeypatch):
    """Test that DB model presets override YAML configuration."""
    backend_config_dir = _isolate_project_config(tmp_path, monkeypatch)
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create YAML config
    (backend_config_dir / "default.yaml").write_text(
        f"""
storage:
  data_dir: "{data_dir}"
models:
  chat:
    model: claude-3-5-sonnet
""",
        encoding="utf-8",
    )

    # Create DB with different chat config
    db_path = data_dir / "memento.db"
    conn = sqlite3.connect(db_path)
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
        """
    )
    chat_config = {
        "endpoint": "https://api.openai.com/v1",
        "model": "gpt-4",
        "api_key": "test_key",
    }
    conn.execute(
        "INSERT INTO model_presets (id, model_name, name, config) VALUES (?, ?, ?, ?)",
        ("preset_1", "chat", "OpenAI GPT-4", json.dumps(chat_config)),
    )
    conn.execute(
        "INSERT INTO active_preset (model_name, preset_id) VALUES (?, ?)",
        ("chat", "preset_1"),
    )
    conn.commit()
    conn.close()

    settings = get_settings()

    # DB should override YAML
    assert settings.models.chat.model == "gpt-4"
    assert settings.models.chat.endpoint == "https://api.openai.com/v1"
    assert settings.models.chat.api_key == "test_key"


def test_db_overrides_yaml_app_config(tmp_path, monkeypatch):
    """Test that DB app_config sections override YAML configuration."""
    backend_config_dir = _isolate_project_config(tmp_path, monkeypatch)
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create YAML config
    (backend_config_dir / "default.yaml").write_text(
        f"""
storage:
  data_dir: "{data_dir}"
rag:
  chunk_size: 800
  overlap: 80
  top_k: 5
""",
        encoding="utf-8",
    )

    # Create DB with different rag config
    db_path = data_dir / "memento.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE app_config (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    rag_config = {"chunk_size": 1200, "overlap": 100, "top_k": 10}
    conn.execute(
        "INSERT INTO app_config (key, value) VALUES (?, ?)",
        ("rag", json.dumps(rag_config)),
    )
    conn.commit()
    conn.close()

    settings = get_settings()

    # DB should override YAML
    assert settings.rag.chunk_size == 1200
    assert settings.rag.overlap == 100
    assert settings.rag.top_k == 10


def test_db_missing_falls_back_to_yaml(tmp_path, monkeypatch):
    """Test that missing DB falls back to YAML configuration."""
    backend_config_dir = _isolate_project_config(tmp_path, monkeypatch)
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create YAML config (no DB)
    (backend_config_dir / "default.yaml").write_text(
        f"""
storage:
  data_dir: "{data_dir}"
""",
        encoding="utf-8",
    )

    settings = get_settings()


def test_db_partial_override_preserves_yaml_values(tmp_path, monkeypatch):
    """Test that DB only overrides models with active presets."""
    backend_config_dir = _isolate_project_config(tmp_path, monkeypatch)
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create YAML config
    (backend_config_dir / "default.yaml").write_text(
        f"""
storage:
  data_dir: "{data_dir}"
""",
        encoding="utf-8",
    )

    # Create DB with only chat preset
    db_path = data_dir / "memento.db"
    conn = sqlite3.connect(db_path)
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
        """
    )
    chat_config = {"model": "gpt-4"}
    conn.execute(
        "INSERT INTO model_presets (id, model_name, name, config) VALUES (?, ?, ?, ?)",
        ("preset_1", "chat", "OpenAI", json.dumps(chat_config)),
    )
    conn.execute(
        "INSERT INTO active_preset (model_name, preset_id) VALUES (?, ?)",
        ("chat", "preset_1"),
    )
    conn.commit()
    conn.close()

    settings = get_settings()

    # asr and embedding should use YAML values
    # chat should use DB value
    assert settings.models.chat.model == "gpt-4"


def test_update_models_writes_to_db_not_yaml(tmp_path, monkeypatch):
    """Test that ConfigStore.update_models() writes to DB, not YAML files."""
    from core.config_store import ConfigStore

    backend_config_dir = _isolate_project_config(tmp_path, monkeypatch)
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create YAML config
    (backend_config_dir / "default.yaml").write_text(
        f"""
storage:
  data_dir: "{data_dir}"
models:
  chat:
    model: claude-3-5-sonnet
""",
        encoding="utf-8",
    )

    # Create config.local.yaml to verify it's not written
    config_local = tmp_path / "config.local.yaml"
    config_local.write_text(
        """
models:
  chat:
    api_key: old_key
""",
        encoding="utf-8",
    )
    original_config_local_mtime = config_local.stat().st_mtime

    # Create DB with active preset
    db_path = data_dir / "memento.db"
    conn = sqlite3.connect(db_path)
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
        """
    )
    chat_config = {"model": "gpt-4", "api_key": "test_key"}
    conn.execute(
        "INSERT INTO model_presets (id, model_name, name, config) VALUES (?, ?, ?, ?)",
        ("preset_1", "chat", "Custom Preset", json.dumps(chat_config)),
    )
    conn.execute(
        "INSERT INTO active_preset (model_name, preset_id) VALUES (?, ?)",
        ("chat", "preset_1"),
    )
    conn.commit()
    conn.close()

    # Update model config
    store = ConfigStore(db_path)
    store.update_models({"chat": {"model": "gpt-4-turbo", "api_key": "new_key"}})

    # Verify DB was updated
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

    updated_config = json.loads(row["config"])
    assert updated_config["model"] == "gpt-4-turbo"
    assert updated_config["api_key"] == "new_key"

    # Verify config.local.yaml was NOT modified
    assert config_local.stat().st_mtime == original_config_local_mtime


def test_update_models_masked_api_key_preservation(tmp_path, monkeypatch):
    """Test that masked api_key (***) preserves the original value."""
    from core.config_store import ConfigStore

    backend_config_dir = _isolate_project_config(tmp_path, monkeypatch)
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    (backend_config_dir / "default.yaml").write_text(
        f"""
storage:
  data_dir: "{data_dir}"
""",
        encoding="utf-8",
    )

    # Create DB with active preset
    db_path = data_dir / "memento.db"
    conn = sqlite3.connect(db_path)
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
        """
    )
    chat_config = {"model": "gpt-4", "api_key": "secret_original_key"}
    conn.execute(
        "INSERT INTO model_presets (id, model_name, name, config) VALUES (?, ?, ?, ?)",
        ("preset_1", "chat", "Custom", json.dumps(chat_config)),
    )
    conn.execute(
        "INSERT INTO active_preset (model_name, preset_id) VALUES (?, ?)",
        ("chat", "preset_1"),
    )
    conn.commit()
    conn.close()

    # Update with None api_key (simulates masked key from UI)
    store = ConfigStore(db_path)
    store.update_models({"chat": {"model": "gpt-4-turbo", "api_key": None}})

    # Verify api_key was preserved
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

    updated_config = json.loads(row["config"])
    assert updated_config["model"] == "gpt-4-turbo"  # updated
    assert updated_config["api_key"] == "secret_original_key"  # preserved


def test_update_models_only_affects_active_preset(tmp_path, monkeypatch):
    """Test that updates only modify the active preset, not other presets."""
    from core.config_store import ConfigStore

    backend_config_dir = _isolate_project_config(tmp_path, monkeypatch)
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    (backend_config_dir / "default.yaml").write_text(
        f"""
storage:
  data_dir: "{data_dir}"
""",
        encoding="utf-8",
    )

    # Create DB with multiple presets
    db_path = data_dir / "memento.db"
    conn = sqlite3.connect(db_path)
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
        """
    )
    # Create two chat presets
    preset1_config = {"model": "gpt-4"}
    preset2_config = {"model": "gpt-3.5-turbo"}
    conn.execute(
        "INSERT INTO model_presets (id, model_name, name, config) VALUES (?, ?, ?, ?)",
        ("preset_1", "chat", "GPT-4", json.dumps(preset1_config)),
    )
    conn.execute(
        "INSERT INTO model_presets (id, model_name, name, config) VALUES (?, ?, ?, ?)",
        ("preset_2", "chat", "GPT-3.5", json.dumps(preset2_config)),
    )
    # Set preset_1 as active
    conn.execute(
        "INSERT INTO active_preset (model_name, preset_id) VALUES (?, ?)",
        ("chat", "preset_1"),
    )
    conn.commit()
    conn.close()

    # Update chat model
    store = ConfigStore(db_path)
    store.update_models({"chat": {"model": "gpt-4-turbo"}})

    # Verify only preset_1 was updated
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute("SELECT config FROM model_presets WHERE id = ?", ("preset_1",))
    preset1_after = json.loads(cursor.fetchone()["config"])

    cursor = conn.execute("SELECT config FROM model_presets WHERE id = ?", ("preset_2",))
    preset2_after = json.loads(cursor.fetchone()["config"])

    conn.close()

    # preset_1 (active) should be updated
    assert preset1_after["model"] == "gpt-4-turbo"
    # preset_2 (inactive) should be unchanged
    assert preset2_after["model"] == "gpt-3.5-turbo"
