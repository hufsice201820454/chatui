from config import settings
from src.core.llm.embedding_class import OpenAIEmbedding


class Embedder(OpenAIEmbedding):
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
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            base_model=model_name or "text-embedding-3-small",
            tiktoken_enabled=True,
        )

