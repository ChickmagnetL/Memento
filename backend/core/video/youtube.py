"""YouTube metadata and subtitle helpers."""

from __future__ import annotations

from html import unescape
import json
import logging
import math
import re
from typing import Callable
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

import yt_dlp

from core.video.bilibili import (
    REASON_NON_CHINESE_SUBTITLES,
    REASON_NO_SUBTITLES,
    REASON_OK,
    REASON_UPSTREAM_ERROR,
    SubtitleEntry,
    SubtitleFetchOutcome,
)


logger = logging.getLogger(__name__)

YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

YOUTUBE_REASON_MESSAGES = {
    REASON_OK: "Subtitles available.",
    REASON_NO_SUBTITLES: (
        "This YouTube video has no usable creator or automatic subtitles. "
        "You can transcribe it with ASR instead."
    ),
    REASON_NON_CHINESE_SUBTITLES: (
        "No Chinese subtitles were found, but YouTube subtitles are available "
        "in other languages. You can import those subtitles or use ASR instead."
    ),
    REASON_UPSTREAM_ERROR: (
        "Could not fetch YouTube subtitles due to a temporary upstream error. "
        "Retry, or transcribe with ASR."
    ),
}


class YouTubeError(Exception):
    pass


class YouTubeSubtitleError(YouTubeError):
    def __init__(self, message: str, *, reason: str = REASON_UPSTREAM_ERROR) -> None:
        super().__init__(message)
        self.reason = reason


