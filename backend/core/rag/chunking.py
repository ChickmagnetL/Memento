"""Markdown document chunking for RAG indexing.

Pure logic module: split a Phase 2C markdown draft into chunks with
metadata (title path, timestamps). No IO, no external dependencies.

Input contract: drafts produced by core.video.markdown.MarkdownDraftWriter
(`# title` header, optional metadata bullets, `## section` bodies).
"""

from dataclasses import dataclass
import re


# Matches "[MM:SS]" or "[HH:MM:SS]" timestamps produced by format_timestamp().
TIMESTAMP_PATTERN = re.compile(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]")


@dataclass(frozen=True)
class Chunk:
    video_id: str | None
    document_id: str
    chunk_index: int
    title_path: str
    text: str
    start_timestamp: str | None


def _split_sections(content: str) -> tuple[str, list[tuple[str, str]]]:
    """Split markdown into (doc_title, [(section_title, body), ...]).

    Lines before the first "## " heading (excluding the "# " title and
    metadata bullets) belong to an intro section with empty title.
    """
    doc_title = ""
    sections: list[tuple[str, str]] = []
    current_title = ""
    current_lines: list[str] = []

    for line in content.splitlines():
        if line.startswith("# ") and not doc_title:
            doc_title = line[2:].strip()
            continue
        if line.startswith("## "):
            if "".join(current_lines).strip():
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = line[3:].strip()
            current_lines = []
            continue
        current_lines.append(line)

    if "".join(current_lines).strip():
        sections.append((current_title, "\n".join(current_lines).strip()))

    return doc_title, sections


def _split_long_body(body: str, chunk_size: int, overlap: int) -> list[str]:
    """Greedily pack lines into pieces of at most chunk_size characters.

    Each piece after the first is prefixed with the tail (up to `overlap`
    characters) of the previous piece so adjacent chunks share context.
    A single line longer than chunk_size becomes its own piece (not cut).
    """
    if len(body) <= chunk_size:
        return [body]

    pieces: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in body.splitlines():
        line_len = len(line) + 1  # +1 for newline
        if current and current_len + line_len > chunk_size:
            pieces.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len
    if current:
        pieces.append("\n".join(current))

    if overlap <= 0:
        return pieces

    overlapped = [pieces[0]]
    for previous, piece in zip(pieces, pieces[1:]):
        overlapped.append(previous[-overlap:] + piece)
    return overlapped


def chunk_markdown(
    content: str,
    *,
    video_id: str | None,
    document_id: str,
    chunk_size: int,
    overlap: int,
) -> list[Chunk]:
    """Split a markdown draft into metadata-rich chunks."""
    if not content.strip():
        raise ValueError("empty markdown content")

    doc_title, sections = _split_sections(content)

    chunks: list[Chunk] = []
    for section_title, body in sections:
        # Skip pure metadata intro (bullets only, no transcript value).
        if not section_title and all(
            line.startswith("- ") or not line.strip()
            for line in body.splitlines()
        ):
            continue
        title_path = (
            f"{doc_title} > {section_title}" if section_title else doc_title
        )
        for piece in _split_long_body(body, chunk_size, overlap):
            text = f"{title_path}\n\n{piece}"
            match = TIMESTAMP_PATTERN.search(piece)
            chunks.append(
                Chunk(
                    video_id=video_id,
                    document_id=document_id,
                    chunk_index=len(chunks),
                    title_path=title_path,
                    text=text,
                    start_timestamp=match.group(1) if match else None,
                )
            )

    return chunks