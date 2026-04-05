from __future__ import annotations

from typing import Any, Dict, List, Protocol


class VectorStoreClient(Protocol):
    """
    시맨틱 검색을 위한 최소한의 벡터 스토어 프로토콜.
    실제 구현(Chroma, PGVector 등)은 이 프로토콜을 만족하면 된다.
    """

    def query(self, embedding: List[float], top_k: int) -> List[Dict[str, Any]]:
        """
        embedding 에 대해 top_k 개의 유사 문서를 반환.
        각 문서는 최소한 {"id", "text", "score", "meta"} 키를 포함해야 한다.
        """
        ...


class SemanticIndex:
    """
    벡터 스토어 클라이언트를 감싸는 시맨틱 검색 인덱스.
    """

    def __init__(self, client: VectorStoreClient):
        self._client = client

    def search(self, query_embedding: List[float], top_k: int = 10) -> List[Dict[str, Any]]:
        if not query_embedding:
            return []
        return self._client.query(query_embedding, top_k)

