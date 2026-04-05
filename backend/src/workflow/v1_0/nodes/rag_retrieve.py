"""RAG 풀 추출 노드.

변경 사항:
- rag_decision이 top-k=5로 이미 결과를 prefetch했으므로,
  rag_contexts가 채워져 있으면 API 재호출 없이 그대로 통과.
- 컨텍스트가 비어있는 예외적 상황에서만 폴백 재조회.
"""
from __future__ import annotations

import logging

from src.workflow.v1_0.state import AgentState
from src.rag.rag_pipeline import get_rag_contexts

logger = logging.getLogger(__name__)

_TOP_K = 5


def rag_retrieve(state: AgentState) -> AgentState:
    """rag_decision에서 채운 rag_contexts를 그대로 사용.

    rag_decision이 이미 top-k=5로 조회해 rag_contexts를 설정했으므로
    정상 경로에서는 API 재호출이 발생하지 않는다.
    컨텍스트가 비어있을 경우(비정상)에만 폴백 재조회를 수행한다.

    Input:  user_query, rag_contexts (rag_decision 결과)
    Output: rag_contexts (재사용 또는 폴백 재조회)
    """
    existing = state.get("rag_contexts") or []

    if existing:
        logger.info(
            "rag_retrieve: rag_decision 결과 재사용 (%d건, API 재호출 없음)",
            len(existing),
        )
        return {**state, "rag_contexts": existing}

    # 비정상 케이스: rag_decision 결과가 없으면 폴백 재조회
    query = state.get("user_query") or ""
    logger.warning(
        "rag_retrieve: rag_contexts 없음 — 폴백 재조회 (top-k=%d)", _TOP_K
    )
    try:
        contexts = get_rag_contexts(query, top_k=_TOP_K)
        logger.info("rag_retrieve: 폴백 %d건 추출", len(contexts))
    except Exception as e:
        logger.error("rag_retrieve: 폴백 RAG 추출 실패 — %s", e)
        contexts = []

    return {**state, "rag_contexts": contexts}
