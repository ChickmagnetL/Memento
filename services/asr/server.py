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

# ---------------------------------------------------------------------------
# Model routing tables (mirror backend/core/asr_model_registry.py)
# ---------------------------------------------------------------------------
_MOONSHINE_SPECS = frozenset({
    "tiny-en",
    "base-en",
    "tiny-streaming-en",
    "small-streaming-en",
    "medium-streaming-en",
})

_SENSEVOICE_MODELS = frozenset({
    "iic/SenseVoiceSmall",
    "sensevoice-small",
})


def _normalize_model(model: str) -> str:
    """Resolve model aliases to canonical model IDs."""
    if model == "sensevoice-small":
        return "iic/SenseVoiceSmall"
    return model


def _get_transcriber_class(model: str):
    """Return the transcriber class for *model*, or raise ValueError.

    *model* must already be normalized via :func:`_normalize_model`.
    """
    # Detect Moonshine models: full model_id or bare spec
    spec = model
    if model.startswith("moonshine_voice/"):
        spec = model[len("moonshine_voice/"):]
    if spec in _MOONSHINE_SPECS:
        global MoonshineVoiceTranscriber
        if MoonshineVoiceTranscriber is None:
            from transcribers import (
                MoonshineVoiceTranscriber as _MoonshineVoiceTranscriber,
            )

            MoonshineVoiceTranscriber = _MoonshineVoiceTranscriber
        return MoonshineVoiceTranscriber

    # SenseVoice Small (model_id or alias)
    if model in _SENSEVOICE_MODELS:
        global FunAsrTranscriber
        if FunAsrTranscriber is None:
            from transcribers import FunAsrTranscriber as _FunAsrTranscriber

            FunAsrTranscriber = _FunAsrTranscriber
        return FunAsrTranscriber

    raise ValueError(f"Unsupported ASR model: {model}")


def get_transcriber(model: str):
    """Lazy-load and cache the transcriber for a configured model."""
    model = _normalize_model(model)
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
