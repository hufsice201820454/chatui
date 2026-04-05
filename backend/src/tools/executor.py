"""
Tool execution loop (BE-TOOL-02).
Drives the LLM → Tool call → Result → LLM cycle until the model stops
requesting tool calls or the max iteration limit is reached.

SSE events emitted:
  {"type": "tool_start", "name": ..., "id": ...}
  {"type": "tool_end",   "name": ..., "id": ..., "result": ...}
  {"type": "text",       "content": ...}
  {"type": "end",        "message_id": ..., "usage": {...}}
  {"type": "error",      "message": ...}
"""
import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Optional

from src.core.exceptions import ToolNotFoundError, ToolExecutionError
from src.core.schema.base import BaseLLMProvider, ChatMessage, LLMResponse
from src.tools import registry
from src.tools.tool_logger import ToolExecutionLogger

logger = logging.getLogger("chatui.tools.executor")

MAX_TOOL_ITERATIONS = 10


async def _execute_single_tool(
    tool_name: str,
    tool_call_id: str,
    tool_input: dict,
    session_id: str,
    message_id: Optional[str],
    tool_logger: ToolExecutionLogger,
) -> tuple[str, any]:
    """Execute one tool call and return (tool_call_id, result)."""
    handler = registry.get_handler(tool_name)
    if not handler:
        raise ToolNotFoundError(tool_name)

    start = time.perf_counter()
    error_str: Optional[str] = None
    result: any = None

    try:
        result = await handler(**tool_input)
    except Exception as exc:
        error_str = str(exc)
        logger.exception("Tool '%s' raised an error", tool_name)

    elapsed = round((time.perf_counter() - start) * 1000, 2)

    await tool_logger.log(
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        session_id=session_id,
        message_id=message_id,
        parameters=tool_input,
        result=result,
        error=error_str,
        execution_time_ms=elapsed,
    )

    if error_str:
        raise ToolExecutionError(tool_name, error_str)

    return tool_call_id, result


def _tool_result_message(tool_calls: list[dict], results: dict[str, any]) -> ChatMessage:
    """Build a tool-result ChatMessage (Anthropic format)."""
    tool_results = []
    for tc in tool_calls:
        res = results.get(tc["id"])
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": tc["id"],
            "content": json.dumps(res) if not isinstance(res, str) else res,
        })
    return ChatMessage(role="tool", content="", tool_results=tool_results)


async def run_tool_loop(
    provider: BaseLLMProvider,
    messages: list[ChatMessage],
    system_prompt: Optional[str],
    tools: list[dict],
    session_id: str,
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Agentic loop with SSE event streaming.
    Yields SSE-formatted strings.
    """
    tool_logger = ToolExecutionLogger()
    current_messages = list(messages)
    assistant_message_id: Optional[str] = None

    for iteration in range(MAX_TOOL_ITERATIONS):
        # --- Get LLM response (non-streaming for tool call detection) ---
        resp: LLMResponse = await provider.generate(
            current_messages,
            system_prompt=system_prompt,
            tools=tools,
            model=model,
        )

        if resp.content:
            yield _sse("text", {"content": resp.content})

        if not resp.tool_calls:
            # No more tool calls – done
            yield _sse("end", {
                "iteration": iteration + 1,
                "usage": {
                    "input_tokens": resp.input_tokens,
                    "output_tokens": resp.output_tokens,
                },
            })
            return

        # --- Emit tool_start events and execute in parallel ---
        tool_call_results: dict[str, any] = {}

        # Append assistant message with tool calls to history
        current_messages.append(ChatMessage(
            role="assistant",
            content=resp.content,
            tool_calls=resp.tool_calls,
        ))

        # Execute all tool calls concurrently
        tasks = []
        for tc in resp.tool_calls:
            yield _sse("tool_start", {"name": tc["name"], "id": tc["id"]})
            tasks.append(
                _execute_single_tool(
                    tc["name"],
                    tc["id"],
                    tc.get("input", {}),
                    session_id,
                    assistant_message_id,
                    tool_logger,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for item in results:
            if isinstance(item, Exception):
                yield _sse("error", {"message": str(item)})
                return
            call_id, result = item
            tool_call_results[call_id] = result

        for tc in resp.tool_calls:
            yield _sse("tool_end", {
                "name": tc["name"],
                "id": tc["id"],
                "result": tool_call_results.get(tc["id"]),
            })

        # Append tool results and continue loop
        current_messages.append(
            _tool_result_message(resp.tool_calls, tool_call_results)
        )

    yield _sse("error", {"message": f"Max tool iterations ({MAX_TOOL_ITERATIONS}) reached"})


async def stream_without_tools(
    provider: BaseLLMProvider,
    messages: list[ChatMessage],
    system_prompt: Optional[str],
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Simple text-only streaming (no tool loop)."""
    async for token in provider.stream(messages, system_prompt=system_prompt, model=model):
        yield _sse("text", {"content": token})
    yield _sse("end", {})


# ---------------------------------------------------------------------------
# SSE helper
# ---------------------------------------------------------------------------

def _sse(event_type: str, data: dict) -> str:
    payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
    return f"data: {payload}\n\n"
