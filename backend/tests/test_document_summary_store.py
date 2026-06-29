"""Tests for DocumentSummaryStore and its helper functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from core.models.chat_completion import ChatCompletionError
from core.rag import document_summary_store as summary_module
from core.rag.document_summary_store import (
    DocumentSummaryStore,
    generate_summary,
    read_markdown,
)


def test_read_markdown_returns_file_text(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text("# hello\n", encoding="utf-8")
    assert read_markdown(str(path)) == "# hello\n"


@pytest.mark.asyncio
async def test_save_and_get_summary():
    sqlite = AsyncMock()
    qdrant = MagicMock()
    store = DocumentSummaryStore(sqlite=sqlite, qdrant=qdrant)

    await store.save_summary(
        document_id="d1",
        title="React Hooks",
        l2="A longer summary.",
        l3="A brief sentence.",
        l3_vector=[0.1, 0.2, 0.3],
    )

    sqlite.set_document_summary.assert_awaited_once_with(
        "d1", l2="A longer summary.", l3="A brief sentence."
    )
    qdrant.upsert_summary.assert_called_once_with(
        document_id="d1",
        vector=[0.1, 0.2, 0.3],
        title="React Hooks",
        brief="A brief sentence.",
    )

    sqlite.get_document_summary.return_value = ("A longer summary.", "A brief sentence.")
    result = await store.get_summary("d1")
    assert result == ("A longer summary.", "A brief sentence.")
    sqlite.get_document_summary.assert_awaited_once_with("d1")


@pytest.mark.asyncio
async def test_search_briefs_returns_top_k():
    qdrant = MagicMock()
    qdrant.search_summaries.return_value = [
        {"score": 0.9, "payload": {"document_id": "d1", "brief": "one"}}
    ]
    store = DocumentSummaryStore(sqlite=AsyncMock(), qdrant=qdrant)

    results = await store.search_briefs(query_vector=[0.1, 0.2], top_k=3)

    qdrant.search_summaries.assert_called_once_with(
        vector=[0.1, 0.2], top_k=3
    )
    assert results == [
        {"score": 0.9, "payload": {"document_id": "d1", "brief": "one"}}
    ]


@pytest.mark.asyncio
async def test_get_or_generate_backfills_legacy_doc(monkeypatch):
    sqlite = AsyncMock()
    sqlite.get_document_summary.return_value = None
    sqlite.get_document.return_value = {
        "id": "d1",
        "file_path": "/tmp/d1.md",
        "title": "Legacy Doc",
    }

    qdrant = MagicMock()
    embedding = MagicMock()
    embedding.embed.return_value = [[0.1, 0.2, 0.3]]

    class FakeChatClient:
        def complete(self, messages):
            return (
                "<summary>paragraph</summary>\n"
                "<brief>brief</brief>"
            )

    store = DocumentSummaryStore(
        sqlite=sqlite,
        qdrant=qdrant,
        embedding=embedding,
        chat_client=FakeChatClient(),
    )

    monkeypatch.setattr(
        summary_module, "read_markdown", lambda path: "# Legacy markdown\n"
    )

    result = await store.get_or_generate("d1")

    assert result == ("paragraph", "brief")
    sqlite.get_document_summary.assert_awaited_once_with("d1")
    sqlite.get_document.assert_awaited_once_with("d1")
    sqlite.set_document_summary.assert_awaited_once_with(
        "d1", l2="paragraph", l3="brief"
    )
    qdrant.upsert_summary.assert_called_once_with(
        document_id="d1",
        vector=[0.1, 0.2, 0.3],
        title="Legacy Doc",
        brief="brief",
    )


@pytest.mark.asyncio
async def test_get_or_generate_returns_existing_summary():
    sqlite = AsyncMock()
    sqlite.get_document_summary.return_value = ("cached l2", "cached l3")
    qdrant = MagicMock()
    store = DocumentSummaryStore(sqlite=sqlite, qdrant=qdrant)

    result = await store.get_or_generate("d1")

    assert result == ("cached l2", "cached l3")
    sqlite.get_document.assert_not_awaited()
    qdrant.upsert_summary.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_generate_skips_qdrant_without_embedding(monkeypatch):
    # Without an embedder, only SQLite is updated.
    sqlite = AsyncMock()
    sqlite.get_document_summary.return_value = None
    sqlite.get_document.return_value = {
        "id": "d1",
        "file_path": "/tmp/d1.md",
        "title": None,
    }
    qdrant = MagicMock()

    class FakeChatClient:
        def complete(self, messages):
            return "<summary>l2</summary>\n<brief>l3</brief>"

    store = DocumentSummaryStore(
        sqlite=sqlite,
        qdrant=qdrant,
        embedding=None,
        chat_client=FakeChatClient(),
    )

    monkeypatch.setattr(summary_module, "read_markdown", lambda path: "text")

    await store.get_or_generate("d1")

    sqlite.set_document_summary.assert_awaited_once_with(
        "d1", l2="l2", l3="l3"
    )
    qdrant.upsert_summary.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_generate_missing_document_raises():
    sqlite = AsyncMock()
    sqlite.get_document_summary.return_value = None
    sqlite.get_document.return_value = None
    qdrant = MagicMock()

    store = DocumentSummaryStore(sqlite=sqlite, qdrant=qdrant)

    with pytest.raises(ValueError, match="document d1 not found"):
        await store.get_or_generate("d1")


def test_generate_summary_extracts_tags():
    class FakeClient:
        def complete(self, messages):
            return (
                "<summary>Paragraph summary here</summary>\n"
                "<brief>One sentence brief</brief>"
            )

    l2, l3 = generate_summary("# markdown", chat_client=FakeClient())

    assert l2 == "Paragraph summary here"
    assert l3 == "One sentence brief"


def test_generate_summary_raises_on_missing_tag():
    class FakeClient:
        def complete(self, messages):
            return "<summary>only summary</summary>"

    with pytest.raises(ChatCompletionError):
        generate_summary("# markdown", chat_client=FakeClient())
