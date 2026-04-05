"""graph_search — 탐색 raw 텍스트 요약."""
from __future__ import annotations

from src.core.llm.factory import get_provider
from src.core.schema.base import ChatMessage
from src.java_ast_graphrag.prompts.graph_search import (
    GRAPH_SEARCH_SYSTEM,
    GRAPH_SEARCH_USER_TEMPLATE,
)


async def run(raw_graph_text: str) -> str:
    user = GRAPH_SEARCH_USER_TEMPLATE.format(raw_graph_text=raw_graph_text)
    resp = await get_provider().generate(
        [ChatMessage(role="user", content=user)],
        system_prompt=GRAPH_SEARCH_SYSTEM,
    )
    return resp.content
