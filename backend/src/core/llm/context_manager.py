"""
Context window management (BE-LLM-04).

Strategies:
  1. Sliding window  – drop oldest non-system messages until token count fits.
  2. Auto-summary   – summarise oldest messages via the LLM, replace them with
                      a single summary message.
"""
import logging
from typing import TYPE_CHECKING

from config import settings
from src.core.schema.base import ChatMessage

if TYPE_CHECKING:
    from src.core.schema.base import BaseLLMProvider

logger = logging.getLogger("chatui.llm.context")


def _count_messages_tokens(messages: list[ChatMessage], provider: "BaseLLMProvider") -> int:
    total = 0
    for m in messages:
        text = m.content if isinstance(m.content, str) else str(m.content)
        total += provider.count_tokens(text)
    return total


def sliding_window(
    messages: list[ChatMessage],
    provider: "BaseLLMProvider",
    max_tokens: int | None = None,
) -> list[ChatMessage]:
    """Drop oldest messages (keeping the first user message) until within budget."""
    budget = max_tokens or int(settings.MAX_CONTEXT_TOKENS * settings.CONTEXT_SUMMARY_THRESHOLD)

    while _count_messages_tokens(messages, provider) > budget and len(messages) > 1:
        # Always keep the last message; drop the second-oldest
        messages.pop(1) if len(messages) > 2 else messages.pop(0)
        logger.debug("Sliding window: dropped 1 message, remaining=%d", len(messages))

    return messages


async def summarize_and_compress(
    messages: list[ChatMessage],
    provider: "BaseLLMProvider",
    max_tokens: int | None = None,
) -> list[ChatMessage]:
    """
    Summarise the first half of the conversation and replace those messages
    with a single summary assistant message.
    """
    budget = max_tokens or int(settings.MAX_CONTEXT_TOKENS * settings.CONTEXT_SUMMARY_THRESHOLD)

    if _count_messages_tokens(messages, provider) <= budget:
        return messages

    mid = max(2, len(messages) // 2)
    to_summarise = messages[:mid]
    to_keep = messages[mid:]

    history_text = "\n".join(
        f"{m.role.upper()}: {m.content if isinstance(m.content, str) else str(m.content)}"
        for m in to_summarise
    )

    summary_prompt = [
        ChatMessage(
            role="user",
            content=(
                "Please provide a concise summary of the following conversation "
                "so it can be used as context for continuing the discussion:\n\n"
                + history_text
            ),
        )
    ]

    try:
        resp = await provider.generate(summary_prompt)
        summary_msg = ChatMessage(
            role="assistant",
            content=f"[Earlier conversation summary]\n{resp.content}",
        )
        logger.info("Context compressed: %d messages → summary", mid)
        return [summary_msg] + to_keep
    except Exception as exc:
        logger.warning("Summarisation failed, falling back to sliding window: %s", exc)
        return sliding_window(messages, provider, budget)


async def fit_context(
    messages: list[ChatMessage],
    provider: "BaseLLMProvider",
    strategy: str = "sliding",  # sliding | summary
) -> list[ChatMessage]:
    """Ensure messages fit within the configured context budget."""
    budget = int(settings.MAX_CONTEXT_TOKENS * settings.CONTEXT_SUMMARY_THRESHOLD)

    if _count_messages_tokens(messages, provider) <= budget:
        return messages

    if strategy == "summary":
        return await summarize_and_compress(messages, provider, budget)
    else:
        return sliding_window(messages, provider, budget)
