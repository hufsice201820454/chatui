"""
Chat / streaming endpoint (BE-LLM-01 ~ BE-LLM-05).
POST /chat/{session_id}/stream  – SSE streaming response
POST /chat/{session_id}         – Non-streaming completion
"""
import json
import logging
from typing import Literal, Optional, List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import chat_rate_limit
from src.core.responses import ok
from src.datasource.sqlite.sqlite import AsyncSessionLocal, get_db
from src.sessions.service import chat_stream
from src.core.llm.factory import get_provider
from src.core.schema.base import ChatMessage
from src.sessions import repository as repo
from mcp_service.client import (
    call_image_parse_via_mcp,
    call_parse_document_via_mcp,
)
from src.rag.bootstrap import get_rag_pipeline
from src.workflow import (
    HIGH_CONFIDENCE_KEYWORDS,
    ITSM_KEYWORDS,
    resume_agent,
    run_agent,
)

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger("chatui.api.chat")

MAX_VISION_CONTEXT_CHARS = 3500
MAX_DOCUMENT_CONTEXT_CHARS = 8000


class ImagePayload(BaseModel):
    mime: str
    data: str  # base64


class DocumentPayload(BaseModel):
    mime: str
    data: str  # base64
    filename: str = ""


class ChatRequest(BaseModel):
    message: str
    provider: Optional[str] = None
    context_strategy: str = "sliding"  # sliding | summary
    model: Optional[str] = None  # 선택 모델 (없으면 config 기본값)
    images: Optional[List[ImagePayload]] = None  # 채팅 첨부 이미지 (첫 장만 Vision 파싱)
    documents: Optional[List[DocumentPayload]] = None  # PDF/DOCX/XLSX (MCP 문서 파서)


async def _build_user_content(
    message: str,
    images: Optional[List[ImagePayload]] = None,
    documents: Optional[List[DocumentPayload]] = None,
) -> str:
    """문서/이미지 MCP 분석 결과와 사용자 메시지를 합쳐 user_content 생성 (일반 채팅용)."""
    parts: list[str] = []

    # RAG 컨텍스트 (ITSM / 기타 VDB) 붙이기
    if message:
        try:
            rag = get_rag_pipeline()
            rag_contexts = rag.get_contexts(message, top_k=5)
            if rag_contexts:
                lines: list[str] = []
                for c in rag_contexts:
                    text = (c.get("text") or "")[:300].replace("\n", " ")
                    meta = c.get("meta") or {}
                    ticket_id = meta.get("ticket_id") or meta.get("id") or c.get("id")
                    lines.append(f"- [티켓 {ticket_id}] {text}")
                rag_block = "[관련 ITSM/RAG 컨텍스트]\n" + "\n".join(lines)
                parts.append(rag_block)
        except Exception as e:  # pragma: no cover - RAG 실패 시 로그만 남기고 무시
            logger.warning("RAG pipeline failed: %s", e)
    if documents and len(documents) > 0:
        for i, doc in enumerate(documents):
            try:
                text = await call_parse_document_via_mcp(
                    file_base64=doc.data,
                    mime_type=doc.mime,
                    filename=doc.filename or "",
                )
                if len(text) > MAX_DOCUMENT_CONTEXT_CHARS:
                    text = text[:MAX_DOCUMENT_CONTEXT_CHARS] + "\n\n...(이하 생략)"
                label = doc.filename or f"문서{i + 1}"
                parts.append(f"[문서 분석 결과 - {label}]\n{text}")
            except Exception as e:
                logger.warning("MCP document parse failed: %s", e)
                parts.append(f"[문서 분석 실패 - {doc.filename or '문서'}: {e}]")
    if images and len(images) > 0:
        img = images[0]
        try:
            vision_text = await call_image_parse_via_mcp(
                image_base64=img.data,
                mime=img.mime,
                user_query=message or "",
            )
            if len(vision_text) > MAX_VISION_CONTEXT_CHARS:
                vision_text = vision_text[:MAX_VISION_CONTEXT_CHARS] + "\n\n...(이하 생략)"
            parts.append(f"[이미지 분석 결과]\n{vision_text}")
        except Exception as e:
            logger.warning("MCP image parse failed for chat image: %s", e)
            parts.append(f"[이미지 분석 실패: {e}]")
    if parts:
        parts.append(f"[사용자 요청]\n{message or '위 내용을 참고해 답변해 주세요.'}")
        return "\n\n".join(parts)
    return message or ""


