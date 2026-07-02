"""Pydantic models for memories API."""

from pydantic import BaseModel


class MemoryResponse(BaseModel):
    id: str
    content: str
    category: str | None
    created_at: str


class MemoryCreateRequest(BaseModel):
    content: str
    category: str | None = None