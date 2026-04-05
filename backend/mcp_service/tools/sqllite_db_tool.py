from typing import Any, List, Dict

import sqlite3
from mcp.server.fastmcp import FastMCP

from config import resolve_backend_path, settings


def _get_sqlite_conn() -> sqlite3.Connection:
    """
    Settings 기반으로 SQLite 커넥션 생성.
    SQLITE_DB_PATH / SQLITE_DB_TIMEOUT 사용.
    """
    raw = getattr(settings, "SQLITE_DB_PATH", "./chatui_dev.db")
    path = resolve_backend_path(raw) or raw
    timeout = float(getattr(settings, "SQLITE_DB_TIMEOUT", 5.0))
    conn = sqlite3.connect(path, timeout=timeout)
    conn.row_factory = sqlite3.Row
    return conn


def _query_all(sql: str, params: tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
    with _get_sqlite_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
    return [dict(r) for r in rows]


def register(mcp: FastMCP) -> None:
    """
    SQLite 기반 ITSM / 일반 테이블 조회용 MCP 툴 등록.
    """
    itsm_table = getattr(settings, "SQLITE_ITSM_TABLE", "itsm_tickets")

    @mcp.tool()
    def search_itsm_tickets(query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        ITSM 테이블에서 query를 LIKE 검색.

        - 레거시: title, description, created_at
        - aa_dataset_tickets_multi_lang: subject, body, answer (title/description 없음)
        """
        like = f"%{query}%"
        # 테이블 컬럼에 맞게 검색 (없는 컬럼 참조 시 아래 폴백)
        sql_primary = f"""
        SELECT *
        FROM {itsm_table}
        WHERE subject LIKE ? OR body LIKE ? OR answer LIKE ?
        ORDER BY rowid DESC
        LIMIT ?
        """
        sql_legacy = f"""
        SELECT *
        FROM {itsm_table}
        WHERE title LIKE ? OR description LIKE ?
        ORDER BY created_at DESC
        LIMIT ?
        """
        try:
            return _query_all(sql_primary, (like, like, like, limit))
        except Exception:
            try:
                return _query_all(sql_legacy, (like, like, limit))
            except Exception as e:  # pragma: no cover - MCP 에러 전파용
                return [{"error": str(e)}]

    @mcp.tool()
    def get_itsm_ticket_by_id(ticket_id: str) -> Dict[str, Any]:
        """
        티켓 식별자로 한 건 조회 (ticket_id 컬럼 또는 subject/body에 포함된 경우).
        """
        sql_id = f"SELECT * FROM {itsm_table} WHERE ticket_id = ? LIMIT 1"
        sql_like = f"""
        SELECT * FROM {itsm_table}
        WHERE subject LIKE ? OR body LIKE ?
        LIMIT 1
        """
        try:
            rows = _query_all(sql_id, (ticket_id,))
            if rows:
                return rows[0]
            like = f"%{ticket_id}%"
            rows = _query_all(sql_like, (like, like))
            if rows:
                return rows[0]
            return {"error": f"Ticket not found: {ticket_id}"}
        except Exception as e:  # pragma: no cover
            return {"error": str(e)}

    @mcp.tool()
    def run_sqlite_query(sql: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        내부 디버깅용 raw SELECT 쿼리 실행.
        결과 행을 최대 limit 건까지 반환.
        """
        try:
            rows = _query_all(sql)
            return rows[:limit]
        except Exception as e:  # pragma: no cover
            return [{"error": str(e)}]

