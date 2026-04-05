"""
Tool registry management API (BE-TOOL-01, BE-TOOL-03, BE-TOOL-04).
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.responses import ok
from src.datasource.sqlite.sqlite import get_db
from src.model.models import ToolLog
from src.tools import registry
from src.tools.schemas import ToolDefinition, ToolInputSchema

router = APIRouter(prefix="/tools", tags=["Tools"])


class ToolEnableRequest(BaseModel):
    enabled: bool


class RegisterToolRequest(BaseModel):
    name: str
    description: str
    properties: dict = {}
    required: list[str] = []


# ---------------------------------------------------------------------------
# Tool registry endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_tools(role: Optional[str] = Query(None)):
    tools = registry.list_tools(role=role, active_only=False)
    return ok([
        {
            "name": t.name,
            "description": t.description,
            "enabled": registry._enabled.get(t.name, False),
            "schema": t.input_schema.model_dump(),
        }
        for t in tools
    ])


@router.get("/{tool_name}")
async def get_tool(tool_name: str):
    defn = registry.get_definition(tool_name)
    if not defn:
        from src.core.exceptions import ToolNotFoundError
        raise ToolNotFoundError(tool_name)
    return ok({
        "name": defn.name,
        "description": defn.description,
        "enabled": registry._enabled.get(defn.name, False),
        "schema": defn.input_schema.model_dump(),
        "openai_format": defn.to_openai(),
    })


@router.patch("/{tool_name}/enable")
async def set_tool_enabled(tool_name: str, body: ToolEnableRequest):
    registry.set_enabled(tool_name, body.enabled)
    return ok({"tool": tool_name, "enabled": body.enabled})


# ---------------------------------------------------------------------------
# Tool execution logs
# ---------------------------------------------------------------------------

@router.get("/logs/recent")
async def get_tool_logs(
    session_id: Optional[str] = Query(None),
    tool_name: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = select(ToolLog).order_by(ToolLog.created_at.desc()).limit(limit)
    if session_id:
        q = q.where(ToolLog.session_id == session_id)
    if tool_name:
        q = q.where(ToolLog.tool_name == tool_name)
    result = await db.execute(q)
    logs = result.scalars().all()
    return ok([
        {
            "id": log.id,
            "tool_name": log.tool_name,
            "tool_call_id": log.tool_call_id,
            "session_id": log.session_id,
            "parameters": log.parameters,
            "result": log.result,
            "error": log.error,
            "execution_time_ms": log.execution_time_ms,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ])
