"""Local Embedding environment and model management API."""

from fastapi import APIRouter, HTTPException, status

from config.settings import resolve_project_root
from core.embedding_model_manager import EmbeddingModelManager
from schemas.embedding import EmbeddingManagerProgress, EmbeddingManagerStatus


router = APIRouter(prefix="/api/embedding", tags=["embedding"])
SERVICE_DIR = resolve_project_root() / "services" / "embedding"
_manager: EmbeddingModelManager | None = None


def _get_manager() -> EmbeddingModelManager:
    global _manager
    if _manager is None:
        _manager = EmbeddingModelManager(service_dir=SERVICE_DIR)
    return _manager


@router.get("/local/status", response_model=EmbeddingManagerStatus)
def local_status() -> EmbeddingManagerStatus:
    return _get_manager().get_status()


@router.post(
    "/local/models/{slug}/install",
    response_model=EmbeddingManagerProgress,
    status_code=status.HTTP_202_ACCEPTED,
)
def local_install_model(slug: str) -> EmbeddingManagerProgress:
    try:
        return _get_manager().install_model(slug)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Model '{slug}' not found")


@router.delete(
    "/local/models/{slug}",
    response_model=EmbeddingManagerProgress,
    status_code=status.HTTP_202_ACCEPTED,
)
def local_uninstall_model(slug: str) -> EmbeddingManagerProgress:
    try:
        return _get_manager().uninstall_model(slug)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Model '{slug}' not found")


@router.post(
    "/local/uninstall-all",
    response_model=EmbeddingManagerProgress,
    status_code=status.HTTP_202_ACCEPTED,
)
def local_uninstall_all() -> EmbeddingManagerProgress:
    return _get_manager().uninstall_all()


@router.get("/local/progress", response_model=EmbeddingManagerProgress)
def local_progress() -> EmbeddingManagerProgress:
    return _get_manager().get_status().progress
