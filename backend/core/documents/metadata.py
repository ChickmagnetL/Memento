"""Parse metadata from the header written by MarkdownDraftWriter.

The header format (see core.video.markdown.MarkdownDraftWriter.write) is::

    # {title}

    - Platform: {platform}
    - Video ID: {id}
    - Source URL: {url}

    ## Transcript
    ...
"""

from pathlib import Path

_FIELDS = {
    "- Platform: ": "platform",
    "- Video ID: ": "video_id",
    "- Source URL: ": "source_url",
}


def parse_markdown_metadata(path: Path) -> dict:
    """Return {title, platform, source_url, video_id} from a markdown header.

    Missing or unparseable fields are None. An unreadable file yields all-None.
    """
    result = {"title": None, "platform": None, "source_url": None, "video_id": None}
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return result

    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        result["title"] = lines[0][2:].strip()

    for line in lines[1:20]:
        for prefix, key in _FIELDS.items():
            if line.startswith(prefix):
                result[key] = line[len(prefix):].strip()
                break
    return result
