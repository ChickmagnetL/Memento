"""Video record API endpoints."""

import logging
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status

from config.settings import get_settings
from core.video.pipeline import VideoPipeline
from schemas.video import VideoCreateRequest, VideoRecord, VideoStatusUpdateRequest
from storage.sqlite_client import SQLiteClient

router = APIRouter(prefix="/api/videos", tags=["videos"])
logger = logging.getLogger(__name__)


def detect_platform(url: str) -> str:
    """Detect supported video platform from URL host."""
    host = urlparse(url).netloc.lower()
    if "bilibili.com" in host or host == "b23.tv":
        return "bilibili"
    if "douyin.com" in host or "iesdouyin.com" in host:
        return "douyin"
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Only Bilibili and Douyin URLs are supported",
    )


def get_sqlite(request: Request) -> SQLiteClient:
    """Return the app-scoped SQLite client."""
    sqlite = getattr(request.app.state, "sqlite", None)
    if sqlite is None:
        raise HTTPException(status_code=500, detail="SQLite client is not initialized")
    return sqlite


@router.post("", response_model=VideoRecord, status_code=status.HTTP_201_CREATED)
async def create_video(payload: VideoCreateRequest, request: Request) -> dict:
    """Create a pending video record."""
    platform = detect_platform(payload.url)
    sqlite = get_sqlite(request)
    return await sqlite.create_video(
        video_id=uuid4().hex,
        platform=platform,
        title=payload.title or payload.url,
        url=payload.url,
    )


@router.get("", response_model=list[VideoRecord])
async def list_videos(request: Request) -> list[dict]:
    """List video records."""
    sqlite = get_sqlite(request)
    return await sqlite.list_videos()


@router.get("/{video_id}", response_model=VideoRecord)
async def get_video(video_id: str, request: Request) -> dict:
    """Return one video record."""
    sqlite = get_sqlite(request)
    video = await sqlite.get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.post("/{video_id}/process", response_model=VideoRecord)
async def process_video(video_id: str, request: Request) -> dict:
    """Trigger skeleton processing for a video record."""
    sqlite = get_sqlite(request)
    processing_video = await sqlite.claim_video_for_processing(video_id)
    if processing_video is None:
        current_video = await sqlite.get_video(video_id)
        if current_video is None:
            raise HTTPException(status_code=404, detail="Video not found")
        if current_video["status"] == "completed":
            return current_video
        if current_video["status"] == "processing":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Video is already processing",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Video could not be claimed for processing",
        )

    settings = get_settings()
    pipeline = VideoPipeline(
        sqlite=sqlite,
        data_dir=settings.storage.data_dir.expanduser(),
        bilibili_cookie=settings.video_processing.bilibili_cookie,
    )
    try:
        result = await pipeline.process(processing_video)
        final_status = "completed" if result.status == "completed" else "failed"
    except Exception:
        logger.exception("Unexpected video pipeline exception for video %s", video_id)
        final_status = "failed"
    final_video = await sqlite.update_video_status(video_id, final_status)
    if final_video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return final_video


@router.patch("/{video_id}/status", response_model=VideoRecord)
async def update_video_status(
    video_id: str,
    payload: VideoStatusUpdateRequest,
    request: Request,
) -> dict:
    """Update a video processing status."""
    sqlite = get_sqlite(request)
    video = await sqlite.update_video_status(video_id, payload.status)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video
