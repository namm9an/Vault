"""Phase 5 tests: department service — budget calculation and alert dedup."""
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.deps import OrgScope
from api.models.department import Department
from api.models.user import UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_dept(
    org_id: uuid.UUID | None = None,
    monthly_budget: Decimal = Decimal("100000"),
    alert_threshold_pct: int = 80,
) -> MagicMock:
    dept = MagicMock(spec=Department)
    dept.id = uuid.uuid4()
    dept.org_id = org_id or uuid.uuid4()
    dept.name = "Engineering"
    dept.monthly_budget = monthly_budget
    dept.budget_currency = "INR"
    dept.alert_threshold_pct = alert_threshold_pct
    dept.manager_id = None
    return dept


def _make_scope(org_id: uuid.UUID | None = None) -> OrgScope:
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    scope = OrgScope(
        db=db,
        org_id=org_id or uuid.uuid4(),
        user_id=uuid.uuid4(),
        role=UserRole.FINANCE_MANAGER,
    )
    return scope


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_budget_status_utilization_calc():
    """Given a known spend amount, verify utilization_pct is calculated correctly."""
    from api.services.department_service import get_budget_status

    org_id = uuid.uuid4()
    scope = _make_scope(org_id=org_id)
    dept = _mock_dept(org_id=org_id, monthly_budget=Decimal("100000"), alert_threshold_pct=80)
    dept_id = dept.id

    # First execute: department lookup
    dept_result = MagicMock()
    dept_result.scalar_one_or_none.return_value = dept

    # Second execute: spent aggregation — returns 50000
    spent_result = MagicMock()
    spent_result.scalar_one.return_value = Decimal("50000.00")

    scope.db.execute = AsyncMock(side_effect=[dept_result, spent_result])

    # 50% < 80% threshold — Redis block is never entered; no mock needed
    # but patch anyway to ensure no real Redis call is made
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.aclose = AsyncMock()

    with patch("api.services.department_service.aioredis.from_url", return_value=redis_mock):
        result = await get_budget_status(scope, dept_id)

    assert result.spent == Decimal("50000.00")
    assert result.monthly_budget == Decimal("100000")
    assert result.utilization_pct == pytest.approx(50.0)
    assert result.remaining == Decimal("50000.00")
    assert result.is_over_threshold is False  # 50% < 80% threshold


@pytest.mark.asyncio
async def test_budget_alert_dedup():
    """First call fires alert; second call (Redis key exists) does NOT fire again.

    New logic (H2 fix): GET key first → if None, commit notification then SET NX.
    """
    from api.services.department_service import get_budget_status
    from api.models.notification import NotificationType

    org_id = uuid.uuid4()
    scope1 = _make_scope(org_id=org_id)
    scope2 = _make_scope(org_id=org_id)
    dept = _mock_dept(org_id=org_id, monthly_budget=Decimal("100000"), alert_threshold_pct=80)
    dept_id = dept.id

    # Both scopes return same dept + 90000 spent (90% > 80% threshold)
    def _make_db_side_effects():
        dept_r = MagicMock()
        dept_r.scalar_one_or_none.return_value = dept
        spent_r = MagicMock()
        spent_r.scalar_one.return_value = Decimal("90000.00")
        return [dept_r, spent_r]

    scope1.db.execute = AsyncMock(side_effect=_make_db_side_effects())
    scope2.db.execute = AsyncMock(side_effect=_make_db_side_effects())

    # First call: GET returns None (key absent) → notify fires → SET NX records key
    redis_first = AsyncMock()
    redis_first.get = AsyncMock(return_value=None)
    redis_first.set = AsyncMock(return_value=1)
    redis_first.aclose = AsyncMock()

    # Second call: GET returns b"1" (key present) → dedup skips notify entirely
    redis_second = AsyncMock()
    redis_second.get = AsyncMock(return_value=b"1")
    redis_second.set = AsyncMock(return_value=None)
    redis_second.aclose = AsyncMock()

    with patch(
        "api.services.department_service.notify_all_fms", new_callable=AsyncMock
    ) as mock_notify:
        with patch(
            "api.services.department_service.aioredis.from_url",
            side_effect=[redis_first, redis_second],
        ):
            await get_budget_status(scope1, dept_id)
            await get_budget_status(scope2, dept_id)

    # notify_all_fms should be called only once (first call)
    assert mock_notify.await_count == 1
    notify_kwargs = mock_notify.call_args.kwargs
    assert notify_kwargs["notification_type"] == NotificationType.BUDGET_THRESHOLD
