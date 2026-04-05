"""
Session service – orchestrates LLM calls, tool execution, and history persistence.
"""
import json
import logging
from typing import AsyncGenerator, Optional

from src.datasource.sqlite.sqlite import AsyncSessionLocal
from src.core.schema.base import ChatMessage
from src.core.llm.context_manager import fit_context
from src.core.llm.factory import get_provider
from src.sessions import repository as repo
from src.tools import executor as tool_executor
from src.tools import registry as tool_registry

logger = logging.getLogger("chatui.sessions.service")


def _db_messages_to_chat(messages) -> list[ChatMessage]:
    result = []
    for m in messages:
        result.append(ChatMessage(
            role=m.role,
            content=m.content or "",
            tool_calls=m.tool_calls or [],
            tool_results=m.tool_results or [],
        ))
    return result


async def chat_stream(
    session_id: str,
    user_content: str,
    provider_name: Optional[str] = None,
    context_strategy: str = "sliding",
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Main chat pipeline:
    1. Load session + history
    2. Save user message
    3. Fit context
    4. Run tool loop (or plain stream if no tools active)
    5. Save assistant message
    Yields SSE strings.

    DB는 짧은 세션으로만 사용 — 스트리밍 전체를 한 트랜잭션으로 묶지 않음(SQLite locked 방지).
    """
    async with AsyncSessionLocal() as db:
        session = await repo.get_session(db, session_id)
        provider = get_provider(provider_name or session.provider)
        system_prompt = session.system_prompt
        session_title = session.title
        await repo.save_message(
            db,
            session_id=session_id,
            role="user",
            content=user_content,
            token_count=provider.count_tokens(user_content),
        )
        await db.flush()
        db_history = await repo.get_recent_messages_for_context(db, session_id)
        await db.commit()

    chat_history = _db_messages_to_chat(db_history)
    chat_history = await fit_context(chat_history, provider, strategy=context_strategy)

    active_tools = tool_registry.list_tools(active_only=True)
    tool_schemas = [t.to_openai() for t in active_tools]

    # Collect full assistant response for persistence
    assistant_content_parts: list[str] = []
    tool_calls_made: list[dict] = []

    async def _collect_and_yield():
        if tool_schemas:
            gen = tool_executor.run_tool_loop(
                provider, chat_history, system_prompt, tool_schemas, session_id, model=model
            )
        else:
            gen = tool_executor.stream_without_tools(provider, chat_history, system_prompt, model=model)

        async for sse_line in gen:
            # Parse to capture content for persistence
            if sse_line.startswith("data: "):
                try:
                    event = json.loads(sse_line[6:])
                    if event.get("type") == "text":
                        assistant_content_parts.append(event.get("content", ""))
                    elif event.get("type") == "tool_start":
                        tool_calls_made.append({"name": event["name"], "id": event["id"]})
                except Exception:
                    pass
            yield sse_line

    async for chunk in _collect_and_yield():
        yield chunk

    # Persist assistant response
    full_content = "".join(assistant_content_parts)
    async with AsyncSessionLocal() as db:
        await repo.save_message(
            db,
            session_id=session_id,
            role="assistant",
            content=full_content or None,
            tool_calls=tool_calls_made or None,
            token_count=provider.count_tokens(full_content) if full_content else None,
        )
        if session_title == "New Chat" and user_content:
            short = user_content[:60].replace("\n", " ")
            await repo.update_session(db, session_id, title=short)
        await db.commit()
