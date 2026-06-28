"""Pydantic models for chat session API responses."""

from pydantic import BaseModel


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
