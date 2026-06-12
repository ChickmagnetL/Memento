"""Chat request schema."""

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Request body for a chat turn."""

    message: str = Field(min_length=1)
    session_id: str | None = None

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value
