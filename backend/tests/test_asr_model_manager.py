"""Tests for ASR model manager — environment, model status, cache detection, disk,
   plus Task 3 orchestration: install, select, uninstall, progress."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from core.asr_model_manager import AsrModelManager
from schemas.asr import AsrManagerStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_venv(path: Path) -> None:
    """Create a minimal fake venv structure."""
    path.mkdir(parents=True, exist_ok=True)
    bin_dir = path / ("Scripts" if os.name == "nt" else "bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "python").touch()
    if os.name == "nt":
        (bin_dir / "python.exe").touch()


def _make_state(data_dir: Path, content: dict) -> Path:
    """Write a state file and return its path."""
    path = data_dir / "local_asr_models.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content))
    return path


def _make_sensevoice_cache(service_dir: Path) -> Path:
    """Create a fake SenseVoice cache at the relocated services/asr/models/ path."""
    cache_dir = service_dir / "models" / "sensevoice" / "iic" / "SenseVoiceSmall"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "model.pt").touch()
    return cache_dir


def _make_modelscope_sensevoice_cache(service_dir: Path) -> Path:
    """Create the cache layout produced by current ModelScope versions."""
    cache_dir = (
        service_dir
        / "models"
        / "sensevoice"
        / "models"
        / "iic--SenseVoiceSmall"
        / "snapshots"
        / "master"
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "model.pt").touch()
    return cache_dir


def _make_moonshine_cache(service_dir: Path, spec: str) -> Path:
    """Create a fake moonshine cache at the relocated services/asr/models/ path.

    Path: <service_dir>/models/moonshine/download.moonshine.ai/model/<spec>/quantized/
    """
    cache_dir = (
        service_dir
        / "models"
        / "moonshine"
        / "download.moonshine.ai"
        / "model"
        / spec
        / "quantized"
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "encoder_model.onnx").touch()
    return cache_dir


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


def test_environment_venv_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """When .venv exists and python binary is present, environment reports healthy."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    service_dir = tmp_path / "services" / "asr"
    data_dir = tmp_path / "data"
    _make_venv(service_dir / ".venv")

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    env = status.environment
    assert env.venv_exists is True
    assert env.service_python_exists is True
    assert env.service_dir_exists is True
    assert env.platform == sys.platform


def test_environment_venv_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """When .venv does not exist, environment reports false."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    service_dir = tmp_path / "services" / "asr"
    data_dir = tmp_path / "data"
    service_dir.mkdir(parents=True, exist_ok=True)  # dir exists, venv does not

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    assert status.environment.venv_exists is False
    assert status.environment.service_python_exists is False
    assert status.environment.service_dir_exists is True


def test_environment_service_dir_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """When the service directory itself is missing."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    service_dir = tmp_path / "services" / "asr"  # never created
    data_dir = tmp_path / "data"

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    assert status.environment.service_dir_exists is False
    assert status.environment.venv_exists is False


def test_fast_status_skips_runtime_probe_and_full_status_caches_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    service_dir = tmp_path / "services" / "asr"
    data_dir = tmp_path / "data"
    _make_venv(service_dir / ".venv")
    calls = []

    class Result:
        stdout = "mps\n"

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return Result()

    monkeypatch.setattr("core.asr_model_manager.subprocess.run", fake_run)
    manager = AsrModelManager(service_dir=service_dir, data_dir=data_dir)

    assert manager.get_status(probe_runtime_device=False).environment.runtime_device is None
    assert calls == []
    assert manager.get_status().environment.runtime_device == "mps"
    assert manager.get_status().environment.runtime_device == "mps"
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# Cache detection — SenseVoice
# ---------------------------------------------------------------------------


def test_sensevoice_installed_when_modelscope_cache_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """SenseVoice detected as installed when ModelScope cache dir exists."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create the ModelScope cache path
    sensevoice_cache = _make_sensevoice_cache(service_dir)

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    sv_status = status.models["sensevoice-small"]
    assert sv_status.installed is True
    assert sv_status.cache_path is not None
    assert str(sensevoice_cache) in sv_status.cache_path
    assert len(sv_status.cache_paths_checked) > 0


def test_sensevoice_not_installed_when_cache_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """SenseVoice reports not installed when no cache paths are found."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    sv_status = status.models["sensevoice-small"]
    assert sv_status.installed is False
    assert sv_status.cache_path is None


