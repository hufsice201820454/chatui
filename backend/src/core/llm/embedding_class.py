from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import openai

class EmbeddingClass(ABC):
    """
    공용 임베딩 인터페이스.

    프로젝트 내 임베더 구현체는 이 클래스를 상속해
    단일/배치 임베딩 메서드를 동일한 시그니처로 제공한다.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        base_model: str | None = None,
        tiktoken_enabled: bool | None = None,
    ) -> None:
        # 구현체 공통 설정값(필요한 경우에만 사용)
        self.api_key = api_key
        self.base_url = base_url
        self.base_model = base_model
        self.tiktoken_enabled = tiktoken_enabled

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """단일 질의 임베딩."""
        raise NotImplementedError

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """배치 텍스트 임베딩."""
        raise NotImplementedError

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        LangChain 관례 메서드명 호환용 alias.
        """
        return self.embed_texts(texts)


class OpenAIEmbedding(EmbeddingClass):
    """
    OpenAI 호환 임베딩 공용 구현체.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str | None = None,
        base_model: str = "text-embedding-3-small",
        tiktoken_enabled: bool | None = True,
        client_kwargs: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            base_model=base_model,
            tiktoken_enabled=tiktoken_enabled,
        )
        kwargs = client_kwargs or {}
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url, **kwargs)

    def embed_query(self, query: str) -> list[float]:
        resp = self._client.embeddings.create(model=self.base_model, input=query)
        return resp.data[0].embedding  # type: ignore[no-any-return]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self._client.embeddings.create(model=self.base_model, input=texts)
        return [d.embedding for d in resp.data]  # type: ignore[no-any-return]
