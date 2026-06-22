"""Tests for the OpenAI-compatible ASR client."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from core.video.asr_client import (
    CHAT_AUDIO_MAX_BYTES,
    TRANSCRIPTIONS_MAX_BYTES,
    AsrError,
    AsrServiceClient,
    extract_chunk,
)
from core.video.bilibili import SubtitleEntry


def _audio_file(tmp_path: Path, size: int = 4) -> Path:
    path = tmp_path / "audio.wav"
    path.write_bytes(b"a" * size)
    return path


def test_transcriptions_posts_multipart_and_maps_segments(tmp_path: Path):
    audio_path = _audio_file(tmp_path)
    calls = []

    def fake_post_multipart(url, fields, files, headers, timeout=30):
        calls.append((url, fields, files, headers, timeout))
        return {
            "segments": [
                {"start": 0.0, "text": "第一段"},
                {"start": 30.0, "text": "第二段"},
            ]
        }

    client = AsrServiceClient(
        endpoint="http://localhost:8001/v1",
        post_multipart=fake_post_multipart,
        ensure_running=lambda endpoint: None,
    )

    entries = client.transcribe(
        str(audio_path),
        model="iic/SenseVoiceSmall",
        protocol="transcriptions",
        api_key="sk-test",
    )

    assert entries == [
        SubtitleEntry(start_seconds=0.0, text="第一段"),
        SubtitleEntry(start_seconds=30.0, text="第二段"),
    ]
    url, fields, files, headers, timeout = calls[0]
    assert url == "http://localhost:8001/v1/audio/transcriptions"
    assert fields == {
        "model": "iic/SenseVoiceSmall",
        "response_format": "verbose_json",
    }
    assert files == {"file": audio_path}
    assert headers == {"Authorization": "Bearer sk-test"}
    assert timeout >= 600


def test_transcriptions_plain_text_falls_back_to_single_segment(tmp_path: Path):
    audio_path = _audio_file(tmp_path)
    client = AsrServiceClient(
        endpoint="https://api.example.com/v1",
        post_multipart=lambda *args, **kwargs: {"text": "只有文本"},
        ensure_running=lambda endpoint: (_ for _ in ()).throw(AssertionError("no ensure")),
    )

    entries = client.transcribe(
        str(audio_path),
        model="model",
        protocol="transcriptions",
        api_key="sk-test",
    )

    assert entries == [SubtitleEntry(start_seconds=0.0, text="只有文本")]


def test_chat_audio_posts_base64_input_audio_and_maps_text(tmp_path: Path):
    audio_path = _audio_file(tmp_path, size=3)
    calls = []

    def fake_post_json(url, payload, headers, timeout=30):
        calls.append((url, payload, headers, timeout))
        return {"choices": [{"message": {"content": "转录文本"}}]}

    client = AsrServiceClient(
        endpoint="https://api.xiaomimimo.com/v1",
        post_json=fake_post_json,
        probe_duration=lambda path: 3.0,
        ensure_running=lambda endpoint: (_ for _ in ()).throw(AssertionError("no ensure")),
    )

    entries = client.transcribe(
        str(audio_path),
        model="mimo-v2.5-asr",
        protocol="chat_audio",
        api_key="sk-test",
    )

    assert entries == [SubtitleEntry(start_seconds=0.0, text="转录文本")]
    url, payload, headers, timeout = calls[0]
    assert url == "https://api.xiaomimimo.com/v1/chat/completions"
    assert payload["model"] == "mimo-v2.5-asr"
    assert payload["asr_options"] == {"language": "auto"}
    content = payload["messages"][0]["content"]
    assert content[0]["type"] == "input_audio"
    assert content[0]["input_audio"]["data"].startswith("data:audio/wav;base64,")
    assert headers == {
        "Authorization": "Bearer sk-test",
        "Content-Type": "application/json",
    }
    assert timeout >= 600


def test_constructor_protocol_used_when_transcribe_protocol_omitted(tmp_path: Path):
    audio_path = _audio_file(tmp_path, size=3)
    calls = []

    def fake_post_json(url, payload, headers, timeout=30):
        calls.append((url, payload))
        return {"choices": [{"message": {"content": "转录文本"}}]}

    client = AsrServiceClient(
        endpoint="https://api.xiaomimimo.com/v1",
        protocol="chat_audio",
        post_json=fake_post_json,
        probe_duration=lambda path: 3.0,
        ensure_running=lambda endpoint: (_ for _ in ()).throw(AssertionError("no ensure")),
    )

    entries = client.transcribe(str(audio_path), model="mimo-v2.5-asr")

    assert entries == [SubtitleEntry(start_seconds=0.0, text="转录文本")]
    assert calls[0][0] == "https://api.xiaomimimo.com/v1/chat/completions"


def test_localhost_transcriptions_ensures_service_running(tmp_path: Path):
    audio_path = _audio_file(tmp_path)
    order = []

    def fake_post_multipart(*args, **kwargs):
        order.append("post")
        return {"segments": []}

    def ensure_running(endpoint):
        order.append(("ensure", endpoint))

    client = AsrServiceClient(
        endpoint="http://localhost:8001/v1",
        post_multipart=fake_post_multipart,
        ensure_running=ensure_running,
    )

    client.transcribe(str(audio_path), model="iic/SenseVoiceSmall")

    assert order == [("ensure", "http://localhost:8001"), "post"]


def test_localhost_transcriptions_adds_v1_for_legacy_endpoint(tmp_path: Path):
    audio_path = _audio_file(tmp_path)
    calls = []

    def fake_post_multipart(url, fields, files, headers, timeout=30):
        calls.append(url)
        return {"segments": []}

    client = AsrServiceClient(
        endpoint="http://localhost:8001",
        post_multipart=fake_post_multipart,
        ensure_running=lambda endpoint: None,
    )

    client.transcribe(str(audio_path), model="iic/SenseVoiceSmall")

    assert calls == ["http://localhost:8001/v1/audio/transcriptions"]


def test_remote_transcriptions_and_chat_audio_do_not_ensure(tmp_path: Path):
    audio_path = _audio_file(tmp_path)

    def fail_ensure(endpoint):
        raise AssertionError("remote endpoints must not be spawned")

    transcriptions = AsrServiceClient(
        endpoint="https://api.siliconflow.cn/v1",
        post_multipart=lambda *args, **kwargs: {"text": "ok"},
        ensure_running=fail_ensure,
    )
    chat_audio = AsrServiceClient(
        endpoint="https://api.xiaomimimo.com/v1",
        post_json=lambda *args, **kwargs: {"choices": [{"message": {"content": "ok"}}]},
        probe_duration=lambda path: 3.0,
        ensure_running=fail_ensure,
    )

    assert transcriptions.transcribe(
        str(audio_path),
        model="FunAudioLLM/SenseVoiceSmall",
        protocol="transcriptions",
        api_key="sk-test",
    )
    assert chat_audio.transcribe(
        str(audio_path),
        model="mimo-v2.5-asr",
        protocol="chat_audio",
        api_key="sk-test",
    )


def test_cloud_transcriptions_chunks_large_audio_and_offsets_segments(tmp_path: Path):
    audio_path = _audio_file(tmp_path, size=TRANSCRIPTIONS_MAX_BYTES + 1)
    chunks_dir = tmp_path / "chunks"
    calls = []

    def fake_detect_silences(path):
        assert path == audio_path
        return [12.0]

    def fake_extract_chunk(source, start, end, destination):
        assert source == audio_path
        chunks_dir.mkdir(exist_ok=True)
        destination.write_bytes(b"chunk")

    def fake_post_multipart(url, fields, files, headers, timeout=30):
        calls.append(files["file"].name)
        if len(calls) == 1:
            return {"segments": [{"start": 1.0, "text": "第一段"}]}
        return {"segments": [{"start": 2.0, "text": "第二段"}]}

    client = AsrServiceClient(
        endpoint="https://api.siliconflow.cn/v1",
        post_multipart=fake_post_multipart,
        detect_silences=fake_detect_silences,
        probe_duration=lambda path: 120.0,
        extract_chunk=fake_extract_chunk,
    )

    entries = client.transcribe(
        str(audio_path),
        model="FunAudioLLM/SenseVoiceSmall",
        protocol="transcriptions",
        api_key="sk-test",
    )

    assert entries == [
        SubtitleEntry(start_seconds=1.0, text="第一段"),
        SubtitleEntry(start_seconds=14.0, text="第二段"),
    ]
    assert len(calls) == 2


def test_chat_audio_uses_smaller_chunk_threshold(tmp_path: Path):
    audio_path = _audio_file(tmp_path, size=CHAT_AUDIO_MAX_BYTES + 1)
    extracted = []

    def fake_extract_chunk(source, start, end, destination):
        extracted.append((start, end))
        destination.write_bytes(b"chunk")

    client = AsrServiceClient(
        endpoint="https://api.xiaomimimo.com/v1",
        post_json=lambda *args, **kwargs: {"choices": [{"message": {"content": "ok"}}]},
        detect_silences=lambda path: [5.0],
        probe_duration=lambda path: 3.0,
        extract_chunk=fake_extract_chunk,
    )

    client.transcribe(
        str(audio_path),
        model="mimo-v2.5-asr",
        protocol="chat_audio",
        api_key="sk-test",
    )

    assert extracted == [(0.0, 5.0), (5.0, None)]


def test_chat_audio_chunks_by_duration_and_prefers_late_silence(tmp_path: Path):
    audio_path = _audio_file(tmp_path, size=4)
    extracted = []

    def fake_extract_chunk(source, start, end, destination):
        extracted.append((start, end))
        destination.write_bytes(b"chunk")

    client = AsrServiceClient(
        endpoint="https://api.xiaomimimo.com/v1",
        post_json=lambda *args, **kwargs: {"choices": [{"message": {"content": "ok"}}]},
        detect_silences=lambda path: [12.0, 48.0, 57.0, 113.0],
        extract_chunk=fake_extract_chunk,
        probe_duration=lambda path: 125.0,
    )

    entries = client.transcribe(
        str(audio_path),
        model="mimo-v2.5-asr",
        protocol="chat_audio",
        api_key="sk-test",
    )

    assert extracted == [(0.0, 57.0), (56.0, 113.0), (112.0, None)]
    assert entries == [
        SubtitleEntry(start_seconds=0.0, text="ok"),
        SubtitleEntry(start_seconds=56.0, text="ok"),
        SubtitleEntry(start_seconds=112.0, text="ok"),
    ]


def test_chat_audio_duration_chunking_falls_back_to_sixty_seconds(tmp_path: Path):
    audio_path = _audio_file(tmp_path, size=4)
    extracted = []

    def fake_extract_chunk(source, start, end, destination):
        extracted.append((start, end))
        destination.write_bytes(b"chunk")

    client = AsrServiceClient(
        endpoint="https://api.xiaomimimo.com/v1",
        post_json=lambda *args, **kwargs: {"choices": [{"message": {"content": "ok"}}]},
        detect_silences=lambda path: [20.0, 30.0],
        extract_chunk=fake_extract_chunk,
        probe_duration=lambda path: 125.0,
    )

    client.transcribe(
        str(audio_path),
        model="mimo-v2.5-asr",
        protocol="chat_audio",
        api_key="sk-test",
    )

    assert extracted == [(0.0, 60.0), (59.0, 119.0), (118.0, None)]


def test_extract_chunk_uses_duration_not_absolute_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "source.wav"
    destination = tmp_path / "chunk.wav"
    source.write_bytes(b"audio")
    calls = []

    def fake_run(args, capture_output, text, timeout):
        calls.append(args)
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("core.video.asr_client.subprocess.run", fake_run)

    extract_chunk(source, 40.0, 60.0, destination)

    args = calls[0]
    assert "-t" in args
    assert args[args.index("-t") + 1] == "20.0"
    assert "-to" not in args


def test_connection_error_wrapped_as_asr_error(tmp_path: Path):
    audio_path = _audio_file(tmp_path)

    def failing(*args, **kwargs):
        raise OSError("connection refused")

    client = AsrServiceClient(
        endpoint="http://localhost:8001/v1",
        post_multipart=failing,
        ensure_running=lambda endpoint: None,
    )
    with pytest.raises(AsrError, match="ASR service"):
        client.transcribe(str(audio_path), model="iic/SenseVoiceSmall")
