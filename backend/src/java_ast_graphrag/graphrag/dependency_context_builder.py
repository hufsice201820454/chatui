"""Neo4j 의존관계 Cypher 조회 → 프롬프트 컨텍스트 블록 생성.

파이프라인 위치:
    analyze_query
    → asyncio.gather(
        fetch_graph_context,          # 기존: 메서드 소스 + depth1/2
        fetch_dependency_context,     # 신규: 클래스 간 의존 관계
      )
    → assemble_context + merge
    → tool LLM

실행 Cypher 3종:
    class_deps   : 아웃바운드 의존 (import + CALLS 경유 외부 클래스)
    reverse_deps : 인바운드 의존 (역방향 CALLS)
    hotspot      : 복잡도 분포 — CODE_SMELL / REFACTOR_GUIDE 전용

배치 위치: backend/src/java_ast_graphrag/graphrag/dependency_context_builder.py
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from src.java_ast_graphrag.graphrag.graph_retriever import run_read_sync
from src.java_ast_graphrag.models import JavaGraphIntent, QueryAnalysis

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Cypher 쿼리
# ──────────────────────────────────────────────────────────────

def _q_class_deps(class_lbl: str, method_lbl: str) -> str:
    """대상 클래스 → 아웃바운드 의존 (import + CALLS 경유)."""
    return f"""
MATCH (c:`{class_lbl}`)
WHERE $tc IS NULL
   OR toLower(c.name) = toLower($tc)
   OR c.fqn ENDS WITH ('.' + $tc)
   OR c.fqn = $tc
WITH c LIMIT 1
WITH c,
     [x IN split(coalesce(toString(c.dependsOn), ''), ';')
      WHERE size(trim(x)) > 0 | trim(x)] AS import_deps
OPTIONAL MATCH (c)-[:DECLARES]->(m:`{method_lbl}`)-[:CALLS]->(callee:`{method_lbl}`)
OPTIONAL MATCH (calleeClass:`{class_lbl}`)-[:DECLARES]->(callee)
WHERE calleeClass.fqn <> c.fqn
RETURN c.fqn                                       AS source_class,
       import_deps                                 AS import_dependencies,
       collect(DISTINCT calleeClass.fqn)           AS call_dependencies,
       collect(DISTINCT {{
           caller: m.signature,
           callee: callee.signature,
           callee_class: calleeClass.fqn
       }})                                         AS call_edges
LIMIT 1
""".strip()


def _q_reverse_deps(class_lbl: str, method_lbl: str) -> str:
    """대상 클래스를 참조하는 인바운드 의존 (역방향 CALLS)."""
    return f"""
MATCH (c:`{class_lbl}`)
WHERE $tc IS NULL
   OR toLower(c.name) = toLower($tc)
   OR c.fqn ENDS WITH ('.' + $tc)
   OR c.fqn = $tc
WITH c LIMIT 1
OPTIONAL MATCH (c)-[:DECLARES]->(m:`{method_lbl}`)
OPTIONAL MATCH (caller_method:`{method_lbl}`)-[:CALLS]->(m)
OPTIONAL MATCH (caller_class:`{class_lbl}`)-[:DECLARES]->(caller_method)
WHERE caller_class.fqn <> c.fqn
RETURN collect(DISTINCT caller_class.fqn)          AS dependent_classes,
       collect(DISTINCT {{
           caller_class:  caller_class.fqn,
           caller_method: caller_method.signature,
           callee_method: m.signature
       }})                                          AS reverse_edges
LIMIT 1
""".strip()


def _q_hotspot(class_lbl: str, method_lbl: str) -> str:
    """대상 클래스 메서드별 복잡도 분포 — CODE_SMELL / REFACTOR 전용."""
    return f"""
MATCH (c:`{class_lbl}`)
WHERE $tc IS NULL
   OR toLower(c.name) = toLower($tc)
   OR c.fqn ENDS WITH ('.' + $tc)
   OR c.fqn = $tc
WITH c LIMIT 1
MATCH (c)-[:DECLARES]->(m:`{method_lbl}`)
RETURN m.signature               AS method,
       m.cyclomaticComplexity    AS cc,
       m.cognitiveComplexity     AS cogc,
       m.loc                     AS loc,
       m.fanOut                  AS fan_out
