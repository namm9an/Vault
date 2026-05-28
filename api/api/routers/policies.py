from uuid import UUID

from fastapi import APIRouter, Depends

from api.deps import OrgScope, get_org_scope, require_role
from api.models.user import UserRole
from api.schemas.policy import PolicyCreate, PolicyOut, PolicyUpdate
from api.services import policy_service

router = APIRouter(prefix="/policies", tags=["policies"])

_admin_or_fm = require_role(UserRole.ADMIN, UserRole.FINANCE_MANAGER)
_admin_only = require_role(UserRole.ADMIN)


@router.get("", response_model=list[PolicyOut])
async def list_policies(
    scope: OrgScope = Depends(get_org_scope),
    _: object = Depends(_admin_or_fm),
):
    return await policy_service.list_policies(scope)


@router.post("", response_model=PolicyOut, status_code=201)
async def create_policy(
    data: PolicyCreate,
    scope: OrgScope = Depends(get_org_scope),
    _: object = Depends(_admin_only),
):
    return await policy_service.create_policy(scope, data)


@router.get("/{policy_id}", response_model=PolicyOut)
async def get_policy(
    policy_id: UUID,
    scope: OrgScope = Depends(get_org_scope),
    _: object = Depends(_admin_or_fm),
):
    return await policy_service.get_policy(scope, policy_id)


@router.patch("/{policy_id}", response_model=PolicyOut)
async def update_policy(
    policy_id: UUID,
    data: PolicyUpdate,
    scope: OrgScope = Depends(get_org_scope),
    _: object = Depends(_admin_only),
):
    return await policy_service.update_policy(scope, policy_id, data)


@router.delete("/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: UUID,
    scope: OrgScope = Depends(get_org_scope),
    _: object = Depends(_admin_only),
):
    await policy_service.delete_policy(scope, policy_id)
