"""Memento ASR service.

Runs in its own venv because funasr/torch are heavy. Receives uploaded
audio and returns OpenAI-compatible verbose JSON transcription output.
The configured Settings ASR model is lazy-loaded on first use.
"""

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

app = FastAPI(title="Memento ASR Service", version="0.1.0")

_transcribers: dict = {}
FunAsrTranscriber = None
MoonshineVoiceTranscriber = None


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


@app.post("/v1/audio/transcriptions")
def transcribe(
    file: UploadFile = File(...),
    model: str = Form(DEFAULT_ASR_MODEL),
    response_format: str = Form("verbose_json"),
) -> dict:
    suffix = Path(file.filename or "").suffix
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="memento-asr-",
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(file.file.read())
        transcriber = get_transcriber(model or DEFAULT_ASR_MODEL)
        segments = transcriber.transcribe(str(temp_path))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    response_segments = [
        {"start": segment["start_seconds"], "text": segment["text"]}
        for segment in segments
    ]
    text = " ".join(segment["text"] for segment in segments if segment["text"])
    if response_format == "text":
        return {"text": text}
    return {"text": text, "segments": response_segments}
