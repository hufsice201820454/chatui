"""엔드투엔드: QueryAnalyzer → CypherGenerator/GraphRetriever → ContextAssembler → (선택) 도구 LLM."""
from __future__ import annotations

from typing import Any, Literal, Optional

from src.java_ast_graphrag.graphrag.context_assembler import assemble_context
from src.java_ast_graphrag.graphrag.query_analyzer import analyze_query
from src.java_ast_graphrag.models import (
    ChangeType,
    ExplainType,
    GraphContextInput,
    QueryAnalysis,
    RefactorFocus,
)
from src.java_ast_graphrag.neo4j.repository import GraphContextRepository
from src.java_ast_graphrag.workflow.tools import (
    code_explain,
    graph_search,
    impact_assess,
    refactor_suggest,
    test_generate,
)

ToolName = Literal[
    "none",
    "code_explain",
    "impact_assess",
    "refactor_suggest",
    "test_generate",
    "graph_search",
]


async def run_java_graphrag(
    user_query: str,
    *,
    tool: ToolName = "none",
    explain_type: ExplainType = "summary",
    change_type: ChangeType = "modify",
    focus: RefactorFocus = "complexity",
    target_signature: str = "",
    dependency_list: str = "",
    rule_confidence_threshold: float = 0.8,
) -> dict[str, Any]:
    analysis = await analyze_query(user_query, rule_confidence_threshold=rule_confidence_threshold)
    repo = GraphContextRepository()
    ctx_input = await repo.fetch(analysis)
    assembled = assemble_context(ctx_input)

    out: dict[str, Any] = {
        "analysis": analysis.model_dump(),
        "assembled_context": assembled,
        "tool": tool,
    }

    if tool == "none":
        return out

    if tool == "code_explain":
        out["result"] = await code_explain.run(assembled, explain_type)
    elif tool == "impact_assess":
        out["result"] = await impact_assess.run(assembled, change_type)
    elif tool == "refactor_suggest":
        out["result"] = await refactor_suggest.run(assembled, focus)
    elif tool == "test_generate":
        sig = target_signature or (
            f"{analysis.target_class or 'Unknown'}.{analysis.target_method or 'method'}(...)"
        )
        deps = dependency_list or "(컨텍스트 내 의존성 참고)"
        out["result"] = await test_generate.run(
            assembled,
            target_signature=sig,
            dependency_list=deps,
        )
    elif tool == "graph_search":
        raw = await repo.fetch_raw_paths(analysis)
        out["raw_graph"] = raw
        out["result"] = await graph_search.run(raw)
    else:
        out["error"] = f"unknown tool: {tool}"

    return out


async def analyze_only(user_query: str) -> QueryAnalysis:
    return await analyze_query(user_query)


async def assemble_only(ctx: GraphContextInput) -> str:
    return assemble_context(ctx)
