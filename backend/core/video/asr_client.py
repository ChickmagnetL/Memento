"""OpenAI-compatible ASR client."""

import base64
import json
import mimetypes
import re
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from core.rag.embedding import post_json as default_post_json
from core.video.asr_supervisor import AsrError, ensure_asr_running
from core.video.bilibili import SubtitleEntry

# Transcription of a long video can take minutes on CPU.
ASR_TIMEOUT_SECONDS = 900
TRANSCRIPTIONS_MAX_BYTES = 50 * 1024 * 1024
CHAT_AUDIO_MAX_BYTES = 10 * 1024 * 1024
CHAT_AUDIO_MAX_SECONDS = 60.0
CHAT_AUDIO_MIN_SILENCE_CUT_SECONDS = 45.0
CHAT_AUDIO_OVERLAP_SECONDS = 1.0


def post_multipart(
    url: str,
    fields: dict[str, str],
    files: dict[str, Path],
    headers: dict[str, str],
    *,
    timeout: int = 30,
) -> dict:
    """POST multipart/form-data and return decoded JSON."""
    boundary = f"----memento-{uuid.uuid4().hex}"
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(
                "utf-8"
            )
        )
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    for name, path in files.items():
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            (
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{path.name}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
        )
        body.extend(path.read_bytes())
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    request_headers = {
        **headers,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    request = Request(url, data=bytes(body), headers=request_headers, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def detect_silences(audio_path: Path) -> list[float]:
    """Return silence end timestamps from ffmpeg silencedetect output."""
    result = subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(audio_path),
            "-af",
            "silencedetect=noise=-35dB:d=0.8",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = f"{result.stdout}\n{result.stderr}"
    return [float(match) for match in re.findall(r"silence_end: ([0-9.]+)", output)]


def probe_duration(audio_path: Path) -> float:
    """Return audio duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise AsrError(f"ffprobe duration failed: {result.stderr[-500:]}")
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise AsrError("ffprobe returned invalid duration") from exc


def extract_chunk(source: Path, start: float, end: float | None, destination: Path) -> None:
    """Extract a time range to a mono WAV chunk."""
    args = [
        "ffmpeg",
        "-y",
        "-ss",
        str(start),
        "-i",
        str(source),
    ]
    if end is not None:
        args.extend(["-t", str(end - start)])
    args.extend(
        [
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(destination),
        ]
    )
    result = subprocess.run(args, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise AsrError(f"ffmpeg chunk extraction failed: {result.stderr[-500:]}")


def _is_localhost(endpoint: str) -> bool:
    host = urlparse(endpoint).hostname
    return host in {"localhost", "127.0.0.1", "::1"}


def _health_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if parsed.path.rstrip("/") == "/v1":
        return endpoint[: -len(parsed.path.rstrip("/"))].rstrip("/")
    return endpoint.rstrip("/")


def _transcriptions_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if _is_localhost(endpoint) and not parsed.path.rstrip("/"):
        return f"{endpoint.rstrip('/')}/v1"
    return endpoint.rstrip("/")


class AsrServiceClient:
    def __init__(
        self,
        *,
        endpoint: str,
        protocol: str = "transcriptions",
        api_key: str | None = None,
        post_json: Callable[..., dict] = default_post_json,
        post_multipart: Callable[..., dict] = post_multipart,
        ensure_running: Callable[[str], None] = ensure_asr_running,
        detect_silences: Callable[[Path], list[float]] = detect_silences,
        probe_duration: Callable[[Path], float] = probe_duration,
        extract_chunk: Callable[[Path, float, float | None, Path], None] = extract_chunk,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.protocol = protocol
        self.api_key = api_key
        self.post_json = post_json
        self.post_multipart = post_multipart
        self.ensure_running = ensure_running
        self.detect_silences = detect_silences
        self.probe_duration = probe_duration
        self.extract_chunk = extract_chunk

    def transcribe(
        self,
        audio_path: str,
        *,
        model: str,
        protocol: str | None = None,
        api_key: str | None = None,
    ) -> list[SubtitleEntry]:
        """Transcribe a local audio file via OpenAI-compatible ASR protocols."""
        protocol = protocol or self.protocol
        api_key = api_key if api_key is not None else self.api_key
        path = Path(audio_path)
        if protocol == "chat_audio":
            return self._transcribe_with_chunking(path, model, api_key, protocol)
        if protocol != "transcriptions":
            raise AsrError(f"Unsupported ASR protocol: {protocol}")

        if _is_localhost(self.endpoint):
            self.ensure_running(_health_endpoint(self.endpoint))
        return self._transcribe_with_chunking(path, model, api_key, protocol)

    def _transcribe_with_chunking(
        self,
        audio_path: Path,
        model: str,
        api_key: str | None,
        protocol: str,
    ) -> list[SubtitleEntry]:
        max_bytes = (
            CHAT_AUDIO_MAX_BYTES
            if protocol == "chat_audio"
            else TRANSCRIPTIONS_MAX_BYTES
        )
        if (
            audio_path.stat().st_size <= max_bytes
            and not self._needs_duration_chunking(audio_path, protocol)
        ):
            return self._transcribe_single(audio_path, model, api_key, protocol)

        entries: list[SubtitleEntry] = []
        boundaries = self._chunk_boundaries(audio_path, protocol)
        with tempfile.TemporaryDirectory(prefix="memento-asr-chunks-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            for index, (start, end) in enumerate(boundaries):
                chunk_path = tmp_path / f"chunk-{index}.wav"
                self.extract_chunk(audio_path, start, end, chunk_path)
                chunk_entries = self._transcribe_single(
                    chunk_path, model, api_key, protocol
                )
                if protocol == "chat_audio" and len(chunk_entries) == 1:
                    text = chunk_entries[0].text
                    entries.append(SubtitleEntry(start_seconds=start, text=text))
                else:
                    entries.extend(
                        SubtitleEntry(
                            start_seconds=start + entry.start_seconds,
                            text=entry.text,
                        )
                        for entry in chunk_entries
                    )
        return entries

    def _needs_duration_chunking(self, audio_path: Path, protocol: str) -> bool:
        if protocol != "chat_audio":
            return False
        return self.probe_duration(audio_path) > CHAT_AUDIO_MAX_SECONDS

    def _chunk_boundaries(
        self, audio_path: Path, protocol: str
    ) -> list[tuple[float, float | None]]:
        silences = [point for point in self.detect_silences(audio_path) if point > 0]
        if protocol == "chat_audio" and (
            duration := self.probe_duration(audio_path)
        ) > CHAT_AUDIO_MAX_SECONDS:
            return self._duration_boundaries(duration, silences)
        if not silences:
            return [(0.0, None)]
        boundaries: list[tuple[float, float | None]] = []
        start = 0.0
        for silence_end in silences:
            boundaries.append((start, silence_end))
            start = silence_end
        boundaries.append((start, None))
        return boundaries

    def _duration_boundaries(
        self, duration: float, silences: list[float]
    ) -> list[tuple[float, float | None]]:
        boundaries: list[tuple[float, float | None]] = []
        start = 0.0
        while start + CHAT_AUDIO_MAX_SECONDS < duration:
            min_cut = start + CHAT_AUDIO_MIN_SILENCE_CUT_SECONDS
            max_cut = start + CHAT_AUDIO_MAX_SECONDS
            candidates = [point for point in silences if min_cut <= point <= max_cut]
            cut = candidates[-1] if candidates else max_cut
            boundaries.append((start, cut))
            next_start = max(0.0, cut - CHAT_AUDIO_OVERLAP_SECONDS)
            if next_start <= start:
                next_start = cut
            start = next_start
        boundaries.append((start, None))
        return boundaries

    def _transcribe_single(
        self,
        audio_path: Path,
        model: str,
        api_key: str | None,
        protocol: str,
    ) -> list[SubtitleEntry]:
        try:
            if protocol == "chat_audio":
                response = self._post_chat_audio(audio_path, model, api_key)
                return self._parse_chat_audio_response(response)
            response = self._post_transcriptions(audio_path, model, api_key)
            return self._parse_transcriptions_response(response)
        except HTTPError as exc:
            detail = str(exc)
            try:
                body = exc.read().decode("utf-8", errors="replace")[:500]
                detail = f"{exc} - body: {body}"
            except Exception:
                pass
            raise AsrError(
                f"ASR service failed at {self.endpoint}: {detail}"
            ) from exc
        except OSError as exc:
            detail = str(exc)
            try:
                if hasattr(exc, "read"):
                    body = exc.read().decode("utf-8", errors="replace")[:500]
                    detail = f"{exc} - body: {body}"
            except Exception:
                pass
            raise AsrError(f"ASR service unreachable at {self.endpoint}: {detail}") from exc

    def _post_transcriptions(
        self,
        audio_path: Path,
        model: str,
        api_key: str | None,
    ) -> dict:
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return self.post_multipart(
            f"{_transcriptions_endpoint(self.endpoint)}/audio/transcriptions",
            {"model": model, "response_format": "verbose_json"},
            {"file": audio_path},
            headers,
            timeout=ASR_TIMEOUT_SECONDS,
        )

    def _post_chat_audio(
        self,
        audio_path: Path,
        model: str,
        api_key: str | None,
    ) -> dict:
        mime_type = mimetypes.guess_type(audio_path.name)[0] or "audio/wav"
        if mime_type == "audio/x-wav":
            mime_type = "audio/wav"
        encoded = base64.b64encode(audio_path.read_bytes()).decode("ascii")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return self.post_json(
            f"{self.endpoint}/chat/completions",
            {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": f"data:{mime_type};base64,{encoded}",
                                },
                            }
                        ],
                    }
                ],
                "asr_options": {"language": "auto"},
            },
            headers,
            timeout=ASR_TIMEOUT_SECONDS,
        )

    def _parse_transcriptions_response(self, response: dict) -> list[SubtitleEntry]:
        segments = response.get("segments") if isinstance(response, dict) else None
        if isinstance(segments, list):
            entries = []
            for segment in segments:
                if not isinstance(segment, dict):
                    raise AsrError("Malformed ASR service response")
                text = segment.get("text")
                start = segment.get("start", segment.get("start_seconds"))
                if text is None or start is None:
                    raise AsrError("Malformed ASR service response")
                entries.append(SubtitleEntry(start_seconds=float(start), text=str(text)))
            return entries

        text = response.get("text") if isinstance(response, dict) else None
        if isinstance(text, str) and text.strip():
            return [SubtitleEntry(start_seconds=0.0, text=text.strip())]
        raise AsrError("Malformed ASR service response")

    def _parse_chat_audio_response(self, response: dict) -> list[SubtitleEntry]:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AsrError("Malformed ASR service response") from exc
        if not isinstance(content, str) or not content.strip():
            raise AsrError("Malformed ASR service response")
        return [SubtitleEntry(start_seconds=0.0, text=content.strip())]
