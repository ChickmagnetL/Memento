"""Search request schema. Result schema lives in core.rag.retrieval."""

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Request body for knowledge base search."""

    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=50)