"""
Session & message data-access layer (BE-HIS-01 ~ BE-HIS-05).
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.model.models import Session, Message
from src.core.exceptions import SessionNotFoundError

logger = logging.getLogger("chatui.sessions.repo")


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

async def create_session(
    db: AsyncSession,
    *,
    title: str = "New Chat",
    provider: str = "openai",
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    meta: Optional[dict] = None,
) -> Session:
    session = Session(
        title=title,
        provider=provider,
        model=model,
        system_prompt=system_prompt,
        meta=meta,
    )
    db.add(session)
    await db.flush()
    logger.info("Created session %s", session.id)
    return session


async def get_session(db: AsyncSession, session_id: str) -> Session:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise SessionNotFoundError(session_id)
    return session


async def list_sessions(
    db: AsyncSession,
    *,
    limit: int = 20,
    cursor: Optional[str] = None,  # session.created_at ISO string
) -> tuple[list[Session], Optional[str]]:
    q = select(Session).order_by(desc(Session.created_at))

    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            q = q.where(Session.created_at < cursor_dt)
        except ValueError:
            pass

    q = q.limit(limit + 1)
    result = await db.execute(q)
    rows = result.scalars().all()

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = rows[-1].created_at.isoformat()

    return list(rows), next_cursor


async def update_session(
    db: AsyncSession,
    session_id: str,
    *,
    title: Optional[str] = None,
    summary: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> Session:
    session = await get_session(db, session_id)
    if title is not None:
        session.title = title
    if summary is not None:
        session.summary = summary
    if system_prompt is not None:
        session.system_prompt = system_prompt
    session.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return session


async def delete_session(db: AsyncSession, session_id: str) -> None:
    session = await get_session(db, session_id)
    await db.delete(session)
    await db.flush()
    logger.info("Deleted session %s", session_id)


# ---------------------------------------------------------------------------
# Message CRUD
# ---------------------------------------------------------------------------

async def save_message(
    db: AsyncSession,
    *,
    session_id: str,
    role: str,
    content: Optional[str],
    tool_calls: Optional[list] = None,
    tool_results: Optional[list] = None,
    token_count: Optional[int] = None,
    meta: Optional[dict] = None,
) -> Message:
    msg = Message(
        session_id=session_id,
        role=role,
        content=content,
        tool_calls=tool_calls,
        tool_results=tool_results,
        token_count=token_count,
        meta=meta,
    )
    db.add(msg)
    await db.flush()
    # Bump session updated_at
    await db.execute(
        Session.__table__.update()
        .where(Session.id == session_id)
        .values(updated_at=datetime.now(timezone.utc))
    )
    return msg


async def list_messages(
    db: AsyncSession,
    session_id: str,
    *,
    limit: int = 50,
    cursor: Optional[str] = None,  # message.created_at ISO string (newest first)
) -> tuple[list[Message], Optional[str]]:
    q = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(desc(Message.created_at))
    )

    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            q = q.where(Message.created_at < cursor_dt)
        except ValueError:
            pass

    q = q.limit(limit + 1)
    result = await db.execute(q)
    rows = result.scalars().all()

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = rows[-1].created_at.isoformat()

    return list(rows), next_cursor


async def search_messages(
    db: AsyncSession,
    session_id: str,
    query: str,
    *,
    limit: int = 20,
) -> list[Message]:
    """
    Full-text search using LIKE (SQLite) or can be extended to PostgreSQL FTS.
    For PostgreSQL, replace with: Message.content.match(query)
    """
    result = await db.execute(
        select(Message)
        .where(
            Message.session_id == session_id,
            Message.content.ilike(f"%{query}%"),
        )
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_recent_messages_for_context(
    db: AsyncSession,
    session_id: str,
    limit: int = 100,
) -> list[Message]:
    """Return messages in chronological order for LLM context building."""
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
        .limit(limit)
    )
    return list(result.scalars().all())
