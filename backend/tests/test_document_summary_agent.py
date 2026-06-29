"""Tests for the lookup_documents and summarize_document agent tools.

Uses TestModel (no real LLM). TestModel calls every registered tool once and
echoes each tool's return value into its final text output.
"""

import pytest
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from core.agent.chat_agent import ChatDeps, build_agent
from core.rag.retrieval import SearchResult


class FakeRetriever:
    """Minimal retriever stand-in (async search)."""

    def __init__(self, results: list[SearchResult]):
        self.results = results

    async def search(self, query: str, *, top_k: int) -> list[SearchResult]:
        return self.results


class FakeSummaryStore:
    """DocumentSummaryStore-compatible stand-in.

    search_briefs returns Qdrant-payload-shaped dicts; get_or_generate returns
    a fixed (l2, l3) pair for any doc id NOT in ``missing_ids``, and raises
    ValueError for ids in ``missing_ids``.
    """

    def __init__(
        self,
        briefs=None,
        l2="paragraph summary",
        l3="one-sentence brief",
        missing_ids=None,
    ):
        self.briefs = briefs if briefs is not None else []
        self.l2 = l2
        self.l3 = l3
        self.missing_ids = missing_ids if missing_ids is not None else set()

    def search_briefs(self, *, query_vector, top_k) -> list[dict]:
        return self.briefs

    async def get_or_generate(self, document_id: str) -> tuple[str, str]:
        if document_id in self.missing_ids:
            raise ValueError(f"document {document_id} not found")
        return self.l2, self.l3


class FakeEmbedder:
    """Embedding client stand-in: synchronous .embed(list[str])."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


def _result(text: str) -> SearchResult:
    return SearchResult(
        video_id="v1", document_id="d1", chunk_index=0,
        title_path="示例视频 > Transcript", text=text,
        start_timestamp="02:35", score=0.9,
    )


def _deps(summary_store) -> ChatDeps:
    return ChatDeps(
        retriever=FakeRetriever([_result("片段内容")]),
        top_k=5,
        summary_store=summary_store,
        embedder=FakeEmbedder(),
    )


@pytest.mark.asyncio
async def test_lookup_documents_returns_top_k_briefs():
    briefs = [
        {
            "score": 0.9,
            "payload": {
                "document_id": "d1",
                "title": "示例视频",
                "brief": "片段简介",
            },
        }
    ]
    store = FakeSummaryStore(briefs=briefs)
    agent = build_agent(TestModel())

    result = await agent.run(
        "有哪些文档？", deps=_deps(store)
    )

    text = str(result.output)
    assert "示例视频" in text
    assert "片段简介" in text
    assert "doc_id: d1" in text


@pytest.mark.asyncio
async def test_summarize_document_returns_summary():
    store = FakeSummaryStore(l2="这是一段关于示例视频的段落级总结。")
    agent = build_agent(TestModel())

    result = await agent.run(
        "总结一下这个视频", deps=_deps(store)
    )

    text = str(result.output)
    assert "这是一段关于示例视频的段落级总结。" in text


@pytest.mark.asyncio
async def test_summarize_document_handles_missing():
    """When get_or_generate raises ValueError, the tool returns a not-found
    string. We invoke the tool function directly via a synthetic RunContext
    because TestModel cannot be made to call the tool with a specific doc_id."""
    store = FakeSummaryStore(missing_ids={"doc-missing"})
    agent = build_agent(TestModel())

    ctx = RunContext(deps=_deps(store), model=TestModel(), usage=RunUsage())
    tool_fn = agent._function_toolset.tools["summarize_document"].function  # type: ignore[attr-defined]

    output = await tool_fn(ctx, "doc-missing")
    assert output == "Document doc-missing not found."
