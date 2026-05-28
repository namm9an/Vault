from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from api.models.card import SpendCategory
from api.models.transaction import PolicyVerdict, TransactionState
from api.models.user import UserRole


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class TransactionCreate(BaseModel):
    card_id: UUID
    amount: Decimal = Field(gt=0)
    merchant: str = Field(min_length=1, max_length=500)
    category: SpendCategory = SpendCategory.OTHER
    # Low: constrain to supported currencies rather than any 3-char string
    currency: Literal["INR", "USD", "EUR", "GBP"] = "INR"
    description: str | None = None
    department_id: UUID | None = None
    occurred_at: datetime | None = None
    # Phase 4: optional receipt to attach at creation time
    receipt_id: UUID | None = None

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, v: datetime | None) -> datetime | None:
        """Reject timestamps more than 24 hours in the future (Low)."""
        if v is None:
            return v
        now = datetime.now(timezone.utc)
        # Make v timezone-aware for comparison if it isn't already
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        delta = v - now
        if delta.total_seconds() > 86400:
            raise ValueError("occurred_at cannot be more than 24 hours in the future")
        return v


class ApproveRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    user_id: UUID
    card_id: UUID
    department_id: UUID | None = None
    receipt_id: UUID | None = None
    amount: Decimal
    currency: str
    merchant: str
    category: SpendCategory
    state: TransactionState
    description: str | None = None
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime


class TransactionEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transaction_id: UUID
    org_id: UUID
    from_state: TransactionState | None = None
    to_state: TransactionState
    triggered_by_user: UUID | None = None
    triggered_by_system: bool
    reason: str | None = None
    event_metadata: dict
    created_at: datetime


class TransactionPolicyResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    transaction_id: UUID
    verdict: PolicyVerdict
    reason: str
    policy_matched: str | None = None
    requires_approval_from_role: UserRole | None = None
    llm_model: str
    llm_latency_ms: int | None = None
    created_at: datetime


class TransactionWithEvents(TransactionOut):
    events: list[TransactionEventOut] = Field(default_factory=list)
    latest_policy_result: TransactionPolicyResultOut | None = None


# ---------------------------------------------------------------------------
# Filter query params (used with Depends() in the router)
# ---------------------------------------------------------------------------

class TransactionFilters(BaseModel):
    from_date: datetime | None = Field(default=None, alias="from_date")
    to_date: datetime | None = Field(default=None, alias="to_date")
    category: SpendCategory | None = None
    department_id: UUID | None = None
    card_id: UUID | None = None
    user_id: UUID | None = None
    state: TransactionState | None = None
    # H3: bounded list — prevents full-history memory loads
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_date_range(self) -> "TransactionFilters":
        """Reject logically impossible date ranges (Low)."""
        if self.from_date and self.to_date:
            from_dt = self.from_date
            to_dt = self.to_date
            # Make both tz-aware for comparison
            if from_dt.tzinfo is None:
                from_dt = from_dt.replace(tzinfo=timezone.utc)
            if to_dt.tzinfo is None:
                to_dt = to_dt.replace(tzinfo=timezone.utc)
            if from_dt > to_dt:
                raise ValueError("from_date must be before or equal to to_date")
        return self
