from uuid import UUID

from fastapi import APIRouter, Depends

from api.deps import OrgScope, get_org_scope, require_role
from api.models.user import UserRole
from api.schemas.department import BudgetStatus, DepartmentCreate, DepartmentOut, DepartmentUpdate
from api.services.department_service import (
    create_department,
    delete_department,
    get_budget_status,
    get_department,
    list_departments,
    update_department,
)

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentOut])
async def list_route(
    scope: OrgScope = Depends(get_org_scope),
    _=Depends(require_role(UserRole.ADMIN, UserRole.FINANCE_MANAGER)),
):
    return await list_departments(scope)


@router.post("", response_model=DepartmentOut, status_code=201)
async def create_route(
    data: DepartmentCreate,
    scope: OrgScope = Depends(get_org_scope),
    _=Depends(require_role(UserRole.ADMIN)),
):
    return await create_department(scope, data)


@router.get("/{dept_id}", response_model=DepartmentOut)
async def get_route(
    dept_id: UUID,
    scope: OrgScope = Depends(get_org_scope),
    _=Depends(require_role(UserRole.ADMIN, UserRole.FINANCE_MANAGER)),
):
    return await get_department(scope, dept_id)


@router.patch("/{dept_id}", response_model=DepartmentOut)
async def update_route(
    dept_id: UUID,
    data: DepartmentUpdate,
    scope: OrgScope = Depends(get_org_scope),
    _=Depends(require_role(UserRole.ADMIN)),
):
    return await update_department(scope, dept_id, data)


@router.delete("/{dept_id}", status_code=204)
async def delete_route(
    dept_id: UUID,
    scope: OrgScope = Depends(get_org_scope),
    _=Depends(require_role(UserRole.ADMIN)),
):
    await delete_department(scope, dept_id)


@router.get("/{dept_id}/budget-status", response_model=BudgetStatus)
async def budget_status_route(
    dept_id: UUID,
    scope: OrgScope = Depends(get_org_scope),
    _=Depends(require_role(UserRole.ADMIN, UserRole.FINANCE_MANAGER)),
):
    return await get_budget_status(scope, dept_id)
