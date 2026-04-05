"""
Vision API 전용 클라이언트 (내부망 VISION_BASE_URL + VISION_MODEL 사용).
이미지 분석(Product Code 추출 등) 시 config의 vision 설정만 사용.
"""
import base64
import logging
from typing import Optional

import openai

from config import settings

logger = logging.getLogger("chatui.llm.vision")


def _get_vision_client() -> openai.AsyncOpenAI:
    """우선 내부망 Vision 설정 사용, 없으면 OpenAI 설정으로 fallback."""
    base_url = settings.VISION_BASE_URL or settings.VISION_BASE_DEV_URL
    api_key = settings.API_KEY
    if api_key and base_url:
        return openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

    # 외부망/테스트 환경 fallback
    openai_key = settings.OPENAI_API_KEY or settings.OPEN_API_KEY
    openai_base = settings.OPEN_BASE_URL
    if not openai_key:
        raise ValueError(
            "Vision settings missing. Set internal(API_KEY + VISION_BASE_URL) "
            "or external(OPENAI_API_KEY/OPEN_API_KEY)."
        )
    logger.warning("Using OpenAI fallback for vision client")
    if openai_base:
        return openai.AsyncOpenAI(api_key=openai_key, base_url=openai_base)
    return openai.AsyncOpenAI(api_key=openai_key)


async def analyze_image(
    image_b64: str,
    mime: str,
    text_prompt: str,
    system_prompt: Optional[str] = None,
) -> str:
    """
    이미지 + 텍스트 프롬프트로 Vision API 호출 후 응답 텍스트 반환.
    config의 VISION_MODEL, VISION_BASE_URL, API_KEY 사용.
    """
    client = _get_vision_client()
    model = settings.VISION_MODEL

    url = f"data:{mime};base64,{image_b64}"
    content = [
        {"type": "text", "text": text_prompt},
        {"type": "image_url", "image_url": {"url": url}},
    ]

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": content})

    resp = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=settings.OPENAI_MAX_TOKENS,
    )
    text = (resp.choices[0].message.content or "").strip()
    logger.info("Vision analysis completed, model=%s", model)
    return text
