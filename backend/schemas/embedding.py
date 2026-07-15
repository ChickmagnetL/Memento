"""Schemas for local Embedding environment and model management."""

from pydantic import BaseModel


class EmbeddingEnvironmentStatus(BaseModel):
    venv_exists: bool
    service_python_exists: bool
    service_dir_exists: bool
    platform: str
    target_device: str
    runtime_device: str | None = None


class EmbeddingModelStatus(BaseModel):
    slug: str
    label: str
    model_id: str
    installed: bool
    installing: bool = False
    cache_path: str | None = None
    last_error: str | None = None


class EmbeddingManagerProgress(BaseModel):
    stage: str = "idle"
    model_slug: str | None = None
    percent: int | None = None
    detail: str = ""
    error: str | None = None
    done: bool = False


class EmbeddingManagerStatus(BaseModel):
    environment: EmbeddingEnvironmentStatus
    models: dict[str, EmbeddingModelStatus]
    progress: EmbeddingManagerProgress
