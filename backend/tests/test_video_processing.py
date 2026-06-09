"""Tests for the video processing pipeline skeleton."""

from pathlib import Path

from core.video.pipeline import VideoPipeline


def make_video(video_id: str, platform: str) -> dict:
    return {
        "id": video_id,
        "platform": platform,
        "title": "Example video",
        "url": f"https://example.com/{video_id}",
        "status": "pending",
    }


def test_process_bilibili_video_returns_success():
    pipeline = VideoPipeline()
    video = make_video("bilibili-1", "bilibili")

    result = pipeline.process(video)

    assert result.video_id == "bilibili-1"
    assert result.status == "completed"


def test_process_douyin_video_returns_success():
    pipeline = VideoPipeline()
    video = make_video("douyin-1", "douyin")

    result = pipeline.process(video)

    assert result.video_id == "douyin-1"
    assert result.status == "completed"


def test_process_is_deterministic_and_does_not_create_files(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    pipeline = VideoPipeline()
    video = make_video("bilibili-1", "bilibili")
    before = set(tmp_path.iterdir())

    first = pipeline.process(video)
    second = pipeline.process(video)

    assert first == second
    assert set(tmp_path.iterdir()) == before
