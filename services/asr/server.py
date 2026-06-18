"""Memento ASR service.

Runs in its own venv because funasr/torch are heavy. Receives local
audio paths (same machine as the main backend) and returns timed
segments. The configured Settings ASR model is lazy-loaded on first use.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Memento ASR Service", version="0.1.0")

_transcribers: dict = {}
FunAsrTranscriber = None
MoonshineVoiceTranscriber = None


class TranscribeRequest(BaseModel):
    audio_path: str
    model: str | None = None


class Segment(BaseModel):
    start_seconds: float
    text: str


class TranscribeResponse(BaseModel):
    segments: list[Segment]


DEFAULT_ASR_MODEL = "iic/SenseVoiceSmall"


def _get_transcriber_class(model: str):
    if model.startswith("moonshine_voice/"):
        global MoonshineVoiceTranscriber
        if MoonshineVoiceTranscriber is None:
            from transcribers import (
                MoonshineVoiceTranscriber as _MoonshineVoiceTranscriber,
            )

            MoonshineVoiceTranscriber = _MoonshineVoiceTranscriber
        return MoonshineVoiceTranscriber

    global FunAsrTranscriber
    if FunAsrTranscriber is None:
        from transcribers import FunAsrTranscriber as _FunAsrTranscriber

        FunAsrTranscriber = _FunAsrTranscriber
    return FunAsrTranscriber


def get_transcriber(model: str):
    """Lazy-load and cache the transcriber for a configured model."""
    if model not in _transcribers:
        transcriber_class = _get_transcriber_class(model)
        _transcribers[model] = transcriber_class(model=model)
    return _transcribers[model]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/transcribe", response_model=TranscribeResponse)
def transcribe(payload: TranscribeRequest) -> dict:
    if not Path(payload.audio_path).is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")
    try:
        transcriber = get_transcriber(payload.model or DEFAULT_ASR_MODEL)
        segments = transcriber.transcribe(payload.audio_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"segments": segments}
