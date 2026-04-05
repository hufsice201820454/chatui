from typing import Any, Optional, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: Optional[Any] = None


class Meta(BaseModel):
    page: Optional[int] = None
    page_size: Optional[int] = None
    total: Optional[int] = None
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None
    meta: Optional[Meta] = None


def ok(data: Any = None, meta: Optional[dict] = None) -> dict:
    """Return a successful response dict."""
    return {
        "success": True,
        "data": data,
        "error": None,
        "meta": meta or {},
    }


def paginated(data: Any, total: int, next_cursor: Optional[str] = None) -> dict:
    """Return a paginated successful response."""
    return {
        "success": True,
        "data": data,
        "error": None,
        "meta": {
            "total": total,
            "next_cursor": next_cursor,
        },
    }
