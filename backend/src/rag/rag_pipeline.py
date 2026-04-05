import logging
import os
import json
from collections import OrderedDict
from operator import itemgetter
from typing import Any, List

import openai

logger = logging.getLogger(__name__)

from config import BACKEND_ROOT, resolve_backend_path, settings
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

def _resolve_vdb_path() -> str:
    """Chroma persist 디렉터리 — BACKEND_ROOT 기준 절대경로 (cwd와 무관)."""
    override = getattr(settings, "RAG_CHROMA_PERSIST_DIR", None)
    if override and str(override).strip():
        resolved = resolve_backend_path(str(override).strip())
        if resolved:
            return resolved
    return str(BACKEND_ROOT / "chroma")


# VDB 경로 (Chroma persist dir)
VDB_PATH = _resolve_vdb_path()

# 기본 컬렉션명 — Settings 필드로 .env RAG_COLLECTION_NAME 로드됨
COLLECTION_NAME = getattr(settings, "RAG_COLLECTION_NAME", None) or "itsm_openai_bge_m3_1024"

# OpenAI 설정 (Embedding / LLM / Reranker 공통)
API_KEY = (
    getattr(settings, "OPENAI_API_KEY", None)
    or getattr(settings, "OPEN_API_KEY", None)
    or getattr(settings, "API_KEY", None)
)
BASE_URL = (
    getattr(settings, "OPENAI_BASE_URL", None)
    or getattr(settings, "OPEN_BASE_URL", None)
    or getattr(settings, "BASE_URL", None)
)

# Embedding 설정 (Settings 에 OPENAI_EMBEDDING_* 정의 시 .env 반영)
EMBEDDING_MODEL = (
    getattr(settings, "OPENAI_EMBEDDING_MODEL", None)
    or getattr(settings, "EMBEDDING_MODEL_NAME", None)
    or "bge-m3"
)
EMBEDDING_BASE_URL = (
    getattr(settings, "OPENAI_EMBEDDING_BASE_URL", None)
    or getattr(settings, "EMBEDDING_BASE_URL", None)
    or BASE_URL
)

# Chat 모델 설정
MODEL_NAME = getattr(settings, "OPENAI_MODEL", None) or "gpt-4o-mini"


def _build_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        api_key=API_KEY,
        model=EMBEDDING_MODEL,
        base_url=EMBEDDING_BASE_URL,
        # 내부망 환경에서 tiktoken 인코딩 파일 다운로드(openaipublic.blob...)가 막힐 수 있어 비활성화
        tiktoken_enabled=False,
        # 내부망에서 transformers AutoTokenizer(HF) 다운로드도 막힐 수 있어 길이 체크/토크나이즈 경로 비활성화
        check_embedding_ctx_length=False,
    )


def _build_chat() -> ChatOpenAI:
    return ChatOpenAI(
        api_key=API_KEY,
        model=MODEL_NAME,
        base_url=BASE_URL,
        temperature=0,
    )


def _load_vdb(embeddings: OpenAIEmbeddings) -> Chroma:
    """
    SEMANTIC_SEARCH (필수)
    - Chroma VDB를 외부 문서로 사용하는 시맨틱 검색
    """
    return Chroma(
        persist_directory=VDB_PATH,
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
    )


def _load_all_documents_from_vdb(vdb: Chroma, limit: int = 5000) -> List[Document]:
    """
    BM25 인덱싱을 위해 VDB에 저장된 문서(청크)를 모두 가져온다.
    (다른 파일/DB를 읽지 않고 rag_pipeline.py 내에서 해결)
    """
    # Chroma get(include=...)에서 include 항목은 documents/metadatas/... 만 허용 (ids는 include가 아님).
    # 또한 대량 get()은 SQLite 변수 제한(too many SQL variables)로 실패할 수 있어 페이지네이션으로 가져온다.
    out: List[Document] = []
    batch_size = min(1000, max(1, int(limit)))
    offset = 0

    while len(out) < limit:
        try:
            data = vdb.get(  # type: ignore[call-arg]
                include=["documents", "metadatas"],
                limit=min(batch_size, limit - len(out)),
                offset=offset,
            )
        except TypeError:
            # 일부 버전에선 offset 미지원일 수 있어, 그 경우엔 안전하게 1회만 제한 호출한다.
            data = vdb.get(  # type: ignore[call-arg]
                include=["documents", "metadatas"],
                limit=min(batch_size, limit - len(out)),
            )

        ids = data.get("ids") or []
        docs = data.get("documents") or []
        metas = data.get("metadatas") or [{} for _ in docs]

        if not docs:
            break

        for _id, text, meta in zip(ids, docs, metas):
            md = dict(meta or {})
            md["vdb_id"] = _id
            out.append(Document(page_content=text or "", metadata=md))
            if len(out) >= limit:
                break

        offset += len(docs)
        if len(docs) < batch_size:
            break

    return out


