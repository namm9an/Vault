"""Phase 4 tests: run_policy_check ARQ job — state transitions and notifications.

Tests mock get_session_factory, complete_json, and notify_all_fms so no
real DB, Redis, or LLM connection is required.
"""
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from api.models.notification import NotificationType
from api.models.policy import Policy
from api.models.transaction import (
    PolicyVerdict,
    Transaction,
    TransactionPolicyResult,
    TransactionState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_txn(
    org_id: uuid.UUID | None = None,
    state: TransactionState = TransactionState.POLICY_CHECKED,
    amount: Decimal = Decimal("1500.00"),
) -> MagicMock:
    txn = MagicMock(spec=Transaction)
    txn.id = uuid.uuid4()
    txn.org_id = org_id or uuid.uuid4()
    txn.state = state
    txn.amount = amount
    txn.currency = "INR"
    txn.merchant = "Acme Corp"
    txn.category = MagicMock(value="SAAS")
    txn.description = None
    return txn


def _mock_policy(org_id: uuid.UUID, text: str = "No personal purchases.") -> MagicMock:
    p = MagicMock(spec=Policy)
    p.id = uuid.uuid4()
    p.org_id = org_id
    p.policy_text = text
    p.is_active = True
    return p


def _make_db_session(txn: MagicMock, policies: list) -> AsyncMock:
    """Return an AsyncMock session that returns txn on first execute and policies on second."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    txn_result = MagicMock()
    txn_result.scalar_one_or_none.return_value = txn

    policy_result = MagicMock()
    policy_result.scalars.return_value.all.return_value = policies

    db.execute = AsyncMock(side_effect=[txn_result, policy_result])
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_active_policies_auto_approves_to_cleared():
    """If no active policies exist, the job auto-approves the transaction to CLEARED."""
    from api.jobs.policy_check import run_policy_check

    txn = _mock_txn()
    db = _make_db_session(txn, policies=[])

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch("api.jobs.policy_check.get_session_factory") as mock_factory:
        mock_factory.return_value.return_value = cm
        await run_policy_check({}, txn_id=str(txn.id))

    added_objects = [c.args[0] for c in db.add.call_args_list]
    policy_results = [o for o in added_objects if isinstance(o, TransactionPolicyResult)]
    events = [o for o in added_objects if not isinstance(o, TransactionPolicyResult)]

    assert len(policy_results) == 1
    assert policy_results[0].verdict == PolicyVerdict.APPROVED
    assert policy_results[0].llm_model == "none"

    # Should transition POLICY_CHECKED → APPROVED → CLEARED
    assert txn.state == TransactionState.CLEARED
    assert db.commit.call_count == 1


@pytest.mark.asyncio
async def test_idempotent_skip_when_not_policy_checked():
    """If the transaction is not in POLICY_CHECKED state, the job does nothing."""
    from api.jobs.policy_check import run_policy_check

    txn = _mock_txn(state=TransactionState.APPROVED)
    txn_result = MagicMock()
    txn_result.scalar_one_or_none.return_value = txn
    db = AsyncMock()
    db.execute = AsyncMock(return_value=txn_result)
    db.add = MagicMock()
    db.commit = AsyncMock()

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch("api.jobs.policy_check.get_session_factory") as mock_factory:
        mock_factory.return_value.return_value = cm
        await run_policy_check({}, txn_id=str(txn.id))

    # No DB mutations should have occurred
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_llm_error_flags_transaction_and_notifies_fms():
    """On LLM error the job flags the transaction and notifies Finance Managers."""
    from api.jobs.policy_check import run_policy_check
    from api.llm.llm_client import LLMUnavailableError

    txn = _mock_txn()
    policy = _mock_policy(txn.org_id, "No purchases above ₹10,000 without approval.")
    db = _make_db_session(txn, policies=[policy])

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("api.jobs.policy_check.get_session_factory") as mock_factory,
        patch("api.jobs.policy_check.complete_json", side_effect=LLMUnavailableError("timeout")),
        patch("api.jobs.policy_check.notify_all_fms", new_callable=AsyncMock) as mock_notify,
    ):
        mock_factory.return_value.return_value = cm
        await run_policy_check({}, txn_id=str(txn.id))

    added_objects = [c.args[0] for c in db.add.call_args_list]
    policy_results = [o for o in added_objects if isinstance(o, TransactionPolicyResult)]

    assert len(policy_results) == 1
    assert policy_results[0].verdict == PolicyVerdict.FLAGGED
    assert txn.state == TransactionState.FLAGGED

    mock_notify.assert_awaited_once()
    notify_kwargs = mock_notify.call_args.kwargs
    assert notify_kwargs["notification_type"] == NotificationType.POLICY_FLAGGED
    assert notify_kwargs["org_id"] == txn.org_id


@pytest.mark.asyncio
async def test_blocked_verdict_transitions_to_blocked_and_notifies():
    """BLOCKED verdict from the LLM transitions the transaction to BLOCKED state."""
    from api.jobs.policy_check import run_policy_check
    from api.llm.schemas import PolicyCheckResult

    txn = _mock_txn()
    policy = _mock_policy(txn.org_id, "No gambling or adult content vendors.")
    db = _make_db_session(txn, policies=[policy])

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)

    llm_result = PolicyCheckResult(
        verdict="BLOCKED",
        reason="Merchant is a known gambling vendor.",
        policy_matched="No gambling or adult content vendors.",
        requires_approval_from=None,
    )

    with (
        patch("api.jobs.policy_check.get_session_factory") as mock_factory,
        patch("api.jobs.policy_check.complete_json", new_callable=AsyncMock, return_value=(llm_result, 240)),
        patch("api.jobs.policy_check.notify_all_fms", new_callable=AsyncMock) as mock_notify,
    ):
        mock_factory.return_value.return_value = cm
        await run_policy_check({}, txn_id=str(txn.id))

    added_objects = [c.args[0] for c in db.add.call_args_list]
    policy_results = [o for o in added_objects if isinstance(o, TransactionPolicyResult)]

    assert len(policy_results) == 1
    assert policy_results[0].verdict == PolicyVerdict.BLOCKED
    assert policy_results[0].llm_latency_ms == 240
    assert txn.state == TransactionState.BLOCKED

    mock_notify.assert_awaited_once()
    assert mock_notify.call_args.kwargs["notification_type"] == NotificationType.POLICY_BLOCKED
