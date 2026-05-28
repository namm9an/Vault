"""Phase 3 tests: transaction state machine, RBAC, multi-tenancy, event audit trail.

All tests mock the DB session — no real DB connection required.
Follows the same AsyncMock/MagicMock pattern as test_multitenancy.py.
"""
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from api.deps import CurrentUser, OrgScope
from api.models.card import Card, CardStatus, SpendCategory
from api.models.transaction import (
    Transaction,
    TransactionEvent,
    TransactionPolicyResult,
    TransactionState,
    PolicyVerdict,
)
from api.models.user import UserRole
from api.schemas.transaction import TransactionCreate, TransactionFilters
from api.services import transaction_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scope(org_id: uuid.UUID | None = None, role: str = "ADMIN") -> OrgScope:
    db = AsyncMock()
    # SQLAlchemy session.add() is synchronous; override so calls don't produce
    # unawaited-coroutine warnings in tests that inspect db.add.call_args_list.
    db.add = MagicMock()
    return OrgScope(
        db=db,
        org_id=org_id or uuid.uuid4(),
        user_id=uuid.uuid4(),
        role=UserRole(role),
    )


def _mock_card(
    org_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    status: CardStatus = CardStatus.ACTIVE,
) -> MagicMock:
    card = MagicMock(spec=Card)
    card.id = uuid.uuid4()
    card.org_id = org_id
    card.user_id = user_id or uuid.uuid4()
    card.status = status
    return card


def _mock_txn(
    org_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    txn_id: uuid.UUID | None = None,
    state: TransactionState = TransactionState.INITIATED,
) -> MagicMock:
    txn = MagicMock(spec=Transaction)
    txn.id = txn_id or uuid.uuid4()
    txn.org_id = org_id
    txn.user_id = user_id or uuid.uuid4()
    txn.state = state
    return txn


# ---------------------------------------------------------------------------
# State machine — legal and illegal transitions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_legal_transitions():
    """INITIATED→POLICY_CHECKED→APPROVED→CLEARED all succeed."""
    scope = _make_scope()
    txn = _mock_txn(scope.org_id, scope.user_id)
    txn.state = TransactionState.INITIATED

    await transaction_service.transition(scope, txn, TransactionState.POLICY_CHECKED, triggered_by_system=True)
    assert txn.state == TransactionState.POLICY_CHECKED

    await transaction_service.transition(scope, txn, TransactionState.APPROVED, triggered_by_system=True)
    assert txn.state == TransactionState.APPROVED

    await transaction_service.transition(scope, txn, TransactionState.CLEARED, triggered_by_system=True)
    assert txn.state == TransactionState.CLEARED


@pytest.mark.asyncio
async def test_illegal_transition_raises_409():
    """INITIATED→APPROVED is not in LEGAL_TRANSITIONS — must raise 409."""
    scope = _make_scope()
    txn = _mock_txn(scope.org_id, scope.user_id)
    txn.state = TransactionState.INITIATED

    with pytest.raises(HTTPException) as exc_info:
        await transaction_service.transition(scope, txn, TransactionState.APPROVED, triggered_by_system=True)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_terminal_state_blocked_raises_409():
    """BLOCKED is terminal — any outgoing transition raises 409."""
    scope = _make_scope()
    txn = _mock_txn(scope.org_id, scope.user_id, state=TransactionState.BLOCKED)

    with pytest.raises(HTTPException) as exc_info:
        await transaction_service.transition(scope, txn, TransactionState.CLEARED, triggered_by_system=True)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_terminal_state_settled_raises_409():
    """SETTLED is terminal — any outgoing transition raises 409."""
    scope = _make_scope()
    txn = _mock_txn(scope.org_id, scope.user_id, state=TransactionState.SETTLED)

    with pytest.raises(HTTPException) as exc_info:
        await transaction_service.transition(scope, txn, TransactionState.CLEARED, triggered_by_system=True)
    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_employee_create_own_card_txn_succeeds():
    """EMPLOYEE creating a transaction on their own ACTIVE card succeeds."""
    scope = _make_scope(role="EMPLOYEE")
    card = _mock_card(scope.org_id, user_id=scope.user_id, status=CardStatus.ACTIVE)

    card_found = MagicMock()
    card_found.scalar_one_or_none.return_value = card
    scope.db.execute = AsyncMock(return_value=card_found)
    scope.db.flush = AsyncMock()
    scope.db.commit = AsyncMock()
    scope.db.refresh = AsyncMock()

    payload = TransactionCreate(
        card_id=card.id,
        amount=Decimal("150.00"),
        merchant="Café Coffee Day",
        category=SpendCategory.MEALS,
    )
    result = await transaction_service.create_transaction(scope, payload)
    # Service returns the txn object (refreshed mock — just verify no exception)
    assert result is not None


