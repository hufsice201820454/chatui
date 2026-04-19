"""ITSM Agent 실행 헬퍼.

API 라우트 또는 직접 실행에서 Agent를 호출하는 진입점.

터미널: backend 디렉터리에서
  python -m src.workflow.v1_0.run "문의 내용"
  python -m src.workflow.v1_0.run "문의" --docs-file path/to.txt
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import uuid
from typing import Any, Optional

from langgraph.types import Command

from src.workflow.v1_0.graph import get_agent_graph
from src.workflow.v1_0.state import AgentState

logger = logging.getLogger(__name__)

_INTERRUPT_KEY = "__interrupt__"


def _parse_ainvoke_result(raw: Any) -> tuple[dict[str, Any], bool]:
    """ainvoke 반환값에서 (state dict, interrupt 여부)."""
    if isinstance(raw, dict) and _INTERRUPT_KEY in raw:
        intr = raw.get(_INTERRUPT_KEY)
        state = {k: v for k, v in raw.items() if k != _INTERRUPT_KEY}
        return state, bool(intr)
    if isinstance(raw, dict):
        return raw, False
    return {}, False


def _merge_state_after_interrupt(
    graph: Any,
    config: dict[str, Any],
    partial: dict[str, Any],
) -> dict[str, Any]:
    """체크포인트 스냅샷과 병합해 draft 등 전체 state 확보.

    get_state가 None을 반환하거나(체크포인터 없음) values가 비어 있는 경우를 안전하게 처리.
    """
    try:
        snap = graph.get_state(config)
    except Exception as e:
        logger.warning("_merge_state_after_interrupt: get_state 실패 — %s", e)
        snap = None

    if snap is not None and snap.values:
        return {**snap.values, **partial}

    logger.warning(
        "_merge_state_after_interrupt: 스냅샷 없음 또는 빈 values — partial만 반환"
    )
    return partial


async def run_agent(
    user_query: str,
    parsed_docs: Optional[str] = None,
    thread_id: Optional[str] = None,
) -> dict[str, Any]:
    """Agent 그래프를 실행하여 HITL interrupt 전까지 처리.

    Returns:
        {
          "thread_id": str,
          "status": "interrupted" | "completed",
          "draft_response": str,
          "final_response": str,
          "action_taken": str,
          "intent": str,
          "intent_confidence": float,
          "use_rag": bool,
          "rag_reason": str,
          "reject_count": int,
        }
    """
    graph = get_agent_graph()
    thread_id = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: AgentState = {
        "user_query": user_query,
        "parsed_docs": parsed_docs,
        "reject_count": 0,
        # outer thread_id를 상태에 포함해 code_review_run에서 inner 코드리뷰 그래프의
        # 동일 checkpoint(thread_id)로 재개할 수 있게 합니다.
        "thread_id": thread_id,
    }

    try:
        raw = await graph.ainvoke(initial_state, config=config)
    except Exception as e:
        if _is_interrupt(e):
            logger.info("run_agent: HITL interrupt (예외) thread_id=%s", thread_id)
            result = _merge_state_after_interrupt(graph, config, {})
            status = "interrupted"
        else:
            logger.error("run_agent: Agent 실행 오류 — %s", e)
            raise
    else:
        partial, interrupted = _parse_ainvoke_result(raw)
        if interrupted:
            logger.info(
                "run_agent: HITL interrupt (반환값 %s) thread_id=%s",
                _INTERRUPT_KEY,
                thread_id,
            )
            result = _merge_state_after_interrupt(graph, config, partial)
            status = "interrupted"
        else:
            result = partial
            status = "completed"

    return _build_response(thread_id, status, result)


async def resume_agent(
    thread_id: str,
    action: str,
    edited: Optional[str] = None,
) -> dict[str, Any]:
    """HITL interrupt 이후 사용자 검토 결과를 전달하여 그래프 재개.

    Args:
        thread_id: run_agent에서 받은 스레드 ID
        action:    "approve" | "edit" | "reject"
        edited:    edit 선택 시 수정된 응대문 / reject 시 거부 사유 (선택)
    """
    graph = get_agent_graph()
    config = {"configurable": {"thread_id": thread_id}}

    human_review: dict[str, Any] = {"action": action}
    if action == "edit":
        human_review["edited"] = edited if edited is not None else ""
    elif edited:
        human_review["edited"] = edited

    try:
        raw = await graph.ainvoke(Command(resume=human_review), config=config)
    except Exception as e:
        if _is_interrupt(e):
            result = _merge_state_after_interrupt(graph, config, {})
            status = "interrupted"
        else:
            logger.error("resume_agent: 재개 오류 — %s", e)
            raise
    else:
        partial, interrupted = _parse_ainvoke_result(raw)
        if interrupted:
            result = _merge_state_after_interrupt(graph, config, partial)
            status = "interrupted"
        else:
            result = partial
            status = "completed"

    response = _build_response(thread_id, status, result)
    response["hitl_action"] = result.get("hitl_action") or action
    return response


def _build_response(
    thread_id: str,
    status: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """run_agent / resume_agent 공통 반환 형식."""
    return {
        "thread_id": thread_id,
        "status": status,
        "draft_response": result.get("draft_response") or "",
        "final_response": result.get("final_response") or "",
        "action_taken": result.get("action_taken") or "",
        "intent": result.get("intent") or "support",
        "intent_confidence": result.get("intent_confidence") or 0.0,
        "intent_reason": result.get("intent_reason") or "",
        "intent_source": result.get("intent_source") or "fallback_rule",
        "intent_signals": result.get("intent_signals") or [],
        "use_rag": result.get("use_rag") or False,
        "rag_reason": result.get("rag_reason") or "",
        "reject_count": result.get("reject_count") or 0,
        "timestamp": result.get("timestamp") or "",
    }


def _is_interrupt(exc: Exception) -> bool:
    """LangGraph GraphInterrupt 여부 확인 (버전 독립적)."""
    exc_type = type(exc).__name__
    return exc_type in ("GraphInterrupt", "NodeInterrupt") or (
        "interrupt" in exc_type.lower()
    )


def _prompt_hitl_action() -> tuple[str, Optional[str]]:
    """터미널에서 approve / edit / reject 및 수정본 입력."""
    while True:
        raw = input("HITL — approve / edit / reject: ").strip().lower()
        if raw in ("approve", "edit", "reject"):
            break
        print("approve, edit, reject 중 하나를 입력하세요.", file=sys.stderr)

    edited: Optional[str] = None
    if raw == "edit":
        print("수정된 응대문을 입력하세요. (여러 줄: 마지막에 빈 줄로 종료)", file=sys.stderr)
        lines: list[str] = []
        while True:
            line = input()
            if not line:
                break
            lines.append(line)
        edited = "\n".join(lines).strip()
        if not edited:
            print("수정본이 비었습니다. approve로 처리합니다.", file=sys.stderr)
            return "approve", None
    elif raw == "reject":
        print(
            "거부 사유·개선 요청을 한 줄로 입력하세요. (선택, Enter만 누르면 생략)",
            file=sys.stderr,
        )
        reason = input().strip()
        if reason:
            edited = reason

    return raw, edited


def _print_hitl_banner(out: dict[str, Any]) -> None:
    print("\n--- HITL 검토 ---", file=sys.stderr)
    print(f"thread_id : {out.get('thread_id')}", file=sys.stderr)
    print(f"reject_count: {out.get('reject_count', 0)}", file=sys.stderr)
    draft = out.get("draft_response") or ""
    print(f"\n[초안]\n{draft}\n", file=sys.stderr)


async def _cli_async(query: str, parsed_docs: Optional[str]) -> dict[str, Any]:
    out = await run_agent(query, parsed_docs=parsed_docs)
    while out.get("status") == "interrupted":
        _print_hitl_banner(out)
        action, edited = _prompt_hitl_action()
        out = await resume_agent(out["thread_id"], action, edited=edited)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="ITSM Agent CLI (HITL은 터미널 input)")
    parser.add_argument(
        "query",
        nargs="?",
        default="MES 로그인 오류가 납니다.",
        help="사용자 문의",
    )
    parser.add_argument(
        "--docs-file",
        type=str,
        default=None,
        metavar="PATH",
        help="참조 문서 텍스트 파일 (parsed_docs)",
    )
    args = parser.parse_args()

    parsed_docs: Optional[str] = None
    if args.docs_file:
        with open(args.docs_file, encoding="utf-8") as f:
            parsed_docs = f.read()

    out = asyncio.run(_cli_async(args.query, parsed_docs))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
