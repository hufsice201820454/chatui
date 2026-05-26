"""Code review workflow node bridging ChatUI and embedded code_review package."""
from __future__ import annotations

import logging
import os
import sys
import types
import importlib.util
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from langgraph.types import Command, interrupt

from src.workflow.v1_0.state import AgentState

logger = logging.getLogger(__name__)

_CODE_REVIEW_ROOT = Path(__file__).resolve().parent.parent / "code_review"
_PATH_INSERTED = False

# ChatUI HITL에서 code_review의 "Cube 채널 입력"을 어떻게
# 해석할지 안내하는 문구입니다. (interrupt payload draft_response에만 추가합니다.)
_HITL_CUBE_CHANNEL_INSTRUCTION_SUFFIX = (
    "\n\n---\n"
    "**Cube 채널로 분석 결과를 전송하시겠습니까?**\n"
    "아래 입력창에 Cube 채널 번호를 입력하고 **전송** 버튼을 클릭하세요.\n"
    "전송을 원하지 않으시면 **건너뜀** 버튼을 클릭하세요."
)


def _is_langgraph_interrupt_exception(exc: Exception) -> bool:
    """LangGraph GraphInterrupt / NodeInterrupt 여부를 버전 독립적으로 판단합니다."""
    exc_type = type(exc).__name__
    return exc_type in ("GraphInterrupt", "NodeInterrupt") or ("interrupt" in exc_type.lower())


def _get_is_paused(snap: Any) -> bool:
    """inner 그래프가 interrupt 지점에서 일시 중단되었는지 확인합니다.

    LangGraph 버전에 따라 snap.next 또는 snap.tasks[].interrupts 중 하나에
    일시 중단 정보가 저장됩니다. 두 가지 방식을 모두 확인합니다.
    """
    if snap is None:
        return False
    # 표준 방식: snap.next 가 비어 있지 않으면 실행 대기 노드 있음
    next_nodes = getattr(snap, "next", ())
    if next_nodes:
        return True
    # LangGraph 0.3.x+: tasks 내 interrupts 확인
    tasks = getattr(snap, "tasks", ())
    for task in tasks:
        if getattr(task, "interrupts", ()):
            return True
    return False


