"""MCP tool: extract text from Word (.docx) files."""
from mcp.server.fastmcp import FastMCP

from mcp_service.tools.document_parser_common import parse_document

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def parse_docx(
        file_base64: str,
        mime_type: str = DOCX_MIME,
        filename: str = "",
        user_query: str = "",
    ) -> str:
        """Extract text from a Word (.docx) file. Pass file content as base64."""
        return await parse_document(file_base64, mime_type, filename)
