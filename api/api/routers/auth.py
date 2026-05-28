from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.base import get_db
from api.deps import CurrentUser, get_current_user
from api.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MeResponse,
    OkResponse,
    OrgOut,
    RefreshRequest,
    SignupRequest,
    TokenPair,
    TokenRefreshResponse,
    UserOut,
)
from api.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenPair, status_code=201)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    user, _org, access, refresh = await auth_service.signup(
        db,
        org_name=body.org_name,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
    )
    return TokenPair(access_token=access, refresh_token=refresh, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenPair)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    user, _org, access, refresh = await auth_service.login(
        db, email=body.email, password=body.password
    )
    return TokenPair(access_token=access, refresh_token=refresh, user=UserOut.model_validate(user))


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenRefreshResponse:
    access, new_refresh = await auth_service.refresh_tokens(db, refresh_token=body.refresh_token)
    return TokenRefreshResponse(access_token=access, refresh_token=new_refresh)


@router.post("/logout", response_model=OkResponse)
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)) -> OkResponse:
    await auth_service.logout(db, refresh_token=body.refresh_token)
    return OkResponse()


@router.get("/me", response_model=MeResponse)
async def me(
    cu: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    user, org = await auth_service.get_user_and_org(db, cu.user_id)
    return MeResponse(user=UserOut.model_validate(user), org=OrgOut.model_validate(org))