def _ensure_code_review_import_path() -> None:
    global _PATH_INSERTED
    if _PATH_INSERTED:
        return
    root = str(_CODE_REVIEW_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    _PATH_INSERTED = True


@contextmanager
def _code_review_config_alias():
    """Temporarily bind `config.settings` to embedded code_review config."""
    previous_config = sys.modules.get("config")
    previous_config_settings = sys.modules.get("config.settings")

    config_dir = _CODE_REVIEW_ROOT / "config"
    settings_file = config_dir / "settings.py"

    pkg = types.ModuleType("config")
    pkg.__path__ = [str(config_dir)]  # type: ignore[attr-defined]

    spec = importlib.util.spec_from_file_location("config.settings", settings_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load code_review settings from {settings_file}")
    settings_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(settings_module)
    pkg.settings = settings_module  # type: ignore[attr-defined]

    sys.modules["config"] = pkg
    sys.modules["config.settings"] = settings_module
    try:
        yield
    finally:
        if previous_config is not None:
            sys.modules["config"] = previous_config
        else:
            sys.modules.pop("config", None)

        if previous_config_settings is not None:
            sys.modules["config.settings"] = previous_config_settings
        else:
            sys.modules.pop("config.settings", None)


@contextmanager
def _temporary_cwd(path: Path):
    prev = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def code_review_run(state: AgentState) -> AgentState:
    """Run embedded code_review analysis and map output to AgentState."""
    query = state.get("user_query") or ""
    if not query.strip():
        return {
            **state,
            "final_response": "코드 리뷰 요청 내용이 비어 있습니다.",
            "draft_response": "코드 리뷰 요청 내용이 비어 있습니다.",
            "action_taken": "code_review_skipped_empty_query",
        }

    # outer(ITSM)의 thread_id(session_id)를 그대로 inner(code_review)의 checkpoint에도 사용합니다.
    thread_id = state.get("thread_id") or str(uuid.uuid4())
    inner_config = {"configurable": {"thread_id": thread_id}}

    _ensure_code_review_import_path()
    with _code_review_config_alias():
        from agent.graph import compiled_graph

        with _temporary_cwd(_CODE_REVIEW_ROOT):
            def _read_inner_state() -> tuple[dict[str, Any], Any]:
                snap_local = compiled_graph.get_state(inner_config)
                values_local = snap_local.values or {}
                return values_local, snap_local

            # inner 그래프가 이미 실행되어 "ask_cube_channel"에서 멈춰있는지부터 확인합니다.
            try:
                inner_values, snap = _read_inner_state()
            except Exception:
                inner_values, snap = {}, None

            final_answer = (inner_values.get("final_answer") or "").strip()
            validation_message = inner_values.get("validation_message")
            is_paused = _get_is_paused(snap)

            # 검증 실패로 끝난 경우(END로 이미 도달)
            if validation_message and not is_paused:
                response = str(validation_message).strip()
                return {
                    **state,
                    "draft_response": response,
                    "final_response": response,
                    "action_taken": "code_review_validation_failed",
                }

            # 이미 완료되어 END까지 갔으면 그대로 반환
            if final_answer and not is_paused:
                return {
                    **state,
                    "draft_response": final_answer,
                    "final_response": final_answer,
                    "action_taken": "code_review_completed",
                }

            # 아직 inner 실행이 안 됐거나(또는 값이 비었거나), snapshot이 불명확하면
            # START부터 다시 inner 그래프를 invoke해서 "ask_cube_channel" interrupt 지점까지 밉니다.
            if not final_answer or not is_paused:
                inner_state: dict[str, Any] = {
                    "query": query,
                    "issues": [],
                    "rules": {},
                    "code_contexts": [],
                    "validation_message": None,
                    "final_answer": "",
                }
                try:
                    compiled_graph.invoke(inner_state, config=inner_config)
                except Exception as exc:
                    if not _is_langgraph_interrupt_exception(exc):
                        raise

                inner_values, snap = _read_inner_state()
                final_answer = (inner_values.get("final_answer") or "").strip()
                validation_message = inner_values.get("validation_message")
                is_paused = _get_is_paused(snap)

            # 다시 한 번 검증 실패/완료 분기
            if validation_message and not is_paused:
                response = str(validation_message).strip()
                return {
                    **state,
                    "draft_response": response,
                    "final_response": response,
                    "action_taken": "code_review_validation_failed",
                }

            if final_answer and not is_paused:
                return {
                    **state,
                    "draft_response": final_answer,
                    "final_response": final_answer,
                    "action_taken": "code_review_completed",
                }

            # inner이 ask_cube_channel에서 중단된 상태이면, ChatUI HITL로 중계합니다.
            # channel_id_prompt: True → 프론트엔드에서 채널 번호 전용 입력 UI를 표시합니다.
            # "edit" + edited=채널번호 → cube_channel로 전달, "approve" → 전송 건너뜀
            if not final_answer:
                final_answer = "코드 리뷰 결과를 생성하지 못했습니다."

            draft_for_prompt = final_answer + _HITL_CUBE_CHANNEL_INSTRUCTION_SUFFIX
            human_review: Any = interrupt(
                {
                    "draft_response": draft_for_prompt,
                    "action_taken": "code_review_cube_channel_prompted",
                    "channel_id_prompt": True,
                }
            )

            if not isinstance(human_review, dict):
                human_review = {"action": "approve"}

            action = str(human_review.get("action") or "approve").lower()
            edited = str(human_review.get("edited") or "")
            cube_channel = edited.strip() or None if action == "edit" else None

            # inner 그래프 재개(ask_cube_channel에서 resume)
            try:
                compiled_graph.invoke(Command(resume=cube_channel), config=inner_config)
            except Exception as exc:
                if not _is_langgraph_interrupt_exception(exc):
                    raise

            inner_values2, _ = _read_inner_state()

            cube_send_result = inner_values2.get("cube_send_result") or {}
            if isinstance(cube_send_result, dict) and cube_send_result.get("success"):
                action_taken = "code_review_cube_sent"
                channel_sent = cube_send_result.get("channel") or cube_channel or ""
                resume_message = f"✅ Cube 채널 **{channel_sent}**으로 코드 리뷰 결과가 전송되었습니다."
            elif cube_channel:
                action_taken = "code_review_completed"
                err = cube_send_result.get("error", "") if isinstance(cube_send_result, dict) else ""
                resume_message = f"⚠️ Cube 채널 전송 중 오류가 발생했습니다.{(' ' + err) if err else ''}"
            else:
                action_taken = "code_review_completed"
                resume_message = ""  # 전송 건너뜀 — 별도 메시지 없음

            return {
                **state,
                "draft_response": resume_message if resume_message else final_answer,
                "final_response": resume_message if resume_message else final_answer,
                "action_taken": action_taken,
            }
