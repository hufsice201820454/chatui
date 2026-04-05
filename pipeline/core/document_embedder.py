"""
문서(S3 → chunk → embed → ChromaDB) 임베딩 처리기
"""
import logging
import os
from typing import List, Dict, Any, Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter

from pipeline.core.schema import EmbedRequest, EmbedResult
from util.chroma_store import ChromaStore
from util.s3_client import download_s3_object
from util.markdownify import to_markdown
from util.image import analyze_image
from config import (
    CHROMA_COLLECTION_DOCUMENT,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    EMBEDDING_BATCH_SIZE,
    IMAGE_FORMATS,
)

logger = logging.getLogger("pipeline.core.document_embedder")


class DocumentEmbedder:
    """S3 파일을 다운로드 → 마크다운 변환 → 청킹 → ChromaDB 임베딩."""

    def __init__(self, collection_name: str = CHROMA_COLLECTION_DOCUMENT):
        self._store = ChromaStore(collection_name)
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ".", " ", ""],
        )

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def add(self, request: EmbedRequest) -> EmbedResult:
        """문서를 S3에서 받아 임베딩 추가."""
        try:
            data = download_s3_object(request.file_path)
            text = self._extract_text(data, request.file_name)
            if not text.strip():
                return EmbedResult(
                    doc_id=request.doc_id, status="skip",
                    status_comment="Empty content after extraction",
                )
            chunks = self._chunk(text)
            ids, texts, metas = self._build_upsert_data(request, chunks)
            self._batch_upsert(ids, texts, metas)
            return EmbedResult(doc_id=request.doc_id, status="success", chunk_count=len(chunks))
        except Exception as e:
            logger.error("DocumentEmbedder.add failed doc_id=%s: %s", request.doc_id, e)
            return EmbedResult(doc_id=request.doc_id, status="fail", status_comment=str(e))

    def update(self, request: EmbedRequest) -> EmbedResult:
        """기존 문서 벡터 삭제 후 재임베딩."""
        self._delete_by_doc_id(request.doc_id)
        return self.add(request)

    def delete(self, request: EmbedRequest) -> EmbedResult:
        """문서 벡터 삭제."""
        try:
            self._delete_by_doc_id(request.doc_id)
            return EmbedResult(doc_id=request.doc_id, status="success")
        except Exception as e:
            logger.error("DocumentEmbedder.delete failed doc_id=%s: %s", request.doc_id, e)
            return EmbedResult(doc_id=request.doc_id, status="fail", status_comment=str(e))

    def count(self) -> int:
        return self._store.count()

    # ------------------------------------------------------------------
    # 내부 메서드
    # ------------------------------------------------------------------

    def _extract_text(self, data: bytes, file_name: str) -> str:
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if ext in IMAGE_FORMATS:
            mime = f"image/{ext}" if ext not in ("jpg",) else "image/jpeg"
            return analyze_image(data, mime_type=mime)
        return to_markdown(data, file_name)

    def _chunk(self, text: str) -> List[str]:
        return self._splitter.split_text(text)

    def _build_upsert_data(
        self, request: EmbedRequest, chunks: List[str]
    ):
        ids, texts, metas = [], [], []
        for i, chunk in enumerate(chunks):
            chunk_id = f"{request.doc_id}_chunk_{i}"
            ids.append(chunk_id)
            texts.append(chunk)
            meta = {
                "doc_id": request.doc_id,
                "file_name": request.file_name,
                "file_path": request.file_path,
                "source_type": request.source_type,
                "chunk_index": i,
                **request.metadata,
            }
            metas.append(meta)
        return ids, texts, metas

    def _batch_upsert(self, ids: List[str], texts: List[str], metas: List[Dict]):
        for i in range(0, len(ids), EMBEDDING_BATCH_SIZE):
            self._store.upsert(
                ids=ids[i: i + EMBEDDING_BATCH_SIZE],
                texts=texts[i: i + EMBEDDING_BATCH_SIZE],
                metadatas=metas[i: i + EMBEDDING_BATCH_SIZE],
            )

    def _delete_by_doc_id(self, doc_id: str):
        self._store.delete_by_metadata({"doc_id": doc_id})
