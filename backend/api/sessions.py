"""Chat sessions REST API: list / create / get-messages / delete."""

from fastapi import APIRouter, HTTPException, Request

from schemas.sessions import (
    MessageResponse,
    SessionCreateRequest,
    SessionResponse,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


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


@router.delete("/{session_id}")
async def delete_session(session_id: str, request: Request):
    sqlite = _get_sqlite(request)
    deleted = await sqlite.delete_chat_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return True
