"""Tests for douyin helpers."""

from pathlib import Path
from urllib.error import HTTPError

import pytest

from core.video.douyin import (
    DouyinAudioDownloader,
    DouyinError,
    DouyinMetadata,
    direct_aweme_id,
)


def test_direct_aweme_id_from_video_path():
    assert (
        direct_aweme_id("https://www.douyin.com/video/7640347491958803748")
        == "7640347491958803748"
    )


def test_direct_aweme_id_from_query_param():
    assert (
        direct_aweme_id("https://www.douyin.com/discover?modal_id=7640347491958803748")
        == "7640347491958803748"
    )


def test_direct_aweme_id_from_bare_id():
    assert direct_aweme_id("7640347491958803748") == "7640347491958803748"


def test_direct_aweme_id_none_for_share_link():
    # Short share links can't be resolved without network access.
    assert direct_aweme_id("https://v.douyin.com/abc123/") is None


def make_video() -> dict:
    return {
        "id": "video-1",
        "platform": "douyin",
        "title": "抖音示例",
        "url": "https://www.douyin.com/video/7640347491958803748",
        "status": "processing",
    }


def test_download_resolves_fetches_and_extracts(tmp_path: Path):
    events: list = []

    def fake_resolve_video_url(aweme_id: str, cookie: str) -> str:
        events.append(("resolve", aweme_id))
        return "https://cdn.example.com/video.mp4"

    def fake_fetch_bytes(url: str) -> bytes:
        events.append(("download", url))
        return b"MP4DATA"

    def fake_run_command(args: list[str]) -> None:
        events.append(("ffmpeg", args))
        Path(args[-1]).write_bytes(b"RIFF")

    downloader = DouyinAudioDownloader(
        data_dir=tmp_path,
        keep_videos=False,
        cookie="sessionid=test",
        resolve_video_url=fake_resolve_video_url,
        fetch_bytes=fake_fetch_bytes,
        run_command=fake_run_command,
    )

    wav_path = downloader.download(make_video())

    assert wav_path == tmp_path / "videos" / "temp" / "video-1.wav"
    assert wav_path.exists()
    assert events[0] == ("resolve", "7640347491958803748")
    assert events[1][0] == "download"
    ffmpeg_args = events[2][1]
    assert ffmpeg_args[0] == "ffmpeg"
    assert str(tmp_path / "videos" / "temp" / "video-1.mp4") in ffmpeg_args
    assert not (tmp_path / "videos" / "temp" / "video-1.mp4").exists()


def test_download_prefers_resolved_audio_url(tmp_path: Path):
    downloaded = []
    ffmpeg_inputs = []

    def fake_run_command(args: list[str]) -> None:
        ffmpeg_inputs.append(Path(args[args.index("-i") + 1]))
        Path(args[-1]).write_bytes(b"RIFF")

    downloader = DouyinAudioDownloader(
        data_dir=tmp_path,
        keep_videos=False,
        cookie="c",
        resolve_video_url=lambda aweme_id, cookie: DouyinMetadata(
            video_url="https://cdn.example.com/video.mp4",
            audio_url="https://cdn.example.com/audio.mp3",
        ),
        fetch_bytes=lambda url: downloaded.append(url) or b"AUDIODATA",
        run_command=fake_run_command,
    )

    wav_path = downloader.download(make_video())

    assert wav_path.exists()
    assert downloaded == ["https://cdn.example.com/audio.mp3"]
    assert [path.suffix for path in ffmpeg_inputs] == [".mp3"]
    assert not ffmpeg_inputs[0].exists()
    assert not (downloader.temp_dir / "video-1.mp4").exists()


def test_download_falls_back_to_video_when_audio_download_fails(tmp_path: Path):
    downloaded = []
    ffmpeg_inputs = []

    def fake_fetch_bytes(url: str) -> bytes:
        downloaded.append(url)
        if url.endswith("audio.mp3"):
            raise OSError("audio unavailable")
        return b"MP4DATA"

    def fake_run_command(args: list[str]) -> None:
        ffmpeg_inputs.append(Path(args[args.index("-i") + 1]))
        Path(args[-1]).write_bytes(b"RIFF")

    downloader = DouyinAudioDownloader(
        data_dir=tmp_path,
        keep_videos=False,
        cookie="c",
        resolve_video_url=lambda aweme_id, cookie: DouyinMetadata(
            video_url="https://cdn.example.com/video.mp4",
            audio_url="https://cdn.example.com/audio.mp3",
        ),
        fetch_bytes=fake_fetch_bytes,
        run_command=fake_run_command,
    )

    wav_path = downloader.download(make_video())

    assert wav_path.exists()
    assert downloaded == [
        "https://cdn.example.com/audio.mp3",
        "https://cdn.example.com/video.mp4",
    ]
    assert [path.suffix for path in ffmpeg_inputs] == [".mp4"]


