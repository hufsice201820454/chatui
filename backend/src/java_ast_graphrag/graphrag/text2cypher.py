from __future__ import annotations

import logging
import re
from typing import Any

from config import settings

logger = logging.getLogger("chatui.java_graphrag.text2cypher")


def _normalize_neo4j_uri(uri: str) -> str:
    u = (uri or "").strip()
    if getattr(settings, "NEO4J_SSL_RELAXED", False):
        if u.startswith("bolt+s://"):
            return "neo4j+ssc://" + u[len("bolt+s://") :]
        if u.startswith("neo4j+s://"):
            return "neo4j+ssc://" + u[len("neo4j+s://") :]
    return u


def _build_neo4j_graph():
    """Create langchain Neo4jGraph lazily to avoid import-time dependency errors."""
    from langchain_neo4j import Neo4jGraph  # pyright: ignore[reportMissingImports]

    db = (settings.NEO4J_DATABASE or "").strip() or None
    if db and re.fullmatch(r"[0-9a-f]{8}(-[0-9a-f]{4}){0,4}", db, re.I):
        logger.warning("Text2Cypher: ignoring UUID-like NEO4J_DATABASE=%s, using home DB", db)
        db = None
    if db is None:
        user_db = (settings.NEO4J_USER or "").strip()
        if user_db and re.fullmatch(r"[0-9a-f]{8}(-[0-9a-f]{4}){0,4}", user_db, re.I):
            logger.warning("Text2Cypher: fallback database from NEO4J_USER=%s", user_db)
            db = user_db

    return Neo4jGraph(
        url=_normalize_neo4j_uri(settings.NEO4J_URI or ""),
        username=settings.NEO4J_USER or "",
        password=settings.NEO4J_PASSWORD or "",
        database=db,
        enhanced_schema=True,
    )


def _build_chain(graph: Any):
    from langchain_openai import ChatOpenAI
    from langchain_neo4j import GraphCypherQAChain  # pyright: ignore[reportMissingImports]

    llm = ChatOpenAI(
        model=getattr(settings, "OPENAI_MODEL", "gpt-4o"),
        api_key=getattr(settings, "OPENAI_API_KEY", None) or getattr(settings, "OPEN_API_KEY", None),
        base_url=getattr(settings, "OPEN_BASE_URL", None),
        temperature=0,
    )
    return GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        validate_cypher=True,
        return_intermediate_steps=True,
        top_k=50,
        allow_dangerous_requests=True,
    )


def _extract_query_and_rows(intermediate_steps: Any) -> tuple[str, int]:
    query = ""
    rows = 0
    if not isinstance(intermediate_steps, list):
        return query, rows
    for step in intermediate_steps:
        if not isinstance(step, dict):
            continue
        if not query and isinstance(step.get("query"), str):
            query = step["query"]
        context = step.get("context")
        if isinstance(context, list):
            rows = max(rows, len(context))
    return query, rows


def run_text2cypher(question: str) -> dict[str, Any]:
    """
    Run Text2Cypher and log generated query + result summary.

    Log examples:
      - Text2Cypher request: ...
      - Text2Cypher generated Cypher: ...
      - Text2Cypher context rows: ...
      - Text2Cypher final answer: ...
    """
    graph = _build_neo4j_graph()
    chain = _build_chain(graph)

    logger.info("Text2Cypher request: %s", question)
    try:
        result = chain.invoke({"query": question})
    except Exception as e:
        logger.exception("Text2Cypher chain failed: %s", e)
        fallback_query = (
            "MATCH (c:Class) WITH count(c) AS classCount "
            "MATCH (m:Method) RETURN classCount, count(m) AS methodCount"
        )
        rows = graph.query(fallback_query)
        logger.info("Text2Cypher fallback Cypher: %s", fallback_query)
        logger.info("Text2Cypher fallback rows: %s", len(rows))
        msg = "Text2Cypher failed; returned fallback aggregate counts."
        if rows:
            msg = (
                f"Class={rows[0].get('classCount', 0)}, "
                f"Method={rows[0].get('methodCount', 0)}"
            )
        result = {
            "query": question,
            "result": msg,
            "intermediate_steps": [
                {"query": fallback_query, "context": rows},
            ],
        }

    intermediate_steps = result.get("intermediate_steps")
    generated_cypher, row_count = _extract_query_and_rows(intermediate_steps)
    if generated_cypher:
        logger.info("Text2Cypher generated Cypher: %s", generated_cypher)
    logger.info("Text2Cypher context rows: %s", row_count)
    logger.info("Text2Cypher final answer: %s", str(result.get("result", ""))[:1000])
    return result

