"""Tests for ASR service model selection."""

import builtins
import sys
import types
from pathlib import Path

from fastapi.testclient import TestClient

import server


def test_transcribe_uses_requested_model(monkeypatch, tmp_path: Path):
    seen_models = []
    seen_paths = []

    class FakeTranscriber:
        def transcribe(self, path: str) -> list[dict]:
            seen_paths.append(path)
            return [{"start_seconds": 0.0, "text": Path(path).name}]

    def fake_get_transcriber(model: str):
        seen_models.append(model)
        return FakeTranscriber()

    monkeypatch.setattr(server, "get_transcriber", fake_get_transcriber)

    response = TestClient(server.app).post(
        "/v1/audio/transcriptions",
        data={"model": "custom-asr-model"},
        files={"file": ("audio.wav", b"RIFF", "audio/wav")},
    )

    assert response.status_code == 200
    assert seen_models == ["custom-asr-model"]
    assert seen_paths and Path(seen_paths[0]).name.startswith("memento-asr-")
    assert response.json()["segments"] == [
        {"start": 0.0, "text": Path(seen_paths[0]).name}
    ]


def test_transcribe_defaults_to_sensevoice_model(monkeypatch):
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
        files={"file": ("audio.wav", b"RIFF", "audio/wav")},
    )

    assert response.status_code == 200
    assert seen_models == ["iic/SenseVoiceSmall"]


def test_legacy_transcribe_endpoint_is_removed():
    response = TestClient(server.app).post(
        "/transcribe",
        json={"audio_path": "/tmp/audio.wav", "model": "custom-asr-model"},
    )

    assert response.status_code == 404


def test_get_transcriber_cache_is_keyed_by_model(monkeypatch):
    server._transcribers.clear()
    seen_models = []

    class FakeTranscriber:
        def __init__(self, *, model: str) -> None:
            seen_models.append(model)

    monkeypatch.setattr(server, "MoonshineVoiceTranscriber", FakeTranscriber)

    first = server.get_transcriber("tiny-en")
    second = server.get_transcriber("tiny-en")
    third = server.get_transcriber("base-en")

    assert first is second
    assert third is not first
    assert seen_models == ["tiny-en", "base-en"]


def test_get_transcriber_selects_moonshine_voice_from_model_prefix(monkeypatch):
    server._transcribers.clear()
    seen_models = []

    class FakeMoonshineVoiceTranscriber:
        def __init__(self, *, model: str) -> None:
            seen_models.append(("moonshine_voice", model))

    class FakeFunAsrTranscriber:
        def __init__(self, *, model: str) -> None:
            seen_models.append(("funasr", model))

    monkeypatch.setattr(
        server, "MoonshineVoiceTranscriber", FakeMoonshineVoiceTranscriber
    )
    monkeypatch.setattr(server, "FunAsrTranscriber", FakeFunAsrTranscriber)

    transcriber = server.get_transcriber("moonshine_voice/medium-streaming-en")

    assert isinstance(transcriber, FakeMoonshineVoiceTranscriber)
    assert seen_models == [
        ("moonshine_voice", "moonshine_voice/medium-streaming-en")
    ]


def test_get_transcriber_selects_funasr_for_modelscope_model(monkeypatch):
    server._transcribers.clear()
    seen_models = []

    class FakeMoonshineVoiceTranscriber:
        def __init__(self, *, model: str) -> None:
            seen_models.append(("moonshine_voice", model))

    class FakeFunAsrTranscriber:
        def __init__(self, *, model: str) -> None:
            seen_models.append(("funasr", model))

    monkeypatch.setattr(
        server, "MoonshineVoiceTranscriber", FakeMoonshineVoiceTranscriber
    )
    monkeypatch.setattr(server, "FunAsrTranscriber", FakeFunAsrTranscriber)

    transcriber = server.get_transcriber("iic/SenseVoiceSmall")

    assert isinstance(transcriber, FakeFunAsrTranscriber)
    assert seen_models == [("funasr", "iic/SenseVoiceSmall")]


def test_get_transcriber_cache_uses_exact_moonshine_voice_model(monkeypatch):
    server._transcribers.clear()
    seen_models = []

    class FakeMoonshineVoiceTranscriber:
        def __init__(self, *, model: str) -> None:
            seen_models.append(model)

    monkeypatch.setattr(
        server, "MoonshineVoiceTranscriber", FakeMoonshineVoiceTranscriber
    )

    first = server.get_transcriber("moonshine_voice/medium-streaming-en")
    second = server.get_transcriber("moonshine_voice/medium-streaming-en")
    third = server.get_transcriber("moonshine_voice/tiny-en")

    assert first is second
    assert third is not first
    assert seen_models == [
        "moonshine_voice/medium-streaming-en",
        "moonshine_voice/tiny-en",
    ]


