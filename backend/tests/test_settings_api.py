"""Tests for the settings API."""

import asyncio
import os
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from api import settings as settings_api
from config.settings import ModelConfig, Settings
from main import app, settings as app_settings


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
    config_path = tmp_path / "config.local.yaml"
    monkeypatch.setattr(settings_api, "local_config_path", lambda: config_path)
    monkeypatch.setattr(app_settings.storage, "data_dir", tmp_path / "data")

    def _test_settings() -> Settings:
        if not config_path.exists():
            return Settings()
        return Settings(**(yaml.safe_load(config_path.read_text()) or {}))

    monkeypatch.setattr(settings_api, "get_settings", _test_settings)
    app.state.chat_sessions = {}
    with TestClient(app) as test_client:
        yield test_client, config_path


def test_get_settings_masks_api_keys(client):
    test_client, _config_path = client
    response = test_client.get("/api/settings/models")

    assert response.status_code == 200
    models = response.json()
    for name in ("chat", "embedding", "asr"):
        assert name in models
        key = models[name]["api_key"]
        assert key is None or not key.startswith("sk-") or key.endswith("***")


def test_put_settings_persists_to_local_config(client):
    test_client, config_path = client

    response = test_client.put(
        "/api/settings/models",
        json={"chat": {"provider": "cloud", "api_key": "sk-real", "model": "m1"}},
    )

    assert response.status_code == 200
    data = yaml.safe_load(config_path.read_text())
    assert data["models"]["chat"]["api_key"] == "sk-real"


def test_local_config_path_uses_project_root_env(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "project"
    monkeypatch.setenv("MEMENTO_PROJECT_ROOT", str(project_root))

    assert settings_api.local_config_path() == project_root / "config.local.yaml"


def test_put_settings_round_trips_project_root_config(monkeypatch, tmp_path: Path):
    _isolate_settings_env(monkeypatch)
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setenv("MEMENTO_PROJECT_ROOT", str(project_root))

    response = asyncio.run(
        settings_api.update_model_settings(
            settings_api.ModelsUpdateRequest(
                chat={
                    "provider": "cloud",
                    "endpoint": "https://example.invalid/v1",
                    "api_key": "sk-roundtrip",
                    "model": "roundtrip-model",
                }
            )
        )
    )

    data = yaml.safe_load((project_root / "config.local.yaml").read_text())
    assert data["models"]["chat"]["endpoint"] == "https://example.invalid/v1"
    assert data["models"]["chat"]["api_key"] == "sk-roundtrip"
    assert data["models"]["chat"]["model"] == "roundtrip-model"
    assert response["chat"]["endpoint"] == "https://example.invalid/v1"
    assert response["chat"]["api_key"] == "sk-r***"
    assert response["chat"]["model"] == "roundtrip-model"


def test_put_masked_key_does_not_overwrite(client):
    test_client, config_path = client
    test_client.put(
        "/api/settings/models", json={"chat": {"api_key": "sk-real"}}
    )

    # Frontend round-trips the masked value; it must be treated as "no change".
    test_client.put(
        "/api/settings/models", json={"chat": {"api_key": "sk-r***", "model": "m2"}}
    )

    data = yaml.safe_load(config_path.read_text())
    assert data["models"]["chat"]["api_key"] == "sk-real"
    assert data["models"]["chat"]["model"] == "m2"


def test_status_reports_configuration_state(client):
    test_client, _config_path = client
    response = test_client.get("/api/settings/status")

    assert response.status_code == 200
    status_map = response.json()
    assert set(status_map) == {"chat", "embedding", "asr"}
    assert status_map["asr"]["status"] in {"ok", "unreachable"}
    assert status_map["chat"]["status"] in {"configured", "not_configured"}


def test_local_provider_configured_without_api_key():
    # Local/ollama models need no api_key; endpoint + model is enough.
    config = ModelConfig(
        provider="ollama",
        endpoint="http://localhost:11434",
        model="qwen3-embedding:0.6b",
    )
    assert settings_api._configured(config) == "configured"


def test_cloud_provider_not_configured_without_api_key():
    config = ModelConfig(provider="cloud", model="deepseek-chat")
    assert settings_api._configured(config) == "not_configured"


def test_cloud_provider_configured_with_api_key():
    config = ModelConfig(provider="cloud", api_key="sk-x", model="deepseek-chat")
    assert settings_api._configured(config) == "configured"


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def test_status_ollama_provider_probes_endpoint(client, monkeypatch):
    test_client, _config_path = client
    test_client.put(
        "/api/settings/models",
        json={"embedding": {"provider": "ollama", "model": "qwen3-embedding:0.6b"}},
    )
    monkeypatch.setattr(
        settings_api, "_check_ollama_health", lambda endpoint: "ok"
    )

    response = test_client.get("/api/settings/status")

    assert response.json()["embedding"]["status"] == "ok"


def test_asr_health_non_json_is_unreachable(monkeypatch):
    # A 200 /health response with a non-JSON body must not crash /status.
    monkeypatch.setattr(
        settings_api,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse(b"<html>not json</html>"),
    )
    assert settings_api._check_asr_health("http://localhost:8001") == "unreachable"


def test_get_api_key_returns_plaintext(client, monkeypatch):
    import config.settings as cs

    test_client, config_path = client
    test_client.put(
        "/api/settings/models",
        json={"chat": {"api_key": "sk-real-key-12345"}},
    )

    # Patch get_settings so the GET handler reads local config from tmp path
    import yaml as _yaml

    def _patched():
        s = cs.Settings()
        if config_path.exists():
            data = _yaml.safe_load(config_path.read_text()) or {}
            models_data = data.get("models", {})
            if "chat" in models_data and "api_key" in models_data["chat"]:
                s.models.chat.api_key = models_data["chat"]["api_key"]
        return s

    monkeypatch.setattr(settings_api, "get_settings", _patched)

    response = test_client.get("/api/settings/models/chat/api_key")

    assert response.status_code == 200
    assert response.json() == {"api_key": "sk-real-key-12345"}


def test_get_api_key_returns_none_when_not_set(client, monkeypatch):
    import config.settings as cs

    test_client, _config_path = client

    monkeypatch.setattr(settings_api, "get_settings", lambda: cs.Settings())

    response = test_client.get("/api/settings/models/chat/api_key")

    assert response.status_code == 200
    assert response.json() == {"api_key": None}
