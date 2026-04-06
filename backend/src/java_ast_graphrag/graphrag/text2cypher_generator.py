"""langchain-neo4j Text2Cypher 기반 동적 쿼리 생성.

기존 cypher_generator.py 의 정적 템플릿을
Neo4jGraph 스키마 + LLM + Few-Shot 예시로 대체합니다.

배치 위치: backend/src/java_ast_graphrag/graphrag/text2cypher_generator.py
설치: pip install langchain-neo4j langchain-openai
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from config import settings
from src.java_ast_graphrag.graphrag.cypher_generator import CypherStep
# text2cypher_generator.py 상단 import 수정
from src.java_ast_graphrag.prompts.few_shot_examples import build_few_shot_block
from src.java_ast_graphrag.models import JavaGraphIntent, QueryAnalysis

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Neo4jGraph 싱글톤 (스키마 캐시)
# ──────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_graph() -> Any | None:
    uri = getattr(settings, "NEO4J_URI", None)
    if not uri:
        logger.warning("NEO4J_URI 미설정 — Text2Cypher 비활성화")
        return None
    try:
        from langchain_neo4j import Neo4jGraph

        graph = Neo4jGraph(
            url=uri,
            username=getattr(settings, "NEO4J_USER", "neo4j"),
            password=getattr(settings, "NEO4J_PASSWORD", ""),
            database=getattr(settings, "NEO4J_DATABASE", None) or "neo4j",
            enhanced_schema=True,
        )
        graph.refresh_schema()
        logger.info("Neo4jGraph 스키마 로드 완료")
        return graph
    except Exception as e:
        logger.error("Neo4jGraph 초기화 실패: %s", e)
        return None


def _schema_text() -> str:
    graph = _get_graph()
    if graph is not None:
        return graph.schema
    return _FALLBACK_SCHEMA


# ──────────────────────────────────────────────────────────────
# 폴백 스키마
# ──────────────────────────────────────────────────────────────

_FALLBACK_SCHEMA = """
Node labels:
  - Class   {fqn: String, name: String, extends: String, implements: String, dependsOn: String}
  - Method  {id: String, name: String, signature: String, source: String, body: String,
             loc: Integer, lineCount: Integer, fanOut: Integer,
             cyclomaticComplexity: Integer, cognitiveComplexity: Integer}
  - JavaFile {path: String}

Relationships:
  (:JavaFile)-[:DECLARES]->(:Class)
  (:Class)-[:DECLARES]->(:Method)
  (:Method)-[:CALLS]->(:Method)

Notes:
  - Method.id  형식: com.example.SomeClass#methodName(ParamType)
  - Class.fqn  형식: com.example.SomeClass
  - source / body 는 동일 내용 — coalesce(m.source, m.body, '') 로 접근
  - 대소문자 비교는 반드시 toLower() 사용
  - $tc = target_class 이름 (null 허용), $tm = target_method 이름 (null 허용)
""".strip()


# ──────────────────────────────────────────────────────────────
# Intent → 조회 목적 힌트
# ──────────────────────────────────────────────────────────────

_INTENT_HINTS: dict[JavaGraphIntent, str] = {
    JavaGraphIntent.METHOD_EXPLAIN: (
        "대상 메서드의 소스코드·시그니처·복잡도 메트릭(cc, cogc, loc, fanOut)을 조회하고, "
        "depth-1 호출 메서드(CALLS 1홉)와 depth-2 이상 간접 호출 시그니처를 수집하세요. "
        "클래스의 상속·구현·의존 정보도 포함하세요."
    ),
    JavaGraphIntent.CALL_CHAIN: (
        "대상 메서드에서 시작하는 호출 체인(CALLS 관계)을 깊이 $depth까지 탐색하세요. "
        "각 단계의 caller→callee 시그니처 경로를 수집하세요."
    ),
    JavaGraphIntent.IMPACT_ANALYSIS: (
        "대상 메서드를 호출하는 상위 메서드(역방향 CALLS)를 깊이 $depth까지 추적하세요. "
        "변경 시 영향받는 호출자 시그니처·클래스 목록을 반환하세요."
    ),
    JavaGraphIntent.DEPENDENCY_MAP: (
        "대상 클래스의 의존 관계(dependsOn 속성 + CALLS 경유 외부 클래스)를 수집하세요. "
        "import 의존과 런타임 호출 의존을 구분해 반환하세요."
    ),
    JavaGraphIntent.CODE_SMELL: (
        "대상 클래스의 메서드별 복잡도(cyclomaticComplexity, cognitiveComplexity, loc, fanOut)를 조회하세요. "
        "복잡도 내림차순으로 정렬해 반환하세요."
    ),
    JavaGraphIntent.REFACTOR_GUIDE: (
        "대상 메서드의 복잡도 지표·소스·depth-1 호출 관계를 조회하세요. "
        "같은 클래스의 다른 메서드 시그니처도 수집해 중복 패턴 파악에 활용하세요."
    ),
}


# ──────────────────────────────────────────────────────────────
# 프롬프트
# ──────────────────────────────────────────────────────────────

_T2C_SYSTEM = """당신은 Neo4j Cypher 전문가입니다. 주어진 그래프 스키마와 요구사항을 바탕으로
정확한 Cypher READ 쿼리를 생성합니다.

규칙:
1. WRITE 쿼리(CREATE/MERGE/DELETE/SET/REMOVE/DROP) 절대 금지
   — MATCH / OPTIONAL MATCH / RETURN / WITH / WHERE / ORDER BY / LIMIT 만 사용
