from uuid import UUID

from fastapi import APIRouter, Depends

from api.deps import OrgScope, get_org_scope, require_role
from api.models.user import UserRole
from api.schemas.transaction import (
    ApproveRejectRequest,
    TransactionCreate,
    TransactionEventOut,
    TransactionFilters,
    TransactionOut,
    TransactionPolicyResultOut,
    TransactionWithEvents,
)
from api.services import transaction_service

router = APIRouter(prefix="/transactions", tags=["transactions"])

_admin_or_fm = require_role(UserRole.ADMIN, UserRole.FINANCE_MANAGER)
_any_role = require_role(UserRole.ADMIN, UserRole.FINANCE_MANAGER, UserRole.EMPLOYEE)


@router.post("", response_model=TransactionOut, status_code=201)
async def create_transaction(
    body: TransactionCreate,
    scope: OrgScope = Depends(get_org_scope),
) -> TransactionOut:
    txn = await transaction_service.create_transaction(scope, body)
    return TransactionOut.model_validate(txn)


@router.get("", response_model=list[TransactionOut])
async def list_transactions(
    filters: TransactionFilters = Depends(),
    scope: OrgScope = Depends(get_org_scope),
) -> list[TransactionOut]:
    pairs = await transaction_service.list_transactions(scope, filters)
    results: list[TransactionOut] = []
    for txn, verdict in pairs:
        out = TransactionOut.model_validate(txn)
        out.policy_verdict = verdict
        results.append(out)
    return results


@router.get("/{txn_id}", response_model=TransactionWithEvents)
async def get_transaction(
    txn_id: UUID,
    scope: OrgScope = Depends(get_org_scope),
) -> TransactionWithEvents:
    txn, events, policy_result = await transaction_service.get_transaction(scope, txn_id)
    return TransactionWithEvents(
        **TransactionOut.model_validate(txn).model_dump(),
        events=[TransactionEventOut.model_validate(e) for e in events],
        latest_policy_result=(
            TransactionPolicyResultOut.model_validate(policy_result) if policy_result else None
        ),
    )


@router.post("/{txn_id}/approve", response_model=TransactionOut, dependencies=[Depends(_admin_or_fm)])
async def approve_transaction(
    txn_id: UUID,
    body: ApproveRejectRequest,
    scope: OrgScope = Depends(get_org_scope),
) -> TransactionOut:
    txn = await transaction_service.approve_transaction(scope, txn_id, body.reason)
    return TransactionOut.model_validate(txn)


@router.post("/{txn_id}/reject", response_model=TransactionOut, dependencies=[Depends(_admin_or_fm)])
async def reject_transaction(
    txn_id: UUID,
    body: ApproveRejectRequest,
    scope: OrgScope = Depends(get_org_scope),
) -> TransactionOut:
    txn = await transaction_service.reject_transaction(scope, txn_id, body.reason)
    return TransactionOut.model_validate(txn)


@router.get("/{txn_id}/events", response_model=list[TransactionEventOut])
async def list_transaction_events(
    txn_id: UUID,
    scope: OrgScope = Depends(get_org_scope),
) -> list[TransactionEventOut]:
    events = await transaction_service.list_events(scope, txn_id)
    return [TransactionEventOut.model_validate(e) for e in events]
