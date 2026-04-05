"""
RAG (Retrieval-Augmented Generation) package.

구성:
- config: RAG 설정 (top-k, 가중치 등)
- embeddings: query/문서 임베딩 생성기
- bm25_index: BM25 기반 텍스트 검색 인덱스
- semantic_index: 벡터 DB 기반 시맨틱 검색 래퍼
- hybrid_retriever: BM25 + semantic 결과 병합
- reranker: 후보 컨텍스트 재정렬
- pipeline: end-to-end RAG 파이프라인
"""

