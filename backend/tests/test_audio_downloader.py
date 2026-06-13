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


def test_cleanup_deletes_temp_file_when_not_keeping(tmp_path: Path):
    downloader = AudioDownloader(
        data_dir=tmp_path, keep_videos=False, run_command=lambda args: None
    )
    downloader.temp_dir.mkdir(parents=True)
    wav_path = downloader.temp_dir / "v1.wav"
    wav_path.write_bytes(b"RIFF")

    downloader.cleanup(wav_path)

    assert not wav_path.exists()


def test_cleanup_moves_file_to_videos_dir_when_keeping(tmp_path: Path):
    downloader = AudioDownloader(
        data_dir=tmp_path, keep_videos=True, run_command=lambda args: None
    )
    downloader.temp_dir.mkdir(parents=True)
    wav_path = downloader.temp_dir / "v1.wav"
    wav_path.write_bytes(b"RIFF")

    downloader.cleanup(wav_path)

    assert not wav_path.exists()
    assert (tmp_path / "videos" / "v1.wav").exists()


def test_cleanup_tolerates_missing_file(tmp_path: Path):
    downloader = AudioDownloader(
        data_dir=tmp_path, keep_videos=False, run_command=lambda args: None
    )

    downloader.cleanup(downloader.temp_dir / "missing.wav")  # no raise


def test_download_passes_cookies_to_ytdlp_when_cookie_str_set(tmp_path: Path):
    commands: list[list[str]] = []

    def fake_run(args: list[str]) -> None:
        commands.append(args)
        output_template = args[args.index("-o") + 1]
        Path(output_template.replace("%(ext)s", "wav")).write_bytes(b"RIFF")

    downloader = AudioDownloader(
        data_dir=tmp_path,
        keep_videos=False,
        cookie_str="buvid3=abc; SESSDATA=xyz",
        run_command=fake_run,
    )

    downloader.download(make_video())

    args = commands[0]
    assert "--cookies" in args
    cookie_idx = args.index("--cookies")
    cookie_path = args[cookie_idx + 1]
    assert not Path(cookie_path).exists()  # cleaned up after download


def test_download_cleans_up_cookie_file_on_error(tmp_path: Path):
    def failing_run(args: list[str]) -> None:
        raise AudioDownloadError("yt-dlp failed")

    downloader = AudioDownloader(
        data_dir=tmp_path,
        keep_videos=False,
        cookie_str="buvid3=abc",
        run_command=failing_run,
    )

    with pytest.raises(AudioDownloadError):
        downloader.download(make_video())

    temp_files = list(downloader.temp_dir.glob("*.txt"))
    assert temp_files == []
