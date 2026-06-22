"""Tests for ASR deployment API endpoints."""

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api import asr as asr_api
from main import app


def test_deploy_status_reports_missing_venv(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(asr_api, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(asr_api, "VENV_DIR", tmp_path / ".venv")
    monkeypatch.setattr(asr_api.Path, "home", lambda: tmp_path)

    response = TestClient(app).get("/api/asr/deploy/status")

    assert response.status_code == 200
    assert response.json() == {
        "venv_exists": False,
        "models_installed": False,
    }


def test_deploy_status_reports_modelscope_cached_sensevoice(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(asr_api, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(asr_api, "VENV_DIR", tmp_path / ".venv")
    monkeypatch.setattr(asr_api.Path, "home", lambda: tmp_path)
    (tmp_path / ".venv").mkdir()
    (
        tmp_path
        / ".cache"
        / "modelscope"
        / "hub"
        / "models"
        / "iic"
        / "SenseVoiceSmall"
        / "model.pt"
    ).parent.mkdir(parents=True)
    (
        tmp_path
        / ".cache"
        / "modelscope"
        / "hub"
        / "models"
        / "iic"
        / "SenseVoiceSmall"
        / "model.pt"
    ).touch()

    response = TestClient(app).get("/api/asr/deploy/status")

    assert response.status_code == 200
    assert response.json() == {
        "venv_exists": True,
        "models_installed": True,
    }


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
    (tmp_path / "model_cache").mkdir()
    monkeypatch.setattr(asr_api, "SERVICE_DIR", tmp_path)
    monkeypatch.setattr(asr_api, "VENV_DIR", venv)

    response = TestClient(app).get("/api/asr/deploy/status")

    assert response.status_code == 200
    assert response.json() == {
        "venv_exists": True,
        "models_installed": True,
    }
