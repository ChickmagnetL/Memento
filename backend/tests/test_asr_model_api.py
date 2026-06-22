"""Tests for local ASR model management API endpoints."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app
from schemas.asr import (
    AsrDiskInfo,
    AsrEnvironmentStatus,
    AsrManagerProgress,
    AsrManagerStatus,
    AsrModelStatus,
)


def _make_mock_manager(**overrides):
    """Build a mock AsrModelManager with sensible defaults for all public methods."""
    mgr = MagicMock()

    # Default get_status
    mgr.get_status.return_value = AsrManagerStatus(
        environment=AsrEnvironmentStatus(
            venv_exists=True,
            service_python_exists=True,
            service_dir_exists=True,
            platform="darwin",
        ),
        models={
            "sensevoice-small": AsrModelStatus(
                slug="sensevoice-small",
                family="sensevoice",
                label="SenseVoice Small",
                model_id="iic/SenseVoiceSmall",
                spec=None,
                size="0.9GB",
                runtime="sensevoice",
                installed=True,
                installing=False,
                selected=True,
                estimated_size="0.9GB",
                cache_path="/home/user/.cache/modelscope/hub/models/iic/SenseVoiceSmall",
            ),
            "moonshine-tiny-en": AsrModelStatus(
                slug="moonshine-tiny-en",
                family="moonshine",
                label="Moonshine Tiny EN",
                model_id="moonshine_voice/tiny-en",
                spec="tiny-en",
                size="71MB",
                runtime="moonshine",
                installed=False,
                installing=False,
                selected=False,
                estimated_size="71MB",
            ),
        },
        current="sensevoice-small",
        disks={
            "service_disk": AsrDiskInfo(total=1000000000, free=500000000, used=500000000),
        },
        progress=AsrManagerProgress(stage="idle"),
    )

    # Default install_model
    mgr.install_model.return_value = AsrManagerProgress(
        stage="queued",
        model_slug="moonshine-tiny-en",
        detail="Install moonshine-tiny-en queued",
        percent=0,
    )

    # Default select_model (no-op success)
    mgr.select_model.return_value = None

    # Default uninstall_model
    mgr.uninstall_model.return_value = AsrManagerProgress(
        stage="queued",
        model_slug="sensevoice-small",
        detail="Uninstall sensevoice-small queued",
        percent=0,
    )

    # Default uninstall_all_local_asr
    mgr.uninstall_all_local_asr.return_value = AsrManagerProgress(
        stage="queued",
        detail="Uninstall all queued",
        percent=0,
    )

    for k, v in overrides.items():
        setattr(mgr, k, v)

    return mgr


# ---------------------------------------------------------------------------
# GET /api/asr/local/status
# ---------------------------------------------------------------------------


def test_status_returns_full_snapshot(monkeypatch):
    """Status endpoint returns environment, models, current, disks, progress."""
    from api import asr as asr_api

    mgr = _make_mock_manager()
    monkeypatch.setattr(asr_api, "_get_manager", lambda: mgr)

    response = TestClient(app).get("/api/asr/local/status")

    assert response.status_code == 200
    data = response.json()
    # Top-level keys
    assert "environment" in data
    assert "models" in data
    assert "current" in data
    assert "disks" in data
    assert "progress" in data
    # environment sub-keys
    assert data["environment"]["venv_exists"] is True
    assert data["environment"]["platform"] == "darwin"
    # models
    assert "sensevoice-small" in data["models"]
    assert data["models"]["sensevoice-small"]["installed"] is True
    assert data["models"]["sensevoice-small"]["selected"] is True
    # current
    assert data["current"] == "sensevoice-small"
    # disks
    assert "service_disk" in data["disks"]
    # progress
    assert data["progress"]["stage"] == "idle"

    mgr.get_status.assert_called_once()


# ---------------------------------------------------------------------------
# POST /api/asr/local/models/{slug}/install
# ---------------------------------------------------------------------------


def test_install_unknown_slug_returns_404(monkeypatch):
    """Installing an unknown model slug returns 404."""
    from api import asr as asr_api

    mgr = _make_mock_manager()
    mgr.install_model.side_effect = KeyError("unknown-slug")
    monkeypatch.setattr(asr_api, "_get_manager", lambda: mgr)

    response = TestClient(app).post("/api/asr/local/models/nonexistent-model/install")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "nonexistent-model" in detail.lower() or "not found" in detail.lower()


def test_install_valid_slug_returns_202_with_progress(monkeypatch):
    """Installing a valid model slug returns 202 with progress payload."""
    from api import asr as asr_api

    mgr = _make_mock_manager()
    mgr.install_model.return_value = AsrManagerProgress(
        stage="queued",
        model_slug="moonshine-tiny-en",
        detail="Install moonshine-tiny-en queued",
        percent=0,
    )
    monkeypatch.setattr(asr_api, "_get_manager", lambda: mgr)

    response = TestClient(app).post("/api/asr/local/models/moonshine-tiny-en/install")

    assert response.status_code == 202
    data = response.json()
    assert data["stage"] == "queued"
    assert data["model_slug"] == "moonshine-tiny-en"
    assert data["percent"] == 0

    mgr.install_model.assert_called_once_with("moonshine-tiny-en")


def test_install_value_error_returns_400(monkeypatch):
    """Installing when manager raises ValueError returns 400."""
    from api import asr as asr_api

    mgr = _make_mock_manager()
    mgr.install_model.side_effect = ValueError("Model not supported")
    monkeypatch.setattr(asr_api, "_get_manager", lambda: mgr)

    response = TestClient(app).post("/api/asr/local/models/sensevoice-small/install")

    assert response.status_code == 400
    assert "not supported" in response.json()["detail"]


# ---------------------------------------------------------------------------
# POST /api/asr/local/models/{slug}/select
# ---------------------------------------------------------------------------


def test_select_uninstalled_model_returns_400(monkeypatch):
    """Selecting a model that is not installed returns 400."""
    from api import asr as asr_api

    mgr = _make_mock_manager()
    mgr.select_model.side_effect = ValueError("Model 'moonshine-tiny-en' is not installed")
    monkeypatch.setattr(asr_api, "_get_manager", lambda: mgr)

    response = TestClient(app).post("/api/asr/local/models/moonshine-tiny-en/select")

    assert response.status_code == 400
    assert "not installed" in response.json()["detail"]


def test_select_installed_model_returns_current(monkeypatch):
    """Selecting an installed model returns the updated current slug."""
    from api import asr as asr_api

    mgr = _make_mock_manager()
    monkeypatch.setattr(asr_api, "_get_manager", lambda: mgr)

    response = TestClient(app).post("/api/asr/local/models/sensevoice-small/select")

    assert response.status_code == 200
    data = response.json()
    assert data["current"] == "sensevoice-small"

    mgr.select_model.assert_called_once_with("sensevoice-small")


def test_select_model_does_not_touch_settings_asr_config(monkeypatch):
    """Select endpoint does NOT modify Settings ASR config.

    The manager's select_model only writes current_model_slug to the state
    file; the API layer must not call any Settings mutation either.
    """
    from api import asr as asr_api

    mgr = _make_mock_manager()
    monkeypatch.setattr(asr_api, "_get_manager", lambda: mgr)

    # Patch get_settings so we can verify it is NOT called for config mutation
    with patch("api.asr.get_settings") as mock_get_settings:
        response = TestClient(app).post("/api/asr/local/models/sensevoice-small/select")
        assert response.status_code == 200
        # get_settings should not have been called (or if called, only for
        # manager init which is bypassed via monkeypatch)
        mock_get_settings.assert_not_called()


def test_select_unknown_slug_returns_404(monkeypatch):
    """Selecting an unknown model slug returns 404."""
    from api import asr as asr_api

    mgr = _make_mock_manager()
    mgr.select_model.side_effect = KeyError("unknown-model")
    monkeypatch.setattr(asr_api, "_get_manager", lambda: mgr)

    response = TestClient(app).post("/api/asr/local/models/unknown-model/select")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/asr/local/models/{slug}
# ---------------------------------------------------------------------------


def test_delete_model_returns_202_with_progress(monkeypatch):
    """Uninstalling a model returns 202 with progress."""
    from api import asr as asr_api

    mgr = _make_mock_manager()
    mgr.uninstall_model.return_value = AsrManagerProgress(
        stage="queued",
        model_slug="sensevoice-small",
        detail="Uninstall sensevoice-small queued",
        percent=0,
    )
    monkeypatch.setattr(asr_api, "_get_manager", lambda: mgr)

    response = TestClient(app).delete("/api/asr/local/models/sensevoice-small")

    assert response.status_code == 202
    data = response.json()
    assert data["stage"] == "queued"
    assert data["model_slug"] == "sensevoice-small"

    mgr.uninstall_model.assert_called_once_with("sensevoice-small")


def test_delete_unknown_slug_returns_404(monkeypatch):
    """Uninstalling an unknown model slug returns 404."""
    from api import asr as asr_api

    mgr = _make_mock_manager()
    mgr.uninstall_model.side_effect = KeyError("nonexistent")
    monkeypatch.setattr(asr_api, "_get_manager", lambda: mgr)

    response = TestClient(app).delete("/api/asr/local/models/nonexistent")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/asr/local/uninstall-all
# ---------------------------------------------------------------------------


def test_uninstall_all_returns_202_with_progress(monkeypatch):
    """Uninstall-all endpoint returns 202 with progress."""
    from api import asr as asr_api

    mgr = _make_mock_manager()
    mgr.uninstall_all_local_asr.return_value = AsrManagerProgress(
        stage="queued",
        detail="Uninstall all queued",
        percent=0,
    )
    monkeypatch.setattr(asr_api, "_get_manager", lambda: mgr)

    response = TestClient(app).post("/api/asr/local/uninstall-all")

    assert response.status_code == 202
    data = response.json()
    assert data["stage"] == "queued"
    assert data["detail"] == "Uninstall all queued"

    mgr.uninstall_all_local_asr.assert_called_once()


# ---------------------------------------------------------------------------
# GET /api/asr/local/progress
# ---------------------------------------------------------------------------


def test_progress_returns_current_progress(monkeypatch):
    """Progress endpoint returns the current/latest progress snapshot."""
    from api import asr as asr_api

    mgr = _make_mock_manager()
    # Override get_status to include a non-idle progress
    mgr.get_status.return_value = AsrManagerStatus(
        environment=AsrEnvironmentStatus(
            venv_exists=True,
            service_python_exists=True,
            service_dir_exists=True,
            platform="darwin",
        ),
        models={},
        current=None,
        disks={},
        progress=AsrManagerProgress(
            stage="downloading",
            model_slug="moonshine-tiny-en",
            detail="Downloading model files...",
            percent=42,
        ),
    )
    monkeypatch.setattr(asr_api, "_get_manager", lambda: mgr)

    response = TestClient(app).get("/api/asr/local/progress")

    assert response.status_code == 200
    data = response.json()
    assert data["stage"] == "downloading"
    assert data["model_slug"] == "moonshine-tiny-en"
    assert data["detail"] == "Downloading model files..."
    assert data["percent"] == 42


def test_progress_error_detail_preserved(monkeypatch):
    """Error detail in progress is passed through to the frontend unchanged."""
    from api import asr as asr_api

    error_msg = "CUDA out of memory: tried to allocate 2.00 GiB on device cuda:0"
    mgr = _make_mock_manager()
    mgr.get_status.return_value = AsrManagerStatus(
        environment=AsrEnvironmentStatus(
            venv_exists=True,
            service_python_exists=True,
            service_dir_exists=True,
            platform="linux",
        ),
        models={},
        current=None,
        disks={},
        progress=AsrManagerProgress(
            stage="failed",
            model_slug="sensevoice-small",
            detail="Install failed: CUDA out of memory",
            percent=None,
            error=error_msg,
        ),
    )
    monkeypatch.setattr(asr_api, "_get_manager", lambda: mgr)

    response = TestClient(app).get("/api/asr/local/progress")

    assert response.status_code == 200
    data = response.json()
    assert data["error"] == error_msg
    assert data["stage"] == "failed"


def test_progress_idle_state(monkeypatch):
    """Progress endpoint returns idle when no job is running."""
    from api import asr as asr_api

    mgr = _make_mock_manager()
    # Default get_status already has idle progress
    monkeypatch.setattr(asr_api, "_get_manager", lambda: mgr)

    response = TestClient(app).get("/api/asr/local/progress")

    assert response.status_code == 200
    data = response.json()
    assert data["stage"] == "idle"
    assert data["error"] is None