def test_sensevoice_installed_with_current_modelscope_cache_layout(tmp_path: Path):
    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True)
    cache_dir = _make_modelscope_sensevoice_cache(service_dir)

    status = AsrModelManager(service_dir, tmp_path / "data").get_status()

    sensevoice = status.models["sensevoice-small"]
    assert sensevoice.installed is True
    assert sensevoice.cache_path == str(cache_dir)


def test_sensevoice_installed_from_state_file_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """When state file records a cache_path, that path is used as primary check."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"

    custom_cache = tmp_path / "custom" / "sensevoice"
    custom_cache.mkdir(parents=True)
    (custom_cache / "model.pt").touch()

    _make_state(
        data_dir,
        {
            "current_model_slug": None,
            "models": {
                "sensevoice-small": {
                    "installed": True,
                    "cache_path": str(custom_cache),
                    "installed_at": "2026-06-01T00:00:00",
                }
            },
        },
    )

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    sv_status = status.models["sensevoice-small"]
    assert sv_status.installed is True
    assert sv_status.cache_path == str(custom_cache)


# ---------------------------------------------------------------------------
# Cache detection — Moonshine
# ---------------------------------------------------------------------------


def test_moonshine_installed_when_voice_cache_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """Moonshine base-en detected when moonshine_voice cache dir exists."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create moonshine_voice cache for base-en
    moonshine_cache = _make_moonshine_cache(service_dir, "base-en")

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    base_status = status.models["moonshine-base-en"]
    assert base_status.installed is True
    assert base_status.cache_path is not None
    assert str(moonshine_cache) in base_status.cache_path


def test_moonshine_not_installed_when_cache_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """Moonshine reports not installed when no moonshine_voice cache found."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    base_status = status.models["moonshine-base-en"]
    assert base_status.installed is False
    assert base_status.cache_path is None


# ---------------------------------------------------------------------------
# State file — current model selection
# ---------------------------------------------------------------------------


def test_current_model_from_state_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """When state file has current_model_slug, status.current reflects it."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"

    _make_state(
        data_dir,
        {
            "current_model_slug": "sensevoice-small",
            "models": {},
        },
    )

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    assert status.current == "sensevoice-small"
    sv_status = status.models["sensevoice-small"]
    assert sv_status.selected is True

    # Other models should not be selected
    assert status.models["moonshine-base-en"].selected is False


def test_current_none_when_no_state_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """When no state file exists, current is None."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    assert status.current is None
    for model_status in status.models.values():
        assert model_status.selected is False


def test_current_none_when_state_file_no_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """When state file exists but has no current_model_slug, current is None."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"

    _make_state(data_dir, {"current_model_slug": None, "models": {}})

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    assert status.current is None


# ---------------------------------------------------------------------------
# Disk usage
# ---------------------------------------------------------------------------


def test_disk_usage_returns_service_and_data_disks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """Disk stats cover the service dir disk and home disk."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    assert isinstance(status.disks, dict)
    # At least one disk entry
    assert len(status.disks) > 0
    for disk_info in status.disks.values():
        assert disk_info.total > 0
        assert disk_info.free >= 0
        assert disk_info.used >= 0


def test_model_dir_size_only_accumulates_explicit_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """Model directory sizes only count the explicit cache dirs, not the whole disk."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create a known cache with a known size
    sensevoice_cache = (
        service_dir / "models" / "sensevoice" / "iic" / "SenseVoiceSmall"
    )
    sensevoice_cache.mkdir(parents=True)
    (sensevoice_cache / "model.pt").write_text("x" * 1000)  # 1000 bytes

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    sv_status = status.models["sensevoice-small"]
    assert sv_status.installed is True
    # estimated_size should be set from the registry
    assert sv_status.estimated_size == "0.9GB"


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------