def test_transcribe_reports_missing_moonshine_voice_dependency(
    monkeypatch, tmp_path: Path
):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"RIFF")

    class MissingMoonshineVoiceTranscriber:
        def __init__(self, *, model: str) -> None:
            raise RuntimeError(
                "Moonshine Voice ASR requires the moonshine_voice dependency. "
                "Install it in the ASR venv with: pip install moonshine-voice"
            )

    monkeypatch.setattr(
        server, "MoonshineVoiceTranscriber", MissingMoonshineVoiceTranscriber
    )
    server._transcribers.clear()

    response = TestClient(server.app).post(
        "/v1/audio/transcriptions",
        data={"model": "moonshine_voice/medium-streaming-en"},
        files={"file": ("audio.wav", audio_path.read_bytes(), "audio/wav")},
    )

    assert response.status_code == 500
    assert "moonshine_voice dependency" in response.json()["detail"]
    assert "pip install moonshine-voice" in response.json()["detail"]


def test_moonshine_voice_transcriber_reports_missing_dependency(monkeypatch):
    monkeypatch.delitem(sys.modules, "moonshine_voice", raising=False)

    from transcribers import MoonshineVoiceTranscriber

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "moonshine_voice":
            raise ImportError("missing moonshine_voice")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    try:
        MoonshineVoiceTranscriber(model="moonshine_voice/medium-streaming-en")
    except RuntimeError as exc:
        assert "moonshine_voice dependency" in str(exc)
        assert "pip install moonshine-voice" in str(exc)
    else:
        raise AssertionError("expected missing Moonshine Voice dependency error")


def test_moonshine_voice_transcriber_uses_medium_streaming_model(
    monkeypatch, tmp_path: Path
):
    fake_soundfile = types.SimpleNamespace()
    calls = []

    def fake_read(path: str, dtype: str):
        import numpy as np

        return np.array([1.0, 2.0], dtype="float32"), 16000

    class FakeModelArch:
        MEDIUM_STREAMING = object()

    returned_model_arch = object()

    def fake_get_model_for_language(*, wanted_language, wanted_model_arch):
        calls.append(
            ("get_model_for_language", wanted_language, wanted_model_arch)
        )
        return "/cache/moonshine-medium", returned_model_arch

    class FakeTranscriber:
        def __init__(self, *, model_path, model_arch) -> None:
            calls.append(("Transcriber", model_path, model_arch))

        def transcribe_without_streaming(self, audio_data, sample_rate):
            calls.append(
                ("transcribe_without_streaming", audio_data, sample_rate)
            )
            return types.SimpleNamespace(
                lines=[
                    types.SimpleNamespace(start_time=1.25, text=" hello "),
                    types.SimpleNamespace(start_time=2.0, text=" "),
                    types.SimpleNamespace(start_time=3.5, text="world"),
                ]
            )

    fake_soundfile.read = fake_read
    fake_moonshine_voice = types.SimpleNamespace(
        ModelArch=FakeModelArch,
        Transcriber=FakeTranscriber,
        get_model_for_language=fake_get_model_for_language,
    )
    monkeypatch.setitem(sys.modules, "moonshine_voice", fake_moonshine_voice)

    import transcribers
    from transcribers import MoonshineVoiceTranscriber

    monkeypatch.setattr(transcribers, "sf", fake_soundfile)

    transcriber = MoonshineVoiceTranscriber(
        model="moonshine_voice/medium-streaming-en"
    )

    assert transcriber.transcribe(str(tmp_path / "audio.wav")) == [
        {"start_seconds": 1.25, "text": "hello"},
        {"start_seconds": 3.5, "text": "world"},
    ]
    assert calls == [
        (
            "get_model_for_language",
            "en",
            FakeModelArch.MEDIUM_STREAMING,
        ),
        ("Transcriber", "/cache/moonshine-medium", returned_model_arch),
        ("transcribe_without_streaming", [1.0, 2.0], 16000),
    ]


def test_moonshine_voice_transcriber_rejects_unsupported_model(monkeypatch):
    class FakeModelArch:
        MEDIUM_STREAMING = object()

    fake_moonshine_voice = types.SimpleNamespace(
        ModelArch=FakeModelArch,
        Transcriber=object,
        get_model_for_language=lambda **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "moonshine_voice", fake_moonshine_voice)

    from transcribers import MoonshineVoiceTranscriber

    try:
        MoonshineVoiceTranscriber(model="moonshine_voice/tiny")
    except ValueError as exc:
        assert "Unsupported Moonshine Voice model" in str(exc)
        assert "moonshine_voice/tiny" in str(exc)
    else:
        raise AssertionError("expected unsupported Moonshine Voice model error")
