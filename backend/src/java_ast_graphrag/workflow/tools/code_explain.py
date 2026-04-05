"""code_explain — 프롬프트 + LLM."""
from __future__ import annotations

from src.core.llm.factory import get_provider
from src.core.schema.base import ChatMessage
from src.java_ast_graphrag.models import ExplainType
from src.java_ast_graphrag.prompts.code_explain import CODE_EXPLAIN_SYSTEM, code_explain_user


async def run(assembled_context: str, explain_type: ExplainType = "summary") -> str:
    system = CODE_EXPLAIN_SYSTEM.get(explain_type) or CODE_EXPLAIN_SYSTEM["summary"]
    user = code_explain_user(assembled_context, explain_type)
    resp = await get_provider().generate(
        [ChatMessage(role="user", content=user)],
        system_prompt=system,
    )
    return resp.content
