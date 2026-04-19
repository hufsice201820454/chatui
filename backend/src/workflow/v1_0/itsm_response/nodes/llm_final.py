"""LLM 응대문 초안 생성 노드."""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from src.workflow.v1_0.state import AgentState
from src.core.llm.factory import get_provider
from src.core.schema.base import ChatMessage

logger = logging.getLogger(__name__)

# MCP/첨부 파싱 본문이 과도하게 길어질 때 시스템 프롬프트 상한 (문자)
_PARSED_DOCS_MAX_CHARS = 16_000


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _call_llm(system_prompt: str, user_content: str) -> str:
    provider = get_provider(None)
    response = _run_async(
        provider.generate(
            [ChatMessage(role="user", content=user_content)],
            system_prompt=system_prompt,
        )
    )
    return (response.content or "").strip()


def _build_context_str(state: AgentState) -> str:
    rag_contexts = state.get("rag_contexts") or []
    error_analysis_result = state.get("error_analysis") or {}

    if rag_contexts:
        parts = []
        for i, ctx in enumerate(rag_contexts, 1):
            text = (ctx.get("text") or "")[:600]
            parts.append(f"[유사 케이스 {i}]\n{text}")
        return "\n\n".join(parts)

    if error_analysis_result:
        return (
            f"에러 유형: {error_analysis_result.get('error_type', '-')}\n"
            f"근본 원인: {error_analysis_result.get('root_cause', '-')}\n"
            f"권장 조치: {error_analysis_result.get('suggested_action', '-')}"
        )

    return "참고 컨텍스트 없음 — 일반적인 ITSM 지식으로 응대하세요."


def _build_system_prompt(state: AgentState) -> str:
    """참조 문서(parsed_docs)와 RAG/에러 요약을 시스템 프롬프트에 포함."""
    doc = (state.get("parsed_docs") or "").strip()
    if len(doc) > _PARSED_DOCS_MAX_CHARS:
        doc = doc[:_PARSED_DOCS_MAX_CHARS] + "\n\n...(참조 문서 일부 생략)"

    doc_section = doc if doc else "(첨부·MCP 등 참조 문서 없음)"
    rag_section = _build_context_str(state)

    return (
        "당신은 Hynix MES ITSM 응대 전문가입니다.\n"
        "아래 [참조 문서]와 [RAG·에러 참고]를 우선 활용하고, 없는 사실은 추측하지 마세요.\n\n"
        "## 참조 문서 (사용자 첨부·MCP 파싱 등)\n"
        f"{doc_section}\n\n"
        "## RAG·에러 참고\n"
        f"{rag_section}\n\n"
        "## 응대문\n"
        "(사용자 문의에 대한 친절하고 명확한 응답. 2~4문장 이내.)\n\n"
        "## 조치내역\n"
        "(구체적인 처리 절차 및 조치 방법을 번호 목록으로 작성.)\n\n"
        "규칙:\n"
        "- 반드시 한국어로 작성\n"
        "- 위 두 섹션(## 응대문, ## 조치내역)을 반드시 모두 포함할 것\n"
        "- 컨텍스트에 없는 내용은 추측하지 말 것"
    )


def _extract_forbidden_sentences(text: str, max_sentences: int = 5) -> list[str]:
    """이전 초안에서 핵심 문장을 추출해 금지 목록으로 반환.

    - 너무 짧은 문장(20자 미만)이나 마크다운 헤더는 제외
    - 최대 max_sentences개만 반환
    """
    import re
    sentences = re.split(r"(?<=[.。!?])\s+|\n", text)
    result = []
    for s in sentences:
        s = s.strip()
        if s.startswith("#") or len(s) < 20:
            continue
        # 번호 목록 앞부분 제거 (예: "1. ", "- ")
        s = re.sub(r"^[\d]+\.\s*|^[-*]\s*", "", s).strip()
        if len(s) >= 20:
            result.append(s)
        if len(result) >= max_sentences:
            break
    return result


def llm_final(state: AgentState) -> AgentState:
    """chat_model으로 응대문 초안 생성.

    - 최초 호출: hitl_action이 None → 일반 초안 생성
    - reject 후 재호출: hitl_action == "reject" → 피드백 반영 재생성
      reject_count를 1 증가시켜 무한 루프 방지에 활용.

    메시지 누적은 별도 노드에서 처리하며, 이 노드는 draft 생성에 집중한다.
    """
    query = state.get("user_query") or ""
    hitl_action = state.get("hitl_action")          # 최초 호출 시 None
    hitl_edited = state.get("hitl_edited")
    reject_count = state.get("reject_count") or 0
    system_prompt = _build_system_prompt(state)

    if hitl_action == "reject":
        logger.info(
            "llm_final: reject 재생성 (reject_count=%d → %d)",
            reject_count,
            reject_count + 1,
        )
        prev_draft = (state.get("draft_response") or "").strip()
        feedback = (hitl_edited or "").strip() or "구체적 거부 사유 없음."

        # 이전 초안에서 핵심 문장을 추출해 명시적으로 금지 목록 생성
        forbidden_lines = _extract_forbidden_sentences(prev_draft)
        forbidden_block = (
            "## 절대 사용 금지 문장 (아래 문장 또는 유사 표현을 그대로 쓰지 말 것)\n"
            + "\n".join(f"  - {s}" for s in forbidden_lines)
        ) if forbidden_lines else ""

        parts = [
            f"문의: {query}\n",
            f"## 거부된 이전 초안\n{prev_draft or '(없음)'}\n",
        ]
        if forbidden_block:
            parts.append(forbidden_block + "\n")
        parts.append(
            f"[HITL] 검토자 거부 사유: {feedback}\n\n"
            "재작성 요구사항 (모두 준수):\n"
            "1. 응대문 첫 문장을 이전과 완전히 다른 구조로 시작할 것 (인사말 형태도 바꿀 것)\n"
            "2. 조치내역 각 항목의 동사·순서·세부 내용을 이전과 다르게 구성할 것\n"
            "3. 위 '절대 사용 금지 문장' 목록의 표현을 그대로 쓰지 말 것\n"
            "4. 사실 관계(원인·조치)는 유지하되 모든 문장을 새로 써서 제출할 것\n"
        )
        user_content = "\n".join(parts)
        new_reject_count = reject_count + 1
    else:
        user_content = f"문의: {query}"
        new_reject_count = reject_count      # 변경 없음

    try:
        draft = _call_llm(system_prompt, user_content)
    except Exception as e:
        logger.error("llm_final: LLM 호출 실패 -- %s", e)
        return {
            **state,
            "draft_response": f"[오류] LLM 응답 생성 실패: {e}",
            "reject_count": new_reject_count,
        }

    logger.info("llm_final: 초안 생성 완료 (len=%d chars)", len(draft))

    return {
        **state,
        "draft_response": draft,
        "reject_count": new_reject_count,
    }
