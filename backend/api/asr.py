"""ASR deployment API."""

from concurrent.futures import Future, ThreadPoolExecutor
import importlib.util
import threading

from fastapi import APIRouter, HTTPException, status

from config.settings import get_settings, resolve_project_root
from core.asr_model_manager import AsrModelManager
from schemas.asr import (
    AsrDeployStatus,
    AsrManagerProgress,
    AsrManagerStatus,
    DeployProgress,
    SelectModelResponse,
)


router = APIRouter(prefix="/api/asr", tags=["asr"])

SERVICE_DIR = resolve_project_root() / "services" / "asr"
VENV_DIR = SERVICE_DIR / ".venv"

_executor = ThreadPoolExecutor(max_workers=1)
_progress = DeployProgress(stage="idle", detail="", percent=None)
_future: Future | None = None
_lock = threading.RLock()

# ---------------------------------------------------------------------------
# Local model management (Task 5)
# ---------------------------------------------------------------------------

_manager: AsrModelManager | None = None


def _get_manager() -> AsrModelManager:
    """Lazy singleton AsrModelManager."""
    global _manager
    if _manager is None:
        settings = get_settings()
        data_dir = settings.storage.data_dir.expanduser().resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        _manager = AsrModelManager(service_dir=SERVICE_DIR, data_dir=data_dir)
    return _manager


def _models_installed() -> bool:
    root = SERVICE_DIR / "models" / "sensevoice"
    return root.is_dir() and any(root.rglob("model.pt"))


def _load_deploy_module():
    spec = importlib.util.spec_from_file_location(
        "memento_asr_deploy",
        SERVICE_DIR / "deploy.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("ASR deploy.py not found")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _set_progress(
    stage: str,
    detail: str,
    percent: int | None = None,
    *,
    done: bool = False,
    error: str | None = None,
) -> None:
    global _progress
    with _lock:
        _progress = DeployProgress(
            stage=stage,
            detail=detail,
            percent=percent,
            done=done,
            error=error,
        )


def _run_deploy() -> None:
    try:
        module = _load_deploy_module()
        module.deploy(on_progress=lambda stage, detail, percent=None: _set_progress(stage, detail, percent))
        _set_progress("done", "ASR environment ready", 100, done=True)
    except Exception as exc:
        _set_progress("failed", "ASR deployment failed", None, done=True, error=str(exc))


@router.get("/deploy/status", response_model=AsrDeployStatus)
def deploy_status() -> AsrDeployStatus:
    return AsrDeployStatus(
        venv_exists=VENV_DIR.exists(),
        models_installed=_models_installed(),
    )


@router.post(
    "/deploy",
    response_model=DeployProgress,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_deploy() -> DeployProgress:
    global _future
    with _lock:
        if _future is not None and not _future.done():
            return _progress
        _set_progress("queued", "ASR deployment queued", 0)
        _future = _executor.submit(_run_deploy)
        return _progress


@router.get("/deploy/progress", response_model=DeployProgress)
def deploy_progress() -> DeployProgress:
    return _progress


# ---------------------------------------------------------------------------
# Local model management endpoints (Task 5)
# ---------------------------------------------------------------------------


@router.get("/local/status", response_model=AsrManagerStatus)
def local_status(probe_runtime_device: bool = True) -> AsrManagerStatus:
    """Return full local ASR status: environment, models, current, disks, progress."""
    return _get_manager().get_status(probe_runtime_device=probe_runtime_device)


@router.post(
    "/local/models/{slug}/install",
    response_model=AsrManagerProgress,
    status_code=status.HTTP_202_ACCEPTED,
)
def local_install_model(slug: str) -> AsrManagerProgress:
    """Start installing a single local ASR model by slug."""
    try:
        return _get_manager().install_model(slug)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Model '{slug}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/local/models/{slug}/select",
    response_model=SelectModelResponse,
)
def local_select_model(slug: str) -> SelectModelResponse:
    """Select an installed model as the current local ASR model."""
    try:
        _get_manager().select_model(slug)
        return SelectModelResponse(current=slug)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Model '{slug}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/local/models/{slug}",
    response_model=AsrManagerProgress,
    status_code=status.HTTP_202_ACCEPTED,
)
def local_uninstall_model(slug: str) -> AsrManagerProgress:
    """Start uninstalling a single local ASR model by slug."""
    try:
        return _get_manager().uninstall_model(slug)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Model '{slug}' not found")


@router.post(
    "/local/uninstall-all",
    response_model=AsrManagerProgress,
    status_code=status.HTTP_202_ACCEPTED,
)
def local_uninstall_all() -> AsrManagerProgress:
    """Uninstall all local ASR models and environment."""
    return _get_manager().uninstall_all_local_asr()


@router.get("/local/progress", response_model=AsrManagerProgress)
def local_progress() -> AsrManagerProgress:
    """Return the current or latest local ASR job progress."""
    return _get_manager().get_status().progress
