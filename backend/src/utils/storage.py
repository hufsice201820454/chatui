"""
Storage abstraction – local filesystem or S3 (BE-FILE-01).
"""
import logging
import uuid
from pathlib import Path

import aiofiles

from config import resolve_backend_path, settings

logger = logging.getLogger("chatui.files.storage")


class LocalStorage:
    def __init__(self, base_dir: str = settings.UPLOAD_DIR):
        resolved = resolve_backend_path(base_dir) or base_dir
        self._base = Path(resolved)
        self._base.mkdir(parents=True, exist_ok=True)

    def _key_to_path(self, key: str) -> Path:
        return self._base / key

    async def save(self, data: bytes, original_name: str) -> str:
        ext = Path(original_name).suffix
        key = f"{uuid.uuid4().hex}{ext}"
        dest = self._key_to_path(key)
        async with aiofiles.open(dest, "wb") as f:
            await f.write(data)
        logger.debug("Saved file locally: %s", key)
        return key

    async def read(self, key: str) -> bytes:
        path = self._key_to_path(key)
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def delete(self, key: str) -> None:
        path = self._key_to_path(key)
        if path.exists():
            path.unlink()
            logger.debug("Deleted local file: %s", key)

    def public_url(self, key: str) -> str:
        return f"/files/{key}"


class S3Storage:
    def __init__(self):
        import boto3
        self._bucket = settings.AWS_BUCKET_NAME
        self._s3 = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )

    async def save(self, data: bytes, original_name: str) -> str:
        import asyncio
        ext = Path(original_name).suffix
        key = f"uploads/{uuid.uuid4().hex}{ext}"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._s3.put_object(Bucket=self._bucket, Key=key, Body=data),
        )
        logger.debug("Saved to S3: %s", key)
        return key

    async def read(self, key: str) -> bytes:
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._s3.get_object(Bucket=self._bucket, Key=key),
        )
        return response["Body"].read()

    async def delete(self, key: str) -> None:
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._s3.delete_object(Bucket=self._bucket, Key=key),
        )

    def public_url(self, key: str) -> str:
        return f"https://{self._bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"


def get_storage() -> LocalStorage | S3Storage:
    if settings.USE_S3:
        return S3Storage()
    return LocalStorage()
