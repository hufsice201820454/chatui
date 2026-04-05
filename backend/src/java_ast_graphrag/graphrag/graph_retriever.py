"""Neo4j 실행 + 행 → GraphContextInput 매핑 (문서: GraphRetriever)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from config import settings

from src.java_ast_graphrag.graphrag.cypher_generator import (
    CypherStep,
    build_context_retrieval_plan,
    build_raw_paths_step,
)
from src.java_ast_graphrag.models import GraphContextInput, QueryAnalysis
from src.java_ast_graphrag.neo4j.client import get_neo4j_driver, run_query_with_db_fallback

logger = logging.getLogger(__name__)


def run_read_sync(cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    driver = get_neo4j_driver()
    if driver is None:
        return []

    def work(session: Any) -> list[dict[str, Any]]:
        result = session.run(cypher, **params)
        return [dict(r) for r in result]

    return run_query_with_db_fallback(driver, work)


def execute_plan_sync(
    steps: list[CypherStep],
    params: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Cypher 단계를 한 스레드에서 순차 실행(스텝마다 to_thread 하면 워커·드라이버가 바뀌어 Aura DB 선택이 깨짐)."""
    out: dict[str, list[dict[str, Any]]] = {}
    for step in steps:
        out[step.name] = run_read_sync(step.cypher, params)
    return out


async def execute_plan(
    steps: list[CypherStep],
    params: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Cypher 단계를 순서대로 실행."""
    return await asyncio.to_thread(execute_plan_sync, steps, params)


def materialize_graph_context_input(
    results: dict[str, list[dict[str, Any]]],
) -> GraphContextInput:
    """execute_plan 결과 → ContextAssembler 입력."""
    base_rows = results.get("resolve_target") or []
    base = base_rows[0] if base_rows else {}

    d1 = results.get("callees_d1") or []
    d2 = results.get("callees_d2") or []
    dep = results.get("deps") or []

    callees = (d1[0].get("callees") if d1 else []) or []
    deep = (d2[0].get("deep_sigs") if d2 else []) or []
    deps = (dep[0].get("deps") if dep else []) or []

    depth1_text = "\n".join(f"- {c}" for c in callees if c) or "(없음)"
    depth2_text = "\n".join(f"- {s}" for s in deep if s) or "(없음)"
    depends_extra = ", ".join(str(x) for x in deps if x) if deps else ""

    src = base.get("method_source") or ""
    sig = base.get("method_signature") or ""
    if sig and src:
        target_block = f"{sig}\n{src}"
    elif sig:
        target_block = sig
    else:
        target_block = src or "(메서드 소스 없음 — 클래스/메서드 매칭 확인)"

    depends_on = base.get("depends_on") or ""
    if depends_extra:
        depends_on = f"{depends_on}; {depends_extra}" if depends_on else depends_extra

    return GraphContextInput(
        target_method_source=target_block,
        depth1_contexts=depth1_text,
        depth2_signatures=depth2_text,
        class_fqn=str(base.get("class_fqn") or ""),
        extends=str(base.get("extends") or ""),
        implements=str(base.get("implements") or ""),
        depends_on=depends_on,
        cc=str(base.get("cc") or ""),
        cogc=str(base.get("cogc") or ""),
        loc=str(base.get("loc") or ""),
        fanout=str(base.get("fanout") or ""),
    )


async def fetch_graph_context_for_analysis(
    analysis: QueryAnalysis,
    *,
    class_label: str,
    method_label: str,
) -> GraphContextInput:
    """CypherGenerator + GraphRetriever + 매핑."""
    if not getattr(settings, "NEO4J_URI", None):
        return GraphContextInput(
            target_method_source="(Neo4j 미구성: config.NEO4J_URI 없음)",
        )

    params: dict[str, Any] = {
        "tc": analysis.target_class,
        "tm": analysis.target_method,
    }
    plan = build_context_retrieval_plan(
        analysis,
        class_label=class_label,
        method_label=method_label,
    )
    try:
        results = await execute_plan(plan, params)
        return materialize_graph_context_input(results)
    except Exception as e:
        logger.exception("Neo4j fetch failed: %s", e)
        return GraphContextInput(
            target_method_source=f"(Neo4j 조회 오류: {e})",
        )


async def fetch_raw_paths_text(
    analysis: QueryAnalysis,
    *,
    class_label: str,
    method_label: str,
) -> str:
    """graph_search 도구용 raw 텍스트."""
    if not getattr(settings, "NEO4J_URI", None):
        return "Neo4j 미설정"
    params: dict[str, Any] = {
        "tc": analysis.target_class,
        "tm": analysis.target_method,
    }
    step = build_raw_paths_step(
        analysis,
        class_label=class_label,
        method_label=method_label,
    )
    try:
        rows = await asyncio.to_thread(run_read_sync, step.cypher, params)
        if not rows:
            return "(경로 없음)"
        r = rows[0]
        return (
            f"root={r.get('root')}\n"
            f"depth1={r.get('callees_depth1')}\n"
            f"indirect={r.get('callees_indirect')}"
        )
    except Exception as e:
        return f"Neo4j 오류: {e}"
