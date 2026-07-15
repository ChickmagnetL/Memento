"""ASR model manager — model-aware status, install, select, uninstall with progress."""

from __future__ import annotations

import datetime
import importlib.util
import json
import shutil
import subprocess
import sys
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

from core.asr_model_registry import (
    SUPPORTED_LOCAL_ASR_MODELS,
    AsrModel,
    get_local_asr_model,
    list_local_asr_models,
)
from schemas.asr import (
    AsrDiskInfo,
    AsrEnvironmentStatus,
    AsrManagerProgress,
    AsrManagerStatus,
    AsrModelStatus,
)

# ---------------------------------------------------------------------------
# Candidate cache path helpers
# ---------------------------------------------------------------------------


def _sensevoice_cache_dir(service_dir: Path) -> Path:
    """Legacy SenseVoiceSmall cache directory under services/asr/models/."""
    return service_dir / "models" / "sensevoice" / "iic" / "SenseVoiceSmall"


def _sensevoice_cache_candidates(service_dir: Path) -> list[Path]:
    """Return supported ModelScope cache layouts for SenseVoiceSmall."""
    root = service_dir / "models" / "sensevoice"
    candidates = [_sensevoice_cache_dir(service_dir)]
    snapshots = root / "models" / "iic--SenseVoiceSmall" / "snapshots"
    if snapshots.is_dir():
        candidates.extend(sorted(path for path in snapshots.iterdir() if path.is_dir()))
    return candidates


def _moonshine_cache_dir(service_dir: Path, spec: str) -> Path:
    """Relocated moonshine cache directory under services/asr/models/.

    Each variant is stored under ``download.moonshine.ai/model/<spec>/quantized/``.
    """
    return service_dir / "models" / "moonshine" / "download.moonshine.ai" / "model" / spec / "quantized"


def _dir_exists_and_accessible(path: Path) -> tuple[bool, str | None]:
    """Return (exists, error_detail).  error=None means accessible."""
    try:
        if not path.exists():
            return False, None
        # Try to list the directory to confirm it is readable
        try:
            next(path.iterdir(), None)
        except PermissionError:
            return True, "directory exists but is not readable (permission denied)"
        return True, None
    except OSError as exc:
        return False, str(exc)


def _model_dir_contains_files(path: Path) -> bool:
    """Conservative check: does *path* look like it holds model files?

    Returns True when the directory contains any file (recursively), False
    when empty or inacessible.
    """
    try:
        for _f in path.rglob("*"):
            if _f.is_file():
                return True
        return False
    except (PermissionError, OSError):
        return False


# ---------------------------------------------------------------------------
# State file
# ---------------------------------------------------------------------------

_STATE_FILENAME = "local_asr_models.json"


def _default_state_content() -> dict:
    return {"current_model_slug": None, "models": {}}


