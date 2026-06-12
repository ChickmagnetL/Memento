"""Bilibili soft subtitle fetching helpers."""

from dataclasses import dataclass
import json
import math
from typing import Callable
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen


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


def fetch_bytes(
    url: str,
    referer: str | None = None,
    cookie: str | None = None,
) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    if referer is not None:
        headers["Referer"] = referer
    if cookie:
        headers["Cookie"] = cookie

    request = Request(url, headers=headers)
    with urlopen(request, timeout=10) as response:
        return response.read()


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


def _read_varint(payload: bytes, offset: int) -> tuple[int, int] | None:
    value = 0
    shift = 0
    while offset < len(payload):
        byte = payload[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7
        if shift >= 64:
            return None
    return None


def _is_subtitle_url(candidate: str) -> bool:
    if "subtitle.bilibili.com" in candidate:
        return True
    if candidate.startswith("//subtitle."):
        return True
    if candidate.startswith(("http://", "https://")) and "subtitle" in candidate:
        return True
    return False


def _extract_subtitle_url_from_protobuf(
    payload: bytes,
    depth: int = 0,
) -> str | None:
    if depth > 4:
        return None

    offset = 0
    while offset < len(payload):
        key = _read_varint(payload, offset)
        if key is None:
            return None
        tag, offset = key
        wire_type = tag & 0x07

        if wire_type == 0:
            value = _read_varint(payload, offset)
            if value is None:
                return None
            _ignored, offset = value
        elif wire_type == 1:
            offset += 8
        elif wire_type == 2:
            length_value = _read_varint(payload, offset)
            if length_value is None:
                return None
            length, offset = length_value
            end = offset + length
            if end > len(payload):
                return None
            field_payload = payload[offset:end]
            offset = end
            try:
                candidate = field_payload.decode("utf-8")
            except UnicodeDecodeError:
                candidate = ""
            if _is_subtitle_url(candidate):
                return candidate
            nested_candidate = _extract_subtitle_url_from_protobuf(
                field_payload,
                depth + 1,
            )
            if nested_candidate is not None:
                return nested_candidate
        elif wire_type == 5:
            offset += 4
        else:
            return None

        if offset > len(payload):
            return None
    return None


class BilibiliSubtitleClient:
    def __init__(
        self,
        fetch_json: Callable[[str, str | None, str | None], dict] = fetch_json,
        fetch_bytes: Callable[[str, str | None, str | None], bytes] = fetch_bytes,
        bilibili_cookie: str = "",
    ) -> None:
        self.fetch_json = fetch_json
        self.fetch_bytes = fetch_bytes
        self.bilibili_cookie = bilibili_cookie.strip()

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
            raise BilibiliSubtitleError("Malformed Bilibili pagelist response")
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
        player = self.fetch_json(player_url, source_url, self.bilibili_cookie or None)
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

        # When cookie is present, player/v2 already returns AI subtitles on
        # aisubtitle.hdslb.com (the _fetch_ai_subtitles path uses the now-dead
        # subtitle.bilibili.com domain, so we only use it as a last-resort
        # fallback when player/v2 returns no subtitles at all).
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

        # Fall back to the separate AI subtitle API (requires cookie).
        if self.bilibili_cookie:
            ai_entries = self._fetch_ai_subtitles(bvid, cid, source_url)
            if ai_entries:
                return ai_entries

        return []

    def _fetch_ai_subtitles(
        self,
        bvid: str,
        cid: str,
        source_url: str,
    ) -> list[SubtitleEntry]:
        if not self.bilibili_cookie:
            return []

        try:
            view_url = (
                "https://api.bilibili.com/x/web-interface/view"
                f"?bvid={quote(bvid)}"
            )
            view_response = self.fetch_json(view_url)
            view_data = (
                view_response.get("data")
                if isinstance(view_response, dict)
                else None
            )
            if not isinstance(view_data, dict):
                return []
            aid = view_data.get("aid")
            if isinstance(aid, bool):
                return []
            if isinstance(aid, int):
                if aid < 0:
                    return []
                aid = str(aid)
            elif not isinstance(aid, str) or not aid.isdigit():
                return []

            ai_query = urlencode(
                {
                    "oid": cid,
                    "pid": aid,
                    "context_ext": '{"video_type":1}',
                    "type": "1",
                    "cur_production_type": "0",
                    "preferred_language": "ai-zh",
                }
            )
            ai_url = f"https://api.bilibili.com/x/v2/subtitle/web/view?{ai_query}"
            payload = self.fetch_bytes(ai_url, source_url, self.bilibili_cookie)
            subtitle_url = _extract_subtitle_url_from_protobuf(payload)
            if subtitle_url is None:
                return []
            try:
                subtitle_url = _normalize_subtitle_url(
                    subtitle_url,
                    "Malformed Bilibili AI subtitle response",
                )
            except BilibiliSubtitleError:
                return []
            return self._fetch_subtitle_body(subtitle_url, source_url)
        except OSError:
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
