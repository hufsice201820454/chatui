"""Neo4j MERGE — Class / Method / JavaFile / DECLARES / CALLS."""
from __future__ import annotations

import logging
from typing import Any

from src.java_ast_graphrag.graphrag.ingestion_pipeline.models import (
    ExtractedCall,
    ExtractedClass,
    ExtractedMethod,
)
from src.java_ast_graphrag.neo4j.client import get_neo4j_driver, run_write_with_db_fallback

logger = logging.getLogger(__name__)


def write_graph(
    *,
    classes: list[ExtractedClass],
    methods: list[ExtractedMethod],
    calls: list[ExtractedCall],
    class_lbl: str,
    method_lbl: str,
    file_lbl: str,
) -> tuple[int, int, int]:
    driver = get_neo4j_driver()
    if driver is None:
        raise RuntimeError("NEO4J_URI가 설정되지 않았습니다.")

    n_cls = n_meth = n_call = 0

    def upsert_classes(tx: Any) -> None:
        nonlocal n_cls
        for c in classes:
            tx.run(
                f"""
                MERGE (cl:`{class_lbl}` {{fqn: $fqn}})
                SET cl.name = $name,
                    cl.extends = $extends,
                    cl.implements = $implements,
                    cl.dependsOn = $dependsOn
                WITH cl
                MERGE (f:`{file_lbl}` {{path: $path}})
                MERGE (f)-[:DECLARES]->(cl)
                """,
                fqn=c.fqn,
                name=c.name,
                extends=c.extends or "",
                implements=c.implements or "",
                dependsOn=c.depends_on or "",
                path=c.file_rel_path,
            )
            n_cls += 1

    def upsert_methods(tx: Any) -> None:
        nonlocal n_meth
        for m in methods:
            tx.run(
                f"""
                MERGE (meth:`{method_lbl}` {{id: $id}})
                SET meth.name = $name,
                    meth.signature = $signature,
                    meth.source = $source,
                    meth.body = $source,
                    meth.lineCount = $lineCount,
                    meth.loc = $lineCount,
                    meth.fanOut = $fanOut,
                    meth.cyclomaticComplexity = $cc,
                    meth.cognitiveComplexity = $cogc
                WITH meth
                MATCH (cl:`{class_lbl}` {{fqn: $classFqn}})
                MERGE (cl)-[:DECLARES]->(meth)
                """,
                id=m.id,
                name=m.name,
                signature=m.signature,
                source=m.source,
                lineCount=m.line_count,
                fanOut=m.fan_out,
                cc=m.cyclomatic_complexity,
                cogc=m.cognitive_complexity,
                classFqn=m.class_fqn,
            )
            n_meth += 1

    def merge_calls(tx: Any) -> None:
        nonlocal n_call
        for c in calls:
            tx.run(
                f"""
                OPTIONAL MATCH (a:`{method_lbl}` {{id: $aid}})
                OPTIONAL MATCH (b:`{method_lbl}` {{id: $bid}})
                WITH a, b WHERE a IS NOT NULL AND b IS NOT NULL
                MERGE (a)-[:CALLS]->(b)
                """,
                aid=c.caller_method_id,
                bid=c.callee_method_id,
            )
            n_call += 1

    def do_writes(session: Any) -> None:
        session.execute_write(upsert_classes)
        session.execute_write(upsert_methods)
        session.execute_write(merge_calls)

    run_write_with_db_fallback(driver, do_writes)

    return n_cls, n_meth, n_call