def test_cache_permission_error_returns_error_detail_not_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """When a cache path exists but is unreadable, status includes error detail."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create a cache directory and simulate it being unreadable.
    sensevoice_cache = _make_sensevoice_cache(service_dir)

    original_iterdir = Path.iterdir

    def permission_denied(path: Path):
        if path == sensevoice_cache:
            raise PermissionError("permission denied")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", permission_denied)
    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    sv_status = status.models["sensevoice-small"]
    assert sv_status.installed is not True
    assert len(sv_status.cache_paths_checked) > 0


def test_state_file_corrupted_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """When state file is corrupted, manager does not crash."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Write corrupt JSON
    (data_dir / "local_asr_models.json").write_text("{invalid json")

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()  # must not raise

    # Should fall back to defaults — current is None
    assert status.current is None


def test_all_registry_models_represented(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Every model in the registry appears in the status response."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    from core.asr_model_registry import SUPPORTED_LOCAL_ASR_MODELS

    assert set(status.models.keys()) == SUPPORTED_LOCAL_ASR_MODELS
    assert len(status.models) == 6


def test_model_status_fields_map_registry_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Each model status carries registry fields (slug, family, label, etc.)."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    mo_status = status.models["moonshine-tiny-en"]
    assert mo_status.slug == "moonshine-tiny-en"
    assert mo_status.family == "moonshine"
    assert mo_status.label == "Moonshine Tiny EN"
    assert mo_status.model_id == "moonshine_voice/tiny-en"
    assert mo_status.spec == "tiny-en"
    assert mo_status.size == "71MB"
    assert mo_status.runtime == "moonshine"


def test_estimated_size_falls_back_to_registry_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """estimated_size defaults to the registry size string."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    for slug, model_status in status.models.items():
        assert model_status.estimated_size, f"{slug} should have estimated_size"
        # For now estimated_size == registry size since we don't measure actual dir size
        from core.asr_model_registry import get_local_asr_model

        assert model_status.estimated_size == get_local_asr_model(slug).size


def test_progress_idle_when_no_operation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Progress shows idle when no install/uninstall is running."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    assert status.progress.stage == "idle"
    assert status.progress.model_slug is None
    assert status.progress.error is None


# ---------------------------------------------------------------------------
# Cache path details — conservative detection
# ---------------------------------------------------------------------------


def test_cache_paths_checked_includes_all_candidate_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """cache_paths_checked reports every path that was checked for each model."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    # SenseVoice should have checked ModelScope default path
    sv_status = status.models["sensevoice-small"]
    checked = [str(p) for p in sv_status.cache_paths_checked]
    # At least one candidate path was checked
    assert len(checked) > 0

    # Moonshine should have checked moonshine cache paths
    mo_status = status.models["moonshine-base-en"]
    mo_checked = [str(p) for p in mo_status.cache_paths_checked]
    assert len(mo_checked) > 0
    assert any("moonshine" in p for p in mo_checked)


def test_moonshine_tiny_streaming_cache_detection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """Each moonshine variant checks its own moonshine_voice cache path."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create moonshine_voice cache with only the tiny-streaming-en variant
    _make_moonshine_cache(service_dir, "tiny-streaming-en")

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    status = mgr.get_status()

    # The tiny-streaming variant should be installed
    ts_status = status.models["moonshine-tiny-streaming-en"]
    assert ts_status.installed is True

    # But base-en should NOT be installed (its cache dir doesn't exist)
    base_status = status.models["moonshine-base-en"]
    assert base_status.installed is False


# ===================================================================
# Task 3: select_model
# ===================================================================


def test_select_model_installed_writes_current_model_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """select_model writes current_model_slug to state when model is installed."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Pre-create state with sensevoice-small marked as installed
    sensevoice_cache = _make_sensevoice_cache(service_dir)

    _make_state(
        data_dir,
        {
            "current_model_slug": None,
            "models": {
                "sensevoice-small": {
                    "installed": True,
                    "cache_path": str(sensevoice_cache),
                    "installed_at": "2026-06-01T00:00:00",
                }
            },
        },
    )

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    mgr.select_model("sensevoice-small")

    # Verify state file was updated
    state = json.loads((data_dir / "local_asr_models.json").read_text())
    assert state["current_model_slug"] == "sensevoice-small"
    # Models entry should still be present
    assert "sensevoice-small" in state["models"]


def test_select_model_uninstalled_raises_value_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """select_model raises ValueError when model is not installed."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)

    with pytest.raises(ValueError, match="not installed"):
        mgr.select_model("sensevoice-small")


def test_select_model_state_has_model_but_cache_missing_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """select_model raises ValueError when state says installed but cache is gone."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # State says installed but no cache exists on disk
    _make_state(
        data_dir,
        {
            "current_model_slug": None,
            "models": {
                "sensevoice-small": {
                    "installed": True,
                    "cache_path": "/nonexistent/path",
                    "installed_at": "2026-06-01T00:00:00",
                }
            },
        },
    )

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)

    with pytest.raises(ValueError, match="not installed"):
        mgr.select_model("sensevoice-small")


