"""Notification ORM model — in-app notifications per user.

The DB table `notifications` was created in 0001_baseline.
No migration needed for Phase 4.

notification_type enum already exists in the DB — create_type=False.

The Python attribute for the JSONB column is `payload` (no rename needed —
`payload` is not a reserved SQLAlchemy name). The `type` attribute is kept
as-is; SQLAlchemy's polymorphic discriminator is only reserved when
__mapper_args__["polymorphic_on"] is set, which we are not using.
"""
import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ENUM as PG_ENUM, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class NotificationType(str, enum.Enum):
    POLICY_FLAGGED        = "POLICY_FLAGGED"
    POLICY_BLOCKED        = "POLICY_BLOCKED"
    APPROVAL_REQUESTED    = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED      = "APPROVAL_GRANTED"
    APPROVAL_REJECTED     = "APPROVAL_REJECTED"
    BUDGET_THRESHOLD      = "BUDGET_THRESHOLD"
    DIGEST_READY          = "DIGEST_READY"
    RECEIPT_REVIEW_NEEDED = "RECEIPT_REVIEW_NEEDED"


notification_type_pg = PG_ENUM(
    NotificationType,
    name="notification_type",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[NotificationType] = mapped_column(notification_type_pg, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"),
    )
    read_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False,
    )
