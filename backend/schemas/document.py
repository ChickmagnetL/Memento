"""Document schemas for API responses."""

from pydantic import BaseModel


class DocumentRecord(BaseModel):
    """Stored document metadata."""

    id: str
    video_id: str | None
    file_path: str
    chunk_count: int
    status: str
    indexed_at: str | None = None


class UnimportedDocument(BaseModel):
    """A markdown file on disk that has no KB document record yet."""

    file_path: str
    title: str | None = None
    platform: str | None = None
    source_url: str | None = None
    video_id: str | None = None
