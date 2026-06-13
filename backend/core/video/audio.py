"""Bilibili audio downloading via yt-dlp.

Wraps the yt-dlp CLI (validated in phase0). The command runner is
injectable so tests never spawn real processes.
"""

from pathlib import Path
import subprocess
import tempfile
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
        cookie_str: str | None = None,
        run_command: Callable[[list[str]], None] = run_command,
    ) -> None:
        self.data_dir = Path(data_dir).expanduser()
        self.keep_videos = keep_videos
        self.cookie_str = cookie_str
        self.run_command = run_command

    @property
    def temp_dir(self) -> Path:
        return self.data_dir / "videos" / "temp"

    def download(self, video: dict) -> Path:
        """Download audio of the first playlist item as WAV and return its path."""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        output_template = str(self.temp_dir / f"{video['id']}.%(ext)s")
        wav_path = self.temp_dir / f"{video['id']}.wav"

        args = [
            "yt-dlp",
            "--playlist-items", "1",
            "-x",
            "--audio-format", "wav",
            "--audio-quality", "0",
            "-o", output_template,
        ]

        cookie_file = None
        if self.cookie_str:
            cookie_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, dir=self.temp_dir
            )
            cookie_file.write("# Netscape HTTP Cookie File\n")
            for pair in self.cookie_str.split(";"):
                pair = pair.strip()
                if not pair:
                    continue
                name, value = pair.split("=", 1)
                cookie_file.write(
                    f".bilibili.com\tTRUE\t/\tTRUE\t0\t{name.strip()}\t{value.strip()}\n"
                )
            cookie_file.close()
            args.extend(["--cookies", cookie_file.name])

        args.append(video["url"])

        try:
            self.run_command(args)
        finally:
            if cookie_file is not None:
                Path(cookie_file.name).unlink(missing_ok=True)

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
