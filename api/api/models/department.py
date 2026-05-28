from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("org_id", "name"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    monthly_budget: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"), server_default=text("0"))
    budget_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR", server_default=text("'INR'"))
    alert_threshold_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=80, server_default=text("80"))
    manager_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False)
