"""Memento ASR service: SenseVoice (zh) + Moonshine (en).

Runs in its own venv because funasr/torch are heavy. Receives local
audio paths (same machine as the main backend) and returns timed
segments. Models are lazy-loaded on first use.
"""

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Memento ASR Service", version="0.1.0")

_transcribers: dict = {}


class TranscribeRequest(BaseModel):
    audio_path: str
    language: Literal["zh", "en"]


class Segment(BaseModel):
    start_seconds: float
    text: str


class TranscribeResponse(BaseModel):
    segments: list[Segment]


def get_transcriber(language: str):
    """Lazy-load and cache the transcriber for a language.

    Model names can be overridden via environment variables:
      SENSEVOICE_MODEL  (default: iic/SenseVoiceSmall)
      MOONSHINE_MODEL   (default: moonshine/base)
    """
    import os

    if language not in _transcribers:
        if language == "zh":
            from transcribers import SenseVoiceTranscriber

            model = os.environ.get("SENSEVOICE_MODEL", "iic/SenseVoiceSmall")
            _transcribers[language] = SenseVoiceTranscriber(model=model)
        else:
            from transcribers import MoonshineTranscriber

            model = os.environ.get("MOONSHINE_MODEL", "moonshine/base")
            _transcribers[language] = MoonshineTranscriber(model_name=model)
    return _transcribers[language]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/transcribe", response_model=TranscribeResponse)
def transcribe(payload: TranscribeRequest) -> dict:
    if not Path(payload.audio_path).is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")
    try:
        transcriber = get_transcriber(payload.language)
        segments = transcriber.transcribe(payload.audio_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"segments": segments}