async def _build_mcp_context(
    message: str,
    images: Optional[List[ImagePayload]] = None,
    documents: Optional[List[DocumentPayload]] = None,
) -> Optional[str]:
    """이미지/문서 MCP 분석 결과만 반환 (Agent 경로 전용 — RAG 제외).

    Agent는 자체 rag_decision/rag_retrieve 노드로 RAG를 처리하므로
    여기서 별도 RAG 호출 없이 MCP 파싱 결과만 parsed_docs로 전달한다.
    """
    parts: list[str] = []

    if documents:
        for i, doc in enumerate(documents):
            try:
                text = await call_parse_document_via_mcp(
                    file_base64=doc.data,
                    mime_type=doc.mime,
                    filename=doc.filename or "",
                )
                if len(text) > MAX_DOCUMENT_CONTEXT_CHARS:
                    text = text[:MAX_DOCUMENT_CONTEXT_CHARS] + "\n\n...(이하 생략)"
                label = doc.filename or f"문서{i + 1}"
                parts.append(f"[문서 분석 결과 - {label}]\n{text}")
            except Exception as e:
                logger.warning("Agent MCP document parse failed: %s", e)
                parts.append(f"[문서 분석 실패 - {doc.filename or '문서'}: {e}]")

    if images:
        img = images[0]
        try:
            vision_text = await call_image_parse_via_mcp(
                image_base64=img.data,
                mime=img.mime,
                user_query=message or "",
            )
            if len(vision_text) > MAX_VISION_CONTEXT_CHARS:
                vision_text = vision_text[:MAX_VISION_CONTEXT_CHARS] + "\n\n...(이하 생략)"
            parts.append(f"[이미지 분석 결과]\n{vision_text}")
        except Exception as e:
            logger.warning("Agent MCP image parse failed: %s", e)
            parts.append(f"[이미지 분석 실패: {e}]")

    return "\n\n".join(parts) if parts else None


JAVA_KEYWORDS = [
    "메서드", "클래스", "호출", "의존", "리팩토링", "리팩터",
    "코드", "소스", "call chain", "영향 분석", "impact",
    "중복", "복잡도", "테스트 생성", "단위 테스트", "junit",
    "java", "서비스", "컨트롤러", "레포지토리",
]

JAVA_HIGH_CONFIDENCE_KEYWORDS = [
    "call chain", "호출 체인", "영향 범위", "의존 관계",
    "리팩토링 제안", "테스트 코드 생성", "코드 분석",
]


def _should_route_to_java_graph(query: str) -> bool:
    q = (query or "").lower()
    if not q.strip():
        return False
    if any(kw.lower() in q for kw in JAVA_HIGH_CONFIDENCE_KEYWORDS):
        return True
    return sum(1 for kw in JAVA_KEYWORDS if kw.lower() in q) >= 2


def _should_route_to_agent(query: str) -> bool:
    """ITSM 관련 문의만 Agent/HITL 경로로 보낸다.

    일반 잡담/일반지식 질문은 기존 chat_stream 경로로 처리해
    ITSM 고정 프롬프트가 잘못 적용되는 것을 방지한다.
    """
    if _should_route_to_java_graph(query):
        return False

    q = (query or "").lower()
    if not q.strip():
        return False

    # high-confidence 시그널 우선
    if any(kw.lower() in q for kw in HIGH_CONFIDENCE_KEYWORDS):
        return True

    # 일반 ITSM 키워드 1개 이상이면 agent 경로
    return any(kw.lower() in q for kw in ITSM_KEYWORDS)


