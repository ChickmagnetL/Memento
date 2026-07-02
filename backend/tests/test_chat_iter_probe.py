"""Probe test: discover agent.run_stream_events() event types in the installed pydantic-ai.

Run with: pytest backend/tests/test_chat_iter_probe.py -s
The -s is REQUIRED to see prints (pytest captures stdout otherwise).
This test is the source of truth for event type names used in chat.py.

Background: an earlier probe confirmed agent.iter() yields graph NODES (no
token-level streaming) and event_stream_handler= is deprecated. The modern
API is agent.run_stream_events(); this probe confirms the event types and
attribute paths chat.py relies on:
  - FunctionToolCallEvent.part.tool_name
  - PartDeltaEvent.delta.content_delta  (delta is a TextPartDelta)
  - terminal event carrying .result.output
"""

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel


@pytest.mark.asyncio
async def test_probe_run_stream_events_types(capsys):
    """Print every event type agent.run_stream_events() yields, so we know the real API."""
    agent = Agent(TestModel(custom_output_text="hello world"), deps_type=str)

    @agent.tool
    async def echo(ctx, x: str) -> str:  # noqa: ARG001
        return x

    event_types = []
    async with agent.run_stream_events("hi", deps="d") as stream:
        async for event in stream:
            event_types.append(type(event).__name__)
            print(f"STREAM_EVENT: {type(event).__name__}  module={type(event).__module__}")
            # Inspect attributes for tool/text/result-bearing events.
            for attr in ("tool_name", "part", "delta", "result"):
                if hasattr(event, attr):
                    val = getattr(event, attr)
                    print(f"    .{attr} = {val!r}")
                    if attr == "part" and hasattr(val, "tool_name"):
                        print(f"    .part.tool_name = {val.tool_name!r}")
                    if attr == "delta" and hasattr(val, "content_delta"):
                        print(f"    .delta.content_delta = {val.content_delta!r}")
                    if attr == "result" and hasattr(val, "output"):
                        print(f"    .result.output = {val.output!r}")

    print("ALL_TYPES:", event_types)
    # Always pass — this is a discovery probe. Read its stdout manually.
    assert True
