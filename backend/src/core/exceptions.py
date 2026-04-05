import logging
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from typing import Any, Optional

from config import settings

logger = logging.getLogger("chatui.exceptions")


class AppError(Exception):
    """Base application error."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 500,
        detail: Optional[Any] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class LLMError(AppError):
    def __init__(self, message: str, detail: Optional[Any] = None):
        super().__init__("LLM_ERROR", message, 502, detail)


class LLMRateLimitError(AppError):
    def __init__(self, message: str = "LLM rate limit exceeded"):
        super().__init__("LLM_RATE_LIMIT", message, 429)


class LLMContextLimitError(AppError):
    def __init__(self, message: str = "Context window limit reached"):
        super().__init__("LLM_CONTEXT_LIMIT", message, 413)


class SessionNotFoundError(AppError):
    def __init__(self, session_id: str):
        super().__init__("SESSION_NOT_FOUND", f"Session {session_id} not found", 404)


class MessageNotFoundError(AppError):
    def __init__(self, message_id: str):
        super().__init__("MESSAGE_NOT_FOUND", f"Message {message_id} not found", 404)


class FileNotFoundError(AppError):
    def __init__(self, file_id: str):
        super().__init__("FILE_NOT_FOUND", f"File {file_id} not found", 404)


class FileTooLargeError(AppError):
    def __init__(self, max_mb: int):
        super().__init__("FILE_TOO_LARGE", f"File exceeds {max_mb}MB limit", 413)


class FileTypeNotSupportedError(AppError):
    def __init__(self, file_type: str):
        super().__init__("FILE_TYPE_NOT_SUPPORTED", f"File type '{file_type}' is not supported", 415)


class ToolNotFoundError(AppError):
    def __init__(self, tool_name: str):
        super().__init__("TOOL_NOT_FOUND", f"Tool '{tool_name}' not found", 404)


class ToolExecutionError(AppError):
    def __init__(self, tool_name: str, message: str):
        super().__init__("TOOL_EXECUTION_ERROR", f"Tool '{tool_name}' failed: {message}", 500)


class RateLimitExceededError(AppError):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__("RATE_LIMIT_EXCEEDED", message, 429)


# ---------------------------------------------------------------------------
# FastAPI exception handlers
# ---------------------------------------------------------------------------

def _error_body(code: str, message: str, detail: Any = None) -> dict:
    return {
        "success": False,
        "data": None,
        "error": {"code": code, "message": message, "detail": detail},
        "meta": {},
    }


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.code, exc.message, exc.detail),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body("HTTP_ERROR", str(exc.detail)),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_error_body(
            "VALIDATION_ERROR",
            "Request validation failed",
            exc.errors(),
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    msg = "An unexpected error occurred"
    detail: Any = None
    if settings.DEBUG:
        msg = f"{type(exc).__name__}: {exc}"
        detail = traceback.format_exc()
    return JSONResponse(
        status_code=500,
        content=_error_body("INTERNAL_ERROR", msg, detail if settings.DEBUG else None),
    )
