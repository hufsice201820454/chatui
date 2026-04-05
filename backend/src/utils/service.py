"""
File upload / processing service (BE-FILE-01 ~ BE-FILE-06).
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import settings
from src.core.exceptions import FileTooLargeError, FileTypeNotSupportedError, FileNotFoundError
from src.model.models import File
from src.utils import parsers, chunker
from src.utils import vision_parser
from src.utils.storage import get_storage

logger = logging.getLogger("chatui.files.service")

_MAX_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024


async def upload_file(
    upload: UploadFile,
    db: AsyncSession,
    session_id: Optional[str] = None,
    chunk_document: bool = True,
) -> File:
    data = await upload.read()

    if len(data) > _MAX_BYTES:
        raise FileTooLargeError(settings.MAX_FILE_SIZE_MB)

    mime = upload.content_type or "application/octet-stream"
    filename = upload.filename or "unnamed"

    if mime not in parsers.SUPPORTED_MIME_TYPES:
        from pathlib import Path
        ext = Path(filename).suffix.lower()
        if ext not in parsers.SUPPORTED_EXTENSIONS:
            raise FileTypeNotSupportedError(mime)

    storage = get_storage()
    storage_key = await storage.save(data, filename)

    # Parse text content (이미지는 Vision API로 파싱)
    if mime in parsers.IMAGE_MIME_TYPES:
        try:
            parsed_text = await vision_parser.parse_image_with_vision(data, mime, user_query="")
        except Exception as exc:
            logger.warning("Vision parsing failed for %s: %s", filename, exc)
            parsed_text = None
    else:
        parsed_text = parsers.parse_file(data, mime, filename)

    # Chunk for RAG
    chunks_list = None
    if chunk_document and parsed_text:
        chunks = chunker.chunk_text(parsed_text, doc_id=storage_key)
        chunks_list = chunker.chunks_to_dicts(chunks)

    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=settings.FILE_EXPIRY_DAYS)
    )

    file_record = File(
        session_id=session_id,
        original_name=filename,
        storage_path=storage_key,
        mime_type=mime,
        size_bytes=len(data),
        parsed_text=parsed_text,
        chunks=chunks_list,
        meta={"content_type": mime},
        expires_at=expires_at,
    )
    db.add(file_record)
    await db.flush()
    logger.info("Uploaded file %s (%d bytes)", filename, len(data))
    return file_record


async def get_file(db: AsyncSession, file_id: str) -> File:
    result = await db.execute(select(File).where(File.id == file_id))
    f = result.scalar_one_or_none()
    if not f:
        raise FileNotFoundError(file_id)
    return f


async def delete_file(db: AsyncSession, file_id: str) -> None:
    f = await get_file(db, file_id)
    storage = get_storage()
    await storage.delete(f.storage_path)
    await db.delete(f)
    await db.flush()
    logger.info("Deleted file %s", file_id)


async def list_files(
    db: AsyncSession,
    session_id: Optional[str] = None,
    limit: int = 50,
) -> list[File]:
    q = select(File).order_by(File.created_at.desc()).limit(limit)
    if session_id:
        q = q.where(File.session_id == session_id)
    result = await db.execute(q)
    return list(result.scalars().all())


async def purge_expired_files(db: AsyncSession) -> int:
    """Delete files past their expiry date. Returns number of deleted files."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(File).where(File.expires_at <= now)
    )
    expired = result.scalars().all()
    storage = get_storage()
    count = 0
    for f in expired:
        try:
            await storage.delete(f.storage_path)
            await db.delete(f)
            count += 1
        except Exception as exc:
            logger.warning("Failed to delete expired file %s: %s", f.id, exc)
    if count:
        await db.flush()
        logger.info("Purged %d expired files", count)
    return count
