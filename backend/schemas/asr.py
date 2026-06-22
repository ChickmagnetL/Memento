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
