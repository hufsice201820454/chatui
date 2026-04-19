"""MCP 클라이언트 헬퍼 및 공유 OpenAI 클라이언트"""
import json
import asyncio
import sys
import os
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.core.llm.openai_provider import OpenAIProvider

_provider = OpenAIProvider()

# 프로젝트 루트 경로 (mcp_servers/ 위치 기준)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def _call_mcp_tool(server_script: str, tool_name: str, arguments: dict) -> Any:
    """MCP stdio 서버에 연결하여 tool을 호출하고 결과를 반환합니다."""
    server_path = os.path.join(_PROJECT_ROOT, server_script)
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_path],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            if result.content and len(result.content) > 0:
                content = result.content[0]
                if hasattr(content, "text"):
                    try:
                        return json.loads(content.text)
                    except json.JSONDecodeError:
                        return {"result": content.text}
            return {}


def run_async(coro) -> Any:
    """동기 컨텍스트에서 비동기 함수를 실행합니다."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def call_mcp(server_script: str, tool_name: str, arguments: dict) -> Any:
    """MCP Tool 동기 호출 래퍼."""
    return run_async(_call_mcp_tool(server_script, tool_name, arguments))


def call_chat_completion(messages: list[dict], max_tokens: int):
    """openai_provider를 통해 chat.completions 호출."""

    async def _call():
        return await _provider._client.chat.completions.create(
            model=_provider._model,
            max_tokens=max_tokens,
            messages=messages,
        )

    return run_async(_call())
