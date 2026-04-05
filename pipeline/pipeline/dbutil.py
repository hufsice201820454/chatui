"""
SQLite DB 유틸리티 — 파이프라인 실행 이력 CRUD
"""
import datetime
import logging
from contextlib import contextmanager
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from config import SQLITE_DB_PATH
from pipeline.model import Base, PipelineExecHis

logger = logging.getLogger("pipeline.dbutil")

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(
            f"sqlite:///{SQLITE_DB_PATH}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(_engine)
    return _engine


@contextmanager
def get_db() -> Session:
    _get_engine()
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 실행 이력
# ---------------------------------------------------------------------------

def create_exec_his(
    pipeline_nm: str,
    dag_id: Optional[str] = None,
    run_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
) -> int:
    """실행 이력 레코드 생성 후 id 반환."""
    with get_db() as db:
        rec = PipelineExecHis(
            pipeline_nm=pipeline_nm,
            dag_id=dag_id,
            run_id=run_id,
            status="RUNNING",
            target_type=target_type,
            target_id=target_id,
            started_at=datetime.datetime.utcnow(),
        )
        db.add(rec)
        db.flush()
        exec_id = rec.id
    return exec_id


def update_exec_his(
    exec_id: int,
    status: str,
    total_cnt: int = 0,
    success_cnt: int = 0,
    fail_cnt: int = 0,
    error_msg: Optional[str] = None,
):
    """실행 이력 상태 업데이트."""
    with get_db() as db:
        rec = db.query(PipelineExecHis).filter(PipelineExecHis.id == exec_id).first()
        if rec:
            rec.status = status
            rec.total_cnt = total_cnt
            rec.success_cnt = success_cnt
            rec.fail_cnt = fail_cnt
            rec.error_msg = error_msg
            rec.finished_at = datetime.datetime.utcnow()


def get_exec_his(exec_id: int) -> Optional[PipelineExecHis]:
    with get_db() as db:
        return db.query(PipelineExecHis).filter(PipelineExecHis.id == exec_id).first()


# ---------------------------------------------------------------------------
# 사전 마스터/상세 조회
# ---------------------------------------------------------------------------

def fetch_all_dic_mas(db: Session) -> list:
    return db.execute(text(f"SELECT * FROM DIC_MAS WHERE status = 'Y'")).fetchall()


def fetch_dic_det_by_dic_id(db: Session, dic_id: str) -> list:
    return db.execute(
        text(f"SELECT * FROM DIC_DET WHERE dic_id = :dic_id AND status = 'Y'"),
        {"dic_id": dic_id},
    ).fetchall()
