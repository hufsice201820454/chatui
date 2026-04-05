"""Error Analysis 노드 (RAG 미스 fallback — LLM 자체 컨텍스트 생성)."""
from __future__ import annotations

import json
import logging

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.workflow.v1_0.state import AgentState
from src.rag.rag_pipeline import API_KEY, BASE_URL, MODEL_NAME

logger = logging.getLogger(__name__)

_SYSTEM = (
    "당신은 Hynix MES ITSM 에러 분석 전문가입니다.\n"
    "사용자 문의를 분석하여 반드시 아래 JSON 형식으로만 응답하세요.\n"
    "다른 텍스트는 포함하지 마세요.\n\n"
    '{{"error_type": "에러 유형", "root_cause": "근본 원인 분석", "suggested_action": "권장 조치 방안"}}'
)

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM),
    (
        "user",
        "문의: {user_query}\n\n추가 컨텍스트 (MCP 문서 등):\n{parsed_docs}\n\n위 문의를 분석하여 JSON으로 응답하세요.",
    ),
])


def _build_chat() -> ChatOpenAI:
    return ChatOpenAI(
        api_key=API_KEY,
        model=MODEL_NAME,
        base_url=BASE_URL,
        temperature=0,
    )


def error_analysis(state: AgentState) -> AgentState:
    """RAG 미스 시 LLM이 에러를 자체 분석하여 구조화된 컨텍스트 생성.

    Input:  user_query, parsed_docs
    Output: error_analysis {error_type, root_cause, suggested_action}
    """
    query = state.get("user_query") or ""
    parsed_docs = state.get("parsed_docs") or "없음"

    # LLM 응답 원문 — json.JSONDecodeError 블록에서 참조하므로 미리 초기화
    raw: str = ""

    try:
        chain = _PROMPT | _build_chat() | StrOutputParser()
        raw = chain.invoke({"user_query": query, "parsed_docs": parsed_docs})

        # JSON 파싱 (마크다운 코드블록 제거 후)
        raw_clean = raw.strip()
        if raw_clean.startswith("```"):
            lines = raw_clean.split("\n")
            raw_clean = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()

        analysis = json.loads(raw_clean)

        # 필수 키 검증
        for key in ("error_type", "root_cause", "suggested_action"):
            if key not in analysis:
                analysis[key] = "-"

    except json.JSONDecodeError:
        # raw가 비어있을 경우(LLM 호출 전 파싱 실패)도 안전하게 처리
        logger.warning(
            "error_analysis: JSON 파싱 실패 — raw=%r",
            raw[:200] if raw else "(LLM 응답 없음)",
        )
        analysis = {
            "error_type": "분석 결과 파싱 오류",
            "root_cause": raw if raw else "LLM 응답을 받지 못했습니다.",
            "suggested_action": "수동 검토 필요",
        }
    except Exception as e:
        logger.error("error_analysis: LLM 호출 실패 — %s", e)
        analysis = {
            "error_type": "분석 불가",
            "root_cause": str(e),
            "suggested_action": "수동 검토 필요",
        }

    logger.info(
        "error_analysis: error_type=%s",
        analysis.get("error_type", "?"),
    )

    return {
        **state,
        "error_analysis": analysis,
    }
