"""Digest ORM model — weekly spend digest per org.

The DB table `digests` and the `digest_status` enum were created in
0001_baseline migration. No migration needed for Phase 6.

digest_status enum already exists in the DB — create_type=False on SAEnum.
"""
import enum
import uuid
from datetime import datetime, date as date_type

from sqlalchemy import Column, String, Text, Date, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import text

from api.db.base import Base


class DigestStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_start: Mapped[date_type] = mapped_column(Date, nullable=False)
    period_end: Mapped[date_type] = mapped_column(Date, nullable=False)
    status: Mapped[DigestStatus] = mapped_column(
        SAEnum(DigestStatus, name="digest_status", create_type=False),
        nullable=False,
        default=DigestStatus.PENDING,
    )
    headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    top_recommendations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    flagged_items: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    aggregated_input: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    raw_llm_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    llm_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
        onupdate=datetime.utcnow,
        nullable=False,
    )
