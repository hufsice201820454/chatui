"""
Airflow Task — 문서 임베딩 (S3 → chunk → embed → ChromaDB)
"""
import logging
import os
import time
import requests
from typing import Dict, List, Optional, Any

from pipeline.core.document_embedder import DocumentEmbedder
from pipeline.core.schema import EmbedRequest, EmbedResult
from pipeline.dbutil import create_exec_his, update_exec_his
from util.s3_client import list_s3_objects, download_s3_object
from config import (
    CHROMA_COLLECTION_DOCUMENT,
    DEDRM_ENDPOINT,
    PDFMAKER_ENDPOINT,
    SUPPORTED_FORMATS,
)

logger = logging.getLogger("pipeline.tasks.document_embedding")


class EmbeddingTask:
    """문서 임베딩 파이프라인 태스크.

    사용 예:
        task = EmbeddingTask(source_type="document")
        task.execute({"action": "add", "doc_id": "D001", "file_path": "docs/report.pdf", "file_name": "report.pdf"})
        task.run()  # S3 전체 배치
    """

    def __init__(self, source_type: str = "document"):
        self._source_type = source_type
        self._collection_name = CHROMA_COLLECTION_DOCUMENT
        self._embedder: Optional[DocumentEmbedder] = None

    # ------------------------------------------------------------------
    # 컬렉션 관리
    # ------------------------------------------------------------------

    def _create_collection(self):
        """임베더 인스턴스 초기화 (lazy)."""
        if self._embedder is None:
            self._embedder = DocumentEmbedder(collection_name=self._collection_name)

    def _set_collection_name(self, collection_name: str):
        self._collection_name = collection_name
        self._embedder = None  # 재초기화 유도

    def _upsert(self, ids: List[str], texts: List[str], metadatas: List[Dict[str, Any]]):
        """직접 upsert (저수준 접근)."""
        self._create_collection()
        self._embedder._store.upsert(ids=ids, texts=texts, metadatas=metadatas)

    # ------------------------------------------------------------------
    # 단건 CRUD
    # ------------------------------------------------------------------

    def add(self, request: Dict[str, str]) -> Dict[str, str]:
        self._create_collection()
        req = self._to_embed_request(request, action="add")
        result = self._embedder.add(req)
        return self._create_response(request, result.status, result.status_comment)

    def update(self, request: Dict[str, str]) -> Dict[str, str]:
        self._create_collection()
        req = self._to_embed_request(request, action="update")
        result = self._embedder.update(req)
        return self._create_response(request, result.status, result.status_comment)

    def delete(self, request: Dict[str, str]) -> Dict[str, str]:
        self._create_collection()
        req = self._to_embed_request(request, action="delete")
        result = self._embedder.delete(req)
        return self._create_response(request, result.status, result.status_comment)

    # ------------------------------------------------------------------
    # 배치 처리
    # ------------------------------------------------------------------

    def add_all(
        self,
        dag_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """S3 파일 목록 전체를 임베딩 (신규 추가)."""
        self._create_collection()
        exec_id = create_exec_his(
            pipeline_nm="DOCUMENT_EMBEDDING_ALL",
            dag_id=dag_id,
            run_id=run_id,
            target_type=self._source_type,
        )
        objects = list_s3_objects()
        valid = [o for o in objects if self._is_supported(o["key"])]
        logger.info("add_all: %d valid S3 objects", len(valid))

        total, success, fail = len(valid), 0, 0
        for obj in valid:
            key = obj["key"]
            file_name = key.rsplit("/", 1)[-1]
            doc_id = os.path.splitext(file_name)[0]
            req = {"doc_id": doc_id, "file_path": key, "file_name": file_name, "source_type": self._source_type}
            resp = self.add(req)
            if resp["status"] == "success":
                success += 1
            else:
                fail += 1
                logger.warning("add_all fail: %s → %s", key, resp["status_comment"])

        result = {"total": total, "success": success, "fail": fail}
        update_exec_his(exec_id=exec_id, status="SUCCESS" if fail == 0 else "PARTIAL",
                        total_cnt=total, success_cnt=success, fail_cnt=fail)
        return result

    def run(
        self,
        dag_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """S3 전체 배치 파이프라인 (add_all과 동일, Airflow callable용)."""
        return self.add_all(dag_id=dag_id, run_id=run_id)

    # ------------------------------------------------------------------
    # 단건 실행 (action 기반 dispatch)
    # ------------------------------------------------------------------

    def execute(self, input: Dict[str, str]) -> Dict[str, str]:
        """action 값에 따라 add/update/delete 분기."""
        action = input.get("action", "add").lower()
        if action == "add":
            return self.add(input)
        elif action == "update":
            return self.update(input)
        elif action == "delete":
            return self.delete(input)
        else:
            return self._create_response(input, "fail", f"Unknown action: {action}")

    # ------------------------------------------------------------------
    # 파일 전처리
    # ------------------------------------------------------------------

    def process_file(self, key: str, data: bytes, file_name: str, file_format: str) -> bytes:
        """DRM 해제 및 PDF 변환 전처리.

        - DRM 보호 파일 → dedrm() 호출
        - 비-PDF 파일 → pdfmaker() 호출 후 반환
        """
        if file_format in ("pdf",):
            # PDF는 DRM 해제만 시도
            try:
                data = self.dedrm(file_name, data)
            except Exception as e:
                logger.warning("dedrm skipped for %s: %s", file_name, e)
        else:
            # 기타 포맷은 PDF 변환
            try:
                data = self.pdfmaker(file_name, data)
            except Exception as e:
                logger.warning("pdfmaker skipped for %s: %s", file_name, e)
        return data

    def dedrm(self, file_name: str, data: bytes, timeout: int = 300) -> bytes:
        """DRM 해제 서비스 호출."""
        resp = requests.post(
            DEDRM_ENDPOINT,
            files={"file": (file_name, data)},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.content

    def pdfmaker(self, file_name: str, data: bytes) -> bytes:
        """파일 → PDF 변환 서비스 호출."""
        resp = requests.post(
            PDFMAKER_ENDPOINT,
            files={"file": (file_name, data)},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.content

    def count_document(self) -> int:
        """ChromaDB 컬렉션 내 벡터 수 반환."""
        self._create_collection()
        return self._embedder.count()

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------

    def _to_embed_request(self, request: Dict[str, str], action: str) -> EmbedRequest:
        return EmbedRequest(
            doc_id=request["doc_id"],
            file_path=request["file_path"],
            file_name=request["file_name"],
            source_type=request.get("source_type", self._source_type),
            action=action,
            metadata={k: v for k, v in request.items()
                       if k not in ("doc_id", "file_path", "file_name", "source_type", "action")},
        )

    def _create_response(
        self, request: Dict[str, str], status: str, status_comment: str = ""
    ) -> Dict[str, str]:
        return {
            "doc_id": request.get("doc_id", ""),
            "file_name": request.get("file_name", ""),
            "status": status,
            "status_comment": status_comment,
        }

    @staticmethod
    def _is_supported(key: str) -> bool:
        ext = key.rsplit(".", 1)[-1].lower() if "." in key else ""
        return ext in SUPPORTED_FORMATS
