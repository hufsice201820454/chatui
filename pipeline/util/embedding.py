"""
OpenAI 임베딩 클라이언트 (재시도 로직 포함)
"""
import logging
import time
from typing import List

from langchain_openai import OpenAIEmbeddings
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import openai

from config import (
    OPENAI_API_KEY,
    EMBEDDING_MODEL,
    EMBEDDING_MAX_RETRIES,
    EMBEDDING_RETRY_MIN_WAIT,
    EMBEDDING_RETRY_MAX_WAIT,
)

logger = logging.getLogger("pipeline.util.embedding")


class Embedding(OpenAIEmbeddings):
    """재시도 및 로깅이 추가된 OpenAI 임베딩 클라이언트."""

    def __init__(self, **kwargs):
        super().__init__(
            openai_api_key=OPENAI_API_KEY,
            model=EMBEDDING_MODEL,
            **kwargs,
        )

    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIError)),
        stop=stop_after_attempt(EMBEDDING_MAX_RETRIES),
        wait=wait_exponential(
            multiplier=1,
            min=EMBEDDING_RETRY_MIN_WAIT,
            max=EMBEDDING_RETRY_MAX_WAIT,
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        logger.debug("Embedding %d document(s)", len(texts))
        return super().embed_documents(texts)

    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIError)),
        stop=stop_after_attempt(EMBEDDING_MAX_RETRIES),
        wait=wait_exponential(
            multiplier=1,
            min=EMBEDDING_RETRY_MIN_WAIT,
            max=EMBEDDING_RETRY_MAX_WAIT,
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def embed_query(self, text: str) -> List[float]:
        return super().embed_query(text)
