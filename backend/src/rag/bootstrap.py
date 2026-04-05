from __future__ import annotations

from functools import lru_cache
from typing import Any

from src.rag.pipeline import RagPipeline
from src.rag.rag_pipeline import VDB_PATH
from src.rag.vector.bge_embedder import BgeM3Embedder
from src.rag.vector.chroma_store import ChromaStore
from src.rag.vector.sqlite_loader import load_sqlite_documents


@lru_cache(maxsize=1)
def get_rag_pipeline() -> RagPipeline:
    """
    전역 RAG 파이프라인 싱글톤.

    - SQLite ITSM 테이블에서 문서를 로드해 BM25 인덱스 구성
    - ChromaStore(itsm_bge_m3_chunks 컬렉션) + BGE-M3 임베더를 사용해 시맨틱 검색

    주의:
    - 사전에 ingest_sqlite_to_chromadb() 를 실행해 벡터 인덱스를 생성해야 한다.
    """
    docs = load_sqlite_documents(limit=None)
    chroma = ChromaStore(
        collection_name="itsm_bge_m3_chunks",
        persist_directory=VDB_PATH,
    )
    embedder = BgeM3Embedder()

    pipeline = RagPipeline(
        documents=docs,
        vector_store_client=chroma,
        embedder=embedder,
    )
    return pipeline
