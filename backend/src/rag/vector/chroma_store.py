from __future__ import annotations

from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from config import BACKEND_ROOT

_DEFAULT_CHROMA_PERSIST = str(BACKEND_ROOT / "chroma")


class ChromaStore:
    """
    ChromaDB 래퍼.

    - 컬렉션명: 기본값 "itsm_bge_m3_chunks"
    - document: 청크 텍스트
    - embedding: BGE-M3 임베딩 벡터
    - metadata: 원본 row/chunk 메타데이터
    """

    def __init__(
        self,
        collection_name: str = "itsm_bge_m3_chunks",
        persist_directory: str = _DEFAULT_CHROMA_PERSIST,
    ):
        self._client = chromadb.Client(
            ChromaSettings(
                is_persistent=True,
                persist_directory=persist_directory,
            )
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name
        )

    def upsert_chunks(
        self,
        ids: List[str],
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        청크들을 컬렉션에 upsert.
        """
        if metadatas is None:
            metadatas = [{} for _ in ids]
        self._collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def similarity_search(
        self,
        embedding: List[float],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        임베딩 기준 top_k 문서를 검색.
        반환: [{"id", "text", "score", "meta"}, ...]
        """
        if not embedding:
            return []

        res = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
        )
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        distances = res.get("distances")
        if distances:
            dists = distances[0]
        else:
            # 거리 정보가 없으면 스코어를 0으로 채운다
            dists = [0.0 for _ in docs]
        metas = (res.get("metadatas") or [[]])[0]

        out: List[Dict[str, Any]] = []
        for _id, doc, dist, meta in zip(ids, docs, dists, metas):
            out.append(
                {
                    "id": _id,
                    "text": doc,
                    # Chroma 는 기본적으로 거리(distance)를 주므로, 간단히 음수로 변환해 score 로 사용
                    "score": -float(dist) if dist is not None else 0.0,
                    "meta": meta or {},
                }
            )
        return out

    # VectorStoreClient 프로토콜과 호환되도록 query 메서드 제공
    def query(self, embedding: List[float], top_k: int) -> List[Dict[str, Any]]:
        return self.similarity_search(embedding, top_k=top_k)

