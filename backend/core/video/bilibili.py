"""Bilibili soft subtitle fetching helpers."""

from dataclasses import dataclass
import json
import logging
import math
import ssl
import time
from typing import Callable
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

import certifi

logger = logging.getLogger(__name__)


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

PLAYER_SUBTITLE_RETRY_SECONDS = 10
PLAYER_SUBTITLE_RETRY_INTERVAL_SECONDS = 0.25


@dataclass(frozen=True)
class SubtitleEntry:
    start_seconds: float
    text: str


REASON_OK = "ok"
REASON_NOT_LOGGED_IN = "not_logged_in"
REASON_AUTH_EXPIRED = "auth_expired"
REASON_NO_SUBTITLES = "no_subtitles"
REASON_SUBTITLE_UNSTABLE = "subtitle_unstable"
REASON_NON_CHINESE_SUBTITLES = "non_chinese_subtitles"
REASON_UPSTREAM_ERROR = "upstream_error"

REASON_MESSAGES = {
    REASON_OK: "Subtitles available.",
    REASON_NOT_LOGGED_IN: (
        "Bilibili login is required to fetch subtitles. "
        "Please sign in on the Login page."
    ),
    REASON_AUTH_EXPIRED: (
        "Bilibili login expired. Please sign in again on the Login page."
    ),
    REASON_NO_SUBTITLES: (
        "This Bilibili video has no usable soft subtitles. "
        "You can transcribe it with ASR instead."
    ),
    REASON_SUBTITLE_UNSTABLE: (
        "Bilibili subtitles were temporarily unavailable. "
        "Retry, or transcribe with ASR."
    ),
    REASON_NON_CHINESE_SUBTITLES: (
        "No Chinese soft subtitles found, but official subtitles are available in other languages. "
        "You can import those official subtitles or use ASR instead."
    ),
    REASON_UPSTREAM_ERROR: (
        "Could not fetch Bilibili subtitles due to a temporary upstream error. "
        "Retry, or transcribe with ASR."
    ),
}


@dataclass(frozen=True)
class SubtitleFetchOutcome:
    entries: list[SubtitleEntry]
    reason: str
    message: str
    available_languages: tuple[str, ...] = ()
    source: str | None = None

    @property
    def has_subtitles(self) -> bool:
        return self.reason == REASON_OK and bool(self.entries)


class BilibiliSubtitleError(Exception):
    def __init__(self, message: str, *, reason: str = REASON_UPSTREAM_ERROR) -> None:
        super().__init__(message)
        self.reason = reason


def cookie_is_usable(cookie: str | None) -> bool:
    if not cookie or not cookie.strip():
        return False
    # Accept SESSDATA= anywhere in the header-style cookie string.
    parts = [p.strip() for p in cookie.split(";") if p.strip()]
    for part in parts:
        name, _, value = part.partition("=")
        if name.strip() == "SESSDATA" and value.strip():
            return True
    return False


def outcome_for(
    reason: str,
    entries: list[SubtitleEntry] | None = None,
    *,
    available_languages: tuple[str, ...] | list[str] | None = None,
    source: str | None = None,
) -> SubtitleFetchOutcome:
    return SubtitleFetchOutcome(
        entries=list(entries or []),
        reason=reason,
        message=REASON_MESSAGES[reason],
        available_languages=tuple(available_languages or ()),
        source=source,
    )


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


def extract_page_number(url: str) -> int:
    """Return the requested Bilibili page number, defaulting to page 1."""
    values = parse_qs(urlparse(url).query).get("p")
    if values and values[0].isdigit():
        page = int(values[0])
        if page > 0:
            return page
    return 1


