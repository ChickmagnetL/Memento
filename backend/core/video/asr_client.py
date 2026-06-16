"""Client for the standalone ASR service."""

from typing import Callable

from core.rag.embedding import post_json as default_post_json
from core.video.bilibili import SubtitleEntry

# Transcription of a long video can take minutes on CPU.
ASR_TIMEOUT_SECONDS = 900


class AsrError(Exception):
    pass


class AsrServiceClient:
    def __init__(
        self,
        *,
        endpoint: str,
        post_json: Callable[..., dict] = default_post_json,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.post_json = post_json

    def transcribe(self, audio_path: str, *, language: str) -> list[SubtitleEntry]:
        """Transcribe a local audio file via the ASR service."""
        try:
            response = self.post_json(
                f"{self.endpoint}/transcribe",
                {"audio_path": audio_path, "language": language},
                {"Content-Type": "application/json"},
                timeout=ASR_TIMEOUT_SECONDS,
            )
        except OSError as exc:
            detail = str(exc)
            # Try to read the response body from an HTTPError for more detail.
            try:
                if hasattr(exc, "read"):
                    body = exc.read().decode("utf-8", errors="replace")[:500]
                    detail = f"{exc} — body: {body}"
            except Exception:
                pass
            raise AsrError(
                f"ASR service unreachable at {self.endpoint}: {detail} "
                "(start it: services/asr/README.md)"
            ) from exc

        segments = response.get("segments") if isinstance(response, dict) else None
        if not isinstance(segments, list):
            raise AsrError("Malformed ASR service response")
        entries = []
        for segment in segments:
            if (
                not isinstance(segment, dict)
                or "start_seconds" not in segment
                or "text" not in segment
            ):
                raise AsrError("Malformed ASR service response")
            entries.append(
                SubtitleEntry(
                    start_seconds=float(segment["start_seconds"]),
                    text=str(segment["text"]),
                )
            )
        return entries
