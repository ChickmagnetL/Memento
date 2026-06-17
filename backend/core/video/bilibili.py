"""Bilibili soft subtitle fetching helpers."""

from dataclasses import dataclass
import json
import logging
import math
from typing import Callable
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class SubtitleEntry:
    start_seconds: float
    text: str


class BilibiliSubtitleError(Exception):
    pass


def extract_bvid(url: str) -> str | None:
    path_parts = [part for part in urlparse(url).path.split("/") if part]
    try:
        video_index = path_parts.index("video")
    except ValueError:
        return None

    if video_index + 1 >= len(path_parts):
        return None

    candidate = path_parts[video_index + 1]
    if candidate.startswith("BV"):
        return candidate
    return None


def fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
    headers = {"User-Agent": USER_AGENT}
    if referer is not None:
        headers["Referer"] = referer
    if cookie:
        headers["Cookie"] = cookie

    request = Request(url, headers=headers)
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _normalize_subtitle_url(subtitle_url: str, error_message: str) -> str:
    if subtitle_url.startswith("//"):
        subtitle_url = f"https:{subtitle_url}"
    try:
        parsed_subtitle_url = urlparse(subtitle_url)
        parsed_subtitle_url.port
    except ValueError as exc:
        raise BilibiliSubtitleError(error_message) from exc
    if parsed_subtitle_url.scheme not in ("http", "https"):
        raise BilibiliSubtitleError(error_message)
    if parsed_subtitle_url.hostname is None:
        raise BilibiliSubtitleError(error_message)
    return subtitle_url


class BilibiliSubtitleClient:
    def __init__(
        self,
        fetch_json: Callable[[str, str | None, str | None], dict] = fetch_json,
        cookie: str = "",
    ) -> None:
        self.fetch_json = fetch_json
        self.cookie = cookie.strip()

    def fetch(self, video: dict) -> list[SubtitleEntry]:
        source_url = video["url"]
        bvid = extract_bvid(source_url)
        if bvid is None:
            raise BilibiliSubtitleError("Missing BV id in Bilibili URL")

        quoted_bvid = quote(bvid)
        pagelist_url = (
            "https://api.bilibili.com/x/player/pagelist"
            f"?bvid={quoted_bvid}"
        )
        pagelist = self.fetch_json(pagelist_url)
        data = pagelist.get("data") if isinstance(pagelist, dict) else None
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            api_code = pagelist.get("code") if isinstance(pagelist, dict) else None
            api_msg = pagelist.get("message") if isinstance(pagelist, dict) else None
            detail = f" (B站 code={api_code}, message={api_msg!r})" if api_code is not None else ""
            raise BilibiliSubtitleError(f"Malformed Bilibili pagelist response{detail}")
        try:
            cid = data[0]["cid"]
        except (KeyError, TypeError, ValueError) as exc:
            raise BilibiliSubtitleError(
                "Malformed Bilibili pagelist response"
            ) from exc
        if cid is None or cid == "":
            raise BilibiliSubtitleError("Malformed Bilibili pagelist response")
        if isinstance(cid, bool):
            raise BilibiliSubtitleError("Malformed Bilibili pagelist response")
        if isinstance(cid, int):
            if cid < 0:
                raise BilibiliSubtitleError("Malformed Bilibili pagelist response")
            cid = str(cid)
        elif not isinstance(cid, str) or not cid.isdigit():
            raise BilibiliSubtitleError("Malformed Bilibili pagelist response")

        player_url = (
            "https://api.bilibili.com/x/player/v2"
            f"?bvid={quoted_bvid}&cid={cid}"
        )
        player = self.fetch_json(player_url, source_url, self.cookie or None)
        if not isinstance(player, dict):
            raise BilibiliSubtitleError("Malformed Bilibili player response")
        data = player.get("data", {})
        if not isinstance(data, dict):
            raise BilibiliSubtitleError("Malformed Bilibili player response")
        subtitle = data.get("subtitle", {})
        if not isinstance(subtitle, dict):
            raise BilibiliSubtitleError("Malformed Bilibili player response")
        subtitles = subtitle.get("subtitles", [])
        if not isinstance(subtitles, list):
            raise BilibiliSubtitleError("Malformed Bilibili player response")

        if subtitles:
            first_subtitle = subtitles[0]
            if not isinstance(first_subtitle, dict):
                raise BilibiliSubtitleError("Malformed Bilibili player response")
            subtitle_url = first_subtitle.get("subtitle_url")
            if subtitle_url is None or subtitle_url == "":
                return []
            if not isinstance(subtitle_url, str):
                raise BilibiliSubtitleError("Malformed Bilibili player response")
            subtitle_url = _normalize_subtitle_url(
                subtitle_url,
                "Malformed Bilibili player response",
            )
            return self._fetch_subtitle_body(subtitle_url, source_url)

        logger.warning(
            "Bilibili player/v2 returned no subtitles for %s, may need login cookie",
            bvid,
        )
        return []

    def _fetch_subtitle_body(
        self,
        subtitle_url: str,
        source_url: str,
    ) -> list[SubtitleEntry]:
        subtitle_body = self.fetch_json(subtitle_url, source_url)
        if not isinstance(subtitle_body, dict):
            raise BilibiliSubtitleError("Malformed Bilibili subtitle body response")
        body = subtitle_body.get("body", [])
        if not isinstance(body, list):
            raise BilibiliSubtitleError("Malformed Bilibili subtitle body response")
        entries = []
        for item in body:
            if not isinstance(item, dict) or "from" not in item:
                raise BilibiliSubtitleError(
                    "Malformed Bilibili subtitle body response"
                )
            raw_from = item["from"]
            if isinstance(raw_from, bool):
                raise BilibiliSubtitleError(
                    "Malformed Bilibili subtitle body response"
                )
            try:
                start_seconds = float(raw_from)
            except (TypeError, ValueError) as exc:
                raise BilibiliSubtitleError(
                    "Malformed Bilibili subtitle body response"
                ) from exc
            if not math.isfinite(start_seconds):
                raise BilibiliSubtitleError(
                    "Malformed Bilibili subtitle body response"
                )
            if start_seconds < 0:
                raise BilibiliSubtitleError(
                    "Malformed Bilibili subtitle body response"
                )
            content = item.get("content", "")
            if not isinstance(content, str):
                raise BilibiliSubtitleError(
                    "Malformed Bilibili subtitle body response"
                )
            text = content.strip()
            if text:
                entries.append(
                    SubtitleEntry(
                        start_seconds=start_seconds,
                        text=text,
                    )
                )
        return entries