2. 파라미터: $tc (target_class, null 허용), $tm (target_method, null 허용)
3. $tc/$tm 이 null일 수 있으므로 반드시 `$tc IS NULL OR ...` 패턴으로 방어
4. 대소문자 비교: toLower() 사용
5. 클래스 매칭 표준 패턴:
   `toLower(c.name) = toLower($tc) OR c.fqn ENDS WITH ('.' + $tc) OR c.fqn = $tc`
6. 레이블명: {class_lbl}, {method_lbl} — 백틱으로 감싸기
7. LIMIT 을 적절히 사용 (기본 200 이하)
8. Cypher 코드만 출력 — 설명·마크다운 펜스 금지"""

_T2C_HUMAN = """[그래프 스키마]
{schema}

{few_shot_block}
[요구사항]
{requirement}

[Cypher 파라미터]
$tc = target_class 이름 (String | null)
$tm = target_method 이름 (String | null)
탐색 깊이 힌트 = {depth}

위 예시의 패턴($tc IS NULL OR, toLower, LIMIT 등)을 따라 Cypher 쿼리 한 개만 출력:"""

_prompt = ChatPromptTemplate.from_messages(
    [("system", _T2C_SYSTEM), ("human", _T2C_HUMAN)]
)


# ──────────────────────────────────────────────────────────────
# LLM 팩토리
# ──────────────────────────────────────────────────────────────

def _get_llm() -> Any:
    """기존 LLM 프로바이더 재사용, 없으면 ChatOpenAI 직접 생성."""
    try:
        from src.core.llm.factory import get_provider
        prov = get_provider()
        if hasattr(prov, "invoke"):
            return prov
    except Exception:
        pass

    try:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            openai_api_key=getattr(settings, "OPENAI_API_KEY", None),
        )
    except ImportError:
        raise RuntimeError(
            "langchain-openai 미설치: pip install langchain-openai"
        )


# ──────────────────────────────────────────────────────────────
# Cypher 정제
# ──────────────────────────────────────────────────────────────

_FORBIDDEN_WRITE = ("CREATE ", "MERGE ", "DELETE ", "SET ", "REMOVE ", "DROP ")


def _clean_cypher(raw: str) -> str:
    text = raw.strip()
    if "```" in text:
        lines = text.split("\n")
        text = "\n".join(
            l for l in lines if not l.strip().startswith("```")
        ).strip()

    upper = text.upper()
    for kw in _FORBIDDEN_WRITE:
        if kw in upper:
            raise ValueError(
                f"Text2Cypher 가 WRITE 쿼리를 생성했습니다 ('{kw.strip()}'): "
                f"{text[:120]}"
            )
    return text


# ──────────────────────────────────────────────────────────────
# 메인 API
# ──────────────────────────────────────────────────────────────

async def generate_cypher(
    analysis: QueryAnalysis,
    *,
    class_label: str,
    method_label: str,
    user_query: str = "",
) -> str:
    """QueryAnalysis → LLM 생성 Cypher 문자열."""
    intent_key = JavaGraphIntent(analysis.intent)
    hint = _INTENT_HINTS.get(intent_key, _INTENT_HINTS[JavaGraphIntent.METHOD_EXPLAIN])
    hint = hint.replace("$depth", str(analysis.depth))

    requirement = (
        f"Intent: {analysis.intent}\n"
        f"Target class: {analysis.target_class or '(any)'}\n"
        f"Target method: {analysis.target_method or '(any)'}\n"
        f"Depth: {analysis.depth}\n"
        f"원본 질의: {user_query}\n\n"
        f"조회 목적:\n{hint}"
    )

    few_shot_block = build_few_shot_block(analysis.intent, max_examples=2)

    chain = _prompt | _get_llm() | StrOutputParser()

    raw = await chain.ainvoke(
        {
            "schema":         _schema_text(),
            "few_shot_block": few_shot_block,
            "requirement":    requirement,
            "depth":          analysis.depth,
            "class_lbl":      class_label,
            "method_lbl":     method_label,
        }
    )

    cypher = _clean_cypher(raw)
    logger.debug(
        "Text2Cypher 생성 [intent=%s]:\n%s", analysis.intent, cypher[:400]
    )
    return cypher


async def build_text2cypher_plan(
    analysis: QueryAnalysis,
    *,
    class_label: str,
    method_label: str,
    user_query: str = "",
) -> list[CypherStep]:
    """Text2Cypher 로 CypherStep 목록 생성 (graph_retriever.execute_plan 호환).

    - METHOD_EXPLAIN : ContextAssembler 포맷 유지를 위해 기존 정적 4-스텝 사용
    - 나머지 Intent : 동적 단일 쿼리 생성, 실패 시 정적 폴백
    """
    intent = JavaGraphIntent(analysis.intent)

    if intent == JavaGraphIntent.METHOD_EXPLAIN:
        from src.java_ast_graphrag.graphrag.cypher_generator import (
            build_context_retrieval_plan,
        )
        return build_context_retrieval_plan(
            analysis,
            class_label=class_label,
            method_label=method_label,
        )

    try:
        cypher = await generate_cypher(
            analysis,
            class_label=class_label,
            method_label=method_label,
            user_query=user_query,
        )
        return [CypherStep(name="text2cypher_result", cypher=cypher)]
    except Exception as e:
        logger.warning(
            "Text2Cypher 실패 [intent=%s] — 정적 플랜 폴백: %s",
            analysis.intent,
            e,
        )
        from src.java_ast_graphrag.graphrag.cypher_generator import (
            build_context_retrieval_plan,
        )
        return build_context_retrieval_plan(
            analysis,
            class_label=class_label,
            method_label=method_label,
        )