def test_select_model_does_not_touch_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """select_model only writes state file, does NOT import or modify Settings."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Set up installed model
    sensevoice_cache = _make_sensevoice_cache(service_dir)

    _make_state(
        data_dir,
        {
            "current_model_slug": None,
            "models": {
                "sensevoice-small": {
                    "installed": True,
                    "cache_path": str(sensevoice_cache),
                    "installed_at": "2026-06-01T00:00:00",
                }
            },
        },
    )

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    # This should complete without trying to touch any Settings module
    mgr.select_model("sensevoice-small")

    # Verify state was written correctly
    status = mgr.get_status()
    assert status.current == "sensevoice-small"


def test_select_model_switches_between_installed_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """select_model can switch from one installed model to another."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Install sensevoice
    sv_cache = _make_sensevoice_cache(service_dir)

    # Install moonshine base-en
    mo_cache = _make_moonshine_cache(service_dir, "base-en")

    _make_state(
        data_dir,
        {
            "current_model_slug": None,
            "models": {
                "sensevoice-small": {
                    "installed": True,
                    "cache_path": str(sv_cache),
                    "installed_at": "2026-06-01T00:00:00",
                },
                "moonshine-base-en": {
                    "installed": True,
                    "cache_path": str(mo_cache),
                    "installed_at": "2026-06-01T00:00:00",
                },
            },
        },
    )

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)

    # Select sensevoice first
    mgr.select_model("sensevoice-small")
    status = mgr.get_status()
    assert status.current == "sensevoice-small"
    assert status.models["sensevoice-small"].selected is True

    # Then switch to moonshine
    mgr.select_model("moonshine-base-en")
    status = mgr.get_status()
    assert status.current == "moonshine-base-en"
    assert status.models["moonshine-base-en"].selected is True
    assert status.models["sensevoice-small"].selected is False


# ===================================================================
# Task 3: install_model (integration with mocked deploy module)
# ===================================================================


class _FakeDeployModule:
    """Simulates services/asr/deploy.py for testing manager orchestration."""

    def __init__(self):
        self.install_calls: list[dict] = []
        self.uninstall_calls: list[str] = []
        self.uninstall_all_calls: list[list[str]] = []

    def install_model(self, *, slug, model_id, runtime, spec, device, on_progress):
        self.install_calls.append({
            "slug": slug,
            "model_id": model_id,
            "runtime": runtime,
            "spec": spec,
        })
        if on_progress:
            on_progress("environment", "env ready", 50)
            on_progress("models", f"Downloading {model_id}", 50)
            on_progress("done", f"Model {slug} installed", 100)

    def uninstall_model(self, cache_path: str):
        import shutil
        self.uninstall_calls.append(cache_path)
        p = __import__("pathlib").Path(cache_path)
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)

    def uninstall_all(self, cache_paths: list[str]):
        self.uninstall_all_calls.append(list(cache_paths))


