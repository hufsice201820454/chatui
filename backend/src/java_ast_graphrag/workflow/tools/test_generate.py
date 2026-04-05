"""test_generate — JUnit5/Mockito 코드 생성."""
from __future__ import annotations

from src.core.llm.factory import get_provider
from src.core.schema.base import ChatMessage
from src.java_ast_graphrag.prompts.test_generate import (
    TEST_GENERATE_SYSTEM,
    TEST_GENERATE_USER_TEMPLATE,
)


async def run(
    assembled_context: str,
    *,
    target_signature: str = "(시그니처 미지정 — 컨텍스트에서 추론)",
    dependency_list: str = "(컨텍스트에 명시된 의존성만 사용)",
) -> str:
    user = TEST_GENERATE_USER_TEMPLATE.format(
        assembled_context=assembled_context,
        target_signature=target_signature,
        dependency_list=dependency_list,
    )
    resp = await get_provider().generate(
        [ChatMessage(role="user", content=user)],
        system_prompt=TEST_GENERATE_SYSTEM,
    )
    return resp.content
