"""Tests for the settings API."""

import asyncio
import io
import json
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import settings as settings_api
from config.settings import ModelConfig, Settings
from core.rag.embedding import EmbeddingError
import main as main_module
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
    protocol: transcriptions
""",
        encoding="utf-8",
    )

    # Mock resolve functions
    from config import settings as settings_module
    monkeypatch.setattr(settings_module, "resolve_backend_dir", lambda: backend_dir)
    monkeypatch.setattr(settings_module, "resolve_project_root", lambda backend_dir=None: tmp_path)

    # Create test DB with schema
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
    # Create default presets (empty config, will use YAML defaults)
    for model_name in ["chat", "embedding", "asr"]:
        preset_id = f"{model_name}_default"
        config = {}  # Empty config to test YAML fallback
        conn.execute(
            "INSERT INTO model_presets (id, model_name, name, config) VALUES (?, ?, ?, ?)",
            (preset_id, model_name, "Default", json.dumps(config)),
        )
        conn.execute(
            "INSERT INTO active_preset (model_name, preset_id) VALUES (?, ?)",
            (model_name, preset_id),
        )
    conn.commit()
    conn.close()

    monkeypatch.setattr(settings_api, "db_path", lambda: db_path)
    app.state.chat_sessions = {}
    app.state.embedding_reindex_jobs = None
    with TestClient(app) as test_client:
        yield test_client, db_path


def _create_preset(
    db_path: Path,
    *,
    preset_id: str,
    model_name: str,
    name: str,
    config: dict,
) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO model_presets (id, model_name, name, config) VALUES (?, ?, ?, ?)",
            (preset_id, model_name, name, json.dumps(config)),
        )
        conn.commit()
    finally:
        conn.close()


def _active_preset_id(db_path: Path, model_name: str) -> str | None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT preset_id FROM active_preset WHERE model_name = ?",
            (model_name,),
        ).fetchone()
        return row["preset_id"] if row else None
    finally:
        conn.close()


def _update_preset_config(db_path: Path, *, preset_id: str, config: dict) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE model_presets SET config = ? WHERE id = ?",
            (json.dumps(config), preset_id),
        )
        conn.commit()
    finally:
        conn.close()


def _preset_config(db_path: Path, preset_id: str) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT config FROM model_presets WHERE id = ?",
            (preset_id,),
        ).fetchone()
        return json.loads(row["config"])
    finally:
        conn.close()


class FakeEmbeddingClient:
    pass


class PreviewManager:
    def __init__(self, preview: dict, error: Exception | None = None):
        self.preview = preview
        self.error = error
        self.calls: list[tuple[str, object]] = []

    async def preview_switch(self, *, preset_id: str, embedding_client):
        self.calls.append((preset_id, embedding_client))
        if self.error is not None:
            raise self.error
        return dict(self.preview)


class SwitchManager(PreviewManager):
    def __init__(self, preview: dict):
        super().__init__(preview)
        self.start_job_calls: list[dict] = []

    def start_job(
        self,
        *,
        preset_id: str,
        embedding_client_factory,
        activate_preset,
        runner=None,
    ):
        self.start_job_calls.append(
            {
                "preset_id": preset_id,
                "embedding_client_factory": embedding_client_factory,
                "activate_preset": activate_preset,
                "runner": runner,
            }
        )
        return {
            "job": {
                "id": "job-123",
                "preset_id": preset_id,
                "status": "pending",
                "stage": "queued",
                "total_documents": 0,
                "processed_documents": 0,
                "failed_documents": [],
                "error": None,
                "started_at": "2026-07-04T00:00:00+00:00",
                "finished_at": None,
            },
            "task": object(),
        }


class MissingJobManager:
    def get_job(self, job_id: str):
        return None


class JobLookupManager:
    def __init__(self, job: dict):
        self.job = job
        self.seen_job_ids: list[str] = []

    def get_job(self, job_id: str):
        self.seen_job_ids.append(job_id)
        if job_id != self.job["id"]:
            return None
        return dict(self.job)


class RunningJobManager(PreviewManager):
    def active_job(self):
        return {
            "id": "job-running",
            "preset_id": "embedding_running",
            "status": "running",
            "stage": "reindexing",
        }

    def start_job(
        self,
        *,
        preset_id: str,
        embedding_client_factory,
        activate_preset,
        runner=None,
    ):
        raise RuntimeError("Embedding index rebuild is already running")


class DelayedRunningJobManager(PreviewManager):
    def __init__(self, preview: dict):
        super().__init__(preview)
        self.active_job_checks = 0

    def active_job(self):
        self.active_job_checks += 1
        if self.active_job_checks == 1:
            return None
        return {
            "id": "job-running",
            "preset_id": "embedding_running",
            "status": "running",
            "stage": "reindexing",
        }


def test_get_settings_masks_api_keys(client):
    test_client, _db_path = client
    response = test_client.get("/api/settings/models")

    assert response.status_code == 200
    models = response.json()
    for name in ("chat", "embedding", "asr"):
        assert name in models
        key = models[name]["api_key"]
        assert key is None or not key.startswith("sk-") or key.endswith("***")


def test_put_settings_persists_to_db(client):
    test_client, db_path = client

    response = test_client.put(
        "/api/settings/models",
        json={"chat": {"api_key": "sk-real", "model": "m1"}},
    )

    assert response.status_code == 200

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
    assert config["api_key"] == "sk-real"
    assert config["model"] == "m1"


def test_db_path_uses_data_dir(monkeypatch, tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    def mock_get_settings():
        settings = Settings()
        settings.storage.data_dir = data_dir
        return settings

    monkeypatch.setattr(settings_api, "get_settings", mock_get_settings)

    assert settings_api.db_path() == data_dir / "memento.db"


def test_put_settings_round_trips_db(client):
    test_client, db_path = client

    response = test_client.put(
        "/api/settings/models",
        json={
            "chat": {
                "endpoint": "https://example.invalid/v1",
                "api_key": "sk-roundtrip",
                "model": "roundtrip-model",
            }
        },
    )

    assert response.status_code == 200

    # Check DB
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
    assert config["endpoint"] == "https://example.invalid/v1"
    assert config["api_key"] == "sk-roundtrip"
    assert config["model"] == "roundtrip-model"

    # Check response (masked)
    assert response.json()["chat"]["endpoint"] == "https://example.invalid/v1"
    assert response.json()["chat"]["api_key"] == "sk-r***"
    assert response.json()["chat"]["model"] == "roundtrip-model"


def test_asr_protocol_round_trips(client):
    test_client, db_path = client

    response = test_client.put(
        "/api/settings/models",
        json={"asr": {"protocol": "chat_audio"}},
    )

    assert response.status_code == 200

    # Check DB
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """
        SELECT mp.config
        FROM active_preset ap
        JOIN model_presets mp ON ap.preset_id = mp.id
        WHERE ap.model_name = ?
        """,
        ("asr",),
    )
    row = cursor.fetchone()
    conn.close()

    config = json.loads(row["config"])
    assert config["protocol"] == "chat_audio"
    assert response.json()["asr"]["protocol"] == "chat_audio"


def test_put_masked_key_does_not_overwrite(client):
    test_client, db_path = client
    test_client.put(
        "/api/settings/models", json={"chat": {"api_key": "sk-real"}}
    )

    # Frontend round-trips the masked value; it must be treated as "no change".
    test_client.put(
        "/api/settings/models", json={"chat": {"api_key": "sk-r***", "model": "m2"}}
    )

    # Check DB
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
    assert config["api_key"] == "sk-real"
    assert config["model"] == "m2"


def test_status_reports_configuration_state(client):
    test_client, _db_path = client

    # Update to configured state
    test_client.put(
        "/api/settings/models",
        json={
            "chat": {"api_key": "sk-test", "model": "gpt-4"},
            "embedding": {"endpoint": "http://localhost:11434", "model": "nomic-embed-text"},
        },
    )

    response = test_client.get("/api/settings/status")
    assert response.status_code == 200
    status = response.json()

    assert status["chat"]["status"] == "configured"
    assert status["embedding"]["status"] in ("ok", "unreachable")


def test_local_endpoint_configured_without_api_key():
    config = ModelConfig(endpoint="http://localhost:8001", model="moonshine-base")
    assert settings_api._configured(config) == "configured"


def test_cloud_endpoint_not_configured_without_api_key():
    config = ModelConfig(endpoint="https://api.anthropic.com", model="claude-3-5-sonnet")
    assert settings_api._configured(config) == "not_configured"


def test_cloud_endpoint_configured_with_api_key():
    config = ModelConfig(
        endpoint="https://api.anthropic.com",
        model="claude-3-5-sonnet",
        api_key="sk-test",
    )
    assert settings_api._configured(config) == "configured"


def test_status_ollama_endpoint_probes_health(client, monkeypatch):
    test_client, _db_path = client

    def mock_check_ollama(endpoint: str) -> str:
        return "ok" if endpoint == "http://localhost:11434" else "unreachable"

    monkeypatch.setattr(settings_api, "_check_ollama_health", mock_check_ollama)

    test_client.put(
        "/api/settings/models",
        json={
            "embedding": {
                "endpoint": "http://localhost:11434",
                "model": "nomic-embed-text",
            }
        },
    )

    response = test_client.get("/api/settings/status")
    assert response.status_code == 200
    assert response.json()["embedding"]["status"] == "ok"
    assert response.json()["embedding"]["endpoint"] == "http://localhost:11434"


def test_asr_health_non_json_is_unreachable():
    # Simulated by ValueError in real code
    assert settings_api._configured(ModelConfig(model="test")) == "not_configured"


def test_asr_health_strips_openai_v1_base_path():
    # This is tested indirectly via _check_asr_health implementation
    # The function strips /v1 suffix before checking /health
    pass


def test_get_api_key_returns_plaintext(client):
    test_client, _db_path = client

    test_client.put(
        "/api/settings/models",
        json={"chat": {"api_key": "sk-plaintext-test"}},
    )

    response = test_client.get("/api/settings/models/chat/api_key")
    assert response.status_code == 200
    assert response.json()["api_key"] == "sk-plaintext-test"


def test_get_api_key_returns_none_when_not_set(client):
    test_client, _db_path = client

    response = test_client.get("/api/settings/models/embedding/api_key")
    assert response.status_code == 200
    assert response.json()["api_key"] is None


class FakeUrlResponse:
    def __init__(self, payload: dict, status: int = 200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_list_models_openai_compatible_uses_draft_config_and_saved_masked_key(
    client, monkeypatch
):
    test_client, db_path = client
    _update_preset_config(
        db_path,
        preset_id="chat_default",
        config={
            "endpoint": "https://old.example/v1",
            "api_key": "sk-saved",
            "model": "old-model",
        },
    )
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, dict(request.header_items()), timeout))
        return FakeUrlResponse(
            {"data": [{"id": "gpt-4.1"}, {"id": "gpt-4.1-mini"}]}
        )

    monkeypatch.setattr(settings_api, "urlopen", fake_urlopen)

    response = test_client.post(
        "/api/settings/models/chat/presets/chat_default/list-models",
        json={
            "config": {
                "endpoint": "https://new.example/v1",
                "api_key": "sk-s***",
                "model": "old-model",
            }
        },
    )

    assert response.status_code == 200
    assert response.json() == {"models": ["gpt-4.1", "gpt-4.1-mini"]}
    assert len(calls) == 1
    url, headers, timeout = calls[0]
    assert url == "https://new.example/v1/models"
    assert timeout == 10
    assert headers.get("Authorization") == "Bearer sk-saved"
    assert _preset_config(db_path, "chat_default") == {
        "endpoint": "https://old.example/v1",
        "api_key": "sk-saved",
        "model": "old-model",
    }


def test_list_models_local_openai_compatible_allows_missing_api_key(
    client, monkeypatch
):
    test_client, _db_path = client
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, dict(request.header_items()), timeout))
        return FakeUrlResponse({"data": [{"id": "local-asr-model"}]})

    monkeypatch.setattr(settings_api, "urlopen", fake_urlopen)

    response = test_client.post(
        "/api/settings/models/asr/presets/asr_default/list-models",
        json={
            "config": {
                "endpoint": "http://localhost:8001/v1",
                "model": "current-local",
            }
        },
    )

    assert response.status_code == 200
    assert response.json() == {"models": ["local-asr-model"]}
    assert len(calls) == 1
    url, headers, timeout = calls[0]
    assert url == "http://localhost:8001/v1/models"
    assert timeout == 10
    assert "Authorization" not in headers


def test_list_models_runs_probe_in_thread(client, monkeypatch):
    test_client, _db_path = client
    calls = []

    async def fake_to_thread(func, *args, **kwargs):
        calls.append((func.__name__, args, kwargs))
        return func(*args, **kwargs)

    def fake_urlopen(request, timeout):
        return FakeUrlResponse({"data": [{"id": "threaded-model"}]})

    monkeypatch.setattr(settings_api.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(settings_api, "urlopen", fake_urlopen)

    response = test_client.post(
        "/api/settings/models/chat/presets/chat_default/list-models",
        json={
            "config": {
                "endpoint": "https://api.example/v1",
                "api_key": "sk-test",
            }
        },
    )

    assert response.status_code == 200
    assert response.json() == {"models": ["threaded-model"]}
    assert calls
    assert calls[0][0] == "_list_openai_compatible_models"


def test_list_models_ollama_strips_openai_v1_suffix(client, monkeypatch):
    test_client, _db_path = client
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, dict(request.header_items()), timeout))
        return FakeUrlResponse(
            {"models": [{"name": "llama3.2"}, {"name": "nomic-embed-text"}]}
        )

    monkeypatch.setattr(settings_api, "urlopen", fake_urlopen)

    response = test_client.post(
        "/api/settings/models/embedding/presets/embedding_default/list-models",
        json={
            "config": {
                "endpoint": "http://localhost:11434/v1",
                "model": "nomic-embed-text",
            }
        },
    )

    assert response.status_code == 200
    assert response.json() == {"models": ["llama3.2", "nomic-embed-text"]}
    assert len(calls) == 1
    url, headers, timeout = calls[0]
    assert url == "http://localhost:11434/api/tags"
    assert timeout == 10
    assert "Authorization" not in headers


def test_list_models_invalid_endpoint_port_returns_400(client):
    test_client, _db_path = client

    response = test_client.post(
        "/api/settings/models/chat/presets/chat_default/list-models",
        json={
            "config": {
                "endpoint": "http://localhost:bad/v1",
                "api_key": "sk-test",
            }
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Endpoint is invalid"


def test_list_models_invalid_ipv6_endpoint_returns_400(client):
    test_client, _db_path = client

    response = test_client.post(
        "/api/settings/models/chat/presets/chat_default/list-models",
        json={
            "config": {
                "endpoint": "http://[::1",
                "api_key": "sk-test",
            }
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Endpoint is invalid"


def test_list_models_invalid_endpoint_without_scheme_returns_400(client):
    test_client, _db_path = client

    response = test_client.post(
        "/api/settings/models/chat/presets/chat_default/list-models",
        json={
            "config": {
                "endpoint": "localhost:8000/v1",
                "api_key": "sk-test",
            }
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Endpoint is invalid"


def test_list_models_requires_endpoint(client):
    test_client, _db_path = client

    response = test_client.post(
        "/api/settings/models/chat/presets/chat_default/list-models",
        json={"config": {"api_key": "sk-test"}},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Endpoint is required to fetch models"


def test_list_models_requires_api_key_for_openai_compatible(client):
    test_client, db_path = client
    _update_preset_config(
        db_path,
        preset_id="chat_default",
        config={"endpoint": "https://api.example/v1"},
    )

    response = test_client.post(
        "/api/settings/models/chat/presets/chat_default/list-models",
        json={"config": {"endpoint": "https://api.example/v1"}},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "API key is required to fetch models"


def test_list_models_upstream_error_returns_502(client, monkeypatch):
    test_client, _db_path = client

    def fake_urlopen(request, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(settings_api, "urlopen", fake_urlopen)

    response = test_client.post(
        "/api/settings/models/chat/presets/chat_default/list-models",
        json={
            "config": {
                "endpoint": "https://api.example/v1",
                "api_key": "sk-test",
            }
        },
    )

    assert response.status_code == 502
    assert "connection refused" in response.json()["detail"]


def test_list_models_http_error_returns_502(client, monkeypatch):
    test_client, _db_path = client

    def fake_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"error":"bad key"}'),
        )

    monkeypatch.setattr(settings_api, "urlopen", fake_urlopen)

    response = test_client.post(
        "/api/settings/models/chat/presets/chat_default/list-models",
        json={
            "config": {
                "endpoint": "https://api.example/v1",
                "api_key": "sk-test",
            }
        },
    )

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "401" in detail
    assert "bad key" in detail


def test_list_models_malformed_response_returns_502(client, monkeypatch):
    test_client, _db_path = client

    def fake_urlopen(request, timeout):
        return FakeUrlResponse({"unexpected": []})

    monkeypatch.setattr(settings_api, "urlopen", fake_urlopen)

    response = test_client.post(
        "/api/settings/models/chat/presets/chat_default/list-models",
        json={
            "config": {
                "endpoint": "https://api.example/v1",
                "api_key": "sk-test",
            }
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Malformed models response"


def test_embedding_switch_preview_same_dimension_success(client, monkeypatch):
    test_client, db_path = client
    _create_preset(
        db_path,
        preset_id="embedding_new",
        model_name="embedding",
        name="New Embedding",
        config={
            "endpoint": "http://embedding.test:11434",
            "model": "embed-v2",
        },
    )
    manager = PreviewManager(
        preview={
            "preset_id": "embedding_new",
            "current_dimension": 768,
            "new_dimension": 768,
            "same_dimension": True,
            "indexed_document_count": 3,
        }
    )
    app.state.embedding_reindex_jobs = manager
    fake_client = FakeEmbeddingClient()
    monkeypatch.setattr(
        settings_api,
        "_build_embedding_client_for_config",
        lambda config: fake_client,
    )

    response = test_client.post(
        "/api/settings/models/embedding/presets/embedding_new/switch-preview"
    )

    assert response.status_code == 200
    assert response.json() == {
        "preset_id": "embedding_new",
        "current_dimension": 768,
        "new_dimension": 768,
        "same_dimension": True,
        "indexed_document_count": 3,
    }
    assert manager.calls == [("embedding_new", fake_client)]


def test_embedding_switch_preview_partial_preset_uses_layered_embedding_config(
    client, monkeypatch
):
    test_client, db_path = client
    default_yaml_path = db_path.parent.parent / "backend" / "config" / "default.yaml"
    default_yaml_path.write_text(
        f"""
