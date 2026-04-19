import json
import logging
from typing import AsyncGenerator, Any

import openai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from config import settings
from src.core.exceptions import LLMError, LLMRateLimitError
from src.core.schema.base import BaseLLMProvider, ChatMessage, LLMResponse

logger = logging.getLogger("chatui.llm.openai")

_RETRYABLE = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
)


def _build_retry():
    return retry(
        reraise=True,
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(
            multiplier=1,
            min=settings.RETRY_MIN_WAIT,
            max=settings.RETRY_MAX_WAIT,
        ),
        retry=retry_if_exception_type(_RETRYABLE),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )


def _to_openai_messages(messages: list[ChatMessage]) -> list[dict]:
    result = []
    for msg in messages:
        if msg.role == "tool":
            for tr in msg.tool_results:
                result.append({
                    "role": "tool",
                    "tool_call_id": tr["tool_use_id"],
                    "content": tr["content"] if isinstance(tr["content"], str)
                               else json.dumps(tr["content"]),
                })
        elif msg.tool_calls:
            tool_calls_oai = []
            for tc in msg.tool_calls:
                tool_calls_oai.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc.get("input", {})),
                    },
                })
            result.append({
                "role": "assistant",
                "content": msg.content or None,
                "tool_calls": tool_calls_oai,
            })
        else:
            result.append({"role": msg.role, "content": msg.content or ""})
    return result


def _oai_tools_to_schema(tools: list[dict]) -> list[dict]:
    """Wrap tool definitions in OpenAI function format if not already."""
    converted = []
    for t in tools:
        if "type" in t and t["type"] == "function":
            converted.append(t)
        else:
            # Legacy tool schema shape; convert to OpenAI function format
            converted.append({
                "type": "function",
                "function": {
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                },
            })
    return converted


class OpenAIProvider(BaseLLMProvider):
    def __init__(self):
        api_key = getattr(settings, "OPENAI_API_KEY", None) or getattr(settings, "OPEN_API_KEY", None) # 하이닉스에서는 OPEN_API_KEY를 API_KEY로 변경
        base_url = getattr(settings, "OPEN_BASE_URL", None) # 하이닉스에서는 OPEN_BASE_URL을 BASE_URL로 변경
        if not api_key:
            raise ValueError("OPENAI_API_KEY or OPEN_API_KEY is not set in .env")
        self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = settings.OPENAI_MODEL
        self._max_tokens = settings.OPENAI_MAX_TOKENS

    async def generate(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        return await _build_retry()(self._generate)(messages, system_prompt, tools, **kwargs)

    async def _generate(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None,
        tools: list[dict] | None,
        **kwargs: Any,
    ) -> LLMResponse:
        try:
            all_messages = []
            if system_prompt:
                all_messages.append({"role": "system", "content": system_prompt})
            all_messages.extend(_to_openai_messages(messages))

            params: dict[str, Any] = dict(
                model=kwargs.get("model") or self._model,
                max_tokens=kwargs.get("max_tokens", self._max_tokens),
                messages=all_messages,
            )
            if tools:
                params["tools"] = _oai_tools_to_schema(tools)
                params["tool_choice"] = "auto"

            resp = await self._client.chat.completions.create(**params)
            choice = resp.choices[0]
            msg = choice.message

            text_content = msg.content or ""
            tool_calls = []
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "id": tc.id,
                        "name": tc.function.name,
                        "input": json.loads(tc.function.arguments or "{}"),
                    })

            return LLMResponse(
                content=text_content,
                tool_calls=tool_calls,
                input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
                output_tokens=resp.usage.completion_tokens if resp.usage else 0,
                model=resp.model,
                stop_reason=choice.finish_reason or "stop",
            )

        except openai.RateLimitError as e:
            raise LLMRateLimitError(str(e)) from e
        except openai.APIStatusError as e:
            raise LLMError(f"OpenAI API error: {e.message}", {"status": e.status_code}) from e
        except Exception as e:
            raise LLMError(f"Unexpected OpenAI error: {e}") from e

    async def stream(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        try:
            all_messages = []
            if system_prompt:
                all_messages.append({"role": "system", "content": system_prompt})
            all_messages.extend(_to_openai_messages(messages))

            params: dict[str, Any] = dict(
                model=kwargs.get("model") or self._model,
                max_tokens=kwargs.get("max_tokens", self._max_tokens),
                messages=all_messages,
                stream=True,
            )
            if tools:
                params["tools"] = _oai_tools_to_schema(tools)
                params["tool_choice"] = "auto"

            async for chunk in await self._client.chat.completions.create(**params):
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content

        except openai.RateLimitError as e:
            raise LLMRateLimitError(str(e)) from e
        except openai.APIStatusError as e:
            raise LLMError(f"OpenAI API error: {e.message}", {"status": e.status_code}) from e
        except Exception as e:
            raise LLMError(f"Unexpected OpenAI error: {e}") from e

    def count_tokens(self, text: str) -> int:
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model(self._model)
            return len(enc.encode(text))
        except Exception:
            return len(text) // 4
