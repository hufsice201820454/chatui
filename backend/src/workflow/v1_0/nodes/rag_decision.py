"""RAG 사용 여부 판단 노드 (top-k=5, rag_retrieve 중복 호출 제거).

변경 사항:
- top-k를 3 → 5로 통합해 rag_retrieve의 중복 API 호출 제거.
  rag_retrieve는 이 노드가 이미 채운 rag_contexts를 재사용만 한다.
- 유사 케이스 존재 여부(use_rag)와 결과(rag_contexts)를 한 번에 설정.
"""
from __future__ import annotations

import logging

from src.workflow.v1_0.state import AgentState
from src.rag.rag_pipeline import get_rag_contexts

logger = logging.getLogger(__name__)

_TOP_K = 5
_SIMILARITY_THRESHOLD = 0.5  # 유사 케이스 존재 판단 기준 (get_rag_contexts 내부에서 필터링)


def rag_decision(state: AgentState) -> AgentState:
    """RAG 사용 여부 판단 + 컨텍스트 prefetch.

    top-k=5로 한 번만 조회하여 use_rag 여부와 rag_contexts를 동시에 설정.
    rag_retrieve는 이 결과를 그대로 사용하므로 임베딩 API 중복 호출이 발생하지 않는다.

    Input:  user_query
    Output: use_rag, rag_reason, rag_contexts
    """
    query = state.get("user_query") or ""

    try:
        contexts = get_rag_contexts(query, top_k=_TOP_K)
    except Exception as e:
        logger.warning(
            "rag_decision: RAG 조회 실패 — RAG 미사용 경로로 진행. 오류: %s", e
        )
        contexts = []

    use_rag = len(contexts) > 0

    if use_rag:
        rag_reason = (
            f"유사 케이스 {len(contexts)}건 발견 (top-k={_TOP_K}) — RAG 경로 선택"
        )
    else:
        rag_reason = (
            f"유사 케이스 없음 (top-k={_TOP_K}, threshold={_SIMILARITY_THRESHOLD})"
            " — LLM 자체 분석 경로 선택"
        )

    logger.info("rag_decision: use_rag=%s reason=%s", use_rag, rag_reason)

    return {
        **state,
        "use_rag": use_rag,
        "rag_reason": rag_reason,
        "rag_contexts": contexts,
    }
