"""Video processing settings API."""

from fastapi import APIRouter

from config.settings import get_settings

router = APIRouter(prefix="/api/video-processing", tags=["video-processing"])


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
