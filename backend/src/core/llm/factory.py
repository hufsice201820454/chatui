from functools import lru_cache

from config import settings
from src.core.schema.base import BaseLLMProvider


@lru_cache(maxsize=2)
def get_provider(provider: str | None = None) -> BaseLLMProvider:
    """Return a cached LLM provider instance (OpenAI only)."""
    name = (provider or settings.DEFAULT_LLM_PROVIDER).lower()
    if name == "openai":
        from src.core.llm.openai_provider import OpenAIProvider
        return OpenAIProvider()
    raise ValueError(f"Unknown LLM provider: {name!r}. Use 'openai'.")
