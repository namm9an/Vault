"""Pydantic schemas for LLM-structured output.

Every LLM response is validated against one of these schemas before reaching the DB.
The retry-on-validation-error loop in llm_client.complete_json() uses these to surface
clear error messages back to the model on the second attempt.
"""
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from api.models.card import SpendCategory


class ReceiptExtraction(BaseModel):
    """Output schema for the OCR receipt pipeline (temperature=0)."""

    merchant: str
    amount: Decimal = Field(gt=0)
    currency: Literal["INR", "USD", "EUR", "GBP"] = "INR"
    date: str  # ISO date string YYYY-MM-DD — validated by caller
    category: SpendCategory = SpendCategory.OTHER
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str | None = None


class PolicyCheckResult(BaseModel):
    """Output schema for the policy engine (temperature=0).

    verdict is the most restrictive verdict across all active policies.
    policy_matched is the verbatim policy text that triggered the verdict (or None).
    requires_approval_from is only set when verdict=FLAGGED.
    """

    verdict: Literal["APPROVED", "FLAGGED", "BLOCKED"]
    reason: str = Field(max_length=1000)
    policy_matched: str | None = None
    requires_approval_from: Literal["FINANCE_MANAGER", "ADMIN"] | None = None