def fetch_json(url: str, referer: str | None = None, cookie: str | None = None) -> dict:
    headers = {
        "User-Agent": USER_AGENT,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if referer is not None:
        headers["Referer"] = referer
    if cookie:
        headers["Cookie"] = cookie

    request = Request(url, headers=headers)
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    with urlopen(request, timeout=10, context=ssl_context) as response:
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


def _extract_prod_path_prefix(subtitle_url: str) -> str | None:
    path = urlparse(subtitle_url).path
    marker = "/prod/"
    if marker not in path:
        return None
    suffix = path.split(marker, 1)[1]
    if not suffix:
        return None
    prod_segment = suffix.split("/", 1)[0]
    return prod_segment or None


def _is_wrong_aid_cid_prod(prod_segment: str, expected_prefix: str) -> bool:
    if not prod_segment or not expected_prefix:
        return False
    if prod_segment.startswith(expected_prefix):
        return False
    # Wrong-video aid+cid embedding: the first len(expected_prefix) chars are ALL digits
    # and not equal to expected_prefix. Pure hex hashes with letters in that window are OK.
    head = prod_segment[: len(expected_prefix)]
    return head.isdigit()


def _should_reject_ai_prod_prefix(prod_segment: str, expected_prefix: str) -> bool:
    """True only when URL embeds a different aid+cid (cross-video risk)."""
    return _is_wrong_aid_cid_prod(prod_segment, expected_prefix)


def _track_has_url(track: dict) -> bool:
    url = track.get("subtitle_url")
    return isinstance(url, str) and bool(url)


def _is_automatic_track(track: dict) -> bool:
    lan = track.get("lan", "")
    if isinstance(lan, str) and lan.startswith("ai-"):
        return True
    return any(
        track.get(key) not in (None, 0, False)
        for key in ("type", "ai_type", "ai_status")
    )


def _subtitle_entries_are_suspicious(
    entries: list[SubtitleEntry], duration
) -> bool:
    if len(entries) >= 3:
        starts = [entry.start_seconds for entry in entries]
        if max(starts) - min(starts) <= 1.0:
            return True

    if isinstance(duration, (int, float)) and not isinstance(duration, bool):
        if entries and entries[-1].start_seconds > float(duration) + 5.0:
            return True
    return False


def _track_prod_segment(track: dict) -> str | None:
    url = track.get("subtitle_url")
    if not isinstance(url, str) or not url:
        return None
    if url.startswith("//"):
        url = f"https:{url}"
    return _extract_prod_path_prefix(url)


def _is_usable_ai_prod(prod: str | None, expected_prefix: str | None) -> bool:
    """True if prod is HASH or MATCH; False for DIGIT_OTHER."""
    if prod is None:
        # non-aisubtitle URLs without /prod/ — treat as usable
        return True
    if not expected_prefix:
        return True
    if prod.startswith(expected_prefix):
        return True  # MATCH
    return not _is_wrong_aid_cid_prod(prod, expected_prefix)  # reject DIGIT_OTHER only


def _non_chinese_language_codes(tracks: list[dict]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for track in tracks:
        lan = track.get("lan")
        if lan == "ai-en" and lan not in seen:
            seen.add(lan)
            ordered.append(lan)
    for track in tracks:
        lan = track.get("lan")
        if isinstance(lan, str) and lan not in seen:
            seen.add(lan)
            ordered.append(lan)
    return tuple(ordered)


def _prefer_non_chinese_track(tracks: list[dict]) -> dict:
    for track in tracks:
        if track.get("lan") == "ai-en":
            return track
    return tracks[0]


def _fallback_subtitle_track(subtitles: list) -> dict | None:
    """Preserve empty/invalid-url selection so type checks can still raise."""
    for track in subtitles:
        if not isinstance(track, dict):
            continue
        lan = track.get("lan", "")
        if isinstance(lan, str) and not lan.startswith("ai-"):
            return track
    for track in subtitles:
        if not isinstance(track, dict):
            continue
        lan = track.get("lan", "")
        if isinstance(lan, str) and lan.startswith("ai-"):
            return track
    return None


class BilibiliSubtitleClient:
    def __init__(
        self,
        fetch_json: Callable[[str, str | None, str | None], dict] = fetch_json,
        cookie: str = "",
    ) -> None:
        self.fetch_json = fetch_json
        self.cookie = " ".join(cookie.split())

    def fetch_outcome(
        self, video: dict, *, allow_non_chinese: bool = False
    ) -> SubtitleFetchOutcome:
        if not cookie_is_usable(self.cookie):
            return outcome_for(REASON_NOT_LOGGED_IN)
        try:
            return self._fetch_outcome_uncached(
                video, allow_non_chinese=allow_non_chinese
            )
        except BilibiliSubtitleError as exc:
            reason = getattr(exc, "reason", REASON_UPSTREAM_ERROR)
            if reason not in REASON_MESSAGES:
                reason = REASON_UPSTREAM_ERROR
            message = str(exc) if str(exc) else REASON_MESSAGES[reason]
            # Prefer stable user messages for known reasons.
            if reason in (
                REASON_NOT_LOGGED_IN,
                REASON_AUTH_EXPIRED,
                REASON_NO_SUBTITLES,
                REASON_SUBTITLE_UNSTABLE,
                REASON_NON_CHINESE_SUBTITLES,
            ):
                message = REASON_MESSAGES[reason]
            return SubtitleFetchOutcome(
                entries=[],
                reason=reason,
                message=message,
                available_languages=(),
            )
        except OSError:
            return outcome_for(REASON_UPSTREAM_ERROR)

    def fetch_metadata(self, bvid: str) -> dict | None:
        metadata_url = (
            "https://api.bilibili.com/x/web-interface/view"
            f"?bvid={quote(bvid)}"
        )
        try:
            response = self.fetch_json(metadata_url)
            if not isinstance(response, dict) or response.get("code") != 0:
                return None
            data = response["data"]
            if not isinstance(data, dict):
                return None
            owner = data["owner"]
            if not isinstance(owner, dict):
                return None
            title = data["title"]
            duration = data["duration"]
            author = owner["name"]
            author_id = owner["mid"]
        except (KeyError, TypeError, ValueError, OSError):
            return None
        if not isinstance(title, str):
            return None
        if not isinstance(author, str):
            return None
        if isinstance(duration, bool) or not isinstance(duration, int):
            return None
        if isinstance(author_id, bool):
            return None
        if isinstance(author_id, int):
            author_id = str(author_id)
        elif not isinstance(author_id, str) or not author_id:
            return None

        return {
            "title": title,
            "author": author,
            "author_id": author_id,
            "duration": duration,
        }

    def fetch(
        self, video: dict, *, allow_non_chinese: bool = False
    ) -> list[SubtitleEntry]:
        outcome = self._fetch_outcome_uncached(
            video, allow_non_chinese=allow_non_chinese
        )
        if outcome.reason == REASON_OK:
            return outcome.entries
        if outcome.reason in (
            REASON_NO_SUBTITLES,
            REASON_SUBTITLE_UNSTABLE,
            REASON_NON_CHINESE_SUBTITLES,
        ):
            return []
        raise BilibiliSubtitleError(outcome.message, reason=outcome.reason)

    def _fetch_outcome_uncached(
        self, video: dict, *, allow_non_chinese: bool = False
    ) -> SubtitleFetchOutcome:
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
        if isinstance(pagelist, dict) and pagelist.get("code") == -101:
            return outcome_for(REASON_AUTH_EXPIRED)
        data = pagelist.get("data") if isinstance(pagelist, dict) else None
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            api_code = pagelist.get("code") if isinstance(pagelist, dict) else None
            api_msg = pagelist.get("message") if isinstance(pagelist, dict) else None
            detail = f" (B站 code={api_code}, message={api_msg!r})" if api_code is not None else ""
            raise BilibiliSubtitleError(f"Malformed Bilibili pagelist response{detail}")
        page_number = extract_page_number(source_url)
        page_data = next(
            (
                item
                for item in data
                if isinstance(item, dict) and item.get("page") == page_number
            ),
            data[0] if page_number == 1 else None,
        )
        if page_data is None:
            raise BilibiliSubtitleError(
                f"Bilibili page {page_number} is not available"
            )
        try:
            cid = page_data["cid"]
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
        start = time.monotonic()
        saw_unstable_subtitle = False
        official_fingerprint_counts: dict[tuple, int] = {}
        while time.monotonic() - start < PLAYER_SUBTITLE_RETRY_SECONDS:
            player = self.fetch_json(player_url, source_url, self.cookie or None)
            if not isinstance(player, dict):
                raise BilibiliSubtitleError("Malformed Bilibili player response")
            if player.get("code") == -101:
                return outcome_for(REASON_AUTH_EXPIRED)
            data = player.get("data", {})
            if not isinstance(data, dict):
                raise BilibiliSubtitleError("Malformed Bilibili player response")
            response_bvid = data.get("bvid")
            response_cid = data.get("cid")
            if (
                response_bvid is not None
                and response_bvid != bvid
            ) or (
                response_cid is not None
                and str(response_cid) != cid
            ):
                saw_unstable_subtitle = True
                time.sleep(PLAYER_SUBTITLE_RETRY_INTERVAL_SECONDS)
                continue
            subtitle = data.get("subtitle", {})
            if not isinstance(subtitle, dict):
                raise BilibiliSubtitleError("Malformed Bilibili player response")
            subtitles = subtitle.get("subtitles", [])
            if not isinstance(subtitles, list):
                raise BilibiliSubtitleError("Malformed Bilibili player response")

            if not subtitles:
                time.sleep(PLAYER_SUBTITLE_RETRY_INTERVAL_SECONDS)
                continue

            expected_prefix: str | None = None
            aid_for_prefix = data.get("aid")
            if isinstance(aid_for_prefix, bool):
                expected_prefix = None
            elif isinstance(aid_for_prefix, int) and aid_for_prefix >= 0:
                expected_prefix = f"{aid_for_prefix}{cid}"
            elif isinstance(aid_for_prefix, str) and aid_for_prefix.isdigit():
                expected_prefix = f"{aid_for_prefix}{cid}"

            human_with_url: list[dict] = []
            usable_ai_zh: list[dict] = []
            usable_non_zh: list[dict] = []
            digit_other_ai = False
            for track in subtitles:
                if not isinstance(track, dict):
                    continue
                lan = track.get("lan", "")
                if not isinstance(lan, str):
                    continue
                if not _is_automatic_track(track):
                    if _track_has_url(track):
                        human_with_url.append(track)
                    continue
                if not _track_has_url(track):
                    continue
                prod = _track_prod_segment(track)
                if not _is_usable_ai_prod(prod, expected_prefix):
                    digit_other_ai = True
                    continue
                if lan == "ai-zh" or lan.lower().startswith("zh"):
                    usable_ai_zh.append(track)
                else:
                    usable_non_zh.append(track)

            selected_subtitle: dict | None = None
            if human_with_url:
                selected_subtitle = human_with_url[0]
            elif usable_ai_zh:
                selected_subtitle = usable_ai_zh[0]
            elif usable_non_zh:
                if not allow_non_chinese:
                    return outcome_for(
                        REASON_NON_CHINESE_SUBTITLES,
                        available_languages=_non_chinese_language_codes(
                            usable_non_zh
                        ),
                    )
                selected_subtitle = _prefer_non_chinese_track(usable_non_zh)
            elif digit_other_ai:
                saw_unstable_subtitle = True
                time.sleep(PLAYER_SUBTITLE_RETRY_INTERVAL_SECONDS)
                continue
            else:
                selected_subtitle = _fallback_subtitle_track(subtitles)

            if selected_subtitle is None:
                raise BilibiliSubtitleError("Malformed Bilibili player response")
            subtitle_url = selected_subtitle.get("subtitle_url")
            if subtitle_url is None or subtitle_url == "":
                time.sleep(PLAYER_SUBTITLE_RETRY_INTERVAL_SECONDS)
                continue
            if not isinstance(subtitle_url, str):
                raise BilibiliSubtitleError("Malformed Bilibili player response")
            subtitle_url = _normalize_subtitle_url(
                subtitle_url,
                "Malformed Bilibili player response",
            )

            parsed_subtitle_url = urlparse(subtitle_url)
            prod_path_prefix = _extract_prod_path_prefix(subtitle_url)
            lan = selected_subtitle.get("lan", "")

            if not _is_automatic_track(selected_subtitle):
                fingerprint = (
                    data.get("aid"),
                    data.get("bvid"),
                    data.get("cid"),
                    selected_subtitle.get(
                        "id_str", selected_subtitle.get("id")
                    ),
                    lan,
                    parsed_subtitle_url.scheme,
                    parsed_subtitle_url.hostname,
                    parsed_subtitle_url.port,
                    parsed_subtitle_url.path,
                )
                count = official_fingerprint_counts.get(fingerprint, 0) + 1
                official_fingerprint_counts[fingerprint] = count
                if count < 2:
                    time.sleep(PLAYER_SUBTITLE_RETRY_INTERVAL_SECONDS)
                    continue

            if (
                _is_automatic_track(selected_subtitle)
                and parsed_subtitle_url.hostname == "aisubtitle.hdslb.com"
                and prod_path_prefix is not None
            ):
                aid = data.get("aid")
                if isinstance(aid, bool):
                    raise BilibiliSubtitleError("Malformed Bilibili player response")
                if isinstance(aid, int):
                    if aid < 0:
                        raise BilibiliSubtitleError("Malformed Bilibili player response")
                    aid = str(aid)
                elif not isinstance(aid, str) or not aid.isdigit():
                    raise BilibiliSubtitleError("Malformed Bilibili player response")

                expected_prefix = f"{aid}{cid}"
                if _should_reject_ai_prod_prefix(prod_path_prefix, expected_prefix):
                    saw_unstable_subtitle = True
                    time.sleep(PLAYER_SUBTITLE_RETRY_INTERVAL_SECONDS)
                    continue

            entries = self._fetch_subtitle_body(subtitle_url, source_url)
            if entries:
                if _subtitle_entries_are_suspicious(
                    entries, page_data.get("duration")
                ):
                    return outcome_for(REASON_SUBTITLE_UNSTABLE)
                source = (
                    "automatic"
                    if _is_automatic_track(selected_subtitle)
                    else "official"
                )
                return outcome_for(REASON_OK, entries, source=source)
            return outcome_for(REASON_NO_SUBTITLES)

        logger.warning(
            "Bilibili player/v2 did not return a usable subtitle for %s "
            "before retry timeout",
            bvid,
        )
        if saw_unstable_subtitle:
            return outcome_for(REASON_SUBTITLE_UNSTABLE)
        return outcome_for(REASON_NO_SUBTITLES)

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
