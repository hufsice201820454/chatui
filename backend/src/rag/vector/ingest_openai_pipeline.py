from __future__ import annotations

from typing import Any, Dict, List

from config import settings
from langchain_openai import OpenAIEmbeddings

from src.rag.rag_pipeline import VDB_PATH as RAG_VDB_PATH
from src.utils.chunker import chunk_text, chunks_to_dicts

from .chroma_store import ChromaStore
from .sqlite_loader import load_sqlite_documents


def _build_openai_embeddings() -> OpenAIEmbeddings:
    api_key = (
        getattr(settings, "OPENAI_API_KEY", None)
        or getattr(settings, "OPEN_API_KEY", None)
        or getattr(settings, "API_KEY", None)
    )
    if not api_key:
        raise ValueError("OPENAI_API_KEY/OPEN_API_KEY/API_KEY 가 필요합니다 (.env/settings 확인).")

    base_url = (
        getattr(settings, "OPENAI_EMBEDDING_BASE_URL", None)
        or getattr(settings, "EMBEDDING_BASE_URL", None)
        or getattr(settings, "OPENAI_BASE_URL", None)
        or getattr(settings, "OPEN_BASE_URL", None)
        or getattr(settings, "BASE_URL", None)
    )
    model = (
        getattr(settings, "OPENAI_EMBEDDING_MODEL", None)
        or getattr(settings, "EMBEDDING_MODEL_NAME", None)
        or "bge-m3"
    )

    return OpenAIEmbeddings(
        api_key=api_key,
        model=model,
        base_url=base_url,
        # 내부망에서 blob/tiktoken 다운로드 경로 차단
        tiktoken_enabled=False,
        # 내부망에서 HF tokenizer 다운로드 경로 차단
        check_embedding_ctx_length=False,
    )


def ingest_sqlite_to_chromadb_openai(
    *,
    limit: int | None = None,
    chunk_size: int = 1000,
    overlap: int = 200,
    collection_name: str | None = None,
    persist_directory: str | None = None,
) -> None:
    """
    SQLite 테이블(settings.SQLITE_ITSM_TABLE) -> chunk -> OpenAIEmbeddings -> ChromaDB 저장.

    rag_pipeline.py 기본값과 맞추기 위해:
    - collection_name: settings.RAG_COLLECTION_NAME or "itsm_openai_bge_m3_1024"
    - persist_directory: backend/chroma
    """
    docs = load_sqlite_documents(limit=limit)
    if not docs:
        return

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
            cleaned_text = (c.get("text") or "").strip()
            if not cleaned_text:
                continue
            cid = f"{doc_id}:{c['index']}"
            chunk_ids.append(cid)
            chunk_texts.append(cleaned_text)
            cm = dict(meta)
            cm.update(c.get("metadata", {}))
            chunk_metas.append(cm)

    if not chunk_texts:
        return

    embeddings = _build_openai_embeddings()
    vectors = embeddings.embed_documents(chunk_texts)

    if collection_name is None:
        collection_name = getattr(settings, "RAG_COLLECTION_NAME", None) or "itsm_openai_bge_m3_1024"
    if persist_directory is None:
        # rag_pipeline.VDB_PATH 와 동일 (backend/chroma)
        persist_directory = RAG_VDB_PATH

    store = ChromaStore(collection_name=collection_name, persist_directory=persist_directory)
    # Chroma upsert는 배치 크기 제한이 있으므로 쪼개서 넣는다.
    batch_size = int(getattr(settings, "CHROMA_UPSERT_BATCH_SIZE", 5000))
    if batch_size <= 0:
        batch_size = 5000

    for start in range(0, len(chunk_ids), batch_size):
        end = min(start + batch_size, len(chunk_ids))
        store.upsert_chunks(
            ids=chunk_ids[start:end],
            texts=chunk_texts[start:end],
            embeddings=vectors[start:end],
            metadatas=chunk_metas[start:end],
        )


def main() -> None:
    ingest_sqlite_to_chromadb_openai()


if __name__ == "__main__":
    main()

