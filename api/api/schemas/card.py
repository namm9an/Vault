from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.models.card import CardStatus, SpendCategory


class CardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    user_id: UUID
    department_id: UUID | None = None
    nickname: str
    last_four: str
    status: CardStatus
    daily_limit: Decimal
    monthly_limit: Decimal
    total_limit: Decimal
    category_restrictions: list[SpendCategory]
    currency: str
    frozen_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CardCreate(BaseModel):
    user_id: UUID
    nickname: str = Field(min_length=1, max_length=200)
    department_id: UUID | None = None
    daily_limit: Decimal = Field(default=Decimal("0"), ge=0)
    monthly_limit: Decimal = Field(default=Decimal("0"), ge=0)
    total_limit: Decimal = Field(default=Decimal("0"), ge=0)
    category_restrictions: list[SpendCategory] = Field(default_factory=list)
    currency: str = Field(default="INR", min_length=3, max_length=3)


class CardUpdate(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=200)
    department_id: UUID | None = None
    daily_limit: Decimal | None = Field(default=None, ge=0)
    monthly_limit: Decimal | None = Field(default=None, ge=0)
    total_limit: Decimal | None = Field(default=None, ge=0)
    category_restrictions: list[SpendCategory] | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class CardResponse(BaseModel):
    card: CardOut
