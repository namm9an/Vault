from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.models.receipt import ReceiptStatus

_ACCEPTED_CONTENT_TYPES = Literal["image/jpeg", "image/png", "application/pdf"]
_MAX_BYTES = 10_485_760  # 10 MB — matches the client-side cap in ReceiptUploader.tsx


class UploadUrlRequest(BaseModel):
    content_type: _ACCEPTED_CONTENT_TYPES


class UploadUrlResponse(BaseModel):
    receipt_id: UUID
    upload_url: str
    object_key: str


class ConfirmUploadRequest(BaseModel):
    byte_size: int = Field(gt=0, le=_MAX_BYTES)  # 10 MB cap — mirrors client-side guard


class ReceiptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    uploaded_by: UUID
    transaction_id: UUID | None = None
    object_key: str
    content_type: str
    byte_size: int | None = None
    status: ReceiptStatus
    extracted_data: dict | None = None
    confidence: Decimal | None = None
    llm_error: str | None = None
    created_at: datetime
    updated_at: datetime
