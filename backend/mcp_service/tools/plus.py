from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def plus(a: int, b: int) -> int:
        return a + b

