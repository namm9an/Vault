from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class CategorySpend(BaseModel):
    category: str
    amount: Decimal
    transaction_count: int


class DepartmentSpend(BaseModel):
    department_id: str
    department_name: str
    amount: Decimal


class MerchantSpend(BaseModel):
    merchant: str
    amount: Decimal
    count: int


class TimeseriesPoint(BaseModel):
    period: str  # ISO datetime string
    amount: Decimal


class DashboardSummary(BaseModel):
    total_spend: Decimal
    transaction_count: int
    mom_delta_pct: float | None  # None if no prior period data
    by_category: list[CategorySpend]
    by_department: list[DepartmentSpend]
    top_merchants: list[MerchantSpend]
    pending_approvals: int
    active_cards: int
