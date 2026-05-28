"""Phase 5 tests: dashboard service — aggregation and Redis cache hit."""
import json
import uuid
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.deps import OrgScope
from api.models.card import SpendCategory
from api.models.user import UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scope(org_id: uuid.UUID | None = None) -> OrgScope:
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    scope = OrgScope(
        db=db,
        org_id=org_id or uuid.uuid4(),
        user_id=uuid.uuid4(),
        role=UserRole.ADMIN,
    )
    return scope


def _make_txn_row(
    category: SpendCategory,
    department_id: uuid.UUID | None,
    merchant: str,
    amount: Decimal,
):
    row = MagicMock()
    row.category = category
    row.department_id = department_id
    row.merchant = merchant
    row.amount = amount
    return row


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summary_aggregates_totals():
    """Mock db.execute to return known transaction rows, verify total_spend and by_category."""
    from api.services.dashboard_service import get_summary

    org_id = uuid.uuid4()
    scope = _make_scope(org_id=org_id)

    dept_id = uuid.uuid4()
    txn_rows = [
        _make_txn_row(SpendCategory.MEALS, None, "Blue Tokai", Decimal("500.00")),
        _make_txn_row(SpendCategory.MEALS, None, "Blue Tokai", Decimal("700.00")),
        _make_txn_row(SpendCategory.SAAS, dept_id, "GitHub", Decimal("8900.00")),
    ]

    # Execute call order:
    # 1. Main txn select
    # 2. Department names (because dept_id is non-null)
    # 3. Prior period spend (MoM delta)
    # 4. Pending approvals count
    # 5. Active cards count
    txns_result = MagicMock()
    txns_result.all.return_value = txn_rows

    dept_row = MagicMock()
    dept_row.id = dept_id
    dept_row.name = "Engineering"
    dept_names_result = MagicMock()
    dept_names_result.all.return_value = [dept_row]

    prior_result = MagicMock()
    prior_result.scalar_one.return_value = Decimal("0")

    pending_result = MagicMock()
    pending_result.scalar_one.return_value = 2

    cards_result = MagicMock()
    cards_result.scalar_one.return_value = 4

    scope.db.execute = AsyncMock(side_effect=[
        txns_result, dept_names_result, prior_result, pending_result, cards_result,
    ])

    # Redis: cache miss on get, setex succeeds
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.setex = AsyncMock()
    redis_mock.aclose = AsyncMock()

    from_date = datetime.now(timezone.utc) - timedelta(days=30)
    to_date = datetime.now(timezone.utc)

    with patch("api.services.dashboard_service.aioredis.from_url", return_value=redis_mock):
        result = await get_summary(scope, from_date, to_date)

    assert result.total_spend == Decimal("10100.00")
    assert result.transaction_count == 3
    assert result.mom_delta_pct is None  # prior_spend = 0

    # by_category: SAAS 8900 > MEALS 1200
    assert result.by_category[0].category == "SAAS"
    assert result.by_category[0].amount == Decimal("8900.00")
    assert result.by_category[1].category == "MEALS"
    assert result.by_category[1].amount == Decimal("1200.00")

    assert result.pending_approvals == 2
    assert result.active_cards == 4


@pytest.mark.asyncio
async def test_summary_cache_hit():
    """Cache hit: Redis returns pre-serialized JSON; db.execute should NOT be called."""
    from api.services.dashboard_service import get_summary
    from api.schemas.dashboard import DashboardSummary

    org_id = uuid.uuid4()
    scope = _make_scope(org_id=org_id)

    cached_summary = DashboardSummary(
        total_spend=Decimal("99999.00"),
        transaction_count=42,
        mom_delta_pct=5.5,
        by_category=[],
        by_department=[],
        top_merchants=[],
        pending_approvals=3,
        active_cards=7,
    )
    cached_json = json.dumps(cached_summary.model_dump(), default=str).encode()

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=cached_json)
    redis_mock.aclose = AsyncMock()

    from_date = datetime.now(timezone.utc) - timedelta(days=30)
    to_date = datetime.now(timezone.utc)

    with patch("api.services.dashboard_service.aioredis.from_url", return_value=redis_mock):
        result = await get_summary(scope, from_date, to_date)

    # Cache hit — db.execute must NOT have been called
    scope.db.execute.assert_not_called()
    assert result.total_spend == Decimal("99999.00")
    assert result.transaction_count == 42
    assert result.pending_approvals == 3
