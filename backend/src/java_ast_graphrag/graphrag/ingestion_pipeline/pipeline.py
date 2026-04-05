"""소스 수집 → 파싱 → CALL 해석 → Neo4j 적재."""
from __future__ import annotations

import logging
from pathlib import Path

from config import settings

from src.java_ast_graphrag.graphrag.ingestion_pipeline.call_resolver import resolve_calls
from src.java_ast_graphrag.graphrag.ingestion_pipeline.models import IngestionReport, WorkspaceGraph
from src.java_ast_graphrag.graphrag.ingestion_pipeline.parser import parse_java_file
from src.java_ast_graphrag.graphrag.ingestion_pipeline.writer import write_graph
from src.java_ast_graphrag.ingestion import SourceCollector, source_collector_from_settings
from src.java_ast_graphrag.ingestion.git_workspace import resolve_java_mes_root

logger = logging.getLogger(__name__)


def _dedupe_classes(classes: list):
    by_fqn: dict = {}
    for c in classes:
        by_fqn[c.fqn] = c
    return list(by_fqn.values())


def _dedupe_methods(methods: list):
    by_id: dict = {}
    for m in methods:
        by_id[m.id] = m
    return list(by_id.values())


def run_ingestion(
    root: str | Path | None = None,
    *,
    dry_run: bool = False,
) -> IngestionReport:
    """
    `root`가 None이면 `JAVA_MES_SOURCE_ROOT`(설정) 사용.
    Neo4j 라벨은 `NEO4J_LABEL_*` 사용.
    """
    if root is not None:
        collector = SourceCollector(resolve_java_mes_root(str(root)))
    else:
        sc = source_collector_from_settings()
        if sc is None:
            raise ValueError(
                "root가 없고 JAVA_MES_SOURCE_ROOT도 비어 있습니다. "
                "경로를 인자로 주거나 .env에 JAVA_MES_SOURCE_ROOT를 설정하세요.",
            )
        collector = sc

    root_str = str(collector.root)
    files = collector.collect()
    ws = WorkspaceGraph()
    errors: list[str] = []
    parsed_ok = 0

    for cf in files:
        outcome = parse_java_file(cf.relative_path, cf.content)
        ws.files.append(outcome)
        if outcome.error:
            errors.append(f"{cf.relative_path}: {outcome.error}")
        else:
            parsed_ok += 1

    classes = _dedupe_classes(ws.all_classes())
    methods = _dedupe_methods(ws.all_methods())
    calls = resolve_calls(ws)

    class_lbl = getattr(settings, "NEO4J_LABEL_CLASS", "Class")
    method_lbl = getattr(settings, "NEO4J_LABEL_METHOD", "Method")
    file_lbl = getattr(settings, "NEO4J_LABEL_JAVA_FILE", "JavaFile")

    n_cls = n_meth = n_call = 0
    if not dry_run:
        if not getattr(settings, "NEO4J_URI", None):
            raise RuntimeError("NEO4J_URI가 없습니다. 적재하려면 Neo4j 연결을 설정하세요.")
        n_cls, n_meth, n_call = write_graph(
            classes=classes,
            methods=methods,
            calls=calls,
            class_lbl=class_lbl,
            method_lbl=method_lbl,
            file_lbl=file_lbl,
        )
    else:
        n_cls, n_meth, n_call = len(classes), len(methods), len(calls)

    return IngestionReport(
        dry_run=dry_run,
        root=root_str,
        files_seen=len(files),
        files_parsed_ok=parsed_ok,
        files_failed=len(files) - parsed_ok,
        classes_upserted=n_cls,
        methods_upserted=n_meth,
        calls_merged=n_call,
        errors=errors,
    )