# ---------------------------------------------------------------------------
# SSE streaming chat
# ---------------------------------------------------------------------------

@router.post("/{session_id}/stream")
async def chat_stream_endpoint(
    session_id: str,
    body: ChatRequest,
    request: Request,
    _rate: None = Depends(chat_rate_limit),
):
    # 스트리밍 구간에서는 get_db(긴 트랜잭션)를 쓰지 않음 — SQLite locked 방지
    async with AsyncSessionLocal() as db:
        await repo.get_session(db, session_id)
        await db.commit()
    image_count = len(body.images) if body.images else 0
    doc_count = len(body.documents) if body.documents else 0
    logger.info(
        "Chat stream: session_id=%s, has_images=%s, has_documents=%s, message_len=%s",
        session_id,
        image_count,
        doc_count,
        len(body.message or ""),
    )

    async def java_graph_event_generator():
        yield f"data: {json.dumps({'type': 'start'})}\n\n"

        async with AsyncSessionLocal() as sdb:
            await repo.save_message(
                sdb, session_id=session_id, role="user", content=body.message
            )
            await sdb.commit()

        try:
            from src.java_ast_graphrag.graphrag.query_analyzer import analyze_query
            from src.java_ast_graphrag.pipeline import run_java_graphrag

            analysis = await analyze_query(body.message or "")

            INTENT_TO_TOOL = {
                "METHOD_EXPLAIN": "code_explain",
                "CALL_CHAIN": "graph_search",
                "IMPACT_ANALYSIS": "impact_assess",
                "DEPENDENCY_MAP": "graph_search",
                "CODE_SMELL": "refactor_suggest",
                "REFACTOR_GUIDE": "refactor_suggest",
            }
            tool = INTENT_TO_TOOL.get(analysis.intent, "code_explain")

            result = await run_java_graphrag(body.message or "", tool=tool)
            response_text = result.get("result") or result.get("assembled_context") or ""

            if response_text:
                async with AsyncSessionLocal() as sdb:
                    await repo.save_message(
                        sdb, session_id=session_id, role="assistant", content=response_text
                    )
                    await sdb.commit()
                yield f"data: {json.dumps({'type': 'text', 'content': response_text}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'end', 'usage': {}})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Java GraphRAG produced no output.'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error("Java GraphRAG error: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    # Java GraphRAG 분기 (ITSM보다 먼저 체크)
    if _should_route_to_java_graph(body.message or ""):
        return StreamingResponse(
            java_graph_event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # 일반 질문은 Agent(HITL) 경로를 타지 않도록 분기
    if not _should_route_to_agent(body.message or ""):
        user_content = await _build_user_content(
            body.message or "",
            images=body.images,
            documents=body.documents,
        )
        return StreamingResponse(
            chat_stream(
                session_id=session_id,
                user_content=user_content,
                provider_name=body.provider,
                context_strategy=body.context_strategy,
                model=body.model,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Agent 경로 전용: MCP 컨텍스트(이미지/문서)만 별도 구성 (RAG는 agent 내부에서 처리)
    parsed_docs = await _build_mcp_context(
        body.message or "",
        images=body.images,
        documents=body.documents,
    )

    async def agent_event_generator():
        yield f"data: {json.dumps({'type': 'start'})}\n\n"
        yield f"data: {json.dumps({'type': 'session_info', 'chatui_session_id': session_id, 'thread_id': session_id})}\n\n"

        # 사용자 메시지 저장
        async with AsyncSessionLocal() as sdb:
            await repo.save_message(sdb, session_id=session_id, role="user", content=body.message)
            await sdb.commit()

        try:
            result = await run_agent(
                user_query=body.message or "",
                parsed_docs=parsed_docs,
                thread_id=session_id,
            )
        except Exception as e:
            logger.error("Agent run error: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            return

        if result["status"] == "interrupted":
            draft = result.get("draft_response", "")
            yield f"data: {json.dumps({'type': 'hitl_request', 'thread_id': result['thread_id'], 'draft_response': draft, 'actions': ['approve', 'reject', 'edit'], 'interrupt_id': result['thread_id']}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'end', 'usage': {}})}\n\n"
            return

        final_response = (result.get("final_response") or "").strip()
        if final_response:
            async with AsyncSessionLocal() as sdb:
                await repo.save_message(sdb, session_id=session_id, role="assistant", content=final_response)
                await sdb.commit()
            yield f"data: {json.dumps({'type': 'text', 'content': final_response}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'end', 'usage': {}})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'error', 'message': 'Agent produced no final output.'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        agent_event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Non-streaming chat (convenience)
# ---------------------------------------------------------------------------

@router.post("/{session_id}")
async def chat_complete(
    session_id: str,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _rate: None = Depends(chat_rate_limit),
):
    session = await repo.get_session(db, session_id)
    provider = get_provider(body.provider or session.provider)

    user_content = await _build_user_content(
        body.message or "",
        images=body.images,
        documents=body.documents,
    )

    db_history = await repo.get_recent_messages_for_context(db, session_id)

    from src.core.llm.context_manager import fit_context
    from src.tools import registry as tool_registry

    messages = [
        ChatMessage(role=m.role, content=m.content or "", tool_calls=m.tool_calls or [])
        for m in db_history
    ]
    messages.append(ChatMessage(role="user", content=user_content))
    messages = await fit_context(messages, provider)

    active_tools = tool_registry.list_tools(active_only=True)
    tool_schemas = [t.to_openai() for t in active_tools]

    resp = await provider.generate(
        messages,
        system_prompt=session.system_prompt,
        tools=tool_schemas or None,
        model=body.model,
    )

    # Persist messages
    await repo.save_message(db, session_id=session_id, role="user", content=user_content)
    await repo.save_message(
        db,
        session_id=session_id,
        role="assistant",
        content=resp.content,
        tool_calls=resp.tool_calls or None,
    )

    return ok({
        "content": resp.content,
        "tool_calls": resp.tool_calls,
        "usage": {
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
        },
        "model": resp.model,
    })


# ---------------------------------------------------------------------------
# HITL resume endpoint
# ---------------------------------------------------------------------------

class HITLResumeRequest(BaseModel):
    thread_id: str
    action: Literal["approve", "reject", "edit"]
    edited: Optional[str] = None


@router.post("/hitl/resume")
async def hitl_resume_endpoint(body: HITLResumeRequest):
    """HITL 검토 결과를 받아 LangGraph 그래프를 재개하고 최종 응답을 SSE로 반환."""

    async def sse_gen():
        yield f"data: {json.dumps({'type': 'start'})}\n\n"
        try:
            result = await resume_agent(
                thread_id=body.thread_id,
                action=body.action,
                edited=body.edited,
            )
        except Exception as e:
            logger.error("HITL resume error: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            return

        if result["status"] == "interrupted":
            # reject 후 재시도 등으로 다시 interrupt된 경우
            draft = result.get("draft_response", "")
            yield f"data: {json.dumps({'type': 'hitl_request', 'thread_id': result['thread_id'], 'draft_response': draft, 'actions': ['approve', 'reject', 'edit'], 'interrupt_id': result['thread_id'], 'reject_count': result.get('reject_count', 0)}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'end', 'usage': {}})}\n\n"
            return

        final_response = (result.get("final_response") or "").strip()
        if final_response:
            # thread_id == session_id 이므로 그대로 사용
            async with AsyncSessionLocal() as sdb:
                await repo.save_message(
                    sdb, session_id=body.thread_id, role="assistant", content=final_response
                )
                await sdb.commit()
            yield f"data: {json.dumps({'type': 'text', 'content': final_response}, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({'type': 'end', 'usage': {}})}\n\n"

    return StreamingResponse(
        sse_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
