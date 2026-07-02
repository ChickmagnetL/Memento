"""Tests for propose_memory tool + <user_memory> block injection."""

import pytest

from core.agent.chat_agent import build_system_prompt


def test_system_prompt_includes_user_memory_block_when_memories_exist():
    memories = [{"content": "在学 React"}, {"content": "偏好简洁"}]
    prompt = build_system_prompt(memories=memories)
    assert "<user_memory>" in prompt
    assert "</user_memory>" in prompt
    assert "在学 React" in prompt
    assert "偏好简洁" in prompt


def test_system_prompt_no_memory_block_when_empty():
    prompt = build_system_prompt(memories=[])
    assert "<user_memory>" not in prompt


def test_system_prompt_no_memory_block_when_none():
    prompt = build_system_prompt(memories=None)
    assert "<user_memory>" not in prompt


def test_system_prompt_memory_block_has_usage_instructions():
    """The <user_memory> block must tell the model to use it for user-related questions."""
    memories = [{"content": "在学 React"}]
    prompt = build_system_prompt(memories=memories)
    assert "<user_memory>" in prompt
    # The block must contain usage instructions, not just bare data
    assert "about THEMSELVES" in prompt
    assert "answer from this section FIRST" in prompt
    assert "Do NOT call search_knowledge for questions about the user" in prompt


def test_system_prompt_has_tool_routing_for_user_questions():
    """Tool routing must tell the model NOT to call search_knowledge for user-self questions."""
    prompt = build_system_prompt(memories=[{"content": "x"}])
    # There must be a routing rule directing user-self questions to <user_memory>
    # and away from search_knowledge, positioned before the search_knowledge rules.
    routing_header = prompt.index("## Tool Routing")
    user_rule = prompt.index(
        "answer from the user memory block; do NOT call search_knowledge",
        routing_header,
    )
    # The user-self rule must appear before the generic search_knowledge routing rule.
    search_rule = prompt.index("call search_knowledge", routing_header)
    assert user_rule < search_rule