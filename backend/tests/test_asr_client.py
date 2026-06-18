"""Tests for the ASR service client."""

import pytest

from core.video.asr_client import AsrError, AsrServiceClient
from core.video.bilibili import SubtitleEntry


def test_transcribe_posts_and_maps_segments():
    calls = []

    def fake_post_json(url, payload, headers, timeout=30):
        calls.append((url, payload, timeout))
        return {
            "segments": [
                {"start_seconds": 0.0, "text": "第一段"},
                {"start_seconds": 30.0, "text": "第二段"},
            ]
        }

    client = AsrServiceClient(
        endpoint="http://localhost:8001", post_json=fake_post_json
    )

    entries = client.transcribe("/tmp/v1.wav", model="iic/SenseVoiceSmall")

    assert entries == [
        SubtitleEntry(start_seconds=0.0, text="第一段"),
        SubtitleEntry(start_seconds=30.0, text="第二段"),
    ]
    url, payload, timeout = calls[0]
    assert url == "http://localhost:8001/transcribe"
    assert payload == {
        "audio_path": "/tmp/v1.wav",
        "model": "iic/SenseVoiceSmall",
    }
    assert timeout >= 600  # transcription is slow


def test_transcribe_malformed_response_raises():
    client = AsrServiceClient(
        endpoint="http://localhost:8001",
        post_json=lambda url, payload, headers, timeout=30: {"bad": 1},
    )
    with pytest.raises(AsrError):
        client.transcribe("/tmp/v1.wav", model="iic/SenseVoiceSmall")


def test_connection_error_wrapped_as_asr_error():
    def failing(url, payload, headers, timeout=30):
        raise OSError("connection refused")

    client = AsrServiceClient(endpoint="http://localhost:8001", post_json=failing)
    with pytest.raises(AsrError, match="ASR service"):
        client.transcribe("/tmp/v1.wav", model="iic/SenseVoiceSmall")
