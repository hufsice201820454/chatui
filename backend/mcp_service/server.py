from mcp.server.fastmcp import FastMCP

from mcp_service.tools import (
    docx_parser,
    excel_parser,
    image_parser,
    oracle,
    pdf_parser,
    sqllite_db_tool,
)

mcp = FastMCP("chatui-mcp-server")

oracle.register(mcp)
image_parser.register(mcp)
docx_parser.register(mcp)
pdf_parser.register(mcp)
excel_parser.register(mcp)
sqllite_db_tool.register(mcp)

if __name__ == "__main__":
    mcp.run(transport="stdio")