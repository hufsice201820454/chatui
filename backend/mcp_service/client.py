import re
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

from config import settings

DEFAULT_MCP_SSE_URL = "http://localhost:8001/sse"


async def _call_tool(name: str, arguments: dict[str, Any]) -> Any:
    mcp_sse_url = getattr(settings, "MCP_SSE_URL", None) or DEFAULT_MCP_SSE_URL
    async with sse_client(mcp_sse_url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments=arguments)

    if result.isError:
        err_text = None
        if result.content:
            texts: list[str] = []
            for block in result.content:
                if getattr(block, "type", None) == "text":
                    texts.append(getattr(block, "text", ""))
            if texts:
                err_text = "\n".join(texts).strip()
        raise RuntimeError(f"MCP tool call failed: {name}. {err_text or ''}".strip())

    if result.structuredContent is not None:
        return result.structuredContent

    if result.content:
        parts: list[str] = []
        for block in result.content:
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", ""))
        if parts:
            return "\n".join(parts).strip()

    raise ValueError(f"Unexpected MCP tool result: {name}")


async def call_plus_via_mcp(a: int, b: int) -> int:
    raw = await _call_tool("plus", {"a": a, "b": b})
    if isinstance(raw, dict):
        for value in raw.values():
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        m = re.search(r"-?\d+", raw)
        if m:
            return int(m.group(0))
    raise ValueError(f"Could not parse plus result: {raw}")


async def call_image_parse_via_mcp(image_base64: str, mime: str, user_query: str) -> str:
    raw = await _call_tool(
        "parse_image_with_vision_tool",
        {
            "image_base64": image_base64,
            "mime": mime,
            "user_query": user_query,
        },
    )
    if isinstance(raw, str):
        return raw
    return str(raw)


# MIME → MCP tool name for document parsing
_DOCUMENT_TOOL_BY_MIME = {
    "application/pdf": "parse_pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "parse_docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "parse_excel",
}


async def call_parse_document_via_mcp(
    file_base64: str,
    mime_type: str,
    filename: str = "",
) -> str:
    """Parse PDF/DOCX/XLSX via MCP. Returns extracted text or error message."""
    tool_name = _DOCUMENT_TOOL_BY_MIME.get(mime_type)
    if not tool_name:
        return f"Unsupported document type for parsing: {mime_type}"
    raw = await _call_tool(
        tool_name,
        {
            "file_base64": file_base64,
            "mime_type": mime_type,
            "filename": filename,
            "user_query": "",
        },
    )
    if isinstance(raw, str):
        return raw
    return str(raw)


async def call_search_itsm_via_mcp(query: str, limit: int = 20) -> Any:
    """
    sqllite_db_tool.search_itsm_tickets 호출 헬퍼.
    """
    return await _call_tool(
        "search_itsm_tickets",
        {
            "query": query,
            "limit": limit,
        },
    )


async def call_get_itsm_ticket_via_mcp(ticket_id: str) -> Any:
    """
    sqllite_db_tool.get_itsm_ticket_by_id 호출 헬퍼.
    """
    return await _call_tool(
        "get_itsm_ticket_by_id",
        {
            "ticket_id": ticket_id,
        },
    )

