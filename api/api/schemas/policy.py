from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PolicyCreate(BaseModel):
    policy_text: str = Field(min_length=5, max_length=2000, alias="text")
    is_active: bool = True

    model_config = ConfigDict(populate_by_name=True)


class PolicyUpdate(BaseModel):
    policy_text: str | None = Field(default=None, min_length=5, max_length=2000, alias="text")
    is_active: bool | None = None

    model_config = ConfigDict(populate_by_name=True)


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    org_id: UUID
    text: str = Field(alias="policy_text")
    is_active: bool
    created_by: UUID
    created_at: datetime
    updated_at: datetime
