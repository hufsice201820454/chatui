"""
SQLAlchemy ORM 모델 (SQLite)
"""
from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()


class PipelineExecHis(Base):
    """파이프라인 실행 이력"""
    __tablename__ = "PIPELINE_EXEC_HIS"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_nm = Column(String(100), nullable=False, comment="파이프라인명")
    dag_id = Column(String(200), nullable=True, comment="Airflow DAG ID")
    run_id = Column(String(200), nullable=True, comment="Airflow Run ID")
    status = Column(String(20), nullable=False, default="RUNNING", comment="RUNNING|SUCCESS|FAIL")
    target_type = Column(String(50), nullable=True, comment="dictionary|document")
    target_id = Column(String(200), nullable=True, comment="대상 ID (doc_id 등)")
    total_cnt = Column(Integer, nullable=True, default=0)
    success_cnt = Column(Integer, nullable=True, default=0)
    fail_cnt = Column(Integer, nullable=True, default=0)
    error_msg = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)


class DicMas(Base):
    """사전 마스터 (용어집)"""
    __tablename__ = "DIC_MAS"

    dic_id = Column(String(50), primary_key=True, comment="사전 ID")
    dic_nm = Column(String(200), nullable=False, comment="사전명")
    category = Column(String(100), nullable=True, comment="카테고리")
    description = Column(Text, nullable=True, comment="설명")
    status = Column(String(10), nullable=False, default="Y", comment="Y|N")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class DicDet(Base):
    """사전 상세 (용어 항목)"""
    __tablename__ = "DIC_DET"

    det_id = Column(String(50), primary_key=True, comment="상세 ID")
    dic_id = Column(String(50), nullable=False, comment="FK → DIC_MAS.dic_id")
    term = Column(String(200), nullable=False, comment="용어")
    definition = Column(Text, nullable=True, comment="정의")
    synonyms = Column(Text, nullable=True, comment="동의어 (쉼표 구분)")
    source = Column(String(200), nullable=True, comment="출처")
    status = Column(String(10), nullable=False, default="Y", comment="Y|N")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
