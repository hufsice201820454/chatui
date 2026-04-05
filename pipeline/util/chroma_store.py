"""
ChromaDB 클라이언트 래퍼
"""
import logging
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.config import Settings

from config import CHROMA_HOST, CHROMA_PORT
from util.embedding import Embedding

logger = logging.getLogger("pipeline.util.chroma_store")


class ChromaStore:
    """ChromaDB 컬렉션에 대한 upsert/delete/query 래퍼."""

    def __init__(self, collection_name: str):
        self._client = chromadb.HttpClient(
            host=CHROMA_HOST,
            port=CHROMA_PORT,
            settings=Settings(anonymized_telemetry=False),
        )
        self._embedding_fn = Embedding()
        self._collection_name = collection_name
        self._collection = self._get_or_create_collection(collection_name)

    def _get_or_create_collection(self, name: str):
        try:
            col = self._client.get_collection(name)
            logger.info("ChromaStore: reuse collection '%s'", name)
        except Exception:
            col = self._client.create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("ChromaStore: created collection '%s'", name)
        return col

    def set_collection(self, collection_name: str):
        self._collection_name = collection_name
        self._collection = self._get_or_create_collection(collection_name)

    def upsert(
        self,
        ids: List[str],
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ):
        if not ids:
            return
        embeddings = self._embedding_fn.embed_documents(texts)
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas or [{} for _ in ids],
        )
        logger.debug("Upserted %d vectors into '%s'", len(ids), self._collection_name)

    def delete(self, ids: List[str]):
        if not ids:
            return
        self._collection.delete(ids=ids)
        logger.debug("Deleted %d vectors from '%s'", len(ids), self._collection_name)

    def delete_by_metadata(self, where: Dict[str, Any]):
        """메타데이터 필터로 벡터 일괄 삭제."""
        results = self._collection.get(where=where, include=["documents"])
        ids = results.get("ids", [])
        if ids:
            self._collection.delete(ids=ids)
            logger.debug(
                "Deleted %d vectors (filter=%s) from '%s'",
                len(ids), where, self._collection_name,
            )

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        embedding = self._embedding_fn.embed_query(query_text)
        kwargs: Dict[str, Any] = {
            "query_embeddings": [embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        result = self._collection.query(**kwargs)
        hits = []
        for i, doc_id in enumerate(result["ids"][0]):
            hits.append({
                "id": doc_id,
                "text": result["documents"][0][i],
                "metadata": result["metadatas"][0][i],
                "distance": result["distances"][0][i],
            })
        return hits

    def count(self) -> int:
        return self._collection.count()

    def get_ids_by_metadata(self, where: Dict[str, Any]) -> List[str]:
        results = self._collection.get(where=where, include=[])
        return results.get("ids", [])