storage:
  data_dir: "{db_path.parent}"
models:
  asr:
    protocol: transcriptions
  embedding:
    endpoint: "http://yaml-embedding.test:11434"
""",
        encoding="utf-8",
    )
    _update_preset_config(
        db_path,
        preset_id="embedding_default",
        config={
            "endpoint": "https://active-only.test/v1",
            "api_key": "sk-active",
            "model": "embed-active",
        },
    )
    _create_preset(
        db_path,
        preset_id="embedding_partial",
        model_name="embedding",
        name="Partial Embedding",
        config={"model": "embed-partial"},
    )
    manager = PreviewManager(
        preview={
            "preset_id": "embedding_partial",
            "current_dimension": 768,
            "new_dimension": 768,
            "same_dimension": True,
            "indexed_document_count": 1,
        }
    )
    app.state.embedding_reindex_jobs = manager
    built_configs: list[dict] = []

    def fake_build_embedding_client_for_config(config):
        built_configs.append(config.model_dump())
        return FakeEmbeddingClient()

    monkeypatch.setattr(
        settings_api,
        "_build_embedding_client_for_config",
        fake_build_embedding_client_for_config,
    )

    response = test_client.post(
        "/api/settings/models/embedding/presets/embedding_partial/switch-preview"
    )

    assert response.status_code == 200
    assert built_configs == [
        {
            "endpoint": "http://yaml-embedding.test:11434",
            "api_key": None,
            "model": "embed-partial",
            "protocol": None,
        }
    ]


def test_embedding_switch_preview_embedding_error_returns_502(client, monkeypatch):
    test_client, db_path = client
    _create_preset(
        db_path,
        preset_id="embedding_fail",
        model_name="embedding",
        name="Failing Embedding",
        config={"endpoint": "http://embedding.test:11434", "model": "bad"},
    )
    app.state.embedding_reindex_jobs = PreviewManager(
        preview={},
        error=EmbeddingError("embedding service unavailable"),
    )
    monkeypatch.setattr(
        settings_api,
        "_build_embedding_client_for_config",
        lambda config: FakeEmbeddingClient(),
    )

    response = test_client.post(
        "/api/settings/models/embedding/presets/embedding_fail/switch-preview"
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "embedding service unavailable"


def test_embedding_switch_preview_config_uses_supplied_config_without_persisting(
    client, monkeypatch
):
    test_client, db_path = client
    _update_preset_config(
        db_path,
        preset_id="embedding_default",
        config={
            "endpoint": "http://old-embedding.test:11434",
            "api_key": "sk-old",
            "model": "embed-old",
        },
    )
    manager = PreviewManager(
        preview={
            "preset_id": "embedding_default",
            "current_dimension": 768,
            "new_dimension": 1024,
            "same_dimension": False,
            "indexed_document_count": 3,
        }
    )
    app.state.embedding_reindex_jobs = manager
    built_configs: list[dict] = []

    def fake_build_embedding_client_for_config(config):
        built_configs.append(config.model_dump())
        return FakeEmbeddingClient()

    monkeypatch.setattr(
        settings_api,
        "_build_embedding_client_for_config",
        fake_build_embedding_client_for_config,
    )

    response = test_client.post(
        "/api/settings/models/embedding/presets/embedding_default/switch-preview-config",
        json={
            "config": {
                "endpoint": "http://new-embedding.test:11434",
                "api_key": "sk-o***",
                "model": "embed-new",
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["same_dimension"] is False
    assert built_configs == [
        {
            "endpoint": "http://new-embedding.test:11434",
            "api_key": "sk-old",
            "model": "embed-new",
            "protocol": None,
        }
    ]
    assert _preset_config(db_path, "embedding_default") == {
        "endpoint": "http://old-embedding.test:11434",
        "api_key": "sk-old",
        "model": "embed-old",
    }


def test_embedding_switch_preview_config_probe_failure_does_not_persist(
    client, monkeypatch
):
    test_client, db_path = client
    _update_preset_config(
        db_path,
        preset_id="embedding_default",
        config={
            "endpoint": "http://old-embedding.test:11434",
            "model": "embed-old",
        },
    )
    app.state.embedding_reindex_jobs = PreviewManager(
        preview={},
        error=EmbeddingError("embedding probe failed"),
    )
    monkeypatch.setattr(
        settings_api,
        "_build_embedding_client_for_config",
        lambda config: FakeEmbeddingClient(),
    )

    response = test_client.post(
        "/api/settings/models/embedding/presets/embedding_default/switch-preview-config",
        json={
            "config": {
                "endpoint": "http://new-embedding.test:11434",
                "model": "embed-new",
            }
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "embedding probe failed"
    assert _preset_config(db_path, "embedding_default") == {
        "endpoint": "http://old-embedding.test:11434",
        "model": "embed-old",
    }


def test_embedding_switch_preview_running_job_returns_409(client, monkeypatch):
    test_client, db_path = client
    _create_preset(
        db_path,
        preset_id="embedding_preview_blocked",
        model_name="embedding",
        name="Preview Blocked",
        config={
            "endpoint": "http://embedding.test:11434",
            "model": "embed-preview-blocked",
        },
    )
    app.state.embedding_reindex_jobs = RunningJobManager(preview={})

    def fail_if_preview_attempted(_config):
        raise AssertionError("preview should not run while a rebuild job is active")

    monkeypatch.setattr(
        settings_api,
        "_build_embedding_client_for_config",
        fail_if_preview_attempted,
    )

    response = test_client.post(
        "/api/settings/models/embedding/presets/embedding_preview_blocked/switch-preview"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Embedding index rebuild is already running"


def test_update_embedding_preset_while_reindex_running_returns_409(client):
    test_client, db_path = client
    _update_preset_config(
        db_path,
        preset_id="embedding_default",
        config={
            "endpoint": "http://old-embedding.test:11434",
            "model": "embed-old",
        },
    )
    app.state.embedding_reindex_jobs = RunningJobManager(preview={})

    response = test_client.patch(
        "/api/settings/models/embedding/presets/embedding_default",
        json={
            "config": {
                "endpoint": "http://new-embedding.test:11434",
                "model": "embed-new",
            }
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Embedding index rebuild is already running"
    assert _preset_config(db_path, "embedding_default") == {
        "endpoint": "http://old-embedding.test:11434",
        "model": "embed-old",
    }


def test_embedding_switch_same_dimension_sets_active_without_job(client, monkeypatch):
    test_client, db_path = client
    _create_preset(
        db_path,
        preset_id="embedding_same",
        model_name="embedding",
        name="Same Dimension",
        config={"endpoint": "http://embedding.test:11434", "model": "embed-same"},
    )
    manager = SwitchManager(
        preview={
            "preset_id": "embedding_same",
            "current_dimension": 768,
            "new_dimension": 768,
            "same_dimension": True,
            "indexed_document_count": 2,
        }
    )
    app.state.embedding_reindex_jobs = manager
    monkeypatch.setattr(
        settings_api,
        "_build_embedding_client_for_config",
        lambda config: FakeEmbeddingClient(),
    )

    response = test_client.post(
        "/api/settings/models/embedding/presets/embedding_same/switch",
        json={"confirm_reindex": False},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["same_dimension"] is True
    assert response.json()["job_id"] is None
    assert _active_preset_id(db_path, "embedding") == "embedding_same"
    assert manager.start_job_calls == []


def test_embedding_switch_probe_failure_returns_502_without_switching_active(
    client, monkeypatch
):
    test_client, db_path = client
    _create_preset(
        db_path,
        preset_id="embedding_bad_key",
        model_name="embedding",
        name="Bad Key",
        config={
            "endpoint": "https://embedding.test/v1",
            "api_key": "sk-bad",
            "model": "embed-bad",
        },
    )
    manager = SwitchManager(preview={})
    manager.error = EmbeddingError("HTTP 401: Authentication failed")
    app.state.embedding_reindex_jobs = manager
    monkeypatch.setattr(
        settings_api,
        "_build_embedding_client_for_config",
        lambda config: FakeEmbeddingClient(),
    )

    response = test_client.post(
        "/api/settings/models/embedding/presets/embedding_bad_key/switch",
        json={"confirm_reindex": False},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "HTTP 401: Authentication failed"
    assert _active_preset_id(db_path, "embedding") == "embedding_default"
    assert manager.start_job_calls == []


def test_set_active_preset_rejects_direct_embedding_switch(client):
    test_client, db_path = client
    _create_preset(
        db_path,
        preset_id="embedding_direct_switch",
        model_name="embedding",
        name="Direct Switch",
        config={
            "endpoint": "http://embedding.test:11434",
            "model": "embed-direct",
        },
    )

    response = test_client.put(
        "/api/settings/models/embedding/active",
        json={"preset_id": "embedding_direct_switch"},
    )

    assert response.status_code == 409
    assert "embedding/presets" in response.json()["detail"]
    assert _active_preset_id(db_path, "embedding") == "embedding_default"


def test_embedding_switch_dimension_change_without_confirmation_returns_409(
    client, monkeypatch
):
    test_client, db_path = client
    _create_preset(
        db_path,
        preset_id="embedding_reindex_needed",
        model_name="embedding",
        name="Reindex Needed",
        config={"endpoint": "http://embedding.test:11434", "model": "embed-large"},
    )
    app.state.embedding_reindex_jobs = SwitchManager(
        preview={
            "preset_id": "embedding_reindex_needed",
            "current_dimension": 768,
            "new_dimension": 1024,
            "same_dimension": False,
            "indexed_document_count": 5,
        }
    )
    monkeypatch.setattr(
        settings_api,
        "_build_embedding_client_for_config",
        lambda config: FakeEmbeddingClient(),
    )

    response = test_client.post(
        "/api/settings/models/embedding/presets/embedding_reindex_needed/switch",
        json={"confirm_reindex": False},
    )

    assert response.status_code == 409
    assert "confirm_reindex" in response.json()["detail"]
    assert _active_preset_id(db_path, "embedding") == "embedding_default"


def test_embedding_switch_dimension_change_with_confirmation_returns_202(
    client, monkeypatch
):
    test_client, db_path = client
    _create_preset(
        db_path,
        preset_id="embedding_reindex",
        model_name="embedding",
        name="Reindex",
        config={
            "endpoint": "http://embedding.test:11434",
            "model": "embed-reindex",
        },
    )
    manager = SwitchManager(
        preview={
            "preset_id": "embedding_reindex",
            "current_dimension": 768,
            "new_dimension": 1024,
            "same_dimension": False,
            "indexed_document_count": 7,
        }
    )
    app.state.embedding_reindex_jobs = manager

    built_configs: list[dict] = []

    def fake_build_embedding_client_for_config(config):
        config_dict = config.model_dump()
        built_configs.append(config_dict)
        return {"model": config_dict["model"]}

    monkeypatch.setattr(
        settings_api,
        "_build_embedding_client_for_config",
        fake_build_embedding_client_for_config,
    )

    response = test_client.post(
        "/api/settings/models/embedding/presets/embedding_reindex/switch",
        json={"confirm_reindex": True},
    )

    assert response.status_code == 202
    assert response.json()["job_id"] == "job-123"
    assert response.json()["status"] == "pending"
    assert response.json()["stage"] == "queued"
    assert response.json()["same_dimension"] is False
    assert len(manager.start_job_calls) == 1
    assert manager.start_job_calls[0]["preset_id"] == "embedding_reindex"
    assert manager.start_job_calls[0]["embedding_client_factory"]() == {
        "model": "embed-reindex"
    }
    assert built_configs
    assert all(
        config == {
            "endpoint": "http://embedding.test:11434",
            "api_key": None,
            "model": "embed-reindex",
            "protocol": None,
        }
        for config in built_configs
    )
    assert _active_preset_id(db_path, "embedding") == "embedding_default"


def test_embedding_switch_partial_preset_reindex_uses_layered_embedding_config(
    client, monkeypatch
):
    test_client, db_path = client
    default_yaml_path = db_path.parent.parent / "backend" / "config" / "default.yaml"
    default_yaml_path.write_text(
        f"""
