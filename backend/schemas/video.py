"""Video schemas for API and storage operations."""

from typing import Literal

from pydantic import BaseModel, Field

VideoPlatform = Literal["bilibili", "douyin", "youtube"]
VideoStatus = Literal["pending", "processing", "completed", "failed"]


class VideoCreateRequest(BaseModel):
    """Request body for creating a video record."""

    url: str = Field(min_length=1)
    title: str | None = None


class VideoStatusUpdateRequest(BaseModel):
    """Request body for updating processing status."""

    status: VideoStatus


class VideoRecord(BaseModel):
    """Stored video metadata."""

    id: str
    platform: VideoPlatform
    title: str
    author: str | None = None
    author_id: str | None = None
    duration: int | None = None
    url: str
    status: VideoStatus
    error_message: str | None = None
    created_at: str
    processed_at: str | None = None
