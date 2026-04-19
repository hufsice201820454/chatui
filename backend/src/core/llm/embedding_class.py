from __future__ import annotations

import time
from abc import ABC, abstractmethod

import requests
from langchain_openai import OpenAIEmbeddings

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


class OpenAIEmbedding(OpenAIEmbeddings, EmbeddingClass):
    """
    OpenAI 호환 임베딩 공용 구현체.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        base_model: str = "bge-m3",
        tiktoken_enabled: bool | None = False,
        dimensions: int | None = 1024,
        max_retries: int = 3,
    ) -> None:
        OpenAIEmbeddings.__init__(
            self,
            model=base_model,
            api_key=api_key,
            base_url=base_url,
            dimensions=dimensions,
            tiktoken_enabled=tiktoken_enabled,
            check_embedding_ctx_length=False,
        )
        EmbeddingClass.__init__(
            self,
            api_key=api_key,
            base_url=base_url,
            base_model=base_model,
            tiktoken_enabled=tiktoken_enabled,
        )
        self.dimensions = dimensions
        self.max_retries = max_retries

    def _embed_impl(self, text: str | list[str]) -> requests.Response:
        sess = requests.Session()
        tg_url = f"{self.base_url.rstrip('/')}/embeddings"
        http_header = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        http_body: dict[str, object] = {
            "model": self.model,
            "input": text,
        }
        if self.dimensions is not None:
            http_body["dimensions"] = self.dimensions
        return sess.post(tg_url, headers=http_header, json=http_body, timeout=60)

    def embed_query(self, query: str) -> list[float]:
        resp = self._embed_impl(query)
        if resp.status_code != 200:
            raise RuntimeError(f"Embedding API error: {resp.status_code} {resp.text}")
        return resp.json()["data"][0]["embedding"]  # type: ignore[no-any-return]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        results: list[list[float]] = []

        for text in texts:
            retry_count = 0
            while retry_count <= self.max_retries:
                try:
                    text_input: str | list[str]
                    if isinstance(text, str):
                        text_input = [text]
                    else:
                        text_input = text

                    resp = self._embed_impl(text_input)
                    if resp.status_code == 429:
                        time.sleep(5)
                        retry_count += 1
                        continue
                    if resp.status_code != 200:
                        raise RuntimeError(f"Embedding API error: {resp.status_code} {resp.text}")

                    data = resp.json()
                    results.append(data["data"][0]["embedding"])
                    break
                except Exception:
                    retry_count += 1
                    if retry_count > self.max_retries:
                        raise
                    time.sleep(3)

        return results