def _build_bm25(docs: List[Document], k: int) -> BM25Retriever:
    """
    BM25 (필수) - langchain BM25Retriever 사용
    """
    bm25 = BM25Retriever.from_documents(docs)
    bm25.k = k
    return bm25


def _merge_ranked(query: str, dense_docs: List[Document], bm25_docs: List[Document], *, k: int) -> List[Document]:
    """
    SEMANTIC_SEARCH + BM25 결과를 단순 앙상블(Reciprocal Rank)로 결합.
    (EnsembleRetriever 대체 - 이 파일 안에서만 해결)
    """
    scores: "OrderedDict[str, float]" = OrderedDict()
    by_key: dict[str, Document] = {}

    def key_of(d: Document) -> str:
        return str(d.metadata.get("vdb_id") or (d.page_content[:2000]))

    for rank, d in enumerate(dense_docs, 1):
        key = key_of(d)
        by_key[key] = d
        scores[key] = scores.get(key, 0.0) + (1.0 / rank) * 0.5

    for rank, d in enumerate(bm25_docs, 1):
        key = key_of(d)
        by_key.setdefault(key, d)
        scores[key] = scores.get(key, 0.0) + (1.0 / rank) * 0.5

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [by_key[k] for k, _ in ranked[:k]]


def _rerank_llm(chat: ChatOpenAI, query: str, docs: List[Document], *, top_k: int) -> List[Document]:
    """
    Reranker (필수)
    - OpenAI처럼 api_key/base_url/model은 ChatOpenAI 생성 시 사용됨 (settings 기반)
    - 후보 문서들을 query 기준으로 순서 재정렬
    """
    if not docs:
        return []
    top_k = max(1, min(top_k, len(docs)))

    blocks = []
    for i, d in enumerate(docs, 1):
        blocks.append(f"[{i}] {(d.page_content or '')[:400].replace('\\n',' ')}")

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "Return JSON only. Format: {{\"order\": [1,2,3]}}"),
            ("user", "Query:\n{query}\n\nCandidates:\n{candidates}\n\nReturn top {top_k}."),
        ]
    )
    chain = prompt | chat | StrOutputParser()
    raw = (chain.invoke({"query": query, "candidates": "\n".join(blocks), "top_k": top_k}) or "").strip()

    try:
        data = json.loads(raw)
        order = data.get("order", [])
        if not isinstance(order, list):
            raise ValueError("order must be list")
        out: List[Document] = []
        seen = set()
        for idx in order:
            if not isinstance(idx, int):
                continue
            if idx < 1 or idx > len(docs):
                continue
            if idx in seen:
                continue
            seen.add(idx)
            out.append(docs[idx - 1])
            if len(out) >= top_k:
                break
        if len(out) < top_k:
            for d in docs:
                if d in out:
                    continue
                out.append(d)
                if len(out) >= top_k:
                    break
        return out[:top_k]
    except Exception:
        return docs[:top_k]


def _build_context(docs: List[Document], k: int) -> str:
    blocks: List[str] = []
    for i, d in enumerate(docs[:k], 1):
        blocks.append(f"[#{i}]\n{d.page_content}")
    return "\n\n".join(blocks)


def build_rag_chain(*, vdb: Chroma, bm25: BM25Retriever, chat: ChatOpenAI, top_k: int) -> Any:
    """
    LangChain RAG 체인:
      {"question": itemgetter("question"), "context": retrieve_ctx} | prompt | llm | StrOutputParser()

    사용 요소는 반드시 3가지:
    - SEMANTIC_SEARCH (Chroma)
    - BM25 (BM25Retriever)
    - Reranker (LLM rerank)
    """

    def retrieve_docs(q: str) -> List[Document]:
        dense = vdb.as_retriever(search_kwargs={"k": top_k}).invoke(q)
        sparse = bm25.invoke(q)
        merged = _merge_ranked(q, dense, sparse, k=max(top_k, 10))
        reranked = _rerank_llm(chat, q, merged, top_k=top_k)
        return reranked

    retrieve_ctx = itemgetter("question") | RunnableLambda(lambda q: _build_context(retrieve_docs(q), top_k))

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "당신은 도움이 되는 어시스턴트입니다. 반드시 주어진 [context]만 근거로 답변하세요. "
                "답변은 **한국어로만** 작성하세요. 근거가 부족하면 추측하지 말고 부족하다고 말하세요.",
            ),
            ("user", "[question]\n{question}\n\n[context]\n{context}\n\n[답변 규칙]\n- 한국어로만 답변\n- context에 없는 내용은 추측 금지"),
        ]
    )

    chain = {"question": itemgetter("question"), "context": retrieve_ctx} | prompt | chat | StrOutputParser()
    return chain


