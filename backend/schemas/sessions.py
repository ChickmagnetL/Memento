"""Pydantic models for chat session API responses."""

from pydantic import BaseModel, Field, field_validator


class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    created_at: str


class SessionCreateRequest(BaseModel):
    title: str | None = None


class SessionUpdateRequest(BaseModel):
    """Body for PATCH /api/sessions/{sid}. All fields optional — client may
    send an empty body to no-op."""
    title: str | None = None


class MessageEditRequest(BaseModel):
    """Body for PATCH /api/sessions/{sid}/messages/{mid}."""
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value
