"""
이미지 분석 유틸 — GPT-4o Vision API
"""
import base64
import logging
from functools import lru_cache
from typing import Optional

from openai import OpenAI

from config import OPENAI_API_KEY, VISION_MODEL, VISION_MAX_TOKENS, VISION_PROMPT

logger = logging.getLogger("pipeline.util.image")


@lru_cache(maxsize=1)
def _get_vision_client() -> OpenAI:
    return OpenAI(api_key=OPENAI_API_KEY)


def analyze_image(
    image_data: bytes,
    mime_type: str = "image/png",
    prompt: Optional[str] = None,
) -> str:
    """이미지 bytes를 GPT-4o로 분석하여 텍스트 설명 반환.

    Args:
        image_data: 이미지 raw bytes
        mime_type: MIME 타입 (image/png, image/jpeg 등)
        prompt: 분석 프롬프트 (없으면 기본값 사용)

    Returns:
        분석 결과 텍스트
    """
    client = _get_vision_client()
    b64 = base64.b64encode(image_data).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"
    user_prompt = prompt or VISION_PROMPT

    try:
        response = client.chat.completions.create(
            model=VISION_MODEL,
            max_tokens=VISION_MAX_TOKENS,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        )
        result = response.choices[0].message.content or ""
        logger.debug("Vision analysis complete (%d chars)", len(result))
        return result
    except Exception as e:
        logger.error("Vision API error: %s", e)
        return f"[이미지 분석 실패: {e}]"
