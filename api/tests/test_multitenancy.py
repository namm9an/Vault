"""Multi-tenancy tests: mutation paths must reject cross-org foreign keys.

Rules enforced:
- Read/update/delete on a resource from another org → 404 (don't leak existence).
- POST /cards with user_id or department_id from another org → 404.
- PATCH /cards with department_id from another org → 404.
- POST /users (invite) with department_id from another org → 404.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from api.deps import OrgScope
from api.models.card import Card, CardStatus
from api.models.user import UserRole
from api.services import card_service, user_service


def _make_scope(org_id: uuid.UUID | None = None, role: str = "ADMIN") -> OrgScope:
    return OrgScope(
        db=AsyncMock(),
        org_id=org_id or uuid.uuid4(),
        user_id=uuid.uuid4(),
        role=UserRole(role),
    )


def _mock_card(org_id: uuid.UUID, card_id: uuid.UUID | None = None) -> MagicMock:
    card = MagicMock(spec=Card)
    card.id = card_id or uuid.uuid4()
    card.org_id = org_id
    card.status = CardStatus.ACTIVE
    card.user_id = uuid.uuid4()
    return card


# Org A scope + card belonging to Org B
@pytest.mark.asyncio
async def test_get_card_cross_org_returns_404():
    scope_a = _make_scope()
    card_b_id = uuid.uuid4()

    # DB returns None because the WHERE clause includes org_id = scope_a.org_id
    scalar = MagicMock()
    scalar.scalar_one_or_none.return_value = None
    scope_a.db.execute = AsyncMock(return_value=scalar)

    with pytest.raises(HTTPException) as exc_info:
        await card_service.get_card(scope_a, card_b_id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_freeze_card_cross_org_returns_404():
    scope_a = _make_scope()
    card_b_id = uuid.uuid4()

    scalar = MagicMock()
    scalar.scalar_one_or_none.return_value = None
    scope_a.db.execute = AsyncMock(return_value=scalar)

    with pytest.raises(HTTPException) as exc_info:
        await card_service.freeze_card(scope_a, card_b_id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_unfreeze_card_cross_org_returns_404():
    scope_a = _make_scope()
    card_b_id = uuid.uuid4()

    scalar = MagicMock()
    scalar.scalar_one_or_none.return_value = None
    scope_a.db.execute = AsyncMock(return_value=scalar)

    with pytest.raises(HTTPException) as exc_info:
        await card_service.unfreeze_card(scope_a, card_b_id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_cancel_card_cross_org_returns_404():
    scope_a = _make_scope()
    card_b_id = uuid.uuid4()

    scalar = MagicMock()
    scalar.scalar_one_or_none.return_value = None
    scope_a.db.execute = AsyncMock(return_value=scalar)

    with pytest.raises(HTTPException) as exc_info:
        await card_service.cancel_card(scope_a, card_b_id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_card_cross_org_returns_404():
    from api.schemas.card import CardUpdate
    scope_a = _make_scope()
    card_b_id = uuid.uuid4()

    scalar = MagicMock()
    scalar.scalar_one_or_none.return_value = None
    scope_a.db.execute = AsyncMock(return_value=scalar)

    with pytest.raises(HTTPException) as exc_info:
        await card_service.update_card(scope_a, card_b_id, CardUpdate(nickname="hacked"))
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_employee_cannot_see_other_users_card():
    """EMPLOYEE scoped query filters by user_id — another user's card = 404."""
    user_a_id = uuid.uuid4()
    org_id = uuid.uuid4()
    scope = OrgScope(db=AsyncMock(), org_id=org_id, user_id=user_a_id, role=UserRole.EMPLOYEE)

    # Card belongs to same org but different user
    card = _mock_card(org_id)
    card.user_id = uuid.uuid4()  # different user

    scalar = MagicMock()
    scalar.scalar_one_or_none.return_value = card
    scope.db.execute = AsyncMock(return_value=scalar)

    with pytest.raises(HTTPException) as exc_info:
        await card_service.get_card(scope, card.id)
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Mutation paths — cross-org foreign key rejection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_card_cross_org_user_id_returns_404():
    """POST /cards with a user_id belonging to another org must return 404."""
    from api.schemas.card import CardCreate
    scope_a = _make_scope()

    # User lookup returns None: user not found in scope_a's org
    not_found = MagicMock()
    not_found.scalar_one_or_none.return_value = None
    scope_a.db.execute = AsyncMock(return_value=not_found)

    payload = CardCreate(user_id=uuid.uuid4(), nickname="stealth card")
    with pytest.raises(HTTPException) as exc_info:
        await card_service.create_card(scope_a, payload)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_create_card_cross_org_department_returns_404():
    """POST /cards with a department_id from another org must return 404."""
    from api.schemas.card import CardCreate
    scope_a = _make_scope()

    # First call: user found (belongs to this org)
    user_found = MagicMock()
    user_found.scalar_one_or_none.return_value = MagicMock()

    # Second call: department not found (cross-org)
    dept_not_found = MagicMock()
    dept_not_found.scalar_one_or_none.return_value = None

    scope_a.db.execute = AsyncMock(side_effect=[user_found, dept_not_found])

    payload = CardCreate(
        user_id=uuid.uuid4(),
        nickname="stealth card",
        department_id=uuid.uuid4(),
    )
    with pytest.raises(HTTPException) as exc_info:
        await card_service.create_card(scope_a, payload)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_card_cross_org_department_returns_404():
    """PATCH /cards/{id} with a department_id from another org must return 404."""
    from api.schemas.card import CardUpdate
    scope_a = _make_scope()
    card_id = uuid.uuid4()

    # First call: _load_card → card found in this org (ACTIVE)
    card = _mock_card(scope_a.org_id, card_id)
    card_found = MagicMock()
    card_found.scalar_one_or_none.return_value = card

    # Second call: department lookup → not in this org
    dept_not_found = MagicMock()
    dept_not_found.scalar_one_or_none.return_value = None

    scope_a.db.execute = AsyncMock(side_effect=[card_found, dept_not_found])

    with pytest.raises(HTTPException) as exc_info:
        await card_service.update_card(scope_a, card_id, CardUpdate(department_id=uuid.uuid4()))
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_invite_user_cross_org_department_returns_404():
    """POST /users with a department_id from another org must return 404."""
    from api.schemas.user import UserInvite
    scope_a = _make_scope()

    # Department lookup returns None: not in this org
    not_found = MagicMock()
    not_found.scalar_one_or_none.return_value = None
    scope_a.db.execute = AsyncMock(return_value=not_found)

    payload = UserInvite(
        email="attacker@evil.com",
        full_name="Attacker",
        role="EMPLOYEE",
        password="password123",
        department_id=uuid.uuid4(),  # cross-org department
    )
    with pytest.raises(HTTPException) as exc_info:
        await user_service.invite_user(scope_a, payload)
    assert exc_info.value.status_code == 404
