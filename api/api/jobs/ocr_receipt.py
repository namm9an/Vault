"""ARQ job: ocr_receipt

Downloads a receipt image from S3 and runs Gemini Vision OCR to extract
merchant, amount, date, currency, and line items.  Sets status=COMPLETED
when confidence ≥ 0.7, NEEDS_REVIEW when confidence is low or validation
fails, and FAILED when S3 or the Gemini network is unreachable.

Idempotent: guards on receipt.status == PROCESSING before doing any work.
"""
import logging
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import select

from api.db.base import get_session_factory
from api.llm.llm_client import (
    LLMUnavailableError,
    LLMValidationError,
    complete_vision_json,
)
from api.models.notification import NotificationType
from api.models.receipt import Receipt, ReceiptStatus
from api.services.notification_service import fire_notification
from api.storage.s3 import StorageNotConfiguredError, get_bytes

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini prompt
# ---------------------------------------------------------------------------

_SYSTEM = (
    "You are a receipt OCR engine. Extract structured data from the receipt image "
    "and return it as JSON. Be precise with numbers — copy them exactly as shown. "
    "If a field is not visible or legible, use null. "
    "confidence is your overall extraction quality between 0.0 and 1.0."
)

_USER = (
    "Extract the following fields from this receipt image:\n"
    "- merchant_name: string or null\n"
    "- amount: number (total amount paid) or null\n"
    "- currency: 3-letter ISO code (e.g. INR, USD) or null\n"
    "- date: ISO 8601 date string YYYY-MM-DD or null\n"
    "- line_items: array of {description: string, amount: number} or []\n"
    "- confidence: float between 0.0 and 1.0\n\n"
    "Return only valid JSON. No explanation, no markdown."
)

_CONFIDENCE_THRESHOLD = 0.7


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

class LineItem(BaseModel):
    description: str
    amount: float


class ReceiptExtraction(BaseModel):
    merchant_name: str | None = None
    amount: float | None = None
    currency: str | None = None
    date: str | None = None
    line_items: list[LineItem] = []
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------

async def ocr_receipt(ctx: dict, *, receipt_id: str) -> None:  # noqa: ARG001
    """ARQ job entry point. ctx is the ARQ worker context dict."""
    async with get_session_factory()() as db:
        receipt = (
            await db.execute(
                select(Receipt)
                .where(Receipt.id == receipt_id)
                .with_for_update()
            )
        ).scalar_one_or_none()

        if receipt is None:
            logger.warning("ocr_receipt: receipt %s not found — skipping", receipt_id)
            return

        if receipt.status != ReceiptStatus.PROCESSING:
            logger.info(
                "ocr_receipt: receipt %s is in %s state — idempotent skip",
                receipt_id,
                receipt.status.value,
            )
            return

        # ------------------------------------------------------------------
        # Download image bytes from S3
        # ------------------------------------------------------------------
        try:
            image_bytes = await get_bytes(receipt.object_key)
        except (FileNotFoundError, StorageNotConfiguredError, Exception) as exc:
            logger.error(
                "ocr_receipt: S3 download failed for receipt %s: %s",
                receipt_id,
                exc,
            )
            receipt.status = ReceiptStatus.FAILED
            receipt.llm_error = f"S3 download failed: {exc}"
            await db.commit()
            return

        # ------------------------------------------------------------------
        # Call Gemini Vision
        # ------------------------------------------------------------------
        try:
            extraction, latency_ms = await complete_vision_json(
                system=_SYSTEM,
                user=_USER,
                image_bytes=image_bytes,
                mime_type=receipt.content_type,
                schema=ReceiptExtraction,
                temperature=0.0,
                max_tokens=1024,
            )
        except LLMUnavailableError as exc:
            logger.error(
                "ocr_receipt: Gemini unavailable for receipt %s: %s",
                receipt_id,
                exc,
            )
            receipt.status = ReceiptStatus.FAILED
            receipt.llm_error = str(exc)
            await db.commit()
            return
        except LLMValidationError as exc:
            logger.warning(
                "ocr_receipt: Gemini returned invalid JSON for receipt %s — NEEDS_REVIEW",
                receipt_id,
            )
            receipt.status = ReceiptStatus.NEEDS_REVIEW
            receipt.llm_error = str(exc)
            await db.commit()
            await _notify_review_needed(db, receipt)
            await db.commit()
            return

        logger.info(
            "ocr_receipt: receipt %s extracted in %dms, confidence=%.2f",
            receipt_id,
            latency_ms,
            extraction.confidence,
        )

        # ------------------------------------------------------------------
        # Persist result
        # ------------------------------------------------------------------
        if extraction.confidence >= _CONFIDENCE_THRESHOLD:
            receipt.status = ReceiptStatus.COMPLETED
            receipt.extracted_data = extraction.model_dump()
            receipt.llm_error = None
            await db.commit()
        else:
            receipt.status = ReceiptStatus.NEEDS_REVIEW
            receipt.extracted_data = extraction.model_dump()
            receipt.llm_error = f"Low confidence: {extraction.confidence:.2f}"
            await db.commit()
            await _notify_review_needed(db, receipt)
            await db.commit()


async def _notify_review_needed(db, receipt: Receipt) -> None:
    await fire_notification(
        db=db,
        org_id=receipt.org_id,
        user_id=receipt.uploaded_by,
        notification_type=NotificationType.RECEIPT_REVIEW_NEEDED,
        entity_id=receipt.id,
        body=(
            "Receipt uploaded — please review the extracted data and correct "
            "any errors before linking to a transaction."
        ),
    )
