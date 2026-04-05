from __future__ import annotations

from typing import Dict, List, Sequence

from .bm25_index import Bm25Index
from .config import config
from .embeddings import Embedder
from .hybrid_retriever import HybridRetriever
from .reranker import Reranker
from .semantic_index import SemanticIndex, VectorStoreClient


class RagPipeline:
    """
    query → hybrid retrieval → rerank → 최종 top-k 컨텍스트 반환 파이프라인.
    """

    def __init__(
        self,
        documents: Sequence[Dict],
        vector_store_client: VectorStoreClient,
        embedder: Embedder | None = None,
        reranker: Reranker | None = None,
    ):
        """
        documents: [{"id", "text", "meta"}, ...] 형태의 문서/청크 리스트
        vector_store_client: SemanticIndex 에서 사용할 벡터 스토어 클라이언트
        """
        self._embedder = embedder or Embedder()
        self._bm25 = Bm25Index(documents)
        self._semantic = SemanticIndex(vector_store_client)
        self._hybrid = HybridRetriever(self._bm25, self._semantic, self._embedder)
        self._reranker = reranker or Reranker()

    def get_contexts(self, query: str, top_k: int | None = None) -> List[Dict]:
        """
        최종 RAG 컨텍스트 리스트를 반환.
        각 항목은 최소한 {"id", "text", "score", "meta"} 를 포함한다.
        """
        top_k = top_k or config.top_k_final

        candidates = self._hybrid.retrieve(query, top_k=top_k)
        reranked = self._reranker.rerank(query, candidates)
        return reranked[:top_k]

