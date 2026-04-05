"""MCP tool: extract text from PDF files."""
from mcp.server.fastmcp import FastMCP

from mcp_service.tools.document_parser_common import parse_document

PDF_MIME = "application/pdf"


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def parse_pdf(
        file_base64: str,
        mime_type: str = PDF_MIME,
        filename: str = "",
        user_query: str = "",
    ) -> str:
        """Extract text from a PDF file. Pass file content as base64."""
        return await parse_document(file_base64, mime_type, filename)
