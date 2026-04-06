"""QueryAnalysis + Neo4j → GraphContextInput 퍼사드.

text2cypher_enabled=True 시 Text2Cypher 동적 플랜 사용.
환경변수 TEXT2CYPHER_ENABLED=true 로도 제어 가능.

배치 위치: backend/src/java_ast_graphrag/neo4j/repository.py
"""
from __future__ import annotations

import logging
from typing import Any

from config import settings

from src.java_ast_graphrag.graphrag.graph_retriever import (
    execute_plan,
    fetch_graph_context_for_analysis,
    fetch_raw_paths_text,
    materialize_graph_context_input,
)
from src.java_ast_graphrag.models import GraphContextInput, QueryAnalysis

logger = logging.getLogger(__name__)


class GraphContextRepository:
    """의도별 그래프 조회 후 ContextAssembler 입력 생성.

    Args:
        text2cypher_enabled:
            True  → Text2Cypher 동적 쿼리 (METHOD_EXPLAIN 제외)
            False → 기존 정적 쿼리 템플릿 (기본값)
            None  → 환경변수 TEXT2CYPHER_ENABLED 로 결정
    """

    def __init__(self, *, text2cypher_enabled: bool | None = None) -> None:
        self._class_lbl  = getattr(settings, "NEO4J_LABEL_CLASS",  "Class")
        self._method_lbl = getattr(settings, "NEO4J_LABEL_METHOD", "Method")

        if text2cypher_enabled is None:
            self._t2c = bool(getattr(settings, "TEXT2CYPHER_ENABLED", False))
        else:
            self._t2c = text2cypher_enabled

    # ── 공개 API ────────────────────────────────────────────────

    async def fetch(
        self,
        analysis: QueryAnalysis,
        *,
        user_query: str = "",
    ) -> GraphContextInput:
        if self._t2c:
            return await self._fetch_text2cypher(analysis, user_query=user_query)
        return await fetch_graph_context_for_analysis(
            analysis,
            class_label=self._class_lbl,
            method_label=self._method_lbl,
        )

    async def fetch_raw_paths(self, analysis: QueryAnalysis) -> str:
        return await fetch_raw_paths_text(
            analysis,
            class_label=self._class_lbl,
            method_label=self._method_lbl,
        )

    # ── Text2Cypher 경로 ─────────────────────────────────────────

    async def _fetch_text2cypher(
        self,
        analysis: QueryAnalysis,
        *,
        user_query: str = "",
    ) -> GraphContextInput:
        from src.java_ast_graphrag.graphrag.text2cypher_generator import (
            build_text2cypher_plan,
        )

        plan = await build_text2cypher_plan(
            analysis,
            class_label=self._class_lbl,
            method_label=self._method_lbl,
            user_query=user_query,
        )

        params: dict[str, Any] = {
            "tc": analysis.target_class,
            "tm": analysis.target_method,
        }

        # 동적 단일 쿼리 경로 (METHOD_EXPLAIN 제외 Intent)
        if len(plan) == 1 and plan[0].name == "text2cypher_result":
            results = await execute_plan(plan, params)
            raw_rows = results.get("text2cypher_result") or []
            raw_text = (
                "\n".join(str(r) for r in raw_rows)
                if raw_rows
                else "(결과 없음)"
            )
            logger.debug(
                "text2cypher_result rows=%d", len(raw_rows)
            )
            return GraphContextInput(target_method_source=raw_text)

        # METHOD_EXPLAIN 정적 4-스텝 경로 → materialize 로 포맷 유지
        results = await execute_plan(plan, params)
        return materialize_graph_context_input(results)