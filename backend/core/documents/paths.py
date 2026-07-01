"""Canonical paths for knowledge markdown documents."""

from pathlib import Path


def normalize_clean_stem(stem: str) -> str:
    """Collapse every trailing .clean suffix from a markdown stem."""
    normalized = stem
    while normalized.endswith(".clean"):
        normalized = normalized.removesuffix(".clean")
    return normalized


def raw_document_path(data_dir, platform: str, video_id: str) -> Path:
    """Return the canonical raw transcript path for a video."""
    return (
        Path(data_dir).expanduser()
        / "knowledge"
        / platform
        / "raw"
        / f"{video_id}.md"
    )


def cleaned_document_path_for_source(source_path, video_id: str | None = None) -> Path:
    """Return the cleaned transcript path matching a source markdown path."""
    path = Path(source_path)
    if path.parent.name in {"raw", "cleaned"}:
        platform_dir = path.parent.parent
    else:
        platform_dir = path.parent
    filename_stem = video_id or normalize_clean_stem(path.stem)
    return platform_dir / "cleaned" / f"{filename_stem}.md"


def preferred_clean_source_path(source_path, video_id: str | None = None) -> Path:
    """Prefer the matching raw draft when re-cleaning an already cleaned file."""
    path = Path(source_path)
    filename_stem = video_id or normalize_clean_stem(path.stem)

    if path.parent.name == "cleaned":
        raw_candidate = path.parent.parent / "raw" / f"{filename_stem}.md"
        if raw_candidate.exists():
            return raw_candidate

    if normalize_clean_stem(path.stem) != path.stem:
        if path.parent.name in {"raw", "cleaned"}:
            platform_dir = path.parent.parent
        else:
            platform_dir = path.parent
        raw_candidate = platform_dir / "raw" / f"{filename_stem}.md"
        if raw_candidate.exists():
            return raw_candidate

        raw_candidate = path.with_name(f"{filename_stem}.md")
        if raw_candidate.exists():
            return raw_candidate

    return path


def is_raw_document_path(path) -> bool:
    """Return True for knowledge/{platform}/raw/{video_id}.md paths."""
    path = Path(path)
    return (
        path.suffix == ".md"
        and path.parent.name == "raw"
        and path.parent.parent.parent.name == "knowledge"
    )
