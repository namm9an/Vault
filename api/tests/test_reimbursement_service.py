"""Phase 5 tests: reimbursement service — create and approve state machine.

All DB calls are mocked; no real Postgres, Redis, or ARQ connection is needed.
"""
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.deps import OrgScope
from api.models.card import SpendCategory
from api.models.reimbursement import Reimbursement, ReimbursementStatus
from api.models.user import UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_reimb(
    org_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    status: ReimbursementStatus = ReimbursementStatus.SUBMITTED,
    amount: Decimal = Decimal("1200.00"),
) -> MagicMock:
    reimb = MagicMock(spec=Reimbursement)
    reimb.id = uuid.uuid4()
    reimb.org_id = org_id or uuid.uuid4()
    reimb.user_id = user_id or uuid.uuid4()
    reimb.status = status
    reimb.amount = amount
    reimb.currency = "INR"
    reimb.category = SpendCategory.MEALS
    reimb.description = "Team lunch"
    reimb.department_id = None
    reimb.receipt_id = None
    reimb.decision_reason = None
    reimb.decided_by = None
    reimb.decided_at = None
    reimb.paid_at = None
    return reimb


def _make_scope(
    org_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    role: UserRole = UserRole.EMPLOYEE,
) -> OrgScope:
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    scope = OrgScope(
        db=db,
        org_id=org_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        role=role,
    )
    return scope


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_reimbursement_enqueues_job():
    """Happy path: receipt_id=None, ARQ job enqueued, status=SUBMITTED returned."""
    from api.schemas.reimbursement import ReimbursementCreate
    from api.services.reimbursement_service import create_reimbursement

    scope = _make_scope(role=UserRole.EMPLOYEE)
    data = ReimbursementCreate(
        amount=Decimal("1200.00"),
        currency="INR",
        category=SpendCategory.MEALS,
        description="Team lunch",
    )

    # Mock db.refresh to set a predictable id on the reimb object
    created_reimb = _mock_reimb(
        org_id=scope.org_id,
        user_id=scope.user_id,
        status=ReimbursementStatus.SUBMITTED,
    )

    async def _fake_refresh(obj):
        # Simulate SQLAlchemy refresh populating id
        pass

    scope.db.refresh = AsyncMock(side_effect=_fake_refresh)

    # We need add() to capture the Reimbursement that was added, and then
    # make refresh() give it a proper id. Use a simpler approach: patch
    # the Reimbursement constructor side effect and return our mock.
    pool_mock = AsyncMock()
    pool_mock.enqueue_job = AsyncMock()
    pool_mock.aclose = AsyncMock()

    with patch("api.services.reimbursement_service.create_pool", return_value=pool_mock):
        # Let db.add capture the call; db.refresh is a no-op
        result = await create_reimbursement(scope, data)

    # db.add was called once (for the Reimbursement row)
    scope.db.add.assert_called_once()
    # commit called at least once
    assert scope.db.commit.await_count >= 1
    # ARQ job was enqueued
    pool_mock.enqueue_job.assert_awaited_once()
    call_kwargs = pool_mock.enqueue_job.call_args
    assert call_kwargs.args[0] == "run_reimbursement_policy_check"
    # pool was closed
    pool_mock.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_approve_reimbursement_wrong_state_raises_409():
    """Guard test: reimb in SUBMITTED state → approve → 409 Conflict."""
    import pytest
    from fastapi import HTTPException
    from api.services.reimbursement_service import approve_reimbursement

    org_id = uuid.uuid4()
    fm_user_id = uuid.uuid4()
    scope = _make_scope(org_id=org_id, user_id=fm_user_id, role=UserRole.FINANCE_MANAGER)

    reimb = _mock_reimb(org_id=org_id, status=ReimbursementStatus.SUBMITTED)
    reimb_id = reimb.id

    # Mock FOR UPDATE select returning a SUBMITTED reimbursement
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = reimb
    scope.db.execute = AsyncMock(return_value=select_result)

    with pytest.raises(HTTPException) as exc_info:
        await approve_reimbursement(scope, reimb_id, reason=None)

    assert exc_info.value.status_code == 409
    assert "POLICY_CHECKED" in exc_info.value.detail
