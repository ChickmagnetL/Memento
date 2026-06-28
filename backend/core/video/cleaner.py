"""AI transcript cleaning: fix errors, punctuation, fillers, topic sections.

Splits the 2C draft into header (title + metadata bullets) and body,
sends only the body to the LLM, and re-attaches the header so video
metadata is never mangled by the model.
"""

import re


CLEANING_SYSTEM_PROMPT = (
    "You clean Chinese video transcripts. Rules:\n"
    "1. Fix recognition errors and add proper punctuation.\n"
    "2. Remove filler words (嗯/啊/就是说/那么 etc.) and repeated phrases.\n"
    "3. Reorganize content into topic sections, each starting with a "
    "'## <topic title>' heading.\n"
    "4. Every paragraph must keep the timestamp of its first source line, "
    "in the original [MM:SS] or [HH:MM:SS] format.\n"
    "5. Do not invent content. Do not translate. Output markdown only, "
    "no extra commentary.\n"
    "6. After the cleaned transcript, append two blocks on separate lines: "
    "first <summary>...</summary> with a 150-300 character paragraph summarizing "
    "what the video covers, then <brief>...</brief> with a single sentence "
    "(<=60 chars) describing the video's topic. Output both tags exactly once in lowercase."
)

TIMESTAMP_PATTERN = re.compile(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]")
SUMMARY_PATTERN = re.compile(r"<summary>\s*(.*?)\s*</summary>", re.DOTALL | re.IGNORECASE)
BRIEF_PATTERN = re.compile(r"<brief>\s*(.*?)\s*</brief>", re.DOTALL | re.IGNORECASE)


class CleaningError(Exception):
    pass


def _extract_tag(text: str, pattern: re.Pattern, label: str) -> str:
    m = pattern.search(text)
    if not m:
        raise CleaningError(f"Missing <{label}> tag in cleaned output")
    return m.group(1).strip()


class TranscriptCleaner:
    def __init__(self, *, chat_client) -> None:
        self.chat_client = chat_client

    @staticmethod
    def _split_header(draft: str) -> tuple[str, str]:
        """Split a 2C draft into (header block, transcript body)."""
        header, _, body = draft.partition("## Transcript")
        if not body:
            return "", draft.strip()
        return header.rstrip(), body.strip()

    def clean_with_summary(self, draft: str) -> tuple[str, str, str]:
        """Clean a draft and return (cleaned markdown, l2 summary, l3 brief)."""
        if not draft.strip():
            raise ValueError("empty draft")

        header, body = self._split_header(draft)
        had_timestamps = bool(TIMESTAMP_PATTERN.search(body))

        raw_output = self.chat_client.complete(
            [
                {"role": "system", "content": CLEANING_SYSTEM_PROMPT},
                {"role": "user", "content": body},
            ]
        ).strip()

        l2_summary = _extract_tag(raw_output, SUMMARY_PATTERN, "summary")
        l3_brief = _extract_tag(raw_output, BRIEF_PATTERN, "brief")

        cleaned_body = SUMMARY_PATTERN.sub("", raw_output)
        cleaned_body = BRIEF_PATTERN.sub("", cleaned_body).strip()

        if had_timestamps and not TIMESTAMP_PATTERN.search(cleaned_body):
            raise CleaningError("Cleaned output lost all timestamps")

        if header:
            cleaned_markdown = f"{header}\n\n{cleaned_body}\n"
        else:
            cleaned_markdown = f"{cleaned_body}\n"

        return cleaned_markdown, l2_summary, l3_brief

    def clean(self, draft: str) -> str:
        """Clean a draft and return the full cleaned markdown document."""
        cleaned_markdown, _, _ = self.clean_with_summary(draft)
        return cleaned_markdown
