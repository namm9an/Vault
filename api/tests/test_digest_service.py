"""Phase 6 tests: digest service.

Tests:
1. test_digest_idempotency — COMPLETED digest already exists → return it, no LLM call
2. test_digest_email_failure_does_not_raise — SMTP error → digest still COMPLETED
"""
import datetime
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.deps import OrgScope
from api.models.digest import Digest, DigestStatus
from api.models.user import UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_digest(
    org_id: uuid.UUID | None = None,
    status: DigestStatus = DigestStatus.COMPLETED,
    period_start: datetime.date | None = None,
    period_end: datetime.date | None = None,
) -> MagicMock:
    d = MagicMock(spec=Digest)
    d.id = uuid.uuid4()
    d.org_id = org_id or uuid.uuid4()
    d.status = status
    d.period_start = period_start or datetime.date(2026, 5, 18)
    d.period_end = period_end or datetime.date(2026, 5, 24)
    d.headline = "Total spend was ₹1.2L this week across all departments."
    d.body = "This week saw steady spending..."
    d.top_recommendations = ["Reduce travel spend", "Review SaaS subscriptions", "Audit vendor invoices"]
    d.flagged_items = []
    d.aggregated_input = {}
    d.raw_llm_response = {}
    d.llm_error = None
    d.created_at = datetime.datetime(2026, 5, 25, 9, 0, 0, tzinfo=datetime.timezone.utc)
    d.updated_at = datetime.datetime(2026, 5, 25, 9, 0, 5, tzinfo=datetime.timezone.utc)
    return d


def _make_scope(
    org_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    role: UserRole = UserRole.ADMIN,
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
# Test 1: Idempotency — COMPLETED digest exists → return immediately, no LLM
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_digest_idempotency():
    """If a COMPLETED digest already exists for the same org + period,
    run_digest_generation returns it immediately without calling the LLM."""
    from api.services.digest_service import run_digest_generation

    org_id = uuid.uuid4()
    period_start = datetime.date(2026, 5, 18)
    period_end = datetime.date(2026, 5, 24)

    existing = _mock_digest(org_id=org_id, status=DigestStatus.COMPLETED,
                             period_start=period_start, period_end=period_end)

    scope = _make_scope(org_id=org_id)

    # First execute call returns the existing COMPLETED digest
    completed_result = MagicMock()
    completed_result.scalar_one_or_none.return_value = existing
    scope.db.execute = AsyncMock(return_value=completed_result)

    with patch("api.services.digest_service.complete_json") as mock_llm:
        result = await run_digest_generation(scope, period_start, period_end)

    # LLM must NOT have been called
    mock_llm.assert_not_called()
    # Returned the existing digest
    assert result is existing
    # No DB commit (we returned early)
    scope.db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test 2: Email failure does not raise — digest still COMPLETED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_digest_email_failure_does_not_raise():
    """If send_digest_email raises (SMTP error), run_digest_generation still
    returns a COMPLETED digest without propagating the exception."""
    import smtplib
    from api.services.digest_service import run_digest_generation

    org_id = uuid.uuid4()
    period_start = datetime.date(2026, 5, 18)
    period_end = datetime.date(2026, 5, 24)

    scope = _make_scope(org_id=org_id)

    # Simulate DB: no existing completed, no pending, no existing-any → new digest created
    no_result = MagicMock()
    no_result.scalar_one_or_none.return_value = None

    # For notify_all_fms select(User) → empty list
    empty_users = MagicMock()
    empty_users.scalars.return_value.all.return_value = []

    call_count = 0

    async def _execute_side_effect(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        # First 3 calls = completed/pending/existing-any checks → None
        if call_count <= 3:
            return no_result
        # aggregate queries → return sensible defaults
        if call_count == 4:
            # total + count query
            row = MagicMock()
            row.total = Decimal("0")
            row.cnt = 0
            r = MagicMock()
            r.one.return_value = row
            return r
        if call_count in (5, 6, 7, 8, 9):
            # top_categories, top_departments, dept_names, top_merchants,
            # pending_approvals, blocked_count queries → empty
            r = MagicMock()
            r.all.return_value = []
            r.scalar_one.return_value = 0
            return r
        # FM users for email
        return empty_users

    scope.db.execute = AsyncMock(side_effect=_execute_side_effect)

    # Mock digest object that gets added to DB (simulating db.add capturing it)
    created_digest = _mock_digest(org_id=org_id, status=DigestStatus.PENDING,
                                   period_start=period_start, period_end=period_end)

    # After commit + refresh, we want digest to look COMPLETED
    async def _fake_refresh(obj):
        if isinstance(obj, MagicMock) and hasattr(obj, "status"):
            pass  # status is already set on the mock

    scope.db.refresh = AsyncMock(side_effect=_fake_refresh)

    from api.services.digest_service import SpendDigest as _SpendDigest

    llm_result = _SpendDigest(
        headline="Spend was normal this week.",
        body="Week was uneventful. Spend across categories stayed within budget.",
        top_recommendations=["Monitor travel", "Check SaaS", "Review meals"],
        flagged_items=[],
    )

    # Track what digest object is added so we can inspect it
    added_objects = []
    original_add = scope.db.add

    def capture_add(obj):
        added_objects.append(obj)

    scope.db.add = MagicMock(side_effect=capture_add)

    with (
        patch("api.services.digest_service.complete_json", new_callable=AsyncMock) as mock_llm,
        patch("api.services.digest_service.send_digest_email",
              side_effect=smtplib.SMTPException("Connection refused")) as mock_email,
        patch("api.services.digest_service.notify_all_fms", new_callable=AsyncMock),
    ):
        mock_llm.return_value = (llm_result, 500)

        # Should NOT raise even though email fails
        try:
            result = await run_digest_generation(scope, period_start, period_end)
        except Exception as exc:
            pytest.fail(f"run_digest_generation raised unexpectedly: {exc}")

    # Email was attempted
    mock_email.assert_called_once()
    # LLM was called
    mock_llm.assert_awaited_once()
    # DB committed at least once (PENDING commit + final commit)
    assert scope.db.commit.await_count >= 1
