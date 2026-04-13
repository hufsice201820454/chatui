from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import settings
from src.java_ast_graphrag.ingestion.collector.source_collector import collect_java_sources
from src.java_ast_graphrag.ingestion.loader.writer import write_graph
from src.java_ast_graphrag.ingestion.parser.ast_parser import (
    ExtractedClass,
    ExtractedMethod,
    PendingCall,
    parse_java_file,
)
from src.java_ast_graphrag.ingestion.resolver.call_resolver import ExtractedCall, resolve_calls


@dataclass
class IngestionReport:
    root: str
    files_seen: int
    files_parsed_ok: int
    files_failed: int
    classes_upserted: int
    methods_upserted: int
    calls_merged: int
    errors: list[str]


async def run_ingestion(root: str | Path | None = None, *, dry_run: bool = False) -> IngestionReport:
    source_root = root or getattr(settings, "JAVA_MES_SOURCE_ROOT", None)
    if not source_root:
        raise ValueError("root is required or JAVA_MES_SOURCE_ROOT must be set")

    src_files = collect_java_sources(source_root)
    classes: list[ExtractedClass] = []
    methods: list[ExtractedMethod] = []
    pending_calls: list[PendingCall] = []
    errors: list[str] = []
    ok = 0

    for src in src_files:
        out = parse_java_file(src.relative_path, src.content)
        if out.error:
            errors.append(f"{src.relative_path}: {out.error}")
            continue
        ok += 1
        classes.extend(out.classes)
        methods.extend(out.methods)
        pending_calls.extend(out.pending_calls)

    dedup_classes = {c.fqn: c for c in classes}
    dedup_methods = {m.id: m for m in methods}
    resolved_calls: list[ExtractedCall] = resolve_calls(list(dedup_methods.values()), pending_calls)
    if dry_run:
        n_cls, n_meth, n_call = len(dedup_classes), len(dedup_methods), len(resolved_calls)
    else:
        n_cls, n_meth, n_call = await write_graph(
            list(dedup_classes.values()),
            list(dedup_methods.values()),
            resolved_calls,
            batch_size=500,
        )
    return IngestionReport(
        root=str(source_root),
        files_seen=len(src_files),
        files_parsed_ok=ok,
        files_failed=len(src_files) - ok,
        classes_upserted=n_cls,
        methods_upserted=n_meth,
        calls_merged=n_call,
        errors=errors,
    )

