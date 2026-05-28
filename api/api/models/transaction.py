import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ENUM as PG_ENUM, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class TransactionState(str, enum.Enum):
    INITIATED = "INITIATED"
    POLICY_CHECKED = "POLICY_CHECKED"
    APPROVED = "APPROVED"
    FLAGGED = "FLAGGED"
    BLOCKED = "BLOCKED"
    CLEARED = "CLEARED"
    SETTLED = "SETTLED"


class PolicyVerdict(str, enum.Enum):
    APPROVED = "APPROVED"
    FLAGGED = "FLAGGED"
    BLOCKED = "BLOCKED"


# All three enum types already exist in the DB (created in 0001_baseline).
# create_type=False tells SQLAlchemy not to emit CREATE TYPE.
transaction_state_pg = PG_ENUM(
    TransactionState,
    name="transaction_state",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)

policy_verdict_pg = PG_ENUM(
    PolicyVerdict,
    name="policy_verdict",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)

# spend_category and user_role already exist — imported lazily via FKs.
# We create local PG_ENUM references for use in TransactionPolicyResult columns.
from api.models.card import SpendCategory  # noqa: E402

spend_category_pg = PG_ENUM(
    SpendCategory,
    name="spend_category",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)

from api.models.user import UserRole  # noqa: E402

user_role_pg = PG_ENUM(
    UserRole,
    name="user_role",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)


class Transaction(Base):
    __tablename__ = "transactions"

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
    card_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cards.id", ondelete="RESTRICT"), nullable=False,
    )
    department_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="INR", server_default=text("'INR'"),
    )
    merchant: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[SpendCategory] = mapped_column(
        spend_category_pg, nullable=False,
        default=SpendCategory.OTHER, server_default=text("'OTHER'"),
    )
    state: Mapped[TransactionState] = mapped_column(
        transaction_state_pg, nullable=False,
        default=TransactionState.INITIATED, server_default=text("'INITIATED'"),
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"),
    )
    # Phase 4: Receipt ORM model now exists — FK mapping restored.
    receipt_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("receipts.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False,
    )


class TransactionEvent(Base):
    """Append-only audit log for every state transition.

    The Python attribute for the JSONB column is ``event_metadata`` because
    SQLAlchemy's DeclarativeBase reserves ``metadata`` as a class attribute.
    The actual DB column name is ``"metadata"`` (via mapped_column alias).
    """

    __tablename__ = "transaction_events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    transaction_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
    )
    from_state: Mapped[TransactionState | None] = mapped_column(
        transaction_state_pg, nullable=True,
    )
    to_state: Mapped[TransactionState] = mapped_column(
        transaction_state_pg, nullable=False,
    )
    triggered_by_user: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    triggered_by_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("FALSE"),
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Python attr = event_metadata; DB column = "metadata"
    event_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False,
    )


class TransactionPolicyResult(Base):
    __tablename__ = "transaction_policy_results"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
    )
    transaction_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False,
    )
    verdict: Mapped[PolicyVerdict] = mapped_column(policy_verdict_pg, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    policy_matched: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Phase 4: Policy ORM model now exists — FK mapping restored.
    matched_policy_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("policies.id", ondelete="SET NULL"),
        nullable=True,
    )
    requires_approval_from_role: Mapped[UserRole | None] = mapped_column(
        user_role_pg, nullable=True,
    )
    raw_llm_response: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"),
    )
    llm_model: Mapped[str] = mapped_column(Text, nullable=False)
    llm_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False,
    )
