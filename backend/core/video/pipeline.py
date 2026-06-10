"""Video processing pipeline."""

import asyncio
from uuid import uuid4

from pydantic import BaseModel

from core.video.bilibili import BilibiliSubtitleClient, BilibiliSubtitleError
from core.video.markdown import MarkdownDraftWriter
from schemas.video import VideoStatus


class VideoProcessingResult(BaseModel):
    video_id: str
    status: VideoStatus
    document_id: str | None = None
    document_path: str | None = None
    error: str | None = None


class VideoPipeline:
    def __init__(
        self,
        *,
        sqlite,
        data_dir,
        subtitle_client=None,
        draft_writer=None,
        bilibili_cookie: str = "",
    ) -> None:
        self.sqlite = sqlite
        self.subtitle_client = subtitle_client or BilibiliSubtitleClient(
            bilibili_cookie=bilibili_cookie
        )
        self.draft_writer = draft_writer or MarkdownDraftWriter(data_dir)

    async def process(self, video: dict) -> VideoProcessingResult:
        try:
            if video["platform"] != "bilibili":
                raise ValueError(f"unsupported platform: {video['platform']}")

            entries = await asyncio.to_thread(self.subtitle_client.fetch, video)
            if not entries:
                raise ValueError("No soft subtitles found")

            document_path = await asyncio.to_thread(
                self.draft_writer.write,
                video,
                entries,
            )
            document_id = uuid4().hex
            await self.sqlite.create_document(
                document_id=document_id,
                video_id=video["id"],
                file_path=str(document_path),
            )

            return VideoProcessingResult(
                video_id=video["id"],
                status="completed",
                document_id=document_id,
                document_path=str(document_path),
            )
        except (BilibiliSubtitleError, OSError, RuntimeError, ValueError) as exc:
            return VideoProcessingResult(
                video_id=video["id"],
                status="failed",
                error=str(exc),
            )
