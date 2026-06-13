"""Memento Douyin Fetcher: lightweight proxy for F2 video resolution.

Runs in its own venv because f2 requires pydantic==2.9.* which
conflicts with the main backend (>=2.12). Receives an aweme_id
and optional cookie, returns the best playable video URL.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Memento Douyin Fetcher", version="0.1.0")


class ResolveRequest(BaseModel):
    aweme_id: str
    cookie: str = ""


class ResolveResponse(BaseModel):
    video_url: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _build_cookie(cookie: str) -> str:
    if cookie:
        return cookie
    from f2.apps.douyin.utils import TokenManager

    return f"ttwid={TokenManager.gen_ttwid()};"


def _extract_video_url(detail: dict) -> str:
    video = detail.get("video") or {}

    bit_rates = video.get("bit_rate") or []
    for item in bit_rates:
        play_addr = (item or {}).get("play_addr") or {}
        urls = play_addr.get("url_list") or []
        if urls:
            return urls[0]

    play_addr = video.get("play_addr") or {}
    urls = play_addr.get("url_list") or []
    if urls:
        return urls[0]

    raise HTTPException(status_code=502, detail="No playable video URL found in response")


@app.post("/resolve", response_model=ResolveResponse)
async def resolve(payload: ResolveRequest) -> dict:
    try:
        from f2.apps.douyin.handler import DouyinHandler
        from f2.apps.douyin.utils import ClientConfManager
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="F2 not installed. Run: bash setup.sh",
        ) from exc

    cookie = _build_cookie(payload.cookie)
    client_conf = ClientConfManager()

    handler = DouyinHandler({
        "cookie": cookie,
        "headers": dict(client_conf.headers()),
        "proxies": client_conf.proxies(),
        "timeout": 10,
        "max_retries": 2,
    })
    handler.enable_bark = False

    try:
        video = await handler.fetch_one_video(payload.aweme_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    raw = video._to_raw()
    detail = raw.get("aweme_detail") or {}
    video_url = _extract_video_url(detail)

    return {"video_url": video_url}
