"""
DAG_DIC_EMBED — 사전(Dictionary) 임베딩 DAG

스케줄: 매일 새벽 2시 (한국 시간 기준 UTC+9 → UTC 17:00)
- DIC_MAS / DIC_DET 테이블 전체를 ChromaDB에 full-refresh 임베딩
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from tasks.dictionary_embedding import run_dictionary_embedding

default_args = {
    "owner": "chatui-pipeline",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
    "email_on_retry": False,
}

with DAG(
    dag_id="DAG_DIC_EMBED",
    default_args=default_args,
    description="사전(DIC_MAS/DIC_DET) → ChromaDB 전체 임베딩 (full-refresh)",
    schedule_interval="0 17 * * *",  # UTC 17:00 = KST 02:00
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["embedding", "dictionary", "itsm"],
    max_active_runs=1,
) as dag:

    embed_task = PythonOperator(
        task_id="dictionary_embed",
        python_callable=run_dictionary_embedding,
        op_kwargs={
            "dag_id": "{{ dag.dag_id }}",
            "run_id": "{{ run_id }}",
        },
    )
