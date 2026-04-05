"""
ITSM Agent HITL – REST (non-streaming) endpoints.

POST /api/v1/agent/chat         { user_query, parsed_docs? }
POST /api/v1/agent/chat/resume  { thread_id, action, edited? }
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from src.workflow import resume_agent, run_agent

router = APIRouter(prefix="/agent", tags=["Agent HITL"])
logger = logging.getLogger("chatui.api.agent_chat")


class AgentChatRequest(BaseModel):
    user_query: str
    parsed_docs: Optional[str] = None


class AgentResumeRequest(BaseModel):
    thread_id: str
    action: str  # approve | edit | reject
    edited: Optional[str] = None


@router.post("/chat")
async def agent_chat(body: AgentChatRequest):
    """최초 문의 실행 – run_agent() 호출 후 JSON 반환."""
    logger.info("agent_chat: query_len=%d", len(body.user_query))
    return await run_agent(body.user_query, parsed_docs=body.parsed_docs)


@router.post("/chat/resume")
async def agent_chat_resume(body: AgentResumeRequest):
    """HITL resume – resume_agent() 호출 후 JSON 반환."""
    logger.info(
        "agent_chat_resume: thread_id=%s action=%s", body.thread_id, body.action
    )
    return await resume_agent(body.thread_id, body.action, edited=body.edited)
