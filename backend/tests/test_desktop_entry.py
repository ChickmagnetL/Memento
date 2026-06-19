"""Tests for frozen-mode path resolution."""

import os
from pathlib import Path

from config.settings import get_settings, resolve_backend_dir, resolve_project_root


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


def _isolate_settings_sources(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
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


def test_resolve_backend_dir_normal_mode():
    """In normal mode it is the backend package directory."""
    assert (resolve_backend_dir() / "config").is_dir()


def test_resolve_backend_dir_frozen_mode(monkeypatch, tmp_path: Path):
    import sys

    bundle = tmp_path / "bundle"
    (bundle / "config").mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    assert resolve_backend_dir() == bundle


def test_resolve_project_root_uses_env_override(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "project"
    monkeypatch.setenv("MEMENTO_PROJECT_ROOT", str(project_root))

    assert resolve_project_root(tmp_path / "bundle") == project_root


def test_frozen_settings_load_project_root_local_config(monkeypatch, tmp_path: Path):
    import sys

    _isolate_settings_sources(monkeypatch, tmp_path)
    bundle = tmp_path / "bundle"
    project_root = tmp_path / "project"
    (bundle / "config").mkdir(parents=True)
    project_root.mkdir()
    (project_root / "config.local.yaml").write_text(
        "video_processing:\n  bilibili_cookie: test-cookie\n"
    )
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setenv("MEMENTO_PROJECT_ROOT", str(project_root))

    settings = get_settings()

    assert settings.video_processing.bilibili_cookie == "test-cookie"
