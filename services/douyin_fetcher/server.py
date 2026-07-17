"""Memento Douyin Fetcher: lightweight proxy for F2 video resolution.

Runs in its own venv because f2 requires pydantic==2.9.* which
conflicts with the main backend (>=2.12). Receives an aweme_id
and optional cookie, returns the best playable video URL plus metadata.
"""

from __future__ import annotations

import re

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Memento Douyin Fetcher", version="0.1.1")


class ResolveRequest(BaseModel):
    aweme_id: str
    cookie: str = ""


class ResolveResponse(BaseModel):
    video_url: str
    audio_url: str | None
    title: str | None
    author: str | None
    author_id: str | None
    duration: int | None


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
    if not isinstance(video, dict):
        video = {}

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


def _extract_audio_url(detail: dict) -> str | None:
    music = detail.get("music") or {}
    if not isinstance(music, dict):
        return None
    play_url = music.get("play_url") or {}
    if not isinstance(play_url, dict):
        return None
    urls = play_url.get("url_list") or []
    if urls and isinstance(urls[0], str) and urls[0]:
        return urls[0]
    return None


def _optional_str(value) -> str | None:
    return value if isinstance(value, str) else None


def _title_without_topics(value) -> str | None:
    if not isinstance(value, str):
        return None
    title = re.sub(r"(?<![A-Za-z0-9])#\S+", "", value).strip()
    title = re.sub(r"\s+", " ", title)
    return title or None


def _duration_seconds(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value / 1000)


def _use_fake_ms_token_for_f2_import() -> None:
    """Avoid F2's import-time dependency on the real msToken endpoint."""
    from f2.apps.douyin.utils import TokenManager

    TokenManager.gen_real_msToken = classmethod(lambda cls: cls.gen_false_msToken())


def _build_resolve_payload(detail: dict) -> dict:
    video = detail.get("video") or {}
    if not isinstance(video, dict):
        video = {}
    author = detail.get("author") or {}
    if not isinstance(author, dict):
        author = {}
    duration_ms = video.get("duration")

    return {
        "video_url": _extract_video_url(detail),
        "audio_url": _extract_audio_url(detail),
        "title": _title_without_topics(detail.get("desc")),
        "author": _optional_str(author.get("nickname")),
        "author_id": _optional_str(author.get("sec_uid")),
        "duration": _duration_seconds(duration_ms),
    }


@app.post("/resolve", response_model=ResolveResponse)
async def resolve(payload: ResolveRequest) -> dict:
    try:
        _use_fake_ms_token_for_f2_import()
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

    return _build_resolve_payload(detail)