# ---------------------------------------------------------------------------
# Agent용 헬퍼 (get_rag_chain, get_rag_contexts)
# ---------------------------------------------------------------------------

_RAG_CACHE: dict[str, Any] = {}


def clear_rag_cache() -> None:
    """VDB 경로/컬렉션 변경 후 또는 재인덱싱 후 호출."""
    _RAG_CACHE.clear()


def get_rag_storage_info() -> dict[str, Any]:
    """Agent/디버그용: 실제 사용 중인 Chroma 경로·컬렉션·임베딩 모델."""
    return {
        "vdb_path": VDB_PATH,
        "collection_name": COLLECTION_NAME,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_base_url_set": bool(EMBEDDING_BASE_URL),
    }


def _get_rag_components() -> tuple[Any, Any, Any, Any]:
    """(chain, vdb, bm25, chat) 싱글톤 반환."""
    if "chain" in _RAG_CACHE:
        return _RAG_CACHE["chain"], _RAG_CACHE["vdb"], _RAG_CACHE["bm25"], _RAG_CACHE["chat"]
    logger.info(
        "RAG 초기화: persist=%s collection=%s embed_model=%s",
        VDB_PATH,
        COLLECTION_NAME,
        EMBEDDING_MODEL,
    )
    embeddings = _build_embeddings()
    chat = _build_chat()
    vdb = _load_vdb(embeddings)
    all_docs = _load_all_documents_from_vdb(vdb, limit=5000)
    bm25 = _build_bm25(all_docs, k=10)
    top_k = 5
    chain = build_rag_chain(vdb=vdb, bm25=bm25, chat=chat, top_k=top_k)
    _RAG_CACHE["chain"] = chain
    _RAG_CACHE["vdb"] = vdb
    _RAG_CACHE["bm25"] = bm25
    _RAG_CACHE["chat"] = chat
    return chain, vdb, bm25, chat


def get_rag_chain() -> Any:
    """RAG 체인 반환 (agent용)."""
    chain, _, _, _ = _get_rag_components()
    return chain


def get_rag_contexts(query: str, top_k: int = 5) -> List[dict]:
    """RAG 컨텍스트만 반환 (agent용: rag_decision, rag_retrieve)."""
    try:
        _, vdb, bm25, chat = _get_rag_components()
        dense = vdb.as_retriever(search_kwargs={"k": top_k}).invoke(query)
        sparse = bm25.invoke(query)
        merged = _merge_ranked(query, dense, sparse, k=max(top_k, 10))
        reranked = _rerank_llm(chat, query, merged, top_k=top_k)
        return [
            {
                "id": d.metadata.get("vdb_id"),
                "text": d.page_content or "",
                "meta": dict(d.metadata or {}),
            }
            for d in reranked
        ]
    except Exception:
        return []


def main() -> None:
    # Windows 콘솔에서 한글 출력 깨짐 방지 (가능한 경우에만 적용)
    try:
        import sys

        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    # 쿼리 입력: argv가 있으면 그걸 쓰고, 없으면 기본값
    query = " ".join(os.sys.argv[1:]).strip() or "Access Request"

    if not API_KEY:
        raise ValueError("OPENAI_API_KEY/OPEN_API_KEY 가 필요합니다 (.env/settings 확인).")

    embeddings = _build_embeddings()
    chat = _build_chat()

    vdb = _load_vdb(embeddings)
    all_docs = _load_all_documents_from_vdb(vdb, limit=5000)
    bm25 = _build_bm25(all_docs, k=10)

    top_k = 5
    chain = build_rag_chain(vdb=vdb, bm25=bm25, chat=chat, top_k=top_k)

    # 항상 컨텍스트 + 답변 출력
    dense_preview = vdb.as_retriever(search_kwargs={"k": top_k}).invoke(query)
    sparse_preview = bm25.invoke(query)
    merged_preview = _merge_ranked(query, dense_preview, sparse_preview, k=max(top_k, 10))
    reranked_preview = _rerank_llm(chat, query, merged_preview, top_k=top_k)

    print("\n[context]")
    for i, d in enumerate(reranked_preview, 1):
        print(f"[#{i}] {(d.page_content or '')[:500].replace('\\n',' ')}")

    answer = chain.invoke({"question": query})
    print("\n[answer]", query)
    print(answer)


if __name__ == "__main__":
    main()
