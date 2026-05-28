import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ENUM as PG_ENUM, ARRAY, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class CardStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    CANCELLED = "CANCELLED"


class SpendCategory(str, enum.Enum):
    TRAVEL = "TRAVEL"
    MEALS = "MEALS"
    SAAS = "SAAS"
    OFFICE = "OFFICE"
    MARKETING = "MARKETING"
    HARDWARE = "HARDWARE"
    PROFESSIONAL_SERVICES = "PROFESSIONAL_SERVICES"
    OTHER = "OTHER"


card_status_pg = PG_ENUM(
    CardStatus,
    name="card_status",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)

spend_category_pg = PG_ENUM(
    SpendCategory,
    name="spend_category",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    department_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    nickname: Mapped[str] = mapped_column(String, nullable=False)
    last_four: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[CardStatus] = mapped_column(card_status_pg, nullable=False, default=CardStatus.ACTIVE, server_default=text("'ACTIVE'"))
    daily_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"), server_default=text("0"))
    monthly_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"), server_default=text("0"))
    total_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"), server_default=text("0"))
    category_restrictions: Mapped[list] = mapped_column(ARRAY(spend_category_pg), nullable=False, default=list, server_default=text("'{}'"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR", server_default=text("'INR'"))
    frozen_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False)
