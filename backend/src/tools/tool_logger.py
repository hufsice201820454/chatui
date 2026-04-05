"""
Tool execution logging (BE-TOOL-04).
Persists every tool invocation to the tool_logs table.
"""
import logging
import time
from typing import Any, Optional

from src.datasource.sqlite.sqlite import AsyncSessionLocal
from src.model.models import ToolLog

logger = logging.getLogger("chatui.tools.logger")


class ToolExecutionLogger:
    """도구 로그는 짧은 세션으로만 기록 — 스트리밍 중 긴 트랜잭션과 분리."""

    async def log(
        self,
        *,
        tool_name: str,
        tool_call_id: Optional[str],
        session_id: str,
        message_id: Optional[str],
        parameters: Optional[dict],
        result: Optional[Any],
        error: Optional[str],
        execution_time_ms: float,
    ) -> ToolLog:
        entry = ToolLog(
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            session_id=session_id,
            message_id=message_id,
            parameters=parameters,
            result=result if isinstance(result, dict) else {"value": str(result)},
            error=error,
            execution_time_ms=execution_time_ms,
        )
        async with AsyncSessionLocal() as db:
            db.add(entry)
            await db.commit()
        logger.info(
            "Tool executed",
            extra={
                "tool_name": tool_name,
                "session_id": session_id,
                "duration_ms": execution_time_ms,
                "error": error,
            },
        )
        return entry
