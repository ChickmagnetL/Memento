"""Tests for bilibili audio downloading."""

from pathlib import Path

import pytest

from core.video.audio import AudioDownloader, AudioDownloadError


def make_video(video_id: str = "v1") -> dict:
    return {
        "id": video_id,
        "platform": "bilibili",
        "title": "示例视频",
        "url": "https://www.bilibili.com/video/BV1abc",
        "status": "processing",
    }


def test_download_invokes_ytdlp_and_returns_wav_path(tmp_path: Path):
    commands: list[list[str]] = []

    def fake_run(args: list[str]) -> None:
        commands.append(args)
        # Simulate yt-dlp writing the output file.
        output_template = args[args.index("-o") + 1]
        Path(output_template.replace("%(ext)s", "wav")).write_bytes(b"RIFF")

    downloader = AudioDownloader(
        data_dir=tmp_path, run_command=fake_run
    )

    wav_path = downloader.download(make_video())

    assert wav_path == tmp_path / "videos" / "temp" / "v1.wav"
    assert wav_path.exists()
    args = commands[0]
    assert args[0] == "yt-dlp"
    assert "https://www.bilibili.com/video/BV1abc" in args
    assert "-x" in args
    assert args[args.index("--audio-format") + 1] == "wav"
    assert args[args.index("--playlist-items") + 1] == "1"


def test_download_raises_when_command_fails(tmp_path: Path):
    def failing_run(args: list[str]) -> None:
        raise AudioDownloadError("yt-dlp exited with code 1")

    downloader = AudioDownloader(
        data_dir=tmp_path, run_command=failing_run
    )

    with pytest.raises(AudioDownloadError):
        downloader.download(make_video())


def test_download_raises_when_no_output_produced(tmp_path: Path):
    downloader = AudioDownloader(
        data_dir=tmp_path, run_command=lambda args: None
    )

    with pytest.raises(AudioDownloadError):
        downloader.download(make_video())