ORDER BY m.cyclomaticComplexity DESC
LIMIT 15
""".strip()


# ──────────────────────────────────────────────────────────────
# 결과 모델
# ──────────────────────────────────────────────────────────────

@dataclass
class DependencyContext:
    source_class:      str            = ""
    import_deps:       list[str]      = field(default_factory=list)
    call_deps:         list[str]      = field(default_factory=list)
    call_edges:        list[dict]     = field(default_factory=list)
    dependent_classes: list[str]      = field(default_factory=list)
    reverse_edges:     list[dict]     = field(default_factory=list)
    hotspots:          list[dict]     = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (
            self.import_deps
            or self.call_deps
            or self.dependent_classes
            or self.hotspots
        )


# ──────────────────────────────────────────────────────────────
# 조회 실행
# ──────────────────────────────────────────────────────────────

def _safe_run(cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        return run_read_sync(cypher, params)
    except Exception as e:
        logger.warning("dependency_context query failed: %s", e)
        return []


def _fetch_sync(
    analysis: QueryAnalysis,
    class_lbl: str,
    method_lbl: str,
    include_hotspot: bool,
) -> DependencyContext:
    params: dict[str, Any] = {
        "tc": analysis.target_class,
        "tm": analysis.target_method,
    }

    rows_deps    = _safe_run(_q_class_deps(class_lbl, method_lbl),    params)
    rows_reverse = _safe_run(_q_reverse_deps(class_lbl, method_lbl),  params)
    rows_hot: list[dict[str, Any]] = (
        _safe_run(_q_hotspot(class_lbl, method_lbl), params)
        if include_hotspot
        else []
    )

    ctx = DependencyContext()

    if rows_deps:
        r = rows_deps[0]
        ctx.source_class = r.get("source_class") or ""
        ctx.import_deps  = list(r.get("import_dependencies") or [])
        ctx.call_deps    = [x for x in (r.get("call_dependencies") or []) if x]
        ctx.call_edges   = [
            e for e in (r.get("call_edges") or [])
            if e and e.get("callee_class")
        ]

    if rows_reverse:
        r = rows_reverse[0]
        ctx.dependent_classes = [
            x for x in (r.get("dependent_classes") or []) if x
        ]
        ctx.reverse_edges = [
            e for e in (r.get("reverse_edges") or [])
            if e and e.get("caller_class")
        ]

    ctx.hotspots = rows_hot
    return ctx


async def fetch_dependency_context(
    analysis: QueryAnalysis,
    *,
    class_label: str,
    method_label: str,
) -> DependencyContext:
    """비동기 엔트리포인트 — pipeline.py 에서 asyncio.gather 로 호출."""
    intent = JavaGraphIntent(analysis.intent)
    include_hotspot = intent in (
        JavaGraphIntent.CODE_SMELL,
        JavaGraphIntent.REFACTOR_GUIDE,
    )
    return await asyncio.to_thread(
        _fetch_sync,
        analysis,
        class_label,
        method_label,
        include_hotspot,
    )


# ──────────────────────────────────────────────────────────────
# 프롬프트 컨텍스트 블록 직렬화
# ──────────────────────────────────────────────────────────────

def format_dependency_block(ctx: DependencyContext, *, max_edges: int = 10) -> str:
    """DependencyContext → LLM 프롬프트 주입용 텍스트 블록."""
    if ctx.is_empty():
        return ""

    lines: list[str] = ["[클래스 의존관계]"]

    # ── 아웃바운드 ──────────────────────────────────────────────
    if ctx.call_deps:
        lines.append(f"  {ctx.source_class} 가 직접 호출하는 외부 클래스:")
        for dep in ctx.call_deps[:15]:
            lines.append(f"    - {dep}")

    if ctx.call_edges:
        lines.append("  메서드 수준 호출 엣지 (caller → callee_class.callee):")
        for e in ctx.call_edges[:max_edges]:
            lines.append(
                f"    {e.get('caller', '?')!s:<50s} "
                f"→ [{e.get('callee_class', '?')}] {e.get('callee', '?')}"
            )
        remaining = len(ctx.call_edges) - max_edges
        if remaining > 0:
            lines.append(f"    ... 외 {remaining}개")

    if ctx.import_deps:
        lines.append(f"  Import 의존 ({len(ctx.import_deps)}개):")
        for dep in ctx.import_deps[:10]:
            lines.append(f"    - {dep}")
        remaining = len(ctx.import_deps) - 10
        if remaining > 0:
            lines.append(f"    ... 외 {remaining}개")

    # ── 인바운드 ────────────────────────────────────────────────
    if ctx.dependent_classes:
        lines.append(f"\n  {ctx.source_class} 를 참조하는 상위 클래스:")
        for dep in ctx.dependent_classes[:10]:
            lines.append(f"    - {dep}")

    if ctx.reverse_edges:
        lines.append("  역방향 호출 엣지 (caller_class.caller → callee):")
        for e in ctx.reverse_edges[:max_edges]:
            lines.append(
                f"    [{e.get('caller_class', '?')}] "
                f"{e.get('caller_method', '?')} "
                f"→ {e.get('callee_method', '?')}"
            )
        remaining = len(ctx.reverse_edges) - max_edges
        if remaining > 0:
            lines.append(f"    ... 외 {remaining}개")

    # ── 복잡도 핫스팟 (CODE_SMELL / REFACTOR 전용) ──────────────
    if ctx.hotspots:
        lines.append("\n  메서드별 복잡도 (cc 내림차순):")
        for h in ctx.hotspots:
            lines.append(
                f"    {str(h.get('method', '?')):<50s} "
                f"cc={str(h.get('cc', '?')):>3}  "
                f"cogc={str(h.get('cogc', '?')):>3}  "
                f"loc={str(h.get('loc', '?')):>4}  "
                f"fanOut={h.get('fan_out', '?')}"
            )

    return "\n".join(lines)
