"""
File upload / management API (BE-FILE-01 ~ BE-FILE-06).
"""
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File as FastAPIFile, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.responses import ok
from src.datasource.sqlite.sqlite import get_db
from src.utils import parsers, vision_parser
from src.utils import service as file_service

router = APIRouter(prefix="/files", tags=["Files"])


@router.post("/analyze-image")
async def analyze_image(
    file: UploadFile = FastAPIFile(...),
    query: Optional[str] = Query(None, description="Optional user query for vision"),
    db: AsyncSession = Depends(get_db),
):
    """이미지 파일만 받아 Vision 파싱 결과(테이블 텍스트) 반환. 검증/테스트용."""
    mime = file.content_type or "application/octet-stream"
    if mime not in parsers.IMAGE_MIME_TYPES:
        raise HTTPException(400, f"Image required (jpeg/png/webp). Got: {mime}")
    data = await file.read()
    result = await vision_parser.parse_image_with_vision(data, mime, user_query=query or "")
    return ok({"parsed_text": result})


@router.post("/upload")
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    session_id: Optional[str] = Query(None),
    chunk: bool = Query(True, description="Chunk document for RAG"),
    db: AsyncSession = Depends(get_db),
):
    record = await file_service.upload_file(
        file, db, session_id=session_id, chunk_document=chunk
    )
    return ok(_file_dict(record))


@router.get("")
async def list_files(
    session_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    files = await file_service.list_files(db, session_id=session_id, limit=limit)
    return ok([_file_dict(f) for f in files])


@router.get("/{file_id}")
async def get_file(file_id: str, db: AsyncSession = Depends(get_db)):
    f = await file_service.get_file(db, file_id)
    return ok(_file_dict(f, include_text=True))


@router.delete("/{file_id}")
async def delete_file(file_id: str, db: AsyncSession = Depends(get_db)):
    await file_service.delete_file(db, file_id)
    return ok({"deleted": file_id})


def _file_dict(f, include_text: bool = False) -> dict:
    d = {
        "id": f.id,
        "session_id": f.session_id,
        "original_name": f.original_name,
        "mime_type": f.mime_type,
        "size_bytes": f.size_bytes,
        "chunk_count": len(f.chunks) if f.chunks else 0,
        "meta": f.meta,
        "created_at": f.created_at.isoformat(),
        "expires_at": f.expires_at.isoformat() if f.expires_at else None,
    }
    if include_text:
        d["parsed_text"] = f.parsed_text
    return d
