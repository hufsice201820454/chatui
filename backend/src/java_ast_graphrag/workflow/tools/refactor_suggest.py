"""refactor_suggest — 리팩터링 제안."""
from __future__ import annotations

from src.core.llm.factory import get_provider
from src.core.schema.base import ChatMessage
from src.java_ast_graphrag.models import RefactorFocus
from src.java_ast_graphrag.prompts.refactor_suggest import (
    REFACTOR_SUGGEST_SYSTEM,
    refactor_suggest_user,
)


async def run(assembled_context: str, focus: RefactorFocus = "complexity") -> str:
    system = REFACTOR_SUGGEST_SYSTEM.get(focus) or REFACTOR_SUGGEST_SYSTEM["complexity"]
    user = refactor_suggest_user(assembled_context, focus)
    resp = await get_provider().generate(
        [ChatMessage(role="user", content=user)],
        system_prompt=system,
    )
    return resp.content
