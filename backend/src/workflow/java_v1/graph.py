"""Java GraphRAG — LangGraph 래퍼 (파이프라인은 src.java_ast_graphrag.pipeline)."""
from __future__ import annotations

from typing import Any, cast

from langgraph.graph import END, START, StateGraph

from src.java_ast_graphrag.pipeline import ToolName, run_java_graphrag
from src.workflow.java_v1.state import JavaGraphRAGState


async def _run_node(state: JavaGraphRAGState) -> dict[str, Any]:
    raw_tool = state.get("tool") or "none"
    tool = cast(ToolName, raw_tool if raw_tool in (
        "none", "code_explain", "impact_assess", "refactor_suggest", "test_generate", "graph_search"
    ) else "none")
    out = await run_java_graphrag(
        state["user_query"],
        tool=tool,
        explain_type=state.get("explain_type") or "summary",
        change_type=state.get("change_type") or "modify",
        focus=state.get("focus") or "complexity",
        target_signature=state.get("target_signature") or "",
        dependency_list=state.get("dependency_list") or "",
        rule_confidence_threshold=float(state.get("rule_confidence_threshold") or 0.8),
    )
    return {
        "analysis": out.get("analysis"),
        "assembled_context": out.get("assembled_context"),
        "raw_graph": out.get("raw_graph"),
        "result": out.get("result"),
        "error": out.get("error"),
    }


def build_java_graphrag_graph():
    g = StateGraph(JavaGraphRAGState)
    g.add_node("pipeline", _run_node)
    g.add_edge(START, "pipeline")
    g.add_edge("pipeline", END)
    return g.compile()


_graph = None


def get_java_graphrag_graph():
    global _graph
    if _graph is None:
        _graph = build_java_graphrag_graph()
    return _graph
