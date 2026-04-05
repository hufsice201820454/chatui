"""Agent 그래프 상태 스키마."""
from __future__ import annotations

from typing import Annotated, List, Literal, Optional, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """LangGraph Agent 상태."""

    # 입력
    user_query: str
    parsed_docs: Optional[str]          # MCP 문서 파싱 결과 등 추가 컨텍스트

    # Intent (1차)
    intent: Literal["agent", "general"]
    intent_confidence: float

    # RAG 판단 (2차)
    use_rag: bool
    rag_reason: str
    rag_contexts: List[dict]

    # Error 분석 (3차, RAG 미스 경로)
    error_analysis: Optional[dict]      # {error_type, root_cause, suggested_action}

    # LLM 최종 초안 (4차)
    messages: Annotated[list, add_messages]   # LLM 대화 누적 (add_messages reducer)
    draft_response: str

    # HITL (5차)
    # ※ 최초 llm_final 진입 시 None이므로 Optional로 선언
    hitl_action: Optional[Literal["approve", "reject", "edit"]]
    hitl_edited: Optional[str]
    # reject 누적 횟수 — 무한 루프 방지용 (최대 MAX_REJECT_COUNT회)
    reject_count: int

    # 최종
    final_response: str
    action_taken: str

    # VDB 적재용 (6차)
    repo_info: str
    code_location: str
    timestamp: str
