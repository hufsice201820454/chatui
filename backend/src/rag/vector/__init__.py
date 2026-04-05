"""
Vector-store & embedding utilities for RAG.

- sqlite_loader: SQLite에서 문서 로딩 + 컬럼 결합
- bge_embedder: BGE-M3 임베딩 래퍼
- chroma_store: ChromaDB 래퍼
- ingest_pipeline: SQLite -> chunks -> embeddings -> Chroma ingest 파이프라인
"""

