"""ARQ cron job: generate weekly digest for all orgs.

Schedule: Monday 09:00 IST = Monday 03:30 UTC
"""
import datetime
import logging

from sqlalchemy import select

from api.db.base import get_session_factory
from api.deps import OrgScope
from api.models.organization import Organization
from api.models.user import UserRole
from api.services.digest_service import run_digest_generation

logger = logging.getLogger(__name__)


async def generate_weekly_digest(ctx) -> None:  # noqa: ARG001
    """ARQ cron job: Monday 09:00 IST (03:30 UTC) — generate digest for all orgs."""
    session_factory = get_session_factory()

    async with session_factory() as db:
        orgs = list((await db.execute(select(Organization))).scalars().all())

    today = datetime.date.today()
    period_end = today - datetime.timedelta(days=1)
    period_start = period_end - datetime.timedelta(days=6)

    for org in orgs:
        async with session_factory() as db:
            scope = OrgScope(db=db, org_id=org.id, user_id=None, role=UserRole.ADMIN)
            try:
                await run_digest_generation(scope, period_start, period_end)
            except Exception as exc:  # noqa: BLE001
                logger.error("Digest failed for org %s: %s", org.id, exc)