class AsrModelManager:
    """Model status aggregator with install / select / uninstall orchestration.

    Parameters
    ----------
    service_dir:
        The ``services/asr`` directory (contains ``deploy.py`` and ``.venv``).
    data_dir:
        The app data directory where the state file lives.
    """

    def __init__(self, service_dir: Path, data_dir: Path) -> None:
        self.service_dir = Path(service_dir)
        self.data_dir = Path(data_dir).expanduser()
        self._state_path = self.data_dir / _STATE_FILENAME
        self._lock = threading.RLock()

        # Background job plumbing (single-process, no concurrent jobs)
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._job_future: Future | None = None
        self._job_lock = threading.RLock()
        self._progress_state = AsrManagerProgress(stage="idle")

    # ------------------------------------------------------------------
    # State file
    # ------------------------------------------------------------------

    def _read_state(self) -> dict:
        """Read state file, returning defaults on any error."""
        try:
            raw = self._state_path.read_text()
            return json.loads(raw)
        except (FileNotFoundError, json.JSONDecodeError):
            return _default_state_content()

    def _write_state(self, content: dict) -> None:
        """Write state file atomically."""
        with self._lock:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._state_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(content, indent=2))
            tmp_path.replace(self._state_path)

    # ------------------------------------------------------------------
    # Environment
    # ------------------------------------------------------------------

    def _env_status(self) -> AsrEnvironmentStatus:
        venv_dir = self.service_dir / ".venv"
        venv_exists = venv_dir.is_dir()

        python_exists = False
        if venv_exists:
            bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
            python_name = "python.exe" if sys.platform == "win32" else "python"
            python_path = bin_dir / python_name
            python_exists = python_path.is_file()

        return AsrEnvironmentStatus(
            venv_exists=venv_exists,
            service_python_exists=python_exists,
            service_dir_exists=self.service_dir.is_dir(),
            platform=sys.platform,
            target_device=self._target_device(),
            runtime_device=self._runtime_device(),
        )

    def _runtime_device(self) -> str | None:
        venv_dir = self.service_dir / ".venv"
        if sys.platform == "win32":
            python = venv_dir / "Scripts" / "python.exe"
        else:
            python = venv_dir / "bin" / "python"
        if not python.is_file():
            return None
        script = (
            "import torch;"
            " print('cuda' if torch.cuda.is_available()"
            " else 'mps' if torch.backends.mps.is_available() else 'cpu')"
        )
        try:
            result = subprocess.run(
                [str(python), "-c", script],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception:
            return None
        device = result.stdout.strip()
        return device if device in {"cuda", "mps", "cpu"} else None

    def _target_device(self) -> str:
        if shutil.which("nvidia-smi") is not None:
            return "cuda"
        if sys.platform == "darwin":
            return "mps"
        return self._runtime_device() or "cpu"

    # ------------------------------------------------------------------
    # Per-model cache detection
    # ------------------------------------------------------------------

    def _detect_sensevoice(self, model: AsrModel, state: dict) -> dict[str, object]:
        """Detect SenseVoiceSmall cache location."""
        model_state = state.get("models", {}).get(model.slug, {})
        checked: list[Path] = []
        result: dict[str, object] = {"installed": False, "cache_path": None, "error": None}

        # 1. Recorded path from state file (if exists and accessible)
        recorded = model_state.get("cache_path")
        if recorded:
            recorded_path = Path(recorded)
            checked.append(recorded_path)
            exists, err = _dir_exists_and_accessible(recorded_path)
            if exists and err is None and (recorded_path / "model.pt").is_file():
                result["installed"] = True
                result["cache_path"] = recorded
                return result
            if err:
                result["installed"] = None
                result["error"] = err
                result["checked"] = checked
                return result
        for candidate in _sensevoice_cache_candidates(self.service_dir):
            if candidate in checked:
                continue
            checked.append(candidate)
            exists, err = _dir_exists_and_accessible(candidate)
            if exists and err is None and (candidate / "model.pt").is_file():
                result["installed"] = True
                result["cache_path"] = str(candidate)
                break
            if err:
                result["installed"] = None
                result["error"] = err
                break

        result["checked"] = checked
        return result

    def _detect_moonshine(self, model: AsrModel, state: dict) -> dict[str, object]:
        """Detect a moonshine model cache."""
        model_state = state.get("models", {}).get(model.slug, {})
        checked: list[Path] = []
        result: dict[str, object] = {"installed": False, "cache_path": None, "error": None}

        # 1. Recorded path from state file
        recorded = model_state.get("cache_path")
        if recorded:
            recorded_path = Path(recorded)
            checked.append(recorded_path)
            exists, err = _dir_exists_and_accessible(recorded_path)
            if exists and err is None and _model_dir_contains_files(recorded_path):
                result["installed"] = True
                result["cache_path"] = recorded
                return result
            if err:
                result["installed"] = None
                result["error"] = err
                result["checked"] = checked
                return result

        # 2. moonshine package default cache
        default = _moonshine_cache_dir(self.service_dir, model.spec or "")
        checked.append(default)
        exists, err = _dir_exists_and_accessible(default)
        if exists and err is None:
            if _model_dir_contains_files(default):
                result["installed"] = True
                result["cache_path"] = str(default)
            else:
                result["installed"] = False
        elif err:
            result["installed"] = None
            result["error"] = err

        result["checked"] = checked
        return result

    def _detect_cache(self, model: AsrModel, state: dict) -> str | None:
        """Detect and return the cache_path for *model*, or None if not installed."""
        if model.runtime == "sensevoice":
            detection = self._detect_sensevoice(model, state)
        else:
            detection = self._detect_moonshine(model, state)
        if detection.get("installed") is True:
            return detection.get("cache_path")
        return None

    def _build_model_status(self, model: AsrModel, state: dict) -> AsrModelStatus:
        """Detect cache and build AsrModelStatus for a single registry model."""
        if model.runtime == "sensevoice":
            detection = self._detect_sensevoice(model, state)
        else:
            detection = self._detect_moonshine(model, state)

        checked_paths: list[Path] = detection.pop("checked", [])
        error: str | None = detection.pop("error", None)

        # Compute installed/selected
        installed: bool | None = detection["installed"]

        # Check if currently installing this slug
        installing = False
        with self._job_lock:
            prog = self._progress_state
            if prog.stage not in ("idle",) and prog.model_slug == model.slug:
                if prog.stage != "done":
                    installing = True

        current = state.get("current_model_slug") == model.slug

        # Estimate size — prefer registry size string
        estimated_size = model.size

        return AsrModelStatus(
            slug=model.slug,
            family=model.family,
            label=model.label,
            model_id=model.model_id,
            spec=model.spec,
            size=model.size,
            runtime=model.runtime,
            installed=installed,
            installing=installing,
            selected=current,
            estimated_size=estimated_size,
            cache_path=detection.get("cache_path"),
            cache_paths_checked=[str(p) for p in checked_paths],
            last_error=error,
        )

    # ------------------------------------------------------------------
    # Disk
    # ------------------------------------------------------------------

    def _disk_info(self) -> dict[str, AsrDiskInfo]:
        """Return disk usage for the service and data mount points."""
        result: dict[str, AsrDiskInfo] = {}
        seen: set[str] = set()

        for label, path in [
            ("service_disk", self.service_dir),
            ("data_disk", self.data_dir),
        ]:
            # Resolve to the real mount point
            try:
                resolved = path.resolve(strict=False)
            except OSError:
                continue
            try:
                usage = shutil.disk_usage(resolved)
            except OSError:
                continue
            key = f"{label} ({resolved})"
            if key not in seen:
                seen.add(key)
                result[label] = AsrDiskInfo(
                    total=usage.total,
                    free=usage.free,
                    used=usage.used,
                )

        return result

    # ------------------------------------------------------------------
    # Progress tracking
    # ------------------------------------------------------------------

    def _set_progress(
        self,
        stage: str,
        detail: str = "",
        *,
        model_slug: str | None = None,
        percent: int | None = None,
        error: str | None = None,
    ) -> None:
        with self._job_lock:
            self._progress_state = AsrManagerProgress(
                stage=stage,
                model_slug=model_slug,
                percent=percent,
                detail=detail,
                error=error,
                done=stage in {"done", "failed"},
            )

    def _progress(self) -> AsrManagerProgress:
        """Return the current progress snapshot."""
        with self._job_lock:
            # If a job just finished, reflect completion in progress
            if self._job_future is not None and self._job_future.done():
                try:
                    self._job_future.result()
                except Exception:
                    pass  # error already captured in progress state
                self._job_future = None
            return self._progress_state

    # ------------------------------------------------------------------
    # Deploy module loader
    # ------------------------------------------------------------------

    def _load_deploy_module(self):
        """Import services/asr/deploy.py as a module."""
        deploy_path = self.service_dir / "deploy.py"
        spec = importlib.util.spec_from_file_location(
            "memento_asr_deploy_manager",
            deploy_path,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("ASR deploy.py not found")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    # ------------------------------------------------------------------
    # Public orchestration API
    # ------------------------------------------------------------------

    def get_status(self) -> AsrManagerStatus:
        """Return full status snapshot — environment, models, current, disks, progress."""
        with self._lock:
            state = self._read_state()
            env = self._env_status()

            models_status: dict[str, AsrModelStatus] = {}
            for model in list_local_asr_models():
                models_status[model.slug] = self._build_model_status(model, state)

            current_slug: str | None = state.get("current_model_slug")
            # Validate that current slug is still a known model
            if current_slug and current_slug not in SUPPORTED_LOCAL_ASR_MODELS:
                current_slug = None

            disks = self._disk_info()
            progress = self._progress()

            return AsrManagerStatus(
                environment=env,
                models=models_status,
                current=current_slug,
                disks=disks,
                progress=progress,
            )

    # ------------------------------------------------------------------
    # install_model
    # ------------------------------------------------------------------

    def install_model(self, slug: str) -> AsrManagerProgress:
        """Start a background install of the model identified by *slug*.

        Returns the current progress.  If a job is already running, the
        progress reflects the busy/in-progress state.
        """
        model = get_local_asr_model(slug)

        with self._job_lock:
            if self._job_future is not None and not self._job_future.done():
                return self._progress_state
            self._set_progress("queued", f"Install {slug} queued", model_slug=slug, percent=0)
            self._job_future = self._executor.submit(self._run_install, model)
            return self._progress_state

    def _run_install(self, model: AsrModel) -> None:
        """Background task: ensure environment + download single model + record state."""
        slug = model.slug
        try:
            self._set_progress("environment", "Setting up ASR environment", model_slug=slug, percent=5)
            deploy_module = self._load_deploy_module()

            def on_progress(stage: str, detail: str, percent: int | None = None) -> None:
                mapped_percent = None
                if percent is not None:
                    # Map deploy progress (0-100) to overall progress (5-95)
                    mapped_percent = 5 + int(percent * 0.9)
                reported_stage = "verifying" if stage == "done" else stage
                self._set_progress(
                    reported_stage,
                    detail,
                    model_slug=slug,
                    percent=mapped_percent,
                )

            deploy_module.install_model(
                slug=slug,
                model_id=model.model_id,
                runtime=model.runtime,
                spec=model.spec,
                device=None,
                on_progress=on_progress,
            )

            # Detect the cache path after successful install
            self._set_progress("detecting", "Detecting installed model cache", model_slug=slug, percent=95)
            state = self._read_state()
            cache_path = self._detect_cache(model, state)
            if cache_path is None:
                raise RuntimeError(
                    f"Model {slug} download finished but no usable model cache was found"
                )

            # Write state: model installed, but do NOT change current_model_slug
            state.setdefault("models", {})[slug] = {
                "installed": True,
                "cache_path": cache_path,
                "installed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            self._write_state(state)

            self._set_progress("done", f"Model {slug} installed", model_slug=slug, percent=100)
        except Exception as exc:
            self._set_progress(
                "failed",
                f"Install failed: {exc}",
                model_slug=slug,
                percent=None,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # select_model
    # ------------------------------------------------------------------

    def select_model(self, slug: str) -> None:
        """Select *slug* as the current model.  Raises ValueError if not installed.

        Only writes ``current_model_slug`` to the state file.  Does NOT
        modify Settings ASR configuration.
        """
        model = get_local_asr_model(slug)
        state = self._read_state()

        # Validate model is installed
        model_state = state.get("models", {}).get(slug)
        if not model_state or not model_state.get("installed"):
            raise ValueError(f"Model '{slug}' is not installed")

        # Also double-check via cache detection
        cache_path = self._detect_cache(model, state)
        if cache_path is None:
            raise ValueError(f"Model '{slug}' is not installed (cache not found)")

        state["current_model_slug"] = slug
        self._write_state(state)

    # ------------------------------------------------------------------
    # uninstall_model
    # ------------------------------------------------------------------

    def uninstall_model(self, slug: str) -> AsrManagerProgress:
        """Start a background uninstall of the model identified by *slug*."""
        model = get_local_asr_model(slug)

        with self._job_lock:
            if self._job_future is not None and not self._job_future.done():
                return self._progress_state
            self._set_progress("queued", f"Uninstall {slug} queued", model_slug=slug, percent=0)
            self._job_future = self._executor.submit(self._run_uninstall, model)
            return self._progress_state

    def _run_uninstall(self, model: AsrModel) -> None:
        """Background task: remove model cache + update state."""
        slug = model.slug
        try:
            self._set_progress("uninstalling", f"Removing {slug}", model_slug=slug, percent=20)

            state = self._read_state()
            cache_path = self._detect_cache(model, state)

            if cache_path:
                deploy_module = self._load_deploy_module()
                self._set_progress("uninstalling", f"Deleting cache for {slug}", model_slug=slug, percent=50)
                deploy_module.uninstall_model(cache_path)

            # Update state: remove model entry
            state.get("models", {}).pop(slug, None)

            # If the uninstalled model was the current one, clear current
            if state.get("current_model_slug") == slug:
                state["current_model_slug"] = None

            self._write_state(state)
            self._set_progress("done", f"Model {slug} uninstalled", model_slug=slug, percent=100)
        except Exception as exc:
            self._set_progress(
                "failed",
                f"Uninstall failed: {exc}",
                model_slug=slug,
                percent=None,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # uninstall_all_local_asr
    # ------------------------------------------------------------------

    def uninstall_all_local_asr(self) -> AsrManagerProgress:
        """Start a background uninstall of ALL local ASR models and environment."""
        with self._job_lock:
            if self._job_future is not None and not self._job_future.done():
                return self._progress_state
            self._set_progress("queued", "Uninstall all queued", percent=0)
            self._job_future = self._executor.submit(self._run_uninstall_all)
            return self._progress_state

    def _run_uninstall_all(self) -> None:
        """Background task: remove all model caches + venv + state."""
        try:
            state = self._read_state()

            # Collect all known cache paths from registry models
            cache_paths: list[str] = []
            for model in list_local_asr_models():
                detected = self._detect_cache(model, state)
                if detected:
                    cache_paths.append(detected)

            self._set_progress("uninstalling", "Removing all model caches", percent=30)
            deploy_module = self._load_deploy_module()
            deploy_module.uninstall_all(cache_paths)

            # Reset state file entirely
            self._set_progress("uninstalling", "Clearing state", percent=90)
            self._write_state(_default_state_content())

            self._set_progress("done", "All local ASR models and environment removed", percent=100)
        except Exception as exc:
            self._set_progress(
                "failed",
                f"Uninstall all failed: {exc}",
                percent=None,
                error=str(exc),
            )
