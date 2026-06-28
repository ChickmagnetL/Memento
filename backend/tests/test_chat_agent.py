"""Tests for the knowledge chat agent (TestModel, no real LLM)."""

import pytest
from pydantic_ai.models.test import TestModel

from core.agent.chat_agent import ChatDeps, build_agent
from core.rag.retrieval import SearchResult


class FakeRetriever:
    def __init__(self, results: list[SearchResult]):
        self.results = results
        self.queries: list[str] = []

    async def search(self, query: str, *, top_k: int) -> list[SearchResult]:
        self.queries.append(query)
        return self.results


def _result(text: str) -> SearchResult:
    return SearchResult(
        video_id="v1", document_id="d1", chunk_index=0,
        title_path="示例视频 > Transcript", text=text,
        start_timestamp="02:35", score=0.9,
    )


@pytest.mark.asyncio
async def test_agent_calls_search_tool_and_returns_text():
    retriever = FakeRetriever([_result("青蒿素相关内容")])
    # TestModel calls every registered tool once, then produces text.
    agent = build_agent(TestModel())

    result = await agent.run(
        "视频里讲了什么？",
        deps=ChatDeps(retriever=retriever, top_k=5),
    )

    assert retriever.queries  # tool was invoked
    assert isinstance(result.output, str)


@pytest.mark.asyncio
async def test_search_tool_formats_results_with_timestamps():
    retriever = FakeRetriever([_result("青蒿素相关内容")])
    agent = build_agent(TestModel())

    result = await agent.run(
        "查一下", deps=ChatDeps(retriever=retriever, top_k=5)
    )

    # TestModel echoes tool return values in its output; the tool output
    # must contain the title path and the timestamp marker.
    text = str(result.output)
    assert "示例视频 > Transcript" in text
    assert "02:35" in text


@pytest.mark.asyncio
async def test_search_tool_handles_empty_results():
    retriever = FakeRetriever([])
    agent = build_agent(TestModel())

    result = await agent.run(
        "查一下", deps=ChatDeps(retriever=retriever, top_k=5)
    )

    assert isinstance(result.output, str)


def test_history_from_pairs_builds_request_response_pairs():
    from core.agent.chat_agent import history_from_pairs

    history = history_from_pairs(
        [("user", "hello"), ("assistant", "hi there")]
    )
    # Alternating: user -> ModelRequest, assistant -> ModelResponse
    assert len(history) == 2
    from pydantic_ai.messages import ModelRequest, ModelResponse
    assert isinstance(history[0], ModelRequest)
    assert isinstance(history[1], ModelResponse)


def test_history_from_pairs_empty():
    from core.agent.chat_agent import history_from_pairs
    assert history_from_pairs([]) == []
