"""SSE chat API backed by the pydantic-ai knowledge agent."""

import json
import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from config.settings import get_settings
from core.agent.chat_agent import ChatDeps, build_agent
from core.rag.embedding import CloudEmbeddingClient, EmbeddingError
from core.rag.retrieval import HybridRetriever
from schemas.chat import ChatRequest

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


def build_embedding_client() -> CloudEmbeddingClient:
    """Build the embedding client from settings (overridable in tests)."""
    embedding = get_settings().models.embedding
    return CloudEmbeddingClient(
        endpoint=embedding.endpoint,
        api_key=embedding.api_key,
        model=embedding.model,
    )


def build_chat_model():
    """Build the chat model from settings (overridable in tests)."""
    chat = get_settings().models.chat
    if not chat.api_key or not chat.model:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chat model is not configured (models.chat api_key/model)",
        )
    # OpenAI-compatible cloud endpoint (DeepSeek, SiliconFlow, ...).
    from pydantic_ai.models.openai import OpenAIModel
    from pydantic_ai.providers.openai import OpenAIProvider

    return OpenAIModel(
        chat.model,
        provider=OpenAIProvider(base_url=chat.endpoint, api_key=chat.api_key),
    )


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("")
async def chat(payload: ChatRequest, request: Request) -> StreamingResponse:
    """Stream one chat turn as SSE events."""
    qdrant = getattr(request.app.state, "qdrant", None)
    sessions = getattr(request.app.state, "chat_sessions", None)
    if qdrant is None or sessions is None:
        raise HTTPException(status_code=500, detail="App state is not initialized")

    try:
        embedding_client = build_embedding_client()
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    settings = get_settings()
    retriever = HybridRetriever(
        embedding_client=embedding_client,
        qdrant=qdrant,
        weights=settings.rag.hybrid_weights,
    )
    deps = ChatDeps(retriever=retriever, top_k=settings.rag.top_k)
    agent = build_agent(build_chat_model())

    session_id = payload.session_id or uuid4().hex
    history = sessions.get(session_id, [])

    async def event_stream():
        try:
            result = await agent.run(
                payload.message, deps=deps, message_history=history
            )
            yield _sse({"type": "text", "delta": result.output})
            sessions[session_id] = history + result.new_messages()
            yield _sse({"type": "done", "session_id": session_id})
        except Exception:  # noqa: BLE001 - stream errors must reach the client
            logger.exception("Chat stream failed for session %s", session_id)
            yield _sse({"type": "error", "message": "Chat failed, see backend logs"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
