from __future__ import annotations

from typing import List

from sentence_transformers import SentenceTransformer
from src.core.llm.embedding_class import EmbeddingClass


class BgeM3Embedder(EmbeddingClass):
    """
    BGE-M3 임베딩 전용 래퍼.

    - 모델: "BAAI/bge-m3"
    - embed_query / embed_texts 만 제공
    """

    def __init__(self, device: str = "cpu"):
        super().__init__(
            api_key=None,
            base_url=None,
            base_model="BAAI/bge-m3",
            tiktoken_enabled=False,
        )
        # lazy load 도 가능하지만, 단순화를 위해 생성 시 로드
        self._model = SentenceTransformer(self.base_model, device=device)

    def embed_query(self, query: str) -> List[float]:
        emb = self._model.encode(query, normalize_embeddings=True)
        return emb.tolist()  # type: ignore[no-any-return]

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        embs = self._model.encode(texts, normalize_embeddings=True)
        return [e.tolist() for e in embs]  # type: ignore[no-any-return]

