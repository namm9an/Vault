"""Dashboard service — Phase 5.

Aggregates spend data for the dashboard summary and timeseries endpoints.
Uses Redis for a 5-minute cache keyed on org+date range.
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import redis.asyncio as aioredis
from sqlalchemy import func, select, text

from api.config import get_settings
from api.deps import OrgScope
from api.models.card import Card, CardStatus
from api.models.department import Department
from api.models.transaction import Transaction, TransactionState
from api.schemas.dashboard import (
    CategorySpend,
    DashboardSummary,
    DepartmentSpend,
    MerchantSpend,
    TimeseriesPoint,
)

settings = get_settings()
_CACHE_TTL = 300  # 5 minutes


async def _get_redis():
    return aioredis.from_url(settings.REDIS_URL)


async def get_summary(scope: OrgScope, from_date: datetime, to_date: datetime) -> DashboardSummary:
    cache_key = (
        f"dash:{scope.org_id}:summary:"
        f"{hashlib.md5(f'{from_date}{to_date}'.encode()).hexdigest()}"
    )

    client = await _get_redis()
    try:
        cached = await client.get(cache_key)
        if cached:
            data = json.loads(cached)
            return DashboardSummary(**data)

        cleared_states = [TransactionState.CLEARED, TransactionState.SETTLED]

        txns = (await scope.db.execute(
            select(
                Transaction.category,
                Transaction.department_id,
                Transaction.merchant,
                Transaction.amount,
            ).where(
                Transaction.org_id == scope.org_id,
                Transaction.state.in_(cleared_states),
                Transaction.occurred_at >= from_date,
                Transaction.occurred_at <= to_date,
            )
        )).all()

        total_spend = sum((t.amount for t in txns), Decimal("0"))
        txn_count = len(txns)

        # by_category
        cat_totals: dict[str, Decimal] = {}
        cat_counts: dict[str, int] = {}
        for t in txns:
            k = t.category.value
            cat_totals[k] = cat_totals.get(k, Decimal("0")) + t.amount
            cat_counts[k] = cat_counts.get(k, 0) + 1
        by_category = [
            CategorySpend(category=k, amount=v, transaction_count=cat_counts[k])
            for k, v in sorted(cat_totals.items(), key=lambda x: -x[1])
        ]

        # by_department
        dept_totals: dict[str, Decimal] = {}
        for t in txns:
            if t.department_id:
                k = str(t.department_id)
                dept_totals[k] = dept_totals.get(k, Decimal("0")) + t.amount

        dept_names: dict[str, str] = {}
        if dept_totals:
            depts = (await scope.db.execute(
                select(Department.id, Department.name).where(Department.org_id == scope.org_id)
            )).all()
            dept_names = {str(d.id): d.name for d in depts}
        by_department = [
            DepartmentSpend(
                department_id=k,
                department_name=dept_names.get(k, "Unknown"),
                amount=v,
            )
            for k, v in sorted(dept_totals.items(), key=lambda x: -x[1])
        ]

        # top merchants
        merch_totals: dict[str, Decimal] = {}
        merch_counts: dict[str, int] = {}
        for t in txns:
            merch_totals[t.merchant] = merch_totals.get(t.merchant, Decimal("0")) + t.amount
            merch_counts[t.merchant] = merch_counts.get(t.merchant, 0) + 1
        top_merchants = [
            MerchantSpend(merchant=k, amount=v, count=merch_counts[k])
            for k, v in sorted(merch_totals.items(), key=lambda x: -x[1])[:10]
        ]

        # MoM delta — compare same-length window before from_date
        window = to_date - from_date
        prior_from = from_date - window - timedelta(seconds=1)
        prior_to = from_date - timedelta(seconds=1)
        prior_spend_result = (await scope.db.execute(
            select(func.coalesce(func.sum(Transaction.amount), Decimal("0"))).where(
                Transaction.org_id == scope.org_id,
                Transaction.state.in_(cleared_states),
                Transaction.occurred_at >= prior_from,
                Transaction.occurred_at <= prior_to,
            )
        )).scalar_one()
        prior_spend = Decimal(str(prior_spend_result))
        mom_delta_pct: float | None = None
        if prior_spend > 0:
            mom_delta_pct = float((total_spend - prior_spend) / prior_spend * 100)

        # pending approvals (FLAGGED transactions awaiting FM review)
        pending = (await scope.db.execute(
            select(func.count()).select_from(Transaction).where(
                Transaction.org_id == scope.org_id,
                Transaction.state == TransactionState.FLAGGED,
            )
        )).scalar_one()

        # active cards
        active_cards = (await scope.db.execute(
            select(func.count()).select_from(Card).where(
                Card.org_id == scope.org_id,
                Card.status == CardStatus.ACTIVE,
            )
        )).scalar_one()

        summary = DashboardSummary(
            total_spend=total_spend,
            transaction_count=txn_count,
            mom_delta_pct=mom_delta_pct,
            by_category=by_category,
            by_department=by_department,
            top_merchants=top_merchants,
            pending_approvals=pending,
            active_cards=active_cards,
        )

        await client.setex(
            cache_key,
            _CACHE_TTL,
            json.dumps(summary.model_dump(), default=str),
        )
        return summary
    finally:
        await client.aclose()


async def get_timeseries(
    scope: OrgScope,
    from_date: datetime,
    to_date: datetime,
    bucket: str = "day",
) -> list[TimeseriesPoint]:
    valid_buckets = {"day", "week", "month"}
    if bucket not in valid_buckets:
        bucket = "day"

    cache_key = (
        f"dash:{scope.org_id}:ts:{bucket}:"
        f"{hashlib.md5(f'{from_date}{to_date}'.encode()).hexdigest()}"
    )

    client = await _get_redis()
    try:
        cached = await client.get(cache_key)
        if cached:
            data = json.loads(cached)
            return [TimeseriesPoint(**p) for p in data]

        rows = (await scope.db.execute(
            text("""
                SELECT date_trunc(:bucket, occurred_at AT TIME ZONE 'UTC') as period,
                       COALESCE(SUM(amount), 0) as amount
                FROM transactions
                WHERE org_id = :org_id
                  AND state IN ('CLEARED', 'SETTLED')
                  AND occurred_at >= :from_date
                  AND occurred_at <= :to_date
                GROUP BY period
                ORDER BY period
            """),
            {
                "bucket": bucket,
                "org_id": str(scope.org_id),
                "from_date": from_date,
                "to_date": to_date,
            },
        )).all()

        points = [
            TimeseriesPoint(period=str(r.period), amount=Decimal(str(r.amount)))
            for r in rows
        ]
        await client.setex(
            cache_key,
            _CACHE_TTL,
            json.dumps([p.model_dump() for p in points], default=str),
        )
        return points
    finally:
        await client.aclose()
