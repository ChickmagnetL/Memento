"""SSE chat API backed by the pydantic-ai knowledge agent."""

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    ModelRequest,
    PartDeltaEvent,
    SystemPromptPart,
    TextPartDelta,
)
from pydantic_ai.run import AgentRunResultEvent

from config.settings import get_settings
from core.agent.chat_agent import (
    ChatDeps,
    build_agent,
    build_system_prompt,
    history_from_pairs,
)
from core.rag.document_summary_store import DocumentSummaryStore
from core.models.factory import (
    build_chat_model as factory_build_chat_model,
    build_embedding_client,  # noqa: F401 - re-export for test monkeypatching
)
from core.rag.embedding import EmbeddingError
from core.rag.retrieval import HybridRetriever
from schemas.chat import ChatRequest

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)

# Streaming retry heuristics (full regeneration of run_stream_events()).
_MAX_RETRIES = 2
_RETRY_BACKOFF_S = 1.0


class _UnavailableEmbeddingClient:
    def __init__(self, error: EmbeddingError) -> None:
        self._error = error

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingError(str(self._error)) from self._error


def build_chat_model():
    """Build the chat model; raises HTTP 409 when unconfigured."""
    try:
        return factory_build_chat_model()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _format_chat_error(exc: BaseException) -> str:
    """Surface a useful, non-sensitive message for the chat SSE error event."""
    if isinstance(exc, ModelHTTPError):
        body = exc.body
        if isinstance(body, dict):
            msg = body.get("message")
            if not isinstance(msg, str) or not msg:
                err = body.get("error")
                msg = err.get("message") if isinstance(err, dict) else None
            if isinstance(msg, str) and msg:
                return f"HTTP {exc.status_code}: {msg}"
        return f"HTTP {exc.status_code}"
    return str(exc) or exc.__class__.__name__


def _get_sqlite(request: Request):
    sqlite = getattr(request.app.state, "sqlite", None)
    if sqlite is None:
        raise HTTPException(status_code=500, detail="App state is not initialized")
    return sqlite


def _extract_memory_proposals(result) -> list[str]:
    """Extract proposed memory contents from agent result."""
    proposals: list[str] = []
    if result is None or not hasattr(result, "all_messages"):
        return proposals
    for msg in result.new_messages():
        if hasattr(msg, "parts"):
            for part in msg.parts:
                if hasattr(part, "tool_name") and part.tool_name == "propose_memory" and hasattr(part, "args"):
                    args = part.args
                    if isinstance(args, str):
                        args = json.loads(args)
                    if isinstance(args, dict) and "content" in args:
                        proposals.append(args["content"])
    return proposals


