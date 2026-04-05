"""
Session CRUD API (BE-HIS-01 ~ BE-HIS-05).
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.responses import ok, paginated
from src.datasource.sqlite.sqlite import get_db
from src.sessions import repository as repo

router = APIRouter(prefix="/sessions", tags=["Sessions"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    title: str = "New Chat"
    provider: str = "openai"
    model: Optional[str] = None
    system_prompt: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    system_prompt: Optional[str] = None


# ---------------------------------------------------------------------------
# Session endpoints
# ---------------------------------------------------------------------------

@router.post("")
async def create_session(body: CreateSessionRequest, db: AsyncSession = Depends(get_db)):
    session = await repo.create_session(
        db,
        title=body.title,
        provider=body.provider,
        model=body.model,
        system_prompt=body.system_prompt,
    )
    return ok(_session_dict(session))


@router.get("")
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    sessions, next_cursor = await repo.list_sessions(db, limit=limit, cursor=cursor)
    return paginated([_session_dict(s) for s in sessions], len(sessions), next_cursor)


@router.get("/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await repo.get_session(db, session_id)
    return ok(_session_dict(session))


@router.patch("/{session_id}")
async def update_session(
    session_id: str, body: UpdateSessionRequest, db: AsyncSession = Depends(get_db)
):
    session = await repo.update_session(
        db, session_id, title=body.title, system_prompt=body.system_prompt
    )
    return ok(_session_dict(session))


@router.delete("/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    await repo.delete_session(db, session_id)
    return ok({"deleted": session_id})


# ---------------------------------------------------------------------------
# Message endpoints
# ---------------------------------------------------------------------------

@router.get("/{session_id}/messages")
async def list_messages(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    messages, next_cursor = await repo.list_messages(
        db, session_id, limit=limit, cursor=cursor
    )
    return paginated([_msg_dict(m) for m in messages], len(messages), next_cursor)


@router.get("/{session_id}/messages/search")
async def search_messages(
    session_id: str,
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    messages = await repo.search_messages(db, session_id, q, limit=limit)
    return ok([_msg_dict(m) for m in messages])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_dict(s) -> dict:
    return {
        "id": s.id,
        "title": s.title,
        "summary": s.summary,
        "provider": s.provider,
        "model": s.model,
        "system_prompt": s.system_prompt,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


def _msg_dict(m) -> dict:
    return {
        "id": m.id,
        "session_id": m.session_id,
        "role": m.role,
        "content": m.content,
        "tool_calls": m.tool_calls,
        "tool_results": m.tool_results,
        "token_count": m.token_count,
        "meta": m.meta,
        "created_at": m.created_at.isoformat(),
    }
