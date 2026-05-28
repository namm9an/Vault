from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.models.card import SpendCategory
from api.models.reimbursement import ReimbursementStatus


class ReimbursementCreate(BaseModel):
    department_id: UUID | None = None
    amount: Decimal = Field(gt=0)
    currency: Literal["INR", "USD", "EUR", "GBP"] = "INR"
    category: SpendCategory
    description: str = Field(min_length=1, max_length=500)
    receipt_id: UUID | None = None


class ReimbursementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    user_id: UUID
    department_id: UUID | None = None
    amount: Decimal
    currency: str
    category: SpendCategory
    description: str
    receipt_id: UUID | None = None
    status: ReimbursementStatus
    decision_reason: str | None = None
    decided_by: UUID | None = None
    decided_at: datetime | None = None
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ReimbursementFilters(BaseModel):
    status: ReimbursementStatus | None = None
    department_id: UUID | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def check_date_order(self) -> "ReimbursementFilters":
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValueError("from_date must be before to_date")
        return self


class ApproveRejectBody(BaseModel):
    reason: str | None = None
