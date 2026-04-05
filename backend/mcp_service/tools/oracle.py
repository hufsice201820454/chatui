from mcp.server.fastmcp import FastMCP
import oracledb

from config import settings


def register(mcp: FastMCP) -> None:
    oracle_port = getattr(settings, "ORACLE_PORT", 1521)
    oracle_host = getattr(settings, "ORACLE_HOST", "localhost")
    oracle_username = getattr(settings, "ORACLE_DATABASE_USER_NAME", "localhost")
    oracle_password = getattr(settings, "ORACLE_DATABASE_PASSWORD", "localhost")
    oracle_dsn = f"{oracle_host}:{oracle_port}"

    @mcp.tool()
    def query_oracle(sql: str) -> str:
        try:
            conn = oracledb.connect(
                user=oracle_username,
                password=oracle_password,
                dsn=oracle_dsn,
            )
            cursor = conn.cursor()
            cursor.execute(sql)
            result = cursor.fetchall()
            cursor.close()
            conn.close()
            return str(result)
        except oracledb.Error as e:
            return f"Error: {e}"

