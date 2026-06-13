"""Tests for the settings API."""

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from api import settings as settings_api
from main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "config.local.yaml"
    monkeypatch.setattr(settings_api, "local_config_path", lambda: config_path)
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
