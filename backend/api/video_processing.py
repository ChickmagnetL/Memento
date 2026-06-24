"""Video processing settings API."""

from fastapi import APIRouter
from pydantic import BaseModel

from config.settings import get_settings
from core.config_store import ConfigStore

router = APIRouter(prefix="/api/video-processing", tags=["video-processing"])


class VideoProcessingUpdate(BaseModel):
    """Model for video processing cookie updates."""

    bilibili_cookie: str | None = None
    douyin_cookie: str | None = None
    bilibili_refresh_token: str | None = None
    bilibili_cookie_expires_at: int | None = None


@router.get("")
async def get_video_processing_settings() -> dict:
    """
    Get current video processing settings including cookie configuration.

    Returns:
        Dictionary containing:
        - bilibili_cookie: Current Bilibili cookie string
        - douyin_cookie: Current Douyin cookie string
        - bilibili_refresh_token: Bilibili refresh token for auto-refresh
        - bilibili_cookie_expires_at: Unix timestamp of cookie expiration
    """
    settings = get_settings()
    vp = settings.video_processing

    return {
        "bilibili_cookie": vp.bilibili_cookie,
        "douyin_cookie": vp.douyin_cookie,
        "bilibili_refresh_token": getattr(vp, "bilibili_refresh_token", ""),
        "bilibili_cookie_expires_at": getattr(vp, "bilibili_cookie_expires_at", 0),
    }


@router.put("")
async def update_video_processing_settings(payload: VideoProcessingUpdate) -> dict:
    """
    Update video processing cookie configuration in database.

    Args:
        payload: Partial updates for cookie fields

    Returns:
        Updated video processing settings
    """
    settings = get_settings()
    db_path = settings.storage.data_dir / "memento.db"

    # Only update fields that are provided (exclude None values)
    update_dict = payload.model_dump(exclude_none=True)
    if update_dict:
        ConfigStore(db_path).update_video_processing(update_dict)

    return await get_video_processing_settings()