def extract_video_id(url: str) -> str | None:
    """Return the video ID for a supported single-video YouTube URL."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.hostname or "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    candidate: str | None = None
    if host in ("youtu.be", "www.youtu.be"):
        if len(path_parts) == 1:
            candidate = path_parts[0]
    elif host == "youtube.com" or host.endswith(".youtube.com"):
        if parsed.path.rstrip("/") == "/watch":
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        elif len(path_parts) == 2 and path_parts[0] == "shorts":
            candidate = path_parts[1]

    if isinstance(candidate, str) and YOUTUBE_ID_RE.fullmatch(candidate):
        return candidate
    return None


def extract_info(url: str) -> dict:
    """Probe one YouTube video without downloading media."""
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)
    if not isinstance(info, dict):
        raise YouTubeError("YouTube returned invalid video metadata")
    return info


def fetch_bytes(url: str, headers: dict[str, str] | None = None) -> bytes:
    request_headers = {"User-Agent": USER_AGENT}
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=15) as response:
        return response.read()


def youtube_outcome(
    reason: str,
    entries: list[SubtitleEntry] | None = None,
    *,
    available_languages: tuple[str, ...] | list[str] | None = None,
) -> SubtitleFetchOutcome:
    return SubtitleFetchOutcome(
        entries=list(entries or []),
        reason=reason,
        message=YOUTUBE_REASON_MESSAGES[reason],
        available_languages=tuple(available_languages or ()),
    )


def _clean_string(value) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _is_chinese_language(language: str) -> bool:
    normalized = language.lower().replace("_", "-")
    return normalized == "zh" or normalized.startswith("zh-")


def _usable_formats(formats) -> list[dict]:
    if not isinstance(formats, list):
        return []
    usable = []
    for item in formats:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        ext = item.get("ext")
        if (
            isinstance(url, str)
            and urlparse(url).scheme in ("http", "https")
            and ext in ("json3", "vtt")
        ):
            usable.append(item)
    return usable


def _usable_tracks(
    raw_tracks, *, exclude_translated: bool = False
) -> dict[str, list[dict]]:
    if not isinstance(raw_tracks, dict):
        return {}
    tracks = {}
    for language, formats in raw_tracks.items():
        if not isinstance(language, str) or language == "live_chat":
            continue
        usable = _usable_formats(formats)
        if exclude_translated:
            usable = [
                item
                for item in usable
                if not parse_qs(urlparse(item["url"]).query).get("tlang")
            ]
        if usable:
            tracks[language] = usable
    return tracks


def _available_languages(
    tracks: dict[str, list[dict]], *, chinese: bool | None = None
) -> tuple[str, ...]:
    languages = []
    for language in tracks:
        public_language = language.removesuffix("-orig")
        if chinese is not None and _is_chinese_language(public_language) != chinese:
            continue
        if public_language not in languages:
            languages.append(public_language)
    return tuple(languages)


def _ordered_languages(
    tracks: dict[str, list[dict]], preferred_language: str | None
) -> list[str]:
    selected = _select_language(tracks, preferred_language)
    return [
        selected,
        *(language for language in tracks if language != selected),
    ]


def _select_language(
    tracks: dict[str, list[dict]], preferred_language: str | None
) -> str:
    chinese_priority = ("zh-Hans", "zh-CN", "zh", "zh-Hant", "zh-TW")
    for language in chinese_priority:
        if language in tracks:
            return language
    for language in tracks:
        if _is_chinese_language(language):
            return language
    if preferred_language in tracks:
        return preferred_language
    if "en" in tracks:
        return "en"
    return next(iter(tracks))


def _ordered_formats(formats: list[dict]) -> list[dict]:
    return sorted(formats, key=lambda item: 0 if item.get("ext") == "json3" else 1)


def _parse_json3(payload: bytes) -> list[SubtitleEntry]:
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise YouTubeSubtitleError("Malformed YouTube subtitle response") from exc
    events = data.get("events") if isinstance(data, dict) else None
    if not isinstance(events, list):
        raise YouTubeSubtitleError("Malformed YouTube subtitle response")

    entries = []
    for event in events:
        if not isinstance(event, dict):
            continue
        raw_start = event.get("tStartMs")
        segments = event.get("segs")
        if isinstance(raw_start, bool) or not isinstance(raw_start, (int, float)):
            continue
        if not math.isfinite(raw_start) or raw_start < 0:
            continue
        if not isinstance(segments, list):
            continue
        text = "".join(
            segment.get("utf8", "")
            for segment in segments
            if isinstance(segment, dict) and isinstance(segment.get("utf8", ""), str)
        )
        text = " ".join(text.split())
        if text:
            entries.append(
                SubtitleEntry(start_seconds=float(raw_start) / 1000, text=text)
            )
    return entries


_VTT_TIMESTAMP_RE = re.compile(
    r"^(?:(?P<hours>\d+):)?(?P<minutes>\d{2}):(?P<seconds>\d{2})"
    r"[.,](?P<millis>\d{3})"
)


def _parse_vtt(payload: bytes) -> list[SubtitleEntry]:
    try:
        content = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise YouTubeSubtitleError("Malformed YouTube subtitle response") from exc

    entries = []
    blocks = re.split(r"\r?\n\s*\r?\n", content)
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timestamp_index = next(
            (index for index, line in enumerate(lines) if "-->" in line), None
        )
        if timestamp_index is None:
            continue
        match = _VTT_TIMESTAMP_RE.match(
            lines[timestamp_index].split("-->", 1)[0].strip()
        )
        if match is None:
            continue
        start_seconds = (
            int(match.group("hours") or 0) * 3600
            + int(match.group("minutes")) * 60
            + int(match.group("seconds"))
            + int(match.group("millis")) / 1000
        )
        text = " ".join(lines[timestamp_index + 1 :])
        text = unescape(re.sub(r"<[^>]+>", "", text)).strip()
        if text:
            entries.append(SubtitleEntry(start_seconds=start_seconds, text=text))
    return entries


class YouTubeSubtitleClient:
    def __init__(
        self,
        *,
        info_extractor: Callable[[str], dict] = extract_info,
        content_fetcher: Callable[[str, dict[str, str] | None], bytes] = fetch_bytes,
    ) -> None:
        self.info_extractor = info_extractor
        self.content_fetcher = content_fetcher

    def fetch_metadata(self, url: str) -> dict:
        try:
            info = self.info_extractor(url)
        except YouTubeError:
            raise
        except (OSError, RuntimeError, ValueError, yt_dlp.utils.DownloadError) as exc:
            raise YouTubeError("Could not fetch YouTube video metadata") from exc
        if not isinstance(info, dict) or info.get("_type") == "playlist":
            raise YouTubeError("YouTube returned invalid video metadata")
        if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
            raise YouTubeError("Live streams and premieres are not supported")

        video_id = _clean_string(info.get("id"))
        title = _clean_string(info.get("title"))
        author = _clean_string(info.get("channel")) or _clean_string(
            info.get("uploader")
        )
        author_id = _clean_string(info.get("channel_id")) or _clean_string(
            info.get("uploader_id")
        )
        raw_duration = info.get("duration")
        if (
            video_id is None
            or not YOUTUBE_ID_RE.fullmatch(video_id)
            or title is None
            or author is None
            or author_id is None
            or isinstance(raw_duration, bool)
            or not isinstance(raw_duration, (int, float))
            or not math.isfinite(raw_duration)
            or raw_duration < 0
        ):
            raise YouTubeError("YouTube returned incomplete video metadata")

        return {
            "id": video_id,
            "title": title,
            "author": author,
            "author_id": author_id,
            "duration": int(raw_duration),
        }

    def fetch_outcome(
        self, video: dict, *, allow_non_chinese: bool = False
    ) -> SubtitleFetchOutcome:
        try:
            info = self.info_extractor(video["url"])
            if not isinstance(info, dict):
                raise YouTubeSubtitleError("YouTube returned invalid subtitle metadata")

            creator_tracks = _usable_tracks(info.get("subtitles"))
            automatic_tracks = _usable_tracks(
                info.get("automatic_captions"), exclude_translated=True
            )
            tracks = {**automatic_tracks, **creator_tracks}
            if not tracks:
                return youtube_outcome(REASON_NO_SUBTITLES)

            available_non_chinese = _available_languages(tracks, chinese=False)
            languages = _ordered_languages(tracks, _clean_string(info.get("language")))
            if (
                not any(_is_chinese_language(language) for language in languages)
                and not allow_non_chinese
            ):
                return youtube_outcome(
                    REASON_NON_CHINESE_SUBTITLES,
                    available_languages=available_non_chinese,
                )

            had_upstream_error = False
            for language in languages:
                if not allow_non_chinese and not _is_chinese_language(language):
                    continue
                for selected_format in _ordered_formats(tracks[language]):
                    try:
                        headers = selected_format.get("http_headers")
                        if not isinstance(headers, dict):
                            headers = None
                        payload = self.content_fetcher(selected_format["url"], headers)
                        if selected_format["ext"] == "json3":
                            entries = _parse_json3(payload)
                        else:
                            entries = _parse_vtt(payload)
                    except (
                        KeyError,
                        OSError,
                        TypeError,
                        ValueError,
                        YouTubeSubtitleError,
                        yt_dlp.utils.DownloadError,
                    ) as exc:
                        had_upstream_error = True
                        logger.warning(
                            "Could not fetch YouTube subtitle track (%s, %s, %s)",
                            language,
                            selected_format.get("ext"),
                            type(exc).__name__,
                        )
                        continue
                    if entries:
                        return youtube_outcome(REASON_OK, entries)

            if not allow_non_chinese and available_non_chinese:
                return youtube_outcome(
                    REASON_NON_CHINESE_SUBTITLES,
                    available_languages=available_non_chinese,
                )
            if had_upstream_error:
                return youtube_outcome(REASON_UPSTREAM_ERROR)
            return youtube_outcome(REASON_NO_SUBTITLES)
        except YouTubeSubtitleError:
            return youtube_outcome(REASON_UPSTREAM_ERROR)
        except (
            KeyError,
            OSError,
            TypeError,
            ValueError,
            YouTubeError,
            yt_dlp.utils.DownloadError,
        ):
            return youtube_outcome(REASON_UPSTREAM_ERROR)

    def fetch(
        self, video: dict, *, allow_non_chinese: bool = False
    ) -> list[SubtitleEntry]:
        outcome = self.fetch_outcome(video, allow_non_chinese=allow_non_chinese)
        if outcome.reason == REASON_OK:
            return outcome.entries
        if outcome.reason in (REASON_NO_SUBTITLES, REASON_NON_CHINESE_SUBTITLES):
            return []
        raise YouTubeSubtitleError(outcome.message, reason=outcome.reason)
