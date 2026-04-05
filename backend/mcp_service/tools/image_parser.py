import base64
from typing import Optional

from mcp.server.fastmcp import FastMCP

from src.core.llm.vision_client import analyze_image


PRODUCT_CODE_SYSTEM_PROMPT = """You are an expert at extracting product code information from images.
Given an image (e.g. product label, barcode, or specification sheet), extract all visible text and attributes.
If the user provides a specific question or focus, consider it.
Output your response as a single markdown table with clear column headers (e.g. 항목 | 값 or Attribute | Value).
Do not add extra commentary before or after the table. If multiple logical groups exist, use one table with appropriate columns or separate sections with table headers."""


async def _parse_image_with_vision(
    data: bytes,
    mime: str,
    user_query: str = "",
    system_prompt: Optional[str] = None,
) -> str:
    image_b64 = base64.standard_b64encode(data).decode("ascii")
    prompt = user_query.strip() or "이 이미지에서 제품 코드 및 속성 정보를 추출해 마크다운 테이블로 정리해 주세요."
    sys_prompt = system_prompt or PRODUCT_CODE_SYSTEM_PROMPT

    return await analyze_image(
        image_b64=image_b64,
        mime=mime,
        text_prompt=prompt,
        system_prompt=sys_prompt,
    )


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def parse_image_with_vision_tool(
        image_base64: str,
        mime: str = "image/png",
        user_query: str = "",
    ) -> str:
        try:
            data = base64.b64decode(image_base64)
        except Exception as e:
            return f"Invalid base64 image data: {e}"

        try:
            return await _parse_image_with_vision(
                data=data,
                mime=mime,
                user_query=user_query,
            )
        except Exception as e:
            return f"Vision tool error: {e}"
