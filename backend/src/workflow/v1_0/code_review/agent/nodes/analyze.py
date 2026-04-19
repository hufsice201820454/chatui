"""노드 4: LLM 분석 실행 및 결과 생성

오류 처리:
  - OpenAI API 오류    : 재시도 2회(총 3회 시도) 후 실패 시 오류 메시지 반환
  - 응답 처리 오류     : 원문 응답을 그대로 반환하고 파싱 오류 로그 기록
"""
import json
import logging
import time

from openai import APIError, APIConnectionError, RateLimitError

from agent.state import AgentState
from agent.prompts import ANALYZE_SYSTEM_PROMPT, ANALYZE_USER_TEMPLATE
from agent.nodes.helpers import call_chat_completion

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2       # 최대 재시도 횟수 (총 3회 시도)
_RETRY_DELAY = 3       # 재시도 대기 시간(초)


def _call_llm(user_message: str) -> str:
    """
    OpenAI API를 호출합니다. 실패 시 최대 _MAX_RETRIES회 재시도합니다.
    모든 시도 실패 시 None을 반환합니다.
    """
    last_error = None
    for attempt in range(1, _MAX_RETRIES + 2):  # 1, 2, 3
        try:
            response = call_chat_completion(
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": ANALYZE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            )
            return response.choices[0].message.content
        except RateLimitError as e:
            last_error = e
            wait = _RETRY_DELAY * attempt
            logger.warning(
                "[Node4] RateLimit 오류 (시도 %d/%d) — %ds 후 재시도. 오류: %s",
                attempt, _MAX_RETRIES + 1, wait, e,
            )
            time.sleep(wait)
        except (APIError, APIConnectionError) as e:
            last_error = e
            logger.warning(
                "[Node4] OpenAI API 오류 (시도 %d/%d) — %ds 후 재시도. 오류: %s",
                attempt, _MAX_RETRIES + 1, _RETRY_DELAY, e,
            )
            if attempt <= _MAX_RETRIES:
                time.sleep(_RETRY_DELAY)

    logger.error("[Node4] OpenAI API 최종 실패 (%d회 시도) — 오류: %s", _MAX_RETRIES + 1, last_error)
    return None


def analyze_and_respond(state: AgentState) -> AgentState:
    """
    이슈 목록, Rule 정보, 코드 컨텍스트를 OpenAI LLM에 전달하여
    이슈별 원인과 수정방안을 마크다운 테이블로 생성합니다.
    """
    query = state["query"]
    issues = state.get("issues", [])
    rules = state.get("rules", {})
    code_contexts = state.get("code_contexts", [])

    # 이슈에 코드 컨텍스트 병합 (issue_key 기준, None 컨텍스트 허용)
    context_map = {ctx.get("issue_key", ""): ctx for ctx in code_contexts}
    enriched_issues = [
        {**issue, "code_context": context_map.get(issue.get("key", ""), None)}
        for issue in issues
    ]

    user_message = ANALYZE_USER_TEMPLATE.format(
        query=query,
        issues_json=json.dumps(enriched_issues, ensure_ascii=False, indent=2),
        rules_json=json.dumps(rules, ensure_ascii=False, indent=2),
        contexts_json=json.dumps(code_contexts, ensure_ascii=False, indent=2),
    )

    # ── LLM 호출 (재시도 포함) ───────────────────────────────────────────────
    raw_response = _call_llm(user_message)

    if raw_response is None:
        return {
            **state,
            "final_answer": "AI 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        }

    # ── 응답 후처리 (파싱 오류 시 원문 반환) ─────────────────────────────────
    try:
        final_answer = raw_response.strip()
        # 마크다운 테이블 시작 여부 기본 검증
        if not final_answer:
            raise ValueError("LLM 응답이 비어 있습니다.")
    except Exception as e:
        logger.warning("[Node4] 응답 후처리 오류 — 원문을 그대로 반환합니다. 오류: %s", e)
        final_answer = raw_response

    return {**state, "final_answer": final_answer}
