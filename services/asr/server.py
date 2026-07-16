"""Memento ASR service.

Runs in its own venv because funasr/torch are heavy. Receives uploaded
audio and returns OpenAI-compatible verbose JSON transcription output.
The configured Settings ASR model is lazy-loaded on first use.
"""

import io
import logging
import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

# Default to the China HuggingFace mirror (moonshine models ship via HF).
# Harmless elsewhere; set HF_ENDPOINT before start to override
# (e.g. HF_ENDPOINT=https://huggingface.co).
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

app = FastAPI(title="Memento ASR Service", version="0.1.1")
logger = logging.getLogger(__name__)

SERVICE_DIR = Path(__file__).resolve().parent
_MODELS_DIR = SERVICE_DIR / "models"

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


def detect_best_device() -> str:
    """Detect the best device supported by this service's installed torch."""
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def _sensevoice_installed() -> bool:
    root = _MODELS_DIR / "sensevoice"
    if not root.is_dir():
        return False
    # Preferred exact layout
    if (root / "iic" / "SenseVoiceSmall" / "model.pt").is_file():
        return True
    # Alternate modelscope layouts
    return any(root.rglob("model.pt"))


def _moonshine_spec_installed(spec: str) -> bool:
    return (_MODELS_DIR / "moonshine" / "download.moonshine.ai" / "model" / spec / "quantized").is_dir()


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
        device = os.environ.get("ASR_DEVICE") or detect_best_device()
        _transcribers[model] = transcriber_class(model=model, device=device)
    return _transcribers[model]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models() -> dict:
    """List ASR models actually installed on disk (OpenAI-compatible).

    Shape matches what backend/api/settings.py:_list_openai_compatible_models
    parses (``data[].id``).
    """
    ids = set()
    if _sensevoice_installed():
        ids.add("iic/SenseVoiceSmall")  # canonical id only; "sensevoice-small" alias still accepted as input via _normalize_model
    for spec in _MOONSHINE_SPECS:
        if _moonshine_spec_installed(spec):
            ids.add(f"moonshine_voice/{spec}")
    return {
        "data": [
            {"id": mid, "object": "model", "created": 0, "owned_by": "memento"}
            for mid in sorted(ids)
        ]
    }


@app.post("/v1/warmup")
def warmup() -> dict:
    if _sensevoice_installed():
        model = DEFAULT_ASR_MODEL  # "iic/SenseVoiceSmall"
    else:
        model = None
        for spec in sorted(_MOONSHINE_SPECS):
            if _moonshine_spec_installed(spec):
                model = f"moonshine_voice/{spec}"
                break
        if model is None:
            raise HTTPException(status_code=503, detail="No ASR models installed")
    get_transcriber(model)
    return {"status": "ok", "model": model}


@app.post("/v1/audio/transcriptions")
def transcribe(
    file: UploadFile = File(...),
    model: str = Form(DEFAULT_ASR_MODEL),
    response_format: str = Form("verbose_json"),
) -> dict:
    try:
        audio = io.BytesIO(file.file.read())
    except Exception as exc:
        logger.exception("ASR upload read failed")
        raise HTTPException(
            status_code=500, detail=f"ASR upload read failed: {exc}"
        ) from exc

    try:
        transcriber = get_transcriber(model or DEFAULT_ASR_MODEL)
    except Exception as exc:
        logger.exception("ASR model load failed")
        raise HTTPException(
            status_code=500, detail=f"ASR model load failed: {exc}"
        ) from exc

    try:
        segments = transcriber.transcribe(audio)
    except Exception as exc:
        logger.exception("ASR transcription failed")
        raise HTTPException(
            status_code=500, detail=f"ASR transcription failed: {exc}"
        ) from exc

    response_segments = [
        {"start": segment["start_seconds"], "text": segment["text"]}
        for segment in segments
    ]
    text = " ".join(segment["text"] for segment in segments if segment["text"])
    if response_format == "text":
        return {"text": text}
    return {"text": text, "segments": response_segments}
