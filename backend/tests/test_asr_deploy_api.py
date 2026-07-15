"""Tests for ASR deployment API endpoints."""

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api import asr as asr_api
from main import app


def test_deploy_status_reports_missing_venv(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(asr_api, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(asr_api, "VENV_DIR", tmp_path / ".venv")

    response = TestClient(app).get("/api/asr/deploy/status")

    assert response.status_code == 200
    assert response.json() == {
        "venv_exists": False,
        "models_installed": False,
    }


def test_deploy_status_reports_modelscope_cached_sensevoice(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(asr_api, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(asr_api, "VENV_DIR", tmp_path / ".venv")
    (tmp_path / ".venv").mkdir()
    sensevoice_cache = tmp_path / "models" / "sensevoice" / "iic" / "SenseVoiceSmall"
    sensevoice_cache.mkdir(parents=True)
    (sensevoice_cache / "model.pt").touch()

    response = TestClient(app).get("/api/asr/deploy/status")

    assert response.status_code == 200
    assert response.json() == {
        "venv_exists": True,
        "models_installed": True,
    }


def test_deploy_status_reports_current_modelscope_snapshot_layout(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(asr_api, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(asr_api, "VENV_DIR", tmp_path / ".venv")
    (tmp_path / ".venv").mkdir()
    cache = (
        tmp_path
        / "models"
        / "sensevoice"
        / "models"
        / "iic--SenseVoiceSmall"
        / "snapshots"
        / "master"
    )
    cache.mkdir(parents=True)
    (cache / "model.pt").touch()

    response = TestClient(app).get("/api/asr/deploy/status")

    assert response.status_code == 200
    assert response.json()["models_installed"] is True


def test_deploy_starts_background_task(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(asr_api, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(asr_api, "VENV_DIR", tmp_path / ".venv")
    submitted = []

    class FakeExecutor:
        def submit(self, fn):
            submitted.append(fn)
            return SimpleNamespace(done=lambda: False)

    monkeypatch.setattr(asr_api, "_executor", FakeExecutor())

    response = TestClient(app).post("/api/asr/deploy")

    assert response.status_code == 202
    assert submitted
    assert response.json()["stage"] == "queued"


def test_progress_reports_current_state(monkeypatch):
    monkeypatch.setattr(
        asr_api,
        "_progress",
        asr_api.DeployProgress(stage="models", detail="Downloading", percent=50),
    )

    response = TestClient(app).get("/api/asr/deploy/progress")

    assert response.status_code == 200
    assert response.json() == {
        "stage": "models",
        "detail": "Downloading",
        "percent": 50,
        "done": False,
        "error": None,
    }


def test_status_reports_installed_after_deploy(monkeypatch, tmp_path: Path):
    venv = tmp_path / ".venv"
    (venv / "bin").mkdir(parents=True)
    sensevoice_cache = tmp_path / "models" / "sensevoice" / "iic" / "SenseVoiceSmall"
    sensevoice_cache.mkdir(parents=True)
    (sensevoice_cache / "model.pt").touch()
    monkeypatch.setattr(asr_api, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(asr_api, "VENV_DIR", venv)

    response = TestClient(app).get("/api/asr/deploy/status")

    assert response.status_code == 200
    assert response.json() == {
        "venv_exists": True,
        "models_installed": True,
    }
