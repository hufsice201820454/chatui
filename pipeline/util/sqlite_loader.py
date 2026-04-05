"""
SQLite에서 ITSM 문서 메타데이터 로드
"""
import logging
import sqlite3
from typing import List, Dict, Any

from config import SQLITE_DB_PATH

logger = logging.getLogger("pipeline.util.sqlite_loader")


def load_sqlite_documents(
    table: str = "DOCUMENTS",
    status_col: str = "status",
    status_val: str = "Y",
    extra_where: str = "",
) -> List[Dict[str, Any]]:
    """SQLite 테이블에서 문서 메타데이터 목록을 반환한다.

    Returns:
        List of dicts with all columns of the table row.
    """
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        where_clause = f"WHERE {status_col} = ?"
        params: list = [status_val]
        if extra_where:
            where_clause += f" AND ({extra_where})"
        sql = f"SELECT * FROM {table} {where_clause}"
        logger.debug("load_sqlite_documents: %s", sql)
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError as e:
        logger.error("SQLite error loading '%s': %s", table, e)
        return []
    finally:
        conn.close()


def load_sqlite_query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """임의 SELECT 쿼리 실행."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError as e:
        logger.error("SQLite query error: %s", e)
        return []
    finally:
        conn.close()