def test_download_falls_back_to_video_when_audio_conversion_fails(tmp_path: Path):
    ffmpeg_inputs = []

    def fake_run_command(args: list[str]) -> None:
        input_path = Path(args[args.index("-i") + 1])
        ffmpeg_inputs.append(input_path)
        if input_path.suffix == ".mp3":
            raise RuntimeError("audio conversion failed")
        Path(args[-1]).write_bytes(b"RIFF")

    downloader = DouyinAudioDownloader(
        data_dir=tmp_path,
        keep_videos=False,
        cookie="c",
        resolve_video_url=lambda aweme_id, cookie: DouyinMetadata(
            video_url="https://cdn.example.com/video.mp4",
            audio_url="https://cdn.example.com/audio.mp3",
        ),
        fetch_bytes=lambda url: b"DATA",
        run_command=fake_run_command,
    )

    wav_path = downloader.download(make_video())

    assert wav_path.exists()
    assert [path.suffix for path in ffmpeg_inputs] == [".mp3", ".mp4"]
    assert not ffmpeg_inputs[0].exists()


def test_download_re_resolves_once_after_forbidden_video_url(tmp_path: Path):
    events: list = []
    resolved_urls = iter(
        [
            "https://cdn.example.com/expired.mp4",
            "https://cdn.example.com/fresh.mp4",
        ]
    )

    def fake_resolve_video_url(aweme_id: str, cookie: str) -> str:
        url = next(resolved_urls)
        events.append(("resolve", aweme_id, url))
        return url

    def fake_fetch_bytes(url: str) -> bytes:
        events.append(("download", url))
        if url.endswith("/expired.mp4"):
            raise HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)
        return b"MP4DATA"

    def fake_run_command(args: list[str]) -> None:
        events.append(("ffmpeg", args))
        Path(args[-1]).write_bytes(b"RIFF")

    downloader = DouyinAudioDownloader(
        data_dir=tmp_path,
        keep_videos=False,
        cookie="sessionid=test",
        resolve_video_url=fake_resolve_video_url,
        fetch_bytes=fake_fetch_bytes,
        run_command=fake_run_command,
    )

    wav_path = downloader.download(make_video())

    assert wav_path.exists()
    assert events[:4] == [
        (
            "resolve",
            "7640347491958803748",
            "https://cdn.example.com/expired.mp4",
        ),
        ("download", "https://cdn.example.com/expired.mp4"),
        (
            "resolve",
            "7640347491958803748",
            "https://cdn.example.com/fresh.mp4",
        ),
        ("download", "https://cdn.example.com/fresh.mp4"),
    ]
    assert events[4][0] == "ffmpeg"


def test_download_unresolvable_url_raises(tmp_path: Path):
    downloader = DouyinAudioDownloader(
        data_dir=tmp_path,
        keep_videos=False,
        cookie="c",
        resolve_video_url=lambda aweme_id, cookie: "https://cdn.example.com/v.mp4",
        fetch_bytes=lambda url: b"",
        run_command=lambda args: None,
    )
    video = make_video()
    video["url"] = "https://v.douyin.com/short/"

    with pytest.raises(DouyinError):
        downloader.download(video)


def test_cleanup_honors_keep_videos(tmp_path: Path):
    downloader = DouyinAudioDownloader(
        data_dir=tmp_path,
        keep_videos=True,
        cookie="c",
        resolve_video_url=lambda aweme_id, cookie: "u",
        fetch_bytes=lambda url: b"",
        run_command=lambda args: None,
    )
    downloader.temp_dir.mkdir(parents=True)
    wav = downloader.temp_dir / "video-1.wav"
    wav.write_bytes(b"RIFF")

    downloader.cleanup(wav)

    assert (tmp_path / "videos" / "video-1.wav").exists()
