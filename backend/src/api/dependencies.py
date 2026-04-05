"""
Common FastAPI dependencies.
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.datasource.sqlite.sqlite import get_db

# ---------------------------------------------------------------------------
# Rate limiter (no-op for skeleton – Redis 제거, 필요 시 인메모리/별도 구현)
# ---------------------------------------------------------------------------

async def chat_rate_limit() -> None:
    """채팅 요청 rate limit. 현재는 비활성(no-op)."""
    pass


# ---------------------------------------------------------------------------
# Re-export DB dependency for convenience
# ---------------------------------------------------------------------------

def db_session():
    return Depends(get_db)
