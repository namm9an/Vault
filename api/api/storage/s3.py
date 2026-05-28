"""S3-compatible object storage helpers for receipt images.

Uses boto3 with E2E Object Storage credentials.  All boto3 calls are sync;
they are wrapped in asyncio.to_thread() to avoid blocking the event loop.

Key scheme: org/{org_id}/receipts/{receipt_id}.{ext}
Bucket: configured via S3_BUCKET env var.
"""
import asyncio
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from api.config import get_settings


class StorageNotConfiguredError(Exception):
    """Raised when S3 credentials are absent from the environment."""


def _get_client():
    """Build a boto3 S3 client from settings.

    Raises StorageNotConfiguredError if S3_ACCESS_KEY is not set.
    Uses path-style addressing for E2E Object Storage compatibility.
    """
    settings = get_settings()
    if not settings.S3_ACCESS_KEY:
        raise StorageNotConfiguredError(
            "S3_ACCESS_KEY is not configured. "
            "Set S3_ACCESS_KEY and S3_SECRET_KEY in .env to enable receipt uploads."
        )
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=Config(
            signature_version="s3v4",
            addressing_style="path",  # required for self-hosted S3-compatible endpoints
        ),
    )


async def presign_put(key: str, content_type: str) -> str:
    """Generate a presigned PUT URL for direct browser-to-S3 upload."""
    settings = get_settings()
    client = _get_client()
    url: str = await asyncio.to_thread(
        client.generate_presigned_url,
        "put_object",
        Params={
            "Bucket": settings.S3_BUCKET,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.S3_PRESIGN_TTL_SECONDS,
    )
    return url


async def presign_get(key: str) -> str:
    """Generate a presigned GET URL for the ARQ worker to download a receipt."""
    settings = get_settings()
    client = _get_client()
    url: str = await asyncio.to_thread(
        client.generate_presigned_url,
        "get_object",
        Params={
            "Bucket": settings.S3_BUCKET,
            "Key": key,
        },
        ExpiresIn=settings.S3_PRESIGN_TTL_SECONDS,
    )
    return url


async def head(key: str) -> dict[str, Any]:
    """Return object metadata. Raises FileNotFoundError if the key does not exist."""
    settings = get_settings()
    client = _get_client()
    try:
        result: dict = await asyncio.to_thread(
            client.head_object,
            Bucket=settings.S3_BUCKET,
            Key=key,
        )
        return result
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("404", "NoSuchKey"):
            raise FileNotFoundError(f"S3 key not found: {key}") from exc
        raise


def _sync_get_bytes(s3_client: Any, bucket: str, key: str) -> bytes:
    """Sync helper — boto3 StreamingBody.read() is blocking."""
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()  # type: ignore[no-any-return]


async def get_bytes(key: str) -> bytes:
    """Download the full object body as bytes (used by the OCR worker)."""
    settings = get_settings()
    client = _get_client()
    return await asyncio.to_thread(_sync_get_bytes, client, settings.S3_BUCKET, key)
