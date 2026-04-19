"""Admin endpoints for ast_graphdb ingestion."""
from __future__ import annotations

from fastapi import APIRouter

from src.core.responses import ok
from src.services.ast_ingestion_service import run_ast_ingestion

router = APIRouter(prefix="/admin/ingestion", tags=["Admin Ingestion"])


@router.post("/run")
async def run_ingestion():
    result = run_ast_ingestion()
    return ok(result)
