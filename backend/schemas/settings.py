"""Settings API schemas."""

from pydantic import BaseModel


class ModelConfigUpdate(BaseModel):
    """Partial model config; None fields keep current values."""

    provider: str | None = None
    endpoint: str | None = None
    api_key: str | None = None
    model: str | None = None
    protocol: str | None = None


class ModelsUpdateRequest(BaseModel):
    chat: ModelConfigUpdate | None = None
    embedding: ModelConfigUpdate | None = None
    asr: ModelConfigUpdate | None = None


# ===== Preset Schemas =====


class PresetConfig(BaseModel):
    """Complete preset configuration."""

    provider: str | None = None
    endpoint: str | None = None
    api_key: str | None = None
    model: str | None = None
    protocol: str | None = None


class ModelListRequest(BaseModel):
    """Request to fetch available models for a draft preset config."""

    config: PresetConfig


class PresetCreateRequest(BaseModel):
    """Request to create a new preset."""

    name: str | None = None
    config: PresetConfig


class PresetUpdateRequest(BaseModel):
    """Request to update an existing preset."""

    name: str | None = None
    model_name: str | None = None
    config: PresetConfig | None = None


class PresetResponse(BaseModel):
    """Preset record returned by the API."""

    id: str
    model_name: str
    name: str
    config: dict
    created_at: str
    updated_at: str
