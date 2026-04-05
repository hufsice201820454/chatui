from abc import ABC, abstractmethod
from typing import AsyncGenerator, Any
from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    role: str  # user | assistant | tool
    content: str | list  # str or multi-part content blocks
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    name: str | None = None  # tool name for tool role


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    stop_reason: str = "end_turn"


class BaseLLMProvider(ABC):
    """Abstract interface every LLM provider must implement."""

    @abstractmethod
    async def generate(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Non-streaming completion."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Streaming completion – yields raw text tokens."""
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Estimate token count for a text string."""
        ...
