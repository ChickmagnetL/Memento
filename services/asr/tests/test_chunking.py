"""Tests for audio chunking (pure logic, no models)."""

import numpy as np

from chunking import iter_chunks


def test_iter_chunks_splits_with_offsets():
    sample_rate = 16000
    audio = np.zeros(int(sample_rate * 70.0), dtype=np.float32)  # 70s

    chunks = list(iter_chunks(audio, sample_rate, chunk_seconds=30.0))

    assert len(chunks) == 3
    offsets = [offset for offset, _ in chunks]
    assert offsets == [0.0, 30.0, 60.0]
    assert len(chunks[0][1]) == sample_rate * 30
    assert len(chunks[2][1]) == sample_rate * 10


def test_iter_chunks_short_audio_single_chunk():
    sample_rate = 16000
    audio = np.zeros(sample_rate * 5, dtype=np.float32)

    chunks = list(iter_chunks(audio, sample_rate, chunk_seconds=30.0))

    assert len(chunks) == 1
    assert chunks[0][0] == 0.0


def test_iter_chunks_empty_audio_yields_nothing():
    assert list(iter_chunks(np.zeros(0), 16000, chunk_seconds=30.0)) == []