def test_install_model_writes_state_with_cache_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """install_model writes state with cache_path but does NOT change current_model_slug."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    fake_deploy = _FakeDeployModule()

    # Create the moonshine_voice cache that would be created by the download
    moonshine_cache = _make_moonshine_cache(service_dir, "tiny-en")

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    monkeypatch.setattr(mgr, "_load_deploy_module", lambda: fake_deploy)

    progress = mgr.install_model("moonshine-tiny-en")
    assert progress.stage == "queued"
    assert progress.model_slug == "moonshine-tiny-en"

    # Wait for background job to complete
    if mgr._job_future is not None:
        mgr._job_future.result(timeout=5)

    # Verify deploy module was called correctly
    assert len(fake_deploy.install_calls) == 1
    call = fake_deploy.install_calls[0]
    assert call["slug"] == "moonshine-tiny-en"
    assert call["model_id"] == "moonshine_voice/tiny-en"
    assert call["runtime"] == "moonshine"
    assert call["spec"] == "tiny-en"

    # Verify state was written with cache_path
    state = json.loads((data_dir / "local_asr_models.json").read_text())
    assert state["models"]["moonshine-tiny-en"]["installed"] is True
    assert state["models"]["moonshine-tiny-en"]["cache_path"] is not None
    assert "installed_at" in state["models"]["moonshine-tiny-en"]

    # current_model_slug should NOT have changed
    assert state["current_model_slug"] is None


def test_install_model_sensevoice_writes_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """install_model for sensevoice-small writes correct state."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    fake_deploy = _FakeDeployModule()

    # Pre-create the cache
    sv_cache = _make_sensevoice_cache(service_dir)

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    monkeypatch.setattr(mgr, "_load_deploy_module", lambda: fake_deploy)

    mgr.install_model("sensevoice-small")
    if mgr._job_future is not None:
        mgr._job_future.result(timeout=5)

    call = fake_deploy.install_calls[0]
    assert call["slug"] == "sensevoice-small"
    assert call["model_id"] == "iic/SenseVoiceSmall"
    assert call["runtime"] == "sensevoice"

    state = json.loads((data_dir / "local_asr_models.json").read_text())
    assert state["models"]["sensevoice-small"]["installed"] is True
    assert state["current_model_slug"] is None


def test_install_model_fails_when_download_has_no_usable_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True)
    data_dir = tmp_path / "data"
    fake_deploy = _FakeDeployModule()
    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    monkeypatch.setattr(mgr, "_load_deploy_module", lambda: fake_deploy)

    mgr.install_model("sensevoice-small")
    if mgr._job_future is not None:
        mgr._job_future.result(timeout=5)

    progress = mgr._progress()
    assert progress.stage == "failed"
    assert "no usable model cache" in (progress.error or "")
    assert not (data_dir / "local_asr_models.json").exists()


def test_install_model_busy_returns_current_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """When a job is already running, install_model returns current progress (busy)."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    fake_deploy = _FakeDeployModule()

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    monkeypatch.setattr(mgr, "_load_deploy_module", lambda: fake_deploy)

    # Start first install
    progress1 = mgr.install_model("moonshine-tiny-en")
    assert progress1.stage == "queued"

    # Try to start second install while first is running
    progress2 = mgr.install_model("sensevoice-small")
    # Should return the current progress (busy), not queue a new job
    # Stage may be "queued" or "environment" depending on executor timing
    assert progress2.stage in ("queued", "environment")
    assert progress2.model_slug == "moonshine-tiny-en"

    # Wait for first job to complete
    if mgr._job_future is not None:
        mgr._job_future.result(timeout=5)

    # Only one install call should have been made
    assert len(fake_deploy.install_calls) == 1


def test_install_model_failure_progress_has_error_detail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """When install fails, progress includes error detail and state is retryable."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    class FailingDeploy:
        def install_model(self, **kwargs):
            raise RuntimeError("Download failed: network error")

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    monkeypatch.setattr(mgr, "_load_deploy_module", lambda: FailingDeploy())

    mgr.install_model("moonshine-tiny-en")
    if mgr._job_future is not None:
        mgr._job_future.result(timeout=5)

    progress = mgr._progress()
    assert progress.stage == "failed"
    assert progress.error is not None
    assert "Download failed" in progress.error

    # State should NOT have the model marked as installed (half-finished state, retryable)
    status = mgr.get_status()
    assert status.models["moonshine-tiny-en"].installed is False


# ===================================================================
# Task 3: uninstall_model
# ===================================================================


