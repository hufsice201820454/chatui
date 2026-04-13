from __future__ import annotations

from dataclasses import asdict
from typing import Any

from neo4j import AsyncGraphDatabase

from config import settings
from src.java_ast_graphrag.ingestion.parser.ast_parser import ExtractedClass, ExtractedMethod
from src.java_ast_graphrag.ingestion.resolver.call_resolver import ExtractedCall


def _neo4j_auth() -> tuple[str, str] | None:
    if settings.NEO4J_USER and settings.NEO4J_PASSWORD:
        return (settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    return None


def _normalize_neo4j_uri(uri: str) -> str:
    u = uri.strip()
    if getattr(settings, "NEO4J_SSL_RELAXED", False):
        if u.startswith("bolt+s://"):
            return "bolt+ssc://" + u[len("bolt+s://") :]
    return u


def _chunks(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


async def _write_classes(session: Any, rows: list[dict[str, Any]], class_lbl: str, file_lbl: str) -> None:
    query = f"""
    UNWIND $rows AS r
    MERGE (c:`{class_lbl}` {{fqn: r.fqn}})
    SET c.name = r.name
    WITH c, r
    MERGE (f:`{file_lbl}` {{path: r.file_rel_path}})
    MERGE (f)-[:DECLARES]->(c)
    """
    cursor = await session.run(query, rows=rows)
    await cursor.consume()


async def _write_methods(session: Any, rows: list[dict[str, Any]], class_lbl: str, method_lbl: str) -> None:
    query = f"""
    UNWIND $rows AS r
    MERGE (m:`{method_lbl}` {{id: r.id}})
    SET m.name = r.name,
        m.signature = r.signature,
        m.source = r.source,
        m.body = r.body,
        m.lineCount = r.line_count,
        m.loc = r.loc,
        m.fanOut = r.fan_out,
        m.cyclomaticComplexity = r.cyclomatic_complexity,
        m.cognitiveComplexity = r.cognitive_complexity
    WITH m, r
    MATCH (c:`{class_lbl}` {{fqn: r.class_fqn}})
    MERGE (c)-[:DECLARES]->(m)
    """
    cursor = await session.run(query, rows=rows)
    await cursor.consume()


async def _write_calls(session: Any, rows: list[dict[str, Any]], method_lbl: str) -> None:
    query = f"""
    UNWIND $rows AS r
    MATCH (a:`{method_lbl}` {{id: r.caller_method_id}})
    MATCH (b:`{method_lbl}` {{id: r.callee_method_id}})
    MERGE (a)-[:CALLS]->(b)
    """
    cursor = await session.run(query, rows=rows)
    await cursor.consume()


async def write_graph(
    classes: list[ExtractedClass],
    methods: list[ExtractedMethod],
    calls: list[ExtractedCall],
    *,
    batch_size: int = 500,
) -> tuple[int, int, int]:
    uri = settings.NEO4J_URI
    if not uri:
        raise RuntimeError("NEO4J_URI is required")
    uri = _normalize_neo4j_uri(uri)
    if not uri.startswith("bolt://") and not uri.startswith("bolt+s://") and not uri.startswith("bolt+ssc://"):
        raise RuntimeError("NEO4J_URI must use bolt:// scheme")

    driver = AsyncGraphDatabase.driver(uri, auth=_neo4j_auth())
    class_lbl = settings.NEO4J_LABEL_CLASS
    method_lbl = settings.NEO4J_LABEL_METHOD
    file_lbl = settings.NEO4J_LABEL_JAVA_FILE

    try:
        # Aura 환경에서 async driver + 명시 database 조합이 graph reference 오류를 낼 수 있어
        # 홈 DB 세션으로 실행한다.
        async with driver.session() as session:
            for chunk in _chunks([asdict(c) for c in classes], batch_size):
                await _write_classes(session, chunk, class_lbl, file_lbl)
            for chunk in _chunks([asdict(m) for m in methods], batch_size):
                await _write_methods(session, chunk, class_lbl, method_lbl)
            for chunk in _chunks([asdict(c) for c in calls], batch_size):
                await _write_calls(session, chunk, method_lbl)
    finally:
        await driver.close()
    return len(classes), len(methods), len(calls)

