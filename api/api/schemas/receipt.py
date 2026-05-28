from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.models.receipt import ReceiptStatus


class UploadUrlRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=500)
    content_type: str = Field(min_length=1, max_length=100)


class UploadUrlResponse(BaseModel):
    receipt_id: UUID
    upload_url: str
    object_key: str


class ConfirmUploadRequest(BaseModel):
    byte_size: int = Field(gt=0)


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
