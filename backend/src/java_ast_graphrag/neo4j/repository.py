"""QueryAnalysis + Neo4j → GraphContextInput (퍼사드)."""
from __future__ import annotations

from config import settings

from src.java_ast_graphrag.graphrag.graph_retriever import (
    fetch_graph_context_for_analysis,
    fetch_raw_paths_text,
)
from src.java_ast_graphrag.models import GraphContextInput, QueryAnalysis


class GraphContextRepository:
    """의도별 그래프 조회 후 Assembler 입력 생성."""

    def __init__(self) -> None:
        self._class_lbl = getattr(settings, "NEO4J_LABEL_CLASS", "Class")
        self._method_lbl = getattr(settings, "NEO4J_LABEL_METHOD", "Method")

    async def fetch(self, analysis: QueryAnalysis) -> GraphContextInput:
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
