from __future__ import annotations

from typing import Dict, List

from .bm25_index import Bm25Index
from .config import config
from .embeddings import Embedder
from .semantic_index import SemanticIndex


class HybridRetriever:
    """
    BM25 + 시맨틱 검색 결과를 결합하는 하이브리드 리트리버.
    """

    def __init__(self, bm25: Bm25Index, semantic: SemanticIndex, embedder: Embedder):
        self._bm25 = bm25
        self._semantic = semantic
        self._embedder = embedder

    def retrieve(self, query: str, top_k: int | None = None) -> List[Dict]:
        """
        동기 방식으로 query 에 대한 하이브리드 검색을 수행.
        (임베딩 호출이 sync 이므로 전체를 sync 로 구성)
        """
        top_k = top_k or config.top_k_final

        # 1) 임베딩 생성
        q_emb = self._embedder.embed_query(query)

        # 2) 개별 검색
        bm25_docs = self._bm25.search(query, config.top_k_bm25)
        sem_docs = self._semantic.search(q_emb, config.top_k_semantic)

        # 3) id 기준으로 스코어 병합
        merged = self._merge_and_score(bm25_docs, sem_docs)

        # 4) 상위 top_k 반환
        return merged[:top_k]

    def _merge_and_score(self, bm25_docs: List[Dict], sem_docs: List[Dict]) -> List[Dict]:
        """
        간단한 정규화 + 가중합 스코어링.
        문서는 "id" 키를 기준으로 동일 문서로 간주한다.
        """
        docs: Dict[str, Dict] = {}

        # BM25 스코어 정규화
        if bm25_docs:
            max_bm25 = max(d.get("score", 0.0) for d in bm25_docs) or 1.0
        else:
            max_bm25 = 1.0

        for d in bm25_docs:
            doc_id = str(d.get("id"))
            norm = (d.get("score", 0.0) / max_bm25) if max_bm25 else 0.0
            base = dict(d)
            base["bm25_score"] = norm
            base.setdefault("semantic_score", 0.0)
            docs[doc_id] = base

        # Semantic 스코어 정규화
        if sem_docs:
            max_sem = max(d.get("score", 0.0) for d in sem_docs) or 1.0
        else:
            max_sem = 1.0

        for d in sem_docs:
            doc_id = str(d.get("id"))
            norm = (d.get("score", 0.0) / max_sem) if max_sem else 0.0
            if doc_id in docs:
                docs[doc_id]["semantic_score"] = norm
            else:
                base = dict(d)
                base.setdefault("bm25_score", 0.0)
                base["semantic_score"] = norm
                docs[doc_id] = base

        # 최종 스코어 계산
        out: List[Dict] = []
        for doc in docs.values():
            bm25_s = float(doc.get("bm25_score", 0.0))
            sem_s = float(doc.get("semantic_score", 0.0))
            final_score = bm25_s * config.bm25_weight + sem_s * config.semantic_weight
            doc["score"] = final_score
            out.append(doc)

        out.sort(key=lambda d: d.get("score", 0.0), reverse=True)
        return out

