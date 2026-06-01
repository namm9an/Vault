import secrets
import string
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from api.deps import OrgScope
from api.models.audit_log import AuditLog
from api.models.card import Card, CardStatus
from api.models.department import Department
from api.models.user import User
from api.schemas.card import CardCreate, CardUpdate


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _random_last_four() -> str:
    # Use secrets module (CSPRNG) — random.choices is Mersenne Twister, not suitable here
    return "".join(secrets.choice(string.digits) for _ in range(4))


def _get_card_or_404(card: Card | None) -> Card:
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "card not found")
    return card


async def _load_card(scope: OrgScope, card_id: UUID) -> Card:
    row = (
        await scope.db.execute(
            select(Card).where(Card.id == card_id, Card.org_id == scope.org_id)
        )
    ).scalar_one_or_none()
    return _get_card_or_404(row)


async def _write_audit(
    scope: OrgScope,
    action: str,
    entity_id: UUID,
    meta: dict,
    entity_type: str = "card",
) -> None:
    scope.db.add(
        AuditLog(
            org_id=scope.org_id,
            actor_user_id=scope.user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            log_metadata=meta,
        )
    )


async def list_cards(scope: OrgScope) -> list[Card]:
    q = select(Card).where(Card.org_id == scope.org_id)
    if scope.role.value == "EMPLOYEE":
        q = q.where(Card.user_id == scope.user_id)
    q = q.order_by(Card.created_at.desc())
    result = await scope.db.execute(q)
    return list(result.scalars().all())


async def get_card(scope: OrgScope, card_id: UUID) -> Card:
    card = await _load_card(scope, card_id)
    # EMPLOYEE can only view own card
    if scope.role.value == "EMPLOYEE" and card.user_id != scope.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "card not found")
    return card


async def create_card(scope: OrgScope, data: CardCreate) -> Card:
    # Verify the target user belongs to this org — prevents ADMIN of Org A
    # assigning a card to a user from Org B
    target_user = (
        await scope.db.execute(
            select(User).where(User.id == data.user_id, User.org_id == scope.org_id)
        )
    ).scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found in this org")

    # Verify department belongs to this org if provided
    if data.department_id is not None:
        dept = (
            await scope.db.execute(
                select(Department).where(
                    Department.id == data.department_id,
                    Department.org_id == scope.org_id,
                )
            )
        ).scalar_one_or_none()
        if dept is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "department not found in this org")

    card = Card(
        org_id=scope.org_id,
        user_id=data.user_id,
        department_id=data.department_id,
        nickname=data.nickname,
        last_four=_random_last_four(),
        daily_limit=data.daily_limit,
        monthly_limit=data.monthly_limit,
        total_limit=data.total_limit,
        category_restrictions=data.category_restrictions,
        currency=data.currency,
    )
    scope.db.add(card)
    # Flush to get DB-generated card.id without committing, then audit in the same transaction
    await scope.db.flush()
    await _write_audit(scope, "card.create", card.id, {
        "nickname": card.nickname,
        "user_id": str(card.user_id),
        "daily_limit": str(card.daily_limit),
        "monthly_limit": str(card.monthly_limit),
    })
    await scope.db.commit()
    await scope.db.refresh(card)
    return card


async def update_card(scope: OrgScope, card_id: UUID, data: CardUpdate) -> Card:
    card = await _load_card(scope, card_id)
    if card.status == CardStatus.CANCELLED:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "cannot update a cancelled card")
    update_data = data.model_dump(exclude_unset=True)

    # Validate that a new department_id, if provided, belongs to this org.
    # Setting department_id=null (removing) is always allowed.
    if "department_id" in update_data and update_data["department_id"] is not None:
        dept = (
            await scope.db.execute(
                select(Department).where(
                    Department.id == update_data["department_id"],
                    Department.org_id == scope.org_id,
                )
            )
        ).scalar_one_or_none()
        if dept is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "department not found in this org")

    for field, value in update_data.items():
        setattr(card, field, value)
    # Serialize for audit (values may be Decimal / enum / list)
    await _write_audit(scope, "card.update", card_id, {k: str(v) for k, v in update_data.items()})
    await scope.db.commit()
    await scope.db.refresh(card)
    return card


async def freeze_card(scope: OrgScope, card_id: UUID) -> Card:
    card = await _load_card(scope, card_id)
    if card.status == CardStatus.CANCELLED:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "cannot freeze a cancelled card")
    if card.status == CardStatus.FROZEN:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "card is already frozen")
    prev = card.status.value
    card.status = CardStatus.FROZEN
    card.frozen_at = _now()
    await _write_audit(scope, "card.freeze", card_id, {"previous_status": prev, "new_status": "FROZEN"})
    await scope.db.commit()
    await scope.db.refresh(card)
    return card


async def unfreeze_card(scope: OrgScope, card_id: UUID) -> Card:
    card = await _load_card(scope, card_id)
    if card.status == CardStatus.CANCELLED:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "cannot unfreeze a cancelled card")
    if card.status == CardStatus.ACTIVE:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "card is already active")
    prev = card.status.value
    card.status = CardStatus.ACTIVE
    card.frozen_at = None
    await _write_audit(scope, "card.unfreeze", card_id, {"previous_status": prev, "new_status": "ACTIVE"})
    await scope.db.commit()
    await scope.db.refresh(card)
    return card


async def delete_card(scope: OrgScope, card_id: UUID) -> None:
    card = await _load_card(scope, card_id)
    if card.status != CardStatus.CANCELLED:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "only cancelled cards can be deleted")
    await scope.db.delete(card)
    await scope.db.commit()


async def cancel_card(scope: OrgScope, card_id: UUID) -> Card:
    card = await _load_card(scope, card_id)
    if card.status == CardStatus.CANCELLED:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "card is already cancelled")
    prev = card.status.value
    card.status = CardStatus.CANCELLED
    card.cancelled_at = _now()
    await _write_audit(scope, "card.cancel", card_id, {"previous_status": prev, "new_status": "CANCELLED"})
    await scope.db.commit()
    await scope.db.refresh(card)
    return card
