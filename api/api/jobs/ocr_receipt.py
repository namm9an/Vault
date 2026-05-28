"""ARQ job: ocr_receipt

Downloads a receipt from S3, then marks it NEEDS_REVIEW so a user can
fill in the transaction details manually.

WHY NOT LLM OCR?
Llama 3.1 8B is a text-only model — it cannot read image pixels.  A
text-only prompt with only filename / content_type / byte_size produces
fabricated merchant names, amounts, and dates.  Shipping hallucinated
extractions as authoritative data (status=COMPLETED) is worse than being
honest that the data is unverified.  Until a real vision model or OCR
service is wired in, every uploaded receipt goes to NEEDS_REVIEW so the
uploader is prompted to fill in the correct values themselves.

When real OCR is available, replace the body of this job with an actual
API call and set status=COMPLETED / FAILED based on the result.

Idempotent: guards on receipt.status == PROCESSING before doing any work.
"""
import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from api.db.base import get_session_factory
from api.models.notification import NotificationType
from api.models.receipt import Receipt, ReceiptStatus
from api.services.notification_service import fire_notification

logger = logging.getLogger(__name__)


async def ocr_receipt(ctx: dict, *, receipt_id: str) -> None:  # noqa: ARG001
    """ARQ job entry point.  ctx is the ARQ worker context dict."""
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

        logger.info(
            "ocr_receipt: marking receipt %s as NEEDS_REVIEW "
            "(text-only model — manual data entry required)",
            receipt_id,
        )

        receipt.status = ReceiptStatus.NEEDS_REVIEW
        receipt.extracted_data = None
        receipt.llm_error = None

        await db.commit()

        await fire_notification(
            db=db,
            org_id=receipt.org_id,
            user_id=receipt.uploaded_by,
            notification_type=NotificationType.RECEIPT_REVIEW_NEEDED,
            entity_id=receipt.id,
            body=(
                "Receipt uploaded — please open the transaction and fill in "
                "the merchant, amount, and date manually."
            ),
        )
        await db.commit()
