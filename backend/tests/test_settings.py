"""Tests for application settings loading."""

import os

import pytest

import config.settings as settings_module
from config.settings import Settings, get_settings


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
    "MODELS__ASR__PROVIDER",
    "MODELS__ASR__ENDPOINT",
    "MODELS__ASR__API_KEY",
    "MODELS__ASR__MODEL",
    "MODELS__EMBEDDING__PROVIDER",
    "MODELS__EMBEDDING__ENDPOINT",
    "MODELS__EMBEDDING__API_KEY",
    "MODELS__EMBEDDING__MODEL",
    "MODELS__CHAT__PROVIDER",
    "MODELS__CHAT__ENDPOINT",
    "MODELS__CHAT__API_KEY",
    "MODELS__CHAT__MODEL",
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
