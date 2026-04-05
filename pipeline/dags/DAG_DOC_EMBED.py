"""
DAG_DOC_EMBED — 문서(Document) 임베딩 DAG

스케줄: 매일 새벽 3시 (KST) = UTC 18:00
- S3 버킷의 지원 파일 목록 전체를 다운로드 → 청킹 → ChromaDB 임베딩
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from tasks.document_embedding import EmbeddingTask

default_args = {
    "owner": "chatui-pipeline",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
    "email_on_failure": False,
    "email_on_retry": False,
}


def _run_document_embedding(**context):
    task = EmbeddingTask(source_type="document")
    result = task.run(
        dag_id=context.get("dag").dag_id,
        run_id=context.get("run_id"),
    )
    return result


with DAG(
    dag_id="DAG_DOC_EMBED",
    default_args=default_args,
    description="S3 문서 → ChromaDB 전체 임베딩 (SQLite→chunk→embed→ChromaDB)",
    schedule_interval="0 18 * * *",  # UTC 18:00 = KST 03:00
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["embedding", "document", "itsm", "s3"],
    max_active_runs=1,
) as dag:

    embed_task = PythonOperator(
        task_id="document_embed",
        python_callable=_run_document_embedding,
        provide_context=True,
    )
