"""LangGraph Agent 그래프 정의."""
from __future__ import annotations

from typing import Any, Literal, Optional

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from src.workflow.v1_0.state import AgentState
from src.workflow.v1_0.nodes import (
    intent_classifier,
    hitl_gate,
    rag_decision,
    rag_retrieve,
    error_analysis,
    llm_final,
    vdb_store,
)

# reject 최대 허용 횟수 (초과 시 현재 초안으로 강제 승인 처리)
MAX_REJECT_COUNT = 3


def _route_after_intent(
    state: AgentState,
) -> Literal["rag_decision", "llm_final"]:
    """intent 분류 결과에 따라 분기.

    - agent  → rag_decision (RAG 사용 여부 판단)
    - general → llm_final  (RAG/에러 분석 없이 일반 LLM 응대)
    """
    intent = state.get("intent") or "general"
    return "rag_decision" if intent == "agent" else "llm_final"


def _route_after_rag_decision(
    state: AgentState,
) -> Literal["rag_retrieve", "error_analysis"]:
    return "rag_retrieve" if state.get("use_rag") else "error_analysis"


def _route_after_hitl(
    state: AgentState,
) -> Literal["vdb_store", "llm_final"]:
    """HITL 결과 라우팅.

    - approve / edit → vdb_store (ChromaDB 적재 후 END)
    - reject         → llm_final (재생성), 단 MAX_REJECT_COUNT 초과 시 vdb_store로 강제 전환
    """
    action = state.get("hitl_action") or "approve"
    reject_count = state.get("reject_count") or 0

    if action == "reject" and reject_count < MAX_REJECT_COUNT:
        return "llm_final"

    # approve / edit 또는 reject 횟수 초과 → 적재
    return "vdb_store"


def build_agent_graph() -> Any:
    builder = StateGraph(AgentState)

    builder.add_node("intent_classifier", intent_classifier)
    builder.add_node("rag_decision", rag_decision)
    builder.add_node("rag_retrieve", rag_retrieve)
    builder.add_node("error_analysis", error_analysis)
    builder.add_node("llm_final", llm_final)
    builder.add_node("hitl_gate", hitl_gate)
    builder.add_node("vdb_store", vdb_store)

    builder.add_edge(START, "intent_classifier")

    # intent 결과로 분기: agent → rag_decision, general → llm_final
    builder.add_conditional_edges(
        "intent_classifier",
        _route_after_intent,
        {
            "rag_decision": "rag_decision",
            "llm_final": "llm_final",
        },
    )

    builder.add_conditional_edges(
        "rag_decision",
        _route_after_rag_decision,
        {
            "rag_retrieve": "rag_retrieve",
            "error_analysis": "error_analysis",
        },
    )

    builder.add_edge("rag_retrieve", "llm_final")
    builder.add_edge("error_analysis", "llm_final")
    builder.add_edge("llm_final", "hitl_gate")

    builder.add_conditional_edges(
        "hitl_gate",
        _route_after_hitl,
        {
            "vdb_store": "vdb_store",
            "llm_final": "llm_final",           # reject → 재생성
        },
    )

    builder.add_edge("vdb_store", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


_graph: Optional[Any] = None


def get_agent_graph() -> Any:
    global _graph
    if _graph is None:
        _graph = build_agent_graph()
    return _graph
