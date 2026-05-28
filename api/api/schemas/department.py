from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    monthly_budget: Decimal = Field(default=Decimal("0"), ge=0)
    budget_currency: str = Field(default="INR", min_length=3, max_length=3)
    alert_threshold_pct: int = Field(default=80, ge=1, le=100)
    manager_id: UUID | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    monthly_budget: Decimal | None = Field(default=None, ge=0)
    budget_currency: str | None = Field(default=None, min_length=3, max_length=3)
    alert_threshold_pct: int | None = Field(default=None, ge=1, le=100)
    manager_id: UUID | None = None


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    name: str
    monthly_budget: Decimal
    budget_currency: str
    alert_threshold_pct: int
    manager_id: UUID | None = None


class BudgetStatus(BaseModel):
    department_id: UUID
    department_name: str
    monthly_budget: Decimal
    budget_currency: str
    spent: Decimal
    remaining: Decimal
    utilization_pct: float
    alert_threshold_pct: int
    is_over_threshold: bool
