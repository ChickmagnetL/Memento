"""Memories REST API: list / create / delete (proposal accept reuses create)."""

from fastapi import APIRouter, HTTPException, Request, status

from schemas.memories import MemoryCreateRequest, MemoryResponse

router = APIRouter(prefix="/api/memories", tags=["memories"])


def _get_sqlite(request: Request):
    sqlite = getattr(request.app.state, "sqlite", None)
    if sqlite is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    return sqlite


@router.get("", response_model=list[MemoryResponse])
async def list_memories(request: Request):
    sqlite = _get_sqlite(request)
    return [MemoryResponse(**m) for m in await sqlite.list_memories()]


@router.post("", response_model=MemoryResponse)
async def create_memory(payload: MemoryCreateRequest, request: Request):
    sqlite = _get_sqlite(request)
    m = await sqlite.add_memory(content=payload.content, category=payload.category)
    return MemoryResponse(**m)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(memory_id: str, request: Request) -> None:
    sqlite = _get_sqlite(request)
    deleted = await sqlite.delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")