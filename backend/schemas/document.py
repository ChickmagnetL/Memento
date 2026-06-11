"""Document schemas for API responses."""

from pydantic import BaseModel


class DocumentRecord(BaseModel):
    """Stored document metadata."""

    id: str
    video_id: str
    file_path: str
    chunk_count: int
    is_indexed: bool
    indexed_at: str | None = None