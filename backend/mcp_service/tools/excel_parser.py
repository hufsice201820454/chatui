"""MCP tool: extract text from Excel (.xlsx) files."""
from mcp.server.fastmcp import FastMCP

from mcp_service.tools.document_parser_common import parse_document

EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def parse_excel(
        file_base64: str,
        mime_type: str = EXCEL_MIME,
        filename: str = "",
        user_query: str = "",
    ) -> str:
        """Extract text from an Excel (.xlsx) file. All sheets. Pass file content as base64."""
        return await parse_document(file_base64, mime_type, filename)
