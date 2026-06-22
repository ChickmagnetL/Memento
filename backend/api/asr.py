"""ASR deployment API."""

from concurrent.futures import Future, ThreadPoolExecutor
import importlib.util
from pathlib import Path
import threading

from fastapi import APIRouter, status

from config.settings import resolve_project_root
from schemas.asr import AsrDeployStatus, DeployProgress


router = APIRouter(prefix="/api/asr", tags=["asr"])

SERVICE_DIR = resolve_project_root() / "services" / "asr"
VENV_DIR = SERVICE_DIR / ".venv"

_executor = ThreadPoolExecutor(max_workers=1)
_progress = DeployProgress(stage="idle", detail="", percent=None)
_future: Future | None = None
_lock = threading.RLock()


def _models_installed() -> bool:
    return (
        Path.home()
        / ".cache"
        / "modelscope"
        / "hub"
        / "models"
        / "iic"
        / "SenseVoiceSmall"
        / "model.pt"
    ).exists()


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
