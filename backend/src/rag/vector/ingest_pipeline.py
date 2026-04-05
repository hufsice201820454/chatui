from __future__ import annotations

"""
SQLite → BGE-M3 로컬 임베딩 → Chroma (itsm_bge_m3_chunks).

`src.rag.rag_pipeline`(OpenAIEmbeddings) 과 차원이 다르므로, 동일 파이프라인을 쓰려면
`ingest_openai_pipeline` 모듈을 실행하세요.
"""
from typing import Any, Dict, List

from config import settings
from src.rag.rag_pipeline import VDB_PATH as RAG_VDB_PATH
from src.utils.chunker import chunk_text, chunks_to_dicts

from .bge_embedder import BgeM3Embedder
from .chroma_store import ChromaStore
from .sqlite_loader import load_sqlite_documents


def ingest_sqlite_to_chromadb(
    limit: int | None = None,
    chunk_size: int = 1000,
    overlap: int = 200,
    collection_name: str = "itsm_bge_m3_chunks",
    persist_directory: str | None = None,
) -> None:
    """
    SQLite ITSM 데이터 -> full_text -> chunk -> BGE-M3 임베딩 -> ChromaDB 저장.
    """
    if persist_directory is None:
        persist_directory = RAG_VDB_PATH

    # 1) SQLite에서 문서 로딩
    docs = load_sqlite_documents(limit=limit)
    if not docs:
        return

    # 2) 청크 생성
    chunk_ids: List[str] = []
    chunk_texts: List[str] = []
    chunk_metas: List[Dict[str, Any]] = []

    for doc in docs:
        doc_id = str(doc["id"])
        text = doc["text"]
        meta = doc["meta"]

        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap, doc_id=doc_id)
        chunk_dicts = chunks_to_dicts(chunks)

        for c in chunk_dicts:
            cleaned = (c.get("text") or "").strip()
            if not cleaned:
                continue
            cid = f"{doc_id}:{c['index']}"
            chunk_ids.append(cid)
            chunk_texts.append(cleaned)
            cm = dict(meta)
            cm.update(c.get("metadata", {}))
            chunk_metas.append(cm)

    if not chunk_texts:
        return

    # 3) BGE-M3 임베딩
    embedder = BgeM3Embedder()
    embeddings = embedder.embed_texts(chunk_texts)

    # 4) ChromaDB upsert (배치 제한)
    store = ChromaStore(collection_name=collection_name, persist_directory=persist_directory)
    batch_size = int(getattr(settings, "CHROMA_UPSERT_BATCH_SIZE", 5000))
    if batch_size <= 0:
        batch_size = 5000
    for start in range(0, len(chunk_ids), batch_size):
        end = min(start + batch_size, len(chunk_ids))
        store.upsert_chunks(
            ids=chunk_ids[start:end],
            texts=chunk_texts[start:end],
            embeddings=embeddings[start:end],
            metadatas=chunk_metas[start:end],
        )


def main() -> None:
    ingest_sqlite_to_chromadb()


if __name__ == "__main__":
    main()

