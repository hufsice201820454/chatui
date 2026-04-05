from pydantic import BaseModel


class RagConfig(BaseModel):
    """
    RAG 파이프라인 공통 설정.
    필요 시 .env / Settings 와 연동해도 된다.
    """

    # 개별 검색 단계 top-k
    top_k_bm25: int = 30
    top_k_semantic: int = 30

    # 최종 반환 개수
    top_k_final: int = 10

    # hybrid 가중치
    bm25_weight: float = 0.4
    semantic_weight: float = 0.6

    # reranker 에 넘길 후보 개수
    rerank_top_k: int = 20

    # 필터링 스코어 기준선 (필요 시 사용)
    min_score_threshold: float = 0.0


config = RagConfig()

