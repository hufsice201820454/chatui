from __future__ import annotations

"""
SQLite -> OpenAI 호환 임베딩 -> Chroma.
"""
from typing import Any, Dict, List

from config import settings
from src.rag.embeddings import Embedder
from src.rag.rag_pipeline import VDB_PATH as RAG_VDB_PATH
from src.utils.chunker import chunk_text, chunks_to_dicts

from .chroma_store import ChromaStore
from .sqlite_loader import load_sqlite_documents


def ingest_sqlite_to_chromadb(
    limit: int | None = None,
    chunk_size: int = 1000,
    overlap: int = 200,
    collection_name: str | None = None,
    persist_directory: str | None = None,
) -> None:
    """
    SQLite ITSM 데이터 -> full_text -> chunk -> OpenAI 호환 임베딩 -> ChromaDB 저장.
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

    # 3) OpenAI 호환 임베딩
    embedding_model = getattr(settings, "OPENAI_EMBEDDING_MODEL", None) or "bge-m3"
    embedder = Embedder(model_name=embedding_model)
    embeddings = embedder.embed_texts(chunk_texts)

    # 4) ChromaDB upsert (배치 제한)
    if collection_name is None:
        collection_name = getattr(settings, "RAG_COLLECTION_NAME", None) or "itsm_openai_bge_m3_1024"
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

