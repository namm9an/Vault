"""Policy ORM model — plain-English spend policies per org.

The DB table `policies` was created in 0001_baseline.
0003_policy_soft_delete adds the nullable `deleted_at` column.

The Python attribute for the text column is `policy_text` mapped to the DB column
"text" — this decouples the attribute name from SQLAlchemy's text() helper
function import in the same module, following the same pattern as
log_metadata → "metadata" in audit_log.py.

Soft-delete: delete_policy sets is_active=False and deleted_at=NOW() instead
of hard-deleting the row.  This preserves the FK reference from
TransactionPolicyResult.matched_policy_id so the audit trail is never orphaned.
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Python attr = policy_text; DB column = "text"
    # Avoids shadowing SQLAlchemy's text() function import at module level.
    policy_text: Mapped[str] = mapped_column("text", Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("TRUE"),
    )
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Soft-delete timestamp — NULL means the policy is alive.
    # Added in migration 0003_policy_soft_delete.
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False,
    )
