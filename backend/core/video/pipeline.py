"""Video processing pipeline."""

import asyncio
import logging
from uuid import uuid4

from pydantic import BaseModel

from core.video.asr_client import AsrError
from core.video.audio import AudioDownloadError
from core.video.bilibili import (
    BilibiliSubtitleClient,
    BilibiliSubtitleError,
    REASON_MESSAGES,
    REASON_NO_SUBTITLES,
)
from core.video.douyin import DouyinError
from core.video.markdown import MarkdownDraftWriter
from core.video.youtube import YouTubeSubtitleClient, YouTubeSubtitleError
from schemas.video import VideoStatus

logger = logging.getLogger(__name__)


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
        cookie: str = "",
        audio_downloader=None,
        youtube_subtitle_client=None,
        youtube_audio_downloader=None,
        douyin_downloader=None,
        asr_client=None,
        asr_model: str = "iic/SenseVoiceSmall",
    ) -> None:
        self.sqlite = sqlite
        self.subtitle_client = subtitle_client or BilibiliSubtitleClient(
            cookie=cookie
        )
        self.draft_writer = draft_writer or MarkdownDraftWriter(data_dir)
        self.audio_downloader = audio_downloader
        self.youtube_subtitle_client = (
            youtube_subtitle_client or YouTubeSubtitleClient()
        )
        self.youtube_audio_downloader = youtube_audio_downloader
        self.douyin_downloader = douyin_downloader
        self.asr_client = asr_client
        self.asr_model = asr_model

    async def process(
        self, video: dict, *, allow_non_chinese: bool = False
    ) -> VideoProcessingResult:
        return await self._process(
            video, force_asr=False, allow_non_chinese=allow_non_chinese
        )

    async def process_with_asr(
        self, video: dict, *, allow_non_chinese: bool = False
    ) -> VideoProcessingResult:
        return await self._process(
            video, force_asr=True, allow_non_chinese=allow_non_chinese
        )

    async def _process(
        self,
        video: dict,
        *,
        force_asr: bool,
        allow_non_chinese: bool = False,
    ) -> VideoProcessingResult:
        try:
            platform = video["platform"]
            if force_asr and platform in ("bilibili", "youtube"):
                downloader = (
                    self.audio_downloader
                    if platform == "bilibili"
                    else self.youtube_audio_downloader
                )
                entries = await self._transcribe_fallback(video, downloader)
                if not entries:
                    raise ValueError(
                        "ASR processing requires the ASR service and "
                        f"{platform} downloader to be configured"
                    )
            elif platform == "bilibili":
                if hasattr(self.subtitle_client, "fetch_outcome"):
                    outcome = await asyncio.to_thread(
                        self.subtitle_client.fetch_outcome,
                        video,
                        allow_non_chinese=allow_non_chinese,
                    )
                    entries = outcome.entries
                    if getattr(outcome, "source", None) == "automatic":
                        entries = []
                        empty_error = BilibiliSubtitleError(
                            REASON_MESSAGES[REASON_NO_SUBTITLES],
                            reason=REASON_NO_SUBTITLES,
                        )
                    else:
                        empty_error = BilibiliSubtitleError(
                            outcome.message, reason=outcome.reason
                        )
                else:
                    entries = await asyncio.to_thread(
                        self.subtitle_client.fetch,
                        video,
                        allow_non_chinese=allow_non_chinese,
                    )
                    empty_error = BilibiliSubtitleError(
                        "This Bilibili video has no usable soft subtitles. You can transcribe it with ASR instead.",
                        reason="no_subtitles",
                    )
                if not entries:
                    raise empty_error
            elif platform == "douyin":
                entries = await self._transcribe_fallback(video, self.douyin_downloader)
                if not entries:
                    raise ValueError(
                        "Douyin processing requires the ASR service and "
                        "douyin downloader to be configured"
                    )
            elif platform == "youtube":
                outcome = await asyncio.to_thread(
                    self.youtube_subtitle_client.fetch_outcome,
                    video,
                    allow_non_chinese=allow_non_chinese,
                )
                entries = outcome.entries
                empty_error = YouTubeSubtitleError(
                    outcome.message, reason=outcome.reason
                )
                if not entries:
                    raise empty_error
            else:
                raise ValueError(f"unsupported platform: {video['platform']}")

            document_path = await asyncio.to_thread(
                self.draft_writer.write,
                video,
                entries,
            )
            document = await self.sqlite.get_document_by_video_and_path(
                video["id"], str(document_path)
            )
            if document is None:
                document_id = uuid4().hex
                await self.sqlite.create_document(
                    document_id=document_id,
                    video_id=video["id"],
                    file_path=str(document_path),
                )
            else:
                document_id = document["id"]

            return VideoProcessingResult(
                video_id=video["id"],
                status="completed",
                document_id=document_id,
                document_path=str(document_path),
            )
        except (AsrError, AudioDownloadError, BilibiliSubtitleError, DouyinError, YouTubeSubtitleError, OSError, RuntimeError, ValueError) as exc:
            return VideoProcessingResult(
                video_id=video["id"],
                status="failed",
                error=str(exc),
            )

    async def _transcribe_fallback(self, video: dict, downloader) -> list:
        """Download audio with the given downloader and transcribe."""
        if downloader is None or self.asr_client is None:
            return []

        wav_path = None
        try:
            wav_path = await asyncio.to_thread(downloader.download, video)
            logger.info(
                "Downloaded audio for %s: %s (%s bytes)",
                video["id"], wav_path, wav_path.stat().st_size,
            )
            result = await asyncio.to_thread(
                self.asr_client.transcribe, str(wav_path), model=self.asr_model
            )
            logger.info("ASR returned %s segments for %s", len(result), video["id"])
            return result
        except Exception:
            logger.exception("Transcribe fallback failed for %s, wav_path=%s", video["id"], wav_path)
            raise
        finally:
            if wav_path is not None:
                await asyncio.to_thread(downloader.cleanup, wav_path)
