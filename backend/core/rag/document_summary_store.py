"""Document summary storage and generation.

A small store that coordinates SQLite (L2 summary + L3 brief) and Qdrant
(L3 vector for brief search). Missing summaries are back-filled by calling
the configured chat completion model.
"""

import asyncio
import re
from pathlib import Path

from config.settings import get_settings
from core.models.chat_completion import (
    ChatCompletionError,
    CloudChatCompletionClient,
)
from core.rag.embedding import post_json


def _build_chat_completion_client() -> CloudChatCompletionClient:
    """Build the chat completion client from settings."""
    chat = get_settings().models.chat
    return CloudChatCompletionClient(
        endpoint=chat.endpoint,
        api_key=chat.api_key,
        model=chat.model,
        post_json=lambda url, payload, headers: post_json(
            url, payload, headers, timeout=300
        ),
    )


SUMMARY_PATTERN = re.compile(
    r"<summary>\s*(.*?)\s*</summary>", re.DOTALL | re.IGNORECASE
)
BRIEF_PATTERN = re.compile(
    r"<brief>\s*(.*?)\s*</brief>", re.DOTALL | re.IGNORECASE
)

_SUMMARY_PROMPT = (
    "Summarize the following markdown document.\n\n"
    "Provide exactly two outputs:\n"
    "1. A paragraph summary (multiple sentences) between <summary> and </summary>.\n"
    "2. A single-sentence brief description between <brief> and </brief>.\n\n"
    "Output only the two tags, with no extra commentary."
)


def read_markdown(path: str) -> str:
    """Return the text content of a markdown file."""
    return Path(path).read_text(encoding="utf-8")


def _extract_tag(text: str, pattern: re.Pattern, label: str) -> str:
    match = pattern.search(text)
    if not match:
        raise ChatCompletionError(f"Missing <{label}> tag in model output")
    return match.group(1).strip()


def generate_summary(
    markdown_text: str,
    chat_client: CloudChatCompletionClient | None = None,
) -> tuple[str, str]:
    """Call the configured chat model and extract <summary> and <brief>."""
    client = chat_client or _build_chat_completion_client()

    output = client.complete(
        [
            {"role": "system", "content": _SUMMARY_PROMPT},
            {"role": "user", "content": markdown_text},
        ]
    )

    l2_summary = _extract_tag(output, SUMMARY_PATTERN, "summary")
    l3_brief = _extract_tag(output, BRIEF_PATTERN, "brief")
    return l2_summary, l3_brief


class DocumentSummaryStore:
    def __init__(self, *, sqlite, qdrant, embedding=None) -> None:
        self.sqlite = sqlite
        self.qdrant = qdrant
        self.embedding = embedding

    async def save_summary(
        self, *, document_id: str, title: str, l2: str, l3: str, l3_vector: list[float]
    ) -> None:
        await self.sqlite.set_document_summary(document_id, l2=l2, l3=l3)
        self.qdrant.upsert_summary(
            document_id=document_id,
            vector=l3_vector,
            title=title,
            brief=l3,
        )

    async def get_summary(self, document_id: str) -> tuple[str, str] | None:
        return await self.sqlite.get_document_summary(document_id)

    def search_briefs(self, *, query_vector: list[float], top_k: int) -> list[dict]:
        return self.qdrant.search_summaries(vector=query_vector, top_k=top_k)

    async def get_or_generate(self, document_id: str) -> tuple[str, str]:
        existing = await self.sqlite.get_document_summary(document_id)
        if existing is not None:
            return existing

        doc = await self.sqlite.get_document(document_id)
        if doc is None:
            raise ValueError(f"document {document_id} not found")

        markdown = await asyncio.to_thread(read_markdown, doc["file_path"])
        l2, l3 = await asyncio.to_thread(generate_summary, markdown)

        if self.embedding:
            l3_vector = (await asyncio.to_thread(self.embedding.embed, [l3]))[0]
            await self.save_summary(
                document_id=document_id,
                title=doc.get("title") or "Untitled",
                l2=l2,
                l3=l3,
                l3_vector=l3_vector,
            )
        else:
            await self.sqlite.set_document_summary(document_id, l2=l2, l3=l3)

        return l2, l3
