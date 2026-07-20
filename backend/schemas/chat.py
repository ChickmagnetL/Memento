"""Chat request schema."""

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Request body for a chat turn.

    When ``regenerate`` is True (edit-regenerate flow), the backend skips
    re-persisting the user message — the edited user turn is expected to have
    been persisted by the edit endpoint that triggered regeneration.
    """

    message: str = Field(min_length=1)
    session_id: str | None = None
    regenerate: bool = False

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value
