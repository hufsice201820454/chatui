"""
Airflow Task — 사전 임베딩 (VDB + Embedding 저장)
"""
import logging
from typing import Optional

from pipeline.core.dictionary_embedder import DictionaryEmbedder
from pipeline.dbutil import create_exec_his, update_exec_his

logger = logging.getLogger("pipeline.tasks.dictionary_embedding")


def run_dictionary_embedding(
    dag_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> dict:
    """전체 사전 데이터를 ChromaDB에 임베딩.

    Airflow PythonOperator callable로 사용:
        PythonOperator(
            task_id="dictionary_embed",
            python_callable=run_dictionary_embedding,
            op_kwargs={"dag_id": "{{ dag.dag_id }}", "run_id": "{{ run_id }}"},
        )
    """
    exec_id = create_exec_his(
        pipeline_nm="DICTIONARY_EMBEDDING",
        dag_id=dag_id,
        run_id=run_id,
        target_type="dictionary",
    )
    logger.info("DictionaryEmbedding start (exec_id=%d)", exec_id)

    try:
        embedder = DictionaryEmbedder()
        result = embedder.run_full()

        status = "SUCCESS" if result["fail"] == 0 else "PARTIAL"
        update_exec_his(
            exec_id=exec_id,
            status=status,
            total_cnt=result["total"],
            success_cnt=result["success"],
            fail_cnt=result["fail"],
        )
        logger.info("DictionaryEmbedding done: %s", result)
        return result

    except Exception as e:
        logger.error("DictionaryEmbedding failed: %s", e)
        update_exec_his(exec_id=exec_id, status="FAIL", error_msg=str(e))
        raise
