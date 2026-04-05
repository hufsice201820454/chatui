"""하이브리드 QueryAnalyzer: 규칙 우선, 애매하면 LLM (문서: QueryAnalyzer)."""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from src.core.llm.factory import get_provider
from src.core.schema.base import ChatMessage
from src.java_ast_graphrag.models import JavaGraphIntent, QueryAnalysis
from src.java_ast_graphrag.prompts.query_analyzer import (
    QUERY_ANALYZER_SYSTEM,
    QUERY_ANALYZER_USER,
)

logger = logging.getLogger(__name__)

_RULE_PATTERNS: list[tuple[re.Pattern[str], JavaGraphIntent, float]] = [
    (re.compile(r"호출\s*체인|콜\s*체인|call\s*chain|누가\s*.*호출", re.I), JavaGraphIntent.CALL_CHAIN, 0.85),
    (re.compile(r"영향|impact|깨지|파급|변경\s*시", re.I), JavaGraphIntent.IMPACT_ANALYSIS, 0.82),
    (re.compile(r"의존|dependency|의존성\s*맵|연결\s*관계", re.I), JavaGraphIntent.DEPENDENCY_MAP, 0.8),
    (re.compile(r"스멜|smell|안티\s*패턴|품질|복잡\s*도", re.I), JavaGraphIntent.CODE_SMELL, 0.78),
    (re.compile(r"리팩터|리팩토링|refactor|개선\s*안", re.I), JavaGraphIntent.REFACTOR_GUIDE, 0.78),
    (re.compile(r"뭐\s*하|어떻게\s*동작|설명|무슨\s*일", re.I), JavaGraphIntent.METHOD_EXPLAIN, 0.75),
]

_CLASS_RE = re.compile(r"\b([A-Z][a-zA-Z0-9]*(?:\.[A-Z][a-zA-Z0-9_]*)+)\b")
_SIMPLE_CLASS_RE = re.compile(r"\b([A-Z][a-zA-Z0-9]+)\b")
_METHOD_RE = re.compile(r"\b([a-z][a-zA-Z0-9]+)\s*\(")


def _extract_class(text: str) -> Optional[str]:
    m = _CLASS_RE.search(text)
    if m:
        return m.group(1).split(".")[-1]
    words = _SIMPLE_CLASS_RE.findall(text)
    skip = {"JSON", "API", "HTTP", "SQL", "JDK", "JVM", "DTO", "DAO"}
    for w in words:
        if w not in skip and len(w) > 2:
            return w
    return None


def _extract_method(text: str) -> Optional[str]:
    m = _METHOD_RE.search(text)
    if m:
        name = m.group(1)
        if name not in ("if", "for", "while", "switch", "catch", "try", "new"):
            return name
    return None


def _extract_depth(text: str) -> Optional[int]:
    m = re.search(r"깊이\s*(\d+)|depth\s*[=:]?\s*(\d+)", text, re.I)
    if m:
        return int(m.group(1) or m.group(2))
    return None


def rule_suggest(user_query: str) -> tuple[Optional[QueryAnalysis], float]:
    """규칙 매칭 시 (분석, confidence). 미매칭 시 (None, 0)."""
    q = user_query.strip()
    best: tuple[Optional[QueryAnalysis], float] = (None, 0.0)
    for pat, intent, conf in _RULE_PATTERNS:
        if pat.search(q) and conf > best[1]:
            tc = _extract_class(q)
            tm = _extract_method(q)
            depth = _extract_depth(q) or 2
            best = (
                QueryAnalysis(
                    intent=intent.value,
                    target_class=tc,
                    target_method=tm,
                    depth=depth,
                    rule_matched=True,
                ),
                conf,
            )
    return best


def _parse_llm_json(raw: str) -> dict:
    text = raw.strip()
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                text = p
                break
    return json.loads(text)


async def analyze_query_llm(user_query: str) -> QueryAnalysis:
    provider = get_provider()
    user_content = QUERY_ANALYZER_USER.format(user_query=user_query)
    resp = await provider.generate(
        [ChatMessage(role="user", content=user_content)],
        system_prompt=QUERY_ANALYZER_SYSTEM,
    )
    data = _parse_llm_json(resp.content)
    return QueryAnalysis.model_validate({**data, "rule_matched": False})


async def analyze_query(user_query: str, *, rule_confidence_threshold: float = 0.8) -> QueryAnalysis:
    ruled, conf = rule_suggest(user_query)
    if ruled is not None and conf >= rule_confidence_threshold:
        logger.debug("QueryAnalyzer: rule hit conf=%s intent=%s", conf, ruled.intent)
        return ruled
    try:
        return await analyze_query_llm(user_query)
    except Exception as e:
        logger.warning("QueryAnalyzer: LLM failed (%s), fallback METHOD_EXPLAIN", e)
        return QueryAnalysis(
            intent=JavaGraphIntent.METHOD_EXPLAIN.value,
            target_class=_extract_class(user_query),
            target_method=_extract_method(user_query),
            depth=_extract_depth(user_query) or 2,
            rule_matched=False,
        )
