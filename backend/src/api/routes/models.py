"""
GET /models – 프론트에서 선택 가능한 LLM 모델 목록 반환
"""
from fastapi import APIRouter

from config import settings
from src.core.responses import ok

router = APIRouter(prefix="/models", tags=["Models"])


@router.get("")
def list_models():
    """config.AVAILABLE_LLM_MODELS 반환. 비어 있으면 기본 모델만."""
    models = list(settings.AVAILABLE_LLM_MODELS) if settings.AVAILABLE_LLM_MODELS else [settings.OPENAI_MODEL]
    return ok({"models": models})