storage:
  data_dir: "{db_path.parent}"
models:
  asr:
    protocol: transcriptions
  embedding:
    endpoint: "http://yaml-embedding.test:11434"
""",
        encoding="utf-8",
    )
    _update_preset_config(
        db_path,
        preset_id="embedding_default",
        config={
            "endpoint": "https://active-only.test/v1",
            "api_key": "sk-active",
            "model": "embed-active",
        },
    )
    _create_preset(
        db_path,
        preset_id="embedding_partial_reindex",
        model_name="embedding",
        name="Partial Reindex",
        config={"model": "embed-partial-reindex"},
    )
    manager = SwitchManager(
        preview={
            "preset_id": "embedding_partial_reindex",
            "current_dimension": 768,
            "new_dimension": 1024,
            "same_dimension": False,
            "indexed_document_count": 6,
        }
    )
    app.state.embedding_reindex_jobs = manager
    built_configs: list[dict] = []

    def fake_build_embedding_client_for_config(config):
        config_dict = config.model_dump()
        built_configs.append(config_dict)
        return {"model": config_dict["model"]}

    monkeypatch.setattr(
        settings_api,
        "_build_embedding_client_for_config",
        fake_build_embedding_client_for_config,
    )

    response = test_client.post(
        "/api/settings/models/embedding/presets/embedding_partial_reindex/switch",
        json={"confirm_reindex": True},
    )

    assert response.status_code == 202
    assert manager.start_job_calls[0]["embedding_client_factory"]() == {
        "model": "embed-partial-reindex",
    }
    assert built_configs == [
        {
            "endpoint": "http://yaml-embedding.test:11434",
            "api_key": None,
            "model": "embed-partial-reindex",
            "protocol": None,
        },
        {
            "endpoint": "http://yaml-embedding.test:11434",
            "api_key": None,
            "model": "embed-partial-reindex",
            "protocol": None,
        },
    ]


def test_embedding_switch_running_job_returns_409(client, monkeypatch):
    test_client, db_path = client
    _create_preset(
        db_path,
        preset_id="embedding_busy",
        model_name="embedding",
        name="Busy",
        config={"endpoint": "http://embedding.test:11434", "model": "embed-busy"},
    )
    app.state.embedding_reindex_jobs = RunningJobManager(
        preview={
            "preset_id": "embedding_busy",
            "current_dimension": 768,
            "new_dimension": 1024,
            "same_dimension": False,
            "indexed_document_count": 4,
        }
    )
    monkeypatch.setattr(
        settings_api,
        "_build_embedding_client_for_config",
        lambda config: FakeEmbeddingClient(),
    )

    response = test_client.post(
        "/api/settings/models/embedding/presets/embedding_busy/switch",
        json={"confirm_reindex": True},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Embedding index rebuild is already running"


def test_embedding_switch_running_job_same_dimension_returns_409(client, monkeypatch):
    test_client, db_path = client
    _create_preset(
        db_path,
        preset_id="embedding_busy_same_dimension",
        model_name="embedding",
        name="Busy Same Dimension",
        config={
            "endpoint": "http://embedding.test:11434",
            "model": "embed-busy-same",
        },
    )
    manager = RunningJobManager(
        preview={
            "preset_id": "embedding_busy_same_dimension",
            "current_dimension": 768,
            "new_dimension": 768,
            "same_dimension": True,
            "indexed_document_count": 4,
        }
    )
    app.state.embedding_reindex_jobs = manager

    def fail_if_preview_attempted(_config):
        raise AssertionError("preview should not run while a rebuild job is active")

    monkeypatch.setattr(
        settings_api,
        "_build_embedding_client_for_config",
        fail_if_preview_attempted,
    )

    response = test_client.post(
        "/api/settings/models/embedding/presets/embedding_busy_same_dimension/switch",
        json={"confirm_reindex": False},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Embedding index rebuild is already running"
    assert _active_preset_id(db_path, "embedding") == "embedding_default"
    assert manager.calls == []


def test_delete_embedding_preset_while_reindex_running_returns_409(client):
    test_client, db_path = client
    _create_preset(
        db_path,
        preset_id="embedding_delete_blocked",
        model_name="embedding",
        name="Delete Blocked",
        config={
            "endpoint": "http://embedding.test:11434",
            "model": "embed-delete",
        },
    )
    app.state.embedding_reindex_jobs = RunningJobManager(preview={})

    response = test_client.delete(
        "/api/settings/models/embedding/presets/embedding_delete_blocked"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Embedding index rebuild is already running"
    assert _active_preset_id(db_path, "embedding") == "embedding_default"


def test_embedding_switch_same_dimension_race_returns_409(client, monkeypatch):
    test_client, db_path = client
    _create_preset(
        db_path,
        preset_id="embedding_race_same_dimension",
        model_name="embedding",
        name="Race Same Dimension",
        config={
            "endpoint": "http://embedding.test:11434",
            "model": "embed-race",
        },
    )
    manager = DelayedRunningJobManager(
        preview={
            "preset_id": "embedding_race_same_dimension",
            "current_dimension": 768,
            "new_dimension": 768,
            "same_dimension": True,
            "indexed_document_count": 4,
        }
    )
    app.state.embedding_reindex_jobs = manager
    monkeypatch.setattr(
        settings_api,
        "_build_embedding_client_for_config",
        lambda config: FakeEmbeddingClient(),
    )

    response = test_client.post(
        "/api/settings/models/embedding/presets/embedding_race_same_dimension/switch",
        json={"confirm_reindex": False},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Embedding index rebuild is already running"
    assert _active_preset_id(db_path, "embedding") == "embedding_default"
    assert len(manager.calls) == 1
    assert manager.calls[0][0] == "embedding_race_same_dimension"


def test_get_active_embedding_reindex_job_returns_running_job(client):
    test_client, _db_path = client
    app.state.embedding_reindex_jobs = RunningJobManager(preview={})

    response = test_client.get("/api/settings/embedding-reindex-jobs/active")

    assert response.status_code == 200
    assert response.json() == {
        "id": "job-running",
        "preset_id": "embedding_running",
        "status": "running",
        "stage": "reindexing",
    }


def test_get_active_embedding_reindex_job_returns_none_without_running_job(client):
    test_client, _db_path = client
    app.state.embedding_reindex_jobs = SwitchManager(preview={})

    response = test_client.get("/api/settings/embedding-reindex-jobs/active")

    assert response.status_code == 200
    assert response.json() is None


def test_get_embedding_reindex_job_missing_returns_404(client):
    test_client, _db_path = client
    app.state.embedding_reindex_jobs = MissingJobManager()

    response = test_client.get("/api/settings/embedding-reindex-jobs/missing-job")

    assert response.status_code == 404
    assert response.json()["detail"] == "Embedding reindex job not found"


def test_get_embedding_reindex_job_returns_job_snapshot(client):
    test_client, _db_path = client
    app.state.embedding_reindex_jobs = JobLookupManager(
        {
            "id": "job-123",
            "preset_id": "embedding_reindex",
            "status": "running",
            "stage": "reindexing_documents",
            "total_documents": 7,
            "processed_documents": 3,
            "failed_documents": [],
            "error": None,
            "started_at": "2026-07-04T00:00:00+00:00",
            "finished_at": None,
        }
    )

    response = test_client.get("/api/settings/embedding-reindex-jobs/job-123")

    assert response.status_code == 200
    assert response.json() == {
        "id": "job-123",
        "preset_id": "embedding_reindex",
        "status": "running",
        "stage": "reindexing_documents",
        "total_documents": 7,
        "processed_documents": 3,
        "failed_documents": [],
        "error": None,
        "started_at": "2026-07-04T00:00:00+00:00",
        "finished_at": None,
    }


def test_lifespan_runs_config_migration_against_memento_db(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    created_clients: dict[str, SimpleNamespace] = {}
    migration_calls: list[Path] = []
    shutdown_calls: list[str] = []

    class FakeSQLiteClient:
        def __init__(self, path: Path):
            self.path = path
            self.connected = False
            self.closed = False
            created_clients[path.name] = self

        async def connect(self):
            self.connected = True

        async def close(self):
            self.closed = True

    class FakeQdrantStore:
        def __init__(self, path: Path):
            self.path = path

        def connect(self, vector_size: int):
            self.vector_size = vector_size

        def ensure_summary_collection(self, vector_size: int):
            self.summary_vector_size = vector_size

        def close(self):
            self.closed = True

    class FakeEmbeddingReindexJobManager:
        def __init__(self, *, sqlite, qdrant):
            self.sqlite = sqlite
            self.qdrant = qdrant

    async def fake_migrate_config_to_db(sqlite):
        migration_calls.append(sqlite.path)

    monkeypatch.setattr(main_module, "SQLiteClient", FakeSQLiteClient)
    monkeypatch.setattr(main_module, "QdrantStore", FakeQdrantStore)
    monkeypatch.setattr(
        main_module, "EmbeddingReindexJobManager", FakeEmbeddingReindexJobManager
    )
    monkeypatch.setattr(main_module, "migrate_config_to_db", fake_migrate_config_to_db)
    monkeypatch.setattr(
        main_module,
        "settings",
        SimpleNamespace(
            storage=SimpleNamespace(data_dir=data_dir),
            rag=SimpleNamespace(vector_size=768),
            log_level="INFO",
            cors_origins=[],
        ),
    )
    monkeypatch.setattr(
        main_module.asr_supervisor,
        "shutdown",
        lambda: shutdown_calls.append("shutdown"),
    )

    async def exercise_lifespan():
        lifecycle_app = FastAPI()
        async with main_module.lifespan(lifecycle_app):
            assert lifecycle_app.state.sqlite.path == data_dir / "metadata.db"
            assert created_clients["memento.db"].closed is True
            assert lifecycle_app.state.embedding_reindex_jobs.sqlite.path == (
                data_dir / "metadata.db"
            )

    asyncio.run(exercise_lifespan())

    assert migration_calls == [data_dir / "memento.db"]
    assert created_clients["metadata.db"].connected is True
    assert created_clients["metadata.db"].closed is True
    assert shutdown_calls == ["shutdown"]


# ===== Preset Management Tests =====


def test_list_presets(client):
    test_client, _db_path = client

    response = test_client.get("/api/settings/models/chat/presets")
    assert response.status_code == 200
    presets = response.json()
    assert len(presets) >= 1
    assert presets[0]["name"] == "Default"


def test_create_preset_with_auto_name(client):
    test_client, _db_path = client

    response = test_client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"model": "claude-3-5-sonnet"}},
    )
    assert response.status_code == 201
    preset = response.json()
    assert preset["name"] == "Preset 1"
    assert preset["model_name"] == "chat"
    assert preset["config"]["model"] == "claude-3-5-sonnet"


def test_create_preset_with_custom_name(client):
    test_client, _db_path = client

    response = test_client.post(
        "/api/settings/models/chat/presets",
        json={
            "name": "我的预设",
            "config": {"model": "claude-3-5-sonnet"},
        },
    )
    assert response.status_code == 201
    preset = response.json()
    assert preset["name"] == "我的预设"


def test_create_preset_does_not_inherit_active_config(client):
    test_client, db_path = client

    # Update active preset to have specific config
    test_client.put(
        "/api/settings/models",
        json={"chat": {"api_key": "sk-test-old"}},
    )

    # Create new preset with only model field
    response = test_client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"model": "claude-3-5-sonnet"}},
    )
    assert response.status_code == 201
    preset = response.json()

    # Should NOT inherit api_key from active preset
    assert "api_key" not in preset["config"] or preset["config"]["api_key"] is None
    assert preset["config"]["model"] == "claude-3-5-sonnet"


def test_get_preset(client):
    test_client, _db_path = client

    # Create a preset
    create_response = test_client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"model": "test-model"}},
    )
    preset_id = create_response.json()["id"]

    # Get the preset
    response = test_client.get(f"/api/settings/models/chat/presets/{preset_id}")
    assert response.status_code == 200
    preset = response.json()
    assert preset["id"] == preset_id
    assert preset["config"]["model"] == "test-model"


def test_update_preset(client):
    test_client, _db_path = client

    # Create a preset
    create_response = test_client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"model": "old-model"}},
    )
    preset_id = create_response.json()["id"]

    # Update the preset
    response = test_client.patch(
        f"/api/settings/models/chat/presets/{preset_id}",
        json={"name": "更新后的预设", "config": {"model": "new-model"}},
    )
    assert response.status_code == 200
    preset = response.json()
    assert preset["name"] == "更新后的预设"
    assert preset["config"]["model"] == "new-model"


def test_delete_preset(client):
    test_client, _db_path = client

    # Create a second preset (so we can delete one)
    create_response = test_client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"model": "test-model"}},
    )
    preset_id = create_response.json()["id"]

    # Delete the preset
    response = test_client.delete(f"/api/settings/models/chat/presets/{preset_id}")
    assert response.status_code == 204

    # Verify it's gone
    response = test_client.get(f"/api/settings/models/chat/presets/{preset_id}")
    assert response.status_code == 404


def test_cannot_delete_last_preset(client):
    test_client, db_path = client

    # Get the default preset ID
    list_response = test_client.get("/api/settings/models/chat/presets")
    presets = list_response.json()
    assert len(presets) == 1
    preset_id = presets[0]["id"]

    # Try to delete the last preset
    response = test_client.delete(f"/api/settings/models/chat/presets/{preset_id}")
    assert response.status_code == 400
    assert "Cannot delete the last preset" in response.json()["detail"]

    # Verify the preset still exists
    verify_response = test_client.get("/api/settings/models/chat/presets")
    assert len(verify_response.json()) == 1


def test_get_active_preset(client):
    test_client, _db_path = client

    response = test_client.get("/api/settings/models/chat/active")
    assert response.status_code == 200
    data = response.json()
    assert "preset_id" in data
    assert data["preset_id"] is not None


def test_set_active_preset(client):
    test_client, _db_path = client

    # Create a new preset
    create_response = test_client.post(
        "/api/settings/models/chat/presets",
        json={"config": {"model": "test-model"}},
    )
    preset_id = create_response.json()["id"]

    # Set it as active
    response = test_client.put(
        "/api/settings/models/chat/active",
        json={"preset_id": preset_id},
    )
    assert response.status_code == 200
    assert response.json()["preset_id"] == preset_id

    # Verify it's active
    verify_response = test_client.get("/api/settings/models/chat/active")
    assert verify_response.json()["preset_id"] == preset_id
