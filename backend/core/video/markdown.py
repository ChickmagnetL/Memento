"""Markdown transcript draft writing helpers."""

from pathlib import Path

from core.documents.paths import raw_document_path
from core.video.bilibili import SubtitleEntry


def format_timestamp(seconds: float) -> str:
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    remaining_seconds = total_seconds % 60

    if hours:
        return f"[{hours:02d}:{minutes:02d}:{remaining_seconds:02d}]"
    return f"[{minutes:02d}:{remaining_seconds:02d}]"


class MarkdownDraftWriter:
    def __init__(self, data_dir) -> None:
        self.data_dir = Path(data_dir).expanduser()

    def path_for(self, video: dict) -> Path:
        """Return the canonical raw transcript path for a video."""
        return raw_document_path(self.data_dir, video["platform"], video["id"])

    def write(self, video: dict, entries: list[SubtitleEntry]) -> Path:
        if not entries:
            raise ValueError("empty transcript")

        path = self.path_for(video)
        path.parent.mkdir(parents=True, exist_ok=True)

        transcript_lines = [
            f"{format_timestamp(entry.start_seconds)} {entry.text}"
            for entry in entries
        ]
        content = "\n".join(
            [
                f"# {video['title']}",
                "",
                f"- Platform: {video['platform']}",
                f"- Video ID: {video['id']}",
                f"- Source URL: {video['url']}",
                f"- Author: {video.get('author', 'Unknown')}",
                "",
                "## Transcript",
                "",
                *transcript_lines,
            ]
        )
        path.write_text(f"{content}\n", encoding="utf-8")
        return path
