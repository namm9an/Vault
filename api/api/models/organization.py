from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, CITEXT, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(CITEXT(), unique=True, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR", server_default=text("'INR'"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False)
