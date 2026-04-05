"""QueryAnalysis → 실행할 Cypher 단계 목록 (문서: CypherGenerator)."""
from __future__ import annotations

from dataclasses import dataclass

from src.java_ast_graphrag.models import QueryAnalysis
from src.java_ast_graphrag.neo4j import queries as q


@dataclass(frozen=True)
class CypherStep:
    """단일 읽기 쿼리 단계."""

    name: str
    cypher: str


def build_context_retrieval_plan(
    analysis: QueryAnalysis,
    *,
    class_label: str,
    method_label: str,
) -> list[CypherStep]:
    """컨텍스트 조립용 Neo4j 읽기 순서."""
    depth = analysis.depth
    return [
        CypherStep("resolve_target", q.resolve_target_method(class_label, method_label)),
        CypherStep("callees_d1", q.callees_depth1(class_label, method_label)),
        CypherStep(
            "callees_d2",
            q.callees_depth2_signatures(class_label, method_label, depth),
        ),
        CypherStep("deps", q.dependency_neighbors(class_label)),
    ]


def build_raw_paths_step(
    analysis: QueryAnalysis,
    *,
    class_label: str,
    method_label: str,
) -> CypherStep:
    """graph_search 도구용 단일 쿼리."""
    return CypherStep(
        "raw_paths",
        q.raw_paths_for_summary(class_label, method_label, analysis.depth),
    )
