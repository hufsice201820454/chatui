"""impact_assess — 변경 영향 평가."""
from __future__ import annotations

from src.core.llm.factory import get_provider
from src.core.schema.base import ChatMessage
from src.java_ast_graphrag.models import ChangeType
from src.java_ast_graphrag.prompts.impact_assess import IMPACT_ASSESS_SYSTEM, impact_assess_user


async def run(assembled_context: str, change_type: ChangeType = "modify") -> str:
    system = IMPACT_ASSESS_SYSTEM.get(change_type) or IMPACT_ASSESS_SYSTEM["modify"]
    user = impact_assess_user(assembled_context, change_type)
    resp = await get_provider().generate(
        [ChatMessage(role="user", content=user)],
        system_prompt=system,
    )
    return resp.content
