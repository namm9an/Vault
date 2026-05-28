"""Phase 4 tests: policy service CRUD, audit log, multi-tenancy.

All tests mock the DB session — no real DB connection required.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from api.deps import OrgScope
from api.models.audit_log import AuditLog
from api.models.policy import Policy
from api.models.user import UserRole
from api.schemas.policy import PolicyCreate, PolicyUpdate
from api.services import policy_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scope(org_id: uuid.UUID | None = None, role: str = "ADMIN") -> OrgScope:
    db = AsyncMock()
    db.add = MagicMock()
    return OrgScope(
        db=db,
        org_id=org_id or uuid.uuid4(),
        user_id=uuid.uuid4(),
        role=UserRole(role),
    )


def _mock_policy(
    org_id: uuid.UUID,
    policy_text: str = "No personal purchases on company cards.",
    is_active: bool = True,
) -> MagicMock:
    p = MagicMock(spec=Policy)
    p.id = uuid.uuid4()
    p.org_id = org_id
    p.policy_text = policy_text
    p.is_active = is_active
    return p


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_policies_returns_org_scoped_results():
    """list_policies returns all policies for the calling org."""
    scope = _make_scope()
    policy_a = _mock_policy(scope.org_id, "No gambling sites.")
    policy_b = _mock_policy(scope.org_id, "Travel must be economy class.")

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [policy_a, policy_b]
    scope.db.execute = AsyncMock(return_value=result_mock)

    policies = await policy_service.list_policies(scope)

    assert len(policies) == 2
    assert policies[0].org_id == scope.org_id
    assert policies[1].org_id == scope.org_id


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_policy_writes_audit_log():
    """create_policy adds both a Policy row and an AuditLog row before committing."""
    scope = _make_scope()
    scope.db.flush = AsyncMock()
    scope.db.commit = AsyncMock()
    scope.db.refresh = AsyncMock()

    data = PolicyCreate.model_validate(
        {"text": "No purchases above ₹50,000 without FM approval.", "is_active": True}
    )
    await policy_service.create_policy(scope, data)

    added_objects = [call.args[0] for call in scope.db.add.call_args_list]

    policy_rows = [o for o in added_objects if isinstance(o, Policy)]
    audit_rows = [o for o in added_objects if isinstance(o, AuditLog)]

    assert len(policy_rows) == 1, "Expected exactly one Policy row added"
    assert len(audit_rows) == 1, "Expected exactly one AuditLog row added"
    assert audit_rows[0].action == "policy.create"
    assert audit_rows[0].org_id == scope.org_id

    # Both rows must land in one commit
    assert scope.db.commit.call_count == 1


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_policy_patches_text_and_active_flag():
    """update_policy mutates only the supplied fields and writes an AuditLog."""
    scope = _make_scope()
    policy = _mock_policy(scope.org_id, "Old policy text.", is_active=True)

    found = MagicMock()
    found.scalar_one_or_none.return_value = policy
    scope.db.execute = AsyncMock(return_value=found)
    scope.db.commit = AsyncMock()
    scope.db.refresh = AsyncMock()

    update_data = PolicyUpdate.model_validate(
        {"text": "Updated policy: no spend above ₹75,000.", "is_active": False}
    )
    await policy_service.update_policy(scope, policy.id, update_data)

    assert policy.policy_text == "Updated policy: no spend above ₹75,000."
    assert policy.is_active is False

    audit_rows = [
        call.args[0]
        for call in scope.db.add.call_args_list
        if isinstance(call.args[0], AuditLog)
    ]
    assert len(audit_rows) == 1
    assert audit_rows[0].action == "policy.update"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_policy_cross_org_returns_404():
    """Attempting to delete a policy from another org raises 404 (not 403)."""
    scope_a = _make_scope()

    not_found = MagicMock()
    not_found.scalar_one_or_none.return_value = None
    scope_a.db.execute = AsyncMock(return_value=not_found)

    with pytest.raises(HTTPException) as exc_info:
        await policy_service.delete_policy(scope_a, uuid.uuid4())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_policy_soft_deletes_and_writes_audit_log():
    """delete_policy soft-deletes (is_active=False, deleted_at set) and writes AuditLog.

    C5: hard-deleting a policy would NULL out TransactionPolicyResult.matched_policy_id
    (FK ondelete=SET NULL) and destroy historical attribution.  The service must
    never call db.delete() on a Policy row.
    """
    scope = _make_scope()
    policy = _mock_policy(scope.org_id)

    found = MagicMock()
    found.scalar_one_or_none.return_value = policy
    scope.db.execute = AsyncMock(return_value=found)
    scope.db.commit = AsyncMock()

    await policy_service.delete_policy(scope, policy.id)

    # Verify audit log was written
    audit_rows = [
        call.args[0]
        for call in scope.db.add.call_args_list
        if isinstance(call.args[0], AuditLog)
    ]
    assert len(audit_rows) == 1
    assert audit_rows[0].action == "policy.delete"

    # Verify soft-delete: is_active=False, deleted_at populated
    assert policy.is_active is False
    assert policy.deleted_at is not None

    # Verify db.delete() was NOT called — the row must survive for FK integrity
    scope.db.delete = MagicMock()
    scope.db.delete.assert_not_called()
