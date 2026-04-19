"""노드 1: 의도 분류 및 필수값 검증

오류 처리:
  - OpenAI API 오류   : validation_message 설정 후 END
  - 의도 분류 실패    : "정적분석 결과 조회 내용으로 질의해 주세요." → END
  - 응답 JSON 파싱 오류: 분류 실패로 간주, validation_message 설정 → END
  - 필수값 누락       : "필수값 [xxx]이(가) 누락되었습니다." → END
"""
import json
import logging

from openai import APIError, APIConnectionError, RateLimitError

from agent.state import AgentState
from agent.prompts import CLASSIFY_SYSTEM_PROMPT
from agent.nodes.helpers import call_chat_completion

logger = logging.getLogger(__name__)

_FIELD_LABELS = {"project_key": "프로젝트코드", "analysis_date": "분석일시"}


def classify_and_validate(state: AgentState) -> AgentState:
    """
    사용자 질의의 의도를 분류하고 필수값(project_key, analysis_date)을 추출/검증합니다.
    """
    query = state["query"]

    # ── OpenAI API 호출 ──────────────────────────────────────────────────────
    try:
        response = call_chat_completion(
            max_tokens=512,
            messages=[
                {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
        )
        raw = response.choices[0].message.content.strip()
    except (APIError, APIConnectionError, RateLimitError) as e:
        logger.error("[Node1] OpenAI API 오류: %s", e)
        return {
            **state,
            "intent": "unknown",
            "validation_message": "AI 서비스 연결 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        }

    # ── 응답 JSON 파싱 (마크다운 코드블록 제거 후) ──────────────────────────
    try:
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[Node1] 분류 응답 JSON 파싱 실패 — 원문: %s", raw)
        return {
            **state,
            "intent": "unknown",
            "validation_message": "정적분석 결과 조회 내용으로 질의해 주세요.",
        }

    intent = parsed.get("intent", "unknown")
    project_key = parsed.get("project_key")
    analysis_date = parsed.get("analysis_date")
    missing_fields = parsed.get("missing_fields", [])

    # ── 비관련 질의 ──────────────────────────────────────────────────────────
    if intent != "static_analysis":
        return {
            **state,
            "intent": intent,
            "project_key": project_key,
            "analysis_date": analysis_date,
            "validation_message": "정적분석 결과 조회 내용으로 질의해 주세요.",
        }

    # ── 필수값 누락 ──────────────────────────────────────────────────────────
    if missing_fields:
        missing_labels = [_FIELD_LABELS.get(f, f) for f in missing_fields]
        parts = [f"필수값 [{label}]이(가) 누락되었습니다." for label in missing_labels]
        msg = " ".join(parts) + " 다시 질의해 주세요."
        return {
            **state,
            "intent": intent,
            "project_key": project_key,
            "analysis_date": analysis_date,
            "validation_message": msg,
        }

    return {
        **state,
        "intent": intent,
        "project_key": project_key,
        "analysis_date": analysis_date,
        "validation_message": None,
    }