def test_uninstall_model_removes_cache_and_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """uninstall_model removes cache dir and state entry, keeps venv."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    # Create venv to verify it's not removed
    _make_venv(service_dir / ".venv")

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create the cache
    moonshine_cache = _make_moonshine_cache(service_dir, "tiny-en")

    _make_state(
        data_dir,
        {
            "current_model_slug": "moonshine-tiny-en",
            "models": {
                "moonshine-tiny-en": {
                    "installed": True,
                    "cache_path": str(moonshine_cache),
                    "installed_at": "2026-06-01T00:00:00",
                }
            },
        },
    )

    fake_deploy = _FakeDeployModule()
    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    monkeypatch.setattr(mgr, "_load_deploy_module", lambda: fake_deploy)

    mgr.uninstall_model("moonshine-tiny-en")
    if mgr._job_future is not None:
        mgr._job_future.result(timeout=5)

    # Cache should be removed
    assert not moonshine_cache.exists()

    # Venv should still exist
    assert (service_dir / ".venv").is_dir()

    # State should have model entry removed and current cleared
    state = json.loads((data_dir / "local_asr_models.json").read_text())
    assert "moonshine-tiny-en" not in state.get("models", {})
    assert state["current_model_slug"] is None

    # deploy.uninstall_model should have been called
    assert len(fake_deploy.uninstall_calls) == 1


def test_uninstall_model_clears_current_only_if_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """uninstall_model only clears current_model_slug if the uninstalled model was current."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create two model caches
    sv_cache = _make_sensevoice_cache(service_dir)

    mo_cache = _make_moonshine_cache(service_dir, "tiny-en")

    _make_state(
        data_dir,
        {
            "current_model_slug": "sensevoice-small",
            "models": {
                "sensevoice-small": {
                    "installed": True,
                    "cache_path": str(sv_cache),
                    "installed_at": "2026-06-01T00:00:00",
                },
                "moonshine-tiny-en": {
                    "installed": True,
                    "cache_path": str(mo_cache),
                    "installed_at": "2026-06-01T00:00:00",
                },
            },
        },
    )

    fake_deploy = _FakeDeployModule()
    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    monkeypatch.setattr(mgr, "_load_deploy_module", lambda: fake_deploy)

    # Uninstall moonshine (NOT the current model)
    mgr.uninstall_model("moonshine-tiny-en")
    if mgr._job_future is not None:
        mgr._job_future.result(timeout=5)

    state = json.loads((data_dir / "local_asr_models.json").read_text())
    # moonshine should be removed from models
    assert "moonshine-tiny-en" not in state.get("models", {})
    # But current should still be sensevoice
    assert state["current_model_slug"] == "sensevoice-small"
    # SenseVoice model entry should still be there
    assert "sensevoice-small" in state["models"]


# ===================================================================
# Task 3: uninstall_all_local_asr
# ===================================================================


def test_uninstall_all_removes_caches_venv_and_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """uninstall_all removes all model caches + .venv + clears state."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    _make_venv(service_dir / ".venv")

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create two model caches
    sv_cache = _make_sensevoice_cache(service_dir)

    mo_cache = _make_moonshine_cache(service_dir, "tiny-en")

    _make_state(
        data_dir,
        {
            "current_model_slug": "sensevoice-small",
            "models": {
                "sensevoice-small": {
                    "installed": True,
                    "cache_path": str(sv_cache),
                    "installed_at": "2026-06-01T00:00:00",
                },
                "moonshine-tiny-en": {
                    "installed": True,
                    "cache_path": str(mo_cache),
                    "installed_at": "2026-06-01T00:00:00",
                },
            },
        },
    )

    fake_deploy = _FakeDeployModule()
    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    monkeypatch.setattr(mgr, "_load_deploy_module", lambda: fake_deploy)

    mgr.uninstall_all_local_asr()
    if mgr._job_future is not None:
        mgr._job_future.result(timeout=5)

    # deploy.uninstall_all should have been called with all cache paths
    assert len(fake_deploy.uninstall_all_calls) == 1
    called_paths = fake_deploy.uninstall_all_calls[0]
    assert len(called_paths) >= 2

    # State should be reset to defaults
    state = json.loads((data_dir / "local_asr_models.json").read_text())
    assert state["current_model_slug"] is None
    assert state["models"] == {}


def test_uninstall_all_does_not_delete_unknown_parent_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """uninstall_all removes registry caches but NOT unknown parent cache directories."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    _make_venv(service_dir / ".venv")

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create a known registry model cache
    sv_cache = _make_sensevoice_cache(service_dir)

    # Create an "unknown" sibling dir in the same parent structure
    unknown_dir = service_dir / "models" / "sensevoice" / "iic" / "some_other_model"
    unknown_dir.mkdir(parents=True)
    (unknown_dir / "other.bin").touch()

    _make_state(
        data_dir,
        {
            "current_model_slug": "sensevoice-small",
            "models": {
                "sensevoice-small": {
                    "installed": True,
                    "cache_path": str(sv_cache),
                    "installed_at": "2026-06-01T00:00:00",
                },
            },
        },
    )

    fake_deploy = _FakeDeployModule()
    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    monkeypatch.setattr(mgr, "_load_deploy_module", lambda: fake_deploy)

    mgr.uninstall_all_local_asr()
    if mgr._job_future is not None:
        mgr._job_future.result(timeout=5)

    # Only the known cache path should be in the uninstall_all call
    # The manager only passes known cache paths to deploy.uninstall_all
    called_paths = fake_deploy.uninstall_all_calls[0]
    assert str(sv_cache) in called_paths
    assert str(unknown_dir) not in called_paths


