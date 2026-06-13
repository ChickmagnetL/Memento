"""Video processing pipeline."""

import asyncio
from uuid import uuid4

from pydantic import BaseModel

from core.video.asr_client import AsrError
from core.video.audio import AudioDownloadError
from core.video.bilibili import BilibiliSubtitleClient, BilibiliSubtitleError
from core.video.language import detect_asr_language
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
        audio_downloader=None,
        asr_client=None,
        asr_language: str = "auto",
    ) -> None:
        self.sqlite = sqlite
        self.subtitle_client = subtitle_client or BilibiliSubtitleClient(
            bilibili_cookie=bilibili_cookie
        )
        self.draft_writer = draft_writer or MarkdownDraftWriter(data_dir)
        self.audio_downloader = audio_downloader
        self.asr_client = asr_client
        self.asr_language = asr_language

    async def process(self, video: dict) -> VideoProcessingResult:
        try:
            if video["platform"] != "bilibili":
                raise ValueError(f"unsupported platform: {video['platform']}")

            entries = await asyncio.to_thread(self.subtitle_client.fetch, video)
            if not entries:
                entries = await self._transcribe_fallback(video)
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
        except (AsrError, AudioDownloadError, BilibiliSubtitleError, OSError, RuntimeError, ValueError) as exc:
            return VideoProcessingResult(
                video_id=video["id"],
                status="failed",
                error=str(exc),
            )

    async def _transcribe_fallback(self, video: dict) -> list:
        """Download audio and transcribe when no subtitles exist."""
        if self.audio_downloader is None or self.asr_client is None:
            return []

        wav_path = None
        try:
            wav_path = await asyncio.to_thread(self.audio_downloader.download, video)
            language = detect_asr_language(
                video["title"], override=self.asr_language
            )
            return await asyncio.to_thread(
                self.asr_client.transcribe, str(wav_path), language=language
            )
        finally:
            if wav_path is not None:
                await asyncio.to_thread(self.audio_downloader.cleanup, wav_path)
