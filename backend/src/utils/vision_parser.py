"""
이미지 Vision 파서 (Product Code 이미지 → 텍스트/속성 테이블).
config의 VISION_MODEL(VISION_BASE_URL, API_KEY) 사용.
"""
import base64
import logging
from typing import Optional

from src.core.llm import vision_client

logger = logging.getLogger("chatui.files.vision_parser")

# Product Code 이미지 분석 시 출력 형태 고정용 시스템 프롬프트
PRODUCT_CODE_SYSTEM_PROMPT = """You are an expert at extracting product code information from images.
Given an image (e.g. product label, barcode, or specification sheet), extract all visible text and attributes.
If the user provides a specific question or focus, consider it.
Output your response as a single markdown table with clear column headers (e.g. 항목 | 값 or Attribute | Value).
Do not add extra commentary before or after the table. If multiple logical groups exist, use one table with appropriate columns or separate sections with table headers."""


async def parse_image_with_vision(
    data: bytes,
    mime: str,
    user_query: str = "",
    system_prompt: Optional[str] = None,
) -> str:
    """
    이미지 바이트 + 선택적 쿼리로 Vision API 호출 후, 테이블 형태 텍스트 반환.
    내부망: config VISION_BASE_URL, API_KEY, VISION_MODEL 사용.
    """
    image_b64 = base64.standard_b64encode(data).decode("ascii")
    prompt = user_query.strip() or "이 이미지에서 제품 코드 및 속성 정보를 추출해 마크다운 테이블로 정리해 주세요."
    sys_prompt = system_prompt or PRODUCT_CODE_SYSTEM_PROMPT

    return await vision_client.analyze_image(
        image_b64=image_b64,
        mime=mime,
        text_prompt=prompt,
        system_prompt=sys_prompt,
    )
