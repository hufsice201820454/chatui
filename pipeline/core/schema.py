"""
파이프라인 데이터 스키마 (dataclass / TypedDict)
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class EmbedRequest:
    """단일 임베딩 요청 단위"""
    doc_id: str
    file_path: str          # S3 key 또는 로컬 경로
    file_name: str
    source_type: str        # "document" | "dictionary"
    action: str = "add"     # "add" | "update" | "delete"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbedResult:
    """단일 임베딩 결과"""
    doc_id: str
    status: str             # "success" | "fail" | "skip"
    status_comment: str = ""
    chunk_count: int = 0


@dataclass
class DictionaryEntry:
    """사전 항목 (DIC_MAS + DIC_DET 조인 결과)"""
    dic_id: str
    dic_nm: str
    category: Optional[str]
    det_id: str
    term: str
    definition: Optional[str]
    synonyms: Optional[str]
    source: Optional[str]

    def to_document_text(self) -> str:
        parts = [f"용어: {self.term}"]
        if self.definition:
            parts.append(f"정의: {self.definition}")
        if self.synonyms:
            parts.append(f"동의어: {self.synonyms}")
        if self.category:
            parts.append(f"카테고리: {self.category}")
        if self.source:
            parts.append(f"출처: {self.source}")
        return "\n".join(parts)

    def to_metadata(self) -> Dict[str, Any]:
        return {
            "dic_id": self.dic_id,
            "dic_nm": self.dic_nm,
            "det_id": self.det_id,
            "term": self.term,
            "category": self.category or "",
            "source": self.source or "",
            "source_type": "dictionary",
        }
