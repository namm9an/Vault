from uuid import UUID

from fastapi import APIRouter, Depends

from api.deps import OrgScope, get_org_scope, require_role
from api.models.user import UserRole
from api.schemas.auth import OkResponse
from api.schemas.card import CardCreate, CardResponse, CardUpdate, CardOut
from api.services import card_service

router = APIRouter(prefix="/cards", tags=["cards"])

_admin = require_role(UserRole.ADMIN)
_admin_or_fm = require_role(UserRole.ADMIN, UserRole.FINANCE_MANAGER)


@router.get("", response_model=list[CardOut])
async def list_cards(scope: OrgScope = Depends(get_org_scope)) -> list[CardOut]:
    cards = await card_service.list_cards(scope)
    return [CardOut.model_validate(c) for c in cards]


@router.post("", response_model=CardResponse, status_code=201, dependencies=[Depends(_admin)])
async def create_card(
    body: CardCreate,
    scope: OrgScope = Depends(get_org_scope),
) -> CardResponse:
    card = await card_service.create_card(scope, body)
    return CardResponse(card=CardOut.model_validate(card))


@router.get("/{card_id}", response_model=CardResponse)
async def get_card(card_id: UUID, scope: OrgScope = Depends(get_org_scope)) -> CardResponse:
    card = await card_service.get_card(scope, card_id)
    return CardResponse(card=CardOut.model_validate(card))


@router.patch("/{card_id}", response_model=CardResponse, dependencies=[Depends(_admin)])
async def update_card(
    card_id: UUID,
    body: CardUpdate,
    scope: OrgScope = Depends(get_org_scope),
) -> CardResponse:
    card = await card_service.update_card(scope, card_id, body)
    return CardResponse(card=CardOut.model_validate(card))


@router.post("/{card_id}/freeze", response_model=CardResponse, dependencies=[Depends(_admin)])
async def freeze_card(card_id: UUID, scope: OrgScope = Depends(get_org_scope)) -> CardResponse:
    card = await card_service.freeze_card(scope, card_id)
    return CardResponse(card=CardOut.model_validate(card))


@router.post("/{card_id}/unfreeze", response_model=CardResponse, dependencies=[Depends(_admin)])
async def unfreeze_card(card_id: UUID, scope: OrgScope = Depends(get_org_scope)) -> CardResponse:
    card = await card_service.unfreeze_card(scope, card_id)
    return CardResponse(card=CardOut.model_validate(card))


@router.post("/{card_id}/cancel", response_model=CardResponse, dependencies=[Depends(_admin)])
async def cancel_card(card_id: UUID, scope: OrgScope = Depends(get_org_scope)) -> CardResponse:
    card = await card_service.cancel_card(scope, card_id)
    return CardResponse(card=CardOut.model_validate(card))
