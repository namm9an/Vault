from uuid import UUID

from fastapi import APIRouter, Depends

from api.deps import OrgScope, get_org_scope, require_role
from api.models.user import UserRole
from api.schemas.reimbursement import (
    ApproveRejectBody,
    ReimbursementCreate,
    ReimbursementFilters,
    ReimbursementOut,
)
from api.services.reimbursement_service import (
    approve_reimbursement,
    create_reimbursement,
    get_reimbursement,
    list_reimbursements,
    mark_paid,
    reject_reimbursement,
)

router = APIRouter(prefix="/reimbursements", tags=["reimbursements"])


@router.post("", response_model=ReimbursementOut, status_code=201)
async def create_route(
    data: ReimbursementCreate,
    scope: OrgScope = Depends(get_org_scope),
):
    return await create_reimbursement(scope, data)


@router.get("", response_model=list[ReimbursementOut])
async def list_route(
    scope: OrgScope = Depends(get_org_scope),
    filters: ReimbursementFilters = Depends(),
):
    return await list_reimbursements(scope, filters)


@router.get("/{reimb_id}", response_model=ReimbursementOut)
async def get_route(
    reimb_id: UUID,
    scope: OrgScope = Depends(get_org_scope),
):
    return await get_reimbursement(scope, reimb_id)


@router.post("/{reimb_id}/approve", response_model=ReimbursementOut)
async def approve_route(
    reimb_id: UUID,
    body: ApproveRejectBody,
    scope: OrgScope = Depends(get_org_scope),
    _=Depends(require_role(UserRole.FINANCE_MANAGER, UserRole.ADMIN)),
):
    return await approve_reimbursement(scope, reimb_id, body.reason)


@router.post("/{reimb_id}/reject", response_model=ReimbursementOut)
async def reject_route(
    reimb_id: UUID,
    body: ApproveRejectBody,
    scope: OrgScope = Depends(get_org_scope),
    _=Depends(require_role(UserRole.FINANCE_MANAGER, UserRole.ADMIN)),
):
    return await reject_reimbursement(scope, reimb_id, body.reason)


@router.post("/{reimb_id}/mark-paid", response_model=ReimbursementOut)
async def mark_paid_route(
    reimb_id: UUID,
    scope: OrgScope = Depends(get_org_scope),
    _=Depends(require_role(UserRole.FINANCE_MANAGER, UserRole.ADMIN)),
):
    return await mark_paid(scope, reimb_id)
