"""ASR deployment API schemas."""

from pydantic import BaseModel


class AsrDeployStatus(BaseModel):
    venv_exists: bool
    models_installed: bool


class DeployProgress(BaseModel):
    stage: str
    detail: str
    percent: int | None = None
    done: bool = False
    error: str | None = None


# ---------------------------------------------------------------------------
# Model-aware status schemas (Task 2)
# ---------------------------------------------------------------------------


class AsrEnvironmentStatus(BaseModel):
    venv_exists: bool
    service_python_exists: bool
    service_dir_exists: bool
    platform: str


class AsrModelStatus(BaseModel):
    """Per-model status merging registry info with runtime state."""

    slug: str
    family: str
    label: str
    model_id: str
    spec: str | None = None
    size: str
    runtime: str
    installed: bool | None = None
    installing: bool = False
    selected: bool = False
    estimated_size: str = ""
    cache_path: str | None = None
    cache_paths_checked: list[str] = []
    last_error: str | None = None


class AsrDiskInfo(BaseModel):
    total: int
    free: int
    used: int


class AsrManagerProgress(BaseModel):
    stage: str = "idle"
    model_slug: str | None = None
    percent: int | None = None
    detail: str = ""
    error: str | None = None


class AsrManagerStatus(BaseModel):
    environment: AsrEnvironmentStatus
    models: dict[str, AsrModelStatus]
    current: str | None = None
    disks: dict[str, AsrDiskInfo]
    progress: AsrManagerProgress


class SelectModelResponse(BaseModel):
    """Response for the select-model endpoint."""
    current: str
