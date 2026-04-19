"""인텐트 분류 노드 (Rule + LLM Hybrid)."""
from __future__ import annotations

import logging

from src.workflow.v1_0.state import AgentState
from src.workflow.v1_0.services.intent_classifier_service import classify_intent_hybrid

logger = logging.getLogger(__name__)


async def intent_classifier(state: AgentState) -> AgentState:
    """사용자 질의를 code_change/code_review/support로 분류."""
    query = (state.get("user_query") or "").strip()
    result = await classify_intent_hybrid(query)
    intent = result.get("intent", "support")
    confidence = float(result.get("confidence", 0.5))
    reason = str(result.get("reason", "분류 이유 없음"))
    source = str(result.get("source", "fallback_rule"))
    signals = result.get("signals", []) if isinstance(result.get("signals"), list) else []

    logger.info(
        "intent_classifier: intent=%s confidence=%.2f source=%s reason=%s",
        intent,
        confidence,
        source,
        reason,
    )

    return {
        **state,
        "intent": intent,  # type: ignore[typeddict-item]
        "intent_confidence": confidence,
        "intent_reason": reason,
        "intent_source": source,  # type: ignore[typeddict-item]
        "intent_signals": [str(s) for s in signals[:8]],
    }
