"""Receipt ORM model — tracks uploaded receipt images and OCR results.

The DB table `receipts` was created in 0001_baseline.
No migration needed for Phase 4.

receipt_status enum already exists in the DB — create_type=False.

reimbursement_id FK is omitted here (same pattern as the receipt_id / matched_policy_id
deferrals in Phase 3): the Reimbursement ORM model does not exist until Phase 5.
The DB column exists and is writable via raw SQL; the ORM just doesn't map the FK yet.
# reimbursement_id FK added in Phase 5 when Reimbursement ORM model exists.
"""
import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, ForeignKey, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ENUM as PG_ENUM, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class ReceiptStatus(str, enum.Enum):
    PENDING_UPLOAD = "PENDING_UPLOAD"
    PROCESSING     = "PROCESSING"
    COMPLETED      = "COMPLETED"
    NEEDS_REVIEW   = "NEEDS_REVIEW"
    FAILED         = "FAILED"


# All enum values already exist in the DB — never emit CREATE TYPE.
receipt_status_pg = PG_ENUM(
    ReceiptStatus,
    name="receipt_status",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    transaction_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    # reimbursement_id FK added in Phase 5 when Reimbursement ORM model exists
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[ReceiptStatus] = mapped_column(
        receipt_status_pg,
        nullable=False,
        default=ReceiptStatus.PENDING_UPLOAD,
        server_default=text("'PENDING_UPLOAD'"),
    )
    extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    llm_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False,
    )
