"""Model-backed transcribers. Heavy imports stay inside functions."""

from typing import BinaryIO

import numpy as np

from chunking import iter_chunks

sf = None


def _load_mono(audio: str | BinaryIO) -> tuple[np.ndarray, int]:
    global sf
    if sf is None:
        import soundfile as _sf

        sf = _sf
    samples, sample_rate = sf.read(audio, dtype="float32")
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    return samples, sample_rate


_MOONSHINE_SPEC_TO_ARCH = {
    "tiny-en": "TINY",
    "base-en": "BASE",
    "tiny-streaming-en": "TINY_STREAMING",
    "small-streaming-en": "SMALL_STREAMING",
    "medium-streaming-en": "MEDIUM_STREAMING",
}


def _sensevoice_local_path(service_dir):
    """Find SenseVoiceSmall in legacy or current ModelScope cache layouts."""
    root = service_dir / "models" / "sensevoice"
    legacy = root / "iic" / "SenseVoiceSmall"
    if (legacy / "model.pt").is_file():
        return legacy
    snapshots = root / "models" / "iic--SenseVoiceSmall" / "snapshots"
    if snapshots.is_dir():
        for candidate in sorted(snapshots.iterdir()):
            if candidate.is_dir() and (candidate / "model.pt").is_file():
                return candidate
    return None


def _moonshine_voice_model(model: str, ModelArch):
    """Resolve a Moonshine model spec or model_id to (language, ModelArch).

    Accepts both bare spec strings (``"tiny-en"``) and full model IDs
    (``"moonshine_voice/tiny-en"``).  All currently supported variants use
    English (``"en"``).
    """
    spec = model
    if spec.startswith("moonshine_voice/"):
        spec = spec[len("moonshine_voice/"):]
    arch_attr = _MOONSHINE_SPEC_TO_ARCH.get(spec)
    if arch_attr is None:
        raise ValueError(f"Unsupported Moonshine Voice model: {model}")
    return "en", getattr(ModelArch, arch_attr)


class FunAsrTranscriber:
    """FunASR-backed transcription, 30s windows."""

    def __init__(
        self,
        model: str = "iic/SenseVoiceSmall",
        device: str = "cpu",
    ):
        from funasr import AutoModel
        from pathlib import Path

        self.device = device
        # Load from the relocated local cache (services/asr/models/sensevoice/...)
        # if present; otherwise fall back to the model id (triggers modelscope
        # download via MODELSCOPE_CACHE or the default home cache).
        service_dir = Path(__file__).resolve().parent
        local_path = _sensevoice_local_path(service_dir)
        resolved = str(local_path) if local_path is not None else model
        self.model = AutoModel(
            model=resolved,
            device=device,
            disable_update=True,
        )

    def transcribe(self, audio: str | BinaryIO) -> list[dict]:
        from funasr.utils.postprocess_utils import rich_transcription_postprocess

        samples, sample_rate = _load_mono(audio)
        segments = []
        for offset, chunk in iter_chunks(samples, sample_rate):
            result = self.model.generate(
                input=chunk, fs=sample_rate, use_itn=True
            )
            text = rich_transcription_postprocess(result[0]["text"]).strip()
            if text:
                segments.append({"start_seconds": offset, "text": text})
        return segments


class MoonshineVoiceTranscriber:
    """Moonshine Voice-backed transcription."""

    def __init__(self, *, model: str, device: str = "cpu"):
        self.device = device
        try:
            from moonshine_voice import (
                ModelArch,
                Transcriber,
                get_model_for_language,
            )
        except ImportError as exc:
            raise RuntimeError(
                "Moonshine Voice ASR requires the moonshine_voice dependency. "
                "Install it in the ASR venv with: "
                "pip install moonshine-voice"
            ) from exc

        language, model_arch = _moonshine_voice_model(model, ModelArch)
        model_path, resolved_arch = get_model_for_language(
            wanted_language=language,
            wanted_model_arch=model_arch,
        )
        self.transcriber = Transcriber(
            model_path=model_path,
            model_arch=resolved_arch,
        )

    def transcribe(self, audio: str | BinaryIO) -> list[dict]:
        samples, sample_rate = _load_mono(audio)
        transcript = self.transcriber.transcribe_without_streaming(
            samples.tolist(),
            sample_rate,
        )
        segments = []
        for line in transcript.lines:
            text = line.text.strip()
            if text:
                segments.append(
                    {"start_seconds": line.start_time, "text": text}
                )
        return segments
