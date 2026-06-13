"""Bilibili audio downloading via yt-dlp.

Wraps the yt-dlp CLI (validated in phase0). The command runner is
injectable so tests never spawn real processes.
"""

from pathlib import Path
import subprocess
from typing import Callable


class AudioDownloadError(Exception):
    pass


def run_command(args: list[str]) -> None:
    """Run a CLI command, raising AudioDownloadError on failure."""
    result = subprocess.run(args, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise AudioDownloadError(
            f"{args[0]} exited with code {result.returncode}: "
            f"{result.stderr.strip()[-500:]}"
        )


class AudioDownloader:
    def __init__(
        self,
        *,
        data_dir,
        keep_videos: bool = False,
        run_command: Callable[[list[str]], None] = run_command,
    ) -> None:
        self.data_dir = Path(data_dir).expanduser()
        self.keep_videos = keep_videos
        self.run_command = run_command

    @property
    def temp_dir(self) -> Path:
        return self.data_dir / "videos" / "temp"

    def download(self, video: dict) -> Path:
        """Download audio of the first playlist item as WAV and return its path."""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        output_template = str(self.temp_dir / f"{video['id']}.%(ext)s")
        wav_path = self.temp_dir / f"{video['id']}.wav"

        self.run_command(
            [
                "yt-dlp",
                "--playlist-items", "1",
                "-x",
                "--audio-format", "wav",
                "--audio-quality", "0",
                "-o", output_template,
                video["url"],
            ]
        )

        if not wav_path.exists():
            raise AudioDownloadError(
                f"yt-dlp produced no WAV output at {wav_path}"
            )
        return wav_path

    def cleanup(self, wav_path: Path) -> None:
        """Remove or archive a temp WAV according to keep_videos."""
        if not wav_path.exists():
            return
        if self.keep_videos:
            target = self.data_dir / "videos" / wav_path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            wav_path.replace(target)
        else:
            wav_path.unlink()