@router.post("")
async def chat(payload: ChatRequest, request: Request) -> StreamingResponse:
    """Stream one chat turn as SSE events; persist messages on success."""
    qdrant = getattr(request.app.state, "qdrant", None)
    if qdrant is None:
        raise HTTPException(status_code=500, detail="App state is not initialized")

    try:
        embedding_client = build_embedding_client()
    except EmbeddingError as exc:
        logger.warning(
            "Embedding client unavailable for chat; retrieval tools will degrade",
            exc_info=True,
        )
        embedding_client = _UnavailableEmbeddingClient(exc)

    sqlite = _get_sqlite(request)
    settings = get_settings()
    retriever = HybridRetriever(
        embedding_client=embedding_client,
        qdrant=qdrant,
        weights=settings.rag.hybrid_weights,
    )
    summary_store = DocumentSummaryStore(
        sqlite=sqlite, qdrant=qdrant, embedding=embedding_client
    )
    deps = ChatDeps(
        retriever=retriever,
        top_k=settings.rag.top_k,
        summary_store=summary_store,
        embedder=embedding_client,
    )
    memories = await sqlite.list_memories()
    system_prompt = build_system_prompt(memories=memories)
    agent = build_agent(build_chat_model(), system_prompt=system_prompt)

    # Resolve session: caller must supply an existing session_id (created via
    # POST /api/sessions). Auto-creation was removed so new sessions appear in
    # the sidebar the instant the first message is sent.
    session_id = payload.session_id
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="session_id is required",
        )
    if await sqlite.get_chat_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Rebuild prior history from SQLite. Only PRIOR turns belong here — this
    # turn's user message is supplied separately via the `message` arg to
    # run_stream_events(). (Earlier code appended it here too, producing
    # duplicate user messages on every turn.)
    history = history_from_pairs(await sqlite.get_chat_history(session_id))
    # pydantic-ai 1.107 silently drops the Agent(system_prompt=...) kwarg
    # whenever message_history is non-empty, so the model would never see the
    # system prompt on any multi-turn conversation. Inject it explicitly as a
    # SystemPromptPart at the front of the history instead. (Verified by
    # capturing the outgoing HTTP request body — see /tmp/verify_fix.py.)
    if history:
        first = history[0]
        history[0] = ModelRequest(
            parts=[SystemPromptPart(content=system_prompt), *first.parts]
        )
    else:
        history = [ModelRequest(parts=[SystemPromptPart(content=system_prompt)])]
    # Persist the user message up-front so it survives a mid-stream crash.
    # On regenerate, the edited user message was already persisted by the
    # edit endpoint that triggered regeneration — don't double-persist.
    if not payload.regenerate:
        await sqlite.add_chat_message(
            session_id=session_id, role="user", content=payload.message
        )

    async def event_stream():
        try:
            result_holder: list = []
            accumulated: list[str] = []
            sent_any = False
            for attempt_i in range(_MAX_RETRIES + 1):
                try:
                    async for etype, epayload in _run_stream(
                        agent, payload.message, history, deps, result_holder,
                        accumulated,
                    ):
                        yield _sse({"type": etype, **epayload})
                        sent_any = True
                    break  # streamed successfully
                except asyncio.CancelledError:
                    # Client disconnected (ESC/stop): do NOT retry, persist, or
                    # emit an error event. Log at INFO and re-raise so Starlette
                    # tears the request down cleanly.
                    logger.info(
                        "Chat stream cancelled by client for session %s",
                        session_id,
                    )
                    raise
                except Exception as exc:  # noqa: BLE001 - any failure mid-run
                    if sent_any:
                        # Already showed content to the client — retrying would
                        # duplicate it. Surface the error and let the user retry.
                        raise
                    logger.warning(
                        "Streaming attempt %d failed", attempt_i, exc_info=True
                    )
                    if attempt_i < _MAX_RETRIES:
                        await asyncio.sleep(_RETRY_BACKOFF_S * (attempt_i + 1))
                    else:
                        raise

            result = result_holder[0] if result_holder else None
            final_output = getattr(result, "output", "") or ""
            # If the authoritative output is empty but deltas reached the client,
            # persist what the user actually saw.
            if not final_output and accumulated:
                final_output = "".join(accumulated)

            # Emit memory proposals before the terminal done event.
            # (_extract_memory_proposals already returns [] for a None result.)
            for content in _extract_memory_proposals(result):
                yield _sse({"type": "memory_proposal", "content": content})

            # Persist the assistant message only on successful generation.
            await sqlite.add_chat_message(
                session_id=session_id, role="assistant", content=final_output
            )
            yield _sse({"type": "done", "session_id": session_id})
        except asyncio.CancelledError:
            # Outer guard: a CancelledError that bypassed the inner try (e.g.
            # injected mid-await outside _run_stream) must still be re-raised
            # silently — no error SSE, no partial assistant persist.
            logger.info(
                "Chat stream cancelled by client for session %s",
                session_id,
            )
            raise
        except Exception as exc:  # noqa: BLE001 - stream errors must reach the client
            logger.exception("Chat stream failed for session %s", session_id)
            yield _sse({"type": "error", "message": _format_chat_error(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def _run_stream(agent, message, history, deps, result_holder: list,
                      accumulated: list[str]):
    """Stream the agent run via ``agent.run_stream_events()``, yielding SSE events.

    ``run_stream_events()`` is pydantic-ai's modern streaming API (the legacy
    ``event_stream_handler`` kwarg is deprecated). It yields token-level text
    deltas (``PartDeltaEvent``) AND tool-call events (``FunctionToolCallEvent``)
    in one stream, and runs the full agent graph. Unlike ``run_stream()`` — which
    stops the graph at the first output and can drop post-tool-call text — it
    never needs a non-streaming ``agent.run()`` fallback, which is the path that
    loses the system message on some OpenAI-compatible proxies (root cause of #7).
    Event type names/attributes are verified by tests/test_chat_iter_probe.py.

    The terminal ``AgentRunResultEvent``'s result is appended to ``result_holder``
    so the caller can extract memory proposals and persist the authoritative
    output. (``return value`` is forbidden in an async generator, so the result
    is handed back via the mutable list instead.) ``accumulated`` collects text
    deltas so the caller can fall back to them if the final output is empty.
    """
    # Cheap insurance: clear any stale result/deltas from a prior failed attempt.
    result_holder.clear()
    accumulated.clear()

    async with agent.run_stream_events(
        message, deps=deps, message_history=history
    ) as stream:
        async for event in stream:
            if isinstance(event, FunctionToolCallEvent):
                # Tool call starting: emit status (tool name kept raw, no mapping).
                yield ("status", {"state": "tool_call", "tool": event.part.tool_name})
            elif isinstance(event, PartDeltaEvent) and isinstance(
                event.delta, TextPartDelta
            ):
                delta_text = event.delta.content_delta or ""
                if delta_text:
                    accumulated.append(delta_text)
                    yield ("text", {"delta": delta_text})
            elif isinstance(event, AgentRunResultEvent):
                # Terminal event: capture authoritative result for the caller.
                result_holder.append(event.result)

    # Reconcile: if the authoritative final text differs from the streamed
    # deltas (rare — e.g. a provider drops the trailing delta), send a full
    # replace so the client ends with the correct text.
    final_text = ""
    if result_holder:
        final_text = getattr(result_holder[0], "output", "") or ""
    if final_text and final_text != "".join(accumulated):
        yield ("text_replace", {"content": final_text})
