"""Douyin video helpers: aweme_id resolution and audio downloading."""

from dataclasses import dataclass
import json
import re
import urllib.request
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

from core.video.audio import AudioDownloadError, run_command as default_run_command


AWEME_ID_PATTERN = re.compile(r"^\d{5,}$")


class DouyinError(Exception):
    pass


@dataclass(frozen=True)
class DouyinMetadata:
    video_url: str
    title: str | None = None
    author: str | None = None
    author_id: str | None = None
    duration: int | None = None


def _optional_str(value) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def direct_aweme_id(value: str) -> str | None:
    """Extract an aweme_id without network access, or None."""
    candidate = value.strip()
    if AWEME_ID_PATTERN.match(candidate):
        return candidate

    parsed = urlparse(candidate)
    match = re.search(r"/video/(\d{5,})", parsed.path)
    if match:
        return match.group(1)

    query = parse_qs(parsed.query)
    for key in ("modal_id", "aweme_id", "item_id"):
        values = query.get(key)
        if values and AWEME_ID_PATTERN.match(values[0]):
            return values[0]
    return None


def fetch_bytes(url: str) -> bytes:
    """Download a binary resource with a browser UA."""
    from core.video.bilibili import USER_AGENT

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read()


def _build_http_resolver(endpoint: str) -> Callable[[str, str], DouyinMetadata]:
    """Return a function resolving aweme_id -> metadata via douyin_fetcher."""

    def resolve(aweme_id: str, cookie: str) -> DouyinMetadata:
        data = json.dumps({"aweme_id": aweme_id, "cookie": cookie}).encode()
        req = urllib.request.Request(
            f"{endpoint}/resolve",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read())
        except OSError as exc:
            raise DouyinError(
                f"Douyin fetcher unreachable at {endpoint} "
                "(start it: services/douyin_fetcher/README.md)"
            ) from exc
        if not isinstance(body, dict):
            raise DouyinError("Fetcher returned no video URL")
        url = body.get("video_url")
        if not isinstance(url, str) or not url:
            raise DouyinError("Fetcher returned no video URL")
        return DouyinMetadata(
            video_url=url,
            title=_optional_str(body.get("title")),
            author=_optional_str(body.get("author")),
            author_id=_optional_str(body.get("author_id")),
            duration=_optional_int(body.get("duration")),
        )

    return resolve


class DouyinAudioDownloader:
    """Download a douyin video's audio as WAV (AudioDownloader-compatible)."""

    def __init__(
        self,
        *,
        data_dir,
        keep_videos: bool,
        cookie: str,
        resolve_video_url: Callable[[str, str], str | DouyinMetadata] | None = None,
        fetcher_endpoint: str = "",
        fetch_bytes: Callable[[str], bytes] = fetch_bytes,
        run_command: Callable[[list[str]], None] = default_run_command,
    ) -> None:
        self.data_dir = Path(data_dir).expanduser()
        self.keep_videos = keep_videos
        self.cookie = cookie
        if resolve_video_url is not None:
            self.resolve_video_url = resolve_video_url
        elif fetcher_endpoint:
            self.resolve_video_url = _build_http_resolver(fetcher_endpoint)
        else:
            self.resolve_video_url = None
        self.fetch_bytes = fetch_bytes
        self.run_command = run_command

    @property
    def temp_dir(self) -> Path:
        return self.data_dir / "videos" / "temp"

    def download(self, video: dict) -> Path:
        """Resolve, download, and extract audio for a douyin video."""
        aweme_id = direct_aweme_id(video["url"])
        if aweme_id is None:
            raise DouyinError(
                "Cannot resolve aweme_id from URL; use a full douyin.com link"
            )

        if self.resolve_video_url is None:
            raise DouyinError(
                "Douyin fetcher endpoint not configured "
                "(set video_processing.douyin_fetcher_endpoint)"
            )

        self.temp_dir.mkdir(parents=True, exist_ok=True)
        mp4_path = self.temp_dir / f"{video['id']}.mp4"
        wav_path = self.temp_dir / f"{video['id']}.wav"

        resolved = self.resolve_video_url(aweme_id, self.cookie)
        video_url = resolved.video_url if isinstance(resolved, DouyinMetadata) else resolved
        mp4_path.write_bytes(self.fetch_bytes(video_url))
        try:
            self.run_command(
                [
                    "ffmpeg", "-y",
                    "-i", str(mp4_path),
                    "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                    str(wav_path),
                ]
            )
        finally:
            mp4_path.unlink(missing_ok=True)

        if not wav_path.exists():
            raise AudioDownloadError(f"ffmpeg produced no WAV at {wav_path}")
        return wav_path

    def cleanup(self, wav_path: Path) -> None:
        """Same keep_videos semantics as AudioDownloader.cleanup."""
        if not wav_path.exists():
            return
        if self.keep_videos:
            target = self.data_dir / "videos" / wav_path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            wav_path.replace(target)
        else:
            wav_path.unlink()
