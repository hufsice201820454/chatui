from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

from config import resolve_backend_path, settings


def load_sqlite_documents(limit: int | None = None) -> List[Dict[str, Any]]:
    """
    SQLITE_ITSM_TABLE 의 각 row 를 하나의 문서로 로드한다.

    - DB 경로: settings.SQLITE_DB_PATH
    - 테이블: settings.SQLITE_ITSM_TABLE
    - 각 row 의 모든 컬럼 값을 문자열로 이어 붙여 full_text 를 만든다.

    반환: [{"id": <doc_id>, "text": <full_text>, "meta": <row_dict>}, ...]
    """
    raw_path = getattr(settings, "SQLITE_DB_PATH", "./chatui_dev.db")
    path = resolve_backend_path(raw_path) or raw_path
    table = getattr(settings, "SQLITE_ITSM_TABLE", "itsm_tickets")

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        sql = f"SELECT * FROM {table}"
        if limit is not None and limit > 0:
            sql += " LIMIT ?"
            cur.execute(sql, (limit,))
        else:
            cur.execute(sql)
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    documents: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        row_dict = dict(row)
        # doc_id 우선순위: ticket_id / id / ROWID / row 인덱스
        raw_id = (
            row_dict.get("ticket_id")
            or row_dict.get("id")
            or row_dict.get("ROWID")
            or f"row_{idx}"
        )
        doc_id = str(raw_id)
        # None 제거 후 컬럼값 전부 문자열로 이어 붙이기
        parts = [str(v) for v in row_dict.values() if v is not None]
        full_text = " | ".join(parts)
        documents.append(
            {
                "id": doc_id,
                "text": full_text,
                "meta": row_dict,
            }
        )
    return documents

