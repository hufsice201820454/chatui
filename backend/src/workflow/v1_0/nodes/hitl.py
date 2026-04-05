"""HITL(Human-In-The-Loop) 게이트 노드.

LangGraph interrupt를 사용하여 사용자 검토를 대기합니다.
approve / edit / reject 중 하나를 선택하고, reject 시 llm_final로 재생성합니다.
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.types import interrupt

from src.workflow.v1_0.state import AgentState

logger = logging.getLogger(__name__)


def hitl_gate(state: AgentState) -> AgentState:
    """사용자 검토를 interrupt로 대기.

    interrupt payload:
        draft_response: 검토 대상 응대문 초안
        instruction: 사용자 안내 메시지

    resume 시 사용자가 전달할 값 (dict):
        action:  "approve" | "edit" | "reject"
        edited:  (edit 선택 시) 수정된 응대문 텍스트

    Input:  draft_response
    Output: hitl_action, hitl_edited
    """
    draft = state.get("draft_response") or ""

    logger.info("hitl_gate: interrupt — 사용자 검토 대기 (draft len=%d)", len(draft))

    # LangGraph interrupt: 그래프 실행을 일시 중단하고 외부 입력을 기다림
    human_review: Any = interrupt({
        "draft_response": draft,
        "instruction": (
            "응대문을 검토하고 아래 중 하나를 선택하세요:\n"
            "  approve  — 그대로 승인\n"
            "  edit     — 수정 후 승인 (edited 필드에 수정 내용 입력)\n"
            "  reject   — 거부 후 재생성 요청"
        ),
    })

    # human_review: {"action": "approve"|"edit"|"reject", "edited": Optional[str]}
    if not isinstance(human_review, dict):
        logger.warning("hitl_gate: 예상치 못한 review 형식 %r — approve로 처리", human_review)
        human_review = {"action": "approve"}

    action: str = str(human_review.get("action") or "approve").lower()
    if action not in ("approve", "edit", "reject"):
        logger.warning("hitl_gate: 알 수 없는 action=%r — approve로 처리", action)
        action = "approve"

    edited: str | None = human_review.get("edited") or None

    logger.info("hitl_gate: action=%s edited=%s", action, bool(edited))

    return {
        **state,
        "hitl_action": action,  # type: ignore[typeddict-item]
        "hitl_edited": edited,
    }