@pytest.mark.asyncio
async def test_employee_create_other_card_raises_404():
    """EMPLOYEE creating a transaction on another user's card raises 404.

    Must be 404 not 403 — returning 403 leaks that the card exists (C1).
    Project rule: cross-resource access returns 404, never 403.
    """
    scope = _make_scope(role="EMPLOYEE")
    other_user_id = uuid.uuid4()
    card = _mock_card(scope.org_id, user_id=other_user_id, status=CardStatus.ACTIVE)

    card_found = MagicMock()
    card_found.scalar_one_or_none.return_value = card
    scope.db.execute = AsyncMock(return_value=card_found)

    payload = TransactionCreate(
        card_id=card.id,
        amount=Decimal("100.00"),
        merchant="Stealth Corp",
        category=SpendCategory.OTHER,
    )
    with pytest.raises(HTTPException) as exc_info:
        await transaction_service.create_transaction(scope, payload)
    assert exc_info.value.status_code == 404


def test_employee_cannot_approve():
    """EMPLOYEE role is blocked at the route layer via require_role."""
    from api.deps import require_role

    checker = require_role(UserRole.ADMIN, UserRole.FINANCE_MANAGER)
    employee_cu = CurrentUser(
        user_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        role=UserRole.EMPLOYEE,
    )
    # checker is the _checker function returned by require_role.
    # Calling it directly with a CurrentUser bypasses FastAPI Depends resolution
    # and hits the role-check logic immediately.
    with pytest.raises(HTTPException) as exc_info:
        checker(employee_cu)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_fm_can_approve_flagged():
    """FINANCE_MANAGER approving a FLAGGED transaction → state becomes CLEARED."""
    scope = _make_scope(role="FINANCE_MANAGER")
    txn = _mock_txn(scope.org_id, scope.user_id, state=TransactionState.FLAGGED)

    txn_found = MagicMock()
    txn_found.scalar_one_or_none.return_value = txn
    scope.db.execute = AsyncMock(return_value=txn_found)
    scope.db.commit = AsyncMock()
    scope.db.refresh = AsyncMock()

    await transaction_service.approve_transaction(scope, txn.id, reason="Reviewed and approved")
    # FLAGGED → APPROVED → CLEARED
    assert txn.state == TransactionState.CLEARED


