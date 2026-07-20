"""Chat sessions REST API: list / create / get-messages / delete."""

from fastapi import APIRouter, HTTPException, Request, status

from schemas.sessions import (
    MessageEditRequest,
    MessageResponse,
    SessionCreateRequest,
    SessionResponse,
    SessionUpdateRequest,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

_TITLE_MAX_LEN = 48


def _get_sqlite(request: Request):
    sqlite = getattr(request.app.state, "sqlite", None)
    if sqlite is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    return sqlite


@router.get("", response_model=list[SessionResponse])
async def list_sessions(request: Request):
    sqlite = _get_sqlite(request)
    sessions = await sqlite.list_chat_sessions()
    return [SessionResponse(**s) for s in sessions]


@router.post("", response_model=SessionResponse)
async def create_session(payload: SessionCreateRequest, request: Request):
    sqlite = _get_sqlite(request)
    session = await sqlite.create_chat_session(title=payload.title)
    return SessionResponse(**session)


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(session_id: str, request: Request):
    sqlite = _get_sqlite(request)
    if await sqlite.get_chat_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = await sqlite.list_chat_messages(session_id)
    return [MessageResponse(**m) for m in messages]


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str, request: Request) -> None:
    sqlite = _get_sqlite(request)
    deleted = await sqlite.delete_chat_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str, payload: SessionUpdateRequest, request: Request
):
    sqlite = _get_sqlite(request)
    existing = await sqlite.get_chat_session(session_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if payload.title is None:
        return SessionResponse(**existing)
    updated = await sqlite.rename_chat_session(session_id, payload.title)
    if updated is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(**updated)


def _truncate_title(message: str) -> str:
    title = message.strip().replace("\n", " ")
    return title[:_TITLE_MAX_LEN] + ("…" if len(title) > _TITLE_MAX_LEN else "")


@router.patch(
    "/{session_id}/messages/{message_id}", response_model=MessageResponse
)
async def edit_message(
    session_id: str,
    message_id: str,
    payload: MessageEditRequest,
    request: Request,
):
    sqlite = _get_sqlite(request)
    if await sqlite.get_chat_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    msg = await sqlite.get_chat_message(message_id)
    if msg is None or msg["session_id"] != session_id:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg["role"] != "user":
        raise HTTPException(
            status_code=400,
            detail="Only user messages can be edited",
        )

    await sqlite.update_chat_message(message_id, payload.content)
    await sqlite.delete_messages_after(session_id, message_id)

    remaining = await sqlite.list_chat_messages(session_id)
    if remaining and remaining[0]["id"] == message_id:
        await sqlite.rename_chat_session(
            session_id, _truncate_title(payload.content)
        )

    updated = await sqlite.get_chat_message(message_id)
    return MessageResponse(**updated)


@router.delete("/{session_id}/messages/{message_id}")
async def delete_message(
    session_id: str, message_id: str, request: Request
) -> dict:
    sqlite = _get_sqlite(request)
    if await sqlite.get_chat_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    msg = await sqlite.get_chat_message(message_id)
    if msg is None or msg["session_id"] != session_id:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg["role"] != "user":
        raise HTTPException(
            status_code=400,
            detail="Only user messages can be deleted via this route",
        )

    deleted_ids: list[str] = [message_id]
    messages = await sqlite.list_chat_messages(session_id)
    for i, m in enumerate(messages):
        if m["id"] == message_id:
            if i + 1 < len(messages) and messages[i + 1]["role"] == "assistant":
                deleted_ids.append(messages[i + 1]["id"])
            break

    for mid in deleted_ids:
        await sqlite.delete_chat_message(mid)

    return {"deleted": deleted_ids}
