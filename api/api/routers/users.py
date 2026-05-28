from uuid import UUID

from fastapi import APIRouter, Depends

from api.deps import OrgScope, get_org_scope, require_role
from api.models.user import UserRole
from api.schemas.auth import OkResponse, UserOut
from api.schemas.user import UserInvite, UserInviteResponse, UserListResponse, UserResponse, UserUpdate
from api.services import user_service

router = APIRouter(prefix="/users", tags=["users"])

_admin = require_role(UserRole.ADMIN)


@router.get("", response_model=UserListResponse)
async def list_users(scope: OrgScope = Depends(get_org_scope)) -> UserListResponse:
    users = await user_service.list_users(scope)
    return UserListResponse(items=[UserOut.model_validate(u) for u in users])


@router.post("", response_model=UserInviteResponse, status_code=201, dependencies=[Depends(_admin)])
async def invite_user(
    body: UserInvite,
    scope: OrgScope = Depends(get_org_scope),
) -> UserInviteResponse:
    user, token = await user_service.invite_user(scope, body)
    return UserInviteResponse(user=UserOut.model_validate(user), invite_token=token)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, scope: OrgScope = Depends(get_org_scope)) -> UserResponse:
    # EMPLOYEE can only view themselves
    if scope.role == UserRole.EMPLOYEE and user_id != scope.user_id:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    user = await user_service.get_user(scope, user_id)
    return UserResponse(user=UserOut.model_validate(user))


@router.patch("/{user_id}", response_model=UserResponse, dependencies=[Depends(_admin)])
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    scope: OrgScope = Depends(get_org_scope),
) -> UserResponse:
    user = await user_service.update_user(scope, user_id, body)
    return UserResponse(user=UserOut.model_validate(user))


@router.delete("/{user_id}", response_model=OkResponse, dependencies=[Depends(_admin)])
async def delete_user(user_id: UUID, scope: OrgScope = Depends(get_org_scope)) -> OkResponse:
    # Soft delete — sets is_active=False
    from api.schemas.user import UserUpdate
    await user_service.update_user(scope, user_id, UserUpdate(is_active=False))
    return OkResponse()
