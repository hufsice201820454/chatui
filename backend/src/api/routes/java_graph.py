"""
Java GraphRAG (Neo4j) — 분석·파이프라인 API.

POST /api/v1/java-graph/analyze  — QueryAnalyzer만
POST /api/v1/java-graph/run      — Neo4j 조회 + 컨텍스트 조립 + (선택) 도구 LLM
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.core.responses import ok
from src.java_ast_graphrag.graphrag.context_assembler import assemble_context
from src.java_ast_graphrag.models import GraphContextInput
from src.java_ast_graphrag.pipeline import analyze_only, run_java_graphrag

router = APIRouter(prefix="/java-graph", tags=["Java GraphRAG"])


class AnalyzeBody(BaseModel):
    user_query: str


class RunBody(BaseModel):
    user_query: str
    tool: Literal[
        "none",
        "code_explain",
        "impact_assess",
        "refactor_suggest",
        "test_generate",
        "graph_search",
    ] = "none"
    explain_type: Literal["summary", "detail", "security"] = "summary"
    change_type: Literal["modify", "delete", "rename"] = "modify"
    focus: Literal["complexity", "duplication", "coupling"] = "complexity"
    target_signature: str = ""
    dependency_list: str = ""
    rule_confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)


class AssembleBody(BaseModel):
    """Neo4j 없이 컨텍스트 조립만 검증할 때."""
    context: GraphContextInput
    max_tokens: Optional[int] = None


@router.post("/analyze")
async def java_graph_analyze(body: AnalyzeBody):
    analysis = await analyze_only(body.user_query)
    return ok({"analysis": analysis.model_dump()})


@router.post("/run")
async def java_graph_run(body: RunBody):
    result = await run_java_graphrag(
        body.user_query,
        tool=body.tool,
        explain_type=body.explain_type,
        change_type=body.change_type,
        focus=body.focus,
        target_signature=body.target_signature,
        dependency_list=body.dependency_list,
        rule_confidence_threshold=body.rule_confidence_threshold,
    )
    return ok(result)


@router.post("/assemble")
async def java_graph_assemble(body: AssembleBody):
    text = assemble_context(body.context, max_tokens=body.max_tokens)
    return ok({"assembled_context": text})
