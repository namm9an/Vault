from uuid import UUID

from fastapi import APIRouter, Depends

from api.deps import OrgScope, get_org_scope
from api.schemas.receipt import (
    ConfirmUploadRequest,
    ReceiptOut,
    UploadUrlRequest,
    UploadUrlResponse,
)
from api.services import receipt_service

router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.post("/upload-url", response_model=UploadUrlResponse, status_code=201)
async def create_upload_url(
    data: UploadUrlRequest,
    scope: OrgScope = Depends(get_org_scope),
):
    """Create a Receipt row and return a presigned PUT URL for direct browser upload."""
    receipt, upload_url = await receipt_service.create_upload_url(scope, data)
    return UploadUrlResponse(
        receipt_id=receipt.id,
        upload_url=upload_url,
        object_key=receipt.object_key,
    )


@router.post("/{receipt_id}/confirm", response_model=ReceiptOut)
async def confirm_upload(
    receipt_id: UUID,
    data: ConfirmUploadRequest,
    scope: OrgScope = Depends(get_org_scope),
):
    """Confirm the browser upload completed. Sets status=PROCESSING and enqueues OCR."""
    return await receipt_service.confirm_upload(scope, receipt_id, data.byte_size)


@router.get("/{receipt_id}", response_model=ReceiptOut)
async def get_receipt(
    receipt_id: UUID,
    scope: OrgScope = Depends(get_org_scope),
):
    """Poll this endpoint after confirm to track OCR status."""
    return await receipt_service.get_receipt(scope, receipt_id)


@router.post("/{receipt_id}/retry", response_model=ReceiptOut)
async def retry_ocr(
    receipt_id: UUID,
    scope: OrgScope = Depends(get_org_scope),
):
    """Re-enqueue OCR for a FAILED or NEEDS_REVIEW receipt."""
    return await receipt_service.retry_ocr(scope, receipt_id)
