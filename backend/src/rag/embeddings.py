from typing import List

import openai

from config import settings


class Embedder:
    """
    간단한 OpenAI 기반 임베딩 생성기.

    - settings.OPENAI_API_KEY / OPEN_API_KEY 를 사용
    - 모델명은 환경에 맞게 변경 가능
    """

    def __init__(self, model_name: str | None = None):
        api_key = getattr(settings, "OPENAI_API_KEY", None) or getattr(
            settings, "OPEN_API_KEY", None
        )
        base_url = getattr(settings, "OPEN_BASE_URL", None)
        if not api_key:
            raise ValueError("OPENAI_API_KEY or OPEN_API_KEY is not set in .env")
        # sync client – 임베딩은 짧아서 sync 로 충분
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)
        # 기본 임베딩 모델 (환경에 맞게 조정)
        self._model = model_name or "text-embedding-3-small"

    def embed_query(self, query: str) -> List[float]:
        """
        단일 질의문 임베딩.
        """
        resp = self._client.embeddings.create(model=self._model, input=query)
        return resp.data[0].embedding  # type: ignore[no-any-return]

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        여러 텍스트 임베딩.
        """
        if not texts:
            return []
        resp = self._client.embeddings.create(model=self._model, input=texts)
        return [d.embedding for d in resp.data]  # type: ignore[no-any-return]

