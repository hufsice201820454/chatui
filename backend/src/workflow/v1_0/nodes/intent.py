"""인텐트 분류 노드 (Rule-Based 키워드 매칭)."""
from __future__ import annotations

import logging

from src.workflow.v1_0.state import AgentState
from src.workflow.v1_0.itsm_query_signals import HIGH_CONFIDENCE_KEYWORDS, ITSM_KEYWORDS

logger = logging.getLogger(__name__)


def intent_classifier(state: AgentState) -> AgentState:
    """사용자 문의가 ITSM Agent 대상인지 Rule-Based 키워드 매칭으로 판단.

    Input:  user_query
    Output: intent, intent_confidence
    """
    query = (state.get("user_query") or "").lower()

    # 고신뢰 키워드 우선 확인
    high_hits = [kw for kw in HIGH_CONFIDENCE_KEYWORDS if kw.lower() in query]
    if high_hits:
        logger.debug("intent_classifier: high_confidence 키워드 매칭 %s", high_hits)
        return {
            **state,
            "intent": "agent",
            "intent_confidence": 1.0,
        }

    # 일반 키워드 매칭
    hits = [kw for kw in ITSM_KEYWORDS if kw.lower() in query]
    match_count = len(hits)

    if match_count == 0:
        confidence = 0.0
        intent = "general"
    elif match_count == 1:
        confidence = 0.5
        intent = "agent"
    elif match_count == 2:
        confidence = 0.75
        intent = "agent"
    else:
        confidence = min(1.0, 0.75 + (match_count - 2) * 0.05)
        intent = "agent"

    logger.debug(
        "intent_classifier: query=%r hits=%s intent=%s confidence=%.2f",
        query[:80],
        hits[:5],
        intent,
        confidence,
    )

    return {
        **state,
        "intent": intent,
        "intent_confidence": confidence,
    }