# ---------------------------------------------------------------------------
# Multi-tenancy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_txn_cross_org_returns_404():
    """A transaction from Org B is invisible to Org A scope → 404."""
    scope_a = _make_scope()
    txn_b_id = uuid.uuid4()

    not_found = MagicMock()
    not_found.scalar_one_or_none.return_value = None
    scope_a.db.execute = AsyncMock(return_value=not_found)

    with pytest.raises(HTTPException) as exc_info:
        await transaction_service.get_transaction(scope_a, txn_b_id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_create_txn_cross_org_card_returns_404():
    """Creating a transaction with a card_id from another org → 404."""
    scope = _make_scope()

    not_found = MagicMock()
    not_found.scalar_one_or_none.return_value = None
    scope.db.execute = AsyncMock(return_value=not_found)

    payload = TransactionCreate(
        card_id=uuid.uuid4(),
        amount=Decimal("500.00"),
        merchant="Cross-org Corp",
        category=SpendCategory.OTHER,
    )
    with pytest.raises(HTTPException) as exc_info:
        await transaction_service.create_transaction(scope, payload)
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Event audit trail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_transaction_writes_events():
    """create_transaction writes exactly 4 events: INITIATED, POLICY_CHECKED, APPROVED, CLEARED."""
    scope = _make_scope()
    card = _mock_card(scope.org_id, user_id=scope.user_id, status=CardStatus.ACTIVE)

    card_found = MagicMock()
    card_found.scalar_one_or_none.return_value = card
    scope.db.execute = AsyncMock(return_value=card_found)
    scope.db.flush = AsyncMock()
    scope.db.commit = AsyncMock()
    scope.db.refresh = AsyncMock()

    payload = TransactionCreate(
        card_id=card.id,
        amount=Decimal("250.00"),
        merchant="AWS",
        category=SpendCategory.SAAS,
    )
    await transaction_service.create_transaction(scope, payload)

    # Inspect all add() calls — filter to TransactionEvent instances
    add_calls = scope.db.add.call_args_list
    event_adds = [c.args[0] for c in add_calls if isinstance(c.args[0], TransactionEvent)]

    assert len(event_adds) == 4, f"Expected 4 events, got {len(event_adds)}"
    assert event_adds[0].to_state == TransactionState.INITIATED
    assert event_adds[1].to_state == TransactionState.POLICY_CHECKED
    assert event_adds[2].to_state == TransactionState.APPROVED
    assert event_adds[3].to_state == TransactionState.CLEARED

    # M5: all 4 events + policy result + audit log must land in exactly one commit
    assert scope.db.commit.call_count == 1, (
        f"Expected 1 commit, got {scope.db.commit.call_count} — "
        "create_transaction must commit once atomically"
    )


@pytest.mark.asyncio
async def test_reject_flagged_writes_blocked_event():
    """Rejecting a FLAGGED transaction writes a BLOCKED event with the given reason."""
    scope = _make_scope()
    txn = _mock_txn(scope.org_id, scope.user_id, state=TransactionState.FLAGGED)

    txn_found = MagicMock()
    txn_found.scalar_one_or_none.return_value = txn
    scope.db.execute = AsyncMock(return_value=txn_found)
    scope.db.commit = AsyncMock()
    scope.db.refresh = AsyncMock()

    rejection_reason = "Exceeds monthly budget policy"
    await transaction_service.reject_transaction(scope, txn.id, reason=rejection_reason)

    assert txn.state == TransactionState.BLOCKED

    # Find the BLOCKED event
    add_calls = scope.db.add.call_args_list
    blocked_events = [
        c.args[0]
        for c in add_calls
        if isinstance(c.args[0], TransactionEvent)
        and c.args[0].to_state == TransactionState.BLOCKED
    ]
    assert len(blocked_events) == 1
    assert blocked_events[0].reason == rejection_reason
    assert blocked_events[0].from_state == TransactionState.FLAGGED


# ---------------------------------------------------------------------------
# M6 — EMPLOYEE cannot bypass user_id filter via query param
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_employee_user_id_filter_is_ignored():
    """?user_id=<other_id> must be silently ignored for EMPLOYEE scope.

    The service must scope to scope.user_id, NOT to filters.user_id.
    This prevents an EMPLOYEE reading another user's transactions via a crafted URL.
    """
    scope = _make_scope(role="EMPLOYEE")
    other_user_id = uuid.uuid4()

    executed_statements: list = []

    async def fake_execute(stmt, *args, **kwargs):
        executed_statements.append(stmt)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        return mock_result

    scope.db.execute = fake_execute

    filters = TransactionFilters(user_id=other_user_id)
    await transaction_service.list_transactions(scope, filters)

    assert len(executed_statements) == 1, "Expected exactly one DB query"

    # Compile the query to SQL text with bound parameters inlined
    from sqlalchemy.dialects import postgresql
    compiled = executed_statements[0].compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    )
    sql_text = str(compiled)

    # The query must reference scope.user_id (the EMPLOYEE's own ID)
    assert str(scope.user_id) in sql_text, (
        "scope.user_id must appear in the WHERE clause for EMPLOYEE"
    )
    # The query must NOT reference the other user's ID
    assert str(other_user_id) not in sql_text, (
        "filters.user_id must be ignored for EMPLOYEE — found it in the query"
    )
