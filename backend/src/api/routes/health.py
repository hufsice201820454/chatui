"""
Health check endpoints (BE-INF-05).
GET /health  – liveness probe
GET /ready   – readiness probe (DB만 검사, Redis 제거)
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.responses import ok
from src.datasource.sqlite.sqlite import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health():
    return ok({"status": "ok"})


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)):
    checks: dict[str, str] = {}

    # DB check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    all_ok = all(v == "ok" for v in checks.values())
    return ok({"status": "ok" if all_ok else "degraded", "checks": checks})
