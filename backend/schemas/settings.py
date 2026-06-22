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
