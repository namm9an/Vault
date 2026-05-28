"""Digest schemas — Phase 6."""
from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, model_validator

from api.models.digest import DigestStatus


class DigestOut(BaseModel):
    id: UUID
    org_id: UUID
    period_start: date
    period_end: date
    status: DigestStatus
    headline: str | None = None
    body: str | None = None
    top_recommendations: list[Any] | None = None
    flagged_items: list[Any] | None = None
    aggregated_input: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DigestGenerateRequest(BaseModel):
    period_start: date
    period_end: date

    @model_validator(mode="after")
    def check_dates(self) -> "DigestGenerateRequest":
        if self.period_start >= self.period_end:
            raise ValueError("period_start must be before period_end")
        return self
