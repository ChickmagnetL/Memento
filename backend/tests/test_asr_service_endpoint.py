"""Tests for the standalone ASR service OpenAI-compatible endpoint."""

import importlib.util
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ASR_SERVER_PATH = Path(__file__).resolve().parents[2] / "services" / "asr" / "server.py"
SPEC = importlib.util.spec_from_file_location("asr_service_server_test", ASR_SERVER_PATH)
server = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = server
SPEC.loader.exec_module(server)


def test_transcriptions_endpoint_returns_verbose_json(monkeypatch):
    seen = []

    class FakeTranscriber:
        def transcribe(self, audio) -> list[dict]:
            seen.append(audio.read())
            return [
                {"start_seconds": 0.0, "text": "第一段"},
                {"start_seconds": 3.5, "text": "第二段"},
            ]

    monkeypatch.setattr(server, "get_transcriber", lambda model: FakeTranscriber())

    response = TestClient(server.app).post(
        "/v1/audio/transcriptions",
        data={"model": "iic/SenseVoiceSmall"},
        files={"file": ("audio.wav", b"RIFF", "audio/wav")},
    )

    assert response.status_code == 200
    assert seen == [b"RIFF"]
    assert response.json() == {
        "text": "第一段 第二段",
        "segments": [
            {"start": 0.0, "text": "第一段"},
            {"start": 3.5, "text": "第二段"},
        ],
    }


def test_transcriptions_endpoint_routes_moonshine_model(monkeypatch):
    seen_models = []

    class FakeTranscriber:
        def transcribe(self, path: str) -> list[dict]:
            return []

    def fake_get_transcriber(model: str):
        seen_models.append(model)
        return FakeTranscriber()

    monkeypatch.setattr(server, "get_transcriber", fake_get_transcriber)

    response = TestClient(server.app).post(
        "/v1/audio/transcriptions",
        data={"model": "moonshine_voice/medium-streaming-en"},
        files={"file": ("audio.wav", b"RIFF", "audio/wav")},
    )

    assert response.status_code == 200
    assert seen_models == ["moonshine_voice/medium-streaming-en"]


def test_transcriptions_endpoint_requires_file():
    response = TestClient(server.app).post(
        "/v1/audio/transcriptions",
        data={"model": "iic/SenseVoiceSmall"},
    )

    assert response.status_code == 422


def test_legacy_transcribe_endpoint_is_removed():
    response = TestClient(server.app).post(
        "/transcribe",
        json={"audio_path": "/tmp/audio.wav", "model": "iic/SenseVoiceSmall"},
    )

    assert response.status_code == 404
