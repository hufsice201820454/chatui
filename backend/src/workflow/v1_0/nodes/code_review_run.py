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

# ChatUI HITL(approve/edit/reject)에서 code_review의 "Cube 채널 입력"을 어떻게
# 해석할지 안내하는 문구입니다. (draft_response에만 추가합니다.)
_HITL_CUBE_CHANNEL_INSTRUCTION_SUFFIX = (
    "\n\n"
    "전송을 원하면 `edit`를 선택하고 입력칸에 Cube 채널 번호를 입력하세요. "
    "approve/reject는 전송을 건너뜁니다."
)

def _is_langgraph_interrupt_exception(exc: Exception) -> bool:
    """LangGraph GraphInterrupt / NodeInterrupt 여부를 버전 독립적으로 판단합니다."""
    exc_type = type(exc).__name__
    return exc_type in ("GraphInterrupt", "NodeInterrupt") or ("interrupt" in exc_type.lower())


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
            is_paused = bool(getattr(snap, "next", None))

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
                is_paused = bool(getattr(snap, "next", None))

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

            # inner이 ask_cube_channel에서 중단된 상태이면, ChatUI HITL(approve/edit/reject)로 중계합니다.
            # approve/reject는 cube 전송 skip, edit는 edit 문자열을 cube_channel로 사용합니다.
            if not final_answer:
                final_answer = "코드 리뷰 결과를 생성하지 못했습니다."

            draft_for_prompt = final_answer + _HITL_CUBE_CHANNEL_INSTRUCTION_SUFFIX
            human_review: Any = interrupt(
                {
                    "draft_response": draft_for_prompt,
                    "action_taken": "code_review_cube_channel_prompted",
                }
            )

            if not isinstance(human_review, dict):
                human_review = {"action": "approve"}

            action = str(human_review.get("action") or "approve").lower()
            edited = str(human_review.get("edited") or "")
            cube_channel = edited.strip() or None if action == "edit" else None

            # inner 그래프 재개(ask_cube_channel에서 resume)
            compiled_graph.invoke(Command(resume=cube_channel), config=inner_config)
            inner_values2, _ = _read_inner_state()

            final_answer2 = (inner_values2.get("final_answer") or "").strip()
            if not final_answer2:
                final_answer2 = final_answer

            cube_send_result = inner_values2.get("cube_send_result") or {}
            action_taken = (
                "code_review_cube_sent"
                if isinstance(cube_send_result, dict) and cube_send_result.get("success")
                else "code_review_completed"
            )

            return {
                **state,
                "draft_response": final_answer2,
                "final_response": final_answer2,
                "action_taken": action_taken,
            }