def test_uninstall_all_busy_returns_current_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """uninstall_all is blocked when another job is running."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create cache so install can succeed
    mo_cache = _make_moonshine_cache(service_dir, "tiny-en")

    fake_deploy = _FakeDeployModule()
    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    monkeypatch.setattr(mgr, "_load_deploy_module", lambda: fake_deploy)

    # Start install first
    mgr.install_model("moonshine-tiny-en")

    # Try uninstall_all while install is running
    progress = mgr.uninstall_all_local_asr()
    # Should reflect the running install job, not a new uninstall_all job
    assert progress.stage == "queued"
    assert progress.model_slug == "moonshine-tiny-en"

    # Wait for install to finish
    if mgr._job_future is not None:
        mgr._job_future.result(timeout=5)


def test_uninstall_all_failure_progress_has_error_detail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """When uninstall_all fails, progress has error detail."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    _make_venv(service_dir / ".venv")

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create a cache so detect_cache finds it
    sv_cache = _make_sensevoice_cache(service_dir)

    _make_state(
        data_dir,
        {
            "current_model_slug": "sensevoice-small",
            "models": {
                "sensevoice-small": {
                    "installed": True,
                    "cache_path": str(sv_cache),
                    "installed_at": "2026-06-01T00:00:00",
                },
            },
        },
    )

    class FailingDeploy:
        def uninstall_all(self, cache_paths):
            raise RuntimeError("Permission denied during cleanup")

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    monkeypatch.setattr(mgr, "_load_deploy_module", lambda: FailingDeploy())

    mgr.uninstall_all_local_asr()
    if mgr._job_future is not None:
        mgr._job_future.result(timeout=5)

    progress = mgr._progress()
    assert progress.stage == "failed"
    assert progress.error is not None
    assert "Permission denied" in progress.error


# ===================================================================
# Task 3: _detect_cache helper
# ===================================================================


def test_detect_cache_returns_path_for_installed_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """_detect_cache returns the cache_path for an installed model."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"

    sv_cache = _make_sensevoice_cache(service_dir)

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)

    from core.asr_model_registry import get_local_asr_model
    model = get_local_asr_model("sensevoice-small")
    state = mgr._read_state()

    cache_path = mgr._detect_cache(model, state)
    assert cache_path == str(sv_cache)


def test_detect_cache_returns_none_for_missing_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """_detect_cache returns None when model is not installed."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)

    from core.asr_model_registry import get_local_asr_model
    model = get_local_asr_model("sensevoice-small")
    state = mgr._read_state()

    cache_path = mgr._detect_cache(model, state)
    assert cache_path is None


# ===================================================================
# Task 3: write_state
# ===================================================================


def test_write_state_creates_file_and_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """_write_state creates the data directory and writes the file."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    service_dir = tmp_path / "services" / "asr"
    service_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "data"
    # Don't create data_dir — _write_state should create it

    mgr = AsrModelManager(service_dir=service_dir, data_dir=data_dir)
    mgr._write_state({"current_model_slug": "sensevoice-small", "models": {}})

    assert (data_dir / "local_asr_models.json").exists()
    content = json.loads((data_dir / "local_asr_models.json").read_text())
    assert content["current_model_slug"] == "sensevoice-small"
