"""
Health check endpoints for the Memento API.

Author: Memento Team
Last Updated: 2026-06-07
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return a simple liveness status."""
    return {"status": "ok", "service": "memento-backend"}
