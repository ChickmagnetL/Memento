"""Tests for the video processing API."""

import json
import os
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app


SETTINGS_ENV_PREFIXES = (
    "STORAGE",
    "MODELS",
    "VIDEO_PROCESSING",
    "RAG",
)
SETTINGS_ENV_VARS = (
    "API_HOST",
    "API_PORT",
    "API_RELOAD",
    "CORS_ORIGINS",
    "LOG_LEVEL",
)


def _isolate_settings_env(monkeypatch):
    target_env_vars = {env_var.lower() for env_var in SETTINGS_ENV_VARS}
    target_env_prefixes = tuple(
        f"{env_prefix.lower()}__" for env_prefix in SETTINGS_ENV_PREFIXES
    )
    target_env_vars.update(env_prefix.lower() for env_prefix in SETTINGS_ENV_PREFIXES)
    for env_var in tuple(os.environ):
        normalized_env_var = env_var.lower()
        if (
            normalized_env_var in target_env_vars
            or normalized_env_var.startswith(target_env_prefixes)
        ):
            monkeypatch.delenv(env_var, raising=False)


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    _isolate_settings_env(monkeypatch)

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "memento.db"

    # Create backend/config structure
    backend_dir = tmp_path / "backend"
    config_dir = backend_dir / "config"
    config_dir.mkdir(parents=True)

    # Create minimal default.yaml
    (config_dir / "default.yaml").write_text(
        f"""
storage:
  data_dir: "{data_dir}"
models:
  asr:
    provider: local
    protocol: transcriptions
  chat:
    provider: cloud
  embedding:
    provider: ollama
video_processing:
  bilibili_cookie: ""
  douyin_cookie: ""
""",
        encoding="utf-8",
    )

    # Mock resolve functions
    from config import settings as settings_module
    monkeypatch.setattr(settings_module, "resolve_backend_dir", lambda: backend_dir)
    monkeypatch.setattr(settings_module, "resolve_project_root", lambda backend_dir=None: tmp_path)

    # Create test DB with basic schema
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
    # Create default presets
    for model_name in ["chat", "embedding", "asr"]:
        preset_id = f"{model_name}_default"
        config = {}
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

    app.state.chat_sessions = {}
    with TestClient(app) as test_client:
        yield test_client


def test_get_video_processing_settings_default(client):
    """Test GET /api/video-processing returns default empty cookie configuration."""
    response = client.get("/api/video-processing")

    assert response.status_code == 200
    data = response.json()

    # Verify required fields exist
    assert "bilibili_cookie" in data
    assert "douyin_cookie" in data
    assert "bilibili_refresh_token" in data
    assert "bilibili_cookie_expires_at" in data

    # Verify default values
    assert data["bilibili_cookie"] == ""
    assert data["douyin_cookie"] == ""
    assert data["bilibili_refresh_token"] == ""
    assert data["bilibili_cookie_expires_at"] == 0
