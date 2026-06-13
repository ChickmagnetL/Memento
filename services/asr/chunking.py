"""Fixed-window audio chunking.

Phase 0 finding: 30s windows beat both whole-file input (Paraformer
crashes, SenseVoice slow) and VAD segmentation (net negative).
"""

from typing import Iterator

import numpy as np


def iter_chunks(
    audio: np.ndarray, sample_rate: int, *, chunk_seconds: float = 30.0
) -> Iterator[tuple[float, np.ndarray]]:
    """Yield (start_seconds, samples) windows of at most chunk_seconds."""
    window = int(sample_rate * chunk_seconds)
    for start in range(0, len(audio), window):
        yield start / sample_rate, audio[start : start + window]
