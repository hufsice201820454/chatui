"""엔드투엔드 파이프라인.

변경 내역 (기존 pipeline.py 대비):
  - asyncio.gather 로 fetch_graph_context + fetch_dependency_context 병렬 실행
  - format_dependency_block 결과를 assembled 뒤에 append → full_context 생성
  - 도구 LLM 에 full_context 전달
  - out dict 에 dependency_context / full_context 키 추가
  - test_generate: dependency_list 미지정 시 dep_ctx.call_deps 자동 주입
  - include_dependency_context=False 로 기존 동작 유지 가능

배치 위치: backend/src/java_ast_graphrag/pipeline.py
"""
from __future__ import annotations

import asyncio
from typing import Any, Literal

from src.java_ast_graphrag.graphrag.context_assembler import assemble_context
from src.java_ast_graphrag.graphrag.dependency_context_builder import (
    DependencyContext,
    fetch_dependency_context,
    format_dependency_block,
)
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


# ──────────────────────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────────────────────

def _merge_contexts(assembled: str, dep_block: str) -> str:
    """assembled context 뒤에 의존관계 블록 추가."""
    if not dep_block:
        return assembled
    return f"{assembled}\n\n{dep_block}"


# ──────────────────────────────────────────────────────────────
# 메인 파이프라인
# ──────────────────────────────────────────────────────────────

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
    include_dependency_context: bool = True,
    text2cypher_enabled: bool | None = None,
) -> dict[str, Any]:
    """Java GraphRAG 엔드투엔드 실행.

    Args:
        user_query: 자연어 질의
        tool: 실행할 도구 (none / code_explain / impact_assess /
              refactor_suggest / test_generate / graph_search)
        explain_type: code_explain 세부 유형
        change_type: impact_assess 변경 유형
        focus: refactor_suggest 집중 영역
        target_signature: test_generate 대상 시그니처 (미지정 시 자동)
        dependency_list: test_generate 의존 목록 (미지정 시 dep_ctx 자동)
        rule_confidence_threshold: QueryAnalyzer 규칙 신뢰도 임계값
        include_dependency_context: False 시 의존관계 조회 생략
        text2cypher_enabled: None 이면 환경변수 TEXT2CYPHER_ENABLED 따름
    """
    # 1. 의도 분석
    analysis = await analyze_query(
        user_query,
        rule_confidence_threshold=rule_confidence_threshold,
    )

    repo = GraphContextRepository(text2cypher_enabled=text2cypher_enabled)

    # 2. 메서드 컨텍스트 + 의존관계 병렬 조회
    if include_dependency_context:
        ctx_input, dep_ctx = await asyncio.gather(
            repo.fetch(analysis, user_query=user_query),
            fetch_dependency_context(
                analysis,
                class_label=repo._class_lbl,
                method_label=repo._method_lbl,
            ),
        )
    else:
        ctx_input = await repo.fetch(analysis, user_query=user_query)
        dep_ctx   = DependencyContext()

    # 3. 컨텍스트 조립
    assembled    = assemble_context(ctx_input)
    dep_block    = format_dependency_block(dep_ctx)
    full_context = _merge_contexts(assembled, dep_block)

    out: dict[str, Any] = {
        "analysis":           analysis.model_dump(),
        "assembled_context":  assembled,     # 메서드 컨텍스트만
        "dependency_context": dep_block,     # 의존관계 블록
        "full_context":       full_context,  # 도구 LLM 전달용 (두 개 합산)
        "tool":               tool,
    }

    if tool == "none":
        return out

    # 4. 도구 실행 (full_context 사용)
    if tool == "code_explain":
        out["result"] = await code_explain.run(full_context, explain_type)

    elif tool == "impact_assess":
        out["result"] = await impact_assess.run(full_context, change_type)

    elif tool == "refactor_suggest":
        out["result"] = await refactor_suggest.run(full_context, focus)

    elif tool == "test_generate":
        sig = target_signature or (
            f"{analysis.target_class or 'Unknown'}"
            f".{analysis.target_method or 'method'}(...)"
        )
        # dependency_list 미지정 시 dep_ctx.call_deps 자동 주입
        deps = dependency_list or (
            "\n".join(dep_ctx.call_deps[:10])
            if dep_ctx.call_deps
            else "(컨텍스트 내 의존성 참고)"
        )
        out["result"] = await test_generate.run(
            full_context,
            target_signature=sig,
            dependency_list=deps,
        )

    elif tool == "graph_search":
        raw = await repo.fetch_raw_paths(analysis)
        out["raw_graph"] = raw
        out["result"]    = await graph_search.run(raw)

    else:
        out["error"] = f"unknown tool: {tool}"

    return out


# ──────────────────────────────────────────────────────────────
# 단계별 유틸
# ──────────────────────────────────────────────────────────────

async def analyze_only(user_query: str) -> QueryAnalysis:
    return await analyze_query(user_query)


async def assemble_only(ctx: GraphContextInput) -> str:
    return assemble_context(ctx)