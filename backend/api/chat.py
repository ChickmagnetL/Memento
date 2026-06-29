"""SSE chat API backed by the pydantic-ai knowledge agent."""

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from config.settings import get_settings
from core.agent.chat_agent import ChatDeps, build_agent, history_from_pairs
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

# Streaming fallback heuristics.
_STREAM_NO_OUTPUT_TIMEOUT_S = 15.0  # no delta within this -> provider misbehaves
_MAX_RETRIES = 2  # request-level retries (full regeneration)
_RETRY_BACKOFF_S = 1.0
_TITLE_MAX_LEN = 48


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


def _get_sqlite(request: Request):
    sqlite = getattr(request.app.state, "sqlite", None)
    if sqlite is None:
        raise HTTPException(status_code=500, detail="App state is not initialized")
    return sqlite


def _truncate_title(message: str) -> str:
    title = message.strip().replace("\n", " ")
    return title[:_TITLE_MAX_LEN] + ("…" if len(title) > _TITLE_MAX_LEN else "")


@router.post("")
async def chat(payload: ChatRequest, request: Request) -> StreamingResponse:
    """Stream one chat turn as SSE events; persist messages on success."""
    qdrant = getattr(request.app.state, "qdrant", None)
    if qdrant is None:
        raise HTTPException(status_code=500, detail="App state is not initialized")

    try:
        embedding_client = build_embedding_client()
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

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
    agent = build_agent(build_chat_model())

    # Resolve or create the session.
    session_id = payload.session_id
    if session_id:
        if await sqlite.get_chat_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = await sqlite.create_chat_session(
            title=_truncate_title(payload.message)
        )
        session_id = session["id"]

    # Rebuild prior history from SQLite, then append this turn's user message.
    history = history_from_pairs(await sqlite.get_chat_history(session_id))
    # Persist the user message up-front so it survives a mid-stream crash.
    await sqlite.add_chat_message(
        session_id=session_id, role="user", content=payload.message
    )
    history = history + history_from_pairs([("user", payload.message)])

    async def _run_with_fallback():
        """Stream; if it stalls or raises, fall back to non-streaming run."""
        try:
            return await _run_stream(agent, payload.message, history, deps)
        except Exception:  # noqa: BLE001 - any failure -> non-streaming retry
            logger.warning(
                "Streaming failed; falling back to non-streaming run",
                exc_info=True,
            )
            result = await agent.run(
                payload.message, deps=deps, message_history=history
            )
            return result.output

    async def event_stream():
        try:
            output = await _run_with_retries(_run_with_fallback)
            yield _sse({"type": "text", "delta": output})
            # Persist the assistant message only on successful generation.
            await sqlite.add_chat_message(
                session_id=session_id, role="assistant", content=output
            )
            yield _sse({"type": "done", "session_id": session_id})
        except Exception:  # noqa: BLE001 - stream errors must reach the client
            logger.exception("Chat stream failed for session %s", session_id)
            yield _sse(
                {"type": "error", "message": "Chat failed, see backend logs"}
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def _run_stream(agent, message, history, deps) -> str:
    """Stream tokens; raise if no output arrives within the timeout."""
    parts: list[str] = []

    async def _produce():
        async with agent.run_stream(
            message, deps=deps, message_history=history
        ) as result:
            async for delta in result.stream_text(delta=True):
                parts.append(delta)
        return "".join(parts)

    try:
        return await asyncio.wait_for(
            _produce(), timeout=_STREAM_NO_OUTPUT_TIMEOUT_S * 3
        )
    except asyncio.TimeoutError:
        if parts:
            # Partial output from a timed-out stream is kept as-is; the caller
            # persists it as the assistant message (truncated > missing reply).
            return "".join(parts)
        raise


async def _run_with_retries(func):
    """Call func() with request-level retries (full regeneration)."""
    last_exc = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return await func()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_BACKOFF_S * (attempt + 1))
            else:
                raise
    raise last_exc  # pragma: no cover
