"""Department service — Phase 5.

Handles department CRUD and budget status calculation with Redis-deduped alerts.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
from decimal import Decimal
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from api.config import get_settings
from api.deps import OrgScope
from api.models.card import Card, CardStatus
from api.models.department import Department
from api.models.notification import NotificationType
from api.models.transaction import Transaction, TransactionState
from api.schemas.department import BudgetStatus, DepartmentCreate, DepartmentUpdate
from api.services.notification_service import notify_all_fms

settings = get_settings()


async def list_departments(scope: OrgScope) -> list[Department]:
    result = await scope.db.execute(
        select(Department).where(Department.org_id == scope.org_id).order_by(Department.name)
    )
    return list(result.scalars().all())


async def get_department(scope: OrgScope, dept_id: UUID) -> Department:
    dept = (await scope.db.execute(
        select(Department).where(
            Department.id == dept_id,
            Department.org_id == scope.org_id,
        )
    )).scalar_one_or_none()
    if dept is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "department not found")
    return dept


async def create_department(scope: OrgScope, data: DepartmentCreate) -> Department:
    dept = Department(
        org_id=scope.org_id,
        name=data.name,
        monthly_budget=data.monthly_budget,
        budget_currency=data.budget_currency,
        alert_threshold_pct=data.alert_threshold_pct,
        manager_id=data.manager_id,
    )
    scope.db.add(dept)
    try:
        await scope.db.commit()
    except IntegrityError:
        await scope.db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "department name already exists in this org")
    await scope.db.refresh(dept)
    return dept


async def update_department(scope: OrgScope, dept_id: UUID, data: DepartmentUpdate) -> Department:
    dept = await get_department(scope, dept_id)
    if data.name is not None:
        dept.name = data.name
    if data.monthly_budget is not None:
        dept.monthly_budget = data.monthly_budget
    if data.budget_currency is not None:
        dept.budget_currency = data.budget_currency
    if data.alert_threshold_pct is not None:
        dept.alert_threshold_pct = data.alert_threshold_pct
    if data.manager_id is not None:
        dept.manager_id = data.manager_id
    await scope.db.commit()
    await scope.db.refresh(dept)
    return dept


async def delete_department(scope: OrgScope, dept_id: UUID) -> None:
    dept = await get_department(scope, dept_id)
    # Check no active cards reference this department
    active_card_count = (await scope.db.execute(
        select(func.count()).select_from(Card).where(
            Card.department_id == dept_id,
            Card.org_id == scope.org_id,
            Card.status == CardStatus.ACTIVE,
        )
    )).scalar_one()
    if active_card_count > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "department has active cards — reassign or cancel them first",
        )
    await scope.db.delete(dept)
    await scope.db.commit()


async def get_budget_status(scope: OrgScope, dept_id: UUID) -> BudgetStatus:
    dept = await get_department(scope, dept_id)

    now = datetime.now(timezone.utc)
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    spent_result = (await scope.db.execute(
        select(func.coalesce(func.sum(Transaction.amount), Decimal("0"))).where(
            Transaction.department_id == dept_id,
            Transaction.org_id == scope.org_id,
            Transaction.state.in_([TransactionState.CLEARED, TransactionState.SETTLED]),
            Transaction.occurred_at >= first_of_month,
        )
    )).scalar_one()
    spent = Decimal(str(spent_result))

    utilization_pct = float(spent / dept.monthly_budget * 100) if dept.monthly_budget > 0 else 0.0
    remaining = dept.monthly_budget - spent
    is_over_threshold = utilization_pct >= dept.alert_threshold_pct

    # Budget threshold alert — dedup with Redis SET NX EX 32 days (2764800s)
    # Order: commit DB notification first, then set Redis key.
    # If DB commit fails we never mark dedup as fired — retry will re-fire correctly.
    # If Redis fails we still return the budget status — notification already committed.
    if is_over_threshold:
        month_key = first_of_month.strftime("%Y-%m")
        redis_key = f"budget_alert:{dept_id}:{month_key}"
        client = aioredis.from_url(settings.REDIS_URL)
        try:
            # Probe Redis first (read-only) to skip the DB write if already deduped
            already_fired = await client.get(redis_key)
            if not already_fired:
                await notify_all_fms(
                    db=scope.db,
                    org_id=scope.org_id,
                    notification_type=NotificationType.BUDGET_THRESHOLD,
                    entity_id=dept_id,
                    body=(
                        f"Department '{dept.name}' has reached {utilization_pct:.0f}% "
                        "of its monthly budget."
                    ),
                )
                await scope.db.commit()
                # DB committed — now mark dedup key (best-effort; failure = duplicate notif, not silent miss)
                try:
                    await client.set(redis_key, "1", nx=True, ex=2764800)
                except Exception:  # noqa: BLE001
                    logger.warning("budget_alert: Redis SET NX failed for key %s — dedup not recorded", redis_key)
        except Exception:  # noqa: BLE001
            logger.warning(
                "budget_alert: Redis unavailable for dept %s — skipping threshold notification",
                dept_id,
            )
        finally:
            await client.aclose()

    return BudgetStatus(
        department_id=dept.id,
        department_name=dept.name,
        monthly_budget=dept.monthly_budget,
        budget_currency=dept.budget_currency,
        spent=spent,
        remaining=remaining,
        utilization_pct=utilization_pct,
        alert_threshold_pct=dept.alert_threshold_pct,
        is_over_threshold=is_over_threshold,
    )
