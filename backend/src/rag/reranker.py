from __future__ import annotations

from typing import Dict, List

from .config import config


class Reranker:
    """
    RAG 후보 컨텍스트 재정렬기.

    처음에는 hybrid 스코어를 그대로 사용하고,
    추후 cross-encoder / LLM 기반 reranker 로 교체 가능하도록 인터페이스만 정의한다.
    """

    def __init__(self, model_name: str | None = None):
        self._model_name = model_name or "hybrid-score"

    def rerank(self, query: str, docs: List[Dict]) -> List[Dict]:
        """
        현재 구현: hybrid 스코어 기준 정렬만 수행.
        """
        if not docs:
            return []

        # 상위 rerank_top_k 만 고려 (향후 실제 reranker 붙일 때 사용)
        candidates = docs[: config.rerank_top_k]
        candidates.sort(key=lambda d: d.get("score", 0.0), reverse=True)
        return candidates

