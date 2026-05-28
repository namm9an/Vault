import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, CITEXT, ENUM as PG_ENUM, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    FINANCE_MANAGER = "FINANCE_MANAGER"
    EMPLOYEE = "EMPLOYEE"


user_role_pg = PG_ENUM(
    UserRole,
    name="user_role",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(CITEXT(), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(user_role_pg, nullable=False, default=UserRole.EMPLOYEE, server_default=text("'EMPLOYEE'"))
    department_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    last_login_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False)
