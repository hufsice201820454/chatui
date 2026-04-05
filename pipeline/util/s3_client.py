"""
AWS S3 클라이언트 래퍼
"""
import logging
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError

from config import (
    S3_BUCKET,
    S3_PREFIX,
    AWS_REGION,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
)

logger = logging.getLogger("pipeline.util.s3_client")

_s3 = None


def _get_s3():
    global _s3
    if _s3 is None:
        kwargs = {"region_name": AWS_REGION}
        if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
            kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY
        _s3 = boto3.client("s3", **kwargs)
    return _s3


def list_s3_objects(prefix: Optional[str] = None) -> List[dict]:
    """버킷의 오브젝트 목록 반환 (key, size, last_modified 포함)."""
    s3 = _get_s3()
    prefix = prefix or S3_PREFIX
    paginator = s3.get_paginator("list_objects_v2")
    objects = []
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            objects.append({
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"],
            })
    return objects


def download_s3_object(key: str) -> bytes:
    """S3 오브젝트를 bytes로 다운로드."""
    s3 = _get_s3()
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=key)
        data = response["Body"].read()
        logger.debug("Downloaded s3://%s/%s (%d bytes)", S3_BUCKET, key, len(data))
        return data
    except ClientError as e:
        logger.error("S3 download error key=%s: %s", key, e)
        raise


def upload_s3_object(key: str, data: bytes, content_type: str = "application/octet-stream"):
    """bytes를 S3에 업로드."""
    s3 = _get_s3()
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=data, ContentType=content_type)
    logger.debug("Uploaded s3://%s/%s (%d bytes)", S3_BUCKET, key, len(data))


def delete_s3_object(key: str):
    """S3 오브젝트 삭제."""
    s3 = _get_s3()
    try:
        s3.delete_object(Bucket=S3_BUCKET, Key=key)
        logger.debug("Deleted s3://%s/%s", S3_BUCKET, key)
    except ClientError as e:
        logger.warning("S3 delete error key=%s: %s", key, e)
