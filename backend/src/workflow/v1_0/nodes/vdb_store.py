"""VDB 적재 노드 — 최종 응대문을 ChromaDB에 저장."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from langchain_chroma import Chroma

from config import BACKEND_ROOT, resolve_backend_path, settings
from src.rag.embeddings import Embedder
from src.workflow.v1_0.state import AgentState

logger = logging.getLogger(__name__)

# 빈 응대문 적재 방지: 이 길이 미만이면 VDB 저장 건너뜀
_MIN_RESPONSE_LENGTH = 10

# Chroma 싱글턴 — 매 호출마다 새 인스턴스 생성 방지
_vdb_instance: Optional[Chroma] = None


def _resolve_vdb_path() -> str:
    override = getattr(settings, "RAG_CHROMA_PERSIST_DIR", None)
    if override and str(override).strip():
        resolved = resolve_backend_path(str(override).strip())
        if resolved:
            return resolved
    return str(BACKEND_ROOT / "chroma")


VDB_PATH = _resolve_vdb_path()
COLLECTION_NAME = getattr(settings, "RAG_COLLECTION_NAME", None) or "itsm_openai_bge_m3_1024"
EMBEDDING_MODEL = getattr(settings, "OPENAI_EMBEDDING_MODEL", None) or "bge-m3"


def _get_vdb() -> Chroma:
    """Chroma 싱글턴 반환. 최초 호출 시에만 초기화."""
    global _vdb_instance
    if _vdb_instance is None:
        embeddings = Embedder(model_name=EMBEDDING_MODEL)
        _vdb_instance = Chroma(
            persist_directory=VDB_PATH,
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
        )
        logger.info("vdb_store: Chroma 싱글턴 초기화 완료 (collection=%s)", COLLECTION_NAME)
    return _vdb_instance


def vdb_store(state: AgentState) -> AgentState:
    """HITL 승인 후 최종 응대문을 VectorDB(Chroma)에 적재.

    approve → draft_response를 final_response로 사용.
    edit    → hitl_edited를 final_response로 사용.
    reject MAX 초과 → 현재 draft_response를 그대로 저장 (강제 승인).

    Input:  user_query, draft_response, hitl_edited, hitl_action,
            repo_info, code_location
    Output: final_response, action_taken, timestamp
    """
    hitl_action = state.get("hitl_action") or "approve"
    draft = state.get("draft_response") or ""
    hitl_edited = state.get("hitl_edited") or ""

    # 최종 응대문 결정
    if hitl_action == "edit" and hitl_edited:
        final_response = hitl_edited
        logger.info("vdb_store: edit — 수정된 응대문 사용")
    else:
        final_response = draft
        logger.info("vdb_store: approve (또는 reject 한도 초과) — 초안 그대로 사용")

    timestamp = datetime.now(tz=timezone.utc).isoformat()
    user_query = state.get("user_query") or ""
    repo_info = state.get("repo_info") or ""
    code_location = state.get("code_location") or ""
    rag_reason = state.get("rag_reason") or ""

    action_taken = _extract_action_taken(final_response)

    # 빈 응대문은 VDB에 저장하지 않음
    if len(final_response.strip()) < _MIN_RESPONSE_LENGTH:
        logger.warning(
            "vdb_store: final_response가 너무 짧음 (%d자) — VDB 저장 건너뜀",
            len(final_response.strip()),
        )
        return {
            **state,
            "final_response": final_response,
            "action_taken": action_taken,
            "timestamp": timestamp,
        }

    metadata = {
        "user_query": user_query[:500],
        "hitl_action": hitl_action,
        "rag_reason": rag_reason,
        "repo_info": repo_info,
        "code_location": code_location,
        "timestamp": timestamp,
        "action_taken": action_taken[:300],
    }

    store_text = f"[문의]\n{user_query}\n\n[응대문]\n{final_response}"
    case_id = str(uuid.uuid4())

    try:
        vdb = _get_vdb()
        vdb.add_texts(
            texts=[store_text],
            metadatas=[metadata],
            ids=[case_id],
        )
        logger.info(
            "vdb_store: ChromaDB 적재 완료 (id=%s, collection=%s)",
            case_id,
            COLLECTION_NAME,
        )
    except Exception as e:
        logger.error("vdb_store: ChromaDB 적재 실패 — %s", e)

    return {
        **state,
        "final_response": final_response,
        "action_taken": action_taken,
        "timestamp": timestamp,
    }


def _extract_action_taken(response_text: str) -> str:
    """응대문에서 조치내역 섹션을 추출. 없으면 빈 문자열 반환."""
    markers = ["조치내역", "조치 내역", "**조치내역**", "**조치 내역**"]
    lower = response_text.lower()

    for marker in markers:
        idx = response_text.find(marker)
        if idx == -1:
            idx = lower.find(marker.lower())
        if idx != -1:
            section = response_text[idx + len(marker):].strip()
            for stop in ["응대문", "**응대", "\n\n\n"]:
                stop_idx = section.find(stop)
                if stop_idx != -1:
                    section = section[:stop_idx]
            return section.strip()[:500]

    return ""
