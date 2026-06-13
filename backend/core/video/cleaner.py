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
    "no extra commentary."
)

TIMESTAMP_PATTERN = re.compile(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]")


class CleaningError(Exception):
    pass


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

    def clean(self, draft: str) -> str:
        """Clean a draft and return the full cleaned markdown document."""
        if not draft.strip():
            raise ValueError("empty draft")

        header, body = self._split_header(draft)
        had_timestamps = bool(TIMESTAMP_PATTERN.search(body))

        cleaned_body = self.chat_client.complete(
            [
                {"role": "system", "content": CLEANING_SYSTEM_PROMPT},
                {"role": "user", "content": body},
            ]
        ).strip()

        if had_timestamps and not TIMESTAMP_PATTERN.search(cleaned_body):
            raise CleaningError("Cleaned output lost all timestamps")

        if header:
            return f"{header}\n\n{cleaned_body}\n"
        return f"{cleaned_body}\n"
