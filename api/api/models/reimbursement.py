import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base
from api.models.card import SpendCategory  # reuse existing enum


class ReimbursementStatus(str, enum.Enum):
    SUBMITTED      = "SUBMITTED"
    POLICY_CHECKED = "POLICY_CHECKED"
    APPROVED       = "APPROVED"
    REJECTED       = "REJECTED"
    PAID           = "PAID"


class Reimbursement(Base):
    __tablename__ = "reimbursements"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
    )
    department_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="INR", server_default=text("'INR'"),
    )
    category: Mapped[SpendCategory] = mapped_column(
        # create_type=False: spend_category enum already exists in DB from baseline
        sa.Enum(SpendCategory, name="spend_category", create_type=False),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(String, nullable=False)
    receipt_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("receipts.id", ondelete="SET NULL"), nullable=True,
    )
    status: Mapped[ReimbursementStatus] = mapped_column(
        # create_type=False: reimbursement_status enum already exists in DB from baseline
        sa.Enum(ReimbursementStatus, name="reimbursement_status", create_type=False),
        nullable=False,
        default=ReimbursementStatus.SUBMITTED,
        server_default=text("'SUBMITTED'"),
    )
    decision_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False,
    )
