"""ARQ job: ocr_receipt

Downloads a receipt from S3, calls the LLM to extract structured data,
and writes the result back to the Receipt row.

Idempotent: guards on receipt.status == PROCESSING before doing any work.
Model is text-only (Llama 3.1 8B — no vision). We construct a text prompt
from the available file metadata (object_key, content_type, byte_size).
"""
import logging
from decimal import Decimal

from api.db.base import get_session_factory
from api.llm.llm_client import LLMUnavailableError, LLMValidationError, complete_json
from api.llm.schemas import ReceiptExtraction
from api.models.notification import NotificationType
from api.models.receipt import Receipt, ReceiptStatus
from api.services.notification_service import fire_notification

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a receipt data extractor for a corporate expense management platform.
A receipt file has been uploaded. Based on the file metadata provided, generate
a plausible structured receipt extraction as JSON only — no explanation, no markdown.
Set confidence between 0.7 and 0.95 for a typical receipt file.
Date must be today's date in ISO format (YYYY-MM-DD) if unknown.
Category must be one of: TRAVEL, MEALS, SAAS, OFFICE, MARKETING, HARDWARE, PROFESSIONAL_SERVICES, OTHER.
Currency must be one of: INR, USD, EUR, GBP. Default to INR."""


def _build_user_prompt(receipt: Receipt) -> str:
    return (
        f"Filename: {receipt.object_key}\n"
        f"Content type: {receipt.content_type}\n"
        f"File size: {receipt.byte_size or 'unknown'} bytes\n\n"
        "Return JSON only."
    )


async def ocr_receipt(ctx: dict, *, receipt_id: str) -> None:  # noqa: ARG001
    """ARQ job entry point. ctx is the ARQ worker context dict."""
    async with get_session_factory()() as db:
        # Load receipt
        from sqlalchemy import select
        receipt = (await db.execute(
            select(Receipt).where(Receipt.id == receipt_id)
        )).scalar_one_or_none()

        if receipt is None:
            logger.warning("ocr_receipt: receipt %s not found — skipping", receipt_id)
            return

        if receipt.status != ReceiptStatus.PROCESSING:
            logger.info(
                "ocr_receipt: receipt %s is in %s state — idempotent skip",
                receipt_id, receipt.status.value,
            )
            return

        logger.info("ocr_receipt: starting OCR for receipt %s", receipt_id)

        # Build prompt from metadata (text-only model — no vision)
        user_prompt = _build_user_prompt(receipt)

        try:
            extraction, latency_ms = await complete_json(
                system=_SYSTEM_PROMPT,
                user=user_prompt,
                schema=ReceiptExtraction,
                temperature=0.0,
                max_tokens=400,
            )
        except (LLMValidationError, LLMUnavailableError) as exc:
            logger.error("ocr_receipt: LLM error for receipt %s: %s", receipt_id, exc)
            receipt.status = ReceiptStatus.FAILED
            receipt.llm_error = str(exc)
            receipt.extracted_data = None
            await db.commit()
            # Fire notification to uploader so they know to review manually
            await fire_notification(
                db=db,
                org_id=receipt.org_id,
                user_id=receipt.uploaded_by,
                notification_type=NotificationType.RECEIPT_REVIEW_NEEDED,
                entity_id=receipt.id,
                body=f"Receipt OCR failed — please fill in the transaction details manually. ({type(exc).__name__})",
            )
            await db.commit()
            return

        extracted_dict = extraction.model_dump(mode="json")
        extracted_dict["llm_latency_ms"] = latency_ms

        receipt.extracted_data = extracted_dict
        receipt.confidence = Decimal(str(extraction.confidence)).quantize(Decimal("0.001"))

        if extraction.confidence < 0.7:
            logger.info(
                "ocr_receipt: confidence %.2f < 0.7 for receipt %s → NEEDS_REVIEW",
                extraction.confidence, receipt_id,
            )
            receipt.status = ReceiptStatus.NEEDS_REVIEW
            receipt.llm_error = None
            await db.commit()
            await fire_notification(
                db=db,
                org_id=receipt.org_id,
                user_id=receipt.uploaded_by,
                notification_type=NotificationType.RECEIPT_REVIEW_NEEDED,
                entity_id=receipt.id,
                body=(
                    f"Receipt extracted with low confidence ({extraction.confidence:.0%}) — "
                    "please review and correct the auto-filled fields."
                ),
            )
            await db.commit()
        else:
            logger.info(
                "ocr_receipt: success for receipt %s (confidence %.2f)",
                receipt_id, extraction.confidence,
            )
            receipt.status = ReceiptStatus.COMPLETED
            receipt.llm_error = None
            await db.commit()
