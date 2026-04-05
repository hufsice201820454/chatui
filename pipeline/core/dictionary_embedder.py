"""
사전(DIC_MAS / DIC_DET) 임베딩 처리기
"""
import logging
from typing import List

from pipeline.core.schema import DictionaryEntry
from pipeline.dbutil import get_db, fetch_all_dic_mas, fetch_dic_det_by_dic_id
from util.chroma_store import ChromaStore
from config import CHROMA_COLLECTION_DICTIONARY, EMBEDDING_BATCH_SIZE

logger = logging.getLogger("pipeline.core.dictionary_embedder")


class DictionaryEmbedder:
    """DIC_MAS + DIC_DET 데이터를 ChromaDB에 임베딩."""

    def __init__(self):
        self._store = ChromaStore(CHROMA_COLLECTION_DICTIONARY)

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def run_full(self) -> dict:
        """전체 사전 재임베딩 (full-refresh)."""
        entries = self._load_entries()
        logger.info("DictionaryEmbedder: loaded %d entries", len(entries))

        # 기존 컬렉션 초기화
        self._store.delete_by_metadata({"source_type": "dictionary"})

        total = len(entries)
        success = 0
        fail = 0
        for batch_start in range(0, total, EMBEDDING_BATCH_SIZE):
            batch = entries[batch_start: batch_start + EMBEDDING_BATCH_SIZE]
            try:
                self._upsert_batch(batch)
                success += len(batch)
            except Exception as e:
                logger.error("Batch upsert failed (start=%d): %s", batch_start, e)
                fail += len(batch)

        result = {"total": total, "success": success, "fail": fail}
        logger.info("DictionaryEmbedder.run_full complete: %s", result)
        return result

    def upsert_entry(self, entry: DictionaryEntry):
        """단일 항목 upsert."""
        self._upsert_batch([entry])

    def delete_entry(self, det_id: str):
        """단일 항목 삭제."""
        self._store.delete([det_id])

    def count(self) -> int:
        return self._store.count()

    # ------------------------------------------------------------------
    # 내부 메서드
    # ------------------------------------------------------------------

    def _load_entries(self) -> List[DictionaryEntry]:
        entries: List[DictionaryEntry] = []
        with get_db() as db:
            mas_rows = fetch_all_dic_mas(db)
            for mas in mas_rows:
                det_rows = fetch_dic_det_by_dic_id(db, mas["dic_id"])
                for det in det_rows:
                    entries.append(
                        DictionaryEntry(
                            dic_id=mas["dic_id"],
                            dic_nm=mas["dic_nm"],
                            category=mas.get("category"),
                            det_id=det["det_id"],
                            term=det["term"],
                            definition=det.get("definition"),
                            synonyms=det.get("synonyms"),
                            source=det.get("source"),
                        )
                    )
        return entries

    def _upsert_batch(self, entries: List[DictionaryEntry]):
        ids = [e.det_id for e in entries]
        texts = [e.to_document_text() for e in entries]
        metadatas = [e.to_metadata() for e in entries]
        self._store.upsert(ids=ids, texts=texts, metadatas=metadatas)
