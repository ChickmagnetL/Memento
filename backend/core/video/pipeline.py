"""Video processing pipeline skeleton."""

from pydantic import BaseModel

from schemas.video import VideoStatus


class VideoProcessingResult(BaseModel):
    video_id: str
    status: VideoStatus


class VideoPipeline:
    def process(self, video: dict) -> VideoProcessingResult:
        return VideoProcessingResult(video_id=video["id"], status="completed")
