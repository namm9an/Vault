"""Receipt service — upload flow and OCR retry.

Upload flow:
  1. create_upload_url() → creates Receipt row (PENDING_UPLOAD) + presigned PUT URL
  2. Browser PUTs the file directly to S3
  3. confirm_upload() → sets status=PROCESSING, enqueues ocr_receipt ARQ job
  4. Worker processes async; client polls GET /receipts/{id}
"""
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import HTTPException, status
from sqlalchemy import select

from api.config import get_settings
from api.deps import OrgScope
from api.models.receipt import Receipt, ReceiptStatus
from api.schemas.receipt import UploadUrlRequest
from api.storage.s3 import StorageNotConfiguredError, head, presign_put


def _object_key(org_id: UUID, receipt_id: UUID, content_type: str) -> str:
    """Derive the S3 key from org + receipt IDs and content type."""
    ext_map = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "application/pdf": "pdf",
    }
    ext = ext_map.get(content_type.lower(), "bin")
    return f"org/{org_id}/receipts/{receipt_id}.{ext}"


async def create_upload_url(
    scope: OrgScope,
    data: UploadUrlRequest,
) -> tuple[Receipt, str]:
    """Create a Receipt row in PENDING_UPLOAD state and return a presigned PUT URL.

    Raises HTTP 503 if S3 is not configured (missing credentials).
    """
    settings = get_settings()
    try:
        # Create the Receipt row first so we have an ID for the key
        receipt = Receipt(
            org_id=scope.org_id,
            uploaded_by=scope.user_id,
            content_type=data.content_type,
            status=ReceiptStatus.PENDING_UPLOAD,
            object_key="",  # filled after we know the ID
        )
        scope.db.add(receipt)
        await scope.db.flush()

        key = _object_key(scope.org_id, receipt.id, data.content_type)
        receipt.object_key = key

        upload_url = await presign_put(key, data.content_type)

        await scope.db.commit()
        await scope.db.refresh(receipt)
        return receipt, upload_url
    except StorageNotConfiguredError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Object storage not configured: {exc}",
        ) from exc


async def confirm_upload(
    scope: OrgScope,
    receipt_id: UUID,
    byte_size: int,
) -> Receipt:
    """Mark the receipt as PROCESSING and enqueue the OCR job.

    Verifies the object actually exists in S3 before transitioning.
    """
    receipt = await _load_receipt(scope, receipt_id)

    if receipt.status != ReceiptStatus.PENDING_UPLOAD:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"receipt is in {receipt.status.value} state — cannot confirm again",
        )

    # Verify the object landed in S3
    try:
        await head(receipt.object_key)
    except FileNotFoundError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "uploaded file not found in object storage — please retry the upload",
        )

    receipt.status = ReceiptStatus.PROCESSING
    receipt.byte_size = byte_size
    await scope.db.commit()
    await scope.db.refresh(receipt)

    # Enqueue OCR job
    pool = await create_pool(RedisSettings.from_dsn(get_settings().ARQ_REDIS_URL))
    await pool.enqueue_job("ocr_receipt", receipt_id=str(receipt.id))
    await pool.aclose()

    return receipt


async def get_receipt(scope: OrgScope, receipt_id: UUID) -> Receipt:
    return await _load_receipt(scope, receipt_id)


async def retry_ocr(scope: OrgScope, receipt_id: UUID) -> Receipt:
    """Reset a FAILED or NEEDS_REVIEW receipt to PROCESSING and re-enqueue OCR."""
    receipt = await _load_receipt(scope, receipt_id)

    if receipt.status not in (ReceiptStatus.FAILED, ReceiptStatus.NEEDS_REVIEW):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"receipt is in {receipt.status.value} state — retry only valid for FAILED or NEEDS_REVIEW",
        )

    receipt.status = ReceiptStatus.PROCESSING
    receipt.llm_error = None
    await scope.db.commit()
    await scope.db.refresh(receipt)

    pool = await create_pool(RedisSettings.from_dsn(get_settings().ARQ_REDIS_URL))
    await pool.enqueue_job("ocr_receipt", receipt_id=str(receipt.id))
    await pool.aclose()

    return receipt


async def _load_receipt(scope: OrgScope, receipt_id: UUID) -> Receipt:
    receipt = (await scope.db.execute(
        select(Receipt).where(
            Receipt.id == receipt_id,
            Receipt.org_id == scope.org_id,
        )
    )).scalar_one_or_none()
    if receipt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "receipt not found")
    return receipt
