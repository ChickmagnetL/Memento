"""Model-backed transcribers. Heavy imports stay inside functions."""

import numpy as np

from chunking import iter_chunks

sf = None


def _load_mono(audio_path: str) -> tuple[np.ndarray, int]:
    global sf
    if sf is None:
        import soundfile as _sf

        sf = _sf
    audio, sample_rate = sf.read(audio_path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return audio, sample_rate


_MOONSHINE_SPEC_TO_ARCH = {
    "tiny-en": "TINY",
    "base-en": "BASE",
    "tiny-streaming-en": "TINY_STREAMING",
    "small-streaming-en": "SMALL_STREAMING",
    "medium-streaming-en": "MEDIUM_STREAMING",
}


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
        cache_dir: str = "model_cache",
        model: str = "iic/SenseVoiceSmall",
    ):
        from funasr import AutoModel

        self.model = AutoModel(
            model=model,
            device="cpu",
            disable_update=True,
            cache_dir=cache_dir,
        )

    def transcribe(self, audio_path: str) -> list[dict]:
        from funasr.utils.postprocess_utils import rich_transcription_postprocess

        audio, sample_rate = _load_mono(audio_path)
        segments = []
        for offset, chunk in iter_chunks(audio, sample_rate):
            result = self.model.generate(
                input=chunk, fs=sample_rate, use_itn=True
            )
            text = rich_transcription_postprocess(result[0]["text"]).strip()
            if text:
                segments.append({"start_seconds": offset, "text": text})
        return segments


class MoonshineVoiceTranscriber:
    """Moonshine Voice-backed transcription."""

    def __init__(self, *, model: str):
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

    def transcribe(self, audio_path: str) -> list[dict]:
        audio, sample_rate = _load_mono(audio_path)
        transcript = self.transcriber.transcribe_without_streaming(
            audio.tolist(),
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
