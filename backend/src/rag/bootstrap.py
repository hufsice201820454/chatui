from __future__ import annotations

from functools import lru_cache
from typing import Any

from config import settings
from src.rag.embeddings import Embedder
from src.rag.pipeline import RagPipeline
from src.rag.rag_pipeline import VDB_PATH
from src.rag.vector.chroma_store import ChromaStore
from src.rag.vector.sqlite_loader import load_sqlite_documents


@lru_cache(maxsize=1)
def get_rag_pipeline() -> RagPipeline:
    """
    전역 RAG 파이프라인 싱글톤.

    - SQLite ITSM 테이블에서 문서를 로드해 BM25 인덱스 구성
    - ChromaStore + OpenAI 호환 임베더를 사용해 시맨틱 검색

    주의:
    - 사전에 ingest_sqlite_to_chromadb() 를 실행해 벡터 인덱스를 생성해야 한다.
    """
    docs = load_sqlite_documents(limit=None)
    collection_name = getattr(settings, "RAG_COLLECTION_NAME", None) or "itsm_openai_bge_m3_1024"
    embedding_model = getattr(settings, "OPENAI_EMBEDDING_MODEL", None) or "bge-m3"
    chroma = ChromaStore(
        collection_name=collection_name,
        persist_directory=VDB_PATH,
    )
    embedder = Embedder(model_name=embedding_model)

    pipeline = RagPipeline(
        documents=docs,
        vector_store_client=chroma,
        embedder=embedder,
    )
    return pipeline
