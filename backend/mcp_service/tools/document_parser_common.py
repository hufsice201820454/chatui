"""
공통 문서 파싱 헬퍼 — base64 디코드, 크기 제한, src.utils.parsers 연동.
MCP 툴(docx_parser, pdf_parser, excel_parser)에서 사용.
"""
import asyncio
import base64
import logging

from config import settings
from src.utils import parsers

logger = logging.getLogger(__name__)

_MAX_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024


def _parse_document_sync(data: bytes, mime_type: str, filename: str = "") -> str:
    text = parsers.parse_file(data, mime_type, filename)
    if text is None:
        return "Unsupported or unknown file type."
    return text


async def parse_document(
    file_base64: str,
    mime_type: str,
    filename: str = "",
) -> str:
    try:
        data = base64.standard_b64decode(file_base64)
    except Exception as e:
        return f"Invalid base64: {e}"

    if len(data) > _MAX_BYTES:
        return f"File too large. Max {settings.MAX_FILE_SIZE_MB}MB."

    try:
        return await asyncio.to_thread(
            _parse_document_sync,
            data,
            mime_type,
            filename,
        )
    except Exception as e:
        logger.exception("Document parse failed: mime=%s filename=%s", mime_type, filename)
        return f"Parse error: {e}"
