"""Model-backed transcribers. Heavy imports stay inside functions."""

import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from chunking import iter_chunks


def _load_mono(audio_path: str) -> tuple[np.ndarray, int]:
    audio, sample_rate = sf.read(audio_path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return audio, sample_rate


class SenseVoiceTranscriber:
    """Chinese (and zh/en mixed) transcription, 30s windows."""

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
                input=chunk, fs=sample_rate, language="zh", use_itn=True
            )
            text = rich_transcription_postprocess(result[0]["text"]).strip()
            if text:
                segments.append({"start_seconds": offset, "text": text})
        return segments


class MoonshineTranscriber:
    """English transcription with Moonshine, 30s windows.

    The moonshine_onnx package accepts file paths (not numpy arrays),
    so chunks are written to temporary WAV files for each window.
    """

    def __init__(self, model_name: str = "moonshine/base"):
        import moonshine_onnx

        self.moonshine = moonshine_onnx
        self.model_name = model_name

    def transcribe(self, audio_path: str) -> list[dict]:
        audio, sample_rate = _load_mono(audio_path)
        segments = []
        for offset, chunk in iter_chunks(audio, sample_rate):
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    tmp_path = f.name
                sf.write(tmp_path, chunk, sample_rate)
                text = self.moonshine.transcribe(tmp_path, self.model_name)
                text = text.strip() if isinstance(text, str) else ""
            finally:
                if tmp_path is not None:
                    Path(tmp_path).unlink(missing_ok=True)
            if text:
                segments.append({"start_seconds": offset, "text": text})
        return segments
